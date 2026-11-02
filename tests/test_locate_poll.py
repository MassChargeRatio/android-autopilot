# -*- coding: utf-8 -*-
"""test_locate_poll.py - B2 _locate 250ms 粒度轮询（2026-10-30 任务卡）

立卡依据：弹窗清扫要顺序试 13 个关闭文案，每次 timeout=0.8。原实现每次都要
睡满 0.8s 才返回，干净屏一轮 = 13×0.8 = 10.4s（快手 3 轮 37s 的主因之一）。
改成 poll 粒度后，未命中一轮降到 13×0.25 ≈ 3.25s，命中延迟也从"最多 0.8s"降到"最多 0.25s"。

语义不变：命中即返回、超时返回未命中、拒配继续找。

运行：
    python tests/test_locate_poll.py
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from locator import Locator  # noqa: E402


class _Rec:
    def log(self, *a, **k):
        pass


class _Info(dict):
    pass


class _Obj:
    """桩元素：第 hits_at 次 wait 起返回 True。"""

    def __init__(self, hits_at):
        self.hits_at = hits_at
        self.waits = []

    def wait(self, timeout=1.0):
        self.waits.append(timeout)
        time.sleep(timeout)
        return len(self.waits) >= self.hits_at

    @property
    def count(self):
        return 1

    @property
    def info(self):
        return _Info(text="签到", contentDescription="", resourceId="",
                     clickable=True,
                     bounds={"left": 100, "top": 200,
                             "right": 300, "bottom": 400})

    @property
    def rect(self):
        class _R:
            left, top, right, bottom = 100, 200, 300, 400
        return _R()


class _D:
    dry_run = False

    def __init__(self, hits_at):
        self.obj = _Obj(hits_at)

    def __call__(self, **kw):
        return self.obj

    def textContains(self, v):
        return self.obj

    def resourceId(self, v):
        return self.obj

    def descriptionContains(self, v):
        return self.obj


def _mk(hits_at):
    loc = Locator.__new__(Locator)
    loc.recorder = _Rec()
    loc.dry_run = False
    loc.d = _D(hits_at)
    return loc, loc.d.obj


def t_hit_returns_early():
    """第 3 次 poll 命中 -> 约 0.75s 返回，且每次 wait ≤ poll。"""
    loc, obj = _mk(hits_at=3)
    t0 = time.time()
    res = loc._locate("text", "签到", timeout=6.0)
    elapsed = time.time() - t0
    assert res.hit is True, res
    assert elapsed < 1.2, f"应在 ~0.75s 内返回，实际 {elapsed:.2f}s"
    assert all(w <= 0.30 for w in obj.waits), obj.waits
    print(f"OK  B2 第 3 次 poll 命中，{elapsed:.2f}s（每次 wait ≤0.25s）")


def t_miss_returns_after_timeout():
    """一直未命中 -> 约 timeout 后返回 False（不再睡满 6s）。"""
    loc, obj = _mk(hits_at=9999)
    t0 = time.time()
    res = loc._locate("text", "签到", timeout=0.6)
    elapsed = time.time() - t0
    assert res.hit is False, res
    assert 0.45 < elapsed < 1.2, f"应在 ~0.6s 后返回，实际 {elapsed:.2f}s"
    print(f"OK  B2 timeout=0.6s 未命中，{elapsed:.2f}s 后返回")


def t_poll_overridable():
    """poll=0.05 -> 更细粒度，命中更快。"""
    loc, obj = _mk(hits_at=4)
    t0 = time.time()
    res = loc._locate("text", "签到", timeout=2.0, poll=0.05)
    elapsed = time.time() - t0
    assert res.hit is True, res
    assert elapsed < 0.5, f"poll=0.05 应更快，实际 {elapsed:.2f}s"
    assert all(w <= 0.06 for w in obj.waits), obj.waits
    print(f"OK  B2 poll=0.05 命中，{elapsed:.2f}s")


def t_dry_run_no_device_untouched():
    """dry-run / 无设备：不构造 selector、不 sleep。"""
    loc = Locator.__new__(Locator)
    loc.recorder = _Rec()
    loc.dry_run = True
    loc.d = None
    t0 = time.time()
    res = loc._locate("text", "签到", timeout=3.0)
    assert res.hit is False
    assert time.time() - t0 < 0.05
    print("OK  B2 dry-run 直接返回，不等待")


def t_unknown_kind_returns_miss():
    loc, _obj = _mk(hits_at=1)
    res = loc._locate("bogus", "x", timeout=0.2)
    assert res.hit is False and "未知定位类型" in res.detail, res
    print("OK  B2 未知 kind 返回未命中")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
