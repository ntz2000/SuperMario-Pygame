"""关卡数据：字符网格 + 对象列表。

关卡用一个小 DSL 在 Python 里搭出来（见 :mod:`mario.core.tiles` 里每个字母的
含义），再交给关卡场景。用代码写地形的好处是可 diff——一段平地就是
``b.floor(4, 22)``，而不是 200 个字符的长串。

世界 1：草原 1-1（带隐藏房 1-1b）、地下 1-2（墙跳竖井）、水关 1-3、城堡 Boss。
每关三枚大金币（Star Coin），其中 1-1 的第二枚藏在隐藏房里。
"""
from __future__ import annotations

from ..core.tiles import TILE


class Builder:
    """空格子必须用空格占位：``"".join`` 会把空串格子折叠掉，行宽就塌了。"""

    def __init__(self, w: int, h: int = 15, fill: str = " "):
        self.w, self.h = w, h
        self.grid = [[fill] * w for _ in range(h)]
        self.objects: list[dict] = []

    def put(self, x: int, y: int, code: str):
        self.grid[y][x] = code
        return self

    def box(self, x0: int, y0: int, x1: int, y1: int, code: str):
        for y in range(y0, min(y1 + 1, self.h)):
            for x in range(x0, min(x1 + 1, self.w)):
                self.grid[y][x] = code
        return self

    def floor(self, x0: int, x1: int, top: int = 13, code: str = "G", depth: int = 2):
        return self.box(x0, top, x1, self.h - 1, code)

    def gap(self, x0: int, x1: int):
        """挖一个坑，逼玩家跳过去。"""
        for y in range(self.h):
            for x in range(x0, x1 + 1):
                self.grid[y][x] = " "
        return self

    def stairs(self, x: int, top: int = 13, steps: int = 4, up: bool = True):
        for i in range(steps):
            col = x + i
            y0 = top - i if up else top - (steps - 1 - i)
            self.box(col, y0, col, top, "D")
        return self

    def pipe(self, x: int, height: int = 2, warp: str = ""):
        """两格宽的管道；``warp`` 非空表示可进入（站上按"下"）。"""
        for y in range(13 - height, 13):
            self.grid[y][x] = "p"
            self.grid[y][x + 1] = "p"
        self.grid[13 - height][x] = "|"
        self.grid[13 - height][x + 1] = "|"
        if warp:
            # 管口可进入区域：盖住帽子上方，中心对齐两格管身
            self.objects.append(dict(t="pipe", x=x + 0.5, y=13 - height - 0.5, to=warp))
        return self

    def row(self, x0: int, x1: int, y: int, code: str = "="):
        return self.box(x0, y, x1, y, code)

    def coins(self, xs: list[int], y: int):
        for x in xs:
            self.objects.append(dict(t="coin", x=x, y=y))
        return self

    def add(self, t: str, x, y, **kw):
        self.objects.append(dict(t=t, x=x, y=y, **kw))
        return self

    def done(self, **meta):
        return dict(rows=["".join(r) for r in self.grid], objects=self.objects, **meta)


