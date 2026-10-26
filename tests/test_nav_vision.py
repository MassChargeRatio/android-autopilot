# -*- coding: utf-8 -*-
"""test_nav_vision.py - 导航前置步跳过视觉兜底（无需真机）

背景：
    `click_point` 带 `vlm_prompt` 时执行器会**先走视觉兜底**（截屏 + VLM 识别）。
    本机 VLM 图像请求常 90s 超时或返回 `User Safety: safe`，而导航「我的」是
    **每个行为都要执行**的固定步骤 —— 让它走视觉既慢又不稳。

    `vision: false` 让该步跳过视觉，直接用比例坐标（已在 18 个 App 上验证）。

运行：
    python tests/test_nav_vision.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append(f"[{level}] {event}")


class _Human:
    def jitter_point(self, x, y):
        return x, y

    def tap(self, d, x, y):
        # F2 统一点击入口；测试里直通 d.click，保持 clicked 断言口径
        self.tapped = getattr(self, "tapped", [])
        self.tapped.append((x, y))
        d.click(x, y)


class _Size:
    """uiautomator2 的 window_size() 返回带 width/height 的对象，不是元组。"""

    def __init__(self, w, h):
        self.width = w
        self.height = h


class _D:
    def __init__(self):
        self.clicked = []

    def window_size(self):
        return _Size(1080, 2340)

    def click(self, x, y):
        self.clicked.append((x, y))


class _Vision:
    def __init__(self):
        self.calls = 0

    def screenshot_from_device(self, d):
        self.calls += 1
        return "img"

    def locate_on_screen(self, **kw):
        self.calls += 1
        return None          # 模拟 VLM 未命中/超时


def _mk():
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex.human = _Human()
    ex.d = _D()
    ex.vision = _Vision()
    ex.vision_enabled = True
    ex.dry_run = False
    return ex


NAV = {"type": "click_point",
       "vlm_prompt": "定位屏幕底部导航栏最右侧的『我的』标签中心",
       "x": 0.9, "y": 0.915, "optional": True}


def t_vision_false_skips_vision():
    ex = _mk()
    act = dict(NAV, vision=False)
    ex._step_click_point(act, "测试")
    assert ex.vision.calls == 0, f"不应调用视觉，实际 {ex.vision.calls} 次"
    assert ex.d.clicked == [(972, 2141)], f"应点比例坐标，实际 {ex.d.clicked}"
    print("OK  vision=false 时跳过视觉，直接点比例坐标")


def t_vision_default_still_tries_vision():
    """未显式关闭时保持旧行为：先试视觉兜底。"""
    ex = _mk()
    ex._step_click_point(dict(NAV), "测试")
    assert ex.vision.calls > 0, "默认应尝试视觉兜底"
    assert ex.d.clicked, "视觉未命中后应回退到比例坐标"
    print("OK  未设 vision 时仍先试视觉兜底，失败后回退比例坐标")


def t_vision_true_explicit():
    ex = _mk()
    ex._step_click_point(dict(NAV, vision=True), "测试")
    assert ex.vision.calls > 0
    print("OK  vision=true 显式开启视觉兜底")


def t_plain_point_without_prompt_never_uses_vision():
    ex = _mk()
    ex._step_click_point({"type": "click_point", "x": 0.5, "y": 0.5}, "测试")
    assert ex.vision.calls == 0
    assert ex.d.clicked == [(540, 1170)]
    print("OK  无视觉绑定的 click_point 不走视觉")


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
