# -*- coding: utf-8 -*-
"""test_click_obj_bounds.py - 锁 _click_obj 元素 bounds API 坑（2026-10-21 二轮回归实崩）

背景：回归 7/12「命中」全是坐标兜底，把 `_click_obj` 从不能被真机走到的
状态遮住；二轮文案一旦命中即崩：
  AttributeError: 'UiObject' object has no attribute 'rect'
u2 UiObject 的正确 API 是 `.bounds()` -> (lx, ly, rx, ry) plain tuple。

覆盖：
  1. 真机形态（.bounds() tuple）-> 点中心；
  2. 测试/探针假元素（.rect 属性对象）-> 兼容点中心；
  3. dry_run -> 零点击；
  4. 统一走 human.tap（F2 入口），不裸调 d.click。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from locator import Locator  # noqa: E402
from behavior_runner import StepError  # noqa: E402


class _Human:
    def __init__(self):
        self.taps = []

    def jitter_point(self, x, y):
        return x, y

    def tap(self, d, x, y):
        self.taps.append((x, y))


class _D:
    def click(self, x, y):  # 直连 click 若被调用说明绕过了 human.tap
        raise AssertionError("_click_obj 不得裸调 d.click（须走 human.tap）")


class _Loc:
    """只借 Locator._click_obj 的真实实现，不构造完整 Locator。"""

    def __init__(self, human, dry_run=False):
        self.human = human
        self.d = _D()
        self.dry_run = dry_run

    _click_obj = Locator._click_obj


class _U2Obj:
    """真机形态：u2 UiObject，无 .rect，.bounds() 回 tuple。"""

    def bounds(self):
        return (100, 200, 300, 400)


class _RectObj:
    """假元素形态：.rect 属性对象（tests/test_dismiss_popups.py 同款）。"""

    @property
    def rect(self):
        class _R:
            left, top, right, bottom = 100, 200, 300, 400
        return _R()


def t_u2_bounds_tuple():
    h = _Human()
    _Loc(h)._click_obj(_U2Obj())
    assert h.taps == [(200, 300)], h.taps
    print("t_u2_bounds_tuple OK")


def t_rect_attr_compat():
    h = _Human()
    _Loc(h)._click_obj(_RectObj())
    assert h.taps == [(200, 300)], h.taps
    print("t_rect_attr_compat OK")


def t_dry_run_no_click():
    h = _Human()
    _Loc(h, dry_run=True)._click_obj(_U2Obj())
    assert h.taps == [], h.taps
    print("t_dry_run_no_click OK")


def t_goes_through_human_tap():
    """ bounds 非偶数轴：(lx+rx)//2 取整；且只许 human.tap 一处出口。"""
    class _Odd:
        def bounds(self):
            return (101, 201, 302, 403)
    h = _Human()
    _Loc(h)._click_obj(_Odd())
    assert h.taps == [((101 + 302) // 2, (201 + 403) // 2)], h.taps
    print("t_goes_through_human_tap OK")


class _StaleObj:
    """真机竞态形态：bounds() 抛 RPCUnknownError(StaleObjectException)。"""

    def __init__(self, box=(100, 200, 300, 400), boom=True):
        self._box, self._boom = box, boom

    def bounds(self):
        if self._boom:
            raise RuntimeError("Unknown RPC error: -32001 StaleObjectException")
        return self._box


def t_stale_relocate_retry():
    """失效后 relocate 重定位成功 -> 点新元素中心（快手 2026-10-21 实崩场景）。"""
    h = _Human()
    fresh = _U2Obj()
    _Loc(h)._click_obj(_StaleObj(), relocate=lambda: fresh)
    assert h.taps == [(200, 300)], h.taps
    print("t_stale_relocate_retry OK")


def t_stale_no_relocate_raises_steperror():
    """失效且无 relocate -> StepError（上层记「步骤失败」不崩）。"""
    h = _Human()
    try:
        _Loc(h)._click_obj(_StaleObj())
    except StepError as e:
        assert "元素已失效" in str(e), str(e)
        assert h.taps == []
        print("t_stale_no_relocate_raises_steperror OK")
        return
    raise AssertionError("应抛 StepError")


def t_stale_relocate_miss_raises():
    """relocate 也找不到 -> StepError，section 不崩。"""
    h = _Human()
    try:
        _Loc(h)._click_obj(_StaleObj(), relocate=lambda: None)
    except StepError:
        assert h.taps == []
        print("t_stale_relocate_miss_raises OK")
        return
    raise AssertionError("应抛 StepError")


if __name__ == "__main__":
    t_u2_bounds_tuple()
    t_rect_attr_compat()
    t_dry_run_no_click()
    t_goes_through_human_tap()
    t_stale_relocate_retry()
    t_stale_no_relocate_raises_steperror()
    t_stale_relocate_miss_raises()
    print("ALL click_obj bounds TESTS PASSED")
