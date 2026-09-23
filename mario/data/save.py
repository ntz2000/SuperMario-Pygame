"""进度存档：done/stars 两项落盘为 JSON（写在游戏根目录 save.json）。

关卡内容本身由代码生成，存档只记"打到哪了"和"大金币收了哪几枚"。
写入用临时文件 + 原子替换，中断不会留下半截存档。
"""
from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAVE_PATH = os.path.join(_ROOT, "save.json")


def load() -> dict:
    """读档；损坏或不存在时返回空进度。"""
    try:
        with open(SAVE_PATH) as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return {"done": list(data.get("done", [])),
                    "stars": {k: dict(v) for k, v in data.get("stars", {}).items()}}
    except (OSError, ValueError):
        pass
    return {"done": [], "stars": {}}


def save(progress: dict):
    slim = {"done": progress.get("done", []),
            "stars": {k: dict(v) for k, v in progress.get("stars", {}).items()}}
    tmp = SAVE_PATH + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(slim, fh, indent=1)
    os.replace(tmp, SAVE_PATH)


def clear():
    try:
        os.remove(SAVE_PATH)
    except OSError:
        pass
