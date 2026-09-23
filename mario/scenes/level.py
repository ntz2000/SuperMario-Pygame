"""关卡场景：整个"世界"的实现。

场景本身充当 actors 拿到的 ``world`` 对象：持有瓦片网格、镜头、actor 列表，
并提供它们要调用的小动词（``spawn``、``sfx``、``fx``、``shake``、``fluid_at``）。
交互规则（踩敌人、顶砖、吃金币、搬龟壳）集中在这里，让每个 actor 保持小巧。

阶段状态机：``play`` → ``death``（重生 / Game Over）或 ``win``（旗杆序列 → 结算）
或 ``pipe``（管道下沉 → 目标关卡）。
"""
from __future__ import annotations

import math
import warnings

import pygame

from ..core.physics import ONE_WAY, SOLID
from ..core.tiles import TILE, default_table
from ..core.tilemap import TileMap
from ..core.tuning import TUNE
from ..engine.camera import Camera
from ..engine.ink import hexc
from ..engine.scene import Scene
from ..game.player import Player

BUMP_TIME = 0.24      # 顶砖动画时长
PIT_MARGIN = 24       # 掉出底部多少像素算坠亡


class LevelScene(Scene):
    name = "level"

    def __init__(self, app, data: dict, carry: dict | None = None):
        super().__init__(app)
        self.data = data
        theme_name = data.get("theme", "overworld")
        self.tilemap = TileMap(data["rows"], default_table(), theme=theme_name)
        self.tilemap.bind(app.assets)
        self.theme = self.tilemap.table.theme(theme_name)
        w, h = self.tilemap.pixel_size
        # 边界是整个关卡的像素范围；Camera 在其中夹紧视口
        self.camera = Camera(app.base, (0, 0, w, h))
        self.actors = []
        self.fx_list = []
        self.bumps: dict[tuple[int, int], float] = {}    # cell -> 顶起动画剩余时间
        self.multi: dict[tuple[int, int], dict] = {}     # 多币块状态
        carry = carry or {}
        self.score = carry.get("score", data.get("score", 0))
        self.coins = carry.get("coins", data.get("coins", 0))
        self.lives = carry.get("lives", data.get("lives", 4))
        self.checkpoint = carry.get("checkpoint")        # (x, y) 像素
        self._hits: list[pygame.Rect] = []
        self.next_level = ""
        self.next_spawn = ""
        self.time_left = data.get("time", 320)
        self.paused = False
        self.phase = "play"        # play | death | win | pipe
        self.phase_t = 0.0
        self.goal = None           # 终点旗杆（win 序列用）
        self._decor_strips = None  # 背景贴片缓存（_decor 惰性生成）
        self._hud_txt = {}         # HUD 文本缓存（数值不变就不重渲染）
        self.font = pygame.font.Font(None, 15)
        self.big = pygame.font.Font(None, 24)
        self.fireworks_done = set()

    # -- world 小动词 ---------------------------------------------------------------------
    @property
    def assets(self):
        return self.app.assets

    @property
    def input(self):
        return self.app.input

    def sfx(self, name: str):
        self.app.sfx(name)

    def fx(self, name: str, pos, **kw):
        self.fx_list.append(dict(name=name, x=pos[0], y=pos[1], t=0.0, **kw))

    def shake(self, amount: float):
        self.camera.shake = max(self.camera.shake, amount)

    def spawn(self, actor_cls, x, y, **kw):
        actor = actor_cls(self, x, y, **kw)
        self.actors.append(actor)
        return actor

    def fluid_at(self, rect: pygame.Rect) -> bool:
        return any(tile and tile.fluid for _c, tile in self.tilemap.cells_in(rect))

    def ladder_at(self, rect: pygame.Rect) -> bool:
        return any(tile and tile.climbable for _c, tile in self.tilemap.cells_in(rect))

    # -- 计分 ------------------------------------------------------------------------------
    def add_score(self, amount: int, pos=None):
        self.score += amount
        if amount >= 500 and pos is not None:
            self.fx("pop", pos)

    def collect_coin(self, pos):
        self.coins += 1
        self.add_score(100, pos)
        self.fx("coin", pos)
        self.sfx("coin")
        if self.coins and self.coins % 100 == 0:
            self.lives += 1
            self.sfx("1up")

    def collect_starcoin(self, idx: int, pos, level: str | None = None):
        key = level or self.id
        prog = getattr(self.app, "progress", None) or {}
        stars = prog.setdefault("stars", {}).setdefault(key, {})
        if not stars.get(idx):
            stars[idx] = True
            self.add_score(1000, pos)
            self.sfx("starcoin")
            for i in range(3):
                self.fx("sparkle", (pos[0] + math.sin(i * 2.1) * 8, pos[1] + i * 4))
            self._persist()

    def _persist(self):
        """进度落盘（过关/收大金币时）。"""
        try:
            from ..data import save as saved
            saved.save(self.app.progress)
        except (OSError, ValueError):
            pass

    def _stars(self) -> dict:
        prog = getattr(self.app, "progress", None) or {}
        stars = prog.setdefault("stars", {})
        return stars.setdefault(self.id if hasattr(self, "id") else
                                 self.data.get("label", "?"), {})

    def combo_score(self) -> int | None:
        """踩踏连击：第 N 次不落地连续踩给 TUNE.combo[N-1]，超出给 1UP。"""
        i = min(self.player.combo, len(TUNE.combo) - 1)
        val = TUNE.combo[i]
        if self.player.combo >= len(TUNE.combo):
            self.lives += 1
            self.sfx("1up")
            return None
        return val

    def _carry(self) -> dict:
        return dict(score=self.score, coins=self.coins, lives=self.lives)

    # -- 生命周期 ---------------------------------------------------------------------------
    def on_enter(self, id: str = "", spawn: str = "", **kw):
        super().on_enter(**kw)
        # 幂等：重复进入时清掉旧对象，防止双份玩家
        self.actors = []
        self.fx_list = []
        self.id = id or self.data.get("label", "level")
        if self.data.get("music"):
            self.app.music(self.data["music"])
        spec = dict(self.data["player"])
        sp = self.data.get("spawns", {}).get(spawn)
        if sp:
            spec.update(sp)
            px, py = spec["x"] * TILE + TILE / 2, spec["y"] * TILE + TILE
        elif self.checkpoint and not spawn:
            # 死亡复活：出生在检查点（checkpoint 存的就是与 Player 同基准的像素坐标）
            px, py = self.checkpoint
        else:
            px, py = spec["x"] * TILE + TILE / 2, spec["y"] * TILE + TILE
        self.player = Player(self, px, py, spec.get("form", "small"))
        self.actors.append(self.player)
        for obj in self.data.get("objects", []):
            from ..game import registry
            cls = registry.actor_for(obj["t"])
            if cls is not None:
                self.actors.append(cls(self, obj["x"] * TILE + TILE / 2,
                                      obj["y"] * TILE + TILE,
                                      **{k: v for k, v in obj.items()
                                         if k not in ("t", "x", "y")}))
        self.camera.center_on((px, py))
        self.camera.follow(self.player.rect, 0, snap=True)
        # 从检查点复活时刷掉已收集的大金币
        for a in self.actors:
            if type(a).__name__ == "StarCoin" and self._stars().get(a.idx):
                a.kill()

    def handle(self, event):
        """Enter 暂停；Esc 从暂停进菜单（菜单压栈，关卡保留）。"""
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_RETURN and self.phase == "play":
            self.paused = not self.paused
            self.input.enabled = not self.paused
            return True
        if event.key == pygame.K_ESCAPE and self.paused:
            from .menu import MenuScene
            self.app.scenes.push(MenuScene(self.app, self.data, self.player.form,
                                           carry=self._carry()))
            return True
        return False

    # -- 主循环 ---------------------------------------------------------------------------
    def update(self):
        if self.paused:
            return
        super().update()
        dt = 1 / 60.0
        self._hits = []
        if self.phase == "play":
            self.time_left = max(0, self.time_left - dt)
            if self.time_left <= 0:
                self.player.kill_outright(self)   # 超时死亡
        for actor in list(self.actors):
            if actor.alive and not getattr(actor, "carried", False):
                if actor is self.player and self.phase == "pipe":
                    continue    # 管道下沉由 _pipe_seq 独占驱动，物理会把玩家弹回管口
                actor.update(self)
        if self.phase == "play":
            self._hidden_probe()
            self._spike_check()
            self._tile_hits()
            self._collisions()
            self._shell_hits()
            self._star_music()
        elif self.phase == "death":
            self._death_seq()
        elif self.phase == "win":
            self._win_seq()
        elif self.phase == "pipe":
            self._pipe_seq()
        self.actors = [a for a in self.actors if not a.removed]
        for f in self.fx_list:
            f["t"] += dt
            f["x"] += f.get("vx", 0.0)
            f["vy"] = f.get("vy", 0.0) + f.get("g", 0.0) * dt
            f["y"] += f["vy"]
        self.fx_list = [f for f in self.fx_list if f["t"] < f.get("life", 0.5)]
        for k in list(self.bumps):
            self.bumps[k] -= dt
            if self.bumps[k] <= 0:
                del self.bumps[k]
        if self.player.alive and self.phase in ("play", "win", "pipe"):
            self.camera.follow(self.player.rect, self.player.body.vx)
        self.phase_t += dt

    # -- 玩家交互 -----------------------------------------------------------------------------
    def on_land(self, actor):
        # 注意：move_y 调到这里之前已把 on_ground 置 True，不能用它判"刚落地"；
        # 该方法只被 contact.ground 且 not was_on_ground 的帧调用，不会连响。
        if actor is self.player:
            self.sfx("land")

    def on_ceiling(self, actor, cell: pygame.Rect):
        if actor is self.player:
            self._hits = [cell]

    def on_death(self, player):
        """玩家死亡：进入 death 阶段（音乐停、死亡音效、控制冻结）。"""
        if self.phase != "play":
            return
        self.phase = "death"
        self.phase_t = 0.0
        self.player.dying = True
        self.player.locked = True
        self.player.body.vx = 0.0
        self.player.body.vy = -4.4
        self.player.combo = 0
        self.app.music(None)
        self.sfx("death")

    def on_checkpoint(self, pos):
        self.checkpoint = pos
        self.fx("sparkle", (pos[0], pos[1] - 40))

    def on_boss_dead(self, boss):
        self.phase = "win"      # Boss 倒下即通关
        self.phase_t = -0.6     # 稍作停顿再进入庆祝
        self.player.locked = True
        self.score += int(self.time_left) * 5
        self.app.music("clear")
        self.sfx("clear")

    def finish(self, flag):
        """碰到旗杆：结算剩余时间，进入通关序列。"""
        if self.phase != "play":
            return
        self.phase = "win"
        self.phase_t = 0.0
        self.goal = flag
        self.player.locked = True
        self.player.combo = 0
        self.player.drop_held(self)
        self.player.body.vx = 0.0
        self.score += int(self.time_left) * 5
        self.app.music("clear")
        self.sfx("clear")

    def enter_pipe(self, target: str):
        if self.phase != "play":
            return
        self.phase = "pipe"
        self.phase_t = 0.0
        self.player.locked = True
        self.player.drop_held(self)
        self.player.body.vx = 0.0
        if "@" in target:
            self.next_level, self.next_spawn = target.split("@", 1)
        else:
            self.next_level, self.next_spawn = target, ""
        self.sfx("pipe")

    def action_pressed(self, player):
        """action 键：拿起脚边的静止龟壳，或把手里的东西扔出去。"""
        if player.held is not None:
            shell = player.held
            player.held = None
            player.holding = ""
            shell.carried = False
            shell.state = "slide"
            shell.dir = player.body.facing
            shell.body.x = player.body.x + player.body.facing * 8
            shell.body.y = player.body.y - 2
            shell.wake_t = 0.0
            self.sfx("kick")
            return
        # 附近 16px 内有静止的壳就搬起
        for a in self.actors:
            if getattr(a, "state", "") == "shell" and not getattr(a, "carried", False) \
                    and a.alive and abs(a.body.x - player.body.x) < 16 \
                    and abs(a.body.y - player.body.y) < 20:
                a.carried = True
                player.held = a
                player.holding = "shell"
                self.sfx("bump")
                return
        self.throw_item(player)

    def throw_item(self, player):
        """火形态扔火球。"""
        if player.form == "fire":
            from ..game.objects import Fireball
            self.spawn(Fireball, player.body.x + player.body.facing * 6,
                       player.body.y - player.body.h * 0.6, dir=player.body.facing)
            self.sfx("throw")

    def pound_impact(self, player):
        """下砸落地：震屏、震死附近地面敌人、砸开脚下的可破坏块。"""
        self.shake(2.4)
        self.sfx("stomp")
        pos = player.body.center
        for _ in range(4):
            self.fx("dust", (pos[0] + math.cos(_ * 1.57) * 7, pos[1] + 3))
        for a in list(self.actors):
            if a is player or a.removed or not getattr(a, "hurt", None) \
                    or getattr(a, "tag", "") in ("proj", "foe_proj"):
                continue
            if abs(a.body.x - player.body.x) < 40 and abs(a.body.y - player.body.y) < 14 \
                    and a.body.on_ground is not False and a.body.vy == 0:
                a.hurt(self, player)
        feet = player.body.rect.move(0, 2)
        for (tx, ty), tile in list(self.tilemap.cells_in(feet)):
            # 1px 向下容差：落地吸附在块顶 +0.001，不能把要砸的块过滤掉
            if tile is None or ty * TILE < player.body.y - 1:
                continue
            code = self.tilemap.at(tx, ty)
            tile = self.tilemap.tile(tx, ty)
            if tile is None:
                continue
            if tile.name == "note":
                player.body.vy = -TUNE.pound_bounce
                self.sfx("note")
                self.bumps[(tx, ty)] = BUMP_TIME
                return
            if tile.destructible:
                self.break_block(tx, ty, tile)
            elif tile.bumpable:
                self.bumps[(tx, ty)] = BUMP_TIME
                self._bump_yield(tx, ty, tile)

    def mega_smash(self, cell: pygame.Rect):
        """巨大形态撞碎挡路的砖。"""
        tx, ty = cell.centerx // TILE, cell.centery // TILE
        tile = self.tilemap.tile(tx, ty)
        if tile is not None and tile.destructible:
            self.break_block(tx, ty, tile)

    def note_check(self, cell: pygame.Rect, player):
        """落到音符块上：大弹跳。"""
        tx, ty = cell.centerx // TILE, cell.bottom // TILE - 1
        tile = self.tilemap.tile(tx, ty)
        if tile is not None and tile.name == "note":
            player.body.vy = -TUNE.note_bounce
            player.combo = 0
            self.sfx("note")
            self.bumps[(tx, ty)] = BUMP_TIME
            self.fx("sparkle", ((tx + 0.5) * TILE, ty * TILE))

    def gravity(self, actor) -> float:
        return 0.30 if actor.tag != "player" else 0.38

    # -- 阶段序列 ---------------------------------------------------------------------------
    def _death_seq(self):
        if getattr(self, "_death_fired", False) or self.phase_t <= 2.0:
            return
        self._death_fired = True
        self.lives -= 1
        if self.lives <= 0:
            from .menu import GameOverScene
            self.app.scenes.fade_to(GameOverScene(self.app, self.score))
        else:
            self.app.scenes.fade_to(LevelScene(
                self.app, self.data,
                carry=dict(**self._carry(), checkpoint=self.checkpoint)))

    def _win_seq(self):
        t = self.phase_t
        p = self.player
        if t < 0:
            return
        if self.goal is not None:
            if t < 0.8:      # 顺杆滑下
                p.body.y = min(self.goal.body.y, p.body.y + 2.6)
                self.goal.flag_t = max(0.0, 1.0 - t / 0.8)
                p.set_anim("jump")
            elif t < 1.1:    # 跳离旗杆
                p.body.facing = 1
                p.body.vx = 1.4
                p.body.vy = -2.6
        elif t < 1.0:
            pass
        # 烟花
        for i, at in enumerate((1.4, 1.8, 2.2)):
            if t >= at and i not in self.fireworks_done:
                self.fireworks_done.add(i)
                w, h = self.app.base
                self.fx("firework", (self.camera.pos[0] + w * (0.3 + i * 0.2),
                                     self.camera.pos[1] + h * (0.25 + 0.12 * i)))
                self.sfx("coin")
                self.shake(1.0)
        if t > 1.1:          # 向右走离场
            p.body.vx = 1.5
            p.set_anim("walk")
            p.fps = 10
        if t > 3.0:
            self.advance()

    def _pipe_seq(self):
        # 玩家沉入管道（此阶段玩家 update 被跳过，动画计时在这里推进）
        self.player.t += 1 / 60.0
        self.player.body.y += 0.9
        self.player.set_anim("crawl")
        if self.phase_t > 0.6:
            self._goto(self.next_level, self.next_spawn)

    def advance(self):
        """离开本关去下一关（或回世界地图）。"""
        if self.phase == "death":
            return
        order = [k for k, v in (getattr(self.app, "progress", {}).get("levels", {})).items()
                 if not v.get("secret")]
        if self.next_level:
            nxt = self.next_level
        elif order and self.id in order and order.index(self.id) + 1 < len(order):
            nxt = order[order.index(self.id) + 1]
        else:
            nxt = ""
        if not self.player.alive:
            return
        self.app.progress.setdefault("done", [])
        if self.id not in self.app.progress["done"]:
            self.app.progress["done"].append(self.id)
        self._persist()
        if nxt:
            self._goto(nxt, "")
        else:
            from .worldmap import WorldMapScene
            self.app.scenes.fade_to(WorldMapScene(
                self.app, [dict(level=k, label=v.get("label", k))
                           for k, v in self.app.progress["levels"].items()
                           if not v.get("secret")], self.app.progress))

    def _goto(self, level_id: str, spawn: str):
        data = self.app.progress["levels"].get(level_id) or \
            (self.data if level_id == self.id else None)
        if data is None:
            data = {**self.data, "label": level_id}
        self.app.scenes.fade_to(LevelScene(self.app, data, carry=self._carry()),
                                id=level_id, spawn=spawn)

    # -- 每帧检测 -----------------------------------------------------------------------------
    def _hidden_probe(self):
        """上升中顶到隐藏块：显形并变成用过的块。"""
        p = self.player
        if p.dying or p.body.vy >= 0:
            return
        probe = p.body.rect.move(0, -2)
        for (tx, ty), tile in list(self.tilemap.cells_in(probe)):
            if tile is not None and tile.hidden:
                self.tilemap.set(tx, ty, "X")
                self.bumps[(tx, ty)] = BUMP_TIME
                self.sfx("reveal")
                if tile.item == "coin":
                    self.collect_coin(((tx + 0.5) * TILE, ty * TILE))

    def _spike_check(self):
        """踩在尖刺上：受伤。"""
        p = self.player
        if p.dying or p.invuln > 0 or p.star > 0 or p.mega_t > 0:
            return
        feet = p.body.rect.move(0, 1).inflate(-4, 0)
        for _c, tile in self.tilemap.cells_in(feet):
            if tile is not None and tile.name == "spike":
                p.hurt(self)
                return

    def _tile_hits(self):
        """玩家头顶顶到的方块。"""
        for cell in self.player_hits:
            tx, ty = int(cell.centerx) // TILE, int(cell.top) // TILE
            tile = self.tilemap.tile(tx, ty)
            if tile is None or not tile.bumpable or self.phase != "play":
                continue
            code = self.tilemap.at(tx, ty)
            self.bumps[(tx, ty)] = BUMP_TIME
            if tile.name == "note":
                self.sfx("note")            # 音符块：只响不消耗
                continue
            if code == "C":                 # 多币块：限时连顶
                self._multi_coin(tx, ty)
                continue
            if tile.item:
                self.pop_block(tx, ty, tile)
                continue
            if tile.destructible and (self.player.pound or
                                      self.player.form in ("super", "fire", "mega")):
                self.break_block(tx, ty, tile)
                continue
            self.sfx("bump")

    def _multi_coin(self, tx, ty):
        st = self.multi.setdefault((tx, ty), dict(n=0, t=0.0))
        now = self.time / 60.0               # Scene.time 是帧数，换算成秒
        if st["n"] == 0:
            st["t"] = now                    # 第一顶启动 4 秒倒计时
        st["n"] += 1
        self.collect_coin(((tx + 0.5) * TILE, ty * TILE - 6))
        from ..game.objects import BlockCoin
        self.spawn(BlockCoin, (tx + 0.5) * TILE, ty * TILE)
        if st["n"] >= 10 or (now - st["t"]) > 4.0:
            self.tilemap.set(tx, ty, "X")

    def pop_block(self, tx, ty, tile):
        """顶出道具（或弹出金币）。"""
        self.tilemap.set(tx, ty, "X")
        if tile.item == "coin":
            self.collect_coin(((tx + 0.5) * TILE, ty * TILE - 4))
            from ..game.objects import BlockCoin
            self.spawn(BlockCoin, (tx + 0.5) * TILE, ty * TILE)
            return
        from ..game import registry
        cls = registry.actor_for(tile.item)
        if cls is not None:
            self.spawn(cls, (tx + 0.5) * TILE, ty * TILE, pop=True)
        else:
            warnings.warn(f"未注册的道具类型 {tile.item!r}（tile={tile.code}），产出被丢弃",
                          stacklevel=2)

    def break_block(self, tx, ty, tile):
        self.tilemap.set(tx, ty, "")
        self.fx("hit", ((tx + 0.5) * TILE, (ty + 0.5) * TILE))
        # 四块旋转碎片
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            self.fx("shard", ((tx + 0.5) * TILE + dx * 4, (ty + 0.5) * TILE + dy * 4),
                    vx=dx * 1.4, vy=dy * 1.2 - 1.6, g=0.3, life=0.55)
        self.score += 10
        self.sfx("break")
        self.shake(0.8)

    def _bump_yield(self, tx, ty, tile):
        if tile.item and tile.item != "note":
            self.pop_block(tx, ty, tile)
        else:
            self.sfx("bump")

    @property
    def player_hits(self):
        """本帧玩家头顶顶到的格子（由 Player 经 move_y 触发）。"""
        return self._hits

    # -- actor 交互 -----------------------------------------------------------------------------
    def _collisions(self):
        """玩家与 actor 接触：拾取、踩踏、弹簧、敌人伤害。"""
        p = self.player
        if not p.alive:
            return
        for a in list(self.actors):
            if a is p or a.removed or not a.alive or getattr(a, "carried", False):
                continue
            if hasattr(a, "collect") and a.rect.colliderect(p.rect):
                a.collect(self, p)
                continue
            if hasattr(a, "bounce") and p.body.vy > 0 and p.rect.bottom >= a.rect.top - 2 \
                    and a.rect.colliderect(p.rect.inflate(0, 6)):
                p.body.y = a.rect.top
                p.body.vy = a.bounce(p)
                continue
            if not getattr(a, "collides_player", True) or not a.rect.colliderect(p.rect):
                continue
            if getattr(a, "tag", "") == "proj":
                continue
            if getattr(a, "tag", "") == "foe_proj":
                p.hurt(self)
                continue
            if p.dying:
                continue
            landing = (p.body.vy > 0.5 and p.rect.bottom - a.rect.top < 9)
            if p.star > 0 or p.mega_t > 0:
                if hasattr(a, "hurt"):
                    a.hurt(self, p)
                continue
            if hasattr(a, "stomp") and (landing or getattr(a, "state", "") == "shell"):
                if a.stomp(self, p):
                    val = self.combo_score()
                    self.player.combo += 1           # 连击递增（落地/死亡处已清零）
                    if val:
                        self.add_score(val, a.body.center)
                    if landing:
                        p.body.y = a.rect.top        # 拉到敌人头顶再弹起，避免侧碰判伤
                        p.body.vy = -TUNE.stomp_bounce
                    p.body.on_ground = True
                elif p.spinning and landing:
                    p.body.y = a.rect.top
                    p.body.vy = -TUNE.stomp_bounce    # 旋转跳可从刺敌身上弹开
                else:
                    p.hurt(self)
            else:
                # 食人花等不可踩的接触物：直接受伤
                p.hurt(self)

        # 玩家火球 vs 敌人
        for proj in [a for a in self.actors if getattr(a, "tag", "") == "proj" and a.alive]:
            for foe in self.actors:
                if foe is self.player or getattr(foe, "tag", "") in ("proj", "foe_proj") \
                        or not foe.alive or not foe.body or getattr(foe, "carried", False):
                    continue    # 玩家自己绝不能当敌人（否则扔火球瞬间崩溃）
                if proj.rect.colliderect(foe.rect) and hasattr(foe, "hurt"):
                    foe.hurt(self, proj)
                    proj.kill()
                    break

    def _shell_hits(self):
        """滑行龟壳 vs 其他敌人。"""
        shells = [a for a in self.actors if getattr(a, "state", "") == "slide" and a.alive]
        if not shells:
            return
        for shell in shells:
            for foe in self.actors:
                if foe is shell or foe.removed or not foe.alive \
                        or getattr(foe, "tag", "") in ("proj", "foe_proj") \
                        or getattr(foe, "carried", False) or not hasattr(foe, "hurt"):
                    continue
                if foe is self.player:
                    continue
                if shell.rect.colliderect(foe.rect) and getattr(foe, "state", "") != "slide":
                    foe.hurt(self, shell)

    def _star_music(self):
        """无敌星的专属 BGM 切换。"""
        want = "star" if self.player.star > 0.4 else self.data.get("music")
        if want and self.app.music_id != want:
            self.app.music(want)

    # -- 绘制 ---------------------------------------------------------------------------
    def draw(self, target: pygame.Surface):
        self._sky(target)
        self._decor(target)
        view = self.camera.view_rect
        self.tilemap.draw(target, view, bumps=self.bumps)
        for actor in sorted(self.actors, key=lambda a: a.z):
            if getattr(actor, "carried", False):
                continue
            actor.draw(target, self.camera)
        for f in self.fx_list:
            surf = self.assets.sprite(f"fx/{f['name']}").frame(f["t"] * 12)
            x, y = self.camera.to_screen(f["x"] - surf.get_width() / 2,
                                        f["y"] - surf.get_height() / 2)
            target.blit(surf, (x, y))
        self._hud(target)
        if self.phase == "win" and self.phase_t > 1.2:
            self._clear_text(target)
        if self.paused:
            self._pause(target)

    # -- 背景 / HUD ---------------------------------------------------------------------------
    def _sky(self, target):
        top, bottom = hexc(self.theme.sky[0])[:3], hexc(self.theme.sky[1])[:3]
        h = self.app.base[1]
        for y in range(0, h, 3):
            t = y / max(1, h - 1)
            row = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
            pygame.draw.rect(target, row, pygame.Rect(0, y, self.app.base[0], 3))

    def _decor(self, target):
        """视差山丘、云、灌木——按滚动速度的一部分移动。

        图案只依赖主题（常量），与滚动无关；按场景实例缓存两张贴片，
        每帧只剩十几次 blit（原来每帧新建 13 个 Surface + 45 个 PIL Canvas）。
        """
        if self._decor_strips is None:
            hill, hill_d, cloud, bush = (self.theme.hill, self.theme.hill_d,
                                         self.theme.cloud, self.theme.bush)
            hills = pygame.Surface((96, 48), pygame.SRCALPHA)
            c_ellipse(hills, (6, 20, 90, 48), hill)
            c_ellipse(hills, (-20, 26, 60, 48), hill_d)
            c_ellipse(hills, (56, 34, 92, 48), bush)
            clouds = pygame.Surface((128, 40), pygame.SRCALPHA)
            for cx, cy, r in ((20, 22, 9), (34, 18, 12), (52, 22, 8), (92, 14, 10)):
                c_ellipse(clouds, (cx - r, cy - r * 0.7, cx + r, cy + r), cloud)
            self._decor_strips = (hills, clouds)
        hills, clouds = self._decor_strips
        ox, _ = self.camera.offset
        base = self.app.base[1]
        for i in range(-1, self.app.base[0] // 96 + 2):
            x = i * 96 - (ox * 0.28) % 96
            target.blit(hills, (x, base - 48))
        for i in range(-1, self.app.base[0] // 128 + 2):
            x = i * 128 - (ox * 0.14) % 128
            target.blit(clouds, (x, 12 + (i % 3) * 6))

    def _hud_text(self, key, text, color):
        """文本只在内容变化时重渲染。"""
        ent = self._hud_txt.get(key)
        if ent is None or ent[0] != (text, color):
            ent = self._hud_txt[key] = ((text, color), self.font.render(text, True, color))
        return ent[1]

    def _hud(self, target):
        # 生命：小英雄头像 ×N
        hero = self.assets.sprite("hero.small.idle").frame(0)
        target.blit(hero, (5, 4))
        target.blit(self._hud_text("lives", f"x{self.lives}", (255, 255, 255)), (14, 6))
        # 金币：图标 ×N
        coin = self.assets.sprite("item/coin").frame(self.time * 0.15)
        target.blit(coin, (34, 4))
        target.blit(self._hud_text("coins", f"x{self.coins:02d}", (255, 240, 150)), (44, 6))
        # 分数 / 时间
        target.blit(self._hud_text("score", f"SCORE {self.score:06d}", (255, 255, 255)),
                    (62, 6))
        tint = (255, 120, 120) if self.time_left < 60 else (255, 255, 255)
        target.blit(self._hud_text("time", f"TIME {int(self.time_left):03d}", tint),
                    (self.app.base[0] - 34, 6))
        # 大金币三槽
        stars = self._stars()
        for i in range(3):
            got = stars.get(i)
            x = self.app.base[0] - 92 + i * 11
            surf = self.assets.sprite("item/bigcoin").frame(0) if got else None
            if surf is not None:
                s = pygame.transform.scale(surf, (9, 12))
                target.blit(s, (x, 4))
            else:
                pygame.draw.circle(target, (90, 100, 120), (x + 4, 10), 4, 1)

    def _clear_text(self, target):
        w, h = self.app.base
        txt = self.big.render("COURSE CLEAR!", True, (255, 246, 210))
        shadow = self.big.render("COURSE CLEAR!", True, (40, 20, 60))
        r = txt.get_rect(center=(w // 2, h // 2 - 6))
        target.blit(shadow, r.move(1, 2))
        target.blit(txt, r)

    def _pause(self, target):
        veil = pygame.Surface(self.app.base, pygame.SRCALPHA)
        veil.fill((10, 12, 24, 170))
        target.blit(veil, (0, 0))
        txt = self.big.render("PAUSED", True, (255, 255, 255))
        target.blit(txt, txt.get_rect(center=(self.app.base[0] // 2, self.app.base[1] // 2)))


def c_ellipse(surf, box, color):
    """背景用的软圆团：山丘 / 灌木 / 云。"""
    from ..engine.ink import Canvas
    c = Canvas((int(box[2] - box[0]), int(box[3] - box[1])))
    c.ellipse((0, 0, box[2] - box[0], box[3] - box[1]), hexc(color)[:3] + (255,))
    surf.blit(c.finish(outline=0.0, light=(-1, -1), rim=0.22), (int(box[0]), int(box[1])))
