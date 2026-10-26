# AUTOP-FEAT-2026-10-20 PROGRESS（Host 自执行 · marvis 投递失败后接管）

> 派单卡：`dispatch/AUTOP-FEAT-2026-10-20-CARD.md`
> 背景：marvis 网关 token 丢失无法派递，Host 按用户指示「派单不成功就自己执行任务」接管。
> 顺序纪律：F1 → F2；每步备份 `_backup_pre_fix/`；每步完成立即 py_compile + 跑测试。

## 状态总览

| 功能 | 状态 | 说明 |
|---|---|---|
| F1 全局弹窗清扫（dismiss_popups） | ✅ 完成，测试 13/13 绿 | 四级关闭顺序/黑名单熔断/watch 保护/extras 合并+整表替换均已实现；待真机冒烟（回归完成后补微博开屏广告场景） |
| F2 反机器人检测 | ✅ 完成，测试全绿 | docs/ANTI_DETECTION.md + human.py 增强（误触回退/限流/验证码冷却/乱逛扩展）+ anti_detection 配置段 + tests/test_anti_detection.py 9 例 |
| pytest tests/ -q 门禁 | ✅ 240 passed（venv，101s） | 含 F1 13 + F2 9 + miniyaml 6 新增 |
| dry-run EXIT=0 | ✅ 2026-10-21 04:41 / 05:18 双验 | `--dry-run --force --app 趣头条/米读小说 --task 签到` 均 EXIT=0；注意**不带 --force 会被作息窗口跳过**（07:30-23:00 外只打印跳过不执行），回归/验证需带 --force |
| 回归联动证据 | ✅ 海马畅听真机 | F1 黑名单熔断在真机正确触发（首页「提现」文案→停扫禁 BACK） |

## F2 完成记录（2026-10-21）

### 改动清单
- `human.py`：
  - 构造读 `anti_detection` 段：`mistake_prob`(0.05)/`cooldown_every`(12)/
    `cooldown_seconds`(20)/`cooldown_on_captcha`(300)/`wander_probability`(0.10，
    两段都缺省时) — 缺省 `enabled: true`，老配置经 `enabled: false` 零影响；
  - `tap(d,x,y)` 统一点击入口：限流长停（每 cooldown_every 次）+ 误触回退
    （±160px 内错点→愣神→正点，防真点歪改页）；
  - `captcha_cooldown()`：验证码失败后会话级长停，返回实际秒数；
  - `maybe_wander` 增加「浏览式连续滑动」分支；`_win_wh` 兼容 tuple；
  - `locator._click_obj`/`behavior_runner._step_click_point` 改走 `human.tap`。
- `behavior_runner.py`：`_step_captcha` 失败路径接 `human.captcha_cooldown()`。
- `config.yaml`：新增 `anti_detection:` 段（默认值+注释）。
- `docs/ANTI_DETECTION.md`：威胁面诚实分级（可缓解/不可缓解）。
- `tests/test_anti_detection.py`：9 例（seed 复现/误触边界/限流阈值/冷却/
  禁用零影响/wander 覆盖/默认值卡规）。

### 测试坑记录
- 首版 3 个用例未套 `_SleepSpy`，`tap` 内限流长停真实睡眠
  （默认每 12 次睡 14-26s）→ 挂死被 timeout 杀。已全部改 spy 口径。
- `t_wander_probability_override` 第三断言：两段都缺省应为 0.10（旧人设 0.06），
  已在 human.py 补 elif 分支。

## F1 完成记录（2026-10-21）

### 改动清单
- `behavior_runner.py`：
  - 模块级表 `DEFAULT_POPUP_TEXTS`(13) / `POPUP_CLOSE_IDS`(空,配置可扩) /
    `POPUP_BLACKLIST_TEXTS`(11) / `POPUP_AD_MARKERS`(6) / `AD_CLOSE_TEXTS`(3)；
  - `_maybe_sweep_popups(intent, bid, app_name)`：`run_app_flow` 行为执行前调用，
    `_popups_enabled` 门控（缺省 False，老配置零影响）；protect_ad = protect_ad_in_watch
    且 (intent=="watch" 或 "watch" in bid)；
  - `_step_dismiss_popups(act, app_name)`：每轮一个关闭动作，最多 max_rounds 轮；
    dump 后先查黑名单 → 命中返回 "blocked"（停扫且禁 BACK）；
  - `_popup_close_one(texts, ids, corner, back_key, ...)`：文案→id→右上角
    `(0.93w, 0.11h)`（仅屏上有广告特征时才动）→BACK；
  - `_run_kind` 注册 `"dismiss_popups"`。
- `executor.py`：`__init__` 末尾读 `popups` 配置段（`_popups_cfg`/`_popups_enabled`）。
- `config.yaml`：新增 `popups:` 段（enabled/max_rounds/back_key/corner_fallback/
  protect_ad_in_watch + extra_texts/extra_ids/extra_blacklist）。
- `device_session.py`：新增 `win_wh(d)` 兼容 helper（plain tuple / .width 双形态）。
- `human.py` / `human_trajectory.py` / `behavior_runner.py`：window_size 崩溃族修复
  （真机实测 `d.window_size()` 返回 plain tuple，`.width` 访问即 AttributeError；
  共 4+3+1 处）。

### 与卡规的偏差（如实记录）
1. 卡规 F1.4 配置段写 `texts/blacklist` 整表；实现采用「模块默认表 + extra_* 追加」，
   默认表升级时自动继承。**已补整表替换支持**：cfg 给了 `texts`/`ids`/`blacklist`
   即整表替换模块默认值，`extra_*` 仍在结果表上追加（两写法规格兼容）。
2. 卡规文案表含「暂不开启/下次再说/暂不升级」等，默认表已含；「取消」在表内但
   只在弹窗为 App 官方信息类时点——当前按文案精确匹配执行，误伤风险由 max_rounds=3
   与黑名单熔断兜底（如实记录，未做弹窗类型判别）。
3. 「直接关闭 app 重新开始」按卡规本期不做。

### 测试
- `tests/test_dismiss_popups.py`（新增 13 例）：文案优先级 / 黑名单熔断禁BACK /
  extra_blacklist 合并 / watch 保护点广告 / 非 watch 正常关 / BACK 兜底顺序 /
  干净屏零交互 / 多轮 / 未启用零扫描 / extras 合并 / watch 双通道 / dry-run 不碰设备 /
  corner 坐标 tuple 回归。**13/13 过**。
- 全量门禁：`.venv` pytest **231 passed**（含新增 19 例；沙箱系统 Python 亦 26/27，
  唯一 skip 项为 numpy 缺装，已补装）。

### 回滚点
`_backup_pre_fix/{behavior_runner,executor,config.yaml}.pre_F1_20261020_225028`

## F2 进行记录（2026-10-21）

（待填）
