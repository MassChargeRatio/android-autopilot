# -*- coding: utf-8 -*-
"""test_landing_structure_change.py - 落地校验「结构变化」兜底（2026-10-30）

立卡依据（34 App 全量跑）：落地校验失败 15 次，其中 **phash 11 次**（UC、今日头条极速版、
大众点评、快手、红果、美团），text_nodes 4 次（京东、美团）。

phash 的机制性问题：基准图是「点击前」那一态，点击后页面必然变样 —— 必然失配。
UC 是最干净的证据：step1 phash 失配 dist=30/34 判失败，紧接着 step3 用另一张基准图
dist=8 通过 —— 说明 step1 其实已经落到任务页了，是**校验判错**，不是点击没生效。

修复口径（默认关闭，按步骤显式开启）：
  expect.accept_structure_change: true
  expect.structure_change_min: 0.15      # 节点集合 Jaccard 差异度阈值
只在 **phash 失配** 时兜底，且要求页面节点结构确实变了。
**不救 text_nodes 失配** —— 文案没出现是有效信号，不能靠「页面变了」放行。

运行：
    python tests/test_landing_structure_change.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import landing  # noqa: E402
from behavior_runner import BehaviorRunner  # noqa: E402

BEFORE = ('<node text="首页" bounds="[0,0][1080,200]"/>'
          '<node text="推荐" bounds="[0,200][540,300]"/>'
          '<node text="视频" bounds="[540,200][1080,300]"/>'
          '<node text="我的" bounds="[0,2100][540,2340]"/>')
AFTER = ('<node text="任务中心" bounds="[0,0][1080,200]"/>'
         '<node text="签到领金币" bounds="[0,200][540,300]"/>'
         '<node text="看视频赚金币" bounds="[540,200][1080,300]"/>'
         '<node text="提现" bounds="[0,2100][540,2340]"/>')


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
        return {"package": "x"}


class _Human:
    def __init__(self):
        self.taps = []

    def tap(self, d, x, y):
        self.taps.append((x, y))

    def jitter_point(self, x, y):
        return x, y


def _mk(xml):
    br = BehaviorRunner.__new__(BehaviorRunner)
    br.recorder = _Rec()
    br.dry_run = False
    br.d = _D(xml)
    br.human = _Human()
    br._last_fail = ""
    return br


def _landing_fail(phash=False, text=False):
    def _f(img, expect, xml=None, pkg=None):
        sig = {}
        if phash:
            sig["phash"] = False
        if text:
            sig["text_nodes"] = False
        return {"ok": False, "signals": sig, "reason": "失败：" +
                ",".join(sig), "score": 0.0}
    return _f


def _run(expect, xml_after, phash=False, text=False):
    br = _mk(xml_after)
    orig = landing.check_landing
    landing.check_landing = _landing_fail(phash=phash, text=text)
    try:
        act = {"expect": expect}
        return br, br._verify_landing(act, "T", x=1, y=2,
                                      nodes_before=BehaviorRunner._screen_nodes(BEFORE))
    finally:
        landing.check_landing = orig


def t_phash_fail_structure_changed_passes():
    """phash 失配 + 结构大变 + 开关打开 -> 判为已落地。"""
    br, ok = _run({"phash": "ref.png", "retry": 2,
                   "accept_structure_change": True}, AFTER, phash=True)
    assert ok is True, ok
    assert br.recorder.has("页面结构已变化"), br.recorder.lines
    assert br.human.taps == [], "不该再重试点击"
    print("OK  phash 失配 + 结构变化 -> 判已落地，且不重试")


def t_phash_fail_structure_same_still_fails():
    """phash 失配但结构没变 -> 仍然失败（不能凭白放行）。"""
    br, ok = _run({"phash": "ref.png", "retry": 0,
                   "accept_structure_change": True}, BEFORE, phash=True)
    assert ok is False, ok
    assert br.recorder.has("结构仅变"), br.recorder.lines
    print("OK  phash 失配 + 结构没变 -> 仍判失败")


def t_switch_off_by_default():
    """没写 accept_structure_change -> 行为与改前一致（结构变了也判失败）。"""
    br, ok = _run({"phash": "ref.png", "retry": 0}, AFTER, phash=True)
    assert ok is False, ok
    print("OK  默认关闭：结构变化不改变结论（老配置零影响）")


def t_text_nodes_fail_not_rescued():
    """text_nodes 失配 **不** 被结构变化兜底 —— 文案没出现是有效信号。"""
    br, ok = _run({"text_any": ["赚现金"], "retry": 0,
                   "accept_structure_change": True}, AFTER, text=True)
    assert ok is False, ok
    print("OK  text_nodes 失配不被兜底（京东/美团那种不救）")


def t_threshold_configurable():
    """structure_change_min 可调：阈值设到 1.01 时永不通过。"""
    br, ok = _run({"phash": "ref.png", "retry": 0,
                   "accept_structure_change": True,
                   "structure_change_min": 1.01}, AFTER, phash=True)
    assert ok is False, ok
    print("OK  structure_change_min 生效（1.01 永不通过）")


def t_structure_diff_math():
    """Jaccard 差异度：同一集合 0，无交集 1，空集 0（不误判）。"""
    a = BehaviorRunner._screen_nodes(BEFORE)
    assert BehaviorRunner._structure_diff(a, a) == 0.0
    assert BehaviorRunner._structure_diff(a, frozenset()) == 0.0
    b = frozenset({("完全不", "同的节点", "[0,0][1,1]")})
    assert BehaviorRunner._structure_diff(a, b) == 1.0
    print("OK  _structure_diff：同=0 / 空=0 / 无交集=1")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
