# -*- coding: utf-8 -*-
"""test_nav_band.py - 底部导航标签的位置合理性校验（无需真机）

背景（踩过的坑）：
    「我的」「我」这类底部导航标签，在页面**中部**也会出现（例如某个卡片
    里写着「我的收益」之外的独立「我的」标签）。实测蛋花免费小说二级页
    命中过 text='我的' @(575,627) —— 1080x2340 的屏幕上 y=627 是页面中部，
    不可能是底部导航栏。若不区分，会：
      1. 度量虚高：把「找到页面中部一个『我的』标签」当成「找到了导航入口」；
      2. 执行出错：执行器可能点到页面中部的那个标签。

新语义：
    * 目标词是底部导航标签时，命中必须落在屏幕底部带（y >= 0.80 * 屏高）
      才算数；否则判为「疑似假命中」。
    * 非导航标签（如「签到」）不受影响。

运行：
    python tests/test_nav_band.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "devtools"))

from verify_live import check_anchor, _nav_ok, NAV_BAND_Y  # noqa: E402

H = 2340


def _node(text, cx, cy, clickable=True, desc=""):
    return {"text": text, "desc": desc, "rid": "", "center": (cx, cy),
            "size": (100, 100), "clickable": clickable,
            "bounds": (cx - 50, cy - 50, cx + 50, cy + 50)}


def t_nav_label_in_middle_is_rejected():
    """y=627 的「我的」不是底部导航 -> 假命中。"""
    nodes = [_node("我的", 575, 627)]
    hit, det = check_anchor(nodes, {"type": "click_text", "text": "我的"}, H)
    assert not hit, f"应判假命中，实际 hit={hit} det={det}"
    assert "不在底部导航带" in det, det
    print("OK  页面中部的『我的』被判为疑似假命中")


def t_nav_label_in_bottom_band_accepted():
    nodes = [_node("我的", 918, 2130)]
    hit, det = check_anchor(nodes, {"type": "click_text", "text": "我的"}, H)
    assert hit, det
    print("OK  底部带的『我的』命中")


def t_boundary_at_band_edge():
    """正好在 0.80 * H 上算命中（>=）。"""
    y = int(NAV_BAND_Y * H)
    assert _nav_ok(_node("我的", 500, y), "我的", H)
    assert not _nav_ok(_node("我的", 500, y - 1), "我的", H)
    print("OK  底部带边界按 >= 0.80*屏高 判定")


def t_non_nav_label_unaffected():
    """非导航标签不做位置限制（签到按钮可能在任何位置）。"""
    nodes = [_node("签到", 720, 2093), _node("每日签到", 300, 500)]
    hit, det = check_anchor(nodes, {"type": "click_text", "text": "签到"}, H)
    assert hit, det
    hit2, det2 = check_anchor(nodes, {"type": "click_text", "text": "每日签到"}, H)
    assert hit2, det2
    print("OK  非导航标签不受底部带限制")


def t_click_first_falls_through_to_bottom_match():
    """click_first：中部命中被否，底部命中被接受。"""
    nodes = [_node("我的", 575, 627), _node("我的", 918, 2130)]
    hit, det = check_anchor(
        nodes,
        {"type": "click_first", "candidates": [{"type": "text", "value": "我的"}]},
        H)
    assert hit, det
    assert "2130" in det, det
    print("OK  click_first 跳过中部假命中、取底部真命中")


def t_no_screen_h_skips_check():
    """未提供屏高时保持旧行为（不做位置校验）。"""
    nodes = [_node("我的", 575, 627)]
    hit, det = check_anchor(nodes, {"type": "click_text", "text": "我的"}, None)
    assert hit, det
    print("OK  未提供屏高时不做位置校验（向后兼容）")


def t_any_of_inherits_nav_band():
    nodes = [_node("我的", 575, 627)]
    act = {"type": "any_of", "optional": True,
           "choices": [[{"type": "click_first",
                         "candidates": [{"type": "text", "value": "我的"}]}]]}
    hit, det = check_anchor(nodes, act, H)
    assert not hit, f"any_of 应继承位置校验: {det}"
    print("OK  any_of 分支继承底部带校验")


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
