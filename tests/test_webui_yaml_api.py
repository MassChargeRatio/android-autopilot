# -*- coding: utf-8 -*-
"""test_webui_yaml_api.py - WebUI YAML API（AUTOP-WEBUI-YAML-2026-10-22）

marvis A 卡会话 failed 零产物，由 Host 接手实现并补测试。
覆盖 6 路由 + 四道闸（YAML 可解析 / eol 保真 / 写后 verify / 自动回滚）+ 资金红线 + 词表门禁。

运行：
    ./.venv/Scripts/python.exe -m pytest tests/test_webui_yaml_api.py -q
"""
import ast
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from devtools import yaml_writer  # noqa: E402
from webui import routes_yaml  # noqa: E402

LF = """name: A
package: com.example.a
behaviors:
  collect:
  - type: click_point
    x: 0.5
    y: 0.5
    timeout: 6
    optional: true
    desc: 图像-收集
"""
CRLF = LF.replace("\n", "\r\n")


class _Handler:
    """假 Handler：只记录 _json/_err，测试直接看返回值。"""

    def _json(self, obj, code=200):
        return code, obj

    def _err(self, code, msg):
        return code, {"ok": False, "error": msg}


def _mk(tmp, extra="name: B\npackage: com.example.b\nbehaviors:\n  sign:\n  - type: think\n"):
    apps = os.path.join(tmp, "config", "apps")
    os.makedirs(apps, exist_ok=True)
    with open(os.path.join(apps, "01_A.yaml"), "w", encoding="utf-8", newline="") as f:
        f.write(LF)
    if extra:
        with open(os.path.join(apps, "02_B.yaml"), "w", encoding="utf-8") as f:
            f.write(extra)
    bak = os.path.join(tmp, "_backup_pre_fix")
    os.makedirs(bak, exist_ok=True)
    old_apps, old_bak = routes_yaml.APPS_DIR, yaml_writer.BACKUP_DIR
    routes_yaml.APPS_DIR = apps
    yaml_writer.BACKUP_DIR = bak
    return apps, old_apps, old_bak


def _restore(old_apps, old_bak):
    routes_yaml.APPS_DIR = old_apps
    yaml_writer.BACKUP_DIR = old_bak


def test_apps_lists_all():
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            code, body = routes_yaml.YamlRoutes(_Handler()).handle_get("/api/yaml/apps", {})
            assert code == 200 and body["ok"], body
            names = [a["name"] for a in body["apps"]]
            assert names == ["A", "B"], names
            assert body["apps"][1]["behaviors"] == ["sign"]
            assert all({"name", "file", "size", "mtime"} <= set(a) for a in body["apps"])
        finally:
            _restore(oa, ob)
    print("OK  GET /api/yaml/apps 列出全部 App 与 behaviors")


def test_app_text_returns_raw_and_eol():
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_get("/api/yaml/app", {"name": ["A"]})
            assert code == 200 and body["eol"] == "\n", body
            assert body["text"] == LF
            # CRLF 文件
            p = os.path.join(apps, "03_C.yaml")
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(CRLF.replace("name: A", "name: C", 1))
            code, body = r.handle_get("/api/yaml/app", {"name": ["C"]})
            assert body["eol"] == "\r\n", body
        finally:
            _restore(oa, ob)
    print("OK  GET /api/yaml/app 返回原文 + eol（LF/CRLF 均可辨）")


def test_unknown_app_and_bad_name():
    with tempfile.TemporaryDirectory() as tmp:
        _apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_get("/api/yaml/app", {"name": ["不存在"]})
            assert code == 404, (code, body)
            code, body = r.handle_get("/api/yaml/app", {"name": ["../etc"]})
            assert code == 404 and "非法" in body["error"], (code, body)
        finally:
            _restore(oa, ob)
    print("OK  未知/非法 app 名返回 404")


def test_fragment_renders_behavior():
    with tempfile.TemporaryDirectory() as tmp:
        _apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_get("/api/yaml/fragment",
                                      {"name": ["A"], "behavior": ["collect"]})
            assert code == 200, body
            assert "collect:" in body["fragment"] and "- type: click_point" in body["fragment"]
            code, body = r.handle_get("/api/yaml/fragment",
                                      {"name": ["A"], "behavior": ["sign"]})
            assert code == 404, body
        finally:
            _restore(oa, ob)
    print("OK  GET /api/yaml/fragment 渲染指定行为")


