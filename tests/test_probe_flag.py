# -*- coding: utf-8 -*-
"""test_probe_flag.py - `_probe_no_vision` 必须有默认值（无需真机）

背景（真实缺陷）：
    `any_of` 需要「只有最后一个分支允许视觉兜底」，靠 `self._probe_no_vision`
    控制。但这个属性最初**只在 `_step_any_of` 内部赋值**，而
    `_step_click_text/_click_id/_click_desc/_click_first` 里是**直接读取**
    `self._probe_no_vision` 的。

    后果：**任何不含 `any_of` 的行为**（例如 34 个 App 里大量未改造的行为）
    一旦走到「元素没找到 → 该走视觉兜底了」这一步，就会
    `AttributeError: 'Executor' object has no attribute '_probe_no_vision'`，
    把「没找到按钮」这种正常情况变成崩溃。

    这类缺陷只在真机跑到那一步才暴露，所以必须用单测钉死。

运行：
    python tests/test_probe_flag.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor, StepError  # noqa: E402


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
    「`__init__` 有没有给 `_probe_no_vision` 默认值」，
    绕过 `__init__` 的测试会把这个缺陷藏起来。
    """
    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=True, config={})
    ex._locate = lambda k, v, timeout=2.0: None
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    return ex


def t_attribute_has_default():
    """构造出的 Executor 就应带默认值（不依赖 any_of 先跑过）。"""
    ex = _mk()
    assert hasattr(ex, "_probe_no_vision"), \
        "_probe_no_vision 必须有默认值，否则非 any_of 行为会 AttributeError"
    assert ex._probe_no_vision is False
    print("OK  Executor 具备 _probe_no_vision 默认值")


def t_click_first_without_anyof_does_not_crash():
    """不含 any_of 的行为，候选全未命中 + optional -> 返回 False，不崩。"""
    ex = _mk()
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "签到"}],
           "timeout": 8, "optional": True}
    assert ex._step_click_first(act, "T") is False
    print("OK  非 any_of 行为的 click_first 未命中不崩溃")


def t_click_first_without_anyof_raises_when_required():
    """非 optional 时应当抛 StepError（而不是 AttributeError）。"""
    ex = _mk()
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "签到"}],
           "timeout": 8, "optional": False}
    try:
        ex._step_click_first(act, "T")
    except StepError:
        print("OK  非 optional 未命中抛 StepError（语义正确）")
        return
    except AttributeError as e:
        raise AssertionError(f"不应是 AttributeError: {e}")
    raise AssertionError("应当抛 StepError")


def t_click_text_without_anyof_does_not_crash():
    ex = _mk()
    act = {"type": "click_text", "text": "提现", "timeout": 6, "optional": True}
    try:
        ex._step_click_text(act, "T")
    except StepError:
        pass          # 未找到按钮 -> StepError 是预期
    except AttributeError as e:
        raise AssertionError(f"不应是 AttributeError: {e}")
    print("OK  非 any_of 行为的 click_text 不崩溃")


def t_attribute_is_load_bearing():
    """反证：把这个属性删掉，非 any_of 行为立刻崩 —— 证明测试真的钉住了缺陷。

    如果哪天有人把 `__init__` 里的初始化删掉，上面几个用例会失败；
    这个用例说明"为什么必须失败"。
    """
    ex = _mk()
    del ex._probe_no_vision
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "签到"}],
           "timeout": 8, "optional": True}
    try:
        ex._step_click_first(act, "T")
    except AttributeError as e:
        assert "_probe_no_vision" in str(e), e
        print("OK  反证成立：缺该属性会 AttributeError（初始化不可省）")
        return
    raise AssertionError("缺属性时竟然没报错，说明读取点已变，测试需更新")


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
