# 派单卡 WEBUI-YAML-2026-11-05-A — webui YAML 编辑页并入 shell tab + 全面检查

> 本卡是唯一任务来源。派单文本只含本卡绝对路径。

## 第 0 节 · 反空转硬约束（必带，违反=任务作废）

1. **先落盘再调研**：第一个写文件动作必须是创建 `WEBUI-YAML-2026-11-05-REPORT.md` 并写入表头。
2. **增量追加**：每完成一类立刻追加到报告，不要全想清楚再统一写。
3. **工具调用 ≤ 8/轮**：连续 8 次必须写一次文件或输出一段结论。
4. **列 todo 不算进度，只有报告文件字节数算**。
5. **上下文警戒**：40+ 工具调用而报告不存在 → 立刻停下先把已查到的写进去。
6. 没做成必须写 `failed` + 原因，禁止静默 continue/pass 吞错误。

## 第 1 节 · 工作目录（第一行必须是绝对路径）

```
C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot-wt-webui
```

- 这是独立 worktree（分支 `feat/webui-yaml-1105`），仅含 git 跟踪文件。
- **`.venv` 不在此目录**（gitignore），**禁止尝试启动服务**——服务验证由协调员在主树完成。
- 只改 `webui/static/` 下的前端文件。**服务端 Python（server.py / data.py / jobs.py / routes_yaml.py）不改**，API 已齐备。

## 第 2 节 · 任务目标

把 YAML 编辑从**独立页**（`/yaml.html`）并入控制台 shell，作为**第 8 个 tab**，与【总览】【收益】等视图行为完全一致；并对 web ui 做一次全面检查。

### 2.1 现状（已确认，勿再全量探索）

- `webui/static/index.html`：左侧 nav 第 8 项是
  `<a href="/yaml.html" data-view="yaml"><i>✎</i>YAML 编辑</a>`（L30）——**独立页面跳转**，异常。
- 其余 7 个 tab 均为 `<a href="#/xxx" data-view="xxx">`，对应
  `<section class="view" id="view-xxx">`：overview / tasks / earnings / device / calib / tools / config。
  **`view-yaml` 的 section 不存在**。
- `webui/static/yaml.html`（59 行）：独立页。`<body class="yaml-page">` + `<header class="yhead">`
  （含「← 返回控制台」）+ `<main class="ymain">`（内：`aside.yside` 筛选/列表、`section.ybody`
  编辑器区、`section.ynl` 自然语言生成区）。引用 `yaml_editor.css` + `yaml_editor.js`。
- 服务端 API 已存在且可用（`webui/routes_yaml.py`，路径 `/api/yaml/apps|app|fragment|generate|apply`）。
- 前端脚本：`app.js`（shell 主逻辑，含 hash router）+ `yaml_editor.js`（yaml 页逻辑）。

### 2.2 要做的事

1. **index.html**：
   - L30 改为 `<a href="#/yaml" data-view="yaml"><i>✎</i>YAML 编辑</a>`（与其它 tab 同构）。
   - 在 `<main class="main">` 内、`view-config` 之后新增
     `<section class="view" id="view-yaml">`，内容取自 yaml.html 的 `<main class="ymain">`。
   - **去掉 yaml.html 的 `<header class="yhead">`**（shell 内统一用 `.vhead`），
     换成与其他视图一致的 `<header class="vhead"><h1>YAML 配置编辑</h1><span class="muted" id="yStatus">加载中…</span></header>`。
   - 引入 `yaml_editor.css` + `yaml_editor.js`（link/script 标签），或把二者并入 app 的 CSS/JS 体系（二选一，保持一致、不重复引用）。
2. **app.js**：确认 hash router 对 `#/yaml` 的激活逻辑（激活 `view-yaml`、高亮 nav 第 8 项）。若 router 按 `data-view` 泛化（`data-view` 匹配 section id），则自动兼容，只需确认无硬编码白名单；若硬编码了 7 个视图，需补 `yaml`。
3. **app.css**：`yaml-page`/`yhead` 相关样式在 shell 内不适用，需适配 `.view#view-yaml` 内的 `.ymain/.yside/.ybody/.ynl` 布局，保证不破 shell 网格、不与其它视图样式冲突。
4. **yaml_editor.js**：确认初始化时机（原独立页 `DOMContentLoaded` 直接 init；并入 shell 后视图可能默认隐藏，需在 router 激活 `view-yaml` 时才 init，或懒加载）。检查 id 冲突（yAppFilter 等 id 在 index.html 中唯一）。
5. **全面检查**（不只是 yaml）：nav 8 项一致性、每个 `data-view` 都有对应 `section#view-*`、每个 `href="#/x"` 都有对应 section、JS 无语法错误、无重复 id、无对已删元素的 JS 引用、移动端/窄屏样式不崩。

## 第 3 节 · 验收标准

- [ ] `index.html` 无 `<a href="/yaml.html">`，nav 8 项全部 `#/x` 同构
- [ ] `view-yaml` section 存在且含 ymain 三区（yside/ybody/ynl）
- [ ] 点击 nav「YAML 编辑」→ 激活 `view-yaml`、nav 高亮（无需整页刷新）
- [ ] `/api/yaml/apps` 拉取列表、选中 app 后 `yEditor` 加载文本（复用现有 API，不新增端点）
- [ ] 静态自检通过：HTML 每个 `data-view` ↔ `section#view-*` 一一对应；JS 语法无错
- [ ] 报告文件 `WEBUI-YAML-2026-11-05-REPORT.md` 含改动 diff 摘要 + 自检结果 + 未决项

## 第 4 节 · 约束与禁止

- **禁止**改动 `webui/*.py`、`config/`、`devtools/`。
- **禁止** `git stash` / `git checkout --` / `git reset`（worktree 独享，但保持整洁）。
- 完成后在 worktree 内 `git add webui/static/` + `git commit -m "webui: yaml 编辑并入 shell tab (#/yaml) + 全检查"`，**不 push**（协调员验证后处理）。
- 若遇无法解决的冲突/依赖，写 `failed` + 具体原因到报告，不要硬改。

## 第 5 节 · 交付

1. `WEBUI-YAML-2026-11-05-REPORT.md`（worktree 根或 worktree/webui/ 下均可，报告里写清路径）。
2. 提交记录（worktree 内 commit）。
