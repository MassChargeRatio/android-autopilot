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
