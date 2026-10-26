# -*- coding: utf-8 -*-
"""sign_evidence.py - 「签到按钮确实被点过了吗」的单一判定口径。

2026-10-25 用户定的判定规则：

    **只有复核过「签到按钮确实被点过了」，才认为已经成功签到。**

常见误用（本模块就是为堵这些口子而存在）：
    - 任务执行完毕 / 流程跑完        → 只说明链没崩，不说明点中了签到按钮
    - 健康体检 GREEN                 → 只说明没有失败信号
    - 日志里没有「步骤失败」字样      → 静默 miss 的步骤一样不留失败字样
    - 顶部金币计数变多                → 每会话重置，且可能来自别的行为

认可的凭据只有两类：
    1. 点击凭据：日志里出现点击行，且该行点中的文案命中签到类词表
    2. 终态凭据：重新打开 app 显示已签状态（由调用方离线核验，不在本模块内）

两类都没有 → 一律「未确认」。宁可少记成功，不可多记。

用法：
    from sign_evidence import signed_evidence
    ok, line, kind = signed_evidence(log_text)
"""
import re

__all__ = ["SIGN_WORDS", "CLICK_LINE", "signed_evidence", "SIGN_EVIDENCE_RULE"]

# 签到类文案词表。命中即认为该次点击的语义对象是「签到按钮」。
# 注意：导航类入口（任务 / 任务中心 / 赚钱 / 福利中心 / 我的）**故意不收**——
# 点中它们只代表进了门，不代表点了签到按钮。
SIGN_WORDS = (
    "签到", "立即签到", "签到领取", "领金币", "领现金", "赚现金", "开宝箱",
    "福利", "早起打卡", "每日签到", "签到奖励", "点金币", "金币签到",
)

# 三种「真的点了某个东西」的日志行。
#   - 多候选命中并点击: (kind)值     —— click_first 命中候选
#   - 点击文本: XXX                  —— click_text 命中
#   - 视觉兜底点击成功: 描述 -> 坐标  —— 模板/VLM 命中
# 故意**不含**「点击坐标: (x,y)」：那是盲点，可能点在任何东西上，
# 拿它当签到凭据等于没有凭据（2026-10-25 悟空踩过的坑）。
CLICK_LINE = re.compile(
    r"(多候选命中并点击|点击文本|视觉兜底点击成功)[^\n]*")

SIGN_EVIDENCE_RULE = (
    "只有复核过「签到按钮确实被点过了」，才认为已经成功签到。"
    "任务执行完毕 / 体检 GREEN / 无「步骤失败」/ 金币计数都不算凭据。"
)


def signed_evidence(log_text):
    """从一段日志里复核「签到按钮是否确实被点过」。

    Args:
        log_text: 一次行为执行的完整日志文本（多行字符串）。

    Returns:
        (confirmed, evidence_line, kind)
            confirmed     True=有点击凭据；False=未确认
            evidence_line 凭据所在日志行（未确认时为 None）
            kind          凭据类型：多候选命中 / 文本命中 / 视觉兜底命中
    """
    if not log_text:
        return False, None, None
    for line in log_text.splitlines():
        if not CLICK_LINE.search(line):
            continue
        if any(w in line for w in SIGN_WORDS):
            if "多候选命中并点击" in line:
                kind = "多候选命中"
            elif "视觉兜底点击成功" in line:
                kind = "视觉兜底命中"
            else:
                kind = "文本命中"
            return True, line.strip(), kind
    return False, None, None
