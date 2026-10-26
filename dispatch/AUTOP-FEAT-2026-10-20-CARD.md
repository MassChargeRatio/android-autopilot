# 派单卡 AUTOP-FEAT-2026-10-20：两个新功能（全局弹窗处理 + 反机器人检测）

> 时间：2026-10-20 19:30 ｜ 派单方：WorkBuddy AI（Host）
> 项目根：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
> 前置状态（Host 已实测，直接用，不必重复验证）：
> - 重构四批 A/B/C/D 已完成，Host 实跑复核 `pytest tests/ -q` → **212 passed**、dry-run EXIT=0
> - 当前引擎结构：`executor.py`(103 行门面) = DeviceSession(device_session.py 186) + Locator(locator.py 235) + BehaviorRunner(behavior_runner.py 574)
> - `behavior_runner.py` `_run_kind` 分派表在 L170-196，已支持 16 种 step 原语（back/wait/think/click_point/click_first/any_of…）；`_step_back` 在 L500（`d.press("back")`）
> - 可复用旧实现：`devtools/calibrate.py` L307 `dismiss_popups()` + L43 `POPUP_TEXTS`（按文案点弹窗，**未用 BACK**——注释「交接文档坑5」）
> - 拟人化底座：`human.py`（Human class L19、think L147，已有对数正态延迟/贝塞尔轨迹/点击抖动/wander）
> - 设备：真机 192.168.1.54:5555 在线；`tools/platform-tools/adb.exe` 在仓库内（adbkit 已兜底解析）
> - 本项目红线（不可违反）：资金类操作强制二次确认；无证据不报 confirmed；每步开工前备份 `_backup_pre_fix/`；不 git push

## 用户原话（需求真源）

> 「对于所有app，遇到各种不是程序自身引起的弹窗，都可以看到就关闭，甚至直接关闭app重新开始。」
> 「关闭弹窗的方式还可以尝试系统的回退键。」
> 「如果遇到不是主动观看的广告，也可以跳过。」
> 「别让app识别到各种调试程序、控制软件的运行，防止被判断为机器人。」

---

## F1：全局弹窗处理（dismiss_popups 原语）

### F1.1 设计（Host 已定，实现不得偏离）

**语义**：「看到就关」——App 自身弹出来的、非程序触发的干扰弹窗。在**每个行为（behavior）开始前**自动执行一轮弹窗清扫（不是让 34 份配置各自手写步骤）。

**新 step 原语** `dismiss_popups`：
- 在 `behavior_runner.py` `_run_kind` 分派表注册 + 实现 `_step_dismiss_popups`；
- 参数（全部有默认值，配置可调）：
  - `max_rounds`（默认 3）：一轮清扫=点一个弹窗→等一下→重新 dump→再找，直到本屏无弹窗或达上限；
  - `texts`（默认全局文案表，见 F1.2）：按序精确匹配（`label == txt` 且 clickable 优先）；
  - `ids`（默认全局关闭按钮 id 表）：如各 App 的 `iv_close` 类（从现有配置 grep `res_id` 收集一轮常见关闭 id 填进去）；
  - `corner_fallback`（默认 true）：无文案命中但屏上有「弹窗特征」（深色蒙层/居中卡片无法归因）时，点右上角 `(0.93w, 0.11h)` 附近的关闭位（开屏广告实测锚点可参照 `devtools/calib/uiprobe/` 微博案例）；
  - `back_key`（默认 true，**用户新要求**）：以上全未命中时，最后尝试 `d.press("back")`。

**F1.2 文案表与黑名单（关键，防误伤）**
- 默认文案表（关）：`关闭 / 跳过 / 暂不 / 暂不开启 / 以后再说 / 稍后再说 / 我知道了 / 知道了 / 不再提醒 / 下次再说 / 暂不升级 / 取消（仅当弹窗为 App 官方信息类时）`。
  - ⚠️ `calibrate.py` 的 POPUP_TEXTS 含「允许/仅在使用中允许/始终允许」——**不要**照搬进关弹窗表：权限授予类点「允许」会扩大权限面，由人决定。
