"""玩法集成测试：无头驱动关卡场景，验证核心机制链路。"""
from __future__ import annotations

import pytest

from mario.core.tiles import TILE
from mario.data.levels import LEVELS
from mario.scenes.level import LevelScene
from tests.conftest import run


def enter(app, level="1-1", **kw):
    scene = LevelScene(app, LEVELS[level])
    scene.on_enter(id=level, **kw)
    return scene


class TestMovement:
    def test_runs_right(self, app, level):
        x0 = level.player.body.x
        app.input.press("right")
        run(level, 60)
        assert level.player.body.x > x0 + 20

    def test_jump_leaves_ground_and_lands(self, app, level):
        y0 = level.player.body.y
        app.input.press("right")
        run(level, 10)
        app.input.press("jump")
        peak = y0
        for _ in range(40):
            level.update()
            app.input.advance()
            peak = min(peak, level.player.body.y)
        assert peak < y0 - 12, "跳起高度不足"
        assert level.player.body.on_ground, "应落回地面"

    def test_pit_death_transitions(self, app, level):
        level.player.body.x = 28 * TILE + 8      # 推到坑上
        level.player.body.vy = 0
        run(level, 120)
        assert level.phase == "death"

    def test_death_then_respawn(self, app, level):
        lives0 = level.lives
        level.player.body.x = 28 * TILE + 8
        run(level, 60)
        assert level.phase == "death"
        run(level, 90)
        assert level.lives == lives0 - 1


class TestEnemies:
    def _drop_on(self, app, level, cls, dx=0, dy=26):
        """把玩家放到敌人头顶上方让它下落踩中。"""
        foe = level.spawn(cls, level.player.body.x + dx, 13 * TILE)
        foe.awake = False                     # 别让它走开
        level.player.body.y = foe.body.y - dy
        level.player.body.vy = 0
        return foe

    def test_stomp_goomba(self, app, level):
        from mario.game.enemies import Goomba

        g = self._drop_on(app, level, Goomba, dx=3)
        score0 = level.score
        run(level, 12)
        assert g.squashed > 0 or not g.alive
        assert level.score > score0

    def test_stomp_koopa_leaves_shell(self, app, level):
        from mario.game.enemies import Koopa

        k = self._drop_on(app, level, Koopa, dx=3, dy=30)
        run(level, 12)
        assert k.state == "shell", f"状态应为 shell: {k.state}"

    def test_shell_pickup_and_throw(self, app, level):
        from mario.game.enemies import Koopa

        k = level.spawn(Koopa, level.player.body.x + 4, 13 * TILE)
        k.state = "shell"
        level.player.body.x = k.body.x - 6
        level.player.body.y = k.body.y
        app.input.press("action")
        run(level, 2)
        assert level.player.held is k, "应该搬起龟壳"
        app.input.press("action")
        run(level, 2)
        assert k.state == "slide" and level.player.held is None

    def test_sliding_shell_kills_enemy(self, app, level):
        from mario.game.enemies import Goomba, Koopa

        k = level.spawn(Koopa, 40 * TILE, 12 * TILE)
        k.state = "slide"
        k.dir = 1
        k.awake = True
        g = level.spawn(Goomba, 44 * TILE, 12 * TILE)
        g.awake = True
        for _ in range(120):
            k.update(level)
            g.update(level)
            level._shell_hits()
            if not g.alive:
                break
        assert not g.alive, "滑行龟壳应杀死板栗仔"

    def test_bowser_three_stomps(self, app):
        scene = enter(app, "1-castle")
        bowser = next(a for a in scene.actors if type(a).__name__ == "Bowser")
        bowser.awake = True
        for _ in range(3):
            bowser.invuln = 0
            scene.player.body.x = bowser.body.x
            scene.player.body.y = bowser.body.y - 20   # 脚要落进身体里
            scene.player.body.vy = 2
            scene._collisions()
        assert bowser.dead
        assert scene.phase == "win"

    def test_piranha_hurts(self, app, level):
        from mario.game.enemies import Piranha

        pir = level.spawn(Piranha, 56 * TILE + 8, 160, phase=1.0)
        pir.body.y = pir.base_y - 20
        p = level.player
        p.body.x = pir.body.x
        p.body.y = pir.body.y + 8
        level._collisions()
        assert p.dying and level.phase == "death", "食人花接触应致死"

    def test_spiny_not_stompable(self, app, level):
        from mario.game.enemies import Spiny

        sp = level.spawn(Spiny, 50 * TILE, 12 * TILE)
        sp.awake = False
        p = level.player
        p.set_form("super")
        p.body.x = sp.body.x
        p.body.y = sp.body.y - 16
        p.body.vy = 2
        level._collisions()
        assert p.form == "small", "踩刺龟应受伤缩水"

    def test_spin_bounces_off_spiny(self, app, level):
        from mario.game.enemies import Spiny

        sp = level.spawn(Spiny, 50 * TILE, 12 * TILE)
        sp.awake = False
        p = level.player
        p.set_form("super")
        p.spinning = True
        p.body.x = sp.body.x
        p.body.y = sp.body.y - 16
        p.body.vy = 2
        level._collisions()
        assert p.body.vy < 0, "旋转跳应从刺龟身上弹开"
        assert p.form == "super", "旋转跳不应受伤"


