# -*- coding: utf-8 -*-
"""test_reward_pick.py - Executor 收益数字提取的单元测试（无需真机）

背景（踩过的坑）：
    原实现是 `re.search(pattern, xml)` 直接在**整份 UI XML** 上取第一个匹配。
    页面上的活动横幅（如「新人 1 元提现」）、广告位数字都会被当成账户余额，
    于是收益表里记的是横幅数字，不是真实收益。

新语义：
    1. 只在 `text="..."` / `content-desc="..."` 属性值里找；
    2. 多处匹配时，金额类（unit=元）优先取带「提现/余额/钱包/现金」语义的文案；
    3. 配置里给了 `context` 关键词时，context 优先级最高；
    4. 属性里一处都没有时，退化为整份 XML 兜底（兼容跨标签的旧 pattern）。

运行：
    python tests/test_reward_pick.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402

AMOUNT_YUAN = r"(?P<amount>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>元)"


def _mk():
    return Executor.__new__(Executor)


def _xml(*texts):
    nodes = "".join(f'<node text="{t}" resource-id="x{i}"/>'
                    for i, t in enumerate(texts))
    return f"<hierarchy>{nodes}</hierarchy>"


def _pick(xml, pattern=AMOUNT_YUAN, **act):
    ex = _mk()
    cands = ex._reward_candidates(xml, pattern, act)
    return cands


def t_ignores_non_text_attributes():
    """resource-id / bounds 里的数字不该被当成收益。"""
    xml = ('<hierarchy><node text="首页" resource-id="tv_1yuan_balance" '
           'bounds="[0,0][1080,100]"/></hierarchy>')
    assert _pick(xml) == [], "不应从 resource-id 里抠出数字"
    print("OK  只在 text/content-desc 里找，忽略 resource-id")


def t_prefers_balance_semantics():
    """页面同时有横幅「新人专享1元」和「可提现0.32元」-> 取后者。"""
    xml = _xml("新人专享1元", "可提现0.32元", "看视频再得50金币")
    cands = _pick(xml, unit="元")
    assert cands, "应有匹配"
    assert cands[0][0] == "可提现0.32元", f"取错了: {cands[0][0]}"
    assert cands[0][1].group("amount") == "0.32"
    print("OK  多处匹配时优先取带「可提现/余额」语义的文案")


def t_banner_only_still_returns_something():
    """只有横幅数字时仍然返回（宁可给个数字也别静默丢），但只有一条候选。"""
    xml = _xml("新人专享1元")
    cands = _pick(xml, unit="元")
    assert len(cands) == 1
    assert cands[0][1].group("amount") == "1"
    print("OK  仅横幅匹配时仍返回单条候选（并在日志里标注）")


def t_context_keyword_wins():
    """配置给了 context 时，context 优先级高于内置语义表。"""
    xml = _xml("可提现0.32元", "账户余额5.00元")
    cands = _pick(xml, unit="元", context=["账户"])
    assert cands[0][0] == "账户余额5.00元", f"context 未生效: {cands[0][0]}"
    print("OK  context 关键词优先级最高")


def t_content_desc_also_scanned():
    xml = '<hierarchy><node content-desc="可提现金额 1.50 元"/></hierarchy>'
    cands = _pick(xml, unit="元")
    assert cands, "content-desc 也应被扫描"
    assert cands[0][1].group("amount") == "1.50"
    print("OK  content-desc 属性同样参与匹配")


def t_fallback_to_whole_xml():
    """属性里没有时退化为整份 XML（兼容跨标签 pattern）。"""
    xml = '<hierarchy><node text="签到"/><node text="3 金币"/></hierarchy>'
    pat = r"签到.*?(?P<amount>[0-9]+)\s*(?P<unit>金币)"
    cands = _pick(xml, pattern=pat)
    assert cands, "整份 XML 兜底应生效"
    assert cands[0][1].group("amount") == "3"
    print("OK  属性无匹配时退化为整份 XML 兜底")


def t_no_match_returns_empty():
    xml = _xml("首页", "我的")
    assert _pick(xml) == []
    print("OK  无匹配返回空列表")


def t_coin_unit_not_reordered():
    """非金额单位（金币）不做「余额语义」重排，保持文档顺序。"""
    xml = _xml("看视频得100金币", "签到得5金币")
    cands = _pick(xml, pattern=r"(?P<amount>[0-9]+)\s*(?P<unit>金币)",
                  unit="金币")
    assert cands[0][0] == "看视频得100金币", f"金币不该重排: {cands[0][0]}"
    print("OK  金币类不做余额语义重排，保持文档顺序")


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
