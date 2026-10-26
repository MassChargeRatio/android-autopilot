# -*- coding: utf-8 -*-
"""test_window_gate.py - 第4步：behavior 时间窗（AUTOP-SELFSEARCH-2026-10-20 第4步）

用户原话：「常用步骤的共性」——签到/领现金类行为常有时效窗口（凌晨福利、
每日首签等）。支持 behaviors[bid] 新形态：

    behaviors:
      sign:
        window: {start: "00:00", end: "06:00"}   # 可选，24 小时制
        actions: [...]                            # 动作列表（旧 list 形态兼容）

规则：
  * window 缺失 / start/end 解析失败 -> 放行（不因配置问题堵死行为）；
  * start <= end   -> 窗口内 = start <= now <= end；
  * start >  end   -> 跨午夜窗口：now >= start 或 now <= end 均算窗口内；
  * 窗口外：记 WARN「跳过(BLOCKED)」，跳过该意图，不报错、不打断流程；
  * _in_window 支持注入 now="HH:MM" 便于测试；None 取当前时间。

运行：
    python -m pytest tests/test_window_gate.py -q
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
    def delay(self, *a):
        pass

    def maybe_wander(self, *a):
        pass

    def think(self):
        pass


def _mk():
    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=True, config={})
    return ex


def t_parse_hhmm_valid_and_invalid():
    ex = _mk()
    assert ex._parse_hhmm("00:00") == 0
    assert ex._parse_hhmm("06:30") == 390
    assert ex._parse_hhmm("23:59") == 1439
    assert ex._parse_hhmm("23:59:59") == 1439
    assert ex._parse_hhmm("24:00") is None
    assert ex._parse_hhmm("6:5") is None
    assert ex._parse_hhmm("abc") is None
    assert ex._parse_hhmm(None) is None
    print("OK  _parse_hhmm 合法/非法")


def t_in_window_simple():
    ex = _mk()
    win = {"start": "00:00", "end": "06:00"}
    assert ex._in_window(win, now="00:00") is True
    assert ex._in_window(win, now="03:15") is True
    assert ex._in_window(win, now="06:00") is True
    assert ex._in_window(win, now="06:01") is False
    assert ex._in_window(win, now="12:00") is False
    assert ex._in_window(win, now="23:59") is False
    print("OK  普通窗口边界")


def t_cross_midnight_window():
    ex = _mk()
    win = {"start": "20:00", "end": "06:00"}
    assert ex._in_window(win, now="23:00") is True
    assert ex._in_window(win, now="02:00") is True
    assert ex._in_window(win, now="12:00") is False
    assert ex._in_window(win, now="19:59") is False
    print("OK  跨午夜窗口")


def t_no_window_or_bad_format_open():
    ex = _mk()
    assert ex._in_window(None, now="12:00") is True
    assert ex._in_window({}, now="12:00") is True
    assert ex._in_window({"start": "abc", "end": "xyz"}, now="12:00") is True
    assert ex._in_window({"start": "00:00", "end": "xyz"}, now="12:00") is True
    print("OK  window 缺失/解析失败均放行")


def t_behavior_actions_compat():
    ex = _mk()
    lst = [{"type": "think"}]
    assert ex._behavior_actions(lst) is lst, "list 形态原样返回"
    dct = {"window": {"start": "00:00", "end": "06:00"}, "actions": lst}
    assert ex._behavior_actions(dct) is lst, "dict 形态取 actions"
    assert ex._behavior_window(dct) == {"start": "00:00", "end": "06:00"}
    assert ex._behavior_window(lst) is None, "list 形态无 window"
    print("OK  behaviors[bid] 双形态兼容")


def t_run_app_flow_skips_blocked_dryrun():
    """dry-run：行为超窗 -> 记 BLOCKED 跳过，动作不打印，不报错。"""
    ex = _mk()
    cfg = {
        "name": "T", "package": "com.t",
        "intent_map": {"sign": "sign"},
        "behaviors": {"sign": {
            "window": {"start": "23:59", "end": "23:59"},   # 未来1分钟窗，当前必不在
            "actions": [{"type": "click_text", "text": "签到"}]}},
    }
    ex.run_app_flow(cfg, [("sign", "签到")])
    joined = "\n".join(ex.recorder.lines)
    assert "BLOCKED" in joined, joined
    # 动作行不应出现
    assert "- {\"type\": \"click_text\"" not in joined, joined
    print("OK  超窗行为被跳过（不报错、动作不打印）")


def t_run_app_flow_executes_in_window_dryrun():
    """dry-run：窗口内 -> 正常打印动作。"""
    ex = _mk()
    cfg = {
        "name": "T", "package": "com.t",
        "intent_map": {"sign": "sign"},
        "behaviors": {"sign": {
            "window": {"start": "00:00", "end": "23:59"},
            "actions": [{"type": "click_text", "text": "签到"}]}},
    }
    ex.run_app_flow(cfg, [("sign", "签到")])
    joined = "\n".join(ex.recorder.lines)
    assert "-> 行为[sign]" in joined, joined
    assert "BLOCKED" not in joined, joined
    print("OK  窗口内行为正常执行")


def t_run_app_flow_old_list_compat_dryrun():
    """dry-run：旧 list 形态（无 window）不受影响。"""
    ex = _mk()
    cfg = {
        "name": "T", "package": "com.t",
        "intent_map": {"sign": "sign"},
        "behaviors": {"sign": [{"type": "click_text", "text": "签到"}]},
    }
    ex.run_app_flow(cfg, [("sign", "签到")])
    joined = "\n".join(ex.recorder.lines)
    assert "-> 行为[sign]" in joined, joined
    assert "BLOCKED" not in joined, joined
    print("OK  旧 list 形态兼容")


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
