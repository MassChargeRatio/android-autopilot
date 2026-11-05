# -*- coding: utf-8 -*-
"""test_webui.py - Web 控制台的纯逻辑与接口契约（不触碰真机）

覆盖三类容易出错、且出错后很难发现的地方：
  1. **数据层纯函数**：锚点摘要（层级/路径数/导航前置步）、配置体检、
     收益聚合与趋势、dumpsys/wm 解析。这些直接决定界面上显示什么。
  2. **任务层**：命令拼装（空行为必须跳过、资金类标记、--dry-run/--force）、
     增量日志的 offset 语义（前端靠它续读，错了会丢日志或重复）。
  3. **服务层**：路由匹配、写操作鉴权、**资金类行为必须二次确认**
     （项目硬约束：提现/支付/转账不得自动执行）、静态文件路径穿越防护。

运行：python tests/test_webui.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from webui import data as D      # noqa: E402
from webui import jobs as J      # noqa: E402
from webui import server as S    # noqa: E402


# ===========================================================================
# 1. 数据层纯函数
# ===========================================================================
def _nav_step():
    return {"type": "click_point", "x": 0.9, "y": 0.915,
            "vlm_prompt": "定位屏幕底部导航栏最右侧的『我的』标签中心"}


def t_summarize_simple_behavior():
    """单锚点行为：1 层、1 条路径、无导航前置步。"""
    s = D.summarize_behavior([{"type": "click_first",
                               "candidates": [{"type": "text", "value": "签到"}]}])
    assert s["levels"] == 1, s
    assert s["branches"] == 1, s
    assert s["has_prelude"] is False, s
    assert s["anchors"][0]["candidates"] == ["签到"], s
    print("OK  单锚点行为 -> 1 层 / 1 路径 / 无前置步")


def t_summarize_three_level_anyof():
    """三级 any_of：识别出导航前置步与最长层级。

    分支2 = [我的(导航), think, 福利中心, 签到]。「我的」不是锚点，但它是
    **前置步**；再加 2 个锚点 —— 这条路径要三级才能到目标。
    口径：层级 = 1(首屏) + 有前置步 + 路径上锚点数 > 1。
    """
    act = [{"type": "any_of", "choices": [
        [{"type": "click_first", "candidates": [{"type": "text", "value": "签到"}]}],
        [_nav_step(), {"type": "think"},
         {"type": "click_first", "candidates": [{"type": "text", "value": "福利中心"}]},
         {"type": "click_first", "candidates": [{"type": "text", "value": "签到"}]}],
    ]}]
    s = D.summarize_behavior(act)
    assert s["branches"] == 2, s
    assert s["levels"] == 3, s          # 1 + 前置步 + 2 个锚点
    assert s["has_prelude"] is True, s
    # 跨分支按 (type, key) 去重：两条分支的「签到」是同一个锚点
    assert [a["key"] for a in s["anchors"]] == ["签到", "福利中心"], s
    print("OK  三级 any_of -> 2 路径 / 3 层 / 检出导航前置步")


def t_anchor_kinds_are_classified_by_payload():
    """锚点必须按**载荷**分类，不能只看 type —— click_point 是重载类型。

    踩过的坑：最初只把 click_text/id/desc/click_first 当锚点，于是把 30 个
    「图像模板匹配」行为误报成「没有可校验的锚点动作」，总览页一片假红字；
    随后又漏了 click_id 靠 res_id 定位，把正常的关闭按钮锚点报成「未配置候选」。
    """
    img = {"type": "click_point", "images": ["images/a/b.png"],
           "desc": "图像-某App-任务界面-签到", "optional": True}
    nav = _nav_step()                                    # 导航前置步，不是锚点
    pure = {"type": "click_point", "x": 0.5, "y": 0.5}   # 纯比例兜底，不是锚点
    rid = {"type": "click_id", "res_id": "com.x:id/iv_close"}
    first = {"type": "click_first",
             "candidates": [{"type": "text", "value": "签到"},
                            {"type": "text", "value": "每日签到"}]}

    assert D.is_anchor(img) is True, img
    assert D.is_anchor(nav) is False, nav
    assert D.is_anchor(pure) is False, pure
    assert D.is_anchor(rid) is True, rid
    assert D.is_nav_prelude(nav) is True and D.is_nav_prelude(img) is False

    s = D.summarize_behavior([img, nav, pure, rid, first])
    assert s["levels"] == 3, s            # 1 + 前置步 + 路径上 3 个锚点(>1)
    assert s["has_prelude"] is True, s
    by_via = {a["via"]: a for a in s["anchors"]}
    assert set(by_via) == {"图像", "rid", "候选"}, s
    assert by_via["图像"]["key"] == "images/a/b.png", s   # key 取参考图
    assert by_via["图像"]["images"] == 1, s
    assert by_via["rid"]["key"] == "com.x:id/iv_close", s  # key 取 res_id
    assert by_via["候选"]["key"] == "签到", s              # key 取首个候选
    # 纯比例兜底点不能混进锚点
    assert len(s["anchors"]) == 3, s
    print("OK  锚点按载荷分类（图像/rid/候选/导航前置/纯比例）")


def t_validate_config_accepts_image_and_rid_anchors():
    """图像锚点与 rid 锚点都是合法定位手段，体检不得报错。"""
    cfg = {"apps": [
        {"name": "图像App", "package": "com.img", "behaviors": {
            "sign": [{"type": "click_point", "images": ["images/x/y.png"]}]}},
        {"name": "RidApp", "package": "com.rid", "behaviors": {
            "sign": [{"type": "click_id", "res_id": "com.rid:id/btn"}]}},
    ]}
    issues = D.validate_config(cfg)
    assert issues == [], issues
    # 反向：真的没有定位依据时仍要报错
    bad = {"apps": [{"name": "空App", "package": "com.bad", "behaviors": {
        "sign": [{"type": "click_point", "x": 0.5, "y": 0.5}]}}]}
    got = D.validate_config(bad)
    assert any(i["level"] == "ERROR" for i in got), got
    print("OK  体检接受图像/rid 锚点，仍拒真·无锚点行为")


def t_summarize_variant_templates():
    """多候选模板 [[..],[..]] 取第一组，不把模板层数算成路径数。"""
    act = [[{"type": "click_text", "text": "签到"}],
           [{"type": "click_text", "text": "每日签到"}]]
    s = D.summarize_behavior(act)
    assert s["levels"] == 1, s
    assert s["anchors"][0]["text"] == "签到", s
    print("OK  多候选模板取第一组")


def t_validate_config_catches_real_problems():
    cfg = {"apps": [
        {"name": "A", "package": "com.a", "behaviors": {
            "sign": [{"type": "click_text", "text": "签到"}]}},
        {"name": "A", "package": "com.a2", "behaviors": {}},          # 重名 + 无行为
        {"name": "B", "package": "", "behaviors": {                   # 缺 package
            "sign": [{"type": "think"}]}},                            # 无锚点
    ]}
    issues = D.validate_config(cfg)
    msgs = " | ".join(i["msg"] for i in issues)
    assert any("App 名重复" in i["msg"] for i in issues), msgs
    assert any("未配置任何行为" in i["msg"] for i in issues), msgs
    assert any("缺少 package" in i["msg"] for i in issues), msgs
    assert any("没有可校验的锚点动作" in i["msg"] for i in issues), msgs
    assert all(i["level"] in ("ERROR", "WARN") for i in issues)
    print(f"OK  配置体检抓到 4 类问题（共 {len(issues)} 条）")


def t_aggregate_and_series():
    rows = [
        ("2026-09-15 08:00:00", "A", "sign", 100, "金币", ""),
        ("2026-09-15 09:00:00", "B", "watch", 50, "金币", ""),
        ("2026-09-14 09:00:00", "A", "sign", 1.5, "元", ""),
    ]
    agg = D.aggregate_earnings(rows, today="2026-09-15")
    by = {x["unit"]: x for x in agg["summary"]}
    assert by["金币"]["total"] == 150, by
    assert by["金币"]["today"] == 150, by
    assert by["元"]["today"] == 0, by
    assert agg["total_rows"] == 3
    ser = D.daily_series(rows, days=2, today="2026-09-15")
    assert [x["date"] for x in ser] == ["2026-09-14", "2026-09-15"], ser
    assert ser[1]["total"] == 150, ser
    print("OK  收益聚合（按单位/今日）与近 N 日趋势正确")


def t_parse_device_outputs():
    out = ("  mCurrentFocus=Window{a1b2 u0 com.kwai.theater/"
           "com.kwai.theater.MainActivity}\n")
    fg = D.parse_foreground(out)
    assert fg["package"] == "com.kwai.theater", fg
    assert fg["activity"] == "com.kwai.theater.MainActivity", fg
    assert D.parse_foreground("") == {"package": "", "activity": ""}
    assert D.parse_wm_size("Physical size: 1080x2340") == (1080, 2340)
    assert D.parse_wm_size("Override size: 720x1280") == (720, 1280)
    assert D.parse_wm_size("garbage") == (None, None)
    print("OK  dumpsys / wm size 解析（含空输入）")


def t_behavior_task_text():
    assert D.behavior_task_text(["sign", "watch"]) == "签到，然后看视频"
    assert D.behavior_task_text([]) == "签到"
    assert D.behavior_task_text(["unknown_x"]) == "unknown_x"
    print("OK  行为 -> 自然语言任务串")


# ===========================================================================
# 2. 任务层
# ===========================================================================
def t_build_app_steps_skips_empty_and_flags_money():
    steps = J.build_app_steps([
        {"name": "A", "behaviors": ["sign", "watch"]},
        {"name": "B", "behaviors": []},                  # 必须跳过，不能退化成默认签到
        {"name": "", "behaviors": ["sign"]},             # 无名，跳过
        {"name": "C", "behaviors": ["withdraw"]},
    ], dry_run=True, force=True, serial="1.2.3.4",
       money_behaviors=["withdraw"])                     # C9 后由调用方注入，测试同步适配
    assert [s.title for s in steps] == ["A", "C"], [s.title for s in steps]
    a = steps[0].cmd
    assert "--dry-run" in a and "--force" in a and "--serial" in a, a
    assert a[a.index("--task") + 1] == "签到，然后看视频", a
    assert steps[1].meta["money"] == ["withdraw"], steps[1].meta
    assert steps[0].meta["money"] == [], steps[0].meta
    print("OK  空行为/无名跳过；--dry-run/--force/--serial 与资金标记正确")


def t_job_log_offset_semantics():
    """前端靠 offset 续读：next 之后必须返回空，不能重复也不能丢。"""
    job = J.Job("tool", "t", [])
    job.append("l1\nl2\n")
    n1, t1 = job.read_log(0)
    assert t1 == "l1\nl2\n" and n1 == 2, (n1, t1)
    job.append("l3\n")
    n2, t2 = job.read_log(n1)
    assert t2 == "l3\n", t2
    n3, t3 = job.read_log(n2)
    assert t3 == "", t3
    assert n3 == n2
    print("OK  日志增量 offset 语义（不重复、不丢失）")


def t_job_runs_and_reports_steps():
    steps = [
        J.Step("ok", [sys.executable, "-c", "print('hello')"]),
        J.Step("bad", [sys.executable, "-c", "import sys;sys.exit(2)"]),
    ]
    job = J.Job("tool", "t", steps)
    job.start()
    for _ in range(100):
        if job.finished:
            break
        time.sleep(0.05)
    assert job.state == "failed", job.state
    assert steps[0].state == "done" and steps[1].state == "failed", \
        (steps[0].state, steps[1].state)
    assert job.progress()["done"] == 2
    _, txt = job.read_log(0)
    assert "hello" in txt, txt
    print("OK  任务串行执行、逐步状态与失败传播")


def t_job_stop_kills_current_step():
    """停止必须真的终止子进程，且后续步骤不再执行。"""
    steps = [
        J.Step("sleep", [sys.executable, "-c", "import time;time.sleep(30)"]),
        J.Step("never", [sys.executable, "-c", "print('should not run')"]),
    ]
    job = J.Job("tool", "t", steps)
    job.start()
    for _ in range(100):
        if steps[0].state == "running":
            break
        time.sleep(0.05)
    job.stop()
    for _ in range(200):
        if job.finished:
            break
        time.sleep(0.05)
    assert job.finished, job.state
    assert steps[0].state == "stopped", steps[0].state
    assert steps[1].state == "stopped", steps[1].state
    _, txt = job.read_log(0)
    assert "should not run" not in txt, "停止后不应继续执行后续步骤"
    print("OK  停止真的杀掉进程且阻止后续步骤")


def t_job_manager_single_active():
    m = J.JobManager()
    j = m.create("tool", "t", [J.Step("s", [sys.executable, "-c", "import time;time.sleep(2)"])])
    j.start()
    assert m.active() is not None
    assert m.list()[0]["id"] == j.id
    m.stop_all()
    for _ in range(200):
        if j.finished:
            break
        time.sleep(0.05)
    assert m.active() is None
    print("OK  JobManager 活动任务追踪与 stop_all")


def t_tool_step_whitelist():
    st = J.build_tool_step("verify_live", ["--apps", "一淘"])
    assert st.cmd[-2:] == ["--apps", "一淘"], st.cmd
    assert "verify_live.py" in st.cmd[1], st.cmd
    try:
        J.build_tool_step("nope")
        raise AssertionError("未知工具应报错")
    except ValueError:
        pass
    ids = {t["id"] for t in J.tool_catalog()}
    assert {"preflight", "shot", "verify_live"} <= ids, ids
    print("OK  工具白名单与参数拼装")


# ===========================================================================
# 3. 服务层（起真实 HTTP 服务，只测本机接口）
# ===========================================================================
def _client(port, path, method="GET", body=None, token=None):
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("X-Auth-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            return r.status, raw, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers.get("Content-Type", "")


def _start_test_server():
    port = S.find_free_port(18800, tries=40)
    console = S.Console(D.CONFIG_YAML, D.DB_PATH)
    httpd = S.make_server("127.0.0.1", port, console)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return port, httpd, console


def t_overview_exposes_frontend_contract():
    """锁定 /api/overview 的字段契约 —— 前端读什么，后端就必须给什么。

    踩过的坑：`Store.apps()` 是**逐字段手工拼**的，新增 `vias` 后忘了往
    这里加，接口静默少一个字段，前端 `b.vias.length` 直接抛 TypeError，
    而所有后端单测照样全绿。这里按前端实际读取的字段逐一断言。
    """
    port, httpd, console = _start_test_server()
    try:
        st, raw, _ = _client(port, "/api/overview", "GET")
        assert st == 200, (st, raw)
        ov = json.loads(raw)
        for key in ("device", "app_count", "behavior_count",
                    "money_behavior_count", "apps", "issues",
                    "verify_coverage"):
            assert key in ov, f"overview 缺字段 {key}"
        assert ov["apps"], "配置里应有 App"
        beh_keys = ("id", "trigger", "money", "levels", "branches",
                    "has_prelude", "vias", "anchors")
        anc_keys = ("type", "via", "key", "text", "candidates", "images")
        for a in ov["apps"]:
            for key in ("index", "name", "package", "aliases", "behaviors"):
                assert key in a, f"{a.get('name')} 缺字段 {key}"
            for b in a["behaviors"]:
                for key in beh_keys:
                    assert key in b, f"{a['name']}.{b.get('id')} 缺字段 {key}"
                assert isinstance(b["vias"], list) and b["vias"], b
                for an in b["anchors"]:
                    for key in anc_keys:
                        assert key in an, f"{a['name']}.{b['id']} 锚点缺 {key}"
                    assert an["key"], f"{a['name']}.{b['id']} 锚点定位依据为空"
        print("OK  /api/overview 字段契约完整（含 vias / 锚点 key）")
    finally:
        httpd.shutdown()
        httpd.server_close()


def t_frontend_only_reads_fields_api_provides():
    """扫前端源码里 `b.<字段>` / `a.<字段>` 的读取点，逐个核对接口确实给了。

    这是上面那个 bug 的**反向**护栏：契约测试只保证「接口有这些字段」，
    但如果哪天前端新读一个接口没给的字段（`b.vias` 当初就是这样漏的），
    后端单测照样全绿、浏览器里直接 TypeError。所以这里从 JS 源码反推需求。
    """
    js_path = os.path.join(ROOT, "webui", "static", "app.js")
    with open(js_path, encoding="utf-8") as f:
        js = f.read()
    api_keys = {
        "b": {"id", "trigger", "money", "levels", "branches", "has_prelude",
              "vias", "anchors"},
        # a.* 里的 class/classList/dataset 是 DOM 元素，不是 App 对象
        "a": {"name", "package", "aliases", "behaviors", "class", "classList",
              "dataset"},
    }
    bad = []
    for var, allowed in api_keys.items():
        found = set(re.findall(r"\b%s\.([a-z_][a-z_0-9]*)" % var, js))
        for k in sorted(found - allowed):
            bad.append(f"{var}.{k}")
    assert not bad, "前端读取了接口未提供的字段：" + "、".join(bad)
    print("OK  前端只读接口已提供的字段（防 vias 式静默漏字段）")


def t_verifier_coverage_uses_verifier_rule():
    """覆盖率必须照 verify_live.py 的口径算（含 click_point 图像锚点）。

    verify_live.py 的 is_anchor_action 已把「带参考图的 click_point」算作锚点，
    因此图像锚点行为会进入 stability_run 的命中率分母、被真正度量。
    界面必须与它同口径，否则会把「已度量」误显示成「未度量」。
    """
    img = [{"type": "click_point", "images": ["i/a.png"]}]
    txt = [{"type": "click_first",
            "candidates": [{"type": "text", "value": "签到"}]}]
    anyof = [{"type": "any_of", "choices": [[
        {"type": "click_first", "candidates": [{"type": "text", "value": "签到"}]}]]}]
    assert D.verifier_can_check(img) is True, "图像锚点行为现在应可校验（进分母）"
    assert D.verifier_can_check(txt) is True
    assert D.verifier_can_check(anyof) is True
    # 与 verify_live.py 的 is_anchor_action 口径一致：图像锚点必须是锚点
    assert D.summarize_behavior(img)["anchors"], "GUI 侧图像锚点必须是锚点"

    cov = D.Store(D.CONFIG_YAML, D.DB_PATH).verify_coverage()
    assert cov["verifiable"] + cov["unverifiable"] == cov["total"], cov
    assert cov["total"] > 0, cov
    # 图像锚点已纳入实机验证器：不再有「仅图像锚点未度量」；配置里无纯兜底行为
    assert cov["image_only"] == 0, cov
    assert cov["unverifiable"] == 0, cov
    print(f"OK  实机覆盖率口径（{cov['verifiable']}/{cov['total']} 可校验，"
          f"图像锚点已进分母，未度量 {cov['unverifiable']}）")


def t_route_match():
    assert S._match("/api/jobs/abc", "/api/jobs/{id}") == {"id": "abc"}
    assert S._match("/api/jobs/abc/log", "/api/jobs/{id}/log") == {"id": "abc"}
    assert S._match("/api/jobs", "/api/jobs/{id}") is None
    assert S._match("/api/jobs//log", "/api/jobs/{id}/log") is None
    print("OK  路由匹配（含空段拒绝）")


def t_http_endpoints_and_auth():
    port, httpd, console = _start_test_server()
    try:
        st, raw, ct = _client(port, "/")
        assert st == 200 and b"__CONSOLE_TOKEN__" not in raw, "token 必须被替换"
        assert console.token.encode() in raw, "首页应注入真实 token"
        assert "text/html" in ct

        st, raw, _ = _client(port, "/api/health")
        assert st == 200 and json.loads(raw)["ok"] is True

        st, raw, _ = _client(port, "/api/overview")
        ov = json.loads(raw)
        assert ov["app_count"] > 0 and "apps" in ov

        # 静态资源：/static/ 前缀必须剥掉（曾拼成 static/static/ 导致 404）
        st, raw, ct = _client(port, "/static/app.css")
        assert st == 200 and b"{" not in raw[:20], (st, ct)

        # 写操作无 token -> 403
        st, raw, _ = _client(port, "/api/jobs", "POST", {"plan": []})
        assert st == 403, st

        # 路径穿越
        for p in ("/static/../webui/data.py", "/static/%2e%2e/webui/data.py"):
            st, _, _ = _client(port, p)
            assert st in (403, 404), (p, st)
        print("OK  HTTP 接口、token 注入、写操作鉴权、静态前缀与路径穿越")
    finally:
        httpd.shutdown()
        httpd.server_close()


def t_money_behavior_requires_confirmation():
    """资金类行为：服务端必须强制二次确认（不能只靠前端弹窗）。"""
    port, httpd, console = _start_test_server()
    try:
        tok = console.token
        # 找一个含 withdraw 的真实 App
        target = next((a for a in console.store.apps()
                       if any(b["money"] for b in a["behaviors"])), None)
        assert target is not None, "配置里应存在资金类行为"
        body = {"plan": [{"name": target["name"], "behaviors": ["withdraw"]}]}

        st, raw, _ = _client(port, "/api/jobs", "POST", body, token=tok)
        assert st == 403, st
        assert "资金" in json.loads(raw)["error"], raw

        # 带 confirm_money 才放行（用 dry_run 避免真操作设备）
        body2 = dict(body, confirm_money=True, dry_run=True)
        st, raw, _ = _client(port, "/api/jobs", "POST", body2, token=tok)
        assert st == 200, (st, raw)
        jid = json.loads(raw)["job"]["id"]
        assert json.loads(raw)["job"]["meta"]["money_apps"] == [target["name"]]
        _client(port, f"/api/jobs/{jid}/stop", "POST", {}, token=tok)
        print(f"OK  资金类行为强制二次确认（{target['name']}）")
    finally:
        httpd.shutdown()
        httpd.server_close()


def t_job_validation_rejects_bad_input():
    port, httpd, console = _start_test_server()
    try:
        tok = console.token
        cases = [
            ({"plan": [{"name": "不存在的App", "behaviors": ["sign"]}]}, "不存在"),
            ({"plan": [{"name": "一淘", "behaviors": ["不存在的行为"]}]}, "未配置行为"),
            ({"plan": []}, "没有可执行"),
            ({"plan": [{"name": "一淘", "behaviors": []}]}, "没有可执行"),
            # 键名写错（如把 plan 写成 apps）时，必须直说「缺字段」并回显收到的
            # 字段名 —— 否则会落到「没有可执行」那句上，让人以为是勾选问题。
            ({"apps": [{"name": "一淘", "behaviors": ["sign"]}]},
             "缺少 plan 字段"),
        ]
        for body, expect in cases:
            st, raw, _ = _client(port, "/api/jobs", "POST", body, token=tok)
            assert st == 400, (body, st)
            assert expect in json.loads(raw)["error"], (body, raw)
        st, raw, _ = _client(port, "/api/jobs", "POST",
                             {"plan": [{"name": "一淘", "behaviors": ["sign"]}],
                              "dry_run": True}, token=tok)
        assert st == 200, (st, raw)
        jid = json.loads(raw)["job"]["id"]
        # 已有任务运行时不得再起一个（设备是独占资源）
        st, raw, _ = _client(port, "/api/jobs", "POST",
                             {"plan": [{"name": "一淘", "behaviors": ["sign"]}],
                              "dry_run": True}, token=tok)
        assert st == 409, (st, raw)
        _client(port, f"/api/jobs/{jid}/stop", "POST", {}, token=tok)
        print("OK  任务参数校验（未知 App / 未知行为 / 空计划 / 缺 plan 字段 / 并发冲突）")
    finally:
        httpd.shutdown()
        httpd.server_close()


def t_css_scroll_containers_disable_flex_shrink():
    """滚动容器：flex 纵向 + max-height 的容器，子项必须禁掉收缩。

    踩过的坑（真实且极难排查）：`.applist` 是 `display:flex;flex-direction:column`
    且有 `max-height`，34 个 App 子项默认 `flex-shrink:1` 被**压扁**到 ~19px，
    再被 `overflow:hidden` 裁掉文字 —— 表现为「DOM 里内容完整、界面上是一片空条」。
    导出 DOM 完全看不出来，只有真正渲染出来才发现。
    """
    css_path = os.path.join(ROOT, "webui", "static", "app.css")
    with open(css_path, encoding="utf-8") as f:
        css = f.read()
    rules = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        # 去掉注释与换行，得到「选择器列表 + 紧凑声明」
        sel = re.sub(r"/\*.*?\*/", "", sel, flags=re.S)
        sel = " ".join(sel.split())
        rules.append((sel, body.replace(" ", "")))

    def shrink_guard_for(container):
        """容器或其 `> *` 子项选择器上是否有禁收缩声明。"""
        base = container.split(",")[0].strip()
        for sel, body in rules:
            if not ("flex:00auto" in body or "flex-shrink:0" in body
                    or "flex:none" in body):
                continue
            for one in sel.split(","):
                one = one.strip()
                if one.startswith(base) and (">" in one or one == base):
                    return True
        return False

    offenders = []
    for sel, body in rules:
        if "display:flex" in body and "flex-direction:column" in body \
                and "max-height" in body:
            for one in sel.split(","):
                one = one.strip()
                if one and not shrink_guard_for(one):
                    offenders.append(one)
    assert not offenders, (
        "以下滚动容器未禁掉子项收缩，内容会被压扁裁掉：" + "、".join(offenders))
    print("OK  CSS 滚动容器均已禁掉 flex 收缩（防「空条」回归）")


def t_http_stop_really_stops():
    """通过 HTTP 停止任务：必须真的结束，而不是一直 running。"""
    port, httpd, console = _start_test_server()
    try:
        tok = console.token
        job = console.jobs.create("tool", "长任务", [
            J.Step("sleep", [sys.executable, "-c", "import time;time.sleep(60)"]),
            J.Step("never", [sys.executable, "-c", "print('MUST-NOT-RUN')"]),
        ])
        job.start()
        for _ in range(60):
            if job.steps[0].state == "running":
                break
            time.sleep(0.05)
        st, raw, _ = _client(port, f"/api/jobs/{job.id}/stop", "POST", {}, token=tok)
        assert st == 200, (st, raw)
        for _ in range(200):
            if job.finished:
                break
            time.sleep(0.05)
        assert job.finished, f"停止后仍是 {job.state}"
        _, txt = job.read_log(0)
        assert "MUST-NOT-RUN" not in txt, "停止后不应继续执行后续步骤"
        print("OK  HTTP 停止任务真正生效（不依赖子进程输出）")
    finally:
        httpd.shutdown()
        httpd.server_close()


# ===========================================================================
# 5. 校准 / 稳定性（devtools/calib 的产物）
# ===========================================================================
def t_stability_report_matches_stability_run():
    """校准页的数字必须与命令行 stability_run **逐项一致**。

    这是本项目踩过的「静默不一致」类型的护栏：如果 GUI 自己另写一份
    命中/作废判定，两套口径会慢慢分叉 —— 界面显示 70.5%、命令行显示别的数，
    而两边单测都是绿的（因为各自都自洽）。所以这里拿 stability_run 的
    分类函数把同一份文件重算一遍做对照。
    """
    sys.path.insert(0, os.path.join(ROOT, "devtools"))
    import stability_run as SR
    if not os.path.exists(D.STABILITY_JSON):
        print("SKIP 无 STABILITY.json（未跑过稳定性统计）")
        return
    rep = D.load_stability(D.STABILITY_JSON)
    with open(D.STABILITY_JSON, encoding="utf-8") as f:
        raw = json.load(f)

    stable, flaky, never = SR.classify(raw["per_behavior"])
    assert rep["counts"]["stable"] == len(stable), rep["counts"]
    assert rep["counts"]["flaky"] == len(flaky), rep["counts"]
    assert rep["counts"]["never"] == len(never), rep["counts"]
    assert rep["counts"]["behaviors"] == len(raw["per_behavior"])
    assert rep["rounds"] == raw["rounds"]

    # 逐行用 statuses 重算，顺带校验报告文件自身没写错
    for row in rep["behaviors"]:
        valid = [s for s in row["statuses"] if not SR.is_void(s)]
        hits = sum(1 for s in valid if SR.is_hit(s))
        assert row["valid"] == len(valid), row
        assert row["hits"] == hits, row
        assert row["kind"] == D._kind_of(row["valid"], row["hits"]), row
    assert rep["total"]["hits"] == sum(r["hits"] for r in rep["behaviors"])
    assert rep["total"]["valid"] == sum(r["valid"] for r in rep["behaviors"])
    assert rep["counts"]["unmeasured"] == sum(
        1 for r in rep["behaviors"] if not r["valid"])
    print(f"OK  校准报告与 stability_run 口径一致"
          f"（{rep['total']['hits']}/{rep['total']['valid']}）")


def t_stability_kind_classification():
    """逐行为三分类的边界：未度量 / 稳定 / 波动 / 从未命中。"""
    assert D._kind_of(0, 0) == "未度量", "valid=0 是「未度量」，不是「从未命中」"
    assert D._kind_of(3, 3) == "稳定"
    assert D._kind_of(3, 0) == "从未命中"
    assert D._kind_of(3, 1) == "波动"
    assert D._kind_of(3, 2) == "波动"
    print("OK  逐行为三分类边界正确（未度量/稳定/波动/从未命中）")


def t_stability_chain_orders_stages():
    """版本对比链必须按**声明的阶段序**排，不能靠文件名排序。"""
    chain = D.stability_chain()
    if not chain:
        print("SKIP 无版本备份")
        return
    assert sum(1 for x in chain if x["current"]) <= 1, "最多一个「当前」"
    known = [x["stage"] for x in chain if x["stage"] in D.STAGE_ORDER]
    expect = [s for s in D.STAGE_ORDER if s in known]
    assert known == expect, f"阶段序不对：{known} != {expect}"
    for x in chain:
        assert x["valid"] >= 0 and x["stable"] + x["flaky"] + x["never"] >= 0
        assert x["rate"] is None or 0.0 <= x["rate"] <= 1.0, x
    print(f"OK  版本对比链按阶段序排列（{len(chain)} 个版本）")


def t_stability_missing_file_degrades():
    """报告缺失时必须降级成「一句可操作的提示」，不能让整页 500。"""
    store = D.Store(config_path=D.CONFIG_YAML, db_path=D.DB_PATH)
    orig = D.STABILITY_JSON
    try:
        D.STABILITY_JSON = os.path.join(D.CALIB_DIR, "__nope__.json")
        r = store.stability()
        assert r["available"] is False, r
        assert r.get("hint"), "降级时必须给出提示，否则用户不知道下一步做什么"
    finally:
        D.STABILITY_JSON = orig
    assert store.stability()["available"] is True, "恢复路径后应能正常读到"
    print("OK  报告缺失时优雅降级（不抛异常、给出可操作提示）")


def t_calib_endpoint_exposes_frontend_contract():
    """锁定 /api/calib 的字段契约。"""
    port, httpd, console = _start_test_server()
    try:
        st, raw, _ = _client(port, "/api/calib", "GET")
        assert st == 200, (st, raw)
        cb = json.loads(raw)
        for key in ("available", "chain", "verify_coverage"):
            assert key in cb, f"/api/calib 缺字段 {key}"
        assert isinstance(cb["chain"], list), cb["chain"]
        assert "verifiable" in cb["verify_coverage"], cb["verify_coverage"]
        if not cb["available"]:
            assert cb.get("hint"), "不可用时必须给 hint"
            print("OK  /api/calib 契约完整（当前无报告，走降级分支）")
            return
        for key in ("rounds", "total", "counts", "behaviors"):
            assert key in cb, f"/api/calib 缺字段 {key}"
        for key in ("hits", "valid", "void", "rate"):
            assert key in cb["total"], f"total 缺 {key}"
        for key in ("stable", "flaky", "never", "behaviors", "unmeasured"):
            assert key in cb["counts"], f"counts 缺 {key}"
        row_keys = ("app", "behavior", "statuses", "valid", "void",
                    "hits", "rate", "kind")
        assert cb["behaviors"], "报告里应有行为行"
        for r in cb["behaviors"]:
            for key in row_keys:
                assert key in r, f"行为行缺 {key}"
            assert r["kind"] in ("稳定", "波动", "从未命中", "未度量"), r
        for x in cb["chain"]:
            for key in ("stage", "label", "current", "mtime", "rate",
                        "hits", "valid", "stable", "flaky", "never"):
                assert key in x, f"版本项缺 {key}"
        print(f"OK  /api/calib 字段契约完整（{len(cb['behaviors'])} 行 / "
              f"{len(cb['chain'])} 个版本）")
    finally:
        httpd.shutdown()
        httpd.server_close()


def t_calib_frontend_only_reads_fields_api_provides():
    """校准页的前端字段护栏（`cb.` 前缀）。

    通用护栏只扫 `b.`/`a.`（App / 行为对象）；`c.` 在总览卡片里被复用成
    「卡片对象」，没法区分。所以校准页刻意把变量命名为 `cb.`，这里单独护栏。

    `assert found` 不是多余的：如果哪天变量被改名，扫不到读取点，
    这道护栏会**静默失效**，比没有护栏更危险。
    """
    js_path = os.path.join(ROOT, "webui", "static", "app.js")
    with open(js_path, encoding="utf-8") as f:
        js = f.read()
    # hint 只在降级分支下发；available/chain/verify_coverage 恒在；
    # 其余四项仅 available=True 时下发。
    allowed = {"available", "hint", "rounds", "total", "counts",
               "behaviors", "chain", "verify_coverage"}
    found = set(re.findall(r"\bcb\.([a-z_][a-z_0-9]*)", js))
    assert found, "没扫到任何 cb.* 读取点 —— 护栏已失效（变量被改名？）"
    bad = sorted(found - allowed)
    assert not bad, "校准页读取了接口未提供的字段：" + "、".join(bad)
    print(f"OK  校准页只读接口已提供字段（{len(found)} 个）")


def t_job_history_exposes_fields_frontend_reads():
    """任务历史列表的字段契约。

    前端靠 `jobs[0]` 当「最近一次」、靠 `j.id/j.state/j.title` 渲染历史条、
    靠 `active` 决定是否跟随轮询。三者任一缺失都会让历史条变空白。
    """
    port, httpd, console = _start_test_server()
    try:
        for t in ("历史甲", "历史乙"):
            console.jobs.create("tool", t, [
                J.Step("noop", [sys.executable, "-c", "print(1)"])])
        st, raw, _ = _client(port, "/api/jobs", "GET")
        assert st == 200, (st, raw)
        d = json.loads(raw)
        assert "jobs" in d and isinstance(d["jobs"], list), d
        assert "active" in d, "缺少 active 字段（前端靠它决定是否跟随）"
        for x in d["jobs"]:
            for key in ("id", "state", "title"):
                assert key in x, f"任务项缺 {key}"
            assert x["state"] in ("pending", "running", "done", "failed",
                                  "stopped"), x
        # 最新在最前 —— 前端直接取 jobs[0]
        assert d["jobs"][0]["title"] == "历史乙", [x["title"] for x in d["jobs"]]
        print("OK  /api/jobs 历史列表字段契约完整（最新在前）")
    finally:
        httpd.shutdown()
        httpd.server_close()


def t_calib_diagnose_deeplink_wiring():
    """校准页「诊断 →」深链的三段接线必须同时在位。

    这条链横跨两个文件、四个约定：前端 `data-diag` → `S.toolPrefill.id`
    → 工具输入框的 `data-arg` → 后端 `tool_catalog()` 里的工具 id。
    任何一段被改名都会**静默失效**：按钮还在、点了没反应，
    而且前后端单测都照样绿。所以这里把四段都静态断言一遍。
    """
    js = open(os.path.join(ROOT, "webui", "static", "app.js"),
              encoding="utf-8").read()
    ids = {t["id"] for t in J.tool_catalog()}
    assert "verify_live" in ids, f"工具目录里没有 verify_live：{sorted(ids)}"
    for needle in ("data-diag", "gotoDiagnose", "toolPrefill", "data-arg="):
        assert needle in js, f"前端缺少深链接线片段：{needle}"
    m = re.search(r"toolPrefill\s*=\s*\{\s*id:\s*'([^']+)'", js)
    assert m, "没找到 gotoDiagnose 里设置的 toolPrefill.id"
    assert m.group(1) in ids, f"深链指向了不存在的工具：{m.group(1)}"
    print(f"OK  校准→诊断深链四段接线完整（目标工具 {m.group(1)}）")


def t_job_title_distinguishes_apps():
    """任务标题必须带 App 名 —— 任务历史列表靠它区分条目。

    实测踩过：标题原本是「预览 1 个 App」，历史里三条一模一样，
    根本认不出哪条是哪个 App，新加的历史列表等于白给。
    用 dry-run 建任务（不碰设备），断言完立即停掉。
    """
    port, httpd, console = _start_test_server()
    try:
        job = console.create_app_job({
            "plan": [{"name": "京东", "behaviors": ["sign"]},
                     {"name": "河马剧场", "behaviors": ["watch"]}],
            "dry_run": True,
        })
        title = job.title
        assert "京东" in title and "河马剧场" in title, title
        assert "2 个 App" not in title, f"标题退回成「N 个 App」了：{title}"
        print(f"OK  任务标题含 App 名（历史条目可区分）：{title}")
    finally:
        console.jobs.stop_all()
        httpd.shutdown()
        httpd.server_close()


def _find_node():
    for c in (shutil.which("node"),
              os.path.expanduser("~/.workbuddy-ai/binaries/node/versions/"
                                 "22.22.2-2/node.exe")):
        if c and os.path.exists(c):
            return c
    return None


def t_ops_event_humanizer_translates_action_json():
    """`humanEvent` 必须把动作 JSON 翻成人话 —— **包括带列表前缀的那种**。

    实测踩过：日志里的计划 dump 长这样 `- {"type":"wait","seconds":3}`，
    最初只判断「首字符是不是 {」，于是带 `- ` 前缀的行原样透出，
    总览的「最近事件」照样是一屏裸 JSON（改完还是没效果）。

    这是纯 JS 函数，用 Node 真跑一遍再断言 —— 光看源码看不出结果对不对。
    """
    node = _find_node()
    if not node:
        print("SKIP 未找到 node，跳过 JS 纯函数校验")
        return
    js = open(os.path.join(ROOT, "webui", "static", "app.js"),
              encoding="utf-8").read()
    m = re.search(r"const ACTION_LABEL = \{.*?\n\};", js, re.S)
    assert m, "app.js 里没找到 ACTION_LABEL 定义"
    label_def = m.group(0)
    m = re.search(r"function humanEvent\(ev\) \{.*?\n\}", js, re.S)
    assert m, "app.js 里没找到 humanEvent 定义"
    fn_def = m.group(0)

    cases = [
        # 输入, 期望包含的子串（None = 只要求别原样透出 JSON）
        ('- {"type":"wait","seconds":3}', "等待 3s"),
        ('{"type":"think"}', "停顿"),
        ('- {"type":"click_id","res_id":"com.x:id/close"}', "点控件 com.x:id/close"),
        # P1-1：分支数字段名以生产端为准 —— behavior_runner._step_any_of 读的
        # 是 act["choices"]（缺失还会 WARN「any_of 动作缺少 choices」），全仓
        # 无任何代码产出 action 级 `branches`。原用例喂 `branches`，恰好把
        # app.js 的字段名错读（o.branches 恒 undefined -> 分支 0 路）掩盖住。
        ('{"type":"any_of","choices":[{},{}]}', "分支 2 路"),
        ('- {"type":"click_first","candidates":[{"value":"福利"},{"value":"金币"}]}',
         "点首个命中 [福利/金币]"),
        ('- {"type":"reward","pattern":"\\\\|¥?([Pp]\\\\d+)"}', "读收益 匹配"),
        ("蛋花[watch](看视频) -> 行为[watch]", "蛋花[watch](看视频) -> 行为[watch]"),
    ]
    script = (label_def + "\n" + fn_def + "\n"
              + "const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
              + "const bad = [];\n"
              + "for (const [inp, want] of cases) {\n"
              + "  const got = humanEvent(inp);\n"
              + "  if (!got.includes(want) || /^[\\s\\-*\\u2022]*[[{]/.test(got))\n"
              + "    bad.push([inp, want, got]);\n"
              + "}\n"
              + "console.log(JSON.stringify(bad));\n")
    # 传参方式说明（Windows 实机坑，都踩过）：
    # 1) `node -e "多行脚本"` 会被 CreateProcess -> CommandLineToArgvW 把参数里的
    #    真实换行当空白分隔符拆 argv，node 只取 argv[1] -> 多行脚本被截断成首行；
    # 2) 压成单行后源码里的 `//` 注释会吞到行尾，把后续代码全注释掉；
    # 3) 用 argv 传 payload 时，参数一长（>~500 字符）node v26 在 Windows 上
    #    会启动期报 "The system cannot find the path specified."（命令行解析错乱）。
    # 所以：脚本写临时 .js 文件（保留原始换行/注释），payload 走 stdin（readFileSync(0)），
    # 完全绕开 Windows 命令行传参，任何长度/中文都稳。
    import tempfile
    fd, js_path = tempfile.mkstemp(suffix=".js", prefix="human_event_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(script)
        p = subprocess.run(
            [node, js_path],
            input=json.dumps(cases, ensure_ascii=True).encode("utf-8"),
            capture_output=True, timeout=60)
    finally:
        os.unlink(js_path)
    if p.returncode != 0:
        try:
            err_txt = p.stderr.decode("utf-8")
        except UnicodeDecodeError:
            err_txt = p.stderr.decode("gbk", errors="replace")
        assert False, f"node 执行失败：{err_txt[:400]}"
    bad = json.loads(p.stdout.decode("utf-8").strip() or "[]")
    assert not bad, "动作 JSON 未被翻译成人话：" + "；".join(
        f"{i!r} -> {g!r}（期望含 {w!r}）" for i, w, g in bad)
    print(f"OK  动作 JSON 翻译成人话（{len(cases)} 个用例，含 `- ` 前缀）")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
