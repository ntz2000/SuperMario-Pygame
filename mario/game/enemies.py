"""敌人：巡逻、被踩、变壳、被搬起、镜头靠近才苏醒。

敌人在镜头接近前处于休眠（``wake``），长关卡因此省 CPU，也还原了原作
"看到才活动" 的节奏。龟壳有完整状态机：walk → shell（静止可搬）→ slide（滑行
杀敌）→ wake 计时回归 walk。Bowser 是城堡关的 Boss，踩三下或火球三次击破。
"""
from __future__ import annotations

import math

import pygame

from ..core.actor import Actor
from ..core.physics import move_x, move_y
from ..core.tiles import TILE


class Enemy(Actor):
    z = 12
    speed = 0.52
    stompable = True
    shell = False          # 被踩后留下龟壳而不是当场压扁
    art = "enemy/goomba"
    shell_art = "enemy/shell"
    w, h = 13, 13
    score = 100
    walk_anim = "walk"

    def __init__(self, world, x, y, dir=-1, **kw):
        super().__init__(world, x, y, **kw)
        self.dir = dir
        self.body.vx = dir * self.speed
        self.awake = False
        self.squashed = 0.0
        self.flip = dir > 0
        self.state = "walk"
        self.carried = False
        self.wake_t = 0.0
        self.frozen_t = 0.0       # 冰冻剩余时间（state=="frozen" 时有效）
        self.invuln = 0.0
        self._multi = None        # multi_frame 的缓存
        self.h0 = type(self).h    # 壳化后恢复用

    @property
    def multi_frame(self) -> bool:
        if self._multi is None:                # 帧数是静态属性，查一次就够
            self._multi = len(self.world.assets.sprite(self.art).frames) > 1
        return self._multi

    def update(self, world):
        if self.carried:
            return                        # 被玩家举着，位置由玩家维护
        if not self.awake:
            # 原版行为：敌人比镜头右缘早一屏就开走（入画时已在巡逻，
            # 而不是站桩等人）。历史 bug：唤醒半径太小，Goomba 像柱子。
            wake_zone = world.camera.view_rect.inflate(320, 120)
            if wake_zone.colliderect(self.rect):
                self.awake = True
                self.body.vx = self.dir * self.speed
            return
        self.t += 1 / 60.0
        if self.invuln > 0:
            self.invuln -= 1 / 60.0
        if self.squashed > 0:
            self.squashed -= 1 / 60.0
            self.body.vx *= 0.7
            if self.squashed <= 0:
                self.kill()
            return
        # 冰冻：不能动不能伤人，倒数解冻（快解冻时抖动预警）
        if self.state == "frozen":
            self.frozen_t -= 1 / 60.0
            if self.frozen_t <= 0:
                self.state = "walk"
                world.fx("splash", self.body.center)
            self.body.vx = 0.0
        # 龟壳静止时慢慢苏醒
        elif self.state == "shell":
            self.wake_t += 1 / 60.0
            if self.wake_t > 6.0:
                self.state = "walk"
                self.body.h = self.h0
            self.body.vx = 0.0
        elif self.state == "slide":
            self.body.vx = self.dir * 4.2
        else:
            self.body.vx = self.dir * self.speed
        if move_x(self.body, world.tilemap):
            self.dir = -1 if self.body.on_wall > 0 else 1
            if self.state == "slide":
                world.sfx("bump")
        self.body.vy = min(6.0, self.body.vy + 0.30)
        move_y(self.body, world.tilemap)
        if not self.multi_frame or self.state in ("shell", "slide"):
            self.set_anim("idle")
        else:
            self.set_anim(self.walk_anim)
        self.flip = self.dir > 0
        # 掉出地图底部
        if self.body.y > world.tilemap.pixel_size[1] + 40:
            self.kill()

    # -- 交互 ------------------------------------------------------------------------------
    def freeze(self, world):
        """冰球命中：冻成冰块 5 秒。踩碎得分；Boss 冻不住。"""
        if self.state == "frozen" or not self.awake:
            return
        if type(self).__name__ == "Bowser":
            return                 # Boss 免疫冰冻（NSMB 同款）
        self.state = "frozen"
        self.frozen_t = 5.0
        self.body.vx = 0.0
        world.sfx("freeze")
        world.fx("sparkle", self.body.center)

    def shatter_ice(self, world):
        """冻结的敌人被踩碎。"""
        self.kill()
        world.sfx("break")
        world.add_score(self.score, self.body.center)
        c = self.body.center
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            world.fx("shard", (c[0] + dx * 4, c[1] + dy * 4), vx=dx * 1.2,
                     vy=dy * 1.0 - 1.2, g=0.3, life=0.4)

    def to_shell(self, world, by):
        """踩第一下：缩壳。"""
        self.state = "shell"
        self.body.h = max(8, type(self).h // 2)
        self.body.vx = 0.0
        self.wake_t = 0.0
        world.sfx("stomp")
        world.hint("按 C 搬起龟壳 · 再按 C 扔出", key="shell")

    def stomp(self, world, by):
        if not self.stompable:
            return False
        if self.state == "frozen":
            # 冻结的敌人：踩上去直接踩碎冰块
            self.shatter_ice(world)
            return True
        if self.shell:
            if self.state == "walk":
                self.to_shell(world, by)
            elif self.state == "shell":
                self.state = "slide"      # 再踩一下踢出去
                self.dir = 1 if by.body.x < self.body.x else -1
                self.wake_t = 0.0
                world.sfx("kick")
            else:                          # 滑行中踩 = 停下
                self.state = "shell"
                self.wake_t = 0.0
                world.sfx("stomp")
        else:
            self.squashed = 0.5
            world.sfx("stomp")
        # 计分交给踩踏连击表（level.combo_score），这里不再重复加分
        return True

    def hurt(self, world, by=None):
        """火球/星星/滑壳的击杀：翻面飘走。"""
        if getattr(self, "invuln", 0) > 0:
            return
        self.alive = False
        self.flying_off = True
        self.removed = True
        world.fx("hit", self.body.center)
        world.add_score(self.score, self.body.center)
        world.sfx("hit")

    def draw(self, target, cam):
        if self.carried:
            surf = self.world.assets.sprite(self.shell_art).frame(self.t * 6)
            x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                                 self.body.y - surf.get_height())
            target.blit(surf, (x, y))
            return
        if self.state == "frozen":
            self._draw_frozen(target, cam)
            return
        self._draw_shadow(target, cam)
        if self.squashed > 0:
            # 压扁贴图：高度压到 40%（压扁物直接贴脚底，不用精灵底检测）
            surf = self.frame_surf()
            flat = pygame.transform.scale(surf, (surf.get_width(),
                                                max(2, int(surf.get_height() * 0.4))))
            x, y = cam.to_screen(self.body.x - flat.get_width() / 2,
                                self.body.y - flat.get_height() - 0.5)
            target.blit(flat, (x, y))
            return
        if self.state in ("shell", "slide"):
            surf = self.world.assets.sprite(self.shell_art).frame(
                self.t * (10 if self.state == "slide" else 0))
            if self.flip:
                surf = pygame.transform.flip(surf, True, False)
            bottom = self._sprite_bottom(surf)
            x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                                 self.body.y - bottom - 0.5)
            target.blit(surf, (x, y))
            return
        super().draw(target, cam)

    def _draw_frozen(self, target, cam):
        """冻结的敌人：原帧 + 蓝色冰壳；快解冻时闪白抖动。"""
        surf = self.frame_surf()
        if self.flip:
            surf = pygame.transform.flip(surf, True, False)
        surf = surf.copy()
        ice = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        ice.fill((140, 205, 255, 115))
        surf.blit(ice, (0, 0))
        r = surf.get_rect()
        pygame.draw.rect(surf, (215, 240, 255), r, 1)
        if self.frozen_t < 1.2 and int(self.frozen_t * 20) % 2:
            flash = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, 90))
            surf.blit(flash, (0, 0))
        bottom = self._sprite_bottom(surf)
        x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                            self.body.y - bottom - 0.5)
        jitter = 1 if (self.frozen_t < 1.2 and int(self.frozen_t * 24) % 2) else 0
        target.blit(surf, (x + jitter, y))


