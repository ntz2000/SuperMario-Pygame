"""Developer helpers: an autopilot that plays a level so headless runs can be screened.

``--capture`` screenshots are useless if nobody is holding "right", so ``Bot`` reads the
tile grid ahead of the hero and presses the same buttons a human would. Tests and
visual reviews both drive the game through it.
"""
from __future__ import annotations

from .core.tiles import TILE


class Bot:
    """Hold right, jump at walls and pits, spin when it is stuck."""

    def __init__(self, run: bool = True, look_ahead: int = 3):
        self.run = run
        self.look_ahead = look_ahead
        self.scene = None
        self.jump_hold = 0     # 起跳后按住的帧数（避免探测消失后提前松键削减跳跃）

    def attach(self, app, scene):
        self.scene = scene
        app.on_step(self)

    def __call__(self, app, frame: int):
        # 跟随栈顶活动关卡（重生/换关后场景会换实例）
        scene = app.scenes.top if hasattr(app, "scenes") else self.scene
        if scene is None or not hasattr(scene, "player"):
            return
        inp = app.input
        p = scene.player
        if not p.alive:
            return
        inp.held_actions = set(inp.held_actions)          # tests may hand us a live set
        inp.press("right")
        if self.run:
            inp.press("run")
        if self.jump_hold > 0:
            self.jump_hold -= 1
            inp.press("jump")
        elif self._wall_ahead(scene, p) or self._pit_ahead(scene, p) \
                or self._enemy_ahead(scene, p):
            self.jump_hold = 16
            inp.press("jump")
        else:
            inp.release("jump")

    # -- readings ------------------------------------------------------------------------
    def _wall_ahead(self, scene, player) -> bool:
        b = player.body
        probe = pygame_rect(int(b.x + b.facing * (b.w / 2 + 3)), int(b.y - b.h / 2), 2, b.h - 6)
        # solid_cells 是生成器，bool() 恒真，必须用 any() 消费
        return any(True for _c, _k in scene.tilemap.solid_cells(probe))

    def _pit_ahead(self, scene, player) -> bool:
        b = player.body
        if not b.on_ground:
            return False
        probe = pygame_rect(int(b.x + b.facing * (b.w / 2 + self.look_ahead * TILE)),
                            int(b.y + 2), 2, 6)
        return not any(True for _c, _k in scene.tilemap.solid_cells(probe))

    def _enemy_ahead(self, scene, player) -> bool:
        """前方 26px、高度差 20px 内有敌人就跳（踩头或跃过）。"""
        b = player.body
        probe = pygame_rect(int(b.x + b.facing * 14) - 12, int(b.y) - 34, 26, 36)
        for a in scene.actors:
            if a is player or not getattr(a, "alive", False) or a.removed:
                continue
            if hasattr(a, "stomp") and probe.colliderect(a.rect):
                return True
        return False


def pygame_rect(x, y, w, h):
    import pygame

    return pygame.Rect(x, y, w, h)
