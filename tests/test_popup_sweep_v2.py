# -*- coding: utf-8 -*-
"""test_popup_sweep_v2.py - 弹窗清扫 v2 回归钉（2026-10-30 任务卡）

立卡依据（真机一手）：快手「签到」103s，其中弹窗清扫 3 轮盲点右上角 (1004,257)
空转 37s，什么都没关掉；落地校验无效重试 13s。

本文件钉住四条：
  A1  _popup_close_one 不再自己 dump（调用方传入 xml）
  A2  每个关闭动作后比屏幕指纹，没变立刻退出，不空转到 max_rounds
  A4  per-app close_points 按序尝试，优先于盲点 corner
  C1  corner 整次清扫最多触发一次（第 2 轮起禁用），且禁用后绝不落到 BACK

注意 A3 的取舍：原方案想用 `class="android.app.Dialog"` 做判据，但项目里
63 份真机 dump 中含该 class 的是 **0 份**（含 PopupWindow 也是 0），
判据会永远不命中 = 静默关掉 corner。故不采用，改为「corner 只用一次」。

运行：
    python tests/test_popup_sweep_v2.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from behavior_runner import BehaviorRunner  # noqa: E402

AD_XML = "<node text='广告'/><node text='下载'/>"


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))

    def has(self, needle):
        return any(needle in e for _l, e in self.lines)


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


class _D:
    def __init__(self, ws=(1080, 2340)):
        self._ws = ws
        self.clicked = []
        self.pressed = []

    def window_size(self):
        return self._ws

    def click(self, x, y):
        self.clicked.append((x, y))

    def press(self, key):
        self.pressed.append(key)


def _mk(present=None, xml="", ws=(1080, 2340)):
    br = BehaviorRunner.__new__(BehaviorRunner)
    br.recorder = _Rec()
    br.human = _Human()
    br.d = _D(ws)
    br.dry_run = False
    present = present or {}
    seq = list(xml) if isinstance(xml, list) else [xml]
    br._dump_calls = 0

    def _dump_safe():
        br._dump_calls += 1
        if len(seq) > 1:
            return seq.pop(0)
        return seq[0] if seq else ""

    def _locate(kind, value, timeout=6.0):
        if (kind, value) in present:
            return type("R", (), {"hit": True,
                                  "obj": _Obj(present[(kind, value)])})()
        return type("R", (), {"hit": False, "obj": None})()

    br._clicked_labels = []
    br._dump_safe = _dump_safe
    br._locate = _locate
    br._click_obj = lambda o: br._clicked_labels.append(o.label)
    return br


# ---------- A1：干净屏那一轮只 dump 一次 ----------

def t_a1_clean_screen_single_dump():
    """干净屏（无文案/id、无广告特征）：1 次 dump 就退出。

    改前是 2 次（_step_dismiss_popups 一次 + _popup_close_one 内部一次）。
    """
    br = _mk(xml="<node text='签到领金币'/>")
    ret = br._step_dismiss_popups({"max_rounds": 3}, "X")
    assert ret is False, ret
    assert br._dump_calls == 1, f"A1 违规：干净屏应只 dump 1 次，实际 {br._dump_calls}"
    print("OK  A1 干净屏 1 次 dump 即退出（改前 2 次）")


def t_a1_acted_round_two_dumps():
    """有动作的轮次 = 前后各 1 次（共 2 次）——A2 的代价，如实钉住。

    不假装"每轮都只 dump 一次"：A2 必须拿到动作后的屏幕才能判断变没变。
    """
    br = _mk(present={("text", "取消"): "btn"},
             xml=["<node text='取消'/>", "<node text='取消'/><node text='b'/>"])
    br._step_dismiss_popups({"max_rounds": 1}, "X")
    assert br._dump_calls == 2, f"应为 2 次（动作前/后各一），实际 {br._dump_calls}"
    print("OK  A1 有动作的轮次 2 次 dump（前后各一）")


# ---------- A2：屏幕没变立即退出 ----------

def t_a2_no_change_exits_after_one_round():
    """点了文案但屏幕不变 -> 第 1 轮就退出，不再打第 2、3 轮。"""
    br = _mk(present={("text", "取消"): "btn"},
             xml="<node text='取消'/>")          # 恒等，模拟点了没反应
    ret = br._step_dismiss_popups({"max_rounds": 3}, "X")
    assert ret is False, ret
    assert br._clicked_labels == ["btn"], br._clicked_labels
    assert br.recorder.has("屏幕无变化"), br.recorder.lines
    print("OK  A2 屏幕不变 -> 1 轮退出并记 WARN")


def t_a2_change_continues():
    """屏幕每轮都变 -> 正常跑满 max_rounds。"""
    br = _mk(present={("text", "取消"): "btn"},
             xml=[f"<node text='取消'/><node text='{i}'/>" for i in range(4)])
    ret = br._step_dismiss_popups({"max_rounds": 2}, "X")
    assert ret is True, ret
    assert len(br._clicked_labels) == 2, br._clicked_labels
    print("OK  A2 屏幕有变化 -> 跑满 2 轮")


def t_a2_fingerprint_is_deterministic():
    """指纹用 md5，不是内置 hash()：同一份 xml 恒定，跨进程可复现。"""
    a = BehaviorRunner._screen_fingerprint("<node text='x' bounds='[0,0][1,1]'/>")
    b = BehaviorRunner._screen_fingerprint("<node text='x' bounds='[0,0][1,1]'/>")
    c = BehaviorRunner._screen_fingerprint("<node text='y' bounds='[0,0][1,1]'/>")
    assert a == b and a != c, (a, b, c)
    assert a != 0
    print("OK  A2 指纹确定性（md5），内容不同则不同")


# ---------- A4：close_points 优先于 corner ----------

def t_a4_close_points_before_corner():
    br = _mk(xml=[AD_XML, AD_XML + "<node text='z'/>"])
    ret = br._step_dismiss_popups({
        "max_rounds": 1, "corner_fallback": True,
        "close_points": [{"x": 0.910, "y": 0.195, "desc": "瓜分弹窗X"}],
    }, "X")
    assert ret is True, ret
    assert br.d.clicked == [(int(1080 * 0.910), int(2340 * 0.195))], br.d.clicked
    assert br.recorder.has("close_points"), br.recorder.lines
    print("OK  A4 close_points 命中，不走 corner")


def t_a4_invalid_close_points_fall_to_corner():
    """close_points 全非法 -> 退回 corner（第 1 轮仍允许）。"""
    br = _mk(xml=[AD_XML, AD_XML + "<node text='z'/>"])
    ret = br._step_dismiss_popups({
        "max_rounds": 1, "corner_fallback": True,
        "close_points": [{"x": None}, {}, "not-a-dict"],
    }, "X")
    assert ret is True, ret
    x, y = br.d.clicked[0]
    assert abs(x - 1080 * 0.93) < 2 and abs(y - 2340 * 0.11) < 2, (x, y)
    print("OK  A4 close_points 全非法 -> 退回 corner")


def t_a4_first_valid_only():
    """多个 close_points 只点第一个有效的。"""
    br = _mk(xml=[AD_XML, AD_XML + "<node text='z'/>"])
    br._step_dismiss_popups({
        "max_rounds": 1,
        "close_points": [{"x": 0.5, "y": 0.5, "desc": "first"},
                         {"x": 0.9, "y": 0.1, "desc": "second"}],
    }, "X")
    assert br.d.clicked == [(540, 1170)], br.d.clicked
    print("OK  A4 多 close_points 只点第一个")


# ---------- C1：corner 整次最多一次，禁用后不落到 BACK ----------

def t_c1_corner_only_once_per_sweep():
    """第 1 轮 corner 触发；第 2 轮即使还在广告页也不许再打同一个点。"""
    # 第 1 轮前后都变（继续），第 2 轮也变（继续），第 3 轮变 -> 3 轮但 corner 只 1 次
    xmls = [AD_XML, AD_XML + "<node text='1'/>",
            AD_XML + "<node text='1'/>", AD_XML + "<node text='2'/>",
            AD_XML + "<node text='2'/>", AD_XML + "<node text='3'/>"]
    br = _mk(xml=xmls)
    br._step_dismiss_popups({"max_rounds": 3, "corner_fallback": True}, "X")
    assert len(br.d.clicked) == 1, f"corner 只许 1 次，实际 {br.d.clicked}"
    print("OK  C1 corner 整次清扫最多 1 次")


def t_c1_no_back_after_corner_disabled():
    """corner 被禁用（第 2 轮起）时绝不下落到 BACK——干净屏按 BACK 会退出 App。"""
    xmls = [AD_XML, AD_XML + "<node text='1'/>",
            AD_XML + "<node text='1'/>", AD_XML + "<node text='2'/>"]
    br = _mk(xml=xmls)
    br._step_dismiss_popups({"max_rounds": 2, "corner_fallback": True,
                             "back_key": True}, "X")
    assert br.d.pressed == [], f"不许按 BACK，实际 {br.d.pressed}"
    print("OK  C1 corner 禁用后不落到 BACK")


def t_c1_video_feed_one_click_total():
    """快手首页形态（广告词一堆、无弹窗）：整次清扫最多 1 次盲点，然后退出。

    改前是连打 3 轮 = 37s。
    """
    br = _mk(xml=AD_XML)          # 恒等，点了没反应
    ret = br._step_dismiss_popups({"max_rounds": 3, "corner_fallback": True}, "X")
    assert ret is False, ret
    assert len(br.d.clicked) == 1, br.d.clicked
    print("OK  C1 视频流首页：1 次盲点 + 屏幕无变化即退出（改前 3 次/37s）")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
