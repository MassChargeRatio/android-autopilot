# 03 · WebUI 与运行（自包含）

## 1. 启动

```bash
cd <项目根>
python webui/server.py            # 默认起 HTTP 服务（本机访问）
# 前端入口：http://127.0.0.1:<port>/
```

要点与历史坑：

1. **端口**：早期 `find_free_port` 只 `bind` 不 `listen`，导致「返回可用但实际被占」→ 起服务报错。已修复为 `bind + listen` 探测且 `allow_reuse_address=False`。**改这段代码不要回退**。
2. **端口被旧进程占用会「返回旧代码」**：曾出现主树旧服务占 8766，访问看到的是旧前端。排查：先确认端口对应进程（`netstat -ano | findstr :8766`），必要时换端口起新服务验证。
3. **静态页白名单**：`server.py` 模块级 `PAGES = ("yaml.html",)`，`do_GET` 与 `_serve_page` 同源判断，防止被当任意文件读取器。**新增顶层页面只改 `PAGES`**，不要在两处各写一遍（历史症状：一处改了另一处没改 → 页面永远 404）。
4. **一次性 token 注入**：页面返回前把 `__CONSOLE_TOKEN__` 替换为 `self.console.token`，写操作需回传；页面禁缓存 `Cache-Control: no-store`。

## 2. 八个视图（前端 shell tab）

前端 `app.js` 定义：`const VIEWS = ['overview','tasks','earnings','device','calib','tools','config','yaml']`。
路由规则：`location.hash`（如 `#/tasks`）→ 匹配 `VIEWS`，否则回落 `overview`；每个视图是 `#view-<name>` 的 `section.view`，切换只加 `.on` 类（**同页切换，不整页刷新**）。

| 视图 | 作用 | 关键点 |
|---|---|---|
| `overview` | 总览：app 数、今日收益、覆盖率、设备状态 | 数据来自 `/api/overview` |
| `tasks` | 任务列表 + 步骤日志 + 启动/停止 | 支持深链 `#/tasks?q=一淘&beh=sign`（按 app/行为过滤） |
| `earnings` | 收益：按日序列、按 app 汇总、明细 | `/api/earnings` |
| `device` | 设备：连接状态、当前前台、截图 | `/api/device`、`/api/device/screen.png` |
| `calib` | 校准：覆盖率、验证口径 | `/api/calib`、`Store.verify_coverage()` |
| `tools` | 工具：白名单工具的运行入口 | `/api/tools`、`POST /api/tools/{id}/run` |
| `config` | 配置查看/打开 | `POST /api/config/open` |
| `yaml` | **YAML 在线编辑**（shell tab，懒加载） | 首次进入调 `ensureYaml()` 加载 `yaml_editor.js`；**IIFE 化**避免顶层 `$`/`api`/`TOKEN` 与 `app.js` 重名打崩 |

## 3. HTTP API 契约（真实路由）

### GET

| 路径 | 返回 |
|---|---|
| `/api/health` | 健康检查 |
| `/api/overview` | 总览聚合（apps 数、今日收益、覆盖率、设备） |
| `/api/device` | 设备信息（serial、model、前台、屏幕尺寸） |
| `/api/device/screen.png` | 当前设备截图（PNG） |
| `/api/earnings` | 收益（`?days=&app=&limit=`） |
| `/api/ops` | 操作日志（`?limit=&level=`） |
| `/api/tools` | 可用工具列表（白名单） |
| `/api/calib` | 校准/覆盖率数据 |
| `/api/jobs` | 任务列表 |
| `/api/jobs/{id}/log` | 某任务日志（增量） |
| `/api/jobs/{id}` | 某任务详情（含步骤状态） |

### POST

| 路径 | 作用 | 返回语义 |
|---|---|---|
| `/api/overview/reload` | 重载配置并刷新总览 | `{ok, ...overview}` |
| `/api/config/open` | 用系统编辑器打开 config.yaml（本机） | `{ok}` |
| `/api/jobs` | **启动任务**（body: `{plan:[{name,behaviors}], dry_run, force, serial, confirm_money}`） | 成功 `{ok:true, job}`；已有运行中任务 **409**；含提现未确认 **403** |
| `/api/jobs/stop` | 停止全部运行中任务 | `{ok}` |
| `/api/jobs/{id}/stop` | 停止指定任务 | `{ok}`；不存在 404 |
| `/api/tools/{id}/run` | 运行白名单工具 | `{ok, job}` |

