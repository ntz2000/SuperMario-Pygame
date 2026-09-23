"""Sound effects and music, generated from note tables.

Everything is registered through the asset registry with ``kind="wav"``, so the same
content-hash cache that covers sprites covers audio: change a note table and the cached
WAV is regenerated on the next run.
"""
from __future__ import annotations

import numpy as np

from ..engine import audio as A
from ..engine.assets import register


def _sfx(fn, **kw):
    return lambda: A.to_wav(fn(**kw))


def jump(dur=0.19, f0=430, f1=980):
    return A.tone(f0, dur, "square", 0.30, decay=3.0, slide=(f1 - f0) / f0)


def coin():
    return A.mix(A.tone("B5", 0.06, "square", 0.26), A.tone("E6", 0.16, "square", 0.24),
                 offset=0.055)


def stomp():
    return A.mix(A.noise(0.09, 0.20, 22.0), A.tone(210, 0.09, "triangle", 0.26, decay=22))


def bump():
    return A.tone(150, 0.09, "triangle", 0.34, decay=26)


def brk():
    return A.noise(0.24, 0.30, 9.0, lp=0.5)


def power_up():
    notes = ["C5", "E5", "G5", "C6"]
    return A.mix(*[A.tone(n, 0.09, "square", 0.24, decay=5) for n in notes])


def hurt():
    return A.tone(360, 0.24, "saw", 0.26, decay=7, slide=-0.55)


def death():
    return A.mix(*[A.tone(n, 0.13, "triangle", 0.26, decay=3)
                  for n in ("G4", "C5", "E5", "G5", "C6")], offset=0)


def kick():
    return A.mix(A.noise(0.14, 0.22, 12.0), A.tone(320, 0.12, "square", 0.18, decay=14))


def pipe():
    return A.tone(700, 0.45, "sine", 0.26, decay=5.5, slide=-0.8)


def spring():
    return A.tone(300, 0.22, "sine", 0.26, decay=6, slide=2.2)


def spin():
    return A.tone(880, 0.12, "square", 0.16, decay=12, slide=0.4)


def star():
    return A.mix(*[A.tone(n, 0.07, "square", 0.2, decay=6)
                  for n in ("C5", "D5", "E5", "G5", "A5", "C6")])


SFX = {
    "jump": lambda: A.tone(430, 0.19, "square", 0.3, decay=3.2, slide=1.2),
    "mini-jump": lambda: A.tone(620, 0.14, "triangle", 0.24, decay=4, slide=0.8),
    "swim": lambda: A.noise(0.16, 0.16, 7.0, lp=0.6),
    "land": lambda: A.noise(0.05, 0.12, 30.0),
    "pound": lambda: A.mix(A.noise(0.16, 0.26, 14.0), A.tone(120, 0.16, "triangle", 0.3, decay=14)),
    "coin": coin,
    "stomp": stomp,
    "bump": bump,
    "break": brk,
    "hit": lambda: A.mix(A.tone(300, 0.12, "square", 0.2, decay=14, slide=-0.4)),
    "kick": kick,
    "power-up": power_up,
    "shrink": hurt,
    "death": death,
    "pipe": pipe,
    "spring": spring,
    "spin": spin,
    "star": star,
    "throw": lambda: A.noise(0.12, 0.18, 18.0, lp=0.35),
    "1up": lambda: A.mix(*[A.tone(n, 0.085, "square", 0.22, decay=4)
                          for n in ("C5", "E5", "G5", "C6", "E6")]),
    "note": lambda: A.tone(360, 0.2, "sine", 0.3, decay=5, slide=1.6),
    "reveal": lambda: A.tone(520, 0.1, "triangle", 0.26, decay=8, slide=0.5),
    "checkpoint": lambda: A.mix(A.tone("G5", 0.1, "square", 0.2, decay=4),
                                A.tone("C6", 0.16, "square", 0.2, decay=4), offset=0.09),
    "starcoin": lambda: A.mix(*[A.tone(n, 0.09, "triangle", 0.24, decay=3)
                               for n in ("E6", "G6", "C7")], offset=0.0),
    "boss-hit": lambda: A.mix(A.tone(85, 0.24, "square", 0.34, decay=9),
                              A.noise(0.18, 0.2, 10.0)),
    "fire": lambda: A.noise(0.3, 0.22, 6.0, lp=0.25),
    "clear": lambda: A.mix(*[A.tone(n, 0.16, "triangle", 0.24, decay=2.5)
                             for n in ("C5", "E5", "G5", "C6", "E6", "G6")]),
}


