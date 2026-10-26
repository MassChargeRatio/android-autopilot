# -*- coding: utf-8 -*-
"""watch_dispatch_queue.py - AUTOP 三卡链式队列守望器

marvis 单 agent。三张卡严格顺序（用户 2026-10-20 21:23 确认手机在线）：
  CARD-A AUTOP-REGRESS-2026-10-20   12 份新 sign 真机回归（verify_live）
  CARD-B AUTOP-FEAT-2026-10-20      F1 全局弹窗 + F2 反检测
  CARD-C AUTOP-SELFSEARCH-2026-10-20 共性提炼 → 引擎自搜寻
流程：等 idle -> 投当前卡 -> 等 completed -> 下一张；非 completed 记终态后继续队列不投后续风险卡时由本卡记录说明。
"""
import os
import sys
import time

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["LOCALAPPDATA"] = r"C:\Users\Administrator\AppData\Local"
sys.path.insert(0, r"C:/Users/Administrator/WorkBuddy/S7 漏洞/.workbuddy/dispatch")

ROOT = r"C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot"
DISP = os.path.join(ROOT, "dispatch")
POLL = 60
QUEUE_WAIT_MAX = 5400   # 每张卡排队等 idle 上限 90 min
EXEC_MAX = 14400        # 每张卡执行上限 4 h

CARD_A = ("AUTOP-REGRESS-2026-10-20", os.path.join(DISP, "AUTOP-REGRESS-2026-10-20-CARD.md"), """派单：12 份新 sign 配置真机回归（verify_live）。手机已在线（192.168.1.54:5555）。
卡片真源（先完整读它再动手）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-REGRESS-2026-10-20-CARD.md

范围：只跑 sign（--behaviors sign，禁止跑 withdraw）；.venv/Scripts/python.exe devtools/verify_live.py --apps 趣头条,拼多多,京东,美团,快手,百度地图,海马畅听,UC浏览器极速版,飞猪旅行,米读小说,米读极速版,大众点评 --behaviors sign --nav-fast --out devtools/calib/LIVE_VERIFY_SIGN12.md --json devtools/calib/LIVE_VERIFY_SIGN12.json；逐 App 落盘命中结论+断点步骤+「待真机校准」坐标修正清单；不修改任何 config/apps/ 文件（清单交 Host 应用）。
红线：资金类弹窗立即停手；设备离线重连≤3 次即记 BLOCKED 退出；不 git push；无证据不报 confirmed。
★ 硬性节奏：前 5 个动作建 dispatch/AUTOP-REGRESS-2026-10-20/PROGRESS.md 骨架；每 App 完成立即覆盖写；预算约 150 次工具调用；不停 requires_action。""")

CARD_B = ("AUTOP-FEAT-2026-10-20", os.path.join(DISP, "AUTOP-FEAT-2026-10-20-CARD.md"), """派单：AndroidAutopilot 两个新功能（F1 全局弹窗处理 + F2 反机器人检测）。
卡片真源（先完整读它再动手）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-FEAT-2026-10-20-CARD.md
sha16=8cd3527c948693ec

范围：F1 dismiss_popups 原语（文案→关闭id→右上角坐标→系统回退键四级关闭顺序；黑名单熔断资金类弹窗；watch 行为进行中保护正在看的广告）；F2 反检测文档 docs/ANTI_DETECTION.md（威胁面诚实标注可缓解/不可缓解，禁过度承诺）+ human.py 拟人化增强（误触回退/乱逛/限流/验证码冷却）。
红线（用户原话）：资金类弹窗不得自动关闭、不得按 BACK 消化（踩项目资金红线即打回）；不许引入第三方改机/root/hook；不许改既有测试断言使其变绿。
交付：新文件+新测试+PROGRESS.md；pytest tests/ -q 全绿并贴真实输出；dry-run EXIT=0；不 git push；每步前备份 _backup_pre_fix/。
★ 硬性节奏：前 5 个动作内在 dispatch/AUTOP-FEAT-2026-10-20/PROGRESS.md 建骨架；每解决一个子问题立即覆盖写；预算约 300 次工具调用；不停 requires_action。""")

