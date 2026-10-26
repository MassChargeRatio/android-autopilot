# 派单卡 A：WebUI 的 YAML 读写 + 自然语言生成 API（后端）

派单编号：`AUTOP-WEBUI-YAML-2026-10-22-A`
工作目录：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
环境：**必须**用 `./.venv/Scripts/python.exe`

## 1. 任务

实现 `webui/routes_yaml.py`（Host 已建好骨架与路由契约，见文件顶部 docstring），
并补 `tests/test_webui_yaml_api.py`。GUI 需要两个能力：**在线编辑 App 的 YAML**、**用自然语言生成 YAML 片段并写入**。

## 2. 可写 / 禁碰

| 类别 | 文件 |
|---|---|
| **可写** | `webui/routes_yaml.py`、`tests/test_webui_yaml_api.py`、`dispatch/AUTOP-WEBUI-YAML-2026-10-22-A/PROGRESS.md` |
| **只读** | `webui/server.py`（钩子已埋好，**不要改**）、`webui/data.py`、`devtools/yaml_writer.py`、`devtools/nl_to_steps.py`、`candidates.py`、`config_loader.py`、`config/apps/*.yaml` |
| **绝对禁碰** | `webui/server.py`、`webui/static/**`、`webui/data.py`、`main.py`、`config.yaml`、`config/apps/**`、任何既有测试、B 卡的一切文件 |

## 3. 已就绪的依赖（直接调，不要重写）

```python
# devtools/yaml_writer.py
read_text(path) -> (lines, eol, ends_nl)      # eol ∈ {"\r\n","\n"}
load_app(path) -> dict
snapshot(config_path=None) -> {app_name: app_dict}
verify(path, before, bid, expect_actions=None) -> (ok, problems)
insert_behavior(path, bid, actions, comments=None, apply=False, force=False) -> WriteResult
replace_behavior(path, bid, actions, comments=None, apply=False, force=False) -> WriteResult
atomic_write(path, lines, eol, ends_nl=True)
backup(path, tag="NL") -> str
app_path(app_name, config_path=None, base_dir=None) -> str
# WriteResult(path, action, backup, diff, warnings)  # action: preview|inserted|replaced|skipped|rolled_back

# devtools/nl_to_steps.py
build_behavior(text, app_name, bid, *, entry="auto", params=None, app_cfg=None)
    -> {"behavior","entry","actions","warnings","candidates_used"}
to_yaml_fragment(actions, indent=2) -> str
template_names() -> ["personal_center","feed_ball","home_direct"]
guess_entry(text) -> str

# config_loader
load_config(path) / money_behaviors(cfg)  # 资金类行为缺省 {"withdraw"}
```

## 4. 路由契约（逐条实现，骨架 docstring 里有完整版）

`handle_get(path, q)` / `handle_post(path, payload)`：**返回 `None` 表示不是我的路由**（server 继续分派）；返回 `(code, obj)` 即响应。所有响应体带 `ok` 字段。

| 方法 | 路径 | 响应 |
|---|---|---|
| GET | `/api/yaml/apps` | `{"ok":true,"apps":[{name,file,size,mtime,behaviors:[...]}]}` |
| GET | `/api/yaml/app?name=X` | `{"ok":true,"name":..,"file":..,"eol":"\\r\\n"/"\\n","text":"原始文本"}` |
| GET | `/api/yaml/fragment?name=X&behavior=sign` | `{"ok":true,"fragment":"该行为的 YAML 文本"}` |
| POST | `/api/yaml/app` `{name,text}` | 保存编辑器内容；`{"ok":true,"action":"saved"/"unchanged","backup":..,"diff":".."}` |
| POST | `/api/yaml/generate` `{name,behavior,text,entry?,tab_text?,tab_xy?,hub_text?,hub_xy?,anchor_text?,anchor_xy?,ball_xy?,xy?,h5?,h5_offset?}` | `{"ok":true,"entry":..,"actions":[...],"fragment":"..","warnings":[...],"candidates_used":{..}}` |
| POST | `/api/yaml/apply` `{name,behavior,actions,force?}` | `{"ok":true,"action":"inserted"/"replaced"/"skipped","backup":..,"diff":"..","warnings":[...]}` |

## 5. 实现要求（硬性）

