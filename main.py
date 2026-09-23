"""Entry point.

``python main.py`` opens the window. The same file drives headless runs: ``--capture``
renders N frames into a PNG and exits, which is how screenshots are checked in CI.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pygame  # noqa: E402

from mario.data.levels import LEVELS  # noqa: E402
from mario.data import save as saved  # noqa: E402
from mario.debug import Bot  # noqa: E402
from mario.engine.app import App  # noqa: E402
from mario.scenes.level import LevelScene  # noqa: E402
from mario.scenes.title import TitleScene  # noqa: E402
from mario.scenes.worldmap import WorldMapScene  # noqa: E402

NODES = [dict(level=name, label=data.get("label", name))
         for name, data in LEVELS.items() if not data.get("secret")]


def build(args) -> App:
    app = App(title="Super Plumbros", base=(args.width // args.scale, args.height // args.scale),
              scale=args.scale, headless=args.headless, enable_cache=not args.no_cache)
    app.progress = {"levels": LEVELS, **saved.load()}
    if args.scene == "level":
        return app, LevelScene(app, LEVELS[args.level])
    if args.scene == "world":
        return app, WorldMapScene(app, NODES, app.progress)
    return app, TitleScene(app, LEVELS)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Super Plumbros")
    p.add_argument("--scene", default="title", choices=["title", "level", "world"])
    p.add_argument("--level", default="1-1")
    p.add_argument("--frames", type=int, default=0, help="stop after N sim frames (0 = free run)")
    p.add_argument("--capture", default="", help="write the final frame here and exit")
    p.add_argument("--scale", type=int, default=4)
    p.add_argument("--width", default="1280")
    p.add_argument("--height", default="720")
    p.add_argument("--headless", action="store_true", default=None)
    p.add_argument("--no-cache", action="store_true",
                   help="rebuild all art, skip the on-disk cache")
    p.add_argument("--bot", action="store_true", help="let the autopilot hold the buttons")
    args = p.parse_args(argv)
    args.width, args.height = int(args.width), int(args.height)
    app, scene = build(args)
    if args.bot:
        app.use_virtual_input()
        Bot().attach(app, scene)
    app.run(scene, frames=args.frames or None, capture=args.capture or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
