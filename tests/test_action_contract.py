# -*- coding: utf-8 -*-
"""test_action_contract.py - 2026-10-29 「type 按返回值契约分 9 类」回归钉

背景：19 个 type 平铺，问题不是"没分类"，而是**同类动作返回值语义不一致**，
`_run_kind` 只能统一 `None -> True` 兜底，于是"没做任何判断"与"判断通过"同义。
这个文件钉住四件事：

  ① `ACTION_CATEGORY` 与 `_run_kind` 的分派表严格一一对应（新增 type 漏登记会红）；
  ② 每个类别都有返回值契约；
  ③ 三个被 `None -> True` 掩盖的真 bug 已按契约修好：
       - `_step_click_point` 丢 `_verify_landing` 返回值（落地失败也算成功）
       - `_step_any_of` 的 optional 全 miss 分支日志写"放行"、却 return False
       - `_step_random` 不汇总子步骤（子步骤全失败，整步仍算成功）
  ④ 只有 point / timing / read 允许返回 None；其余类别返回 None 记 WARN 判失败。

运行：
    python tests/test_action_contract.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import behavior_runner as br  # noqa: E402
from executor import Executor, LocateResult  # noqa: E402
from config_loader import load_config  # noqa: E402
import nlu  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append(f"[{level}] {event}")


class _Human:
    def tap(self, *a, **k):
        pass

    def jitter_point(self, x, y):
        return x, y

    def delay(self, *a):
        pass

    def maybe_wander(self, *a):
        pass

    def think(self, *a):
        pass


class _Dev:
    pass


def _mk():
    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=False, config={})
    ex.d = _Dev()
    ex._locate = lambda k, v, timeout=2.0: LocateResult(False, None, "测试未命中")
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    return ex


# ---------- ① 分类表与分派表一一对应 ----------

def t_category_matches_dispatch_table():
    """分派表里的每个 type 都必须在 ACTION_CATEGORY 里登记，且不得多登记。

    漏登记 → `_run_kind` 记「动作类型未登记分类」并按失败处理，行为静默失效。
    直接从源码里抽出 `_run_kind` 的 dict 键做比对，避免测试里再抄一份名单。
    """
    src = open(br.__file__, encoding="utf-8").read()
    body = src.split("def _run_kind")[1].split("}.get(t)")[0]
    dispatched = set(re.findall(r'"([a-z_]+)":\s*self\._step_', body))
    assert dispatched, "没能从 _run_kind 抽出分派表，正则需更新"
    missing = dispatched - set(br.ACTION_CATEGORY)
    extra = set(br.ACTION_CATEGORY) - dispatched
    assert not missing, f"分派表有、分类表没有: {sorted(missing)}"
    assert not extra, f"分类表有、分派表没有: {sorted(extra)}"
    print(f"OK  分类表与分派表一一对应（{len(dispatched)} 个 type）")


def t_every_category_has_contract():
    """每个类别都必须有返回值契约，否则 `_check_return` 会退回 {bool} 兜底。"""
    cats = set(br.ACTION_CATEGORY.values())
    assert cats <= set(br._RETURN_CONTRACT), \
        f"缺契约的类别: {sorted(cats - set(br._RETURN_CONTRACT))}"
    for c, allowed in br._RETURN_CONTRACT.items():
        assert allowed and allowed <= {"bool", "none"}, (c, allowed)
    print(f"OK  {len(cats)} 个类别都有返回值契约")


def t_none_allowed_only_for_point_timing_read():
    """只有 point / timing / read 允许 None —— 其余类别返回 None 即失败。"""
    allow_none = {c for c, a in br._RETURN_CONTRACT.items() if "none" in a}
    assert allow_none == {"point", "timing", "read"}, allow_none
    print("OK  允许 None 的类别恰为 point/timing/read")


# ---------- ② bug 1：click_point 必须把落地校验结果返回上去 ----------

def t_click_point_landing_false_propagates():
    """落地校验失败 → `_step_click_point` 与 `_run_kind` 都必须返回 False。

    改前：`self._verify_landing(...)` 的返回值被丢弃，函数末尾无 return（None），
    `_run_kind` 把 None 当 True —— 落地失败也算成功。
    """
    ex = _mk()
    ex._verify_landing = lambda act, app, x=None, y=None, no_retry=False: False
    act = {"type": "click_point", "x": 0.5, "y": 0.5,
           "expect": {"text_any": ["签到"]}}
    assert ex._step_click_point(act, "T") is False
    assert ex._run_kind(act, "T") is False
    print("OK  click_point 落地失败 -> False（不再被 None 兜成成功）")


def t_click_point_landing_true_and_no_expect():
    """落地通过 → True；没写 expect → True（点了就是成功，无可判信号不算失败）。"""
    ex = _mk()
    ex._verify_landing = lambda act, app, x=None, y=None, no_retry=False: True
    assert ex._run_kind({"type": "click_point", "x": 0.5, "y": 0.5,
                         "expect": {"text_any": ["签到"]}}, "T") is True
    ex2 = _mk()
    assert ex2._run_kind({"type": "click_point", "x": 0.5, "y": 0.5}, "T") is True
    print("OK  click_point 落地通过/无 expect 均返回 True")


# ---------- ③ bug 2：any_of optional 放行必须返回 True ----------

def t_any_of_optional_all_miss_is_true():
    """optional 的 any_of 全 miss → True，且日志与返回值同义。"""
    ex = _mk()
    ex._dispatch_probe = lambda act, app, allow_vision=True: False
    act = {"type": "any_of", "optional": True,
           "choices": [[{"type": "click_text", "text": "签到"}]]}
    assert ex._step_any_of(act, "T") is True
    assert any("optional 放行" in l for l in ex.recorder.lines)
    print("OK  any_of optional 全 miss -> True（放行）")


def t_any_of_non_optional_all_miss_is_false():
    """非 optional 的 any_of 全 miss → False（B6 语义不变）。"""
    ex = _mk()
    ex._dispatch_probe = lambda act, app, allow_vision=True: False
    act = {"type": "any_of", "choices": [[{"type": "click_text", "text": "签到"}]]}
    assert ex._step_any_of(act, "T") is False
    print("OK  any_of 非 optional 全 miss -> False")


# ---------- ④ bug 3：random 必须汇总子步骤 ----------

def t_random_aggregates_substeps():
    """随机分支里任一子步骤失败 → 整步 False（改前恒为 None->True）。"""
    ex = _mk()
    ex._dispatch_probe = lambda act, app, allow_vision=True: False
    act = {"type": "random",
           "choices": [[{"type": "click_text", "text": "A"},
                        {"type": "click_text", "text": "B"}]]}
    assert ex._step_random(act, "T") is False
    assert ex._run_kind(act, "T") is False

    ex2 = _mk()
    ex2._dispatch_probe = lambda act, app, allow_vision=True: True
    assert ex2._run_kind(act, "T") is True

    ex3 = _mk()
    assert ex3._step_random({"type": "random", "choices": []}, "T") is False
    print("OK  random 汇总子步骤（全成功 True / 有失败 False / 无 choices False）")


# ---------- ⑤ 契约校验：None 只在允许的类别里算成功 ----------

def t_timing_and_read_none_are_success():
    """wait/think（timing）与 reward（read）返回 None 是合法的，算成功。"""
    ex = _mk()
    ex._step_wait = lambda act, app: None
    assert ex._run_kind({"type": "wait", "seconds": 1}, "T") is True
    ex2 = _mk()
    ex2._step_reward = lambda act, app: None
    assert ex2._run_kind({"type": "reward", "name": "金币"}, "T") is True
    print("OK  timing/read 返回 None 视为成功（合法契约）")


def t_click_none_violates_contract():
    """元素点击返回 None 属契约违反：记 WARN 并按失败处理。"""
    ex = _mk()
    ex._step_click_text = lambda act, app, allow_vision=True: None
    assert ex._run_kind({"type": "click_text", "text": "签到"}, "T") is False
    assert any("返回值契约违反" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  click 返回 None -> WARN + False（不再兜成成功）")


def t_unregistered_type_is_failure():
    """分派表有、分类表没有的 type（人为制造）→ WARN + False。"""
    ex = _mk()
    br.ACTION_CATEGORY.pop("back", None)
    try:
        assert ex._run_kind({"type": "back"}, "T") is False
        assert any("未登记分类" in l for l in ex.recorder.lines)
    finally:
        br.ACTION_CATEGORY["back"] = "key"
    print("OK  未登记分类的 type -> WARN + False")


# ---------- ⑦ 顶层 optional 未命中必须放行（2026-11-04） ----------

def t_top_level_optional_click_point_miss_passes():
    """顶层 click_point（仅 images 无坐标）optional miss -> 放行，行为不算未完成。

    2026-11-04：飞猪更新弹窗关X / 红果「立即签到」都是「仅 images 无坐标 +
    optional」，模板不命中是**常态**（无弹窗/已签日按钮变灰），却被记「步骤失败」
    + all_ok=False -> 行为误判「执行未完成」。修复：_run_actions 消费 optional。
    """
    ex = _mk()
    ex._vision_click = lambda act, app, desc: False
    act = {"type": "click_point", "images": ["images/x.png"],
           "template_threshold": 0.96, "timeout": 6, "optional": True,
           "desc": "版本更新插屏关闭X"}
    assert ex._run_actions([act], "T", "sign") is True
    assert any("optional 放行" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  顶层 click_point optional miss -> 放行（行为不算未完成）")


def t_top_level_non_optional_click_point_miss_is_failure():
    """顶层 click_point 无坐标 miss、非 optional -> 记步骤失败 + all_ok False（B6 不变）。"""
    ex = _mk()
    ex._vision_click = lambda act, app, desc: False
    act = {"type": "click_point", "images": ["images/x.png"], "desc": "无坐标非optional"}
    assert ex._run_actions([act], "T", "sign") is False
    assert any("步骤失败" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  顶层 click_point 非 optional miss -> 失败（B6 语义不变）")


def t_top_level_optional_click_first_miss_passes():
    """顶层 click_first optional 候选全未出现 -> 放行（与 click_point 顶层语义一致）。"""
    ex = _mk()

    def _fake_click_first_miss(act, app, allow_vision=True):
        ex._last_fail = ("所有候选均未出现: "
                         "[{'type': 'text', 'value': '里程签到'}]")
        return False

    ex._step_click_first = _fake_click_first_miss
    act = {"type": "click_first", "candidates": [{"type": "text", "value": "里程签到"}],
           "optional": True, "timeout": 6}
    assert ex._run_actions([act], "T", "sign") is True
    print("OK  顶层 click_first optional 候选未出现 -> 放行")


def t_top_level_coord_optional_landing_fail_is_failure():
    """有坐标 click_point + optional + 落地校验失败 -> 不放行（不掩盖坐标过时/点错）。

    2026-11-04：全民K歌模板 scale 问题就是这类——有坐标但点到错位，落地校验失败。
    若 optional 无脑放行，会把"点了却没到目标页"伪装成成功。必须严格报告。
    """
    ex = _mk()
    ex._vision_click = lambda act, app, desc: False
    act = {"type": "click_point", "x": 0.5, "y": 0.5, "optional": True,
           "expect": {"text_any": ["签到"]}}
    # _verify_landing 返回 False（落地失败）→ _step_click_point 返回 False
    ex._verify_landing = lambda act, app, x=None, y=None, no_retry=False: False
    ex._last_fail = "落地校验失败"
    assert ex._run_actions([act], "T", "sign") is False
    assert any("步骤失败" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  有坐标 click_point optional 落地校验失败 -> 不放行（严格报告）")


# ---------- ⑧ behavior 层：删 growth / 降级 open ----------

def t_growth_intent_removed():
    """growth 已从意图表删除：相关文案不再解析出 growth。"""
    for text in ("去做任务", "浇花施肥", "升级"):
        intents = [i for i, _ in nlu.parse_intents(text)]
        assert "growth" not in intents, (text, intents)
    assert "growth" not in nlu.DEFAULT_INTENT_MAP
    print("OK  growth 意图已删除（做任务/浇花/升级 不再产出 growth）")


def t_open_intent_removed():
    """open 已从意图表删除（系统动作，不是用户目标）。"""
    for text in ("打开", "启动", "开启应用"):
        intents = [i for i, _ in nlu.parse_intents(text)]
        assert "open" not in intents, (text, intents)
    assert "open" not in nlu.DEFAULT_INTENT_MAP
    print("OK  open 意图已删除")


def t_baidu_lite_redirects_sign_to_open():
    """百度极速版只有 open 一条链，必须靠 intent_map 重定向，否则彻底不可执行。"""
    apps = load_config(os.path.join(ROOT, "config.yaml"))["apps"]
    app = next(a for a in apps if a.get("name") == "百度极速版")
    assert (app.get("intent_map") or {}).get("sign") == "open", app.get("intent_map")
    assert "open" in (app.get("behaviors") or {}), list(app.get("behaviors") or {})
    print("OK  百度极速版 intent_map: sign -> open")


if __name__ == "__main__":
    tests = [t_category_matches_dispatch_table, t_every_category_has_contract,
             t_none_allowed_only_for_point_timing_read,
             t_click_point_landing_false_propagates,
             t_click_point_landing_true_and_no_expect,
             t_any_of_optional_all_miss_is_true,
             t_any_of_non_optional_all_miss_is_false,
             t_random_aggregates_substeps,
             t_timing_and_read_none_are_success,
             t_click_none_violates_contract,
             t_unregistered_type_is_failure,
             t_top_level_optional_click_point_miss_passes,
             t_top_level_non_optional_click_point_miss_is_failure,
             t_top_level_optional_click_first_miss_passes,
             t_top_level_coord_optional_landing_fail_is_failure,
             t_growth_intent_removed, t_open_intent_removed,
             t_baidu_lite_redirects_sign_to_open]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
