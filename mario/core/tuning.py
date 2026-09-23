"""Tweakable feel numbers, all in one place.

Units are art pixels per frame and per frame squared, at a fixed 60 Hz sim step. A jump
that reaches ``h`` pixels needs ``v = sqrt(2 g h)``, so the pairs below are always read
together: gravity 0.38 with a 5.05 launch peaks at ~34 px (just over two tiles) and the
hold-to-jump-higher window covers the rest.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tuning:
    # --- world -----------------------------------------------------------------------
    # NSMB 手感：按住跳满跳约 4.5 格（72px），轻点约 2 格，下落比上升重。
    gravity: float = 0.50
    gravity_rise: float = 0.76    # 按住跳跃上升时减轻的重力
    gravity_fall: float = 1.25     # 更重的下落，经典的"吸地"感
    gravity_release: float = 0.62   # 提前松开跳跃的额外削减
    max_fall: float = 7.0
    # --- ground movement ---------------------------------------------------------------
    # 手感基准：SMB/NSMB 的地面加速度约 0.036~0.05 px/f²，比"一按就窜出去"的
    # 0.11+ 沉得多；空中转向能力被压到 1/3，跳跃弧线因此"有承诺感"而不飘。
    walk_max: float = 1.30
    run_max: float = 2.06
    accel_walk: float = 0.048
    accel_run: float = 0.075
    decel: float = 0.10
    skid_decel: float = 0.26
    air_control: float = 0.30
    # --- jump --------------------------------------------------------------------------
    jump_vel: float = 7.4
    coyote: int = 6                # 离开平台后的宽限帧数
    jump_buffer: int = 7           # 按键预输入缓冲帧数
    wall_slide_speed: float = 1.35  # 贴墙下滑的落速上限（墙跳的前提）
    wall_jump_push: float = 2.05
    note_bounce: float = 8.0       # 音符块弹床
    pound_bounce: float = 8.8       # 下砸踩中音符块的额外高度
    # --- forms -------------------------------------------------------------------------
    small_h: int = 14
    super_h: int = 22
    mini_h: int = 10
    mega_h: int = 26
    stomp_bounce: float = 5.2      # 踩踏反弹（约 2 格，够从龟壳上跳开不被误踢）
    # 踩踏连击分值表（NSMB 经典 100→8000→1UP）
    combo: tuple = (100, 200, 400, 500, 800, 1000, 2000, 4000, 8000)


TUNE = Tuning()
