"""Axis-separated swept AABB movement against a tile grid.

Positions are stored as bottom-center in art pixels (floats) because that is what
platformer code wants: ``y`` is the feet, so ground contact and sprite anchoring are
both direct. Movement is resolved one axis per pass, which is stable at these speeds
and gives clean wall/ceil/ground contact lists for blocks to react to.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol

import pygame


@dataclass
class Contact:
    """What an entity touched this frame, so actors can react (bump a block, etc)."""

    ground: list[pygame.Rect] = field(default_factory=list)
    ceiling: list[pygame.Rect] = field(default_factory=list)
    wall: list[pygame.Rect] = field(default_factory=list)
    platform: bool = False  # landed on a one-way platform

    @property
    def any(self) -> bool:
        return bool(self.ground or self.ceiling or self.wall)


SOLID = "solid"     # full tile, blocks on every axis
ONE_WAY = "one_way"  # thin top surface, blocks downward falls only

EPS = 0.05  # 子像素防抖：贴面 0.05px 内的接触不算穿透


def _hit(body: Body, cell: pygame.Rect) -> bool:
    """浮点盒与格子的真实重叠（区别于 solid_cells 的宽容探测）。

    ``Body.rect`` 会取整，而贴地吸附会留下 0.001px 的"穿透"，取整后无法区分
    真碰撞与贴面。用浮点盒 + EPS 判断，站立时地面不会被当成横墙。
    """
    left = body.x - body.w / 2
    right = body.x + body.w / 2
    top = body.y - body.h
    bottom = body.y
    return (cell.left < right - EPS and cell.right > left + EPS
            and cell.top < bottom - EPS and cell.bottom > top + EPS)


class Collider(Protocol):
    """Anything that can answer "which cells overlap this rect, and how solid are they"."""

    def solid_cells(self, rect: pygame.Rect) -> Iterable[tuple[pygame.Rect, str]]: ...


@dataclass
class Body:
    """Axis-aligned moving box with the state a platformer actor needs."""

    x: float = 0.0
    y: float = 0.0  # feet (bottom edge)
    w: int = 8
    h: int = 14
    vx: float = 0.0
    vy: float = 0.0
    facing: int = 1
    on_ground: bool = False
    on_wall: int = 0  # -1 wall on left, 1 on right, 0 none
    hit_ceiling: bool = False
    gravity_scale: float = 1.0
    active: bool = True
    tag: str = ""

    @property
    def rect(self) -> pygame.Rect:
        """Integer world box derived from the float position."""
        return pygame.Rect(round(self.x - self.w / 2), round(self.y - self.h), self.w, self.h)

    @rect.setter
    def rect(self, r: pygame.Rect):
        self.x = r.centerx
        self.y = r.bottom

    @property
    def center(self) -> tuple[float, float]:
        return (self.x, self.y - self.h / 2)

    @property
    def bottom(self) -> float:
        return self.y

    @property
    def top(self) -> float:
        return self.y - self.h

    def overlaps(self, other: pygame.Rect) -> bool:
        return self.rect.colliderect(other)


def move_x(body: Body, grid: Collider) -> list[pygame.Rect]:
    """Integrate horizontal motion; returns solid cells the body pressed into."""
    body.on_wall = 0
    if body.vx == 0:
        return []
    body.x += body.vx
    hits: list[pygame.Rect] = []
    for cell, kind in grid.solid_cells(body.rect):
        if kind != SOLID or not _hit(body, cell):
            continue
        hits.append(cell)
        body.x = cell.left - body.w / 2 + 0.001 if body.vx > 0 else cell.right + body.w / 2 - 0.001
        body.on_wall = 1 if body.vx > 0 else -1
    if hits:
        body.vx = 0.0
    return hits


def move_y(body: Body, grid: Collider) -> Contact:
    """Integrate vertical motion; sets ``on_ground`` / ``hit_ceiling`` on ``body``.

    ``body.y`` is the feet, so the previous bottom is simply ``body.y`` before the
    step, which is exactly what one-way platforms need to test against.
    """
    if body.vy == 0:
        return Contact()
    prev_bottom = body.y
    body.y += body.vy
    c = Contact()
    for cell, kind in grid.solid_cells(body.rect):
        if kind == SOLID:
            blocking = _hit(body, cell)
        elif kind == ONE_WAY:
            blocking = _hit(body, cell) and body.vy > 0 and prev_bottom <= cell.top + 1.0
        else:
            blocking = False
        if not blocking:
            continue
        if body.vy > 0:
            body.y = cell.top + 0.001
            c.ground.append(cell)
            c.platform = c.platform or kind == ONE_WAY
        else:
            body.y = cell.bottom + body.h - 0.001
            c.ceiling.append(cell)
        r = body.rect
    if c.ground:
        body.on_ground = True
        body.vy = 0.0
    elif c.ceiling:
        body.hit_ceiling = True
        body.vy = 0.0
    else:
        body.on_ground = False
        body.hit_ceiling = False
    if c.platform:
        body.on_ground = True
    return c


def grounded(grid: Collider, body: Body) -> bool:
    """Is there floor directly under the feet? Used for coyote-time checks."""
    feet = pygame.Rect(round(body.x - body.w / 2), round(body.y), body.w, 1)
    return any(kind == SOLID or kind == ONE_WAY for _cell, kind in grid.solid_cells(feet))
