# -*- coding: utf-8 -*-
"""test_probe_pick.py - 探针候选挑选逻辑的单元测试（无需真机）

为什么必须测：
    `probe_deep` 报「二级入口」和「三级锚点」直接决定我们往 config 里写什么路径。
    挑错一次，就会写进一条**永远命不中的三级导航**（而且要下一轮才发现）。

这里固化两个关键决策：
  1. **可点击优先排序，但不硬过滤** —— 实测入口文案常常挂在不可点击的 text
     子节点上，真正可点的是父容器（一淘的「去福狸中心做任务」就是这种）。
     早期版本用「必须可点击」硬过滤，把整个入口滤掉了，导致漏判。
  2. **长文案拒配** —— `textContains` 会命中"长文案里恰好包含关键词"的节点
     （例如 FAQ 链接「什么是签到领钱，如何参加？」里含「签到」）。

运行：
    python tests/test_probe_pick.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "devtools"))

from probe_deep import find_all, find_first, _ok_len  # noqa: E402
from probe_sidebar import find_more, MORE_DESC  # noqa: E402


def _n(text="", desc="", cx=500, cy=1000, clickable=True, rid=""):
    return {"text": text, "desc": desc, "rid": rid, "center": (cx, cy),
            "size": (100, 100), "clickable": clickable,
            "bounds": (cx - 50, cy - 50, cx + 50, cy + 50)}


def t_ok_len_rejects_long_nonclickable():
    long_text = "什么是签到领钱，如何参加？" * 3
    assert not _ok_len(_n(text=long_text, clickable=False), "签到", "text")
    # 可点击的长文案不受限（可能是按钮整体）
    assert _ok_len(_n(text=long_text, clickable=True), "签到", "text")
    # 短文案接受
    assert _ok_len(_n(text="签到"), "签到", "text")
    print("OK  长文案拒配：不可点击的超长文本被拒，可点击的不受影响")


def t_find_first_prefers_clickable():
    nodes = [_n(text="任务中心", clickable=False, cy=300),
             _n(text="任务中心", clickable=True, cy=2100)]
    hit = find_first(nodes, ["任务中心"])
    assert hit is not None
    lab, c, kind = hit
    assert c == (500, 2100), f"应优先可点击的，实际 {c}"
    print("OK  find_first 优先返回可点击节点")


def t_find_first_without_hard_filter_keeps_nonclickable():
    """入口文案挂在不可点击的 text 上时，不能整个滤掉。"""
    nodes = [_n(text="去福狸中心做任务", clickable=False, cy=900)]
    hit = find_first(nodes, ["任务中心", "做任务"])
    assert hit is not None, "不可点击的入口不应被硬过滤掉"
    assert hit[0] == "去福狸中心做任务"
    print("OK  不做硬过滤：不可点击的入口仍能被选中")


def t_find_first_require_clickable_is_strict():
    nodes = [_n(text="签到", clickable=False)]
    assert find_first(nodes, ["签到"], require_clickable=True) is None
    assert find_first(nodes, ["签到"]) is not None
    print("OK  require_clickable=True 时才硬过滤")


def t_find_all_dedupes_and_limits():
    nodes = [
        _n(text="福利", cx=100, cy=100),
        _n(text="福利", cx=100, cy=100),      # 完全重复 -> 去重
        _n(text="福利中心", cx=200, cy=200),
        _n(text="任务中心", cx=300, cy=300),
        _n(text="金币中心", cx=400, cy=400),
    ]
    out = find_all(nodes, ["福利", "任务中心", "金币中心"], limit=6)
    labs = [o[0] for o in out]
    assert len(labs) == len(set(labs)), f"未去重: {labs}"
    assert labs.count("福利") == 1, labs
    assert len(out) <= 6
    out2 = find_all(nodes, ["福利", "任务中心", "金币中心"], limit=2)
    assert len(out2) == 2, out2
    print("OK  find_all 去重 + 受 limit 限制")


def t_find_all_orders_clickable_first():
    nodes = [_n(text="赚钱", clickable=False, cy=300),
             _n(text="赚钱", clickable=True, cy=2000)]
    out = find_all(nodes, ["赚钱"])
    assert out[0][1] == (500, 2000), out
    print("OK  find_all 可点击优先排序")


def t_find_all_empty_when_no_match():
    assert find_all([_n(text="首页")], ["任务中心"]) == []
    print("OK  无匹配返回空列表")


def t_find_more_prefers_exact_desc():
    nodes = [_n(desc="更多功能", clickable=True, cx=1, cy=1),
             _n(desc=MORE_DESC, clickable=True, cx=984, cy=174)]
    xy, via = find_more(nodes)
    assert xy == (984, 174), (xy, via)
    assert via == "desc精确", via
    print("OK  find_more 优先 content-desc 精确等于『更多』")


def t_find_more_falls_back_to_contains():
    nodes = [_n(desc="查看更多", clickable=True, cx=900, cy=170)]
    xy, via = find_more(nodes)
    assert xy == (900, 170), (xy, via)
    assert via == "desc包含", via
    print("OK  find_more 退而求其次用 desc 包含")


def t_find_more_ignores_nonclickable_and_returns_none():
    nodes = [_n(desc=MORE_DESC, clickable=False)]
    xy, via = find_more(nodes)
    assert xy is None, (xy, via)
    assert via == "未找到", via
    print("OK  find_more 忽略不可点击的『更多』并返回未找到")


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
