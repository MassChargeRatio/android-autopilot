# 弹窗清扫精准化 + 超时收窄：实施记录（2026-10-30）

> 任务卡：`handoff/task_popup_timeout/任务卡_弹窗清扫与超时收窄.md`
> 外部 AI 给了实施方案，本文记录**采纳了什么、否决了什么、为什么**，以及实测数据。

## 一、否决了两条（有硬证据）

### A3 `DIALOG_CLASS_MARKERS` 判据 → 否决

外部方案想用 `class="android.app.Dialog"` / `PopupWindow` 判断"是否真有弹窗容器"，
替代原来的"dump 里出现广告词"。

用项目自带的 **63 份真机 dump**（`devtools/calib/**/*.xml`）实测：

| 检查 | 结果 |
|---|---|
| 样本总数 | 63 |
| 含 `class="android.app.Dialog"` | **0** |
| 含 `PopupWindow` | **0** |
| 含任意 dialog 字样 | 3（抖音里的小写字符串 `dialog`，不是 class） |

该判据在本项目真实屏幕上**永不命中** → `corner_fallback` 与 `back_key` 会变成死代码。
这不是"收紧判据"，是"静默关闭"，而且比显式关闭更糟：代码看着还在，
测试要手工塞一个真机上不存在的 Dialog class 才过（测试绿、线上死）。

**替代方案**：`corner` 改为**整次清扫最多触发一次**（只在第 1 轮允许）。
快手首页形态（广告词一堆、无弹窗）→ 1 次盲点 + A2 发现屏幕没变 → 立刻退出，
而不是连打 3 轮 37s。

### Q2「保持 corner 默认 True」→ 否决

方案主张保持默认值以兼容。但既然 A3 不用了，corner 在 feed 页仍会误触发；
而"显式关掉 + per-app `close_points`"才是可回滚、可 review 的做法。

**落地**：`config.yaml` 里显式 `corner_fallback: false`（代码默认值仍是 `true`，
一行配置即可回滚）。快手改用 `popups.close_points` 指向实测坐标 (0.910, 0.195)。

> 顺带修掉一个方案没提的**新风险**：corner 关掉后，`back_key: true` 会变成
> "AD_MARKERS 命中就按 BACK"，而视频流首页天然带「广告/下载」字样 —— 一按 BACK
> 直接退出 App。已把 back 纳入 corner 这个「盲操作总开关」：corner 关闭时不再单独按 BACK。

## 二、采纳了五条

| 项 | 落地 | 备注 |
|---|---|---|
| A1 传 xml | `_popup_close_one` 不再自己 dump | 只省"干净屏那一轮"的 1 次；有动作的轮次仍是前后各 1 次（A2 的代价），测试如实钉住 |
| A2 指纹校验 | `_screen_fingerprint` | 用 **md5 前 8 字节**而非内置 `hash()`：后者每进程随机，跨进程不可复现 |
| A4 close_points | 文案 → id → close_points → corner | 兼容旧调用（新参数全为关键字/可选） |
| B1 any_of 总预算 | `timeouts.any_of_total`，默认 30 | 默认值 = 现行为；预算只在**分支边界**检查，不打断进行中的分支 |
| B2 250ms 轮询 | `_locate(..., poll=0.25)` | 干净屏一轮从 13×0.8=10.4s 降到 13×0.25≈3.25s |
| B3 text_any 旁路 | `_is_target_page_from_dump` | 保留（通用旁路），但**对快手那步不生效**——见下 |

## 三、B3 治不了本，真修法是配置

`text_any` 全项目只配了 3 处，快手「立即签到」那步的 `expect` 只有
`phash / phash_max_dist / settle / retry`，没有 `text_any` → B3 直接 return False。

**真修法**：那一步 `retry: 1 → 0`。基准图是「签到前」弹窗，签到成功后内容必变
（实测距离 23~41，阈值 10），再点一次注定还是失配——一次无效重试 13s。
已在 `config/apps/05_快手.yaml` 落地。

## 四、实测对比（真机 快手「签到」）

| 指标 | 改前（10:38） | 改后（3 次） |
|---|---|---|
| 总耗时 | 103s | **65s / 108s / 62s** |
| 弹窗清扫触发 | 3 轮，盲点同一坐标，**37s 零效果** | **0 次**（3/3 次运行） |
| 落地校验 | 2 次判定 + 1 次重点，13s | **1 次判定，无重试** |

108s 那次是另一个失败模式：`页面就绪提前放行（波动型页面，已过半数预算）`，
侧边栏点空导致任务中心未命中——与本次改动无关（同代码在 14:24 跑出 65s），
属于「页面就绪判定」的独立缺陷，未在本卡范围。

## 五、回归

```
pytest tests                 → 513 passed（487 基线 + 26 新增），0 failed
devtools/verify_coverage.py  → PASS 99/99，unverifiable 0
34 app dry-run（复合任务）    → OK=34 FAIL=0
编译层 lint                  → 389 步 / 0 ERROR / 112 WARN / 4 INFO（与改前一致）
资金护栏                     → POPUP_BLACKLIST_TEXTS 熔断逻辑 0 行改动
```

新增测试：
- `tests/test_popup_sweep_v2.py` 11 条（A1/A2/A4/C1）
- `tests/test_any_of_budget.py` 5 条（B1）
- `tests/test_locate_poll.py` 5 条（B2）
- `tests/test_verify_landing_skip.py` 4 条（B3）
- `tests/test_dismiss_popups.py` 改 4 条 + 增 1 条（A2 后"屏幕不变就退出"是新语义，
  多轮用例必须让 dump 每轮都在变）

基线 `_backup_pre_fix/config.yaml.split_baseline` 已按「只含 apps」刷新
（77,412 bytes / 34 apps，无 `api_key`、无 `sk-`），旧基线留 `.bak.<ts>`。
