# -*- coding: utf-8 -*-
"""test_selfsearch_inject.py - 第5步：click_first 自搜寻注入（AUTOP-SELFSEARCH-2026-10-20）

用户原话：「使程序自己有一套思路，不用依赖外部描述而能自己搜寻」。
第5步把全局词表接进引擎执行路径：

  * `candidates_from: sign|task_center|nav_tab|withdraw`：
    显式 candidates 优先（精确定向），全局词表（+ App 级 extra_candidates）
    按序追加兜底（自搜寻）。candidates 可省略——纯词表即为纯自搜寻；
  * `zone: tab_zone|top_right|right_edge`：
    click_first 定位透传位置先验（多匹配时底部带/右上/右缘加分）。

规则：
  * 显式候选与词表重复 -> 去重（词表不重复注入同一 (kind,value)）；
  * 词表注入同样走知识库过滤（disabled 候选跳过）；
  * 未知 candidates_from 分类 -> WARN 忽略，不中断；
  * zone 只透传不改变无 zone 的既有行为（默认 None）。

运行：
    python -m pytest tests/test_selfsearch_inject.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor, LocateResult  # noqa: E402


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

    def natural_swipe(self, d):
        pass


class _HitList:
    """按 value 命中的 _locate 桩：记录收到的 (kind, value, zone)。"""

    def __init__(self, hits):
        self.hits = set(hits)      # 命中的 value 集合
        self.calls = []            # (kind, value, zone)

    def __call__(self, k, v, timeout=2.0, zone=None, screen_w=0):
        self.calls.append((k, v, zone))
        if v in self.hits:
            return LocateResult(True, {"kind": k, "value": v}, "测试命中")
        return LocateResult(False, None, "测试未命中")


def _mk(script):
    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=True, config={})
    ex.dry_run = False
    ex._locate = script
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    ex._click_obj = lambda obj, relocate=None: None
    ex._app_extras = lambda app: {}
    return ex


def t_candidates_from_falls_back_to_global():
    """显式候选未命中 -> 全局词表兜底命中（自搜寻）。"""
    # 显式「今日签到」不在屏上，全局表里的「立即签到」在屏上
    script = _HitList({"立即签到"})
    ex = _mk(script)
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "今日签到"}],
           "candidates_from": "sign"}
    assert ex._step_click_first(act, "T") is True
    values = [c[1] for c in script.calls]
    assert "今日签到" in values and "立即签到" in values, values
    print("OK  显式未命中后全局词表兜底命中")


def t_candidates_from_pure_selfsearch():
    """无显式 candidates：纯 candidates_from 即为自搜寻。"""
    script = _HitList({"签到领元宝"})
    ex = _mk(script)
    act = {"type": "click_first", "candidates_from": "sign"}
    assert ex._step_click_first(act, "T") is True
    assert ("text", "签到领元宝") in [(c[0], c[1]) for c in script.calls]
    print("OK  纯 candidates_from 自搜寻命中")


def t_explicit_wins_before_global_dup_dedup():
    """显式候选在词表之前被尝试；重复词不二次注入。"""
    script = _HitList({"今日签到"})
    ex = _mk(script)
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "今日签到"}],
           "candidates_from": "sign"}
    assert ex._step_click_first(act, "T") is True
    # 首轮即命中：不应再去试词表里的「今日签到」
    assert script.calls == [("text", "今日签到", None)], script.calls
    print("OK  显式优先且重复词去重")


def t_unknown_category_warn_and_ignore():
    """未知 candidates_from -> WARN 忽略，仍走显式候选。"""
    script = _HitList({"今日签到"})
    ex = _mk(script)
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "今日签到"}],
           "candidates_from": "bogus"}
    assert ex._step_click_first(act, "T") is True
    assert any("未知 candidates_from" in l for l in ex.recorder.lines), \
        ex.recorder.lines
    print("OK  未知分类 WARN 忽略不中断")


def t_app_extra_candidates_injected():
    """App 级 extra_candidates 参与词表注入（不重复已有全局词）。"""
    script = _HitList({"独家签到"})
    ex = _mk(script)
    ex._app_extras = lambda app: {"sign": ["独家签到", "今日签到"]}
    act = {"type": "click_first", "candidates_from": "sign"}
    assert ex._step_click_first(act, "T") is True
    values = [c[1] for c in script.calls]
    assert "独家签到" in values, values
    assert values.count("今日签到") == 1, "全局+extra 重复词应去重"
    print("OK  App 级 extra_candidates 注入且去重")


def t_zone_passed_to_locate():
    """zone 透传：click_first 定位带 zone（tab_zone 底部带优先）。"""
    script = _HitList({"任务"})
    ex = _mk(script)
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "任务"}],
           "zone": "tab_zone"}
    assert ex._step_click_first(act, "T") is True
    assert script.calls == [("text", "任务", "tab_zone")], script.calls
    print("OK  zone 透传定位")


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
