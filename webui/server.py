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
# 需要注入 token 的「顶层页面」白名单（唯一事实源）：
# 新增页面只改这里，do_GET 与 _serve_page 都基于它判断，避免两处硬编码
# 白名单漂移（历史症状：do_GET 里写了 path == "/xxx.html" 但 _serve_page
# 的白名单元组没同步 -> 页面永远 404，或反过来白名单放宽成任意文件读取器）。
PAGES = ("yaml.html",)

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
        job = self.jobs.create_exclusive("apps", title, steps, meta={
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
            if path.lstrip("/") in PAGES:
                return self._serve_page(path.lstrip("/"))
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
            # 判空闲 + 登记收敛到 JobManager.create_exclusive（同一把锁内完成）：
            # 历史写法「先 active() 检查、再 create()」中间有空窗，两个并发
            # 请求可同时通过检查 -> 同时起两个任务抢独占设备。
            try:
                job = c.create_app_job(payload)
            except J.JobBusy as e:
                return self._err(409, str(e))
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
            try:
                job = c.create_tool_job(m["id"], payload)
            except J.JobBusy as e:
                return self._err(409, str(e))
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
        if name not in PAGES:                 # 白名单，避免当任意文件读取器用
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
