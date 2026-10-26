# 验收台账：WebUI YAML 编辑 + 自然语言配置（AUTOP-WEBUI-YAML-2026-10-22）

## 0. 派单前基线（2026-10-22 15:50）

| 项 | 值 |
|---|---|
| `pytest tests -q` | **360 passed**, 1 warning |
| `config/apps/*.yaml` + `config.yaml` sha256 | 35 条 → `baseline_sha256.txt` |
| `tests/test_webui.py` | 34 passed |

## 1. Host 预埋（已完成，两卡只读）

| 文件 | 改动 |
|---|---|
| `webui/routes_yaml.py` | 新建骨架：`YamlRoutes.handle_get/handle_post` + `_app_file()` + 6 路由契约 docstring |
| `webui/server.py` | GET/POST 各加 4 行钩子（`ImportError/NotImplementedError` 安全穿透）；新增 `/yaml.html` 路由（白名单 + token 注入） |
| `webui/static/index.html` | 导航加 1 行「✎ YAML 编辑」→ `/yaml.html` |
| `webui/static/yaml.html` / `yaml_editor.js` / `yaml_editor.css` | 占位三件套（B 卡接管），元素 ID 契约已定 |

踩坑记录：钩子最初只捕 `ImportError`，骨架抛 `NotImplementedError` 导致 7 个 webui 测试 500；
已改为同时捕获，复跑 34 passed。

## 2. 投递记录

| 卡 | tag | cid | 时间 | 首响 |
|---|---|---|---|---|
| A（后端 API） | `AUTOP-WEBUI-YAML-A-2026-10-22` | `conv_f0a88d4ce05244e59b23f7dd37822ff1` | 15:52 | 开始理解任务 |
| B（前端） | `AUTOP-WEBUI-YAML-B-2026-10-22` | `conv_90dcd6fea5e84f0fa3d184b7ac36e813` | 15:52 | 「让我先读卡片了解任务详情」 |

投递前 marvis：23 会话，3 个 in_progress（均为历史 `A2A mesh probe`）。
两卡文件级不重叠（A=webui/routes_yaml.py + 其测试；B=static/yaml_editor.* + yaml.html + 其测试）。

## 3. 验收清单（待填）

| # | 判据 | 状态 |
|---|---|---|
| 1 | 两卡 PROGRESS 有终态表 | 待验 |
| 2 | `pytest tests/test_webui_yaml_api.py tests/test_yaml_editor_static.py -q` 全绿 | 待验 |
| 3 | 全量 `pytest tests/ -q` ≥ 360 | 待验 |
| 4 | `sha256sum -c baseline_sha256.txt` 全 OK | 待验 |
| 5 | AST 词表门禁：routes_yaml.py 无签到词表字面量 | 待验 |
| 6 | 起服务打开 `/yaml.html` 目视：能列出 App、能编辑保存、能生成/应用 | 待验 |
| 7 | 禁碰文件 mtime 不变 | 待验 |

---

# 交付结果（2026-10-22 17:40，Host 接手）

## 背景

A/B 两卡的 marvis 会话均 **failed**（15:52 投递，17:10 查探时 PROGRESS 分别停在 15:58 / 15:54，
尾部显示仍在「读文件」阶段即被网关判失败）——历史上「只探索不落盘」的失败模式，零产物。
按预案由 Host 接手实现。

## 交付物

| 文件 | 行数 | 测试 |
|---|---|---|
| `webui/routes_yaml.py` | 6 路由实现（apps/app/fragment/app(POST)/generate/apply） | 14 passed |
| `tests/test_webui_yaml_api.py` | 14 例（tempdir + monkeypatch APPS_DIR） | 14 passed |
| `webui/static/yaml_editor.js` | 三栏交互（列表/编辑器/生成） | 8 passed |
| `webui/static/yaml_editor.css` | 引用 app.css 变量、栅格、窄屏堆叠 | — |
| `webui/static/yaml.html` | 增补 10 个坐标入参 + 强制替换勾选 | — |
| `tests/test_yaml_editor_static.py` | 8 例静态契约 | 8 passed |

## 验收（Host 实跑）

| # | 判据 | 结果 |
|---|---|---|
| 1 | 两卡 PROGRESS | marvis 失败，Host 接手；本文件即终态记录 |
| 2 | 新测试全绿 | **22 passed**（14 API + 8 静态） |
| 3 | 全量 pytest | **382 passed**（基线 360 → +22） |
| 4 | 配置零写入 | `sha256sum -c` → **35/35 OK** |
| 5 | AST 词表门禁 | `test_vocab_gate_ast` 通过（routes_yaml.py 字符串字面量无签到词表） |
| 6 | 起服务端到端 | 见下 |
| 7 | 禁碰文件 | candidates.py / behavior_runner.py / main.py / app.js / app.css 均未改 |

## 端到端冒烟（起真实服务）

```
GET  /yaml.html                              200  token 已注入（无 __CONSOLE_TOKEN__ 残留）
GET  /api/yaml/apps                         200  34 个 App（趣头条: sign/watch/withdraw）
GET  /api/yaml/app?name=七猫免费小说          200  text 1135 字符，eol='\n'
GET  /api/yaml/fragment?name=趣头条&behavior=sign  200  72 行
POST /api/yaml/generate （带 token）          200  entry=home_direct, actions=2, warnings=[]
POST /api/yaml/generate （错 token）          403
```

## 使用方式

浏览器打开控制台 → 左侧导航「✎ YAML 编辑」：

1. **左栏**选 App（可筛选）→ 中栏 textarea 直接编辑 YAML →「保存」
   （保存走 yaml_writer：YAML 校验 → eol 保真 → 备份 → 写后 verify → 失败自动回滚）
2. **右栏**输入一句中文（如「点底部福利tab，点连续签到卡」）→「生成片段」→ 预览 + warnings
   →「写入配置」（已存在行为时勾选「强制替换」）
3. 展开「坐标与模板参数」可填 tab_xy / anchor_xy / xy 等真机校准坐标，与 CLI 的
   `--tab-xy/--anchor-xy/--xy` 等价。

## 教训

1. marvis 本轮两卡同时失败，且失败前**只读不写**——「硬性落盘节奏」只约束了它自己建 PROGRESS，
   没约束「先建骨架代码」。后续派单卡要把「前 5 个调用内先落一个可运行的最小骨架」写进节奏。
2. Host 预埋的钩子用 `except (ImportError, NotImplementedError)` 穿透是对的：
   否则 A 卡未实现时任何 `/api/yaml/*` 请求都会 500，而不是落到原有 404 分派。
