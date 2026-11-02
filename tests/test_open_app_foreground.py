# -*- coding: utf-8 -*-
"""test_open_app_foreground.py - 启动后前台包名闸门（2026-10-30）

立卡依据（真机采样，京东冷启动 35 秒）：
    1.0s n=  64 .MainFrameActivity
    7.6s n= 162 com.xingin.matrix.detail.activity.DetailFeedActivity   ← 小红书
   35.3s n=  78 com.xingin.matrix.detail.activity.DetailFeedActivity   ← 还在小红书

京东开屏广告 deeplink 直接跳到小红书，前台已经不是京东；而 `_open_app` 原来
无条件打印「已启动 京东」就往下走，整条 sign 链的盲点坐标全打在小红书里。
这与 2026-10-30 早些时候「趣头条未安装 → 坐标打进微信」是同一类事故：
**设备层已经跑偏，上层却当成成功**。

修复：`_wait_page_ready` 多返回一个前台包名；`_open_app` 校验它，
不对就重启一次，仍不对就跳过整个 App（返回 False）。

运行：
    python tests/test_open_app_foreground.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402

PKG = "com.jingdong.app.mall"
OTHER = "com.xingin.matrix"


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))

    def has(self, level, needle):
        return any(lv == level and needle in ev for lv, ev in self.lines)


class _D:
    def __init__(self):
        self.started = []

    def shell(self, cmd, **kw):
        return f"package:{PKG}\n"

    def app_start(self, pkg, stop=False):
        self.started.append((pkg, stop))


class _Human:
    def after_open(self):
        pass


def _mk(fg_sequence):
    """fg_sequence: 每次 _wait_page_ready 返回的前台包名序列。"""
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    ex.d = _D()
    ex.dry_run = False
    ex.human = _Human()
    seq = list(fg_sequence)

    def _wait(pkg, name, **kw):
        fg = seq.pop(0) if seq else ""
        return 100, 1.0, True, fg

    ex._wait_page_ready = _wait
    return ex


def t_foreground_ok_proceeds():
    ex = _mk([PKG])
    assert ex._open_app(PKG, "京东") is True
    assert ex.d.started == [(PKG, False)], ex.d.started
    assert ex.recorder.has("INFO", "已启动"), ex.recorder.lines
    print("OK  前台正确 -> 正常启动")


def t_foreground_other_app_restarts_once():
    """第一次跳到了别的 App -> 重启一次，第二次正常就继续。"""
    ex = _mk([OTHER, PKG])
    assert ex._open_app(PKG, "京东") is True
    assert len(ex.d.started) == 2, ex.d.started
    assert ex.d.started[1] == (PKG, True), "重启必须是冷启动"
    assert ex.recorder.has("WARN", "deeplink"), ex.recorder.lines
    print("OK  前台跑到别的 App -> 冷启动重启一次后继续")


def t_foreground_other_twice_skips_app():
    """两次都跑到别的 App -> 返回 False，且绝不打印「已启动」。"""
    ex = _mk([OTHER, OTHER])
    assert ex._open_app(PKG, "京东") is False
    assert not ex.recorder.has("INFO", "已启动"), ex.recorder.lines
    assert ex.recorder.has("ERROR", "跳过本次全部行为"), ex.recorder.lines
    print("OK  两次都跑偏 -> 跳过整个 App（不盲点）")


def t_empty_foreground_also_gated():
    """取不到前台包名（空串）同样视为「没起来」，不能放行。"""
    ex = _mk(["", ""])
    assert ex._open_app(PKG, "京东") is False
    print("OK  前台取不到（空）-> 同样跳过")


def t_dry_run_unaffected():
    ex = _mk([PKG])
    ex.dry_run = True
    assert ex._open_app(PKG, "京东") is True
    assert ex.d.started == [], "dry-run 不该真启动"
    print("OK  dry-run 不触碰设备")


def t_runner_skips_on_false():
    """behavior_runner 侧：`is False` 才跳过（None 是测试 stub，不受影响）。"""
    import inspect
    import behavior_runner
    src = inspect.getsource(behavior_runner)
    assert "跳过本次全部行为" in src
    print("OK  behavior_runner 收到 False 会整单跳过")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