### YAML 编辑 API（`routes_yaml.py`）

| 方法 路径 | 作用 |
|---|---|
| GET `/api/yaml/apps` | 列出可编辑 app 文件 |
| GET `/api/yaml/app` | 读取单个 app YAML（`?name=`） |
| GET `/api/yaml/fragment` | 读取配置片段 |
| POST `/api/yaml/app` | 保存单个 app YAML（备份→原子写→校验→失败回滚） |
| POST `/api/yaml/generate` | 生成新 app 配置骨架 |
| POST `/api/yaml/apply` | 应用编辑器整体改动 |

**保存链路（重要语义）**：
1. `backup(path, tag="WEBUI")` 备份
2. `atomic_write(path, lines, eol, ends_nl)` 原子写
3. `_verify(path, before)` 校验（可解析 + 结构合法）
4. 失败 → `shutil.copy2(backup, path)` 回滚，返回 **`{"ok": false, "action": "rolled_back", "warnings": problems}`**
5. 成功 → `{"ok": true, "action": "saved", "diff": ...}`

**app 名安全校验**：拒绝空、`/`、`\`、`..`、`\x00`；只允许匹配 `config/apps/` 下已存在的文件名（stem 或 `NN_` 后缀匹配）。

## 4. 任务调度（jobs.py）

```python
class JobBusy(RuntimeError):        # 已有运行中任务 → 上层转 409
    def __init__(self, active=None): ...

class JobManager:
    def create_exclusive(self, kind, title, steps, meta=None):
        with self._lock:                      # ★ 判空闲 + 登记 必须在同一把锁内
            busy = self._active_locked()
            if busy is not None:
                raise JobBusy(busy)
            return self._create_locked(...)
```

- **设备是独占资源**：同一时刻只允许 1 个运行中任务。历史 bug 是「先 `active()` 检查、再 `create()`」两次取锁有空窗，并发 POST 会启动两个任务；已收敛为 `create_exclusive`。
- 历史列表保留最近 `history=30` 条（有上限，防内存增长）。
- 执行子进程：`subprocess.Popen(..., stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)` + **独立读取线程写队列**（不能用 `for line in p.stdout`，子进程不输出时会卡死无法停止）；停止用 `_kill_tree`（Windows `taskkill /T /F`，否则 adb 子进程残留）；收尾 `p.wait(timeout=15)`，超时再 `_kill_tree`。

## 5. 前端约定（改 UI 必读）

1. 新视图三步：`index.html` 加 `<section class="view" id="view-x">` + 导航 `<a data-view="x" href="#/x">` + `app.js` 的 `VIEWS` 加 `'x'`。
2. **不要新增顶层全局变量**：`app.js` 与 `yaml_editor.js` 共享页面，后者必须 IIFE 包裹（曾因顶层 `TOKEN`/`$`/`api` 重名把 `app.js` 打崩）。
3. `any_of` 分支数显示读 `o.choices`（不是 `o.branches`）。
4. 回滚/失败以 `body.ok === false` 判断，不要只看 `action`。
5. CSS 作用域化到 `.yeditor`/`.ymain`，避免污染全局；有 1440px / 1000px 断点。

## 6. 运行模式

| 模式 | 命令 | 说明 |
|---|---|---|
| 单任务 | `python main.py --task "去一淘签到"` | 走 CLI，不进 WebUI |
| 计划 | `python main.py --app 一淘 --task "签到并看视频"` | 指定 app |
| 预演 | `python main.py --task "..." --dry-run` | 只打印计划，不碰设备 |
| 收益 | `python main.py --today` | 今日汇总 |
| 定时 | Windows 任务计划程序调 `main.py` | 脚本内还有作息窗口+随机偏移 |
| 设备端 | Termux + adb 连本机 5555 | 可选，需把 `serial` 留空 |