- 黑名单文案（命中任一 → **本轮立即停止清扫，且禁止按 BACK**）：`提现 / 确认提现 / 立即提现 / 支付 / 确认支付 / 付款 / 银行卡 / 实名 / 验证码 / 身份验证`。
  理由：资金类弹窗按 BACK 消化=跳过用户确认，踩项目资金红线；这类页面应保留并交由 reward/告警记录。
- 黑名单 route：出现黑名单文案时，写一条 recorder 日志（app 名 + 文案），清扫函数返回 `blocked`，调用方记 WARN 但不失败行为。

**F1.3 广告跳过语义（用户新要求：「不是主动观看的广告，也可以跳过」）**
- 定义「被动广告」：开屏广告 / 插屏广告 / 弹窗广告，特征=含「跳过/跳过广告/关闭广告/skip ad」或 X 按钮 + 全屏/半屏蒙层。
- 规则：
  - 当前行为 **不是 watch/看视频类** → 遇到被动广告一律按弹窗清扫规则跳过（这即用户说的「不是主动观看的广告，也可以跳过」）；
  - 当前行为 **是 watch 类**（看视频领金币流程）→ **不得**清扫正在观看的广告页面（关了就领不到奖励）。实现：`dismiss_popups` 入参带 `protect_ad: true/false`，由 `run_app_flow` 按当前 intent 注入（intent==watch 或 behavior id 含 watch → protect_ad=true）。
- 「直接关闭 app 重新开始」**本期不做**（风险高：重开=冷启动 20s+，且重启后仍可能再弹；如清扫 3 轮仍失败，记 BLOCKED 由上层决定）。

### F1.4 配置接入

- `config.yaml` 新增全局段（经 `config_loader.py` 读取，注意 loader 已有 7 只读方+6 写回工具，**新字段不得破坏既有结构**）：
  ```yaml
  popups:
    enabled: true
    max_rounds: 3
    back_key: true
    corner_fallback: true
    protect_ad_in_watch: true
    texts: [上面的默认文案表]
    blacklist: [上面的黑名单]
  ```
- 接入点：`behavior_runner.run_app_flow`（L46）每个 behavior 首步执行前，若 `popups.enabled` → 跑一轮 `dismiss_popups`（existing behavior 配置无需改动即生效；App 级覆盖本期可不做，留扩展位）。
- `main.py --dry-run` 应能在计划预览里看到清扫步（可选：仅日志）。

### F1.5 测试（tests/test_dismiss_popups.py，新增）

用现有 tests 的假 device 打桩风格（参考 test_locate_pick 的 `_mk`）。必须覆盖：
1. 文案精确命中优先（`关闭` 在多个含「闭」字节点中被唯一选中）；
2. 黑名单熔断：页面含「确认提现」时 → 返回 blocked、**未调用 press("back")**（断言 back 计数=0）；
3. watch 保护：`protect_ad=true` 时含「跳过」的广告页不得被点；
4. `back_key` 兜底顺序：文案未命中→corner 未命中→press("back") 恰好调 1 次；
5. 多轮：第一轮点掉「暂不」后第二轮出现「我知道了」→两轮都被点掉（max_rounds=3）；
6. 全未命中：返回 False，行为正常继续（不能抛异常炸流程）。

### F1.6 验收

- `pytest tests/ -q` 全绿（212 + 新增，数一下报数）；
- 真机冒烟（设备在线时）：微博启动（有开屏广告）跑一次 `main.py --app 微博移动版 --task 早起打卡` 观察日志出现清扫/跳过记录；设备不可用则记 BLOCKED，**重试不超过 3 次**；
- `python main.py --dry-run --app 趣头条 --task 签到并提现` EXIT=0；
- 回滚点：`_backup_pre_fix/behavior_runner.py.pre_F1_<ts>` 等。

---

## F2：反机器人检测（反检测能力 + 诚实边界文档）

### F2.1 先写威胁面文档 `docs/ANTI_DETECTION.md`（Host 验收重点：**不许过度承诺**）

