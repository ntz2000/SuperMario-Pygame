"""真实素材图集（atlas）：asset id → 精灵图上的裁剪矩形。

下载的 NSMB 官方 sheet 放在 ``mario/assets/sheets/``；本模块在
``Assets.sprite`` 之前拦截：id 命中图集就用真实贴图（16px 原生瓦片按
RES_SCALE 最近邻放大），否则回落到程序化生成器——两张路径共用同一套 id。

语义坐标是通过颜色签名分析锁定的（见 docs/ASSETS.md）：
- Grassland 行 7-8：草帽黄土地面 / 行 13：草柱
- Jyotyu：问号块 / 砖 / 灰石
"""
from __future__ import annotations

import json
import os

import pygame

_SHEETS = os.path.dirname(os.path.abspath(__file__)) + "/sheets"
_ATLAS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "atlas.json")


def _load_atlas() -> dict:
    try:
        with open(_ATLAS_PATH) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


ATLAS = _load_atlas()

_sheet_cache: dict[str, pygame.Surface] = {}


def sheet_surface(name: str) -> pygame.Surface:
    """载入并缓存精灵图（PNG/GIF 都支持，统一转 RGBA）。"""
    if name not in _sheet_cache:
        from PIL import Image
        import io
        path = os.path.join(_SHEETS, name)
        im = Image.open(path).convert("RGBA")
        raw = im.tobytes()
        surf = pygame.image.frombuffer(raw, im.size, "RGBA")
        _sheet_cache[name] = surf
    return _sheet_cache[name]


# 调色板交换定义（NSMB 原版 fire/ice 就是调色板交换，不是独立美术）
_REMAPS = {
    "fire": {  # 红(180,0,0)→白, 蓝背带(12,60,159)→红：经典火马里奥
        (180, 0, 1): (242, 242, 242),
        (1, 1, 1): None,
    },
    "ice": {   # 红→淡蓝, 蓝背带→深蓝：冰马里奥
        (180, 0, 1): (150, 200, 255),
        (12, 60, 159): (30, 80, 200),
    },
}


def remap_frame(surf, form: str):
    """把真实帧的红色域换成 fire/ice 配色（返回新 Surface）。"""
    import numpy as _np
    arr = _np.frombuffer(pygame.image.tobytes(surf, "RGBA"), dtype="uint8").copy()
    arr = arr.reshape(surf.get_height(), surf.get_width(), 4).astype(int)
    red = (arr[..., 0] > 110) & (arr[..., 0] > arr[..., 1] + 40) & (arr[..., 0] > arr[..., 2] + 40)
    blue = (arr[..., 2] > 110) & (arr[..., 2] > arr[..., 0] + 30)
    if form == "fire":
        arr[red, 0], arr[red, 1], arr[red, 2] = 242, 242, 242   # 红衣→白
        arr[blue, 0], arr[blue, 1], arr[blue, 2] = 224, 34, 34   # 蓝背带→红
    elif form == "ice":
        arr[red, 0], arr[red, 1], arr[red, 2] = 140, 195, 255    # 红衣→冰蓝
        arr[blue, 0], arr[blue, 1], arr[blue, 2] = 20, 90, 180   # 背带→深蓝
    return pygame.image.frombuffer(arr.astype("uint8").tobytes(),
                                   surf.get_size(), "RGBA")


def atlas_asset(id: str, res_scale: int):
    """从图集裁剪一个资产。返回 [surface, ...] 或 None（id 不在图集）。

    id 支持 "hero.fire.walk" 这类派生形式：fire/ice 是 super 的调色板换色
    （NSMB 原版同款做法），命中 "hero.super.<anim>" 条目后按 form 重着色。

    条目可带 ``fit_h``（逻辑像素目标高度）：真实帧缩放到贴合碰撞盒，
    避免贴图大面积超出碰撞盒导致视觉穿模（历史 bug：super 贴图 66px vs
    碰撞盒 44px，头穿天花板）。
    """
    entry = ATLAS.get(id)
    remap = ""
    if not entry:
        parts = id.split(".")          # hero.<form>.<anim>
        if len(parts) == 3 and parts[1] in ("fire", "ice"):
            entry = ATLAS.get(f"hero.super.{parts[2]}")
            remap = parts[1]
        if not entry:
            return None
    sheet = sheet_surface(entry["sheet"])
    frames = []
    for x, y, w, h in entry["rects"]:
        cell = sheet.subsurface(pygame.Rect(x, y, w, h))
        if remap:
            cell = remap_frame(cell, remap)
        if res_scale != 1:
            cell = pygame.transform.scale(cell, (w * res_scale, h * res_scale))
        frames.append(cell)
    # 缩放到目标逻辑高度（乘 res_scale 后的目标渲染高度）
    fit_h = entry.get("fit_h")
    if fit_h and frames:
        target = fit_h * res_scale
        cur = frames[0].get_height()
        if abs(cur - target) > 1:
            k = target / cur
            frames = [pygame.transform.scale(
                f, (max(1, round(f.get_width() * k)), target)) for f in frames]
    return frames