def level_1_1() -> dict:
    b = Builder(96)
    b.floor(0, 69)
    b.gap(28, 29).gap(44, 46).gap(62, 64)
    b.stairs(70, 12, 4, up=True)
    b.floor(70, 95)
    b.box(84, 9, 87, 9, "D")
    # 方块排布：! 出火花、? 出金币、B 砖、N 音符、C 多币、* 出无敌星
    b.put(16, 9, "!")
    b.put(45, 9, "*")                           # 无敌星块
    for x, y, code in ((21, 9, "B"), (22, 9, "?"), (23, 9, "B")):
        b.put(x, y, code)
    b.put(78, 9, "?").put(79, 9, "C").put(80, 9, "N")
    b.put(76, 9, "B")
    # 隐藏块（顶头显形出金币）
    b.put(35, 9, "H")
    # 管道：36 号可进隐藏房
    b.pipe(14, 2).pipe(36, 3, warp="1-1b").pipe(57, 4)
    b.row(24, 26, 6, "=")
    b.coins([21, 22, 23], 7).coins([44, 45, 46], 9).coins([30, 31, 32], 10)
    b.coins([64, 65, 66], 9)
    # 敌人
    b.add("biddybud", 33, 12).add("biddybud", 34, 12, dir=1)   # NSMBW 甲虫小队
    b.add("goomba", 24, 12).add("goomba", 27, 12)
    b.add("goomba", 42, 12).add("koopa", 40, 12, dir=-1)   # 朝远离检查点的方向巡逻
    b.add("goomba", 55, 12).add("goomba", 56, 12)
    b.add("red_koopa", 74, 12).add("piranha", 57, 9, phase=0.4)
    b.add("goomba", 90, 6)
    # 大金币 0/2（1 号在隐藏房）
    b.add("starcoin", 31, 6, idx=0)
    b.add("starcoin", 85, 5, idx=2)
    # 检查点 + 终点旗
    b.add("checkpoint", 48, 12)
    b.add("flag", 92, 9)
    return b.done(label="1-1", theme="overworld", music="overworld", time=320,
                  player=dict(x=3, y=12, form="small"),
                  spawns=dict(exit=dict(x=39, y=12)))


def level_1_1b() -> dict:
    """1-1 的隐藏房：地下金币库，音符块蹦床够大金币，管道返回。"""
    b = Builder(22)
    b.box(0, 0, 21, 2, "D")
    b.floor(0, 21, top=13, code="D")
    b.coins([4, 6, 8, 10, 12, 14, 16], 10)
    b.row(9, 13, 7, "N")                       # 音符块蹦床
    b.add("starcoin", 11, 4, idx=1, of="1-1")   # 归属 1-1 的大金币
    b.add("1up", 18, 12)                       # 房间尽头的奖励
    b.pipe(16, 2, warp="1-1@exit")             # 出口管道
    return b.done(label="1-B", theme="underground", music="underground", time=200,
                  secret=True, player=dict(x=2, y=4, form="small"))


def level_1_2() -> dict:
    """地下关：天花板压顶，中段一段墙跳竖井拿大金币。"""
    b = Builder(76)
    b.box(0, 0, 75, 2, "M")
    b.floor(0, 75, top=13, code="D")
    b.gap(20, 22)
    b.row(10, 14, 9, "=").row(30, 34, 8, "=")
    b.box(40, 6, 44, 6, "D")
    # 墙跳竖井：高台起跳跃入，井内左右弹墙上爬；大金币悬在井里
    b.box(52, 9, 57, 12, "D")              # 上井台阶（两段跳可达）
    b.row(54, 57, 5, "=")                  # 井口平台
    b.box(59, 5, 59, 12, "D")              # 左墙
    b.box(62, 6, 62, 12, "D")              # 右墙（顶面 row6，从井口平台可满跳越出）
    b.add("starcoin", 61, 8, idx=1)
    b.coins([60, 61], 11)
    b.put(10, 8, "!")                          # 火花块
    b.put(12, 6, "m")                          # 迷你蘑菇块
    b.put(56, 4, "P")                          # 螺旋桨块（井口平台上方）
    b.coins([10, 11, 12, 13, 14], 8).coins([30, 31, 32, 33, 34], 7)
    b.add("goomba", 16, 12).add("buzzy", 26, 12).add("buzzy", 27, 12)
    b.add("spiny", 46, 12, dir=1).add("red_koopa", 50, 12, dir=1)   # 背对检查点
    b.add("piranha", 36, 10, phase=0.2)
    b.add("platform", 20, 10, to=(3, 0), period=3.2)   # 跨坑移动平台
    b.add("spring", 24, 12)                    # 弹簧垫
    b.add("starcoin", 12, 6, idx=0)
    b.add("starcoin", 70, 7, idx=2)
    b.add("checkpoint", 38, 12)
    b.add("flag", 72, 9)
    return b.done(label="1-2", theme="underground", music="underground", time=300,
                  player=dict(x=2, y=12, form="small"))


