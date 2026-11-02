# -*- coding: utf-8 -*-
"""test_open_app_guard.py - Executor._open_app 的「未安装拒跑」闸门

背景（2026-10-30 真机事故，一手取证）：
    趣头条（com.jifen.qukan）在本机根本没安装。`d.app_start(pkg)` 对不存在的
    包静默失败，`_open_app` 仍然无条件打印「已启动 趣头条」，随后 sign 链的
    click_point 盲点坐标 (750,2132) / (163,1049) 全部落在当时前台的微信上。
    日志里看不出任何异常——这是「误报成功族」的典型：设备层失败被上层当成功。

修复：启动前用 `pm list packages <pkg>` 确认包存在，不存在则
    - 记 ERROR
    - 返回 False（调用方 behavior_runner 整单跳过，不再执行任何步骤）

运行：
    python tests/test_open_app_guard.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402

PKG = "com.jifen.qukan"


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))

    def has(self, level, needle):
        return any(lv == level and needle in ev for lv, ev in self.lines)


class _FakeDevice:
    """只实现 _open_app 用到的 shell / app_start / info。"""

    def __init__(self, installed=True, shell_raises=False):
        self.installed = installed
        self.shell_raises = shell_raises
        self.started = []
        self.shells = []

    def shell(self, cmd, **kw):
        self.shells.append(cmd)
        if self.shell_raises:
            raise RuntimeError("adb 掉了")
        if self.installed:
            return f"package:{PKG}\n"
        return ""

    def app_start(self, pkg, stop=False):
        self.started.append((pkg, stop))

    @property
    def info(self):
        return {}


class _Human:
    def after_open(self):
        pass


def _mk(device, dry_run=False):
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex.d = device
    ex.dry_run = dry_run
    ex.human = _Human()
    # 页面就绪判定与本次修复无关，直接短路，避免依赖 dump
    # 返回 4 元组：第 4 位是前台包名，_open_app 会校验它是否等于目标包
    ex._wait_page_ready = lambda pkg, name, **kw: (100, 0.1, True, pkg)
    return ex


def t_not_installed_refuses_and_returns_false():
    dev = _FakeDevice(installed=False)
    ex = _mk(dev)
    r = ex._open_app(PKG, "趣头条")
    assert r is False, f"未安装必须返回 False，实际 {r!r}"
    assert dev.started == [], f"未安装时不该 app_start，实际 {dev.started}"
    assert ex.recorder.has("ERROR", "未安装"), ex.recorder.lines
    print("OK  未安装 -> 返回 False 且不 app_start")


def t_not_installed_does_not_claim_started():
    """关键：绝不能打印「已启动」。这正是当初骗过眼睛的那句日志。"""
    ex = _mk(_FakeDevice(installed=False))
    ex._open_app(PKG, "趣头条")
    assert not ex.recorder.has("INFO", "已启动"), ex.recorder.lines
    print("OK  未安装时不打印「已启动」（不再误报成功）")


def t_installed_launches_and_returns_true():
    dev = _FakeDevice(installed=True)
    ex = _mk(dev)
    r = ex._open_app(PKG, "趣头条", reset=True)
    assert r is True, r
    assert dev.started == [(PKG, True)], dev.started
    assert ex.recorder.has("INFO", "已启动"), ex.recorder.lines
    print("OK  已安装 -> app_start(stop=True) 且返回 True")


def t_shell_error_does_not_block():
    """查询本身失败（adb 抖动）不能误杀：宁可继续跑。"""
    dev = _FakeDevice(installed=False, shell_raises=True)
    ex = _mk(dev)
    r = ex._open_app(PKG, "趣头条")
    assert r is True, f"查询失败应放行，实际 {r!r}"
    assert dev.started == [(PKG, False)], dev.started
    print("OK  pm 查询异常时放行，不误杀")


def t_dry_run_never_touches_device():
    dev = _FakeDevice(installed=False)
    ex = _mk(dev, dry_run=True)
    r = ex._open_app(PKG, "趣头条")
    assert r is True, "dry-run 视为成功"
    assert dev.shells == [] and dev.started == [], (dev.shells, dev.started)
    print("OK  dry-run 不查包也不启动")


def t_runner_skips_app_when_open_returns_false():
    """behavior_runner 侧：`is False` 才跳过，None（测试 stub）不受影响。"""
    import inspect
    import behavior_runner
    src = inspect.getsource(behavior_runner)
    assert "is False" in src, "必须用 `is False` 判定，否则 stub 返回 None 会误跳过"
    assert "跳过本次全部行为" in src
    print("OK  behavior_runner 用 `is False` 判定并整单跳过")


def main():
    t_not_installed_refuses_and_returns_false()
    t_not_installed_does_not_claim_started()
    t_installed_launches_and_returns_true()
    t_shell_error_does_not_block()
    t_dry_run_never_touches_device()
    t_runner_skips_app_when_open_returns_false()
    print("\n全部通过 6/6")


if __name__ == "__main__":
    main()
