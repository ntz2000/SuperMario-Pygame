"""Tile grid: storage, collision queries, chunked rendering, level JSON loading.

Tiles are stored as one string per row. Rendering is per-chunk (a chunk is a vertical
strip of tiles) so a level only pays for the strips it actually shows, and each strip
is rasterized once then blitted.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field

import pygame

from .physics import ONE_WAY, SOLID
from .tiles import TERRAIN_FAMILIES, TILE, Tile, TileTable, default_table

CHUNK = 16  # tiles per rendered strip


class TileMap:
    """A rectangular grid of tile codes that answers collision and draw queries."""

    def __init__(self, rows: list[str], table: TileTable | None = None, theme: str = ""):
        self.rows = [list(r) for r in rows]
        self.table = table or default_table()
        self.theme = theme
        self.h = len(self.rows)
        self.w = max((len(r) for r in self.rows), default=0)
        self._chunks: dict[int, pygame.Surface] = {}
        self.assets = None  # set by a scene via bind()

    # -- queries -----------------------------------------------------------------------
    @property
    def pixel_size(self) -> tuple[int, int]:
        return (self.w * TILE, self.h * TILE)

    def at(self, tx: int, ty: int) -> str:
        if 0 <= ty < self.h and 0 <= tx < len(self.rows[ty]):
            return self.rows[ty][tx] or ""
        return ""

    def tile(self, tx: int, ty: int) -> Tile | None:
        """Resolved tile, with the level's palette already applied to terrain."""
        code = self.at(tx, ty)
        if not code:
            return None
        base = self.table.get(code)
        if base is None:
            return None
        if self.theme and base.name in TERRAIN_FAMILIES:
            return self.table.terrain(code, self.theme)
        return base

    def code_at(self, tx: int, ty: int) -> str:
        return self.at(tx, ty)

    def def_of(self, code: str) -> Tile | None:
        return self.table.get(code)

    def set(self, tx: int, ty: int, code: str):
        self.rows[ty][tx] = code
        self._chunks.pop(tx // CHUNK, None)

    def cell_rect(self, tx: int, ty: int) -> pygame.Rect:
        return pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)

    def solid_cells(self, rect: pygame.Rect):
        """Collider protocol: yield ``(cell_rect, kind)`` for cells touching ``rect``."""
        x0 = (rect.left - 1) // TILE
        x1 = (rect.right + 1) // TILE
        y0 = (rect.top - 1) // TILE
        y1 = (rect.bottom + 1) // TILE
        for ty in range(max(0, y0), min(self.h, y1 + 1)):
            for tx in range(max(0, x0), min(self.w, x1 + 1)):
                code = self.at(tx, ty)
                if not code:
                    continue
                tile = self.table.get(code)
                if tile is None or not tile.kind:
                    continue
                yield self.cell_rect(tx, ty), tile.kind

    def cells_in(self, rect: pygame.Rect):
        for ty in range(max(0, rect.top // TILE), min(self.h, rect.bottom // TILE + 1)):
            for tx in range(max(0, rect.left // TILE), min(self.w, rect.right // TILE + 1)):
                code = self.at(tx, ty)
                if code:
                    yield (tx, ty), self.table.get(code)

    def friction_at(self, rect: pygame.Rect) -> float:
        """脚下瓦片的摩擦系数（取触到的最低值=最滑的）。"""
        best = 1.0
        for _cell, tile in self.cells_in(rect):
            if tile is not None and tile.solid:
                best = min(best, getattr(tile, "friction", 1.0))
        return best

    def solid_at(self, rect: pygame.Rect, one_way: bool = True) -> bool:
        """Is there anything solid in ``rect``? Handy for "is there a wall/pit ahead"."""
        for _cell, kind in self.solid_cells(rect):
            if kind == SOLID or (one_way and kind == ONE_WAY):
                return True
        return False

    # -- rendering ---------------------------------------------------------------------
    def bind(self, assets):
        self.assets = assets
        self._chunks.clear()

    def variant(self, tx: int, ty: int, tile: Tile) -> str:
        """Pick the art variant from the neighbour mask (auto-tile)."""
        above = self.at(tx, ty - 1)
        exposed = above not in self.table.tiles
        if exposed and self.at(tx - 1, ty) != tile.code and self.at(tx + 1, ty) != tile.code:
            return "cap"
        if exposed:
            return "top"
        return "fill"

    def chunk(self, index: int, bumps: dict | None = None, bump_time: float = 0.24):
        """Rasterize tile strip ``index``; cells in ``bumps`` get a rising animation.

        Chunks containing active bumps are rebuilt every frame (cheap: 16x15 cells),
        the rest come from the render cache. 条带以 16px 艺术分辨率光栅化，
        再按 RES_SCALE 放大缓存——高清渲染的同时碰撞/逻辑完全不变。
        """
        from ..engine.res import RES_SCALE
        if index in self._chunks and not bumps:
            return self._chunks[index]
        w = min(CHUNK, max(0, self.w - index * CHUNK))
        # 直接按高清分辨率光栅化：art 本身就是 TILE×RES_SCALE 的
        surf = pygame.Surface((max(1, w) * TILE * RES_SCALE,
                               self.h * TILE * RES_SCALE), pygame.SRCALPHA)
        for tx in range(index * CHUNK, index * CHUNK + w):
            for ty in range(self.h):
                tile = self.tile(tx, ty)
                if tile is None or not tile.art or tile.decoration or tile.hidden:
                    continue
                dy = 0
                if bumps and (tx, ty) in bumps:
                    # 顶起动画：剩余时间比例 -> 上移 0..6px 的正弦
                    k = 1.0 - bumps[(tx, ty)] / bump_time
                    dy = -round(math.sin(min(1.0, k) * math.pi) * 6)
                art = self.assets.sprite(f"{tile.art}.{self.variant(tx, ty, tile)}",
                                        **tile.colors()).surface
                surf.blit(art, ((tx * TILE - index * CHUNK * TILE) * RES_SCALE,
                                (ty * TILE + dy) * RES_SCALE))
        if not bumps:
            self._chunks[index] = surf
        return surf

    def draw(self, target: pygame.Surface, view: pygame.Rect, bumps: dict | None = None):
        if self.assets is None:
            return
        from ..engine.res import RES_SCALE
        first = max(0, (view.left // TILE) // CHUNK)
        last = min((self.w - 1) // CHUNK, (view.right // TILE) // CHUNK)
        # 只有含顶起格子的列需要绕过缓存
        hot = {tx // CHUNK for (tx, _ty) in (bumps or ())}
        for i in range(first, last + 1):
            strip_bumps = {(tx, ty): t for (tx, ty), t in (bumps or {}).items()
                          if tx // CHUNK == i} or None
            surf = self.chunk(i) if (strip_bumps is None and i not in hot) \
                else self.chunk(i, strip_bumps)
            target.blit(surf, ((i * CHUNK * TILE - view.left) * RES_SCALE,
                               -view.top * RES_SCALE))

    # -- io ----------------------------------------------------------------------------
    @classmethod
    def load(cls, path: str, table: TileTable | None = None):
        with open(path) as fh:
            data = json.load(fh)
        return cls(data["rows"], table), data

    def to_json(self, path: str, **extra):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump({"tile": TILE, "rows": ["".join(r) for r in self.rows], **extra}, fh, indent=1)
