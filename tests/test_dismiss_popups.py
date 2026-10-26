# -*- coding: utf-8 -*-
"""test_dismiss_popups.py - F1 全局弹窗清扫（AUTOP-FEAT-2026-10-20）无需真机

用户原话三条需求的落点：
  1. 「遇到各种不是程序自身引起的弹窗，都可以看到就关闭」
  2. 「关闭弹窗的方式还可以尝试系统的回退键」  -> 文案 -> id -> 右上角 -> BACK
  3. 「不是主动观看的广告，也可以跳过」        -> protect_ad 关掉正在看的广告文案

硬护栏（2026-10-20 蜗牛睡眠 + 资金红线教训）：
  - 资金类黑名单命中 -> "blocked"：停扫且禁用 BACK
  - 干净屏（无广告特征）不动坐标/返回键

运行：
    python tests/test_dismiss_popups.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from behavior_runner import (  # noqa: E402
    BehaviorRunner, DEFAULT_POPUP_TEXTS, POPUP_BLACKLIST_TEXTS)


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))


class _Human:
    def __init__(self):
        self.thoughts = 0

    def jitter_point(self, x, y):
        return x, y

    def think(self):
        self.thoughts += 1


class _Obj:
    def __init__(self, label):
        self.label = label

    @property
    def rect(self):
        class _R:
            left, top, right, bottom = 100, 200, 300, 400
        return _R()


class _Size:
    def __init__(self, w, h):
        self.width, self.height = w, h


class _D:
    """window_size 返回 plain tuple（2026-10-20 真机实测形态）。"""

    def __init__(self, ws=(1080, 2340)):
        self._ws = ws
        self.clicked = []   # (x, y)
        self.pressed = []   # key

    def window_size(self):
        return self._ws

    def click(self, x, y):
        self.clicked.append((x, y))

    def press(self, key):
        self.pressed.append(key)


def _mk(present=None, xml="", ws=(1080, 2340)):
    """present: {(kind, value): label} _locate 命中表；xml: dump 内容。"""
    br = BehaviorRunner.__new__(BehaviorRunner)
    br.recorder = _Rec()
    br.human = _Human()
    br.d = _D(ws)
    br.dry_run = False
    present = present or {}

    def _dump_safe():
        return xml

    def _locate(kind, value, timeout=6.0):
        if (kind, value) in present:
            return type("R", (), {"hit": True, "obj": _Obj(present[(kind, value)])})()
        return type("R", (), {"hit": False, "obj": None})()

    clicked_labels = []

    def _click_obj(obj):
        clicked_labels.append(obj.label)

    br._dump_safe = _dump_safe
    br._locate = _locate
    br._click_obj = _click_obj
    br._clicked_labels = clicked_labels
    return br


def t_text_priority():
    """文案优先：多个关闭文案同时在场，点 DEFAULT_POPUP_TEXTS 首个命中。"""
    br = _mk(present={("text", "我知道了"): "btn-know"})
    # 「我知道了」在默认表第 8 位；assert 它被点且没有动坐标/返回键
    ok = br._popup_close_one(DEFAULT_POPUP_TEXTS, [], corner=True,
                             back_key=True, app_name="X", rnd=1)
    assert ok is True
    assert br._clicked_labels == ["btn-know"], br._clicked_labels
    assert br.d.clicked == [] and br.d.pressed == []
    print("t_text_priority OK")


def t_blacklist_blocks_back():
    """资金黑名单熔断：命中即停扫且禁用 BACK。"""
    xml = "<node text='确认提现'/>"
    br = _mk(xml=xml)
    ret = br._step_dismiss_popups(
        {"max_rounds": 3, "blacklist": POPUP_BLACKLIST_TEXTS}, "X")
    assert ret == "blocked", ret
    assert br.d.pressed == [], "资金屏禁止按 BACK（提现确认必须留给人）"
    assert any("熔断" in e and "资金" in e for _, e in br.recorder.lines)
    print("t_blacklist_blocks_back OK")


def t_blacklist_extra_merge():
    """extra_blacklist 配置追加：屏上只有自定义资金文案也应熔断。"""
    xml = "<node text='红包余额已发放'/>"
    br = _mk(xml=xml)
    ret = br._step_dismiss_popups(
        {"max_rounds": 2, "blacklist": POPUP_BLACKLIST_TEXTS + ["红包余额"]},
        "X")
    assert ret == "blocked", ret
    assert br.d.pressed == []
    print("t_blacklist_extra_merge OK")


def t_watch_protects_ad():
    """watch 流程 protect_ad：正在看的广告文案不关，落到右上角坐标。"""
    # 屏上有「跳过」按钮（正在看的广告）与广告特征
    br = _mk(present={("text", "跳过"): "ad-skip"}, xml="<node text='广告'/>")
    act = {"max_rounds": 1, "protect_ad": True}
    ret = br._step_dismiss_popups(act, "X")
    assert ret is True
    assert br._clicked_labels == [], "protect_ad 下不得点『跳过』"
    assert len(br.d.clicked) == 1, "应落右上角坐标兜底"
    x, y = br.d.clicked[0]
    assert abs(x - 1080 * 0.93) < 2 and abs(y - 2340 * 0.11) < 2, (x, y)
    print("t_watch_protects_ad OK")


def t_watch_protect_off():
    """非 watch（protect_ad=False）：「跳过」应正常关。"""
    br = _mk(present={("text", "跳过"): "ad-skip"})
    ret = br._step_dismiss_popups({"max_rounds": 1, "protect_ad": False}, "X")
    assert ret is True
    assert br._clicked_labels == ["ad-skip"]
    assert br.d.clicked == [] and br.d.pressed == []
    print("t_watch_protect_off OK")


def t_back_fallback_order():
    """顺序最后一级：有广告特征 + corner_fallback=False -> 系统返回键。"""
    br = _mk(xml="<node text='跳过广告 5'/>")
    act = {"max_rounds": 1, "corner_fallback": False, "back_key": True}
    ret = br._step_dismiss_popups(act, "X")
    assert ret is True
    assert br.d.pressed == ["back"], br.d.pressed
    assert br.d.clicked == []
    print("t_back_fallback_order OK")


def t_clean_screen_no_action():
    """干净屏零交互：无文案/id 命中且无广告特征 -> 不动坐标不动 BACK。"""
    br = _mk(xml="<node text='签到领金币'/>")
    ret = br._step_dismiss_popups({"max_rounds": 3}, "X")
    assert ret is False, ret
    assert br.d.clicked == [] and br.d.pressed == []
    print("t_clean_screen_no_action OK")


def t_multi_rounds():
    """多轮：每轮关一个，最多 max_rounds 轮后返回 True。"""
    present = {("text", "取消"): "btn-cancel"}
    br = _mk(present=present)
    ret = br._step_dismiss_popups({"max_rounds": 3}, "X")
    assert ret is True
    assert br._clicked_labels == ["btn-cancel"] * 3, br._clicked_labels
    assert br.human.thoughts >= 3
    print("t_multi_rounds OK")


def t_sweep_disabled():
    """未启用：_popups_enabled=False 时零扫描零交互。"""
    br = _mk()
    br._popups_enabled = False
    br._maybe_sweep_popups("sign", "sign", "X")
    assert br.d.clicked == [] and br.d.pressed == []
    assert br.recorder.lines == []
    print("t_sweep_disabled OK")


def t_sweep_merge_extras():
    """_maybe_sweep_popups 合并 extra_texts/extra_ids/extra_blacklist。"""
    br = _mk()
    br._popups_enabled = True
    br._popups_cfg = {
        "enabled": True, "max_rounds": 2,
        "extra_texts": ["狠心拒绝"], "extra_ids": ["com.x.iv_close"],
        "extra_blacklist": ["零钱"],
    }
    captured = {}

    def _cap(act, app_name):
        captured.update(act)

    br._step_dismiss_popups = _cap
    br._maybe_sweep_popups("sign", "b_sign", "X")
    assert "狠心拒绝" in captured["texts"]
    assert all(t in captured["texts"] for t in DEFAULT_POPUP_TEXTS)
    assert "com.x.iv_close" in captured["ids"]
    assert "零钱" in captured["blacklist"]
    assert all(b in captured["blacklist"] for b in POPUP_BLACKLIST_TEXTS)
    assert captured["protect_ad"] is False   # sign 非 watch
    print("t_sweep_merge_extras OK")


def t_sweep_watch_flag():
    """watch intent / watch 行为 id 任一命中 -> protect_ad=True。"""
    for intent, bid in (("watch", "watch"), ("sign", "watch_ad")):
        br = _mk()
        br._popups_enabled = True
        br._popups_cfg = {"enabled": True}
        captured = {}
        br._step_dismiss_popups = lambda a, n, c=captured: c.update(a)
        br._maybe_sweep_popups(intent, bid, "X")
        assert captured["protect_ad"] is True, (intent, bid)
    print("t_sweep_watch_flag OK")


def t_dry_run_no_device():
    """dry-run：只记日志不碰设备。"""
    br = _mk()
    br.dry_run = True
    ret = br._step_dismiss_popups({"max_rounds": 3}, "X")
    assert ret is False
    assert br.d.clicked == [] and br.d.pressed == []
    assert any("dry-run" in e for _, e in br.recorder.lines)
    print("t_dry_run_no_device OK")


def t_win_wh_tuple():
    """corner 兜底坐标用 plain tuple 的 window_size（崩溃族回归）。"""
    br = _mk(xml="<node text='广告'/>", ws=(1080, 2340))
    ret = br._popup_close_one(DEFAULT_POPUP_TEXTS, [], corner=True,
                              back_key=False, app_name="X", rnd=1)
    assert ret is True
    assert br.d.clicked == [(1004, 257)], br.d.clicked
    print("t_win_wh_tuple OK")


if __name__ == "__main__":
    t_text_priority()
    t_blacklist_blocks_back()
    t_blacklist_extra_merge()
    t_watch_protects_ad()
    t_watch_protect_off()
    t_back_fallback_order()
    t_clean_screen_no_action()
    t_multi_rounds()
    t_sweep_disabled()
    t_sweep_merge_extras()
    t_sweep_watch_flag()
    t_dry_run_no_device()
    t_win_wh_tuple()
    print("ALL dismiss_popups TESTS PASSED")
