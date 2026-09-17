# -*- coding: utf-8 -*-
"""
recorder.py - 操作与收益记录模块
SQLite 记账：记录每次操作日志 + 识别的收益（金币/金额/积分）。
控制台同步输出，全部落盘，方便事后复盘与对账。
"""
import os
import sqlite3
import time
from datetime import datetime


class Recorder:
    def __init__(self, db_path: str, log_path: str = None):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_schema()
        self.log_file = log_path
        if self.log_file:
            os.makedirs(os.path.dirname(self.log_file) or ".", exist_ok=True)

    # ---------- 数据库 ----------
    def _init_schema(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS earnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                app TEXT,
                action TEXT,
                amount REAL,
                unit TEXT,
                detail TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS ops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                app TEXT,
                event TEXT,
                level TEXT DEFAULT 'INFO'
            )
        """)
        self.conn.commit()

    # ---------- 通用日志 ----------
    def log(self, event: str, app: str = "", level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] [{app or '-'}] {event}"
        print(line)
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        try:
            self.conn.execute(
                "INSERT INTO ops (ts, app, event, level) VALUES (?,?,?,?)",
                (ts, app, event, level),
            )
            self.conn.commit()
        except Exception:
            pass

    # ---------- 收益记账 ----------
    def record_earning(self, app: str, action: str, amount: float, unit: str = "", detail: str = ""):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            "INSERT INTO earnings (ts, app, action, amount, unit, detail) VALUES (?,?,?,?,?,?)",
            (ts, app, action, amount, unit, detail),
        )
        self.conn.commit()
        self.log(f"收益入账: {app} / {action} / {amount}{unit} {detail}", app, "GAIN")

    # ---------- 汇总 ----------
    def today_summary(self):
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT app, action, amount, unit FROM earnings WHERE ts LIKE ?",
            (today + "%",),
        ).fetchall()
        return rows

    def print_today_summary(self):
        rows = self.today_summary()
        if not rows:
            print("今日暂无收益记录。")
            return
        print("\n========== 今日收益汇总 ==========")
        groups = {}
        for app, action, amount, unit in rows:
            key = (app, unit)
            g = groups.setdefault(key, {"actions": [], "total": 0.0})
            g["actions"].append((action, amount))
            g["total"] += float(amount or 0)
        for (app, unit), g in groups.items():
            print(f"  {app or '-'}: 合计 {g['total']:.2f}{unit}")
            for action, amt in g["actions"]:
                print(f"      - {action}: {amt}{unit}")
        print("==================================\n")

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
