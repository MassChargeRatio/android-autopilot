# -*- coding: utf-8 -*-
"""test_unified_steps.py - 2026-10-25 「behavior/type 重新规划整理」回归钉

背景：整理前三处重复/失效，靠这个文件钉住，防止改回去：
  ① click_text / click_id / click_desc 是同一段代码的三份拷贝 →
     合并为统一点击原语 `click`（by=text/id/desc），旧名字降级为别名；
  ② `swipe` 写 `natural: true` 时**忽略 from/to** 且永远向下滑
     （抖音火山版校准实测踩到：想上滑回顶，结果连滑到底）→ 已修；
  ③ behavior 名出现中文（快手「白拿礼物」）→ 收编为标准意图 gift；
     抖音火山版「没有签到只有预约」→ behavior 改名 reserve + intent_map 映射。

运行：
    python tests/test_unified_steps.py
"""
import os
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


class _Traj:
    def __init__(self):
        self.calls = []

    def generate_gesture(self, start, end, **kw):
        self.calls.append((start, end))
        return ([(start[0], start[1]), (end[0], end[1])], [0.1])

    def inject_touch(self, d, points, intervals):
        return True


class _Human:
    def __init__(self):
        self.trajectory = _Traj()
        self.natural_calls = 0

    def natural_swipe(self, d):
        self.natural_calls += 1

    def delay(self, *a):
        pass

    def maybe_wander(self, *a):
        pass

    def think(self, *a):
        pass

    def tap(self, *a, **k):
        pass


class _Dev:
    def __init__(self):
        self.swipes = []
        self.presses = []

    def swipe(self, sx, sy, ex, ey, duration=0.5):
        self.swipes.append((sx, sy, ex, ey))

    def press(self, key):
        self.presses.append(key)


def _mk():
    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=True, config={})
    ex._locate = lambda k, v, timeout=2.0: LocateResult(False, None, "测试未命中")
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    return ex


# ---------- ① 统一点击原语 ----------