class Goomba(Enemy):
    art = "enemy/goomba"


class Koopa(Enemy):
    art = "enemy/koopa"
    shell_art = "enemy/shell"
    w, h = 13, 18
    speed = 0.62
    shell = True


class RedKoopa(Koopa):
    """红龟：平台边缘会自己掉头。"""
    art = "enemy/red_koopa"
    shell_art = "enemy/shell_red"

    def update(self, world):
        before = self.body.x
        super().update(world)
        if self.state == "walk" and self.awake and not self.squashed and not self._grounded():
            self.body.x = before
            self.dir *= -1

    def _grounded(self) -> bool:
        ahead = pygame.Rect(round(self.body.x - 6 + self.dir * 8), round(self.body.y), 12, 3)
        return any(k == "solid" or k == "one_way"
                   for _c, k in self.world.tilemap.solid_cells(ahead))


class Spiny(Koopa):
    """刺龟：不能踩（但旋转跳可以弹开）。"""
    art = "enemy/spiny"
    shell_art = "enemy/shell_spiny"
    stompable = False


class Buzzy(Enemy):
    art = "enemy/buzzy"
    shell = True
    w, h = 13, 9


class Piranha(Actor):
    """食人花：不能踩，英雄靠近就缩回管子里。"""

    art = "enemy/piranha"
    w, h = 13, 22
    z = 9
    collides_player = True
    score = 200

    def __init__(self, world, x, y, phase=0.0, **kw):
        super().__init__(world, x, y, **kw)
        self.phase = phase
        self.base_y = y

    def update(self, world):
        self.t += 1 / 60.0
        player = world.player
        near = abs(player.body.x - self.body.x) < 24
        cycle = (self.t + self.phase) % 3.2
        rise = 0.0 if near or player.dying else max(0.0, math.sin(cycle * math.pi / 1.6)) \
            if cycle < 1.6 else 0.0
        self.body.y = self.base_y - rise * TILE * 1.5

    def hurt(self, world, by=None):
        self.alive = False
        self.removed = True
        world.fx("hit", self.body.center)
        world.add_score(self.score, self.body.center)
        world.sfx("hit")


