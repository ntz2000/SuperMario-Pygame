"""暂停菜单与 Game Over 画面。"""
from __future__ import annotations

import pygame

from ..engine.scene import Scene


class MenuScene(Scene):
    """暂停后 Esc 打开的菜单：继续 / 重开 / 回标题（压栈实现，关卡保留在下面）。"""

    name = "menu"
    opaque = False

    def __init__(self, app, data: dict, form: str = "small", carry: dict | None = None):
        super().__init__(app)
        self.data, self.form = data, form
        self.carry = carry or {}
        self.options = ["resume", "restart", "title"]
        self.index = 0

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return False
        if event.key in (pygame.K_UP, pygame.K_w):
            self.index -= 1
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.index += 1
        elif event.key in (pygame.K_SPACE, pygame.K_z, pygame.K_RETURN):
            self.pick()
        elif event.key == pygame.K_ESCAPE:
            self.pick()
        else:
            return False
        return True

    def pick(self):
        from .level import LevelScene
        from .title import TitleScene
        choice = self.options[self.index % len(self.options)]
        if choice == "resume":
            stack = self.app.scenes.stack
            if len(stack) >= 2 and getattr(stack[-2], "name", "") == "level":
                level = stack[-2]
                level.paused = False
                level.input.enabled = True
            self.app.scenes.pop()
        elif choice == "restart":
            self.app.scenes.fade_to(LevelScene(self.app, self.data, carry=self.carry))
        else:
            levels = getattr(self.app, "progress", {}).get("levels", {}) or self.data
            self.app.scenes.fade_to(TitleScene(self.app, levels))

    def draw(self, target):
        w, h = self.app.base
        panel = pygame.Surface((140, 74), pygame.SRCALPHA)
        panel.fill((16, 20, 38, 235))
        pygame.draw.rect(panel, (255, 240, 150, 255), (0, 0, 140, 2))
        target.blit(panel, (w // 2 - 70, h // 2 - 44))
        target.blit(pygame.font.Font(None, 24).render("PAUSED", True, (255, 246, 210)),
                    (w // 2 - 30, h // 2 - 38))
        f = pygame.font.Font(None, 19)
        for i, opt in enumerate(self.options):
            col = (255, 240, 150) if i == self.index % len(self.options) else (226, 226, 236)
            target.blit(f.render(opt.upper(), True, col), (w // 2 - 44, h // 2 - 14 + i * 17))


class GameOverScene(Scene):
    """Game Over：按跳跃回标题。"""

    name = "gameover"
    opaque = True

    def __init__(self, app, score: int = 0):
        super().__init__(app)
        self.score = score

    def on_enter(self, **kw):
        super().on_enter(**kw)
        self.app.music(None)
        self.app.sfx("death")

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return False
        if event.key in (pygame.K_SPACE, pygame.K_z, pygame.K_RETURN):
            from .title import TitleScene
            levels = getattr(self.app, "progress", {}).get("levels", {})
            self.app.scenes.fade_to(TitleScene(self.app, levels))
            return True
        return False

    def draw(self, target):
        w, h = self.app.base
        target.fill((12, 8, 18))
        big = pygame.font.Font(None, 40)
        f = pygame.font.Font(None, 18)
        for i, (txt, y) in enumerate((("G A M E   O V E R", h // 2 - 20),)):
            shadow = big.render(txt, True, (90, 20, 20))
            main = big.render(txt, True, (240, 240, 250))
            r = main.get_rect(center=(w // 2, y))
            target.blit(shadow, r.move(2, 2))
            target.blit(main, r)
        if self.score:
            target.blit(f.render(f"SCORE {self.score:06d}", True, (200, 200, 210)),
                        (w // 2 - 40, h // 2 + 6))
        hint = f.render("press JUMP to continue", True, (170, 170, 190))
        if int(self.time / 20) % 2:
            target.blit(hint, hint.get_rect(center=(w // 2, h // 2 + 30)))
