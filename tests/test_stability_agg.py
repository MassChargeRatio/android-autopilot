# -*- coding: utf-8 -*-
"""test_stability_agg.py - 多轮稳定性聚合口径的单元测试（无需真机）

为什么必须测这个：
    `aggregate()` 的输出就是**头条指标**（总命中率 / 稳定命中数）。
    如果它的口径写错（例如把"作废"轮次算进分母、或把 `导航可救` 漏算成未命中），
    整轮结论都会错，而且是**看起来合理**的错。这类代码必须被测住。

口径（与 `ROUND3_FINDINGS.md` / `STABILITY.md` 必须一致）：
    命中   = 首屏命中 / 导航后命中 / 导航可救(建议加前置步)
    未命中 = 首屏未命中 / 导航后仍未命中 / 导航后也未命中(不可救)
    作废   = 数据作废(...) / 异常 / 无锚点动作   -> **不进分母**

运行：
    python tests/test_stability_agg.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "devtools"))

from stability_run import (  # noqa: E402
    aggregate, classify, is_hit, is_void, HIT_STATUS,
)


def t_hit_status_set_is_exact():
    """命中口径就是这三个状态，不多不少。"""
    assert HIT_STATUS == {"首屏命中", "导航后命中", "导航可救(建议加前置步)"}
    assert is_hit("首屏命中") and is_hit("导航后命中")
    assert is_hit("导航可救(建议加前置步)")
    assert not is_hit("首屏未命中")
    assert not is_hit("导航后仍未命中")
    assert not is_hit("导航后也未命中(不可救)")
    print("OK  命中口径 = 首屏命中/导航后命中/导航可救")


def t_void_status_set():
    assert is_void("数据作废(页面非目标App)")
    assert is_void("数据作废(前台非目标App)")
    assert is_void("异常")
    assert is_void("无锚点动作")
    assert not is_void("首屏命中")
    assert not is_void("导航后也未命中(不可救)")
    print("OK  作废口径 = 数据作废(...)/异常/无锚点动作")


def t_void_rounds_excluded_from_denominator():
    """作废轮次不进分母：2 命中 + 1 作废 -> 2/2，不是 2/3。"""
    acc = {("A", "sign"): ["首屏命中", "数据作废(页面非目标App)", "导航后命中"]}
    per, tot = aggregate(acc)
    row = per[0]
    assert row["valid"] == 2, row
    assert row["void"] == 1, row
    assert row["hits"] == 2, row
    assert row["rate"] == 1.0, row
    assert tot == {"hits": 2, "valid": 2, "void": 1}, tot
    print("OK  作废轮次不进分母（2/2 而非 2/3）")


def t_all_void_gives_none_rate():
    acc = {("A", "sign"): ["数据作废(页面非目标App)"] * 3}
    per, tot = aggregate(acc)
    assert per[0]["valid"] == 0
    assert per[0]["rate"] is None, "全作废时不应给出命中率"
    assert tot["valid"] == 0 and tot["hits"] == 0
    print("OK  全作废时 rate=None，不污染总命中率")


def t_total_rate_math():
    """2/2 + 0/2 -> 2/4 = 50%。"""
    acc = {
        ("A", "sign"): ["首屏命中", "导航后命中"],
        ("B", "sign"): ["首屏未命中", "导航后也未命中(不可救)"],
    }
    per, tot = aggregate(acc)
    assert tot["hits"] == 2 and tot["valid"] == 4, tot
    print("OK  总命中率 = 总命中/总有效 = 2/4")


def t_classify_three_buckets():
    acc = {
        ("A", "sign"): ["首屏命中", "首屏命中", "首屏命中"],          # 稳定
        ("B", "sign"): ["首屏命中", "首屏未命中", "导航后命中"],        # 波动
        ("C", "sign"): ["首屏未命中", "首屏未命中", "导航后也未命中(不可救)"],  # 从未
        ("D", "sign"): ["数据作废(页面非目标App)"] * 2,              # 全作废 -> 不进任何类
    }
    per, _ = aggregate(acc)
    stable, flaky, never = classify(per)
    assert [x["app"] for x in stable] == ["A"], stable
    assert [x["app"] for x in flaky] == ["B"], flaky
    assert [x["app"] for x in never] == ["C"], never
    assert len(stable) + len(flaky) + len(never) == 3, "全作废的行为不应进任何类"
    print("OK  classify 三分：稳定/波动/从未（全作废不进任何类）")


def t_order_is_sorted_and_statuses_preserved():
    acc = {
        ("B", "watch"): ["首屏命中"],
        ("A", "sign"): ["首屏命中"],
    }
    per, _ = aggregate(acc)
    assert [x["app"] for x in per] == ["A", "B"], per
    assert per[1]["statuses"] == ["首屏命中"]
    print("OK  输出按 (app, behavior) 排序且保留各轮状态")


def t_void_counted_per_row():
    acc = {
        ("A", "sign"): ["首屏命中", "异常"],
        ("B", "sign"): ["数据作废(页面非目标App)"],
    }
    _, tot = aggregate(acc)
    assert tot["void"] == 2, tot
    print("OK  作废轮次总数跨行为累加正确")


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