class Cheep(Enemy):
    """水中鱼：直线游过，带正弦起伏。"""

    art = "enemy/cheep"
    w, h = 13, 11
    speed = 1.3

    def update(self, world):
        if not self.awake:
            if world.camera.view_rect.inflate(80, 0).colliderect(self.rect):
                self.awake = True
            return
        self.t += 1 / 60.0
        self.body.x += self.dir * self.speed
        self.body.y += math.sin(self.t * 6.0) * 0.55
        if self.rect.left < 0 or self.rect.left > self.world.tilemap.pixel_size[0]:
            self.kill()


class Biddybud(Enemy):
    """NSMBW 甲虫：直线行走（5 帧动画），可踩扁，成群出现是它的特色。"""

    art = "enemy/biddybud"
    w, h = 12, 11
    speed = 0.62


class Goombrat(Enemy):
    """NSMBW 栗子怪：像 Goomba，但悬崖边会自己掉头。"""

    art = "enemy/goombrat"
    w, h = 12, 12

    def update(self, world):
        before = self.body.x
        super().update(world)
        if self.state == "walk" and self.awake and not self.squashed and not self._grounded():
            self.body.x = before
            self.dir *= -1

    def _grounded(self) -> bool:
        ahead = pygame.Rect(round(self.body.x - 6 + self.dir * 8), round(self.body.y), 12, 3)
        return any(k == "solid" or k == "one_way"
                   for _c, k in self.world.tilemap.solid_cells(ahead))


