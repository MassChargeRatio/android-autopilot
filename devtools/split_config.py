# -*- coding: utf-8 -*-
"""split_config.py - 将 config.yaml 的 apps 段拆到 config/apps/（幂等可重跑）

背景（C9）：
    拆分后主文件瘦身为 device/human/trajectory/vision/knowledge/diversify/captcha
    + apps_dir + apps: [] + money_behaviors；逐 App 写 config/apps/<safe_name>.yaml。

用法：
    python devtools/split_config.py [--config config.yaml]

行为：
    1. apps 非空 → 逐 App 写 config/apps/<safe_name>.yaml（App 内原文保序 dump）；
    2. 原文件备份 _backup_pre_fix/config.yaml.pre_split_<ts>；
    3. 主文件瘦身写回；
    4. 已拆分（apps 空且 config/apps 存在）再跑 → 报错退出。
"""
import argparse
import os
import shutil
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from config_loader import safe_app_name, DEFAULT_APPS_DIR  # noqa: E402

KEEP_TOP_KEYS = ["device", "human", "trajectory", "vision", "knowledge",
                 "diversify", "captcha"]


def split(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    apps = cfg.get("apps") or []
    if not apps:
        if os.path.isdir(cfg.get("apps_dir") or DEFAULT_APPS_DIR):
            print(f"[split_config] 已拆分（apps 为空且 {cfg.get('apps_dir') or DEFAULT_APPS_DIR} 存在），"
                  f"禁止重复拆分")
            return 2
        print("[split_config] apps 为空且未发现 apps 目录，无需拆分")
        return 0

    apps_dir = cfg.get("apps_dir") or DEFAULT_APPS_DIR
    if not os.path.isabs(apps_dir):
        apps_dir = os.path.join(ROOT, apps_dir)
    os.makedirs(apps_dir, exist_ok=True)

    # safe 名冲突检测：同名会互相覆盖，直接报错退出
    safe_names = [safe_app_name(a.get("name", "app")) for a in apps]
    if len(set(safe_names)) != len(safe_names):
        dup = {n for n in safe_names if safe_names.count(n) > 1}
        print(f"[split_config] App 名转安全文件名冲突: {sorted(dup)}，中止")
        return 2

    for i, (a, safe) in enumerate(zip(apps, safe_names)):
        # 文件名带序号前缀：load_config 按文件名排序即可还原 config.yaml 原始顺序
        fp = os.path.join(apps_dir, f"{i + 1:02d}_{safe}.yaml")
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(a, f, allow_unicode=True, sort_keys=False,
                           default_flow_style=False)
        print(f"[split_config] 写 {os.path.relpath(fp, ROOT)}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak_dir = os.path.join(ROOT, "_backup_pre_fix")
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, f"config.yaml.pre_split_{ts}")
    shutil.copy2(config_path, bak)
    print(f"[split_config] 备份 {os.path.relpath(bak, ROOT)}")

    slim = {k: v for k, v in cfg.items() if k in KEEP_TOP_KEYS}
    slim["apps_dir"] = os.path.relpath(apps_dir, ROOT).replace("\\", "/")
    slim["apps"] = []
    slim["money_behaviors"] = ["withdraw"]
    with open(config_path, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(slim, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)
    print(f"[split_config] 主文件瘦身完成: {config_path}")
    print(f"[split_config] 共拆分 {len(apps)} 个 App -> {os.path.relpath(apps_dir, ROOT)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="拆分 config.yaml apps 段到 config/apps/")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    args = ap.parse_args()
    sys.exit(split(args.config))


if __name__ == "__main__":
    main()