def test_save_valid_and_unchanged():
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_post("/api/yaml/app", {"name": "A", "text": LF})
            assert body["action"] == "unchanged", body
            new = LF.replace("desc: 图像-收集", "desc: 改过的描述")
            code, body = r.handle_post("/api/yaml/app", {"name": "A", "text": new})
            assert body["action"] == "saved" and body["backup"], body
            assert os.path.exists(body["backup"])
            assert yaml.safe_load(open(os.path.join(apps, "01_A.yaml"), encoding="utf-8")
                                  )["behaviors"]["collect"][0]["desc"] == "改过的描述"
            code, body = r.handle_post("/api/yaml/app", {"name": "A", "text": new})
            assert body["action"] == "unchanged", body
        finally:
            _restore(oa, ob)
    print("OK  保存：unchanged / saved / 备份落盘 / 二次保存 unchanged")


def test_save_rejects_bad_yaml_without_touching_file():
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            before = open(os.path.join(apps, "01_A.yaml"), "rb").read()
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_post("/api/yaml/app",
                                       {"name": "A", "text": "name: [unclosed"})
            assert code == 400 and "解析失败" in body["error"], (code, body)
            assert open(os.path.join(apps, "01_A.yaml"), "rb").read() == before
        finally:
            _restore(oa, ob)
    print("OK  非法 YAML 400 且文件未动")


def test_save_preserves_crlf_and_untouched_lines():
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            p = os.path.join(apps, "01_A.yaml")
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(CRLF)
            raw_before = open(p, "rb").read()
            r = routes_yaml.YamlRoutes(_Handler())
            # 浏览器 textarea 会把 CRLF 归一成 LF —— 服务端必须按原 eol 写回
            sent = CRLF.replace("\r\n", "\n").replace("desc: 图像-收集", "desc: 改过")
            code, body = r.handle_post("/api/yaml/app", {"name": "A", "text": sent})
            assert body["action"] == "saved", body
            raw_after = open(p, "rb").read()
            assert b"\r\n" in raw_after, "CRLF 未被保持"
            assert raw_after.count(b"\n") == raw_after.count(b"\r\n")
            for ln in raw_before.split(b"\r\n"):
                if ln.strip() and "图像-收集".encode("utf-8") not in ln:
                    assert ln in raw_after, f"原行被改写: {ln!r}"
            assert "改过".encode("utf-8") in raw_after
        finally:
            _restore(oa, ob)
    print("OK  eol 保真：CRLF 文件保存后仍 CRLF，原行字节不变")


def test_save_rolls_back_on_collateral_damage():
    """写后 verify 发现误伤其他 App -> rolled_back 且文件恢复。"""
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            p = os.path.join(apps, "01_A.yaml")
            original = open(p, "rb").read()
            r = routes_yaml.YamlRoutes(_Handler())
            real_verify = r._verify
            r._verify = lambda path, before: (False, ["模拟误伤"])
            code, body = r.handle_post("/api/yaml/app",
                                       {"name": "A", "text": LF.replace("x: 0.5", "x: 0.6")})
            assert body["action"] == "rolled_back", body
            assert open(p, "rb").read() == original, "回滚后文件未恢复"
            r._verify = real_verify
        finally:
            _restore(oa, ob)
    print("OK  复验失败自动回滚，文件字节恢复")


def _points(actions):
    """递归收集所有 click_point（它们嵌在 any_of.choices 里）。"""
    out = []
    for a in actions or []:
        if not isinstance(a, dict):
            continue
        if a.get("type") == "click_point":
            out.append(a)
        for ch in a.get("choices") or []:
            out.extend(_points(ch))
    return out


def test_generate_maps_coord_params():
    with tempfile.TemporaryDirectory() as tmp:
        _apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_post("/api/yaml/generate", {
                "name": "A", "behavior": "sign", "entry": "home_direct",
                "text": "点底部福利tab，点连续签到卡",
                "anchor_text": "福利", "anchor_xy": "0.5,0.927", "xy": "0.398,0.372",
            })
            assert code == 200, body
            assert body["entry"] == "home_direct", body["entry"]
            acts = body["actions"]
            assert acts and acts[0]["type"] == "any_of"
            pts = _points(acts)
            assert any(abs(p["x"] - 0.5) < 1e-6 and abs(p["y"] - 0.927) < 1e-6
                       for p in pts), pts
            assert any(abs(p["x"] - 0.398) < 1e-6 for p in pts), pts
            assert "candidates_used" in body and body["fragment"]
        finally:
            _restore(oa, ob)
    print("OK  generate：坐标字段映射进 actions，返回 fragment/candidates_used")


