# -*- coding: utf-8 -*-
"""human_engine.py - touch-humanization 适配层（可选引擎，默认关闭）

背景
----
本项目原 `human.py` / `human_trajectory.py` 的时序与轨迹算法已提炼为独立库
`touch-humanization`（MIT），其 `Timing.sample` 与本项目 `Human._rand` 的
均值校正公式完全一致；`Kinematics.generate` 与 `HumanTrajectory.generate_gesture`
同为「三次贝塞尔 + Fitts 步数 + smoothstep 速度轮廓 + 末段微颤 + 过冲回拉」。

差异（也是接入收益）
--------------------
* 原 `human_trajectory.py` 的 `_control_points` / `_gauss` 使用**全局 random**，
  无法按 seed 复现、会污染全局随机；新库全部走实例级 `Random`。
* 新库单一随机流贯穿 timing / kinematics / sensors（`Humanizer.rng`）。

启用方式（config.yaml）
-----------------------
    human:
      engine: touch_humanization     # legacy（默认） | touch_humanization

接入范围（严格限定，避免影响点击语义）
--------------------------------------
* 委托：时序采样（`_rand`）、启动等待、作息窗口、轨迹生成。
* 不委托：点击抖动 `jitter_point`、误触 `tap` 的坐标逻辑、分心 `maybe_wander`、
  自然退场 `close_naturally`、`inject_touch` / `natural_swipe_points` 的注入细节
  （新库不覆盖这些能力）。
"""
from __future__ import annotations

import sys

__all__ = ["available", "is_enabled", "build_engine", "TouchEngine",
           "EngineTrajectory"]

try:  # 允许未安装时优雅降级（pip install -e ../touch-humanization）
    from touch_humanization import Humanizer
    _IMPORT_ERR = None
except Exception as _e:  # noqa: BLE001
    Humanizer = None
    _IMPORT_ERR = _e

_ENGINE_ALIASES = {"touch_humanization", "touch-humanization", "v6", "th"}


def available() -> bool:
    return Humanizer is not None


def is_enabled(cfg: dict | None) -> bool:
    """是否启用新引擎（human.engine / 顶层 engine）。"""
    cfg = cfg or {}
    h = cfg.get("human") or {}
    val = h.get("engine", cfg.get("engine", "legacy"))
    return str(val or "").strip().lower() in _ENGINE_ALIASES


def _as_range(v, default):
    if isinstance(v, dict):
        v = v.get("range") or v.get("lo_hi")
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return [float(v[0]), float(v[1])]
    return list(default)


def build_hcfg(cfg: dict | None) -> dict:
    """把本项目 config 映射为 touch-humanization 的配置结构。"""
    cfg = cfg or {}
    h = cfg.get("human") or {}
    ad = cfg.get("anti_detection") or {}
    ln = h.get("lognormal") or {}
    traj = cfg.get("trajectory") or {}
    return {
        "kinematics": dict(traj),
        "timing": {
            "mu_ratio": float(ln.get("mu_ratio", 0.18)),
            "sigma_range": _as_range(ln.get("sigma_range", [0.45, 0.75]),
                                     (0.45, 0.75)),
            "delay_between_actions": _as_range(
                h.get("delay_between_actions", [0.6, 2.2]), (0.6, 2.2)),
            "delay_after_open": _as_range(
                h.get("delay_after_open", [3.0, 6.0]), (3.0, 6.0)),
            "think_delay": _as_range(h.get("think_delay", [1.5, 4.0]),
                                     (1.5, 4.0)),
            "start_jitter": _as_range(h.get("run_jitter_seconds", [0, 600]),
                                      (0, 600)),
            "wake_window": h.get("wake_window") or {"start": "07:30",
                                                    "end": "23:00"},
            "cooldown_every": int(ad.get("cooldown_every", 12)),
            "cooldown_seconds": float(ad.get("cooldown_seconds", 20)),
            "cooldown_on_captcha": float(ad.get("cooldown_on_captcha", 300)),
        },
        "sensors": dict(cfg.get("sensor") or {}),
    }