CARD_C = ("AUTOP-SELFSEARCH-2026-10-20", os.path.join(DISP, "AUTOP-SELFSEARCH-2026-10-20-CARD.md"), """派单：领现金路径共性提炼 → 引擎自搜寻能力。
卡片真源（先完整读它再动手，含 12 App 人工勘察描述存档）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-SELFSEARCH-2026-10-20-CARD.md
数据源：同目录 APP_PATHS.md；最新真机证据在 devtools/calib/LIVE_VERIFY_SIGN12.md（若已产出，作为坐标校准输入）。

范围（严格按卡内五步）：① 全局分类候选词表 candidates.py（NAV_TAB/TASK_CENTER/SIGN/WITHDRAW+App 级微调）；② click_first 滚动重试 scroll_retry；③ _pick_best 位置先验 zone；④ behavior 时间窗 window；⑤ docs/SELF_SEARCH_PLAYBOOK.md + 收敛 Host 已写的 12 份 sign 配置（消费回归校准清单，不得降低命中面）。
红线：测试必须能红（变异验证四条）；不改既有测试断言使其变绿；无证据不报 confirmed；不 git push；每步前备份 _backup_pre_fix/。
交付：pytest tests/ -q 全绿并贴真实输出；dry-run 趣头条/美团 EXIT=0；PROGRESS 按硬性节奏落盘。
★ 硬性节奏：前 5 个动作建 dispatch/AUTOP-SELFSEARCH-2026-10-20/PROGRESS.md 骨架；每子问题立即覆盖写；预算约 300 次工具调用；不停 requires_action。""")

CARDS = [CARD_A, CARD_B, CARD_C]


def log(msg):
    print(f"[queue] {msg}", flush=True)


def wait_idle(max_wait, phase):
    from marvis_dispatch import list_conversations
    waited = 0
    while waited < max_wait:
        try:
            convs = list_conversations("marvis", 40)
        except Exception as e:  # noqa: BLE001
            log(f"{phase} list 失败 {POLL}s 后重试: {e}")
            time.sleep(POLL)
            waited += POLL
            continue
        busy = [c for c in convs if c.get("status") == "in_progress"]
        if not busy:
            return True
        log(f"{phase} marvis 忙（{len(busy)} in_progress），已等 {waited}s")
        time.sleep(POLL)
        waited += POLL
    return False


def wait_done(cid, max_wait):
    from marvis_dispatch import conversation_status
    waited = 0
    while waited < max_wait:
        try:
            st = conversation_status(cid)
        except Exception as e:  # noqa: BLE001
            log(f"conversation_status({cid}) 失败: {e}")
            time.sleep(POLL)
            waited += POLL
            continue
        log(f"cid={cid} 状态={st}（已等 {waited}s）")
        if st in ("completed", "failed", "cancelled", "not_found"):
            return st
        time.sleep(POLL)
        waited += POLL
    return "timeout"


def record(card, text):
    with open(card, "a", encoding="utf-8") as f:
        f.write(text)


def main():
    from marvis_dispatch import dispatch
    for tag, card, msg in CARDS:
        if not wait_idle(QUEUE_WAIT_MAX, tag):
            record(card, f"\n- 2026-10-20 排队超时（>{QUEUE_WAIT_MAX}s）未投递，卡片就绪待派\n")
            log(f"{tag} 排队超时，后续卡也不投（保持顺序），退出")
            return 1
        log(f"{tag} marvis 空闲，投递")
        _d, _r, cid = dispatch("marvis", msg, timeout=240, hold=True, tag=tag)
        log(f"{tag} 已投递 cid={cid}")
        record(card, f"\n- 链式队列投递：2026-10-20 {time.strftime('%H:%M')} ｜ tag={tag} ｜ cid={cid}\n")
        st = wait_done(cid, EXEC_MAX)
        log(f"{tag} 终态={st}")
        record(card, f"- 会话终态：{st}（{time.strftime('%Y-%m-%d %H:%M')} 观测）\n")
        if st != "completed":
            record(card, f"- 注意：{tag} 非 completed，后续卡未越位投递，卡片就绪待派\n")
            log(f"{tag} 非 completed，停止后续投递，退出")
            return 1
    log("三卡队列全部执行完毕")
    return 0


if __name__ == "__main__":
    sys.exit(main())
