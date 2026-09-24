"""Tile sprites.

Every terrain tile gets a ``fill`` (fully buried), ``top`` (exposed above) and ``cap``
(isolated block) variant, chosen at render time by ``TileMap.variant`` from the
neighbour mask.  Generators are registered in a loop from the tile table so the table
stays the single source of truth for what exists.
"""
from __future__ import annotations

from ..engine.assets import asset, register
from ..engine.ink import Canvas, hexc


def _speckle(c: Canvas, color, n: int, seed: int):
    """Deterministic grit so buried terrain still reads as material, not flat color."""
    for i in range(n):
        x = ((seed * 37 + i * 53) % 13) / 13 * 12 + 1
        y = ((seed * 17 + i * 29) % 11) / 11 * 8 + 6
        c.rrect((x, y, x + 2, y + 2), 1, color)


def block_art(seed: int = 3, studs: bool = False):
    """Build the three variants of a 16x16 terrain block.

    Colors are generator arguments, not closure state, so a theme can recolour
    terrain through ``Assets.sprite(..., body=..., lip=...)`` and the content-hash
    cache sees the override.
    """

    def build(variant: str, body: str = "#9c5a24", lip: str = "#5ec24a",
              grit: str = "#7d4519") -> Canvas:
        body_c, lip_c, grit_c = hexc(body), hexc(lip), hexc(grit)
        c = Canvas((16, 16))
        c.rrect((0, 0, 16, 16), 3 if variant == "cap" else 1, body_c)
        if variant == "fill":
            c.rect((0, 12, 16, 13), (0, 0, 0, 24))
        if variant in ("top", "cap"):
            c.rrect((0, 0, 16, 6), 3 if variant == "cap" else 1, lip_c)
            c.rect((0, 4, 16, 5), (255, 255, 255, 70))
        if studs and variant != "fill":
            for sx in (3, 11):
                c.rrect((sx, 6, sx + 2, 8), 1, grit_c)
        _speckle(c, grit_c, 4, seed + (0 if variant == "top" else 5))
        return c

    return build


def register_block(name: str, body: str, lip: str, grit: str, seed: int = 3, studs=False):
    build = block_art(seed, studs)
    for variant in ("fill", "top", "cap"):
        register(f"{name}.{variant}", build, variant=variant, body=body, lip=lip, grit=grit,
                 finish={"outline": 1.0})


def _stable_seed(name: str) -> int:
    """Deterministic per-family seed (str hash is per-process random, unusable here)."""
    return sum(b * (i + 1) for i, b in enumerate(name.encode())) % 97


for _name, _body, _lip, _grit in (
    ("tile/ground", "#9c5a24", "#5ec24a", "#7d4519"),
    ("tile/rock", "#5d6c86", "#9fb1d8", "#465268"),
    ("tile/brick", "#c0713c", "#e8a869", "#8f4a22"),
    ("tile/ice", "#7fd0f0", "#e6fbff", "#4f9dc4"),
    ("tile/metal", "#7e8798", "#c3cddd", "#4c5566"),
    ("tile/crate", "#a5761f", "#d9a94a", "#7a5512"),
):
    register_block(_name, _body, _lip, _grit, seed=_stable_seed(_name))


# -- special blocks ----------------------------------------------------------------------

def _question(variant: str) -> Canvas:
    c = Canvas((16, 16))
    c.rrect((0, 0, 16, 16), 3, hexc("#e8a13a"))
    c.rrect((2, 2, 14, 14), 2, hexc("#f6c95c"))
    for x, y in ((1, 1), (13, 1), (1, 13), (13, 13)):
        c.rect((x, y, x, y), hexc("#a86a1c"))
    c.poly([(6, 4), (10, 4), (11, 7), (8.5, 9), (8.5, 11)], hexc("#a8621a"))  # the "?" glyph
    c.rect((7, 12, 8, 13), hexc("#a8621a"))
    return c


