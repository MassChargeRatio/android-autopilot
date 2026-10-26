# -*- coding: utf-8 -*-
"""check_apps.py - 核对 config.yaml 里的 app 是否真实安装在真机上

用法：
    python devtools/check_apps.py [--config config.yaml] [--json out.json]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from adbkit import Adb  # noqa: E402
from config_loader import load_config  # noqa: E402


def load_apps(path):
    cfg = load_config(path)
    return cfg.get("apps") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    apps = load_apps(args.config)
    a = Adb()
    a.ensure()
    out = a.shell("pm list packages")
    installed = set()
    for line in out.splitlines():
        m = re.match(r"package:(\S+)", line.strip())
        if m:
            installed.add(m.group(1))
    print(f"真机已安装第三方+系统包: {len(installed)} 个")
    print(f"config.yaml app 数: {len(apps)}\n")

    ok, missing = [], []
    for app in apps:
        pkg = app.get("package")
        (ok if pkg in installed else missing).append(app)

    print(f"=== 已安装 {len(ok)} ===")
    for app in ok:
        print(f"  ✓ {app.get('name')}  [{app.get('package')}]")
    print(f"\n=== 未安装 {len(missing)} ===")
    for app in missing:
        print(f"  ✗ {app.get('name')}  [{app.get('package')}]")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"installed": [x.get("package") for x in ok],
                       "missing": [x.get("package") for x in missing]},
                      f, ensure_ascii=False, indent=2)
        print(f"\n已写出: {args.json}")


if __name__ == "__main__":
    main()
