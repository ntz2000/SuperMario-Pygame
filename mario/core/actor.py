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

    def frame_surf(self, anim: str | None = None) -> pygame.Surface:
        """Frames live under ``<art>.<anim>``; art with no per-state art falls back."""
        from ..engine.assets import registered_ids
        want, have = f"{self.art}.{anim or self.anim}", self.art
        asset = self.world.assets.sprite(want if want in registered_ids() else have)
        return asset.frame(self.frame)

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
        x, y = cam.to_screen(self.body.x - surf.get_width() / 2, self.body.y - surf.get_height())
        target.blit(surf, (x, y))

    def touch(self, other: "Actor") -> bool:
        return self.rect.colliderect(other.rect)

    def kill(self):
        self.alive = False
        self.removed = True
