# -*- coding: utf-8 -*-
"""watch_dispatch_feat.py - AUTOP-FEAT-2026-10-20 排队投递守望器

marvis 是单 agent。投递前若 in_progress 非空 → 每隔 POLL 秒重查；
空闲即投递（tag=AUTOP-FEAT-2026-10-20），cid 写回卡片「投递记录」节后退出。
超过 MAX_WAIT 秒仍忙 → 落盘 BLOCKED 记录退出（不猛发、不撤销卡片）。
"""
import os
import re
import sys
import time

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["LOCALAPPDATA"] = r"C:\Users\Administrator\AppData\Local"
sys.path.insert(0, r"C:/Users/Administrator/WorkBuddy/S7 漏洞/.workbuddy/dispatch")

ROOT = r"C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot"
CARD = os.path.join(ROOT, "dispatch", "AUTOP-FEAT-2026-10-20-CARD.md")
TAG = "AUTOP-FEAT-2026-10-20"
POLL = 60
MAX_WAIT = 5400  # 90 分钟

MSG = """派单：AndroidAutopilot 两个新功能（F1 全局弹窗处理 + F2 反机器人检测）。
卡片真源（先完整读它再动手）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-FEAT-2026-10-20-CARD.md
sha16=8cd3527c948693ec

范围：F1 dismiss_popups 原语（文案→id→右上角坐标→系统回退键四级关闭顺序；黑名单熔断资金类弹窗；watch 行为进行中保护正在看的广告）；F2 反检测文档 docs/ANTI_DETECTION.md（威胁面诚实标注可缓解/不可缓解，禁过度承诺）+ human.py 拟人化增强（误触回退/乱逛/限流/验证码冷却）。
红线（用户原话）：资金类弹窗不得自动关闭、不得按 BACK 消化（踩项目资金红线即打回）；不许引入第三方改机/root/hook；不许改既有测试断言使其变绿。
交付：新文件+新测试+PROGRESS.md；pytest tests/ -q 全绿并贴真实输出；dry-run EXIT=0；不 git push；每步前备份 _backup_pre_fix/。
★ 硬性节奏（上一轮教训：只探索不落盘=零产出的必须遵守）：
1. 前 5 个动作内在 dispatch/AUTOP-FEAT-2026-10-20/PROGRESS.md 建骨架（哪怕空）；
2. 每解决一个子问题立即覆盖写该文件，禁止攒最后；
3. 工具调用预算约 300，超预算落盘部分结论+OPEN/BLOCKED 停步；
4. 不停在 requires_action，疑义写 PROGRESS 质疑记录段。"""


def main():
    from marvis_dispatch import list_conversations, dispatch

    os.makedirs(os.path.dirname(CARD), exist_ok=True)
    t0 = time.time()
    waited = 0
    while waited < MAX_WAIT:
        try:
            convs = list_conversations("marvis", 40)
        except Exception as e:  # noqa: BLE001
            print(f"[watch] list_conversations 失败，{POLL}s 后重试: {e}", flush=True)
            time.sleep(POLL)
            waited += POLL
            continue
        busy = [c for c in convs if c.get("status") == "in_progress"]
        if not busy:
            print(f"[watch] marvis 空闲（已排队 {waited}s），投递 tag={TAG}", flush=True)
            d, r, cid = dispatch("marvis", MSG, timeout=240, hold=True, tag=TAG)
            print(f"[watch] 投递回执 cid={cid}", flush=True)
            rec = (
                f"\n- 排队投递：2026-10-20 ｜ tag={TAG} ｜ 投递前等待 {waited}s（marvis 忙别条线任务，按单 agent 纪律排队）\n"
                f"- cid：{cid}\n- 卡片 sha16：8cd3527c948693ec（sha256 8cd3527c948693ec1157754f2948ee1f75cd98d927429ab01d57ec880e17cfb2）\n"
            )
            with open(CARD, "a", encoding="utf-8") as f:
                f.write(rec)
            print("[watch] 投递记录已写回卡片，退出", flush=True)
            return 0
        print(f"[watch] marvis 忙（{len(busy)} 个 in_progress），已等 {waited}s，{POLL}s 后重查", flush=True)
        time.sleep(POLL)
        waited += POLL
    print(f"[watch] 超过 {MAX_WAIT}s 仍忙，未投递；卡片就绪待派", flush=True)
    with open(CARD, "a", encoding="utf-8") as f:
        f.write(f"\n- 2026-10-20 投递尝试：排队超过 {MAX_WAIT}s marvis 仍 in_progress，未投递，卡片就绪待派\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
