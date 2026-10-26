# -*- coding: utf-8 -*-
"""test_reward_pick_pure.py - reward_pick.rank_reward_candidates 纯函数直测（B8）

test_reward_pick.py 9 例走 executor 正则壳（零修改）保持集成语义；
本文件直接对抽出的纯函数做单元直测，钉住排序规则本身。

运行：
    python tests/test_reward_pick_pure.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from reward_pick import rank_reward_candidates, _BALANCE_HINTS  # noqa: E402

PAT = re.compile(r"(?P<amount>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>元)")


def _out(*texts):
    """构造 [(来源文案, match), ...]：每个文案都匹配 PAT。"""
    return [(t, PAT.search(t)) for t in texts]


def t_context_wins_over_balance():
    """context 唯一前置：即便后面有带余额语义的文案，也取 context 命中项。"""
    out = _out("可提现0.32元", "账户余额5.00元")
    res = rank_reward_candidates(out, ["账户"], _BALANCE_HINTS, "元", "元")
    assert res[0][0] == "账户余额5.00元", res
    print("OK  context 关键词唯一前置（覆盖余额语义）")


def t_balance_hints_reorder_yuan():
    """unit==money_unit("元") 且命中余额 hints → 该候选前置。"""
    out = _out("看视频再得50金币", "可提现0.32元", "新人专享1元")
    res = rank_reward_candidates(out, [], _BALANCE_HINTS, "元", "元")
    assert res[0][0] == "可提现0.32元", res
    print("OK  金额类命中余额语义候选前置")


def t_coin_unit_keeps_order():
    """非金额单位不做余额语义重排，保持文档原序。"""
    out = _out("看视频得100金币", "签到得5金币")
    res = rank_reward_candidates(out, [], _BALANCE_HINTS, "元", "金币")
    assert res == out, res
    print("OK  金币类不重排，原序返回")


def t_single_or_empty_returns_as_is():
    """空/单候选直接原样返回，不做任何排序。"""
    assert rank_reward_candidates([], ["账户"], _BALANCE_HINTS, "元", "元") == []
    one = _out("可提现1.00元")
    assert rank_reward_candidates(one, ["账户"], _BALANCE_HINTS, "元", "元") == one
    print("OK  空/单候选原样返回")


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
