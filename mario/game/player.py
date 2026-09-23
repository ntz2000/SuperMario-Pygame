"""玩家角色：NSMB 风格的地面/空中操控、形态与招式。

移动手感由 :mod:`mario.core.tuning` 里的数值决定：走/跑各有极速，急刹比滑行
减速更狠，上升中按住跳跃减轻重力，跳跃输入有预输入缓冲，起跳前踩空有土狼时间。
NSMB 的招牌动作也在这里：墙跳、旋转跳、下砸，以及可搬运的龟壳。
"""
from __future__ import annotations

import pygame

from ..core.actor import Actor
from ..core.physics import move_x, move_y
from ..core.tuning import TUNE

# 星星无敌期间的循环染色（叠加增亮，制造经典彩虹闪烁）
STAR_TINTS = ((90, 0, 0), (0, 90, 0), (0, 40, 90), (90, 60, 0))


class Player(Actor):
    art = "hero"
    w, h = 10, 14
    z = 20

    def __init__(self, world, x, y, form="small", **kw):
        super().__init__(world, x, y, **kw)
        self.form = form
        self.art = f"hero.{form}"
        self.in_water = False
        self.climbing = False
        self.spinning = False
        self.diving = False
        self.pound = False
        self.invuln = 0.0
        self.star = 0.0
        self.mega_t = 0.0
        self.mini = 0.0
        self.holding = ""       # 举在头上的东西（"shell"）
        self.held = None        # 被搬运的 actor
        self.was_on_ground = False
        self._coyote = 0.0
        self._wall_coyote = 0.0
        self._wall_dir = 0
        self.wall_slide = 0     # 本帧贴的墙方向（-1 左 / 1 右 / 0 无）
        self.dying = False
        self.locked = False     # 过场脚本控制（旗杆等），屏蔽输入
        self.combo = 0          # 踩踏连击数，落地清零

    # -- 形态 ---------------------------------------------------------------------------
    @property
    def height(self) -> int:
        return {"mini": TUNE.mini_h, "small": TUNE.small_h,
                "super": TUNE.super_h, "fire": TUNE.super_h,
                "mega": TUNE.mega_h}[self.form]

    def set_form(self, form: str, world=None):
        if form not in ("mini", "small", "super", "fire", "mega"):
            form = "small"
        self.form = form
        self.art = f"hero.{form}"
        self.body.h = self.height
        self.body.w = max(8, int(self.body.h * 0.66))

    def grow(self, world):
        if self.form in ("mini", "small"):
            self.set_form("super")
            world.fx("pop", self.body.center)
            world.sfx("power-up")

    def shrink(self, world):
        if self.form in ("super", "fire"):
            self.set_form("small")
            self.invuln = 1.4
            world.sfx("shrink")
            world.shake(1.6)
        else:
            self.kill_outright(world)

    def kill_outright(self, world):
        """直接死亡（小个被撞 / 掉坑 / 超时），由场景接管死亡动画。"""
        if self.dying:
            return
        self.drop_held(world)
        world.on_death(self)

    def hurt(self, world):
        if self.invuln > 0 or self.star > 0 or self.mega_t > 0 or not self.alive:
            return
        self.shrink(world)

    def drop_held(self, world):
        """松手放下面前的龟壳（死亡/受伤时）。"""
        if self.held is not None:
            self.held.carried = False
            self.held.state = "shell"
            self.held = None
            self.holding = ""

    # -- 每帧 -----------------------------------------------------------------------------
    def update(self, world):
        if self.dying:
            # 死亡抛物线：无视地形，先弹起再坠落
            self.t += 1 / 60.0
            self.body.vy = min(6.0, self.body.vy + 0.30)
            self.body.y += self.body.vy
            self.set_anim("jump")
            return
        b = self.body
        super().update(world)
        for name in ("invuln", "star", "mini"):
            if getattr(self, name) > 0:
                setattr(self, name, max(0.0, getattr(self, name) - 1 / 60.0))
        if self.mega_t > 0:
            self.mega_t -= 1 / 60.0
            if self.mega_t <= 0:
                self.set_form("super")
                world.fx("pop", self.body.center)
                world.sfx("shrink")
        self.in_water = world.fluid_at(b.rect.inflate(-2, -2))
        self.climbing = world.ladder_at(b.rect)

        was_grounded = b.on_ground or self._coyote > 0
        self._coyote = (TUNE.coyote / 60.0 if b.on_ground
                        else max(0.0, self._coyote - 1 / 60.0))
        was_water = self.in_water
        if not self.locked:
            self._horizon(world.input, world)
            self._vertical(world.input, world, was_grounded)
        else:
            b.vy = min(TUNE.max_fall, b.vy + TUNE.gravity)
        cells_hit = move_x(b, world.tilemap)
        if self.form == "mega":
            for cell in cells_hit:
                world.mega_smash(cell)          # 巨人形态横冲直撞
        vy_before = b.vy
        contact = move_y(b, world.tilemap)
        if self.pound and contact.ground:
            self.pound = False
            world.pound_impact(self)
        if contact.ground:
            if not self.was_on_ground:
                world.on_land(self)
                self.combo = 0
                if vy_before > 4.5:             # 重落地扬尘
                    for i in (-1, 1):
                        world.fx("dust", (b.x + i * 4, b.y))
            for cell in contact.ground:
                world.note_check(cell, self)     # 音符块弹床
        # 入水水花 / 急刹尘土
        if not was_water and self.in_water and vy_before > 2:
            for i in range(4):
                world.fx("splash", (b.x + (i - 1.5) * 3, b.y - b.h))
            world.sfx("swim")
        if b.on_ground and abs(b.vx) > TUNE.walk_max and not self.locked:
            if int(self.t * 30) % 5 == 0:
                world.fx("dust", (b.x - b.facing * 3, b.y - 1))
        if contact.ceiling:
            world.on_ceiling(self, contact.ceiling[0])
        if not self.locked:
            self._wall_slide_check(world)
        # 掉出地图底部 = 坠亡
        if b.y > world.tilemap.pixel_size[1] + 24:
            self.kill_outright(world)
            return
        self._anim(None if self.locked else world.input)
        self.flip = b.facing < 0
        if self.held is not None:                 # 搬运物举在头顶
            self.held.body.x = b.x + b.facing * 2
            self.held.body.y = b.y - b.h - 9

    # -- 移动 ------------------------------------------------------------------------------
    def _horizon(self, inp, world):
        b = self.body
        crawling = inp.held("down") and b.on_ground
        axis = 0 if self.climbing else inp.axis_x()
        if crawling and abs(b.vx) < 0.6:
            axis = 0
        if axis:
            b.facing = 1 if axis > 0 else -1
        running = inp.held("run")
        top = (TUNE.run_max if running else TUNE.walk_max)
        if self.form == "mini":
            top *= 1.12                          # 迷你马里奥更轻快
        if self.form == "mega":
            top *= 1.18
        top *= (0.72 if self.in_water else 1.0)
        if self.climbing:
            top = min(top, 1.15)
        if axis:
            skid = bool(b.vx) and (b.vx > 0) != (axis > 0)
            step = ((TUNE.skid_decel if skid else
                     (TUNE.accel_run if running else TUNE.accel_walk))
                    * (1.0 if b.on_ground else TUNE.air_control))
            b.vx += axis * step
            if abs(b.vx) > top:                   # 加速吃到 buff 后回落
                b.vx *= 0.94
        else:
            f = TUNE.decel if b.on_ground else TUNE.decel * 0.35
            b.vx = 0.0 if abs(b.vx) <= f else b.vx - (f if b.vx > 0 else -f)
        if self.in_water:
            b.vx *= 0.985

    def _vertical(self, inp, world, was_grounded):
        b = self.body
        ground = b.on_ground or (was_grounded and self._coyote > 0)
        jump_scale = {"mini": 1.12, "mega": 0.9}.get(self.form, 1.0)
        if inp.buffered("jump", TUNE.jump_buffer):
            if self.climbing:
                b.vy = -2.6
                self.climbing = False
                world.sfx("jump")
            elif ground:
                b.vy = -TUNE.jump_vel * jump_scale
                self._coyote = 0.0
                world.sfx("mini-jump" if self.form == "mini" else "jump")
            elif self._wall_coyote > 0:
                # 墙跳：沿墙反方向跃出
                b.vy = -TUNE.jump_vel * 0.96 * jump_scale
                b.vx = -self._wall_dir * max(TUNE.wall_jump_push, abs(b.vx) + 0.4)
                b.facing = -self._wall_dir
                self._wall_coyote = 0.0
                self.spinning = False
                world.sfx("jump")
                world.fx("dust", (b.x - self._wall_dir * 5, b.y - b.h * 0.5))
        if inp.released("jump") and b.vy < -1.0 and not self.in_water:
            b.vy *= TUNE.gravity_release
        if self.climbing:
            b.vy = inp.axis_y() * 1.35
        if self.in_water and inp.pressed("jump"):
            b.vy = -2.55
            world.sfx("swim")
        # 旋转跳（空中按 spin）与下砸（空中 下+跳跃）
        if inp.pressed("spin") and not b.on_ground and not self.in_water:
            self.spinning, b.vy = True, -3.4
            world.sfx("spin")
        if inp.held("down") and inp.pressed("jump") and not b.on_ground and not self.pound:
            self.pound, b.vy = True, 2.0
            self.spinning = False
            world.sfx("pound")
        if b.on_ground:
            self.spinning = False
            self.pound = False
            self.diving = inp.held("down") and abs(b.vx) > TUNE.walk_max * 0.85
        if inp.pressed("action"):
            world.action_pressed(self)
        # 重力：只要不在爬梯就始终施加（站台上时每帧 0.5px 下压→重新落地）。
        # 若用 on_ground 做闸门，站定后走出平台边缘 vy=0、move_y 早退不清状态，
        # 玩家会悬空（历史 bug）。
        if not self.climbing:
            g = TUNE.gravity
            if b.vy < 0 and inp.held("jump"):
                g *= TUNE.gravity_rise
            elif b.vy > 0:
                g *= TUNE.gravity_fall
            if self.in_water:
                b.vy = min(0.8, b.vy + TUNE.gravity * 0.34 * 0.5)  # 水中缓慢下沉
            else:
                if self.pound:
                    g = TUNE.gravity * 2.1
                cap = TUNE.max_fall
                b.vy = min(cap, b.vy + g)

    def _wall_slide_check(self, world):
        """贴墙下滑检测：空中、下落、朝着墙按方向键才成立。"""
        b = self.body
        self.wall_slide = 0
        if b.on_ground or self.in_water or b.vy <= 0 or self.climbing:
            self._wall_coyote = max(0.0, self._wall_coyote - 1 / 60.0)
            return
        inp = world.input
        for side in (-1, 1):
            if not (inp.held("right") if side > 0 else inp.held("left")):
                continue
            probe = b.rect.move(side * 2, 0)
            # 注意：solid_cells 是生成器，bool() 恒真，必须用 any() 消费
            if any(True for _c, _k in world.tilemap.solid_cells(probe)):
                b.vy = min(b.vy, TUNE.wall_slide_speed)
                self.wall_slide = side
                self._wall_dir = side
                self._wall_coyote = 0.14
                if int(self.t * 30) % 6 == 0:
                    world.fx("dust", (b.x + side * 4, b.y - b.h * 0.4))
                break

    # -- 动画 ------------------------------------------------------------------------------
    def _anim(self, inp):
        b = self.body
        if self.climbing:
            self.set_anim("swim")
        elif self.in_water:
            self.set_anim("swim")
        elif self.wall_slide:
            self.set_anim("skid")
        elif not b.on_ground:
            if self.pound:
                self.set_anim("dive")
            elif self.spinning:
                self.set_anim("spin")
            else:
                self.set_anim("jump" if b.vy < -0.4 else "fall")
        elif inp is None or not any(inp.held(a) for a in ("left", "right")):
            if abs(b.vx) > 0.25:
                self.set_anim("run" if abs(b.vx) > TUNE.walk_max else "walk")
                self.fps = 9.0 + abs(b.vx) * 2.2
            else:
                self.set_anim("idle")
                self.fps = 4.0
        elif inp.held("down"):
            self.set_anim("crawl")
        elif abs(b.vx) > 0.25:
            self.set_anim("run" if abs(b.vx) > TUNE.walk_max else "walk")
            self.fps = 9.0 + abs(b.vx) * 2.2
        else:
            self.set_anim("idle")
            self.fps = 4.0
        if self.holding:
            self.set_anim("throw", reset=False)

    # -- 绘制 ------------------------------------------------------------------------------
    def draw(self, target, cam):
        if self.invuln > 0 and int(self.t * 30) % 2:
            return
        surf = self.frame_surf()
        if self.dying:
            surf = pygame.transform.flip(surf, False, True)
        elif self.star > 0 and not self.spinning:
            # 星星无敌：循环色彩叠加
            tint = STAR_TINTS[int(self.t * 18) % len(STAR_TINTS)]
            surf = surf.copy()
            veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            veil.fill(tint + (110,))
            surf.blit(veil, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        if self.flip:
            surf = pygame.transform.flip(surf, True, False)
        x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                             self.body.y - surf.get_height())
        target.blit(surf, (x, y))
        if self.held is not None:
            self.held.draw(target, cam)
