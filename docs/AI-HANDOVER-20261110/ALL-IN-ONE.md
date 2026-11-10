# Android Autopilot · AI 交接合并版（2026-11-10）

> 本文件是 `docs/AI-HANDOVER-20261110/` 下 5 份**自包含**文档的合并版，用于**一次性粘贴**给无法访问本机的网页版 AI。
>
> **阅读顺序**：第 0 章 → 第 1 章 → 第 2 章 → 第 3 章 → 第 4 章。
> **若超出上下文**：改用分册文件，只粘「00 + 你要改的那一册」。
> **需要全部源码**：本文件**不含**源码，仅内联关键代码形态；完整源码见同目录 `ALL-IN-ONE-WITH-SOURCE.md`（208 文件 / 2.04 MB，适合作为**附件上传**给网页 AI，不建议直接粘贴）。
> **文档与代码冲突时，以代码为准**；本文件中的文件路径仅作定位参考，必要信息均已内联。

## 总目录

| 章 | 标题 | 适合任务 |
|---|---|---|
| 0 | 总览与使用说明 | 首次接手、了解边界与铁律 |
| 1 | 架构与数据流 | 改代码前理解分层与耦合 |
| 2 | 配置规范 | 加 App、改签到/任务配置 |
| 3 | WebUI 与运行 | 改管理端、排查运行/端口 |
| 4 | 状态、待办与可拆分小项目 | 规划下一步、评估拆项 |

---

# 00 · 总览与使用说明（自包含）

> **给接手的网页版 AI**：你**没有本机文件系统、终端、设备**权限。
> 因此本套文档是**完全自包含**的：所有必要信息都已内联，不要假设你能打开仓库文件、运行测试或执行命令。
> 你的产出形态应为：① 架构/代码评审意见；② 设计方案与权衡；③ 可直接粘贴的补丁（diff 或整文件）；④ 配置（YAML）修改稿；⑤ 排查思路。**不要输出「请运行 xxx 把结果发我」这类需要本机执行才能推进的空指令**，除非给出完整命令并说明如何解读输出。

---

## 1. 项目一句话

一个**单机 Windows 工具**：通过 **ADB + uiautomator2** 驱动 Android 真机/模拟器，按「**YAML 配置 + 自然语言意图**」自动完成多个 App 的日常任务（签到 / 打卡 / 预约 / 看视频 / 领金币 / 提现），收益写入 **SQLite** 记账，配 **WebUI** 管理与在线编辑 YAML，并内置**真人化**（作息窗口、坐标抖动、贝塞尔手势、对数正态间隔、传感器模拟）以降低风控识别概率。

定位：**个人自用自动化工具**，非多租户服务、无云端。

## 2. 规模（2026-11 实测）

| 指标 | 值 |
|---|---|
| 文件总数 | 2738（其中 temp/ 1728、_backup_pre_fix/ 163 为非核心） |
| Python 文件 | 397（根模块约 25 个、tests 60、devtools 多） |
| 已配置 App | 35（`config/apps/*.yaml`） |
| 测试文件 | 60 |
| 图像锚点模板 | 104 文件 |
| 配置顶层节 | 13 |
| WebUI 视图 | 8 |

## 3. 文件清单与职责（内联，无需打开）

### 3.1 核心执行链（最重要）

| 文件 | 职责 |
|---|---|
| `main.py` | CLI 入口：`--list` 列 app/行为、`--task "自然语言"`、`--app`、`--dry-run`、`--today` |
| `executor.py` | **执行引擎门面（约 160 行）**：用多重继承组合 `device_session` + `locator` + `behavior_runner`，负责组装状态（设备、视觉、知识库、验证码、变体、多样化概率） |
| `device_session.py` | 设备会话：连接设备、启停 App、等待页面稳定、顶层复位、安全 dump |
| `locator.py` | 元素定位：`_locate` / `_pick_best` / 元素知识库联动 / 视觉兜底（A3 共享件） |
| `behavior_runner.py` | **行为执行（88 KB，最大）**：顶层流程 `run_app_flow`、分派、分支（`any_of`/`random`）、全部 `_step_*` 动作原语、收益识别、验证码 |
| `step_model.py` | **v1/v2 步骤统一编译器**：把 YAML 每个 step 规范化为**不可变 Step**；执行层仍用 `step.raw`，故老配置零改动；产物用于编译期 lint / dry-run 语义投影 |
| `adb_backend.py` | 裸 ADB 后端（可选，`device.backend=adb`）；已建立 `None=失败` 契约 |
| `nlu.py` | 自然语言 → 意图（关键词匹配） |

