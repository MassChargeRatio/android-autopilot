# -*- coding: utf-8 -*-
"""adbkit.py - 路径无关的 adb 工具层

设计目标（针对本工程踩过的坑）：
  1. 不硬编码某台机器的 adb 路径：按 环境变量 -> PATH -> 常见安装位置 依次解析。
  2. 截图一律走 `exec-out screencap -p` 并由 python 直接读 stdout 写字节，
     避免 cmd/PowerShell 重定向导致的 PNG 截断（历史上出现过 62 字节坏图）。
  3. 每次调用前自动确保 `adb connect <addr>`，因为本机 adb server 在
     工具进程结束后可能被回收（表现为 "no devices/emulators found"）。
  4. 所有命令带超时，避免 shell 卡死。

用法：
    from adbkit import Adb
    adb = Adb()                      # 自动解析 adb + 默认设备
    adb.ensure()                     # 确保 daemon + 连接
    adb.screenshot("out.png")
    print(adb.foreground())
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time

# 常见 adb 位置（按优先级）。仅作为 PATH 之外的兜底，不做强绑定。
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CANDIDATE_PATHS = [
    # 项目自带（随仓库走，换机器不丢，最优先）
    os.path.join(_ROOT, "tools", "platform-tools", "adb.exe"),
    r"D:\Program Files\Netease\MuMu Player 12\shell\adb.exe",
    r"C:\Program Files\Netease\MuMu Player 12\shell\adb.exe",
    r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe",
    os.path.expanduser(r"~\platform-tools\adb.exe"),
    r"C:\platform-tools\adb.exe",
    r"D:\platform-tools\adb.exe",
    r"C:\Android\Sdk\platform-tools\adb.exe",
    r"D:\Android\Sdk\platform-tools\adb.exe",
]


def resolve_adb() -> str:
    """解析可用的 adb 可执行文件路径。"""
    env = os.environ.get("ADB_PATH") or os.environ.get("ADBUTILS_ADB_PATH")
    if env and os.path.exists(env):
        return env
    found = shutil.which("adb")
    if found:
        return found
    for p in _CANDIDATE_PATHS:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "未找到 adb。请安装 platform-tools 并加入 PATH，"
        "或设置环境变量 ADB_PATH 指向 adb.exe")


def default_serial(config_path: str | None = None) -> str | None:
    """从 config.yaml 的 device.serial 读取默认设备地址（零依赖解析）。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = config_path or os.path.join(root, "config.yaml")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    try:
        import yaml  # type: ignore
        cfg = yaml.safe_load(text) or {}
        val = (cfg.get("device") or {}).get("serial")
        return str(val) if val else None
    except Exception:
        pass
    m = re.search(r"^device:\s*$.*?^\s+serial:\s*(\S+)", text,
                  re.MULTILINE | re.DOTALL)
    return m.group(1).strip("'\"") if m else None


class AdbError(RuntimeError):
    pass


