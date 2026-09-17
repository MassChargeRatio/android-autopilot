# -*- coding: utf-8 -*-
"""
tests/test_diversify_sensor.py - 行为序列多样化 / 随机分布升级 / 传感器模拟 / IP 助手

运行：python -m tests.test_diversify_sensor（从项目根目录运行）
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from human import Human
from sensor_sim import SensorProfile, stats, is_dead, self_check

import executor as executor_mod


class _Recorder:
    def log(self, *a, **k):
        pass


def _human(human_cfg=None):
    """Human 入参需顶层含 human 节。"""
    return Human({"human": human_cfg or {}, "trajectory": None})


def _make_executor(human, cfg):
    rec = _Recorder()
    return executor_mod.Executor(None, human, rec, dry_run=True, config=cfg)


# ---------- 随机分布升级（对数正态） ----------
def test_lognormal_in_range_and_clamped():
    human = _human()  # 默认 use_lognormal=True
    lo, hi = human.delay_between
    for _ in range(500):
        v = human._sample(human.delay_between, human.delay_between_ln)
        assert lo <= v <= hi, f"采样越界: {v}"
    print("[lognormal] 500 次采样全部落在区间内")


def test_lognormal_right_skewed():
    """对数正态应偏态：大部分值贴近低端（人类间隔多数短、偶尔长）。"""
    human = _human()
    vals = [human._sample(human.delay_between, True) for _ in range(2000)]
    lo, hi = human.delay_between
    mid = (lo + hi) / 2
    below = sum(1 for v in vals if v < mid)
    ratio = below / len(vals)
    assert ratio > 0.55, f"期望偏态(低端更多)，实际 low 占比 {ratio:.3f}"
    assert max(vals) <= hi and min(vals) >= lo
    print(f"[lognormal] 偏态检查: 低于中值占比={ratio:.3f}")


def test_uniform_fallback():
    human = _human({"delay_between_actions":
                    {"range": [0.5, 1.5], "dist": "uniform"}})
    assert human.delay_between_ln is False, "显式 uniform 应关闭对数正态"
    vals = [human._sample(human.delay_between, False) for _ in range(1000)]
    assert max(vals) <= 1.5 and min(vals) >= 0.5
    print("[uniform] 显式 uniform 生效")


def test_parse_delay_dict():
    lo, hi = Human._parse_delay({"range": [1.0, 3.0], "dist": "uniform"})[0]
    assert (lo, hi) == (1.0, 3.0)
    lo, hi = Human._parse_delay([0.2, 0.9])[0]
    assert (lo, hi) == (0.2, 0.9)
    print("[parse_delay] dict/list 两种写法解析一致")


# ---------- 行为序列多样化（候选模板 + random 分支） ----------
def test_pick_variant_single_template_passthrough():
    human = _human()
    ex = _make_executor(human, {"diversify": {"variant_prob": 0.5}})
    single = [{"type": "wait", "seconds": 1}]
    assert ex._pick_variant(single, "app", "sign") is single
    print("[variant] 单模板原样透传")


def test_pick_variant_multi_avoid_repeat():
    human = _human()
    ex = _make_executor(human, {"diversify": {"variant_prob": 1.0}})
    choices = [[{"type": "wait", "seconds": 1}],
               [{"type": "wait", "seconds": 2}],
               [{"type": "wait", "seconds": 3}]]
    first = ex._pick_variant(choices, "app", "a")
    idx0 = ex._variant_last["a"]
    second = ex._pick_variant(choices, "app", "a")
    assert ex._variant_last["a"] != idx0, "应避免连续使用同一模板"
    assert any(second == c for c in choices), "返回值必须来自候选集"
    print("[variant] 多候选命中且避开上次")


def test_step_random_dispatch():
    """random 分支原语：随机选中且正确分发（dry-run，无设备，不失手）。"""
    human = _human()
    ex = _make_executor(human, {})
    for _ in range(60):
        ex._dispatch({
            "type": "random",
            "choices": [{"type": "wait", "seconds": 0},
                        [{"type": "back"}, {"type": "wait", "seconds": 0}],
                        {"type": "think"}],
        }, "app", ritual=False)
    print("[random] 60 次 random 分支分发无异常")


def test_pick_variant_last_key_update():
    human = _human()
    ex = _make_executor(human, {"diversify": {"variant_prob": 1.0}})
    choices = [[{"type": "wait", "seconds": 1}], [{"type": "wait", "seconds": 2}]]
    ex._pick_variant(choices, "app", "s")
    assert "s" in ex._variant_last, "应记录上次用过的模板"
    print("[variant] 最近使用记录已写入")


# ---------- 传感器模拟与死寂检测 ----------
def test_sensor_alive_all_modes():
    alive, res = self_check()
    assert alive, f"生成器不应退化成死寂: {res}"
    print("[sensor] 4 个模式数据均判为'活着':", res)


def test_sensor_dead_detection():
    dead = [dict(t=i * 0.01, acc=[0.0, 0.0, 9.8], lin=[0, 0, 0],
                 gyro=[0.0, 0.0, 0.0], mag=[0.0, 0.0, 0.0]) for i in range(300)]
    assert is_dead(dead), "全死寂数据应被识别"
    print("[sensor] 死寂数据被识别")


def test_sensor_csv_export():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "p.csv")
        p = SensorProfile(fs=50, duration=1.0, mode="resting", seed=1)
        p.write_csv(path)
        with open(path, "r", encoding="utf-8") as f:
            head = f.readline().strip()
        assert head.startswith("t,acc_x"), f"CSV 头异常: {head}"
        assert os.stat(path).st_size > 200, "CSV 应有内容"
    print("[sensor] CSV 导出正常")


def test_sensor_stats_magnitude():
    p = SensorProfile(fs=100, duration=3.0, mode="walking", seed=7)
    s = stats(p.rows)
    assert s["acc_z_std"] > 0.03, "步行时垂直加速度应有明显波动"
    print(f"[sensor] stats 量级合理 acc_z_std={s['acc_z_std']:.4f}")


# ---------- IP 助手（纯逻辑，不触发真 adb） ----------
def test_help_proxy_format():
    import helper_proxy
    assert helper_proxy.set_proxy("no-colon")[0] is False, "错误格式应拒绝"
    assert "代理格式" in helper_proxy.set_proxy("x")[1]
    print("[proxy] 格式校验正常")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed, failed = 0, []
    for fn in fns:
        try:
            fn()
            passed += 1
        except Exception as e:
            import traceback
            traceback.print_exc()
            failed.append((fn.__name__, str(e)))
    print(f"\n== 结果: {passed}/{len(fns)} 通过 ==")
    for name, err in failed:
        print(f"  FAIL {name}: {err}")
    sys.exit(1 if failed else 0)