for _name, _fn in SFX.items():
    register(f"sfx/{_name}", _fn, kind="wav")


# -- music -------------------------------------------------------------------------------
# Songs are note tables at one step per 16th note; "-" is a rest, and the step count
# must match the tokens in each track so the loop lines up exactly.

SONGS = {
    "overworld": dict(tempo=152, tracks=[
        ("square", 0.15, "E5 - G5 - C6 - B5 A5 G5 - A5 G5 E5 - G5 - "
                          "F5 - A5 - D6 - C6 B5 A5 - B5 A5 F5 A5 C6 -"),
        ("triangle", 0.22, "C3 - - - E3 - - - G3 - - - G3 - - - "
                           "F3 - - - A3 - - - C4 - - - C4 - - -"),
    ]),
    "title": dict(tempo=112, tracks=[
        ("sine", 0.24, "C5 - - - E5 - - - G5 - - - E5 - - - D5 - - - F5 - - - E5 - - - C5 - - -"),
        ("triangle", 0.20, "C3 - - - G3 - - - A3 - - - E3 - - - F3 - - - C4 - - - G3 - - - C3 - - -"),
    ]),
    "underground": dict(tempo=138, tracks=[
        ("square", 0.14, "A4 - C5 - A4 - E4 F4 G4 - G4 - F4 - E4 - "
                         "D4 - F4 - D4 - A4 B4 C5 - C5 - B4 - A4 - G4 -"),
        ("triangle", 0.22, "A2 - - - A3 - - - A2 - - - E3 - - - "
                           "D3 - - - D3 - - - E3 - - - E2 - - -"),
    ]),
    "water": dict(tempo=126, tracks=[
        ("sine", 0.22, "D5 - F5 - A5 - G5 F5 E5 - E5 F5 G5 - A5 - D5 -"),
        ("triangle", 0.24, "D3 - - - F3 - - - A3 - - - A3 - - - G3 - - - B3 - - - A3 - - - F3 - - -"),
    ]),
    "castle": dict(tempo=144, tracks=[
        ("saw", 0.11, "C5 - C5 - D#5 - C5 - A4 - G4 - F4 - E4 - D#4 - C4 -"),
        ("triangle", 0.22, "C3 - - - C3 - - - G2 - - - G2 - - - A2 - - - A2 - - - F2 - - - G2 - - -"),
    ]),
    "map": dict(tempo=118, tracks=[
        ("triangle", 0.22, "C5 - E5 - G5 - E5 - D5 - F5 - A5 - G5 - E5 - C5 - G4 - E4 -"),
    ]),
    "star": dict(tempo=168, tracks=[
        ("square", 0.13, "C5 C5 C5 - E5 - G5 - C6 - B5 - G5 - E5 - C5 C5 C5 - E5 - G5 - C6 -"),
        ("triangle", 0.2, "C3 - C3 - E3 - E3 - G3 - G3 - C3 - E3 - F3 - F3 - G3 - G3 -"),
    ]),
    "clear": dict(tempo=150, tracks=[
        ("triangle", 0.26, "C5 - E5 - G5 - C6 - E6 - D6 - C6 - G5 - E5 - C5 -"),
    ]),
}

for _name, _cfg in SONGS.items():
    register(f"music/{_name}", A.render_song, kind="wav", tempo=_cfg["tempo"],
             tracks=_cfg["tracks"], steps=len(_cfg["tracks"][0][2].split()))
