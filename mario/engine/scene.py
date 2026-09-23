"""Scene stack with fade transitions.

Scenes own a full screen (title, world map, a level, results). Overlay scenes such
as the pause menu are pushed on top of the scene below and receive input first.
"""
from __future__ import annotations

import pygame


class Scene:
    name = "scene"
    opaque = True  # opaque scenes clear the target before drawing
    native = False  # True=直接画到高清 buffer；False=画进 base 尺寸离屏再放大

    def __init__(self, app):
        self.app = app
        self.time = 0  # sim frames since entering
        self.entered = False

    def on_enter(self, **kwargs):
        self.entered = True

    def on_exit(self):
        pass

    def handle(self, event) -> bool:
        """Return True to swallow the event (and stop it reaching scenes below)."""
        return False

    def update(self):
        self.time += 1

    def draw(self, target: pygame.Surface):
        raise NotImplementedError


class Transition:
    """Black fade between scenes."""

    def __init__(self, color=(0, 0, 12), frames=14):
        self.color = color
        self.frames = frames
        self.t = 0
        self.phase = "in"  # in -> hold -> out
        self.queued = None

    @property
    def busy(self) -> bool:
        return self.phase != "done"

    def step(self) -> bool:
        """Advance; returns True while the stack should not simulate."""
        self.t += 1
        if self.phase == "in" and self.t >= self.frames:
            self.phase = "out"
            self.t = 0
            if self.queued:
                self.queued()
                self.queued = None
            return True
        if self.phase == "out" and self.t >= self.frames:
            self.phase = "done"
            return False
        return True

    def alpha(self) -> int:
        if self.phase == "in":
            return int(255 * min(1.0, self.t / max(1, self.frames)))
        if self.phase == "out":
            return int(255 * (1 - min(1.0, self.t / max(1, self.frames))))
        return 0

    def draw(self, target: pygame.Surface):
        a = self.alpha()
        if a <= 0:
            return
        veil = pygame.Surface(target.get_size(), pygame.SRCALPHA)
        veil.fill((*self.color, a))
        target.blit(veil, (0, 0))


class SceneManager:
    """Scene stack plus the fade that swaps one scene for the next."""

    def __init__(self, app):
        self.app = app
        self.stack: list[Scene] = []
        self.transition = Transition()
        self.transition.phase = "done"
        self._offscreen = None   # 像素风场景的高清放大中转

    @property
    def top(self) -> Scene | None:
        return self.stack[-1] if self.stack else None

    def push(self, scene: Scene, **kw):
        self.stack.append(scene)
        scene.on_enter(**kw)

    def pop(self):
        if self.stack:
            self.stack.pop().on_exit()

    def replace(self, scene: Scene, **kw):
        """Swap the base scene instantly (used by tests and boot)."""
        while self.stack:
            self.stack.pop().on_exit()
        self.push(scene, **kw)

    def fade_to(self, scene: Scene, **kw):
        """Fade out, swap, fade back in. Scenes only update once visible."""
        while len(self.stack) > 1:
            self.stack.pop().on_exit()
        self.transition.phase = "in"
        self.transition.t = 0
        self.transition.queued = lambda: self.replace(scene, **kw)

    def update(self):
        self.transition.step()
        scene = self.top
        if scene is not None and self.transition.phase != "in":
            scene.update()

    def handle(self, event) -> bool:
        for scene in reversed(self.stack):
            if scene.handle(event):
                return True
        return False

    def draw(self, target: pygame.Surface):
        for scene in reversed(self.stack):
            if getattr(scene, "native", False):
                scene.draw(target)
            else:
                # 像素风场景：画进 base 尺寸的离屏，再整数倍放大到高清 buffer
                if self._offscreen is None or self._offscreen.get_size() != self.app.base:
                    self._offscreen = pygame.Surface(self.app.base, pygame.SRCALPHA)
                if scene.opaque:
                    self._offscreen.fill((0, 0, 0, 0))
                scene.draw(self._offscreen)
                target.blit(pygame.transform.scale(self._offscreen, target.get_size()),
                            (0, 0))
            if scene.opaque:
                break
        self.transition.draw(target)
