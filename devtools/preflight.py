# -*- coding: utf-8 -*-
"""preflight.py - 环境自检（接手/排障第一步）

一次跑完，输出可读报告：
  1. Python 与关键依赖（uiautomator2 / yaml / PIL / cv2 / requests）
  2. adb 解析结果 + 设备在线状态 + 屏幕参数 + 前台包名
  3. 截图链路（字节数 + PNG 魔数校验）
  4. VLM 网关 /models 可达性
  5. config.yaml 可加载 + app 数量与行为分布

用法：
    python devtools/preflight.py [--serial 192.168.1.54:5555] [--config config.yaml]
退出码：0 全部通过；1 有 FAIL 项（WARN 不影响退出码）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from config_loader import load_config  # noqa: E402

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"
_results = []


def rec(level, name, detail=""):
    _results.append((level, name, detail))
    print(f"[{level}] {name}" + (f" -> {detail}" if detail else ""))


def check_python():
    rec(OK, "Python", sys.version.split()[0])
    mods = {"uiautomator2": "uiautomator2", "yaml": "PyYAML",
            "PIL": "Pillow", "cv2": "opencv-python", "requests": "requests"}
    missing = []
    for mod, pkg in mods.items():
        try:
            __import__(mod)
            rec(OK, f"依赖 {pkg}")
        except ImportError:
            missing.append(pkg)
            rec(WARN, f"依赖 {pkg}", "未安装（模板匹配/VLM 相关能力会降级）")
    return missing


def check_adb(serial):
    from adbkit import Adb, resolve_adb
    try:
        adb_path = resolve_adb()
    except FileNotFoundError as e:
        rec(FAIL, "adb 解析", str(e))
        return None
    rec(OK, "adb 路径", adb_path)
    a = Adb(serial=serial, adb_path=adb_path)
    try:
        got = a.ensure(serial)
        rec(OK, "设备在线", got)
    except Exception as e:
        rec(FAIL, "设备连接", f"{type(e).__name__}: {e}")
        return None
    try:
        w, h = a.screen_size()
        rec(OK, "屏幕分辨率", f"{w}x{h}")
        rec(OK if a.is_screen_on() else WARN, "屏幕点亮",
            "awake" if a.is_screen_on() else "熄屏/锁屏 —— 需先唤醒")
        rec(OK, "前台包名", a.foreground() or "(未识别)")
    except Exception as e:
        rec(WARN, "设备信息", f"{type(e).__name__}: {e}")
    try:
        data = a.screenshot_bytes()
        rec(OK, "截图链路", f"{len(data)} 字节, PNG 魔数校验通过")
    except Exception as e:
        rec(FAIL, "截图链路", f"{type(e).__name__}: {e}")
    return a


def check_vlm(cfg):
    vlm = ((cfg or {}).get("vision") or {}).get("vlm") or {}
    base = (vlm.get("base_url") or "").rstrip("/")
    key = vlm.get("api_key") or ""
    if not base:
        rec(WARN, "VLM 网关", "config.yaml 未配置 vision.vlm.base_url")
        return
    url = base + "/models"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
        ids = []
        try:
            ids = [m.get("id") for m in json.loads(body).get("data", [])]
        except Exception:
            pass
        want = vlm.get("model")
        hit = want in ids
        rec(OK if hit else WARN, "VLM 网关",
            f"{url} HTTP 200, 主模型 {want} {'可用' if hit else '不在模型列表'}"
            f" (共 {len(ids)} 个模型)")
    except Exception as e:
        rec(FAIL, "VLM 网关", f"{url} 不可达: {type(e).__name__}: {e}")


def check_config(path):
    if not os.path.exists(path):
        rec(FAIL, "config.yaml", f"不存在: {path}")
        return {}
    try:
        cfg = load_config(path)
    except Exception as e:
        rec(FAIL, "config.yaml 解析", f"{type(e).__name__}: {e}")
        return {}
    apps = cfg.get("apps") or []
    rec(OK, "config.yaml", f"加载成功, {len(apps)} 个 app")
    dist = {}
    no_behavior = []
    for app in apps:
        bh = app.get("behaviors") or {}
        if not bh:
            no_behavior.append(app.get("name"))
        for k in bh:
            dist[k] = dist.get(k, 0) + 1
    rec(OK, "行为分布", ", ".join(f"{k}={v}" for k, v in sorted(dist.items())))
    if no_behavior:
        rec(WARN, "无行为配置的 app", ", ".join(map(str, no_behavior)))
    missing_pkg = [a.get("name") for a in apps if not a.get("package")]
    if missing_pkg:
        rec(WARN, "缺少 package", ", ".join(map(str, missing_pkg)))
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=None)
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    args = ap.parse_args()

    print("=" * 62)
    print("Android Autopilot 环境自检")
    print("=" * 62)
    print("-- 1. Python / 依赖 --")
    check_python()

    print("\n-- 2. config.yaml --")
    cfg = check_config(args.config)
    serial = args.serial or ((cfg.get("device") or {}).get("serial"))

    print("\n-- 3. 设备 / adb --")
    check_adb(serial)

    print("\n-- 4. VLM 网关 --")
    check_vlm(cfg)

    fails = [r for r in _results if r[0] == FAIL]
    warns = [r for r in _results if r[0] == WARN]
    print("\n" + "=" * 62)
    print(f"结果: {len(_results)} 项检查, FAIL={len(fails)}, WARN={len(warns)}")
    if fails:
        for lvl, name, detail in fails:
            print(f"  FAIL: {name} -> {detail}")
    print("=" * 62)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
