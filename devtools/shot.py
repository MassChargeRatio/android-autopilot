# -*- coding: utf-8 -*-
"""shot.py - 真机截图（字节安全）

用法：
    python devtools/shot.py out.png [--serial 192.168.1.54:5555] [--wait 3]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from adbkit import Adb  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="输出 png 路径")
    ap.add_argument("--serial", default=None)
    ap.add_argument("--wait", type=float, default=0.0, help="截图前等待秒数")
    args = ap.parse_args()
    a = Adb(serial=args.serial)
    a.ensure()
    if args.wait:
        time.sleep(args.wait)
    data = a.screenshot_bytes()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(data)
    print(f"saved: {args.out} ({len(data)} bytes) size={a.screen_size()} "
          f"fg={a.foreground()}")


if __name__ == "__main__":
    main()