### 3.2 配置与解析

| 文件 | 职责 |
|---|---|
| `config.yaml` | 主配置（**gitignore，含真实 VLM key**）；13 个顶层节，`apps: []` 由 `apps_dir` 拼接 |
| `config.example.yaml` | 可提交模板（内联示例 apps、占位密钥） |
| `config_loader.py` | 加载 `config.yaml` + `config/apps/*.yaml` 拼接为 `apps` |
| `miniyaml.py` | 零依赖 YAML 子集解析（无 PyYAML 时 fallback） |
| `config/apps/*.yaml` | 35 个 App 配置（**权威拆分源**，如 `19_一淘.yaml`） |

### 3.3 定位 / 视觉 / 知识

| 文件 | 职责 |
|---|---|
| `vision.py` | 视觉兜底：OpenCV 多尺度模板匹配 + VLM（OpenAI 兼容视觉接口） |
| `pick_locate.py` | 定位候选打分与选择（区域/最佳候选） |
| `candidates.py` | `click_first` 候选池展开 |
| `landing.py` | 落地判定（操作后是否真的到达目标页） |
| `knowledge.py` | 元素知识库：成功刷新 `last_ok`、失败计数、超阈值 `disabled`、备选轮换 |
| `reward_pick.py` | 收益候选识别（正则 + 启发式排名） |

### 3.4 真人化 / 反检测

| 文件 | 职责 |
|---|---|
| `human.py` | 作息窗口 `wake_window`、启动抖动、点击抖动、对数正态间隔采样（`mu=ln(mean)-σ²/2` 已做均值校正） |
| `human_trajectory.py` | 贝塞尔曲线 + Fitts 步数 + 慢-快-慢 + 末段高斯微颤 + 过冲回拉；滑块专用分支 |
| `sensor_sim.py` | 传感器序列生成（resting/walking/tapping/scrolling）+ 「死寂」检测 |
| `captcha_slider.py` | 滑块验证码：edge（单图边缘）/ diff（双图差分）/ vlm 三模式 + 拟人拖拽 + 重试 |
| `helper_proxy.py` | 设备 http 代理设置/清除/状态 + IP 策略建议（不内置 hook） |

### 3.5 记账 / 证据 / 其他

| 文件 | 职责 |
|---|---|
| `recorder.py` | SQLite 记账 + 日志；批量提交（仅 commit 成功才清 pending） |
| `sign_evidence.py` | 签到证据（截图/记录） |
| `ui_page.py` | UI 页面片段小工具 |
| `gui.py` / `run_gui.bat` | 旧 Tk 图形入口（非主链路） |

### 3.6 WebUI（管理端）

| 文件 | 职责 |
|---|---|
| `webui/server.py` | HTTP 服务：路由、静态资源、`PAGES` 页面白名单、一次性 token 注入 |
| `webui/data.py` | 数据聚合：overview / apps / earnings / device 状态 |
| `webui/jobs.py` | 任务调度：`JobManager` 同时只允许 1 个运行中任务；`create_exclusive` 原子「判空闲+登记」 |
| `webui/routes_yaml.py` | YAML 在线编辑 API：读/写/校验/回滚、app 名安全校验 |
| `webui/static/` | 前端：`index.html`（8 个视图 shell）、`app.js`、`app.css`、`yaml_editor.js/css` |

### 3.7 辅助目录

| 目录 | 内容 |
|---|---|
| `tests/` | 60 个测试（免设备逻辑 + 部分需 config） |
| `devtools/` | 校准/探针/回归工具（`calibrate.py`、`verify_live.py`、`probe_*.py`、`apply_*.py`、`check_secrets.py`）+ `calib/` 历史报告 |
| `images/` | 图像锚点模板（按 App 分目录，PNG） |
| `data/` | 运行数据（`records.db`、日志；gitignore） |
| `_backup_pre_fix/` | 配置备份 + **parity 基线** `config.yaml.split_baseline`（被 git 跟踪，仅含 apps 段） |
| `dispatch/` `review/` `handoff/` `handover/` | 派单卡、代码审查包、历史交接（过程产物） |
| `temp/` | 临时脚本/截图/抽帧（可清理，不影响运行） |

## 4. 铁律（违反=返工）