class Grrrol(Enemy):
    """NSMBW 滚石球：带刺滚动的巨石，踩不得打不得，只能躲。"""

    art = "enemy/grrrol"
    w, h = 13, 13
    z = 13
    speed = 1.1
    stompable = False
    score = 0

    def stomp(self, world, by):
        return False          # 踩上去只会伤到自己

    def hurt(self, world, by=None):
        pass                  # 火球/星星/龟壳全都免疫——它就是无敌的路障

    def update(self, world):
        if not self.awake:
            if world.camera.view_rect.inflate(48, 0).colliderect(self.rect):
                self.awake = True
            return
        self.t += 1 / 60.0
        if self.squashed > 0:
            self.squashed -= 1 / 60.0
            return
        self.body.vx = self.dir * self.speed
        if move_x(self.body, world.tilemap):
            self.dir = -1 if self.body.on_wall > 0 else 1
            world.sfx("bump")
        self.body.vy = min(6.0, self.body.vy + 0.30)
        move_y(self.body, world.tilemap)
        if self.body.y > world.tilemap.pixel_size[1] + 40:
            self.kill()

    def draw(self, target, cam):
        surf = self.frame_surf()
        if self.flip:
            surf = pygame.transform.flip(surf, True, False)
        # 滚动感：按行进距离旋转
        angle = (self.t * 520 * self.dir) % 360
        surf = pygame.transform.rotate(surf, -angle)
        # 危险警示：滚动中的红色脉冲描边（"碰不得"的视觉语言）
        warn = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        warn.fill((255, 60, 40, int(46 + 40 * abs(math.sin(self.t * 8)))))
        surf.blit(warn, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        bottom = self._sprite_bottom(surf)
        x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                             self.body.y - bottom - 0.5)
        target.blit(surf, (x, y))


class DryBones(Enemy):
    """NSMBW 骷髅龟：踩散架 4 秒后重新拼起来；只有火球/星星/龟壳能真正干掉。"""

    art = "enemy/drybones"
    w, h = 13, 16
    speed = 0.45
    shell = False
    score = 200

    def __init__(self, world, x, y, dir=-1, **kw):
        super().__init__(world, x, y, dir=dir, **kw)
        self.collapsed = 0.0    # 散架倒计时

    def stomp(self, world, by):
        if self.collapsed > 0:
            return False        # 已经散了，再踩只是踩灰
        self.collapsed = 4.0
        self.body.vx = 0.0
        world.sfx("stomp")
        world.add_score(100, self.body.center)
        return True

    def hurt(self, world, by=None):
        # 火球/星星/滑壳才能击杀
        self.alive = False
        self.removed = True
        world.fx("hit", self.body.center)
        world.add_score(self.score, self.body.center)
        world.sfx("hit")

    def update(self, world):
        if self.collapsed > 0:
            self.collapsed -= 1 / 60.0
            self.t += 1 / 60.0
            if self.collapsed <= 0:
                self.collapsed = 0.0
                world.fx("pop", self.body.center)
            return
        super().update(world)

    def draw(self, target, cam):
        if self.collapsed > 0:
            # 散架：贴图压扁贴地 + 快苏醒时抖动
            surf = self.frame_surf()
            if self.flip:
                surf = pygame.transform.flip(surf, True, False)
            flat = pygame.transform.scale(surf, (surf.get_width(),
                                                 max(4, int(surf.get_height() * 0.22))))
            x, y = cam.to_screen(self.body.x - flat.get_width() / 2,
                                 self.body.y - flat.get_height())
            jit = 1 if (self.collapsed < 1.0 and int(self.collapsed * 24) % 2) else 0
            target.blit(flat, (x + jit, y))
            return
        super().draw(target, cam)


class Flame(Actor):
    """Bowser 吐出的火苗：水平飘行，碰到玩家造成伤害。"""

    art = "enemy/flame"
    w, h = 10, 10
    z = 14
    tag = "foe_proj"
    collides_player = True

    def __init__(self, world, x, y, dir=1, **kw):
        super().__init__(world, x, y, **kw)
        self.dir = dir
        self.life = 2.4

    def update(self, world):
        self.t += 1 / 60.0
        self.life -= 1 / 60.0
        self.body.x += self.dir * 1.5
        self.body.y += math.sin(self.t * 9.0) * 0.35
        if self.life <= 0 or move_x(self.body, world.tilemap):
            self.kill()