def _note(variant: str) -> Canvas:
    c = Canvas((16, 16))
    c.rrect((0, 0, 16, 16), 3, hexc("#c9563c"))
    c.rrect((2, 2, 14, 14), 2, hexc("#f0864f"))
    c.ellipse((5, 8, 9, 12), hexc("#5a2418"))
    c.line([(8, 9), (8, 4), (11, 5)], 1.4, hexc("#5a2418"))
    return c


def _used(variant: str) -> Canvas:
    c = Canvas((16, 16))
    c.rrect((0, 0, 16, 16), 3, hexc("#8c7c66"))
    c.rrect((2, 2, 14, 14), 2, hexc("#a89a80"))
    return c


for _v in ("fill", "top", "cap"):
    register("tile/question." + _v, _question, variant=_v, finish={"outline": 1.0, "rim": 0.34})
    register("tile/note." + _v, _note, variant=_v, finish={"outline": 1.0})
    register("tile/used." + _v, _used, variant=_v, finish={"outline": 1.0})


# -- structures --------------------------------------------------------------------------

def _platform(variant: str) -> Canvas:
    """One-way platform: a thin lit slab with a soft underside."""
    c = Canvas((16, 16))
    c.rrect((0, 0, 16, 7), 2, hexc("#b9863f"))
    c.rect((0, 0, 16, 2), hexc("#f0d29a"))
    c.rect((0, 5, 16, 7), hexc("#7d5323"))
    return c


def _pipe(variant: str) -> Canvas:
    c = Canvas((16, 16))
    cap = variant == "cap"
    c.rrect((1, 0 if cap else 1, 15, 16), 4 if cap else 1, hexc("#2aa04a"))
    # 竖向双高光带（左强右弱=立体圆柱感）
    c.rect((3, 0 if cap else 2, 4.6, 13), hexc("#8fef9a"))
    c.rect((12.4, 0 if cap else 2, 13.4, 13), hexc("#57c868"))
    if variant in ("cap", "top"):
        c.rect((1, 1, 15, 3), hexc("#63e07a"))
    return c


def _ladder(variant: str) -> Canvas:
    c = Canvas((16, 16))
    for x in (3, 11):
        c.rect((x, 0, x + 2, 15), hexc("#a5761f"))
    for y in (2, 7, 12):
        c.rect((3, y, 11, y + 1), hexc("#d9a94a"))
    return c


def _water(variant: str) -> Canvas:
    c = Canvas((16, 16))
    c.rect((0, 0, 16, 16), (60, 150, 240, 190))
    return c


def _water_top(variant: str) -> Canvas:
    c = Canvas((16, 16))
    c.rect((0, 2, 16, 16), (74, 178, 250, 190))
    c.rect((0, 1, 16, 2), (206, 246, 255, 220))
    return c


def _spike(variant: str) -> Canvas:
    c = Canvas((16, 16))
    for i in range(3):
        x = i * 5.5
        c.poly([(x, 15), (x + 5, 15), (x + 2.5, 4)], hexc("#c9d6e8"))
    return c


def _coin_block(variant: str) -> Canvas:
    c = Canvas((16, 16))
    c.rrect((0, 0, 16, 16), 3, hexc("#c0713c"))
    c.ellipse((4, 4, 11, 11), hexc("#f6c95c"))
    return c


def _switch(variant: str) -> Canvas:
    c = Canvas((16, 16))
    c.rrect((0, 0, 16, 16), 3, hexc("#3f7fbd"))
    c.rrect((3, 3, 12, 12), 2, hexc("#7fd0f0"))
    return c


for _name, _fn in (("tile/platform", _platform), ("tile/pipe", _pipe), ("tile/ladder", _ladder),
                   ("tile/water", _water), ("tile/water_top", _water_top), ("tile/spike", _spike),
                   ("tile/coin_block", _coin_block), ("tile/switch", _switch)):
    for _v in ("fill", "top", "cap"):
        register(f"{_name}.{_v}", _fn, variant=_v,
                 finish={"outline": 1.0 if "water" not in _name else 0.0})