def t_click_unified_hit_logs_same_as_before():
    """click by=text 命中时日志必须是「点击文本: X」（与旧 click_text 逐字一致）。"""
    ex = _mk()
    ex._locate_with_kb = lambda app, primary, timeout=6: (object(), False, True)
    act = {"type": "click", "by": "text", "text": "赚钱", "timeout": 8}
    assert ex._step_click(act, "T") is True
    assert any("点击文本: 赚钱" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  click by=text 命中日志与旧 click_text 一致")


def t_click_unified_id_and_desc():
    for by, field, value, verb in (("id", "res_id", "iv_btn", "点击控件"),
                                   ("desc", "desc", "领火苗，按钮", "点击描述")):
        ex = _mk()
        ex._locate_with_kb = lambda app, primary, timeout=6: (object(), False, True)
        act = {"type": "click", "by": by, field: value}
        assert ex._step_click(act, "T") is True
        assert any(f"{verb}: {value}" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  click by=id / by=desc 日志动词正确")


def t_click_alias_equivalent_to_unified():
    """别名与统一原语必须完全等价：命中日志一致、未命中 _last_fail 一致。"""
    for alias, by in (("click_text", "text"), ("click_id", "id"), ("click_desc", "desc")):
        ex_a, ex_b = _mk(), _mk()
        # 命中分支
        ex_a._locate_with_kb = lambda app, primary, timeout=6: (object(), False, True)
        ex_b._locate_with_kb = lambda app, primary, timeout=6: (object(), False, True)
        act_a = {"type": alias, "text": "X", "res_id": "X", "desc": "X"}
        act_b = dict(act_a, by=by)
        ra = getattr(ex_a, f"_step_{alias}")(act_a, "T")
        rb = ex_b._step_click(act_b, "T")
        assert ra is rb is True, (alias, ra, rb)
        assert ex_a.recorder.lines == ex_b.recorder.lines, (alias, ex_a.recorder.lines,
                                                            ex_b.recorder.lines)
        # 未命中分支
        ex_c, ex_d = _mk(), _mk()
        rc = getattr(ex_c, f"_step_{alias}")(act_a, "T")
        rd = ex_d._step_click(act_b, "T")
        assert rc is rd is False, (alias, rc, rd)
        assert ex_c._last_fail == ex_d._last_fail, (alias, ex_c._last_fail,
                                                    ex_d._last_fail)
    print("OK  click_text/click_id/click_desc 与统一点击原语完全等价")


def t_click_unknown_by_is_rejected():
    ex = _mk()
    ok = ex._step_click({"type": "click", "by": "xpath", "text": "X"}, "T")
    assert ok is False
    assert "未知 click by" in (ex._last_fail or ""), ex._last_fail
    print("OK  未知 by 返回 False 并记录 detail（不静默点错东西）")


def t_dispatch_table_has_click_and_aliases():
    """分派表必须同时认 click 与三个旧名（老配置不改也能跑）。"""
    src = open(os.path.join(ROOT, "behavior_runner.py"), encoding="utf-8").read()
    for t in ('"click": self._step_click', '"click_text": self._step_click_text',
              '"click_id": self._step_click_id', '"click_desc": self._step_click_desc',
              '"swipe_natural": self._step_swipe_natural'):
        assert t in src, f"分派表缺少 {t}"
    assert "click" in br._VISION_GATED_STEPS, br._VISION_GATED_STEPS
    print("OK  分派表含统一点击与全部别名，且 click 在视觉门控集合内")


# ---------- ② swipe natural 尊重 from/to（本次修的 bug） ----------

def _run_swipe(act, natural=True):
    ex = _mk()
    ex.d = _Dev()
    ex.dry_run = False
    br.win_wh = lambda d: (1080, 2340)  # 钉住窗口尺寸，坐标可算
    ex._step_swipe(act, "T")
    return ex


def t_swipe_natural_respects_from_to():
    """natural:true + from/to 必须按坐标走轨迹，而不是随机向下滑。"""
    ex = _run_swipe({"type": "swipe", "natural": True,
                     "from": [0.5, 0.25], "to": [0.5, 0.78], "duration": 0.45})
    assert ex.human.trajectory.calls == [((540, 585), (540, 1825))], \
        ex.human.trajectory.calls
    assert ex.human.natural_calls == 0, "natural+from/to 不应走随机滑动"
    assert any("滑动(轨迹)" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  natural:true 尊重 from/to（bug 已修，坐标 540,585 -> 540,1825）")


def t_swipe_natural_without_coords_stays_random():
    """省略 from/to 时保留旧的随机自然滑动语义（recorder 录制的 swipe_natural）。"""
    ex = _run_swipe({"type": "swipe", "natural": True})
    assert ex.human.natural_calls == 1, "无坐标时应走随机自然滑动"
    assert any("自然滑动(随机)" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  natural:true 无坐标时仍是随机自然滑动（向后兼容）")


def t_swipe_natural_alias_matches_swipe():
    ex = _run_swipe({"type": "swipe_natural",
                     "from": [0.5, 0.25], "to": [0.5, 0.78]})
    assert ex.human.trajectory.calls == [((540, 585), (540, 1825))], \
        ex.human.trajectory.calls
    assert ex.human.natural_calls == 0
    print("OK  swipe_natural 别名与 swipe+natural 行为一致")


def t_swipe_plain_still_uses_trajectory():
    ex = _run_swipe({"type": "swipe", "from": [0.5, 0.7], "to": [0.5, 0.3]})
    assert ex.human.trajectory.calls == [((540, 1638), (540, 702))], \
        ex.human.trajectory.calls
    print("OK  普通 swipe 仍走人类轨迹（行为未变）")


def t_swipe_returns_true_contract_satisfied():
    """契约回归钉：swipe 成功路径必须返回 True（gesture 契约只认 bool）。

    2026-10-31 全量 35 app 实测：`_step_swipe` 所有成功路径都是裸 return（返回 None），
    `_check_return` 见 None ∉ {bool} → 记「返回值契约违反: swipe(gesture) 返回 None」
    并把已真实执行的滑动判成失败。全量 17 处 / 16 app 因此误报（拼多多/一淘/抖音…）。
    本钉：改后 swipe 成功必须返回 True，且经 `_run_kind` 契约检查不违反。
    """
    # 有 from/to → 人类轨迹路径
    ex = _mk()
    ex.d = _Dev()
    ex.dry_run = False
    br.win_wh = lambda d: (1080, 2340)
    act = {"type": "swipe", "from": [0.5, 0.7], "to": [0.5, 0.3]}
    assert ex._step_swipe(act, "T") is True
    assert ex._run_kind(act, "T") is True
    # 无 from/to + natural → 随机自然滑动路径
    ex2 = _mk()
    ex2.d = _Dev()
    ex2.dry_run = False
    act2 = {"type": "swipe", "natural": True}
    assert ex2._step_swipe(act2, "T") is True
    assert     ex2._run_kind(act2, "T") is True
    print("OK  swipe 成功路径返回 True，契约不违反（修复 返回值契约违反 误报）")


def t_key_back_home_return_true_contract_satisfied():
    """契约回归钉：back/home（key 类别）成功路径必须返回 True。

    2026-10-31 全量实测：`_step_back`/`_step_home` 成功路径无 return（返回 None），
    key 契约只认 bool → 记「返回值契约违反: back(key) 返回 None」并判失败
    （今晚 飞猪旅行 1 处）。本钉：改后 back/home 成功必须返回 True 且 `_run_kind` 不违反。
    """
    ex = _mk()
    ex.d = _Dev()
    ex.dry_run = False
    assert ex._step_back({"type": "back"}, "T") is True
    assert ex._run_kind({"type": "back"}, "T") is True
    assert ex._step_home({"type": "home"}, "T") is True
    assert ex._run_kind({"type": "home"}, "T") is True
    assert "back" in ex.d.presses and "home" in ex.d.presses, ex.d.presses
    print("OK  back/home 成功路径返回 True，契约不违反（修复 back 返回值契约违反 误报）")


# ---------- ③ behavior 名规范化 ----------

def t_nlu_sign_not_hijacked_by_growth():
    """「签到领金币」必须解析成 sign —— growth 的「签到领」关键词已删。"""
    intents = [i for i, _ in nlu.parse_intents("帮我签到领金币")]
    assert intents and intents[0] == "sign", intents
    print("OK  「签到领金币」解析为 sign（不再被 growth 劫持）")


def t_nlu_gift_and_reserve_intents():
    assert ("gift", "白拿礼物") in nlu.parse_intents("去快手白拿礼物"), \
        nlu.parse_intents("去快手白拿礼物")
    assert ("reserve", "预约") in nlu.parse_intents("抖音火山版预约"), \
        nlu.parse_intents("抖音火山版预约")
    print("OK  gift / reserve 意图可被自然语言命中")


def t_config_behavior_names_are_ascii():
    """全部 34 个 app 的 behavior 名必须是小写 ASCII（中文名无法被意图命中）。"""
    cfg = load_config(os.path.join(ROOT, "config.yaml"))
    bad = []
    for a in cfg["apps"]:
        for bid in (a.get("behaviors") or {}):
            if not bid.isascii() or bid != bid.lower():
                bad.append((a["name"], bid))
    assert not bad, f"非规范 behavior 名: {bad}"
    print(f"OK  {len(cfg['apps'])} 个 app 的 behavior 名全部规范（无中文/无大写）")


def t_config_huoshan_sign_routes_to_reserve():
    cfg = load_config(os.path.join(ROOT, "config.yaml"))
    app = next(a for a in cfg["apps"] if a["name"] == "抖音火山版")
    assert app["intent_map"].get("sign") == "reserve", app.get("intent_map")
    assert "reserve" in app["behaviors"], list(app["behaviors"])
    print("OK  抖音火山版：sign 意图 → reserve 行为（没有签到只有预约）")


def t_config_kuaishou_gift_behavior():
    cfg = load_config(os.path.join(ROOT, "config.yaml"))
    app = next(a for a in cfg["apps"] if a["name"] == "快手")
    assert "gift" in app["behaviors"], list(app["behaviors"])
    print("OK  快手：白拿礼物 → gift（标准意图名）")


def t_dedup_consecutive_same_behavior_dry():
    """2026-11-01 抖音火山版三连超时根因：sign→reserve + reserve→reserve 使
    reserve 行为跑两遍（每遍 ~150-200s），叠加冷启动间隔与 watch 后单 app 超
    300s 上限。去重后 dry-run 预览只显示一遍 reserve，并提示跳过重复。"""
    app_cfg = {
        "name": "T", "package": "com.t",
        "intent_map": {"sign": "reserve", "watch": "watch"},
        "behaviors": {"reserve": [{"type": "wait", "seconds": 1}],
                      "watch": [{"type": "wait", "seconds": 1}]},
    }
    rec = _Rec()
    ex = Executor("fake-serial", _Human(), rec, dry_run=True, config={})
    ex.run_app_flow(app_cfg, [("sign", "签到"), ("reserve", "预约"),
                              ("bonus", "领红包"), ("watch", "看视频")])
    joined = "\n".join(rec.lines)
    assert joined.count("行为[reserve]:") == 1, joined
    assert joined.count("行为[watch]:") == 1, joined
    assert "未配置行为，跳过" in joined, joined   # bonus 无行为
    assert "跳过重复执行" in joined, joined      # reserve→reserve 去重
    print("OK  去重：dry-run 连续同行为只显示一遍（sign→reserve + reserve→reserve 收敛为一次）")


def t_dedup_consecutive_same_behavior_real():
    """真实执行路径：连续同行为只跑一次，不重复执行。"""
    app_cfg = {
        "name": "T", "package": "com.t",
        "intent_map": {"sign": "reserve", "watch": "watch"},
        "behaviors": {"reserve": [{"type": "wait", "seconds": 1}],
                      "watch": [{"type": "wait", "seconds": 1}]},
    }
    ran = []
    rec = _Rec()
    ex = Executor("fake-serial", _Human(), rec, dry_run=False, config={})
    ex._open_app = lambda pkg, name, reset=False: None
    ex._run_actions = lambda actions, name, bid: ran.append(bid) or True
    ex._reset_to_landing = lambda pkg, name, max_back=3, launch_reset=False, launch_back=0: None
    ex._maybe_sweep_popups = lambda *a, **k: None
    ex._close_app = lambda name: None
    ex.human.think = lambda *a, **k: None
    ex.run_app_flow(app_cfg, [("sign", "签到"), ("reserve", "预约"),
                              ("bonus", "领红包"), ("watch", "看视频")])
    assert ran == ["reserve", "watch"], ran
    joined = "\n".join(rec.lines)
    assert "跳过重复执行" in joined, joined
    print("OK  去重：真实路径 reserve 只跑一次，bonus 跳过，watch 跑一次")


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
            print(f"ERROR {fn.__name__}: {type(e).name__ if False else type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
