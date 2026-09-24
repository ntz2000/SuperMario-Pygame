"""玩家角色：NSMB 风格的地面/空中操控、形态与招式。

移动手感由 :mod:`mario.core.tuning` 里的数值决定：走/跑各有极速，急刹比滑行
减速更狠，上升中按住跳跃减轻重力，跳跃输入有预输入缓冲，起跳前踩空有土狼时间。
NSMB 的招牌动作也在这里：墙跳、旋转跳、下砸、气泡重生，以及可搬运的龟壳。
"""
from __future__ import annotations

import math

import pygame

from ..core.actor import Actor
from ..core.physics import move_x, move_y
from ..core.tuning import TUNE
from ..engine.res import RES_SCALE as S

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
        self.bubble = False     # 气泡重生（NSMB）：从天上安全降落到出生点
        self._bubble_ground = 0.0
        self._bubble_t = 0.0
        self.pending_form = ""  # 头顶空间不足时排队等长（防变大穿模）
        self.prop_fuel = 0.0    # 螺旋桨燃料（propeller 形态）
        self.sliding = False    # 企鹅冰滑状态
        self.squash_t = 0.0     # 落地压扁/起跳拉伸计时（squash&stretch 让动作有生命感）

    def start_bubble(self, ground_y: float):
        """进入气泡重生：从出生点上方 150px 开始降落，落地破泡给 2 秒无敌。

        修复"重生即死"：重生瞬间对敌人完全免疫（连碰撞都不发生），
        落地后还有无敌帧，不会再被巡逻到出生点的敌人秒杀。
        """
        self.bubble = True
        self.locked = True
        self.body.y = ground_y - 150.0
        self.body.vx = self.body.vy = 0.0
        self._bubble_ground = ground_y
        self._bubble_t = 0.0

    # -- 形态 ---------------------------------------------------------------------------
    @property
    def height(self) -> int:
        return {"mini": TUNE.mini_h, "small": TUNE.small_h,
                "super": TUNE.super_h, "fire": TUNE.super_h, "ice": TUNE.super_h,
                "propeller": TUNE.super_h, "penguin": TUNE.super_h,
                "mega": TUNE.mega_h}[self.form]

    def set_form(self, form: str, world=None):
        if form not in ("mini", "small", "super", "fire", "ice",
                        "propeller", "penguin", "mega"):
            form = "small"
        # 长高前检查头顶空间（经典行为：顶不够就先不长，留 pending 等有空间）。
        # 防止变大瞬间嵌入天花板瓦片 → 横移被卡死/视觉穿模。
        if self.body.h < self._form_h(form) and not self._can_fit(form):
            self.pending_form = form
            return
        self.pending_form = None
        grew = self.body.h < self._form_h(form)
        self.form = form
        self.art = f"hero.{form}"
        self.body.h = self.height
        self.body.w = max(8, int(self.body.h * 0.66))
        if grew:
            self.squash_t = 1.2      # 长大时的弹性缩放（变身动画感）

    def _form_h(self, form: str) -> int:
        return {"mini": TUNE.mini_h, "small": TUNE.small_h,
                "super": TUNE.super_h, "fire": TUNE.super_h, "ice": TUNE.super_h,
                "propeller": TUNE.super_h, "penguin": TUNE.super_h,
                "mega": TUNE.mega_h}.get(form, TUNE.small_h)

    def _can_fit(self, form: str) -> bool:
        """用目标形态的碰撞盒试放，看是否嵌进实心瓦片。"""
        h = self._form_h(form)
        r = pygame.Rect(round(self.body.x - self.body.w / 2),
                        round(self.body.y - h), self.body.w, h)
        for cell, kind in self.world.tilemap.solid_cells(r):
            if kind != "solid":
                continue
            if r.colliderect(cell.inflate(-2, -2)):
                return False
        return True

    def grow(self, world):
        if self.form in ("mini", "small"):
            self.set_form("super")
            world.fx("pop", self.body.center)
            world.sfx("power-up")

    def shrink(self, world):
        if self.form in ("super", "fire", "ice", "propeller", "penguin"):
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
        if self.bubble:
            # 气泡重生：无视地形与敌人，左右轻摆地缓缓降落
            self.t += 1 / 60.0
            self._bubble_t += 1 / 60.0
            self.body.x += math.sin(self._bubble_t * 3.0) * 0.35
            self.body.y = min(self._bubble_ground, self.body.y + 1.2)
            self.set_anim("swim")
            if self.body.y >= self._bubble_ground:
                self.bubble = False
                self.locked = False
                self.invuln = 3.0     # 落地后再给 3 秒无敌，应付身边的敌人
                self.body.on_ground = True
                self.was_on_ground = True
                world.fx("pop", self.body.center)
                world.fx("sparkle", (self.body.x, self.body.y - 8))
                world.sfx("reveal")
            return
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
        # 排队的变身：头顶有空间了就长
        if self.pending_form and self._can_fit(self.pending_form):
            form, self.pending_form = self.pending_form, ""
            old_h = self.body.h
            self.form = form
            self.art = f"hero.{form}"
            self.body.h = self._form_h(form)
            self.body.w = max(8, int(self.body.h * 0.66))
            self.squash_t = 1.2 if self.body.h > old_h else -1.2   # 长大弹一下
            world.fx("pop", self.body.center)
            world.sfx("power-up")
        if self.squash_t > 0:          # 负值=拉伸，向 0 衰减
            self.squash_t = max(0.0, self.squash_t - 1 / 30.0)
        elif self.squash_t < 0:
            self.squash_t = min(0.0, self.squash_t + 1 / 30.0)
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
                self.squash_t = 0.8 if vy_before > 4.0 else 0.5   # 落地压扁
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
        # 无敌星彩虹尾迹（NSMB 星星跑动时身后拖彩色光点）
        if self.star > 0 and abs(b.vx) > 0.8:
            if int(self.t * 40) % 2 == 0:
                world.fx("sparkle", (b.x - b.facing * 6, b.y - b.h * 0.5))
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
        # 企鹅冰滑：地面高速冲刺（≥跑速 95%）→ 肚皮滑行，加速+难转向+撞飞敌人
        if self.form == "penguin" and b.on_ground and abs(b.vx) > TUNE.run_max * 0.95:
            if not self.sliding:
                self.sliding = True
                world.sfx("spin")
        elif self.sliding and (not b.on_ground or abs(b.vx) < TUNE.run_max * 0.5):
            self.sliding = False
        if self.sliding:
            b.vx = max(TUNE.run_max * 1.35, abs(b.vx)) * (1 if b.vx >= 0 else -1)
            if abs(b.vx) < TUNE.run_max * 1.35:
                b.vx = TUNE.run_max * 1.35 * (1 if b.vx >= 0 else -1)
            if int(self.t * 30) % 3 == 0:
                world.fx("dust", (b.x - (1 if b.vx > 0 else -1) * 5, b.y - 1))
            self.facing = 1 if b.vx > 0 else -1
            return   # 滑行中不受普通方向控制（这就是"冰滑"的代价与爽点）
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
            if skid and b.on_ground:      # 冰上急刹也刹不住
                step *= world.friction_at(b.rect.move(0, 2))
            b.vx += axis * step
            if abs(b.vx) > top:                   # 加速吃到 buff 后回落
                b.vx *= 0.94
        else:
            f = TUNE.decel if b.on_ground else TUNE.decel * 0.35
            if b.on_ground:
                # 冰面打滑：松开方向后按地面摩擦滑行（脚下瓦片的 friction）
                f *= world.friction_at(b.rect.move(0, 2))
            b.vx = 0.0 if abs(b.vx) <= f else b.vx - (f if b.vx > 0 else -f)
        if self.in_water:
            b.vx *= 0.985

    def _vertical(self, inp, world, was_grounded):
        b = self.body
        ground = b.on_ground or (was_grounded and self._coyote > 0)
        jump_scale = {"mini": 1.12, "mega": 0.9}.get(self.form, 1.0)
        # 螺旋桨燃料：地面回满，空中消耗
        if b.on_ground:
            self.prop_fuel = 1.2
        if inp.buffered("jump", TUNE.jump_buffer):
            if self.climbing:
                b.vy = -2.6
                self.climbing = False
                world.sfx("jump")
            elif self.form == "propeller" and not ground and self.prop_fuel > 0.05:
                # 螺旋桨起飞：空中再按跳=垂直升空（NSMBW 同款）
                b.vy = -4.2
                self.prop_fuel -= 0.22
                self.spinning = True
                world.sfx("spin")
                world.fx("dust", (b.x, b.y))
            elif ground:
                # 跑动起跳加成（NSMB：跑跳比站跳更高更远，助跑有意义）
                run_boost = TUNE.run_jump_bonus if abs(b.vx) > TUNE.walk_max else 1.0
                b.vy = -TUNE.jump_vel * run_boost * jump_scale
                self._coyote = 0.0
                self.squash_t = -0.7          # 起跳拉伸（负值=拉长）
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
        elif self.form == "propeller" and not ground and inp.held("jump") \
                and self.prop_fuel > 0:
            # 按住跳跃：螺旋桨持续消耗燃料缓缓上升
            b.vy = min(b.vy, -2.6)
            self.prop_fuel -= 1 / 60.0
            self.spinning = True
        if inp.released("jump") and b.vy < -1.0 and not self.in_water \
                and self.form != "propeller":
            b.vy *= TUNE.gravity_release
        if self.climbing:
            b.vy = inp.axis_y() * 1.35
        if self.in_water and inp.pressed("jump"):
            # 企鹅装水中如鱼（NSMBW：划水更强）
            b.vy = -3.4 if self.form == "penguin" else -2.55
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
        if self.form != "penguin":
            self.sliding = False
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
                # 企鹅装水中下沉更慢（浮力）
                sink = 0.17 if self.form == "penguin" else 0.5
                b.vy = min(0.8, b.vy + TUNE.gravity * 0.34 * sink)
            else:
                if self.pound:
                    g = TUNE.gravity * 2.1
                cap = TUNE.max_fall
                b.vy = min(cap, b.vy + g)
                # 螺旋桨缓降：下落中按住跳=旋翼减速漂浮（燃料耗尽仍有一点缓冲）
                if self.form == "propeller" and b.vy > 1.3 and inp.held("jump"):
                    b.vy = 1.3
                    self.spinning = self.prop_fuel > 0
                    if int(self.t * 30) % 4 == 0:
                        world.fx("dust", (b.x, b.y))

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
        # 动画速率随速度（NSMB 手感：18 帧 walk 在跑动时 ~0.6s 一循环）
        def _pace():
            self.fps = min(34.0, 15.0 + abs(b.vx) * 8.0)
        if self.sliding:
            self.set_anim("dive")     # 企鹅肚皮滑行姿势
        elif self.climbing:
            self.set_anim("swim")
        elif self.in_water:
            self.set_anim("swim")
            self.fps = 10.0
        elif self.wall_slide:
            self.set_anim("skid")
        elif not b.on_ground:
            if self.pound:
                self.set_anim("pound")
            elif self.spinning:
                self.set_anim("spin")
            else:
                self.set_anim("jump" if b.vy < -0.4 else "fall")
        elif inp is None:
            self.set_anim("idle")
            self.fps = 6.0
        elif (inp.held("left") and b.vx > 0.9) or (inp.held("right") and b.vx < -0.9):
            # 反向急刹：速度与输入相反且够快 → 打滑姿势（NSMB 的 skid 烟雾时刻）
            self.set_anim("skid")
        elif inp.held("down"):
            self.set_anim("crawl" if abs(b.vx) > 0.25 else "crawl")
            self.fps = 8.0
        elif abs(b.vx) > 0.25:
            want = "run" if abs(b.vx) > TUNE.walk_max else "walk"
            # walk↔run 是同一循环的快慢版，切换时不重置帧（否则在阈值附近
            # 抖动会每帧归零动画，看起来完全静止）
            self.set_anim(want, reset=False)
            _pace()
        else:
            self.set_anim("idle")
            self.fps = 6.0
        if self.holding:
            self.set_anim("throw", reset=False)

    # -- 绘制 ------------------------------------------------------------------------------
    def draw(self, target, cam):
        if self.bubble:
            self._draw_bubble(target, cam)
            return
        if self.invuln > 0 and int(self.t * 30) % 2:
            return
        self._draw_shadow(target, cam)
        surf = self.frame_surf()
        if self.dying:
            surf = pygame.transform.flip(surf, False, True)
        elif self.star > 0 and not self.spinning:
            # 星星无敌：循环色彩叠加 + 亮度脉冲（NSMB 闪闪发光感）
            tint = STAR_TINTS[int(self.t * 18) % len(STAR_TINTS)]
            surf = surf.copy()
            veil = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            veil.fill(tint + (110,))
            surf.blit(veil, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            pulse = int(40 * abs(math.sin(self.t * 9.0)))
            if pulse > 12:
                glow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
                glow.fill((255, 255, 255, pulse))
                surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        if self.flip:
            surf = pygame.transform.flip(surf, True, False)
        # squash & stretch：落地压扁（宽+高-），起跳拉伸（宽-高+）
        k = self.squash_t
        if k:
            amount = min(1.0, abs(k)) * 0.18
            if k > 0:   # 落地压扁
                w2 = round(surf.get_width() * (1 + amount))
                h2 = round(surf.get_height() * (1 - amount))
            else:        # 起跳拉伸
                w2 = round(surf.get_width() * (1 - amount))
                h2 = round(surf.get_height() * (1 + amount))
            surf = pygame.transform.scale(surf, (w2, h2))
        # 贴地绘制（squash 变形时贴脚底；正常时精灵底对齐，去 +1 偏移）
        bottom = self._sprite_bottom(surf) if not k else surf.get_height() - 1
        x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                             self.body.y - bottom - 0.5)
        target.blit(surf, (x, y))
        if self.held is not None:
            self.held.draw(target, cam)

    def _draw_bubble(self, target, cam):
        """重生气泡：半透明的角色泡在圆泡泡里，泡泡随呼吸轻微缩放。"""
        surf = self.frame_surf()
        if self.flip:
            surf = pygame.transform.flip(surf, True, False)
        surf = surf.copy()
        surf.set_alpha(150)      # 泡里的角色半透明
        cx, cy = cam.to_screen(self.body.x, self.body.y - self.body.h / 2)
        w, h = surf.get_width(), surf.get_height()
        target.blit(surf, (cx - w / 2, cy - h / 2))
        r = max(w, h) * 0.78 * (1.0 + math.sin(self._bubble_t * 5.0) * 0.03)
        pygame.draw.circle(target, (210, 235, 255, 90), (cx, cy), int(r), 2 * S)
        pygame.draw.circle(target, (255, 255, 255, 60), (cx, cy), int(r - 2 * S), S)
        # 左上高光弧
        pygame.draw.circle(target, (255, 255, 255),
                           (cx - int(r * 0.45), cy - int(r * 0.5)), 2 * S)
