"""Chiptune renderer and SFX synth.

Music is written as note tables and rendered to WAV bytes at load time with numpy, so
there is no tracker dependency and loops are exact. SFX are tiny synthesized blips.
"""
from __future__ import annotations

import io
import math
import wave

import numpy as np
import pygame

RATE = 44100
SEMI = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def freq(note: str) -> float:
    """``'A4'`` -> 440.0; ``'C#3'`` -> equal temperament."""
    name, octave = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((SEMI[name] + (octave - 4) * 12) / 12)


def _wave(kind: str, phase: np.ndarray) -> np.ndarray:
    p = phase % (2 * math.pi)
    if kind == "square":
        return np.sign(np.sin(p))
    if kind == "triangle":
        return 2 / math.pi * np.arcsin(np.sin(p))
    if kind == "saw":
        return 1 - p / math.pi
    if kind == "sine":
        return np.sin(p)
    return np.sin(p)


def tone(note: str | float, dur: float, kind: str = "square", vol: float = 0.3,
         attack: float = 0.005, decay: float = 2.0, slide: float = 0.0) -> np.ndarray:
    n = int(RATE * dur)
    t = np.arange(n) / RATE
    f0 = float(note) if isinstance(note, (int, float)) else freq(note)
    pitch = f0 * (1 + slide * (t / max(1e-6, dur)))
    phase = 2 * math.pi * np.cumsum(pitch) / RATE
    env = np.minimum(1, t / max(1e-6, attack)) * np.exp(-t * decay)
    return _wave(kind, phase) * env * vol


def noise(dur: float, vol: float = 0.3, decay: float = 8.0, lp: float = 0.25) -> np.ndarray:
    rng = np.random.default_rng(11)
    raw = rng.standard_normal(int(RATE * dur))
    step = int(1 / lp)
    pad = np.zeros(int(RATE * dur) % step)
    smoothed = (raw[: len(raw) - len(raw) % step].reshape(-1, step).mean(axis=1))
    out = np.repeat(smoothed, step)
    out = np.concatenate([out, pad]) if len(out) != len(raw) else out
    t = np.arange(len(out)) / RATE
    return out * np.exp(-t * decay) * vol


def mix(*parts: np.ndarray, offset: float = 0.0) -> np.ndarray:
    """Overlay voices; shorter ones are padded out."""
    end = int(max(len(p) for p in parts) + RATE * offset) if parts else 0
    out = np.zeros(end)
    for p in parts:
        out[int(RATE * offset): int(RATE * offset) + len(p)] += p
    return out


def to_wav(samples: np.ndarray, ceiling: float = 0.92) -> bytes:
    """Wrap samples as 16-bit mono WAV. Loud material is brought down, quiet stays quiet,
    so the relative mix between the voices each generator asked for survives."""
    peak = float(np.max(np.abs(samples))) or 1.0
    gain = min(1.0, ceiling / peak)
    data = (samples * gain * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    return buf.getvalue()


def from_wav(data: bytes) -> pygame.Sound:
    return pygame.mixer.Sound(io.BytesIO(data))


# -- sequencer -----------------------------------------------------------------------

def bar(notes: str) -> list[tuple[str, float]]:
    """``'C4 - E4 G4'`` -> events at one step each. ``.``, ``_`` extend the last note."""
    out = []
    for tok in notes.split():
        out.append((tok, 1.0))
    return out


def render_song(tempo: float, tracks: list[tuple[str, float, list[tuple[str, float]]]],
                steps: int, swing: float = 0.0) -> bytes:
    """Render note tracks into a looping WAV.

    ``tracks`` is a list of ``(wave, volume, notes)`` where notes are either a space
    separated string of note names (one step each, ``-`` = rest) or explicit
    ``(note, steps)`` pairs. One step is one 16th note.
    """
    if isinstance(tracks, (list, tuple)):
        tracks = [(k, v, [(t, 1.0) for t in notes.split()] if isinstance(notes, str) else notes)
                  for k, v, notes in tracks]
    step = 60.0 / tempo / 4
    total = np.zeros(int(RATE * steps * step) + 8)
    for kind, vol, notes in tracks:
        cursor = 0.0
        for note, length in notes:
            dur = length * step
            if note != "-":
                voice = tone(note, dur, kind, vol) if not isinstance(note, tuple) else note[1]
                start = int(cursor * RATE)
                total[start: start + len(voice)] += voice[: max(0, len(total) - start)]
            cursor += length
    return to_wav(total)
