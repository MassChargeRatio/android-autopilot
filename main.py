# -*- coding: utf-8 -*-
"""
main.py - Android Autopilot 入口
用法：
  python main.py --app 阅读App --task "签到并看视频"
  python main.py --task "去10分钟签到"
  python main.py --list
  python main.py --today
  python main.py --app 阅读App --task "签到" --dry-run   # 只打印计划不操作设备
推荐（周期任务语义更稳）：
  python main.py --task "去示例阅读App签到，然后看视频，最后提现"
"""
import argparse
import os
import sys
from datetime import datetime

try:
    import yaml
except ImportError:  # 无 PyYAML 时用内置零依赖解析器兜底
    import miniyaml as yaml

from human import Human
from recorder import Recorder
from nlu import match_app, parse_intents

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(BASE_DIR, "config.yaml")


def parse_args():
    ap = argparse.ArgumentParser(description="Android Autopilot - 模拟真人自动完成 app 签到/打卡/看视频/提现")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="配置文件路径")
    ap.add_argument("--app", default=None, help="目标 app（名称/别名/序号；缺省时从 --task 语义推断）")
    ap.add_argument("--task", default="签到", help="自然语言描述的行为，例如：签到并看视频，然后提现")
    ap.add_argument("--serial", default=None, help="覆盖设备 adb 地址，如 127.0.0.1:5555")
    ap.add_argument("--dry-run", action="store_true", help="只打印执行计划，不触碰设备")
    ap.add_argument("--force", action="store_true", help="忽略作息窗口限制强制执行")
    ap.add_argument("--today", action="store_true", help="仅打印今日收益汇总")
    ap.add_argument("--list", action="store_true", help="列出配置的 app 与可用行为")
    return ap.parse_args()


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        print(f"配置文件不存在: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def show_list(cfg: dict):
    apps = cfg.get("apps", []) or []
    if not apps:
        print("配置中暂无 app。请在 config.yaml 的 apps 段添加。")
        return
    print(f"共 {len(apps)} 个 app：\n")
    for i, app in enumerate(apps, 1):
        behaviors = app.get("behaviors", {}) or {}
        bdesc = "、".join(behaviors.keys()) or "(无)"
        print(f"  {i}. {app.get('name','?')}  [{app.get('package','?')}]")
        print(f"     别名: {', '.join(app.get('aliases', []) or []) or '-'}")
        print(f"     可用行为: {bdesc}")
        print()


def main():
    args = parse_args()
    cfg = load_config(args.config)

    human = Human(cfg)
    data_dir = os.path.join(BASE_DIR, "data")
    recorder = Recorder(
        db_path=os.path.join(data_dir, "records.db"),
        log_path=os.path.join(data_dir, f"run-{datetime.now():%Y%m%d}.log"),
    )

    if args.list:
        show_list(cfg)
        recorder.close()
        return

    if args.today:
        recorder.print_today_summary()
        recorder.close()
        return

    # ---- 目标 app ----
    app_cfg, err = None, None
    if args.app:
        app_cfg, err = match_app(args.app, cfg.get("apps", []) or [])
    if app_cfg is None:
        app_cfg, err = match_app(args.task, cfg.get("apps", []) or [])
    if app_cfg is None:
        recorder.log(f"无法确定目标 app：{err}", "sys", "ERROR")
        recorder.close()
        sys.exit(1)

    # ---- 自然语言 -> 意图 ----
    intents = parse_intents(args.task)
    if not intents:
        recorder.log(f"从任务描述中未识别到行为关键词，回退为[签到]: {args.task}",
                     "sys", "WARN")
        intents = [("sign", "签到")]
    plan = " -> ".join(f"{kw}({i})" for i, kw in intents)
    recorder.log(f"目标 app: {app_cfg.get('name')} | 执行计划: {plan}", "sys")

    # ---- 作息窗口 ----
    if not args.force and not human.in_wake_window():
        recorder.log(
            f"当前不在作息活跃窗口内（{cfg.get('human', {}).get('wake_window')}），已跳过。"
            "如需强制执行请加 --force。",
            "sys", "INFO")
        recorder.close()
        return

    # ---- 启动时刻随机偏移（打散节奏）----
    wait = human.start_wait()
    if wait > 0 and not args.dry_run:
        print(f"[Human] 随机等待 {int(wait)}s 后开始……")
        import time
        time.sleep(wait)

    # ---- 执行 ----
    serial = args.serial or (cfg.get("device", {}) or {}).get("serial")
    ex = __import__("executor").Executor(
        serial, human, recorder, dry_run=args.dry_run, config=cfg)
    ex.connect()

    if args.dry_run:
        recorder.log("[dry-run] 以下为计划执行的行为（不操作设备）", app_cfg.get("name"))

    ex.run_app_flow(app_cfg, intents)

    # ---- 汇总 ----
    recorder.log("本次任务执行完毕", app_cfg.get("name"))
    recorder.print_today_summary()
    recorder.close()


if __name__ == "__main__":
    main()