class Bowser(Enemy):
    """城堡 Boss：追踪玩家、跳跃、喷火；踩 3 次或火球 3 次击破。"""

    art = "enemy/bowser"
    w, h = 26, 26
    speed = 0.42
    stompable = True
    shell = False
    score = 5000
    hp = 3

    def __init__(self, world, x, y, hp=None, **kw):
        super().__init__(world, x, y, **kw)
        self.hp = int(hp) if hp is not None else type(self).hp
        self.jump_t = 1.2
        self.fire_t = 2.0
        self.dead = False

    def update(self, world):
        if self.dead:
            # 死亡动画：翻面坠出屏幕
            self.t += 1 / 60.0
            self.body.vy = min(5.0, self.body.vy + 0.25)
            self.body.y += self.body.vy
            return
        if not self.awake:
            if world.camera.view_rect.inflate(60, 0).colliderect(self.rect):
                self.awake = True
            return
        self.t += 1 / 60.0
        if self.invuln > 0:
            self.invuln -= 1 / 60.0
        if self.squashed > 0:                 # 受击压扁动画（Bowser 覆盖了 update，
            self.squashed -= 1 / 60.0          # 这里自己递减，且不能走 Enemy 的 kill 分支）
        player = world.player
        # 缓慢逼近玩家（有最大巡-range 半径）
        self.dir = 1 if player.body.x > self.body.x else -1
        self.body.vx = self.dir * self.speed
        move_x(self.body, world.tilemap)
        # 周期跳跃
        self.jump_t -= 1 / 60.0
        if self.jump_t <= 0 and self.body.on_ground:
            self.body.vy = -4.4
            self.jump_t = 2.6 + (self.t % 1.0)
        self.body.vy = min(6.0, self.body.vy + 0.30)
        move_y(self.body, world.tilemap)
        # 喷火
        self.fire_t -= 1 / 60.0
        if self.fire_t <= 0 and abs(player.body.x - self.body.x) < 110 \
                and world.phase == "play":
            world.spawn(Flame, self.body.x + self.dir * 14,
                        self.body.y - self.body.h * 0.7, dir=self.dir)
            world.sfx("fire")
            self.fire_t = 2.6
        self.flip = self.dir > 0

    def stomp(self, world, by):
        if self.invuln > 0 or self.dead:
            return False
        self.hp -= 1
        world.shake(2.2)
        if self.hp <= 0:
            self.dead = True
            self.body.vy = -3.4
            self.flip = not self.flip
            world.sfx("boss-hit")
            world.add_score(self.score, self.body.center)
            world.fx("pop", self.body.center)
            world.on_boss_dead(self)
            return True
        self.invuln = 1.2
        self.speed = min(1.0, self.speed + 0.22)
        self.squashed = 0.3
        world.sfx("boss-hit")
        world.add_score(500, self.body.center)
        return True

    def hurt(self, world, by=None):
        # 火球同样按次扣血
        self.stomp(world, by)

    def draw(self, target, cam):
        if self.dead or self.squashed > 0 or self.state in ("shell", "slide"):
            surf = self.frame_surf()
            if self.dead:
                surf = pygame.transform.flip(surf, False, True)
            if self.flip:
                surf = pygame.transform.flip(surf, True, False)
            if self.squashed > 0:
                surf = pygame.transform.scale(surf, (surf.get_width(),
                                                     max(4, int(surf.get_height() * 0.7))))
            x, y = cam.to_screen(self.body.x - surf.get_width() / 2,
                                 self.body.y - surf.get_height())
            target.blit(surf, (x, y))
            return
        if self.invuln > 0 and int(self.t * 30) % 2:
            return
        super().draw(target, cam)
