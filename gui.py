#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gui.py - Android Autopilot 本地 Web 控制台（入口）

    python gui.py                     # 启动并自动打开浏览器
    python gui.py --port 9000         # 指定端口
    python gui.py --no-browser        # 只起服务，不开浏览器
    python gui.py --config other.yaml # 指定配置文件

为什么不是 tkinter：
    本工程的运行环境（`.workbuddy-ai` 托管的 Python venv）**没有编译 tkinter**，
    `import tkinter` 直接 ModuleNotFoundError，任何 tkinter GUI 在这台机器上
    都起不来。改用 stdlib `http.server` + 浏览器前端，零第三方运行时依赖。

安全：只监听 127.0.0.1（局域网内其它机器访问不到）；写操作需要一次性 token
（启动时生成并注入首页），因此浏览器里的其它网页无法悄悄调用本控制台。

功能概览：
    总览     —— 设备状态、收益指标、近 7 日趋势、最近事件、配置体检
    任务编排 —— 34 个 App × 行为的勾选编排、串行执行、逐步进度、实时日志
    收益     —— 今日/7 日/30 日/累计汇总、按 App 排行、明细表
    设备     —— 在线状态、型号/分辨率/前台 App、实时截图（可自动刷新）
    工具     —— preflight / check_apps / shot / verify_live / stability_run / probe_deep
    配置     —— App·行为·锚点浏览、配置体检、重新载入
"""
import argparse
import os
import sys
import threading
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from webui import server as S            # noqa: E402
from webui import data as D              # noqa: E402


def build_parser():
    ap = argparse.ArgumentParser(description="Android Autopilot 本地 Web 控制台")
    ap.add_argument("--config", default=D.CONFIG_YAML, help="config.yaml 路径")
    ap.add_argument("--db", default=D.DB_PATH, help="records.db 路径")
    ap.add_argument("--host", default="127.0.0.1",
                    help="监听地址（默认仅本机；改成 0.0.0.0 会把控制台暴露到局域网）")
    ap.add_argument("--port", type=int, default=8765, help="监听端口（默认 8765）")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)

    console = S.Console(args.config, args.db)
    try:
        httpd = S.make_server(args.host, args.port, console)
    except OSError as e:
        print(f"[错误] 无法监听 {args.host}:{args.port} —— {e}")
        port = S.find_free_port(args.port + 1, args.host)
        print(f"       改用端口 {port}")
        httpd = S.make_server(args.host, port, console)

    host, port = httpd.server_address[0], httpd.server_address[1]
    url = f"http://{host}:{port}/"

    print("=" * 62)
    print("  Android Autopilot 控制台")
    print("=" * 62)
    print(f"  地址    : {url}")
    print(f"  配置    : {console.store.config_path}")
    print(f"  数据库  : {console.store.db_path}")
    print(f"  解释器  : {sys.executable}")
    if args.host not in ("127.0.0.1", "localhost"):
        print(f"  ⚠ 警告  : 正在监听 {args.host}，局域网内其它机器可访问！")
    print("  退出    : Ctrl+C")
    print("=" * 62)

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在退出…")
        console.jobs.stop_all()
        httpd.shutdown()
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
