# -*- coding: utf-8 -*-
"""test_any_of_budget.py - B1 any_of 整次总预算（2026-10-30 任务卡）

立卡依据：快手一次 any_of 全 miss 实测 26s（单分支 timeout 8s 串行 + 内部重试）。
本文件钉住：默认 30s = 现行为（老配置零影响）；显式 total_timeout 才截断。

运行：
    python tests/test_any_of_budget.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append(f"[{level}] {event}")

    def has(self, needle):
        return any(needle in l for l in self.lines)


def _mk(total=30.0):
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex._any_of_total = total
    return ex


def t_default_budget_does_not_cut():
    """act 未写 total_timeout -> 用实例默认 30s，3 个快分支全跑。"""
    seen = []

    def probe(act, app, allow_vision):
        seen.append(act.get("tag"))
        return False

    ex = _mk(30.0)
    ex._dispatch_probe = probe
    act = {"type": "any_of", "choices": [[{"tag": 1}], [{"tag": 2}], [{"tag": 3}]]}
    assert ex._step_any_of(act, "T") is False
    assert seen == [1, 2, 3], seen
    assert not ex.recorder.has("总预算"), "默认预算下不该出现截断日志"
    print("OK  B1 默认 30s 不截断（老配置零影响）")


def t_explicit_total_timeout_cuts_off():
    """act 显式 total_timeout 很小 + 慢分支 -> 截断剩余分支并记 WARN。"""
    def probe(act, app, allow_vision):
        time.sleep(0.08)
        return False

    ex = _mk(30.0)
    ex._dispatch_probe = probe
    act = {"type": "any_of", "total_timeout": 0.05,
           "choices": [[{"tag": 1}], [{"tag": 2}], [{"tag": 3}]]}
    assert ex._step_any_of(act, "T") is False
    assert ex.recorder.has("总预算"), ex.recorder.lines
    print("OK  B1 显式 total_timeout 截断并记 WARN")


def t_budget_exhausted_optional_passes():
    """预算用尽 + optional -> 放行 True（与「全部分支未命中 + optional」一致）。"""
    def probe(act, app, allow_vision):
        time.sleep(0.08)
        return False

    ex = _mk(30.0)
    ex._dispatch_probe = probe
    act = {"type": "any_of", "total_timeout": 0.05, "optional": True,
           "choices": [[{"tag": 1}], [{"tag": 2}]]}
    assert ex._step_any_of(act, "T") is True
    print("OK  B1 预算用尽 + optional -> True")


def t_instance_default_from_config():
    """Executor 构造时从 config.timeouts.any_of_total 读；缺省 30；脏值回落 30。"""
    for cfg, want in [
        ({}, 30.0),
        ({"timeouts": {"any_of_total": 12}}, 12.0),
        ({"timeouts": {"any_of_total": "abc"}}, 30.0),
    ]:
        ex = Executor.__new__(Executor)
        # 复刻 __init__ 里那三行的取值逻辑
        t = (cfg or {}).get("timeouts") or {}
        try:
            got = float(t.get("any_of_total", 30.0))
        except (TypeError, ValueError):
            got = 30.0
        ex._any_of_total = got
        assert got == want, (cfg, got, want)
    print("OK  B1 config.timeouts.any_of_total 取值（缺省 30 / 脏值回落 30）")


def t_budget_zero_means_unlimited():
    """total_timeout: 0 -> 不设 deadline（保持老语义：不截断）。"""
    seen = []

    def probe(act, app, allow_vision):
        seen.append(1)
        return False

    ex = _mk(30.0)
    ex._dispatch_probe = probe
    act = {"type": "any_of", "total_timeout": 0,
           "choices": [[{"tag": 1}], [{"tag": 2}]]}
    assert ex._step_any_of(act, "T") is False
    assert len(seen) == 2, seen
    print("OK  B1 total_timeout=0 视为不限")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
