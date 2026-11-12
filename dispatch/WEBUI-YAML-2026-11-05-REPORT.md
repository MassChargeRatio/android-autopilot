# WEBUI-YAML-2026-11-05 · 执行报告

- 派单卡: `C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot\dispatch\WEBUI-YAML-2026-11-05-A-CARD.md`
- 工作目录: `C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot-wt-webui`
- 分支: `feat/webui-yaml-1105`
- 报告路径: worktree 根 `WEBUI-YAML-2026-11-05-REPORT.md`
- 状态: DONE（静态自检 + 桩冒烟全通过；浏览器实跑按卡由协调员在主树完成）

## 0. 环境勘察

- 分支 `feat/webui-yaml-1105`，git 干净（仅本报告 untracked）。
- `webui/static/` 文件：index.html(11855) / app.css(15916) / app.js(41667) / yaml.html(2808) / yaml_editor.css(4745) / yaml_editor.js(7268)。
- 服务端 `webui/server.py:186` 有 `/yaml.html` 专门路由且 `_serve_page` 白名单含 "yaml.html"（不改 py，保留独立页可用性）。

### 关键风险（勘察结论）

1. **顶层标识符冲突（致命）**：`app.js` 顶层 `const TOKEN` / `const $` / `async function api`；
   `yaml_editor.js` 同样顶层 `const TOKEN` / `const $` / `async function api`。
   两个 classic script 放进同一页面时：
   - `const` 重复声明 → 第二个脚本整体 SyntaxError，编辑器彻底失效；
   - 即便只有函数，`function api` 也会互相覆盖，**会连带打崩 app.js 的请求封装**。
   → 处理：把 `yaml_editor.js` 整体 IIFE 化，只导出 `window.YamlEditor`。
2. **路由白名单硬编码**：`app.js:73` `const VIEWS = ['overview',...,'config']`，`route()` 用
   `VIEWS.includes(v)` 兜底，`#/yaml` 会被降级成 overview。→ 必须补 `yaml`。
3. **初始化时机**：原 `yaml_editor.js` 在 `DOMContentLoaded` 直接 `boot()`（独立页语义）。
   并入 shell 后需懒加载，否则首屏就会打 `/api/yaml/apps`。
4. **布局**：`.ymain` 三栏 `240px / 1fr / 380px` 是整页宽度语义，塞进有 200px 侧栏的
   `.main` 后需 shell 作用域内的列宽与断点适配。
5. `yaml_editor.css` 里 `.yhead` / `.yaml-page` 在 shell 内不再生效（保留给独立页），
   `.yeditor` 缺 `box-sizing:border-box`，`width:100%` + padding 会溢出父容器。

## 1. 改动清单

| 文件 | 改动 |
|---|---|
| `webui/static/index.html` | ① `<head>` 增 `<link href="/static/yaml_editor.css">`；② nav 第 8 项 `href="/yaml.html"` → `href="#/yaml"`（含对齐空格）；③ `view-config` 之后新增 `<section class="view" id="view-yaml">`：`.vhead`(h1 + `#yStatus`) + `.ymain`(yside/ybody/ynl 三区，取自 yaml.html 的 `<main class="ymain">`，**丢弃** 原 `.yhead` 与「← 返回控制台」)；④ `<script src="/static/yaml_editor.js">` 置于 app.js **之前**（router 在 app.js 末尾同步执行 `route()`，深链 `#/yaml` 需要先有 `window.YamlEditor`）。 |
| `webui/static/app.js` | ① `VIEWS` 补 `'yaml'`（8 项）；② `route()` 增 `if (view === 'yaml') ensureYaml();`；③ 新增 `ensureYaml()`：校验 `window.YamlEditor.init` 存在后调用，缺失则 toast 报错。|
| `webui/static/yaml_editor.js` | **整体 IIFE 化**（消 `TOKEN/$/api/state` 与 app.js 的顶层重名，防 app.js 的 `api` 被覆盖）；`init()` 幂等 + 懒加载（有节点才初始化，不重复绑事件）；导出 `window.YamlEditor = {init, isBooted}`；独立页 `body.yaml-page` 仍在 `DOMContentLoaded` 自动初始化（`/yaml.html` 路由与白名单保留，独立页可用性不回退）。 |
| `webui/static/yaml_editor.css` | ① `.yeditor` 补 `box-sizing:border-box`（修 `width:100%`+padding 溢出）；② 追加 `#view-yaml` 作用域布局块：三栏 `minmax(160px,220px)/minmax(0,1fr)/minmax(260px,340px)`、`padding:0`；`@media 1440px` 自然语言区整行落下；`@media 1000px` 单列堆叠。全部带 `#view-yaml` 前缀，不影响 `.yaml-page` 独立页与其它 7 视图。 |
| `webui/static/yaml.html` | **未改**（保留独立页兜底；shell 已不再链接它）。 |
| `webui/*.py`、`config/`、`devtools/` | **未改**（遵守第 4 节）。 |

