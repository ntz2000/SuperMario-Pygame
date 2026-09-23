"""Screen-space camera with deadzone follow, look-ahead and shake."""
from __future__ import annotations

import math

import pygame


class Camera:
    """Scrolling window over a level, in art pixels.

    ``view`` is the internal render size, ``bounds`` the level pixel rect. The
    deadzone keeps the world feeling planted while the hero leads the frame, which
    is what makes an NSMB camera read as confident rather than floaty.
    """

    def __init__(self, view, bounds, ease: float = 0.22):
        self.view = (int(view[0]), int(view[1]))
        self.bounds = pygame.Rect(bounds)
        self.pos = [float(self.bounds.left), float(self.bounds.top)]
        self.zone = (self.view[0] * 0.30, self.view[1] * 0.30)
        self.ease = ease
        self.shake = 0.0
        self._t = 0

    def clamp(self, x: float, y: float) -> tuple[float, float]:
        if self.bounds.width > self.view[0]:
            x = max(self.bounds.left, min(x, self.bounds.right - self.view[0]))
        else:
            x = self.bounds.left + (self.bounds.width - self.view[0]) / 2
        if self.bounds.height > self.view[1]:
            y = max(self.bounds.top, min(y, self.bounds.bottom - self.view[1]))
        else:
            y = self.bounds.top + (self.bounds.height - self.view[1]) / 2
        return x, y

    def center_on(self, point):
        self.pos = list(self.clamp(point[0] - self.view[0] / 2, point[1] - self.view[1] / 2))

    def follow(self, rect: pygame.Rect, vx: float = 0.0, vy: float = 0.0, snap: bool = False):
        """Keep ``rect`` inside a view-relative deadzone; lead the way while running."""
        lead = max(-self.view[0] * 0.12, min(self.view[0] * 0.12, vx * 3.4))
        zx = self.pos[0] + (self.view[0] - self.zone[0]) / 2 + lead
        dx = 0.0
        if rect.left < zx:
            dx = rect.left - zx
        elif rect.right > zx + self.zone[0]:
            dx = rect.right - (zx + self.zone[0])
        zy = self.pos[1] + (self.view[1] - self.zone[1]) / 2
        dy = 0.0
        if rect.top < zy:
            dy = rect.top - zy
        elif rect.bottom > zy + self.zone[1]:
            dy = rect.bottom - (zy + self.zone[1])
        # 横向硬跟随；竖向带缓动，snap=True 时进场直接对齐
        self.pos[0], self.pos[1] = self.clamp(
            self.pos[0] + dx, self.pos[1] + dy * (1.0 if snap else self.ease))

    def update(self, rect: pygame.Rect, vx: float = 0.0, snap: bool = False):
        self.follow(rect, vx, snap=snap)

    # -- accessors ---------------------------------------------------------------------
    @property
    def offset(self) -> tuple[int, int]:
        self._t += 1
        if self.shake > 0.05:
            self.shake *= 0.86
            jx = math.sin(self._t * 1.7) * self.shake
            jy = math.cos(self._t * 2.3) * self.shake
            return (round(self.pos[0] + jx), round(self.pos[1] + jy))
        self.shake = 0.0
        return (round(self.pos[0]), round(self.pos[1]))

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        ox, oy = self.offset
        return (round(x - ox), round(y - oy))

    def world_rect(self, rect: pygame.Rect) -> pygame.Rect:
        ox, oy = self.offset
        return rect.move(-ox, -oy)

    @property
    def view_rect(self) -> pygame.Rect:
        return pygame.Rect(round(self.pos[0]), round(self.pos[1]), *self.view)
