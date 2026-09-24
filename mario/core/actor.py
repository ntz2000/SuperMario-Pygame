"""Base class for anything that moves inside a level.

An actor owns a :class:`~mario.core.physics.Body`, an animation state, and two methods
(``update`` / ``draw``). The level scene drives them in list order and hands them a
``world`` object exposing ``tilemap``, ``camera``, ``spawn``, ``sfx`` and ``fx``.
"""
from __future__ import annotations

import pygame

from .physics import Body


class Actor:
    art: str = ""            # asset id prefix; frames come from "<art>.<anim>"
    anim: str = "idle"
    fps: float = 9.0
    z: int = 10
    collides_player: bool = True

    def __init__(self, world, x: float, y: float, **kw):
        self.world = world
        self.body = Body(x=x, y=y, **{"w": type(self).w, "h": type(self).h, **kw.get("body", {})})
        if "vx" in kw:
            self.body.vx = kw["vx"]
        self.alive = True
        self.removed = False
        self.anim = kw.get("anim", type(self).anim)
        self.t = 0.0
        self.flip = False

    w: int = 12
    h: int = 14

    # -- helpers ------------------------------------------------------------------------
    @property
    def rect(self) -> pygame.Rect:
        return self.body.rect

    @property
    def frame(self) -> int:
        """动画帧号。fps 是每秒帧数（历史 bug：曾写成 t*fps/60，动画慢 60 倍
        ——这就是"动作僵硬"的元凶）。"""
        return int(self.t * self.fps)

    _bottom_cache: dict = {}     # class 级：asset 帧 → 精灵底部实体行号

    def frame_surf(self, anim: str | None = None) -> pygame.Surface:
        """Frames live under ``<art>.<anim>``; art with no per-state art falls back."""
        from ..engine.assets import registered_ids
        want, have = f"{self.art}.{anim or self.anim}", self.art
        asset = self.world.assets.sprite(want if want in registered_ids() else have)
        return asset.frame(self.frame)

    def _sprite_bottom(self, surf) -> int:
        """精灵在贴图内的最低实体行（用于贴地绘制，修"悬空"）。

        抠图后的帧底部常有 1-2px 空边（GIF 切分的边距），按贴图高度
        对齐会让脚浮起来。检测每帧实底并缓存。
        """
        key = id(surf)
        b = self._bottom_cache.get(key)
        if b is None:
            import numpy as _np
            import pygame as _pg
            arr = _np.frombuffer(_pg.image.tobytes(surf, "RGBA"), dtype="uint8")
            arr = arr.reshape(surf.get_height(), -1, 4)
            rows = (arr[..., 3] > 60).any(axis=1)
            nz = _np.where(rows)[0]
            b = int(nz[-1]) if len(nz) else surf.get_height() - 1
            self._bottom_cache[key] = b
        return b

    def set_anim(self, name: str, reset: bool = True):
        if name != self.anim:
            self.anim = name
            if reset:
                self.t = 0.0

    # -- lifecycle ----------------------------------------------------------------------
    def update(self, world):
        self.t += 1 / 60.0

    def draw(self, target: pygame.Surface, cam):
        surf = self.frame_surf()
        if self.flip:
            surf = pygame.transform.flip(surf, True, False)
        # 贴地绘制：精灵最低实体行精确踩在 body.y（历史 +1 偏移让脚悬 1px）
        bottom = self._sprite_bottom(surf)
        x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                             self.body.y - bottom - 0.5)
        self._draw_shadow(target, cam)
        target.blit(surf, (x, y))

    def _draw_shadow(self, target, cam):
        """脚下椭圆软影（NSMB 标志特征：所有角色带影）。

        贴地：宽 72% 碰撞盒、不透明；空中：缩小 38% 且更透明。
        """
        b = self.body
        from ..engine.res import RES_SCALE as RS
        if b.on_ground:
            scale, alpha = 1.0, 120
        else:
            scale, alpha = 0.62, 60
        rw = max(4, int(b.w * 0.78 * RS * scale))
        rh = max(2, int(3.2 * RS * scale))
        cx, cy = cam.to_screen(b.x, b.y + 1)
        shadow = pygame.Surface((rw * 2 + 2, rh * 2 + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (8, 10, 22, alpha),
                            shadow.get_rect().inflate(-2, -2))
        target.blit(shadow, (cx - rw - 1, cy - rh - 1))

    def touch(self, other: "Actor") -> bool:
        return self.rect.colliderect(other.rect)

    def kill(self):
        self.alive = False
        self.removed = True
