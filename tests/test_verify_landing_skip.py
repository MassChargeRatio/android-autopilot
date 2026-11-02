# -*- coding: utf-8 -*-
"""test_verify_landing_skip.py - B3 重试前先判目标页（2026-10-30 任务卡）

立卡依据：快手「立即签到」那步的 expect.phash 指向「签到前」弹窗基准图，
签到成功后弹窗内容必变（实测距离 23~27，阈值 10），于是判失败 -> 原地再点一次
-> 再等 settle -> 再判 -> 13s 白烧，且把成功记成「步骤失败」。

B3 提供通用旁路：phash 失败时若 expect.text_any 命中，视为已落地、跳过重试。
注意：**这条对快手那一步不生效**（那步没配 text_any，全项目只有 3 处配了），
快手的真修法是 retry: 0（配置），已在 config/apps/05_快手.yaml 落地。

运行：
    python tests/test_verify_landing_skip.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import landing  # noqa: E402
from behavior_runner import BehaviorRunner  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))

    def has(self, needle):
        return any(needle in e for _l, e in self.lines)


class _D:
    def __init__(self, xml):
        self._xml = xml

    def screenshot(self):
        return None

    def dump_hierarchy(self):
        return self._xml

    def app_current(self):
        return {"package": "com.smile.gifmaker"}


class _Human:
    def __init__(self):
        self.taps = []

    def tap(self, d, x, y):
        self.taps.append((x, y))


def _mk(xml):
    br = BehaviorRunner.__new__(BehaviorRunner)
    br.recorder = _Rec()
    br.dry_run = False
    br.d = _D(xml)
    br.human = _Human()
    return br


def _fake_landing(ok, calls):
    def _f(img, expect, xml=None, pkg=None):
        calls["n"] += 1
        return {"ok": ok, "signals": {}, "reason": "失败：phash", "score": 0.0}
    return _f


def t_text_any_hit_skips_retry():
    """phash 失败但 text_any 命中 -> 跳过重试，直接 True，且不再点。"""
    br = _mk('<node text="已连续签到6天"/>')
    calls = {"n": 0}
    orig = landing.check_landing
    landing.check_landing = _fake_landing(False, calls)
    try:
        act = {"expect": {"phash": "ref.png", "retry": 2,
                          "text_any": ["已连续签到", "明日再来"]}}
        ok = br._verify_landing(act, "T", x=500, y=500)
    finally:
        landing.check_landing = orig
    assert ok is True, ok
    assert calls["n"] == 1, f"应只判一次，实际 {calls['n']}"
    assert br.human.taps == [], f"不该再点，实际 {br.human.taps}"
    assert br.recorder.has("已是目标页，跳过重试"), br.recorder.lines
    print("OK  B3 text_any 命中 -> 跳过重试并返回 True")


def t_no_text_any_keeps_retry():
    """没配 text_any -> 保持原行为：重试到 retry 上限。"""
    br = _mk('<node text="别的页面"/>')
    calls = {"n": 0}
    orig = landing.check_landing
    landing.check_landing = _fake_landing(False, calls)
    try:
        act = {"expect": {"phash": "ref.png", "retry": 2}}
        ok = br._verify_landing(act, "T", x=500, y=500)
    finally:
        landing.check_landing = orig
    assert ok is False, ok
    assert calls["n"] == 3, f"retry=2 应判 3 次，实际 {calls['n']}"
    assert len(br.human.taps) == 2, br.human.taps
    print("OK  B3 无 text_any -> 保持重试（3 次判定 / 2 次重点）")


def t_text_any_miss_still_retries():
    """配了 text_any 但没命中 -> 仍按原逻辑重试。"""
    br = _mk('<node text="任务中心"/>')
    calls = {"n": 0}
    orig = landing.check_landing
    landing.check_landing = _fake_landing(False, calls)
    try:
        act = {"expect": {"phash": "ref.png", "retry": 1,
                          "text_any": ["已连续签到"]}}
        ok = br._verify_landing(act, "T", x=1, y=2)
    finally:
        landing.check_landing = orig
    assert ok is False, ok
    assert calls["n"] == 2, calls["n"]
    assert len(br.human.taps) == 1, br.human.taps
    print("OK  B3 text_any 未命中 -> 仍重试")


def t_is_target_page_quote_agnostic():
    """单双引号都能识别（真机 dump 用双引号，测试桩常用单引号）。"""
    assert BehaviorRunner._is_target_page_from_dump(
        "<node text='已连续签到5天'/>", {"text_any": ["已连续签到"]}) is True
    assert BehaviorRunner._is_target_page_from_dump(
        '<node text="已连续签到5天"/>', {"text_any": ["已连续签到"]}) is True
    assert BehaviorRunner._is_target_page_from_dump(
        '<node content-desc="明天再来"/>', {"text_any": ["明天再来"]}) is True
    assert BehaviorRunner._is_target_page_from_dump(
        '<node text="任务中心"/>', {"text_any": ["已连续签到"]}) is False
    assert BehaviorRunner._is_target_page_from_dump(
        '<node text="x"/>', {}) is False
    print("OK  B3 引号无关 + 无 text_any 时恒 False")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
