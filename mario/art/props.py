"""Enemy, item, effect and HUD sprites.

Each generator is small and literal: a handful of shapes per actor, with the shading
handled by :class:`Canvas.finish`.  Frames that animate are registered with ``frames=N``
and the registry stores them side by side.
"""
from __future__ import annotations

import math

from ..engine.assets import register
from ..engine.ink import Canvas, hexc, mix

BROWN = hexc("#a85a28")
BROWN_D = hexc("#6b3410")
CREAM = hexc("#f0d9a8")
GREEN = hexc("#3fa535")
YELLOW = hexc("#f6c95c")


def _eyes(c: Canvas, cx, cy, r=1.6, angry=True):
    for s in (-1, 1):
        c.ellipse((cx + s * r * 2.1 - r, cy - r, cx + s * r * 2.1 + r, cy + r), hexc("#fff8f0"))
        c.ellipse((cx + s * r * 2.1 - r * .5, cy - r * .6, cx + s * r * 2.1 + r * .5, cy + r * .6),
                  hexc("#2a2233"))


def goomba(frame: int = 0):
    c = Canvas((14, 14))
    s = 1.0 if frame % 2 == 0 else 0.94
    c.ellipse((1, 1, 13, 10 + 2 * s), BROWN)
    c.pie((1, 2, 13, 12), 180, 360, mix(BROWN, CREAM, 0.35))
    _eyes(c, 7, 6, 1.5)
    for i, x in enumerate((1.5, 8.5)):
        off = 0.8 if frame % 4 < 2 else -0.4
        c.rrect((x + off, 10.5, x + 4.5 + off, 14), 1.6, BROWN_D)
    return c


def koopa(frame: int = 0, shell=GREEN, trim=CREAM):
    c = Canvas((14, 18))
    c.ellipse((2, 6, 12, 17), shell)
    c.ellipse((4, 8, 10, 15), trim)
    c.ellipse((4, 1, 11, 7), mix(shell, (255, 255, 255, 255), 0.35))
    c.pie((7, 0, 13, 5), 250, 30, mix(shell, (0, 0, 0, 255), 0.2))
    _eyes(c, 9.5, 3, 1.2)
    c.ellipse((1, 14, 6, 18), mix(trim, (0, 0, 0, 255), 0.05))
    c.line([(6, 12), (9 + math.sin(frame), 16)], 2.2, shell)
    return c


def shell(frame: int = 0, color="#3fa535"):
    """龟壳：圆顶 + 花纹，滑行时旋转靠帧轮换。"""
    c = Canvas((14, 10))
    body = hexc(color)
    c.pie((1, 0, 13, 14), 180, 360, body)
    c.ellipse((3, 3, 11, 9), mix(body, (0, 0, 0, 255), 0.25))
    c.ellipse((5, 1, 9, 7), mix(body, (255, 255, 255, 255), 0.30))
    c.rect((0, 7, 14, 10), mix(body, (0, 0, 0, 255), 0.35))
    c.line([(2, 4), (7, 2), (12, 4)], 1.0, mix(body, (255, 255, 255, 255), 0.4))
    return c


def piranha(frame: int = 0):
    c = Canvas((14, 22))
    open_ = 1.0 if frame % 2 == 0 else 0.35
    c.line([(7, 21), (7, 9)], 3.6, hexc("#2f8f3c"))
    c.pie((1, 4, 8, 14), 30, 200, hexc("#2f8f3c"))
    c.ellipse((2, 0, 13, 11), hexc("#e0392b"))
    c.poly([(2, 3), (13, 2 + open_ * 3), (7.5, 6 + open_ * 4)], hexc("#f6f2ea"))
    for i in range(3):
        c.poly([(3 + i * 3, 3), (5 + i * 3, 3), (4 + i * 3, 1 + open_ * 3)], hexc("#fff8f0"))
    return c


def cheep(frame: int = 0):
    c = Canvas((14, 12))
    c.ellipse((1, 2, 12, 11), hexc("#e8613a"))
    c.poly([(10, 3), (14, 1), (13, 10)], hexc("#c94a2a"))
    _eyes(c, 5, 5.5, 1.1)
    c.pie((2, 7, 8, 11), 0, 180, hexc("#a83a20"))
    return c


def buzzy(frame: int = 0):
    c = Canvas((14, 10))
    c.ellipse((1, 1, 13, 9), hexc("#3a4a86"))
    for i in range(3):
        c.rect((3 + i * 3, 4, 4 + i * 3, 8), hexc("#26305c"))
    return c


def spiny(frame: int = 0):
    c = koopa(frame, shell=hexc("#d05a2a"), trim=hexc("#f0c48a"))
    for i in range(3):
        c.poly([(3 + i * 3.4, 6), (5 + i * 3.4, 1), (7 + i * 3.4, 6)], hexc("#f6f2ea"))
    return c


