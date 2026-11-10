# -*- coding: utf-8 -*-
"""test_human_engine_bridge.py - touch-humanization 接入层（可选引擎）回归。

覆盖：
  * 默认 legacy：`_engine is None`，行为零变化；
  * 启用开关：`human.engine: touch_humanization` 时挂载引擎；
  * 同 seed 可复现（时序 + 轨迹）；
  * 轨迹返回契约（intervals 首位 0.0、端点精确）；
  * 作息窗口与 legacy 一致。
未安装 touch-humanization 时自动 skip（允许无库环境跑全量）。
"""
import copy
import time

import pytest

import human_engine
from human import Human

CFG = {
    "human": {
        "enabled": True,
        "use_lognormal": True,
        "lognormal": {"mu_ratio": 0.18, "sigma_range": [0.45, 0.75]},
        "delay_between_actions": [0.6, 2.2],
        "delay_after_open": [3.0, 6.0],
        "think_delay": [1.5, 4.0],
        "run_jitter_seconds": [0, 600],
        "wake_window": {"start": "07:30", "end": "23:00"},
        "tap_jitter_px": 12,
    },
    "trajectory": {"enabled": True, "steps_min": 20, "steps_max": 60,
                   "px_per_step": 15},
    "anti_detection": {"enabled": True, "cooldown_every": 12,
                       "cooldown_seconds": 20, "cooldown_on_captcha": 300},
}

needs_lib = pytest.mark.skipif(not human_engine.available(),
                               reason="touch-humanization 未安装")


def _cfg_engine():
    c = copy.deepcopy(CFG)
    c["human"]["engine"] = "touch_humanization"
    return c


def test_default_is_legacy():
    h = Human(CFG, seed=1)
    assert h._engine is None
    assert h_engine_off(h)


def h_engine_off(h):
    return isinstance(getattr(h, "_engine", None), type(None))


def test_is_enabled_flag_parsing():
    assert human_engine.is_enabled(CFG) is False
    for v in ("touch_humanization", "touch-humanization", "V6", " TH "):
        assert human_engine.is_enabled({"human": {"engine": v}}) is True
    assert human_engine.is_enabled({"human": {"engine": "legacy"}}) is False
    assert human_engine.is_enabled({}) is False


@needs_lib
def test_engine_mounted_and_reproducible_timing():
    h1 = Human(_cfg_engine(), seed=3)
    h2 = Human(_cfg_engine(), seed=3)
    assert h1._engine is not None
    a = [h1._rand(0.6, 2.2) for _ in range(5)]
    b = [h2._rand(0.6, 2.2) for _ in range(5)]
    assert a == b
    for _ in range(200):
        assert 0.6 <= h1._rand(0.6, 2.2) <= 2.2


@needs_lib
def test_engine_trajectory_contract():
    h = Human(_cfg_engine(), seed=4)
    pts, ivs = h.trajectory.generate_gesture((100, 1800), (900, 400))
    assert len(pts) >= 2
    assert pts[-1] == (900, 400)
    assert len(ivs) == len(pts)          # 旧契约：intervals 首位补 0.0
    assert ivs[0] == 0.0
    assert sum(ivs) > 0


@needs_lib
def test_engine_trajectory_reproducible():
    h1 = Human(_cfg_engine(), seed=9)
    h2 = Human(_cfg_engine(), seed=9)
    assert (h1.trajectory.generate_gesture((0, 0), (400, 400)) ==
            h2.trajectory.generate_gesture((0, 0), (400, 400)))


@needs_lib
def test_wake_window_parity_with_legacy():
    legacy = Human(CFG, seed=0)
    eng = Human(_cfg_engine(), seed=0)
    for hh in (0, 8, 12, 22, 23):
        ts = time.mktime((2026, 11, 10, hh, 0, 0, 0, 0, -1))
        assert legacy.in_wake_window(ts) == eng.in_wake_window(ts), hh


@needs_lib
def test_legacy_path_unchanged_when_disabled():
    """legacy 分支的采样与旧实现同算法（同 seed 同序列）。"""
    a = Human(CFG, seed=11)
    b = Human(CFG, seed=11)
    assert [a._rand(0.6, 2.2) for _ in range(10)] == \
           [b._rand(0.6, 2.2) for _ in range(10)]
