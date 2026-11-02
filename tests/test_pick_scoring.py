# -*- coding: utf-8 -*-
"""test_pick_scoring.py - 打分择优改造（#2）的回归单测

背景：旧版 pick_best 对「超长且不可点击」的候选一票否决，实测制造了大量
冤案（data/records.db WARN 归纳出 ~20 例）：真短按钮被同页 FAQ/推送文案
挤掉、营销后缀入口（'立即签到 +1000火龙币'）整条扔弃。

新语义：全量打分排序，超长只是重罚；仅当**无任何常规可信候选**时才进入
超长甄别兜底 —— 噪声句式（FAQ/疑问/说明句/标点收尾长句）照旧拒绝。

用例全部取自 records.db 的真实失败文案，按三类场景组织：
  A. score_entry 分值结构（含旧口径兼容：精确>可点>更短）
  B. pick_best 多匹配择优（冤案场景翻案 + 经典正确拒配不回退）
  C. 兜底顺序与降级路径（推送标题降权、probe_deep._ok_len 同口径）

运行：
    python -m pytest tests/test_pick_scoring.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pick_locate import (pick_best, score_entry, is_noise_label,
                         overlen_limit, _PLAUSIBLE_FLOOR)  # noqa: E402


def _log(lines):
    return lambda event, app="", level="INFO": lines.append((level, event))


def _ent(label, clickable=False, top=1000, left=None, right=None):
    e = {"label": label, "clickable": clickable, "top": top}
    if left is not None:
        e["left"], e["right"] = left, right
    return e


# ===========================================================================
# A. score_entry 分值结构
# ===========================================================================
def t_exact_beats_everything():
    """精确相等 1000+clickable50=1050 > 任何模糊命中（旧口径保持）。"""
    s_exact, _ = score_entry(_ent("签到", True), "签到", "text")
    s_contains, ov = score_entry(_ent("签到福利", True), "签到", "text")
    assert s_exact == 1050 and s_contains < 300 and ov is False
    print("OK  精确相等压倒一切，正常长度不加 overlong 标志")


def t_clickable_outweighs_length():
    """可点击(+50)在含词同档内足以翻长度差；精确命中(1000)仍是铁王座。"""
    s_a, _ = score_entry(_ent("签到吧", True), "签到", "text")      # 100-3+80+50
    s_b, _ = score_entry(_ent("签到", False), "签到", "text")       # 1000
    s_c, _ = score_entry(_ent("每日签到领现金活动入口", False), "签到", "text")  # 含词长文案
    assert s_a == 227 and s_b > s_a and s_c < s_a, (s_a, s_b, s_c)
    print("OK  clickable 加权生效且不翻转精确命中")


def t_overlong_penalized_not_rejected():
    """超长非可点：罚 700 分但仍返回数值（否决权已上交 pick_best 甄别层）。"""
    lab = "关闭签到提醒后,可能会错过签到福利领取,确认关闭"   # 25 字 > limit 8
    s, ov = score_entry(_ent(lab), "签到", "text")
    assert ov is True and s < 0
    lim = overlen_limit("签到")
    s_ok, ov_ok = score_entry(_ent("x" * lim), "签到", "text")
    assert ov_ok is False, "len==limit 恰在线内（口径与旧版一致）"
    print("OK  超长 -> 罚分为负，阈值边界 len==limit 不罚")


def t_noise_double_penalty_and_exempt():
    """FAQ/通知句式双罚（-700-400）；疑问标记须独立成词才算。"""
    s_faq, _ = score_entry(_ent("什么是签到领钱，如何参加？"), "签到", "text")
    s_mkt, _ = score_entry(_ent("立即签到 +1000火龙币x"), "签到", "text")
    assert s_faq < s_mkt, (s_faq, s_mkt)
    # 「查看」是按钮动词（查看更多入口），不再列为噪声标记 ——
    # 判噪会误伤「查看更多福利」这类真入口文案，锁定该豁免不回退：
    assert not is_noise_label("查看更多福利", "更多")
    print("OK  噪声追加罚分低于纯营销长文案；按钮动词不判噪")


def t_punctuation_tail_rule():
    """标点收尾规则只打不含目标词的说明句；含词营销后缀句放行。"""
    # 含 '取消' -> 标点收尾规则不适用（它是真入口文案的可能性远大于说明句）
    assert not is_noise_label("本周五更新取消，下周一补上 20 集，审核原因，", "取消")
    assert is_noise_label("活动最终解释权归平台所有。", "取消")   # 不含词+句号
    assert not is_noise_label("再看16s可领取奖励", "领取")
    print("OK  标点收尾规则仅作用于不含目标词的长句")


# ===========================================================================
# B. pick_best 多匹配择优（冤案场景）
# ===========================================================================
def t_real_button_wins_over_faq_and_notification():
    """京东金融场景：真短按钮 vs 推送标题 vs FAQ —— 选真按钮。"""
    entries = [
        _ent("京东金融通知：签到即将中断", top=100),
        _ent("签到", clickable=True, top=1500),
        _ent("什么是签到领钱，如何参加？", top=900),
    ]
    idx = pick_best(entries, "签到", "text", 2340)
    assert idx == 1, f"应选中可点的『签到』，实际 {idx}"
    print("OK  多匹配：真按钮胜出（噪声文案沉底但不否决全局）")


def t_marketing_suffix_button_salvaged():
    """冤案翻案：唯一候选是营销后缀入口 -> 兜底放行并留 WARN。"""
    lines = []
    entries = [_ent("立即签到 +1000火龙币", clickable=True, top=300)]
    idx = pick_best(entries, "签到", "text", 2340, _log(lines))
    assert idx == 0, f"可点击营销入口必须放行，实际 {idx}"
    print("OK  营销后缀可点入口照常选中（score>floor 直接可信）")


def t_nonclickable_marketing_salvage_warns():
    """入口文案挂在不可点击子节点（父容器才可点）：兜底放行 + WARN 留痕。"""
    lines = []
    entries = [_ent("去福狸中心做任务领金币", top=900)]
    idx = pick_best(entries, "做任务", "text", 2340, _log(lines))
    assert idx == 0
    assert any(l == "WARN" and "兜底" in m for l, m in lines), lines
    print("OK  不可点入口文案兜底放行且必留 WARN（可审计）")


def t_all_noise_returns_none():
    """全是 FAQ/问句时维持 None（视觉兜底链路入口不能丢）。"""
    entries = [_ent("什么是签到领钱，如何参加？"*2, top=900),
               _ent("怎样查看活动规则？", top=950)]
    assert pick_best(entries, "签到", "text", 2340) is None
    assert pick_best([], "签到", "text", 2340) is None
    print("OK  全噪声/空列表 -> None（旧正确行为零回退）")


def t_plausible_floor_excludes_salvage_zone():
    """可信线含义锁定：含目标词的正常长度候选 > floor，超长候选 <= floor
    —— 兜底甄别分支只对超长/低分池开启。"""
    normal, ov_n = score_entry(_ent("每日签到领现金"), "签到", "text")
    over, ov_o = score_entry(_ent("签到" + "长" * 30), "签到", "text")
    assert normal > _PLAUSIBLE_FLOOR and ov_n is False
    assert over <= _PLAUSIBLE_FLOOR and ov_o is True
    print("OK  可信线两侧划分正确（含词正常长度 / 超长）")


def t_no_target_long_copy_cannot_beat_contains_target_short():
    """铁律：超长/降档的营销长句永远压不过含目标词的常规可点候选。

    冤案原型 target='红包'：'看新闻就能领红包，秒到账'(12字>limit8,非可点)
    vs '领红包'(含词、正常长度、可点)。后者必须胜出。
    """
    entries = [
        _ent("看新闻就能领红包，秒到账", top=400),      # 含词但超长非可点
        _ent("领红包", clickable=True, top=500),        # 含词、正常长度、可点
    ]
    idx = pick_best(entries, "红包", "text", 2340)
    assert idx == 1, f"真按钮必须胜出，实际 {idx}"
    # 不含目标词的等长说明句则被降档到不可信区
    s_nt, _ = score_entry(_ent("蚂蚁搬砖奖励翻倍啦"), "红包", "desc")
    assert s_nt < _PLAUSIBLE_FLOOR
    print("OK  超长罚分+不含词降档共同保证真按钮优先")


# ===========================================================================
# C. 兜底顺序 / zone 与 nav 先验在新框架下不变
# ===========================================================================
def t_salvage_prefers_button_over_push_title():
    """兜底排序：都含目标词时，营销按钮优先于『…通知/提醒』标题。"""
    entries = [
        _ent("闲鱼通知：闲鱼币今日签到提醒", top=100),
        _ent("立即签到 +1000火龙币", top=300),
    ]
    idx = pick_best(entries, "签到", "text", 2340)
    assert idx == 1, f"推送标题应让位于按钮文案，实际 {idx}"
    print("OK  兜底顺序：按钮文案 > 推送标题")


def t_nav_band_prior_still_applies():
    """导航词先验在新打分下保持不变：底部带内胜出中部假命中。"""
    entries = [_ent("我的", top=627), _ent("我的", top=2100)]
    idx = pick_best(entries, "我的", "text", 2340)
    assert idx == 1
    print("OK  nav 带 ±120 先验未受改造影响")


def t_zone_bonus_still_applies():
    """tab_zone 先验保持：声明了 zone 时底部候选加分生效。"""
    entries = [_ent("赚钱", top=600), _ent("赚钱", top=2160)]
    idx = pick_best(entries, "赚钱", "text", 2340, screen_w=1080,
                    zone="tab_zone")
    assert idx == 1
    print("OK  zone 位置先验未受改造影响")


def t_probe_ok_len_parity():
    """度量与执行同口径：probe_deep._ok_len 复用同一甄别器。

    旧版硬滤会连营销入口一起滤除；新版放行非噪声超长文案、
    照旧滤除 FAQ 句式 —— 探针不再比执行器更悲观。
    """
    sys.path.insert(0, os.path.join(ROOT, "devtools"))
    from probe_deep import _ok_len as ok_len

    def node(text, clickable):
        return {"text": text, "desc": "", "clickable": clickable}

    assert ok_len(node("什么是签到领钱，如何参加？", False), "签到", "text") \
        is False, "FAQ 仍须滤除"
    assert ok_len(node("立即签到 +1000火龙币", False), "签到", "text") \
        is True, "营销入口不再被硬滤"
    assert ok_len(node("签到", False), "签到", "text") is True
    assert ok_len(node("x" * 40, True), "签到", "text") is True, "可点不受限"
    print("OK  probe_deep._ok_len 与 pick_locate 甄别器同口径")


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
