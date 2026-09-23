"""标题画面：选关开始，方向键浏览。"""
from __future__ import annotations

import pygame

from ..engine.scene import Scene


class TitleScene(Scene):
    name = "title"

    def __init__(self, app, levels: dict, on_start=None):
        super().__init__(app)
        self.levels = {k: v for k, v in levels.items() if not v.get("secret")}
        self.on_start = on_start
        self.index = 0
        self.names = list(self.levels)

    def on_enter(self, **kw):
        super().on_enter(**kw)
        self.names = list(self.levels)
        self.index = min(self.index, max(0, len(self.names) - 1))
        self.app.music("title")

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return False
        if event.key in (pygame.K_SPACE, pygame.K_z, pygame.K_RETURN):
            self.start()
            return True
        if event.key in (pygame.K_UP, pygame.K_w):
            self.index = (self.index - 1) % max(1, len(self.names))
            self.app.sfx("bump")
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.index = (self.index + 1) % max(1, len(self.names))
            self.app.sfx("bump")
        elif event.key == pygame.K_r:
            from ..data import save as saved
            saved.clear()
            prog = getattr(self.app, "progress", None)
            if prog is not None:
                prog["done"] = []
                prog["stars"] = {}
            self.app.sfx("shrink")
            return True
        return False

    def start(self):
        from .level import LevelScene
        if not self.names:
            return
        name = self.names[self.index]
        self.app.music(None)
        self.app.scenes.fade_to(LevelScene(self.app, self.levels[name]), id=name)

    def update(self):
        super().update()
        self.t = self.time / 60.0

    def draw(self, target):
        w, h = self.app.base
        for y in range(0, h, 3):
            t = y / (h - 1)
            pygame.draw.rect(target, tuple(round(a + (b - a) * t) for a, b in
                                           zip(pygame.Color("#2b6fd6"), pygame.Color("#a9e2ff"))),
                             pygame.Rect(0, y, w, 3))
        # 背景里奔跑的英雄
        hero = self.app.assets.sprite("hero.super.run").frame(int(self.time / 6) % 6)
        ground = h - 34
        target.blit(hero, (int(self.time * 0.8) % (w + 30) - 30, ground - hero.get_height()))
        for i in range(-1, 4):
            x = i * 90 - (self.time * 0.8 * 0.3) % 90
            self._hill(target, x, ground)
        big = pygame.font.Font(None, 44)
        small = pygame.font.Font(None, 17)
        title = big.render("SUPER PLUMBROS", True, (255, 246, 210))
        shadow = big.render("SUPER PLUMBROS", True, (60, 30, 10))
        r = title.get_rect(center=(w // 2, 46))
        target.blit(shadow, r.move(2, 3))
        target.blit(title, r)
        hint = small.render("press JUMP to start", True, (255, 255, 255))
        if int(self.time / 20) % 2:
            target.blit(hint, hint.get_rect(center=(w // 2, 74)))
        for i, name in enumerate(self.names):
            col = (255, 240, 150) if i == self.index else (230, 230, 240)
            label = self.levels[name].get("label", name)
            txt = small.render(label, True, col)
            target.blit(txt, txt.get_rect(midleft=(w // 2 - 16, 98 + i * 15)))
            stars = (getattr(self.app, "progress", {}) or {}).get("stars", {}).get(name, {})
            for j in range(3):
                x = w // 2 + 52 + j * 9
                if stars.get(j):
                    pygame.draw.circle(target, (255, 214, 90), (x, 99 + i * 15), 3)
                else:
                    pygame.draw.circle(target, (90, 100, 130), (x, 99 + i * 15), 3, 1)
        if self.names:
            arrow = small.render(">", True, (255, 255, 255))
            target.blit(arrow, (w // 2 - 26, 92 + self.index * 15))
        target.blit(small.render("R: reset save", True, (200, 200, 220)),
                    (8, h - 14))

    def _hill(self, target, x, ground):
        from ..engine.ink import Canvas, hexc
        c = Canvas((90, 26))
        c.ellipse((4, 8, 86, 40), hexc("#3fa535"))
        c.ellipse((-18, 14, 50, 40), hexc("#2c7d2a"))
        target.blit(c.finish(outline=0.0, light=(-1, -1), rim=0.2), (int(x), ground - 18))
