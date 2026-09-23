"""世界地图：节点连线，英雄在上面走，选关进入。"""
from __future__ import annotations

import pygame

from ..engine.scene import Scene


class WorldMapScene(Scene):
    name = "world"

    def __init__(self, app, nodes: list[dict], progress: dict | None = None):
        super().__init__(app)
        self.nodes = nodes
        self.progress = progress or {}
        self.index = min(1, max(0, len(nodes) - 1))

    def on_enter(self, **kw):
        super().on_enter(**kw)
        # 从完成的进度推进光标
        done = set(self.progress.get("done", []))
        for i, node in enumerate(self.nodes):
            if node["level"] in done:
                self.index = i
        self.app.music("map")

    def handle(self, event):
        if event.type != pygame.KEYDOWN:
            return False
        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.index = max(0, self.index - 1)
            self.app.sfx("bump")
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.index = min(len(self.nodes) - 1, self.index + 1)
            self.app.sfx("bump")
        elif event.key in (pygame.K_SPACE, pygame.K_z, pygame.K_RETURN):
            self.enter()
        else:
            return False
        return True

    def enter(self):
        from .level import LevelScene
        node = self.nodes[self.index]
        data = self.progress.get("levels", {}).get(node["level"])
        if data:
            self.app.music(None)
            self.app.scenes.fade_to(LevelScene(self.app, data), id=node["level"])

    def update(self):
        super().update()
        self.hero_x += (self.target_x() - self.hero_x) * 0.18

    hero_x = 0.0

    def target_x(self) -> float:
        if not self.nodes:
            return 0.0
        i = min(self.index, len(self.nodes) - 1)
        return (i + 0.6) * (self.app.base[0] / max(1, len(self.nodes)))

    def node_pos(self, i: int):
        w, h = self.app.base
        x = int((i + 0.6) * (w / max(1, len(self.nodes))))
        y = h // 2 + int((i % 2) * 36 - 18)
        return x, y

    def draw(self, target):
        w, h = self.app.base
        # 草地 + 天空渐变
        for y in range(0, h, 3):
            t = y / (h - 1)
            pygame.draw.rect(target, tuple(round(a + (b - a) * t) for a, b in
                                           zip(pygame.Color("#3f8f4f"), pygame.Color("#9fd8ff"))),
                             pygame.Rect(0, y, w, 3))
        f = pygame.font.Font(None, 15)
        done = set(self.progress.get("done", []))
        pts = [self.node_pos(i) for i in range(len(self.nodes))]
        if len(pts) >= 2:
            pygame.draw.lines(target, (240, 226, 170), False, pts, 3)
            pygame.draw.lines(target, (170, 140, 80), False, pts, 1)
        for i, ((x, y), node) in enumerate(zip(pts, self.nodes)):
            is_done = node["level"] in done
            # 节点：完成的实心金圆，当前的高亮
            if i == self.index:
                pygame.draw.circle(target, (255, 250, 220), (x, y), 9)
            pygame.draw.circle(target, (255, 214, 90) if is_done else (70, 90, 120),
                              (x, y), 7 if is_done else 6)
            if not is_done:
                pygame.draw.circle(target, (235, 235, 245), (x, y), 3)
            label = node["label"]
            txt = f.render(label, True, (250, 250, 250))
            target.blit(txt, txt.get_rect(center=(x, y + 15)))
            # 该关大金币收集情况
            stars = self.progress.get("stars", {}).get(node["level"], {})
            for j in range(3):
                sx = x - 10 + j * 10
                if stars.get(j):
                    pygame.draw.circle(target, (255, 214, 90), (sx, y - 11), 2)
                else:
                    pygame.draw.circle(target, (90, 100, 120), (sx, y - 11), 2, 1)
        # 行走中的英雄
        hero = self.app.assets.sprite("hero.small.run").frame(int(self.time / 5) % 6)
        hy = self.node_pos(self.index)[1] if self.nodes else h // 2
        target.blit(hero, (int(self.hero_x) - hero.get_width() // 2,
                           hy - hero.get_height() - 8))
        hint = f.render("LEFT/RIGHT choose   JUMP enter", True, (250, 250, 250))
        target.blit(hint, (8, h - 16))
