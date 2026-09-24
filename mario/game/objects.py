"""道具、机关与关卡目标。

从砖块里蹦出的蘑菇/星星、可以搬的弹簧、载人平台、传送管道、检查点小旗、
终点的旗杆，以及 NSMB 标志性的三枚大金币（Star Coin）。
"""
from __future__ import annotations

import math

import pygame

from ..core.actor import Actor
from ..core.physics import move_x, move_y
from ..core.tiles import TILE
from ..engine.res import RES_SCALE as S


class PowerUp(Actor):
    """从方块里顶出来、然后朝一个方向慢悠悠走的道具。"""

    art = "item/super"
    w, h = 12, 13
    z = 8
    speed = 0.9
    collides_player = True

    def __init__(self, world, x, y, pop=False, dir=1, **kw):
        super().__init__(world, x, y, **kw)
        self.pop = pop
        self.dir = 1 if dir >= 0 else -1
        self.body.vx = self.dir * self.speed

    def update(self, world):
        self.t += 1 / 60.0
        if self.pop:                       # 从方块里缓缓升起
            self.body.y -= 1.1
            if self.t > 0.35:
                self.pop = False
            return
        if move_x(self.body, world.tilemap):
            # move_x 碰撞时已把 vx 清零，必须按方向重设而不是取负
            self.dir = -self.dir
            self.body.vx = self.dir * self.speed
        self.body.vy = min(6.0, self.body.vy + 0.30)
        move_y(self.body, world.tilemap)
        if self.body.y > world.tilemap.pixel_size[1] + 40:
            self.kill()

    def collect(self, world, player):
        self.apply(world, player)
        self.kill()
        world.fx("pop", self.body.center)

    def apply(self, world, player):
        player.grow(world)
        world.add_score(1000, self.body.center)


class Mushroom(PowerUp):
    art = "item/super"


class MegaMushroom(PowerUp):
    """巨大蘑菇：变身后撞碎砖块、碾压敌人。"""

    art = "item/mega"
    w, h = 16, 17

    def apply(self, world, player):
        player.set_form("mega")
        player.mega_t = 8.0
        world.sfx("power-up")
        world.hint("巨大化！撞碎砖块、碾压敌人", key="mega")
        world.add_score(2000, self.body.center)


class OneUp(PowerUp):
    art = "item/1up"

    def apply(self, world, player):
        world.lives += 1
        world.sfx("1up")
        world.fx("pop", self.body.center)


class FireFlower(PowerUp):
    art = "item/fire_flower"

    def apply(self, world, player):
        if player.form == "mini":
            player.set_form("small")
        elif player.form in ("small", "super"):
            player.set_form("fire")
        world.sfx("power-up")
        world.hint("火之花到手！按 C 发射火球", key="fire")
        world.add_score(1000, self.body.center)


class IceFlower(PowerUp):
    """冰之花（NSMB Wii）：发射冰球把敌人冻成冰块，冰块可以踩碎。"""

    art = "item/ice_flower"

    def apply(self, world, player):
        if player.form == "mini":
            player.set_form("small")
        elif player.form in ("small", "super", "fire"):
            player.set_form("ice")
        world.sfx("power-up")
        world.hint("冰之花到手！按 C 发射冰球冻结敌人", key="ice")
        world.add_score(1000, self.body.center)


class Star(PowerUp):
    """无敌星：彩虹闪烁 + 专属 BGM + 碰到的敌人全灭。"""

    art = "item/star"
    w, h = 13, 13

    def update(self, world):
        self.t += 1 / 60.0
        if self.pop:
            self.body.y -= 1.1
            if self.t > 0.35:
                self.pop = False
            return
        if move_x(self.body, world.tilemap):
            self.dir = -self.dir
            self.body.vx = self.dir * self.speed
        # 无敌星自带弹跳：move_y 返回 Contact（恒真值），必须看 ground 字段
        self.body.vy = min(6.0, self.body.vy + 0.30)
        c = move_y(self.body, world.tilemap)
        if c.ground:
            self.body.vy = -3.6
        if self.body.y > world.tilemap.pixel_size[1] + 40:
            self.kill()

    def apply(self, world, player):
        player.star = 8.0
        world.sfx("star")
        world.hint("无敌星！碰到的敌人直接撞飞", key="star")
        world.add_score(1000, self.body.center)


