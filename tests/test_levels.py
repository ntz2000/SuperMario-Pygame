"""关卡数据有效性：行宽、对象类型、出生点。"""
from __future__ import annotations

import pytest

from mario.core.tiles import TILE, default_table
from mario.data.levels import LEVELS
from mario.game.registry import actor_for


class TestLevelData:
    @pytest.mark.parametrize("name", sorted(LEVELS))
    def test_rows_same_height(self, name):
        data = LEVELS[name]
        h = len(data["rows"])
        assert h >= 10, "关卡太矮"
        for i, row in enumerate(data["rows"]):
            assert len(row) == len(data["rows"][0]), f"第 {i} 行宽度不一致"

    @pytest.mark.parametrize("name", sorted(LEVELS))
    def test_objects_registered(self, name):
        unknown = [o for o in LEVELS[name].get("objects", [])
                   if actor_for(o["t"]) is None]
        assert not unknown, f"未注册的对象类型: {unknown}"

    @pytest.mark.parametrize("name", sorted(LEVELS))
    def test_player_spawn_in_bounds(self, name):
        data = LEVELS[name]
        spec = data["player"]
        rows = data["rows"]
        assert 0 <= spec["x"] < len(rows[0])
        assert 0 <= spec["y"] < len(rows)
        for sp in data.get("spawns", {}).values():
            assert 0 <= sp["x"] < len(rows[0])
            assert 0 <= sp["y"] < len(rows)

    @pytest.mark.parametrize("name", sorted(LEVELS))
    def test_flag_or_boss_present(self, name):
        if LEVELS[name].get("secret"):
            return  # 隐藏房靠管道返回，不需要终点
        objs = [o["t"] for o in LEVELS[name].get("objects", [])]
        assert "flag" in objs or "bowser" in objs, "没有终点"

    def test_three_star_coins_per_level(self):
        """每主关 0/1/2 三枚大金币（隐藏房里 `of` 指向主关的也算）。"""
        for name, data in LEVELS.items():
            if data.get("secret"):
                continue
            idxs = set()
            for other in LEVELS.values():
                for o in other.get("objects", []):
                    if o["t"] == "starcoin" and o.get("of", "") in ("", name):
                        idxs.add(o["idx"])
            assert idxs == {0, 1, 2}, f"{name} 的大金币: {sorted(idxs)}"

    @pytest.mark.parametrize("name", sorted(LEVELS))
    def test_valid_tile_codes(self, name):
        table = default_table()
        bad = set()
        for row in LEVELS[name]["rows"]:
            for ch in row:
                if ch not in ("", " ") and ch not in table.tiles:
                    bad.add(ch)
        assert not bad, f"未知字符: {bad}"

    def test_secret_level_has_warp_back(self):
        """隐藏房必须有回去的路。"""
        objs = LEVELS["1-1b"]["objects"]
        pipes = [o for o in objs if o["t"] == "pipe"]
        assert any("@" in o.get("to", "") for o in pipes), "隐藏房需要出口管道"

    def test_warp_targets_exist(self):
        for name, data in LEVELS.items():
            for o in data.get("objects", []):
                if o["t"] == "pipe":
                    target = o.get("to", "")
                    if target:
                        lvl = target.split("@")[0]
                        assert lvl in LEVELS, f"{name} 的管道指向不存在的 {lvl}"
                        if "@" in target:
                            spawn = target.split("@")[1]
                            assert spawn in data.get("spawns", {}) or \
                                spawn in LEVELS[lvl].get("spawns", {}), \
                                f"管道目标 {target} 缺少出生点定义"


class TestSpawnGround:
    @pytest.mark.parametrize("name", sorted(LEVELS))
    def test_player_not_inside_solid(self, name):
        data = LEVELS[name]
        spec = data["player"]
        table = default_table()
        code = data["rows"][spec["y"]][spec["x"]]
        tile = table.get(code)
        assert tile is None or not tile.solid, "出生点被埋在实心块里"
