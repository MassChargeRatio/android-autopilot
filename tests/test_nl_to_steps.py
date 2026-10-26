# -*- coding: utf-8 -*-
"""test_nl_to_steps.py - 自然语言→动作链 YAML（AUTOP-NL-2026-10-22-A 第1层）

锁定契约（全部纯函数，不碰文件不碰设备）：
  * parse_line/parse_script：动词识别（长词优先）、位置词、中文/数字时长、
    多句拆分、unknown 不抛异常；
  * guess_entry 三分支；
  * render_chain 结构：每 hop 独立 any_of；文案支 click_first(optional=False)
    与坐标支 click_point(vision=False) 分属两个 choice；tab 跳显式
    candidates_from=nav_tab + zone=tab_zone；
  * --h5：坐标支 1 点 -> wait1.5 + 第二点 y 偏移 offset/2340；
  * 缺 *_xy：只出文案支 + warning「缺坐标兜底，建议真机校准后补」，绝不猜坐标；
  * 词表门禁：源码无中文词表字面量 + candidates.candidates_for 是唯一词表来源；
  * 幂等：同输入两次 build_behavior 深相等；
  * round-trip：yaml.safe_load(to_yaml_fragment(actions)) == actions
    （含全角冒号、+、%）。

运行：./.venv/Scripts/python.exe -m pytest tests/test_nl_to_steps.py -q
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

import devtools.nl_to_steps as n  # noqa: E402


# ---------- parse_line / parse_script ----------

def test_parse_line_tap_with_pos():
    steps, w = n.parse_line("点右下角我的")
    assert w == []
    assert len(steps) == 1
    st = steps[0]
    assert st["verb"] == "tap"
    assert st["target"] == "我的"
    assert st["pos"] == (0.90, 0.914)


def test_parse_line_tap_quoted():
    steps, _ = n.parse_line("点击「立即签到」")
    st = steps[0]
    assert st["verb"] == "tap"
    assert st["target"] == "立即签到"
    assert st["pos"] is None


def test_parse_line_wait_digits():
    steps, _ = n.parse_line("等3秒")
    st = steps[0]
    assert st["verb"] == "wait"
    assert st["seconds"] == 3.0
    assert st["target"] is None


def test_parse_line_wait_cn_and_half_minute():
    st, _ = n.parse_line("等三秒")
    assert st[0]["verb"] == "wait" and st[0]["seconds"] == 3.0
    st, _ = n.parse_line("等半分钟")
    assert st[0]["verb"] == "wait" and st[0]["seconds"] == 30.0
    assert n._cn_number("五秒") == 5.0
    assert n._cn_number("十秒") == 10.0
    assert n._cn_number("看不懂") is None


def test_parse_line_swipe_twice():
    steps, _ = n.parse_line("上滑两次")
    st = steps[0]
    assert st["verb"] == "swipe"
    assert st.get("count") == 2
    assert st["pos"] is None


def test_parse_line_swipe_down():
    st, _ = n.parse_line("下滑")
    assert st[0]["verb"] == "swipe"


def test_parse_script_multi():
    steps, w = n.parse_script("点我的，然后点福利中心，最后点签到")
    assert w == []
    assert len(steps) == 3
    assert [s["target"] for s in steps] == ["我的", "福利中心", "签到"]
    assert all(s["verb"] == "tap" for s in steps)


def test_parse_line_unknown_no_raise():
    steps, w = n.parse_line("随便什么没有动词")
    assert len(steps) == 1
    assert steps[0]["verb"] == "unknown"
    assert len(w) == 1 and "无法识别动词" in w[0]


def test_parse_line_back():
    st, _ = n.parse_line("返回")
    assert st[0]["verb"] == "back"


# ---------- guess_entry / templates ----------

def test_guess_entry_personal_center():
    assert n.guess_entry("点我的，点福利中心") == "personal_center"
    assert n.guess_entry("进入个人中心") == "personal_center"


def test_guess_entry_feed_ball():
    assert n.guess_entry("点右上角金币") == "feed_ball"
    assert n.guess_entry("点浮球") == "feed_ball"


def test_guess_entry_home_direct():
    assert n.guess_entry("点签到") == "home_direct"
    assert n.guess_entry("") == "home_direct"


def test_template_names():
    assert n.template_names() == ["personal_center", "feed_ball", "home_direct"]


# ---------- render_chain 结构 ----------

def test_render_chain_personal_structure():
    params = {"tab_xy": (0.9, 0.914), "hub_xy": (0.3, 0.5), "sign_xy": (0.5, 0.641)}
    actions, w = n.render_chain("personal_center", params, "sign")
    assert w == []
    hops = [a for a in actions if a.get("type") == "any_of"]
    assert len(hops) == 3  # tab / hub / sign

    tab, hub, sign = hops
    # tab：文案支 click_first（optional False、candidates_from nav_tab、zone tab_zone）
    assert tab["choices"][0][0]["type"] == "click_first"
    assert tab["choices"][0][0]["optional"] is False
    assert tab["choices"][0][0]["candidates_from"] == "nav_tab"
    assert tab["choices"][0][0]["zone"] == "tab_zone"
    # tab：坐标支 click_point（vision False），与文案支分属两个 choice
    assert tab["choices"][1][0]["type"] == "click_point"
    assert tab["choices"][1][0]["vision"] is False
    # hub：candidates_from task_center、无 zone
    assert hub["choices"][0][0]["candidates_from"] == "task_center"
    assert "zone" not in hub["choices"][0][0]
    # sign：candidates_from sign
    assert sign["choices"][0][0]["candidates_from"] == "sign"
    # 坐标支不复制后续步骤
    for hop in hops:
        assert len(hop["choices"][1]) == 1


def test_render_chain_h5_offset():
    params = {"sign_xy": (0.5, 0.641)}
    actions, _ = n.render_chain("home_direct", params, "sign")
    sign = actions[-1]
    assert len(sign["choices"][1]) == 1  # 默认单点
    assert sign["choices"][1][0]["type"] == "click_point"

    params2 = dict(params)
    params2["h5"] = True
    params2["h5_offset"] = 60.0
    actions2, _ = n.render_chain("home_direct", params2, "sign")
    sign2 = actions2[-1]
    pts = [a for a in sign2["choices"][1] if a["type"] == "click_point"]
    assert len(pts) == 2  # h5：2 个 click_point
    assert pts[1]["y"] == round(0.641 + 60.0 / 2340.0, 6)
    assert sign2["choices"][1][1]["type"] == "wait"
    assert sign2["choices"][1][1]["seconds"] == 1.5


def test_render_chain_missing_xy_warning():
    actions, w = n.render_chain("personal_center", {}, "sign")
    assert len(w) == 3
    assert all("缺坐标兜底，建议真机校准后补" in x for x in w)
    for a in actions:
        assert a["type"] == "any_of"
        assert len(a["choices"]) == 1  # 只出文案支，绝不猜坐标


def test_render_chain_scroll_confirm():
    params = {"sign_xy": (0.5, 0.641), "scroll_text": "签到", "confirm_text": "确认领取"}
    actions, _ = n.render_chain("personal_center", params, "sign")
    types = [a["type"] for a in actions]
    assert types == ["any_of", "any_of", "scroll_to", "any_of", "click_first"]
    assert actions[2]["text"] == "签到"
    assert actions[-1]["type"] == "click_first"
    assert actions[-1]["candidates"][0]["value"] == "确认领取"
    assert actions[-1]["optional"] is True


# ---------- 词表门禁 ----------

def test_vocab_gate_source():
    src = inspect.getsource(n)
    for banned in ("今日签到", "立即签到", "任务中心"):
        assert banned not in src


def test_vocab_gate_candidates_single_source(monkeypatch):
    calls = []

    def fake_candidates_for(category, app_cfg=None):
        calls.append(category)
        return [f"w_{category}_x"]

    monkeypatch.setattr(n.candidates, "candidates_for", fake_candidates_for)
    r = n.build_behavior("点我的，点福利中心，点签到", "A", "sign",
                         params={"tab_xy": "0.9,0.914",
                                 "hub_xy": "0.3,0.5",
                                 "sign_xy": "0.5,0.641"})
    assert "nav_tab" in calls and "task_center" in calls and "sign" in calls
    assert r["candidates_used"]["sign"] == ["w_sign_x"]
    # 动作链里只有 candidates_from，不含字面候选词
    for a in r["actions"]:
        for choice in a.get("choices", []):
            assert "candidates" not in choice[0]


# ---------- 幂等 / round-trip ----------

def test_build_behavior_idempotent():
    kw = dict(params={"tab_xy": "0.9,0.914", "hub_xy": "0.3,0.5",
                      "sign_xy": "0.5,0.641"})
    r1 = n.build_behavior("点我的，点福利中心，点签到", "A", "sign", **kw)
    r2 = n.build_behavior("点我的，点福利中心，点签到", "A", "sign", **kw)
    assert r1 == r2
    assert r1["behavior"] == "sign"
    assert r1["entry"] == "personal_center"


def test_build_behavior_auto_entry():
    r = n.build_behavior("点我的，点福利中心，点签到", "A", "sign")
    assert r["entry"] == "personal_center"
    r2 = n.build_behavior("点右上角金币，点签到", "A", "sign")
    assert r2["entry"] == "feed_ball"
    r3 = n.build_behavior("点签到", "A", "sign")
    assert r3["entry"] == "home_direct"


def test_to_yaml_fragment_roundtrip():
    actions = n.build_behavior(
        "点我的，点福利中心，点签到", "A", "sign",
        params={"tab_xy": "0.9,0.914", "hub_xy": "0.3,0.5",
                "sign_xy": "0.5,0.641"})["actions"]
    frag = n.to_yaml_fragment(actions)
    loaded = yaml.safe_load(frag)
    assert loaded == actions


def test_to_yaml_fragment_special_chars_roundtrip():
    actions = [{
        "type": "click_first",
        "candidates": [
            {"type": "text", "value": "测试：全角冒号＋百分号%100"},
            {"type": "text", "value": "x+y 加号"},
        ],
        "candidates_from": "sign",
        "timeout": 8,
        "optional": False,
    }]
    frag = n.to_yaml_fragment(actions)
    assert yaml.safe_load(frag) == actions


# ---------- render_steps（自由解析兜底入口） ----------

def test_render_steps_basic():
    steps, w = n.parse_script("点我的，等2秒，上滑两次")
    actions, w2 = n.render_steps(steps, {}, "sign")
    assert w == [] and w2 == []
    assert [a["type"] for a in actions] == ["click_first", "wait", "swipe", "swipe"]
    assert actions[0]["candidates"][0]["value"] == "我的"
    assert actions[1]["seconds"] == 2.0


def test_render_steps_unknown_warning():
    steps, w = n.parse_line("随便乱写")
    assert steps[0]["verb"] == "unknown"
    actions, w2 = n.render_steps(steps, {}, "sign")
    assert actions == []
    assert len(w2) == 1 and "无法识别" in w2[0]