def level_1_3() -> dict:
    """水关：整段泡在水里，岛屿与金属平台之间穿行。"""
    b = Builder(84)
    b.box(0, 4, 83, 4, "~")                    # 水面
    b.box(0, 5, 83, 12, "w")                   # 水体
    b.floor(0, 83, top=13, code="G")
    b.box(10, 10, 14, 12, "G")                 # 岛屿
    b.box(30, 9, 36, 12, "G")
    b.box(52, 10, 57, 12, "G")
    b.box(74, 9, 83, 12, "G")                  # 终点岛
    b.row(18, 20, 6, "M")                      # 高处的金属平台
    b.row(44, 47, 6, "M")
    b.coins([11, 12, 13], 9).coins([22, 23, 24], 7)
    b.coins([33, 34, 35], 8).coins([45, 46], 5)
    b.coins([54, 55, 56], 9).coins([62, 63, 64], 8)
    b.add("cheep", 24, 8, dir=-1)
    b.add("cheep", 42, 7, dir=1)
    b.add("cheep", 60, 9, dir=-1)
    b.add("goomba", 12, 9)                    # 岛上的敌人
    b.add("goomba", 35, 8, dir=1)             # 远离检查点（33）方向走
    b.put(32, 5, "?")
    b.put(33, 5, "!")
    b.put(55, 5, "f")   # 冰之花块
    b.put(21, 5, "Q")   # 企鹅装块（水关绝配）
    b.add("goombrat", 20, 9, dir=-1)           # NSMBW 栗子怪
    b.add("starcoin", 24, 5, idx=0)            # 水下高处
    b.add("starcoin", 48, 5, idx=1)
    b.add("starcoin", 76, 5, idx=2)
    b.add("checkpoint", 33, 8)
    b.add("flag", 80, 8)
    return b.done(label="1-3", theme="water", music="water", time=320,
                  player=dict(x=2, y=11, form="small"))


def level_castle() -> dict:
    """城堡关：尖刺、音符块、移动平台，深处 Bowser 镇守。"""
    b = Builder(68)
    b.box(0, 0, 67, 2, "M")
    b.floor(0, 67, top=13, code="D")
    b.gap(24, 27)
    b.box(24, 14, 27, 14, "S")                 # 坑底尖刺（掉进去就完）
    b.put(8, 9, "!")
    b.put(45, 8, "g")                          # 巨大蘑菇块（配合砖排拆迁）
    b.box(16, 9, 19, 9, "B")
    b.put(17, 9, "?")
    b.row(28, 30, 9, "N")                      # 音符块段
    b.box(40, 8, 43, 8, "D")
    b.put(41, 8, "C")                          # 多币块
    b.add("platform", 24, 10, to=(4, 0), period=3.6)   # 跨尖刺坑
    b.add("spiny", 20, 12).add("buzzy", 34, 12)
    b.add("spiny", 46, 12, dir=1)   # 检查点(36)在左，让它朝右走
    b.add("drybones", 30, 12, dir=1)           # 骷髅龟：踩散会复活
    b.add("grrrol", 34, 12, dir=1)             # 滚石球：无敌路障
    b.add("goomba", 12, 12).add("goomba", 13, 12)
    b.add("bowser", 58, 12)                    # Boss
    b.add("checkpoint", 36, 12)
    b.add("starcoin", 16, 4, idx=0)
    b.add("starcoin", 41, 5, idx=1)
    b.add("starcoin", 62, 4, idx=2)
    b.add("flag", 64, 9)                      # 备用终点（Boss 被击破也算过关）
    return b.done(label="1-Castle", theme="castle", music="castle", time=300,
                  player=dict(x=2, y=12, form="super"))


LEVELS = {"1-1": level_1_1(), "1-2": level_1_2(), "1-3": level_1_3(),
          "1-castle": level_castle(), "1-1b": level_1_1b()}
