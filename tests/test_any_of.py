# -*- coding: utf-8 -*-
"""test_any_of.py - Executor._step_any_of 单元测试（无需真机）

背景：App 落地页不确定（开屏广告/活动弹窗/新手引导/上次退出的 tab/登录态），
同一行为的入口可能在首屏、也可能只在二级页。写死前置步会堵死首屏路径，
只写首屏锚点又会在页面漂移时全灭。`any_of` 让多条路径共存。

这里覆盖它的关键语义：
  1. 分支按顺序尝试，第一组**全部动作成功**即停，后续分支不执行；
  2. `optional: true` 的定位动作「没找到」返回 False（不是 None/异常），
     必须被识别为分支未命中 —— 否则任何分支都会"成功"，any_of 形同虚设；
  3. 分支内某步抛 StepError → 该分支判失败，且**后续步骤不执行**；
  4. 全部分支未命中时：optional 放行返回 False，否则 WARN 返回 False；
  5. 视觉门控是显式参数链：只有最后一个分支 allow_vision=True
     （B7 教训：早期用 `_probe_no_vision` 实例标志位临时改写再还原，
     异常/新增直调点会留下脏状态，测试只能靠反证用例兜底；现改为
     `allow_vision` 参数显式贯穿，反证用例随之取消）。

运行：
    python tests/test_any_of.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor, StepError, LocateResult  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append(f"[{level}] {event}")


def _mk(fake_probe):
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex._dispatch_probe = fake_probe
    return ex


def _scripted(mapping, calls):
    """构造一个按 (type, tag) 返回 True/False/抛异常的假 _dispatch_probe。

    mapping: {(type, tag): True|False|"raise"}
    calls:   调用记录列表，元素为 (type, tag)
    """
    def fake(act, app_name, allow_vision):
        key = (act.get("type"), act.get("tag"))
        calls.append(key)
        res = mapping.get(key, True)
        if res == "raise":
            raise StepError(f"模拟失败 {key}")
        return bool(res)
    return fake


# ---------- 用例 ----------

def t_first_branch_wins():
    """第一分支命中即停，第二分支不应被执行。"""
    calls = []
    ex = _mk(_scripted({("a", 1): True, ("b", 1): True}, calls))
    act = {"type": "any_of", "choices": [
        [{"type": "a", "tag": 1}],
        [{"type": "b", "tag": 1}],
    ]}
    assert ex._step_any_of(act, "T") is True
    assert calls == [("a", 1)], calls
    print("OK  第一分支命中即停，后续分支不执行")


def t_fallback_to_second_branch():
    """第一分支未命中（定位动作返回 False）→ 继续试第二分支。"""
    calls = []
    ex = _mk(_scripted({("a", 1): False, ("b", 1): True}, calls))
    act = {"type": "any_of", "choices": [
        [{"type": "a", "tag": 1}],
        [{"type": "b", "tag": 1}],
    ]}
    assert ex._step_any_of(act, "T") is True
    assert calls == [("a", 1), ("b", 1)], calls
    print("OK  首分支未命中时回退到第二分支")


def t_optional_miss_is_not_success():
    """optional 定位动作返回 False 必须被当作未命中（关键语义）。"""
    calls = []
    ex = _mk(_scripted({("miss", 1): False, ("hit", 1): True}, calls))
    act = {"type": "any_of", "choices": [
        [{"type": "miss", "tag": 1}],          # 模拟 optional click_first 没找到
        [{"type": "hit", "tag": 1}],
    ]}
    assert ex._step_any_of(act, "T") is True
    assert ("hit", 1) in calls, "optional 未命中必须继续试下一分支"
    print("OK  optional 未命中不被误判为分支成功")


def t_multistep_branch_stops_on_failure():
    """分支内某步失败 → 该分支后续步骤不执行，直接转下一分支。"""
    calls = []
    ex = _mk(_scripted({("nav", 1): True, ("anchor", 1): False,
                        ("anchor", 2): True}, calls))
    act = {"type": "any_of", "choices": [
        [{"type": "nav", "tag": 1}, {"type": "anchor", "tag": 1}],
        [{"type": "anchor", "tag": 2}],
    ]}
    assert ex._step_any_of(act, "T") is True
    assert calls == [("nav", 1), ("anchor", 1), ("anchor", 2)], calls
    print("OK  分支内失败即中断该分支（多步分支）")


def t_step_error_treated_as_miss():
    """分支内抛 StepError → 判该分支失败并继续。"""
    calls = []
    ex = _mk(_scripted({("a", 1): "raise", ("b", 1): True}, calls))
    act = {"type": "any_of", "choices": [
        [{"type": "a", "tag": 1}],
        [{"type": "b", "tag": 1}],
    ]}
    assert ex._step_any_of(act, "T") is True
    assert calls == [("a", 1), ("b", 1)], calls
    print("OK  分支抛 StepError 被当作未命中并继续")


def t_all_miss_optional_pass():
    """全部分支未命中 + optional → 返回 **True**（放行），不抛异常。

    2026-10-29 契约修正：此前这里断言 False，理由是"没命中就是没命中"。
    但日志一直写的是「optional 放行」，而放行在语义上等于"本步不算失败"。
    日志说放行、返回值说失败，外层 `_run_kind` 只认返回值，于是 49 处
    optional 的 any_of 全 miss 都被记成「步骤失败」，体检报告因此长期偏红。
    现在返回值与日志同义：True。
    """
    calls = []
    ex = _mk(_scripted({("a", 1): False}, calls))
    act = {"type": "any_of", "optional": True,
           "choices": [[{"type": "a", "tag": 1}]]}
    assert ex._step_any_of(act, "T") is True
    assert any("optional 放行" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  全部分支未命中 + optional 放行（返回 True，与日志同义）")


def t_all_miss_returns_false_warn():
    """全部分支未命中 + 非 optional → WARN 并返回 False（B6 不再抛 StepError）。"""
    calls = []
    ex = _mk(_scripted({("a", 1): False}, calls))
    act = {"type": "any_of", "choices": [[{"type": "a", "tag": 1}]]}
    assert ex._step_any_of(act, "T") is False
    assert any("any_of 全部分支均未命中" in l for l in ex.recorder.lines)
    print("OK  全部分支未命中且非 optional 时 WARN 返回 False")


def t_empty_choices():
    """choices 为空 → 返回 False 且不崩。"""
    ex = _mk(_scripted({}, []))
    assert ex._step_any_of({"type": "any_of", "choices": []}, "T") is False
    assert any("缺少 choices" in l for l in ex.recorder.lines)
    print("OK  choices 为空时安全返回 False")


def t_dict_choice_supported():
    """choice 允许是单个动作 dict（不必包成 list）。"""
    calls = []
    ex = _mk(_scripted({("a", 1): True}, calls))
    act = {"type": "any_of", "choices": [{"type": "a", "tag": 1}]}
    assert ex._step_any_of(act, "T") is True
    assert calls == [("a", 1)]
    print("OK  choice 支持单个动作 dict")


# ---------- 与 _step_click_first 的集成（any_of 成立的前提） ----------

def _mk_real_click_first(locate_result):
    """构造一个真实的 Executor（不打桩 _dispatch_probe），只打桩定位相关依赖。"""
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex.dry_run = True
    ex.d = None
    ex._last_fail = ""
    ex._locate = lambda k, v, timeout=6.0: locate_result
    ex._kb_candidates = lambda app, primary: ([primary], True)
    ex._kb_mark_fail = lambda app, prims: None
    ex._vision_click = lambda act, app, desc: False
    ex.knowledge = type("K", (), {"mark_ok": lambda *a: None})()
    return ex


def t_click_first_optional_miss_returns_false():
    """optional 且全候选未命中时，_step_click_first 必须返回 False（而非 None）。

    这是 any_of 正确工作的前提：若返回 None，_dispatch 会映射为 True，
    于是任何含 optional 定位动作的分支都被判成"成功"，any_of 形同虚设。
    """
    ex = _mk_real_click_first(LocateResult(False, None, "测试未命中"))
    act = {"type": "click_first", "optional": True,
           "candidates": [{"type": "text", "value": "签到"}]}
    res = ex._step_click_first(act, "T")
    assert res is False, f"应返回 False，实际 {res!r}"
    print("OK  click_first(optional) 未命中返回 False（any_of 前提）")


def t_click_first_nonoptional_miss_returns_false():
    """非 optional 且全候选未命中时，返回 False 并记录 detail（B6 不再抛 StepError）。"""
    ex = _mk_real_click_first(LocateResult(False, None, "测试未命中"))
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "签到"}]}
    res = ex._step_click_first(act, "T")
    assert res is False, f"应返回 False，实际 {res!r}"
    assert ex._last_fail and "所有候选均未出现" in ex._last_fail, ex._last_fail
    print("OK  click_first(非 optional) 未命中返回 False 并记录 detail")


def t_three_level_branch_runs_nav_mid_anchor():
    """三级导航分支：我的 → 中间入口 → 目标锚点，逐步执行到位。

    这是 sign 类行为的真实形态（河马剧场：我的 → 福利 → 签到）。
    """
    calls = []
    ex = _mk(_scripted({("anchor", 0): False, ("nav", 1): True,
                        ("mid", 1): True, ("anchor", 1): True}, calls))
    act = {"type": "any_of", "optional": True, "choices": [
        # 分支1：首屏直连（未命中）
        [{"type": "anchor", "tag": 0}],
        # 分支2：我的 → 中间入口 → 锚点
        [{"type": "nav", "tag": 1}, {"type": "think", "tag": 1},
         {"type": "mid", "tag": 1}, {"type": "think", "tag": 2},
         {"type": "anchor", "tag": 1}],
    ]}
    assert ex._step_any_of(act, "T") is True
    assert calls == [("anchor", 0), ("nav", 1), ("think", 1), ("mid", 1),
                     ("think", 2), ("anchor", 1)], calls
    print("OK  三级导航分支逐步执行：首屏 → 我的 → 中间入口 → 锚点")


def t_three_level_mid_miss_stops_branch():
    """三级分支里中间入口没找到 → 该分支失败，不执行后面的锚点。"""
    calls = []
    ex = _mk(_scripted({("anchor", 0): False, ("nav", 1): True,
                        ("mid", 1): False, ("anchor", 1): True}, calls))
    act = {"type": "any_of", "optional": True, "choices": [
        [{"type": "anchor", "tag": 0}],
        [{"type": "nav", "tag": 1}, {"type": "mid", "tag": 1},
         {"type": "anchor", "tag": 1}],
    ]}
    assert ex._step_any_of(act, "T") is True      # 全分支未命中 + optional 放行
    assert ("anchor", 1) not in calls, "中间入口失败后不应继续点锚点"
    print("OK  三级分支中间入口失败即中断，不误点后续锚点")


def t_only_last_branch_allows_vision():
    """只有最后一个分支允许视觉兜底（前面的分支是"便宜探测"）。

    B7：门控是显式参数链，断言 allow_vision 序列 == [False, True]。
    """
    seen = []

    def fake(act, app_name, allow_vision):
        seen.append((act.get("tag"), allow_vision))
        return act.get("tag") == 2      # 只有最后一个分支命中

    ex = _mk(fake)
    act = {"type": "any_of", "optional": True, "choices": [
        [{"type": "x", "tag": 1}],
        [{"type": "x", "tag": 2}],
    ]}
    assert ex._step_any_of(act, "T") is True
    assert seen == [(1, False), (2, True)], seen
    print("OK  仅最后一个分支 allow_vision=True（显式参数链）")


def t_dispatch_maps_none_to_true():
    """_dispatch 兼容薄包装：None 归一化为 True，False 原样传出。"""
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex.human = type("H", (), {"delay": lambda *a: None,
                              "maybe_wander": lambda *a: None})()
    ex.d = None
    ex._step_wait = lambda act, app: None
    ex._step_click_first = lambda act, app, allow_vision=True: False
    assert ex._dispatch({"type": "wait"}, "T", ritual=False) is True
    assert ex._dispatch({"type": "click_first"}, "T", ritual=False) is False
    assert ex._dispatch({"type": "不存在"}, "T", ritual=False) is False
    print("OK  _dispatch 归一化：None->True，False->False，未知类型->False")


if __name__ == "__main__":
    tests = [t_first_branch_wins, t_fallback_to_second_branch,
             t_optional_miss_is_not_success, t_multistep_branch_stops_on_failure,
             t_step_error_treated_as_miss, t_all_miss_optional_pass,
             t_all_miss_returns_false_warn, t_empty_choices, t_dict_choice_supported,
             t_three_level_branch_runs_nav_mid_anchor,
             t_three_level_mid_miss_stops_branch,
             t_only_last_branch_allows_vision,
             t_click_first_optional_miss_returns_false,
             t_click_first_nonoptional_miss_returns_false,
             t_dispatch_maps_none_to_true]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
