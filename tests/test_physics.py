"""物理：轴向分离移动、单程平台、浮点碰撞过滤。"""
from __future__ import annotations

from mario.core.physics import Body, move_x, move_y
from mario.core.tilemap import TileMap


class TestMove:
    def test_fall_lands_on_ground(self):
        m = TileMap(["  ", "GG"])     # 地砖在第 1 行，顶面 y=16
        b = Body(x=8, y=8, w=8, h=14)
        for _ in range(60):
            b.vy = min(7, b.vy + 0.5)
            move_y(b, m)
        assert b.on_ground
        assert abs(b.y - 16.001) < 0.01

    def test_rise_hits_ceiling(self):
        m = TileMap(["GG", "  "])
        b = Body(x=8, y=30, w=8, h=14)
        b.vy = -4
        move_y(b, m)
        assert b.hit_ceiling
        assert abs(b.y - (16 + 14 - 0.001)) < 0.01   # 头顶被推回砖底

    def test_wall_stops_horizontal(self):
        m = TileMap(["G..", "G..", "G.."])   # 左侧一堵墙
        b = Body(x=18, y=44, w=8, h=8)      # 第 2 行，贴着墙
        b.vx = -5
        hits = move_x(b, m)
        assert hits, "应该撞到左墙"
        assert abs(b.x - (16 + 4 - 0.001)) < 0.01
        assert b.on_wall == -1

    def test_on_wall_resets_when_moving_freely(self):
        m = TileMap(["...", "..."])
        b = Body(x=8, y=40, w=8, h=8)
        b.on_wall = 1
        b.vx = 2
        move_x(b, m)
        assert b.on_wall == 0  # 没撞墙时必须清零（墙滑检测依赖）


class TestGroundNotWall:
    """脚下 0.001px 的贴面吸附不能被横移当成墙——历史 bug 的回归测试。"""

    def test_stand_and_walk_over_flat_ground(self):
        m = TileMap(["", "GGG"])
        b = Body(x=24, y=16.001, w=8, h=14)   # 站在地面顶面
        for i in range(30):
            b.vx = 1.2
            move_x(b, m)
            assert b.on_wall == 0, f"第 {i} 帧把地面当成了墙"
            b.vy = min(7, b.vy + 0.5)
            move_y(b, m)

    def test_wall_jump_surface_detectable(self):
        """真正的侧墙（贴墙 0.5px 以上）仍然算撞墙。"""
        m = TileMap(["..G", "..G", "..G"])
        b = Body(x=30, y=44, w=8, h=8)
        b.vx = 5
        hits = move_x(b, m)
        assert hits and b.on_wall == 1


class TestOneWay:
    def test_fall_through_from_below(self):
        m = TileMap(["  ", "==", "  "])   # 单程平台在第 1 行
        b = Body(x=8, y=40, w=8, h=8)
        b.vy = -5
        move_y(b, m)
        assert not b.hit_ceiling, "单程平台不能挡上升"

    def test_land_from_above(self):
        m = TileMap(["  ", "==", "  "])
        b = Body(x=8, y=10, w=8, h=8)
        b.vy = 4
        move_y(b, m)      # 10 -> 14，还没到平台
        assert not b.on_ground
        b.vy = 4
        c = move_y(b, m)  # 14 -> 18，穿入平台
        assert b.on_ground
        assert c.platform
        assert abs(b.y - 16.001) < 0.01


class TestTileMap:
    def test_solid_cells_margin_range(self):
        """solid_cells 是宽容探测（±1 格）；精确过滤由 move_* 完成。"""
        import pygame
        m = TileMap(["GG", "GG"])
        cells = list(m.solid_cells(pygame.Rect(16, 16, 2, 2)))
        assert len(cells) == 4

    def test_terrain_recolor_by_theme(self):
        """有真实瓦片 atlas 时主题走真实贴图；否则用 Theme 配色回退。"""
        try:
            from mario.assets.atlas import ATLAS
            has_atlas = "tile/castle-ground.top" in ATLAS
        except Exception:
            has_atlas = False
        m = TileMap(["G"], theme="castle")
        tile = m.tile(0, 0)
        if has_atlas:
            assert tile.art == "tile/castle-ground" and tile.body == "", \
                "应使用真实城堡瓦片"
        else:
            assert tile.body == m.table.theme("castle").ground[0], "应换成城堡配色"

    def test_no_theme_keeps_default(self):
        m = TileMap(["G"])
        assert m.tile(0, 0).colors() == {}, "无主题时应沿用注册的默认色"

    def test_hidden_tile_flag(self):
        m = TileMap(["H"], theme="overworld")
        assert m.tile(0, 0).hidden
        assert m.tile(0, 0).solid is False

    def test_set_invalidates_chunk(self):
        m = TileMap(["GG"])
        m.bind(_FakeAssets())
        m.chunk(0)
        m.set(0, 0, "X")
        assert 0 not in m._chunks

    def test_rows_with_spaces(self):
        """空格子必须是空格而非空串：空串 join 后行宽会塌缩。"""
        m = TileMap(["G   G"])
        assert m.at(2, 0) == " "
        assert m.at(0, 0) == "G"


class _FakeAssets:
    def __init__(self):
        import pygame
        self._s = pygame.Surface((16, 16), pygame.SRCALPHA)

    def sprite(self, id, **kw):
        class _S:
            surface = None
        s = _S()
        s.surface = self._s
        return s
