# -*- coding: utf-8 -*-
"""test_record_flow.py - 引导式录制（AUTOP-NL-2026-10-22-B 第2层）

覆盖：ui_digest / page_delta / step_to_action / steps_to_actions / guess_entry /
is_money_step / assemble_actions / machine_check / record_step（mock 设备）/ finish 合并顺序。

运行：
    ./.venv/Scripts/python.exe -m pytest tests/test_record_flow.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytest  # noqa: E402

import devtools.record_flow as rf  # noqa: E402

PKG = "com.example.app"


# ---------- 工具 ----------

def _xml(nodes, package=PKG):
    """节点 -> UI dump XML。节点键：text/desc/rid/clickable/l/t/r/b。"""
    parts = ['<?xml version="1.0" encoding="utf-8"?>', "<hierarchy>"]
    for n in nodes:
        attrs = [
            f'package="{package}"',
            f'text="{n.get("text", "")}"',
            f'content-desc="{n.get("desc", "")}"',
            f'resource-id="{n.get("rid", "")}"',
            'class="android.view.View"',
            f'clickable="{str(n.get("clickable", True)).lower()}"',
            f'bounds="[{n["l"]},{n["t"]}][{n["r"]},{n["b"]}]"',
        ]
        parts.append("<node " + " ".join(attrs) + "/>")
    parts.append("</hierarchy>")
    return "\n".join(parts)


MAIN_XML = _xml([
    {"text": "首页", "l": 0, "t": 0, "r": 200, "b": 100},
    {"text": "我的", "l": 880, "t": 2200, "r": 1080, "b": 2340},
])
SIGN_XML = _xml([
    {"text": "签到", "l": 400, "t": 900, "r": 680, "b": 1100, "clickable": True},
    {"text": "我的", "l": 880, "t": 2200, "r": 1080, "b": 2340},
])
JUMP_XML = _xml([
    {"text": "相机", "l": 100, "t": 100, "r": 300, "b": 300, "clickable": True},
], package="com.other.app")


class FakeDevice:
    """按页序返回 dump 的假设备；超界重复最后一页。"""

    def __init__(self, pages, package=PKG):
        self._pages = list(pages)
        self._idx = 0
        self.window = (1080, 2340)
        self.current = {"package": package, "activity": ".Main"}
        self.clicks = []
        self.swipes = []
        self.presses = []

    def dump_hierarchy(self):
        if not self._pages:
            return ""
        p = self._pages[min(self._idx, len(self._pages) - 1)]
        self._idx += 1
        return p

    def click(self, x, y):
        self.clicks.append((x, y))

    def swipe(self, x1, y1, x2, y2, **kw):
        self.swipes.append((x1, y1, x2, y2))

    def press(self, key):
        self.presses.append(key)

    def window_size(self):
        return self.window

    def app_current(self):
        return dict(self.current)

    def screenshot(self, path):  # pragma: no cover - 无真机不写盘
        pass


def mk_step(seq=1, cmd="点签到", verb="tap", target="签到", hit_kind="text",
            hit_value="签到", point_norm=(0.5, 0.5), delta=0.5,
            confirmed=True, **kw):
    act_before = kw.pop("act_before", ".Main")
    act_after = kw.pop("act_after", ".Sign")
    return rf.Step(seq=seq, cmd=cmd, verb=verb, target=target, pos=None,
                   hit_kind=hit_kind, hit_value=hit_value,
                   bounds=(0, 0, 100, 100), point_norm=point_norm,
                   act_before=act_before, act_after=act_after, delta=delta,
                   confirmed=confirmed, **kw)


def _no_sleep(monkeypatch):
    monkeypatch.setattr(rf.time, "sleep", lambda *a, **k: None)


# ---------- ui_digest / page_delta ----------

def t_ui_digest_order_insensitive():
    xml1 = _xml([
        {"text": "签到", "l": 10, "t": 20, "r": 30, "b": 40, "clickable": True},
        {"text": "我的", "l": 50, "t": 60, "r": 70, "b": 80},
    ])
    xml2 = _xml([
        {"text": "我的", "l": 50, "t": 60, "r": 70, "b": 80},
        {"text": "签到", "l": 10, "t": 20, "r": 30, "b": 40, "clickable": True},
    ])
    assert rf.ui_digest(xml1) == rf.ui_digest(xml2)
    assert len(rf.ui_digest(xml1)) == 2


def t_ui_digest_skips_inert_nodes():
    xml = _xml([
        {"text": "", "desc": "", "rid": "", "l": 0, "t": 0, "r": 10, "b": 10,
         "clickable": False},
        {"text": "签到", "l": 0, "t": 0, "r": 100, "b": 50, "clickable": True},
    ])
    digest = rf.ui_digest(xml)
    assert len(digest) == 1
    assert any(t == "签到" for t, _, _, _ in digest)


def t_page_delta_same_zero():
    d = rf.ui_digest(MAIN_XML)
    assert rf.page_delta(d, d) == 0.0


def t_page_delta_all_changed_one():
    a = rf.ui_digest(_xml([{"text": "A", "l": 0, "t": 0, "r": 10, "b": 10}]))
    b = rf.ui_digest(_xml([{"text": "B", "l": 0, "t": 0, "r": 10, "b": 10}]))
    assert rf.page_delta(a, b) == 1.0


def t_page_delta_both_empty_zero():
    assert rf.page_delta(frozenset(), frozenset()) == 0.0


def t_page_delta_partial_between():
    shared = {"text": "我的", "l": 880, "t": 2200, "r": 1080, "b": 2340}
    a = rf.ui_digest(_xml([shared, {"text": "首页", "l": 0, "t": 0,
                                    "r": 200, "b": 100}]))
    b = rf.ui_digest(_xml([shared, {"text": "签到", "l": 400, "t": 900,
                                    "r": 680, "b": 1100}]))
    d = rf.page_delta(a, b)
    assert 0.0 < d < 1.0


# ---------- step_to_action ----------

def t_step_to_action_text_hit():
    act = rf.step_to_action(mk_step(hit_kind="text", hit_value="签到"))
    assert act == {
        "type": "click_first",
        "candidates": [{"type": "text", "value": "签到"}],
        "timeout": 8,
        "optional": True,
    }


def t_step_to_action_desc_id_hit():
    for kind in ("desc", "id"):
        act = rf.step_to_action(mk_step(hit_kind=kind, hit_value="v"))
        assert act["type"] == "click_first"
        assert act["candidates"] == [{"type": kind, "value": "v"}]


def t_step_to_action_point_hit():
    act = rf.step_to_action(mk_step(hit_kind="point", hit_value="右下角",
                                    point_norm=(0.9, 0.88)))
    assert act["type"] == "click_point"
    assert act["x"] == 0.9 and act["y"] == 0.88
    assert act["vision"] is False


def t_step_to_action_swipe_wait_back():
    assert rf.step_to_action(mk_step(verb="swipe", target="上滑",
                                     hit_kind=None, hit_value=None)) == \
        {"type": "swipe_natural"}
    assert rf.step_to_action(mk_step(verb="wait", target="等2秒",
                                     hit_kind=None, hit_value=None)) == \
        {"type": "wait", "seconds": 2.0}
    assert rf.step_to_action(mk_step(verb="back", target="返回",
                                     hit_kind=None, hit_value=None)) == \
        {"type": "back"}


def t_step_to_action_unconfirmed_none():
    assert rf.step_to_action(mk_step(confirmed=False)) is None


def t_step_to_action_no_hit_none():
    assert rf.step_to_action(mk_step(hit_kind=None, hit_value=None)) is None


# ---------- steps_to_actions / guess_entry / money ----------

def t_steps_to_actions_drops_unconfirmed():
    steps = [mk_step(seq=1, confirmed=True), mk_step(seq=2, confirmed=False),
             mk_step(seq=3, confirmed=True, hit_kind=None, hit_value=None)]
    actions, warnings = rf.steps_to_actions(steps)
    assert len(actions) == 1
    assert any("未确认" in w for w in warnings)
    assert any("无可映射" in w for w in warnings)


def t_guess_entry_first_text_hit():
    steps = [mk_step(seq=1, hit_kind="point", hit_value="右下角"),
             mk_step(seq=2, hit_kind="text", hit_value="签到"),
             mk_step(seq=3, hit_kind="desc", hit_value="福利")]
    assert rf.guess_entry(steps) == "签到"
    assert rf.guess_entry([]) == "auto"


def t_is_money_step_true_false():
    money = {"提现", "立即提现", "转账", "支付"}
    assert rf.is_money_step(mk_step(cmd="立即提现", target="立即提现"), money)
    assert not rf.is_money_step(mk_step(cmd="点签到", target="签到"), money)


# ---------- assemble / machine_check ----------

def t_assemble_actions_hops_first():
    steps = [mk_step(seq=1, hit_kind="text", hit_value="签到")]
    hops = [{"type": "click_first",
             "candidates": [{"type": "text", "value": "我的"}],
             "timeout": 8, "optional": True}]
    actions, warnings = rf.assemble_actions(steps, hops)
    assert actions[0] == hops[0]
    assert actions[1]["candidates"][0]["value"] == "签到"
    assert warnings == []


def t_machine_check_package_jump():
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    step = mk_step(delta=0.5)
    ok, note, fatal = rec._machine_check(step, JUMP_XML, ".Main")
    assert ok is False
    assert "跳转/误触" in note
    assert fatal is False


def t_machine_check_low_delta_needs_confirm():
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    step = mk_step(delta=0.01, act_before=".Main", act_after=".Main")
    ok, note, fatal = rec._machine_check(step, MAIN_XML, ".Main")
    assert ok is False
    assert "疑似无效点击" in note
    assert fatal is False


def t_machine_check_ok():
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    ok, note, fatal = rec._machine_check(mk_step(delta=0.5), SIGN_XML, ".Main")
    assert ok is True and note == "" and fatal is False


def t_machine_check_money_fatal():
    rec = rf.FlowRecorder("七猫免费小说", PKG, allow_money=False)
    step = mk_step(cmd="立即提现", target="立即提现")
    ok, note, fatal = rec._machine_check(step, SIGN_XML, ".Main")
    assert ok is False and fatal is True
    assert "资金红线" in note


# ---------- record_step（mock 设备） ----------

def t_record_step_ok_input_y(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _p="": "y")
    dev = FakeDevice([MAIN_XML, SIGN_XML, SIGN_XML])
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    rec.d = dev
    step = rec.record_step("点签到")
    assert step is not None
    assert step.hit_kind == "text" and step.hit_value == "签到"
    assert step.confirmed is True
    assert rec.trace == [step]
    assert dev.clicks == [(540, 1000)]  # 签到节点 center


def t_record_step_package_jump_default_reject(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _p="": "n")
    dev = FakeDevice([MAIN_XML, JUMP_XML, JUMP_XML])
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    rec.d = dev
    step = rec.record_step("点相机")
    assert step is None
    assert rec.trace == []


def t_record_step_low_delta_default_reject(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _p="": "n")
    dev = FakeDevice([SIGN_XML, SIGN_XML, SIGN_XML])
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    rec.d = dev
    step = rec.record_step("点签到")
    assert step is None
    assert rec.trace == []


def t_record_step_money_rejected_without_flag(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _p="": "y")
    dev = FakeDevice([MAIN_XML, SIGN_XML, SIGN_XML])
    rec = rf.FlowRecorder("七猫免费小说", PKG, allow_money=False)
    rec.d = dev
    step = rec.record_step("立即提现")
    assert step is None
    assert rec.trace == []


def t_record_step_allow_money_keeps(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _p="": "y")
    dev = FakeDevice([MAIN_XML, SIGN_XML, SIGN_XML])
    rec = rf.FlowRecorder("七猫免费小说", PKG, allow_money=True)
    rec.d = dev
    step = rec.record_step("立即提现")
    assert step is not None
    assert rec.trace == [step]


def t_record_step_pos_click(monkeypatch):
    _no_sleep(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _p="": "y")
    dev = FakeDevice([MAIN_XML, MAIN_XML, MAIN_XML])
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    rec.d = dev
    step = rec.record_step("点右下角")
    assert step is not None
    assert step.hit_kind == "point"
    # A 卡 nl_to_steps 把「点右下角」解析为 pos=(0.9, 0.914)
    assert step.point_norm == (0.9, 0.914)
    # 1080x2340 → (972, 2138)
    assert dev.clicks == [(972, 2138)]


def t_record_step_undo_via_input(monkeypatch):
    _no_sleep(monkeypatch)
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    rec.trace = [mk_step(seq=1), mk_step(seq=2)]
    popped = rec.undo()
    assert popped.seq == 2
    assert len(rec.trace) == 1


# ---------- finish ----------

def t_finish_merge_order_hops_first(monkeypatch):
    _no_sleep(monkeypatch)
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    rec.trace = [mk_step(seq=1, hit_kind="text", hit_value="签到"),
                 mk_step(seq=2, verb="wait", target="等2秒", hit_kind=None,
                         hit_value=None)]
    captured = {}

    monkeypatch.setattr(rf, "NL_TO_STEPS_READY", True)
    monkeypatch.setattr(rf, "render_hop", lambda entry, params: [
        {"type": "click_first",
         "candidates": [{"type": "text", "value": "我的"}],
         "timeout": 8, "optional": True}])

    def fake_app_path(name, **kw):
        return "/fake/apps.yaml"

    def fake_insert(path, bid, actions, **kw):
        captured["bid"] = bid
        captured["actions"] = list(actions)
        return rf.yw.WriteResult(path, "inserted", None, "", [])

    monkeypatch.setattr(rf.yw, "app_path", fake_app_path)
    monkeypatch.setattr(rf.yw, "insert_behavior", fake_insert)

    res = rec.finish("七猫免费小说", "sign", entry="我的")
    assert res.action == "inserted"
    assert captured["bid"] == "sign"
    assert captured["actions"][0]["candidates"][0]["value"] == "我的"  # hop 在前
    assert captured["actions"][1]["candidates"][0]["value"] == "签到"  # 录制步在后
    assert captured["actions"][2] == {"type": "wait", "seconds": 2.0}


def t_finish_existing_behavior_falls_back_to_replace(monkeypatch):
    rec = rf.FlowRecorder("七猫免费小说", PKG)
    rec.trace = [mk_step(seq=1, hit_kind="text", hit_value="签到")]
    captured = {}

    def fake_app_path(name, **kw):
        return "/fake/apps.yaml"

    def fake_insert(path, bid, actions, **kw):
        return rf.yw.WriteResult(path, "skipped", None, "",
                                 ["sign 已存在；如需覆盖请用 replace_behavior(force=True)"])

    def fake_replace(path, bid, actions, **kw):
        captured["bid"] = bid
        captured["force"] = kw.get("force")
        return rf.yw.WriteResult(path, "replaced", "bak", "", [])

    monkeypatch.setattr(rf.yw, "app_path", fake_app_path)
    monkeypatch.setattr(rf.yw, "insert_behavior", fake_insert)
    monkeypatch.setattr(rf.yw, "replace_behavior", fake_replace)

    res = rec.finish("七猫免费小说", "sign", entry="auto", apply=True, force=True)
    assert res.action == "replaced"
    assert captured["bid"] == "sign"
    assert captured["force"] is True


# ---------- 2026-10-22 真机实跑修正：tap 未命中且无坐标必须拦截 ----------

def t_machine_check_rejects_missed_tap_even_when_delta_high():
    """真机踩坑：App 自身加载会造成高 delta/activity 变化，
    旧判据把「什么都没点」误判为有效点击。现在显式拦截。"""
    rec = rf.FlowRecorder.__new__(rf.FlowRecorder)
    rec.allow_money = False
    rec.money_words = set()
    step = mk_step(hit_kind=None, hit_value=None, point_norm=None,
                   delta=1.0, act_before=".Loading", act_after=".Home")
    ok, note, fatal = rec._machine_check(step, "<x/>", ".Loading")
    assert ok is False, "未定位到元素的 tap 不应通过"
    assert "未定位到元素" in note, note
    assert fatal is False
    print("OK  tap 未命中且无坐标：即使 delta=1.0 也拦截")


def t_machine_check_allows_tap_with_point_only():
    rec = rf.FlowRecorder.__new__(rf.FlowRecorder)
    rec.allow_money = False
    rec.money_words = set()
    step = mk_step(hit_kind="point", hit_value=None, point_norm=(0.5, 0.927))
    ok, _note, _fatal = rec._machine_check(step, "<x/>", ".Main")
    assert ok is True, "有坐标兜底的 tap 应放行"
    print("OK  有坐标兜底的 tap 正常放行")


def t_steps_to_actions_names_the_dropped_step():
    good = mk_step(seq=1, cmd="点福利")
    bad = mk_step(seq=2, cmd="点不存在的按钮", hit_kind=None,
                  hit_value=None, point_norm=None)
    actions, warnings = rf.steps_to_actions([good, bad])
    assert len(actions) == 1, actions
    assert any("step#2" in w and "未定位到元素" in w for w in warnings), warnings
    print("OK  steps_to_actions 告警指名到步与原因")


def t_suggest_targets_prints_clickable_texts(capsys):
    """未命中时给出当前屏可点文案，交互录制的关键提示。"""
    rec = rf.FlowRecorder.__new__(rf.FlowRecorder)
    # 注意：parse_nodes 会丢弃 y2<120 的状态栏节点，测试数据要避开
    xml = ('<h><node text="福利" clickable="true" bounds="[0,200][100,300]"/>'
           '<node text="我的" clickable="true" bounds="[0,400][100,500]"/></h>')
    rec._dump = lambda: xml
    rec._suggest_targets(limit=5)
    out = capsys.readouterr().out
    assert "福利" in out and "我的" in out and "未定位到元素" in out, out
    print("OK  未命中时打印当前屏可点文案")
