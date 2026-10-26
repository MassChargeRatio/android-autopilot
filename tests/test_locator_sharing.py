# -*- coding: utf-8 -*-
"""test_locator_sharing.py - A3 定位链共享件单元测试（无需真机）

覆盖：
  1. `_locate_with_kb` 的 mark_fail 触发条件：
     - has_entry=True 且 attempted=True 且定位失败 -> 计数；
     - 知识库已 disabled（cands 空，attempted=False）-> 不计数；
     - 无知识库记录（has_entry=False）-> 不计数；
  2. `_vision_or_miss` 的 desc 串透传与 allow_vision 开关。

运行：
    python -m pytest tests/test_locator_sharing.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor, LocateResult  # noqa: E402


class _Rec:
    def log(self, event, app="", level="INFO"):
        pass


class _KB:
    """记录 mark_fail / mark_ok 调用。"""
    def __init__(self):
        self.fails = []
        self.oks = []

    def mark_fail(self, app, sel):
        self.fails.append((app, sel))

    def mark_ok(self, app, sel):
        self.oks.append((app, sel))


def _mk(kb_cands, locate_result):
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex.dry_run = True
    ex.knowledge = _KB()
    if locate_result is None:
        ex._locate = lambda k, v, timeout=6.0: LocateResult(False, None, "测试未命中")
    else:
        ex._locate = lambda k, v, timeout=6.0: LocateResult(True, locate_result, "")
    ex._kb_candidates = lambda app, primary: kb_cands
    return ex


def _kb(has_entry, cands):
    return (cands, has_entry)


def test_mark_fail_trigger_conditions():
    """mark_fail 仅当 has_entry and cands（实际尝试过才计数）。"""
    # a) 有记录且启用、定位失败 -> mark_fail
    ex = _mk(_kb(True, ["text=签到", "text=去签到"]), None)
    obj, has_entry, attempted = ex._locate_with_kb("T", "text=签到", 2.0)
    assert obj is None and has_entry and attempted
    assert ("T", "text=签到") in ex.knowledge.fails, ex.knowledge.fails
    print("OK  has_entry+attempted+失败 -> mark_fail")

    # b) 记录已 disabled（cands 空）-> 不计数
    ex = _mk(_kb(True, []), None)
    obj, has_entry, attempted = ex._locate_with_kb("T", "text=签到", 2.0)
    assert obj is None and has_entry and not attempted
    assert ex.knowledge.fails == [], ex.knowledge.fails
    print("OK  disabled（attempted=False）-> 不 mark_fail")

    # c) 无知识库记录 -> 不计数
    ex = _mk(_kb(False, ["text=签到"]), None)
    obj, has_entry, attempted = ex._locate_with_kb("T", "text=签到", 2.0)
    assert obj is None and not has_entry
    assert ex.knowledge.fails == [], ex.knowledge.fails
    print("OK  无记录（has_entry=False）-> 不 mark_fail")

    # d) 命中时即使 has_entry 也不 mark_fail，而是 mark_ok
    ex = _mk(_kb(True, ["text=签到"]), object())
    obj, has_entry, attempted = ex._locate_with_kb("T", "text=签到", 2.0)
    assert obj is not None
    assert ex.knowledge.fails == []
    print("OK  命中分支不 mark_fail")


def test_vision_or_miss_desc_passthrough():
    """desc 串原样透传给 _vision_click；allow_vision=False 时完全不调用。"""
    seen = []

    def fake_vision(act, app, desc):
        seen.append((app, desc))
        return True

    ex = Executor.__new__(Executor)
    ex._vision_click = fake_vision
    act = {"type": "click_desc", "desc": "我的"}
    ok = ex._vision_or_miss(act, "T", "click_desc[我的]", allow_vision=True)
    assert ok is True
    assert seen == [("T", "click_desc[我的]")], seen
    print("OK  desc 串 click_desc[我的] 原样透传")

    seen.clear()
    ex = Executor.__new__(Executor)
    ex._vision_click = fake_vision
    ok = ex._vision_or_miss(act, "T", "click_first[all-candidates]",
                            allow_vision=False)
    assert ok is False and seen == [], seen
    print("OK  allow_vision=False 时跳过视觉兜底")
