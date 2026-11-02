# -*- coding: utf-8 -*-
"""test_rpc_overflow.py - RPCStackOverflowError 防御性重试（2026-11-01 微博实崩定位）

背景：RPCError 族继承 BaseException 而非 Exception，现有 `except Exception` 全部漏接，
Android 侧 java.lang.StackOverflowError 会直接穿出崩掉整条 App 流程（微博一轮 6 次）。

修复落点（locator.py）：
  - `_locate`：捕获溢出，退避重试 `rpc_retries` 次；超限返回 hit=False（B6 契约：
    定位永不因未命中抛异常，上层记「步骤失败」继续跑）。
  - `_click_obj`：溢出按「元素失效」同一语义处理 —— relocate 重定位一次再点；
    仍溢出抛 StepError。

运行：python tests/test_rpc_overflow.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from locator import Locator, LocateResult  # noqa: E402

try:
    from uiautomator2.exceptions import RPCStackOverflowError
    HAS_U2 = True
except Exception:  # pragma: no cover - 无 uiautomator2 依赖时跳过
    HAS_U2 = False


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))


class _Human:
    def __init__(self):
        self.taps = []

    def jitter_point(self, x, y):
        return x, y

    def tap(self, d, x, y):
        self.taps.append((x, y))


class _D:
    """d(textContains=...) 每次返回同一 obj（计数器跨轮次持久）。"""

    def __init__(self, obj):
        self._obj = obj

    def __call__(self, **kw):
        return self._obj


class _ObjWait:
    """fake UiObject：wait() 先抛 n 次溢出，之后返回 True。"""

    def __init__(self, n_overflow):
        self._n = n_overflow
        self.wait_calls = 0

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self._n > 0:
            self._n -= 1
            raise RPCStackOverflowError("StackOverflowError: test", {}, "")
        return True


class _BoundsObj:
    """fake 元素：bounds() 先抛 n 次溢出，之后返回坐标。无 .rect（走真机 bounds 路径）。"""

    def __init__(self, n_overflow):
        self._n = n_overflow
        self.bounds_calls = 0

    def bounds(self):
        self.bounds_calls += 1
        if self._n > 0:
            self._n -= 1
            raise RPCStackOverflowError("StackOverflowError: test", {}, "")
        return (100, 200, 300, 400)


def _mk_locator(d, retries=2, backoff=0.0):
    lc = Locator.__new__(Locator)
    lc.d = d
    lc.dry_run = False
    lc.recorder = _Rec()
    lc.human = _Human()
    lc.rpc_retries = retries
    lc.rpc_backoff = backoff
    # 绕过 pick_locate：本测试只验证重试机制，不测 _pick_best 内部
    lc._pick_best = lambda obj, *a, **k: obj
    return lc


def t_locate_overflow_once_then_hit():
    """溢出一次 -> 退避重试 -> 第二次命中。"""
    obj = _ObjWait(n_overflow=1)
    lc = _mk_locator(_D(obj))
    res = lc._locate("text", "签到", timeout=3.0)
    assert res.hit, f"重试后应命中，got {res.detail}"
    assert obj.wait_calls >= 2, f"wait 应被调 >=2 次，got {obj.wait_calls}"


def t_locate_overflow_exhausted_miss():
    """持续溢出超限 -> hit=False（B6 契约：不抛异常）。"""
    obj = _ObjWait(n_overflow=99)
    lc = _mk_locator(_D(obj), retries=2, backoff=0.0)
    res = lc._locate("text", "签到", timeout=3.0)
    assert not res.hit, "超限应未命中"
    assert "RPC 栈溢出持续" in res.detail, f"detail 应说明溢出放弃，got {res.detail}"
    assert obj.wait_calls == 3, f"retries=2 应共试 3 次，got {obj.wait_calls}"


def t_click_obj_overflow_retry_succeeds():
    """溢出一次 -> 退避重试（不 relocate，元素仍有效）-> 点击成功。"""
    obj = _BoundsObj(n_overflow=1)
    lc = _mk_locator(_D(obj), retries=2, backoff=0.0)
    lc._click_obj(obj)
    assert lc.human.taps, "退避重试后应完成点击"
    assert obj.bounds_calls == 2, f"应 bounds 两次（1 溢出+1 成功），got {obj.bounds_calls}"


def t_click_obj_overflow_exhausted_step_error():
    """持续溢出超限 -> StepError（上层记步骤失败继续跑，不崩流程）。"""
    from behavior_runner import StepError
    obj = _BoundsObj(n_overflow=99)
    lc = _mk_locator(_D(obj), retries=2, backoff=0.0)
    try:
        lc._click_obj(obj)
    except StepError as e:
        assert "RPC 栈溢出" in str(e), f"StepError 应标注溢出，got {e}"
        assert obj.bounds_calls == 3, f"retries=2 应共试 3 次，got {obj.bounds_calls}"
        return
    raise AssertionError("持续溢出应抛 StepError")


if __name__ == "__main__":
    if not HAS_U2:
        print("SKIP: 无 uiautomator2，跳过 RPC 溢出测试")
        sys.exit(0)
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)}/{len(tests)} PASS")
