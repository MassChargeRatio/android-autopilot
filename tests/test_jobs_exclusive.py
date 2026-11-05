# -*- coding: utf-8 -*-
"""test_jobs_exclusive.py - 设备独占不变式（P2-5）

背景（并发竞态）：历史实现是上层「先 jobs.active() 检查、再 jobs.create() 登记」，
两次取锁之间是空窗 —— 两个并发 POST /api/jobs 都能看到「无运行中任务」并各自
登记，于是同时跑两个任务抢同一台设备，设备独占不变式被破。

修法：JobManager.create_exclusive() 把「判空闲 + 登记」放进同一把锁，
已有运行中任务时抛 JobBusy（server 转 409）。

运行：
    python -m pytest tests/test_jobs_exclusive.py -q
"""
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from webui import jobs as J  # noqa: E402


def _steps():
    return [J.Step("假步骤", [sys.executable, "-c", "pass"])]


def test_create_exclusive_raises_when_busy():
    """已有运行中任务：第二次必须抛 JobBusy，而不是再登记一个。"""
    mgr = J.JobManager()
    first = mgr.create_exclusive("apps", "第一单", _steps())
    assert first is not None
    assert mgr.active() is first
    try:
        mgr.create_exclusive("apps", "第二单", _steps())
    except J.JobBusy as e:
        assert "已有任务在运行" in str(e), str(e)
        assert e.active is first
    else:
        raise AssertionError("并发冲突未抛 JobBusy")
    assert len(mgr.list()) == 1, mgr.list()


def test_create_exclusive_race_only_one_wins():
    """12 线程同时抢：只允许 1 单成功，其余全部 JobBusy。"""
    mgr = J.JobManager()
    ok, busy = [], []
    lock = threading.Lock()
    start = threading.Barrier(12)

    def worker(i):
        try:
            start.wait(timeout=5)
            job = mgr.create_exclusive("apps", f"抢单{i}", _steps())
            with lock:
                ok.append(job)
        except J.JobBusy:
            with lock:
                busy.append(i)

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=10)

    assert len(ok) == 1, f"应只成功 1 单，实际 {len(ok)}"
    assert len(busy) == 11, f"应 11 单被拒，实际 {len(busy)}"
    assert len(mgr.list()) == 1, mgr.list()


def test_create_still_works_after_finish():
    """前一单结束后可正常起下一单（不误锁死）。"""
    mgr = J.JobManager()
    first = mgr.create_exclusive("apps", "第一单", _steps())
    # finished 是只读属性（state in 终态集合），直接置终态 state
    first.state = J.STATE_DONE
    second = mgr.create_exclusive("apps", "第二单", _steps())
    assert second is not first


if __name__ == "__main__":
    n = f = 0
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            n += 1
            try:
                fn()
                print(f"OK  {name}")
            except Exception as e:  # noqa: BLE001
                f += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}")
    print(f"\n{n - f}/{n} 通过")
    sys.exit(1 if f else 0)
