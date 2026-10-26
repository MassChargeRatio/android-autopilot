# -*- coding: utf-8 -*-
"""test_pick_best_pure.py - pick_locate.pick_best 纯函数单元测试（A2）

覆盖：
  1. nav 带边界：top == NAV_BAND_Y * screen_h 恰好算带内（>= 判据）；
  2. 平局取先：完全同分时返回先出现的下标；
  3. screen_h=0 时跳过 nav 带内加分（未知屏高不猜）；
  4. 拒配 limit 边界：len == limit 接受、len == limit+1 且不可点击拒绝。

运行：
    python -m pytest tests/test_pick_best_pure.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pick_locate import pick_best, NAV_BAND_Y  # noqa: E402


def _log(lines):
    return lambda event, app="", level="INFO": lines.append((level, event))


def test_nav_boundary_in_band():
    """top 恰好等于 NAV_BAND_Y*screen_h 时算带内，应获 +120 加分。"""
    screen_h = 2340
    band = int(NAV_BAND_Y * screen_h)
    lines = []
    entries = [
        {"label": "我的", "clickable": True, "top": 500},    # 带外
        {"label": "我的", "clickable": False, "top": band},  # 边界=带内
    ]
    idx = pick_best(entries, "我的", "text", screen_h, _log(lines))
    assert idx == 1, f"边界带内条目应被选中，实际 {idx}"
    print("OK  nav 边界 top==NAV_BAND_Y*screen_h 算带内")


def test_tie_keeps_first():
    """完全同分时返回先出现的下标（平局取先）。"""
    entries = [
        {"label": "签到", "clickable": True, "top": 100},
        {"label": "签到", "clickable": True, "top": 100},
    ]
    idx = pick_best(entries, "签到", "text", 2340)
    assert idx == 0, f"平局应取先，实际 {idx}"
    print("OK  平局取先")


def test_screen_h_zero_skips_nav():
    """screen_h=0（未知屏高）时跳过 nav 带内加分，不猜位置。"""
    entries = [
        {"label": "我的", "clickable": False, "top": 500},
        {"label": "我的", "clickable": False, "top": 2000},
    ]
    idx = pick_best(entries, "我的", "text", 0)
    assert idx == 0, f"screen_h=0 时不应做 nav 加分，平局取先 -> 0，实际 {idx}"
    print("OK  screen_h=0 跳过 nav 加分")


def test_limit_boundary_accept_and_reject():
    """拒配 limit 边界：len==limit 接受，len==limit+1 且不可点击拒绝。"""
    # target='签到' len=2 -> limit=max(8,6)=8
    accept = pick_best([{"label": "12345678", "clickable": False, "top": 0}],
                       "签到", "text", 0)
    assert accept == 0, "len==limit 应被接受"
    lines = []
    reject = pick_best([{"label": "123456789", "clickable": False, "top": 0}],
                       "签到", "text", 0, _log(lines))
    assert reject is None, "len==limit+1 且不可点击应被拒配"
    assert any("过长文案" in m for _l, m in lines), lines
    print("OK  limit 边界：len==limit 接受 / +1 拒")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
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
