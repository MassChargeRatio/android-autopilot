# -*- coding: utf-8 -*-
"""启动 App 并探测前台包名（枚举/探活核心方法）。
用法: python adb_probe_front.py <package_name> [等待秒数]
流程: resolve-activity 取启动组件 -> am start -n -> 等待 -> dumpsys window 前台包名 + 截图。
注意: 赚钱/资讯类 app 开屏广告期勿按 BACK(等于退出), 等待 12-20s 后再确认。
"""
import subprocess, sys, time, os

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
DEV = "192.168.1.54:5555"
OUT = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp"


def adb(args, t=60):
    return subprocess.run([ADB, "-s", DEV, "shell"] + args, capture_output=True, timeout=t, text=True)


def front_pkg():
    out = adb(["dumpsys", "window", "displays"]).stdout
    for line in out.splitlines():
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            return line.strip()
    return "(no focus line)"


def main():
    pkg = sys.argv[1]
    wait = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    # 1) 取启动组件
    r = adb(["cmd", "package", "resolve-activity", "--brief", pkg])
    comp = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    if not comp or comp.startswith("Error") or "NONE" in comp:
        print("[FAIL] resolve-activity 无结果:", pkg)
        return
    print("component:", comp)
    # 2) 启动
    subprocess.run([ADB, "-s", DEV, "shell", "am", "start", "-n", comp], capture_output=True, timeout=30)
    time.sleep(wait)
    # 3) 确认前台
    print("front:", front_pkg())
    # 4) 截图留证
    name = "probe_" + pkg.replace(".", "_") + ".png"
    p = subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], capture_output=True, timeout=60)
    path = os.path.join(OUT, name)
    open(path, "wb").write(p.stdout)
    print("shot:", path, len(p.stdout), "bytes", p.stdout[:8] == b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    main()