1. **密钥**：`config.yaml` 的 `vision.vlm.api_key` 是真实密钥且该文件已 gitignore；任何提交前跑 `devtools/check_secrets.py`。配置类文档/基线**只写 apps 段**，禁止把整份 config 抄进基线（曾把 api_key 抄进 `split_baseline`，被 pre-commit 拦截）。
2. **无行号引用**：`behavior_runner.py` 等已删除写死行号（会失效误导），改造时按职责定位。
3. **执行层只认 `step.raw`**：`step_model.py` 只是编译层，改造不得改变老 YAML 的行为。
4. **改 `config/apps/*.yaml` 后必须刷新 parity 基线**并使 `tests/test_config_split_parity.py` 1/1。
5. **资金类（提现）需二次确认**：`money_behaviors` 由配置驱动，不得硬编码行为名单。
6. **不加无界内存/数据增长**：日志、队列、历史列表都要有上限。
7. **测试只跑相关项**，用例数实测回写；未做成写 `failed + 原因`，禁止静默吞错。

## 5. 本套文档如何使用

| 文件 | 内容 |
|---|---|
| `00-总览与使用说明.md` | 本文：定位、文件职责、铁律 |
| `01-架构与数据流.md` | 分层、门面组合、Step 编译、执行数据流、关键代码形态 |
| `02-配置规范.md` | 13 个顶层节、app YAML 完整示例、动作原语表、常见坑 |
| `03-WebUI与运行.md` | 启动方式、8 视图、API 契约、任务调度、端口问题 |
| `04-状态待办与拆项.md` | 已完成、已知问题、待办、**可拆分小项目** |

若网页 AI 上下文有限：**只粘 00 + 你要改的那一册**。若需一次性全量上下文，按 00→04 顺序拼接。


---

# 01 · 架构与数据流（自包含）

## 1. 分层

```
CLI / WebUI  ──────────────►  入口层
    │  main.py（CLI）  /  webui/server.py + jobs.py（HTTP + 任务调度）
    ▼
意图与配置   ──────────────►  语义层
    │  nlu.py（自然语言→intent）  config_loader.py（config.yaml + config/apps/*.yaml 拼接）
    ▼
执行引擎门面  ─────────────►  执行层
    │  Executor(DeviceSession, Locator, BehaviorRunner)   ← 多继承组合
    ▼
设备/定位/视觉  ───────────►  能力层
    │  adb_backend.py（裸 ADB）  uiautomator2（主）  vision.py  knowledge.py  pick_locate.py
    ▼
设备（真机/模拟器）  ──────►  物理层
```

## 2. 执行引擎门面（关键设计）

`executor.py` 不是「大而全的 1000 行类」，而是 **~160 行门面**，用**多重继承**组合三个 mixin：

```python
class Executor(DeviceSession, Locator, BehaviorRunner):
    def __init__(self, serial, human, recorder, dry_run=False, config=None, base_dir=None):
        ...
        # 组装 mixin 状态：d（设备）、vision、knowledge、captcha、
        #               _variant_last（上次变体）、_diversify_prob（多样化概率）
        self.backend = str((config or {}).get("device", {}).get("backend", "u2") or "u2").strip().lower()
```

三个部件职责边界：

| mixin | 文件 | 负责 | 不负责 |
|---|---|---|---|
| `DeviceSession` | `device_session.py` | 连接/断连、启停 App、等页面稳定、顶层复位、安全 dump | 定位、点击 |
| `Locator` | `locator.py` | `_locate` / `_pick_best`、知识库候选、视觉兜底、A3 共享件 | 业务流程 |
| `BehaviorRunner` | `behavior_runner.py` | 顶层流程、分派、`any_of`/`random` 分支、全部 `_step_*`、收益识别 | 设备连接 |

**关键约定（改代码必须遵守）**：方法体内通过 `self._xxx` 调用；因为三个 mixin 都有同名可覆盖入口，**测试对 Executor 实例打桩**（如 `ex._locate = fake`）会按 MRO 优先于部件类实现。**不要把 `self._xxx()` 改成 `Locator._xxx(self, ...)` 这样的显式调用**，会打断测试桩与子类覆盖。

对外兼容再导出：`StepError` / `LocateResult` / `_parse_sel` 由 `executor.py` re-export，测试依赖，不可删除。

## 3. BehaviorRunner 内部结构（职责目录，无行号）

```
顶层流程   run_app_flow / _resolve / _pick_variant / _run_actions
分派       _exec_step / _dispatch_step / _dispatch_probe / _run_kind / _dispatch
分支       _step_any_of / _step_random
点击       _step_click（统一，by=text/id/desc）
           + _step_click_text / _step_click_id / _step_click_desc（别名）
           + _step_click_point / _step_click_first
滚动滑动   _step_swipe（natural:true 尊重 from/to）/ _step_swipe_natural / _step_scroll_to
导航       _step_back / _step_home / _step_dismiss_popups
等待拟人   _step_wait / _step_think
收益断言   _step_reward / _reward_candidates / _step_ensure
验证码     _step_captcha
内部件     _locate_with_kb / _kb_candidates / _expand_kb_pool
           / _click_tracked / _click_obj / _verify_landing / _vision_or_miss
```