class TestBlocks:
    def _stand_under(self, app, level, tx, ty, form=None):
        """把玩家放到 (tx,ty) 方块正下方的地面上站稳。"""
        if form:
            level.player.set_form(form)
        level.player.body.x = (tx + 0.5) * TILE
        level.player.body.y = 13 * TILE + 0.001
        level.player.body.vy = 0
        run(level, 2)      # 让落地状态生效

    def test_question_block_yields_coin(self, app, level):
        tx, ty = 22, 9
        self._stand_under(app, level, tx, ty)
        coins0 = level.coins
        app.input.press("jump")
        for _ in range(40):
            level.update()
            app.input.advance()
        assert level.tilemap.at(tx, ty) == "X", "问号块应变为用过的块"
        assert level.coins == coins0 + 1

    def test_brick_breaks_when_super(self, app, level):
        tx, ty = 21, 9
        level.tilemap.set(tx, ty, "b")     # 可破坏砖
        self._stand_under(app, level, tx, ty, form="super")
        app.input.press("jump")
        for _ in range(40):
            level.update()
            app.input.advance()
        assert level.tilemap.at(tx, ty) == "", "超级形态应撞碎砖块"

    def test_hidden_block_reveals(self, app, level):
        tx, ty = 35, 9
        self._stand_under(app, level, tx, ty)
        coins0 = level.coins
        app.input.press("jump")
        for _ in range(40):
            level.update()
            app.input.advance()
        assert level.tilemap.at(tx, ty) == "X", "隐藏块应显形"
        assert level.coins == coins0 + 1

    def test_multi_coin_block(self, app, level):
        tx, ty = 79, 9
        # 清掉游荡的敌人，避免测试期间被撞死
        for a in list(level.actors):
            if a is not level.player and hasattr(a, "stomp"):
                a.kill()
        self._stand_under(app, level, tx, ty)
        coins0 = level.coins
        for _ in range(3):
            app.input.press("jump")
            for _ in range(45):
                level.update()
                app.input.advance()
            app.input.release("jump")
        assert level.coins > coins0 + 2, "多币块应连续出币"


