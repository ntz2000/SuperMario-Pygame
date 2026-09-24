"""Pixel-art rasterizer used for every sprite in the game.

Shapes are drawn with PIL at ``SS``x supersampling, then box-downsampled to art
pixels.  The result is a crisp-edged but slightly soft sprite, close to the
glossy cell-shaded look of the "New Super Mario" era sprites.  Edge treatment
(outline, top-left rim light, bottom-right shade) is derived from the alpha
mask in numpy, so generators only have to supply flat colored shapes.
"""
from __future__ import annotations

import hashlib
from typing import Sequence

import numpy as np
import pygame
from PIL import Image, ImageDraw

SS = 4  # supersample factor: shapes are drawn at 4 art pixels per art pixel


def hexc(value: str) -> tuple[int, int, int, int]:
    """``'#c05a2e'`` -> ``(192, 90, 46, 255)``."""
    value = value.lstrip("#")
    parts = [int(value[i:i + 2], 16) for i in range(0, len(value), 2)]
    while len(parts) < 4:
        parts.append(255)
    return tuple(parts)  # type: ignore[return-value]


def shade(color, factor: float) -> tuple[int, int, int, int]:
    """Scale a color's brightness. ``factor > 1`` lightens toward white."""
    r, g, b, a = color[0], color[1], color[2], color[3] if len(color) > 3 else 255
    if factor >= 1.0:
        t = (factor - 1.0)
        comps = [c + (255 - c) * t for c in (r, g, b)]
    else:
        comps = [c * factor for c in (r, g, b)]
    return tuple(int(min(255, max(0, round(c)))) for c in comps) + (a,)  # type: ignore[return-value]


def mix(a, b, t: float) -> tuple[int, int, int, int]:
    out = [round(a[i] + (b[i] - a[i]) * t) for i in range(len(a))]
    return tuple(out)  # type: ignore[return-value]


