# -*- coding: utf-8 -*-
"""test_yaml_editor_static.py - 前端静态契约（AUTOP-WEBUI-YAML-2026-10-22）

marvis B 卡会话 failed 零产物，由 Host 接手实现并补测试。
不起服务，只做静态检查：文件存在、元素 ID 齐全、token 用法正确、端点齐全、无 CRLF 转换。

运行：
    ./.venv/Scripts/python.exe -m pytest tests/test_yaml_editor_static.py -q
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "webui", "static")

REQUIRED_IDS = ["yStatus", "yAppFilter", "yAppList", "yBehavior", "ySave",
                "yReload", "yEditor", "yMsg", "yNlText", "yGen", "yApply",
                "yNlOut", "yForce"]
# 前端实际调用的 4 个；/api/yaml/fragment 由后端提供（按需查看单行为块），
# 编辑器走「整文件载入」所以前端不调它。
ENDPOINTS = ["/api/yaml/apps", "/api/yaml/app", "/api/yaml/generate",
             "/api/yaml/apply"]
BACKEND_ONLY = ["/api/yaml/fragment"]


def _read(name):
    with open(os.path.join(STATIC, name), encoding="utf-8") as f:
        return f.read()


def test_files_exist_and_nonempty():
    for name in ("yaml.html", "yaml_editor.js", "yaml_editor.css"):
        p = os.path.join(STATIC, name)
        assert os.path.isfile(p), f"缺少 {name}"
        assert os.path.getsize(p) > 200, f"{name} 内容过少（疑似占位）"
    print("OK  三个前端文件存在且非占位")


def test_html_has_required_ids():
    html = _read("yaml.html")
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in html]
    assert not missing, f"yaml.html 缺少元素 ID: {missing}"
    assert 'href="/static/yaml_editor.css"' in html
    assert 'src="/static/yaml_editor.js"' in html
    assert "__CONSOLE_TOKEN__" in html, "yaml.html 必须保留 token 占位"
    print("OK  yaml.html 含全部元素 ID / 引入 css+js / 保留 token 占位")


def test_js_reads_token_from_meta():
    js = _read("yaml_editor.js")
    assert 'meta[name="console-token"]' in js, "必须从 meta 读 token"
    assert "X-Auth-Token" in js, "POST 必须带 X-Auth-Token"
    # 每个 POST fetch 都要经过 api()，而 api() 统一带 token 头
    posts = re.findall(r"method:\s*'POST'", js)
    assert len(posts) >= 3, f"POST 调用点过少: {len(posts)}"
    assert "const TOKEN =" in js, "token 需为模块级常量"
    print("OK  token 从 meta 读取，POST 统一带 X-Auth-Token")


def test_js_covers_all_endpoints():
    js = _read("yaml_editor.js")
    missing = [e for e in ENDPOINTS if e not in js]
    assert not missing, f"yaml_editor.js 未覆盖端点: {missing}"
    assert "/api/yaml/fragment" in open(
        os.path.join(ROOT, "webui", "routes_yaml.py"), encoding="utf-8").read(), \
        "后端应保留 fragment 端点"
    print("OK  前端覆盖 4 个端点；fragment 由后端保留")


def test_js_has_no_hardcoded_token():
    js = _read("yaml_editor.js")
    assert not re.search(r"TOKEN\s*=\s*['\"][0-9a-zA-Z]{8,}['\"]", js), "疑似写死 token"
    print("OK  无写死 token")


def test_js_does_not_convert_newlines():
    js = _read("yaml_editor.js")
    assert not re.search(r"replace\(/\\r\\n/g", js), "前端不应做 CRLF 转换（服务端负责 eol 保真）"
    assert not re.search(r"split\(['\"]\\\\n", js), "前端不应自行拆行"
    print("OK  前端不做换行转换")


def test_css_uses_variables_and_media_query():
    css = _read("yaml_editor.css")
    assert len(re.findall(r"var\(--", css)) >= 3, "应引用 app.css 的 CSS 变量"
    assert "@media" in css, "应有窄屏适配"
    assert "grid-template-columns" in css, "应为栅格布局"
    print("OK  css 引用变量 + 栅格 + 窄屏媒体查询")


def test_js_wires_all_controls():
    js = _read("yaml_editor.js")
    for cid in ("yAppFilter", "ySave", "yReload", "yEditor", "yGen", "yApply"):
        assert f"#{cid}" in js, f"未绑定 #{cid}"
    print("OK  6 个控件均已绑定事件")


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