class TestPickups:
    def test_coin_collect(self, app, level):
        from mario.game.objects import Coin

        level.spawn(Coin, level.player.body.x, level.player.body.y - 4)
        coins0 = level.coins
        run(level, 3)
        assert level.coins == coins0 + 1

    def test_star_coin_recorded(self, app, level):
        from mario.game.objects import StarCoin

        level.spawn(StarCoin, level.player.body.x, level.player.body.y - 10, idx=2)
        run(level, 3)
        assert app.progress["stars"]["1-1"].get(2) is True

    def test_mushroom_grows(self, app, level):
        from mario.game.objects import Mushroom

        level.spawn(Mushroom, level.player.body.x, level.player.body.y - 4)
        run(level, 3)
        assert level.player.form == "super"

    def test_flower_gives_fire(self, app, level):
        from mario.game.objects import FireFlower

        level.player.set_form("super")
        level.spawn(FireFlower, level.player.body.x, level.player.body.y - 4)
        run(level, 3)
        assert level.player.form == "fire"

    def test_mega_form_breaks_bricks(self, app, level):
        level.player.set_form("mega")
        level.player.mega_t = 5
        # 前方放一排碎砖
        tx = int(level.player.body.x // TILE) + 1
        level.tilemap.set(tx, 12, "b")
        level.player.body.vx = 3
        app.input.press("right")
        for _ in range(30):
            level.update()
            app.input.advance()
        assert level.tilemap.at(tx, 12) == "", "巨人应撞碎砖块"


class TestFlow:
    def test_fireball_no_crash_and_kills(self, app, level):
        """火形态扔火球：不崩（玩家不能被当敌人）、命中敌人有效。"""
        from mario.game.enemies import Goomba
        from mario.game.objects import Fireball

        level.player.set_form("fire")
        level.player.body.facing = 1
        g = level.spawn(Goomba, level.player.body.x + 30, 13 * TILE)
        g.awake = True
        level.player.body.x = g.body.x - 40
        app.input.press("action")
        for _ in range(60):
            level.update()
            app.input.advance()
            level.player.body.facing = 1
        assert level.player.alive, "扔火球不能崩或自杀"
        assert not g.alive, "火球应能烧死敌人"

    def test_ice_flower_freezes_and_shatters(self, app, level):
        """冰之花（NSMB Wii）：吃花→冰形态→冰球冻结敌人→踩碎冰块。"""
        from mario.game.enemies import Goomba, Bowser
        from mario.game.objects import IceFlower

        level.spawn(IceFlower, level.player.body.x, level.player.body.y - 4)
        run(level, 3)
        assert level.player.form == "ice", "应变成冰形态"
        g = level.spawn(Goomba, level.player.body.x + 60, 13 * TILE)
        g.awake = True
        level.player.body.facing = 1
        app.input.press("action")
        for _ in range(60):
            level.update()
            app.input.advance()
            level.player.body.facing = 1
        assert g.state == "frozen", "冰球应冻结敌人"
        # 踩碎
        p = level.player
        p.body.x = g.body.x
        p.body.y = g.body.y - 10
        p.body.vy = 2
        level._collisions()
        assert not g.alive, "踩冻结敌人应碎冰"
        # Boss 免疫
        bow = level.spawn(Bowser, 100 * TILE, 13 * TILE)
        bow.awake = True
        bow.freeze(level)
        assert bow.state != "frozen", "Bowser 冻不住"

    def test_frozen_expires_and_hint_fires(self, app, level):
        from mario.game.enemies import Goomba
        from mario.game.objects import FireFlower

        g = level.spawn(Goomba, 60 * TILE, 13 * TILE)
        g.awake = True
        g.state = "frozen"
        g.frozen_t = 0.05
        run(level, 10)
        assert g.state == "walk", "冰冻到期应解冻"
        # 火花提示系统
        level.spawn(FireFlower, level.player.body.x, level.player.body.y - 4)
        run(level, 3)
        assert level.player.form == "fire"
        assert any("火球" in h["text"] for h in level.hints), "拾取火花应有按键提示"

    def test_combo_increments(self, app, level):
        """不落地连踩：连击分递增，连击表走完后给 1UP。"""
        from mario.game.enemies import Goomba

        lives0 = level.lives
        p = level.player
        p.body.x = 100 * TILE           # 空旷处
        p.set_form("super")
        score0 = level.score
        for i in range(10):
            g = level.spawn(Goomba, p.body.x + 4, 13 * TILE)
            g.awake = False
            p.body.vy = 2
            p.body.y = g.body.y - 12          # 脚要落进敌人碰撞盒
            level._collisions()
        assert p.combo == 10
        assert level.score > score0 + 8000, "连击分应按表累加"
        assert level.lives == lives0 + 1, "连击表走完应给 1UP"

    def test_note_block_bounces(self, app, level):
        from mario.core.tiles import TILE as T

        tx = int(level.player.body.x // T) + 2
        level.tilemap.set(tx, 12, "N")
        p = level.player
        p.body.x = (tx + 0.5) * T
        p.body.y = 13 * T + 0.001
        level.update()
        app.input.advance()
        p.body.vy = 3
        level.update()
        app.input.advance()
        assert p.body.vy < -5, "落到音符块上应被弹起"

    def test_checkpoint_respawn_position(self, app, level):
        """死亡后应从检查点复活，而不是回关卡开头。"""
        from mario.game.objects import CheckpointFlag

        cp = next(a for a in level.actors if type(a) is CheckpointFlag)
        level.player.body.x = cp.body.x
        level.player.body.y = cp.body.y
        run(level, 3)
        assert level.checkpoint is not None
        level.player.body.x = 28 * TILE + 8          # 推下坑
        run(level, 200)
        assert level.phase == "death"
        # 重生的新场景出生在检查点
        assert level.checkpoint == (cp.body.x, cp.body.y)

    def test_pound_breaks_block_below(self, app, level):
        from mario.core.tiles import TILE as T

        tx = int(level.player.body.x // T) + 1
        level.tilemap.set(tx, 12, "b")
        p = level.player
        p.body.x = (tx + 0.5) * T
        p.body.y = 11 * T
        p.pound = True
        p.body.vy = 4
        for _ in range(30):
            level.update()
            app.input.advance()
        assert level.tilemap.at(tx, 12) == "", "下砸应砸碎脚下的碎砖"

    def test_new_enemies_v6(self, app, level):
        """NSMBW 新敌人：Biddybud 可踩 / Grrrol 无敌 / DryBones 散架复活。"""
        from mario.game.enemies import Biddybud, Grrrol, DryBones

        b = level.spawn(Biddybud, 50 * TILE, 13 * TILE)
        b.awake = True
        p = level.player
        p.body.x = b.body.x; p.body.y = b.body.y - 10; p.body.vy = 2
        level._collisions()
        assert b.squashed > 0, "Biddybud 应可踩扁"

        r = level.spawn(Grrrol, 60 * TILE, 13 * TILE)
        r.awake = True
        r.hurt(level, None)
        p.star = 99
        p.body.x = r.body.x; p.body.y = r.body.y - 10; p.body.vy = 2
        level._collisions()
        assert r.alive, "Grrrol 星星也踩不死"
        p.star = 0

        d = level.spawn(DryBones, 70 * TILE, 13 * TILE)
        d.awake = True
        p.body.x = d.body.x; p.body.y = d.body.y - 10; p.body.vy = 2
        level._collisions()
        assert d.collapsed > 0, "DryBones 应散架"
        d.collapsed = 0.05
        for _ in range(10):
            d.update(level)
        assert d.alive and d.collapsed == 0, "散架后应复活"
        d.hurt(level, None)
        assert not d.alive, "火球可击杀"

    def test_propeller_and_penguin_v6(self, app, level):
        """NSMBW 招牌道具：螺旋桨空中起飞 + 企鹅冰球/滑行。"""
        from mario.game.objects import PropellerMushroom, PenguinSuit

        level.spawn(PropellerMushroom, level.player.body.x, level.player.body.y - 4)
        run(level, 4)
        assert level.player.form == "propeller"
        p = level.player
        p.body.y = 13 * TILE - 60
        p.body.vy = 0
        app.input.press("jump")
        y0 = p.body.y
        for _ in range(20):
            level.update(); app.input.advance()
        assert y0 - p.body.y > 15, "螺旋桨应空中上升"
        app.input.release("jump")

        level.spawn(PenguinSuit, p.body.x, p.body.y - 4)
        run(level, 4)
        assert level.player.form == "penguin"
        app.input.press("action")
        for _ in range(30):
            level.update(); app.input.advance()
        assert any(type(a).__name__ == "IceBall" for a in level.actors), "企鹅应扔冰球"

    def test_ice_slippery_v7(self, app):
        """世界2 冰面：松开方向后继续滑行（摩擦 0.15）。"""
        from mario.data.levels import LEVELS as L

        scene = LevelScene(app, L["2-2"])
        scene.on_enter(id="2-2")
        for a in list(scene.actors):
            if a is not scene.player:
                a.kill()
        p = scene.player
        app.input.press("right", "run")
        for _ in range(40):
            scene.update(); app.input.advance()
        assert p.body.vx > 1.5
        app.input.release("right", "run")
        for _ in range(40):
            scene.update(); app.input.advance()
        assert p.body.vx > 0.5, "冰面松开后应继续滑行"

    def test_bump_block_kills_enemy_above(self, app, level):
        """顶块冲击波：块正上方的敌人被弹飞（NSMB 顶块杀敌）。"""
        from mario.game.enemies import Goomba

        tx = 22
        g = level.spawn(Goomba, (tx + 0.5) * TILE, 9 * TILE - 1)
        g.awake = True
        p = level.player
        p.body.x = (tx + 0.5) * TILE
        p.body.y = 13 * TILE + 0.001
        app.input.press("jump")
        for _ in range(40):
            level.update()
            app.input.advance()
        assert not g.alive, "顶块应弹飞上方敌人"
        assert p.alive

    def test_flag_finish(self, app, level):
        from mario.game.objects import GoalFlag

        flag = next(a for a in level.actors if type(a) is GoalFlag)
        level.player.body.x = flag.body.x
        level.player.body.y = flag.body.y
        run(level, 2)
        assert level.phase == "win"
        assert level.player.locked

    def test_checkpoint_sets_respawn(self, app, level):
        from mario.game.objects import CheckpointFlag

        cp = next(a for a in level.actors if type(a) is CheckpointFlag)
        level.player.body.x = cp.body.x
        level.player.body.y = cp.body.y
        run(level, 2)
        assert level.checkpoint == (cp.body.x, cp.body.y)
        assert cp.passed

    def test_warp_pipe_enters_bonus(self, app, level):
        from mario.game.objects import WarpPipe

        pipe = next(a for a in level.actors if type(a) is WarpPipe)
        assert pipe.to == "1-1b"
        level.player.body.x = pipe.body.x
        level.player.body.y = pipe.body.y
        level.player.body.on_ground = True
        app.input.press("down")
        run(level, 3)
        assert level.phase == "pipe"
        assert level.next_level == "1-1b"

    def test_advance_to_next_level(self, app, level):
        level.phase = "win"
        level.phase_t = 5.0
        level.player.alive = True
        level.update()
        # fade 已排队（transition in 阶段）
        assert app.scenes.transition.busy

    def test_time_out_kills(self, app, level):
        level.time_left = 0.01
        run(level, 5)
        assert level.phase == "death"

    def test_respawn_bubble_safe(self, app, level):
        """NSMB 气泡重生：死→气泡降落→落地无敌→不被出生点敌人秒杀（回归锁定）。"""
        from mario.game.enemies import Koopa

        # 检查点旁放一只朝检查点巡逻的龟（历史 bug 的元凶布局）
        cp = next(a for a in level.actors if type(a).__name__ == "CheckpointFlag")
        koopa = level.spawn(Koopa, cp.body.x + 16, 13 * TILE, dir=-1)
        koopa.awake = True
        p = level.player
        p.body.x, p.body.y = cp.body.x, cp.body.y     # 触发检查点
        run(level, 3)
        assert level.checkpoint is not None
        p.body.x = 63 * TILE + 8                       # 检查点之后的坑
        run(level, 120)                                # 死亡序列
        assert level.phase == "death"
        run(level, 60)                                 # 等待重生场景换入（fade 期间不更新）
        # fade_to 已排队：直接构造新场景验证气泡
        app2 = app
        new = LevelScene(app2, level.data,
                         carry=dict(score=5, coins=0, lives=3,
                                    checkpoint=level.checkpoint, respawn=True))
        new.on_enter(id="1-1")
        p2 = new.player
        assert p2.bubble is True, "重生应以气泡开始"
        assert p2.body.y < p2._bubble_ground - 100, "气泡应从高处开始"
        for _ in range(200):                           # 等气泡降落
            new.update()
            new.input.advance()
        assert p2.bubble is False, "气泡应已落地"
        assert p2.invuln > 0, "落地后应有无敌帧"
        assert p2.alive and new.phase == "play"
        # 落地 3 秒无敌期间巡逻龟不能秒杀
        for _ in range(180):
            new.update()
            new.input.advance()
        assert new.phase == "play", "无敌期内不应死亡"


class TestScenes:
    def test_title_music_and_select(self, app):
        from mario.scenes.title import TitleScene

        t = TitleScene(app, LEVELS)
        t.on_enter()
        assert "1-1b" not in t.names, "隐藏房不应出现在标题列表"
        t.start()
        assert app.scenes.transition.busy

    def test_worldmap_music(self, app):
        from mario.scenes.worldmap import WorldMapScene

        wm = WorldMapScene(app, [dict(level=k, label=v.get("label", k))
                                 for k, v in LEVELS.items() if not v.get("secret")],
                           app.progress)
        wm.on_enter()

    def test_headless_capture(self, app, tmp_path):
        """整帧循环 + 渲染 + 截图，确保 draw 链路无异常。"""
        out = tmp_path / "shot.png"
        app.run(enter(app, "1-1"), frames=30, capture=str(out))
        assert out.exists() and out.stat().st_size > 1000