def test_generate_money_redline():
    with tempfile.TemporaryDirectory() as tmp:
        _apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_post("/api/yaml/generate", {
                "name": "A", "behavior": "withdraw", "text": "去提现"})
            assert code == 400 and "资金类" in body["error"], (code, body)
            code, body = r.handle_post("/api/yaml/generate", {
                "name": "A", "behavior": "withdraw", "text": "去提现",
                "allow_money": True})
            assert code == 200, body
        finally:
            _restore(oa, ob)
    print("OK  资金红线：withdraw 默认拒绝，allow_money 放行")


def test_apply_insert_then_skip_then_force():
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, gen = r.handle_post("/api/yaml/generate", {
                "name": "A", "behavior": "sign", "entry": "home_direct",
                "text": "点福利tab，点签到", "anchor_text": "福利",
                "anchor_xy": "0.5,0.927", "xy": "0.398,0.372"})
            actions = gen["actions"]
            code, body = r.handle_post("/api/yaml/apply",
                                       {"name": "A", "behavior": "sign", "actions": actions})
            assert body["action"] == "inserted", body
            data = yaml_writer.load_app(os.path.join(apps, "01_A.yaml"))
            assert data["behaviors"]["sign"] == actions
            code, body = r.handle_post("/api/yaml/apply",
                                       {"name": "A", "behavior": "sign", "actions": actions})
            assert body["action"] == "skipped", body
            # 换一组坐标再 force，才是真正的 replaced（相同内容按设计幂等 skip）
            code, gen2 = r.handle_post("/api/yaml/generate", {
                "name": "A", "behavior": "sign", "entry": "home_direct",
                "text": "点福利tab，点签到", "anchor_text": "福利",
                "anchor_xy": "0.5,0.927", "xy": "0.4,0.38"})
            code, body = r.handle_post("/api/yaml/apply",
                                       {"name": "A", "behavior": "sign",
                                        "actions": gen2["actions"], "force": True})
            assert body["action"] == "replaced", body
            data = yaml_writer.load_app(os.path.join(apps, "01_A.yaml"))
            assert data["behaviors"]["sign"] == gen2["actions"]
        finally:
            _restore(oa, ob)
    print("OK  apply：inserted → skipped → force 后 replaced")


def test_apply_by_text_only():
    with tempfile.TemporaryDirectory() as tmp:
        apps, oa, ob = _mk(tmp)
        try:
            r = routes_yaml.YamlRoutes(_Handler())
            code, body = r.handle_post("/api/yaml/apply", {
                "name": "A", "behavior": "sign", "entry": "home_direct",
                "text": "点福利tab，点签到", "anchor_text": "福利",
                "anchor_xy": "0.5,0.927", "xy": "0.398,0.372"})
            assert code == 200 and body["action"] == "inserted", body
            assert "sign" in (yaml_writer.load_app(
                os.path.join(apps, "01_A.yaml")).get("behaviors") or {})
        finally:
            _restore(oa, ob)
    print("OK  apply 只传 text 也能生成并写入")


def test_non_owned_paths_return_none():
    r = routes_yaml.YamlRoutes(_Handler())
    assert r.handle_get("/api/health", {}) is None
    assert r.handle_get("/api/yaml/unknown", {}) is None
    assert r.handle_post("/api/jobs", {}) is None
    print("OK  非本模块路径返回 None（不影响原有分派）")


def test_vocab_gate_ast():
    src = open(os.path.join(ROOT, "webui", "routes_yaml.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    lits = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    hits = [(i, w) for i, s in enumerate(lits) for w in
            ("今日签到", "立即签到", "任务中心", "连续签到", "签到领金币") if w in s]
    assert not hits, f"词表被复制进代码字面量: {hits[:3]}"
    print("OK  词表门禁：routes_yaml.py 字符串字面量无签到词表")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} 通过")
    sys.exit(1 if failed else 0)
