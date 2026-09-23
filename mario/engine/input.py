"""Action-based input with press-edge tracking and short input buffers.

Platformers feel tight because of coyote time and jump buffering, so the layer in
front of the sim must know *when* a key was pressed, not just whether it is down.
"""
from __future__ import annotations

import pygame

# Sim runs at 60 Hz; buffers are counted in sim frames.
DEFAULT_BINDINGS = {
    "left": [pygame.K_LEFT, pygame.K_a],
    "right": [pygame.K_RIGHT, pygame.K_d],
    "up": [pygame.K_UP, pygame.K_w],
    "down": [pygame.K_DOWN, pygame.K_s],
    "run": [pygame.K_LSHIFT, pygame.K_z],
    "jump": [pygame.K_SPACE, pygame.K_k],
    "spin": [pygame.K_x, pygame.K_j],
    "action": [pygame.K_c, pygame.K_v],
    "pause": [pygame.K_RETURN],
    "menu_back": [pygame.K_ESCAPE],
}


class Input:
    def __init__(self, bindings: dict[str, list[int]] | None = None, frame_ms: float = 1000 / 60):
        self.bindings = {k: list(v) for k, v in (bindings or DEFAULT_BINDINGS).items()}
        self.frame_ms = frame_ms
        self._down: set[int] = set()
        self._pressed: set[int] = set()
        self._released: set[int] = set()
        self._age: dict[str, int] = {}  # action -> frames since last press
        self.enabled = True
        self._quit = False

    # -- events ----------------------------------------------------------------------
    def feed(self, events) -> None:
        for e in events:
            if e.type == pygame.KEYDOWN:
                self._press(e.key)
            elif e.type == pygame.KEYUP:
                self._release(e.key)
            elif e.type == pygame.QUIT:
                self._quit = True

    def _press(self, key):
        if key in self._down:
            return
        self._down.add(key)
        self._pressed.add(key)
        self._released.discard(key)   # 新按下使旧的释放边沿失效（同帧 up+down）
        for action, keys in self.bindings.items():
            if key in keys:
                self._age[action] = 0

    def _release(self, key):
        self._down.discard(key)
        self._released.add(key)

    # -- sampling ----------------------------------------------------------------------
    def advance(self):
        """Call once per sim frame: ages buffers, clears edges."""
        self._pressed.clear()
        self._released.clear()
        for k in list(self._age):
            self._age[k] += 1

    def held(self, action: str) -> bool:
        if not self.enabled:
            return False
        return any(k in self._down for k in self.bindings.get(action, ()))

    def pressed(self, action: str) -> bool:
        """True on the exact frame the key went down."""
        if not self.enabled:
            return False
        return any(k in self._pressed for k in self.bindings.get(action, ()))

    def released(self, action: str) -> bool:
        if not self.enabled:
            return False
        return any(k in self._released for k in self.bindings.get(action, ()))

    def buffered(self, action: str, frames: int = 6) -> bool:
        """True if ``action`` was pressed within the last ``frames`` frames."""
        if not self.enabled:
            return False
        age = self._age.get(action, 999)
        return age <= frames

    def buffer_age(self, action: str) -> int:
        return self._age.get(action, 999)

    def axis_x(self) -> int:
        return (1 if self.held("right") else 0) - (1 if self.held("left") else 0)

    def axis_y(self) -> int:
        return (1 if self.held("down") else 0) - (1 if self.held("up") else 0)

    def quit_requested(self) -> bool:
        return bool(self._quit)

    def bind(self, action: str, keys: list[int]):
        self.bindings[action] = list(keys)


class VirtualInput:
    """The same surface as :class:`Input`, driven by code instead of a keyboard.

    Tests and headless screenshots need to hold a button for N frames without a real
    event queue, and they need the same press-edge bookkeeping the real input has.
    """

    def __init__(self):
        self.enabled = True
        self.held_actions: set[str] = set()
        self._pressed: set[str] = set()
        self._released: set[str] = set()
        self._age: dict[str, int] = {}
        self._quit = False

    def press(self, *actions: str):
        for a in actions:
            self.held_actions.add(a)
            self._pressed.add(a)
            self._released.discard(a)   # 新按下使旧的释放边沿失效
            self._age[a] = 0

    def release(self, *actions: str):
        for a in (actions or tuple(self.held_actions)):
            self.held_actions.discard(a)
            self._released.add(a)

    def feed(self, events=()):
        return None

    def advance(self):
        self._pressed.clear()
        self._released.clear()
        for k in list(self._age):
            self._age[k] += 1

    def held(self, action: str) -> bool:
        return self.enabled and action in self.held_actions

    def pressed(self, action: str) -> bool:
        return self.enabled and action in self._pressed

    def released(self, action: str) -> bool:
        return self.enabled and action in self._released

    def buffered(self, action: str, frames: int = 6) -> bool:
        return self.enabled and self._age.get(action, 999) <= frames

    def buffer_age(self, action: str) -> int:
        return self._age.get(action, 999)

    @property
    def _on(self):
        return self.held_actions if self.enabled else ()

    def axis_x(self) -> int:
        return (1 if "right" in self._on else 0) - (1 if "left" in self._on else 0)

    def axis_y(self) -> int:
        return (1 if "down" in self._on else 0) - (1 if "up" in self._on else 0)

    def quit_requested(self) -> bool:
        return self._quit

    def request_quit(self):
        self._quit = True
