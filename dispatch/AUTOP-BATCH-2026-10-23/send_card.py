# -*- coding: utf-8 -*-
"""投递 AUTOP-BATCH-2026-10-23 给 marvis。"""
import os
import sys

os.environ["LOCALAPPDATA"] = r"C:\Users\Administrator\AppData\Local"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
sys.path.insert(0, r"C:/Users/Administrator/WorkBuddy/S7 漏洞/.workbuddy/dispatch")

from marvis_dispatch import dispatch, list_conversations  # noqa: E402

ROOT = r"C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot"

MSG = """[派单 AUTOP-BATCH-2026-10-23]
目录：{root}
卡片（唯一任务来源，先完整读）：dispatch\\AUTOP-BATCH-2026-10-23-CARD.md
任务：按卡片顺序真机带跑 17 个带 sign 的 App，每个跑 `main.py --app "<App>" --task 签到 --force --fast`，结果逐行记入 PROGRESS.md 表格 + 每 App 一份 logs/*.log。
前置（必做）：.venv/Lib/site-packages/adbutils/binaries/adb.exe connect 192.168.1.54:5555（每次跑前都要连，daemon 会被回收）
红线：不改 config/**、不改任何 .py；遇提现/支付/验证码/登录页直接跳过并记 SKIP；单 App 超时 150s。
★硬性节奏（前两卡因只读不写被判失败）：
1) 前 3 个调用内建 PROGRESS.md（表头+17 行空行）和 logs/ 目录；
2) 每跑完 1 个 App 立即追加一行（含真实日志摘录），禁止攒最后；
3) 预算 250 次调用，超预算落盘剩余清单收尾；
4) 不停在 requires_action。
环境：必须 ./.venv/Scripts/python.exe""".format(root=ROOT)


def main():
    convs = list_conversations("marvis", 40)
    busy = [c for c in convs if c.get("status") == "in_progress"]
    print("PRE total=%d busy=%d %s" % (len(convs), len(busy),
                                       [c.get("title") for c in busy]), flush=True)
    try:
        d, r, cid = dispatch("marvis", MSG, timeout=240, hold=True,
                             tag="AUTOP-BATCH-2026-10-23")
        print("SENT cid=%s" % cid, flush=True)
        print("  evidence:", str(getattr(r, "evidence", ""))[:200], flush=True)
    except Exception as exc:  # noqa: BLE001
        print("FAIL %s: %s" % (type(exc).__name__, exc), flush=True)


if __name__ == "__main__":
    main()