class TouchEngine:
    """把 Humanizer 适配成 Human / HumanTrajectory 需要的调用形态。"""

    def __init__(self, cfg: dict | None = None, seed=None):
        if Humanizer is None:
            raise RuntimeError(f"touch_humanization 不可用: {_IMPORT_ERR}")
        self.cfg = cfg or {}
        self.h = Humanizer(build_hcfg(self.cfg), seed=seed)

    @property
    def rng(self):
        return self.h.rng

    # ---- 时序（与原 Human._rand 同算法） ----
    def sample(self, lo, hi, lognormal=True) -> float:
        return self.h.timing.sample(lo, hi, lognormal=lognormal)

    def start_wait(self) -> float:
        return self.h.timing.start_wait()

    def in_wake_window(self, now=None) -> bool:
        return self.h.timing.in_wake_window(now)

    def captcha_cooldown(self) -> float:
        return self.h.timing.captcha_cooldown()

    # ---- 轨迹（返回旧接口：intervals 首位补 0.0） ----
    def generate_gesture(self, start, end, for_slider=False, exact_end=True):
        g = self.h.kinematics.generate(start, end, for_slider=for_slider,
                                       exact_end=exact_end)
        return [tuple(p) for p in g.points], [0.0] + list(g.intervals)

    # ---- 传感器（可选能力，供后续接入） ----
    def sensor_rows(self, mode=None, fs=None, duration=None):
        return self.h.sensors.generate(mode=mode, fs=fs, duration=duration)

    def sensor_is_dead(self, rows) -> bool:
        return self.h.sensors.is_dead(rows)


class EngineTrajectory:
    """`HumanTrajectory` 的等价替身：仅把轨迹生成切到新引擎，注入/滑动沿用父类。

    注意：这里**不继承** HumanTrajectory，而是持有其实例，避免循环导入与
    MRO 复杂化；外部只用到 `generate_gesture` / `inject_touch` /
    `natural_swipe_points` 三个方法，全部按原签名透传。
    """

    def __init__(self, engine: TouchEngine, cfg: dict | None = None):
        from human_trajectory import HumanTrajectory
        self._engine = engine
        self._legacy = HumanTrajectory(cfg)
        self.enabled = self._legacy.enabled

    def generate_gesture(self, start, end, for_slider=False, exact_end=True):
        return self._engine.generate_gesture(start, end, for_slider=for_slider,
                                             exact_end=exact_end)

    def inject_touch(self, *args, **kwargs):
        return self._legacy.inject_touch(*args, **kwargs)

    def natural_swipe_points(self, *args, **kwargs):
        # 父类内部调用 self.generate_gesture；此处显式改用引擎版本，保证
        # 注入仍走父类实现、轨迹点来自新引擎。
        d, start, end, duration_fixed = _unpack_args(args, kwargs)
        if d is None:
            return None, None
        wh = self._legacy_win_wh(d)
        if not wh:
            return None, None
        w, h = wh
        import random as _random
        if start is None:
            sx = int(w * _random.uniform(0.35, 0.65))
            sy = int(h * _random.uniform(0.55, 0.75))
        else:
            sx, sy = start
        if end is None:
            ex = sx + int(w * _random.uniform(-0.08, 0.08))
            ey = int(h * _random.uniform(0.15, 0.38))
        else:
            ex, ey = end
        points, intervals = self.generate_gesture((sx, sy), (ex, ey))
        self._legacy.inject_touch(d, points, intervals)
        return points, intervals

    @staticmethod
    def _legacy_win_wh(d):
        try:
            from human_trajectory import _win_wh
            return _win_wh(d)
        except Exception:
            return None


def _unpack_args(args, kwargs):
    d = kwargs.get("d", args[0] if len(args) > 0 else None)
    start = kwargs.get("start", args[1] if len(args) > 1 else None)
    end = kwargs.get("end", args[2] if len(args) > 2 else None)
    dur = kwargs.get("duration_fixed", args[3] if len(args) > 3 else None)
    return d, start, end, dur


def build_engine(cfg: dict | None = None, seed=None) -> TouchEngine:
    return TouchEngine(cfg, seed=seed)