## 2. diff 摘要

- `index.html`：+1 link、nav 1 行替换、+52 行 `#view-yaml` 视图块（含三区与 11 个 `yOpt-*` 参数输入）、+1 script（顺序在 app.js 前）。
- `app.js`：1 行 `VIEWS` +1 元素；`route()` +1 行；+10 行 `ensureYaml()`（含注释）。
- `yaml_editor.js`：72 → 244 行（IIFE 包裹 + 幂等 `init` + 独立页兼容钩子）；业务逻辑逐条保留，未改任何 API 路径与请求体。
- `yaml_editor.css`：1 行 `box-sizing` + 62 行 shell 作用域规则（13 条 `#view-yaml` 选择器）。

## 3. 静态自检

脚本：`temp/webui_selfcheck.py`（结构/id/引用）、`node --check`（语法）、
`temp/yaml_editor_smoke.js`（最小 DOM stub 跑真实 `yaml_editor.js`）、
`tests/test_yaml_editor_static.py`（仓库既有 8 例）。

### 3.1 结构一致性

| 检查项 | 结果 |
|---|---|
| nav 项数 | 8，全部 `#/x` 形式 |
| nav data-view ↔ `section#view-*` | 8 ↔ 8 一一对应，差集为空 |
| `href` 尾段 == `data-view` | 全部一致 |
| `index.html` 残留 `<a href="/yaml.html">` | 无 |
| `app.js` `VIEWS` ↔ nav data-view | 一致（8 项，含 `yaml`） |
| `<main class="main">` 内 `view-yaml` 位置 | 紧跟 `view-config` 之后 |
| ymain 三区 | `yside` / `ybody` / `ynl` 齐备，11 个 `yOpt-*` + `yForce` 全部迁入 |
| 标签配平 | section 10/10、header 8/8、div 115/115、aside 2/2、main 1/1 |

说明：`view-yaml` 内用 `<div class="ymain">` 而非 `<main class="ymain">` —— 原独立页的
`<main>` 若原样搬入会造成 `<main>` 嵌套，HTML 不允许，故降级为 div（样式选择器不变）。

### 3.2 id 与 JS 引用

| 检查项 | 结果 |
|---|---|
| `index.html` id 总数 / 重复 id | 111 / **无重复** |
| app.js 引用的 id（77 个）是否都在 index.html | 全部存在（唯一"缺失"是 `#view-` 拼接串，动态模板，非真实引用） |
| yaml_editor.js 静态引用 id（14 个） | 全部存在 |
| `yOpt-*` 动态拼参（10 个） | 与 HTML 完全对齐，无缺无余 |
| 对已删元素的 JS 引用 | 无（`.yhead` 无 JS 引用，纯样式） |

### 3.3 同页共存安全（关键）

| 检查项 | 结果 |
|---|---|
| 两脚本顶层 `const` 交集 | 空（IIFE 已包裹） |
| 两脚本顶层 `function` 交集 | 空（`api` 不再互相覆盖） |
| 脚本加载顺序 | `yaml_editor.js` → `app.js`（深链 `#/yaml` 需要先有 `window.YamlEditor`） |
| 导出 | `window.YamlEditor = {init, isBooted}` |
| 独立页兼容 | `yaml.html` 仍含 `yaml_editor.js`，`DOMContentLoaded` 检测 `body.yaml-page` 自动 init |

