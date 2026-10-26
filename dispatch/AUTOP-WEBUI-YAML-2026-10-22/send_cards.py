# -*- coding: utf-8 -*-
"""投递 AUTOP-WEBUI-YAML 两卡给 marvis（Host 侧，一次性脚本）。"""
import os
import sys

os.environ["LOCALAPPDATA"] = r"C:\Users\Administrator\AppData\Local"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
sys.path.insert(0, r"C:/Users/Administrator/WorkBuddy/S7 漏洞/.workbuddy/dispatch")

from marvis_dispatch import dispatch, list_conversations  # noqa: E402

ROOT = r"C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot"

MSG_A = """[派单 AUTOP-WEBUI-YAML-A-2026-10-22]
目录：{root}
卡片（唯一任务来源，先完整读）：dispatch\\AUTOP-WEBUI-YAML-2026-10-22-A-CARD.md
任务：实现 webui/routes_yaml.py（Host 已建骨架，含 6 个路由契约）+ tests/test_webui_yaml_api.py（>=12 例）
关键：保存必须走 yaml_writer（eol 保真/备份/写后 verify/失败自动回滚）；generate 必须调 nl_to_steps.build_behavior；模块级 APPS_DIR 要可 monkeypatch。
禁碰：webui/server.py / webui/static/** / webui/data.py / main.py / config.yaml / config/apps/** / 既有测试 / B 卡文件
环境：必须 ./.venv/Scripts/python.exe
★硬性节奏：
1) 前 5 个工具调用内建 dispatch/AUTOP-WEBUI-YAML-2026-10-22-A/PROGRESS.md；
2) 每完成一个处理函数立即覆盖写 PROGRESS（签名+测试命令+真实输出）；
3) 预算约 250 次调用，超预算落盘 OPEN/BLOCKED；
4) 不停在 requires_action。
自检：pytest 新测试全绿 + 全量 >= 360 + config/apps sha256 不变""".format(root=ROOT)

MSG_B = """[派单 AUTOP-WEBUI-YAML-B-2026-10-22]
目录：{root}
卡片（唯一任务来源，先完整读）：dispatch\\AUTOP-WEBUI-YAML-2026-10-22-B-CARD.md
任务：实现 webui/static/yaml_editor.js + yaml_editor.css（可微调 yaml.html，但必须保留骨架元素 ID）+ tests/test_yaml_editor_static.py（>=8 例）
关键：POST 一律带 X-Auth-Token（从 meta[name=console-token] 读，禁止写死）；纯原生 JS 无 CDN；前端不做 CRLF 转换。
禁碰：webui/server.py / webui/routes_yaml.py / webui/data.py / app.css / app.js / index.html / main.py / config.yaml / config/apps/** / 既有测试 / A 卡文件
环境：必须 ./.venv/Scripts/python.exe
★硬性节奏：
1) 前 5 个工具调用内建 dispatch/AUTOP-WEBUI-YAML-2026-10-22-B/PROGRESS.md；
2) 每完成一个模块立即覆盖写 PROGRESS（含真实测试输出）；
3) 预算约 250 次调用，超预算落盘 OPEN/BLOCKED；
4) 不停在 requires_action。
自检：pytest 新测试全绿 + 全量 >= 360 + config/apps sha256 不变""".format(root=ROOT)


def main():
    convs = list_conversations("marvis", 40)
    busy = [c for c in convs if c.get("status") == "in_progress"]
    print("PRE total=%d busy=%d %s" % (len(convs), len(busy),
                                       [c.get("title") for c in busy]), flush=True)
    for tag, msg in (("AUTOP-WEBUI-YAML-A-2026-10-22", MSG_A),
                     ("AUTOP-WEBUI-YAML-B-2026-10-22", MSG_B)):
        try:
            d, r, cid = dispatch("marvis", msg, timeout=240, hold=True, tag=tag)
            print("SENT %s cid=%s" % (tag, cid), flush=True)
            print("  evidence:", str(getattr(r, "evidence", ""))[:180], flush=True)
        except Exception as exc:  # noqa: BLE001
            print("FAIL %s %s: %s" % (tag, type(exc).__name__, exc), flush=True)


if __name__ == "__main__":
    main()