class Adb:
    def __init__(self, serial: str | None = None, adb_path: str | None = None,
                 default_timeout: float = 60.0):
        self.adb = adb_path or resolve_adb()
        # 未显式指定设备时，回退到 config.yaml 的 device.serial
        self.serial = serial or default_serial()
        self.default_timeout = default_timeout
        self._connected = False

    # ---------- 低层 ----------
    def run(self, args: list[str], timeout: float | None = None,
            binary: bool = False):
        cmd = [self.adb] + [str(a) for a in args]
        if self.serial and args and args[0] not in ("connect", "devices",
                                                    "start-server", "kill-server"):
            cmd = [self.adb, "-s", self.serial] + [str(a) for a in args]
        p = subprocess.run(cmd, capture_output=True,
                           timeout=timeout or self.default_timeout)
        if binary:
            return p
        out = p.stdout.decode("utf-8", "replace")
        err = p.stderr.decode("utf-8", "replace")
        return p.returncode, out, err

    def shell(self, cmd: str, timeout: float | None = None) -> str:
        rc, out, err = self.run(["shell", cmd], timeout=timeout)
        return out if out.strip() else err

    # ---------- 连接 ----------
    def devices(self) -> list[str]:
        rc, out, _ = self.run(["devices"], timeout=20)
        lines = [l.strip() for l in out.splitlines()[1:] if l.strip()]
        return [l.split()[0] for l in lines if "\tdevice" in l or " device" in l]

    def connect(self, addr: str | None = None) -> str:
        addr = addr or self.serial
        if not addr:
            raise AdbError("未指定设备地址（config.yaml device.serial 或 --serial）")
        rc, out, err = self.run(["connect", addr], timeout=30)
        msg = (out or err).strip()
        self.serial = addr
        if "connected" not in msg and "already" not in msg:
            raise AdbError(f"adb connect {addr} 失败: {msg}")
        self._connected = True
        return msg

    def ensure(self, addr: str | None = None, retries: int = 3) -> str:
        """确保 daemon 在跑且设备在线；返回设备地址。

        先做一次轻量探测（不重启 daemon），只有设备缺失时才 start-server/connect，
        避免每次截图都付一次 daemon 启动开销。
        """
        addr = addr or self.serial
        try:
            devs = self.devices()
            if devs and (not addr or addr in devs):
                self.serial = addr if addr else devs[0]
                return self.serial
        except Exception:
            pass
        for i in range(retries):
            try:
                self.run(["start-server"], timeout=30)
                if addr and addr not in self.devices():
                    self.connect(addr)
                devs = self.devices()
                if devs:
                    self.serial = addr if (addr and addr in devs) else devs[0]
                    return self.serial
            except Exception:
                pass
            time.sleep(1.5 * (i + 1))
        raise AdbError(f"设备不可用（addr={addr}）。请检查真机是否联网/休眠，"
                       "必要时重走 tcpip 5555 流程。")

    # ---------- 设备信息 ----------
    def screen_size(self) -> tuple[int, int]:
        out = self.shell("wm size")
        for line in out.splitlines():
            if ":" in line and "x" in line:
                wh = line.split(":")[-1].strip()
                w, h = wh.lower().split("x")
                return int(w), int(h)
        return (0, 0)

    def foreground(self) -> str:
        """当前前台包名（多级兜底）。"""
        for cmd, key in (
            ("dumpsys window", "mCurrentFocus"),
            ("dumpsys window", "mFocusedApp"),
            ("dumpsys activity activities", "topResumedActivity"),
            ("dumpsys activity activities", "mResumedActivity"),
        ):
            out = self.shell(cmd)
            for line in out.splitlines():
                if key in line and "/" in line:
                    frag = line.split(key)[-1]
                    frag = frag.strip().lstrip("=").strip()
                    # 形如 Window{xxx u0 com.pkg/com.pkg.Act}
                    for tok in frag.replace("{", " ").replace("}", " ").split():
                        if "/" in tok and "." in tok:
                            return tok.split("/")[0]
        return ""

    def is_screen_on(self) -> bool:
        out = self.shell("dumpsys power")
        if "mWakefulness=Awake" in out:
            return True
        if "mWakefulness=Asleep" in out or "mWakefulness=Dozing" in out:
            return False
        return "mScreenOn=true" in out or "state=ON" in out

    # ---------- 截图 ----------
    def screenshot_bytes(self, retries: int = 3) -> bytes:
        """取全屏 PNG 字节。

        坑位记录：本机 adb server 可能随工具进程退出被回收，表现为
        `exec-out screencap -p` 返回 0 字节。因此这里做三件事：
          1. 每次截图前 ensure() 一次（start-server + connect）；
          2. 失败重试；
          3. 全部失败后回退到「设备侧写文件 + pull」。
        """
        last_err = None
        for i in range(retries):
            try:
                self.ensure()
                p = self.run(["exec-out", "screencap", "-p"], timeout=90,
                             binary=True)
                data = p.stdout or b""
                if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 5000:
                    return data
                last_err = f"exec-out 返回 {len(data)} 字节"
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.0 + i)
        # 回退：设备侧写文件再 pull
        try:
            self.ensure()
            remote = "/sdcard/_autopilot_shot.png"
            self.shell(f"screencap -p {remote}")
            import tempfile
            tmp = os.path.join(tempfile.gettempdir(), "_autopilot_shot.png")
            if os.path.exists(tmp):
                os.remove(tmp)
            self.run(["pull", remote, tmp], timeout=90)
            with open(tmp, "rb") as f:
                data = f.read()
            if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 5000:
                return data
            last_err = f"pull 回退得到 {len(data)} 字节"
        except Exception as e:
            last_err = f"pull 回退失败: {type(e).__name__}: {e}"
        raise AdbError(
            f"截图失败（{last_err}）。常见原因：USB 直连断流 —— 改用无线 adb；"
            "或真机息屏/断网，需 adb connect 重连。")

    def screenshot(self, path: str) -> str:
        data = self.screenshot_bytes()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    # ---------- UI ----------
    def dump_hierarchy(self, path: str | None = None) -> str:
        """导出 UI 层级 XML。优先 exec-out（无需设备临时文件）。"""
        p = self.run(["exec-out", "uiautomator", "dump", "/dev/tty"],
                     timeout=90, binary=True)
        xml = (p.stdout or b"").decode("utf-8", "replace")
        if "<?xml" not in xml:
            # 兜底：写设备文件再 pull
            self.shell("uiautomator dump /sdcard/window_dump.xml")
            p2 = self.run(["exec-out", "cat", "/sdcard/window_dump.xml"],
                          timeout=90, binary=True)
            xml = (p2.stdout or b"").decode("utf-8", "replace")
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(xml)
        return xml

    # ---------- 交互 ----------
    def tap(self, x: int, y: int):
        self.shell(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300):
        self.shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(ms)}")

    def keyevent(self, code: str | int):
        self.shell(f"input keyevent {code}")

    def start_app(self, package: str) -> str:
        """正确启动方式：先 resolve-activity 拿组件，再 am start -n。"""
        out = self.shell(f"cmd package resolve-activity --brief {package}")
        comp = ""
        for line in out.splitlines():
            line = line.strip()
            if "/" in line and "." in line:
                comp = line
        if not comp:
            return f"resolve-activity 未找到组件: {package}"
        return self.shell(f"am start -n {comp}")


if __name__ == "__main__":
    import json
    a = Adb()
    print("adb:", a.adb)
    info = {"adb": a.adb, "devices": a.devices()}
    try:
        a.ensure()
        info["serial"] = a.serial
        info["screen"] = a.screen_size()
        info["screen_on"] = a.is_screen_on()
        info["foreground"] = a.foreground()
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(info, ensure_ascii=False, indent=2))
