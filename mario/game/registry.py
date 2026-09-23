"""Object-type name to actor class, used when loading level JSON."""
from __future__ import annotations

from . import enemies as E
from . import objects as O

ACTORS: dict[str, type] = {
    # enemies
    "goomba": E.Goomba,
    "koopa": E.Koopa,
    "red_koopa": E.RedKoopa,
    "buzzy": E.Buzzy,
    "spiny": E.Spiny,
    "piranha": E.Piranha,
    "cheep": E.Cheep,
    "bowser": E.Bowser,
    "flame": E.Flame,
    # pickups
    "super": O.Mushroom,
    "mushroom": O.Mushroom,
    "1up": O.OneUp,
    "mega": O.MegaMushroom,
    "fire_flower": O.FireFlower,
    "star": O.Star,
    "mini": O.Mini,
    "coin": O.Coin,
    "bcoin": O.BlockCoin,
    "starcoin": O.StarCoin,
    # fixtures
    "spring": O.Spring,
    "platform": O.MovingPlatform,
    "pipe": O.WarpPipe,
    "checkpoint": O.CheckpointFlag,
    "flag": O.GoalFlag,
    "fireball": O.Fireball,
}


def actor_for(name: str):
    return ACTORS.get(name)