### 3.4 语法与运行时

| 检查项 | 结果 |
|---|---|
| `node --check app.js` | 通过（node v22.12.0） |
| `node --check yaml_editor.js` | 通过 |
| `tests/test_yaml_editor_static.py` | **8/8 通过**（既有契约未被破坏：required ids / token / 端点 / 无写死 token / 不转换行 / 控件绑定） |
| DOM stub 冒烟：脚本加载 | 无异常 |
| DOM stub 冒烟：加载阶段请求数 | 0（确认懒加载生效，首屏不打 `/api/yaml/apps`） |
| DOM stub 冒烟：首次 `init()` | `isBooted=true`，随后恰好 1 次 `/api/yaml/apps`，`#yStatus` = "共 2 个 App" |
| DOM stub 冒烟：二次 `init()` | 幂等，无重复请求（router 每次切 tab 都会调） |

### 3.5 全面检查中额外修掉的问题

1. **深色主题变量不匹配（视觉级）**：`yaml_editor.css` 写的是 `--color-*` 语义变量，
   `app.css` 只提供 `--bg/--bg2/--fg/--line/--acc` 等暗色 token，导致全部落回 `var()`
   里的浅色兜底（`#fff` / `#f5f6f7`）——并入 shell 后会在暗色控制台里出现白色面板。
   已补作用域化别名块（`.yaml-page, #view-yaml`），把 17 个语义变量映射到暗色 token；
   顺带修好独立页同样的白块问题。
2. **`.yeditor` 溢出**：`width:100%` + `padding:10px` + `border` 无 `border-box`，
   在栅格列内会溢出 2~22px。已补 `box-sizing:border-box`。
3. **懒加载**：原 `DOMContentLoaded` 无条件 `boot()`，并入 shell 后会让首屏多打一次
   `/api/yaml/apps`（且此时视图隐藏）。改为 `init()` 幂等 + 由 router 触发。
4. **窄屏**：`.ymain` 三栏在 1200~1440px 会挤压中间编辑器（`minmax(360px,1fr)` 触底），
   已加 1440px（自然语言区整行落下）/1000px（单列堆叠）两级断点。

## 4. 未决项

1. **浏览器实跑未做**：按卡第 1 节，worktree 无 `.venv`、禁止起服务，故未做真实页面渲染
   与点击验证（验收表中的「点击 nav → 激活 view-yaml」「选中 app → yEditor 加载文本」两条
   属运行时行为，本卡只能静态 + 桩验证）。请在主树起服务后目视确认：
   `http://127.0.0.1:<port>/#/yaml` 深链直达、nav 第 8 项高亮、切换 tab 不整页刷新。
2. **`/yaml.html` 未删**：服务端 `server.py` 的路由与 `_serve_page` 白名单仍指向它（py 禁改），
   且既有测试 `test_html_has_required_ids` 直接校验该文件，故保留为独立页兜底。
   若协调员希望彻底下线，需改 py 白名单 + tests，超出本卡可写范围。
3. **未新增自动化测试**：卡限定「只改 `webui/static/`」，未动 `tests/`。建议后续补：
   - `index.html` 的 `data-view` ↔ `section#view-*` 一一对应；
   - `yaml_editor.js` 顶层无裸 `const TOKEN/$`、整体 IIFE（防回归到重名打崩 app.js）；
   - `app.js` 的 `VIEWS` 含 `yaml`。
   上述三条已在本报告的 3.1/3.3 用一次性脚本验证，可直接改写成 pytest。
4. **`yaml_editor.js` diff 偏大**：因整体包 IIFE 后统一缩进两格，diff 显示 406 行变更
   （实际语义变更仅 ~20 行）。业务逻辑、API 路径、请求体逐条保持不变。