class Mini(PowerUp):
    """迷你蘑菇：变小变轻，跳得更高。"""

    art = "item/mini"
    w, h = 9, 10

    def apply(self, world, player):
        player.set_form("mini")
        player.mini = 12.0
        world.sfx("power-up")
        world.hint("迷你马里奥！更轻快，跳得更高", key="mini")


class PropellerMushroom(PowerUp):
    """NSMBW 螺旋桨蘑菇：按住跳跃垂直起飞，空中再按可悬浮缓降。"""

    art = "item/propeller"
    w, h = 13, 14

    def apply(self, world, player):
        if player.form == "mini":
            player.set_form("small")
        player.set_form("propeller")
        player.prop_fuel = 1.2
        world.sfx("power-up")
        world.hint("螺旋桨！空中按住 跳 垂直升空/缓降", key="propeller")
        world.add_score(1000, self.body.center)


class PenguinSuit(PowerUp):
    """NSMBW 企鹅装：水中如飞 + 冰面滑行 + 冰球。"""

    art = "item/penguin"
    w, h = 13, 14

    def apply(self, world, player):
        if player.form == "mini":
            player.set_form("small")
        player.set_form("penguin")
        world.sfx("power-up")
        world.hint("企鹅装！水中更灵活，高速冲刺=冰滑", key="penguin")
        world.add_score(1000, self.body.center)


class BlockCoin(Actor):
    """从方块里顶出的金币：弹起旋转后消失，纯粹是视觉。"""

    art = "item/coin"
    w, h = 10, 14
    z = 30
    collides_player = False

    def __init__(self, world, x, y, **kw):
        super().__init__(world, x, y, **kw)
        self.vy = -3.4

    def update(self, world):
        self.t += 1 / 60.0
        self.body.y += self.vy
        self.vy += 0.24
        if self.vy > 0 and self.t > 0.5:
            world.fx("sparkle", self.body.center)
            self.kill()


class Coin(Actor):
    """浮在场景里的金币：原地上下摆动，碰到即收。"""

    art = "item/coin"
    w, h = 10, 14
    z = 8
    collides_player = True

    def __init__(self, world, x, y, bob=3.0, **kw):
        super().__init__(world, x, y, **kw)
        self.y0 = y
        self.bob = bob

    def update(self, world):
        self.t += 1 / 60.0
        self.body.y = self.y0 + math.sin(self.t * 3.0) * self.bob * 0.2

    def collect(self, world, player):
        world.collect_coin(self.body.center)
        self.kill()


class StarCoin(Actor):
    """NSMB 标志收集品：每关三枚大金币，收集后记录进存档。

    ``of`` 指定归属关卡（隐藏房里的大金币计入主关）。"""

    art = "item/bigcoin"
    w, h = 16, 22
    z = 8
    collides_player = True

    def __init__(self, world, x, y, idx=0, of="", **kw):
        super().__init__(world, x, y, **kw)
        self.idx = int(idx)
        self.of = of
        self.y0 = y
        self.got = False

    def update(self, world):
        self.t += 1 / 60.0
        self.body.y = self.y0 + math.sin(self.t * 2.0) * 2.0

    def collect(self, world, player):
        if self.got:
            return
        self.got = True
        world.collect_starcoin(self.idx, self.body.center, level=self.of or None)
        self.kill()


