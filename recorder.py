# -*- coding: utf-8 -*-
"""
recorder.py - 操作与收益记录模块
SQLite 记账：记录每次操作日志 + 识别的收益（金币/金额/积分）。
控制台同步输出，全部落盘，方便事后复盘与对账。

批量缓冲（A1）：ops 日志走"计数/超时批量 commit"，降低频繁落盘开销；
earnings（资金数据）保持立即 commit，不可丢失。
"""
import atexit
import os
import sqlite3
import threading
import time
from datetime import datetime


class Recorder:
    def __init__(self, db_path: str, log_path: str = None):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_schema()
        self.log_file = log_path
        # 批量提交参数：默认每 50 条或距上次提交 2.0 秒落库一次 ops。
        # config.yaml 新增 recorder 节可覆盖；读不到就用缺省值。
        self._flush_every = 50
        self._flush_seconds = 2.0
        try:
            try:
                import yaml as _y
            except ImportError:  # 无 PyYAML 时用内置零依赖解析器兜底
                import miniyaml as _y
            _cfg = _y.safe_load(open(
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "config.yaml"),
                encoding="utf-8")) or {}
            _r = _cfg.get("recorder") or {}
            self._flush_every = int(_r.get("flush_every", 50))
            self._flush_seconds = float(_r.get("flush_seconds", 2.0))
        except Exception:
            pass
        # ops 批量提交缓冲状态
        self._buf = []              # 已 execute 未 commit 的 ops 行
        self._lock = threading.RLock()
        self._pending = 0
        self._last_flush = time.time()
        self._closed = False
        # 日志文件长开句柄（append），避免每次 log 都 open/close
        self._log_f = None
        if self.log_file:
            os.makedirs(os.path.dirname(self.log_file) or ".", exist_ok=True)
            self._log_f = open(self.log_file, "a", encoding="utf-8")
        # 兜底：webui 强杀等异常退出时把积压 ops 落库、关闭句柄
        atexit.register(self._atexit_flush)

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

    # ---------- 批量提交 ----------
    def _flush_ops(self):
        """把积压的 ops 事务落库（commit）。失败保持 except: pass 语义。"""
        try:
            self.conn.commit()
        except Exception:
            pass
        self._pending = 0
        self._last_flush = time.time()

    def _maybe_flush_ops(self):
        """达到条数阈值或超时秒数时触发落库。"""
        if (self._pending >= self._flush_every
                or (time.time() - self._last_flush) >= self._flush_seconds):
            self._flush_ops()

    def flush(self):
        """显式落库积压 ops（进程正常退出 / 关键节点调用）。"""
        with self._lock:
            self._flush_ops()

    # ---------- 通用日志 ----------
    def log(self, event: str, app: str = "", level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] [{app or '-'}] {event}"
        print(line)
        if self._log_f is not None:
            self._log_f.write(line + "\n")
            self._log_f.flush()
        try:
            with self._lock:
                self.conn.execute(
                    "INSERT INTO ops (ts, app, event, level) VALUES (?,?,?,?)",
                    (ts, app, event, level),
                )
                self._buf.append((ts, app, event, level))
                self._pending += 1
                self._maybe_flush_ops()
        except Exception:
            pass

    # ---------- 收益记账 ----------
    def record_earning(self, app: str, action: str, amount: float, unit: str = "", detail: str = ""):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 资金数据不可丢：先把积压 ops 落库保证时序，再立即 commit earnings
        self._flush_ops()
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

    def _atexit_flush(self):
        """atexit 兜底：进程被强杀/异常退出时仍尽量落库尾部 ops。"""
        if self._closed:
            return
        try:
            self._flush_ops()
        except Exception:
            pass
        if self._log_f is not None:
            try:
                self._log_f.flush()
                self._log_f.close()
            except Exception:
                pass
            self._log_f = None
        try:
            self.conn.close()
        except Exception:
            pass

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.flush()
        except Exception:
            pass
        if self._log_f is not None:
            try:
                self._log_f.flush()
                self._log_f.close()
            except Exception:
                pass
            self._log_f = None
        try:
            self.conn.close()
        except Exception:
            pass
