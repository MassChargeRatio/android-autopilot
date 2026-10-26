# -*- coding: utf-8 -*-
"""test_anti_detection.py - F2 反检测增强单测（AUTOP-FEAT-2026-10-20）

覆盖卡规 F2.3：
  1. seed 固定 -> 误触发生序列可复现（含误触点坐标）；
  2. 限流长停触发条件命中/不命中；
  3. 验证码冷却生效（含未启用/零值时不冷却）；
  4. 不破坏既有 human 测试（test_human_seed 基线先跑过，全绿）。

运行：
    python -m pytest tests/test_anti_detection.py -q
    python tests/test_anti_detection.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import human as human_mod  # noqa: E402
from human import Human  # noqa: E402


class _D:
    """假设备：window_size 回 plain tuple（真机实测形态），click 全记录。"""

    def __init__(self, ws=(1080, 2340)):
        self._ws = ws
        self.clicks = []

    def window_size(self):
        return self._ws

    def click(self, x, y):
        self.clicks.append((x, y))


def _human(anti=None, seed=42):
    return Human({"human": {}, "anti_detection": anti or {}}, seed=seed)


class _SleepSpy:
    """把 human 模块内的 time.sleep 换成记录器（用完还原）。"""

    def __init__(self):
        self.durations = []
        self._orig = None

    def __enter__(self):
        self._orig = human_mod.time.sleep
        human_mod.time.sleep = lambda s: self.durations.append(s)
        return self

    def __exit__(self, *a):
        human_mod.time.sleep = self._orig
        return False


def t_seed_reproducible_mistakes():
    """同 seed 的两个 Human：误触序列（含错点坐标）逐帧一致。"""
    a, b = _human({"mistake_prob": 0.5}, seed=20261021), \
           _human({"mistake_prob": 0.5}, seed=20261021)
    da, db = _D(), _D()
    # tap 内含限流长停（默认每 12 次睡 14-26s）——测试必须 spy sleep，
    # 否则 40 次循环要跑几分钟（2026-10-21 首版即因此挂死被 timeout 杀）。
    with _SleepSpy():
        for i in range(40):
            a.tap(da, 500 + i, 1200)
            b.tap(db, 500 + i, 1200)
    assert da.clicks == db.clicks, "同 seed 点击序列必须一致（含误触）"
    # 至少发生过误触（双跳：错点+正点），否则本用例没测到东西
    doubles = sum(1 for i in range(0, len(da.clicks) - 1, 2)
                  if da.clicks[i] != da.clicks[i + 1])
    assert doubles > 0, "mistake_prob=0.5 下 40 次应出现误触"
    print("t_seed_reproducible_mistakes OK（误触 %d 次）" % doubles)


def t_mistake_prob_zero_no_mistake():
    """mistake_prob=0：永不误触，每次 tap 恰好一次 click。"""
    h = _human({"mistake_prob": 0.0}, seed=7)
    d = _D()
    with _SleepSpy():
        for i in range(30):
            h.tap(d, 300, 900)
    assert len(d.clicks) == 30, d.clicks
    assert all(c == (300, 900) for c in d.clicks)
    print("t_mistake_prob_zero_no_mistake OK")


def t_mistake_offset_bounded():
    """误触点约束：±160px 内且不出屏（防真点歪改页面）。"""
    h = _human({"mistake_prob": 1.0}, seed=9)
    d = _D()
    with _SleepSpy():
        for i in range(30):
            h.tap(d, 540, 1170)
    assert len(d.clicks) == 60          # 每次都误触+正点
    for j in range(0, 60, 2):
        mx, my = d.clicks[j]
        assert 8 <= mx <= 1080 - 8 and 8 <= my <= 2340 - 8, (mx, my)
        assert abs(mx - 540) <= 160 and abs(my - 1170) <= 160, (mx, my)
    print("t_mistake_offset_bounded OK")


def t_cooldown_triggers_at_threshold():
    """限流：每 cooldown_every 次点击触发一次长停，时长在 0.7~1.3 倍区间。"""
    h = _human({"cooldown_every": 3, "cooldown_seconds": 10}, seed=11)
    d = _D()
    with _SleepSpy() as spy:
        for i in range(9):
            h.tap(d, 100, 100)
    long_sleeps = [s for s in spy.durations if s >= 7.0]
    assert len(long_sleeps) == 3, (spy.durations, "9 次点击/每3次=3 次长停")
    assert all(7.0 <= s <= 13.0 for s in long_sleeps), long_sleeps
    print("t_cooldown_triggers_at_threshold OK")


def t_cooldown_not_before_threshold():
    """未到阈值不长停（短延迟不算长停）。"""
    h = _human({"cooldown_every": 5, "cooldown_seconds": 20}, seed=13)
    d = _D()
    with _SleepSpy() as spy:
        for i in range(4):
            h.tap(d, 100, 100)
    assert not [s for s in spy.durations if s >= 14.0], spy.durations
    print("t_cooldown_not_before_threshold OK")


def t_captcha_cooldown_effective():
    """验证码冷却：默认 300s（0.8~1.2 抖动）；禁用/零值返回 0 不冷却。"""
    h = _human({}, seed=17)                     # 缺省即 300
    with _SleepSpy() as spy:
        sec = h.captcha_cooldown()
    assert 240.0 <= sec <= 360.0, sec
    assert spy.durations and spy.durations[-1] == sec
    off = _human({"enabled": False}, seed=17)
    assert off.captcha_cooldown() == 0.0
    zero = _human({"cooldown_on_captcha": 0}, seed=17)
    assert zero.captcha_cooldown() == 0.0
    print("t_captcha_cooldown_effective OK")


def t_anti_disabled_no_effects():
    """anti_detection.enabled=false：无误触、无限流、无冷却（老行为零影响）。"""
    h = _human({"enabled": False, "mistake_prob": 1.0,
                "cooldown_every": 1, "cooldown_seconds": 50}, seed=19)
    d = _D()
    with _SleepSpy() as spy:
        for i in range(6):
            h.tap(d, 100, 100)
        assert h.captcha_cooldown() == 0.0
    assert len(d.clicks) == 6, d.clicks       # 无误触双跳
    assert not [s for s in spy.durations if s >= 35.0], spy.durations
    print("t_anti_disabled_no_effects OK")


def t_wander_probability_override():
    """anti_detection.wander_probability 覆盖 human 段同名值。"""
    h = Human({"human": {"wander_probability": 0.06},
               "anti_detection": {"wander_probability": 0.25}}, seed=23)
    assert abs(h.wander_prob - 0.25) < 1e-9
    # 缺省回落 human 段
    h2 = Human({"human": {"wander_probability": 0.06},
                "anti_detection": {}}, seed=23)
    assert abs(h2.wander_prob - 0.06) < 1e-9
    # 两段都缺省 -> 0.10（F2 默认）
    h3 = Human({"human": {}, "anti_detection": {}}, seed=23)
    assert abs(h3.wander_prob - 0.10) < 1e-9
    print("t_wander_probability_override OK")


def t_defaults_match_card():
    """默认值与派单卡 F2.2 配置段一致。"""
    h = _human({}, seed=29)
    assert abs(h.mistake_prob - 0.05) < 1e-9
    assert h.cooldown_every == 12
    assert abs(h.cooldown_seconds - 20) < 1e-9
    assert abs(h.cooldown_on_captcha - 300) < 1e-9
    assert h._anti_enabled is True
    print("t_defaults_match_card OK")


if __name__ == "__main__":
    t_seed_reproducible_mistakes()
    t_mistake_prob_zero_no_mistake()
    t_mistake_offset_bounded()
    t_cooldown_triggers_at_threshold()
    t_cooldown_not_before_threshold()
    t_captcha_cooldown_effective()
    t_anti_disabled_no_effects()
    t_wander_probability_override()
    t_defaults_match_card()
    print("ALL anti_detection TESTS PASSED")
