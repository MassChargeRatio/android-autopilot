# -*- coding: utf-8 -*-
"""test_click_point_no_coord.py - 纯图像锚点步骤不得崩溃（2026-10-30）

立卡依据（全量跑实测）：34 个 App 跑一遍，3 个 FAIL-异常，其中 2 个是同一个
`TypeError: float() argument must be ... not 'NoneType'` —— 快手 bonus 与
飞猪旅行的 `click_point` 只配了 `images`（图像锚点）、没有 `x/y`，视觉一 miss
就掉到 `float(act.get("x"))` 崩掉，**整个 App 的运行直接中断**。

配置实测量级：72 个顶层 click_point 里 53 个带 images，其中 45 个没有 x/y。
也就是说这个崩溃面覆盖了 45 个步骤。

修复口径：没有坐标 = 没有可点的地方，按「未命中」返回 False，
交给 optional / 步骤失败逻辑，不许抛异常。

运行：
    python tests/test_click_point_no_coord.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from behavior_runner import BehaviorRunner  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))


class _D:
    dry_run = False

    def __init__(self):
        self.clicked = []

    def window_size(self):
        return (1080, 2340)

    def click(self, x, y):
        self.clicked.append((x, y))


class _Human:
    def jitter_point(self, x, y):
        return x, y

    def tap(self, d, x, y):
        d.click(x, y)


def _mk(vision_hit=False):
    br = BehaviorRunner.__new__(BehaviorRunner)
    br.recorder = _Rec()
    br.d = _D()
    br.dry_run = False
    br.human = _Human()
    br._last_fail = ""
    br._vision_click = lambda act, app, desc: vision_hit
    return br


def t_image_only_miss_returns_false():
    """images 锚点 + 视觉 miss + 无 x/y -> 返回 False，不抛异常。"""
    br = _mk(vision_hit=False)
    act = {"type": "click_point", "images": ["a.png"], "optional": True,
           "desc": "图像-快手-任务界面-红包图标"}
    ok = br._step_click_point(act, "快手")
    assert ok is False, f"应返回 False，实际 {ok!r}"
    assert br.d.clicked == [], f"不该点任何坐标，实际 {br.d.clicked}"
    assert br._last_fail, "应留下失败原因供上层日志使用"
    print("OK  图像锚点 miss + 无坐标 -> False，零点击，不崩")


def t_image_only_hit_returns_true():
    """images 锚点 + 视觉命中 -> True。"""
    br = _mk(vision_hit=True)
    act = {"type": "click_point", "images": ["a.png"], "optional": True}
    assert br._step_click_point(act, "快手") is True
    print("OK  图像锚点命中 -> True")


def t_coord_step_unaffected():
    """有坐标的步骤行为不变（归一化 -> 像素）。"""
    br = _mk()
    act = {"type": "click_point", "x": 0.5, "y": 0.25, "vision": False}
    assert br._step_click_point(act, "X") is True
    assert br.d.clicked == [(540, 585)], br.d.clicked
    print("OK  坐标步骤不受影响（0.5/0.25 -> 540,585）")


def t_x_only_also_guarded():
    """只给 x 不给 y 也算「没有完整坐标」，同样按未命中处理。"""
    br = _mk()
    act = {"type": "click_point", "x": 0.5, "vision": False}
    assert br._step_click_point(act, "X") is False
    assert br.d.clicked == []
    print("OK  只有 x 缺 y -> False，不崩")


def t_zero_coord_is_valid():
    """x=0 是合法坐标，不能被 `or` 式的假值判断误伤。"""
    br = _mk()
    act = {"type": "click_point", "x": 0, "y": 0, "vision": False}
    assert br._step_click_point(act, "X") is True
    assert br.d.clicked == [(0, 0)], br.d.clicked
    print("OK  x=0/y=0 是合法坐标（用 is None 判断，不是假值判断）")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
