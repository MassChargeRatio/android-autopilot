# 派单卡 B：WebUI 的 YAML 编辑器前端

派单编号：`AUTOP-WEBUI-YAML-2026-10-22-B`
工作目录：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
环境：**必须**用 `./.venv/Scripts/python.exe`

## 1. 任务

实现 `webui/static/yaml_editor.js` + `webui/static/yaml_editor.css`（可按需微调 `webui/static/yaml.html`，但**必须保留骨架里的元素 ID**），并补 `tests/test_yaml_editor_static.py`。

入口：控制台左侧导航「✎ YAML 编辑」→ `/yaml.html`（Host 已埋路由，页面会注入一次性 token）。

## 2. 可写 / 禁碰

| 类别 | 文件 |
|---|---|
| **可写** | `webui/static/yaml_editor.js`、`webui/static/yaml_editor.css`、`webui/static/yaml.html`（保留 ID）、`tests/test_yaml_editor_static.py`、`dispatch/AUTOP-WEBUI-YAML-2026-10-22-B/PROGRESS.md` |
| **只读** | `webui/server.py`、`webui/routes_yaml.py`（A 卡产物，可能稍后才就绪）、`webui/static/app.css`、`webui/static/index.html`、`webui/static/app.js` |
| **绝对禁碰** | `webui/server.py`、`webui/routes_yaml.py`、`webui/data.py`、`webui/static/app.css`、`webui/static/app.js`、`webui/static/index.html`、`main.py`、`config.yaml`、`config/apps/**`、任何既有测试、A 卡的一切文件 |

## 3. 后端契约（A 卡实现中，Host 骨架已定稿；按契约写前端，不要等）

```
GET  /api/yaml/apps              -> {ok, apps:[{name,file,size,mtime,behaviors:[...]}]}
GET  /api/yaml/app?name=X        -> {ok, name, file, eol, text}
GET  /api/yaml/fragment?name=X&behavior=sign -> {ok, fragment}
POST /api/yaml/app       {name,text}            -> {ok, action:"saved"|"unchanged"|"rolled_back", backup, diff}
POST /api/yaml/generate  {name,behavior,text,entry?,tab_text?,tab_xy?,hub_text?,hub_xy?,
                           anchor_text?,anchor_xy?,ball_xy?,xy?,h5?,h5_offset?}
                                  -> {ok, entry, actions, fragment, warnings, candidates_used}
POST /api/yaml/apply     {name,behavior,actions,force?}
                                  -> {ok, action:"inserted"|"replaced"|"skipped", backup, diff, warnings}
```

**鉴权**：所有 POST 必须带请求头 `X-Auth-Token: <token>`，token 从
`<meta name="console-token" content="...">` 读（Host 在 `/yaml.html` 注入）。
**禁止**把 token 写死进 js/css，也禁止打印到界面。

## 4. 必须保留的元素 ID（骨架已定义）

`yStatus` `yAppFilter` `yAppList` `yBehavior` `ySave` `yReload` `yEditor` `yMsg`
`yNlText` `yGen` `yApply` `yNlOut`

## 5. 功能要求

1. **左侧 App 列表**：`GET /api/yaml/apps` 渲染；`yAppFilter` 输入即筛选（名称/别名子串，不区分大小写）。
2. **中间编辑器**：选中 App → `GET /api/yaml/app?name=` 把 `text` 灌入 `yEditor`（textarea）；
   `yBehavior` 下拉列出该 App 的 behaviors（来自 apps 接口的 `behaviors` 字段）；
   `yReload` 重新拉取；`ySave` → `POST /api/yaml/app`，把响应里的 `action/backup/diff` 显示到 `yMsg`
   （saved 用绿色、rolled_back/错误用红色、unchanged 用灰色），**保存前若 textarea 被改过要弹 confirm**。
3. **右侧自然语言生成**：`yNlText` 输入一句话 → `yGen` → `POST /api/yaml/generate`，
   把 `fragment` 显示到 `yNlOut`（只读预览，带语法高亮可选），`warnings` 逐条黄色列出；
   `yApply` → `POST /api/yaml/apply`（带 generate 返回的 `actions`），结果显示 action/backup/diff。
   `yApply` 在未生成前禁用；生成后若用户手改了 fragment 文本，apply 仍用**结构化 actions**（不要让用户改 JSON）。
4. **坐标入参**：在生成区给出可选输入框（tab_xy / hub_xy / xy / h5 开关），
   随 generate 一起提交——真机校准后的坐标从这里进。
5. **换行**：**不要**在前端做 CRLF/LF 转换；服务端按原文件 eol 写回。
6. **样式**：`yaml_editor.css` 用 `app.css` 已有的 CSS 变量（`--color-*`、`--border-radius-*`、`--font-mono`），
   三栏布局（列表 / 编辑器 / 生成），窄屏（<1100px）堆叠为单栏；编辑器用等宽字体、tab 缩进 2。
7. **无依赖**：纯原生 JS（不引 CDN、不引框架），与 app.js 的写法风格一致（IIFE、`const $ = sel => document.querySelector(sel)`）。

## 6. 测试（`tests/test_yaml_editor_static.py`，≥8 例，纯静态检查，不起服务）

- 三个文件存在且非空
- `yaml.html` 含全部必需元素 ID；引入 `yaml_editor.css` 与 `yaml_editor.js`；含 `__CONSOLE_TOKEN__` 占位
- `yaml_editor.js` 读取 token 用的是 `meta[name="console-token"]`；所有 `fetch(..., {method:"POST"})` 都带 `X-Auth-Token`
- js 中出现了契约里的 6 个端点路径（apps/app/fragment/generate/apply），且没有写死 token 字面量
- `yaml_editor.js` 不包含 `\r\n` 转换逻辑（不出现 `.replace(/\\r\\n/g` 之类）
- css 中不使用硬编码 hex 主色（应引用 `var(--` 变量；至少 3 处）
- 窄屏媒体查询存在（`@media`）

## 7. 硬性节奏

1. **前 5 个工具调用内**创建 `dispatch/AUTOP-WEBUI-YAML-2026-10-22-B/PROGRESS.md` 骨架。
2. 每完成一个模块立即覆盖写 PROGRESS（含真实测试输出）。
3. 预算约 250 次工具调用；超预算落盘 OPEN/BLOCKED。
4. 不停在 `requires_action`。

## 8. 验收

1. `pytest tests/test_yaml_editor_static.py -q` 全绿
2. 全量 `pytest tests/ -q` ≥ 360
3. `sha256sum -c dispatch/AUTOP-WEBUI-YAML-2026-10-22/baseline_sha256.txt` 全 OK
4. Host 人工起服务打开 `/yaml.html` 目视检查（不要求截图，要求能加载、能列出 App）
5. PROGRESS 有终态表

## 9. 投递记录

（Host 填：cid / 时间 / 首响）

## 投递记录

| 项 | 值 |
|---|---|
| cid | `conv_f0a88d4ce05244e59b23f7dd37822ff1` |
| 时间 | 2026-10-22 15:52 |
