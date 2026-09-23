"""Tile table: what each level character means, and how it behaves.

Levels are written as rows of characters. Each character maps to a :class:`Tile` holding
its collision kind, its sprite family (auto-tiled by neighbour mask into ``fill``/``top``/
``cap`` variants) and any block behaviour an actor needs to know about. Terrain colors
live in :class:`Theme` so one family of blocks can wear grass, stone, metal or ice with
no level edits and no duplicated art code.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from .physics import ONE_WAY, SOLID

TILE = 16


@dataclass(frozen=True)
class Theme:
    """One environment: sky, backdrop silhouettes and the terrain palettes."""

    name: str
    sky: tuple = ("#7cc7f5", "#cdeeff")
    hill: str = "#3fa535"
    hill_d: str = "#2c7d2a"
    cloud: str = "#ffffff"
    bush: str = "#54c24a"
    ground: tuple = ("#9c5a24", "#5ec24a", "#7d4519")   # body, lip, grit
    rock: tuple = ("#8a6a4a", "#b08a5a", "#6a4a30")
    brick: tuple = ("#c0713c", "#e8a869", "#8f4a22")
    platform: tuple = ("#b9863f", "#f0d29a", "#7d5323")
    music: str = "overworld"


@dataclass(frozen=True)
class Tile:
    code: str
    name: str
    art: str                      # asset id prefix, e.g. "tile/ground"
    kind: str = SOLID             # SOLID | ONE_WAY | "" (decor)
    item: str = ""                # what popping this block yields
    bumpable: bool = False        # hit from below -> pops and goes empty
    destructible: bool = False    # destroyed by a grounded punch/ground pound
    bounce: float = 0.0           # upward launch given to things standing on it
    climbable: bool = False
    fluid: bool = False
    decoration: bool = False
    hidden: bool = False          # invisible until head-butted (``H`` in a level)
    body: str = ""
    lip: str = ""
    grit: str = ""

    @property
    def solid(self) -> bool:
        return bool(self.kind)

    def colors(self) -> dict:
        """The kwargs a terrain generator needs; empty for props with fixed art."""
        if not (self.body and self.lip):
            return {}
        return dict(body=self.body, lip=self.lip, grit=self.grit)


# which Theme palette family recolours each terrain tile name
TERRAIN_FAMILIES = {"ground": "ground", "rock": "rock", "brick": "brick",
                    "platform": "platform", "crate": "brick"}


@dataclass
class TileTable:
    """The code -> Tile map plus the per-theme recolors of the terrain families."""

    tiles: dict[str, Tile] = field(default_factory=dict)
    themes: dict[str, Theme] = field(default_factory=dict)

    def add(self, tile: Tile) -> Tile:
        self.tiles[tile.code] = tile
        return tile

    def add_theme(self, theme: Theme) -> Theme:
        self.themes[theme.name] = theme
        return theme

    def __getitem__(self, code: str) -> Tile:
        return self.tiles[code]

    def get(self, code: str, default=None):
        return self.tiles.get(code, default)

    def theme(self, name: str) -> Theme:
        return self.themes.get(name, self.themes["overworld"])

    def terrain(self, code: str, theme: str) -> Tile:
        """A terrain tile wearing an environment's palette.

        草原（overworld）使用真实 NSMB 瓦片图集（mario/assets/atlas.json），
        其余主题沿用注册的 art id + 主题配色——两条路径由 ``Assets.sprite``
        内部统一调度（图集命中优先）。
        """
        base = self.tiles[code]
        # 真实瓦片主题前缀（NSMB 官方 tileset，见 mario/assets/atlas.json）
        REAL = {"overworld": "ow", "underground": "ug", "castle": "castle",
                "water": "water"}
        if theme in REAL and base.name in ("ground", "rock"):
            real = f"tile/{REAL[theme]}-{base.name}"
            try:
                from ..assets.atlas import ATLAS
                if f"{real}.top" in ATLAS:
                    return replace(base, art=real, body="", lip="", grit="")
            except ImportError:
                pass
        family = TERRAIN_FAMILIES.get(base.name, "rock")
        colors = getattr(self.theme(theme), family)
        return replace(base, body=colors[0], lip=colors[1], grit=colors[2])

    def kind_of(self, code: str) -> str:
        t = self.tiles.get(code)
        return t.kind if t else ""


def default_table() -> TileTable:
    t = TileTable()
    add = t.add
    for theme in THEMES:
        t.add_theme(theme)
    # --- terrain ---------------------------------------------------------------------
    add(Tile("G", "ground", "tile/ground"))
    add(Tile("D", "rock", "tile/rock"))
    add(Tile("B", "brick", "tile/brick", bumpable=True, item="coin"))
    add(Tile("b", "brick", "tile/brick", bumpable=True, destructible=True, item=""))
    add(Tile("?", "question", "tile/question", bumpable=True, item="coin"))
    add(Tile("!", "power block", "tile/question", bumpable=True, item="fire_flower"))
    add(Tile("f", "ice block", "tile/question", bumpable=True, item="ice_flower"))
    add(Tile("*", "star block", "tile/question", bumpable=True, item="star"))
    add(Tile("m", "mini block", "tile/question", bumpable=True, item="mini"))
    add(Tile("g", "mega block", "tile/question", bumpable=True, item="mega"))
    add(Tile("P", "propeller block", "tile/question", bumpable=True, item="propeller"))
    add(Tile("Q", "penguin block", "tile/question", bumpable=True, item="penguin"))
    add(Tile("H", "hidden block", "", kind="", bumpable=True, hidden=True, item="coin"))
    add(Tile("N", "note", "tile/note", bumpable=True))
    add(Tile("X", "used block", "tile/used"))
    add(Tile("o", "coin tile", "", kind="", decoration=True, item="coin"))
    add(Tile("C", "coin block", "tile/coin_block", bumpable=True, item="coin10"))
    add(Tile("=", "platform", "tile/platform", kind=ONE_WAY))
    add(Tile("l", "ladder", "tile/ladder", kind="", climbable=True))
    add(Tile("S", "spike", "tile/spike"))
    add(Tile("I", "ice", "tile/ice"))
    add(Tile("M", "metal", "tile/metal"))
    add(Tile("W", "wood crate", "tile/crate", bumpable=True, destructible=True))
    add(Tile("T", "switch block (off)", "tile/switch", bumpable=True))
    add(Tile("t", "switch block (on)", "tile/used", bumpable=True))
    # --- structures -------------------------------------------------------------------
    add(Tile("p", "pipe", "tile/pipe"))
    add(Tile("|", "pipe cap", "tile/pipe"))
    add(Tile("v", "vine", "", kind="", climbable=True, decoration=True))
    add(Tile("w", "water", "tile/water", kind="", fluid=True))
    add(Tile("~", "water top", "tile/water_top", kind="", fluid=True))
    return t


OVERWORLD = Theme("overworld")
UNDERGROUND = Theme("underground", sky=("#141830", "#232a48"), hill="#3a4266",
                    hill_d="#262c4c", cloud="#8fa4d8", bush="#4a5c9c",
                    ground=("#3f4a6e", "#6a7cb0", "#2c3454"),
                    rock=("#3a4464", "#56628c", "#2a3252"),
                    brick=("#4a5578", "#7688b8", "#333c5c"),
                    platform=("#6a7cb0", "#a8bcf0", "#3f4a6e"), music="underground")
CASTLE = Theme("castle", sky=("#2a1a1a", "#5a3226"), hill="#5a3a34", hill_d="#3c2622",
               cloud="#c9a08a", bush="#7a4a3a", ground=("#5a4340", "#7a5a50", "#3c2a26"),
               rock=("#4e4750", "#6e6674", "#332e38"), brick=("#6a4a3a", "#9a7256", "#46302a"),
               platform=("#6e6674", "#a8a0b0", "#332e38"), music="castle")
SKY = Theme("sky", sky=("#8fd8ff", "#eafaff"), hill="#cfe9ff", hill_d="#a9cbe8",
            cloud="#ffffff", bush="#dff0ff", ground=("#dfeaf8", "#f6fbff", "#b8cde4"),
            rock=("#c4d6ec", "#eaf4ff", "#a8bcd6"), brick=("#cfe0f2", "#f0f8ff", "#a4bcd8"),
            platform=("#eaf4ff", "#ffffff", "#b8cde4"), music="sky")
WATER = Theme("water", sky=("#0f4a7a", "#1c7fc4"), hill="#1a5f96", hill_d="#124468",
              cloud="#bfe6ff", bush="#2a8fd0", ground=("#1f6ea8", "#54b8e8", "#154a74"),
              rock=("#1a5580", "#2f7fb0", "#123c5c"), brick=("#1f6ea8", "#4a9fd0", "#154a74"),
              platform=("#2f7fb0", "#8fd8ff", "#154a74"), music="water")
THEMES = (OVERWORLD, UNDERGROUND, CASTLE, SKY, WATER)
