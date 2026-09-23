"""测试环境：SDL 无头驱动 + 音频禁用 + 公共 fixtures。"""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402
import pytest  # noqa: E402

import mario.art  # noqa: E402,F401  触发全部资源生成器注册


@pytest.fixture(scope="session", autouse=True)
def _sdl():
    pygame.init()
    try:
        pygame.mixer.init(44100, -16, 2, 512)
    except pygame.error:
        pass
    yield


@pytest.fixture()
def app():
    """无头 App + 虚拟输入，测试用它驱动关卡场景。"""
    from mario.data.levels import LEVELS
    from mario.engine.app import App
    from mario.engine.input import VirtualInput

    a = App(title="test", base=(320, 180), scale=1, headless=True,
            input=VirtualInput())
    a.progress = {"levels": LEVELS, "done": []}
    return a


@pytest.fixture()
def level(app):
    """进入 1-1 的关卡场景。"""
    from mario.data.levels import LEVELS
    from mario.scenes.level import LevelScene

    scene = LevelScene(app, LEVELS["1-1"])
    scene.on_enter(id="1-1")
    return scene


def run(scene, frames: int):
    """手动推进 N 个模拟帧。"""
    for _ in range(frames):
        scene.update()
        scene.input.advance()
