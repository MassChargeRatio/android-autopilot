# -*- coding: utf-8 -*-
"""test_rpc_timeout.py - JSON-RPC 超时收紧（2026-10-31）

立卡依据：10-31 全量跑里抖音火山版、微博移动版各卡死**整整 300 秒**、期间零日志，
然后被外层 300s 上限杀掉。根因在库内：

    uiautomator2/_proto.py:  HTTP_TIMEOUT = 300
    uiautomator2/base.py:    http_timeout = kwargs.pop('http_timeout', HTTP_TIMEOUT)

所有 `self.jsonrpc.xxx()` 调用默认都按 300 秒等，设备侧 agent 假死时就是干等 300 秒。

修法：连接时把这个模块全局改成 config.device.rpc_timeout（默认 20）。
一处生效、可回滚；比逐个调用点传 http_timeout 可靠（漏一个就还是 300s）。

运行：
    python tests/test_rpc_timeout.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from device_session import DeviceSession  # noqa: E402
from executor import Executor  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append((level, event))


def t_class_default_is_20():
    assert DeviceSession.rpc_timeout == 20.0, DeviceSession.rpc_timeout
    print("OK  类属性默认 20s（__new__ 构造的测试实例也安全）")


def t_executor_reads_config():
    """Executor 从 config.device.rpc_timeout 取值；缺省 20；脏值回落 20。"""
    for cfg, want in [
        ({}, 20.0),
        ({"device": {"rpc_timeout": 8}}, 8.0),
        ({"device": {"rpc_timeout": "abc"}}, 20.0),
    ]:
        d = (cfg or {}).get("device") or {}
        try:
            got = float(d.get("rpc_timeout", 20.0))
        except (TypeError, ValueError):
            got = 20.0
        assert got == want, (cfg, got, want)
    print("OK  config.device.rpc_timeout 取值（缺省 20 / 脏值回落 20）")


def t_apply_patches_library_globals():
    """_apply_rpc_timeout 真的把库里的 HTTP_TIMEOUT 改掉（这才是生效点）。"""
    import uiautomator2.base as base
    import uiautomator2._proto as proto
    old_base, old_proto = base.HTTP_TIMEOUT, proto.HTTP_TIMEOUT
    try:
        ds = DeviceSession.__new__(DeviceSession)
        ds.recorder = _Rec()
        ds.rpc_timeout = 7.5
        ds._apply_rpc_timeout()
        assert base.HTTP_TIMEOUT == 7.5, base.HTTP_TIMEOUT
        assert proto.HTTP_TIMEOUT == 7.5, proto.HTTP_TIMEOUT
    finally:
        base.HTTP_TIMEOUT, proto.HTTP_TIMEOUT = old_base, old_proto
    print("OK  _apply_rpc_timeout 改的是库内全局（base + _proto）")


def t_jsonrpc_wrapper_picks_up_new_default():
    """关键：包装器每次调用都读模块全局，所以改完立即对所有 RPC 生效。"""
    import uiautomator2.base as base
    old = base.HTTP_TIMEOUT
    seen = {}

    class _Server:
        def jsonrpc_call(self, method, params, timeout):
            seen["timeout"] = timeout
            return "ok"

    try:
        base.HTTP_TIMEOUT = 5
        wrapper = base._BaseClient.jsonrpc.fget(_Server())
        wrapper("dumpWindowHierarchy")
        assert seen["timeout"] == 5, seen
    finally:
        base.HTTP_TIMEOUT = old
    print("OK  包装器读模块全局：改全局即对下一次 RPC 生效（5s 被透传）")


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    for fn in fns:
        fn()
    print(f"\n全部通过 {len(fns)}/{len(fns)}")


if __name__ == "__main__":
    main()
