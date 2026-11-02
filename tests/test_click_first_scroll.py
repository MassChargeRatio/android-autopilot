# -*- coding: utf-8 -*-
"""test_click_first_scroll.py - 第2步：click_first 滚动重试 scroll_retry（AUTOP-SELFSEARCH-2026-10-20）

用户原话：「应该总结这些app的领现金过程中…常用步骤的共性，使程序自己有一套思路，
不用依赖外部描述而能自己搜寻」——入口按钮常不在首屏（如「任务中心」在二级页），
引擎需要能自己翻页找。`scroll_retry: N` = 候选全未命中后自然向下滑动 N 次再重试。

语义：
  * 默认 0 = 旧行为（绝不滑动），回归保护；
  * scroll 只发生在「一轮全 miss」之后，首轮命中绝不滑动；
  * N 次滚动后仍未命中：行为与原逻辑完全一致（optional 放行 / 记 _last_fail）。

运行：
    python -m pytest tests/test_click_first_scroll.py -q
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
    def __init__(self):
        self.swipes = 0

    def delay(self, *a):
        pass

    def maybe_wander(self, *a):
        pass

    def think(self):
        pass

    def natural_swipe(self, d):
        self.swipes += 1


class _ScriptLocate:
    """按已发生滑动次数演进的 _locate 桩：滑满 hit_after 次才对 text 命中。"""

    def __init__(self, human, hit_after):
        self.human = human
        self.hit_after = hit_after
        self.calls = []

    def __call__(self, k, v, timeout=2.0):
        self.calls.append((k, v))
        if self.human.swipes >= self.hit_after:
            return LocateResult(True, {"kind": k, "value": v}, "测试命中")
        return LocateResult(False, None, "测试未命中")


def _mk(script, human):
    ex = Executor("fake-serial", human, _Rec(), dry_run=True, config={})
    ex.dry_run = False          # 让命中分支真正走到 _click_obj（桩）
    ex._locate = script
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    ex._click_obj = lambda obj, relocate=None: None
    return ex


def _act(retry, optional=True):
    return {"type": "click_first",
            "candidates": [{"type": "text", "value": "签到"}],
            "scroll_retry": retry, "optional": optional}


def t_default_zero_no_swipe():
    """无 scroll_retry（默认 0）：未命中不滑动（旧行为回归保护）。"""
    h = _Human()
    ex = _mk(_ScriptLocate(h, hit_after=99), h)
    assert ex._step_click_first(_act(0, optional=False), "T") is False
    assert h.swipes == 0, f"默认不应滑动，实际 {h.swipes}"
    assert ex._last_fail and "所有候选均未出现" in ex._last_fail, ex._last_fail
    print("OK  默认 scroll_retry=0 不滑动")


def t_scroll_one_then_hit():
    """scroll_retry=1：首轮全 miss -> 滑动一次 -> 命中并点击。"""
    h = _Human()
    ex = _mk(_ScriptLocate(h, hit_after=1), h)
    assert ex._step_click_first(_act(1), "T") is True
    assert h.swipes == 1, f"应恰好滑动 1 次，实际 {h.swipes}"
    assert any("多候选命中并点击" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  scroll_retry=1 滑动一次后命中并点击")


def t_scroll_exhausted_returns_false():
    """scroll_retry=2：两轮全 miss -> 恰好滑动 2 次 -> 返回 False。

    2026-10-29 复核：本用例原先用 optional=True（_act 默认）断言 False，看起来
    像在钉一个矛盾，其实钉的是**必须保留**的语义 —— click_first 常作为 any_of 的
    分支，any_of 靠这个返回值判「分支是否命中」。若 optional 全 miss 返回 True，
    any_of 会在第 1 个分支就收工，后面的兜底分支永不执行。
    故保留 False，并补一条用例钉住"日志不得再写放行"。
    """
    h = _Human()
    ex = _mk(_ScriptLocate(h, hit_after=99), h)
    assert ex._step_click_first(_act(2, optional=False), "T") is False
    assert h.swipes == 2, f"应恰好滑动 2 次，实际 {h.swipes}"
    print("OK  scroll_retry=2 滑满仍 miss 返回 False")


def t_scroll_exhausted_optional_still_false_and_log_honest():
    """optional=True 且全 miss：返回值仍是 False（any_of 依赖），日志不得说"放行"。

    这两件事必须同时成立：返回值承载 any_of 的分支判定，日志承载人的判断。
    历史上二者相反（日志写放行、返回值 False），读日志的人会以为这步没失败。
    """
    h = _Human()
    ex = _mk(_ScriptLocate(h, hit_after=99), h)
    assert ex._step_click_first(_act(2), "T") is False
    assert h.swipes == 2, f"应恰好滑动 2 次，实际 {h.swipes}"
    joined = "\n".join(ex.recorder.lines)
    assert "optional 放行" not in joined, joined
    assert "optional 仅抑制告警" in joined, joined
    print("OK  optional 全 miss 仍返回 False，且日志不再谎称放行")


def t_no_scroll_when_first_round_hits():
    """首轮即命中：绝不滑动（scroll 只发生在全 miss 之后）。"""
    h = _Human()
    ex = _mk(_ScriptLocate(h, hit_after=0), h)
    assert ex._step_click_first(_act(2), "T") is True
    assert h.swipes == 0, f"首轮命中不应滑动，实际 {h.swipes}"
    print("OK  首轮命中不滑动")


# ---------- back_retry（AUTOP-FAMILY-2026-11-01）----------
# 与 scroll_retry 并列的重试机制：候选全未命中（且 scroll 用尽）时按 BACK
# 重新露出底层导航再扫。默认 0 = 行为不变；按 BACK 后校验前台，离开目标 App 停手。


class _BackD:
    """伪造设备：记录 BACK 次数；fg 恒为目标 App（不触发冷重启分支）。"""

    def __init__(self):
        self.back_presses = 0

    @property
    def info(self):
        return {"currentPackageName": "com.test.app"}

    def press(self, key):
        self.back_presses += 1


class _ScriptBack:
    """按已按 BACK 次数演进的 _locate 桩：按满 hit_after_back 次才对 text 命中。"""

    def __init__(self, d, hit_after_back):
        self.d = d
        self.hit_after_back = hit_after_back

    def __call__(self, k, v, timeout=2.0):
        if self.d.back_presses >= self.hit_after_back:
            return LocateResult(True, {"kind": k, "value": v}, "测试命中")
        return LocateResult(False, None, "测试未命中")


def _mk_back(script, d):
    ex = _mk(script, _Human())
    ex.d = d
    return ex


def _act_back(retry, optional=True):
    return {"type": "click_first",
            "candidates": [{"type": "text", "value": "签到"}],
            "back_retry": retry, "optional": optional}


def t_back_retry_default_zero_no_back():
    """无 back_retry（默认 0）：未命中不按 BACK（回归保护）。"""
    d = _BackD()
    ex = _mk_back(_ScriptBack(d, hit_after_back=99), d)
    assert ex._step_click_first(_act_back(0, optional=False), "T") is False
    assert d.back_presses == 0, f"默认不应按 BACK，实际 {d.back_presses}"
    assert ex._last_fail and "所有候选均未出现" in ex._last_fail, ex._last_fail
    print("OK  默认 back_retry=0 不按 BACK")


def t_back_retry_one_then_hit():
    """back_retry=1：首轮全 miss -> 按 1 次 BACK -> 命中并点击。"""
    d = _BackD()
    ex = _mk_back(_ScriptBack(d, hit_after_back=1), d)
    assert ex._step_click_first(_act_back(1), "T") is True
    assert d.back_presses == 1, f"应恰好按 1 次 BACK，实际 {d.back_presses}"
    assert any("多候选命中并点击" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  back_retry=1 按 1 次 BACK 后命中并点击")


def t_back_retry_exhausted_returns_false():
    """back_retry=2：三轮全 miss -> 恰好按 2 次 BACK -> 返回 False（any_of 语义保留）。"""
    d = _BackD()
    ex = _mk_back(_ScriptBack(d, hit_after_back=99), d)
    assert ex._step_click_first(_act_back(2, optional=False), "T") is False
    assert d.back_presses == 2, f"应恰好按 2 次 BACK，实际 {d.back_presses}"
    assert ex._last_fail and "所有候选均未出现" in ex._last_fail, ex._last_fail
    print("OK  back_retry=2 按满仍 miss 返回 False")


def t_back_retry_first_round_hits_no_back():
    """首轮即命中：绝不按 BACK。"""
    d = _BackD()
    ex = _mk_back(_ScriptBack(d, hit_after_back=0), d)
    assert ex._step_click_first(_act_back(2), "T") is True
    assert d.back_presses == 0, f"首轮命中不应按 BACK，实际 {d.back_presses}"
    print("OK  首轮命中不按 BACK")


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
