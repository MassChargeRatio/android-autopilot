# -*- coding: utf-8 -*-
"""投递 AUTOP-NL 两卡给 marvis（Host 侧，一次性脚本）。"""
import os
import sys

os.environ["LOCALAPPDATA"] = r"C:\Users\Administrator\AppData\Local"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
sys.path.insert(0, r"C:/Users/Administrator/WorkBuddy/S7 漏洞/.workbuddy/dispatch")

from marvis_dispatch import dispatch, list_conversations  # noqa: E402

ROOT = r"C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot"

MSG_A = """[派单 AUTOP-NL-A-2026-10-22]
目录：{root}
卡片（唯一任务来源，先完整读）：dispatch\\AUTOP-NL-2026-10-22-A-CARD.md
任务：新建 devtools/nl_to_steps.py + tests/test_nl_to_steps.py（自然语言→动作链 YAML 片段，3 种入口模板）
禁碰：candidates.py / behavior_runner.py / executor.py / main.py / config.yaml / config/apps/** / devtools/yaml_writer.py（只读）/ 任何既有测试
环境：必须 ./.venv/Scripts/python.exe
★硬性节奏（上一轮教训：只探索不落盘=零产出）：
1) 前 5 个工具调用内创建 dispatch/AUTOP-NL-2026-10-22-A/PROGRESS.md 骨架；
2) 每完成一个函数立即覆盖写 PROGRESS（签名+测试命令+真实输出），禁止攒最后；
3) 预算约 250 次工具调用，超预算落盘 OPEN/BLOCKED 并结束；
4) 不要停在 requires_action，疑义写 PROGRESS 继续干。
自检：pytest 新测试全绿 + 全量 >= 291 + config/apps sha256 不变""".format(root=ROOT)

MSG_B = """[派单 AUTOP-NL-B-2026-10-22]
目录：{root}
卡片（唯一任务来源，先完整读）：dispatch\\AUTOP-NL-2026-10-22-B-CARD.md
任务：新建 devtools/record_flow.py + tests/test_record_flow.py（引导式录制：NL 指令→执行→记录→YAML）
禁碰：candidates.py / behavior_runner.py / executor.py / main.py / config.yaml / config/apps/** / devtools/yaml_writer.py / devtools/nl_to_steps.py / 任何既有测试
环境：必须 ./.venv/Scripts/python.exe
★硬性节奏：
1) 前 5 个工具调用内创建 dispatch/AUTOP-NL-2026-10-22-B/PROGRESS.md 骨架；
2) 每完成一个函数立即覆盖写 PROGRESS（签名+测试命令+真实输出），禁止攒最后；
3) 预算约 250 次工具调用，超预算落盘 OPEN/BLOCKED 并结束；
4) 不要停在 requires_action。
软依赖：nl_to_steps.py 可能尚未存在，用 try/except import 兜底并记 BLOCKED-DEP，禁止复制 parse_line 逻辑。""".format(root=ROOT)


def main():
    convs = list_conversations("marvis", 40)
    busy = [c for c in convs if c.get("status") == "in_progress"]
    print("PRE total=%d busy=%d %s" % (len(convs), len(busy),
                                       [c.get("title") for c in busy]), flush=True)

    for tag, msg in (("AUTOP-NL-A-2026-10-22", MSG_A), ("AUTOP-NL-B-2026-10-22", MSG_B)):
        try:
            d, r, cid = dispatch("marvis", msg, timeout=240, hold=True, tag=tag)
            print("SENT %s cid=%s" % (tag, cid), flush=True)
            ev = str(getattr(r, "evidence", ""))[:200]
            print("  evidence:", ev, flush=True)
        except Exception as exc:  # noqa: BLE001
            print("FAIL %s %s: %s" % (tag, type(exc).__name__, exc), flush=True)


if __name__ == "__main__":
    main()