要点：
- `_step_click` 是 2026-10-25 合并后的**唯一统一点击入口**，其余三个 `_step_click_text/id/desc` 是别名薄包装。
- `_step_any_of` 读 `choices`（不是 `branches`）；缺 `choices` 会 WARN。
- 所有 step 返回值语义：`True`=成功/已执行，`False`=未命中；`optional: true` 的失败不中断整条行为。

## 4. Step 编译层（step_model.py）

**目的**：给 v1（只有 `type`）与 v2（`action`/`flow`/`macro`）两种写法提供统一、不可变的 `Step` 对象，用于**编译期 lint、dry-run 语义投影、静态校验**；但**执行仍用 `step.raw`**，所以老配置零改动、行为零变化。

三种点击形态（设计约定）：

| 形态 | 写法 | 说明 |
|---|---|---|
| ① 元素点击 | `action: click` + `target: {by: text/id/desc}` | 控件树定位 |
| ② 视觉锚+兜底 | `action: click` + `target: {by: image/vision, fallback: (x,y)}` | 图像模板/VLM，失败回退坐标 |
| ③ 纯坐标 | `action: tap` + `point: (x,y)` | 最终兜底 |

## 5. 端到端数据流

```
用户输入（CLI --task 或 WebUI 勾选）
   │
   ├─ nlu.py：关键词 → intents（sign / watch / withdraw …）
   │
   ├─ config_loader.load_config()：
   │     config.yaml（device/human/vision/...） + config/apps/*.yaml（35 个 app）
   │     → apps[]（每个含 name/package/aliases/intent_map/behaviors）
   │
   ├─ Executor.run_app_flow(app_cfg, intents)：
   │     1) _open_app_timed：冷启动/前台校验/等 splash 消失（带超时与重启）
   │     2) for intent in intents：
   │          _resolve → 行为模板（intent_map 或同名 behavior）
   │          _pick_variant → diversify 多模板随机（防序列 replay）
   │          _run_actions → 逐 step 执行
   │              _step_* → Locator._locate（先知识库 → 静态 selector → 视觉兜底）
   │                       → 命中则点击（带 human 抖动/轨迹）
   │                       → _step_reward 识别页面数字并写账
   │
   └─ recorder：SQLite 记录（app/event/level/时间/金额）+ 日志；批量 commit
```

## 6. 配置双源机制（易错点）

- `config.yaml` 的 `apps: []` 通常是**空列表**，真实 app 来自 `apps_dir: config/apps`，由 `config_loader.load_config()` 拼接。
- `config.example.yaml` 里**内联了示例 apps**（模板用途），与实际拆分源是两处，**改配置以 `config/apps/*.yaml` 为准**。
- 一致性护栏：`tests/test_config_split_parity.py` 把「当前 apps」与基线 `_backup_pre_fix/config.yaml.split_baseline` 深比较；**任何 apps 变更都要刷新基线**（只写 apps 段）。

## 7. 错误与失败语义

| 位置 | 语义 |
|---|---|
| `adb_backend._run` | 失败返回 `None`（**绝不返回错误字符串**）；`""` = 成功但无输出 |
| `adb_backend._retry` | 全失败返回 `None`，异常详情只 print |
| `_step_*` | 返回 bool；`optional` 失败不中断 |
| `Locator._locate` | 返回 `LocateResult`（hit/fail + 来源：kb/selector/vision） |
| `recorder._flush_ops` | commit 成功才清 `_pending`；失败保留待重试（不丢数据） |
| `JobManager.create_exclusive` | 已有运行中任务抛 `JobBusy` → HTTP 409 |

## 8. 扩展点（新增能力应改哪里）

| 想加 | 改 | 配套 |
|---|---|---|
| 新动作原语 | `behavior_runner._step_xxx` + `_dispatch_step` 分派表 | `step_model.py` 校验 + 单测 |
| 新定位方式 | `locator.py` + `pick_locate.py` | `vision.py` / `knowledge.py` |
| 新真人化维度 | `human.py` / `human_trajectory.py` | `config.yaml` 对应节 |
| 新 WebUI 页面 | `webui/static/index.html` 加 `section.view` + `app.js` 的 `VIEWS` 数组 | `webui/server.py` 的 `PAGES` 白名单 |
| 新 App | `config/apps/NN_x.yaml` | `images/` 锚点图 + parity 基线刷新 |