class Spring(Actor):
    """弹簧垫：被压扁后把踩上来的角色弹上天。"""

    art = "item/spring"
    w, h = 14, 12
    z = 7
    power = 8.4

    def __init__(self, world, x, y, power=8.4, **kw):
        super().__init__(world, x, y, **kw)
        self.power = power
        self.squash = 0.0

    def update(self, world):
        self.t += 1 / 60.0
        self.squash = max(0.0, self.squash - 1 / 60.0)

    def bounce(self, actor):
        self.squash = 0.2
        self.set_anim("idle")
        self.world.sfx("spring")
        return -self.power


class MovingPlatform(Actor):
    """沿两点间直线往返的移动平台，头顶站人一起带走。"""

    art = "tile/platform.cap"
    w, h = 32, 6
    z = 6
    collides_player = False

    def __init__(self, world, x, y, to=(0, 0), period=4.0, phase=0.0, **kw):
        super().__init__(world, x, y, **kw)
        self.x0, self.y0 = x, y
        self.dx, self.dy = to[0] * TILE, to[1] * TILE
        self.period, self.phase = period, phase
        self.prev_x = x

    def update(self, world):
        self.t += 1 / 60.0
        k = 0.5 - 0.5 * math.cos(2 * math.pi * (self.t + self.phase) / self.period)
        self.body.x = self.x0 + self.dx * k
        self.body.y = self.y0 + self.dy * k
        self.carrier(world)

    def carrier(self, world):
        p = world.player
        r = self.rect
        if (abs(p.body.y - r.top) < 8 and r.left - 4 <= p.body.x <= r.right + 4
                and p.body.vy >= 0):
            p.body.y = r.top
            p.body.vy = 0.0
            p.body.on_ground = True
            p.body.x += (self.body.x - self.prev_x)
        self.prev_x = self.body.x

    def draw(self, target, cam):
        surf = self.world.assets.sprite(self.art).surface
        x, y = cam.to_screen(self.body.x - self.body.w / 2, self.body.y - self.body.h)
        target.blit(pygame.transform.scale(surf, (self.body.w * S, self.body.h * S)), (x, y))


class WarpPipe(Actor):
    """可进入的管道：站上去按住"下"传送到目标关卡/出生点。"""

    art = "tile/pipe.cap"
    w, h = 32, 10
    z = 5
    collides_player = False

    def __init__(self, world, x, y, to="", **kw):
        super().__init__(world, x, y, **kw)
        self.to = to

    def update(self, world):
        p = world.player
        if p.rect.colliderect(self.rect) and world.input.held("down") \
                and p.body.on_ground and world.phase == "play":
            world.enter_pipe(self.to)


class CheckpointFlag(Actor):
    """中途检查点：碰到后立旗，死亡从这里复活。"""

    w, h = 4, 64
    z = 5
    collides_player = False
    color = (240, 240, 250)

    def __init__(self, world, x, y, **kw):
        super().__init__(world, x, y, **kw)
        self.passed = False
        self.flag_t = 0.0

    def update(self, world):
        p = world.player
        if not self.passed and p.rect.colliderect(self.rect.inflate(18, 0)) \
                and world.phase == "play":
            self.passed = True
            world.on_checkpoint((self.body.x, self.body.y))
            world.sfx("checkpoint")
        if self.passed and self.flag_t < 1.0:
            self.flag_t += 1 / 30.0

    def draw(self, target, cam):
        x, y = cam.to_screen(self.body.x - 2, self.body.y - self.h)
        pygame.draw.rect(target, (190, 190, 210), (x, y, 3 * S, self.h * S))
        pygame.draw.circle(target, (255, 240, 160), (x + S, y), 2 * S)
        # 未过：灰旗；已过：金旗升起
        fy = y + 6 * S + (1.0 - min(1.0, self.flag_t)) * 18 * S
        col = (255, 214, 90) if self.passed else (150, 150, 165)
        pygame.draw.polygon(target, col, [(x + 3 * S, fy), (x + 15 * S, fy + 4 * S),
                                         (x + 3 * S, fy + 9 * S)])


