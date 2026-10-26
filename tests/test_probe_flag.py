# -*- coding: utf-8 -*-
"""test_probe_flag.py - 非 any_of 行为的定位未命中不崩溃（无需真机）

背景（真实缺陷，B6 修复）：`_step_click_text/_click_id/_click_desc/_click_first`
里直接读 `self._probe_no_vision`，而该属性最初只在 `_step_any_of` 内部赋值，
**任何不含 `any_of` 的行为**一旦走到「元素没找到 → 该走视觉兜底了」就会
`AttributeError`，把「没找到按钮」这种正常情况变成崩溃。

B7 演进：视觉门控从实例标志位改为显式参数链（`_step_click_*(…, allow_vision=True)`），
不再有 `_probe_no_vision` 属性。教训：靠"临时改写再还原"的实例标志位做门控，
异常/新增直调点会留下脏状态；现在 allow_vision 显式贯穿，参数默认值
天然保证非 any_of 行为可走视觉兜底。原「属性必须有默认值」与「反证删除即崩」
两用例随之取消（钉的属性已不存在），语义用例保留：非 any_of 定位未命中
一律返回 False 且不崩溃。

运行：
    python tests/test_probe_flag.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor, LocateResult  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append(f"[{level}] {event}")


class _KB:
    def mark_ok(self, app, sel):
        pass

    def mark_fail(self, app, sel):
        pass


class _Human:
    def delay(self, *a):
        pass

    def maybe_wander(self, *a):
        pass


def _mk():
    """用**真实构造函数**造 Executor（dry_run，不连设备）。

    刻意不用 `Executor.__new__` 绕过 `__init__` —— 本文件要钉住的正是
    「`__init__` 缺初始化时行为是否还安全」。B7 后门控是参数默认值，
    `__init__` 不再有 _probe_no_vision，用例只验行为不崩。
    """
    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=True, config={})
    ex._locate = lambda k, v, timeout=2.0: LocateResult(False, None, "测试未命中")
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    return ex


def t_click_first_without_anyof_does_not_crash():
    """不含 any_of 的行为，候选全未命中 + optional -> 返回 False，不崩。"""
    ex = _mk()
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "签到"}],
           "timeout": 8, "optional": True}
    assert ex._step_click_first(act, "T") is False
    print("OK  非 any_of 行为的 click_first 未命中不崩溃")


def t_click_first_without_anyof_returns_false_when_required():
    """非 optional 时返回 False 并记录 detail（B6 不再抛 StepError）。"""
    ex = _mk()
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "签到"}],
           "timeout": 8, "optional": False}
    res = ex._step_click_first(act, "T")
    assert res is False, f"应返回 False，实际 {res!r}"
    assert ex._last_fail and "所有候选均未出现" in ex._last_fail, ex._last_fail
    print("OK  非 optional 未命中返回 False 并记录 detail（语义正确）")


def t_click_text_without_anyof_returns_false():
    ex = _mk()
    act = {"type": "click_text", "text": "提现", "timeout": 6, "optional": True}
    try:
        res = ex._step_click_text(act, "T")
    except AttributeError as e:
        raise AssertionError(f"不应是 AttributeError: {e}")
    assert res is False, f"应返回 False，实际 {res!r}"
    print("OK  非 any_of 行为的 click_text 未命中返回 False 不崩溃")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
