"""引擎与交互盲区补测：Camera、真实键盘 Input 边沿、损坏缓存。"""
from __future__ import annotations

import pygame

from mario.engine.camera import Camera
from mario.engine.input import Input
from mario.engine.assets import Assets, UnknownAsset


class TestCamera:
    def test_clamp_inside_bounds(self):
        c = Camera((320, 180), (0, 0, 640, 360))
        x, y = c.clamp(700, 500)
        assert x == 640 - 320
        assert y == 360 - 180

    def test_clamp_centers_small_bounds(self):
        """边界比视口小的时候水平居中，而不是夹成负数。"""
        c = Camera((320, 180), (0, 0, 100, 100))
        x, y = c.clamp(700, 500)
        assert x == (100 - 320) / 2
        assert y == (100 - 180) / 2

    def test_deadzone_keeps_position(self):
        c = Camera((320, 180), (0, 0, 2000, 2000))
        c.center_on((1000, 1000))
        before = list(c.pos)
        # 死区中心在镜头中心右侧（玩家领跑）：zone = [zx, zx+zone_w]
        zx = c.pos[0] + (c.view[0] - c.zone[0]) / 2
        zy = c.pos[1] + (c.view[1] - c.zone[1]) / 2
        c.follow(pygame.Rect(int(zx + c.zone[0] / 2 - 4), int(zy + c.zone[1] / 2 - 4), 8, 8))
        assert c.pos == before, "死区内的移动不应带动镜头"

    def test_snap_aligns_vertically(self):
        c = Camera((320, 180), (0, 0, 2000, 2000))
        c.pos = [0.0, 0.0]
        r = pygame.Rect(0, 400, 8, 8)
        c.follow(r, snap=True)
        assert c.pos[1] > 50, "snap 应立即对齐到目标高度"

    def test_shake_decays(self):
        c = Camera((320, 180), (0, 0, 640, 360))
        c.center_on((320, 180))
        c.shake = 4.0
        seen = 0
        for _ in range(40):
            ox, oy = c.offset
            if (ox, oy) != (round(c.pos[0]), round(c.pos[1])):
                seen += 1
        assert 0 < seen < 40, "震屏应该出现又衰减消失"
        assert c.shake <= 0.05


class TestKeyboardInput:
    def _mk(self):
        return Input()

    @staticmethod
    def _key(type_, key):
        return pygame.event.Event(type_, key=key)

    def test_press_release_edges(self):
        inp = self._mk()
        inp.feed([self._key(pygame.KEYDOWN, pygame.K_SPACE)])
        assert inp.pressed("jump") and inp.held("jump")
        inp.advance()                       # 边沿只活一帧
        assert not inp.pressed("jump") and inp.held("jump")
        inp.feed([self._key(pygame.KEYUP, pygame.K_SPACE)])
        assert inp.released("jump") and not inp.held("jump")
        inp.advance()
        assert not inp.released("jump")

    def test_same_frame_up_then_down_press_wins(self):
        """同帧 KEYUP 后 KEYDOWN：新按下使释放边沿失效（跳跃不被削减）。"""
        inp = self._mk()
        inp.feed([self._key(pygame.KEYDOWN, pygame.K_SPACE)])
        inp.advance()
        inp.feed([self._key(pygame.KEYUP, pygame.K_SPACE),
                  self._key(pygame.KEYDOWN, pygame.K_SPACE)])
        assert inp.pressed("jump")
        assert not inp.released("jump"), "新按下必须清除旧的释放边沿"

    def test_repeat_keydown_ignored(self):
        """系统按键重复（KEYDOWN 且已按下）不能重复触发边沿。"""
        inp = self._mk()
        inp.feed([self._key(pygame.KEYDOWN, pygame.K_LEFT)])
        inp.advance()
        inp.feed([self._key(pygame.KEYDOWN, pygame.K_LEFT)])   # 系统重复事件
        assert not inp.pressed("left")
        assert inp.held("left"), "仍然按住"

    def test_buffer_window(self):
        inp = self._mk()
        inp.feed([self._key(pygame.KEYDOWN, pygame.K_k)])
        for _ in range(7):
            inp.advance()
        assert inp.buffered("jump", 7)      # age=7 仍在窗口内（含端点）
        inp.advance()
        assert not inp.buffered("jump", 7)

    def test_disabled_blocks_everything(self):
        inp = self._mk()
        inp.enabled = False
        inp.feed([self._key(pygame.KEYDOWN, pygame.K_SPACE)])
        assert not inp.held("jump") and not inp.pressed("jump")
        assert inp.axis_x() == 0

    def test_axes(self):
        inp = self._mk()
        inp.feed([self._key(pygame.KEYDOWN, pygame.K_RIGHT),
                  self._key(pygame.KEYDOWN, pygame.K_DOWN)])
        assert inp.axis_x() == 1 and inp.axis_y() == 1


class TestAssetsRobustness:
    def test_unknown_asset_raises(self):
        a = Assets(enable_cache=False)
        try:
            a.sprite("definitely/not/registered")
        except UnknownAsset:
            return
        raise AssertionError("应当抛 UnknownAsset")

    def test_corrupt_manifest_recovers(self, tmp_path):
        """manifest 损坏时回退重建，不能让游戏起不来。"""
        cache = tmp_path / "c"
        cache.mkdir()
        (cache / "manifest.json").write_text("{broken json")
        a = Assets(cache_dir=str(cache))     # 不抛异常
        a.sprite("item/coin")
        a.flush()
        b = Assets(cache_dir=str(cache))
        b.sprite("item/coin")
        assert b.built == 0, "重建后应命中缓存"

    def test_corrupt_png_recovers(self, tmp_path):
        cache = tmp_path / "c"
        good = Assets(cache_dir=str(cache))
        good.sprite("item/coin")
        good.flush()
        # 把缓存 PNG 写坏
        for p in cache.glob("item_coin*.png"):
            p.write_bytes(b"not a png")
        bad = Assets(cache_dir=str(cache))
        bad.sprite("item/coin")
        assert bad.built == 1, "坏图应回退重建"