逐项列：信号名 → 检测方可见性（adb/u2 层）→ 本项目现状 → 可缓解/不可缓解 → 具体动作。至少覆盖：
- 开发者选项 / USB 无线调试开启（`ADB_ENABLED`、`service.adb.tcp.port`）：App 可读 → **不可完全隐藏**，只能降低同时可观测的相关性（如错峰、短会话）；
- 已知自动化包名/服务（uiautomator2 server、`com.github.uiautomator` 等）：部分 App 会扫包列表 → 不可隐藏 server 本身，缓解=缩短 server 暴露时长（用完即停 `d.uiautomator.stop()`?? 需实测该 API 在注入式 u2 下是否可用，不可用则如实写不可行）；
- 时序规律：固定间隔、固定顺序、全天均匀分布 → **可缓解**（随机化）；
- 输入模式：无误触、无回退、无乱看、坐标过于居中 → **可缓解**（拟人化）；
- 设备农场特征：机型/分辨率/语言/时区单一 → 本项目单机 → 不可缓解（文档说明）；
- 验证码/风控命中后的应对：触发即冷却（见 F2.2），**不许**尝试破解风控。

### F2.2 可实现层（human.py + 配置）

- `human.py` 增强（保持既有随机配置化风格，seed 可复现）：
  1. 「误触-回退」：以 `mistake_prob`（默认 0.05）概率先点错位置再点回（增加输入熵）；
  2. 「乱逛」wander 检查现有 `wander_probability` 覆盖情况，不足则补：行为间隙以一定概率做无关滑动/停留；
  3. 「限流」：连续同类点击 N 次后强制插入一次长停（`cooldown_every`/`cooldown_seconds`，防机械节奏）；
  4. 遇验证码/captcha step 失败 → 会话级冷却 `cooldown_on_captcha`（默认 300s）后再继续，期间不重试猛点。
- `config.yaml` 新增全局段：
  ```yaml
  anti_detection:
    enabled: true
    mistake_prob: 0.05
    wander_probability: 0.10
    cooldown_every: 12
    cooldown_seconds: 20
    cooldown_on_captcha: 300
  ```
- 取值纪律：**所有概率类参数必须为可复现随机（seed）**，遵守 human.py 现有 seed 化设计，禁止 `random.random()` 裸调（monkeypatch 不动的写法不许引入）。

### F2.3 测试

- `tests/test_anti_detection.py`（新增）：seed 固定 → 误触发生次数可复现断言；cool-down 触发条件命中/不命中；captcha 冷却生效；不得破坏既有 human 测试（human seed 化有既有单测，先跑一遍确认基线绿）。
- 回归：`pytest tests/ -q` 全绿（数数报数）。

### F2.4 验收

- `docs/ANTI_DETECTION.md` 落盘，Host 会逐项核对「可缓解/不可缓解」标注是否诚实（过度承诺打回）；
- human 新能力单测绿 + 全量门禁绿；
- 不引入任何第三方改机/root/hook 框架（越界即打回）；
- 回滚点：`_backup_pre_fix/human.py.pre_F2_<ts>` 等。

---

## 执行顺序与纪律（不变）

1. **严格按 F1 → F2 顺序**（F1 有真机可验证锚点，先行）；每功能内：设计核对 → 备份 → 实现 → 测试 → 验证 → 立即落盘 PROGRESS。
2. **§5.15 硬性落盘节奏**（派单消息里同样带）：
   - 前 5 个动作内创建 `dispatch/AUTOP-FEAT-2026-10-20/PROGRESS.md`（骨架+待办即可）；
   - 每解决一个子问题立即覆盖写对应段；禁止攒到最后；
   - 工具调用预算约 300；到预算落盘「部分结论 + OPEN/BLOCKED」停步；
   - 不停在 requires_action；疑义写 PROGRESS.md 质疑记录段。
3. 每步开工前备份 `_backup_pre_fix/`（命名 `*.pre_F1_<ts>` / `*.pre_F2_<ts>`）；跑 pytest 前清 .venv 外 `__pycache__`（先 print 核对再删）。
4. **每步完成后立即 py_compile + 直跑相关测试**（B7 教训：编辑残留 SyntaxError）。
5. 不 git push；不碰计划外文件；不修改既有测试断言使其变绿（确需适配→在 PR 描述/进度里写清原因）。
6. 汇总格式：最终 PROGRESS 补「两功能终态 + 偏差说明 + 回滚点」表。

## 投递记录

- （待 Host 投递时填写：时间 / 投递前 marvis 状态 / cid / 首响摘要）