1. **保存（`/api/yaml/app`）四道闸**：
   a. `yaml.safe_load(text)` 必须成功，否则 `(400, {"ok":false,"error":"YAML 解析失败: ..."})`；
   b. 用 `yaml_writer.snapshot()` 取写前快照，写后 `verify()` 比对——**除目标 App 外 34 份必须逐字相等**，否则自动回滚并返回 `rolled_back`；
   c. **eol 保真**：用 `read_text()` 探测原文件 eol，`atomic_write()` 按原 eol 写。浏览器 textarea 会把 CRLF 归一成 LF，所以**不能信任传入文本的换行**，必须以原文件 eol 为准；
   d. 写前 `backup(path, tag="WEBUI")`；内容与原文件逐行相同则返回 `unchanged` 且不写盘。
2. **`/api/yaml/generate` 必须走 `nl_to_steps.build_behavior`**，payload 的坐标字段原样映射进 `params`（`tab_text/tab_xy/hub_text/hub_xy/anchor_text/anchor_xy/ball_xy/xy→sign_xy/h5/h5_offset`）。
   **禁止**在 routes_yaml.py 里出现任何签到词表字面量（用 AST 自检：`ast.parse` 收集字符串常量，不得含「今日签到/立即签到/任务中心/连续签到/签到领金币」）。
3. **资金红线**：`behavior` 命中 `money_behaviors(cfg)` 且 payload 无 `allow_money:true` → 拒绝 `(400, ...)`，与 CLI 一致。
4. **`/api/yaml/apply`**：payload 带 `actions`（generate 的产物）时直接写；带 `text` 时先 build_behavior。`force` 缺省走 `insert_behavior`，已存在行为时返回 `skipped` 并在 warnings 里提示加 force。
5. **模块级 `APPS_DIR` 必须可被 monkeypatch**（测试要指向临时目录）——所有文件定位都通过 `self._app_file()` / 模块常量，不要缓存成实例属性或局部变量。
6. 异常一律转成 `(4xx/5xx, {"ok":false,"error":...})`，**不要抛到 server 层**（server 只会返回 500 文本）。

## 6. 测试（`tests/test_webui_yaml_api.py`，≥12 例）

用 `tempfile.TemporaryDirectory()` 造 `config/apps/` + `config.yaml`，monkeypatch `routes_yaml.APPS_DIR` 与 `yaml_writer` 的 base 参数；用假 Handler（`_json/_err` 记录）驱动：

- `handle_get('/api/yaml/apps')` 返回全部 App 与 behaviors 键
- `handle_get('/api/yaml/app?name=A')` 返回原文 + eol（分别造 CRLF/LF 两份断言）
- 保存：合法 YAML → saved；非法 YAML → 400 且文件未动；内容不变 → unchanged 且不写盘
- 保存后 `verify`：人为把另一份 App 改坏 → 返回 rolled_back 且文件字节恢复
- eol 保真：CRLF 文件保存后仍 CRLF，未修改行字节不变
- `/api/yaml/generate`：返回 actions/fragment/warnings；坐标字段映射正确（传 `tab_xy` 后 actions 里出现对应 click_point）
- 词表门禁：AST 收集 routes_yaml.py 字符串常量，无签到词表
- 资金红线：`behavior=withdraw` 无 allow_money → 400
- `/api/yaml/apply`：actions 写入 → inserted；重复 → skipped + 提示 force；`force=true` → replaced
- 非本模块路径返回 None（如 `/api/health`）
- 非法 app 名（含 `/`、`..`）→ 400

## 7. 硬性节奏

1. **前 5 个工具调用内**创建 `dispatch/AUTOP-WEBUI-YAML-2026-10-22-A/PROGRESS.md` 骨架。
2. 每完成一个处理函数立即覆盖写 PROGRESS（签名 + 测试命令 + 真实输出）。
3. 预算约 250 次工具调用；超预算落盘 OPEN/BLOCKED。
4. 不停在 `requires_action`；疑义写 PROGRESS 继续干。

## 8. 验收（Host 实跑复核）

1. `pytest tests/test_webui_yaml_api.py -q` 全绿
2. 全量 `pytest tests/ -q` ≥ 360
3. `sha256sum -c dispatch/AUTOP-WEBUI-YAML-2026-10-22/baseline_sha256.txt` 全 OK（开发期配置零写入）
4. AST 词表门禁零命中
5. PROGRESS 有终态表

## 9. 投递记录

（Host 填：cid / 时间 / 首响）

## 投递记录

| 项 | 值 |
|---|---|
| cid | `conv_f0a88d4ce05244e59b23f7dd37822ff1` |
| 时间 | 2026-10-22 15:52 |
