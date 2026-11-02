# -*- coding: utf-8 -*-
"""step_model.py - v1/v2 步骤统一编译层（AUTOP v6 · S1）

职责单一：把一份 YAML 的每个 step dict 规范化成**不可变**的 Step 对象。
  * v1 写法（只有 type）与 v2 写法（action/flow/macro）都能产出 Step；
  * **执行层仍用 step.raw**，所以老配置一行不改、行为零变化；
  * 编译产物可用于：编译期 lint / dry-run 语义投影对拍 / 静态校验。

三种点击形态（任务书 §5.6）：
  ① 元素点击      action: click + target{by: text/id/desc}
  ② 视觉锚+兜底   action: click + target{by: image/vision, fallback: (x,y)}
  ③ 纯坐标        action: tap   + point: (x, y)

设计红线（都是踩过的坑，改这里之前先读）：
  1. **坐标不许取整**。`click_point` 的 x/y 是 0~1 的比例值，`int(0.9)` = 0，
     会把「图像锚命中不了时兜底点 (0.9,0.138)」变成「点屏幕左上角」。实测有 8 个
     步骤是「图像 + 坐标兜底」的写法，取整等于让它们的兜底全部失效。
  2. **click_text/click_id/click_desc 必须走 "action+field"**。它们是 click 的别名，
     定位值在 `text` / `res_id` / `desc` 字段里，不能当成 action 名直接分派
     （`_compile_action_from_v1` 只认 swipe/press/wait/extract）。
  3. **编译失败不等于跳过执行**。调用方（`_run_actions`）拿到 ValueError 只记 WARN，
     必须继续用原 dict 执行 —— 否则一个新加的、没登记映射的 type 会让整条链静默失效。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["Target", "Step", "compile_step", "compile_actions", "project",
           "lint", "LEGACY_TO_V2", "ACTION_NAMES", "FLOW_NAMES", "MACRO_NAMES"]

# v6 三个主键的规范成员（任务书 §5.1/5.2/5.3）
ACTION_NAMES = frozenset({"click", "tap", "swipe", "press", "wait",
                          "extract", "input"})
FLOW_NAMES = frozenset({"first_ok", "pick_one"})
MACRO_NAMES = frozenset({"dismiss_popups", "captcha"})
# 旧名 -> 规范名（任务书 §11「旧名映射」，永久有效，不许删）
FLOW_ALIASES = {"any_of": "first_ok", "random": "pick_one"}

# 旧 type -> v2。值的第一位是"怎么编译"：
#   ("action", name[, extra...])   直接 action，extra 见 _compile_action_from_v1
#   ("action+field", name, field, by)  action=click + 定位值在哪个字段
#   ("flow_via_branches", flow)    click_first：每个 candidate 一条分支
#   ("flow_via_choices", flow)     any_of/random：每组 choices 一条分支
#   ("macro", name)                弹窗/验证码
#   ("click_point",)               独立分支：有锚 -> click+fallback，无锚 -> tap
#   ("legacy", name)               暂未折叠，保留 legacy_type，执行层走旧分派
LEGACY_TO_V2: dict[str, Any] = {
    # 元素点击三别名 —— 定位值分别在 text / res_id / desc
    "click_text": ("action+field", "click", "text", "text"),
    "click_id":   ("action+field", "click", "res_id", "id"),
    "click_desc": ("action+field", "click", "desc", "desc"),
    # 分支编排
    "click_first": ("flow_via_branches", "first_ok"),
    "any_of":      ("flow_via_choices", "first_ok"),
    "random":      ("flow_via_choices", "pick_one"),
    # 手势
    "swipe":         ("action", "swipe"),
    "swipe_natural": ("action", "swipe"),
    # 系统键
    "back": ("action", "press", "back"),
    "home": ("action", "press", "home"),
    # 时序
    "wait":  ("action", "wait", "seconds"),
    "think": ("action", "wait", "think"),
    # 读取 / 断言
    "reward": ("action", "extract", "reward"),
    "ensure": ("legacy", "ensure"),      # S2 再折叠成 extract + on_miss: fail
    "scroll_to": ("legacy", "scroll_to"),
    # 复合宏
    "dismiss_popups": ("macro", "dismiss_popups"),
    "captcha":        ("macro", "captcha"),
    # 坐标点击：独立分支
    "click_point": ("click_point",),
    # `click` 本身是 v6 合法名，但 v1 里也可能直接写 type: click
    "click": ("v2_click",),
}

# v2 动作名 -> 9 分类口径（与 behavior_runner.ACTION_CATEGORY 对齐）
# 只补 ACTION_CATEGORY 里没有的 v2 新名；其余直接查 ACTION_CATEGORY。
_V2_CATEGORY = {
    "tap": "point",      # 与 click_point 同类：坐标点击
    "press": "key",      # 与 back/home 同类
    "extract": "read",   # 与 reward 同类
    "input": "read",
    "swipe": "gesture",
    "wait": "timing",
    "click": "click",
}


@dataclass(frozen=True)
class Target:
    """元素点击的定位描述（仅 action=click 时存在）。"""
    by: str                                  # text / id / desc / image / vision
    value: str = ""
    pool: tuple[str, ...] = ()
    search: str | None = None
    fallback: tuple[tuple[float, float], ...] = ()   # 坐标兜底，**保留比例值**
    vision: bool = True


@dataclass(frozen=True)
class Step:
    """统一编译产物。`raw` 是原始 dict —— 执行层用它，这是"零行为变化"的关键。"""
    action: str | None = None
    flow: str | None = None
    macro: str | None = None
    target: Target | None = None
    expect: dict | None = None
    on_miss: str = "fail"                    # skip / fail
    label: str = ""
    point: tuple[float, float] | None = None  # action=tap
    key: str | None = None                    # action=press
    seconds: float | None = None              # action=wait
    branches: tuple[tuple["Step", ...], ...] = ()   # flow=first_ok/pick_one
    pool_from: str | None = None              # flow 的候选来自词池（candidates_from）
    legacy_type: str | None = None            # 未折叠的旧 type
    raw: dict = field(default_factory=dict)


# ---------------- 工具 ----------------

def _xy(act: dict) -> tuple[float, float]:
    """取 (x, y)。**保留原值，绝不取整** —— 0~1 是比例坐标。"""
    try:
        return float(act["x"]), float(act["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"坐标动作缺少合法 x/y: {act!r}") from exc


def _on_miss(act: dict) -> str:
    """optional: false -> fail；其余（含未写）-> skip。

    注意：这是**块级**语义，描述"整个 step 没命中时该不该算失败"。
    它不改变原语的返回值 —— `click_first` 作为 any_of 分支时全 miss 仍返回 False，
    否则 any_of 会在第 1 个分支就收工（见 behavior_runner._step_any_of docstring）。
    """
    return "fail" if act.get("optional") is False else "skip"


def _base(act: dict) -> dict:
    return {"expect": act.get("expect") or None,
            "on_miss": _on_miss(act),
            "label": str(act.get("desc") or "")}


def _fallback_points(act: dict) -> tuple[tuple[float, float], ...]:
    """解析 target.fallback：接受 [[x,y]] / [{"point":[x,y]}] / {"point":[x,y]}。"""
    out: list[tuple[float, float]] = []
    fbs = act.get("fallback")
    if not fbs:
        return ()
    if isinstance(fbs, dict):
        fbs = [fbs]
    for fb in fbs:
        pt = None
        if isinstance(fb, (list, tuple)) and len(fb) == 2:
            pt = (float(fb[0]), float(fb[1]))
        elif isinstance(fb, dict) and "point" in fb:
            v = fb["point"]
            if isinstance(v, (list, tuple)) and len(v) == 2:
                pt = (float(v[0]), float(v[1]))
        if pt is not None:
            out.append(pt)
    return tuple(out)


def _target_from_fields(act: dict, by: str | None = None,
                        value: str | None = None) -> Target:
    """从 act 构造 Target。显式 by/value 优先，否则按字段推断。"""
    if by is None:
        if "text" in act:
            by = "text"
        elif "res_id" in act:
            by = "id"
        elif "desc" in act and act.get("desc"):
            by = "desc"
        elif "value" in act:
            by = "text"
        else:
            raise ValueError(f"action=click 缺少 by 或定位字段: {act!r}")
    by = by.strip().lower()
    if by not in ("text", "id", "desc", "image", "vision"):
        raise ValueError(f"未知 click by: {by!r}")

    if value is None:
        field_name = {"text": "text", "id": "res_id", "desc": "desc",
                      "image": "value", "vision": "value"}[by]
        value = str(act.get(field_name, "") or "")

    pool: list[str] = []
    for v in (act.get("pool") or []):
        pool.append(str(v))
    if not pool:
        # 兼容 candidates 写法（每个 candidate 的 value）
        for c in (act.get("candidates") or []):
            if isinstance(c, dict) and c.get("value"):
                pool.append(str(c["value"]))

    return Target(by=by, value=str(value), pool=tuple(pool),
                  search=str(act["search"]) if act.get("search") else None,
                  fallback=_fallback_points(act),
                  vision=bool(act.get("vision", True)))


# ---------------- 各分支编译 ----------------

def _compile_click_point(act: dict) -> Step:
    """click_point 拆两种（任务书 §5.6）。

    注意 x/y **不是必填**：实测 72 个顶层 click_point 里，有 53 个只写 `images`
    没有坐标（纯视觉锚点，命中不了就算未命中，没有兜底可言）。
    只有"既给图像又给坐标"的 8 个才产生 fallback。
    """
    imgs = act.get("images") or ([act["template"]] if act.get("template") else [])
    vlm = act.get("vlm_prompt") or act.get("prompt")
    has_xy = "x" in act and "y" in act
    if imgs or vlm:
        by = "image" if imgs else "vision"
        value = str(imgs[0]) if imgs else str(vlm)
        fb = (_xy(act),) if has_xy else ()
        target = Target(by=by, value=value, fallback=fb,
                        vision=bool(act.get("vision", True)))
        return Step(action="click", target=target, raw=act, **_base(act))
    # 无锚点：必须是纯坐标
    x, y = _xy(act)
    return Step(action="tap", point=(x, y), raw=act, **_base(act))


def _compile_flow(act: dict, flow_name: str, kind: str) -> Step:
    branches: list[tuple[Step, ...]] = []
    if kind == "flow_via_branches":
        # click_first：每个 candidate 一条单步分支
        for c in (act.get("candidates") or []):
            if not isinstance(c, dict):
                continue
            val = str(c.get("value") or "")
            if not val:
                continue
            by = str(c.get("type") or "text").lower()
            by = {"res_id": "id"}.get(by, by)
            if by not in ("text", "id", "desc"):
                continue
            field_name = {"text": "text", "id": "res_id", "desc": "desc"}[by]
            branches.append((Step(action="click",
                                  target=Target(by=by, value=val),
                                  raw={field_name: val, "type": "click_text",
                                       "by": by},
                                  **_base({})),))
    else:
        for ch in (act.get("choices") or []):
            steps = ch if isinstance(ch, list) else [ch]
            branch = tuple(compile_step(a) for a in steps if isinstance(a, dict))
            if branch:
                branches.append(branch)
    # `candidates_from: sign` = 候选由词池在运行期提供，静态 candidates 可以为空。
    # 这是合法写法（实测 2 处：飞猪旅行/米读极速版的 sign 链），不能当配置错误。
    pool_from = None
    if not branches and act.get("candidates_from"):
        pool_from = str(act["candidates_from"])
    return Step(flow=flow_name, branches=tuple(branches), pool_from=pool_from,
                raw=act, **_base(act))


def _compile_action_from_v1(act: dict, name: str, extra: tuple) -> Step:
    """旧 type -> action（swipe / press / wait / extract）。"""
    if name == "swipe":
        return Step(action="swipe", raw=act, **_base(act))
    if name == "press":
        key = extra[0] if extra else "back"
        return Step(action="press", key=key, raw=act, **_base(act))
    if name == "wait":
        secs = None
        if extra and extra[0] == "seconds":
            try:
                secs = float(act.get("seconds", 1.0))
            except (TypeError, ValueError):
                secs = 1.0
        # think = wait + 拟人抖动；S1 只记 seconds=None 表示"由 human 决定时长"
        return Step(action="wait", seconds=secs, raw=act, **_base(act))
    if name == "extract":
        return Step(action="extract", raw=act, **_base(act))
    raise ValueError(f"内部映射错误：旧 type 无法折叠到 action={name!r}")


def _compile_v2_action(act: dict, action: str) -> Step:
    if action not in ACTION_NAMES:
        raise ValueError(f"未知 action: {action!r}")
    if action == "click":
        return Step(action="click", target=_target_from_fields(act),
                    raw=act, **_base(act))
    if action == "tap":
        x, y = _xy(act)
        return Step(action="tap", point=(x, y), raw=act, **_base(act))
    if action == "press":
        key = str(act.get("key") or "").strip().lower()
        if key not in ("back", "home"):
            raise ValueError(f"action=press 缺少合法 key（back/home）: {act!r}")
        return Step(action="press", key=key, raw=act, **_base(act))
    if action == "wait":
        secs = act.get("seconds")
        try:
            secs_f = float(secs) if secs is not None else None
        except (TypeError, ValueError):
            secs_f = None
        return Step(action="wait", seconds=secs_f, raw=act, **_base(act))
    if action == "swipe":
        return Step(action="swipe", raw=act, **_base(act))
    if action == "extract":
        return Step(action="extract", raw=act, **_base(act))
    if action == "input":
        return Step(action="input", raw=act, **_base(act))
    raise ValueError(f"未知 action: {action!r}")


# ---------------- 主入口 ----------------

def compile_step(act: dict) -> Step:
    """单个 step dict -> Step。v1（只有 type）与 v2（action/flow/macro）都接受。"""
    if not isinstance(act, dict):
        raise ValueError(f"step 必须是 dict，收到 {type(act).__name__}")

    t = act.get("type")
    a = act.get("action")
    f = act.get("flow")
    m = act.get("macro")

    # 1) 三个主键互斥
    primaries = [x for x in (a, f, m) if x]
    if len(primaries) > 1:
        raise ValueError(f"action/flow/macro 同时出现多个: {primaries!r}")

    # 2) type 与主键并存：只允许"语义等价"的写法，其余一律拒绝（不许猜）
    if t and primaries:
        ok = False
        if a and t == a:
            ok = True
        elif a and LEGACY_TO_V2.get(t, (None,))[0] == "action+field" \
                and LEGACY_TO_V2[t][1] == a:
            ok = True                     # type: click_text + action: click
        elif f and LEGACY_TO_V2.get(t, (None,))[0] in ("flow_via_branches",
                                                       "flow_via_choices") \
                and LEGACY_TO_V2[t][1] == f:
            ok = True                     # type: any_of + flow: first_ok
        elif m and LEGACY_TO_V2.get(t, (None,))[0] == "macro" \
                and LEGACY_TO_V2[t][1] == m:
            ok = True
        if not ok:
            raise ValueError(f"type 与主键冲突: type={t!r} "
                             f"action={a!r} flow={f!r} macro={m!r}")

    # 3) 纯 v2 写法
    if a:
        return _compile_v2_action(act, a)
    if f:
        if f not in FLOW_NAMES:
            raise ValueError(f"未知 flow: {f!r}（合法值 {sorted(FLOW_NAMES)}）")
        return _compile_flow(act, f, "flow_via_choices")
    if m:
        if m not in MACRO_NAMES:
            raise ValueError(f"未知 macro: {m!r}（合法值 {sorted(MACRO_NAMES)}）")
        return Step(macro=m, raw=act, **_base(act))

    # 4) v1 写法
    if not t:
        raise ValueError(f"step 缺少 type 或 action/flow/macro: {act!r}")
    spec = LEGACY_TO_V2.get(t)
    if spec is None:
        raise ValueError(f"未知 type: {t!r}（未在 LEGACY_TO_V2 登记，拒绝静默忽略）")

    kind = spec[0]
    if kind == "action":
        return _compile_action_from_v1(act, spec[1], tuple(spec[2:]))
    if kind == "action+field":
        _, name, fld, by = spec
        target = _target_from_fields(act, by=by, value=str(act.get(fld, "") or ""))
        return Step(action=name, target=target, raw=act, **_base(act))
    if kind in ("flow_via_branches", "flow_via_choices"):
        return _compile_flow(act, spec[1], kind)
    if kind == "click_point":
        return _compile_click_point(act)
    if kind == "macro":
        return Step(macro=spec[1], raw=act, **_base(act))
    if kind == "v2_click":
        return _compile_v2_action(act, "click")
    if kind == "legacy":
        return Step(legacy_type=spec[1], raw=act, **_base(act))
    raise ValueError(f"内部映射错误: type={t!r} spec={spec!r}")


def compile_actions(actions: list) -> list:
    """批量编译。行为可能是 [[..],[..]] 多候选模板，编译后保持两级结构。"""
    if not actions:
        return []
    if all(isinstance(x, list) for x in actions):
        return [compile_actions(grp) for grp in actions]
    return [compile_step(x) for x in actions]


# ---------------- 语义投影（对拍用） ----------------

def _category_of(name: str) -> str:
    if name in _V2_CATEGORY:
        return _V2_CATEGORY[name]
    try:
        import behavior_runner as br
        return br.ACTION_CATEGORY.get(name, "unknown")
    except ImportError:
        return "unknown"


def project(step: Step) -> tuple:
    """把 Step 投影成可比较的元组，用于新旧对拍。

    字段固定：(category, kind_name, by, selector, on_miss, vision, label)
    关键点：`click_text` 与 `click`+`by:text` 必须投影出**同一个值** ——
    category 走 9 分类口径，selector 取 target.value，所以两者天然相等。
    """
    if step.legacy_type:
        return (_category_of(step.legacy_type), step.legacy_type,
                "", "", step.on_miss, True, step.label)
    if step.action:
        sel = ""
        by = ""
        vision = True
        if step.target:
            by = step.target.by
            sel = step.target.value or "|".join(step.target.pool)
            vision = step.target.vision
        if step.point is not None:
            sel = f"{step.point[0]:g},{step.point[1]:g}"
        return (_category_of(step.action), step.action, by, sel,
                step.on_miss, vision, step.label)
    if step.flow:
        return (_category_of("any_of"), step.flow, "", "",
                step.on_miss, True, step.label)
    if step.macro:
        return (_category_of(step.macro), step.macro, "", "",
                step.on_miss, True, step.label)
    return ("unknown", "", "", "", step.on_miss, True, step.label)


# ---------------- 编译期 lint（任务书 §3.1） ----------------

_DEAD_OPTIONAL_TYPES = frozenset({"click_text", "click_id", "click_desc",
                                  "click_point"})


def lint(steps: list, app_name: str = "", behavior: str = "") -> list[dict]:
    """编译期校验。返回 [{level, app, behavior, msg}]。

    ERROR 应阻断（配置写错，跑起来必然静默失败）；WARN/INFO 只提示。
    注意：WARN 不改变任何行为，也不自动改写配置 —— 死字段要人来确认。
    """
    issues: list[dict] = []

    def _add(level: str, msg: str) -> None:
        issues.append({"level": level, "app": app_name,
                       "behavior": behavior, "msg": msg})

    def _walk(items) -> None:
        for s in items:
            if isinstance(s, list):
                _walk(s)
                continue
            if not isinstance(s, Step):
                continue
            if s.legacy_type:
                _add("INFO", f"legacy step 待折叠: type={s.legacy_type}")
            if s.action == "click" and s.target is None:
                _add("ERROR", "action=click 缺少 target")
            if s.target and s.target.by == "image" and not s.target.vision:
                _add("WARN", "by=image 且 vision:false 自相矛盾（锚点永不生效）")
            if s.flow and not s.branches and not s.pool_from:
                _add("ERROR", f"flow={s.flow} 既无 branches 也无 candidates_from")
            if s.pool_from:
                _add("INFO", f"flow={s.flow} 候选由词池动态提供: "
                             f"candidates_from={s.pool_from}")
            raw_t = (s.raw or {}).get("type")
            if raw_t in _DEAD_OPTIONAL_TYPES and "optional" in (s.raw or {}):
                _add("WARN", f"type={raw_t} 上的 optional 是死字段"
                             f"（执行层从不读），批量转 on_miss 会改变行为")
            if s.branches:
                _walk(list(s.branches))

    _walk(steps)
    return issues
