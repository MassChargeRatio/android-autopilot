# -*- coding: utf-8 -*-
"""test_page_ready.py - Executor._wait_page_ready 单元测试（无需真机）

背景：App 落地页不确定（开屏广告/活动弹窗/新手引导/上次退出的 tab/登录态），
启动后立刻 dump 常抓到启动页，导致锚点全部未命中。实测同一批配置不同轮次
结果差异显著。`_wait_page_ready` 轮询 dump，等节点数连续两次变化很小
（<=10%）且达标才认为页面已稳定。

运行：
    python tests/test_page_ready.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402

PKG = "com.demo.app"


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append(f"[{level}] {event}")


class _Info:
    def __init__(self, pkg):
        self._pkg = pkg

    def get(self, k, d=None):
        return self._pkg if k == "currentPackageName" else d


class _FakeDevice:
    """按脚本逐次返回节点数；脚本耗尽后重复最后一个值。"""

    def __init__(self, counts, pkgs=None):
        self.counts = list(counts)
        self.pkgs = list(pkgs) if pkgs else None
        self.i = 0
        self.dumps = 0

    def dump_hierarchy(self):
        n = self.counts[min(self.i, len(self.counts) - 1)]
        self.dumps += 1
        return "<hierarchy>" + "<node/>" * n + "</hierarchy>"

    @property
    def info(self):
        p = (self.pkgs[min(self.i, len(self.pkgs) - 1)]
             if self.pkgs else PKG)
        self.i += 1
        return _Info(p)


def _mk(device, dry_run=False):
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex.d = device
    ex.dry_run = dry_run
    return ex


def t_dry_run_short_circuit():
    ex = _mk(_FakeDevice([10]), dry_run=True)
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=1, poll=0.01)
    assert (n, waited, stable) == (0, 0.0, True), (n, waited, stable)
    assert ex.d.dumps == 0, "dry-run 不应 dump 设备"
    print("OK  dry-run 直接返回 (0,0,True)，不触碰设备")


def t_stable_immediately():
    """节点数稳定且达标 -> 很快返回稳定。"""
    ex = _mk(_FakeDevice([100, 100, 100]))
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=5, poll=0.01)
    assert stable is True, (n, waited, stable)
    assert n == 100, n
    print("OK  节点数稳定且达标时判定为已就绪")


def t_waits_until_settled():
    """页面先剧烈变化，稳定后才返回（不会在启动页就动手）。"""
    ex = _mk(_FakeDevice([5, 40, 42, 200, 200]))
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=5, poll=0.01)
    assert stable is True and n == 200, (n, waited, stable)
    assert ex.d.dumps >= 4, f"应至少轮询 4 次，实际 {ex.d.dumps}"
    print("OK  页面从启动页(5节点)变化到稳定(200节点)后才就绪")


def t_never_returns_on_wrong_foreground():
    """前台不是目标包时不应判定就绪（哪怕节点数稳定）。"""
    ex = _mk(_FakeDevice([100, 100, 100, 100, 100, 100],
                         pkgs=["com.other.app"] * 6))
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=0.05, poll=0.01)
    assert stable is False, "前台非目标包不应判就绪"
    print("OK  前台非目标包时不会误判为就绪")


def t_min_nodes_enforced():
    """节点数不达标（疑似启动页）不算稳定。"""
    ex = _mk(_FakeDevice([3, 3, 3, 3, 3, 3]))
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=0.05, poll=0.01)
    assert stable is False, "节点数不足不应判就绪"
    print("OK  节点数低于阈值时不算就绪")


def t_timeout_returns_last():
    """一直变化（始终不稳定）时超时返回，且不抛异常。

    2026-10-23：节点数保持在 80 以下，避免触发「波动型页面提前放行」兜底
    （该兜底见 t_volatile_page_accepted_early）。
    """
    ex = _mk(_FakeDevice([10, 20, 40, 60, 30, 70]))
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=0.05, poll=0.01)
    assert stable is False
    assert n > 0
    print("OK  持续不稳定时超时返回（不阻塞流程）")


def t_volatile_page_accepted_early():
    """波动型页面（节点数一直小幅变化但已很丰富）应提前放行，不再白等满 max_wait。"""
    ex = _mk(_FakeDevice([100, 300, 500, 900, 1300, 1700]))
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=0.2, poll=0.01)
    assert stable is True, "节点数充足且已过半数预算时应提前放行"
    assert n >= 80
    assert waited < 0.2, f"应早于 max_wait 返回，实际 {waited}"
    print("OK  波动型页面提前放行（省下等待时间）")


def t_dump_exception_is_tolerated():
    """dump 抛异常时应继续重试而不是崩掉。"""
    class _Bad(_FakeDevice):
        def __init__(self):
            super().__init__([100, 100, 100, 100])
            self.first = True

        def dump_hierarchy(self):
            if self.first:
                self.first = False
                raise RuntimeError("device offline")
            return super().dump_hierarchy()

    ex = _mk(_Bad())
    n, waited, stable, fg = ex._wait_page_ready(PKG, "T", max_wait=5, poll=0.01)
    assert stable is True and n == 100, (n, waited, stable)
    assert any("探测异常" in l for l in ex.recorder.lines)
    print("OK  dump 异常被容忍并继续重试")


if __name__ == "__main__":
    tests = [t_dry_run_short_circuit, t_stable_immediately,
             t_waits_until_settled, t_never_returns_on_wrong_foreground,
             t_min_nodes_enforced, t_timeout_returns_last,
             t_dump_exception_is_tolerated]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
