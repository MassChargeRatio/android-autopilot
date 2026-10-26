# -*- coding: utf-8 -*-
"""test_click_first_pool.py - R1：_step_click_first 知识库展开合一（AUTOP-REFINE-2026-10-21）

R1 把 _step_click_first 里「显式 candidates」与「词表 candidates」两段几乎相同的
kb 展开（_kb_candidates -> _parse_sel -> 去重入 pool）抽为共享 helper
`_expand_kb_pool(app_name, pool, primary)`，行为零变化：

  * 无知识库记录（kb_cands=[primary]）-> 加入 pool，primary 传 None（原语义）；
  * 知识库 disabled（kb_cands=[]）-> 返回 False，调用点跳过该候选；
  * 有记录且启用 -> 主 + alternatives 全部按 (k,v) 去重追加，primary 透传。

锁定三例（均可红：helper 未实现时 AttributeError）：
  1. 同一候选经 kb 展开只入池一次（去重）；
  2. 词表候选追加在显式之后（顺序）；
  3. kb disabled 候选被跳过。

运行：
    python -m pytest tests/test_click_first_pool.py -q
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
        self.hits = set(hits)
        self.calls = []

    def __call__(self, k, v, timeout=2.0, zone=None, screen_w=0):
        self.calls.append((k, v, zone))
        if v in self.hits:
            return LocateResult(True, {"kind": k, "value": v}, "测试命中")
        return LocateResult(False, None, "测试未命中")


def _mk(script=None):
    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=True, config={})
    ex.dry_run = False
    ex._locate = script or _HitList(set())
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    ex._click_obj = lambda obj, relocate=None: None
    ex._app_extras = lambda app: {}
    return ex


def t_expand_kb_pool_no_record_adds_primary_none():
    """无知识库记录：kb_cands=[primary]，入池且 primary=None（原语义）。"""
    ex = _mk()
    pool = []
    assert ex._expand_kb_pool("T", pool, "text=签到") is True
    assert pool == [("text", "签到", None)], pool
    print("OK  kb 无记录时入池且 primary=None")


def t_expand_kb_pool_disabled_returns_false():
    """知识库 disabled（kb_cands=[]）：返回 False，不入池。"""
    ex = _mk()
    ex._kb_candidates = lambda app, primary: ([], True)
    pool = [("text", "签到", None)]
    assert ex._expand_kb_pool("T", pool, "text=签到") is False
    assert pool == [("text", "签到", None)], "disabled 不应改动 pool"
    print("OK  kb disabled 返回 False 且不入池")


def t_expand_kb_pool_dedup_and_primary():
    """有记录且启用：主 + alternatives 展开，(k,v) 已存在的不重复追加。"""
    ex = _mk()
    ex._kb_candidates = lambda app, primary: (
        ["text=签到", "id=btn_sign", "text=签到"], True)
    pool = [("text", "签到", "text=签到")]
    assert ex._expand_kb_pool("T", pool, "text=签到") is True
    assert pool == [("text", "签到", "text=签到"),
                    ("id", "btn_sign", "text=签到")], pool
    print("OK  kb 展开去重、primary 透传")


def t_explicit_dup_enters_pool_once():
    """同一候选经 kb 展开只入池一次：重复显式候选只尝试一次。"""
    script = _HitList({"签到"})
    ex = _mk(script)
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "签到"},
                          {"type": "text", "value": "签到"}]}
    assert ex._step_click_first(act, "T") is True
    assert script.calls == [("text", "签到", None)], script.calls
    print("OK  显式重复候选只入池一次")


def t_words_after_explicit_order():
    """词表候选追加在显式之后：调用顺序先显式后词表（精确定向优先）。"""
    script = _HitList({"立即签到"})
    ex = _mk(script)
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "今日签到"}],
           "candidates_from": "sign"}
    assert ex._step_click_first(act, "T") is True
    values = [c[1] for c in script.calls]
    assert values == ["今日签到", "立即签到"], values
    print("OK  词表候选追加在显式之后")


def t_kb_disabled_candidate_skipped():
    """kb disabled 候选被跳过：其 value 不会被尝试。"""
    script = _HitList({"签到"})
    ex = _mk(script)
    # 显式「今日签到」被知识库 disabled；词表「签到」正常
    ex._kb_candidates = lambda app, primary: (
        ([], True) if primary == "text=今日签到" else ([primary], False))
    act = {"type": "click_first",
           "candidates": [{"type": "text", "value": "今日签到"}],
           "candidates_from": "sign"}
    assert ex._step_click_first(act, "T") is True
    values = [c[1] for c in script.calls]
    assert "今日签到" not in values, values
    assert "签到" in values, values
    print("OK  kb disabled 候选被跳过、其余正常入池")


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
