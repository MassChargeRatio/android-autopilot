# -*- coding: utf-8 -*-
"""test_recorder_batch.py - recorder 批量缓冲（A1）单元测试

覆盖：
  1. ops 按条数阈值批量 commit（未达阈值不落库）；
  2. ops 按超时秒数批量 commit；
  3. close() 会把积压 ops 全量落库；
  4. earnings（资金数据）立即 commit，不受缓冲影响；
  5. 缓冲满前 ops 对其他连接不可见；
  6. 显式 flush() 立即可见；
  7. 重复 close 安全；
  8. DB 异常时 log 不抛（except: pass 语义）。

运行：
    python -m pytest tests/test_recorder_batch.py -q
"""
import os
import sqlite3
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from recorder import Recorder  # noqa: E402


def _mk(flush_every=50, flush_seconds=2.0):
    tmp = tempfile.mkdtemp(prefix="rec_batch_")
    db = os.path.join(tmp, "test.db")
    r = Recorder(db)
    r._flush_every = flush_every
    r._flush_seconds = flush_seconds
    r._last_flush = time.time()
    return r, db


def _op_count(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM ops").fetchone()[0]
    finally:
        conn.close()


def _earning_count(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute("SELECT COUNT(*) FROM earnings").fetchone()[0]
    finally:
        conn.close()


def test_flush_by_count():
    """达条数阈值自动落库。"""
    r, db = _mk(flush_every=3, flush_seconds=99)
    r.log("a1")
    r.log("a2")
    assert _op_count(db) == 0, "未达阈值不应落库"
    r.log("a3")
    assert _op_count(db) == 3, "达阈值应落库 3 条"
    r.close()
    print("OK  条数触发批量 commit")


def test_flush_by_time():
    """超时秒数触发自动落库。"""
    r, db = _mk(flush_every=999, flush_seconds=0.3)
    r.log("t1")
    time.sleep(0.5)
    r.log("t2")
    assert _op_count(db) == 2, "超时应已落库"
    r.close()
    print("OK  时间触发批量 commit")


def test_close_flushes_all():
    """close 前积压的 ops 在 close 后全量可见。"""
    r, db = _mk(flush_every=999, flush_seconds=99)
    for i in range(7):
        r.log(f"c{i}")
    assert _op_count(db) == 0, "close 前不应落库"
    r.close()
    assert _op_count(db) == 7, "close 后应全量落库"
    print("OK  close 全量落库")


def test_earning_immediate():
    """earnings 立即 commit，不等批量。"""
    r, db = _mk(flush_every=999, flush_seconds=99)
    r.record_earning("测试App", "签到", 1.5, "元", "detail")
    assert _earning_count(db) == 1, "earnings 应立即可见"
    r.close()
    print("OK  earnings 立即落库")


def test_ops_buffered_invisible_before_threshold():
    """缓冲满前 ops 对其他连接不可见。"""
    r, db = _mk(flush_every=50, flush_seconds=99)
    r.log("b1")
    r.log("b2")
    assert _op_count(db) == 0, "未达阈值且未 flush 时 ops 不应可见"
    r.close()
    assert _op_count(db) == 2, "close 后应可见"
    print("OK  缓冲语义：阈值前不可见")


def test_flush_explicit():
    """显式 flush() 立即落库。"""
    r, db = _mk(flush_every=999, flush_seconds=99)
    r.log("f1")
    r.flush()
    assert _op_count(db) == 1, "flush 后应立即可见"
    r.close()
    print("OK  显式 flush 落库")


def test_double_close_safe():
    """重复 close 不抛异常、不重复落库。"""
    r, db = _mk(flush_every=999, flush_seconds=99)
    r.log("d1")
    r.close()
    r.close()
    assert _op_count(db) == 1
    print("OK  重复 close 安全")


def test_db_error_swallowed():
    """DB 写入失败时 log 不抛（except: pass 语义）。"""
    tmp = tempfile.mkdtemp(prefix="rec_batch_")
    db = os.path.join(tmp, "test.db")
    r = Recorder(db)
    r.close()
    # 关闭后 conn 已失效，此时 log 不应抛异常
    r.log("should-not-crash")
    print("OK  DB 异常被吞，不抛")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