def coin(frame: int = 0, n=4):
    """Spinning coin: width follows cos of the spin phase."""
    c = Canvas((10, 14))
    w = 0.35 + 0.65 * abs(math.cos(2 * math.pi * frame / n))
    c.ellipse((5 - 3.4 * w, 2, 5 + 3.4 * w, 13), YELLOW)
    c.ellipse((5 - 2.0 * w, 4, 5 + 2.0 * w, 11), hexc("#fff0b0"))
    return c


def mushroom(variant: str = "super"):
    col = {"super": "#e0392b", "1up": "#3fa535", "mega": "#c95bd6", "mini": "#3a7fd0"}[variant]
    c = Canvas((14, 14))
    c.pie((0, 1, 14, 13), 180, 360, hexc(col))
    c.rrect((1, 7, 13, 14), 3, CREAM)
    for x, y, r in ((3, 4, 2.4), (9, 3.5, 2.8)):
        c.ellipse((x - r, y - r, x + r, y + r), hexc("#fff8f0"))
    return c


def fire_flower(frame: int = 0):
    c = Canvas((14, 16))
    c.line([(7, 15), (7, 8)], 2.2, GREEN)
    c.pie((2, 10, 7, 14), 90, 250, GREEN)
    for i in range(6):
        a = i * math.pi / 3 + frame * 0.2
        c.ellipse((7 + math.cos(a) * 3 - 1.8, 4 + math.sin(a) * 3 - 1.8,
                   7 + math.cos(a) * 3 + 1.8, 4 + math.sin(a) * 3 + 1.8), hexc("#f07a2a"))
    c.ellipse((5, 2.5, 9, 6.5), YELLOW)
    return c


def star(frame: int = 0):
    c = Canvas((14, 14))
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 6.2 if i % 2 == 0 else 2.9
        pts.append((7 + math.cos(a) * r, 7 + math.sin(a) * r))
    c.poly(pts, YELLOW)
    _eyes(c, 7, 8, 1.1)
    return c


def spring(frame: int = 0):
    c = Canvas((14, 12))
    squash = 1 - 0.45 * (frame % 2)
    c.rrect((1, 8, 13, 12), 2, hexc("#c9c9d6"))
    for i in range(3):
        c.rect((2, 8 - i * 1.4 * squash, 12, 9 - i * 1.4 * squash), hexc("#8a8a9c"))
    c.rrect((1, 1, 13, 5), 2, hexc("#e0392b"))
    return c


ENEMIES = {"goomba": goomba, "koopa": koopa, "red_koopa": lambda f=0: koopa(f, hexc("#d8582a")),
           "piranha": piranha, "cheep": cheep, "buzzy": buzzy, "spiny": spiny}
for _name, _fn in ENEMIES.items():
    _n = 4 if _name in ("goomba", "koopa", "red_koopa", "cheep", "piranha") else 2
    register(f"enemy/{_name}", _fn, frames=_n, finish={"outline": 1.0, "rim": 0.28})

# 龟壳（绿/红/刺）与 Bowser、火苗
for _name, _col in (("shell", "#3fa535"), ("shell_red", "#d8582a"),
                    ("shell_spiny", "#d05a2a")):
    register(f"enemy/{_name}", shell, color=_col, frames=2, finish={"outline": 1.0, "rim": 0.26})


def bowser(frame: int = 0):
    """Bowser：绿壳 spiked + 橙色身体。"""
    c = Canvas((28, 28))
    body = hexc("#e8a13a")
    shell_c = hexc("#3f8f3f")
    # 尾巴 + 后腿
    c.poly([(2, 20), (8, 16), (8, 24)], hexc("#d0802a"))
    c.ellipse((4, 18, 12, 27), hexc("#c06a20"))
    # 龟壳
    c.ellipse((8, 12, 24, 28), shell_c)
    for i in range(4):        # 壳刺
        c.poly([(10 + i * 3.6, 13), (12 + i * 3.6, 8 + (i % 2) * 2), (14 + i * 3.6, 13)],
               hexc("#f6f2ea"))
    # 身体与胸甲
    c.ellipse((16, 14, 26, 27), body)
    c.ellipse((18, 19, 25, 26), hexc("#f0d9a8"))
    # 头
    c.ellipse((18, 3, 29, 14), body)
    c.poly([(20, 4), (23, -1 + (0.6 if frame % 2 else 0)), (26, 4)], hexc("#f6f2ea"))
    c.poly([(26, 4), (29, 1), (28, 6)], hexc("#f6f2ea"))
    # 眼与嘴
    c.ellipse((24, 6, 27, 9), hexc("#fff8f0"))
    c.ellipse((25, 6.5, 26.4, 8.5), hexc("#c03020"))
    c.poly([(22, 11), (29, 10), (23, 13)], hexc("#f6f2ea"))
    c.poly([(24, 11), (28, 10.4), (24, 12.6)], hexc("#8a2a1a"))
    # 前腿
    c.ellipse((20, 23, 27, 28), hexc("#c06a20"))
    return c


register("enemy/bowser", bowser, frames=2, finish={"outline": 1.2, "rim": 0.22})