---

# 02 · 配置规范（自包含）

> 目标：让网页 AI 能在**不打开仓库**的情况下，读懂、修改、新增 App 配置。
> 配置权威源是 `config/apps/*.yaml`；`config.yaml` 提供全局节。

## 1. `config.yaml` 的 13 个顶层节

| 节 | 作用 | 关键子项 |
|---|---|---|
| `device` | 设备 | `serial`（如 `127.0.0.1:5555` / `192.168.1.100:5555`）、`screen_w`、`screen_h`、`backend`（`u2` 默认 / `adb`） |
| `human` | 真人化 | `enabled`、`wake_window{start,end}`（作息窗口）、`run_jitter_seconds`、`delay_between_actions`、`delay_after_open`、`think_delay`、`swipe_duration`、`tap_jitter_px`、`wander_probability`、`scroll_probability`、`use_swipe_home` |
| `trajectory` | 手势曲线 | `enabled`、`px_per_step`、`perpendicular_ratio`、`jitter_sigma`、`overshoot_prob` 等 |
| `vision` | 视觉兜底 | `enabled`、`template_dir`、`template_threshold`、`template_scales`、`vlm{enabled,base_url,api_key,model,timeout}` |
| `knowledge` | 元素知识库 | `file`（默认 `element_knowledge.yaml`）、`fail_threshold`（默认 3 次自动停用） |
| `diversify` | 行为多样化 | `variant_prob`（默认 0.8，按概率在多套候选模板间随机） |
| `popups` | 全局弹窗 | 文案列表 + `close_points`（坐标兜底，如 `(983,456)`） |
| `timeouts` | 超时 | 页面/点击/等待各类默认超时 |
| `anti_detection` | 反检测开关 | 各类拟人/传感器/代理开关 |
| `captcha` | 滑块验证码 | `enabled`、`slider.gap.mode`（`edge`/`diff`/`vlm`）、`retry_times`、`background_template` |
| `apps_dir` | apps 拆分目录 | 默认 `config/apps` |
| `apps` | 内联 app 列表 | 通常为 `[]`（为空时全部来自 apps_dir） |
| `money_behaviors` | 资金类行为名单 | 配置驱动（提现等），用于强制二次确认，不硬编码 |

**注意**：`device.serial` 与 `vision.vlm.api_key` 是真实值、`config.yaml` 已 gitignore。分享/提交时用 `config.example.yaml` 的占位写法。

## 2. App 配置（`config/apps/NN_名称.yaml`）完整结构

```yaml
name: 一淘                      # 展示名（自然语言匹配用）
package: com.taobao.etao        # 真实包名：adb shell pm list packages | grep xxx
aliases:                        # 自然语言里可能出现的叫法
- 一淘
launch_reset: true              # 每次先冷启动回首页（防恢复脏子页；可选，默认 false）
intent_map:                     # 意图 → 行为 id 的绑定（可选，缺省同名）
  sign: sign
  watch: watch
  withdraw: withdraw
behaviors:
  sign:
  - type: any_of                # 分支：多路径任一命中即算成功
    optional: true
    choices:                    # ★ 字段名是 choices，不是 branches
    - - type: click_first       # 路径 1：直接找签到入口
        candidates:
        - type: text
          value: 签到领钱
        - type: text
          value: 签到
        - type: desc
          value: 签到
        timeout: 8
        optional: false
    - - type: click_point       # 路径 2：先点「我的」再找签到
        x: 0.9
        y: 0.915
        optional: true
        vision: false
      - type: think
      - type: click_first
        candidates:
        - type: text
          value: 签到
        timeout: 8
        optional: false
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 领取
    - type: text
      value: 领金币
    timeout: 6
    optional: true
  watch:
  - type: click_first
    candidates:
    - type: text
      value: 看视频领金币
    timeout: 8
    optional: true
  - type: swipe
    from: [0.5, 0.7]
    to: [0.5, 0.3]
    duration: 0.8
    natural: true
  - type: wait
    seconds: 3
  withdraw:
  - type: click_text
    text: 提现
    timeout: 6
    optional: true
  - type: reward
    pattern: 可提现(?P<amount>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>元)
    unit: 元
    name: 可提现余额
```

## 3. 动作原语（step `type` 全表）

