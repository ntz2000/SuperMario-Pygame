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


def atlas_asset(id: str, res_scale: int):
    """从图集裁剪一个资产。返回 [(surface, ...frames)] 或 None（id 不在图集）。"""
    entry = ATLAS.get(id)
    if not entry:
        return None
    sheet = sheet_surface(entry["sheet"])
    frames = []
    for x, y, w, h in entry["rects"]:
        cell = sheet.subsurface(pygame.Rect(x, y, w, h))
        if res_scale != 1:
            cell = pygame.transform.scale(cell, (w * res_scale, h * res_scale))
        frames.append(cell)
    return frames
