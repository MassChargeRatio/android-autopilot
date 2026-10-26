# -*- coding: utf-8 -*-
"""test_human_seed.py - A5 human 随机配置化（seed 可复现、reseed、lognormal 配置）

运行：
    python -m pytest tests/test_human_seed.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from human import Human  # noqa: E402


def _human(cfg=None, seed=None):
    return Human({"human": cfg or {}, "trajectory": None}, seed=seed)


def _seq(h, n=50):
    return [h._rand(0.5, 2.5, lognormal=True) for _ in range(n)]


def test_same_seed_same_sequence():
    """同 seed 的两个 Human 产生完全一致的随机序列。"""
    a, b = _human(seed=20261019), _human(seed=20261019)
    sa, sb = _seq(a), _seq(b)
    assert sa == sb, "同 seed 序列必须一致"
    print("OK  同 seed 序列一致")


def test_diff_seed_diff_sequence():
    """异 seed 的序列不同（随机源隔离）。"""
    a, b = _human(seed=1), _human(seed=2)
    sa, sb = _seq(a), _seq(b)
    assert sa != sb, "异 seed 序列不应相同"
    print("OK  异 seed 序列不同")


def test_reseed_resets_sequence():
    """reseed 后用同 seed 重现与初始构造一致的序列。"""
    h = _human(seed=777)
    first = _seq(h)
    _ = _seq(h)                       # 推进若干步，丢掉原状态
    h.reseed(777)
    again = _seq(h)
    assert again == first, "reseed 同 seed 应复现初始序列"
    print("OK  reseed 重置后复现初始序列")


def test_lognormal_config_effective():
    """lognormal 配置项生效：mu_ratio / sigma_range 被实例读取。"""
    h = _human({"lognormal": {"mu_ratio": 0.30,
                              "sigma_range": [0.20, 0.50]}})
    assert abs(h.mu_ratio - 0.30) < 1e-9
    assert abs(h.sigma_lo - 0.20) < 1e-9
    assert abs(h.sigma_hi - 0.50) < 1e-9
    # 自定义参数下采样仍 clamp 在区间内
    lo, hi = 0.5, 2.5
    for _ in range(300):
        v = h._rand(lo, hi, lognormal=True)
        assert lo <= v <= hi, v
    print("OK  lognormal 配置生效且采样仍 clamp 在区间内")


def test_default_lognormal_equiv():
    """默认参数与旧硬编码等价：mu_ratio=0.18、sigma_range=[0.45,0.75]。"""
    h = _human()
    assert abs(h.mu_ratio - 0.18) < 1e-9
    assert abs(h.sigma_lo - 0.45) < 1e-9
    assert abs(h.sigma_hi - 0.75) < 1e-9
    print("OK  默认 lognormal 参数与旧硬编码等价")