class GoalFlag(Actor):
    """终点旗杆：碰到触发通关序列，旗子滑落 + 烟花。"""

    w, h = 6, 110
    z = 4
    collides_player = False

    def __init__(self, world, x, y, **kw):
        super().__init__(world, x, y, **kw)
        self.flag_t = 1.0     # 1=杆顶，0=滑到底

    def update(self, world):
        p = world.player
        if world.phase == "play" and p.rect.colliderect(self.rect.inflate(14, 0)):
            world.finish(self)

    def draw(self, target, cam):
        x, y = cam.to_screen(self.body.x - 3, self.body.y - self.h)
        # 杆
        pygame.draw.rect(target, (200, 205, 220), (x + 2 * S, y, 3 * S, self.h * S))
        pygame.draw.rect(target, (255, 255, 255), (x + 2 * S, y, S, self.h * S))
        # 顶球
        pygame.draw.circle(target, (255, 224, 130), (x + 3 * S, y), 3 * S)
        # 旗（随 flag_t 从顶滑到底）
        fy = y + 6 * S + (1.0 - self.flag_t) * (self.h - 20) * S
        pts = [(x + 5 * S, fy), (x + 20 * S, fy + 6 * S), (x + 5 * S, fy + 13 * S)]
        pygame.draw.polygon(target, (72, 168, 80), pts)
        pygame.draw.polygon(target, (120, 210, 120),
                            [(x + 5 * S, fy), (x + 12 * S, fy + 3 * S), (x + 5 * S, fy + 6 * S)])


class Fireball(Actor):
    art = "fx/hit"
    w, h = 8, 8
    z = 14
    tag = "proj"
    freezes = False
    collides_player = False

    def __init__(self, world, x, y, dir=1, **kw):
        super().__init__(world, x, y, **kw)
        self.dir = dir
        self.life = 1.6
        self.body.vx = dir * 3.4

    def update(self, world):
        self.t += 1 / 60.0
        self.life -= 1 / 60.0
        if self.life <= 0:
            self.kill()
            return
        if int(self.t * 60) % 3 == 0:      # 尾迹粒子
            world.fx("sparkle" if getattr(self, "freezes", False) else "hit",
                     self.body.center)
        if move_x(self.body, world.tilemap):
            self.kill()
            world.fx("pop", self.body.center)
        self.body.vy = min(5.0, self.body.vy + 0.5)
        # 落地反弹：看 Contact.ground（返回值本身恒真值，不能用）
        c = move_y(self.body, world.tilemap)
        if c.ground:
            self.body.vy = -2.6

    def draw(self, target, cam):
        x, y = cam.to_screen(*self.body.center)
        pygame.draw.circle(target, (255, 190, 90), (x, y), 3 * S)
        pygame.draw.circle(target, (255, 245, 200), (x, y), S)


class IceBall(Fireball):
    """冰球：命中敌人改为冻结（由 level 的投射物循环调用 freeze）。"""

    freezes = True
    art = "fx/iceball"

    def __init__(self, world, x, y, dir=1, **kw):
        super().__init__(world, x, y, dir=dir, **kw)
        self.life = 1.6

    def update(self, world):
        self.t += 1 / 60.0
        self.life -= 1 / 60.0
        if self.life <= 0:
            self.kill()
            return
        if move_x(self.body, world.tilemap):
            self.kill()
            world.fx("splash", self.body.center)   # 撞墙碎成雪沫
        self.body.vy = min(5.0, self.body.vy + 0.5)
        c = move_y(self.body, world.tilemap)
        if c.ground:
            self.body.vy = -2.6

    def draw(self, target, cam):
        x, y = cam.to_screen(*self.body.center)
        pygame.draw.circle(target, (150, 210, 255), (x, y), 3 * S)
        pygame.draw.circle(target, (225, 245, 255), (x, y), S)
