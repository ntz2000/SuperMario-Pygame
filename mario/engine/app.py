"""Window, fixed-step loop, scene stack wiring, headless capture.

Everything renders into a fixed internal buffer (default 384x216 art pixels) which is
upscaled with nearest neighbour to the window size, so art keeps hard pixels at any
resolution and the sim never depends on DPI.
"""
from __future__ import annotations

import io
import os
import time
from typing import Callable

import pygame

from .assets import Assets, UnknownAsset
from .audio import from_wav
from .input import Input, VirtualInput
from .scene import SceneManager

FPS = 60
STEP_MS = 1000.0 / FPS


class App:
    def __init__(self, title="Super Mario", base=(384, 216), scale=3, headless=None,
                 input=None, enable_cache: bool = True):
        if headless is None:
            headless = not os.environ.get("DISPLAY") and "SDL_VIDEODRIVER" not in os.environ
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        if not pygame.get_init():
            pygame.init()
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(44100, -16, 2, 512)
            except pygame.error:
                pass
        self.base = (int(base[0]), int(base[1]))
        self.buffer = pygame.Surface(self.base, pygame.SRCALPHA)
        flags = pygame.RESIZABLE | (pygame.NOFRAME if headless else 0)
        self.window = pygame.display.set_mode((self.base[0] * scale, self.base[1] * scale), flags)
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.assets = Assets(enable_cache=enable_cache)
        self.input = Input() if input is None else input
        self.scenes = SceneManager(self)
        self.running = False
        self.fps = FPS
        self.frame = 0
        self.sounds: dict[str, object] = {}
        self.music_id = None
        self.volume = 0.7
        self.sound_on = pygame.mixer.get_init() is not None
        self.hooks: list[Callable] = []

    def use_virtual_input(self) -> VirtualInput:
        """Swap in a code-driven input and hand it back (used by tests and captures)."""
        self.input = VirtualInput()
        return self.input

    def on_step(self, fn: Callable):
        """Run ``fn(app, frame)`` at the top of every sim frame, before the scene steps."""
        self.hooks.append(fn)

    # -- loop --------------------------------------------------------------------------
    def step(self):
        """One sim frame at a fixed 60 Hz: input edges first, then the active scene."""
        for fn in self.hooks:
            fn(self, self.frame)
        self.scenes.update()
        self.input.advance()
        self.frame += 1

    def render(self):
        self.scenes.draw(self.buffer)
        w, h = self.window.get_size()
        scale = max(1, min(w // self.base[0], h // self.base[1]))
        if scale == 1:
            self.window.blit(pygame.transform.scale(self.buffer, (w, h)), (0, 0))
        else:
            bw, bh = self.base[0] * scale, self.base[1] * scale
            scaled = pygame.transform.scale(self.buffer, (bw, bh))
            self.window.fill((6, 8, 16))
            self.window.blit(scaled, ((w - bw) // 2, (h - bh) // 2))
        pygame.display.flip()

    def run(self, scene, frames: int | None = None, on_frame: Callable | None = None,
            capture: str | None = None):
        """Run the loop. ``frames`` bounds it, which is how tests take screenshots."""
        self.running = True
        self.scenes.replace(scene)
        acc, last = 0.0, time.perf_counter()
        while self.running:
            now = time.perf_counter()
            acc += STEP_MS if self.headless else (now - last) * 1000.0
            last = now
            while acc >= STEP_MS:
                events = pygame.event.get()
                self.input.feed(events)
                for e in events:
                    if self.scenes.handle(e):
                        break
                if self.input.quit_requested():
                    self.running = False
                self.step()
                if on_frame:
                    on_frame(self, self.frame)
                if frames and self.frame >= frames:
                    self.running = False
                    break
                acc -= STEP_MS
            self.render()
            if self.headless:
                continue
            self.clock.tick(self.fps)
        if capture:
            pygame.image.save(self.buffer, capture)
        self.assets.flush()
        return self.buffer

    # -- sound ---------------------------------------------------------------------------
    def sfx(self, name: str):
        """Play a one-shot. Silent when the mixer has no device (CI, docker)."""
        if not self.sound_on:
            return None
        key = name if "/" in name else f"sfx/{name}"
        sound = self.sounds.get(key)
        if sound is None:
            try:
                sound = from_wav(self.assets.sprite(key).surface)
            except (UnknownAsset, pygame.error):
                return None
            self.sounds[key] = sound
        try:
            return sound.play()
        except pygame.error:  # pragma: no cover - depends on the host audio stack
            self.sound_on = False
            return None

    def music(self, name: str | None, volume: float = 0.5, force: bool = False):
        """Loop a track; switching to the same track again is a no-op."""
        if name == self.music_id and not force:
            return
        self.music_id = name
        if not self.sound_on:
            return
        try:
            if name is None:
                pygame.mixer.music.fadeout(150)
                return
            pygame.mixer.music.load(io.BytesIO(self.assets.sprite(f"music/{name}").surface))
            pygame.mixer.music.set_volume(self.volume * volume)
            pygame.mixer.music.play(-1)
        except (pygame.error, UnknownAsset):
            self.sound_on = False
