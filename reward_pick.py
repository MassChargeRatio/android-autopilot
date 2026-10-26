# -*- coding: utf-8 -*-
"""reward_pick.py - 收益候选排序纯函数（B8 抽取，无设备/无状态依赖）

从 executor._reward_candidates 抽出的排序逻辑：
    context 唯一前置（首个命中即返回）→ unit=="元" 且命中余额 hints 前置 → 原序。
纯函数便于直测：test_reward_pick.py 9 例保持零修改（走 executor 正则壳），
另新增 test_reward_pick_pure.py 直测本模块。
"""
import re

# 只在 text / content-desc 里找收益数字。
# 踩坑：直接在整份 XML 上 re.search，会命中活动横幅、广告位等无关数字
# （例如「新人 1 元提现」），把横幅数字当成账户余额记进收益表。
_TEXT_ATTR_RE = re.compile(r'(?:text|content-desc)="([^"]*)"')
# 金额类收益的语义提示词：多处匹配时优先取带这些词的文案
_BALANCE_HINTS = ("可提现", "提现", "余额", "钱包", "现金", "账户", "收益")


def rank_reward_candidates(out, context, balance_hints, money_unit, unit):
    """对候选 [(来源文案, match), ...] 按可信度排序（纯函数，无副作用）。

    - context 唯一前置：配置里显式给的 context 关键词，首个命中即返回；
    - 金额类（unit == money_unit，如 "元"）优先带余额语义的文案；
    - 否则原序返回。
    """
    if len(out) <= 1:
        return out
    if context:
        for i, (val, _) in enumerate(out):
            if any(k in val for k in context):
                return [out[i]] + out[:i] + out[i + 1:]
    if unit == money_unit:
        for i, (val, _) in enumerate(out):
            if any(k in val for k in balance_hints):
                return [out[i]] + out[:i] + out[i + 1:]
    return out
