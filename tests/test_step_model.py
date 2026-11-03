# -*- coding: utf-8 -*-
"""test_step_model.py - v1/v2 编译层回归钉（v6 · S1）

锁定四件事：
  ① v1 旧 type 与 v2 新写法编译出**语义等价**的 Step（project 投影相等）；
  ② 四类非法组合必须抛 ValueError（不许猜、不许静默忽略）；
  ③ 坐标**不许取整** —— click_point 的 x/y 是 0~1 比例值，
     `int(0.9)` = 0 会把"图像锚失败时兜底点 (0.9,0.138)"变成"点屏幕左上角"；
  ④ **34 份真配置 389 个顶层步骤全部编译通过**（这是最强的一条，
     合成用例永远测不出"某个 type 忘了登记映射"）。

运行：
    ./.venv/Scripts/python.exe -m pytest tests/test_step_model.py -q
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from step_model import (compile_step, compile_actions, project, lint,
                        Step, Target, LEGACY_TO_V2)  # noqa: E402


# ---------- ① v1/v2 语义等价 ----------

def t_click_text_equals_click_by_text():
    a = compile_step({"type": "click_text", "text": "签到"})
    b = compile_step({"action": "click", "by": "text", "text": "签到"})
    assert a.action == b.action == "click"
    assert a.target.by == b.target.by == "text"
    assert a.target.value == b.target.value == "签到"
    assert project(a) == project(b), (project(a), project(b))
    print("OK  click_text == click+by:text")


def t_click_id_and_desc():
    for legacy, field, by in (("click_id", "res_id", "id"),
                              ("click_desc", "desc", "desc")):
        a = compile_step({"type": legacy, field: "v"})
        b = compile_step({"action": "click", "by": by, field: "v"})
        assert a.target.by == b.target.by == by
        assert a.target.value == b.target.value == "v"
        assert project(a) == project(b), (legacy, project(a), project(b))
    print("OK  click_id/click_desc == click+by:id/desc")


def t_click_point_no_anchor_is_tap():
    s = compile_step({"type": "click_point", "x": 0.5, "y": 0.641})
    assert s.action == "tap"
    assert s.target is None
    assert s.point == (0.5, 0.641)
    print("OK  无锚点 click_point -> tap + point")


def t_click_point_image_keeps_float_fallback():
    """有图像锚 + 坐标 -> click + by:image + fallback **保留比例值**。

    这条钉的是"不许取整"：写成 int(0.9) 会得到 (0,0)，
    兜底点击落到屏幕左上角，比不兜底更糟（会误触广告位）。
    """
    s = compile_step({"type": "click_point", "x": 0.9, "y": 0.138,
                      "images": ["ref.png"]})
    assert s.action == "click"
    assert s.target.by == "image"
    assert s.target.value == "ref.png"
    assert s.target.fallback == ((0.9, 0.138),), s.target.fallback
    print(f"OK  图像锚 -> click + fallback={s.target.fallback}（未取整）")


def t_click_point_image_without_xy_has_no_fallback():
    """只写 images 不写坐标（实测 53 个）-> 合法，fallback 为空。"""
    s = compile_step({"type": "click_point",
                      "images": ["ref.png"], "optional": True})
    assert s.action == "click" and s.target.by == "image"
    assert s.target.fallback == ()
    print("OK  只有 images 无坐标 -> click，无 fallback")


def t_click_point_with_vlm_is_click_with_vision():
    s = compile_step({"type": "click_point", "x": 0.9, "y": 0.138,
                      "vlm_prompt": "定位『我的』"})
    assert s.action == "click" and s.target.by == "vision"
    assert s.target.value == "定位『我的』"
    print("OK  vlm_prompt -> click + by:vision")


def t_any_of_is_first_ok():
    s = compile_step({"type": "any_of", "optional": True,
                      "choices": [[{"type": "click_text", "text": "A"}],
                                  [{"type": "click_text", "text": "B"}]]})
    assert s.flow == "first_ok"
    assert len(s.branches) == 2
    assert s.branches[0][0].action == "click"
    print("OK  any_of -> flow:first_ok + 2 branches")


def t_random_is_pick_one():
    s = compile_step({"type": "random", "choices": [[{"type": "think"}]]})
    assert s.flow == "pick_one"
    print("OK  random -> flow:pick_one")


def t_back_home_are_press():
    b = compile_step({"type": "back"})
    h = compile_step({"type": "home"})
    assert (b.action, b.key) == ("press", "back")
    assert (h.action, h.key) == ("press", "home")
    print("OK  back/home -> press+key")


def t_click_first_is_flow_not_click():
    """click_first 语义是"多候选依次试、第一个成功即停"，不是单个 click。"""
    s = compile_step({"type": "click_first",
                      "candidates": [{"type": "text", "value": "A"},
                                     {"type": "text", "value": "B"}]})
    assert s.flow == "first_ok"
    assert len(s.branches) == 2
    print("OK  click_first -> flow:first_ok + 2 分支")


def t_click_first_pool_from_is_legal():
    """不写静态 candidates、靠 candidates_from 词池动态取候选是合法写法。"""
    s = compile_step({"type": "click_first", "candidates_from": "sign",
                      "optional": True})
    assert s.flow == "first_ok"
    assert s.branches == ()
    assert s.pool_from == "sign"
    assert not [i for i in lint([s]) if i["level"] == "ERROR"], lint([s])
    print("OK  candidates_from 词池写法不报 ERROR")


def t_ensure_preserved_as_legacy():
    """ensure 暂未折叠成三维度：保留 legacy_type，执行层仍走 _step_ensure。"""
    s = compile_step({"type": "ensure", "text": "已签到"})
    assert s.legacy_type == "ensure"
    assert s.action is None and s.flow is None and s.macro is None
    print("OK  ensure 保留 legacy_type（S2 再折叠）")


# ---------- ② 必须抛错 ----------

def t_type_and_action_conflict():
    try:
        compile_step({"type": "click_text", "action": "tap", "x": 0.5, "y": 0.5})
    except ValueError as e:
        assert "冲突" in str(e), e
        return
    raise AssertionError("type 与 action 冲突应抛")


def t_type_and_action_equivalent_is_ok():
    """等价写法（type: click_text + action: click）允许，不算冲突。"""
    s = compile_step({"type": "click_text", "action": "click", "text": "X"})
    assert s.action == "click" and s.target.by == "text"
    print("OK  type/action 等价写法放行")


def t_click_missing_target():
    for bad in ({"action": "click"}, {"type": "click"}):
        try:
            compile_step(bad)
        except ValueError:
            continue
        raise AssertionError(f"click 缺定位字段应抛: {bad}")
    print("OK  click 缺定位字段抛错")


def t_multiple_primary_keys():
    try:
        compile_step({"action": "tap", "flow": "first_ok", "x": 0, "y": 0})
    except ValueError:
        return
    raise AssertionError("多主键应抛")


def t_unknown_type():
    try:
        compile_step({"type": "bogus_action"})
    except ValueError as e:
        assert "未知 type" in str(e), e
        return
    raise AssertionError("未知 type 应抛")


def t_unknown_flow_and_macro():
    for bad in ({"flow": "nope"}, {"macro": "nope"}):
        try:
            compile_step(bad)
        except ValueError:
            continue
        raise AssertionError(f"未知主键值应抛: {bad}")
    print("OK  未知 flow/macro 抛错")


def t_press_requires_valid_key():
    try:
        compile_step({"action": "press", "key": "volume_up"})
    except ValueError:
        return
    raise AssertionError("press 非法 key 应抛")


# ---------- ③ 语义投影 ----------

def t_project_equivalence_v1_v2():
    pairs = [
        ({"type": "click_text", "text": "X"},
         {"action": "click", "by": "text", "text": "X"}),
        ({"type": "back"}, {"action": "press", "key": "back"}),
        ({"type": "click_point", "x": 0.3, "y": 0.4},
         {"action": "tap", "x": 0.3, "y": 0.4}),
    ]
    for a, b in pairs:
        pa, pb = project(compile_step(a)), project(compile_step(b))
        assert pa == pb, (a, b, pa, pb)
    print("OK  语义投影 v1/v2 一致")


def t_project_category_matches_behavior_runner():
    """project 的分类必须与 behavior_runner.ACTION_CATEGORY 同源。

    唯一的例外是 v6 **有意重分类**的那几个 —— 必须逐条列出来，
    不许用 `continue` 悄悄跳过，否则"重分类"和"写错了"就分不清了：

      click_first  v5 分类 click（返回值是 bool，像单次点击）
                   v6 分类 flow（结构上是"多候选依次试"，归 flow 才对）
      click_text/id/desc  是 click 的别名，折叠后同为 click
      swipe_natural       是 swipe 的别名
    """
    import behavior_runner as br

    RECLASSIFIED = {"click_first": "flow"}     # v5 分类 -> v6 分类
    ALIASES = {"click_text", "click_id", "click_desc", "swipe_natural"}

    checked = 0
    for t, v5_cat in br.ACTION_CATEGORY.items():
        if t in ALIASES:
            continue
        if t == "click":
            step = compile_step({"action": "click", "text": "X"})
        elif t == "click_point":
            step = compile_step({"action": "tap", "x": 0.1, "y": 0.2})
        else:
            try:
                step = compile_step({"type": t})
            except ValueError:
                continue
        want = RECLASSIFIED.get(t, v5_cat)
        got = project(step)[0]
        assert got == want, f"{t}: 期望 {want}（v5={v5_cat}），实际 {got}"
        checked += 1
    assert checked >= 15, f"只校验了 {checked} 个 type，覆盖不足"
    print(f"OK  project 分类与 ACTION_CATEGORY 同源（{checked} 个，"
          f"click_first 已按 v6 重分类为 flow）")


def t_compile_actions_keeps_variant_levels():
    """多候选模板 [[..],[..]] 编译后保持两级结构。"""
    out = compile_actions([[{"type": "click_text", "text": "A"}],
                           [{"type": "click_text", "text": "B"}]])
    assert len(out) == 2 and isinstance(out[0], list)
    assert out[0][0].action == "click"
    print("OK  多候选模板保持两级结构")


# ---------- ④ 真配置全量编译（最强的一条） ----------

def t_all_app_configs_compile():
    """35 份 App 配置的 **378 个顶层步骤**全部编译通过，且 lint 无 ERROR。

    合成用例测不出"某个 type 忘了登记 LEGACY_TO_V2"这类漏项 ——
    只有拿真配置全量跑一遍才行。实测基线：378 步 / 0 失败 / 115 WARN。
    2026-10-31 改：35-app 重排（删趣头条/加快手极速版/河马畅听）后
    基线由 389 步/112 WARN/legacy{ensure,scroll_to} 变为 383/116/{scroll_to}。
    2026-11-02 改：悟空浏览器删掉已失效的冷启动 `wait 3s`（全屏播放页盖住导航，
    固定 wait 会把 ~2s 导航窗口睡过去）-> 383 -> 382。
    2026-11-03 改：快手极速版 sign 重校（去赚钱入口直达任务中心、直接签到无中间
    弹窗）——删掉一个带 optional 的 click_point（弹窗按钮）-> WARN 117 -> 116。
    2026-11-03 改：快手 bonus 重校（宝箱入口改右下浮动红盒，删旧 红包图标/点可领
    模板，保留关闭X）-> 步数 379 -> 378，WARN 116 -> 115。
    """
    from miniyaml import safe_load
    total = 0
    warns = 0
    errors = []
    legacy = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "config", "apps", "*.yaml"))):
        fn = os.path.basename(p)
        with open(p, encoding="utf-8") as f:
            d = safe_load(f.read())
        for rname, steps in (d.get("behaviors") or {}).items():
            try:
                cs = compile_actions(steps)
            except ValueError as e:
                errors.append(f"{fn}/{rname}: {e}")
                continue
            total += sum(len(x) if isinstance(x, list) else 1 for x in cs)
            for s in cs:
                if isinstance(s, Step) and s.legacy_type:
                    legacy[s.legacy_type] = legacy.get(s.legacy_type, 0) + 1
            for i in lint(cs, fn, rname):
                if i["level"] == "ERROR":
                    errors.append(f"{fn}/{rname}: {i['msg']}")
                elif i["level"] == "WARN":
                    warns += 1
    assert not errors, errors
    assert total == 378, f"顶层步骤数应为 378，实际 {total}"
    assert warns == 115, f"死 optional WARN 应为 115，实际 {warns}"
    assert legacy == {"scroll_to": 1}, legacy
    print(f"OK  35 份配置 {total} 步全编译，0 ERROR，{warns} WARN")


def t_no_step_returns_none_contract_violation():
    """编译产物不得改变原语返回值语义：on_miss 只是块级标注，不是返回值。"""
    s = compile_step({"type": "click_first", "optional": True,
                      "candidates": [{"type": "text", "value": "A"}]})
    # click_first 作为 any_of 分支时必须能在全 miss 时返回 False，
    # 所以它的 on_miss 描述的是"整块可跳过"，不改变原语布尔值。
    assert s.on_miss == "skip"
    assert s.raw.get("optional") is True
    print("OK  on_miss 为块级标注，不改原语返回值")


# ---------- ⑤ 接入执行层后的行为（防止 _validate_step 是摆设） ----------

class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, msg, app=None, level="INFO"):
        self.lines.append(f"[{level}] {msg}")


def _executor_with(rec):
    """最小 BehaviorRunner 替身：只需要 recorder 与 human。"""
    from behavior_runner import BehaviorRunner
    ex = BehaviorRunner.__new__(BehaviorRunner)
    ex.recorder = rec
    ex.dry_run = True
    ex.d = None
    ex._last_fail = ""
    return ex


def t_validate_step_logs_but_does_not_raise():
    """非法 step 只记 WARN，不抛 —— 抛了会让整条链中断。"""
    from behavior_runner import BehaviorRunner
    rec = _Rec()
    ex = _executor_with(rec)
    BehaviorRunner._validate_step(ex, {"type": "bogus_action"}, "T")
    assert any("编译校验失败" in ln for ln in rec.lines), rec.lines
    print("OK  非法 step 记 WARN 不抛")


def t_validate_step_silent_for_good_step():
    """合法 step 不产生任何日志（否则每次运行都刷屏）。"""
    from behavior_runner import BehaviorRunner
    rec = _Rec()
    ex = _executor_with(rec)
    BehaviorRunner._validate_step(ex, {"type": "click_text", "text": "签到"}, "T")
    assert not rec.lines, rec.lines
    print("OK  合法 step 不记日志")


def t_run_kind_accepts_step_and_uses_raw():
    """_run_kind 收到 Step 时，执行用的是 step.raw —— 而不是从 Step 反推。"""
    from behavior_runner import BehaviorRunner
    rec = _Rec()
    ex = _executor_with(rec)
    calls = []

    def fake_wait(raw, app):
        calls.append(raw)
        return True

    ex._step_wait = fake_wait
    act = {"type": "wait", "seconds": 3}
    step = compile_step(act)
    assert isinstance(step, Step)
    assert BehaviorRunner._run_kind(ex, step, "T") is True
    assert calls and calls[0] is act, "必须把原始 dict 交给原语，不能传 Step"
    print("OK  _run_kind 接受 Step 但执行用 raw")


def t_run_actions_never_skips_on_compile_error():
    """编译失败也必须继续执行下一步 —— 这是"零行为变化"的底线。

    方案原文在编译失败时 `continue`，会让 40+ 个 click 步骤静默不执行。
    这里用一个必然编译失败的 type 验证：它仍然会被送到 _exec_step。
    """
    from behavior_runner import BehaviorRunner
    rec = _Rec()
    ex = _executor_with(rec)
    seen = []
    ex._exec_step = lambda act, app: (seen.append(act), True)[1]
    BehaviorRunner._run_actions(ex, [{"type": "bogus_action"},
                               {"type": "wait", "seconds": 1}], "T", "sign")
    assert len(seen) == 2, f"两步都应被执行，实际 {len(seen)}"
    assert any("编译校验失败" in ln for ln in rec.lines), rec.lines
    print("OK  编译失败不跳过执行（2 步都跑了）")


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
