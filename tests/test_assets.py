"""资源一致性：所有被引用的 art id 都真的注册了（防 koopa_red 类事故）。"""
from __future__ import annotations

import pygame

import mario.art  # noqa: F401
from mario.engine.assets import Assets, registered
from mario.core.tiles import default_table


def new_assets():
    return Assets(enable_cache=False)


class TestTileArt:
    """方块表里的每个 art 前缀 × 三种变体都能生成。"""

    def test_every_tile_art_exists(self):
        a = new_assets()
        table = default_table()
        missing = []
        for code, tile in table.tiles.items():
            if not tile.art or tile.hidden or tile.decoration:
                continue  # 装饰与隐藏块不参与网格渲染
            for variant in ("fill", "top", "cap"):
                aid = f"{tile.art}.{variant}"
                if aid not in registered():
                    missing.append(aid)
                    continue
                try:
                    a.sprite(aid, **tile.colors())
                except Exception as e:  # noqa: BLE001
                    missing.append(f"{aid}: {e}")
        assert not missing, f"缺失: {missing}"

    def test_theme_overrides_generate(self):
        a = new_assets()
        table = default_table()
        for theme in ("overworld", "underground", "castle", "sky", "water"):
            for code in "GDB":
                tile = table.terrain(code, theme)
                a.sprite(f"{tile.art}.top", **tile.colors())


class TestActorArt:
    """每个 actor 类的 art / shell_art / 动画帧都存在。"""

    def test_all_actor_art_exists(self):
        a = new_assets()
        import mario.game.enemies as E
        import mario.game.objects as O
        from mario.game.player import Player

        classes = [E.Enemy, E.Goomba, E.Koopa, E.RedKoopa, E.Spiny, E.Buzzy,
                   E.Piranha, E.Cheep, E.Flame, E.Bowser,
                   O.PowerUp, O.Mushroom, O.MegaMushroom, O.OneUp, O.FireFlower,
                   O.Star, O.Mini, O.BlockCoin, O.Coin, O.StarCoin, O.Spring,
                   O.MovingPlatform, O.WarpPipe, O.CheckpointFlag, O.GoalFlag,
                   O.Fireball, Player]
        missing = []
        for cls in classes:
            for prefix in (cls.art, getattr(cls, "shell_art", "")):
                if not prefix or prefix in ("hero") or prefix.startswith("tile/") \
                        or prefix.startswith("fx/"):
                    continue  # hero 的 art 会带上形态后缀，单独由 hero 测试覆盖
                if prefix not in registered():
                    missing.append(prefix)
                    continue
                a.sprite(prefix)
        assert not missing, f"缺失: {missing}"

    def test_hero_all_forms_and_anims(self):
        a = new_assets()
        from mario.art.hero import CYCLES, FORMS
        missing = []
        for form in FORMS:
            for anim in CYCLES:
                aid = f"hero.{form}.{anim}"
                if aid not in registered():
                    missing.append(aid)
                    continue
                a.sprite(aid)
        assert not missing


class TestFxArt:
    def test_fx_ids(self):
        a = new_assets()
        for fx in ("coin", "pop", "hit", "dust", "shard", "sparkle", "firework"):
            a.sprite(f"fx/{fx}")


class TestSounds:
    def test_sfx_and_music(self):
        a = new_assets()
        for aid in registered():
            if aid.startswith(("sfx/", "music/")):
                a.sprite(aid)  # 全部能渲染，不抛异常


class TestCacheRoundTrip:
    def test_manifest_written(self, tmp_path):
        cache = tmp_path / "cache"
        a = Assets(cache_dir=str(cache))
        a.sprite("item/coin")
        a.flush()
        assert (cache / "manifest.json").exists()
        # 重新加载命中缓存而不是重新生成
        b = Assets(cache_dir=str(cache))
        b.sprite("item/coin")
        assert b.built == 0