| type | 参数 | 说明 |
|---|---|---|
| `wait` | `seconds` | 固定等待 |
| `think` | — | 随机「思考」停留 |
| `click_text` | `text, timeout` | 按文本（模糊/子串）定位并点 |
| `click_id` | `res_id, timeout` | 按 resource-id 点 |
| `click_desc` | `desc, timeout` | 按 content-desc 点 |
| `click_point` | `x, y`（0~1 比例或像素） | 坐标点；支持 `vision`/`vlm_prompt` 兜底 |
| `click_first` | `candidates: [{type,value}]` | 点第一个出现的候选（推荐，抗文案变化） |
| `click_obj` | 目标对象 | 点击已定位对象（bounds 中心） |
| `swipe` | `from,to,duration,natural,straight` | 滑动；`natural:true` 走真人轨迹 |
| `swipe_natural` | `from,to` 可省 | 显式自然滑动（轨迹交 human_trajectory） |
| `scroll_to` | `text/desc, max_pages` | 翻页找目标并点 |
| `back` / `home` | — | 返回 / 回桌面 |
| `reward` | `pattern,unit,name` | 正则提取页面收益并记账 |
| `ensure` | `text, exists, timeout` | 关键页校验 |
| `captcha` | `mode: slider, optional` | 检测并求解滑块 |
| `any_of` | `choices: [[step...], [step...]]` | 多路径分支，任一成功即可 |
| `random` | `choices`（dict 或 list 混排） | 随机挑一支（行为序列多样化） |
| `click_first` 的候选 type | `text` / `desc` / `id` | 候选匹配方式 |

**step 通用字段**：`optional`（失败不中断）、`timeout`、`desc`（注释/日志）、`expect`（成功校验：`text_any`/`retry`/`settle`）、`images`（模板锚点，相对 `images/` 或 `template_dir`）、`vlm_prompt`。

## 4. 常见坑（历史事故，务必避开）

1. **`any_of` 的字段是 `choices`**：写成 `branches` 会导致 WebUI 显示 0 路、且行为校验 WARN「缺少 choices」。
2. **空 `desc: ""`**：判断是否存在必须用 `act.get("desc")`，不能用 `"desc" in act`（空串也会命中，导致定位空文本）。
3. **`click_point` 用 0~1 比例**更稳（换分辨率不失效）；视频/截图目测像素须按 `真机宽/视频宽` 换算（本项目视频 720×1560 → 真机 1080×2340 是 ×1.5）。
4. **`launch_reset: true`** 用于「热启动会恢复上次脏子页」的 App（如一淘），否则候选不出现。
5. **弹窗**：优先用 `popups` 全局文案 + `close_points` 坐标兜底；新出现的弹窗先补文案再补坐标。
6. **子串匹配**：`click_text`/`find` 默认是**子串**（节点文本带后缀时必需），不是全等；需要全等用 `exact` 语义。
7. **`optional: false`** 会让该步失败中断整条行为；入口类步骤建议 `optional: false`，领取类建议 `optional: true`。
8. **不要写死行号**引用代码。

## 5. 改配置后的必做检查

```bash
# 1) 解析合法性（35 个 app 应能全部加载）
python -c "import sys;sys.path.insert(0,'.');from config_loader import load_config;print(len(load_config('config.yaml')['apps']))"

# 2) 刷新 parity 基线（★ 只写 apps 段，禁止整份 config）
python -c "import sys;sys.path.insert(0,'.');import yaml;from config_loader import load_config;apps=load_config('config.yaml')['apps'];open('_backup_pre_fix/config.yaml.split_baseline','w',encoding='utf-8').write(yaml.safe_dump({'apps':apps},allow_unicode=True,sort_keys=False))"

# 3) 对拍必须 1/1
python tests/test_config_split_parity.py

# 4) 密钥扫描
python devtools/check_secrets.py --staged
```

## 6. 配置质量护栏（测试会拦什么）

| 测试 | 拦什么 |
|---|---|
| `test_config_split_parity` | 拆分前后 apps 深比较不一致 / 基线缺失（SKIP 已改为显式失败） |
| `test_webui` 的 `t_verifier_coverage...` | 行为缺可校验锚点（`unverifiable > 0` 会 FAIL） |
| `test_webui` 的 `t_overview_exposes_frontend_contract` | 某 app 的 sign 无锚点（`levels: 0`） |
| `test_step_model` | 顶层步骤数基线（386）/ 死 optional WARN 数基线（117）—— 有意变更需同步基线 |
| `test_webui_yaml_api` | app 名安全校验（`/`、`\`、`..`、`\x00`）、YAML 读写回滚语义 |


---

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


---

# 04 · 状态、待办与可拆分小项目（自包含）

## 1. 已完成（近期，按提交时间倒序）

| 事项 | 证据 | 说明 |
|---|---|---|
| 一淘 sign 入口校准 | commit `6248a6e` | 视频 1106 人工演示确认：一淘顶部导航「签到领钱」→ 签到页；sign 首候选改为「签到领钱」（原「签到」子串易误点） |
| 12 项 P1/P2 缺陷修复 | commit `19b3b8c` + `FIX-P1P2-2026-11-05-REPORT.md` | 见下表「已修缺陷」 |
| config 拆分基线刷新 | `3f53872`、`6248a6e` | 仅 apps 段，35 app，parity 1/1，0 密钥 |
| WebUI YAML 并入 shell tab | `acd71f5` | `#/yaml` 与其它视图同页切换；`yaml_editor.js` IIFE 化 |