def _shift(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """Shift a boolean mask, filling vacated rows/columns with False."""
    out = np.zeros_like(mask)
    ys, xs = mask.shape
    src_y = slice(max(0, dy), ys + min(0, dy))
    dst_y = slice(max(0, -dy), ys - max(0, dy))
    src_x = slice(max(0, dx), xs + min(0, dx))
    dst_x = slice(max(0, -dx), xs - max(0, dx))
    out[dst_y, dst_x] = mask[src_y, src_x]
    return out


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx or dy:
                out |= _shift(out, dx, dy)
    return out


class Canvas:
    """Draw-ordered shape buffer that downsamples into an art-pixel sprite."""

    def __init__(self, size, ss: int = SS):
        self.size = (int(size[0]), int(size[1]))
        self.ss = ss
        self._img = Image.new("RGBA", (self.size[0] * ss, self.size[1] * ss), (0, 0, 0, 0))
        self._draw = ImageDraw.Draw(self._img)

    # -- shape helpers ---------------------------------------------------------------
    def rect(self, box, fill):
        self._draw.rectangle(self._box(box), fill=fill)

    def rrect(self, box, radius, fill):
        box = self._box(box)
        self._draw.rounded_rectangle(box, radius=radius * self.ss, fill=fill)

    def ellipse(self, box, fill, box_width: int = 0, outline=None):
        self._draw.ellipse(self._box(box), fill=fill, width=box_width * self.ss, outline=outline)

    def pie(self, box, start, end, fill):
        self._draw.pieslice(self._box(box), start, end, fill=fill)

    def poly(self, points: Sequence[Sequence[float]], fill):
        pts = [(p[0] * self.ss, p[1] * self.ss) for p in points]
        self._draw.polygon(pts, fill=fill)

    def line(self, points: Sequence[Sequence[float]], width: float, fill, joint="curve"):
        pts = [(p[0] * self.ss, p[1] * self.ss) for p in points]
        self._draw.line(pts, fill=fill, width=max(1, round(width * self.ss)), joint=joint)

    def arc(self, box, start, end, width, fill):
        self._draw.arc(self._box(box), start, end, fill=fill, width=round(width * self.ss))

    def paste(self, img: Image.Image, at):
        img = img.resize((img.width * self.ss, img.height * self.ss), Image.NEAREST)
        self._img.paste(img, (round(at[0] * self.ss), round(at[1] * self.ss)), img)

    def mask(self, mask: "Canvas"):
        """Composite another canvas in, using its alpha as a mask."""
        self._img.paste(mask._img, (0, 0), mask._img)

    def _box(self, box):
        """Boxes are exclusive float-art-pixel rects; scale to the supersampled grid."""
        s = self.ss
        return (box[0] * s, box[1] * s, box[2] * s, box[3] * s)

    # -- finish ----------------------------------------------------------------------
    def finish(self, outline: float = 1.0, light=(-1.0, -1.0), rim: float = 0.30,
               shade_edge: float = 0.16, out_scale: int = 1) -> pygame.Surface:
        """Downsample, then add outline + rim light + core shade; return a Surface.

        ``out_scale`` 为输出分辨率倍率：内部以 SS 倍超采样画形，一步缩到
        size×out_scale——高清模式（RES_SCALE=2）下精灵天生就是高清的。
        """
        w, h = self.size[0] * out_scale, self.size[1] * out_scale
        img = self._img.resize((w, h), Image.BOX)
        arr = np.asarray(img).astype(np.float32)
        alpha = arr[..., 3] / 255.0
        solid = alpha > 0.35

        if outline > 0:
            ring = _dilate(solid, max(1, int(round(outline * out_scale)))) & ~solid
            # Edge pixels keep a smear of the shape's own color after BOX resize;
            # darken it so outlines inherit local hue. Fully clear pixels go neutral.
            base = arr[ring, :3] * 0.40
            empty = arr[ring, :3].sum(axis=-1) < 30
            base[empty] = 46
            arr[ring, 3] = 255

        if light is not None:
            lx, ly = light
            r = max(1, int(round(outline * out_scale)))
            left = solid & _shift(~solid, -r, 0)
            right = solid & _shift(~solid, r, 0)
            top = solid & _shift(~solid, 0, -r)
            bottom = solid & _shift(~solid, 0, r)
            lit = np.zeros_like(solid)
            dark = np.zeros_like(solid)
            if ly < 0:
                lit |= top
            if ly > 0:
                dark |= bottom
            if lx < 0:
                lit |= left
            if lx > 0:
                lit |= right
            if lx > 0:
                dark |= left
            if lx < 0:
                dark |= right
            dark |= _dilate(top, 1) & ~top & solid & ~lit
            arr[lit, :3] = np.minimum(255, arr[lit, :3] * (1 + rim))
            arr[dark, :3] *= (1 - shade_edge)

        out = np.dstack([np.round(arr[..., :3]), np.round(arr[..., 3])]).astype(np.uint8)
        # outline 的描边若触到画布边界会连成方框（"黑框"bug）。
        # 只清除"原本透明、被描边点亮"的边界像素：solid 形状本体贴边不受影响。
        if outline > 0 and out.shape[0] > 4 and out.shape[1] > 4:
            edge = np.zeros(solid.shape, bool)
            edge[0, :] = edge[-1, :] = True
            edge[:, 0] = edge[:, -1] = True
            added_by_ring = ~solid & edge   # 边界上非形状本体的像素=描边产物
            out[added_by_ring, 3] = 0
        surf = pygame.image.frombuffer(out.tobytes(), (w, h), "RGBA")
        surf.set_colorkey(None)
        return surf

    def image(self) -> Image.Image:
        return self._img.resize(self.size, Image.BOX)


def strip(frames: Sequence[pygame.Surface]) -> pygame.Surface:
    """Pack frames side by side; ``Asset`` crops them back out by index."""
    w = max(f.get_width() for f in frames)
    h = max(f.get_height() for f in frames)
    out = pygame.Surface((w * len(frames), h), pygame.SRCALPHA)
    for i, f in enumerate(frames):
        out.blit(f, (i * w, 0))
    return out