def flame(frame: int = 0):
    """Bowser 的火苗。"""
    c = Canvas((12, 10))
    w = 1.0 if frame % 2 == 0 else 0.86
    c.poly([(1, 5), (10, 2), (11, 5), (10, 8), (1, 5)], hexc("#f07a2a"))
    c.ellipse((3, 3, 8 * w + 3, 7), hexc("#ffd24a"))
    c.ellipse((4, 4, 6, 6), hexc("#fff6c0"))
    return c


register("enemy/flame", flame, frames=2, finish={"outline": 0.8, "light": None})

register("item/coin", coin, frames=4, finish={"outline": 1.0})
for _k in ("super", "1up", "mega", "mini"):
    register(f"item/{_k}", mushroom, variant=_k, finish={"outline": 1.0})
register("item/fire_flower", fire_flower, frames=2, finish={"outline": 1.0})
register("item/star", star, frames=2, finish={"outline": 1.0})
register("item/spring", spring, frames=2, finish={"outline": 1.0})
register("fx/coin", coin, frames=4, finish={"outline": 1.0})


def bigcoin(frame: int = 0, n=4):
    """NSMB 大金币（Star Coin）：更大的旋转金币 + 星形镂空。"""
    c = Canvas((16, 22))
    w = 0.4 + 0.6 * abs(math.cos(2 * math.pi * frame / n))
    cx = 8
    c.ellipse((cx - 7 * w, 1, cx + 7 * w, 21), hexc("#f6c95c"))
    c.ellipse((cx - 5 * w, 3, cx + 5 * w, 19), hexc("#ffe9a0"))
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 5.5 * w if i % 2 == 0 else 2.4 * w
        pts.append((cx + math.cos(a) * r, 11 + math.sin(a) * r))
    c.poly(pts, hexc("#f6c95c"))
    return c


register("item/bigcoin", bigcoin, frames=4, finish={"outline": 1.0, "rim": 0.3})


def _poof(frame: int = 0, n: int = 3, color="#fff8f0"):
    c = Canvas((12, 12))
    r = 2 + frame * 2.4
    c.ellipse((6 - r, 6 - r, 6 + r, 6 + r), hexc(color))
    for i in range(n):
        a = i * 2 * math.pi / n + frame
        c.ellipse((6 + math.cos(a) * r - 1.6, 6 + math.sin(a) * r - 1.6,
                   6 + math.cos(a) * r + 1.6, 6 + math.sin(a) * r + 1.6), hexc(color))
    return c


register("fx/pop", _poof, frames=3, finish={"outline": 0.8, "light": None})
register("fx/hit", lambda f=0: _poof(f, 4, "#ffd9a0"), frames=3, finish={"outline": 0.8, "light": None})
register("fx/dust", lambda f=0: _poof(f, 3, "#e6d8bc"), frames=2, finish={"outline": 0.0, "light": None})


def _shard(frame: int = 0):
    """砖块碎片：旋转的小方块。"""
    c = Canvas((5, 5))
    c.rrect((0.5, 0.5, 4.5, 4.5), 1, hexc("#c0713c"))
    c.rect((0.5, 0.5, 4.5, 1.4), hexc("#e8a869"))
    c.rect((2, 2.6, 3.6, 3.4), hexc("#8f4a22"))
    return c


def _sparkle(frame: int = 0):
    """星光闪烁：四芒星由小变大再收缩。"""
    c = Canvas((10, 10))
    r = (1.2, 3.2, 4.6)[frame % 3]
    pts = []
    for i in range(8):
        a = i * math.pi / 4
        rad = r if i % 2 == 0 else r * 0.35
        pts.append((5 + math.cos(a) * rad, 5 + math.sin(a) * rad))
    c.poly(pts, hexc("#fffbe0"))
    return c


def _firework(frame: int = 0):
    """烟花：放射状圆点爆开。"""
    c = Canvas((28, 28))
    r = 4 + frame * 4
    for i in range(8):
        a = i * math.pi / 4 + frame * 0.5
        rr = 2.0 if frame < 2 else 1.4
        x, y = 14 + math.cos(a) * r, 14 + math.sin(a) * r
        c.ellipse((x - rr, y - rr, x + rr, y + rr), hexc(("#ffe9a0", "#ff9a6a", "#a0d8ff")[i % 3]))
    return c


register("fx/shard", _shard, frames=3, finish={"outline": 0.6, "light": None})
register("fx/sparkle", _sparkle, frames=3, finish={"outline": 0.4, "light": None})
register("fx/firework", _firework, frames=3, finish={"outline": 0.0, "light": None})


def _splash(frame: int = 0):
    """入水水花：两滴水珠溅起。"""
    c = Canvas((10, 10))
    r = 1.2 + frame * 0.9
    for sx in (-1, 1):
        x = 5 + sx * (1.5 + frame * 1.4)
        c.ellipse((x - r, 4 - frame * 1.2, x + r, 4 - frame * 1.2 + r * 2),
                  hexc("#bfe6ff" if frame < 2 else "#8fd0f0"))
    return c


register("fx/splash", _splash, frames=3, finish={"outline": 0.4, "light": None})