**已修缺陷（12 项，全部经独立 diff 核实）**：

| # | 项 | 修复要点 |
|---|---|---|
| P1-1 | app.js any_of 分支数恒 0 | `o.branches` → `o.choices` |
| P1-2 | adb 错误当成功 | `_run/_retry` 建立 `None=失败` 契约；tap/swipe/back/cold_start/app_start 可判定 |
| P2-3 | recorder 吞 commit 失败 | 仅 commit 成功才清 `_pending` |
| P2-4 | YAML 回滚误报成功 | 回滚返回 `ok:false`（前端按 `ok`/`action` 双判） |
| P2-5 | 启动任务非原子 | `JobManager.create_exclusive`（同锁判空闲+登记），并发 → 409 |
| P2-6 | 延迟均值偏高 10~32% | lognormal `mu = ln(mean) − σ²/2` |
| P2-7 | find 子串误匹配 | 加 `exact` 开关，默认子串语义不变（设计权衡，非 bug） |
| P2-8 | 空 desc 误判 | `if act.get("desc")` |
| P2-9 | parity SKIP 静默通过 | SKIP → `AssertionError`；刷新命令只写 apps 段 |
| P3-10 | app 名未查 `\x00` | 并入 `/`、`\`、`..` 校验 |
| P3-11 | 页面白名单硬编码 | 收敛为模块级 `PAGES` |
| P3-12 | backend 未规范化 | `str(...).strip().lower()` |

## 2. 已知遗留（勿误判为新 bug）

| 项 | 性质 | 说明 |
|---|---|---|
| `test_webui` 2 个 FAIL | **基线既有，非回归** | `t_overview_exposes_frontend_contract`（某 app sign `levels:0` 无锚点）、`t_verifier_coverage_uses_verifier_rule`（`unverifiable:2`）。均为**配置内容**问题。已用基线 `3f53872` 实测对比：失败集逐条同名，0 新增失败。 |
| 快手 sign | 待重校 | 11.11 改版：任务由「连续签到14天」→「前3天打卡得金币 最高1264」，「去打卡」钮 (955,1350) 打开空白 WebView；`[立即签到]` 旧路径过时 |
| 拼多多 / 京东 / 微博 sign | 待重校 | 需**未签态窗口**（次日首次运行）实测 |
| `temp/` 1728 文件 | 非核心 | 抽帧/截图/临时脚本，可清理，不影响运行 |
| `README.md` | 过时 | 仍是早期单机版介绍（main/nlu/executor 简版），未覆盖 WebUI/step_model/config 拆分；以本套文档为准 |

## 3. 待办（按优先级）

| 优先级 | 任务 | 验收 |
|---|---|---|
| P1 | 快手 sign 按「前3天打卡得金币」重校（未签态窗口） | `test` 相关通过 + 真机签到成功 |
| P1 | 拼多多/京东/微博 sign 未签态重校 | 同上 |
| P2 | 修 2 个基线 FAIL（某 app sign 缺锚点、2 个不可校验行为） | `test_webui` 34/34 |
| P2 | 更新 `README.md` 至当前架构（或改为指向本交接目录） | 文档与代码一致 |
| P3 | 清理 `temp/`（1728 文件）与旧 `_backup_pre_fix/*.pre_*` | 目录体积下降，parity 仍 1/1 |
| P3 | WebUI 补「yaml 编辑」的测试覆盖（现有 static/API 测试可加强） | 新增用例 |

## 4. 可拆分小项目（按耦合度评估）

结论先行：这个仓库**可以拆成 11 个逻辑子项目**，但只有 **6 个具备「独立成库/独立交付」价值**（下表「可独立」列 ★★★ 以上）；`executor` 三件套**不要拆**（互相调用 + 测试打桩依赖 MRO）。

| # | 子项目 | 包含文件 | 对外接口 | 可独立 | 拆分风险 |
|---|---|---|---|---|---|
| A | **核心执行引擎** | `executor.py` + `device_session.py` + `locator.py` + `behavior_runner.py` + `step_model.py` | `Executor(serial, human, recorder, config)` / `run_app_flow` | ★☆☆（**不建议拆**） | 三件套通过 `self._xxx` 互相调用，测试对实例打桩依赖 MRO；拆开会打断覆盖机制 |
| B | **定位与视觉** | `locator.py`(部分) + `vision.py` + `pick_locate.py` + `candidates.py` + `landing.py` + `knowledge.py` | `locate(by, value)` / `VisionLocator.match()` / `KnowledgeBase` | ★★☆ | `locator.py` 与 BehaviorRunner 强耦合；但 `vision`/`knowledge`/`pick_locate` 可先独立 |
| C | **设备与 ADB 层** | `device_session.py` + `adb_backend.py` + `helper_proxy.py` | `connect()` / `dump()` / `shell()` / `set_proxy()` | ★★★ | 低；`adb_backend` 已建立 `None=失败` 契约，可独立成库 |
| D | **真人化与反检测** | `human.py` + `human_trajectory.py` + `sensor_sim.py` + `captcha_slider.py` | `Human.delay()` / `trajectory(...)` / `SensorProfile` / `SliderCaptchaSolver` | ★★★★（**最易拆，可单独开源**） | 低；只依赖 config 数值与设备 touch 接口 |
| E | **配置系统** | `config_loader.py` + `miniyaml.py` + `config/apps/*.yaml` + parity 基线 | `load_config(path)` | ★★★ | 低；但 parity 基线依赖仓库内 `_backup_pre_fix` |
| F | **记账与收益** | `recorder.py` + `reward_pick.py` + `sign_evidence.py` | `Recorder.record()` / `rank_reward_candidates()` | ★★★ | 低；`recorder` 可用 sqlite 独立 |
| G | **WebUI 后端** | `webui/server.py` + `data.py` + `jobs.py` + `routes_yaml.py` | HTTP API（见 03） | ★★★★ | 低；只依赖 config/recorder/executor 的**稳定接口** |
| H | **WebUI 前端** | `webui/static/*` | 静态资源 | ★★★★ | 低；纯前端，可独立部署（需 API 契约） |
| I | **测试与质量护栏** | `tests/`（60 个） | pytest 用例 | ★★★ | 中；大量用例直接 import 根模块，拆分后 import 路径会变 |
| J | **校准与探针工具链** | `devtools/`（calibrate/verify_live/probe_*/apply_*/check_secrets）+ `calib/` 报告 | CLI | ★★☆ | 中；强依赖真机与 App 现场 |
| K | **文档与交接** | `docs/` + `handover/` + `handoff/` + `dispatch/` + `review/` | Markdown | ★★★★★ | 无；纯文档 |

