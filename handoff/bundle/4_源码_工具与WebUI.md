# 第 4 册：工具与 WebUI（只读）

> **这一册不要改。** 它是验收工具和可视化面板，改了就没法验证你的改动。
> 放在这里只是为了让对方能看到 `verify_live.py` / `stability_run.py` 的口径，以及 `webui/data.py::verify_coverage` 的判据。

## 1. 验收与标定工具（38 个）

### 本册清单：devtools/（39 个文件 / 8,798 行）

| # | 文件 | 行数 |
|---:|---|---:|
| 1 | `devtools/adbkit.py` | 303 |
| 2 | `devtools/apply_candidate_fixes.py` | 201 |
| 3 | `devtools/apply_nav_fixes.py` | 93 |
| 4 | `devtools/apply_sign_configs.py` | 621 |
| 5 | `devtools/calib_summary.py` | 110 |
| 6 | `devtools/calibrate.py` | 769 |
| 7 | `devtools/check_apps.py` | 66 |
| 8 | `devtools/check_secrets.py` | 142 |
| 9 | `devtools/compare_verify.py` | 123 |
| 10 | `devtools/e2e_vlm.py` | 75 |
| 11 | `devtools/g_scan.py` | 80 |
| 12 | `devtools/gh_api_push.py` | 291 |
| 13 | `devtools/nl_to_steps.py` | 508 |
| 14 | `devtools/patch_nav_vision.py` | 115 |
| 15 | `devtools/plan_anchor_fixes.py` | 368 |
| 16 | `devtools/preflight.py` | 172 |
| 17 | `devtools/probe_deep.py` | 365 |
| 18 | `devtools/probe_flow.py` | 94 |
| 19 | `devtools/probe_manual.py` | 263 |
| 20 | `devtools/probe_path.py` | 100 |
| 21 | `devtools/probe_path_u2.py` | 122 |
| 22 | `devtools/probe_sidebar.py` | 244 |
| 23 | `devtools/propose_anchors.py` | 162 |
| 24 | `devtools/record_flow.py` | 667 |
| 25 | `devtools/remove_prelude.py` | 166 |
| 26 | `devtools/run_sign_regression.py` | 147 |
| 27 | `devtools/shot.py` | 36 |
| 28 | `devtools/split_config.py` | 92 |
| 29 | `devtools/stability_run.py` | 213 |
| 30 | `devtools/to_any_of.py` | 307 |
| 31 | `devtools/verify_coverage.py` | 38 |
| 32 | `devtools/verify_live.py` | 731 |
| 33 | `devtools/vlm_bench.py` | 94 |
| 34 | `devtools/vlm_probe.py` | 109 |
| 35 | `devtools/vlm_templates.py` | 136 |
| 36 | `devtools/vocab_report.py` | 68 |
| 37 | `devtools/watch_dispatch_feat.py` | 75 |
| 38 | `devtools/watch_dispatch_queue.py` | 126 |
| 39 | `devtools/yaml_writer.py` | 406 |


---

## 2. WebUI（5 个）

### 本册清单：webui/（5 个文件 / 1,945 行）

| # | 文件 | 行数 |
|---:|---|---:|
| 1 | `webui/__init__.py` | 16 |
| 2 | `webui/data.py` | 757 |
| 3 | `webui/jobs.py` | 420 |
| 4 | `webui/routes_yaml.py` | 307 |
| 5 | `webui/server.py` | 445 |


---

### `devtools/adbkit.py`（303 行）

```python
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
```

### `devtools/apply_candidate_fixes.py`（201 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「已验证的候选锚点」写回 config.yaml（行级编辑，保留原有排版与注释）。

数据来源：devtools/calib/<app>/ui.xml | ui_after.xml 中真实存在的节点。
每条修复 = (app, behavior, label)；label 是在 dump 里实测到的完整文案，
以 textContains 语义写入 candidates 列表首位（最高置信度优先尝试）。

用法：
    python devtools/apply_candidate_fixes.py            # 预览（不写盘）
    python devtools/apply_candidate_fixes.py --apply    # 写回（自动备份）
"""
import argparse
import os
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")

# (app, behavior, 实测文案)  —— 顺序与 FIX_PLAN.md 的 candidate 项一致
FIXES = [
    ("一淘",           "watch",   "去福狸中心做任务"),
    ("今日头条极速版", "bonus",   "完成挑战得奖励"),
    ("喜番免费短剧",   "watch",   "去看剧"),
    ("微博移动版",     "bonus",   "点击领取"),
    ("悟空浏览器",     "watch",   "看剧"),
    ("抖音火山版",     "watch",   "点击赚钱"),
    ("星图金融",       "collect", "迎新福利"),
    ("梧桐免费小说",   "watch",   "福利商城"),
    ("河马剧场",       "watch",   "福利"),
    ("火龙漫剧",       "watch",   "福利"),
    ("点淘",           "collect", "待领取"),
    ("红果免费短剧",   "collect", "去领取"),
]

CAND_TPL = [
    "      - type: text",
    "        value: {v}",
]


def find_app_block(lines, app_name):
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- name: {app_name}":
            start = i
            break
    if start is None:
        # 拆分后 App 级文件：整文件即一个 App 块（首行 `name: xxx`）
        if lines and lines[0].strip() == f"name: {app_name}":
            start = 0
        else:
            return None, None
        end = len(lines)
        return start, end
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- name: "):
            end = j
            break
    return start, end


def behavior_indent(lines, start, end):
    """返回 behaviors 子键（行为名）的缩进空格数：拆分后 App 文件=2，旧单文件=4。"""
    for k in range(start, end):
        s = lines[k].rstrip()
        if s.endswith(":") and s.strip() == "behaviors":
            return len(s) - len(s.lstrip()) + 2
    return 4


def find_behavior(lines, start, end, behavior, indent=4):
    """返回 behavior 名字所在行号。"""
    for k in range(start, end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) \
                and s.rstrip().endswith(":") and s.strip().rstrip(":") == behavior:
            return k
    return None


def behavior_span(lines, bstart, app_end, indent=4):
    """behavior 块的结束行（下一个行为名 / app 结束）。"""
    for k in range(bstart + 1, app_end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) and s.rstrip().endswith(":"):
            return k
    return app_end


def apply_one(lines, app, behavior, value):
    s, e = find_app_block(lines, app)
    if s is None:
        return None, f"未找到 app 块: {app}"
    ind = behavior_indent(lines, s, e)
    b = find_behavior(lines, s, e, behavior, ind)
    if b is None:
        return None, f"未找到行为: {app}.{behavior}"
    bend = behavior_span(lines, b, e, ind)
    # 在该行为块里找第一个 click_first 的 candidates:
    ci = None
    for k in range(b + 1, bend):
        if lines[k].strip() == "- type: click_first":
            for m in range(k + 1, bend):
                if lines[m].strip() == "candidates:":
                    ci = m
                    break
                if lines[m].startswith("      - type:") or lines[m].strip().startswith("- type:"):
                    break
            if ci is not None:
                break
    if ci is None:
        return None, f"{app}.{behavior} 首个 click_first 未找到 candidates:"
    # 去重：若已存在同值候选则跳过
    for k in range(ci + 1, bend):
        if lines[k].strip().startswith("value:") and lines[k].split("value:", 1)[1].strip() == value:
            return None, f"{app}.{behavior} 已存在候选 {value!r}，跳过"
    ins = [tpl.format(v=value) for tpl in CAND_TPL]
    lines[ci + 1:ci + 1] = ins
    return ci, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写回 config.yaml")
    args = ap.parse_args()

    # 按 App 分组，逐 App 文件行级编辑（拆分后每 App 一个文件）
    by_app = {}
    for app, behavior, value in FIXES:
        by_app.setdefault(app, []).append((behavior, value))

    ok, skip, fail = [], [], []
    # 先做一次干跑收集行号，再倒序插入；任一失败则整体不写盘
    results = []
    for app, items in by_app.items():
        path = app_config_path(app)
        if not os.path.exists(path):
            fail.append(f"未找到 app 配置文件: {app} ({path})")
            continue
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")
        work = list(lines)
        local_ok = []
        for behavior, value in items:
            pos, err = apply_one(work, app, behavior, value)
            if err:
                (skip if "已存在" in err else fail).append(err)
            else:
                local_ok.append(f"{app}.{behavior} <- {value!r}")
        ok.extend(local_ok)
        if local_ok:
            results.append((app, path, work))

    if fail:
        print("!! 有失败项，未写盘：")
        for x in fail:
            print("   ", x)
        return 1

    print(f"计划插入 {len(ok)} 处候选锚点：")
    for x in ok:
        print("   ", x)
    for x in skip:
        print("  [跳过]", x)

    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    for app, path, work in results:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{path}.bak-cand-{ts}"
        shutil.copy2(path, bak)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(work))
        print(f"已写回 {path}")
        print(f"备份: {bak}")

    # 复验
    try:
        cfg = load_config(CONFIG)
        print(f"复验: config 加载成功, {len(cfg['apps'])} 个 app")
    except Exception as ex:  # noqa
        print(f"复验失败: {ex}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/apply_nav_fixes.py`（93 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""根据实机探路结果（LIVE_PROBE_NAV.json）自动补导航前置步。

链路：verify_live.py --probe-nav 会对**所有**未命中项试一次「导航到我的」，
       命中则状态为 `导航可救(建议加前置步)`。
       本脚本把这类行为的前置步写回 config.yaml（幂等，自动备份）。

用法：
    python devtools/apply_nav_fixes.py                       # 预览
    python devtools/apply_nav_fixes.py --apply               # 写回
    python devtools/apply_nav_fixes.py --json <path> --apply
"""
import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402
from plan_anchor_fixes import apply_prelude, NAV_ACTION  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")
DEFAULT_JSON = os.path.join(HERE, "calib", "LIVE_PROBE_NAV.json")

FIXABLE = "导航可救(建议加前置步)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.json):
        print(f"找不到探路结果: {args.json}")
        return 1
    data = json.load(open(args.json, encoding="utf-8"))
    report = data.get("report", data)

    plan = {}
    for app, rows in report.items():
        for r in rows:
            if r.get("status") == FIXABLE:
                plan.setdefault(app, []).append(r["behavior"])

    if not plan:
        print("没有可补前置步的项（探路结果为 0）")
        return 0

    total = sum(len(v) for v in plan.values())
    print(f"计划补前置步 {total} 处：")
    for app, bs in plan.items():
        print(f"  {app}: {', '.join(bs)}")

    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    bak = f"{CONFIG}.bak-nav-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(CONFIG, bak)
    print(f"已备份: {bak}")
    inserted = 0
    for app, bs in plan.items():
        path = app_config_path(app)
        if not os.path.exists(path):
            print(f"  !! 未找到 app 配置文件: {app} ({path})")
            continue
        bak_app = f"{path}.bak-nav-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak_app)
        n = apply_prelude(path, app, set(bs))
        print(f"  {app}: 插入 {n} 处（{len(bs)} 个行为中 {len(bs) - n} 个已有前置步）")
        inserted += n
    print(f"共插入 {inserted} 处")
    try:
        cfg = load_config(CONFIG)
        print(f"复验: config 加载成功, {len(cfg['apps'])} 个 app")
    except Exception as ex:
        print(f"复验失败: {ex}，回滚")
        shutil.copy2(bak, CONFIG)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/apply_sign_configs.py`（621 行）

```python
# -*- coding: utf-8 -*-
"""apply_sign_configs.py - 把用户 2026-10-20 人工勘察的 12 App 签到路径写入 sign 配置

替换既有 sign 段（京东/美团为新增插入 behaviors 顶部）。全部用现有 step 原语：
any_of / click_first / click_point / scroll_to / back / think。
坐标一律 0-1 归一化并注释「待真机校准」。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(ROOT, "config", "apps")

# ---------------- 12 份 sign 配置块 ----------------

S_QUKANTOUTIAO = """  sign:
  # 【用户人工描述 2026-10-20】需关好几个弹窗才进正式界面；底部5按钮右下=我的、右二=任务；任务界面中部最左=今日签到
  # 多轮弹窗清扫（F1 dismiss_popups 上线后由全局清扫接管，此处为过渡手写版）
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 暂不
        - type: text
          value: 关闭
        - type: text
          value: 以后再说
        - type: text
          value: 稍后再说
        - type: text
          value: 我知道了
        - type: text
          value: 知道了
        - type: text
          value: 不再提醒
        - type: text
          value: 取消
        timeout: 3
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 暂不
        - type: text
          value: 关闭
        - type: text
          value: 以后再说
        - type: text
          value: 我知道了
        - type: text
          value: 知道了
        timeout: 3
  # 底部右二 tab「任务」
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 任务
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.7
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部右二tab「任务」坐标兜底（待真机校准）
  - type: think
  # 任务界面中部最左「今日签到」
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 今日签到
        - type: text
          value: 立即签到
        - type: text
          value: 签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.16
        y: 0.45
        timeout: 8
        optional: false
        vision: false
        desc: 任务界面中部最左「今日签到」坐标兜底（待真机校准）
"""

S_PINDUODUO = """  sign:
  # 【用户人工描述 2026-10-20】左下数第2 tab=多多视频；其上部最右边缘圆形=签到/提现共用入口；入口任务列表没有签到就滑动；入口上部右侧=提现（暂略）
  # 注意：签到入口禁止截图 → 只用文案+归一化坐标，不用图像模板
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 多多视频
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.3
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部左二tab「多多视频」坐标兜底（待真机校准）
  - type: think
  # 上部最右侧边沿圆形共用入口（禁截图→坐标）
  - type: click_point
    x: 0.93
    y: 0.12
    timeout: 6
    optional: true
    vision: false
    desc: 多多视频页右上缘圆形共用入口（待真机校准）
  # 入口任务列表：没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_JINGDONG = """  sign:
  # 【用户人工描述 2026-10-20】左下数第2 tab=逛；右上缘圆形=签到/提现共用入口；入口中部=连续签到/去提现
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 逛
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.3
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部左二tab「逛」坐标兜底（待真机校准）
  - type: think
  - type: click_point
    x: 0.93
    y: 0.12
    timeout: 6
    optional: true
    vision: false
    desc: 逛页面右上缘圆形共用入口（待真机校准）
  - type: click_first
    candidates:
    - type: text
      value: 连续签到
    - type: text
      value: 今日签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_MEITUAN = """  sign:
  # 【用户人工描述 2026-10-20】左下数第2 tab=视频；右上缘圆形=共用入口；入口上部=今日签到/提现（提现限8-20点，提现组暂略）
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 视频
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.3
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部左二tab「视频」坐标兜底（待真机校准）
  - type: think
  - type: click_point
    x: 0.93
    y: 0.12
    timeout: 6
    optional: true
    vision: false
    desc: 视频页右上缘圆形共用入口（待真机校准）
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_KUAISHOU = """  sign:
  # 【用户人工描述 2026-10-20】首页左上角☰侧边栏→上部任务中心→签到，没有就滑动
  - type: click_point
    x: 0.07
    y: 0.06
    timeout: 6
    optional: true
    vision: false
    desc: 首页左上角☰侧边栏（待真机校准）
  - type: think
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 任务中心
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.18
        timeout: 8
        optional: false
        vision: false
        desc: 侧边栏上部「任务中心」坐标兜底（待真机校准）
  - type: think
  # 任务中没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_BAIDUMAP = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮左下=首页右下=我的；首页中部偏下（或上部）「现金签到」
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 暂不
        - type: text
          value: 关闭
        - type: text
          value: 以后再说
        - type: text
          value: 我知道了
        timeout: 3
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 现金签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.45
        timeout: 8
        optional: false
        vision: false
        desc: 首页中部「现金签到」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 直接领取
    - type: text
      value: 立即签到
    - type: text
      value: 领取
    timeout: 6
    optional: true
"""

S_HAIMA = """  sign:
  # 【用户人工描述 2026-10-20】底部4文本右下=我的、右二=领现金；签到在领现金任务里，没有就滑动
  # 启动弹窗里可能出现签到按钮（旧版 open 弹窗），顺手先试
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 立即签到
        - type: text
          value: 签到领金币
        - type: text
          value: 关闭
        - type: text
          value: 暂不
        timeout: 4
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 领现金
        - type: text
          value: 我的
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.7
        y: 0.97
        timeout: 8
        optional: false
        vision: false
        desc: 底部右二tab「领现金」坐标兜底（待真机校准）
  - type: think
  # 领现金任务里没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    - type: text
      value: 签到领金币
    timeout: 8
    optional: true
"""

S_UC = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮右下=任务；签到领元宝在任务界面里，没有就滑动
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 任务
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.9
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部右下tab「任务」坐标兜底（待真机校准）
  - type: think
  # 任务界面里没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 签到领元宝
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_FEIZHU = """  sign:
  # 【用户人工描述 2026-10-20】能量红包和里程签到都要自动化，都在首页中部
  # 第一目标：能量红包
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 能量红包
        - type: desc
          value: 能量红包
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.42
        timeout: 8
        optional: false
        vision: false
        desc: 首页中部「能量红包」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即领取
    - type: text
      value: 领取
    - type: text
      value: 签到
    timeout: 6
    optional: true
  - type: back
  - type: think
  # 第二目标：里程签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 里程签到
        - type: desc
          value: 里程签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.55
        timeout: 8
        optional: false
        vision: false
        desc: 首页中部「里程签到」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 6
    optional: true
"""

S_MIDUXIAOSHUO = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮右下=任务；我的中部=福利中心；福利中心上部=立即签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 福利中心
        timeout: 8
        optional: false
    - - type: click_first
        candidates:
        - type: text
          value: 我的
        timeout: 8
        optional: false
      - type: think
      - type: click_first
        candidates:
        - type: text
          value: 福利中心
        timeout: 8
        optional: false
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_MIDUJISU = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮右下=我的、右二=福利；福利上部=立即签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 福利
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.7
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部右二tab「福利」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_DIANPING = """  sign:
  # 【用户人工描述 2026-10-20】首页最右上=签到或得金币；进入后上部=立即签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 签到
        - type: text
          value: 得金币
        - type: desc
          value: 签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.88
        y: 0.08
        timeout: 8
        optional: false
        vision: false
        desc: 首页右上「签到」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

# 文件 -> (sign 块, 是否替换既有 sign 段；False=插入 behaviors 顶部)
JOBS = {
    "01_趣头条.yaml": (S_QUKANTOUTIAO, True),
    "02_拼多多.yaml": (S_PINDUODUO, True),
    "03_京东.yaml": (S_JINGDONG, False),
    "04_美团.yaml": (S_MEITUAN, False),
    "05_快手.yaml": (S_KUAISHOU, True),
    "06_百度地图.yaml": (S_BAIDUMAP, True),
    "07_海马畅听.yaml": (S_HAIMA, True),
    "08_UC浏览器极速版.yaml": (S_UC, True),
    "09_飞猪旅行.yaml": (S_FEIZHU, True),
    "10_米读小说.yaml": (S_MIDUXIAOSHUO, True),
    "11_米读极速版.yaml": (S_MIDUJISU, True),
    "13_大众点评.yaml": (S_DIANPING, True),
}

BOUNDARY = re.compile(r"^  ([A-Za-z]\S*?:)")


def splice_replace(txt, block):
    """替换已有 sign 段（从 '  sign:' 到下一个 behaviors 键或 EOF）。"""
    m = re.search(r"^  sign:\s*$", txt, re.M)
    if not m:
        return None
    lines = txt[m.start():].splitlines(keepends=True)
    end_rel = len(lines)
    for i in range(1, len(lines)):
        if BOUNDARY.match(lines[i]):
            end_rel = i
            break
    return txt[:m.start()] + block + txt[m.start():].split("\n", 0)[0] and \
        txt[:m.start()] + block + "".join(lines[end_rel:])


def splice_insert(txt, block):
    """behaviors: 之后插入新 sign 段。"""
    m = re.search(r"^behaviors:\s*$", txt, re.M)
    if not m:
        return None
    return txt[:m.start()] + "behaviors:\n" + block + txt[m.end():]


def main():
    import yaml
    for fname, (block, replace) in JOBS.items():
        path = os.path.join(APPS, fname)
        txt = open(path, encoding="utf-8").read()
        if replace:
            new = splice_replace(txt, block)
        else:
            new = splice_insert(txt, block)
        if new is None:
            print(f"!! {fname} 未找到锚点，跳过")
            sys.exit(1)
        # 校验 YAML 合法 + sign 在
        cfg = yaml.safe_load(new)
        assert cfg and "sign" in cfg.get("behaviors", {}), f"{fname} sign 缺失"
        assert isinstance(cfg["behaviors"]["sign"], list) and cfg["behaviors"]["sign"]
        open(path, "w", encoding="utf-8").write(new)
        print(f"OK {fname}: sign {len(cfg['behaviors']['sign'])} 步")
    print("ALL DONE")


if __name__ == "__main__":
    main()
```

### `devtools/calib_summary.py`（110 行）

```python
# -*- coding: utf-8 -*-
"""calib_summary.py - 汇总 devtools/calib/ 下所有校准报告

用法：
    python devtools/calib_summary.py            # 打印汇总表
    python devtools/calib_summary.py --out devtools/calib/SUMMARY.md
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(HERE, "calib"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = []
    for p in sorted(glob.glob(os.path.join(args.dir, "*", "report.json"))):
        try:
            with open(p, "r", encoding="utf-8") as f:
                rows.append(json.load(f))
        except Exception as e:
            print(f"跳过 {p}: {e}")

    if not rows:
        print(f"{args.dir} 下没有找到 report.json，请先跑 devtools/calibrate.py")
        return 1

    rows.sort(key=lambda r: (r.get("entry_total", 0)
                             and r.get("entry_hit", 0) / r.get("entry_total", 1),
                             r.get("app", "")))

    md = ["# 18 个新 App 校准汇总", "",
          "> 入口命中率 = 每个行为**首个锚点动作**是否在 App 落地页命中。",
          "> 二级页命中率 = 用 VLM 点进底栏「我的」后再校验同一批入口。",
          "> 后续步骤依赖跳转后的页面，静态 dump 无法校验，需实跑。", "",
          "| App | 包名 | 首屏入口 | 二级页入口 | 落地页节点 | 前台包名 | 备注 |",
          "|---|---|---|---|---|---|---|"]
    th = tt = ah = at = 0
    problems = []
    for r in rows:
        h, t = r.get("entry_hit", 0), r.get("entry_total", 0)
        th += h
        tt += t
        aft = r.get("after") or {}
        a_h, a_t = aft.get("entry_hit", 0), aft.get("entry_total", 0)
        ah += a_h
        at += a_t
        note = ""
        fg = r.get("foreground") or ""
        if fg and fg != r.get("package"):
            note = f"⚠ 前台是 {fg}"
            problems.append(f"{r['app']}: 落地时前台为 {fg}（非目标包名，"
                            f"可能被登录页/弹窗/广告占据）")
        if t == 0:
            note = (note + " 无锚点类动作").strip()
        md.append(f"| {r['app']} | `{r['package']}` | {h}/{t} | "
                  f"{a_h}/{a_t} | {r.get('nodes', 0)} | `{fg}` | {note} |")
    md += ["", f"**首屏入口命中率合计: {th}/{tt} = "
              f"{(th / tt * 100 if tt else 0):.0f}%**  ",
           f"**二级页入口命中率合计: {ah}/{at} = "
           f"{(ah / at * 100 if at else 0):.0f}%**", ""]

    if problems:
        md += ["## 需要人工确认", ""] + [f"- {x}" for x in problems] + [""]

    md += ["## 各 App 入口明细（首屏 / 二级页）", ""]
    for r in rows:
        md.append(f"### {r['app']}  (`{r['package']}`)")
        md.append("")
        md.append("首屏：")
        for k, v in (r.get("entry_detail") or {}).items():
            mark = "✅" if v.get("status") == "命中" else "❌"
            md.append(f"- {mark} `{k}` [{v.get('type')}] {v.get('detail')}")
        aft = r.get("after") or {}
        if aft:
            md.append("")
            md.append(f"二级页（点击『{aft.get('prompt')}』-> {aft.get('click')}，"
                      f"节点 {aft.get('nodes')}）：")
            for k, v in (aft.get("entry_detail") or {}).items():
                mark = "✅" if v.get("status") == "命中" else "❌"
                md.append(f"- {mark} `{k}` [{v.get('type')}] {v.get('detail')}")
            if aft.get("candidate_anchors"):
                md.append("")
                md.append("二级页可用锚点：")
                for a in aft["candidate_anchors"][:12]:
                    if a.get("kw"):
                        md.append(f"  - `{a['label']}` @{a['center']} "
                                  f"kw={','.join(a['kw'])}")
        md.append("")

    text = "\n".join(md)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"已写出: {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/calibrate.py`（769 行）

```python
# -*- coding: utf-8 -*-
"""calibrate.py - 单 App 实跑校准

做什么：
  1. 启动目标 App，等开屏/广告自然结束（不按 BACK，按交接文档坑5）；
  2. 尝试点掉常见弹窗（青少年模式/隐私政策/更新提示等）；
  3. dump UI 层级 + 截图，落盘到 devtools/calib/<app>/；
  4. 用**工程真实的选择器语义**逐条校验 config.yaml 里该 App 的每个行为动作能否命中；
  5. 抽取页面上的"候选锚点"（签到/提现/金币/看视频/我的…）及其坐标，供补配置用。

用法：
    python devtools/calibrate.py --app 红果免费短剧
    python devtools/calibrate.py --apps 星图金融,微博移动版,一淘
    python devtools/calibrate.py --app 抖音 --wait 25 --no-launch   # 只 dump 当前画面
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from config_loader import load_config  # noqa: E402

ADB_PATH = None
try:
    from adbkit import resolve_adb
    ADB_PATH = resolve_adb()
    os.environ.setdefault("ADBUTILS_ADB_PATH", ADB_PATH)
except Exception:
    pass

CALIB_DIR = os.path.join(HERE, "calib")

# 常见拦截弹窗的按钮文案（按顺序尝试点击）
POPUP_TEXTS = ["同意并继续", "同意", "我知道了", "知道了", "我已知晓", "继续",
               "以后再说", "暂不", "暂不开启", "稍后再说", "跳过", "关闭",
               "取消", "不再提醒", "允许", "仅在使用中允许", "始终允许"]

# 抽取候选锚点用的兴趣关键词
INTEREST_KEYWORDS = [
    "签到", "每日签到", "立即签到", "打卡", "提现", "立即提现", "去提现",
    "领", "领取", "领取奖励", "领金币", "领红包", "金币", "元", "现金",
    "看视频", "看广告", "看剧", "去完成", "去逛逛", "任务", "福利", "红包",
    "我的", "赚钱", "开宝箱", "抽奖", "转盘", "新人",
]

BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def safe_name(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]", "_", name)


def load_apps(config_path):
    return load_config(config_path)


def parse_nodes(xml_text, drop_statusbar=True):
    """解析 UI dump，返回节点列表（含 text/desc/rid/clickable/center）。

    drop_statusbar：丢弃状态栏区域（y 底部 < 120）的节点。
    否则系统通知文案（"XX通知：现金提现倒计时"）会污染候选锚点列表，
    造成"提现/签到 锚点已存在"的假象。
    """
    nodes = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return nodes
    for el in root.iter("node"):
        a = el.attrib
        m = BOUNDS_RE.match(a.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = (int(v) for v in m.groups())
        if drop_statusbar and y2 < 120:
            continue
        nodes.append({
            "text": a.get("text", "") or "",
            "desc": a.get("content-desc", "") or "",
            "rid": a.get("resource-id", "") or "",
            "cls": a.get("class", "") or "",
            "clickable": a.get("clickable", "") == "true",
            "bounds": (x1, y1, x2, y2),
            "center": ((x1 + x2) // 2, (y1 + y2) // 2),
            "size": (x2 - x1, y2 - y1),
        })
    return nodes


PKG_ATTR_RE = re.compile(r'package="([^"]+)"')
# 系统 UI 包不算"页面属于谁"的依据
SYS_PKGS = {"com.android.systemui", "com.vivo.upslide", "android",
            "com.android.launcher3", "com.bbk.launcher2"}


def package_profile(xml_text):
    """统计 dump 里各 package 出现的节点数，排除系统 UI。返回 {pkg: count}。"""
    from collections import Counter
    c = Counter(m for m in PKG_ATTR_RE.findall(xml_text or "")
                if m not in SYS_PKGS)
    return dict(c)


def dominant_package(xml_text):
    """返回 dump 里出现次数最多的 App 包名（即"屏幕上实际是谁"）。

    用途：跨 App 污染检测。目标 App 启动失败/崩溃时，前台会停留在上一个 App，
    两个 App 会得到完全相同的坐标（看似合理、实为垃圾数据）。
    uiautomator2 的 currentPackageName 在这种时序下可能已报新包名，
    所以必须从 dump 本身判断。
    """
    prof = package_profile(xml_text)
    return max(prof, key=prof.get) if prof else ""


def page_belongs_to(xml_text, pkg, ratio=0.5):
    """判断 dump 出来的页面是否确实属于 pkg。

    允许目标包不是"唯一"的（WebView 内嵌、系统控件），
    只要目标包出现、且其节点数不低于主导包的 ratio 倍即可。
    返回 (是否属于, 主导包名, 目标包节点数, 主导包节点数)
    """
    prof = package_profile(xml_text)
    if not prof:
        return False, "", 0, 0
    dom = max(prof, key=prof.get)
    mine = prof.get(pkg, 0)
    dom_n = prof[dom]
    if dom == pkg:
        return True, dom, mine, dom_n
    return (mine > 0 and mine >= dom_n * ratio), dom, mine, dom_n


def match_selector(nodes, kind, value):
    """按工程语义匹配：text=textContains / id=resourceId(精确) / desc=descContains"""
    hits = []
    for n in nodes:
        if kind == "text" and value and value in n["text"]:
            hits.append(n)
        elif kind == "id" and value and value == n["rid"]:
            hits.append(n)
        elif kind == "desc" and value and value in n["desc"]:
            hits.append(n)
    return hits


def parse_sel(sel):
    sel = str(sel)
    if "=" in sel:
        k, _, v = sel.partition("=")
        if k.strip().lower() in ("text", "id", "desc"):
            return k.strip().lower(), v.strip()
    return "text", sel


def check_actions(app_cfg, nodes):
    """逐行为/逐动作校验，返回 [(behavior, idx, action, status, detail)]"""
    out = []
    behaviors = app_cfg.get("behaviors") or {}
    for bid, actions in behaviors.items():
        if not actions:
            continue
        # 行为支持「多候选模板」[[..],[..]]
        variants = actions if all(isinstance(a, list) for a in actions) else [actions]
        for vi, variant in enumerate(variants):
            for i, act in enumerate(variant or []):
                if not isinstance(act, dict):
                    continue
                t = act.get("type")
                if t == "click_text":
                    hits = match_selector(nodes, "text", act.get("text", ""))
                    out.append((bid, vi, i, act, "命中" if hits else "未命中",
                                f"text={act.get('text')!r} "
                                f"候选数={len(hits)}" +
                                (f" 首个坐标={hits[0]['center']}" if hits else "")))
                elif t == "click_id":
                    hits = match_selector(nodes, "id", act.get("res_id", ""))
                    out.append((bid, vi, i, act, "命中" if hits else "未命中",
                                f"id={act.get('res_id')!r} 候选数={len(hits)}"))
                elif t == "click_desc":
                    hits = match_selector(nodes, "desc", act.get("desc", ""))
                    out.append((bid, vi, i, act, "命中" if hits else "未命中",
                                f"desc={act.get('desc')!r} 候选数={len(hits)}"))
                elif t == "click_first":
                    cands = act.get("candidates") or []
                    found = None
                    for c in cands:
                        if not isinstance(c, dict):
                            continue
                        hits = match_selector(nodes, c.get("type", "text"),
                                              c.get("value", ""))
                        if hits:
                            found = (c, hits[0])
                            break
                    out.append((bid, vi, i, act, "命中" if found else "未命中",
                                f"candidates={[c.get('value') for c in cands if isinstance(c, dict)]} "
                                + (f"-> {found[0].get('value')!r} @{found[1]['center']}"
                                   if found else "")))
                elif t == "any_of":
                    # 条件分支：任一分支里的锚点命中即算命中
                    choices = act.get("choices") or []
                    found = None
                    tried = []
                    for ci, ch in enumerate(choices):
                        steps = ch if isinstance(ch, list) else [ch]
                        for a in steps:
                            if not isinstance(a, dict):
                                continue
                            at = a.get("type")
                            if at == "click_first":
                                for c in a.get("candidates") or []:
                                    if not isinstance(c, dict):
                                        continue
                                    hits = match_selector(
                                        nodes, c.get("type", "text"),
                                        c.get("value", ""))
                                    tried.append(c.get("value"))
                                    if hits:
                                        found = (f"分支#{ci + 1}", c.get("value"),
                                                 hits[0])
                                        break
                            elif at == "click_text":
                                hits = match_selector(nodes, "text",
                                                      a.get("text", ""))
                                tried.append(a.get("text"))
                                if hits:
                                    found = (f"分支#{ci + 1}", a.get("text"),
                                             hits[0])
                            elif at == "click_id":
                                hits = match_selector(nodes, "id",
                                                      a.get("res_id", ""))
                                tried.append(a.get("res_id"))
                                if hits:
                                    found = (f"分支#{ci + 1}", a.get("res_id"),
                                             hits[0])
                            elif at == "click_desc":
                                hits = match_selector(nodes, "desc",
                                                      a.get("desc", ""))
                                tried.append(a.get("desc"))
                                if hits:
                                    found = (f"分支#{ci + 1}", a.get("desc"),
                                             hits[0])
                            if found:
                                break
                        if found:
                            break
                    out.append((bid, vi, i, act, "命中" if found else "未命中",
                                f"any_of 分支数={len(choices)} 试过={tried} "
                                + (f"-> {found[0]} {found[1]!r} @{found[2]['center']}"
                                   if found else "")))
                elif t == "click_point":
                    imgs = act.get("images") or ([act["template"]]
                                                 if act.get("template") else [])
                    out.append((bid, vi, i, act, "图片模板",
                                f"需 OpenCV 模板匹配，图数={len(imgs)}: {imgs[:2]}"))
                elif t in ("wait", "think", "swipe", "swipe_natural", "back",
                           "home", "random", "ensure", "scroll_to"):
                    out.append((bid, vi, i, act, "无需锚点", t))
                elif t == "reward":
                    pat = act.get("pattern", "")
                    hit = re.search(pat, " ".join(n["text"] for n in nodes)) \
                        if pat else None
                    out.append((bid, vi, i, act, "命中" if hit else "未命中",
                                f"pattern={pat!r} 当前页文本"
                                + (f" -> {hit.group(0)!r}" if hit else "无匹配")))
                else:
                    out.append((bid, vi, i, act, "跳过", f"type={t}"))
    return out


def extract_anchors(nodes):
    """抽取页面上的候选锚点（可点击或带关键词的节点）。"""
    seen, out = set(), []
    for n in nodes:
        label = (n["text"] or n["desc"]).strip()
        if not label:
            continue
        hit_kw = [k for k in INTEREST_KEYWORDS if k in label]
        if not hit_kw and not n["clickable"]:
            continue
        key = (label, n["center"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "label": label[:40],
            "rid": n["rid"],
            "center": n["center"],
            "size": n["size"],
            "clickable": n["clickable"],
            "kw": hit_kw,
        })
    # 关键词命中的优先
    out.sort(key=lambda x: (len(x["kw"]) == 0, -len(x["kw"]), x["center"][1]))
    return out[:60]


def dismiss_popups(d, nodes, log):
    """按文案点掉常见弹窗；不按 BACK（交接文档坑5）。"""
    for txt in POPUP_TEXTS:
        for n in nodes:
            label = (n["text"] or n["desc"]).strip()
            if label == txt and n["clickable"]:
                log.append(f"点掉弹窗按钮: {txt} @{n['center']}")
                d.click(*n["center"])
                time.sleep(1.2)
                return True
    return False


def entry_hit_rate(checks):
    """入口命中率：每个行为**第一个带锚点的动作**是否命中。

    静态单次 dump 只能校验"落在落地页上的动作"，即各行为的入口步；
    后续步骤依赖前一步跳转后的页面，必须实跑才能校验。
    因此入口命中率才是本次校准的可信指标。
    """
    firsts = {}
    for c in checks:
        if c[4] not in ("命中", "未命中"):
            continue
        firsts.setdefault(c[0], c)
    total = len(firsts)
    hit = sum(1 for c in firsts.values() if c[4] == "命中")
    return hit, total, firsts


def wait_ready(d, pkg, max_wait, min_nodes, log, poll=3.0):
    """自适应等待 App 就绪。

    为什么不用固定 sleep：重型 App（抖音/头条系）冷启动常超过 18s，
    固定等待会 dump 到启动页（只有 15 个节点），校准结果全是"未命中"。
    这里轮询 dump，满足任一条件即认为就绪：
      - 节点数 >= min_nodes 且前台包名是目标包（或包含目标包）
      - dump 中出现任一兴趣关键词（说明内容页已渲染）
    上限 max_wait 秒。返回最终 (xml, nodes, 实际等待秒数)。
    """
    t0 = time.time()
    last_nodes, last_xml = [], ""
    while True:
        try:
            last_xml = d.dump_hierarchy()
            last_nodes = parse_nodes(last_xml)
            fg = ""
            try:
                fg = d.info.get("currentPackageName") or ""
            except Exception:
                pass
            text_blob = " ".join(n["text"] for n in last_nodes)
            kw_hit = any(k in text_blob for k in INTEREST_KEYWORDS)
            pkg_ok = (not pkg) or (fg == pkg) or (pkg in fg)
            elapsed = time.time() - t0
            if len(last_nodes) >= min_nodes and pkg_ok:
                log.append(f"就绪判定: 节点={len(last_nodes)} 前台={fg} "
                           f"耗时={elapsed:.1f}s（节点数达标）")
                return last_xml, last_nodes, elapsed
            if kw_hit and pkg_ok and len(last_nodes) >= 10:
                log.append(f"就绪判定: 节点={len(last_nodes)} 前台={fg} "
                           f"耗时={elapsed:.1f}s（命中兴趣关键词）")
                return last_xml, last_nodes, elapsed
        except Exception as e:
            log.append(f"等待中就绪探测异常: {type(e).__name__}: {e}")
        if time.time() - t0 >= max_wait:
            log.append(f"达到最大等待 {max_wait}s 仍未就绪，"
                       f"节点={len(last_nodes)}，按当前页继续")
            return last_xml, last_nodes, time.time() - t0
        time.sleep(poll)


def probe_after(d, prompt, wait, log, vision_cfg):
    """用 VLM 定位并点击一个入口，然后 dump 跳转后的页面。

    为什么需要：签到/提现这类入口几乎都在二级页（"我的"/"赚钱"），
    落地页 dump 里根本没有这些锚点，只校验落地页必然全"未命中"。
    这里用已校准好的 VLM 兜底（0~1000 归一化，实测误差 ~10px）点进去，
    再 dump 一页，才能拿到二级页的真实锚点。

    提示词回退：各 App 底栏标签写法不一（"我的"/"我"/"个人中心"），
    只用一个提示词会在部分 App 上全部未命中，故按顺序尝试多个写法。
    """
    try:
        import vision as vs
    except ImportError:
        log.append("probe: 无法导入 vision 模块，跳过探针")
        return None, [], None
    loc = vs.VisionLocator(vision_cfg or {}, base_dir=ROOT)
    if not loc.enabled or not loc.vlm_available:
        log.append("probe: VLM 未启用/不可用，跳过探针")
        return None, [], None

    prompts = [prompt,
               "定位屏幕底部导航栏最右侧的『我』标签中心",
               "定位屏幕底部导航栏的个人中心（我的）标签中心",
               "定位屏幕右下角的个人中心头像/图标中心"]
    hit = None
    used = None
    for p in prompts:
        try:
            img = d.screenshot()
        except Exception as e:
            log.append(f"probe: 截图失败 {e}")
            return None, [], None
        hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                   app="calibrate", tag="probe")
        if hit is not None:
            used = p
            break
        log.append(f"probe: 提示词未命中，尝试下一个 -> {p}")
    if hit is None:
        log.append("probe: 全部提示词均未命中")
        return None, [], None
    log.append(f"probe: VLM 命中『{used}』-> ({hit.x},{hit.y})，点击并等待 {wait}s")
    d.click(hit.x, hit.y)
    time.sleep(wait)
    xml = d.dump_hierarchy()
    return xml, parse_nodes(xml), (hit.x, hit.y)


def connect_device(serial, retries=3):
    """连接设备，带自愈重试 + 无线 adb 修复。

    本机环境特有坑1：每条独立 shell 命令结束后 adb daemon 会被回收，
    uiautomator2/adbutils 若正好连到"将死的" daemon，会抛
    ConnectionResetError(WinError 10054)。这里先用 adbkit 显式
    start-server + connect，失败则 kill-server 重来。

    本机环境特有坑2（2026-09 实机踩到）：uiautomator2 3.x 在无线 adb 上
    create_connection 隧道会挂起（d.info/dump 全部卡死），且 u2 服务
    不自启。修复：1) 建立本地 adb forward；2) 服务未就绪则用 setsid
    后台拉起（adb shell 退出后进程不被回收）；3) patch HTTP 连接层走
    本地 forward，绕开无线隧道挂起。
    """
    import socket
    import urllib.request
    import uiautomator2 as u2
    from uiautomator2 import core as u2core
    _U2_PORT = 9008

    def _ensure_forward():
        if not ADB_PATH:
            return False
        try:
            os.popen(f'"{ADB_PATH}" -s {serial} '
                     f'forward tcp:{_U2_PORT} tcp:{_U2_PORT}').read()
            return True
        except Exception:
            return False

    def _ping_local(port=_U2_PORT, timeout=3.0):
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/ping", timeout=timeout) as r:
                return r.status == 200 and b"pong" in r.read()
        except Exception:
            return False

    def _ensure_u2_service():
        # 服务未就绪则用 setsid 后台拉起（u2.jar 由 u2 库首次连接时推入）
        if not ADB_PATH:
            return
        if _ping_local():
            return
        cmd = ("setsid nohup sh -c 'CLASSPATH=/data/local/tmp/u2.jar "
               f"app_process / com.wetest.uia2.Main -p {_U2_PORT} "
               f">/data/local/tmp/u2srv{_U2_PORT}.log 2>&1' >/dev/null 2>&1 &")
        try:
            os.popen(f'"{ADB_PATH}" -s {serial} shell "{cmd}"').read()
        except Exception as e:
            print(f"  u2 服务拉起失败（{type(e).__name__}: {e}）")
        for _ in range(20):
            if _ping_local():
                return
            time.sleep(2)

    # 0) 无线 adb 修复：forward + 服务保障 + HTTP 层 patch
    _ensure_forward()
    _ensure_u2_service()

    def _patched_connect(self):
        # 走本地 adb forward，而不是设备 create_connection（无线隧道会挂起）
        self.sock = socket.create_connection(
            ("127.0.0.1", self._AdbHTTPConnection__port), timeout=20)
    u2core.AdbHTTPConnection.connect = _patched_connect

    last = None
    for i in range(retries):
        try:
            if ADB_PATH:
                os.environ["ADBUTILS_ADB_PATH"] = ADB_PATH
            try:
                from adbkit import Adb
                Adb(serial=serial, adb_path=ADB_PATH).ensure()
            except Exception as e:
                print(f"  adb 预连接失败（{type(e).__name__}: {e}），继续尝试 u2")
            d = u2.connect(serial, port=_U2_PORT)
            _ = d.info  # 触发一次真实通信，确认链路可用
            return d
        except Exception as e:
            last = e
            print(f"  连接失败（第 {i + 1}/{retries} 次）: "
                  f"{type(e).__name__}: {e}")
            try:
                from adbkit import Adb
                a = Adb(serial=serial, adb_path=ADB_PATH)
                a.run(["kill-server"], timeout=20)
                time.sleep(1.5)
                a.ensure()
            except Exception:
                pass
            time.sleep(2)
    raise RuntimeError(f"设备连接失败（已重试 {retries} 次）: {last}")


def calibrate(app_cfg, args, d):
    name = app_cfg.get("name") or "?"
    pkg = app_cfg.get("package") or ""
    outdir = os.path.join(CALIB_DIR, safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    log = []

    if not args.no_launch:
        d.press("home")
        time.sleep(1.5)
        try:
            d.app_start(pkg, stop=True)
            log.append(f"已启动 {name} ({pkg})")
        except Exception as e:
            log.append(f"启动失败: {type(e).__name__}: {e}")
        if args.fixed_wait:
            log.append(f"固定等待 {args.wait}s（不按 BACK）")
            time.sleep(args.wait)
            xml = nodes = None
        else:
            log.append(f"自适应等待就绪（上限 {args.max_wait}s，"
                       f"最小节点数 {args.min_nodes}；不按 BACK）")
            xml, nodes, waited = wait_ready(
                d, pkg, args.max_wait, args.min_nodes, log)

    # 弹窗处理最多 3 轮
    for rnd in range(3):
        xml = d.dump_hierarchy()
        nodes = parse_nodes(xml)
        if not dismiss_popups(d, nodes, log):
            break
        time.sleep(2)

    xml = d.dump_hierarchy()
    nodes = parse_nodes(xml)
    shot = os.path.join(outdir, "screen.png")
    try:
        d.screenshot(shot)
    except Exception as e:
        log.append(f"截图失败: {e}")
    with open(os.path.join(outdir, "ui.xml"), "w", encoding="utf-8") as f:
        f.write(xml)

    cur_pkg = ""
    try:
        cur_pkg = d.info.get("currentPackageName") or ""
    except Exception:
        pass
    # 归属判定以 dump 自身为准：崩溃/切换时序下 currentPackageName 会失真，
    # 会把「上一个 App 的页面」当成目标 App 的落地页，产出垃圾锚点。
    page_ok, dom_pkg, mine_n, dom_n = page_belongs_to(xml, pkg)
    if not page_ok:
        log.append(f"⚠ 页面归属校验失败: dump 主导包={dom_pkg}（{dom_n} 节点），"
                   f"目标包 {pkg} 仅 {mine_n} 节点，前台={cur_pkg or '?'}"
                   f" -> 本份 dump 判定为**污染**，锚点结论不可用")

    checks = check_actions(app_cfg, nodes)
    anchors = extract_anchors(nodes)
    e_hit, e_total, e_firsts = entry_hit_rate(checks)

    # ---- 可选：二级页探针 ----
    after = None
    if args.probe_vlm:
        axml, anodes, acoord = probe_after(
            d, args.probe_vlm, args.probe_wait, log, args.vision_cfg)
        if anodes:
            with open(os.path.join(outdir, "ui_after.xml"), "w",
                      encoding="utf-8") as f:
                f.write(axml)
            try:
                d.screenshot(os.path.join(outdir, "screen_after.png"))
            except Exception:
                pass
            a_checks = check_actions(app_cfg, anodes)
            a_anchors = extract_anchors(anodes)
            a_hit, a_total, a_firsts = entry_hit_rate(a_checks)
            after = {
                "prompt": args.probe_vlm, "click": acoord,
                "nodes": len(anodes),
                "entry_hit": a_hit, "entry_total": a_total,
                "entry_detail": {k: {"type": v[3].get("type"), "status": v[4],
                                     "detail": v[5]} for k, v in a_firsts.items()},
                "candidate_anchors": a_anchors,
            }
            log.append(f"二级页: 节点={len(anodes)} 入口命中={a_hit}/{a_total}")

    hits = sum(1 for c in checks if c[4] == "命中")
    anchor_req = [c for c in checks if c[4] in ("命中", "未命中")]
    summary = {
        "app": name, "package": pkg, "foreground": cur_pkg,
        "page_owner_ok": page_ok, "dominant_package": dom_pkg,
        "nodes": len(nodes), "anchors": len(anchors),
        "anchor_actions_total": len(anchor_req),
        "anchor_actions_hit": hits,
        "entry_hit": e_hit, "entry_total": e_total,
        "entry_detail": {k: {"type": v[3].get("type"), "status": v[4],
                             "detail": v[5]} for k, v in e_firsts.items()},
        "after": after,
        "log": log,
        "checks": [
            {"behavior": c[0], "variant": c[1], "step": c[2],
             "type": c[3].get("type"), "status": c[4], "detail": c[5]}
            for c in checks],
        "candidate_anchors": anchors,
    }
    with open(os.path.join(outdir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md = [f"# 校准报告 · {name}", "",
          f"- 包名: `{pkg}`",
          f"- 前台包名: `{cur_pkg or '未知'}`",
          f"- 页面归属: {'✅ 属于目标 App' if page_ok else '❌ **污染**'}"
          f"（dump 主导包 `{dom_pkg or '?'}`，目标包 {mine_n} 节点 / "
          f"主导包 {dom_n} 节点）",
          f"- UI 节点数: {len(nodes)}（已剔除状态栏通知）",
          f"- **入口命中率: {e_hit}/{e_total}**"
          f"（每个行为首个锚点动作是否在落地页命中）",
          f"- 全部锚点类动作命中: {hits}/{len(anchor_req)}"
          f"（后续步骤需跳转后页面，静态 dump 校验不了）", ""]
    if log:
        md += ["## 过程日志", ""] + [f"- {x}" for x in log] + [""]
    md += ["## 入口校验（关键）", "",
           "| 行为 | 类型 | 结果 | 详情 |", "|---|---|---|---|"]
    for k, v in e_firsts.items():
        md.append(f"| {k} | {v[3].get('type')} | {v[4]} | {v[5]} |")
    md += ["", "## 全部动作校验", "",
           "| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |",
           "|---|---|---|---|---|---|"]
    for c in checks:
        md.append(f"| {c[0]} | {c[1]+1} | {c[2]} | {c[3].get('type')} | "
                  f"{c[4]} | {c[5]} |")
    md += ["", "## 页面候选锚点（前 40）", "",
           "| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |",
           "|---|---|---|---|---|---|"]
    for a in anchors[:40]:
        md.append(f"| {a['label']} | `{a['rid'][:48]}` | {a['center']} | "
                  f"{a['size']} | {a['clickable']} | {','.join(a['kw'])} |")

    if after:
        md += ["", f"## 二级页（点击『{after['prompt']}』后）", "",
               f"- VLM 命中坐标: {after['click']}",
               f"- 节点数: {after['nodes']}",
               f"- **二级页入口命中: {after['entry_hit']}/{after['entry_total']}**",
               "", "| 行为 | 类型 | 结果 | 详情 |", "|---|---|---|---|"]
        for k, v in after["entry_detail"].items():
            md.append(f"| {k} | {v.get('type')} | {v.get('status')} | "
                      f"{v.get('detail')} |")
        md += ["", "| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |",
               "|---|---|---|---|---|"]
        for a in after["candidate_anchors"][:40]:
            md.append(f"| {a['label']} | `{a['rid'][:48]}` | {a['center']} | "
                      f"{a['clickable']} | {','.join(a['kw'])} |")

    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"[{name}] 前台={cur_pkg or '?'} 节点={len(nodes)} "
          + ("" if page_ok else f"[污染 主导={dom_pkg}] ")
          + f"入口命中={e_hit}/{e_total} 锚点动作命中={hits}/{len(anchor_req)}"
          + (f" 二级页命中={after['entry_hit']}/{after['entry_total']}"
             if after else "") + f" 报告={outdir}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=None)
    ap.add_argument("--apps", default=None, help="逗号分隔多个 App 名")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--serial", default=None)
    ap.add_argument("--wait", type=float, default=18.0,
                    help="固定等待秒数（配合 --fixed-wait 使用）")
    ap.add_argument("--fixed-wait", action="store_true",
                    help="改用固定等待而非自适应等待")
    ap.add_argument("--max-wait", type=float, default=70.0,
                    help="自适应等待上限秒数（默认 70s）")
    ap.add_argument("--min-nodes", type=int, default=40,
                    help="判定就绪的最小 UI 节点数（默认 40）")
    ap.add_argument("--probe-vlm", default=None,
                    help="二级页探针：用 VLM 定位并点击该描述的目标后，"
                         "再 dump 一页（如「定位底部导航栏最右侧的『我的』标签中心」）")
    ap.add_argument("--probe-wait", type=float, default=6.0,
                    help="探针点击后等待秒数（默认 6s）")
    ap.add_argument("--no-launch", action="store_true",
                    help="不启动 App，只 dump 当前画面")
    args = ap.parse_args()

    cfg = load_apps(args.config)
    apps = cfg.get("apps") or []
    serial = args.serial or (cfg.get("device") or {}).get("serial")
    args.vision_cfg = cfg.get("vision") or {}

    want = []
    if args.apps:
        want = [x.strip() for x in args.apps.split(",") if x.strip()]
    elif args.app:
        want = [args.app]
    if want:
        picked = []
        for w in want:
            for a in apps:
                if a.get("name") == w or w in (a.get("aliases") or []):
                    picked.append(a)
                    break
            else:
                print(f"!! 配置中找不到 App: {w}")
        apps = picked

    if not apps:
        print("没有要校准的 App")
        return 1

    import uiautomator2 as u2  # noqa: F401
    d = connect_device(serial)
    print(f"设备已连接: {d.info.get('displayWidth')}x"
          f"{d.info.get('displayHeight')}  待校准 {len(apps)} 个 App")

    results = []
    for i, a in enumerate(apps, 1):
        print(f"\n===== [{i}/{len(apps)}] {a.get('name')} =====")
        try:
            results.append(calibrate(a, args, d))
        except Exception as e:
            print(f"!! {a.get('name')} 校准异常: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("汇总（入口命中率 = 每个行为首个锚点动作是否在落地页命中）")
    print("=" * 60)
    tot_h = tot_t = bad = 0
    for r in results:
        tot_h += r["entry_hit"]
        tot_t += r["entry_total"]
        flag = ""
        if not r.get("page_owner_ok", True):
            bad += 1
            flag = f"  ❌污染(主导={r.get('dominant_package') or '?'})"
        print(f"  {r['app']:16} 入口 {r['entry_hit']:2}/{r['entry_total']:2}  "
              f"节点 {r['nodes']:5}  前台 {r['foreground'] or '?'}{flag}")
    if tot_t:
        print(f"\n  合计入口命中率: {tot_h}/{tot_t} = {tot_h / tot_t * 100:.0f}%")
    if bad:
        print(f"  ⚠ 其中 {bad} 个 App 的 dump 页面不属于目标 App，结论不可用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/check_apps.py`（66 行）

```python
# -*- coding: utf-8 -*-
"""check_apps.py - 核对 config.yaml 里的 app 是否真实安装在真机上

用法：
    python devtools/check_apps.py [--config config.yaml] [--json out.json]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from adbkit import Adb  # noqa: E402
from config_loader import load_config  # noqa: E402


def load_apps(path):
    cfg = load_config(path)
    return cfg.get("apps") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    apps = load_apps(args.config)
    a = Adb()
    a.ensure()
    out = a.shell("pm list packages")
    installed = set()
    for line in out.splitlines():
        m = re.match(r"package:(\S+)", line.strip())
        if m:
            installed.add(m.group(1))
    print(f"真机已安装第三方+系统包: {len(installed)} 个")
    print(f"config.yaml app 数: {len(apps)}\n")

    ok, missing = [], []
    for app in apps:
        pkg = app.get("package")
        (ok if pkg in installed else missing).append(app)

    print(f"=== 已安装 {len(ok)} ===")
    for app in ok:
        print(f"  ✓ {app.get('name')}  [{app.get('package')}]")
    print(f"\n=== 未安装 {len(missing)} ===")
    for app in missing:
        print(f"  ✗ {app.get('name')}  [{app.get('package')}]")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"installed": [x.get("package") for x in ok],
                       "missing": [x.get("package") for x in missing]},
                      f, ensure_ascii=False, indent=2)
        print(f"\n已写出: {args.json}")


if __name__ == "__main__":
    main()
```

### `devtools/check_secrets.py`（142 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_secrets.py - 提交前拦下明文密钥

背景（真实踩过）：本工程的 VLM API Key 曾经**硬编码在源码里** ——
`devtools/vlm_probe.py` 与 3 个 `handover/02_适配脚本/*.py` 各写了一份明文。
只要把工程推上 GitHub，Key 就跟着走了。这类东西靠「记得别提交」是守不住的，
必须有一条**自动化的**检查。

用法：
    python devtools/check_secrets.py              # 扫 git 暂存区（pre-commit 用）
    python devtools/check_secrets.py --tracked    # 扫全部已跟踪文件
    python devtools/check_secrets.py <文件...>    # 只扫指定文件
    python devtools/check_secrets.py --all        # 扫工作区全部文件（忽略 .gitignore）

退出码：0 = 干净；1 = 发现疑似密钥（会打印 file:line）。
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 疑似密钥的形态。宁可误报也别漏报 —— 误报只是多看一眼，漏报是不可逆的泄露。
PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
     "疑似 API Key（sk- 前缀）"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
     "私钥文件内容"),
    (re.compile(r"(?i)\b(?:api[_-]?key|apikey|access[_-]?key|secret|"
                r"passwd|password|auth[_-]?token)\b\s*[:=]\s*[\"']?"
                r"([A-Za-z0-9_\-+/]{20,})"),
     "赋值式密钥（字段名 + 长字面量）"),
]

# 命中行里出现这些词就放行：说明不是硬编码的真值。
ALLOW = re.compile(
    r"(?i)(environ|getenv|os\.environ|"
    r"example|placeholder|sample|dummy|fake|redacted|"
    r"your[_-]|change[_-]?me|xxx+|\*\*\*|<[^>]*>|\{\{?[^}]*\}?\})")

SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz",
            ".tar", ".db", ".pyc", ".woff", ".woff2", ".ttf", ".mp4", ".exe",
            ".dll", ".so", ".bin"}

MAX_BYTES = 2 * 1024 * 1024      # 单文件超过 2MB 不扫（几乎不会是源码）


def _git(*args):
    try:
        out = subprocess.run(["git", "-C", ROOT] + list(args),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def list_staged():
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [x for x in (out or "").splitlines() if x.strip()]


def list_tracked():
    out = _git("ls-files")
    return [x for x in (out or "").splitlines() if x.strip()]


def scan(path):
    """返回 [(行号, 说明, 命中片段), ...]。"""
    full = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.isfile(full):
        return []
    if os.path.splitext(full)[1].lower() in SKIP_EXT:
        return []
    try:
        if os.path.getsize(full) > MAX_BYTES:
            return []
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []

    hits = []
    for n, line in enumerate(lines, 1):
        if ALLOW.search(line):
            continue
        for rx, why in PATTERNS:
            m = rx.search(line)
            if m:
                got = m.group(0)
                # 命中片段也做遮蔽，避免把密钥又打印到 CI 日志里
                shown = got if len(got) <= 12 else got[:8] + "…（已遮蔽）"
                hits.append((n, why, shown))
                break
    return hits


def main():
    ap = argparse.ArgumentParser(description="提交前扫明文密钥")
    ap.add_argument("files", nargs="*", help="只扫这些文件")
    ap.add_argument("--staged", action="store_true",
                    help="扫 git 暂存区（默认行为）")
    ap.add_argument("--tracked", action="store_true", help="扫全部已跟踪文件")
    ap.add_argument("--all", action="store_true",
                    help="扫工作区全部文件（无视 .gitignore，含未跟踪）")
    args = ap.parse_args()

    if args.files:
        targets = args.files
    elif args.all:
        targets = []
        for base, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__", "node_modules")]
            targets += [os.path.relpath(os.path.join(base, n), ROOT)
                        for n in names]
    elif args.tracked:
        targets = list_tracked()
    else:
        targets = list_staged()

    bad = 0
    for p in targets:
        for n, why, shown in scan(p):
            print(f"  ✗ {p}:{n}  {why}  ->  {shown}")
            bad += 1

    if bad:
        print(f"\n发现 {bad} 处疑似明文密钥 —— 已阻止提交。")
        print("修法：改成从环境变量或 config.yaml 读，"
              "真实配置加进 .gitignore（参考 config.example.yaml）。")
        return 1
    print(f"OK  未发现明文密钥（扫描 {len(targets)} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/compare_verify.py`（123 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对比两次 verify_live.py 的结果，量化 any_of / 前置步改造的净效果。

用法：
    python devtools/compare_verify.py \
        --base devtools/calib/LIVE_VERIFY.json \
        --new  devtools/calib/LIVE_VERIFY_ANYOF.json

输出：
    - 总体命中率变化（首屏命中 + 导航后命中 视为「命中」）
    - 逐行为 diff：改善 / 恶化 / 持平
    - 结果波动清单（同一行为两次状态不同）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 视为「命中」的状态（锚点最终在某个层级上被找到）
HIT_STATUS = {"首屏命中", "导航后命中", "导航可救(建议加前置步)"}
# 明确不可用（污染/异常），不参与命中率计算
VOID_STATUS = {"数据作废(页面非目标App)", "数据作废(前台非目标App)", "异常"}


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("report") or {}


def flatten(report):
    """{(app, behavior): status}"""
    out = {}
    for app, rows in report.items():
        for r in rows:
            out[(app, r["behavior"])] = r.get("status", "?")
    return out


def is_hit(st):
    return st in HIT_STATUS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", default=None, help="可选：写一份 markdown 报告")
    args = ap.parse_args()

    base = flatten(load(args.base))
    new = flatten(load(args.new))
    keys = sorted(set(base) | set(new))

    improved, worsened, same, voided = [], [], [], []
    for k in keys:
        b, n = base.get(k), new.get(k)
        if n in VOID_STATUS:
            voided.append((k, b, n))
            continue
        if b is None:
            improved.append((k, b, n))
        elif n is None:
            worsened.append((k, b, n))
        elif is_hit(n) and not is_hit(b):
            improved.append((k, b, n))
        elif is_hit(b) and not is_hit(n):
            worsened.append((k, b, n))
        elif b != n:
            same.append((k, b, n))          # 状态不同但命中与否一致（如首屏->导航后）
        else:
            same.append((k, b, n))

    def rate(d):
        vals = [v for v in d.values() if v not in VOID_STATUS]
        h = sum(1 for v in vals if is_hit(v))
        return h, len(vals)

    bh, bt = rate(base)
    nh, nt = rate(new)
    print("=" * 68)
    print(f"基线命中: {bh}/{bt}" + (f" = {bh / bt * 100:.1f}%" if bt else ""))
    print(f"新  命中: {nh}/{nt}" + (f" = {nh / nt * 100:.1f}%" if nt else ""))
    if bt and nt:
        print(f"净变化  : {(nh / nt - bh / bt) * 100:+.1f} 个百分点")
    print("=" * 68)

    def dump(title, items):
        print(f"\n## {title}（{len(items)}）")
        for (app, beh), b, n in items:
            print(f"  {app:16s} {beh:10s} {b}  ->  {n}")

    dump("改善", improved)
    dump("恶化", worsened)
    dump("持平/层级变化", same)
    if voided:
        print(f"\n## 本轮作废（不计入统计）（{len(voided)}）")
        for (app, beh), b, n in voided:
            print(f"  {app:16s} {beh:10s} {b}  ->  {n}")

    if args.out:
        md = ["# any_of 改造前后对比", "",
              f"- 基线: `{os.path.basename(args.base)}` → 命中 **{bh}/{bt}**",
              f"- 新结果: `{os.path.basename(args.new)}` → 命中 **{nh}/{nt}**", ""]
        for title, items in (("改善", improved), ("恶化", worsened),
                             ("持平/层级变化", same), ("本轮作废", voided)):
            md += [f"## {title}（{len(items)}）", "",
                   "| App | 行为 | 基线 | 新 |", "|---|---|---|---|"]
            for (app, beh), b, n in items:
                md.append(f"| {app} | {beh} | {b} | {n} |")
            md.append("")
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        print(f"\n报告: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/e2e_vlm.py`（75 行）

```python
# -*- coding: utf-8 -*-
"""e2e_vlm.py - 真机截图 -> VisionLocator -> 坐标 端到端回测

替代交接包里硬编码旧机路径的 e2e_vlm_adapt.py / e2e_vlm_real.py。
直接复用工程自身的 vision.VisionLocator，保证测的就是实际执行路径。

用法：
    python devtools/e2e_vlm.py --prompt "定位屏幕上的『设置』应用图标"
    python devtools/e2e_vlm.py --image shot.png --prompt "..." --expected 281,1610
    python devtools/e2e_vlm.py --image shot.png            # 不连真机，用已有截图
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import vision as vs  # noqa: E402


def build_cfg():
    try:
        import yaml
        with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("vision") or {}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None, help="截图路径；缺省则现场截真机")
    ap.add_argument("--prompt", default="定位屏幕上『设置』应用图标的中心")
    ap.add_argument("--expected", default=None, help="期望中心 x,y，用于算误差")
    ap.add_argument("--save", default=None, help="现场截图保存路径")
    args = ap.parse_args()

    path = args.image
    if not path:
        from adbkit import Adb
        a = Adb()
        a.ensure()
        path = args.save or os.path.join(HERE, "out", "e2e_input.png")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        a.screenshot(path)
        print(f"[shot] 真机截图 -> {path} ({os.path.getsize(path)} bytes)")

    locator = vs.VisionLocator(build_cfg(), base_dir=ROOT)
    print(f"[cfg] vision.enabled={locator.enabled} "
          f"vlm_available={locator.vlm_available}")

    from PIL import Image
    img = Image.open(path).convert("RGB")
    print(f"[input] {path} size={img.size}")
    print(f"[prompt] {args.prompt}")

    hit = locator.locate_on_screen(prompt=args.prompt, screen_img=img,
                                   app="devtools", tag="e2e")
    if hit is None:
        print("RESULT: None（未命中，或 VLM 未配置/不可用）")
        print("提示：先跑 devtools/vlm_probe.py --models 确认网关可用。")
        return 1
    print(f"RESULT: 命中 ({hit.x:.1f}, {hit.y:.1f}) score={hit.score}")
    if args.expected:
        ex, ey = (int(v) for v in args.expected.split(","))
        err = ((hit.x - ex) ** 2 + (hit.y - ey) ** 2) ** 0.5
        print(f"期望中心 ({ex},{ey})  欧氏误差 {err:.1f}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/g_scan.py`（80 行）

```python
# -*- coding: utf-8 -*-
"""g_scan.py - 带跑辅助：扫描当前页文本节点（含 bounds），可按关键词过滤。

用法：
    python devtools/g_scan.py                # 全部文本节点
    python devtools/g_scan.py 打卡 签到       # 只看含这些关键词的节点
    python devtools/g_scan.py --click 打卡   # 点第一个文本恰为「打卡」的节点
"""
import sys
import time

import uiautomator2 as u2
import xml.etree.ElementTree as ET

SERIAL = "192.168.1.54:5555"


def walk(node, out):
    text = (node.get("text") or "").strip()
    desc = (node.get("content-desc") or "").strip()
    bounds = node.get("bounds") or ""
    if text or desc:
        out.append({
            "text": text,
            "desc": desc,
            "bounds": bounds,
            "clickable": node.get("clickable"),
        })
    for child in node:
        walk(child, out)


def center(bounds):
    try:
        left_top, right_bottom = bounds.split("][")
        x1, y1 = [int(v) for v in left_top.strip("[]").split(",")]
        x2, y2 = [int(v) for v in right_bottom.strip("[]").split(",")]
        return (x1 + x2) // 2, (y1 + y2) // 2
    except Exception:
        return None


def main():
    args = [a for a in sys.argv[1:]]
    do_click = "--click" in args
    args = [a for a in args if a != "--click"]
    keywords = args

    d = u2.connect(SERIAL)
    print("activity:", d.app_current().get("activity"))
    root = ET.fromstring(d.dump_hierarchy())
    nodes = []
    walk(root, nodes)
    print("total nodes:", len(nodes))

    hits = nodes
    if keywords:
        hits = [n for n in nodes if any(k in (n["text"] + n["desc"]) for k in keywords)]

    for n in hits[:60]:
        c = center(n["bounds"])
        print(f"{n['text'][:30]:32s}| {n['desc'][:16]:18s}| {n['bounds']:24s}| cl={n['clickable']} c={c}")

    if do_click and keywords:
        target = None
        for n in hits:
            if n["text"] == keywords[0]:
                target = n
                break
        if target is None and hits:
            target = hits[0]
        if target:
            c = center(target["bounds"])
            print("clicking", target["text"], c)
            d.click(*c)
            time.sleep(2)


if __name__ == "__main__":
    main()
```

### `devtools/gh_api_push.py`（291 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gh_api_push.py - 当 `github.com` 不可达时，用 REST API 把本地 HEAD 推上去

为什么需要它：本机出口代理能连 `api.github.com`，但 **`github.com` 被挡**
（`CONNECT tunnel failed, response 502`），`git push` 无论换 schannel 还是
openssl 后端都失败。而 git 协议走的正是 `github.com`。
GitHub 的 **Git Data API** 在 `api.github.com` 上，功能等价：
建 blob → 建 tree → 建 commit → 更新 ref。

用法：
    python devtools/gh_api_push.py --repo owner/name --branch main
    python devtools/gh_api_push.py --repo owner/name --dry-run

Token 来源（按优先级）：`--token` > 环境变量 `GITHUB_TOKEN` > Git Credential
Manager（`git-credential-manager get`）。**Token 不会被打印。**

增量：会先读远端 tree，只上传 sha 变化的 blob；未变的直接复用远端 sha。
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://api.github.com"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GCM = (r"C:/Users/Mass/.workbuddy-ai/binaries/PortableGit/versions/1.2.0"
       r"/mingw64/bin/git-credential-manager.exe")

# 2026-10-26 实测（本机 VUL / 代理 127.0.0.1:52068）：
#   走代理：大二进制（100KB+ 的 png）正常，但 ~8KB 以上的**文本** blob 会被
#           弄坏 —— GitHub 回 400 "We received a malformed request"。
#   走直连：文本正常，大 png 写入超时（60s 不够）。
# 两者互补，所以每次请求先走代理，遇到 400 malformed 再换直连重试一次；
# 超时放宽到 240s 让直连的大文件也能传完。
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_TIMEOUT = 240


# --------------------------------------------------------------------------
# git 侧
# --------------------------------------------------------------------------
def git(*args, binary=False):
    p = subprocess.run(["git", "-C", ROOT] + list(args),
                       capture_output=True, timeout=180)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败："
                           f"{p.stderr.decode('utf-8', 'replace')[:300]}")
    return p.stdout if binary else p.stdout.decode("utf-8", "replace")


def head_entries():
    """本地 HEAD 的全部 blob：[(mode, sha, path), ...]。"""
    raw = git("ls-tree", "-r", "-z", "HEAD")
    out = []
    for rec in raw.split("\0"):
        if not rec:
            continue
        meta, path = rec.split("\t", 1)
        mode, _typ, sha = meta.split()
        out.append((mode, sha, path))
    return out


def read_blobs(shas):
    """用一次 `git cat-file --batch` 把所有 blob 内容读出来（省进程开销）。"""
    p = subprocess.run(["git", "-C", ROOT, "cat-file", "--batch"],
                       input=("\n".join(shas) + "\n").encode(),
                       capture_output=True, timeout=600)
    data, pos, out = p.stdout, 0, {}
    for _ in shas:
        nl = data.index(b"\n", pos)
        header = data[pos:nl].decode()
        if header.endswith(" missing"):
            raise RuntimeError(f"blob 缺失：{header}")
        _sha, _typ, size = header.split()
        size = int(size)
        out[header.split()[0]] = data[nl + 1: nl + 1 + size]
        pos = nl + 1 + size + 1
    return out


def head_meta():
    fmt = "%H%n%an%n%ae%n%aI%n%s"
    lines = git("log", "-1", f"--format={fmt}").split("\n")
    return {"sha": lines[0], "name": lines[1], "email": lines[2],
            "date": lines[3], "subject": lines[4],
            "message": git("log", "-1", "--format=%B").rstrip("\n")}


# --------------------------------------------------------------------------
# GitHub 侧
# --------------------------------------------------------------------------
class Api:
    def __init__(self, token, dry_run=False):
        self.token = token
        self.dry_run = dry_run
        self.calls = 0

    def __call__(self, path, method="GET", payload=None, ok=(200, 201)):
        """发一次请求；代理弄坏 body 时自动换直连重试一次（见文件头说明）。"""
        if self.dry_run and method != "GET":
            return {"_dry_run": True}
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Authorization": "Bearer " + self.token,
                   "Accept": "application/vnd.github+json",
                   "User-Agent": "gh-api-push",
                   "Content-Type": "application/json"}
        last = None
        for direct in (False, True):
            self.calls += 1
            try:
                req = urllib.request.Request(API + path, method=method,
                                             data=data, headers=headers)
                opener = _DIRECT.open if direct else urllib.request.urlopen
                with opener(req, timeout=_TIMEOUT) as r:
                    return json.loads(r.read().decode("utf-8") or "{}")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if e.code in ok:
                    return {"_http": e.code}
                last = f"{method} {path} -> HTTP {e.code}: {body[:300]}"
                # 只有「代理把 body 弄坏」才值得换链路；权限/不存在类 4xx 换也没用
                if e.code != 400 or "malformed" not in body:
                    raise RuntimeError(last) from None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = f"{method} {path} -> {type(e).__name__}: {e}"
                # 直连大文件可能写超时，但此时已无链路可换，交给外层报错
        raise RuntimeError(last)


def get_token(explicit=None):
    if explicit:
        return explicit
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    if os.path.exists(GCM):
        p = subprocess.run([GCM, "get"],
                           input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=120)
        for line in (p.stdout or "").splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    return None


def remote_tree(api, repo, branch):
    """远端分支当前的 tree 映射 {path: sha}；分支不存在返回 (None, None)。"""
    try:
        ref = api(f"/repos/{repo}/git/ref/heads/{branch}")
    except RuntimeError as e:
        if "HTTP 404" in str(e) or "HTTP 409" in str(e):
            return None, None
        raise
    commit_sha = ref["object"]["sha"]
    commit = api(f"/repos/{repo}/git/commits/{commit_sha}")
    tree_sha = commit["tree"]["sha"]
    tree = api(f"/repos/{repo}/git/trees/{tree_sha}?recursive=1")
    return commit_sha, {x["path"]: x["sha"] for x in tree.get("tree", [])
                        if x["type"] == "blob"}


def bootstrap_empty(api, repo, branch):
    """空仓库不接受 Git Data API 建 blob（HTTP 409 "Git Repository is empty"）。

    实测踩过：直接在刚 create 出来的空仓库上建 blob，189 个全部 409。
    必须先用 Contents API 建一个占位文件把第一个提交撑起来，
    之后 Git Data API 才可用。占位文件在随后建 tree 时会被自然丢弃
    （tree 完全按本地 HEAD 生成，不带 base_tree）。
    """
    # Contents API 建/改文件是 **PUT**，不是 POST（POST 会直接 404）
    api(f"/repos/{repo}/contents/.gitkeep", "PUT", {
        "message": "chore: bootstrap repository",
        "content": base64.b64encode(b"# bootstrap\n").decode("ascii"),
        "branch": branch,
    }, ok=(200, 201, 409, 422))


def main():
    ap = argparse.ArgumentParser(description="用 GitHub REST API 推送本地 HEAD")
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--token", default=None)
    ap.add_argument("--jobs", type=int, default=10, help="并发上传数")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = get_token(args.token)
    if not token:
        print("FAIL 取不到 token（--token / GITHUB_TOKEN / GCM 都没有）")
        return 2
    api = Api(token, dry_run=args.dry_run)

    entries = head_entries()
    meta = head_meta()
    print(f"本地 HEAD {meta['sha'][:8]}  共 {len(entries)} 个文件")
    print(f"提交者 {meta['name']} <{meta['email']}>  {meta['date']}")
    print(f"目标 {args.repo}@{args.branch}")

    parent, remote = remote_tree(api, args.repo, args.branch)
    if parent:
        print(f"远端已有 {len(remote)} 个 blob（将只上传变化的）")
    elif args.dry_run:
        print("远端分支不存在（首次推送；真实执行时会先 bootstrap）")
    else:
        print("远端分支不存在 —— 先 bootstrap 空仓库")
        bootstrap_empty(api, args.repo, args.branch)
        parent, remote = remote_tree(api, args.repo, args.branch)
        print(f"bootstrap 完成，parent={parent[:8] if parent else None}")

    todo = [e for e in entries if remote is None or remote.get(e[2]) != e[1]]
    print(f"需要上传 {len(todo)} / {len(entries)} 个 blob")

    blobs = read_blobs([e[1] for e in todo]) if todo else {}
    tree_entries, done, failed = [], 0, []

    def upload(ent):
        mode, sha, path = ent
        if api.dry_run:          # dry-run 不真调接口，沿用本地 sha 占位
            return path, sha
        return path, api(f"/repos/{args.repo}/git/blobs", "POST", {
            "content": base64.b64encode(blobs[sha]).decode("ascii"),
            "encoding": "base64"})["sha"]

    if todo:
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            futs = {ex.submit(upload, e): e for e in todo}
            for fu in as_completed(futs):
                ent = futs[fu]
                try:
                    path, new_sha = fu.result()
                    tree_entries.append((ent[0], new_sha, path))
                    done += 1
                    if done % 25 == 0 or done == len(todo):
                        print(f"  已上传 {done}/{len(todo)}")
                except Exception as e:  # noqa: BLE001
                    failed.append((ent[2], str(e)[:120]))
    if failed:
        print(f"\nFAIL {len(failed)} 个 blob 上传失败：")
        for p, e in failed[:5]:
            print(f"  {p}: {e}")
        return 1

    # 未变化的条目直接沿用远端 sha
    for mode, sha, path in entries:
        if remote is not None and remote.get(path) == sha and \
                not any(t[2] == path for t in tree_entries):
            tree_entries.append((mode, sha, path))

    if args.dry_run:
        print(f"\n[dry-run] 将建 tree（{len(tree_entries)} 项）→ commit → "
              f"{'更新' if parent else '创建'} refs/heads/{args.branch}")
        print(f"[dry-run] 已用 {api.calls} 次 API 调用")
        return 0

    tree = api(f"/repos/{args.repo}/git/trees", "POST", {
        "tree": [{"path": p, "mode": m, "type": "blob", "sha": s}
                 for m, s, p in tree_entries]})
    print(f"tree {tree['sha'][:8]}")

    cpayload = {"message": meta["message"], "tree": tree["sha"],
                "author": {"name": meta["name"], "email": meta["email"],
                           "date": meta["date"]},
                "committer": {"name": meta["name"], "email": meta["email"],
                              "date": meta["date"]}}
    if parent:
        cpayload["parents"] = [parent]
    commit = api(f"/repos/{args.repo}/git/commits", "POST", cpayload)
    print(f"commit {commit['sha'][:8]}")

    if parent:
        api(f"/repos/{args.repo}/git/refs/heads/{args.branch}", "PATCH",
            {"sha": commit["sha"], "force": False})
    else:
        api(f"/repos/{args.repo}/git/refs", "POST",
            {"ref": f"refs/heads/{args.branch}", "sha": commit["sha"]})
    print(f"已推送 -> https://github.com/{args.repo}/tree/{args.branch}"
          f"（{api.calls} 次 API 调用）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/nl_to_steps.py`（508 行）

```python
# -*- coding: utf-8 -*-
"""nl_to_steps.py - 自然语言 → 动作链 YAML（AUTOP-NL-2026-10-22-A 第1层：模板填槽）

把一句中文自然语言 + App 名，生成可直接插入 config/apps/<app>.yaml 的
behaviors.<bid> 动作链 YAML 片段。**只产出片段，不写配置**（写回由
devtools/yaml_writer.py 负责，Host 已落地并通过 14 例测试）。

设计取舍（与结构约束一一对应，违反即返工）：
  1. 每个 hop 独立成一个 `any_of`：choices[0] = 文案支（click_first + 显式
     candidates_from + 仅 tab 跳 zone: tab_zone），choices[1] = 坐标支
     （click_point + vision: false）。
     原因：any_of 分支内任一步失败即整支 break（behavior_runner._step_any_of
     文档已述），写在同一支里坐标永远执行不到。
  2. 文案支/坐标支必须分属两个 choice；后续步骤**不复制进两个分支**
     （反例：config/apps/10_米读小说.yaml 的嵌套复制会让配置指数膨胀）。
  3. tab 跳显式 candidates_from: nav_tab，hub 跳 task_center，sign 跳 sign。
     原因：candidates_from 缺省时按当前行为自动推断（sign 行为里点 tab 会
     被推断成 sign 词表），不能依赖它。
  4. 坐标兜底默认单点；--h5 时才在坐标支内追加 wait 1.5 + 下移 --h5-offset
     （默认 60px，实测 32/43/60 均有效）。原因：_step_click_point 除视觉
     分支外没有 return，_run_kind 把 None 当成功 —— 多点若拆成两个 choice，
     第二个永远不可达。
  5. 任何 *_xy 缺省 → 该跳只出文案支 + warning「缺坐标兜底，建议真机校准后补」，
     绝不猜坐标。
  6. 文案来源只走 candidates.candidates_for(category, app_cfg)；本模块
     不含任何词表副本（词表门禁：tests 里 assert 无中文词表字面量）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import candidates  # noqa: E402
from devtools import yaml_writer  # noqa: E402
import config_loader  # noqa: E402

# ---------- 解析：纯函数（无 IO、无设备、无全局状态） ----------

_SPLIT_RE = r"[，,；;。]|然后|接着|之后|再|并(?=[点滑等返找翻])|\s*->\s*"

# 长词优先：先按长度降序匹配（"点击「带引号的目标」" 不能被 "点" 截胡）
_VERBS = [
    ("向上滑", "swipe"), ("往下滑", "swipe"),
    ("点击", "tap"), ("点开", "tap"), ("打开", "tap"),
    ("上滑", "swipe"), ("下滑", "swipe"),
    ("翻页", "scroll_to"), ("滚动", "scroll_to"),
    ("等待", "wait"), ("停留", "wait"),
    ("返回", "back"), ("后退", "back"),
    ("查找", "find"), ("出现", "find"),
    ("点", "tap"), ("戳", "tap"), ("按", "tap"),
    ("滑", "swipe"), ("翻", "scroll_to"),
    ("等", "wait"),
    ("找", "find"),
]

_POS = {
    "右下角": (0.90, 0.914), "右上角": (0.93, 0.12),
    "底部最右": (0.90, 0.914), "底部右二": (0.70, 0.914),
    "底部左二": (0.30, 0.914), "底部最左": (0.10, 0.914),
    "屏幕中间": (0.50, 0.50), "中间": (0.50, 0.50),
}

_CN_DIGIT = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_CN_UNITS = {"秒": 1.0, "分": 60.0, "分钟": 60.0, "小时": 3600.0}


def _strip_quotes(s: str) -> str:
    """剥掉成对引号：「」""''《》『』。"""
    s = (s or "").strip()
    for left, right in (("「", "」"), ("『", "』"), ("“", "”"),
                        ("\"", "\""), ("'", "'"), ("《", "》")):
        if len(s) >= 2 and s[0] == left and s[-1] == right:
            s = s[1:-1].strip()
            break
    return s


def _cn_number(s: str) -> float | None:
    """中文时长 -> 秒；支持 三秒/五秒/十秒/半分钟；无法识别返回 None。"""
    if not s:
        return None
    s = _strip_quotes(s)
    m = re.search(r"半\s*(分钟|分)", s)
    if m:
        return 30.0
    m = re.search(r"([一二两三四五六七八九十]+)\s*(小时|分钟|分|秒)", s)
    if not m:
        return None
    n = _CN_DIGIT.get(m.group(1))
    if n is None:
        return None
    return float(n) * _CN_UNITS[m.group(2)]


def _extract_seconds(s: str) -> float | None:
    """阿拉伯数字秒 -> 秒（3秒 / 1.5s）。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|s|S)", s or "")
    return float(m.group(1)) if m else None


def _parse_xy(v):
    """坐标兜底入参归一：'0.5,0.641' / (0.5, 0.641) / [0.5, 0.641] -> (x, y)。"""
    if v is None:
        raise ValueError("坐标不能为 None")
    if isinstance(v, (tuple, list)) and len(v) == 2:
        return float(v[0]), float(v[1])
    s = str(v).strip().strip("()[]（）")
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        raise ValueError(f"坐标格式应为 x,y: {v!r}")
    return float(parts[0]), float(parts[1])


def _match_verb(text: str) -> tuple[str | None, str | None]:
    for v, kind in _VERBS:  # 已按长度降序
        if v in text:
            return v, kind
    return None, None


def parse_line(text: str) -> tuple[list[dict], list[str]]:
    """解析一句自然语言 -> (steps, warnings)。

    steps 元素: {"verb","target","pos","seconds","raw"}（缺省 None）；
    无法识别动词 → verb="unknown" + warning，不抛异常。
    """
    raw = (text or "").strip()
    if not raw:
        return [], ["空行无法解析"]
    s = _strip_quotes(raw)
    verb, kind = _match_verb(s)
    if verb is None:
        return [{"verb": "unknown", "target": s, "pos": None,
                 "seconds": None, "raw": raw}], [f"无法识别动词: {raw}"]

    idx = s.find(verb)
    head = s[:idx]
    tail = s[idx + len(verb):]
    step = {"verb": kind, "target": None, "pos": None,
            "seconds": None, "raw": raw}

    # 位置词（右下角/右上角/底部最右/...）
    for pos_word, xy in _POS.items():
        if pos_word in s:
            step["pos"] = xy
            head = head.replace(pos_word, "")
            tail = tail.replace(pos_word, "")
            break

    # 次数（两次/三次/...）
    m = re.search(r"([一二两三四五六七八九十])次", head + tail)
    if m:
        step["count"] = _CN_DIGIT[m.group(1)]
        head = head.replace(m.group(0), "")
        tail = tail.replace(m.group(0), "")

    # 连词噪声（split 未消掉的引导词）
    for w in ("最后", "首先", "先", "然后", "接着", "之后"):
        head = head.replace(w, "")
        tail = tail.replace(w, "")

    if kind == "wait":
        secs = _cn_number(s) or _extract_seconds(tail or head or s)
        step["seconds"] = secs if secs is not None else 1.0

    t = _strip_quotes((tail or head).strip()).strip()
    if kind in ("back", "swipe", "wait"):
        step["target"] = None
    else:
        step["target"] = t or None
    return [step], []


def parse_script(text: str) -> tuple[list[dict], list[str]]:
    """多行/多句：按 _SPLIT_RE 切分后逐句 parse_line。"""
    parts = [p.strip() for p in re.split(_SPLIT_RE, text or "") if p.strip()]
    steps: list[dict] = []
    warnings: list[str] = []
    for p in parts:
        ss, ww = parse_line(p)
        steps.extend(ss)
        warnings.extend(ww)
    return steps, warnings


# ---------- 模板（结构化，非字符串拼接） ----------

TEMPLATES = {
    "personal_center": {"hops": ["tab", "hub", "sign"]},
    "feed_ball": {"hops": ["tab", "ball", "sign"]},
    "home_direct": {"hops": ["anchor", "sign"]},
}

# kind -> (text 槽位, xy 槽位)
_HOP_KEYS = {
    "tab": ("tab_text", "tab_xy"),
    "hub": ("hub_text", "hub_xy"),
    "sign": (None, "sign_xy"),
    "ball": (None, "ball_xy"),
    "anchor": ("anchor_text", "anchor_xy"),
}

# kind -> 显式 candidates_from 类别（缺省时按当前行为自动推断，不能依赖）
_HOP_CATEGORY = {
    "tab": "nav_tab",
    "hub": "task_center",
    "sign": "sign",
    "anchor": "sign",
    "ball": "nav_tab",
}


def template_names() -> list[str]:
    return list(TEMPLATES.keys())


def guess_entry(text: str) -> str:
    """含「我的/个人中心」→personal_center；含「浮球/金币/右上」→feed_ball；
    否则 home_direct。"""
    s = text or ""
    if "个人中心" in s or "我的" in s:
        return "personal_center"
    if "浮球" in s or "金币" in s or "右上" in s:
        return "feed_ball"
    return "home_direct"


def render_hop(kind: str, params: dict, category: str,
               app_cfg: dict | None = None) -> list[dict]:
    """渲染单个 hop（any_of：文案支 + 可选坐标支）。"""
    params = params or {}
    if kind not in _HOP_KEYS:
        raise ValueError(f"未知 hop 类型: {kind!r}（可选 {list(_HOP_KEYS)}）")
    text_key, xy_key = _HOP_KEYS[kind]
    eff_cat = _HOP_CATEGORY.get(kind, category)

    choices: list[list[dict]] = []

    # 文案支
    text_branch: list[dict] = [{
        "type": "click_first",
        "candidates_from": eff_cat,
        "timeout": 8,
        "optional": False,
    }]
    text_val = params.get(text_key) if text_key else None
    if text_val:
        text_branch[0]["candidates"] = [{"type": "text", "value": text_val}]
    if kind == "tab":
        text_branch[0]["zone"] = "tab_zone"
    choices.append(text_branch)

    # 坐标支（缺 xy 不出坐标支，绝不猜坐标）
    xy_val = params.get(xy_key)
    if xy_val:
        x, y = _parse_xy(xy_val)
        point = {
            "type": "click_point", "x": x, "y": y,
            "timeout": 8, "optional": False, "vision": False,
            "desc": f"{kind}坐标兜底（待真机校准）",
        }
        if params.get("h5"):
            offset = float(params.get("h5_offset") or 60)
            y2 = round(y + offset / 2340.0, 6)
            choices.append([
                point,
                {"type": "wait", "seconds": 1.5},
                {"type": "click_point", "x": x, "y": y2,
                 "timeout": 8, "optional": False, "vision": False,
                 "desc": f"{kind}坐标兜底（h5 下移 {offset}px）"},
            ])
        else:
            choices.append([point])

    return [{"type": "any_of", "optional": True, "choices": choices}]


def render_chain(entry: str, params: dict, category: str,
                 app_cfg: dict | None = None) -> tuple[list[dict], list[str]]:
    """按模板 hops 渲染整条动作链 -> (actions, warnings)。"""
    if entry not in TEMPLATES:
        raise ValueError(f"未知模板: {entry!r}（可选 {template_names()}）")
    params = params or {}
    actions: list[dict] = []
    warnings: list[str] = []
    for kind in TEMPLATES[entry]["hops"]:
        xy_key = _HOP_KEYS[kind][1]
        if not params.get(xy_key):
            warnings.append(f"{kind} 跳缺坐标兜底，建议真机校准后补")
        if kind == "sign" and params.get("scroll_text"):
            actions.append({
                "type": "scroll_to",
                "text": str(params["scroll_text"]),
                "max_pages": 6,
            })
        actions.extend(render_hop(kind, params, category, app_cfg))
    if params.get("confirm_text"):
        actions.append({
            "type": "click_first",
            "candidates": [{"type": "text", "value": str(params["confirm_text"])}],
            "candidates_from": _HOP_CATEGORY.get("sign", category),
            "timeout": 6,
            "optional": True,
        })
    return actions, warnings


def render_steps(steps: list[dict], params: dict, category: str,
                 app_cfg: dict | None = None) -> tuple[list[dict], list[str]]:
    """把 parse_line/parse_script 的自由步骤渲染成动作链（模板之外的兜底入口）。"""
    params = params or {}
    actions: list[dict] = []
    warnings: list[str] = []
    for st in steps:
        kind = st.get("verb")
        raw = st.get("raw") or ""
        if kind == "unknown":
            warnings.append(f"无法识别的步骤: {raw}")
            continue
        if kind == "wait":
            actions.append({"type": "wait", "seconds": float(st.get("seconds") or 1.0)})
        elif kind == "tap":
            if st.get("pos"):
                x, y = st["pos"]
                actions.append({
                    "type": "click_point", "x": x, "y": y,
                    "timeout": 8, "optional": True, "vision": False,
                    "desc": f"点击坐标兜底（待真机校准）",
                })
            elif st.get("target"):
                actions.append({
                    "type": "click_first",
                    "candidates": [{"type": "text", "value": st["target"]}],
                    "candidates_from": category,
                    "timeout": 8, "optional": True,
                })
            else:
                warnings.append(f"缺少点击目标: {raw}")
        elif kind == "swipe":
            up = "上" in raw and "下" not in raw
            cnt = int(st.get("count") or 1)
            for _ in range(cnt):
                if up:
                    actions.append({"type": "swipe", "from": [0.5, 0.7],
                                    "to": [0.5, 0.3], "duration": 0.8, "natural": True})
                else:
                    actions.append({"type": "swipe", "from": [0.5, 0.3],
                                    "to": [0.5, 0.7], "duration": 0.8, "natural": True})
        elif kind in ("scroll_to", "find"):
            actions.append({"type": "scroll_to",
                            "text": str(st.get("target") or ""), "max_pages": 6})
        elif kind == "back":
            actions.append({"type": "back"})
        else:
            warnings.append(f"暂不支持的步骤类型: {kind}")
    return actions, warnings


# ---------- 组装 / 输出 ----------

def build_behavior(text: str, app_name: str, bid: str, *,
                   entry: str = "auto", params: dict | None = None,
                   app_cfg: dict | None = None) -> dict:
    """-> {"behavior","entry","actions","warnings","candidates_used"}。"""
    params = dict(params or {})
    warnings: list[str] = []
    if entry == "auto":
        entry = guess_entry(text)
    if entry not in TEMPLATES:
        warnings.append(f"未知模板: {entry!r}，已回退 home_direct")
        entry = "home_direct"
    category = candidates.category_for_intent(bid) or "sign"
    actions, hop_warnings = render_chain(entry, params, category, app_cfg)
    warnings.extend(hop_warnings)
    used: dict[str, list[str]] = {}
    for kind in TEMPLATES[entry]["hops"]:
        cat = _HOP_CATEGORY.get(kind, category)
        used.setdefault(cat, list(candidates.candidates_for(cat, app_cfg)))
    return {"behavior": bid, "entry": entry, "actions": actions,
            "warnings": warnings, "candidates_used": used}


def to_yaml_fragment(actions: list[dict], indent: int = 2) -> str:
    """动作链 -> YAML 文本（转调 yaml_writer.render_actions，PyYAML 风格）。"""
    return "\n".join(yaml_writer.render_actions(actions, indent))


# ---------- CLI ----------

def _load_app_cfg(app_name: str) -> dict | None:
    try:
        snap = yaml_writer.snapshot()
    except Exception:  # noqa: BLE001 - CLI 容错，配置加载失败按无 App 微调处理
        return None
    return snap.get(app_name) if snap else None


def _print_templates() -> None:
    print("可用模板（3 种入口）与槽位：")
    for name in template_names():
        hops = " -> ".join(TEMPLATES[name]["hops"])
        print(f"  {name}: {hops}")
    print("公共槽位: tab_text/tab_xy/hub_text/hub_xy/ball_xy/anchor_text/"
          "anchor_xy/sign_xy/scroll_text/confirm_text/h5/h5_offset")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="自然语言 → 动作链 YAML 片段（只产出片段，--apply 才写盘）")
    parser.add_argument("--app", help="App 名（config/apps/<app>.yaml）")
    parser.add_argument("--behavior", default="sign", help="行为 ID（默认 sign）")
    parser.add_argument("--text", help="中文自然语言描述")
    parser.add_argument("--entry", default="auto",
                        choices=["auto"] + template_names(),
                        help="入口模板（默认 auto 自动猜测）")
    parser.add_argument("--h5", action="store_true",
                        help="H5 页：坐标支内追加 wait 1.5 + 下移 --h5-offset")
    parser.add_argument("--h5-offset", type=float, default=60.0,
                        help="H5 下移像素（默认 60，屏幕高按 2340 归一）")
    parser.add_argument("--xy", help="签到步坐标兜底，如 0.5,0.641")
    parser.add_argument("--tab-text", help="tab 跳文案（如 我的/福利）")
    parser.add_argument("--tab-xy", help="tab 跳坐标兜底，如 0.9,0.914")
    parser.add_argument("--hub-text", help="hub 跳文案（如 福利中心）")
    parser.add_argument("--hub-xy", help="hub 跳坐标兜底")
    parser.add_argument("--anchor-text", help="anchor 跳文案（首页直落型）")
    parser.add_argument("--anchor-xy", help="anchor 跳坐标兜底")
    parser.add_argument("--ball-xy", help="ball 跳坐标兜底（内容流浮球型）")
    parser.add_argument("--print-yaml", action="store_true", help="打印 YAML 片段")
    parser.add_argument("--apply", action="store_true",
                        help="写盘（insert_behavior apply=True）")
    parser.add_argument("--force", action="store_true",
                        help="行为已存在时走 replace_behavior(force=True)")
    parser.add_argument("--allow-money", action="store_true",
                        help="允许为资金类行为生成配置（默认拒绝）")
    parser.add_argument("--templates", action="store_true",
                        help="列出 3 模板与槽位后退出")
    args = parser.parse_args(argv)

    if args.templates:
        _print_templates()
        return 0
    if not args.app or not args.text:
        parser.error("--app 与 --text 必填（或使用 --templates）")

    # 资金类行为拒绝（config_loader.money_behaviors，缺省 {"withdraw"}）
    try:
        cfg = config_loader.load_config(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"))
    except Exception:  # noqa: BLE001
        cfg = {}
    money = config_loader.money_behaviors(cfg)
    if args.behavior in money and not args.allow_money:
        print(f"拒绝为资金类行为生成配置: {args.behavior}（money_behaviors="
              f"{sorted(money)}；如确需生成请加 --allow-money）", file=sys.stderr)
        return 1

    app_cfg = _load_app_cfg(args.app)
    params: dict = {}
    if args.h5:
        params["h5"] = True
        params["h5_offset"] = args.h5_offset
    if args.xy:
        params["sign_xy"] = args.xy
    # 真机校准后的多跳坐标兜底（AUTOP-NL 真机实跑补：只有 --xy 时 tab/hub 无坐标支）
    for flag, key in (("--tab-text", "tab_text"), ("--tab-xy", "tab_xy"),
                      ("--hub-text", "hub_text"), ("--hub-xy", "hub_xy"),
                      ("--anchor-text", "anchor_text"), ("--anchor-xy", "anchor_xy"),
                      ("--ball-xy", "ball_xy")):
        val = getattr(args, flag.lstrip("-").replace("-", "_"))
        if val:
            params[key] = val

    result = build_behavior(args.text, args.app, args.behavior,
                            entry=args.entry, params=params, app_cfg=app_cfg)
    for w in result["warnings"]:
        print(f"WARN: {w}", file=sys.stderr)
    fragment = to_yaml_fragment(result["actions"])
    if args.print_yaml or not args.apply:
        print(f"# {args.app} / {args.behavior} / entry={result['entry']}")
        print(fragment)
    if not args.apply:
        return 0

    path = yaml_writer.app_path(args.app)
    if not args.force:
        wr = yaml_writer.insert_behavior(path, args.behavior,
                                         result["actions"], apply=True)
    else:
        wr = yaml_writer.replace_behavior(path, args.behavior,
                                          result["actions"], apply=True,
                                          force=True)
    print(f"write action={wr.action} path={wr.path}")
    for w in wr.warnings:
        print(f"WRITE-WARN: {w}", file=sys.stderr)
    if wr.action == "skipped" and not args.force:
        print("提示：该行为已存在；如需覆盖请加 --force", file=sys.stderr)
    return 0 if wr.changed else (0 if wr.action == "skipped" else 1)


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/patch_nav_vision.py`（115 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给「导航到我的」前置步补上 `vision: false`（幂等）。

为什么
------
`click_point` 若带 `vlm_prompt`，执行器会**先走视觉兜底**（截屏 + VLM 识别）。
本机 VLM 图像请求常 90s 超时或返回 `User Safety: safe`（非确定性），
而导航「我的」是**每个行为都要执行**的固定步骤 —— 让它走视觉既慢又不稳。

比例坐标 (0.90, 0.915) 已在 18 个 App 上实机验证可靠（各 App『我的』中心
y 落在 2106~2192）。因此导航步显式关闭视觉兜底，直接点比例坐标。

保留 `vlm_prompt` 字段：devtools（plan_anchor_fixes / verify_live /
to_any_of）靠它识别「这是导航前置步」，删了会破坏前置步检测。

用法
----
    python devtools/patch_nav_vision.py            # 预览
    python devtools/patch_nav_vision.py --apply    # 写回（自动备份）
"""
import argparse
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")
NAV_MARK = "最右侧"


def patch(node, counter):
    """递归给导航 click_point 加 vision: false（原地修改）。"""
    if isinstance(node, dict):
        if (node.get("type") == "click_point"
                and NAV_MARK in str(node.get("vlm_prompt", ""))
                and node.get("vision", True) is not False):
            node["vision"] = False
            counter["patched"] += 1
        else:
            if (node.get("type") == "click_point"
                    and NAV_MARK in str(node.get("vlm_prompt", ""))):
                counter["already"] += 1
        for v in node.values():
            patch(v, counter)
    elif isinstance(node, list):
        for v in node:
            patch(v, counter)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    import copy
    import yaml
    cfg = load_config(args.config)

    counter = {"patched": 0, "already": 0}
    patched_apps = {}
    for app in cfg.get("apps") or []:
        name = app.get("name")
        c1 = {"patched": 0, "already": 0}
        patch([app], c1)
        counter["patched"] += c1["patched"]
        counter["already"] += c1["already"]
        if c1["patched"] and name:
            patched_apps[name] = app
    print(f"导航前置步: 待补 {counter['patched']} 处，"
          f"已补过 {counter['already']} 处")

    if not counter["patched"]:
        print("无需改动")
        return 0
    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    # 拆分后：逐 App 文件写回（App 级文件无注释，直接 dump）
    for name in sorted(patched_apps):
        path = app_config_path(name)
        bak = f"{path}.bak-navvision-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak)
        out = yaml.dump(patched_apps[name], allow_unicode=True, sort_keys=False,
                        default_flow_style=False, width=200)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        print(f"已写回 {path}\n备份: {bak}")

    try:
        cfg2 = load_config(args.config)
        c2 = {"patched": 0, "already": 0}
        patch(cfg2.get("apps") or [], c2)
        print(f"复验: 加载成功, {len(cfg2['apps'])} 个 app, "
              f"仍待补 {c2['patched']} 处（应为 0）")
        if c2["patched"]:
            raise RuntimeError("复验发现仍有未补项")
    except Exception as ex:
        print(f"复验失败: {ex}（各 App 备份文件已保留，可手动回滚）")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/plan_anchor_fixes.py`（368 行）

```python
# -*- coding: utf-8 -*-
"""plan_anchor_fixes.py - 数据驱动地规划并（可选）应用锚点修补

依据 devtools/calib/<app>/ 下的两份 dump（落地页 ui.xml + 二级页 ui_after.xml）
判断每个行为的入口该怎么修：

  A. 首屏已命中          -> 不动
  B. 首屏未命中、二级页命中 -> 在行为最前面插一步「导航到我的」（click_point + vlm_prompt）
  C. 两页都无文本锚点     -> 需 click_point 坐标 / VLM 专项，本脚本只报告
  D. 只差"语义"（text 找不到但 desc 能找到） -> 给候选追加一条同值 desc 候选

用法：
    python devtools/plan_anchor_fixes.py                 # 只出计划（默认）
    python devtools/plan_anchor_fixes.py --apply          # 写回 config.yaml（自动备份）
    python devtools/plan_anchor_fixes.py --apps 一淘,抖音  # 限定 App
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402
from calibrate import parse_nodes, match_selector  # noqa: E402

ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")

# 二级页导航前置步：先试 VLM 视觉定位，失败则用比例坐标兜底
NAV_ACTION = [
    "    - type: click_point",
    "      vlm_prompt: \"定位屏幕底部导航栏最右侧的『我的』标签中心\"",
    "      x: 0.9",
    "      y: 0.908",
    "      optional: true",
    "    - type: think",
]

# 用于给「纯图片按钮」兜底的通用文案（按行为）
BEHAVIOR_KEYWORDS = {
    "sign": ["签到", "每日签到", "立即签到", "去签到", "打卡", "签到领"],
    "watch": ["看视频", "看广告", "看剧", "去完成", "任务", "赚钱", "福利"],
    "withdraw": ["提现", "可提现", "余额", "现金", "钱包", "我的"],
    "collect": ["任务中心", "福利", "开宝箱", "领取", "做任务"],
    "bonus": ["领红包", "领金币", "领取", "奖励", "红包"],
}


def load_cfg():
    return load_config(os.path.join(ROOT, "config.yaml"))


def first_anchor_action(actions):
    variants = actions if all(isinstance(a, list) for a in actions) else [actions]
    for vi, variant in enumerate(variants):
        for i, act in enumerate(variant or []):
            if isinstance(act, dict) and act.get("type") in ANCHOR_TYPES + ("any_of",):
                return vi, i, act
    return None, None, None


def _cands_of_one(act):
    t = act.get("type")
    if t == "click_first":
        return [c for c in (act.get("candidates") or [])
                if isinstance(c, dict) and c.get("value")]
    if t == "click_text":
        return [{"type": "text", "value": act.get("text", "")}]
    if t == "click_id":
        return [{"type": "id", "value": act.get("res_id", "")}]
    return [{"type": "desc", "value": act.get("desc", "")}]


def candidates_of(act):
    """展开锚点动作的候选；any_of 时汇总所有分支里的候选。"""
    if act.get("type") == "any_of":
        out = []
        for ch in act.get("choices") or []:
            for a in (ch if isinstance(ch, list) else [ch]):
                if isinstance(a, dict) and a.get("type") in ANCHOR_TYPES:
                    out += _cands_of_one(a)
        return out
    return _cands_of_one(act)


def hit_native(nodes, cands):
    """只按候选自身声明的语义匹配（与 executor 的真实行为一致）"""
    for c in cands:
        k, v = c.get("type", "text"), str(c.get("value") or "")
        if v and match_selector(nodes, k, v):
            return k, v
    return None


def hit_cross(nodes, cands):
    """在候选里找命中；先按自身语义，再跨 text/desc 语义。返回 (kind, value) 或 None"""
    for c in cands:
        k, v = c.get("type", "text"), str(c.get("value") or "")
        if not v:
            continue
        if match_selector(nodes, k, v):
            return k, v
        for k2 in ("text", "desc"):
            if k2 != k and match_selector(nodes, k2, v):
                return k2, v
    return None


def scan_keywords(nodes, keywords):
    """在节点里搜关键词，返回 [(label, kind, center)]"""
    out = []
    for kw in keywords:
        for kind in ("text", "desc"):
            for h in match_selector(nodes, kind, kw):
                label = (h["text"] or h["desc"]).strip()
                limit = max(len(kw) + 6, len(kw) * 3)
                if len(label) > limit and not h["clickable"]:
                    continue          # 长文案误命中，跳过
                out.append((label, kind, kw, h["center"]))
    return out


# rid（resource-id）关键词表：很多 App 的入口图标 text/desc 全空，
# 但 resource-id 稳定且带语义（实测河马剧场 item_cash=提现 / item_wallet=福利）。
# 注意：只用「强信号」词，且匹配时要求剥离前缀后**以关键词开头**
# （否则 tl_home_capture_video_btn 会被 "video" 误判成看视频入口）。
RID_KEYWORDS = {
    "sign": ["sign", "checkin", "check_in", "qiandao", "clock", "daily"],
    "watch": ["watch", "video_task", "browse", "read", "task"],
    "withdraw": ["cash", "wallet", "withdraw", "balance", "purse", "asset"],
    "collect": ["task_center", "taskcenter", "mission", "welfare",
                "benefit", "mall"],
    "bonus": ["reward", "redpacket", "red_packet", "box", "bonus",
              "lucky", "prize", "gift"],
}

# rid 常见无意义前缀，剥离后再判断
RID_PREFIXES = ("item_", "btn_", "iv_", "tv_", "ll_", "img_", "icon_",
                "fl_", "rl_", "layout_", "button_")


def scan_rid(nodes, behavior):
    """扫 rid 语义锚点：返回 (rid, center, size) 或 None。

    只在「text/desc 全空但 rid 有语义」的可点击节点里找，
    避免抢掉已有的文本锚点。匹配要求剥离前缀后以关键词开头。
    """
    kws = RID_KEYWORDS.get(behavior, [])
    if not kws:
        return None
    best = None
    for n in nodes:
        if not n["clickable"]:
            continue
        if (n["text"] or n["desc"]).strip():
            continue                      # 有文案的交给文本扫描
        rid = n["rid"]
        if not rid:
            continue
        short = rid.split("/")[-1].lower()
        core = short
        for p in RID_PREFIXES:
            if core.startswith(p):
                core = core[len(p):]
                break
        for kw in kws:
            if core.startswith(kw):
                score = -len(short)       # 越短的 rid 越可能是叶子按钮本身
                if best is None or score > best[0]:
                    best = (score, rid, n["center"], n["size"])
                break
    if best is None:
        return None
    return best[1], best[2], best[3]



def analyze(app, app_dir):
    land = os.path.join(app_dir, "ui.xml")
    aft = os.path.join(app_dir, "ui_after.xml")
    lnodes = parse_nodes(open(land, encoding="utf-8").read()) if os.path.exists(land) else []
    anodes = parse_nodes(open(aft, encoding="utf-8").read()) if os.path.exists(aft) else []
    plan = []
    for bid, actions in (app.get("behaviors") or {}).items():
        if not actions:
            continue
        vi, si, act = first_anchor_action(actions)
        if act is None:
            continue
        cands = candidates_of(act)
        ln = hit_native(lnodes, cands)
        lc = hit_cross(lnodes, cands)
        an = hit_native(anodes, cands)
        ac = hit_cross(anodes, cands)
        if ln:
            plan.append({"behavior": bid, "action": "keep",
                         "why": f"首屏已命中 {ln[0]}={ln[1]}"})
        elif lc:
            plan.append({"behavior": bid, "action": "candidate",
                         "why": f"首屏只在 {lc[0]} 语义命中 {lc[1]!r}"
                                f"（候选声明的是其它语义，执行器会漏）",
                         "suggest": {"type": lc[0], "value": lc[1]}})
        elif an:
            plan.append({"behavior": bid, "action": "prelude",
                         "why": f"首屏无、二级页命中 {an[0]}={an[1]}"})
        elif ac:
            plan.append({"behavior": bid, "action": "prelude",
                         "why": f"首屏无、二级页只在 {ac[0]} 语义命中 {ac[1]!r}",
                         "suggest": {"type": ac[0], "value": ac[1]}})
        else:
            kws = BEHAVIOR_KEYWORDS.get(bid, [])
            alt = scan_keywords(anodes, kws) or scan_keywords(lnodes, kws)
            if alt:
                label, kind, kw, center = alt[0]
                plan.append({"behavior": bid, "action": "candidate",
                             "why": f"两页均未命中；发现可用锚点 "
                                    f"{kind}={label!r} @{center}（关键词 {kw}）",
                             "suggest": {"type": kind, "value": kw}})
            else:
                # 文本/desc 都没有 -> 退到 rid 语义（纯图标按钮）
                rid = scan_rid(anodes, bid)
                page = "二级页"
                if rid is None:
                    rid = scan_rid(lnodes, bid)
                    page = "首屏"
                if rid:
                    rv, center, size = rid
                    plan.append({"behavior": bid, "action": "rid",
                                 "why": f"两页均无文本锚点；发现 rid 锚点 "
                                        f"{rv!r} @{center} sz={size}（{page}）",
                                 "suggest": {"type": "id", "value": rv}})
                else:
                    plan.append({"behavior": bid, "action": "manual",
                                 "why": "两页均无可用文本/rid 锚点，"
                                        "需 click_point 坐标 / VLM 专项"})
    return plan


def apply_prelude(path, app_name, behaviors):
    """在指定 App 的这些行为最前面插入导航前置步。"""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")
    # 定位 App 块
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- name: {app_name}":
            start = i
            break
    if start is None:
        # 拆分后 App 级文件：整文件即一个 App 块（首行 `name: xxx`）
        if lines and lines[0].strip() == f"name: {app_name}":
            start = 0
        else:
            return 0
    end = len(lines)
    if start != 0:
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("- name: "):
                end = j
                break
    # 从后往前插，避免行号漂移
    ind = 4
    for k in range(start, end):
        s = lines[k].rstrip()
        if s.endswith(":") and s.strip() == "behaviors":
            ind = len(s) - len(s.lstrip()) + 2
            break
    targets = []
    for k in range(start, end):
        s = lines[k]
        if s.startswith(" " * ind) and not s.startswith(" " * (ind + 1)) and s.rstrip().endswith(":"):
            bid = s.strip().rstrip(":")
            if bid in behaviors:
                targets.append(k)
    inserted = 0
    for k in sorted(targets, reverse=True):
        # 幂等守卫：若行为块开头已是导航前置步，则跳过，避免重复插入
        nxt = lines[k + 1:k + 1 + len(NAV_ACTION)]
        if nxt == list(NAV_ACTION):
            continue
        lines[k + 1:k + 1] = list(NAV_ACTION)
        inserted += 1
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写回 config.yaml")
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    ap.add_argument("--out", default=os.path.join(HERE, "calib",
                                                  "FIX_PLAN.md"))
    args = ap.parse_args()

    cfg = load_cfg()
    apps = {a.get("name"): a for a in (cfg.get("apps") or [])}
    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None

    md = ["# 锚点修补计划（数据驱动）", "",
          "> 依据 `devtools/calib/<app>/ui.xml`（首屏）与 `ui_after.xml`（二级页）。",
          "> `prelude` = 在行为最前面插一步导航到「我的」；`candidate` = 追加候选；",
          "> `rid` = 纯图标按钮，用 resource-id 锚定；`manual` = 需人工给坐标/VLM。", ""]
    counts = {"keep": 0, "prelude": 0, "candidate": 0, "rid": 0, "manual": 0}
    prelude_by_app = {}

    for name in sorted(apps):
        if only and name not in only:
            continue
        app_dir = os.path.join(HERE, "calib", name)
        if not os.path.isdir(app_dir):
            continue
        plan = analyze(apps[name], app_dir)
        if not plan:
            continue
        md.append(f"## {name}  (`{apps[name].get('package')}`)")
        md.append("")
        md.append("| 行为 | 处置 | 依据 |")
        md.append("|---|---|---|")
        for p in plan:
            counts[p["action"]] += 1
            md.append(f"| {p['behavior']} | {p['action']} | {p['why']} |")
            if p["action"] == "prelude":
                prelude_by_app.setdefault(name, []).append(p["behavior"])
        md.append("")

    md += ["## 统计", "",
           f"- 保持不动: {counts['keep']}",
           f"- 加导航前置步(prelude): {counts['prelude']}",
           f"- 追加候选(candidate): {counts['candidate']}",
           f"- rid 锚点(rid): {counts['rid']}",
           f"- 需人工(manual): {counts['manual']}", ""]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"计划已写出: {args.out}")
    print(f"keep={counts['keep']} prelude={counts['prelude']} "
          f"candidate={counts['candidate']} rid={counts['rid']} "
          f"manual={counts['manual']}")

    if args.apply and prelude_by_app:
        total = 0
        for name, bids in prelude_by_app.items():
            path = app_config_path(name)
            bak = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(path, bak)
            print(f"已备份: {bak}")
            n = apply_prelude(path, name, set(bids))
            print(f"  {name}: 插入 {n} 处导航前置步")
            total += n
        print(f"共插入 {total} 处")
        # 立刻校验可加载
        cfg2 = load_cfg()
        print(f"复验: config 加载成功, {len(cfg2.get('apps') or [])} 个 app")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/preflight.py`（172 行）

```python
# -*- coding: utf-8 -*-
"""preflight.py - 环境自检（接手/排障第一步）

一次跑完，输出可读报告：
  1. Python 与关键依赖（uiautomator2 / yaml / PIL / cv2 / requests）
  2. adb 解析结果 + 设备在线状态 + 屏幕参数 + 前台包名
  3. 截图链路（字节数 + PNG 魔数校验）
  4. VLM 网关 /models 可达性
  5. config.yaml 可加载 + app 数量与行为分布

用法：
    python devtools/preflight.py [--serial 192.168.1.54:5555] [--config config.yaml]
退出码：0 全部通过；1 有 FAIL 项（WARN 不影响退出码）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from config_loader import load_config  # noqa: E402

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"
_results = []


def rec(level, name, detail=""):
    _results.append((level, name, detail))
    print(f"[{level}] {name}" + (f" -> {detail}" if detail else ""))


def check_python():
    rec(OK, "Python", sys.version.split()[0])
    mods = {"uiautomator2": "uiautomator2", "yaml": "PyYAML",
            "PIL": "Pillow", "cv2": "opencv-python", "requests": "requests"}
    missing = []
    for mod, pkg in mods.items():
        try:
            __import__(mod)
            rec(OK, f"依赖 {pkg}")
        except ImportError:
            missing.append(pkg)
            rec(WARN, f"依赖 {pkg}", "未安装（模板匹配/VLM 相关能力会降级）")
    return missing


def check_adb(serial):
    from adbkit import Adb, resolve_adb
    try:
        adb_path = resolve_adb()
    except FileNotFoundError as e:
        rec(FAIL, "adb 解析", str(e))
        return None
    rec(OK, "adb 路径", adb_path)
    a = Adb(serial=serial, adb_path=adb_path)
    try:
        got = a.ensure(serial)
        rec(OK, "设备在线", got)
    except Exception as e:
        rec(FAIL, "设备连接", f"{type(e).__name__}: {e}")
        return None
    try:
        w, h = a.screen_size()
        rec(OK, "屏幕分辨率", f"{w}x{h}")
        rec(OK if a.is_screen_on() else WARN, "屏幕点亮",
            "awake" if a.is_screen_on() else "熄屏/锁屏 —— 需先唤醒")
        rec(OK, "前台包名", a.foreground() or "(未识别)")
    except Exception as e:
        rec(WARN, "设备信息", f"{type(e).__name__}: {e}")
    try:
        data = a.screenshot_bytes()
        rec(OK, "截图链路", f"{len(data)} 字节, PNG 魔数校验通过")
    except Exception as e:
        rec(FAIL, "截图链路", f"{type(e).__name__}: {e}")
    return a


def check_vlm(cfg):
    vlm = ((cfg or {}).get("vision") or {}).get("vlm") or {}
    base = (vlm.get("base_url") or "").rstrip("/")
    key = vlm.get("api_key") or ""
    if not base:
        rec(WARN, "VLM 网关", "config.yaml 未配置 vision.vlm.base_url")
        return
    url = base + "/models"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", "replace")
        ids = []
        try:
            ids = [m.get("id") for m in json.loads(body).get("data", [])]
        except Exception:
            pass
        want = vlm.get("model")
        hit = want in ids
        rec(OK if hit else WARN, "VLM 网关",
            f"{url} HTTP 200, 主模型 {want} {'可用' if hit else '不在模型列表'}"
            f" (共 {len(ids)} 个模型)")
    except Exception as e:
        rec(FAIL, "VLM 网关", f"{url} 不可达: {type(e).__name__}: {e}")


def check_config(path):
    if not os.path.exists(path):
        rec(FAIL, "config.yaml", f"不存在: {path}")
        return {}
    try:
        cfg = load_config(path)
    except Exception as e:
        rec(FAIL, "config.yaml 解析", f"{type(e).__name__}: {e}")
        return {}
    apps = cfg.get("apps") or []
    rec(OK, "config.yaml", f"加载成功, {len(apps)} 个 app")
    dist = {}
    no_behavior = []
    for app in apps:
        bh = app.get("behaviors") or {}
        if not bh:
            no_behavior.append(app.get("name"))
        for k in bh:
            dist[k] = dist.get(k, 0) + 1
    rec(OK, "行为分布", ", ".join(f"{k}={v}" for k, v in sorted(dist.items())))
    if no_behavior:
        rec(WARN, "无行为配置的 app", ", ".join(map(str, no_behavior)))
    missing_pkg = [a.get("name") for a in apps if not a.get("package")]
    if missing_pkg:
        rec(WARN, "缺少 package", ", ".join(map(str, missing_pkg)))
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=None)
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    args = ap.parse_args()

    print("=" * 62)
    print("Android Autopilot 环境自检")
    print("=" * 62)
    print("-- 1. Python / 依赖 --")
    check_python()

    print("\n-- 2. config.yaml --")
    cfg = check_config(args.config)
    serial = args.serial or ((cfg.get("device") or {}).get("serial"))

    print("\n-- 3. 设备 / adb --")
    check_adb(serial)

    print("\n-- 4. VLM 网关 --")
    check_vlm(cfg)

    fails = [r for r in _results if r[0] == FAIL]
    warns = [r for r in _results if r[0] == WARN]
    print("\n" + "=" * 62)
    print(f"结果: {len(_results)} 项检查, FAIL={len(fails)}, WARN={len(warns)}")
    if fails:
        for lvl, name, detail in fails:
            print(f"  FAIL: {name} -> {detail}")
    print("=" * 62)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/probe_deep.py`（365 行）

````python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三级导航探针：验证「我的 → 任务中心/福利 → 签到」这条路径是否成立。

背景
----
剩余缺口里 `sign` 类占 8/16。签到入口普遍不在「我的」首层，
而在「我的 → 任务中心 / 福利」子页里。现有配置只表达到第二层，
所以这类行为必然未命中。

本工具做的事：
    启动 App → 等待就绪 → 关弹窗 → 点「我的」
      → dump：在二级页找「任务中心/福利/赚钱/金币…」入口
        → 找到就点进去
          → dump：在三级页找目标锚点（签到/看视频/提现…）
            → 报告命中情况 + 存三级页截图供目视复核

产物：
    devtools/calib/<app>/deep_<behavior>_L2.png / _L3.png
    devtools/calib/DEEP_PROBE.md / .json

用法：
    python devtools/probe_deep.py --apps 一淘,河马剧场 --behaviors sign
    python devtools/probe_deep.py                 # 默认跑全部 sign 缺口
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from config_loader import load_config  # noqa: E402
from calibrate import (  # noqa: E402
    parse_nodes, match_selector, wait_ready, dismiss_popups,
    connect_device, safe_name, page_belongs_to,
)

# 默认目标：本轮实机回归里未命中的 sign 行为
DEFAULT_TARGETS = [
    ("一淘", "sign"),
    ("今日看点极速版", "sign"),
    ("天天快讯极速版", "sign"),
    ("蛋花免费小说", "sign"),
    ("喜番免费短剧", "sign"),
    ("河马剧场", "sign"),
    ("悟空浏览器", "sign"),
    ("抖音火山版", "sign"),
]

# 二级页上的「任务/福利」入口候选（按优先级）。
# 末尾几项来自实机 dump 里见过的真实文案（点淘「元宝中心」等）。
L2_CANDIDATES = [
    "任务中心", "福利中心", "我的福利", "福利", "赚钱", "金币",
    "领金币", "天天领", "做任务", "任务", "钱包", "现金",
    "元宝中心", "金币中心", "福利商城", "任务广场", "赚金币",
    "看剧赚钱", "看书赚钱", "看视频赚钱", "我的金币", "现金奖励",
]

# 目标锚点（三级页上要找的东西）
# 注意：sign 里**不要**放裸的「打卡」—— 实测会误报「喝水打卡」「早起打卡」
# 这类与每日签到无关的任务（今日看点极速版的 我的 页就有「喝水打卡」）。
L3_KEYWORDS = {
    "sign": ["签到", "每日签到", "立即签到", "去签到", "已签到",
             "签到领金币", "签到得金币", "连续签到", "签到打卡"],
    "watch": ["看视频", "看剧赚钱", "去完成", "任务", "赚钱"],
    "withdraw": ["提现", "立即提现", "余额", "可提现"],
    "bonus": ["领红包", "开宝箱", "领取", "红包"],
    "collect": ["任务中心", "去领取", "领取", "福利"],
}

MINE_XY = (0.90, 0.915)


def find_all(nodes, keywords, limit=6):
    """按关键词顺序收集**多个**候选入口（按 label+center 去重，可点击优先）。

    为什么要多个：实测「我的」页上常有多个任务/福利类入口，
    签到可能只在其中某一个里面（例如天天快讯极速版要进「福利中心」，
    蛋花的「福利」页里却没有签到）。只试第一个会漏判。

    为什么不做「必须可点击」的硬过滤：实测入口文案常常挂在**不可点击的
    text 子节点**上，真正可点的是它的父容器（一淘的「去福狸中心做任务」
    就是这种）。硬过滤会把入口整个滤掉。所以只做**排序**（可点击在前），
    点击时用文案中心坐标，uiautomator2 会命中其上层容器。
    """
    out, seen = [], set()
    for kw in keywords:
        for kind in ("text", "desc"):
            hits = match_selector(nodes, kind, kw)
            hits = [h for h in hits if _ok_len(h, kw, kind)]
            hits.sort(key=lambda h: (not h["clickable"], len(
                h["text"] if kind == "text" else h["desc"])))
            for h in hits:
                lab = (h["text"] or h["desc"]).strip()
                key = (lab, h["center"])
                if key in seen:
                    continue
                seen.add(key)
                out.append((lab, h["center"], kind))
                if len(out) >= limit:
                    return out
    return out


def find_first(nodes, keywords, require_clickable=False):
    """按关键词顺序找节点，返回 (label, center, kind)。

    排序上**可点击优先**；`require_clickable=True` 时才硬过滤 ——
    仅在「判断这是不是一个入口」且不能容忍标签误报时使用。
    """
    for kw in keywords:
        for kind in ("text", "desc"):
            hits = match_selector(nodes, kind, kw)
            hits = [h for h in hits if _ok_len(h, kw, kind)]
            if require_clickable:
                hits = [h for h in hits if h["clickable"]]
            if hits:
                hits.sort(key=lambda h: (not h["clickable"], len(
                    h["text"] if kind == "text" else h["desc"])))
                h = hits[0]
                lab = (h["text"] or h["desc"]).strip()
                return lab, h["center"], kind
    return None


def _ok_len(node, target, kind):
    """长度闸门 —— 与执行器 pick_locate.pick_best 同口径（度量与执行同口径纪律）。

    2026-10-28 改造：旧版「超长且不可点 = 一律滤掉」会连营销后缀按钮一起扔
    （'立即签到 +1000火龙币'、'京东金融通知：签到即将中断' 旁的真入口）。
    现改为复用 pick_locate 的句式甄别：噪声句式（FAQ/通知/说明句）照旧滤除，
    其余超长文案放行给排序层（可点击优先 + 短文本优先，超长非可点自然沉底）。
    """
    if kind not in ("text", "desc"):
        return True
    label = node["text"] if kind == "text" else node["desc"]
    limit = max(len(str(target)) + 6, len(str(target)) * 3)
    if len(label) <= limit or node["clickable"]:
        return True
    try:
        from pick_locate import is_noise_label
        return not is_noise_label(label, target)
    except ImportError:  # pragma: no cover - 探针单独拷走时退回旧硬滤
        return False


def probe_one(d, app_cfg, behavior, log, max_l2=3):
    name, pkg = app_cfg["name"], app_cfg["package"]
    outdir = os.path.join(HERE, "calib", safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    res = {"app": name, "behavior": behavior, "l2": None, "l3": None,
           "l2_xy": None, "l3_xy": None, "shot_l2": None, "shot_l3": None,
           "on_l2": None}

    ok_page, dom, mine, dom_n, fg = False, "", 0, 0, ""
    for attempt in (1, 2):
        try:
            d.app_start(pkg, wait=True)
        except Exception as e:
            log.append(f"启动异常: {type(e).__name__}: {e}")
        xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
        log.append(f"就绪: 节点={len(nodes)} 等待={waited:.1f}s")
        dismiss_popups(d, nodes, log)
        try:
            fg = d.info.get("currentPackageName") or ""
        except Exception:
            fg = ""
        # 归属以 dump 自身为准（前台包名在崩溃/切换时序下会失真）
        ok_page, dom, mine, dom_n = page_belongs_to(xml, pkg)
        log.append(f"归属校验: 主导包={dom}（{dom_n} 节点） 目标包={mine} 节点"
                   f" 前台={fg} -> {'属于目标 App' if ok_page else '不属于'}")
        if ok_page:
            break
        log.append("归属校验失败，重试")
        time.sleep(3)
    if not ok_page:
        log.append(f"归属校验最终失败（主导包 {dom}），作废")
        res["error"] = f"页面非目标App(主导={dom})"
        return res

    # 第一层：点「我的」
    w, h = d.window_size()
    x, y = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
    log.append(f"点『我的』({x},{y})")
    d.click(x, y)
    time.sleep(3.5)
    xml2 = d.dump_hierarchy()
    nodes2 = parse_nodes(xml2)
    dismiss_popups(d, nodes2, log)
    ok2, dom2, _m2, _d2 = page_belongs_to(xml2, pkg)
    log.append(f"二级页节点={len(nodes2)} 主导包={dom2}"
               f"{'' if ok2 else ' -> 已离开目标 App，作废'}")
    if not ok2:
        res["error"] = f"二级页非目标App(主导={dom2})"
        return res
    try:
        p = os.path.join(outdir, f"deep_{behavior}_L2.png")
        d.screenshot(p)
        res["shot_l2"] = p
    except Exception as e:
        log.append(f"二级页截图失败: {e}")

    # 有些 App 的签到入口**就在二级页**（「我的」页本身就有签到按钮），
    # 先就地找一次，避免漏判成「不可救」。
    # 两段式：先找可点击的（真入口），没有再退而求其次找文案（可能是标签，
    # 结果标注 [低置信]，人工复核时优先看这类）。
    hit_on_l2 = find_first(nodes2, L3_KEYWORDS.get(behavior, []),
                           require_clickable=True)
    low_conf = False
    if hit_on_l2 is None:
        hit_on_l2 = find_first(nodes2, L3_KEYWORDS.get(behavior, []))
        low_conf = hit_on_l2 is not None
    if hit_on_l2 is not None:
        lab, c, kind = hit_on_l2
        res["on_l2"] = f"{kind}={lab}" + (" [低置信]" if low_conf else "")
        res["l2_xy"] = c
        log.append(f"★ 二级页即命中: {kind}={lab!r} @{c}"
                   + ("（不可点击，可能只是标签，需人工复核）" if low_conf
                      else "（可点击入口，无需三级导航）"))
        return res

    # 第二层：收集「任务中心/福利」类入口，依次尝试
    entries = find_all(nodes2, L2_CANDIDATES, limit=max_l2)
    if not entries:
        log.append("二级页未找到任务/福利入口")
        return res
    log.append(f"二级页候选入口 {len(entries)} 个: "
               f"{[f'{lab}@{c}' for lab, c, _ in entries]}")
    res["attempts"] = []
    for idx, (lab2, c2, kind2) in enumerate(entries):
        if idx:
            # 回到「我的」页再试下一个入口
            try:
                d.press("back")
                time.sleep(2.0)
                d.click(int(MINE_XY[0] * w), int(MINE_XY[1] * h))
                time.sleep(3.0)
            except Exception as e:
                log.append(f"回退失败: {type(e).__name__}: {e}")
        log.append(f"[{idx + 1}/{len(entries)}] 点入口 {kind2}={lab2!r} @{c2}")
        d.click(c2[0], c2[1])
        time.sleep(3.5)
        xml3 = d.dump_hierarchy()
        nodes3 = parse_nodes(xml3)
        dismiss_popups(d, nodes3, log)
        ok3, dom3, _m3, _d3 = page_belongs_to(xml3, pkg)
        log.append(f"  三级页节点={len(nodes3)} 主导包={dom3}"
                   f"{'' if ok3 else ' -> 已离开目标 App，本次作废'}")
        if not ok3:
            res["attempts"].append({"l2": f"{kind2}={lab2}", "l3": None,
                                    "error": f"页面非目标App(主导={dom3})"})
            continue
        try:
            p = os.path.join(outdir, f"deep_{behavior}_L3_{idx + 1}.png")
            d.screenshot(p)
            res["shot_l3"] = p
        except Exception as e:
            log.append(f"三级页截图失败: {e}")
        hit3 = find_first(nodes3, L3_KEYWORDS.get(behavior, []))
        if hit3 is None:
            log.append("  三级页未找到目标锚点")
            res["attempts"].append({"l2": f"{kind2}={lab2}", "l3": None})
            continue
        lab3, c3, kind3 = hit3
        res["l2"] = f"{kind2}={lab2}"
        res["l2_xy"] = c2
        res["l3"] = f"{kind3}={lab3}"
        res["l3_xy"] = c3
        res["attempts"].append({"l2": f"{kind2}={lab2}",
                                "l3": f"{kind3}={lab3}"})
        log.append(f"  ★ 三级页命中: {kind3}={lab3!r} @{c3}")
        return res
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None)
    ap.add_argument("--behaviors", default=None)
    ap.add_argument("--max-l2", type=int, default=3,
                    help="每个 App 最多依次尝试几个二级入口（默认 3）")
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "DEEP_PROBE.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "DEEP_PROBE.json"))
    args = ap.parse_args()

    cfg = load_config(args.config)
    apps = {a["name"]: a for a in (cfg.get("apps") or []) if a.get("name")}
    only_a = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None

    targets = [(a, b) for a, b in DEFAULT_TARGETS
               if (not only_a or a in only_a) and (not only_b or b in only_b)]
    print(f"待探针: {len(targets)} 项 -> {targets}")

    serial = (cfg.get("device") or {}).get("serial")
    d = connect_device(serial)

    results, logs = [], {}
    for app, beh in targets:
        if app not in apps:
            print(f"跳过（配置无此 App）: {app}")
            continue
        print(f"\n===== {app} / {beh} =====")
        log = []
        try:
            r = probe_one(d, apps[app], beh, log, max_l2=args.max_l2)
        except Exception as e:
            log.append(f"异常: {type(e).__name__}: {e}")
            r = {"app": app, "behavior": beh, "error": str(e)}
        results.append(r)
        logs[f"{app}.{beh}"] = log
        if r.get("l3"):
            print(f"  ★ 三级页命中 {r['l3']} @{r['l3_xy']}（二级入口 {r['l2']}）")
        elif r.get("on_l2"):
            print(f"  ★ 二级页即命中 {r['on_l2']} @{r['l2_xy']}")
        elif r.get("l2"):
            print(f"  二级入口 {r['l2']} 找到，但三级页未命中锚点")
        else:
            print(f"  二级页未找到任务/福利入口（{r.get('error') or ''}）")

    ok3 = sum(1 for r in results if r.get("l3"))
    ok2 = sum(1 for r in results if r.get("on_l2"))
    l2 = sum(1 for r in results if r.get("l2"))
    print(f"\n===== 汇总: 三级页命中 {ok3}/{len(results)}；"
          f"二级页即命中 {ok2}；找到二级入口 {l2} =====")

    md = ["# 三级导航探针报告", "",
          f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial}",
          f"> 三级页命中: {ok3}/{len(results)}；二级页即命中: {ok2}；"
          f"找到二级入口: {l2}", "",
          "| App | 行为 | 二级页即命中 | 尝试过的二级入口 | 命中的入口 | 三级锚点 |",
          "|---|---|---|---|---|---|"]
    for r in results:
        tried = r.get("attempts") or []
        tried_s = "<br>".join(
            f"{a.get('l2')} → {a.get('l3') or ('✗ ' + (a.get('error') or '未命中'))}"
            for a in tried) or "-"
        md.append(f"| {r['app']} | {r['behavior']} | {r.get('on_l2') or '-'} | "
                  f"{tried_s} | {r.get('l2') or '-'} | {r.get('l3') or '-'} |")
    md.append("")
    for k, v in logs.items():
        md.append(f"<details><summary>{k}</summary>")
        md.append("")
        md.append("```")
        md += v
        md.append("```")
        md.append("</details>")
        md.append("")
    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    open(args.md, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(results, open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### `devtools/probe_flow.py`（94 行）

```python
# -*- coding: utf-8 -*-
"""probe_flow.py - 按描述路径逐屏抓锚点（Host 一次性探针）

用法:
  python probe_flow.py <serial> <app_name> <package>
交互: 它会启动App并打印当前屏可点元素(text/id/desc/坐标)。
      输入序号点击元素，输入 d 重新dump，输入 n 进入下一屏(只重新dump)，q 退出。
      每屏的 dump 自动存 devtools/calib/uiprobe/<pkg>/NN.xml + NN.png
"""
import os
import re
import subprocess
import sys

PROJ = os.path.dirname(os.path.abspath(__file))
ADB = os.path.join(PROJ, "tools", "platform-tools", "adb.exe")
OUT = os.path.join(PROJ, "devtools", "calib", "uiprobe")


def sh(*args):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True,
                          text=True, timeout=30, encoding="utf-8", errors="replace").stdout


def parse_nodes(xml):
    out = []
    for m in re.finditer(r'<node\b[^>]*>', xml):
        tag = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', tag) or [None, ""])[1]
        text, rid, desc = g("text"), g("resource-id"), g("content-desc")
        if not (text or rid or desc):
            continue
        b = g("bounds")
        mm = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
        if not mm:
            continue
        l, t, r, bo = map(int, mm.groups())
        out.append({"text": text, "id": rid, "desc": desc, "click": g("clickable"),
                    "rect": (l, t, r, bo)})
    return out


def dump(idx, app_pkg):
    xml = sh("exec-out", "uiautomator", "dump", "/dev/tty")  # fallback below
    xml = sh("exec-out", "cat", "/sdcard/window_dump.xml") if False else xml
    # 用 u2 更稳：shell uiautomator dump 输出到 stdout 需要 /dev/tty 支持
    p = subprocess.run([ADB, "-s", SERIAL, "shell", "uiautomator", "dump",
                        "/sdcard/_probe.xml"], capture_output=True, text=True, timeout=60)
    xml = subprocess.run([ADB, "-s", SERIAL, "exec-out", "cat", "/sdcard/_probe.xml"],
                         capture_output=True, timeout=30).stdout.decode("utf-8", "replace")
    os.makedirs(os.path.join(OUT, app_pkg), exist_ok=True)
    with open(os.path.join(OUT, app_pkg, f"{idx:02d}.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    png = subprocess.run([ADB, "-s", SERIAL, "exec-out", "screencap", "-p"],
                         capture_output=True, timeout=30).stdout
    with open(os.path.join(OUT, app_pkg, f"{idx:02d}.png"), "wb") as f:
        f.write(png)
    return xml


def main():
    global SERIAL
    SERIAL, app_name, app_pkg = sys.argv[1], sys.argv[2], sys.argv[3]
    sh("shell", "am", "force-stop", app_pkg)
    sh("shell", "monkey", "-p", app_pkg, "-c", "android.intent.category.LAUNCHER", "1")
    import time; time.sleep(5)
    idx = 0
    while True:
        xml = dump(idx, app_pkg)
        nodes = parse_nodes(xml)
        clickable = [n for n in nodes if n["click"] == "true"]
        print(f"\n===== 屏 {idx} | 可点元素 {len(clickable)} 个 =====")
        for i, n in enumerate(clickable[:40]):
            lab = n["text"] or n["desc"] or n["id"]
            l, t, r, b = n["rect"]
            print(f"  [{i:2d}] {lab!r} id={n['id'].split('/')[-1]} cx={(l+r)//2} cy={(t+b)//2}")
        cmd = input("点击序号 / d=重dump / n=下一屏 / q=退出: ").strip()
        if cmd == "q":
            break
        if cmd in ("d", "n"):
            idx += int(cmd == "n")
            continue
        try:
            i = int(cmd)
            l, t, r, b = clickable[i]["rect"]
            sh("shell", "input", "tap", str((l + r) // 2), str((t + b) // 2))
            idx += 1
            import time; time.sleep(2.5)
        except (ValueError, IndexError):
            print("无效输入")


if __name__ == "__main__":
    main()
```

### `devtools/probe_manual.py`（263 行）

````python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""manual 项实机探针：为「两页都没有文本锚点」的行为找到可点的视觉入口。

背景：`devtools/plan_anchor_fixes.py` 把 15 个行为判为 manual —— 落地页与
二级页的 dump 里都没有可用文本锚点。这类入口要么是**纯图片按钮**，要么
文案由图片/Canvas 绘制（dump 拿不到）。对此唯一可靠的办法是：

    启动 App -> 等待就绪 -> 导航到『我的』-> 截图
      -> 用 VLM 按「行为专属提示词」定位入口
      -> 命中则记录 (像素, 比例坐标, 生效提示词)，并把截图存盘供人工复核

产物：
    devtools/calib/<app>/manual_<behavior>.png   截图（可直接肉眼看）
    devtools/calib/MANUAL_PROBE.md               探针报告
    devtools/calib/MANUAL_PROBE.json             结构化结果（供写回脚本消费）

用法：
    python devtools/probe_manual.py --apps 抖音,点淘
    python devtools/probe_manual.py                 # 全部 15 个 manual 项
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from config_loader import load_config  # noqa: E402
from calibrate import (  # noqa: E402
    parse_nodes, wait_ready, dismiss_popups, connect_device, safe_name,
)

# (app, behavior) —— 与 FIX_PLAN.md 的 manual 项一致
MANUAL = [
    ("今日看点极速版", "withdraw"),
    ("全民K歌",        "bonus"),
    ("喜番免费短剧",   "sign"),
    ("天天快讯极速版", "sign"),
    ("天天快讯极速版", "watch"),
    ("天天快讯极速版", "withdraw"),
    ("悟空浏览器",     "sign"),
    ("抖音",           "watch"),
    ("抖音",           "bonus"),
    ("抖音极速版",     "watch"),
    ("抖音火山版",     "sign"),
    ("河马剧场",       "sign"),
    ("点淘",           "watch"),
    ("点淘",           "withdraw"),
    ("蛋花免费小说",   "sign"),
]

# 行为专属提示词（按顺序回退，命中即止）
PROMPTS = {
    "sign": [
        "定位页面上『签到』按钮或签到入口的中心",
        "定位『每日签到』或『立即签到』按钮中心",
        "定位『签到领金币』或『已签到』卡片中心",
        "定位页面上『领取』按钮的中心",
    ],
    "watch": [
        "定位『看视频赚金币』任务入口中心",
        "定位『看剧赚钱』或『看视频』按钮中心",
        "定位『任务中心』入口中心",
        "定位『去完成』按钮中心",
    ],
    "bonus": [
        "定位『领红包』或『开宝箱』按钮中心",
        "定位『领取奖励』或『点击领取』按钮中心",
        "定位页面上金币/红包奖励图标的中心",
    ],
    "withdraw": [
        "定位『提现』按钮中心",
        "定位『现金』或『钱包』入口中心",
        "定位『余额』或『可提现』区域的中心",
    ],
    "collect": [
        "定位『任务中心』入口中心",
        "定位『福利』或『领福利』入口中心",
        "定位『去领取』按钮中心",
    ],
}

NAV_PROMPTS = [
    "定位屏幕底部导航栏最右侧的『我的』标签中心",
    "定位屏幕底部导航栏最右侧的『我』标签中心",
    "定位屏幕底部导航栏的个人中心（我的）标签中心",
]
MINE_XY = (0.9, 0.908)


def load_cfg(path):
    return load_config(path)


def goto_mine(d, loc, log):
    """导航到『我的』。返回 (nodes, 是否成功跳到新页)。"""
    x = y = None
    if loc is not None:
        try:
            img = d.screenshot()
            for p in NAV_PROMPTS:
                hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                           app="probe", tag="nav")
                if hit is not None:
                    x, y = hit.x, hit.y
                    log.append(f"导航: VLM 命中『{p}』-> ({x},{y})")
                    break
        except Exception as e:
            log.append(f"导航: VLM 异常 {type(e).__name__}: {e}")
    if x is None:
        w, h = d.window_size()
        x, y = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
        log.append(f"导航: 比例坐标 -> ({x},{y})")
    d.click(x, y)
    time.sleep(3.5)
    return parse_nodes(d.dump_hierarchy())


def probe_one(d, app_cfg, behavior, loc, log):
    name = app_cfg["name"]
    pkg = app_cfg["package"]
    log.append(f"启动 {pkg}")
    for attempt in (1, 2):
        try:
            d.app_start(pkg, wait=True)
        except Exception as e:
            log.append(f"启动异常: {type(e).__name__}: {e}")
        xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
        log.append(f"就绪: 节点={len(nodes)} 等待={waited:.1f}s")
        dismiss_popups(d, nodes, log)
        try:
            fg = d.info.get("currentPackageName") or ""
        except Exception:
            fg = ""
        if fg == pkg or pkg in fg:
            break
        log.append(f"前台={fg} 非目标包，重试一次")
        time.sleep(2)

    nodes = goto_mine(d, loc, log)
    dismiss_popups(d, nodes, log)
    outdir = os.path.join(HERE, "calib", safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    shot = os.path.join(outdir, f"manual_{behavior}.png")
    try:
        d.screenshot(shot)
        log.append(f"截图: {shot}")
    except Exception as e:
        log.append(f"截图失败: {e}")

    res = {"app": name, "behavior": behavior, "hit": False,
           "prompt": None, "xy": None, "ratio": None,
           "shot": shot, "nodes_after": len(nodes)}
    if loc is None:
        log.append("VLM 不可用，仅存截图")
        return res
    for p in PROMPTS.get(behavior, []):
        try:
            img = d.screenshot()
            hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                       app="probe", tag=behavior)
        except Exception as e:
            log.append(f"VLM 异常 {type(e).__name__}: {e}")
            continue
        if hit is not None:
            w, h = d.window_size()
            res.update(hit=True, prompt=p, xy=[hit.x, hit.y],
                       ratio=[round(hit.x / w, 3), round(hit.y / h, 3)])
            log.append(f"VLM 命中『{p}』-> ({hit.x},{hit.y}) "
                       f"ratio=({res['ratio'][0]},{res['ratio'][1]})")
            break
        log.append(f"未命中 -> {p}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    ap.add_argument("--behaviors", default=None, help="逗号分隔，限定行为")
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "MANUAL_PROBE.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "MANUAL_PROBE.json"))
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    apps = {a["name"]: a for a in (cfg.get("apps") or []) if a.get("name")}
    only_a = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None

    targets = [(a, b) for a, b in MANUAL
               if (not only_a or a in only_a) and (not only_b or b in only_b)]
    print(f"待探针: {len(targets)} 项")

    serial = (cfg.get("device") or {}).get("serial")
    d = connect_device(serial)

    loc = None
    try:
        import vision as vs
        cand = vs.VisionLocator(cfg.get("vision") or {}, base_dir=ROOT)
        if cand.enabled and cand.vlm_available:
            loc = cand
            print("VLM: 可用")
        else:
            print("VLM: 不可用（仅存截图）")
    except Exception as e:
        print(f"VLM 初始化失败: {e}")

    results, logs = [], {}
    for app, beh in targets:
        if app not in apps:
            print(f"跳过（配置无此 App）: {app}")
            continue
        print(f"\n===== {app} / {beh} =====")
        log = []
        try:
            r = probe_one(d, apps[app], beh, loc, log)
        except Exception as e:
            log.append(f"探针异常: {type(e).__name__}: {e}")
            r = {"app": app, "behavior": beh, "hit": False,
                 "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        logs[f"{app}.{beh}"] = log
        print(f"  -> {'命中 ' + str(r.get('ratio')) if r.get('hit') else '未命中'}")

    hit = sum(1 for r in results if r.get("hit"))
    print(f"\n===== 探针汇总: 命中 {hit}/{len(results)} =====")

    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    md = ["# manual 项实机探针报告", "",
          f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial}",
          f"> 命中: {hit}/{len(results)}", "",
          "| App | 行为 | 结果 | 比例坐标 | 生效提示词 | 截图 |",
          "|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['app']} | {r['behavior']} | "
                  f"{'命中' if r.get('hit') else '未命中'} | "
                  f"{r.get('ratio') or '-'} | {r.get('prompt') or '-'} | "
                  f"`{os.path.basename(r.get('shot') or '')}` |")
    md.append("")
    for k, v in logs.items():
        md.append(f"<details><summary>{k}</summary>")
        md.append("")
        md.append("```")
        md += v
        md.append("```")
        md.append("</details>")
        md.append("")
    open(args.md, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(results, open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### `devtools/probe_path.py`（100 行）

```python
# -*- coding: utf-8 -*-
"""probe_path.py - 按文案路径自动走屏并 dump 每屏锚点

用法: python probe_path.py <serial> <pkg> <app_name> <text1> <text2> ...
每屏解析可点元素，按文案匹配(text/desc/id 精确优先、包含次之)点击；
未命中则把该屏可点元素全打印出来(便于补候选)。
"""
import os
import re
import subprocess
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJ, "tools", "platform-tools", "adb.exe")
OUT = os.path.join(PROJ, "devtools", "calib", "uiprobe")
SERIAL = None


def sh(*args):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True,
                          text=True, timeout=60, encoding="utf-8", errors="replace").stdout


def sh_bin(*args):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True, timeout=60).stdout


def parse_nodes(xml):
    out = []
    for m in re.finditer(r'<node\b[^>]*>', xml):
        tag = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', tag) or [None, ""])[1]
        text, rid, desc = g("text"), g("resource-id"), g("content-desc")
        b = g("bounds")
        mm = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
        if not mm:
            continue
        l, t, r, bo = map(int, mm.groups())
        out.append({"text": text, "id": rid, "desc": desc, "click": g("clickable"),
                    "rect": (l, t, r, bo)})
    return out


def dump(idx, pkg, app_name):
    subprocess.run([ADB, "-s", SERIAL, "shell", "uiautomator", "dump",
                    "/sdcard/_probe.xml"], capture_output=True, timeout=60)
    xml = sh_bin("exec-out", "cat", "/sdcard/_probe.xml").decode("utf-8", "replace")
    d = os.path.join(OUT, pkg.replace(".", "_"))
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"{idx:02d}.xml"), "w", encoding="utf-8").write(xml)
    open(os.path.join(d, f"{idx:02d}.png"), "wb").write(
        sh_bin("exec-out", "screencap", "-p"))
    return xml


def find_and_tap(nodes, label):
    cands = [n for n in nodes if (n["text"] or n["desc"] or n["id"]).strip() == label]
    if not cands:
        cands = [n for n in nodes if label in (n["text"] or n["desc"] or "")]
    if not cands:
        return None
    # 优先可点击、短的文案（同 _pick_best 精神）
    cands.sort(key=lambda n: (n["click"] != "true",
                              -len(n["text"] or n["desc"] or "")))
    n = cands[0]
    l, t, r, b = n["rect"]
    sh("shell", "input", "tap", str((l + r) // 2), str((t + b) // 2))
    return n


def main():
    global SERIAL
    SERIAL, pkg, app_name, *labels = sys.argv[1:]
    sh("shell", "am", "force-stop", pkg)
    sh("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(5)
    xml = dump(0, pkg, app_name)
    for i, label in enumerate(labels, 1):
        nodes = parse_nodes(xml)
        hit = find_and_tap(nodes, label)
        if hit:
            lab = hit['text'] or hit['desc'] or hit['id']
            msg = f"\n--- 目标[{i}] {label!r} -> 命中 {lab!r} @{hit['rect']}"
        else:
            msg = f"\n--- 目标[{i}] {label!r} -> 未命中!"
        print(msg)
        if not hit:
            print("本屏可点元素(前40):")
            for n in [x for x in nodes if x["click"] == "true"][:40]:
                lab = n["text"] or n["desc"] or n["id"]
                print(f"   {lab!r} id={n['id'].split('/')[-1]} rect={n['rect']}")
            break
        time.sleep(3)
        xml = dump(i, pkg, app_name)
    print(f"\nDONE dumps -> devtools/calib/uiprobe/{pkg.replace('.', '_')}/")


if __name__ == "__main__":
    main()
```

### `devtools/probe_path_u2.py`（122 行）

```python
# -*- coding: utf-8 -*-
"""probe_path_u2.py - 用 uiautomator2 按文案路径走屏 dump 锚点（走项目真实链路）

用法: python probe_path_u2.py <serial> <pkg> <app_name> <text1> <text2> ...
每屏 dump_xml，按 text/desc/id 精确->包含匹配点击；未命中打印本屏可点元素。
"""
import os
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
OUT = os.path.join(PROJ, "devtools", "calib", "uiprobe")


def parse_nodes(xml):
    import re
    out = []
    for m in re.finditer(r'<node\b[^>]*>', xml):
        tag = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', tag) or [None, ""])[1]
        text, rid, desc = g("text"), g("resource-id"), g("content-desc")
        b = g("bounds")
        mm = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
        if not mm:
            continue
        l, t, r, bo = map(int, mm.groups())
        out.append({"text": text, "id": rid, "desc": desc, "click": g("clickable"),
                    "clickable": g("clickable") == "true", "rect": (l, t, r, bo)})
    return out


def find_and_tap(d, label):
    xml = d.dump_hierarchy()
    nodes = parse_nodes(xml)
    cands = [n for n in nodes if (n["text"] or n["desc"] or "").strip() == label]
    if not cands:
        cands = [n for n in nodes if label and label in (n["text"] or n["desc"] or "")]
    if not cands:
        return None, nodes
    cands.sort(key=lambda n: (not n["clickable"], -len(n["text"] or n["desc"] or "")))
    n = cands[0]
    l, t, r, b = n["rect"]
    d.click((l + r) // 2, (t + b) // 2)
    return n, nodes


def dump(d, idx, pkg, app_name):
    xml = d.dump_hierarchy()
    dd = os.path.join(OUT, pkg.replace(".", "_"))
    os.makedirs(dd, exist_ok=True)
    open(os.path.join(dd, f"{idx:02d}.xml"), "w", encoding="utf-8").write(xml)
    png = d.screenshot()
    png.save(os.path.join(dd, f"{idx:02d}.png"))
    return xml


def has_text(xml, kw):
    return kw in xml


def skip_splash(d, max_rounds=10):
    """开屏广告处理：优先文案节点，其次右下角坐标(1080x2340基准按比例)。"""
    for i in range(max_rounds):
        xml = d.dump_hierarchy()
        nodes = parse_nodes(xml)
        hit = None
        for n in nodes:
            lab = (n["text"] or n["desc"] or "").strip()
            if lab in ("跳过", "跳过广告", "skip", "Skip", "关闭广告"):
                hit = n
                break
        if hit:
            l, t, r, b = hit["rect"]
            print(f"   [splash] 文案命中 {hit['text'] or hit['desc']!r} @{hit['rect']}")
            d.click((l + r) // 2, (t + b) // 2)
        elif "广告" in xml and "跳过" in xml:
            pass  # 上面的循环已覆盖
        elif has_text(xml, "广告") or len(nodes) < 5:
            # 自定义绘制广告：XML 不可点，按右下角比例点击
            w, h = d.info["displayWidth"], d.info["displayHeight"]
            print(f"   [splash] 自定义广告，点击右下角 x={int(w*.93)} y={int(h*.915)}")
            d.click(int(w * 0.93), int(h * 0.915))
        else:
            return True  # 无广告特征
        time.sleep(2)
    return False


def main():
    import uiautomator2 as u2
    serial, pkg, app_name, *labels = sys.argv[1:]
    d = u2.connect(serial)
    d.app_stop(pkg)
    d.app_start(pkg)
    time.sleep(5)
    if not skip_splash(d):
        print("!! 开屏广告未跳过")
    time.sleep(2)
    xml = dump(d, 0, pkg, app_name)
    for i, label in enumerate(labels, 1):
        hit, _ = find_and_tap(d, label)
        if hit:
            lab = hit["text"] or hit["desc"] or hit["id"]
            print(f"--- [{i}] {label!r} -> 命中 {lab!r} @{hit['rect']}")
            time.sleep(3)
            xml = dump(d, i, pkg, app_name)
        else:
            print(f"--- [{i}] {label!r} -> 未命中!")
            nodes = parse_nodes(xml)
            shown = [x for x in nodes if (x["text"] or x["desc"] or "").strip()]
            if not shown:
                shown = nodes
            for n in shown[:60]:
                lab = n["text"] or n["desc"] or n["id"]
                print(f"   {'C' if n['clickable'] else '-'} {lab!r} id={n['id'].split('/')[-1]} rect={n['rect']}")
            break
    print(f"DONE -> devtools/calib/uiprobe/{pkg.replace('.', '_')}/")


if __name__ == "__main__":
    main()
```

### `devtools/probe_sidebar.py`（244 行）

````python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抖音系「≡ 更多」侧边栏探针。

背景
----
抖音 / 抖音极速版 / 抖音火山版的「我的」页是**纯个人主页**，
金币/任务入口不在页面上，而在右上角 `≡ 更多`（实机 dump 里是
`content-desc="更多"`、中心约 (984, 174)）弹出的**侧边栏**里。
单步前置步覆盖不了，需要「我的 → ≡更多 → 目标」两级菜单。

本工具做的事：
    启动 → 等就绪 → 点「我的」→ 点「更多」→ dump 侧边栏
      → 报告侧边栏里的全部可点条目（文案 / rid / 坐标）
      → 顺便标注命中了哪些行为关键词（金币/任务/福利/签到/提现…）
      → 存截图供目视复核

产物：
    devtools/calib/<app>/sidebar.png
    devtools/calib/SIDEBAR_PROBE.md / .json

用法：
    python devtools/probe_sidebar.py
    python devtools/probe_sidebar.py --apps 抖音极速版
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from config_loader import load_config  # noqa: E402

from calibrate import (  # noqa: E402
    parse_nodes, wait_ready, dismiss_popups, connect_device, safe_name,
    page_belongs_to,
)

DEFAULT_APPS = ["抖音", "抖音极速版", "抖音火山版"]

# 「更多」按钮的定位方式（实机 dump 实测：content-desc="更多" @ (984,174)）
MORE_DESC = "更多"
MORE_XY_FALLBACK = (0.911, 0.074)      # 984/1080, 174/2340

MINE_XY = (0.90, 0.915)

# 侧边栏条目里我们关心的行为关键词
BEHAVIOR_KEYWORDS = {
    "sign": ["签到", "打卡", "每日"],
    "watch": ["看视频", "刷视频", "视频", "任务", "赚钱", "金币"],
    "withdraw": ["提现", "钱包", "现金", "余额", "收益"],
    "bonus": ["红包", "宝箱", "抽奖", "领取", "福利"],
    "collect": ["任务中心", "福利", "领取", "金币"],
}


def find_more(nodes):
    """找「更多」按钮：优先 content-desc 精确/包含，其次比例坐标。"""
    for n in nodes:
        if (n["desc"] or "").strip() == MORE_DESC and n["clickable"]:
            return n["center"], "desc精确"
    for n in nodes:
        if MORE_DESC in (n["desc"] or "") and n["clickable"]:
            return n["center"], "desc包含"
    return None, "未找到"


def probe_one(d, app_cfg, log):
    name, pkg = app_cfg["name"], app_cfg["package"]
    outdir = os.path.join(HERE, "calib", safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    res = {"app": name, "package": pkg, "more_xy": None, "more_via": None,
           "items": [], "hits": {}, "shot": None, "error": None}

    ok_page, dom, mine, dom_n, fg = False, "", 0, 0, ""
    for attempt in (1, 2):
        try:
            d.app_start(pkg, wait=True)
        except Exception as e:
            log.append(f"启动异常: {type(e).__name__}: {e}")
        xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
        log.append(f"就绪: 节点={len(nodes)} 等待={waited:.1f}s")
        dismiss_popups(d, nodes, log)
        try:
            fg = d.info.get("currentPackageName") or ""
        except Exception:
            fg = ""
        ok_page, dom, mine, dom_n = page_belongs_to(xml, pkg)
        log.append(f"归属校验: 主导包={dom}（{dom_n} 节点） 目标包={mine} 节点"
                   f" -> {'属于目标 App' if ok_page else '不属于'}")
        if ok_page:
            break
        log.append("归属校验失败，重试")
        time.sleep(3)
    if not ok_page:
        res["error"] = f"页面非目标App(主导={dom})"
        log.append(f"归属校验最终失败（主导包 {dom}），作废")
        return res

    # 第一层：点「我的」
    w, h = d.window_size()
    mx, my = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
    log.append(f"点『我的』({mx},{my})")
    d.click(mx, my)
    time.sleep(3.5)
    xml2 = d.dump_hierarchy()
    nodes2 = parse_nodes(xml2)
    dismiss_popups(d, nodes2, log)
    ok2, dom2, _, _ = page_belongs_to(xml2, pkg)
    log.append(f"二级页节点={len(nodes2)} 主导包={dom2}")
    if not ok2:
        res["error"] = f"二级页非目标App(主导={dom2})"
        return res

    # 第二层：点「更多」
    xy, via = find_more(nodes2)
    if xy is None:
        xy = (int(MORE_XY_FALLBACK[0] * w), int(MORE_XY_FALLBACK[1] * h))
        log.append(f"未在 dump 里找到『更多』按钮，用比例坐标兜底 {xy}")
    else:
        log.append(f"找到『更多』按钮（{via}）@{xy}")
    res["more_xy"], res["more_via"] = xy, via
    d.click(xy[0], xy[1])
    time.sleep(3.0)
    xml3 = d.dump_hierarchy()
    nodes3 = parse_nodes(xml3)
    ok3, dom3, _, _ = page_belongs_to(xml3, pkg)
    log.append(f"侧边栏节点={len(nodes3)} 主导包={dom3}")
    try:
        p = os.path.join(outdir, "sidebar.png")
        d.screenshot(p)
        res["shot"] = p
    except Exception as e:
        log.append(f"截图失败: {e}")

    # 收集侧边栏里的可点条目
    items = []
    for n in nodes3:
        t = (n["text"] or "").strip()
        dd = (n["desc"] or "").strip()
        label = t or dd
        if not label or len(label) > 20:
            continue
        items.append({"label": label, "text": t, "desc": dd,
                      "rid": n["rid"], "center": n["center"],
                      "clickable": n["clickable"]})
    res["items"] = items
    log.append(f"侧边栏可点/可见条目 {len(items)} 条")

    # 行为关键词命中
    for beh, kws in BEHAVIOR_KEYWORDS.items():
        found = []
        for it in items:
            if any(k in it["label"] for k in kws):
                found.append(f"{it['label']}@{it['center']}")
        if found:
            res["hits"][beh] = found
    for beh, found in res["hits"].items():
        log.append(f"  [{beh}] {found}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None)
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "SIDEBAR_PROBE.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "SIDEBAR_PROBE.json"))
    args = ap.parse_args()

    cfg = load_config(args.config)
    apps = {a["name"]: a for a in (cfg.get("apps") or []) if a.get("name")}
    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    targets = [a for a in DEFAULT_APPS if not only or a in only]
    print(f"待探针: {targets}")

    serial = (cfg.get("device") or {}).get("serial")
    d = connect_device(serial)

    results, logs = [], {}
    for name in targets:
        if name not in apps:
            print(f"跳过（配置无此 App）: {name}")
            continue
        print(f"\n===== {name} =====")
        log = []
        try:
            r = probe_one(d, apps[name], log)
        except Exception as e:
            log.append(f"异常: {type(e).__name__}: {e}")
            r = {"app": name, "error": str(e), "items": [], "hits": {}}
        results.append(r)
        logs[name] = log
        if r.get("error"):
            print(f"  ✗ {r['error']}")
        else:
            print(f"  「更多」@ {r.get('more_xy')}（{r.get('more_via')}）"
                  f" 侧边栏条目 {len(r.get('items') or [])}")
            for beh, found in (r.get("hits") or {}).items():
                print(f"    [{beh}] {found}")

    md = ["# 抖音系「≡ 更多」侧边栏探针", "",
          f"> 生成: {time.strftime('%Y-%m-%d %H:%M:%S')}", f"> 设备: {serial}", ""]
    for r in results:
        md += [f"## {r['app']}", "",
               f"- 包名: `{r.get('package')}`",
               f"- 「更多」坐标: {r.get('more_xy')}（{r.get('more_via')}）",
               f"- 截图: `{os.path.basename(r.get('shot') or '')}`",
               f"- 错误: {r.get('error') or '无'}", ""]
        if r.get("hits"):
            md += ["### 行为关键词命中", ""]
            for beh, found in r["hits"].items():
                md.append(f"- **{beh}**: {', '.join(found)}")
            md.append("")
        md += ["### 侧边栏条目", "", "| 文案 | resource-id | 坐标 | 可点 |",
               "|---|---|---|---|"]
        for it in (r.get("items") or [])[:80]:
            md.append(f"| {it['label']} | `{it['rid'][-40:]}` | {it['center']} | "
                      f"{it['clickable']} |")
        md.append("")
        md.append("<details><summary>执行日志</summary>")
        md.append("")
        md.append("```")
        md += logs.get(r["app"], [])
        md.append("```")
        md.append("</details>")
        md.append("")

    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    with open(args.md, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    json.dump(results, open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### `devtools/propose_anchors.py`（162 行）

```python
# -*- coding: utf-8 -*-
"""propose_anchors.py - 基于校准 dump 生成锚点修补建议（只读，不改配置）

对每个已校准的 App：
  - 读 devtools/calib/<app>/ui.xml
  - 对该 App 每个行为的**入口动作**，把候选锚点分别在 text / desc / id 三种语义下搜索，
    做"跨语义交叉匹配"（很多 App 把按钮做成图片，文案在 content-desc 里，
    只按 text 匹配必然未命中 —— 这是新 18 App 大量"未命中"的主因之一）
  - 输出：现状 / 建议候选（含实际命中文案与坐标）/ 或"无文本锚点，需坐标或 VLM"

用法：
    python devtools/propose_anchors.py
    python devtools/propose_anchors.py --out devtools/calib/ANCHOR_PROPOSAL.md
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import load_config  # noqa: E402
from calibrate import parse_nodes, match_selector  # noqa: E402

ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")


def load_cfg():
    return load_config(os.path.join(ROOT, "config.yaml"))


def search_all_kinds(nodes, value):
    """在 text/desc/id 三种语义下搜索 value，返回 {kind: [(label, center)]}"""
    out = {}
    for kind in ("text", "desc"):
        hits = match_selector(nodes, kind, value)
        if hits:
            out[kind] = [(h["text"] or h["desc"], h["center"]) for h in hits]
    hits = match_selector(nodes, "id", value)
    if hits:
        out["id"] = [(h["rid"], h["center"]) for h in hits]
    return out


def first_anchor_action(actions):
    """返回 (index, action)；actions 可能是单模板或多候选模板。"""
    variants = actions if all(isinstance(a, list) for a in actions) else [actions]
    for vi, variant in enumerate(variants):
        for i, act in enumerate(variant or []):
            if isinstance(act, dict) and act.get("type") in ANCHOR_TYPES:
                return vi, i, act
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "calib",
                                                 "ANCHOR_PROPOSAL.md"))
    args = ap.parse_args()

    cfg = load_cfg()
    apps = {a.get("name"): a for a in (cfg.get("apps") or [])}

    lines = ["# 锚点修补建议（基于真机校准 dump）", "",
             "> 由 `devtools/propose_anchors.py` 生成，**只读不改配置**。",
             "> 「跨语义命中」= 候选文案虽然在 text 里找不到，但在 content-desc 里找到了。",
             "> 这类锚点只需给候选加一条 `type: desc` 即可修复，无需重新截图。", ""]

    fixed_cnt = need_coord = no_dump = 0

    for path in sorted(glob.glob(os.path.join(HERE, "calib", "*", "ui.xml"))):
        app_dir = os.path.dirname(path)
        app_name = os.path.basename(app_dir)
        app = apps.get(app_name)
        if not app:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                nodes = parse_nodes(f.read())
        except Exception as e:
            lines.append(f"## {app_name}\n\n读取 dump 失败: {e}\n")
            no_dump += 1
            continue

        lines.append(f"## {app_name}  (`{app.get('package')}`)")
        lines.append("")
        lines.append("| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |")
        lines.append("|---|---|---|---|---|---|")

        for bid, actions in (app.get("behaviors") or {}).items():
            if not actions:
                continue
            vi, si, act = first_anchor_action(actions)
            if act is None:
                continue
            t = act.get("type")
            if t == "click_first":
                cands = [c for c in (act.get("candidates") or [])
                         if isinstance(c, dict) and c.get("value")]
            elif t == "click_text":
                cands = [{"type": "text", "value": act.get("text", "")}]
            elif t == "click_id":
                cands = [{"type": "id", "value": act.get("res_id", "")}]
            else:
                cands = [{"type": "desc", "value": act.get("desc", "")}]

            found_any = False
            detail_rows = []
            for c in cands:
                val = str(c.get("value") or "")
                if not val:
                    continue
                res = search_all_kinds(nodes, val)
                native = c.get("type", "text")
                native_hit = bool(res.get(native))
                alt = {k: v for k, v in res.items() if k != native and v}
                if native_hit:
                    found_any = True
                    label, center = res[native][0]
                    detail_rows.append((val, native, "命中",
                                        f"{native}:{label} @{center}", "无需修改"))
                elif alt:
                    found_any = True
                    k = list(alt)[0]
                    label, center = alt[k][0]
                    detail_rows.append((val, native, "未命中",
                                        f"{k}:{label} @{center}",
                                        f"加候选 `{{type: {k}, value: \"{val}\"}}`"))
                else:
                    detail_rows.append((val, native, "未命中", "-", "落地页无此锚点"))

            if not found_any:
                need_coord += 1
                detail_rows.append(("—", "—", "—", "—",
                                    "⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM)"))
            else:
                fixed_cnt += 1

            for val, native, st, cross, sug in detail_rows:
                lines.append(f"| {bid} | {t} | `{val}` | {st} | {cross} | {sug} |")
        lines.append("")

    lines += ["## 统计", "",
              f"- 入口有可用文本锚点的行为: **{fixed_cnt}**",
              f"- 落地页无文本锚点、需坐标/VLM 的行为: **{need_coord}**", ""]

    text = "\n".join(lines)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"已写出: {args.out}")
    print(f"入口有文本锚点: {fixed_cnt} | 需坐标/VLM: {need_coord}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/record_flow.py`（667 行）

```python
# -*- coding: utf-8 -*-
"""record_flow.py - 引导式录制：NL 指令 → 执行 → 记录 → YAML（AUTOP-NL-2026-10-22-B）

为什么不用 getevent 抓物理触摸：
    1. 无语义：raw ABS_MT 只给 slot/tracking_id/pressure，拿不到「点的是哪个元素」；
    2. 坐标空间不同：event 是触摸屏原始量程，需 `getevent -p` 读 `0035/0036` 的 max
       自行换算，多指 slot 还要解析 `SYN_REPORT` 分帧；
    3. 无法归因：录制期脚本注入的点击与用户物理点击混在同一事件流；
    4. 阻塞流收尾差：`adb shell getevent -lt` 是长驻流，Windows 下易留僵尸 adb；
    5. H5 场景坐标本身不可信（星图金融打卡按钮被透明层遮挡就是证据）。

结论：录制输入是「一句 NL 指令」，坐标由 `d.dump_hierarchy()` 的 bounds 反算。

工作流：
    用户逐句输入 NL 指令（点签到 / 点右下角 / 上滑 / 等2秒 / 返回），
    脚本执行并记录每步（命中方式、归一化坐标、执行前后 activity、页面差分），
    结束时给一句命名 + 指定 app/behavior，渲染成 YAML 片段交给 yaml_writer 写回（缺省预览）。

用法：
    python devtools/record_flow.py --app 七猫免费小说 [--serial 192.168.1.54:5555] \\
           [--behavior sign] [--entry auto] [--max-steps 20] [--allow-money] [--apply]

    > 点右下角我的
    > 点福利中心
    > 点签到
    > trace / undo / done
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 只读复用 calibrate 的节点解析/匹配/包判断（不修改其任何逻辑）
from devtools import calibrate  # noqa: E402
from devtools import yaml_writer as yw  # noqa: E402

# ---- 软依赖：A 卡 nl_to_steps.py（可能稍后出现）；未就绪时用极简兜底 ----
NL_TO_STEPS_READY = False
try:  # pragma: no cover - 由 A 卡是否就绪决定
    from nl_to_steps import (  # type: ignore[import-not-found]
        parse_line,
        render_hop,
        render_steps,
        to_yaml_fragment,
    )
    NL_TO_STEPS_READY = True
except ImportError:
    pass

# 兜底（A 卡未就绪）：仅剥最朴素的动词前缀，全句当文案；不复制 A 卡 parse_line 的动词表/切分逻辑
def _fallback_parse_line(cmd: str) -> dict:
    c = (cmd or "").strip()
    if c.startswith("点"):
        return {"verb": "tap", "target": c[1:].strip()}
    if c.startswith("上滑") or c.startswith("下滑") or c.startswith("左滑") \
            or c.startswith("右滑") or c.startswith("滑动"):
        return {"verb": "swipe", "target": c}
    if c.startswith("等"):
        return {"verb": "wait", "target": c}
    if c.startswith("返回"):
        return {"verb": "back", "target": ""}
    return {"verb": "tap", "target": c}


def _split_cmd(cmd: str) -> tuple[str, str, str | tuple | None]:
    """统一把 NL 指令拆成 (verb, target, pos)；A 卡就绪时走真 parse_line。

    A 卡结构：parse_line(cmd) -> (steps: list[dict], warnings: list)。
    单条指令通常只有 1 步；多于 1 步时取首步并打印提示（本工具按单步录制）。
    """
    try:
        info = parse_line(cmd) if NL_TO_STEPS_READY else _fallback_parse_line(cmd)
    except Exception:  # noqa: BLE001 - A 卡结构变化时兜底不阻断录制
        info = _fallback_parse_line(cmd)

    steps: list | None = None
    if isinstance(info, tuple) and info and isinstance(info[0], list):
        steps = info[0]
    elif isinstance(info, list) and info and isinstance(info[0], dict):
        steps = info
    if steps:
        if len(steps) > 1:
            print(f"[warn] 指令拆出 {len(steps)} 步，仅取首步：{steps[0]}")
        first = steps[0] if isinstance(steps[0], dict) else {}
        verb = str(first.get("verb") or "tap")
        target = first.get("target")
        pos = first.get("pos")          # A 卡可能是 (x,y) tuple 或方位词 str
        return verb, (str(target) if target else ""), pos

    if isinstance(info, dict):
        verb = str(info.get("verb") or "tap")
        target = str(info.get("target") or "")
        pos = info.get("pos")
        return verb, target, pos
    if isinstance(info, (tuple, list)):
        parts = tuple(info) + (None, None)
        return str(parts[0] or "tap"), str(parts[1] or ""), parts[2]
    return "tap", str(cmd), None


# ---- 方位词 → 归一化坐标（点右下角 / 点右上…） ----
_POS: dict[str, tuple[float, float]] = {
    "右下角": (0.90, 0.88),
    "右下": (0.90, 0.88),
    "右上角": (0.90, 0.10),
    "右上": (0.90, 0.10),
    "左下角": (0.10, 0.88),
    "左下": (0.10, 0.88),
    "左上角": (0.10, 0.10),
    "左上": (0.10, 0.10),
    "中间偏上": (0.50, 0.35),
    "中间偏下": (0.50, 0.65),
    "中间": (0.50, 0.50),
    "中心": (0.50, 0.50),
    "中部": (0.50, 0.50),
    "上部": (0.50, 0.20),
    "下部": (0.50, 0.80),
}


def _match_pos(target: str) -> tuple[float, float] | None:
    """target 是否以方位词开头（或本身就是方位词）。返回归一化坐标。"""
    if not target:
        return None
    for key in sorted(_POS, key=len, reverse=True):
        if target == key or target.startswith(key):
            return _POS[key]
    return None


def _parse_seconds(target: str) -> float:
    """从「等2秒/等 2.5 秒/等两秒」里取秒数；取不到默认 1.0。"""
    m = re.search(r"(\d+(?:\.\d+)?)", target or "")
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 1.0


# ---- 纯函数（可单测，无设备） ----

@dataclass
class Step:
    seq: int
    cmd: str
    verb: str
    target: str | None
    pos: str | tuple | None
    hit_kind: str | None      # text|desc|id|point|None
    hit_value: str | None
    bounds: tuple | None      # (l,t,r,b) 像素
    point_norm: tuple | None  # (x,y) round(4)
    act_before: str
    act_after: str
    delta: float
    confirmed: bool
    note: str = ""


def ui_digest(xml: str) -> frozenset:
    """可点节点的 (text, desc, id, bounds) 集合；对节点顺序不敏感。

    可点 = clickable=="true"，或带非空 text/desc 的节点。
    bounds 归一为 (l,t,r,b) int 元组，保证可哈希、可差分。
    """
    items: set[tuple] = set()
    try:
        root = ET.fromstring(xml or "")
    except ET.ParseError:
        return frozenset()
    for el in root.iter("node"):
        a = el.attrib
        m = calibrate.BOUNDS_RE.match(a.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = (int(v) for v in m.groups())
        text = a.get("text", "") or ""
        desc = a.get("content-desc", "") or ""
        rid = a.get("resource-id", "") or ""
        clickable = a.get("clickable", "") == "true"
        if not (clickable or text or desc):
            continue
        items.add((text, desc, rid, (x1, y1, x2, y2)))
    return frozenset(items)


def page_delta(a: frozenset, b: frozenset) -> float:
    """页面差分：1 - Jaccard(a, b)。同页=0.0，全换=1.0，双空=0.0。"""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return 1.0 - len(a & b) / len(union)


def step_to_action(step: Step) -> dict | None:
    """把已确认 Step 映射成引擎动作 dict；未确认/未命中返回 None。

    text/desc/id 命中 → click_first；point 命中 → click_point；
    swipe → swipe_natural；wait → wait；back → back。
    """
    if not step.confirmed:
        return None
    kind = step.hit_kind
    if kind in ("text", "desc", "id") and step.hit_value:
        return {
            "type": "click_first",
            "candidates": [{"type": kind, "value": step.hit_value}],
            "timeout": 8,
            "optional": True,
        }
    if kind == "point" and step.point_norm:
        x, y = step.point_norm
        return {
            "type": "click_point",
            "x": x,
            "y": y,
            "vision": False,
            "desc": step.hit_value or step.cmd,
        }
    if step.verb == "swipe":
        return {"type": "swipe_natural"}
    if step.verb == "wait":
        return {"type": "wait", "seconds": _parse_seconds(step.target)}
    if step.verb == "back":
        return {"type": "back"}
    return None


def steps_to_actions(steps: list[Step]) -> tuple[list[dict], list[str]]:
    """遍历 trace，丢弃未确认步，返回 (动作链, warnings)。"""
    actions: list[dict] = []
    warnings: list[str] = []
    for s in steps:
        if not s.confirmed:
            warnings.append(f"step#{s.seq} {s.cmd!r} 未确认，已丢弃")
            continue
        act = step_to_action(s)
        if act is None:
            reason = ("未定位到元素且无坐标兜底"
                      if (s.verb == "tap" and not s.hit_kind and not s.point_norm)
                      else "无可映射动作")
            warnings.append(f"step#{s.seq} {s.cmd!r} {reason}，已丢弃"
                            f"（note={s.note or '-'}）")
            continue
        actions.append(act)
    return actions, warnings


def guess_entry(steps: list[Step]) -> str:
    """从 trace 里猜入口锚点：第一个 text/desc/id 命中值；无则 'auto'。"""
    for s in steps:
        if s.hit_kind in ("text", "desc", "id") and s.hit_value:
            return s.hit_value
    return "auto"


def is_money_step(step: Step, money_words: set[str]) -> bool:
    """资金红线：指令/目标/命中值是否触碰资金类词。"""
    blob = " ".join(filter(None, [step.cmd, step.target, step.hit_value]))
    return any(w and w in blob for w in money_words)


def assemble_actions(steps: list[Step], entry_hops: list[dict]) -> tuple[list[dict], list[str]]:
    """finish 组装：entry hops 在前、录制步在后。"""
    step_actions, warnings = steps_to_actions(steps)
    return list(entry_hops) + list(step_actions), warnings


# ---- 设备层 ----

MONEY_WORDS = frozenset({
    "提现", "立即提现", "收款", "转账", "充值", "支付", "付款", "银行卡", "余额宝",
})


class FlowRecorder:
    """交互式录制器：连接设备 → 逐步执行 → 记录 Step → finish 渲染 YAML。"""

    def __init__(self, app: str, package: str, serial: str | None = None,
                 out_dir: str | None = None, max_steps: int = 20,
                 allow_money: bool = False):
        self.app = app
        self.package = package
        self.serial = serial
        self.out_dir = out_dir
        self.max_steps = max_steps
        self.allow_money = allow_money
        self.money_words: set[str] = set(MONEY_WORDS)
        self.trace: list[Step] = []
        self.d = None            # u2 设备（测试可注入 fake）
        self._session_dir: str | None = None
        self._seq = 0
        self._closed = False
        self._screen: tuple[int, int] | None = None

    # ---- 连接 / 生命周期 ----
    def _connect(self):  # 测试 monkeypatch 点
        if self.serial:
            return calibrate.connect_device(self.serial)
        raise RuntimeError("未提供 serial，且未注入设备")

    def start(self) -> None:
        """连接设备、启动 App、建快照会话目录。"""
        if self._closed:
            raise RuntimeError("recorder 已关闭")
        if self.d is None:
            self.d = self._connect()
        base = self.out_dir or os.path.join(ROOT, "devtools", "calib", "record",
                                            calibrate.safe_name(self.package))
        self._session_dir = os.path.join(base, datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(self._session_dir, exist_ok=True)
        try:
            self.d.press("home")
            time.sleep(1.2)
            self.d.app_start(self.package, stop=True)
            self._wait_app_ready()
        except Exception as exc:  # noqa: BLE001 - 设备差异不阻断录制
            print(f"[warn] 启动 App 失败（{type(exc).__name__}: {exc}），继续")

    def _wait_app_ready(self, timeout: float = 10.0) -> None:
        """等 App 离开启动页（真机修正：七猫 LoadingActivity 可持续数秒，
        早期只睡 1.5s 导致首屏只有系统导航节点，文案全部定位不到）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                dom = calibrate.dominant_package(self._dump())
            except Exception:  # noqa: BLE001
                return
            if dom and dom == self.package:
                return
            time.sleep(1.0)

    def close(self) -> None:
        self._closed = True

    # ---- 设备辅助 ----
    def _screen_size(self) -> tuple[int, int]:
        if self._screen is None:
            try:
                w, h = self.d.window_size()
                self._screen = (int(w), int(h))
            except Exception:  # noqa: BLE001
                self._screen = (1080, 2340)
        return self._screen

    def _activity(self) -> str:
        try:
            cur = self.d.app_current()
            if isinstance(cur, dict):
                return str(cur.get("activity") or cur.get("package") or "?")
        except Exception:  # noqa: BLE001
            pass
        return "?"

    def _dump(self) -> str:
        try:
            return str(self.d.dump_hierarchy() or "")
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] dump 失败（{type(exc).__name__}: {exc}）")
            return ""

    def _snapshot(self, seq: int, phase: str, xml: str) -> None:
        if not self._session_dir:
            return
        tag = f"{seq:02d}_{phase}"
        try:
            with open(os.path.join(self._session_dir, f"{tag}.xml"),
                      "w", encoding="utf-8") as f:
                f.write(xml)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.d.screenshot(os.path.join(self._session_dir, f"{tag}.png"))
        except Exception:  # noqa: BLE001 - 无截图能力时只留 XML
            pass

    # ---- 执行 ----
    def _execute(self, verb: str, target: str,
                 pos: str | tuple | None = None
                 ) -> tuple[str | None, str | None, tuple | None, tuple | None]:
        """按 verb 执行动作，返回 (hit_kind, hit_value, bounds, point_norm)。"""
        xml = self._dump()
        nodes = calibrate.parse_nodes(xml)
        if verb == "tap":
            # text → desc → id 顺序定位（与 match_selector 工程语义一致）
            if target:
                for kind in ("text", "desc", "id"):
                    hits = calibrate.match_selector(nodes, kind, target)
                    if hits:
                        n = hits[0]
                        cx, cy = n["center"]
                        w, h = self._screen_size()
                        self.d.click(cx, cy)
                        return kind, target, n["bounds"], \
                            (round(cx / w, 4), round(cy / h, 4))
            # 坐标兜底：A 卡已给 (x,y) 归一化坐标，或方位词
            p = pos if isinstance(pos, (tuple, list)) else _match_pos(str(pos) if pos else "")
            if p is not None:
                px, py = float(p[0]), float(p[1])
                w, h = self._screen_size()
                self.d.click(int(px * w), int(py * h))
                return "point", target or (pos if isinstance(pos, str) else "坐标点击"), \
                    None, (round(px, 4), round(py, 4))
            # 文案没命中、又没有坐标兜底：不静默空转，给出可点击文案建议
            self._suggest_targets()
            return None, None, None, None
        if verb == "swipe":
            w, h = self._screen_size()
            self.d.swipe(int(w * 0.5), int(h * 0.8), int(w * 0.5), int(h * 0.3),
                         duration=0.4)
            return None, None, None, None
        if verb == "wait":
            time.sleep(_parse_seconds(target))
            return None, None, None, None
        if verb == "back":
            self.d.press("back")
            return None, None, None, None
        return None, None, None, None

    def _suggest_targets(self, limit: int = 8) -> None:
        """tap 未命中时打印当前屏可点击文案，便于改口述词（真机调试关键）。"""
        try:
            nodes = calibrate.parse_nodes(self._dump())
        except Exception:  # noqa: BLE001
            return
        seen, texts = set(), []
        for n in nodes:
            for key in ("text", "desc"):
                v = (n.get(key) or "").strip()
                if v and v not in seen and len(v) <= 12:
                    seen.add(v)
                    texts.append(v)
            if len(texts) >= limit:
                break
        if texts:
            print("    [提示] 未定位到元素且无坐标兜底，未执行点击。当前屏可点文案："
                  + " / ".join(texts))

    # ---- 机器校验（先于人工，防误触） ----
    def _machine_check(self, step: Step, after_xml: str, act_before: str
                       ) -> tuple[bool, str, bool]:
        """返回 (ok, note, fatal)。fatal=True 表示直接拒绝、不可人工 override（资金红线）。"""
        if not self.allow_money and is_money_step(step, self.money_words):
            return False, "资金红线: 触碰资金类词且未开启 --allow-money", True
        dom = calibrate.dominant_package(after_xml)
        if dom and dom != self.package:
            return False, f"跳转/误触: 主导包 {dom} != {self.package}", False
        # 2026-10-22 真机实跑修正：文案未命中且无坐标时 _execute 根本不点击，
        # 但 App 自身加载会造成高 delta / activity 变化，旧判据把它误判为"有效点击"。
        # 这里显式拦住：没定位到东西就不算一步。
        if step.verb == "tap" and not step.hit_kind and not step.point_norm:
            return False, "未定位到元素且无坐标兜底（未执行点击）", False
        if step.delta < 0.02 and step.act_before == step.act_after:
            return False, "疑似无效点击: delta<0.02 且 activity 未变", False
        return True, "", False

    # ---- 单步录制 ----
    def record_step(self, cmd: str) -> Step | None:
        """执行一条 NL 指令并记录；直接拒绝/丢弃返回 None。"""
        if self._closed:
            raise RuntimeError("recorder 已关闭")
        if self.d is None:
            self.start()
        if len(self.trace) >= self.max_steps:
            print(f"[warn] 已达 max_steps={self.max_steps}")
            return None
        cmd = (cmd or "").strip()
        if not cmd:
            return None
        verb, target, pos = _split_cmd(cmd)

        before_xml = self._dump()
        act_before = self._activity()
        hit_kind, hit_value, bounds, point_norm = self._execute(verb, target, pos)
        time.sleep(1.2)
        after_xml = self._dump()
        act_after = self._activity()

        seq = self._seq + 1
        delta = page_delta(ui_digest(before_xml), ui_digest(after_xml))
        step = Step(seq=seq, cmd=cmd, verb=verb, target=target, pos=pos,
                    hit_kind=hit_kind, hit_value=hit_value, bounds=bounds,
                    point_norm=point_norm, act_before=act_before,
                    act_after=act_after, delta=delta, confirmed=False)
        ok, note, fatal = self._machine_check(step, after_xml, act_before)
        if fatal:
            print(f"[reject] {note}")
            return None
        step.confirmed = ok
        step.note = note
        self._seq = seq
        self._snapshot(seq, "before", before_xml)
        self._snapshot(seq, "after", after_xml)
        self._show_step(step)

        # 人工确认：y=收下（可 override 机器拒绝） n=丢弃 e=改文案后重记
        # r=重试 u=撤销上一步
        ans = input("y=收下 n=丢弃 e=改文案后重记 r=重试 u=撤销上一步 > ").strip().lower()
        if ans == "u":
            self.undo()
            return None
        if ans == "r":
            return self.record_step(cmd)
        if ans in ("", "y"):
            step.confirmed = True
            self.trace.append(step)
            return step
        return None  # n / e / 其他 → 丢弃，不入 trace

    def _show_step(self, step: Step) -> None:
        print(f"--- step#{step.seq} {step.cmd!r} verb={step.verb} "
              f"hit={step.hit_kind}:{step.hit_value} "
              f"bounds={step.bounds} point={step.point_norm}")
        print(f"    activity {step.act_before} -> {step.act_after} "
              f"delta={step.delta:.3f} confirmed={step.confirmed} "
              f"note={step.note or '-'}")

    # ---- 撤销 / 展示 ----
    def undo(self) -> Step | None:
        if not self.trace:
            return None
        return self.trace.pop()

    def show_trace(self) -> None:
        if not self.trace:
            print("(trace 为空)")
            return
        for s in self.trace:
            print(f"  #{s.seq} {s.cmd!r} -> {s.hit_kind}:{s.hit_value} "
                  f"@{s.point_norm} delta={s.delta:.3f} ok={s.confirmed}")

    # ---- 收尾渲染 ----
    def _render_hops(self, entry: str) -> list[dict]:
        if not entry or entry == "auto":
            return []
        try:
            hops = render_hop(entry, {}) if NL_TO_STEPS_READY else []
        except Exception:  # noqa: BLE001
            hops = []
        return list(hops or [])

    def _resolve_entry(self, entry: str) -> str:
        if entry == "auto":
            guessed = guess_entry(self.trace)
            return guessed if guessed != "auto" else ""
        return entry

    def finish(self, name: str, behavior: str, entry: str = "auto",
               apply: bool = False, force: bool = False,
               comments: list[str] | None = None) -> object:
        """组装动作链并交给 yaml_writer 写回（缺省预览）。

        name 是 **App 名**（对应 config/apps/<app>.yaml），不是行为命名；
        行为命名请走 comments，会作为 YAML 注释写进配置。
        """
        if not self.trace:
            return yw.WriteResult("", "error", None, "", ["trace 为空，无内容可写"])
        entry = self._resolve_entry(entry)
        hops = self._render_hops(entry)
        actions, warnings = assemble_actions(self.trace, hops)
        if not actions:
            detail = "；".join(warnings) if warnings else "所有步骤都未产出动作"
            return yw.WriteResult("", "error", None, "",
                                  [f"无可用动作：{detail}",
                                   "建议：用屏上实际文案（如「福利」）或方位词"
                                   "（如「点右下角」）重录，必要时加 --xy 坐标兜底"])
        try:
            path = yw.app_path(name, base_dir=ROOT)
        except Exception as exc:  # noqa: BLE001
            return yw.WriteResult("", "error", None, "", [f"app 配置定位失败: {exc}"])
        result = yw.insert_behavior(path, behavior, actions, comments=comments,
                                    apply=apply, base_dir=ROOT)
        if result.action == "skipped" and any("已存在" in w for w in result.warnings):
            result = yw.replace_behavior(path, behavior, actions, comments=comments,
                                         apply=apply, force=force, base_dir=ROOT)
        result.warnings = list(result.warnings) + list(warnings)
        return result


# ---- CLI ----
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="引导式录制：NL 指令 → 执行 → 记录 → YAML")
    ap.add_argument("--app", required=True, help="App 名（对应 config/apps/*.yaml）")
    ap.add_argument("--package", default=None, help="目标包名；缺省从配置推断")
    ap.add_argument("--serial", default=None, help="设备序列号（无线 adb 用 ip:port）")
    ap.add_argument("--behavior", default="sign", help="行为 ID（如 sign/collect）")
    ap.add_argument("--entry", default="auto", help="入口锚点；auto 自动猜")
    ap.add_argument("--max-steps", type=int, default=20)
    ap.add_argument("--allow-money", action="store_true", help="允许录制资金类步骤")
    ap.add_argument("--apply", action="store_true", help="确认后写盘；缺省仅预览")
    args = ap.parse_args(argv)

    package = args.package
    if not package:
        try:
            cfg = yw.load_app(yw.app_path(args.app, base_dir=ROOT))
            package = (cfg.get("package") or "").strip()
        except Exception:  # noqa: BLE001
            package = ""
    if not package:
        print(f"[error] 无法推断包名：{args.app}")
        return 2

    rec = FlowRecorder(args.app, package, serial=args.serial,
                       max_steps=args.max_steps, allow_money=args.allow_money)
    rec.start()
    print(f"开始录制 {args.app}（{package}）。指令示例：点签到 / 点右下角我的 / "
          f"上滑 / 等2秒 / 返回；trace / undo / done")
    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line in ("done", "退出", "结束"):
                break
            if line in ("trace", "回放"):
                rec.show_trace()
                continue
            if line in ("undo", "撤销"):
                rec.undo()
                print("已撤销上一步")
                continue
            rec.record_step(line)
    except (EOFError, KeyboardInterrupt):
        pass

    rec.show_trace()
    name = input("一句话命名（行为用途，如：每日签到）: ").strip() or "sign"
    try:
        result = rec.finish(args.app, args.behavior, entry=args.entry,
                            apply=args.apply, force=args.force,
                            comments=[f"录制命名：{name}"])
    except yw.WriterError as exc:
        print(f"[error] 写回失败：{exc}")
        rec.close()
        return 1
    rec.close()
    print(f"[result] action={result.action}")
    if result.diff:
        print(result.diff)
    if result.warnings:
        for w in result.warnings:
            print(f"  [warn] {w}")
    if not args.apply:
        print("（预览模式：加 --apply 才写盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/remove_prelude.py`（166 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""移除某个行为最前面的「导航前置步」。

为什么需要：前置步不是越多越好。若某个行为的锚点本来就在**落地页**，
而配置里又给它加了「先点『我的』」的前置步，真实执行时会
「先跳到我的页 → 再找落地页才有的锚点」→ 必然失败。
实测 `今日看点极速版.sign`（首屏就有 `签到`）就是这种情况。

用法：
    python devtools/remove_prelude.py --app 今日看点极速版 --behavior sign
    python devtools/remove_prelude.py --app X --behavior sign --apply
    python devtools/remove_prelude.py --list          # 列出所有带前置步的行为
"""
import argparse
import glob
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402
from plan_anchor_fixes import NAV_ACTION  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")


def app_files():
    """拆分后返回全部 App 级配置文件；旧单文件（apps 非空）则返回 [CONFIG]。"""
    try:
        cfg = load_config(CONFIG)
    except Exception:
        cfg = {}
    if cfg.get("apps"):
        return [CONFIG]
    files = sorted(glob.glob(os.path.join(ROOT, "config", "apps", "*.yaml")))
    return files or [CONFIG]


def find_app_block(lines, app_name):
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- name: {app_name}":
            start = i
            break
    if start is None:
        # 拆分后 App 级文件：整文件即一个 App 块（首行 `name: xxx`）
        if lines and lines[0].strip() == f"name: {app_name}":
            start = 0
        else:
            return None, None
        end = len(lines)
        return start, end
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- name: "):
            end = j
            break
    return start, end


def find_behavior(lines, start, end, behavior, indent=4):
    for k in range(start, end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) \
                and s.rstrip().endswith(":") and s.strip().rstrip(":") == behavior:
            return k
    return None


def list_preludes(lines):
    out = []
    app = None
    beh_ind = None
    for i, ln in enumerate(lines):
        if ln.startswith("- name: "):
            app = ln[len("- name: "):].strip()
        elif ln.startswith("name: ") and not ln.startswith(" "):
            app = ln[len("name: "):].strip()
        elif ln.rstrip().endswith(":") and ln.strip() == "behaviors":
            beh_ind = len(ln) - len(ln.lstrip()) + 2
        elif beh_ind and ln.startswith(" " * beh_ind) \
                and not ln.startswith(" " * (beh_ind + 1)) \
                and ln.rstrip().endswith(":"):
            bid = ln.strip().rstrip(":")
            if lines[i + 1:i + 1 + len(NAV_ACTION)] == list(NAV_ACTION):
                out.append((app, bid, i))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app")
    ap.add_argument("--behavior")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if args.list:
        found = []
        for path in app_files():
            lines = open(path, encoding="utf-8").read().split("\n")
            for app, bid, ln in list_preludes(lines):
                found.append((app, bid, ln + 1))
        print(f"带导航前置步的行为共 {len(found)} 个：")
        for app, bid, ln in found:
            print(f"  {app}.{bid}  (行 {ln})")
        return 0

    if not (args.app and args.behavior):
        print("需要 --app 和 --behavior（或用 --list 查看）")
        return 1

    path = app_config_path(args.app)
    if not os.path.exists(path):
        print(f"未找到 app 配置文件: {args.app} ({path})")
        return 1
    lines = open(path, encoding="utf-8").read().split("\n")

    s, e = find_app_block(lines, args.app)
    if s is None:
        print(f"未找到 app: {args.app}")
        return 1
    ind = 4
    for k in range(s, e):
        l2 = lines[k].rstrip()
        if l2.endswith(":") and l2.strip() == "behaviors":
            ind = len(l2) - len(l2.lstrip()) + 2
            break
    b = find_behavior(lines, s, e, args.behavior, ind)
    if b is None:
        print(f"未找到行为: {args.app}.{args.behavior}")
        return 1
    if lines[b + 1:b + 1 + len(NAV_ACTION)] != list(NAV_ACTION):
        print(f"{args.app}.{args.behavior} 开头不是标准导航前置步，未改动")
        return 1

    print(f"将移除 {args.app}.{args.behavior} 的前置步（{len(NAV_ACTION)} 行）")
    if not args.apply:
        print("（预览模式，未写盘；加 --apply 生效）")
        return 0

    bak = f"{path}.bak-rmprelude-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(path, bak)
    del lines[b + 1:b + 1 + len(NAV_ACTION)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    print(f"已写回 {path}；备份 {bak}")
    try:
        cfg = load_config(CONFIG)
        print(f"复验: config 加载成功, {len(cfg['apps'])} 个 app")
    except Exception as ex:
        print(f"复验失败: {ex}，回滚")
        shutil.copy2(bak, path)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/run_sign_regression.py`（147 行）

```python
# -*- coding: utf-8 -*-
"""run_sign_regression.py - 12 份新 sign 配置真机回归驱动（Host 自执行版）

背景：verify_live/stability_run 只校验「有 calib dump 的 App」的入口命中率，
新配置的 12 个 App 无 dump 会被过滤。本驱动直接走 main.py 真实链路跑 sign，
逐 App 落盘日志 + 三级判读（A签=终态确认 / B走=有效交互未确认 / C断=断点崩溃），
并区分文案命中与坐标兜底（收敛后配置首次真机回归专用）。
安全约束：只跑 sign（不跑 withdraw/看视频后的提现）；发现资金类文案立即标记人工复核。
"""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
LOGDIR = os.path.join(ROOT, "devtools", "calib", "sign_regression")

APPS = ["趣头条", "拼多多", "京东", "美团", "快手", "百度地图",
        "海马畅听", "UC浏览器极速版", "飞猪旅行", "米读小说",
        "米读极速版", "大众点评"]

# 资金类红线文案：日志里出现即视为该 App 触及资金面，标记人工复核
MONEY_RE = re.compile(r"提现|确认支付|立即支付|银行卡|实名|验证码|付款")

# 终态确认（2026-10-21 15:27 增补，补判读缺口）：
# 签到成功的 App 一般会把按钮/提示切成这些文案；日志出现即记 verified。
SIGNED_RE = re.compile(r"已签|签到成功|签过|明日签到|明天再签|已领取|领取成功|签到完成")

SUMMARY = []


def run_one(app, force=True, fast=True):
    os.makedirs(LOGDIR, exist_ok=True)
    logf = os.path.join(LOGDIR, f"{app}.log")
    t0 = time.time()
    cmd = [PY, os.path.join(ROOT, "main.py"), "--app", app, "--task", "签到"]
    if force:
        # 作息窗口 07:30-23:00 是给人看的；回归验证要全时段可跑，
        # 2026-10-20 首轮 6 个 App 1-2 秒退出就是被 wake_window 拦的。
        cmd.append("--force")
    if fast:
        # 启动随机等待 60-350s 纯睡眠，回归不需要；其余真人模拟保留
        cmd.append("--fast")
    with open(logf, "w", encoding="utf-8") as f:
        p = subprocess.run(
            cmd,
            cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=420)
    dur = time.time() - t0
    txt = open(logf, encoding="utf-8").read()
    money_hit = MONEY_RE.search(txt)
    # 判读（2026-10-21 二轮口径）：
    #  - 有效交互 = 文案命中（点击文本/控件/描述/多候选/滚动）或坐标兜底命中
    #  - optional 前置（弹窗清扫 any_of）miss 会打「optional 放行」，不算失败
    #  - Traceback = 引擎级失败（首轮的 window_size 崩溃族即此）
    has_sign = "意图[sign]" in txt or "目标 app:" in txt
    done = "任务执行完毕" in txt or "执行完毕" in txt
    crash = "Traceback" in txt
    text_hits = re.findall(
        r"点击文本: |点击控件: |点击描述: |多候选命中并点击: |滚动找到并点击: ", txt)
    coord_hits = re.findall(r"点击坐标: \((\d+),(\d+)\)", txt)
    effective = len(text_hits) + len(coord_hits)
    # 仅保留非 optional 的失败步（optional 放行不算）
    fails = [ln for ln in re.findall(r"步骤失败: ([^\n]+)", txt)
             if "所有候选均未出现" not in ln]
    optional_miss = txt.count("optional 放行")
    signed = bool(SIGNED_RE.search(txt))
    hit = bool(has_sign and done and effective > 0 and not crash)
    # 三级判读：verified=有已签终态文案；effective=走到有效交互未确认终态；
    # blocked=断点/崩溃/零交互
    grade = "verified" if (hit and signed) else (
        "effective" if hit else "blocked")
    return {
        "app": app, "rc": p.returncode, "dur": round(dur), "hit": hit,
        "sign": has_sign, "done": done, "crash": crash, "signed": signed,
        "grade": grade,
        "text_hits": len(text_hits), "coord_hits": len(coord_hits),
        "effective": effective, "optional_miss": optional_miss,
        "fails": fails,
        "money": money_hit.group(0) if money_hit else "",
        "coord_clicks": len(coord_hits), "log": logf,
    }


def main():
    # 用法：python run_sign_regression.py [App1 App2 ...]
    # 无参 = 全量 12 App；带参 = 只跑指定 App（二轮补跑 5 个 MISS 用）。
    targets = sys.argv[1:] or APPS
    os.makedirs(LOGDIR, exist_ok=True)
    for i, app in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {app} ...", flush=True)
        try:
            r = run_one(app)
        except subprocess.TimeoutExpired:
            r = {"app": app, "rc": -1, "dur": 420, "hit": False, "sign": True,
                 "done": False, "crash": False, "signed": False, "grade": "blocked",
                 "text_hits": 0, "coord_hits": 0,
                 "effective": 0, "optional_miss": 0, "fails": ["TIMEOUT"],
                 "money": "", "coord_clicks": 0, "log": "?"}
        SUMMARY.append(r)
        flag = {"verified": "A签", "effective": "B走", "blocked": "C断"}[r["grade"]]
        print(f"  -> {flag} rc={r['rc']} {r['dur']}s "
              f"text={r['text_hits']} coord={r['coord_hits']} "
              f"opt_miss={r['optional_miss']} fails={len(r['fails'])} "
              f"signed={r['signed']} money={r['money'] or '-'}", flush=True)
        if r["money"]:
            print(f"  !! 资金类文案出现: {r['money']} —— 已记录，需人工复核", flush=True)
    # 写汇总
    lines = [f"# sign 真机回归汇总（Host 自执行 · --force --fast · 目标 {len(SUMMARY)} App）", "",
             f"时间：{time.strftime('%Y-%m-%d %H:%M')}  设备：192.168.1.54:5555", "",
             "引擎版本锚点：`engine_snapshot_20261021_1527/`（marvis REFINE R1 完成后 / R2 前；"
             "若回归途中引擎再被修改，按 App 时间段在表格备注）", "",
             "判读口径：有效交互=文案命中或坐标兜底命中；optional 前置 miss 不计失败；",
             "Traceback=引擎级失败；终态确认=日志出现「已签/签到成功/明日签到」类文案。", "",
             "三级判读：**A签**=verified（终态确认）｜**B走**=effective（有交互未确认终态）｜**C断**=blocked", "",
             "| App | 判定 | 耗时s | 文案命中 | 坐标命中 | 终态确认 | optional miss | 非可选失败 | 资金标记 | 日志 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in SUMMARY:
        lines.append(
            f"| {r['app']} | {r['grade']} | {r['dur']} | "
            f"{r['text_hits']} | {r['coord_hits']} | "
            f"{'✅' if r['signed'] else '-'} | {r['optional_miss']} | "
            f"{len(r['fails'])} | {r['money'] or '-'} | {os.path.basename(r['log'])} |")
    lines.append("")
    lines.append("## 失败步明细（非 optional）")
    any_fail = False
    for r in SUMMARY:
        if r["fails"]:
            any_fail = True
            lines.append(f"- **{r['app']}**: " + " / ".join(str(x)[:80] for x in r["fails"][:6]))
    if not any_fail:
        lines.append("（无）")
    lines.append("")
    lines.append("## 坐标兜底命中明细（待校准：文案 miss 说明真实文案与描述有出入）")
    for r in SUMMARY:
        if r["coord_hits"]:
            lines.append(f"- **{r['app']}**: 坐标命中 {r['coord_hits']} 次，"
                         f"详见 {os.path.basename(r['log'])}")
    out = os.path.join(LOGDIR, "SUMMARY.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    hits = sum(1 for r in SUMMARY if r["hit"])
    print(f"\nDONE {hits}/{len(SUMMARY)} 命中 -> {out}", flush=True)


if __name__ == "__main__":
    main()
```

### `devtools/shot.py`（36 行）

```python
# -*- coding: utf-8 -*-
"""shot.py - 真机截图（字节安全）

用法：
    python devtools/shot.py out.png [--serial 192.168.1.54:5555] [--wait 3]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from adbkit import Adb  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="输出 png 路径")
    ap.add_argument("--serial", default=None)
    ap.add_argument("--wait", type=float, default=0.0, help="截图前等待秒数")
    args = ap.parse_args()
    a = Adb(serial=args.serial)
    a.ensure()
    if args.wait:
        time.sleep(args.wait)
    data = a.screenshot_bytes()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(data)
    print(f"saved: {args.out} ({len(data)} bytes) size={a.screen_size()} "
          f"fg={a.foreground()}")


if __name__ == "__main__":
    main()
```

### `devtools/split_config.py`（92 行）

```python
# -*- coding: utf-8 -*-
"""split_config.py - 将 config.yaml 的 apps 段拆到 config/apps/（幂等可重跑）

背景（C9）：
    拆分后主文件瘦身为 device/human/trajectory/vision/knowledge/diversify/captcha
    + apps_dir + apps: [] + money_behaviors；逐 App 写 config/apps/<safe_name>.yaml。

用法：
    python devtools/split_config.py [--config config.yaml]

行为：
    1. apps 非空 → 逐 App 写 config/apps/<safe_name>.yaml（App 内原文保序 dump）；
    2. 原文件备份 _backup_pre_fix/config.yaml.pre_split_<ts>；
    3. 主文件瘦身写回；
    4. 已拆分（apps 空且 config/apps 存在）再跑 → 报错退出。
"""
import argparse
import os
import shutil
import sys
import time

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from config_loader import safe_app_name, DEFAULT_APPS_DIR  # noqa: E402

KEEP_TOP_KEYS = ["device", "human", "trajectory", "vision", "knowledge",
                 "diversify", "captcha"]


def split(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    apps = cfg.get("apps") or []
    if not apps:
        if os.path.isdir(cfg.get("apps_dir") or DEFAULT_APPS_DIR):
            print(f"[split_config] 已拆分（apps 为空且 {cfg.get('apps_dir') or DEFAULT_APPS_DIR} 存在），"
                  f"禁止重复拆分")
            return 2
        print("[split_config] apps 为空且未发现 apps 目录，无需拆分")
        return 0

    apps_dir = cfg.get("apps_dir") or DEFAULT_APPS_DIR
    if not os.path.isabs(apps_dir):
        apps_dir = os.path.join(ROOT, apps_dir)
    os.makedirs(apps_dir, exist_ok=True)

    # safe 名冲突检测：同名会互相覆盖，直接报错退出
    safe_names = [safe_app_name(a.get("name", "app")) for a in apps]
    if len(set(safe_names)) != len(safe_names):
        dup = {n for n in safe_names if safe_names.count(n) > 1}
        print(f"[split_config] App 名转安全文件名冲突: {sorted(dup)}，中止")
        return 2

    for i, (a, safe) in enumerate(zip(apps, safe_names)):
        # 文件名带序号前缀：load_config 按文件名排序即可还原 config.yaml 原始顺序
        fp = os.path.join(apps_dir, f"{i + 1:02d}_{safe}.yaml")
        with open(fp, "w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(a, f, allow_unicode=True, sort_keys=False,
                           default_flow_style=False)
        print(f"[split_config] 写 {os.path.relpath(fp, ROOT)}")

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak_dir = os.path.join(ROOT, "_backup_pre_fix")
    os.makedirs(bak_dir, exist_ok=True)
    bak = os.path.join(bak_dir, f"config.yaml.pre_split_{ts}")
    shutil.copy2(config_path, bak)
    print(f"[split_config] 备份 {os.path.relpath(bak, ROOT)}")

    slim = {k: v for k, v in cfg.items() if k in KEEP_TOP_KEYS}
    slim["apps_dir"] = os.path.relpath(apps_dir, ROOT).replace("\\", "/")
    slim["apps"] = []
    slim["money_behaviors"] = ["withdraw"]
    with open(config_path, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(slim, f, allow_unicode=True, sort_keys=False,
                       default_flow_style=False)
    print(f"[split_config] 主文件瘦身完成: {config_path}")
    print(f"[split_config] 共拆分 {len(apps)} 个 App -> {os.path.relpath(apps_dir, ROOT)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="拆分 config.yaml apps 段到 config/apps/")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    args = ap.parse_args()
    sys.exit(split(args.config))


if __name__ == "__main__":
    main()
```

### `devtools/stability_run.py`（213 行）

````python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""多轮稳定性跑批：同一批配置连跑 N 轮，统计每个行为的**命中率**。

为什么需要
----------
单轮 pass/fail 不可信（见 `devtools/calib/ROUND2_FINAL.md` §五）：
同一批配置、同一台设备，不同轮次结果差异显著 ——
一淘.sign 三轮三种结果；火龙漫剧 3 个行为在「全未命中 / 全导航后命中 /
全首屏命中」之间跳。根因是 **App 落地页不确定**（开屏广告 / 活动弹窗 /
新手引导 / 上次退出的 tab / 登录态 / 灰度活动页），不是锚点写错。

所以判定「锚点好不好」「any_of 改造有没有用」必须看多轮统计：
  * 命中率 = 命中的轮数 / 有效轮数（数据作废的轮次不计入分母）
  * 一个只在 1/3 轮命中的锚点，和 3/3 命中的锚点，价值完全不同

命中口径
--------
    命中   = 首屏命中 / 导航后命中 / 导航可救(建议加前置步)
    未命中 = 首屏未命中 / 导航后仍未命中 / 导航后也未命中(不可救)
    作废   = 数据作废(...)  -> 不计入分母（宁可不给结论，也不给错结论）

用法
----
    python devtools/stability_run.py --rounds 3
    python devtools/stability_run.py --rounds 3 --apps 一淘,河马剧场
    python devtools/stability_run.py --rounds 3 --nav-fast --probe-nav
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from config_loader import load_config  # noqa: E402
from calibrate import connect_device, safe_name  # noqa: E402
from verify_live import verify_app  # noqa: E402

HIT_STATUS = {"首屏命中", "导航后命中", "导航可救(建议加前置步)"}
VOID_PREFIX = "数据作废"


def is_void(st):
    return (st or "").startswith(VOID_PREFIX) or st in ("异常", "无锚点动作")


def is_hit(st):
    return st in HIT_STATUS


def aggregate(acc):
    """把 {(app, behavior): [status,...]} 聚合成逐行为统计。

    口径（决定头条指标，务必与文档一致）：
      * valid  = 非作废的轮数（作废轮次**不进分母** —— 宁可不给结论也不给错结论）
      * hits   = valid 里判为命中的轮数
      * rate   = hits / valid；valid 为 0 时 rate=None（该行不参与总命中率）
    返回 (per_behavior, total)；per_behavior 按 (app, behavior) 排序。
    """
    per_behavior = []
    for (app, beh), sts in sorted(acc.items()):
        valid = [s for s in sts if not is_void(s)]
        hits = sum(1 for s in valid if is_hit(s))
        per_behavior.append({
            "app": app, "behavior": beh, "statuses": list(sts),
            "valid": len(valid), "void": len(sts) - len(valid), "hits": hits,
            "rate": (hits / len(valid)) if valid else None,
        })
    total = {
        "hits": sum(x["hits"] for x in per_behavior),
        "valid": sum(x["valid"] for x in per_behavior),
        "void": sum(x["void"] for x in per_behavior),
    }
    return per_behavior, total


def classify(per_behavior):
    """分成 稳定命中 / 波动 / 从未命中 三类（valid=0 的行不进任何一类）。"""
    stable = [x for x in per_behavior if x["valid"] and x["hits"] == x["valid"]]
    flaky = [x for x in per_behavior if x["valid"] and 0 < x["hits"] < x["valid"]]
    never = [x for x in per_behavior if x["valid"] and x["hits"] == 0]
    return stable, flaky, never


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--apps", default=None)
    ap.add_argument("--behaviors", default=None)
    ap.add_argument("--probe-nav", action="store_true")
    ap.add_argument("--nav-fast", action="store_true")
    ap.add_argument("--pause", type=float, default=4.0,
                    help="轮次之间的间隔秒数")
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "STABILITY.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "STABILITY.json"))
    args = ap.parse_args()

    cfg = load_config(args.config)
    vision_cfg = cfg.get("vision") or {}
    serial = (cfg.get("device") or {}).get("serial")

    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None
    apps = [a for a in (cfg.get("apps") or []) if not only or a.get("name") in only]
    apps = [a for a in apps
            if os.path.isdir(os.path.join(HERE, "calib", safe_name(a.get("name", ""))))]

    print(f"待跑 App: {len(apps)} -> {[a['name'] for a in apps]}")
    print(f"轮数: {args.rounds}  probe_nav={args.probe_nav}  nav_fast={args.nav_fast}")
    d = connect_device(serial)

    # {(app, behavior): [status, ...]}
    acc = {}
    all_log = {}
    for rnd in range(1, args.rounds + 1):
        print(f"\n########## 第 {rnd}/{args.rounds} 轮 ##########")
        for a in apps:
            name = a.get("name")
            print(f"\n===== [R{rnd}] {name} =====")
            log = []
            try:
                rows = verify_app(a, only_b, d, vision_cfg, log,
                                  probe_nav=args.probe_nav,
                                  nav_fast=args.nav_fast)
            except Exception as e:
                log.append(f"验证异常: {type(e).__name__}: {e}")
                rows = [{"behavior": "-", "status": "异常", "detail": str(e)}]
            all_log.setdefault(name, []).append({"round": rnd, "log": log})
            for row in rows:
                key = (name, row["behavior"])
                acc.setdefault(key, []).append(row.get("status", "?"))
                print(f"  {row['behavior']:10s} {row['status']:14s} "
                      f"{row.get('detail', '')[:120]}")
            if args.pause:
                time.sleep(args.pause)

    # ---- 汇总 ----
    per_behavior, tot = aggregate(acc)
    tot_h, tot_v, tot_void = tot["hits"], tot["valid"], tot["void"]
    stable_hit, flaky, never = classify(per_behavior)

    print("\n" + "=" * 70)
    print(f"多轮统计（{args.rounds} 轮）")
    print("=" * 70)
    print(f"  总命中: {tot_h}/{tot_v}"
          + (f" = {tot_h / tot_v * 100:.1f}%" if tot_v else "")
          + f"   作废轮次: {tot_void}")
    print(f"  稳定命中（每轮都中）: {len(stable_hit)}")
    print(f"  波动（有时中）      : {len(flaky)}")
    print(f"  从未命中            : {len(never)}")

    def dump(title, items):
        if not items:
            return
        print(f"\n## {title}（{len(items)}）")
        for x in items:
            rate = "-" if x["rate"] is None else f"{x['hits']}/{x['valid']}"
            print(f"  {x['app']:16s} {x['behavior']:10s} {rate:6s} "
                  f"{' | '.join(x['statuses'])}")

    dump("稳定命中", stable_hit)
    dump("波动（重点观察）", flaky)
    dump("从未命中", never)

    md = ["# 多轮稳定性报告", "",
          f"> 生成: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial} · 轮数: {args.rounds} · "
          f"probe_nav={args.probe_nav} nav_fast={args.nav_fast}", "",
          "## 汇总", "",
          f"- 总命中: **{tot_h}/{tot_v}**"
          + (f" = **{tot_h / tot_v * 100:.1f}%**" if tot_v else ""),
          f"- 作废轮次: {tot_void}",
          f"- 稳定命中（每轮都中）: **{len(stable_hit)}**",
          f"- 波动（有时中）: **{len(flaky)}**",
          f"- 从未命中: **{len(never)}**", "",
          "## 逐行为明细", "",
          "| App | 行为 | 命中率 | 各轮状态 |", "|---|---|---|---|"]
    for x in per_behavior:
        rate = "-" if x["rate"] is None else f"{x['hits']}/{x['valid']}"
        md.append(f"| {x['app']} | {x['behavior']} | {rate} | "
                  f"{' / '.join(x['statuses'])} |")
    md += ["", "## 执行日志", ""]
    for name, rounds in all_log.items():
        for item in rounds:
            md.append(f"<details><summary>{name} · 第 {item['round']} 轮</summary>")
            md.append("")
            md.append("```")
            md += item["log"]
            md.append("```")
            md.append("</details>")
            md.append("")

    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    with open(args.md, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    json.dump({"rounds": args.rounds, "per_behavior": per_behavior,
               "total": {"hits": tot_h, "valid": tot_v, "void": tot_void},
               "stable_hit": len(stable_hit), "flaky": len(flaky),
               "never": len(never)},
              open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### `devtools/to_any_of.py`（307 行）

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「导航前置步 + 锚点」改造成 `any_of` 条件分支（消除页面波动带来的失败）。

背景
----
App 启动后的落地页不确定（开屏广告/活动弹窗/新手引导/上次退出的 tab/登录态/
灰度活动页）。同一行为的入口可能在首屏、也可能只在二级页：
  * 写死前置步  → 首屏那条路径被堵死（"先跳走再找"）；
  * 只写首屏锚点 → 页面漂移时全灭。

`any_of` 让两条路径共存：

    - type: any_of
      optional: true
      choices:
      - - type: click_first          # 分支1：首屏直接找
          candidates: [...]
          optional: false            # 必须非 optional，否则"没找到"会被当成成功
      - - type: click_point          # 分支2：先跳「我的」再找
          vlm_prompt: "..."
          x: 0.9
          y: 0.915
          optional: true
        - type: think
        - type: click_first
          candidates: [...]
          optional: false

转换规则
--------
1. 行为里已有「导航前置步」+ 锚点 → 自动转成 any_of（分支1=首屏，分支2=原前置步+锚点）。
2. 无前置步但用 `--add-nav app.behavior,...` 指定 → 也转成 any_of，并补一个
   导航分支（用于「锚点只在二级页、但首屏偶尔也有」的行为）。
3. 已有 any_of 的行为不动（幂等）。

用法
----
    python devtools/to_any_of.py                                  # 预览
    python devtools/to_any_of.py --apply                          # 写回（自动备份）
    python devtools/to_any_of.py --add-nav 今日看点极速版.sign --apply
"""
import argparse
import copy
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")
NAV_MARK = "最右侧"
ANCHOR_TYPES = ("click_first", "click_text", "click_id", "click_desc")

# 标准导航前置步（与 plan_anchor_fixes.NAV_ACTION 等价的结构）
# `vision: false`：跳过视觉兜底，直接用比例坐标。理由：这是**每个行为都要跑**
# 的固定步骤，而本机 VLM 图像请求常 90s 超时；比例坐标已被 18 个 App 实机验证。
# 保留 vlm_prompt 仅作语义标注（devtools 靠它识别「导航前置步」）。
NAV_POINT = {
    "type": "click_point",
    "vlm_prompt": "定位屏幕底部导航栏最右侧的『我的』标签中心",
    "x": 0.9,
    "y": 0.915,
    "vision": False,
    "optional": True,
}

# 需要原样保留的注释（PyYAML dump 会丢注释，写回后补上）
COMMENTS = [
    ("    coord_space: norm1000",
     "    # 坐标空间：norm1000 = 模型返回 0-1000 归一化坐标（本网关实测为默认行为，\n"
     "    # 明确要求并换算后误差可到 ~1px）；pixel = 模型直接返回像素坐标。\n"),
    ("    attempts: 3",
     "    # 每个后端重试次数。网关偶发返回内容安全串（\"User Safety: safe\"）而非 JSON，\n"
     "    # 重试可显著提升可用率。\n"),
]


def is_nav_point(act):
    return (isinstance(act, dict) and act.get("type") == "click_point"
            and NAV_MARK in str(act.get("vlm_prompt", "")))


def is_anchor(act):
    return isinstance(act, dict) and act.get("type") in ANCHOR_TYPES


def convert_one(actions, add_nav=False):
    """把单个行为的动作列表转成 any_of。返回 (new_actions, changed, why)。"""
    if not isinstance(actions, list) or not actions:
        return actions, False, ""
    # 变体结构 [[..],[..]] 暂不处理（保持原样）
    if all(isinstance(a, list) for a in actions):
        return actions, False, "变体结构，跳过"
    # 已经是 any_of
    if any(isinstance(a, dict) and a.get("type") == "any_of" for a in actions):
        return actions, False, "已是 any_of，跳过"

    ai = next((i for i, a in enumerate(actions) if is_anchor(a)), None)
    if ai is None:
        return actions, False, "无锚点动作，跳过"

    anchor = copy.deepcopy(actions[ai])
    pre = [copy.deepcopy(a) for a in actions[:ai]]
    has_nav = any(is_nav_point(a) for a in pre)
    if not has_nav and not add_nav:
        return actions, False, "无前置步（未指定 --add-nav），跳过"

    anchor["optional"] = False          # 分支内必须能"报未命中"
    branch1 = [copy.deepcopy(anchor)]
    if has_nav:
        branch2 = pre + [copy.deepcopy(anchor)]
    else:
        branch2 = [copy.deepcopy(NAV_POINT), {"type": "think"},
                   copy.deepcopy(anchor)]

    any_of = {
        "type": "any_of",
        "optional": bool(anchor_optional(actions[ai])),
        "choices": [branch1, branch2],
    }
    new = [any_of] + [copy.deepcopy(a) for a in actions[ai + 1:]]
    why = "首屏直连 + " + ("原前置步" if has_nav else "补导航分支")
    return new, True, why


def anchor_optional(act):
    return act.get("optional", False)


# 二级页上的「任务/福利」入口候选（与 probe_deep.L2_CANDIDATES 保持一致）。
# 用于三级导航分支：点「我的」后再点这里，才能到签到所在的三级页。
DEEP_L2_CANDIDATES = [
    "任务中心", "福利中心", "我的福利", "福利", "赚钱", "金币",
    "领金币", "天天领", "做任务", "任务", "钱包", "现金",
    "元宝中心", "金币中心", "福利商城", "任务广场", "赚金币",
    "看剧赚钱", "看书赚钱", "看视频赚钱", "我的金币", "现金奖励",
]


def convert_deep(actions, l2_label=None, extra_steps=None):
    """三级导航版 any_of：首屏直连 / 我的 / 我的→(中间步骤)→锚点。

    l2_label   : probe_deep 在二级页实测到的入口**文案**（如 '任务中心'）。
                 为 None 表示「我的」页本身就能命中锚点 -> 只加一层导航。
    extra_steps: 显式指定中间步骤（优先于 l2_label）。
                 用于入口不是 text 而是 desc/坐标的场景，例如抖音系
                 「我的 → ≡更多(desc='更多') → 金币」：
                     extra_steps=[{"type": "click_desc", "desc": "更多",
                                   "timeout": 6, "optional": False}]
    """
    if not isinstance(actions, list) or not actions:
        return actions, False, ""
    if all(isinstance(a, list) for a in actions):
        return actions, False, "变体结构，跳过"
    if any(isinstance(a, dict) and a.get("type") == "any_of" for a in actions):
        return actions, False, "已是 any_of，跳过"
    ai = next((i for i, a in enumerate(actions) if is_anchor(a)), None)
    if ai is None:
        return actions, False, "无锚点动作，跳过"

    anchor = copy.deepcopy(actions[ai])
    anchor["optional"] = False
    branch1 = [copy.deepcopy(anchor)]

    mid = []
    if extra_steps:
        mid = [copy.deepcopy(a) for a in extra_steps]
        why = "三级导航(我的→自定义入口)"
    elif l2_label:
        cands = [{"type": "text", "value": l2_label}]
        cands += [{"type": "text", "value": kw}
                  for kw in DEEP_L2_CANDIDATES if kw != l2_label]
        mid = [{"type": "click_first", "candidates": cands,
                "timeout": 8, "optional": False}]
        why = f"三级导航(我的→{l2_label})"
    else:
        why = "二级导航(我的)"

    branch2 = [copy.deepcopy(NAV_POINT), {"type": "think"}]
    for st in mid:
        branch2.append(copy.deepcopy(st))
        branch2.append({"type": "think"})
    branch2.append(copy.deepcopy(anchor))

    any_of = {
        "type": "any_of",
        "optional": bool(anchor_optional(actions[ai])),
        "choices": [branch1, branch2],
    }
    new = [any_of] + [copy.deepcopy(a) for a in actions[ai + 1:]]
    return new, True, why


def restore_comments(text):
    for line, comment in COMMENTS:
        if line in text and comment not in text:
            text = text.replace(line, comment + line, 1)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--add-nav", default=None,
                    help="逗号分隔的 app.behavior，无前置步也补导航分支")
    ap.add_argument("--deep-json", default=None,
                    help="probe_deep.py 产出的 DEEP_PROBE.json（可逗号分隔多个）；"
                         "对其中命中的 app.behavior 加三级导航分支")
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    args = ap.parse_args()

    import yaml
    cfg = load_config(args.config)

    # 探针结果 -> {(app, behavior): 二级入口文案 or None(我的页即命中)}
    # 支持多个探针文件（分轮跑的合并）
    deep_map = {}
    if args.deep_json:
        import json
        for path in [p.strip() for p in args.deep_json.split(",") if p.strip()]:
            if not os.path.exists(path):
                print(f"⚠ 探针文件不存在，跳过: {path}")
                continue
            with open(path, encoding="utf-8") as f:
                rows = json.load(f)
            for r in rows:
                if r.get("error"):
                    continue
                if r.get("l3"):
                    lab = (r.get("l2") or "")
                    lab = lab.split("=", 1)[1] if "=" in lab else None
                    deep_map[(r["app"], r["behavior"])] = lab or None
                elif r.get("on_l2"):
                    deep_map[(r["app"], r["behavior"])] = None
        print(f"探针结果可用: {len(deep_map)} 项 -> "
              f"{sorted(f'{a}.{b}' for a, b in deep_map)}")

    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    force = set(x.strip() for x in args.add_nav.split(",")) if args.add_nav else set()

    changed = []
    changed_apps = {}
    for app in cfg.get("apps") or []:
        name = app.get("name")
        if only and name not in only:
            continue
        for bid, actions in (app.get("behaviors") or {}).items():
            if not actions:
                continue
            key = f"{name}.{bid}"
            if (name, bid) in deep_map:
                new, ch, why = convert_deep(actions, deep_map[(name, bid)])
            else:
                new, ch, why = convert_one(actions, add_nav=(key in force))
            if ch:
                app["behaviors"][bid] = new
                changed.append((key, why))
                changed_apps[name] = app

    if not changed:
        print("没有需要转换的行为")
        return 0
    print(f"计划转换 {len(changed)} 个行为为 any_of：")
    for key, why in changed:
        print(f"  {key}  ({why})")

    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    # 拆分后：逐 App 文件写回（App 级文件无注释，直接 dump）
    for name in sorted(changed_apps):
        app = changed_apps[name]
        path = app_config_path(name)
        bak = f"{path}.bak-anyof-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak)
        out = yaml.dump(app, allow_unicode=True, sort_keys=False,
                        default_flow_style=False, width=200)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(out)
        print(f"已写回 {path}\n备份: {bak}")

    # 复验
    try:
        cfg2 = load_config(args.config)
        n = sum(1 for a in cfg2["apps"] for b, acts in (a.get("behaviors") or {}).items()
                if isinstance(acts, list) and any(
                    isinstance(x, dict) and x.get("type") == "any_of" for x in acts))
        print(f"复验: 加载成功, {len(cfg2['apps'])} 个 app, "
              f"{n} 个行为已用 any_of")
    except Exception as ex:
        print(f"复验失败: {ex}（各 App 备份文件已保留，可手动回滚）")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/verify_coverage.py`（38 行）

```python
# -*- coding: utf-8 -*-
"""verify_coverage.py - 覆盖率验收门（CI 用，退出码 0=PASS / 1=FAIL）

用法：
    ./.venv/Scripts/python.exe devtools/verify_coverage.py

判据：total == verifiable 且 unverifiable == 0。

"可校验"= 该 routine 的每一步都能被 dry-run 规划出来（有明确的 type 与目标）。
"不可校验"通常意味着出现了 verify_live 认不出的锚点类型 —— 那批行为是
**完全没被度量**的，命中率分母里没有它，所以必须让它以非零退出码暴露出来。
"""
import json
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from webui.data import Store  # noqa: E402

CONFIG = os.path.join(BASE, "config.yaml")
DB = os.path.join(tempfile.gettempdir(), "autopilot_coverage.db")


def main() -> int:
    store = Store(CONFIG, DB)
    rep = store.verify_coverage()
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    ok = (rep.get("total") == rep.get("verifiable")
          and rep.get("unverifiable", 1) == 0)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

### `devtools/verify_live.py`（731 行）

````python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""实机锚点验证：对已修补的行为做「真机回归」。

与 calibrate.py 的区别：
  calibrate.py 只校验**落地页**，而签到/看视频/提现这类入口几乎都在二级页
  （底部导航「我的」之后）。本次修补的核心就是「前置导航步 + 追加候选」，
  因此验证必须走完整链路：

      启动 App -> 自适应等待就绪 -> 关闭弹窗 -> dump(落地页)
        -> 校验锚点
          命中  -> 首屏命中
          未命中且该行为有前置步 -> VLM/比例坐标点『我的』-> dump(二级页)
                                   -> 再校验 -> 导航后命中 / 导航后仍未命中
          未命中且无前置步 -> 首屏未命中

用法：
    python devtools/verify_live.py                        # 全部有校准数据的 App
    python devtools/verify_live.py --apps 一淘,河马剧场
    python devtools/verify_live.py --behaviors watch,collect
    python devtools/verify_live.py --out devtools/calib/LIVE_VERIFY.md
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from config_loader import load_config  # noqa: E402
from calibrate import (  # noqa: E402
    parse_nodes, match_selector, wait_ready, dismiss_popups,
    connect_device, safe_name,
    dominant_package, page_belongs_to,
)
# 页面结构判据与执行器共用同一份实现（度量与执行必须同口径）
from ui_page import NAV_LABELS, NAV_BAND_Y, at_top_level_nodes  # noqa: E402

ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")
POINT_TYPE = "click_point"
NAV_MARK = "最右侧"

# 底部导航标签（NAV_LABELS）与底部带阈值（NAV_BAND_Y）单一来源在 ui_page.py，
# 上面已 import；此处不再另立一份，避免与执行器口径漂移。


def is_anchor_action(action):
    """该动作是不是「可校验的锚点」（口径与 webui/data.py::is_anchor 一致）。

    click_point 是**重载**类型，必须按载荷区分用途（本工程实测分布 68 / 31 / 0）：
      * 带 images/template      —— OpenCV 模板匹配锚点（一等定位手段，**算锚点**）
      * 带「最右侧」vlm_prompt  —— 「导航到我的」前置步（比例坐标兜底，不算锚点）
      * 两者皆无                —— 纯比例坐标兜底（不算锚点）
    踩坑：早期只把 click_text/id/desc/click_first 当锚点，于是 68 个图像锚点
    动作所在的行为被记成「无锚点动作」→ stability_run 当废、**不进命中率分母**。
    """
    if not isinstance(action, dict):
        return False
    t = action.get("type")
    if t in ANCHOR_TYPES:
        return True
    if t == POINT_TYPE:
        return bool(action.get("images") or action.get("template"))
    return False


def act_has_image_anchor(act):
    """该锚点动作（含 any_of 各分支）里是否含**图像锚点**（需要截图做模板匹配）。"""
    if isinstance(act, dict) and act.get("type") == "any_of":
        for ch in act.get("choices") or []:
            steps = ch if isinstance(ch, list) else [ch]
            for a in steps:
                if is_anchor_action(a) and a.get("type") == POINT_TYPE:
                    return True
        return False
    return bool(isinstance(act, dict) and act.get("type") == POINT_TYPE
                and (act.get("images") or act.get("template")))

# 前置步兜底坐标。实测各 App『我的』中心 y 分布在 2106~2192，
# 取中位数附近 (0.90, 0.915) 比原来的 0.908 更稳。
MINE_XY = (0.90, 0.915)

NAV_PROMPTS = [
    "定位屏幕底部导航栏最右侧的『我的』标签中心",
    "定位屏幕底部导航栏最右侧的『我』标签中心",
    "定位屏幕底部导航栏的个人中心（我的）标签中心",
]


def _variant_of(actions):
    if not actions:
        return []
    if all(isinstance(a, list) for a in actions):
        return actions[0] or []
    return actions


def first_anchor_action(actions):
    """返回 (索引, 动作)；行为可能是 [[..],[..]] 变体结构。

    `any_of` 也算锚点动作（真正的锚点在其 choices 里），由 check_anchor 展开。
    """
    for i, act in enumerate(_variant_of(actions)):
        if isinstance(act, dict) and act.get("type") in ANCHOR_TYPES + ("any_of",):
            return i, act
    return None, None


def has_prelude(actions):
    """该行为是否带「导航到我的」前置步（含 any_of 分支内的）。"""
    for act in _variant_of(actions):
        if not isinstance(act, dict):
            continue
        if act.get("type") == "click_point" and NAV_MARK in str(act.get("vlm_prompt", "")):
            return True
        if act.get("type") == "any_of":
            for ch in act.get("choices") or []:
                for a in (ch if isinstance(ch, list) else [ch]):
                    if isinstance(a, dict) and a.get("type") == "click_point" \
                            and NAV_MARK in str(a.get("vlm_prompt", "")):
                        return True
    return False


def _anchor_actions_of_branch(steps):
    return [a for a in steps if is_anchor_action(a)]


def mid_entry_of(act):
    """三级导航的**中间入口**动作（没有则返回 None）。

    三级分支形如 `[我的, think, 福利中心, think, 签到]`：
    末位是目标锚点，**中间**那个锚点类动作就是入口。
    verify_live 只走到「我的」是不够的 —— 必须继续点中间入口，
    否则三级行为会被必然误判为未命中。
    """
    if not isinstance(act, dict) or act.get("type") != "any_of":
        return None
    for ch in act.get("choices") or []:
        steps = ch if isinstance(ch, list) else [ch]
        anchors = _anchor_actions_of_branch(steps)
        if len(anchors) > 1:
            return anchors[-2]          # 末位是目标，倒数第二个是入口
    return None


def target_anchor_of(act):
    """取「真正的目标锚点」动作（any_of 则取某分支的末位锚点）。"""
    if isinstance(act, dict) and act.get("type") == "any_of":
        for ch in act.get("choices") or []:
            steps = ch if isinstance(ch, list) else [ch]
            anchors = _anchor_actions_of_branch(steps)
            if anchors:
                return anchors[-1]
        return None
    return act


def _screen_gray(screen_img):
    """把 PIL/ndarray 截图转成灰度 ndarray（与 vision.locate_on_screen 同款逻辑）。"""
    try:
        from PIL import Image
        import numpy as np
        import cv2
        if isinstance(screen_img, Image.Image):
            arr = np.array(screen_img.convert("RGB"))
            return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        arr = np.asarray(screen_img)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if arr.ndim == 3 else arr
    except Exception:
        return None


def _image_templates(act):
    """提取 click_point 的参考图列表（images + template，与 executor 同语义）。"""
    tpls = list(act.get("images") or [])
    tpl = act.get("template")
    if tpl:
        if isinstance(tpl, (list, tuple)):
            tpls = list(tpl) + tpls
        else:
            tpls = [tpl] + tpls
    return tpls


def _check_image_anchor(act, screen_img, vision):
    """图像锚点校验：OpenCV 模板匹配（与 executor._step_click_point 同口径，不进 VLM）。"""
    templates = _image_templates(act)
    if not templates:
        return False, "click_point 无参考图（纯比例兜底，不算锚点）"
    if vision is None or not vision.template_available:
        return False, "图像锚点但视觉组件不可用（OpenCV 未就绪）"
    if screen_img is None:
        return False, "图像锚点但无屏幕截图（本轮无法度量）"
    gray = _screen_gray(screen_img)
    if gray is None:
        return False, "图像锚点截图转灰度失败"
    for tpl in templates:
        hit = vision.match_template(gray, tpl)
        if hit is not None:
            return True, (f"图像锚点 {os.path.basename(str(tpl))} "
                          f"score={hit.score:.3f} scale={hit.scale} -> "
                          f"({hit.x:.0f},{hit.y:.0f})")
    return False, f"图像锚点全部未命中（{len(templates)} 张参考图）"


def _find_image_anchor(act, screen_img, vision):
    """在截图里定位图像锚点，返回 (伪节点, detail)；伪节点带 center 可直接点击。"""
    templates = _image_templates(act)
    if not templates:
        return None, "click_point 无参考图（纯比例兜底，不算锚点）"
    if vision is None or not vision.template_available:
        return None, "图像锚点但视觉组件不可用（OpenCV 未就绪）"
    if screen_img is None:
        return None, "图像锚点但无屏幕截图（本轮无法度量）"
    gray = _screen_gray(screen_img)
    if gray is None:
        return None, "图像锚点截图转灰度失败"
    for tpl in templates:
        hit = vision.match_template(gray, tpl)
        if hit is not None:
            return ({"center": (int(hit.x), int(hit.y))},
                    f"图像锚点 {os.path.basename(str(tpl))} "
                    f"score={hit.score:.3f} -> ({hit.x:.0f},{hit.y:.0f})")
    return None, f"图像锚点全部未命中（{len(templates)} 张参考图）"


def find_anchor_node(nodes, act, screen_h=None, screen_img=None, vision=None):
    """返回 (node, detail)；node 为命中的节点（可直接点击），未命中为 None。"""
    t = act.get("type")
    if t == POINT_TYPE:
        return _find_image_anchor(act, screen_img, vision)
    if t == "click_first":
        for c in act.get("candidates") or []:
            if not isinstance(c, dict):
                continue
            kind = c.get("type", "text")
            val = c.get("value", "")
            hits = [h for h in match_selector(nodes, kind, val)
                    if _ok_len(h, val, kind)]
            good = [h for h in hits if _nav_ok(h, val, screen_h)]
            if good:
                return good[0], f"{kind}={val!r} @{good[0]['center']}"
        return None, "candidates 全部未命中"
    if t in ("click_text", "click_desc"):
        kind = "text" if t == "click_text" else "desc"
        val = act.get("text" if kind == "text" else "desc", "")
        hits = [h for h in match_selector(nodes, kind, val)
                if _ok_len(h, val, kind)]
        good = [h for h in hits if _nav_ok(h, val, screen_h)]
        return (good[0], f"{kind}={val!r} @{good[0]['center']}") if good \
            else (None, f"{kind}={val!r} 未命中")
    if t == "click_id":
        hits = match_selector(nodes, "id", act.get("res_id", ""))
        return (hits[0], f"id={act.get('res_id')!r}") if hits else (None, "id 未命中")
    return None, f"非锚点动作 type={t}"


def check_anchor(nodes, act, screen_h=None, screen_img=None, vision=None):
    """按执行器语义校验单个锚点动作，返回 (hit, detail)。

    screen_h 给出时，对**底部导航标签**做位置合理性校验：命中的 y 必须落在
    屏幕底部带（y >= NAV_BAND_Y * screen_h），否则判为假命中。
    screen_img/vision 供**图像锚点**（click_point 带参考图）做 OpenCV 模板匹配。
    """
    t = act.get("type")
    if t == POINT_TYPE:
        return _check_image_anchor(act, screen_img, vision)
    if t == "any_of":
        # 一个分支是否命中，取决于该分支的**最后一个**锚点动作（真正的目标），
        # 而不是中途的入口。
        # 踩坑：三级导航分支形如
        #   [我的, think, 福利中心, think, 签到]
        # 中间那步「福利中心」也是锚点类动作；早期实现"分支里任一锚点命中即算命中"，
        # 于是「福利中心」在落地页出现时就报成 `首屏命中 分支#2: text='福利'`
        # —— 看起来命中，实际签到锚点根本没出现（实测污染了 3 个三级行为）。
        #
        # 另注：convert_deep 生成的两条分支**共用同一个目标锚点**，
        # 所以单份 dump 上分支2不会比分支1多命中；分支2 的价值在于
        # 「换一个页面再找」（由 导航后 复校那一步体现）。
        last = "（无分支）"
        for i, ch in enumerate(act.get("choices") or []):
            steps = ch if isinstance(ch, list) else [ch]
            anchors = _anchor_actions_of_branch(steps)
            if not anchors:
                continue
            hit, det = check_anchor(nodes, anchors[-1], screen_h,
                                    screen_img, vision)
            if hit:
                return True, f"any_of 分支#{i + 1}: {det}"
            last = det
        return False, f"any_of 全部分支未命中（末次: {last}）"
    if t == "click_first":
        first_miss = None
        for c in act.get("candidates") or []:
            if not isinstance(c, dict):
                continue
            kind = c.get("type", "text")
            val = c.get("value", "")
            hits = match_selector(nodes, kind, val)
            hits = [h for h in hits if _ok_len(h, val, kind)]
            if not hits:
                continue
            good = [h for h in hits if _nav_ok(h, val, screen_h)]
            if good:
                return True, f"{kind}={val!r} @{good[0]['center']}"
            if first_miss is None:
                first_miss = (f"{kind}={val!r} @{hits[0]['center']} "
                              f"但不在底部导航带（y={hits[0]['center'][1]}），"
                              f"疑似假命中")
        if first_miss:
            return False, first_miss
        vals = [c.get("value") for c in act.get("candidates") or []
                if isinstance(c, dict)]
        return False, f"candidates={vals} 全部未命中"
    if t == "click_text":
        return _check_single(nodes, "text", act.get("text", ""),
                             act.get("text", ""), screen_h)
    if t == "click_desc":
        return _check_single(nodes, "desc", act.get("desc", ""),
                             act.get("desc", ""), screen_h)
    if t == "click_id":
        hits = match_selector(nodes, "id", act.get("res_id", ""))
        return (bool(hits),
                f"id={act.get('res_id')!r}" + (f" @{hits[0]['center']}" if hits else " 未命中"))
    return False, f"非锚点动作 type={t}"


def _nav_ok(node, label, screen_h):
    """底部导航标签的位置合理性校验。"""
    if screen_h is None or str(label).strip() not in NAV_LABELS:
        return True
    return node["center"][1] >= NAV_BAND_Y * screen_h


def _check_single(nodes, kind, value, label, screen_h):
    hits = match_selector(nodes, kind, value)
    hits = [h for h in hits if _ok_len(h, value, kind)]
    if not hits:
        return False, f"{kind}={label!r} 未命中"
    good = [h for h in hits if _nav_ok(h, label, screen_h)]
    if good:
        return True, f"{kind}={label!r} @{good[0]['center']}"
    return False, (f"{kind}={label!r} @{hits[0]['center']} "
                   f"但不在底部导航带（y={hits[0]['center'][1]}），疑似假命中")


def _ok_len(node, target, kind):
    """复刻执行器的「长文案拒配」。"""
    if kind not in ("text", "desc"):
        return True
    label = node["text"] if kind == "text" else node["desc"]
    limit = max(len(str(target)) + 6, len(str(target)) * 3)
    if len(label) > limit and not node["clickable"]:
        return False
    return True


def goto_mine(d, vision_cfg, log, use_vlm=True):
    """导航到『我的』：优先 VLM 定位，失败用比例坐标兜底。返回新 dump 的 nodes。

    use_vlm=False 时直接走比例坐标 —— 探路跑批时用，因为本机 VLM 图像请求
    常 90s 超时（一次导航可能耗 9~27 分钟），而比例坐标兜底已被实机验证可靠
    （多数 App 的『我的』就在 x≈0.90 / y≈0.91）。
    """
    x, y = None, None
    if use_vlm:
        try:
            import vision as vs
            loc = vs.VisionLocator(vision_cfg or {}, base_dir=ROOT)
            if loc.enabled and loc.vlm_available:
                img = d.screenshot()
                for p in NAV_PROMPTS:
                    hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                               app="verify", tag="nav")
                    if hit is not None:
                        x, y = hit.x, hit.y
                        log.append(f"导航: VLM 命中『{p}』-> ({x},{y})")
                        break
                if x is None:
                    log.append("导航: VLM 全部提示词未命中，回退比例坐标")
            else:
                log.append("导航: VLM 不可用，用比例坐标")
        except Exception as e:
            log.append(f"导航: VLM 异常 {type(e).__name__}: {e}，用比例坐标")
    else:
        log.append("导航: --nav-fast 跳过 VLM，直接用比例坐标")
    if x is None:
        w, h = d.window_size()
        x, y = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
        log.append(f"导航: 比例坐标 -> ({x},{y})")
    d.click(x, y)
    time.sleep(3.5)
    xml = d.dump_hierarchy()
    return parse_nodes(xml), (x, y), xml


def at_top_level(nodes, screen_h=None):
    """判断当前页是否是 App 的**顶层页**（带底部导航栏）。

    实现见 ui_page.at_top_level_nodes —— 与执行器共用同一份判据，
    否则「离线统计说能命中、真机执行却失败」这类脱钩问题无法被发现。

    行为之间必须复位，否则会串味：实测喜番 sign 走三级导航
    （我的 → 福利中心 → 签到）后被留在「签到」二级页，紧随的 watch
    从脏页面起步，比例坐标 (972,2141) 点飞到了 com.eggflower.read（蛋花）。
    """
    return at_top_level_nodes(nodes, screen_h)


def reset_to_landing(d, pkg, log, screen_h=None, max_back=3):
    """把 App 退回顶层页并返回新的 (xml, nodes)。

    策略：**先判断、后动作** ——
      1) 已经在顶层页且页面属于目标 App -> 直接返回，一个 BACK 都不按；
      2) 否则按 BACK（快、不触发开屏广告），每次都校验页面仍属于目标 App；
      3) 退不回去 -> stop + start（确定但慢，约 20~30s）。

    为什么必须先判断：多数 App 在顶层页（如「我的」tab）按 BACK 会**直接退出
    App**。实测复位前不看一眼就按，喜番 withdraw 那次一按就退到桌面
    （主导包 com.vivo.vtouch），白白多吃一次冷启动。

    踩坑（铁律）：开屏广告期按 BACK 会直接退出 App，故 BACK 后一旦发现
    已不在目标 App，立刻改走重启，不再继续按。
    """
    xml = d.dump_hierarchy()
    nodes = parse_nodes(xml)
    ok, dom, _m, _n = page_belongs_to(xml, pkg)
    if ok and at_top_level(nodes, screen_h):
        log.append("复位: 已在顶层页，无需 BACK")
        return xml, nodes
    for i in range(1, max_back + 1):
        try:
            d.press("back")
        except Exception as e:
            log.append(f"复位: BACK 异常 {type(e).__name__}: {e}")
            break
        time.sleep(1.5)
        xml = d.dump_hierarchy()
        nodes = parse_nodes(xml)
        ok, dom, _m, _n = page_belongs_to(xml, pkg)
        if not ok:
            log.append(f"复位: 第{i}次 BACK 后已不在目标 App（主导包 {dom}）"
                       f"-> 改走重启")
            break
        if at_top_level(nodes, screen_h):
            log.append(f"复位: 第{i}次 BACK 回到顶层页")
            return xml, nodes
    log.append("复位: BACK 未能回到顶层页 -> 重启 App")
    try:
        d.app_stop(pkg)
    except Exception as e:
        log.append(f"复位: stop 异常 {type(e).__name__}: {e}")
    try:
        d.app_start(pkg, wait=True)
    except Exception as e:
        log.append(f"复位: 重启异常 {type(e).__name__}: {e}")
    xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
    dismiss_popups(d, nodes, log)
    return xml, nodes


def verify_app(app_cfg, behaviors, d, vision_cfg, log, probe_nav=False,
               nav_fast=False):
    name = app_cfg.get("name")
    pkg = app_cfg.get("package")
    rows = []
    # 屏幕高度：用于底部导航标签的位置合理性校验
    try:
        _w, screen_h = d.window_size()
    except Exception:
        screen_h = None
    # 视觉组件：图像锚点（click_point 带参考图）需要 OpenCV 模板匹配来校验。
    vs = None
    try:
        import vision as vs_mod
        vs = vs_mod.VisionLocator(vision_cfg or {}, base_dir=ROOT)
    except Exception as e:
        log.append(f"视觉组件初始化失败（图像锚点将无法度量）: "
                   f"{type(e).__name__}: {e}")
    # 惰性截图：只在当前行为含图像锚点时截，页面变化后强制重截
    _screen_cache = {"img": None}

    def _fresh_screen():
        _screen_cache["img"] = None

    def _screen():
        if _screen_cache["img"] is None:
            try:
                _screen_cache["img"] = d.screenshot()
            except Exception:
                _screen_cache["img"] = None
        return _screen_cache["img"]
    # 启动 + 归属校验，最多试 2 次（偶发启动失败会停留上一个 App）
    xml, nodes, waited = "", [], 0.0
    ok_page, dom, mine, dom_n, fg = False, "", 0, 0, ""
    for attempt in (1, 2):
        log.append(f"启动 {pkg}（第 {attempt} 次）")
        try:
            d.app_start(pkg, wait=True)
        except Exception as e:
            log.append(f"启动失败: {type(e).__name__}: {e}")
        xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
        log.append(f"就绪: 节点={len(nodes)} 等待={waited:.1f}s")
        dismiss_popups(d, nodes, log)
        try:
            fg = d.info.get("currentPackageName") or ""
        except Exception:
            fg = ""
        # 归属判定以 dump 自身为准：崩溃/切换时序下前台包名会失真
        ok_page, dom, mine, dom_n = page_belongs_to(xml, pkg)
        log.append(f"归属校验: dump 主导包={dom}（{dom_n} 节点） 目标包={mine} 节点"
                   f" 前台={fg} -> {'属于目标 App' if ok_page else '不属于目标 App'}")
        if ok_page:
            break
        log.append("归属校验失败" + ("，重试一次" if attempt == 1 else ""))
        time.sleep(3)

    # 页面归属：dump 到的必须真是目标 App。
    # 踩坑：若目标 App 启动失败/崩溃，前台会停留在**上一个 App**，
    # 于是两个 App 会得到完全相同的坐标（看似合理、实为垃圾数据）。
    # 宁可不给结论，也不要给出错误结论。
    if not ok_page:
        log.append(f"归属校验最终失败 -> 本轮结果作废（dump 主导包 {dom}，前台 {fg}）")
        return [{"behavior": "-", "status": "数据作废(页面非目标App)",
                 "detail": f"期望 {pkg}；dump 主导包 {dom}（{dom_n} 节点），"
                           f"目标包 {mine} 节点；前台 {fg}",
                 "prelude": False}]

    bcfg = app_cfg.get("behaviors") or {}
    targets = [b for b in (behaviors or bcfg.keys()) if bcfg.get(b)]
    # 行为间复位标记：上一个行为导航过（离开顶层页）就置脏，下一个行为
    # 开始前必须先复位，否则量到的是「上一行为留下的页面」。
    dirty = False
    for bid in targets:
        if dirty:
            xml, nodes = reset_to_landing(d, pkg, log, screen_h)
            dirty = False
        actions = bcfg[bid]
        idx, act = first_anchor_action(actions)
        if act is None:
            rows.append({"behavior": bid, "status": "无锚点动作",
                         "detail": "该行为无 click_* 动作", "prelude": has_prelude(actions)})
            continue
        prelude = has_prelude(actions)
        need_img = act_has_image_anchor(act)
        if need_img:
            _fresh_screen()
        hit, detail = check_anchor(nodes, act, screen_h,
                                   _screen() if need_img else None, vs)
        if hit:
            rows.append({"behavior": bid, "status": "首屏命中",
                         "detail": detail, "prelude": prelude})
            log.append(f"  {bid}: 首屏命中 {detail}")
            continue
        if not prelude and not probe_nav:
            rows.append({"behavior": bid, "status": "首屏未命中",
                         "detail": detail, "prelude": False})
            log.append(f"  {bid}: 首屏未命中（无前置步）{detail}")
            continue
        # 走前置步（probe_nav 时即使配置里没有前置步也试一次，用于判断
        # 「这个未命中能否靠导航到我的救回」）。
        # 实测导航有波动（同一 App 两次跑结果可能不同），故最多试 2 轮。
        dirty = True        # 下面一定会离开顶层页
        log.append(f"  {bid}: 首屏未命中，执行前置导航"
                   + ("（probe-nav 探路）" if not prelude else ""))
        # 三级导航行为（如 sign：我的 → 福利中心 → 签到）：只走到「我的」不够，
        # 必须继续点中间入口，否则三级行为必然被误判为未命中。
        mid = mid_entry_of(act)
        tgt = target_anchor_of(act) or act
        if mid is not None:
            log.append(f"  {bid}: 检测到三级导航，中间入口 = "
                       f"{mid.get('candidates') or mid.get('text') or mid.get('desc')}")
        hit2, detail2, nodes2, xy = False, detail, [], None
        void_rounds = 0
        for attempt in (1, 2):
            hit2 = False
            nodes2, xy, xml2 = goto_mine(d, vision_cfg, log, use_vlm=not nav_fast)
            dismiss_popups(d, nodes2, log)
            ok2, dom2, _mine2, dom2_n = page_belongs_to(xml2, pkg)
            if not ok2:
                void_rounds += 1
                log.append(f"  {bid}: 第{attempt}轮导航后页面不属于目标 App"
                           f"（主导包 {dom2}，{dom2_n} 节点）-> 本轮作废")
                continue
            hit2, detail2 = check_anchor(nodes2, tgt, screen_h)
            log.append(f"  {bid}: 第{attempt}轮导航后 "
                       f"{'命中' if hit2 else '仍未命中'} {detail2}")
            # 二级页没找到目标 -> 再点中间入口，进三级页找
            if not hit2 and mid is not None:
                node, det_mid = find_anchor_node(nodes2, mid, screen_h)
                if node is None:
                    log.append(f"  {bid}: 第{attempt}轮二级页未找到中间入口 {det_mid}")
                else:
                    cx, cy = node["center"]
                    log.append(f"  {bid}: 点中间入口 {det_mid}")
                    d.click(cx, cy)
                    time.sleep(3.5)
                    xml3 = d.dump_hierarchy()
                    nodes3 = parse_nodes(xml3)
                    dismiss_popups(d, nodes3, log)
                    ok3, dom3, _m3, _d3 = page_belongs_to(xml3, pkg)
                    if not ok3:
                        log.append(f"  {bid}: 三级页不属于目标 App（主导包 {dom3}）")
                    else:
                        hit2, detail2 = check_anchor(nodes3, tgt, screen_h)
                        log.append(f"  {bid}: 第{attempt}轮三级页 "
                                   f"{'命中' if hit2 else '仍未命中'} {detail2}")
                        if hit2:
                            detail2 = f"（三级页）{detail2}"
            if hit2:
                break
            if attempt == 1:
                log.append(f"  {bid}: 第1轮未命中，回退首页重试一次")
                try:
                    d.press("back")
                    time.sleep(2)
                except Exception:
                    pass
        if hit2:
            # 原本没前置步、导航后才命中 -> 说明补前置步能救回
            status = "导航后命中" if prelude else "导航可救(建议加前置步)"
        elif void_rounds >= 2:
            # 两轮导航都落在别的 App 上：这是**测量无效**，不是「未命中」。
            # 计入未命中分母会系统性低估命中率（实测喜番 watch 就这样被误判）。
            status = "数据作废(导航后页面非目标App)"
        else:
            status = "导航后仍未命中" if prelude else "导航后也未命中(不可救)"
        rows.append({"behavior": bid, "status": status,
                     "detail": f"{detail} | 二级页: {detail2}",
                     "nav_xy": xy, "prelude": prelude,
                     "nodes_after": len(nodes2)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    ap.add_argument("--behaviors", default=None, help="逗号分隔，限定行为")
    ap.add_argument("--out", default=os.path.join(HERE, "calib", "LIVE_VERIFY.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "LIVE_VERIFY.json"))
    ap.add_argument("--probe-nav", action="store_true",
                    help="所有未命中项都试一次导航到『我的』，"
                         "用于判断能否靠前置步救回")
    ap.add_argument("--nav-fast", action="store_true",
                    help="导航到『我的』时跳过 VLM，直接用比例坐标"
                         "（本机 VLM 图像请求常 90s 超时，跑批时建议开启）")
    args = ap.parse_args()

    cfg = load_config(args.config)
    vision_cfg = cfg.get("vision") or {}
    serial = (cfg.get("device") or {}).get("serial")

    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None

    apps = [a for a in (cfg.get("apps") or [])
            if not only or a.get("name") in only]
    # 只验证有校准数据的 App（无 dump 的说明还没跑过校准）
    apps = [a for a in apps
            if os.path.isdir(os.path.join(HERE, "calib", safe_name(a.get("name", ""))))]

    print(f"待验证 App: {len(apps)} -> {[a['name'] for a in apps]}")
    d = connect_device(serial)

    report = {}
    all_log = {}
    for a in apps:
        name = a.get("name")
        print(f"\n===== {name} =====")
        log = []
        try:
            rows = verify_app(a, only_b, d, vision_cfg, log,
                              probe_nav=args.probe_nav,
                              nav_fast=args.nav_fast)
        except Exception as e:
            log.append(f"验证异常: {type(e).__name__}: {e}")
            rows = [{"behavior": "-", "status": "异常", "detail": str(e)}]
        report[name] = rows
        all_log[name] = log
        for r in rows:
            print(f"  {r['behavior']:10s} {r['status']:14s} {r['detail'][:200]}")

    # 汇总
    stat = {}
    for rows in report.values():
        for r in rows:
            stat[r["status"]] = stat.get(r["status"], 0) + 1
    print("\n===== 汇总 =====")
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    md = ["# 实机锚点回归报告", "",
          f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial}", "", "## 汇总", ""]
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        md.append(f"- {k}: **{v}**")
    md.append("")
    for name, rows in report.items():
        md.append(f"## {name}")
        md.append("")
        md.append("| 行为 | 结果 | 明细 | 前置步 |")
        md.append("|---|---|---|---|")
        for r in rows:
            md.append(f"| {r['behavior']} | {r['status']} | {r['detail']} | "
                      f"{'有' if r.get('prelude') else '-'} |")
        md.append("")
        md.append("<details><summary>执行日志</summary>")
        md.append("")
        md.append("```")
        md += all_log.get(name, [])
        md.append("```")
        md.append("")
        md.append("</details>")
        md.append("")
    open(args.out, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump({"report": report, "stat": stat},
              open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n报告: {args.out}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
````

### `devtools/vlm_bench.py`（94 行）

```python
# -*- coding: utf-8 -*-
"""vlm_bench.py - VLM 定位后端量化基准

为什么需要它：VLM 定位是"元素定位失败后的最后兜底"，一旦它幻觉出坐标，
executor 会照着错误坐标去点——可能点到广告、甚至点到提现/支付按钮。
所以必须量化两件事：
  - 正向命中率与像素误差（目标真实存在时）
  - 负向误报率（目标不存在时是否仍给出坐标）

用法：
    python devtools/vlm_bench.py --image devtools/out/p1.png --trials 5
    python devtools/vlm_bench.py --image p1.png --positive "设置:173,1609" \
        --negative "抖音" --negative "网易云音乐"
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import vision as vs  # noqa: E402


def build_locator():
    try:
        import yaml
        with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
            cfg = (yaml.safe_load(f) or {}).get("vision") or {}
    except Exception:
        cfg = {}
    return vs.VisionLocator(cfg, base_dir=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--positive", action="append", default=[],
                    help="正向用例，格式 目标名:期望x,期望y（可重复）")
    ap.add_argument("--negative", action="append", default=[],
                    help="负向用例（目标不存在，可重复）")
    ap.add_argument("--tol", type=float, default=120.0,
                    help="判定为命中的像素容差（默认 120px）")
    args = ap.parse_args()

    from PIL import Image
    img = Image.open(args.image).convert("RGB")
    print(f"图像: {args.image} {img.size}  试验次数={args.trials} 容差={args.tol}px")
    loc = build_locator()
    print(f"vision.enabled={loc.enabled} vlm_available={loc.vlm_available}\n")

    if not args.positive and not args.negative:
        args.positive = ["设置:173,1609"]

    print("=== 正向用例（应命中） ===")
    for case in args.positive:
        name, _, xy = case.partition(":")
        ex, ey = (float(v) for v in xy.split(","))
        hits, errs = 0, []
        for i in range(args.trials):
            hit = loc.locate_by_vlm(img, f"定位屏幕上『{name}』应用图标的中心")
            if hit is not None:
                err = ((hit.x - ex) ** 2 + (hit.y - ey) ** 2) ** 0.5
                errs.append(err)
                if err <= args.tol:
                    hits += 1
                print(f"  #{i+1} -> ({hit.x},{hit.y}) 误差 {err:.0f}px "
                      f"{'命中' if err <= args.tol else '偏离'}")
            else:
                print(f"  #{i+1} -> None（未命中）")
        rate = hits / args.trials * 100
        avg = sum(errs) / len(errs) if errs else float("nan")
        print(f"  [{name}] 命中率 {hits}/{args.trials} = {rate:.0f}%, "
              f"平均误差 {avg:.0f}px\n")

    print("=== 负向用例（应返回 None） ===")
    for name in args.negative:
        false_pos = 0
        for i in range(args.trials):
            hit = loc.locate_by_vlm(img, f"定位屏幕上『{name}』应用图标的中心")
            if hit is not None:
                false_pos += 1
                print(f"  #{i+1} -> ({hit.x},{hit.y}) 误报！")
            else:
                print(f"  #{i+1} -> None（正确）")
        rate = false_pos / args.trials * 100
        print(f"  [{name}] 误报率 {false_pos}/{args.trials} = {rate:.0f}%\n")


if __name__ == "__main__":
    main()
```

### `devtools/vlm_probe.py`（109 行）

```python
# -*- coding: utf-8 -*-
"""vlm_probe.py - 裸调 VLM 网关，区分「未命中」与「后端故障」

背景：locate_by_vlm 未命中目标时静默返回 None，容易误判为网关坏了。
本脚本绕过工程封装，直接 POST /chat/completions，打印原始状态码与响应片段。

用法：
    python devtools/vlm_probe.py --image shot.png --prompt "定位屏幕上的签到按钮"
    python devtools/vlm_probe.py --models          # 只列出可用模型
"""
import argparse
import base64
import json
import os
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:20128"


def config_key():
    """API Key 从环境变量或 `config.yaml` 读，**绝不写进源码**。

    硬编码的 Key 会随 git 一起被推走 —— 本项目实测踩过：本文件与 3 个
    `handover/02_适配脚本/` 脚本都硬编码了同一个 Key。
    优先级：`VLM_KEY` / `VLM_API_KEY` 环境变量 > `config.yaml` 的 `vision.vlm.api_key`。
    """
    key = os.environ.get("VLM_KEY") or os.environ.get("VLM_API_KEY")
    if key:
        return key
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import yaml
    except ImportError:      # 与 main.py 一致：无 PyYAML 时用内置解析器
        import miniyaml as yaml  # type: ignore
    try:
        with open(os.path.join(root, "config.yaml"), "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return ((cfg.get("vision") or {}).get("vlm") or {}).get("api_key") or ""
    except Exception:        # noqa: BLE001 - 读不到就让调用方用 --key 传
        return ""


DEFAULT_KEY = config_key()


def list_models(base, key):
    r = requests.get(base.rstrip("/") + "/models",
                     headers={"Authorization": f"Bearer {key}"}, timeout=20)
    print("status:", r.status_code)
    try:
        for m in r.json().get("data", []):
            print("  -", m.get("id"))
    except Exception:
        print(r.text[:500])


def probe(base, key, model, image, prompt):
    with open(image, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "temperature": 0,
    }
    r = requests.post(base.rstrip("/") + "/chat/completions",
                      headers={"Authorization": f"Bearer {key}",
                               "Content-Type": "application/json"},
                      json=payload, timeout=120)
    print(f"=== model={model} status={r.status_code} ===")
    if r.status_code != 200:
        print("body:", r.text[:800])
        return None
    body = r.json()
    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("content:", str(content)[:400].replace("\n", " "))
    return content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None)
    ap.add_argument("--prompt", default='定位图中目标元素中心，只返回JSON：'
                                        '{"x": 中心x, "y": 中心y}')
    ap.add_argument("--base", default=os.environ.get("VLM_BASE", DEFAULT_BASE))
    ap.add_argument("--key", default=DEFAULT_KEY)
    ap.add_argument("--model", default="auto/best-vision")
    ap.add_argument("--models", action="store_true", help="仅列出模型")
    args = ap.parse_args()

    if args.models or not args.image:
        list_models(args.base, args.key)
        return
    for m in (args.model, "auto/vision"):
        probe(args.base, args.key, m, args.image, args.prompt)


if __name__ == "__main__":
    main()
```

### `devtools/vlm_templates.py`（136 行）

```python
# -*- coding: utf-8 -*-
"""vlm_templates.py - 提示词模板横向评测

背景：实测同一张图、同一个目标，网关的表现差异极大：
  - 中文提示词常被内容安全拦截，返回字符串 "User Safety: safe"（不是坐标）；
  - 英文提示词成功率更高，但坐标精度波动大（41px ~ 205px）。
本脚本对候选模板做 N 次重复，统计「可用率（返回可解析 JSON）」与「平均误差」，
用于挑选写回 config.yaml 的默认模板。

用法：
    python devtools/vlm_templates.py --image devtools/out/p1.png \
        --target 设置 --truth 170,1685 --trials 3
"""
import argparse
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import requests  # noqa: E402

SUFFIX_ZH = ("\n严格按以下要求作答：\n"
             "1) 坐标基于原图像素，左上角为原点，x 向右增大，y 向下增大；\n"
             "2) 只有图中确实存在该目标时才给坐标，否则返回 {\"x\": null, \"y\": null}；\n"
             "3) 只返回一个 JSON 对象，不要任何其他文字。")

SUFFIX_EN = ("\nAnswer strictly as follows:\n"
             "1) Coordinates are in the ORIGINAL image pixel space, "
             "origin at top-left, x to the right, y downward.\n"
             "2) Only give coordinates if the target is clearly visible; "
             "otherwise return {\"x\": null, \"y\": null}. Never guess.\n"
             "3) Return exactly one JSON object {\"x\": <int>, \"y\": <int>} "
             "and nothing else.")

TEMPLATES = {
    "T1_中文体+中文后缀": lambda t: f"定位屏幕上『{t}』图标的中心" + SUFFIX_ZH,
    "T2_中文体+英文后缀": lambda t: f"定位屏幕上『{t}』图标的中心" + SUFFIX_EN,
    "T3_英文体+英文后缀": lambda t: (
        f"This is a phone screenshot. Locate the '{t}' app icon and "
        f"return its center pixel coordinate." + SUFFIX_EN),
    "T4_纯JSON约束": lambda t: (
        f"Output the center pixel coordinate of the '{t}' icon in this "
        f"screenshot. Reply with JSON only: {{\"x\": int, \"y\": int}}. "
        f"If absent, reply {{\"x\": null, \"y\": null}}."),
}


def build_cfg():
    try:
        import yaml
        with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("vision") or {}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--target", default="设置")
    ap.add_argument("--truth", default=None, help="真值 x,y")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    cfg = build_cfg()
    vlm = cfg.get("vlm") or {}
    url = (vlm.get("base_url") or "http://127.0.0.1:20128/v1").rstrip("/") \
        + "/chat/completions"
    key = vlm.get("api_key") or ""
    model = args.model or vlm.get("model") or "auto/best-vision"
    truth = None
    if args.truth:
        truth = tuple(float(v) for v in args.truth.split(","))

    from PIL import Image
    img = Image.open(args.image).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = buf.getvalue()
    import base64
    b64 = base64.b64encode(b64).decode()

    print(f"image={args.image} {img.size} model={model} trials={args.trials}")
    print(f"target={args.target} truth={truth}\n")

    for name, fn in TEMPLATES.items():
        prompt = fn(args.target)
        ok, errs, raws = 0, [], []
        for i in range(args.trials):
            try:
                r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                                  json={"model": model, "temperature": 0,
                                        "messages": [{"role": "user", "content": [
                                            {"type": "text", "text": prompt},
                                            {"type": "image_url", "image_url": {
                                                "url": "data:image/png;base64," + b64}}]}]},
                                  timeout=180, allow_redirects=False)
                content = r.json()["choices"][0]["message"]["content"]
            except Exception as e:
                raws.append(f"ERR {type(e).__name__}")
                continue
            m = re.search(r"\{.*?\}", str(content), re.S)
            if not m:
                raws.append(str(content).strip()[:40])
                continue
            try:
                d = json.loads(m.group(0))
            except Exception:
                raws.append("JSON解析失败")
                continue
            x, y = d.get("x"), d.get("y")
            if x is None or y is None:
                raws.append("null(未命中)")
                continue
            ok += 1
            raws.append(f"({x},{y})")
            if truth:
                errs.append(((float(x) - truth[0]) ** 2
                             + (float(y) - truth[1]) ** 2) ** 0.5)
            time.sleep(0.4)
        rate = ok / args.trials * 100
        avg = f"{sum(errs) / len(errs):.0f}px" if errs else "-"
        print(f"{name}: 可用率 {ok}/{args.trials} = {rate:.0f}%  平均误差 {avg}")
        print(f"    样本: {raws}")


if __name__ == "__main__":
    main()
```

### `devtools/vocab_report.py`（68 行）

```python
# -*- coding: utf-8 -*-
"""vocab_report.py - 打印跨 App 共性词表的归纳结果（AUTOP-NL-2026-10-22 第3项观察工具）

用途：人工复核「哪些词被自动升级为共性词」，以及每个行为的最终候选池。
只读，不写任何文件。

用法：
    ./.venv/Scripts/python.exe devtools/vocab_report.py
    ./.venv/Scripts/python.exe devtools/vocab_report.py --app 拼多多
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import candidates  # noqa: E402
from config_loader import load_config  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", help="只看某个 App 的候选池")
    args = ap.parse_args()

    cfg = load_config(CONFIG)
    apps = cfg.get("apps") or []
    candidates.register_apps(apps)

    print(f"App 总数: {len(apps)}")
    print(f"归纳门槛: 同一行为下 >= {candidates.MIN_APP_SUPPORT} 个 App 用过\n")

    mined = candidates.mine_words()
    if not mined:
        print("归纳结果: 空（所有共性词都已在人工词表中）")
    else:
        print("归纳出的表外共性词：")
        for cat, words in sorted(mined.items()):
            print(f"  [{cat}] {', '.join(words)}")

    print("\n各行为最终候选池：")
    for bid in sorted(candidates.INTENT_TO_CATEGORY):
        cat = candidates.INTENT_TO_CATEGORY[bid]
        pool = candidates.candidates_for(cat)
        print(f"  {bid:10s} -> {cat:12s} ({len(pool)} 个) {', '.join(pool)}")

    if args.app:
        target = next((a for a in apps if a.get("name") == args.app
                       or args.app in (a.get("aliases") or [])), None)
        if not target:
            print(f"\n未找到 App: {args.app}")
            return 1
        print(f"\n{target.get('name')} 的行为与候选池：")
        for bid in (target.get("behaviors") or {}):
            cat = candidates.category_for_intent(bid)
            if cat:
                pool = candidates.candidates_for(cat, target)
                print(f"  {bid:10s} -> {len(pool)} 个候选")
            else:
                print(f"  {bid:10s} -> （该行为不参与词表推断）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/watch_dispatch_feat.py`（75 行）

```python
# -*- coding: utf-8 -*-
"""watch_dispatch_feat.py - AUTOP-FEAT-2026-10-20 排队投递守望器

marvis 是单 agent。投递前若 in_progress 非空 → 每隔 POLL 秒重查；
空闲即投递（tag=AUTOP-FEAT-2026-10-20），cid 写回卡片「投递记录」节后退出。
超过 MAX_WAIT 秒仍忙 → 落盘 BLOCKED 记录退出（不猛发、不撤销卡片）。
"""
import os
import re
import sys
import time

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["LOCALAPPDATA"] = r"C:\Users\Administrator\AppData\Local"
sys.path.insert(0, r"C:/Users/Administrator/WorkBuddy/S7 漏洞/.workbuddy/dispatch")

ROOT = r"C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot"
CARD = os.path.join(ROOT, "dispatch", "AUTOP-FEAT-2026-10-20-CARD.md")
TAG = "AUTOP-FEAT-2026-10-20"
POLL = 60
MAX_WAIT = 5400  # 90 分钟

MSG = """派单：AndroidAutopilot 两个新功能（F1 全局弹窗处理 + F2 反机器人检测）。
卡片真源（先完整读它再动手）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-FEAT-2026-10-20-CARD.md
sha16=8cd3527c948693ec

范围：F1 dismiss_popups 原语（文案→id→右上角坐标→系统回退键四级关闭顺序；黑名单熔断资金类弹窗；watch 行为进行中保护正在看的广告）；F2 反检测文档 docs/ANTI_DETECTION.md（威胁面诚实标注可缓解/不可缓解，禁过度承诺）+ human.py 拟人化增强（误触回退/乱逛/限流/验证码冷却）。
红线（用户原话）：资金类弹窗不得自动关闭、不得按 BACK 消化（踩项目资金红线即打回）；不许引入第三方改机/root/hook；不许改既有测试断言使其变绿。
交付：新文件+新测试+PROGRESS.md；pytest tests/ -q 全绿并贴真实输出；dry-run EXIT=0；不 git push；每步前备份 _backup_pre_fix/。
★ 硬性节奏（上一轮教训：只探索不落盘=零产出的必须遵守）：
1. 前 5 个动作内在 dispatch/AUTOP-FEAT-2026-10-20/PROGRESS.md 建骨架（哪怕空）；
2. 每解决一个子问题立即覆盖写该文件，禁止攒最后；
3. 工具调用预算约 300，超预算落盘部分结论+OPEN/BLOCKED 停步；
4. 不停在 requires_action，疑义写 PROGRESS 质疑记录段。"""


def main():
    from marvis_dispatch import list_conversations, dispatch

    os.makedirs(os.path.dirname(CARD), exist_ok=True)
    t0 = time.time()
    waited = 0
    while waited < MAX_WAIT:
        try:
            convs = list_conversations("marvis", 40)
        except Exception as e:  # noqa: BLE001
            print(f"[watch] list_conversations 失败，{POLL}s 后重试: {e}", flush=True)
            time.sleep(POLL)
            waited += POLL
            continue
        busy = [c for c in convs if c.get("status") == "in_progress"]
        if not busy:
            print(f"[watch] marvis 空闲（已排队 {waited}s），投递 tag={TAG}", flush=True)
            d, r, cid = dispatch("marvis", MSG, timeout=240, hold=True, tag=TAG)
            print(f"[watch] 投递回执 cid={cid}", flush=True)
            rec = (
                f"\n- 排队投递：2026-10-20 ｜ tag={TAG} ｜ 投递前等待 {waited}s（marvis 忙别条线任务，按单 agent 纪律排队）\n"
                f"- cid：{cid}\n- 卡片 sha16：8cd3527c948693ec（sha256 8cd3527c948693ec1157754f2948ee1f75cd98d927429ab01d57ec880e17cfb2）\n"
            )
            with open(CARD, "a", encoding="utf-8") as f:
                f.write(rec)
            print("[watch] 投递记录已写回卡片，退出", flush=True)
            return 0
        print(f"[watch] marvis 忙（{len(busy)} 个 in_progress），已等 {waited}s，{POLL}s 后重查", flush=True)
        time.sleep(POLL)
        waited += POLL
    print(f"[watch] 超过 {MAX_WAIT}s 仍忙，未投递；卡片就绪待派", flush=True)
    with open(CARD, "a", encoding="utf-8") as f:
        f.write(f"\n- 2026-10-20 投递尝试：排队超过 {MAX_WAIT}s marvis 仍 in_progress，未投递，卡片就绪待派\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/watch_dispatch_queue.py`（126 行）

```python
# -*- coding: utf-8 -*-
"""watch_dispatch_queue.py - AUTOP 三卡链式队列守望器

marvis 单 agent。三张卡严格顺序（用户 2026-10-20 21:23 确认手机在线）：
  CARD-A AUTOP-REGRESS-2026-10-20   12 份新 sign 真机回归（verify_live）
  CARD-B AUTOP-FEAT-2026-10-20      F1 全局弹窗 + F2 反检测
  CARD-C AUTOP-SELFSEARCH-2026-10-20 共性提炼 → 引擎自搜寻
流程：等 idle -> 投当前卡 -> 等 completed -> 下一张；非 completed 记终态后继续队列不投后续风险卡时由本卡记录说明。
"""
import os
import sys
import time

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["LOCALAPPDATA"] = r"C:\Users\Administrator\AppData\Local"
sys.path.insert(0, r"C:/Users/Administrator/WorkBuddy/S7 漏洞/.workbuddy/dispatch")

ROOT = r"C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot"
DISP = os.path.join(ROOT, "dispatch")
POLL = 60
QUEUE_WAIT_MAX = 5400   # 每张卡排队等 idle 上限 90 min
EXEC_MAX = 14400        # 每张卡执行上限 4 h

CARD_A = ("AUTOP-REGRESS-2026-10-20", os.path.join(DISP, "AUTOP-REGRESS-2026-10-20-CARD.md"), """派单：12 份新 sign 配置真机回归（verify_live）。手机已在线（192.168.1.54:5555）。
卡片真源（先完整读它再动手）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-REGRESS-2026-10-20-CARD.md

范围：只跑 sign（--behaviors sign，禁止跑 withdraw）；.venv/Scripts/python.exe devtools/verify_live.py --apps 趣头条,拼多多,京东,美团,快手,百度地图,海马畅听,UC浏览器极速版,飞猪旅行,米读小说,米读极速版,大众点评 --behaviors sign --nav-fast --out devtools/calib/LIVE_VERIFY_SIGN12.md --json devtools/calib/LIVE_VERIFY_SIGN12.json；逐 App 落盘命中结论+断点步骤+「待真机校准」坐标修正清单；不修改任何 config/apps/ 文件（清单交 Host 应用）。
红线：资金类弹窗立即停手；设备离线重连≤3 次即记 BLOCKED 退出；不 git push；无证据不报 confirmed。
★ 硬性节奏：前 5 个动作建 dispatch/AUTOP-REGRESS-2026-10-20/PROGRESS.md 骨架；每 App 完成立即覆盖写；预算约 150 次工具调用；不停 requires_action。""")

CARD_B = ("AUTOP-FEAT-2026-10-20", os.path.join(DISP, "AUTOP-FEAT-2026-10-20-CARD.md"), """派单：AndroidAutopilot 两个新功能（F1 全局弹窗处理 + F2 反机器人检测）。
卡片真源（先完整读它再动手）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-FEAT-2026-10-20-CARD.md
sha16=8cd3527c948693ec

范围：F1 dismiss_popups 原语（文案→关闭id→右上角坐标→系统回退键四级关闭顺序；黑名单熔断资金类弹窗；watch 行为进行中保护正在看的广告）；F2 反检测文档 docs/ANTI_DETECTION.md（威胁面诚实标注可缓解/不可缓解，禁过度承诺）+ human.py 拟人化增强（误触回退/乱逛/限流/验证码冷却）。
红线（用户原话）：资金类弹窗不得自动关闭、不得按 BACK 消化（踩项目资金红线即打回）；不许引入第三方改机/root/hook；不许改既有测试断言使其变绿。
交付：新文件+新测试+PROGRESS.md；pytest tests/ -q 全绿并贴真实输出；dry-run EXIT=0；不 git push；每步前备份 _backup_pre_fix/。
★ 硬性节奏：前 5 个动作内在 dispatch/AUTOP-FEAT-2026-10-20/PROGRESS.md 建骨架；每解决一个子问题立即覆盖写；预算约 300 次工具调用；不停 requires_action。""")

CARD_C = ("AUTOP-SELFSEARCH-2026-10-20", os.path.join(DISP, "AUTOP-SELFSEARCH-2026-10-20-CARD.md"), """派单：领现金路径共性提炼 → 引擎自搜寻能力。
卡片真源（先完整读它再动手，含 12 App 人工勘察描述存档）：
C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\dispatch\\AUTOP-SELFSEARCH-2026-10-20-CARD.md
数据源：同目录 APP_PATHS.md；最新真机证据在 devtools/calib/LIVE_VERIFY_SIGN12.md（若已产出，作为坐标校准输入）。

范围（严格按卡内五步）：① 全局分类候选词表 candidates.py（NAV_TAB/TASK_CENTER/SIGN/WITHDRAW+App 级微调）；② click_first 滚动重试 scroll_retry；③ _pick_best 位置先验 zone；④ behavior 时间窗 window；⑤ docs/SELF_SEARCH_PLAYBOOK.md + 收敛 Host 已写的 12 份 sign 配置（消费回归校准清单，不得降低命中面）。
红线：测试必须能红（变异验证四条）；不改既有测试断言使其变绿；无证据不报 confirmed；不 git push；每步前备份 _backup_pre_fix/。
交付：pytest tests/ -q 全绿并贴真实输出；dry-run 趣头条/美团 EXIT=0；PROGRESS 按硬性节奏落盘。
★ 硬性节奏：前 5 个动作建 dispatch/AUTOP-SELFSEARCH-2026-10-20/PROGRESS.md 骨架；每子问题立即覆盖写；预算约 300 次工具调用；不停 requires_action。""")

CARDS = [CARD_A, CARD_B, CARD_C]


def log(msg):
    print(f"[queue] {msg}", flush=True)


def wait_idle(max_wait, phase):
    from marvis_dispatch import list_conversations
    waited = 0
    while waited < max_wait:
        try:
            convs = list_conversations("marvis", 40)
        except Exception as e:  # noqa: BLE001
            log(f"{phase} list 失败 {POLL}s 后重试: {e}")
            time.sleep(POLL)
            waited += POLL
            continue
        busy = [c for c in convs if c.get("status") == "in_progress"]
        if not busy:
            return True
        log(f"{phase} marvis 忙（{len(busy)} in_progress），已等 {waited}s")
        time.sleep(POLL)
        waited += POLL
    return False


def wait_done(cid, max_wait):
    from marvis_dispatch import conversation_status
    waited = 0
    while waited < max_wait:
        try:
            st = conversation_status(cid)
        except Exception as e:  # noqa: BLE001
            log(f"conversation_status({cid}) 失败: {e}")
            time.sleep(POLL)
            waited += POLL
            continue
        log(f"cid={cid} 状态={st}（已等 {waited}s）")
        if st in ("completed", "failed", "cancelled", "not_found"):
            return st
        time.sleep(POLL)
        waited += POLL
    return "timeout"


def record(card, text):
    with open(card, "a", encoding="utf-8") as f:
        f.write(text)


def main():
    from marvis_dispatch import dispatch
    for tag, card, msg in CARDS:
        if not wait_idle(QUEUE_WAIT_MAX, tag):
            record(card, f"\n- 2026-10-20 排队超时（>{QUEUE_WAIT_MAX}s）未投递，卡片就绪待派\n")
            log(f"{tag} 排队超时，后续卡也不投（保持顺序），退出")
            return 1
        log(f"{tag} marvis 空闲，投递")
        _d, _r, cid = dispatch("marvis", msg, timeout=240, hold=True, tag=tag)
        log(f"{tag} 已投递 cid={cid}")
        record(card, f"\n- 链式队列投递：2026-10-20 {time.strftime('%H:%M')} ｜ tag={tag} ｜ cid={cid}\n")
        st = wait_done(cid, EXEC_MAX)
        log(f"{tag} 终态={st}")
        record(card, f"- 会话终态：{st}（{time.strftime('%Y-%m-%d %H:%M')} 观测）\n")
        if st != "completed":
            record(card, f"- 注意：{tag} 非 completed，后续卡未越位投递，卡片就绪待派\n")
            log(f"{tag} 非 completed，停止后续投递，退出")
            return 1
    log("三卡队列全部执行完毕")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `devtools/yaml_writer.py`（406 行）

```python
# -*- coding: utf-8 -*-
"""yaml_writer.py - 统一 YAML 写回层（AUTOP-NL-2026-10-22）

为什么需要它：
    仓库里已有三套写回范式，各写各的、零测试覆盖，且都有已知缺陷：
      * `to_any_of.py` 整对象 yaml.dump —— 中文注释全丢；
      * `apply_candidate_fixes.py` 行级插入 —— 用 `open(...,"r")` 读，
        Windows 下会把 CRLF 静默统一成 LF，写回造成整份文件 diff；
      * `apply_sign_configs.py` 硬编码文本块 —— 一次性脚本，不可复用。
    34 份 App 配置里 13 份是 CRLF、21 份是 LF，混存是客观事实，
    所以「保换行」不是洁癖，是防止误判「整份文件被改」。

设计取舍（三种写法）：
    A. 行级插入/替换（默认）：保留注释、保留未修改行的字节序列；依赖缩进探测，
       缩进从 `behaviors:` 行实测反推（拆分文件=2，旧单文件=4），不靠猜。
    B. 整对象 dump（`dump_app`，逃生门）：只在文件无注释或需要把
       `[动作]` 改造成 `[[动作],[动作]]` 多模板时用；写前打 WARN。
    C. 硬编码文本块：不提供，已弃用。

契约（`tests/test_yaml_writer.py` 逐条锁定）：
    1. `apply=False` 是缺省：只返回 diff，绝不碰盘。
    2. 幂等：目标块文本逐行相等 -> action="skipped"。
    3. `insert_behavior` 遇已存在 bid 一律 skip；`replace_behavior` 需 force=True。
    4. 只在 apply=True 且确有变更时创建备份。
    5. apply 后必须 verify；verify 失败自动从备份回滚（action="rolled_back"）。
    6. 换行保真：未修改行的字节序列完全不变。
    7. 路径白名单：只允许 <root>/config/apps/*.yaml；拒写 config.yaml 主文件。
"""
from __future__ import annotations

import difflib
import os
import shutil
import time
from dataclasses import dataclass, field

try:
    import yaml
except ImportError as exc:  # pragma: no cover - 仓库 venv 内必有 PyYAML
    raise ImportError(
        "yaml_writer 需要 PyYAML（miniyaml 只有 load，没有 dump）。"
        "请用项目 venv：./.venv/Scripts/python.exe"
    ) from exc

import config_loader

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = "_backup_pre_fix"
TS_FMT = "%Y%m%d_%H%M%S"
APPS_SUBDIR = os.path.join("config", "apps")


class WriterError(RuntimeError):
    """写回层不可恢复错误（路径越界、缺少 behaviors 段等）。"""


@dataclass
class WriteResult:
    path: str
    action: str  # preview | inserted | replaced | skipped | rolled_back | error
    backup: str | None = None
    diff: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.action in ("inserted", "replaced")


# ---------- 定位 / 读取 ----------

def app_path(app_name: str, config_path: str | None = None,
             base_dir: str | None = None) -> str:
    """App 名 -> App 级 YAML 绝对路径（薄封装 config_loader.app_config_path）。"""
    base = base_dir or DEFAULT_ROOT
    cfg = None
    if config_path and os.path.exists(config_path):
        try:
            cfg = config_loader._load_yaml(config_path)
        except Exception:
            cfg = None
    path = config_loader.app_config_path(app_name, cfg=cfg, base_dir=base)
    assert_in_apps_dir(path, base)
    return path


def assert_in_apps_dir(path: str, base_dir: str | None = None) -> None:
    """路径白名单：必须是 <base>/config/apps/*.yaml，且不是主 config.yaml。"""
    base = os.path.abspath(base_dir or DEFAULT_ROOT)
    target = os.path.abspath(path)
    apps_dir = os.path.join(base, APPS_SUBDIR)
    if os.path.abspath(target) == os.path.join(base, "config.yaml"):
        raise WriterError("拒绝写 config.yaml 主文件：apps: [] 是拆分约定，改它必然破坏 parity")
    if not target.lower().endswith((".yaml", ".yml")):
        raise WriterError(f"只允许写 .yaml/.yml：{path}")
    if os.path.commonpath([target, os.path.abspath(apps_dir)]) != os.path.abspath(apps_dir):
        raise WriterError(f"只允许写 config/apps/ 下的文件：{path}")


def read_text(path: str) -> tuple[list[str], str, bool]:
    """读文件 -> (lines, eol, ends_with_newline)。

    按字节判断 eol（不依赖文本模式的通用换行转换），保证写回时字节一致。
    """
    with open(path, "rb") as f:
        raw = f.read()
    eol = "\r\n" if b"\r\n" in raw else "\n"
    ends_nl = raw.endswith(b"\n")
    text = raw.decode("utf-8")
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    lines = text.replace("\r\n", "\n").split("\n") if text else []
    return lines, eol, ends_nl


def load_app(path: str) -> dict:
    """读单个 App 文件；兼容旧式 `- name: X`（加载成 list）的形态，取首个元素。"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}
    return data if isinstance(data, dict) else {}


def find_app_block(lines: list[str], app_name: str) -> tuple[int | None, int | None]:
    """返回 app 块 [start, end)；拆分后的 App 级文件整文件即一个块。"""
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- name: {app_name}":
            start = i
            break
    if start is None:
        if lines and lines[0].strip() == f"name: {app_name}":
            return 0, len(lines)
        return None, None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- name: "):
            end = j
            break
    return start, end


def behavior_indent(lines: list[str], start: int, end: int) -> int | None:
    """behaviors 子键缩进：拆分文件=2，旧单文件=4；找不到 behaviors: 返回 None。"""
    for k in range(start, end):
        s = lines[k].rstrip()
        if s.strip() == "behaviors:":
            return len(s) - len(s.lstrip()) + 2
    return None


def find_behavior(lines: list[str], start: int, end: int, bid: str,
                  indent: int) -> int | None:
    for k in range(start, end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) \
                and s.rstrip().endswith(":") and s.strip().rstrip(":") == bid:
            return k
    return None


def behavior_span(lines: list[str], bstart: int, app_end: int, indent: int) -> int:
    for k in range(bstart + 1, app_end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) \
                and s.rstrip().endswith(":"):
            return k
    return app_end


# ---------- 渲染（纯函数，无 IO） ----------

def render_actions(actions: list[dict], indent: int = 2) -> list[str]:
    """动作链 -> YAML 文本行（带缩进）。产出与仓库既有 `- - type:` 风格逐字一致。"""
    dumped = yaml.safe_dump(
        actions,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=200,
    )
    pad = " " * indent
    return [pad + ln if ln.strip() else "" for ln in dumped.rstrip("\n").split("\n")]


def render_behavior_block(bid: str, actions: list[dict], indent: int,
                          comments: list[str] | None = None) -> list[str]:
    """渲染 `  sign:` + 注释 + 动作链（不含前后空行）。"""
    pad = " " * indent
    out = []
    for c in (comments or []):
        out.append(f"{pad}# {c}" if c and not c.startswith("#") else f"{pad}{c}")
    out.append(f"{pad}{bid}:")
    out.extend(render_actions(actions, indent + 2))
    return out


# ---------- 备份 / 写盘 ----------

def backup(path: str, tag: str = "NL", base_dir: str | None = None) -> str:
    """字节级备份到 _backup_pre_fix/<stem>.pre_<TAG>_<yyyymmdd_HHMMSS>.yaml。"""
    base = base_dir or DEFAULT_ROOT
    bdir = os.path.join(base, BACKUP_DIR)
    os.makedirs(bdir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(bdir, f"{stem}.pre_{tag}_{time.strftime(TS_FMT)}{ext}")
    shutil.copy2(path, dst)
    return dst


def atomic_write(path: str, lines: list[str], eol: str, ends_nl: bool = True) -> None:
    data = eol.join(lines) + (eol if ends_nl else "")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data.encode("utf-8"))
    os.replace(tmp, path)


def _unified_diff(old: list[str], new: list[str], path: str) -> str:
    return "".join(difflib.unified_diff(
        [ln + "\n" for ln in old], [ln + "\n" for ln in new],
        fromfile=f"a/{os.path.basename(path)}",
        tofile=f"b/{os.path.basename(path)}",
        n=3,
    ))


# ---------- 复验 ----------

def snapshot(config_path: str | None = None,
             base_dir: str | None = None) -> dict[str, dict]:
    """{app_name: app_dict} 全量快照（用于写后确认「没误伤别的 App」）。"""
    base = base_dir or DEFAULT_ROOT
    cfg_path = config_path or os.path.join(base, "config.yaml")
    try:
        cfg = config_loader.load_config(cfg_path)
    except Exception:
        return {}
    return {(a.get("name") or "").strip(): a for a in (cfg.get("apps") or [])}


def verify(path: str, before: dict[str, dict], bid: str,
           expect_actions: list[dict] | None = None,
           config_path: str | None = None,
           base_dir: str | None = None) -> tuple[bool, list[str]]:
    """写后复验：①可加载 ②其他 App 未变 ③目标 bid 与期望深比较相等。"""
    problems: list[str] = []
    try:
        app = load_app(path)
    except Exception as exc:  # noqa: BLE001
        return False, [f"目标文件无法解析: {exc}"]

    name = (app.get("name") or "").strip()
    behaviors = app.get("behaviors") or {}
    if bid not in behaviors:
        problems.append(f"目标行为缺失: {name}.{bid}")
    elif expect_actions is not None and behaviors.get(bid) != expect_actions:
        problems.append(f"目标行为与期望不一致: {name}.{bid}")

    if before:
        try:
            cfg_path = config_path or os.path.join(base_dir or DEFAULT_ROOT, "config.yaml")
            after = {(a.get("name") or "").strip(): a for a in
                     (config_loader.load_config(cfg_path).get("apps") or [])}
        except Exception as exc:  # noqa: BLE001
            problems.append(f"整体配置无法加载: {exc}")
            after = {}
        if after:
            if len(after) != len(before):
                problems.append(f"app 数量变化: {len(before)} -> {len(after)}")
            for aname, aapp in before.items():
                if aname == name:
                    continue
                if after.get(aname) != aapp:
                    problems.append(f"误伤其他 App: {aname}")
    return (not problems), problems


# ---------- 主操作 ----------

def _prepare(path: str, bid: str, actions: list[dict], comments: list[str] | None,
             indent_hint: int | None) -> tuple[list[str], str, bool, int, int, int | None]:
    if not os.path.exists(path):
        raise WriterError(f"文件不存在: {path}")
    lines, eol, ends_nl = read_text(path)
    start, end = find_app_block(lines, _app_name_of(lines))
    if start is None:
        raise WriterError(f"无法定位 App 块: {path}")
    indent = behavior_indent(lines, start, end)
    if indent is None:
        raise WriterError(f"缺少 behaviors: 段，拒绝写（{path}）")
    if indent_hint is not None and indent_hint != indent:
        pass  # 以实测为准，hint 仅作调试参考
    bstart = find_behavior(lines, start, end, bid, indent)
    block = render_behavior_block(bid, actions, indent, comments)
    return lines, eol, ends_nl, indent, start, (bstart, end, block)  # type: ignore[return-value]


def _app_name_of(lines: list[str]) -> str:
    for ln in lines[:5]:
        s = ln.strip()
        if s.startswith("name:"):
            return s.split(":", 1)[1].strip()
        if s.startswith("- name:"):
            return s.split(":", 1)[1].strip()
    raise WriterError("无法从文件首部读取 name:")


def insert_behavior(path: str, bid: str, actions: list[dict],
                    comments: list[str] | None = None,
                    apply: bool = False, tag: str = "NL",
                    base_dir: str | None = None) -> WriteResult:
    """在 behaviors: 末尾插入新行为；已存在则 skip（不覆盖，覆盖请用 replace_behavior）。"""
    assert_in_apps_dir(path, base_dir)
    lines, eol, ends_nl, indent, start, tail = _prepare(path, bid, actions, comments, None)
    bstart, end, block = tail
    if bstart is not None:
        return WriteResult(path, "skipped", None, "",
                           [f"{bid} 已存在；如需覆盖请用 replace_behavior(force=True)"])

    # behaviors 段的结束位置：下一个缩进 <= behaviors 的键，或文件末尾
    b_indent = indent - 2
    insert_at = end
    for k in range(start, end):
        if lines[k].rstrip().strip() == "behaviors:":
            for j in range(k + 1, end):
                s = lines[j]
                if not s.strip():
                    continue
                cur = len(s) - len(s.lstrip())
                if cur <= b_indent:
                    insert_at = j
                    break
            break

    # 插入点前补一个空行（若上一行非空），保持文件风格
    new_lines = list(lines)
    payload = list(block)
    if insert_at > 0 and new_lines[insert_at - 1].strip():
        payload = [""] + payload
    if insert_at < len(new_lines) and new_lines[insert_at].strip():
        payload = payload + [""]
    new_lines[insert_at:insert_at] = payload

    diff = _unified_diff(lines, new_lines, path)
    if not apply:
        return WriteResult(path, "preview", None, diff, [])
    bak = backup(path, tag, base_dir)
    atomic_write(path, new_lines, eol, ends_nl)
    ok, problems = verify(path, {}, bid, actions, base_dir=base_dir)
    if not ok:
        shutil.copy2(bak, path)
        return WriteResult(path, "rolled_back", bak, diff, problems)
    return WriteResult(path, "inserted", bak, diff, [])


def replace_behavior(path: str, bid: str, actions: list[dict],
                     comments: list[str] | None = None,
                     apply: bool = False, force: bool = False, tag: str = "NL",
                     base_dir: str | None = None) -> WriteResult:
    """替换已有行为块；force=False 时 skip。"""
    assert_in_apps_dir(path, base_dir)
    lines, eol, ends_nl, indent, start, tail = _prepare(path, bid, actions, comments, None)
    bstart, end, block = tail
    if bstart is None:
        return WriteResult(path, "skipped", None, "", [f"{bid} 不存在；新增请用 insert_behavior"])
    if not force:
        return WriteResult(path, "skipped", None, "", ["replace 需要 force=True"])

    bend = behavior_span(lines, bstart, end, indent)
    old_block = lines[bstart:bend]
    if old_block == block:
        return WriteResult(path, "skipped", None, "", ["内容与现有块逐行相同（幂等）"])

    new_lines = list(lines)
    new_lines[bstart:bend] = block
    diff = _unified_diff(lines, new_lines, path)
    if not apply:
        return WriteResult(path, "preview", None, diff, [])
    bak = backup(path, tag, base_dir)
    atomic_write(path, new_lines, eol, ends_nl)
    ok, problems = verify(path, {}, bid, actions, base_dir=base_dir)
    if not ok:
        shutil.copy2(bak, path)
        return WriteResult(path, "rolled_back", bak, diff, problems)
    return WriteResult(path, "replaced", bak, diff, [])


def dump_app(app: dict, path: str, apply: bool = False, tag: str = "NL",
             base_dir: str | None = None) -> WriteResult:
    """整对象重写（逃生门：丢注释）。仅在文件无注释或需改多模板结构时使用。"""
    assert_in_apps_dir(path, base_dir)
    lines, eol, ends_nl = read_text(path)
    dumped = yaml.safe_dump(app, allow_unicode=True, sort_keys=False,
                            default_flow_style=False, width=200)
    new_lines = dumped.rstrip("\n").split("\n")
    diff = _unified_diff(lines, new_lines, path)
    warn = ["dump_app 会丢弃全部中文注释，非必要勿用"]
    if not apply:
        return WriteResult(path, "preview", None, diff, warn)
    bak = backup(path, tag, base_dir)
    atomic_write(path, new_lines, eol, True)
    return WriteResult(path, "replaced", bak, diff, warn)
```


---

## 3. WebUI 源码

### `webui/__init__.py`（16 行）

```python
# -*- coding: utf-8 -*-
"""webui - Android Autopilot 本地 Web 控制台

为什么不是 tkinter：本项目运行环境（`.workbuddy-ai` 托管的 Python venv）
**没有编译 tkinter**，`import tkinter` 直接 ModuleNotFoundError，
所以任何 tkinter GUI 在这台机器上根本起不来。

改用 stdlib `http.server` + 浏览器前端：
  * 零第三方运行时依赖（与本工程一贯约束一致）；
  * 只监听 127.0.0.1，不对外暴露；
  * 后端直接复用工程自身的模块（config / records.db / devtools），
    不重复实现设备访问与记账逻辑。
"""

__all__ = ["data", "jobs", "server"]
__version__ = "1.0.0"
```

### `webui/data.py`（757 行）

```python
# -*- coding: utf-8 -*-
"""webui.data - 控制台的数据访问层

职责单一：把「工程自身的数据源」读成前端能直接用的结构。
  * config.yaml      -> App / 行为 / 锚点摘要、配置体检
  * data/records.db  -> 收益汇总与明细、操作事件
  * devtools/adbkit  -> 设备在线状态、分辨率、前台 App、实时截图

设计约束：
  * **不重复实现业务逻辑**。设备访问走 `devtools/adbkit.resolve_adb/Adb`，
    记账口径与 `recorder.py` 的 `earnings(ts,app,action,amount,unit,detail)`
    表结构保持一致。
  * 纯计算部分（锚点摘要、配置体检、收益聚合）写成**无 IO 的纯函数**，
    便于单测；带 IO 的部分单独一层。
"""
import json
import os
import re
import sqlite3
import sys
import threading
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_YAML = os.path.join(BASE_DIR, "config.yaml")
DB_PATH = os.path.join(BASE_DIR, "data", "records.db")
DEVTOOLS = os.path.join(BASE_DIR, "devtools")

if DEVTOOLS not in sys.path:
    sys.path.insert(0, DEVTOOLS)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config_loader import load_config as _load_config_merged  # noqa: E402
from config_loader import latest_config_mtime as _latest_config_mtime  # noqa: E402
from config_loader import money_behaviors as _money_behaviors  # noqa: E402

# 行为 key -> 自然语言触发词。与 main.py/nlu.py 的意图表保持一致，
# 保证 GUI 勾选行为后拼出的 --task 能被 nlu.parse_intents 正确解析。
KEY_TO_TRIGGER = {
    "sign": "签到",
    "reserve": "预约打卡",
    "watch": "看视频",
    "withdraw": "提现",
    "bonus": "领金币",
    "collect": "收集",
    "growth": "做任务",
}

# 资金类行为：执行前必须由用户显式确认（项目硬约束 —— 提现/支付/转账
# 不得自动执行，必须先说明影响面并取得授权）。
# C9 起来源统一收敛到 config_loader.money_behaviors（配置可覆盖），
# 此处保留兼容别名供 server.py 等旧引用使用。
MONEY_BEHAVIORS = {"withdraw"}

# 锚点动作类型：带「可校验的定位依据」的动作。这是判断一个行为能否被
# verify_live.py 校验的依据。
ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")

# click_point 是**重载**类型，必须按载荷区分用途（本工程实测分布 68 / 31 / 0）：
#   * 带 images             —— OpenCV 模板匹配锚点（一等定位手段，**算锚点**）
#   * 带「最右侧」vlm_prompt —— 「导航到我的」前置步（比例坐标兜底，不算锚点）
#   * 两者皆无              —— 纯比例坐标兜底（不算锚点，且脆弱，体检时告警）
# 踩过的坑：最初只把 click_text/id/desc/click_first 当锚点，于是把 30 个
# 图像锚点行为误报成「没有可校验的锚点动作」，总览页红字一片假警报。
POINT_TYPE = "click_point"
NAV_MARK = "最右侧"


def is_nav_prelude(action):
    """是不是「导航到我的」前置步（比例坐标兜底，非锚点）。"""
    return (isinstance(action, dict)
            and action.get("type") == POINT_TYPE
            and NAV_MARK in str(action.get("vlm_prompt", "")))


def is_anchor(action):
    """是不是「可校验的锚点」动作。"""
    if not isinstance(action, dict):
        return False
    t = action.get("type")
    if t in ANCHOR_TYPES:
        return True
    if t == POINT_TYPE:
        # 只有配了参考图才算锚点；比例坐标兜底不算。
        return bool(action.get("images"))
    return False


def anchor_via(action):
    """锚点的定位依据，用于前端展示与体检文案。"""
    t = (action or {}).get("type")
    if t == POINT_TYPE:
        return "图像"
    if t == "click_id":
        return "rid"
    if t == "click_first":
        return "候选"
    return "文案"


def _anchor_of(action):
    """把一个锚点动作压成前端要展示的结构。

    `key` = 该锚点真正用来定位的依据，按类型取不同字段 —— 体检要看的是
    「这个锚点到底靠什么找元素」，只盯 text/candidates 会把
    click_id（靠 res_id）和图像锚点（靠参考图）误报成没配置。
    """
    t = action.get("type")
    imgs = action.get("images") or []
    imgs = imgs if isinstance(imgs, list) else []
    cands = [c.get("value") for c in (action.get("candidates") or [])
             if isinstance(c, dict)][:8]
    if t == "click_id":
        key = action.get("res_id") or ""
    elif t == POINT_TYPE:
        key = imgs[0] if imgs else ""
    elif t == "click_first":
        key = cands[0] if cands else (action.get("candidates_from") or "")
    else:
        key = action.get("text") or action.get("desc") or ""
    return {
        "type": t,
        "via": anchor_via(action),
        "key": key,
        "text": action.get("text") or action.get("desc") or "",
        "candidates": cands,
        "images": len(imgs),
    }


def _variant_of(actions):
    """行为可能是 [[..],[..]] 多候选模板，取第一组作为主视图。"""
    if not actions:
        return []
    if all(isinstance(a, list) for a in actions):
        return actions[0] or []
    return actions


def _paths_of(acts):
    """把行为展开成若干条**完整路径**。

    `any_of` 的语义是「按顺序试多组动作，第一组全部成功即停」，它**前后**的
    动作对每条分支都生效，必须拼进每条路径 —— 否则会漏算
    「any_of 之后还有一个锚点」的情况（实测 `一淘.sign` 正是这种：
    `[any_of{[[签到],[我的,think,签到]]}, think, 签到]`，
    展开后第二条路径是 `[我的,think,签到,think,签到]`，才是真正的三级导航）。
    """
    paths = [[]]
    for a in acts:
        if isinstance(a, dict) and a.get("type") == "any_of":
            choices = [ch if isinstance(ch, list) else [ch]
                       for ch in (a.get("choices") or [])]
            expanded = [p + ch for p in paths for ch in choices]
            paths = expanded or paths
        else:
            for p in paths:
                p.append(a)
    return [p for p in paths if p]


def _all_actions(acts):
    """展开后所有路径上的动作（用于全量体检，不重不漏）。"""
    out = []
    for p in _paths_of(acts):
        out.extend(p)
    return out


# verify_live.py 的锚点口径已与 is_anchor() 对齐（含 click_point 图像锚点），
# 见 devtools/verify_live.py 的 is_anchor_action。图像锚点行为现在会被
# stability_run 计入命中率分母，不再算「未度量」。
# ⚠️ 改 verify_live.py 的锚点判断时，这里必须同步，否则覆盖率会显示错。
# VERIFIER_ANCHOR_TYPES 已删除 —— verifier_can_check 直接复用 is_anchor，
# 避免两套口径再次漂移。


def verifier_can_check(actions):
    """该行为能否被**实机验证器**校验到（口径对齐 verify_live.py，图像锚点也算）。"""
    return any(is_anchor(a) or (isinstance(a, dict) and a.get("type") == "any_of")
               for a in _variant_of(actions))


def summarize_behavior(actions):
    """把一个行为的动作列表压成前端要展示的摘要。

    返回 {anchors, levels, has_prelude, branches, vias, optional_all}：
      * anchors     —— 去重后的锚点动作（跨 any_of 各分支合并）
      * levels      —— 最长路径的可达层数（1=首屏可达，2=需导航，3=需二级入口）
      * has_prelude —— 是否带「导航到我的」前置步
      * branches    —— 候选路径条数（>1 表示有多路径覆盖）
      * vias        —— 去重后的定位依据（文案/图像/rid/候选）
    """
    acts = _variant_of(actions)
    paths = _paths_of(acts)

    anchors, seen = [], set()
    has_prelude = False
    levels = 0
    for p in paths:
        prelude = any(is_nav_prelude(a) for a in p)
        has_prelude = has_prelude or prelude
        n = 0
        for a in p:
            if not is_anchor(a):
                continue
            n += 1
            an = _anchor_of(a)
            sig = (an["type"], an["key"])
            if sig not in seen:
                seen.add(sig)
                anchors.append(an)
        if n:
            # 1=首屏可达；+1=需先导航到「我的」；再+1=还需穿透一层二级入口。
            levels = max(levels, 1 + (1 if prelude else 0) + (1 if n > 1 else 0))

    branches = len(paths) if len(paths) > 1 else (1 if anchors else 0)
    vias = []
    for an in anchors:
        if an["via"] not in vias:
            vias.append(an["via"])
    return {
        "anchors": anchors,
        "levels": levels,
        "has_prelude": has_prelude,
        "branches": branches,
        "vias": vias,
        "optional_all": all(isinstance(a, dict) and a.get("optional")
                            for a in acts if isinstance(a, dict)) and bool(acts),
    }


def validate_config(cfg):
    """配置体检：返回问题列表 [{level, app, msg}]。纯函数。"""
    issues = []
    apps = (cfg or {}).get("apps") or []
    seen = {}
    for i, a in enumerate(apps):
        name = (a.get("name") or "").strip()
        pkg = (a.get("package") or "").strip()
        if not name:
            issues.append({"level": "ERROR", "app": f"#{i + 1}",
                           "msg": "缺少 name"})
            continue
        if not pkg:
            issues.append({"level": "ERROR", "app": name, "msg": "缺少 package"})
        if name in seen:
            issues.append({"level": "ERROR", "app": name,
                           "msg": f"App 名重复（第 {seen[name] + 1} 与第 {i + 1} 项）"})
        seen.setdefault(name, i)
        beh = a.get("behaviors") or {}
        if not beh:
            issues.append({"level": "WARN", "app": name, "msg": "未配置任何行为"})
        for bid, actions in beh.items():
            s = summarize_behavior(actions)
            if not s["anchors"]:
                issues.append({"level": "ERROR", "app": name,
                               "msg": f"行为 {bid} 没有可校验的锚点动作"
                                      "（文案/rid/图像都没有）"})
            for an in s["anchors"]:
                if not an["key"]:
                    issues.append({"level": "WARN", "app": name,
                                   "msg": f"行为 {bid} 的 {an['via']} 锚点"
                                          "未配置定位依据"})
            # 纯比例坐标兜底：能跑但很脆（换机型/改版即失效），值得提醒。
            # 要展开 any_of 分支后再扫，否则分支里的兜底点会被漏掉。
            for a in _all_actions(actions):
                if (isinstance(a, dict) and a.get("type") == POINT_TYPE
                        and not a.get("images") and not is_nav_prelude(a)):
                    issues.append({"level": "WARN", "app": name,
                                   "msg": f"行为 {bid} 用纯比例坐标兜底（无参考图）"})
    return issues


def aggregate_earnings(rows, today=None):
    """按单位聚合收益明细。

    rows: [(ts, app, action, amount, unit, detail)]
    返回 {summary:[{unit,total,count}], by_app:[{app,unit,total,count}], total_rows}
    """
    today = today or datetime.now().strftime("%Y-%m-%d")
    by_unit, by_app = {}, {}
    for ts, app, action, amount, unit, _detail in rows:
        unit = unit or ""
        try:
            amt = float(amount or 0)
        except (TypeError, ValueError):
            amt = 0.0
        u = by_unit.setdefault(unit, {"unit": unit, "total": 0.0, "count": 0,
                                      "today": 0.0})
        u["total"] += amt
        u["count"] += 1
        if str(ts).startswith(today):
            u["today"] += amt
        k = (app or "-", unit)
        g = by_app.setdefault(k, {"app": app or "-", "unit": unit,
                                  "total": 0.0, "count": 0})
        g["total"] += amt
        g["count"] += 1
    return {
        "summary": sorted(by_unit.values(), key=lambda x: -x["total"]),
        "by_app": sorted(by_app.values(), key=lambda x: -x["total"]),
        "total_rows": len(rows),
    }


def daily_series(rows, days=7, today=None):
    """近 N 日按天聚合（用于趋势图）。返回 [{date,total,count}]，按日期升序。"""
    today_d = datetime.strptime(today, "%Y-%m-%d") if today else datetime.now()
    buckets = {}
    for i in range(days - 1, -1, -1):
        d = (today_d - timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[d] = {"date": d, "total": 0.0, "count": 0}
    for ts, _app, _action, amount, _unit, _d in rows:
        d = str(ts)[:10]
        if d in buckets:
            try:
                buckets[d]["total"] += float(amount or 0)
            except (TypeError, ValueError):
                pass
            buckets[d]["count"] += 1
    return list(buckets.values())


def parse_foreground(dumpsys_window_output):
    """从 `dumpsys window` 输出里取前台 Activity 与包名。纯函数。

    踩坑：`d.info.currentPackageName` 在崩溃/切换时序下会先报新包名，
    而屏幕还是旧 App。这里用 dumpsys 的 mCurrentFocus 作为交叉参考。
    """
    m = re.search(r"mCurrentFocus=Window\{[^}]*?\s([\w.]+)/([\w.$]+)\}", dumpsys_window_output or "")
    if m:
        return {"package": m.group(1), "activity": m.group(2)}
    m = re.search(r"mFocusedApp=.*?\s([\w.]+)/([\w.$]+)", dumpsys_window_output or "")
    if m:
        return {"package": m.group(1), "activity": m.group(2)}
    return {"package": "", "activity": ""}


def parse_wm_size(out):
    """解析 `wm size` 输出 -> (w, h) 或 (None, None)。纯函数。"""
    m = re.search(r"Override size:\s*(\d+)x(\d+)", out or "")
    if not m:
        m = re.search(r"Physical size:\s*(\d+)x(\d+)", out or "")
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def behavior_task_text(behaviors):
    """把行为 key 列表拼成 main.py --task 能解析的自然语言。纯函数。"""
    parts = [KEY_TO_TRIGGER.get(b, b) for b in (behaviors or [])]
    return "，然后".join(parts) or "签到"


# ===========================================================================
# IO 层
# ===========================================================================
def load_yaml(path):
    try:
        import yaml
    except ImportError:  # 与 main.py 一致：无 PyYAML 时用内置解析器
        sys.path.insert(0, BASE_DIR)
        import miniyaml as yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Store:
    """配置 + 数据库的只读访问（带轻量缓存）。线程安全。"""

    def __init__(self, config_path=CONFIG_YAML, db_path=DB_PATH):
        self.config_path = config_path
        self.db_path = db_path
        self._lock = threading.Lock()
        self._cfg = None
        self._cfg_mtime = None
        self._stab = None
        self._stab_mtime = None

    # ---------- 配置 ----------
    def config(self, reload=False):
        with self._lock:
            try:
                mtime = _latest_config_mtime(self.config_path)
            except OSError:
                mtime = None
            if reload or self._cfg is None or mtime != self._cfg_mtime:
                self._cfg = _load_config_merged(self.config_path)
                self._cfg_mtime = mtime
            return self._cfg

    def apps(self):
        # 2026-10-29 性能修正：config() / _money_behaviors() 原先写在两层循环**里面**，
        # 34 个 App × 平均 3 条 behavior 会调用 config() 近百次。config() 带 mtime 缓存，
        # 命中时很便宜，但一旦缓存未命中（每次冷启动、或配置目录 mtime 抖动）就是
        # 「解析 34 份 YAML」× 99 次 —— 实测包内环境单次 /api/overview 45s，
        # 超过前端 20s 超时，4 个 webui HTTP 用例直接 TimeoutError。
        # 把不随循环变化的量提到循环外，单次耗时从 45s 降到 2s 量级。
        cfg = self.config()
        money = _money_behaviors(cfg)
        out = []
        for i, a in enumerate((cfg.get("apps") or [])):
            beh = a.get("behaviors") or {}
            behaviors = []
            for bid, actions in beh.items():
                s = summarize_behavior(actions)
                behaviors.append({
                    "id": bid,
                    "trigger": KEY_TO_TRIGGER.get(bid, bid),
                    "money": bid in money,
                    "levels": s["levels"],
                    "branches": s["branches"],
                    "has_prelude": s["has_prelude"],
                    "vias": s["vias"],
                    "anchors": s["anchors"],
                })
            out.append({
                "index": i,
                "name": a.get("name") or f"app{i}",
                "package": a.get("package") or "",
                "aliases": list(a.get("aliases") or []),
                "behaviors": behaviors,
            })
        return out

    def device_cfg(self):
        return self.config().get("device") or {}

    def verify_coverage(self):
        """实机验证器的**行为覆盖率**。

        verify_live.py 遇到它认不出的锚点类型会记「无锚点动作」并跳过，
        而 stability_run.py 把该状态当作废、**不计入命中率分母** ——
        所以命中率不会被稀释，但那批行为是**完全没被度量**的。
        这个数字必须让人看得见，否则容易把「70% 命中率」误读成「覆盖了七成」。
        """
        total = checked = 0
        image_only = 0
        for a in self.config().get("apps") or []:
            for _bid, actions in (a.get("behaviors") or {}).items():
                total += 1
                if verifier_can_check(actions):
                    checked += 1
                elif summarize_behavior(actions)["vias"] == ["图像"]:
                    image_only += 1
        return {"total": total, "verifiable": checked,
                "unverifiable": total - checked, "image_only": image_only}

    def overview(self):
        cfg = self.config()
        apps = self.apps()
        return {
            "device": self.device_cfg(),
            "app_count": len(apps),
            "behavior_count": sum(len(a["behaviors"]) for a in apps),
            "money_behavior_count": sum(1 for a in apps for b in a["behaviors"]
                                        if b["money"]),
            "apps": apps,
            "issues": validate_config(cfg),
            "verify_coverage": self.verify_coverage(),
            "human": cfg.get("human") or {},
            "vision_enabled": bool((cfg.get("vision") or {}).get("enabled")),
            "captcha_enabled": bool((cfg.get("captcha") or {}).get("enabled")),
        }

    # ---------- 数据库 ----------
    def _connect(self):
        if not os.path.exists(self.db_path):
            return None
        # 只读打开：控制台不写库，避免与运行中的执行器抢锁
        uri = "file:%s?mode=ro" % self.db_path.replace("?", "%3f").replace("#", "%23")
        conn = sqlite3.connect(uri, uri=True, timeout=3.0)
        conn.row_factory = sqlite3.Row
        return conn

    def earnings(self, days=None, app=None, limit=2000):
        conn = self._connect()
        if conn is None:
            return {"summary": [], "by_app": [], "total_rows": 0,
                    "series": [], "rows": []}
        try:
            where, params = [], []
            if days:
                since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
                where.append("ts >= ?")
                params.append(since)
            if app:
                where.append("app = ?")
                params.append(app)
            sql = "SELECT ts, app, action, amount, unit, detail FROM earnings"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY ts DESC LIMIT ?"
            params.append(int(limit))
            rows = [tuple(r) for r in conn.execute(sql, params).fetchall()]
            agg = aggregate_earnings(rows)
            agg["series"] = daily_series(rows, days=min(days or 7, 30))
            agg["rows"] = [dict(zip(("ts", "app", "action", "amount", "unit",
                                     "detail"), r)) for r in rows[:limit]]
            return agg
        finally:
            conn.close()

    def ops(self, limit=50, level=None):
        conn = self._connect()
        if conn is None:
            return []
        try:
            sql = "SELECT ts, app, event, level FROM ops"
            params = []
            if level:
                sql += " WHERE level = ?"
                params.append(level)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(int(limit))
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def ops_stats(self):
        conn = self._connect()
        if conn is None:
            return {"total": 0, "by_level": {}, "last_ts": ""}
        try:
            total = conn.execute("SELECT COUNT(*) FROM ops").fetchone()[0]
            by_level = {r[0] or "INFO": r[1] for r in conn.execute(
                "SELECT level, COUNT(*) FROM ops GROUP BY level")}
            last = conn.execute("SELECT MAX(ts) FROM ops").fetchone()[0] or ""
            return {"total": total, "by_level": by_level, "last_ts": last}
        finally:
            conn.close()

    # ---------- 校准 / 稳定性 ----------
    def stability(self):
        """读 `devtools/calib/STABILITY*.json`，供「校准」页展示。

        这是本工程最核心的度量产物（多轮命中率、稳定/波动/从未命中三分类、
        改动的版本对比链），此前只能手工打开 markdown 看。控制台能**运行**
        stability_run，却看不到它的结果 —— 这个接口补上那一半。
        """
        with self._lock:
            try:
                mtime = os.path.getmtime(STABILITY_JSON)
            except OSError:
                return {"available": False,
                        "hint": "尚无稳定性报告 —— 到「诊断工具」页跑一次"
                                "「多轮稳定性统计」，完成后回到本页刷新"}
            if self._stab is None or mtime != self._stab_mtime:
                try:
                    self._stab = load_stability(STABILITY_JSON)
                except Exception as e:  # noqa: BLE001
                    return {"available": False,
                            "hint": f"报告解析失败（{type(e).__name__}: {e}）"}
                self._stab_mtime = mtime
            out = dict(self._stab)
        # 覆盖率口径与 verify_live.py 对齐（见 verify_coverage 的注释）。
        # 放在锁外：verify_coverage -> config() 也要拿同一把锁。
        out["verify_coverage"] = self.verify_coverage()
        return out


# ===========================================================================
# 校准 / 稳定性报告
# ===========================================================================
CALIB_DIR = os.path.join(DEVTOOLS, "calib")
STABILITY_JSON = os.path.join(CALIB_DIR, "STABILITY.json")

# 版本对比链的顺序**不能靠文件名排序**：`STABILITY.json` 是当前版，
# `STABILITY_pre_*.json` 是改动前的备份。名字排序恰好把 `STABILITY` 排在
# 最后，但一旦再新增备份就会错位。这里显式声明已知阶段，未知备份按名追加。
STAGE_ORDER = ["STABILITY_pre_fix", "STABILITY_pre_reset", "STABILITY"]
STAGE_LABELS = {
    "STABILITY_pre_fix": "修「中间入口当命中」之前",
    "STABILITY_pre_reset": "修完中间入口 · 未加行为间复位",
    "STABILITY": "当前",
}


def _stage_key(stem):
    try:
        return (0, STAGE_ORDER.index(stem))
    except ValueError:
        return (1, stem)


def _kind_of(valid, hits):
    """逐行为三分类。与 stability_run.classify 同义，只是这里要逐行徽章。"""
    if not valid:
        return "未度量"
    if hits == valid:
        return "稳定"
    if hits == 0:
        return "从未命中"
    return "波动"


def load_stability(path):
    """把一份 STABILITY*.json 归一化成前端直接可用的结构。

    **命中/作废判定直接复用 devtools/stability_run**，不在这里另写一份 ——
    口径一旦分叉，界面上的命中率就会与命令行输出、与 ROUND3_FINDINGS.md
    对不上，而两边单测都还是绿的（这正是本项目踩过的「静默不一致」）。
    """
    import stability_run as SR  # devtools 已在 sys.path（见文件头）

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    rows = raw.get("per_behavior") or []
    behaviors = []
    for x in rows:
        valid = int(x.get("valid") or 0)
        hits = int(x.get("hits") or 0)
        behaviors.append({
            "app": x.get("app") or "",
            "behavior": x.get("behavior") or "",
            "statuses": list(x.get("statuses") or []),
            "valid": valid,
            "void": int(x.get("void") or 0),
            "hits": hits,
            "rate": (hits / valid) if valid else None,
            "kind": _kind_of(valid, hits),
        })

    stable, flaky, never = SR.classify(rows)
    tot = raw.get("total") or {}
    valid = int(tot.get("valid") or 0)
    hits = int(tot.get("hits") or 0)
    return {
        "available": True,
        "path": path,
        "mtime": os.path.getmtime(path),
        "rounds": int(raw.get("rounds") or 0),
        "total": {
            "hits": hits, "valid": valid,
            "void": int(tot.get("void") or 0),
            "rate": (hits / valid) if valid else None,
        },
        "counts": {
            "stable": len(stable), "flaky": len(flaky), "never": len(never),
            "unmeasured": sum(1 for b in behaviors if not b["valid"]),
            "behaviors": len(behaviors),
        },
        "behaviors": behaviors,
    }


def stability_chain():
    """列出 `calib/STABILITY*.json` 备份链，供「版本对比」用。

    每次现算（几个十几 KB 的 JSON），不缓存：用户刚跑完 stability_run
    就会来点刷新，缓存反而会显示旧结果。
    """
    try:
        names = sorted(os.listdir(CALIB_DIR))
    except OSError:
        return []
    stems = []
    for n in names:
        if n.startswith("STABILITY") and n.endswith(".json"):
            stems.append(n[:-5])
    stems.sort(key=_stage_key)

    chain = []
    for stem in stems:
        path = os.path.join(CALIB_DIR, stem + ".json")
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:  # noqa: BLE001 - 坏文件不该让整页挂掉
            continue
        tot = raw.get("total") or {}
        valid = int(tot.get("valid") or 0)
        hits = int(tot.get("hits") or 0)
        chain.append({
            "stage": stem,
            "label": STAGE_LABELS.get(stem, stem),
            "current": stem == "STABILITY",
            "mtime": os.path.getmtime(path),
            "rounds": int(raw.get("rounds") or 0),
            "hits": hits, "valid": valid,
            "rate": (hits / valid) if valid else None,
            "stable": int(raw.get("stable_hit") or 0),
            "flaky": int(raw.get("flaky") or 0),
            "never": int(raw.get("never") or 0),
        })
    return chain


# ===========================================================================
# 设备
# ===========================================================================
def _adbkit():
    import adbkit
    return adbkit


def adb_path():
    try:
        return _adbkit().resolve_adb()
    except Exception as e:  # noqa: BLE001
        return f"(未找到 adb: {type(e).__name__}: {e})"


def device_status(serial=None, deep=True):
    """设备状态。deep=True 时额外取型号/分辨率/前台 App（稍慢）。"""
    k = _adbkit()
    info = {
        "adb_path": adb_path(),
        "serial": serial or "",
        "online": False,
        "model": "", "size": "", "foreground": "",
        "error": "",
    }
    try:
        adb = k.Adb(serial)
        info["serial"] = adb.serial or ""
        addr = adb.ensure(retries=2)
        info["serial"] = addr or info["serial"]
        info["online"] = True
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
        return info
    if not deep:
        return info
    try:
        info["model"] = adb.shell("getprop ro.product.model", timeout=15).strip()
    except Exception:
        pass
    try:
        w, h = parse_wm_size(adb.shell("wm size", timeout=15))
        info["size"] = f"{w}x{h}" if w else ""
    except Exception:
        pass
    try:
        fg = parse_foreground(adb.shell("dumpsys window", timeout=30))
        info["foreground"] = fg["package"]
        info["foreground_activity"] = fg["activity"]
    except Exception:
        pass
    return info


def screenshot_png(serial=None, timeout=40):
    """实时截图，返回 PNG bytes（失败抛异常）。"""
    k = _adbkit()
    adb = k.Adb(serial)
    adb.ensure(retries=2)
    p = adb.run(["exec-out", "screencap", "-p"], timeout=timeout, binary=True)
    data = p.stdout or b""
    if not data.startswith(b"\x89PNG"):
        raise RuntimeError("截图失败（未返回 PNG）: "
                           + (p.stderr or b"").decode("utf-8", "replace")[:200])
    return data
```

### `webui/jobs.py`（420 行）

```python
# -*- coding: utf-8 -*-
"""webui.jobs - 后台任务执行器

一个 Job = 一串**串行**执行的子进程步骤，带增量日志与逐步状态。

为什么要子进程而不是进程内调用：
  * 执行器（executor.py）会独占设备与 uiautomator2 连接，崩溃/卡死会带走整个
    GUI；子进程隔离后，卡死可以 terminate，主服务不受影响；
  * 「停止」语义干净：杀掉进程树即可，不需要在业务代码里到处埋中断点。

为什么日志用「增量拉取」而不是 WebSocket：
  * stdlib 起 WebSocket 要自己实现握手与帧，成本高于收益；
  * 前端按 offset 轮询 `/api/jobs/<id>/log?offset=N` 只传新增部分，
    本地回环下开销可忽略，且天然支持断线重连后补齐。
"""
import os
import queue
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(BASE_DIR, "main.py")
DEVTOOLS = os.path.join(BASE_DIR, "devtools")

RUN_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}

# 日志环形缓冲上限（行）。超出后丢弃最旧的，但保留 base 偏移量，
# 前端仍能按绝对 offset 正确续读。
LOG_MAX_LINES = 20000

STATE_PENDING = "pending"
STATE_RUNNING = "running"
STATE_DONE = "done"
STATE_FAILED = "failed"
STATE_STOPPED = "stopped"


class Step:
    """一个子进程步骤（跑一个 App / 跑一个工具）。"""

    def __init__(self, title, cmd, meta=None):
        self.title = title
        self.cmd = list(cmd)
        self.meta = dict(meta or {})
        self.state = STATE_PENDING
        self.rc = None
        self.started = None
        self.ended = None

    @property
    def seconds(self):
        if self.started is None:
            return 0.0
        end = self.ended if self.ended is not None else time.time()
        return round(end - self.started, 1)

    def to_dict(self):
        return {
            "title": self.title,
            "cmd": self.cmd,
            "meta": self.meta,
            "state": self.state,
            "rc": self.rc,
            "seconds": self.seconds,
        }


class Job:
    """串行任务。线程安全：日志与状态都通过内部锁访问。"""

    def __init__(self, kind, title, steps, meta=None):
        self.id = uuid.uuid4().hex[:12]
        self.kind = kind                    # 'apps' | 'tool'
        self.title = title
        self.steps = list(steps)
        self.meta = dict(meta or {})
        self.state = STATE_PENDING
        self.created = time.time()
        self.started = None
        self.ended = None
        self.error = ""
        self._lines = []
        self._base = 0                      # 已丢弃的行数（绝对偏移基准）
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._proc = None
        self._thread = None

    # ---------------- 日志 ----------------
    def append(self, text):
        if not text:
            return
        with self._lock:
            self._lines.extend(text.splitlines(True))
            extra = len(self._lines) - LOG_MAX_LINES
            if extra > 0:
                del self._lines[:extra]
                self._base += extra

    def read_log(self, offset=0):
        """返回 (next_offset, text)。offset 是**绝对**行号。"""
        with self._lock:
            start = max(0, offset - self._base)
            chunk = "".join(self._lines[start:])
            return self._base + len(self._lines), chunk

    # ---------------- 状态 ----------------
    @property
    def finished(self):
        return self.state in (STATE_DONE, STATE_FAILED, STATE_STOPPED)

    def progress(self):
        done = sum(1 for s in self.steps if s.state in (STATE_DONE, STATE_FAILED,
                                                        STATE_STOPPED))
        return {
            "total": len(self.steps),
            "done": done,
            "current": next((s.title for s in self.steps
                             if s.state == STATE_RUNNING), ""),
        }

    def to_dict(self, with_steps=True):
        d = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "state": self.state,
            "meta": self.meta,
            "created": self.created,
            "started": self.started,
            "ended": self.ended,
            "seconds": round((self.ended or time.time()) - self.started, 1)
            if self.started else 0.0,
            "error": self.error,
            "progress": self.progress(),
        }
        if with_steps:
            d["steps"] = [s.to_dict() for s in self.steps]
        return d

    # ---------------- 控制 ----------------
    def start(self):
        if self._thread is not None:
            return False
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"job-{self.id}")
        self._thread.start()
        return True

    def stop(self):
        """请求停止：杀掉当前子进程树，并阻止后续步骤。"""
        self._stop.set()
        p = self._proc
        if p is not None and p.poll() is None:
            self.append("\n[控制台] 收到停止请求，正在终止子进程…\n")
            _kill_tree(p)

    @property
    def alive(self):
        return self._thread is not None and self._thread.is_alive()

    # ---------------- 执行 ----------------
    def _run(self):
        self.state = STATE_RUNNING
        self.started = time.time()
        self.append(f"[控制台] 任务开始 {datetime.now():%Y-%m-%d %H:%M:%S} "
                    f"（{len(self.steps)} 步）\n")
        stopped = False
        for i, step in enumerate(self.steps, 1):
            if self._stop.is_set():
                step.state = STATE_STOPPED
                stopped = True
                continue
            step.state = STATE_RUNNING
            step.started = time.time()
            self.append("\n" + "=" * 72 + "\n")
            self.append(f"▶ [{i}/{len(self.steps)}] {step.title}"
                        f"  （{datetime.now():%H:%M:%S}）\n")
            self.append("$ " + " ".join(step.cmd) + "\n")
            self.append("=" * 72 + "\n")
            rc = self._run_step(step)
            step.ended = time.time()
            if self._stop.is_set():
                step.state = STATE_STOPPED
                stopped = True
                self.append(f"—— [{i}/{len(self.steps)}] {step.title} 已停止\n")
            elif rc == 0:
                step.state = STATE_DONE
                self.append(f"—— [{i}/{len(self.steps)}] {step.title} 完成"
                            f"（{step.seconds}s）\n")
            else:
                step.state = STATE_FAILED
                self.append(f"—— [{i}/{len(self.steps)}] {step.title} 失败"
                            f"（退出码 {rc}，{step.seconds}s）\n")
        self.ended = time.time()
        if stopped:
            self.state = STATE_STOPPED
        elif any(s.state == STATE_FAILED for s in self.steps):
            self.state = STATE_FAILED
        else:
            self.state = STATE_DONE
        ok = sum(1 for s in self.steps if s.state == STATE_DONE)
        self.append(f"\n[控制台] 任务结束 {datetime.now():%Y-%m-%d %H:%M:%S}  "
                    f"成功 {ok}/{len(self.steps)}  用时 {round(self.ended - self.started, 1)}s\n")

    def _run_step(self, step):
        # 已经在停止状态就别再起了（stop 可能发生在启动瞬间）
        if self._stop.is_set():
            return -1
        try:
            p = subprocess.Popen(
                step.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1, cwd=BASE_DIR, env=RUN_ENV,
            )
        except Exception as e:  # noqa: BLE001
            self.append(f"[启动失败] {type(e).__name__}: {e}\n")
            return 1
        self._proc = p

        # 用读取线程 + 队列，而不是 `for line in p.stdout`。
        # 后者在**子进程不产生任何输出**时会一直阻塞 —— 而"卡死不输出"恰恰是
        # 最需要能停下来的场景：实测停止请求要等子进程自己写出内容才生效。
        q = queue.Queue()

        def _pump(pipe):
            try:
                for ln in pipe:
                    q.put(ln)
            except Exception:  # noqa: BLE001
                pass
            finally:
                q.put(None)          # 结束哨兵

        reader = threading.Thread(target=_pump, args=(p.stdout,), daemon=True)
        reader.start()
        try:
            while True:
                try:
                    line = q.get(timeout=0.2)
                except queue.Empty:
                    if self._stop.is_set():
                        _kill_tree(p)
                        continue
                    if p.poll() is not None:
                        # 进程已退出但读取线程还没吐完 -> 再等一小会
                        time.sleep(0.05)
                        try:
                            while True:
                                ln = q.get_nowait()
                                if ln is None:
                                    break
                                self.append(ln)
                        except queue.Empty:
                            pass
                        break
                    continue
                if line is None:
                    break
                self.append(line)
                if self._stop.is_set():
                    _kill_tree(p)
        except Exception as e:  # noqa: BLE001
            self.append(f"[读取输出异常] {type(e).__name__}: {e}\n")
        finally:
            if self._stop.is_set():
                _kill_tree(p)
            try:
                rc = p.wait(timeout=15)
            except Exception:
                _kill_tree(p)
                rc = p.poll()
            self._proc = None
        return rc if rc is not None else 1


def _kill_tree(p):
    """终止进程及其子树。Windows 上必须 /T，否则 uiautomator2 的 adb 子进程会残留。"""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            p.terminate()
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


class JobManager:
    """任务注册表。同一时刻只允许一个**运行中**任务（设备是独占资源）。"""

    def __init__(self, history=30):
        self._jobs = {}
        self._order = []
        self._history = history
        self._lock = threading.Lock()

    def create(self, kind, title, steps, meta=None):
        job = Job(kind, title, steps, meta)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self._history:
                old = self._order.pop(0)
                j = self._jobs.get(old)
                if j is not None and j.alive:
                    self._order.append(old)      # 还在跑，别丢
                    break
                self._jobs.pop(old, None)
        return job

    def get(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit=20):
        with self._lock:
            ids = list(reversed(self._order))[:limit]
            return [self._jobs[i].to_dict(with_steps=False)
                    for i in ids if i in self._jobs]

    def active(self):
        with self._lock:
            for i in reversed(self._order):
                j = self._jobs.get(i)
                if j is not None and not j.finished:
                    return j
        return None

    def stop_all(self):
        j = self.active()
        if j is not None:
            j.stop()
            return True
        return False


# ===========================================================================
# 命令构造（纯函数，便于单测）
# ===========================================================================
def build_app_steps(plan, dry_run=False, force=False, serial=None,
                    python=None, money_behaviors=None):
    """把 [{name, behaviors}] 编成 main.py 子进程步骤。

    plan 中 behaviors 为空表示「该 App 不做任何事」，直接跳过 ——
    不要退化成默认「签到」，那会让用户以为没选却跑了。
    money_behaviors: 资金类行为集合（提现等需人工确认的行为 key），
    由调用方从 config_loader.money_behaviors 注入，避免在命令构造层
    硬编码行为名单。
    """
    py = python or sys.executable
    mb = set(money_behaviors or ())
    steps = []
    for item in plan or []:
        name = (item.get("name") or "").strip()
        behaviors = [b for b in (item.get("behaviors") or []) if b]
        if not name or not behaviors:
            continue
        cmd = [py, MAIN_PY, "--app", name, "--task",
               _task_text(behaviors)]
        if serial:
            cmd += ["--serial", serial]
        if dry_run:
            cmd += ["--dry-run"]
        if force:
            cmd += ["--force"]
        steps.append(Step(name, cmd, meta={
            "app": name, "behaviors": behaviors,
            "money": [b for b in behaviors if b in mb],
        }))
    return steps


def _task_text(behaviors):
    from webui.data import behavior_task_text
    return behavior_task_text(behaviors)


# 预置工具：名字 -> (显示名, [脚本, 参数...], 说明, 参数输入提示)
TOOLS = {
    "preflight": ("环境自检", ["preflight.py"],
                  "检查依赖 / config / 设备 / 截图 / VLM", ""),
    "check_apps": ("应用安装核对", ["check_apps.py"],
                   "核对 34 个 App 是否已安装", ""),
    "shot": ("立即截图", ["shot.py"],
             "抓一张当前屏幕并存盘", ""),
    "verify_live": ("单 App 锚点回归", ["verify_live.py", "--probe-nav", "--nav-fast"],
                    "对指定 App 实机跑一遍锚点校验", "--apps 一淘"),
    "stability_run": ("多轮稳定性统计", ["stability_run.py", "--rounds", "3",
                                        "--probe-nav", "--nav-fast"],
                      "跑 3 轮统计命中率（耗时较长，勿与其它任务并行）",
                      "--apps 一淘,河马剧场"),
    "probe_deep": ("二级页深探", ["probe_deep.py"],
                   "穿透到二级页找真正入口", "--apps 一淘"),
}


def build_tool_step(tool, args=None, python=None):
    """构造一个 devtools 工具步骤。args 为附加参数列表（已由调用方白名单校验）。"""
    py = python or sys.executable
    if tool not in TOOLS:
        raise ValueError(f"未知工具: {tool}")
    title, script_args = TOOLS[tool][0], TOOLS[tool][1]
    cmd = [py, os.path.join(DEVTOOLS, script_args[0])] + list(script_args[1:])
    cmd += list(args or [])
    return Step(title, cmd, meta={"tool": tool})


def tool_catalog():
    return [{"id": k, "title": v[0], "desc": v[2],
             "argHint": v[3] if len(v) > 3 else "",
             "args": [a for a in v[1] if a.startswith("--")]}
            for k, v in TOOLS.items()]
```

### `webui/routes_yaml.py`（307 行）

```python
# -*- coding: utf-8 -*-
"""routes_yaml.py - WebUI 的 YAML 配置读写 + 自然语言生成接口（AUTOP-WEBUI-YAML-2026-10-22）

原计划派 marvis A 卡实现，但其会话 failed（零产物），由 Host 接手完成。
契约见派单卡 `dispatch/AUTOP-WEBUI-YAML-2026-10-22-A-CARD.md`。

设计要点：
  * 只暴露 `YamlRoutes`，`handle_get/handle_post` 返回 `None` 表示「不是我的路由」。
  * 写盘一律走 `devtools/yaml_writer`（eol 保真 / 备份 / 原子写），不自己 open(path,"w")。
  * 自然语言生成一律走 `devtools/nl_to_steps.build_behavior`，不复制词表。
  * `_snapshot/_verify` 按**当前 APPS_DIR** 做快照与比对（模块级常量可 monkeypatch），
    测试用临时目录即可，不必依赖真实 config.yaml。
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import yaml  # noqa: E402
except ImportError as _exc:  # pragma: no cover - 解释器选错时的友好提示
    raise ImportError(
        "routes_yaml 需要 PyYAML，但当前解释器没装它。\n"
        "本项目依赖装在仓库根目录的 .venv 里，请用项目解释器：\n"
        "    C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\.venv\\Scripts\\python.exe\n"
        "正确启动方式（注意是 gui.py，不是本文件）：\n"
        "    ./.venv/Scripts/python.exe gui.py --port 8765\n"
        "本文件是被 webui/server.py import 的库模块，直接运行它没有入口。"
    ) from _exc

from devtools import yaml_writer  # noqa: E402
from devtools import nl_to_steps  # noqa: E402

APPS_DIR = os.path.join(_ROOT, "config", "apps")
CONFIG_YAML = os.path.join(_ROOT, "config.yaml")


class YamlRoutes:
    """挂到 server.py 的 Handler 上：self.h 提供 _json/_err。"""

    def __init__(self, handler):
        self.h = handler

    # ---------- 入口 ----------

    def handle_get(self, path, q):
        if path == "/api/yaml/apps":
            return self._apps()
        if path == "/api/yaml/app":
            return self._app_text((q.get("name") or [""])[0])
        if path == "/api/yaml/fragment":
            return self._fragment((q.get("name") or [""])[0],
                                  (q.get("behavior") or ["sign"])[0])
        return None

    def handle_post(self, path, payload):
        if path == "/api/yaml/app":
            return self._save(payload or {})
        if path == "/api/yaml/generate":
            return self._generate(payload or {})
        if path == "/api/yaml/apply":
            return self._apply(payload or {})
        return None

    # ---------- 共用 ----------

    @staticmethod
    def _app_file(name: str) -> str:
        if not name or "/" in name or ".." in name or "\\" in name:
            raise ValueError(f"非法 app 名: {name!r}")
        for fn in sorted(os.listdir(APPS_DIR)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            stem = fn[:-5]
            if stem == name or stem.split("_", 1)[-1] == name:
                return os.path.join(APPS_DIR, fn)
        raise ValueError(f"未找到 App 配置: {name}")

    @staticmethod
    def _app_name_of(path: str) -> str:
        try:
            return (yaml_writer.load_app(path).get("name") or "").strip()
        except Exception:  # noqa: BLE001
            return os.path.splitext(os.path.basename(path))[0]

    def _snapshot(self) -> dict:
        """{app_name: app_dict}，范围=当前 APPS_DIR（可 monkeypatch）。"""
        out = {}
        for fn in sorted(os.listdir(APPS_DIR)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            p = os.path.join(APPS_DIR, fn)
            out[self._app_name_of(p)] = yaml_writer.load_app(p)
        return out

    def _verify(self, path: str, before: dict) -> tuple[bool, list[str]]:
        """目标文件可解析 + 除目标外其余 App 逐字不变。"""
        problems: list[str] = []
        try:
            target_name = (yaml_writer.load_app(path).get("name") or "").strip()
        except Exception as exc:  # noqa: BLE001
            return False, [f"目标文件无法解析: {exc}"]
        after = self._snapshot()
        if len(after) != len(before):
            problems.append(f"app 数量变化: {len(before)} -> {len(after)}")
        for name, app in before.items():
            if name == target_name:
                continue
            if after.get(name) != app:
                problems.append(f"误伤其他 App: {name}")
        return (not problems), problems

    @staticmethod
    def _money_behaviors() -> set:
        try:
            import config_loader
            return set(config_loader.money_behaviors(
                config_loader.load_config(CONFIG_YAML)))
        except Exception:  # noqa: BLE001
            return {"withdraw"}

    # ---------- GET ----------

    def _apps(self):
        apps = []
        for fn in sorted(os.listdir(APPS_DIR)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            p = os.path.join(APPS_DIR, fn)
            try:
                data = yaml_writer.load_app(p)
            except Exception:  # noqa: BLE001
                continue
            apps.append({
                "name": (data.get("name") or "").strip(),
                "file": fn,
                "size": os.path.getsize(p),
                "mtime": int(os.path.getmtime(p)),
                "behaviors": sorted((data.get("behaviors") or {}).keys()),
            })
        return 200, {"ok": True, "apps": apps}

    def _app_text(self, name):
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}
        try:
            _lines, eol, _ends = yaml_writer.read_text(path)
            with open(path, "r", encoding="utf-8", newline="") as f:
                text = f.read()
        except OSError as e:
            return 500, {"ok": False, "error": str(e)}
        return 200, {"ok": True, "name": name, "file": os.path.basename(path),
                     "eol": eol, "text": text}

    def _fragment(self, name, behavior):
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}
        data = yaml_writer.load_app(path)
        acts = (data.get("behaviors") or {}).get(behavior)
        if acts is None:
            return 404, {"ok": False, "error": f"{name} 没有行为 {behavior}"}
        lines, _eol, _ends = yaml_writer.read_text(path)
        indent = yaml_writer.behavior_indent(lines, 0, len(lines)) or 2
        block = yaml_writer.render_behavior_block(behavior, acts, indent)
        return 200, {"ok": True, "fragment": "\n".join(block)}

    # ---------- POST ----------

    def _save(self, payload):
        name = str(payload.get("name") or "").strip()
        text = payload.get("text")
        if not name or not isinstance(text, str):
            return 400, {"ok": False, "error": "缺少 name 或 text"}
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}

        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as e:
            return 400, {"ok": False, "error": f"YAML 解析失败: {e}"}
        if not isinstance(parsed, dict) or not parsed.get("name"):
            return 400, {"ok": False, "error": "YAML 顶层必须是含 name 的映射"}

        before = self._snapshot()
        lines, eol, ends_nl = yaml_writer.read_text(path)
        new_lines = text.replace("\r\n", "\n").rstrip("\n").split("\n")
        if new_lines == lines:
            return 200, {"ok": True, "action": "unchanged", "diff": ""}

        bak = yaml_writer.backup(path, tag="WEBUI")
        yaml_writer.atomic_write(path, new_lines, eol, ends_nl)
        ok, problems = self._verify(path, before)
        if not ok:
            import shutil
            shutil.copy2(bak, path)
            return 200, {"ok": True, "action": "rolled_back", "backup": bak,
                         "diff": "", "warnings": problems}
        diff = yaml_writer._unified_diff(lines, new_lines, path)
        return 200, {"ok": True, "action": "saved", "backup": bak, "diff": diff}

    def _generate(self, payload):
        name = str(payload.get("name") or "").strip()
        behavior = str(payload.get("behavior") or "sign").strip()
        text = str(payload.get("text") or "").strip()
        if not name or not text:
            return 400, {"ok": False, "error": "缺少 name 或 text"}
        if behavior in self._money_behaviors() and not payload.get("allow_money"):
            return 400, {"ok": False,
                         "error": f"拒绝为资金类行为生成配置: {behavior}（需 allow_money）"}
        try:
            app_cfg = yaml_writer.load_app(self._app_file(name))
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}

        params = {}
        for key in ("tab_text", "tab_xy", "hub_text", "hub_xy",
                    "anchor_text", "anchor_xy", "ball_xy"):
            if payload.get(key):
                params[key] = payload[key]
        if payload.get("xy"):
            params["sign_xy"] = payload["xy"]      # 前端的 xy 就是签到跳坐标
        if payload.get("h5"):
            params["h5"] = True
            params["h5_offset"] = float(payload.get("h5_offset") or 60)
        entry = str(payload.get("entry") or "auto")

        result = nl_to_steps.build_behavior(text, name, behavior,
                                            entry=entry, params=params,
                                            app_cfg=app_cfg)
        return 200, {"ok": True, "entry": result["entry"],
                     "actions": result["actions"],
                     "fragment": nl_to_steps.to_yaml_fragment(result["actions"]),
                     "warnings": result["warnings"],
                     "candidates_used": result["candidates_used"]}

    def _apply(self, payload):
        name = str(payload.get("name") or "").strip()
        behavior = str(payload.get("behavior") or "sign").strip()
        actions = payload.get("actions")
        force = bool(payload.get("force"))
        if not name:
            return 400, {"ok": False, "error": "缺少 name"}
        if behavior in self._money_behaviors() and not payload.get("allow_money"):
            return 400, {"ok": False,
                         "error": f"拒绝写入资金类行为: {behavior}（需 allow_money）"}
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}

        if not actions and payload.get("text"):
            gen_code, gen = self._generate({
                "name": name, "behavior": behavior, "text": payload["text"],
                "entry": payload.get("entry") or "auto",
                **{k: payload[k] for k in ("tab_text", "tab_xy", "hub_text", "hub_xy",
                                           "anchor_text", "anchor_xy", "ball_xy", "xy",
                                           "h5", "h5_offset") if payload.get(k)},
            })
            if gen_code != 200:
                return gen_code, gen
            actions = gen["actions"]
        if not isinstance(actions, list) or not actions:
            return 400, {"ok": False, "error": "缺少 actions（或提供 text 由后端生成）"}

        # yaml_writer 的路径白名单按 base_dir 判定；base_dir 取 APPS_DIR 的上两级，
        # 这样测试把 APPS_DIR 指到临时目录时同样合法。
        base_dir = os.path.dirname(os.path.dirname(APPS_DIR))
        before = self._snapshot()
        if force:
            wr = yaml_writer.replace_behavior(path, behavior, actions,
                                              apply=True, force=True, tag="WEBUI",
                                              base_dir=base_dir)
        else:
            wr = yaml_writer.insert_behavior(path, behavior, actions,
                                             apply=True, tag="WEBUI",
                                             base_dir=base_dir)
        if not wr.changed:
            return 200, {"ok": True, "action": wr.action, "diff": wr.diff,
                         "warnings": wr.warnings}
        ok, problems = self._verify(path, before)
        if not ok:
            import shutil
            if wr.backup and os.path.exists(wr.backup):
                shutil.copy2(wr.backup, path)
            return 200, {"ok": True, "action": "rolled_back", "backup": wr.backup,
                         "diff": wr.diff, "warnings": problems}
        return 200, {"ok": True, "action": wr.action, "backup": wr.backup,
                     "diff": wr.diff, "warnings": wr.warnings}


if __name__ == "__main__":  # pragma: no cover - 只给人看，不该被直接运行
    print(__doc__ or "")
    print("本文件是被 webui/server.py import 的库模块，没有可执行入口。")
    print("启动 Web 控制台请用项目 venv：")
    print("    ./.venv/Scripts/python.exe gui.py --port 8765")
    print("启动后浏览器打开 http://127.0.0.1:8765/ ，左侧导航「✎ YAML 编辑」。")
    sys.exit(2)
```

### `webui/server.py`（445 行）

```python
# -*- coding: utf-8 -*-
"""webui.server - 本地 HTTP 服务与 JSON API

安全设计（本地工具也要防）：
  1. **只绑定 127.0.0.1** —— 不监听 0.0.0.0，局域网内其他机器访问不到。
  2. **写操作要求一次性 token**：启动时随机生成，注入首页 HTML，
     前端在 `X-Auth-Token` 头里回传。这样即使浏览器打开了恶意网页，
     它既拿不到 token（同源策略），也无法用简单表单触发 POST。
  3. **静态文件路径穿越防护**：解析后必须落在 static 目录内。
  4. **资金类行为二次确认在服务端强制**：带 `withdraw` 的计划必须显式带
     `confirm_money=true`，否则 400 —— 不能只靠前端弹窗（项目硬约束：
     提现/支付/转账必须先向用户说明影响面并取得明确授权）。
"""
import json
import mimetypes
import os
import posixpath
import secrets
import socket
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

sys.path.insert(0, BASE_DIR)

from webui import data as D            # noqa: E402
from webui import jobs as J            # noqa: E402

API_PREFIX = "/api/"
MAX_BODY = 1 << 20          # 1 MiB


class Console:
    """服务端上下文：数据、任务、token。"""

    def __init__(self, config_path=D.CONFIG_YAML, db_path=D.DB_PATH):
        self.store = D.Store(config_path, db_path)
        self.jobs = J.JobManager()
        self.token = secrets.token_urlsafe(24)
        self.started = time.time()

    # ---------------- 业务 ----------------
    def create_app_job(self, payload):
        if "plan" not in payload:
            raise ValueError(
                "缺少 plan 字段：应为 [{name, behaviors}] 数组"
                f"（收到字段：{', '.join(sorted(payload)) or '空'}）")
        plan = payload.get("plan") or []
        if not isinstance(plan, list):
            raise ValueError("plan 必须是数组")
        serial = (payload.get("serial") or "").strip() or None
        dry_run = bool(payload.get("dry_run"))
        force = bool(payload.get("force"))

        known = {a["name"]: {b["id"] for b in a["behaviors"]}
                 for a in self.store.apps()}
        # 资金类行为集合统一来自 config_loader.money_behaviors（配置可覆盖），
        # 不在此硬编码行为名单（C9 MONEY 驱动收敛）。
        money_behaviors = D._money_behaviors(self.store.config())
        clean, money_apps = [], []
        for item in plan:
            name = str((item or {}).get("name") or "").strip()
            if name not in known:
                raise ValueError(f"配置中不存在 App：{name}")
            behaviors = [str(b) for b in ((item or {}).get("behaviors") or [])]
            bad = [b for b in behaviors if b not in known[name]]
            if bad:
                raise ValueError(f"{name} 未配置行为：{', '.join(bad)}")
            if behaviors:
                clean.append({"name": name, "behaviors": behaviors})
            if any(b in money_behaviors for b in behaviors):
                money_apps.append(name)
        if not clean:
            raise ValueError("没有可执行的步骤（请至少勾选一个 App 的行为）")

        # 资金类行为：必须显式确认（服务端强制，不依赖前端）
        if money_apps and not payload.get("confirm_money"):
            raise PermissionError(
                "计划包含资金类行为（提现）：" + "、".join(money_apps) +
                "。提现属于资金操作，需人工确认后才会执行。")

        steps = J.build_app_steps(clean, dry_run=dry_run, force=force,
                                  serial=serial,
                                  money_behaviors=money_behaviors)
        mode = "预览" if dry_run else "执行"
        # 标题必须带 App 名：否则历史列表里十条全是「执行 1 个 App」，
        # 完全分不清哪条是哪条（实测就是这么撞上的）。
        names = "、".join(x["name"] for x in clean[:3])
        if len(clean) > 3:
            names += f" 等 {len(clean)} 个"
        title = f"{mode} {names}" + ("（含提现）" if money_apps else "")
        job = self.jobs.create("apps", title, steps, meta={
            "dry_run": dry_run, "force": force, "serial": serial,
            "money_apps": money_apps, "plan": clean,
        })
        job.start()
        return job

    def create_tool_job(self, tool, payload):
        args = payload.get("args") or []
        if not isinstance(args, list):
            raise ValueError("args 必须是数组")
        args = [str(a) for a in args][:12]
        # 白名单：只允许 --flag 与普通值，禁止任何 shell 元字符以外的路径拼接
        for a in args:
            if len(a) > 120 or "\n" in a or "\r" in a:
                raise ValueError(f"非法参数：{a!r}")
        step = J.build_tool_step(tool, args)
        job = self.jobs.create("tool", f"工具 · {step.title}", [step],
                               meta={"tool": tool, "args": args})
        job.start()
        return job


class Handler(BaseHTTPRequestHandler):
    server_version = "AndroidAutopilotConsole"
    protocol_version = "HTTP/1.1"

    # ---------- 基础设施 ----------
    @property
    def console(self):
        return self.server.console

    def log_message(self, fmt, *args):        # 静音默认 access log
        pass

    def _send(self, code, body=b"", ctype="application/json; charset=utf-8",
              extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        extra = dict(extra or {})
        if not any(k.lower() == "cache-control" for k in extra):
            extra["Cache-Control"] = "no-store"
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError):
                pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _err(self, code, msg):
        self._json({"ok": False, "error": msg}, code)

    def _auth_ok(self):
        """写操作鉴权：token 必须匹配。"""
        tok = self.headers.get("X-Auth-Token") or ""
        return secrets.compare_digest(tok, self.console.token)

    def _read_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return {}
        if n > MAX_BODY:
            raise ValueError("请求体过大")
        raw = self.rfile.read(n)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    # ---------- 路由 ----------
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path, q = u.path, urllib.parse.parse_qs(u.query)
        try:
            if path.startswith(API_PREFIX):
                return self._api_get(path, q)
            if path in ("/", "/index.html"):
                return self._serve_index()
            if path == "/yaml.html":
                return self._serve_page("yaml.html")
            return self._serve_static(path)
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    do_HEAD = do_GET

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        if not path.startswith(API_PREFIX):
            return self._err(404, "not found")
        if not self._auth_ok():
            return self._err(403, "缺少或错误的 X-Auth-Token（写操作需鉴权）")
        try:
            payload = self._read_json()
        except Exception as e:  # noqa: BLE001
            return self._err(400, f"请求体解析失败：{e}")
        try:
            return self._api_post(path, payload)
        except PermissionError as e:
            return self._err(403, str(e))
        except ValueError as e:
            return self._err(400, str(e))
        except Exception as e:  # noqa: BLE001
            self._err(500, f"{type(e).__name__}: {e}")

    # ---------- GET ----------
    def _api_get(self, path, q):
        c = self.console
        # YAML 配置读写 / 自然语言生成（AUTOP-WEBUI-YAML-2026-10-22）
        try:
            from webui.routes_yaml import YamlRoutes
            hit = YamlRoutes(self).handle_get(path, q)
        except (ImportError, NotImplementedError):
            hit = None
        if hit is not None:
            code, obj = hit
            return self._json(obj, code)
        if path == "/api/health":
            return self._json({
                "ok": True, "version": _version(), "root": BASE_DIR,
                "python": sys.executable, "uptime": round(time.time() - c.started, 1),
                "config": c.store.config_path,
            })
        if path == "/api/overview":
            return self._json(c.store.overview())
        if path == "/api/device":
            deep = (q.get("deep", ["1"])[0] != "0")
            serial = (q.get("serial", [""])[0] or "").strip() or None
            return self._json(D.device_status(serial, deep=deep))
        if path == "/api/device/screen.png":
            serial = (q.get("serial", [""])[0] or "").strip() or None
            png = D.screenshot_png(serial)
            return self._send(200, png, "image/png")
        if path == "/api/earnings":
            days = int((q.get("days", ["7"])[0] or 7))
            app = (q.get("app", [""])[0] or "").strip() or None
            limit = int((q.get("limit", ["500"])[0] or 500))
            return self._json(c.store.earnings(days=days, app=app, limit=limit))
        if path == "/api/ops":
            return self._json({
                "rows": c.store.ops(limit=int((q.get("limit", ["50"])[0] or 50)),
                                    level=(q.get("level", [""])[0] or None)),
                "stats": c.store.ops_stats(),
            })
        if path == "/api/tools":
            return self._json({"tools": J.tool_catalog()})
        if path == "/api/calib":
            out = dict(c.store.stability())
            out["chain"] = D.stability_chain()
            return self._json(out)
        if path == "/api/jobs":
            return self._json({"jobs": c.jobs.list(),
                               "active": (c.jobs.active().id
                                          if c.jobs.active() else None)})
        m = _match(path, "/api/jobs/{id}/log")
        if m:
            job = c.jobs.get(m["id"])
            if job is None:
                return self._err(404, "任务不存在")
            off = int((q.get("offset", ["0"])[0] or 0))
            nxt, text = job.read_log(off)
            return self._json({"offset": off, "next": nxt, "text": text,
                               "state": job.state})
        m = _match(path, "/api/jobs/{id}")
        if m:
            job = c.jobs.get(m["id"])
            if job is None:
                return self._err(404, "任务不存在")
            return self._json(job.to_dict())
        return self._err(404, f"未知接口 {path}")

    # ---------- POST ----------
    def _api_post(self, path, payload):
        c = self.console
        # YAML 配置读写 / 自然语言生成（写操作已由 do_POST 统一鉴权）
        try:
            from webui.routes_yaml import YamlRoutes
            hit = YamlRoutes(self).handle_post(path, payload)
        except (ImportError, NotImplementedError):
            hit = None
        if hit is not None:
            code, obj = hit
            return self._json(obj, code)
        if path == "/api/overview/reload":
            c.store.config(reload=True)
            return self._json(c.store.overview())
        if path == "/api/config/open":
            return self._open_config()
        if path == "/api/jobs":
            active = c.jobs.active()
            if active is not None:
                return self._err(409, f"已有任务在运行（{active.title}），请先停止")
            job = c.create_app_job(payload)
            return self._json({"ok": True, "job": job.to_dict(with_steps=False)})
        if path == "/api/jobs/stop":
            ok = c.jobs.stop_all()
            return self._json({"ok": ok})
        m = _match(path, "/api/jobs/{id}/stop")
        if m:
            job = c.jobs.get(m["id"])
            if job is None:
                return self._err(404, "任务不存在")
            job.stop()
            return self._json({"ok": True})
        m = _match(path, "/api/tools/{id}/run")
        if m:
            active = c.jobs.active()
            if active is not None:
                return self._err(409, f"已有任务在运行（{active.title}），请先停止")
            job = c.create_tool_job(m["id"], payload)
            return self._json({"ok": True, "job": job.to_dict(with_steps=False)})
        return self._err(404, f"未知接口 {path}")

    # ---------- 静态资源 ----------
    def _open_config(self):
        """用系统默认程序打开 config.yaml（仅限配置内的这个路径，不接受任意路径）。"""
        p = self.console.store.config_path
        if not os.path.isfile(p):
            raise ValueError(f"配置文件不存在：{p}")
        if os.name == "nt":
            os.startfile(p)                      # noqa: S606
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", p])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", p])
        return self._json({"ok": True, "path": p})

    def _serve_index(self):
        p = os.path.join(STATIC_DIR, "index.html")
        try:
            with open(p, "r", encoding="utf-8") as f:
                html = f.read()
        except OSError as e:
            return self._err(500, f"缺少前端文件 {p}: {e}")
        # 注入一次性 token（前端写操作回传），并禁止被缓存
        html = html.replace("__CONSOLE_TOKEN__", self.console.token)
        return self._send(200, html, "text/html; charset=utf-8",
                          {"Cache-Control": "no-store"})

    def _serve_page(self, name: str):
        """ serve 其它顶层页面（如 yaml.html），同样注入一次性 token。"""
        p = os.path.join(STATIC_DIR, name)
        if name not in ("yaml.html",):        # 白名单，避免当任意文件读取器用
            return self._err(404, "未知页面")
        try:
            with open(p, "r", encoding="utf-8") as f:
                html = f.read()
        except OSError as e:
            return self._err(500, f"缺少前端文件 {p}: {e}")
        html = html.replace("__CONSOLE_TOKEN__", self.console.token)
        return self._send(200, html, "text/html; charset=utf-8",
                          {"Cache-Control": "no-store"})

    def _serve_static(self, path):
        # URL 形如 /static/app.css —— 前缀 "/static/" 是路由，不是目录名，
        # 必须剥掉，否则会拼成 webui/static/static/app.css（实测踩过）。
        rel = urllib.parse.unquote(path)
        if rel.startswith("/static/"):
            rel = rel[len("/static/"):]
        else:
            rel = rel.lstrip("/")
        rel = posixpath.normpath(rel)
        if rel.startswith("..") or os.path.isabs(rel):
            return self._err(403, "非法路径")
        full = os.path.join(STATIC_DIR, rel)
        real = os.path.realpath(full)
        if not real.startswith(os.path.realpath(STATIC_DIR) + os.sep):
            return self._err(403, "非法路径")
        if not os.path.isfile(real):
            return self._err(404, f"未找到 {rel}")
        ctype = mimetypes.guess_type(real)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",
                                                  "application/json"):
            ctype += "; charset=utf-8"
        with open(real, "rb") as f:
            return self._send(200, f.read(), ctype,
                              {"Cache-Control": "no-cache"})


def _match(path, pattern):
    """极简路径匹配：/api/jobs/{id}/log -> {'id': ...}。"""
    p, q = pattern.split("/"), path.split("/")
    if len(p) != len(q):
        return None
    out = {}
    for a, b in zip(p, q):
        if a.startswith("{") and a.endswith("}"):
            if not b:
                return None
            out[a[1:-1]] = b
        elif a != b:
            return None
    return out


def _version():
    try:
        from webui import __version__
        return __version__
    except Exception:
        return "?"


def find_free_port(preferred=8765, host="127.0.0.1", tries=20):
    # Windows 下 SO_REUSEADDR 允许抢占已监听端口，探测不得带该选项；
    # bind+listen 双成功才算端口真实空闲（踩坑：8765 被 MySessions 占用仍误判可用）。
    for port in range(preferred, preferred + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                s.listen(1)
                return port
            except OSError:
                continue
    raise RuntimeError(f"{preferred}~{preferred + tries} 端口都被占用")


def make_server(host="127.0.0.1", port=8765, console=None):
    console = console or Console()

    class _Server(ThreadingHTTPServer):
        # Windows 上 allow_reuse_address=1 同样可抢占已监听端口，必须关掉。
        allow_reuse_address = False

    httpd = _Server((host, port), Handler)
    httpd.daemon_threads = True
    httpd.console = console
    return httpd


def serve_forever(host="127.0.0.1", port=8765, console=None):
    httpd = make_server(host, port, console)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd
```