### 推荐拆分顺序（若要做）

1. **D 真人化包**（`human_trajectory` + `sensor_sim` + `captcha_slider` + `human`）→ 独立 PyPI 包 `android-humanize`。理由：零业务耦合、可复用性最高、有公开参考实现（ghost-cursor/pyclick）。
2. **C 设备层**（`adb_backend` + `device_session` 的 dump/connect）→ `adb-lite`。
3. **E 配置系统**（`config_loader` + `miniyaml`）→ `yaml-config-loader`（需带上 apps 目录约定）。
4. **F 记账**（`recorder` + `reward_pick`）→ 可视化收益库。
5. **H+G WebUI** 作为**独立管理面板**，通过 HTTP 契约对接任意后端（不打包执行引擎）。

### 不建议拆的部分

- **A 执行引擎三件套**：`Executor(DeviceSession, Locator, BehaviorRunner)` 的多继承 + `self._xxx` 可覆盖入口是测试打桩的基础，拆开会引发大面积测试失效。
- **B 中的 `locator.py`**：与 BehaviorRunner 的定位→点击→落地校验链路交织，单独拆收益低。

## 5. 给接手 AI 的建议切入点

1. 先读 `00`（职责与铁律）→ `02`（配置）→ `04`（待办）。
2. 若任务是**改配置/加 App**：只需 `02`，改完按「5. 改配置后的必做检查」四步。
3. 若任务是**改代码**：读 `01`（架构）→ 定位到文件 → 注意「扩展点」与「错误语义」两节。
4. 若任务是**评审**：重点看 `01` 的失败语义、`03` 的并发与白名单、`02` 的常见坑；这三处历史事故最多。
5. **不要**要求必须真机才能推进的结论；涉及坐标校准时，明确标注「需真机实测」，给出换算方法（视频宽→真机宽的比例）。


---

