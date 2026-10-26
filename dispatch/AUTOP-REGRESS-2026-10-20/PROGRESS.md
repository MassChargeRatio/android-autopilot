# PROGRESS - AUTOP-REGRESS-2026-10-20：12 份新 sign 真机回归

> 派单变更：2026-10-20 22:20 marvis 网关 token 日志（MarvisHostStd.log）被删，
> 当时自助恢复路径穷尽（旧 token 401、空 token 401、回收站无权读 Administrator 桶）。
> 用户指示「派单不成功就自己执行」→ **本卡由 Host 直接执行**。
> 设备：192.168.1.54:5555 在线。
>
> **2026-10-21 04:2x 网关恢复**：用户提供 Marvis 安装路径线索，定位到
> `C:\Users\Administrator\AppData\Local\Temp\Tencent\Marvis\logs\MarvisHostStd.log`
> （MarvisHost 重启后重建，`local_ws_url=ws://127.0.0.1:10123/?token=...`）。
> 派单模块实测连通（list_conversations 正常）。但当时 marvis 有**他人项目**的
> in_progress 会话（N14 CDP 探针任务），按单 agent 纪律不抢占 → 本卡继续 Host 自执行。

## 执行记录

- [x] 12 App sign 回归一轮（2026-10-21 01:0x，`--force`，引擎 bug 修复前）→ 7/12
- [x] 引擎级 bug 排查与修复（三族，详见下）
- [x] 二轮 4 App（scroll_to 修复后）→ 3/4（快手崩 StaleObject）
- [x] 三轮：`_click_obj` bounds API + StaleObject 自救修复后
      拼多多/海马畅听/UC/快手 全部 HIT
- [x] 米读小说：真机手动全链验证 + 按校准坐标重写配置 → HIT
- [x] 逐 App 命中结论 + 断点步骤
- [x] 「待真机校准」坐标校准清单
- [x] 终态 + 偏差说明

## 终态：12/12 执行无崩溃；分级结论

| 分级 | App | 证据 |
|---|---|---|
| A 全链真机验证 | 米读小说 | 手动 dump 全链：我的(0.900,0.931)→福利中心(0.158,0.562)→立即签到(0.773,0.221) 点击后变「已签」；配置已按校准坐标重写并回归 HIT |
| B 流程执行到交互 | 趣头条、京东、美团、百度地图、飞猪旅行、米读极速版、大众点评、拼多多 | 回归文字/坐标点击均发生、无崩溃、任务正常收尾；金币到账效果未逐一目验 |
| C 进到任务页、签到入口未定位 | 快手、海马畅听、UC浏览器极速版 | 见下「断点」 |

### 断点明细（C 级三个）

- **快手**（05:31-05:36 真机 dump）：☰(0.07,0.06)→任务中心 链路通；任务中心滚 2 屏
  **无「签到」入口**（任务均为：看视频赚金币/看广告得金币/起床赚金币/走路赚金币…）。
  scroll_to 目标「签到」真机不存在 → 原配置此步必然失败。待用户确认快手是否有
  独立签到入口（或签到已并入「起床赚金币」类任务）。
- **海马畅听**：F1 清扫熔断正确触发（首页「提现」文案，停扫禁 BACK）→ 文案点击
  「领现金」成功 → 领现金页滚动 4 页未找到「签到」。待 dump 领现金页校准。
- **UC浏览器极速版**：底 tab 坐标兜底命中 → 滚动 4 页未找到「签到」。
  待 dump 任务页校准。

### 坐标校准清单（下次真机勘察输入）

- 米读小说：已按真机校准写入 config/apps/10_米读小说.yaml（见文件头注释）。
- 快手：☰(0.07,0.06) 命中、任务中心文案命中 —— **不要再找「签到」**，需重新定义目标。
- 海马畅听 / UC：进页坐标已命中，缺签到入口的文案/坐标（dump 待补）。

## 一轮暴露的引擎级 bug（全部已修）

1. **`d.window_size()` 返回 plain tuple**：`behavior_runner`/`human`/
   `human_trajectory` 共 8 处按 `.width/.height` 访问 → `AttributeError` 潜伏崩溃族
   （此前文案候选总先命中，从未走到坐标/滑动分支所以没爆）。
   修复：`device_session.win_wh(d)` 兼容 helper + 全部调用点替换。
2. **`_step_scroll_to` 把 `LocateResult` 当元素**传给 `_click_obj`
   （B6 `_locate` 返回值显式化后漏改）→ `'LocateResult' object has no attribute 'rect'`，
   拼多多/快手/海马畅听/UC 4 个 App 一走到 scroll_to 即崩。已修 res.hit/res.obj 口径。
3. **`_step_ensure` 同族**：`obj is None` 恒假 → `exists: yes/no` 校验静默失效。已修。
4. **作息窗口拦截**：23:02 超过 wake_window 23:00 → 6 个 App 1-2 秒退出。回归统一带 `--force`。
5. **启动随机等待 60-352s**（真人抖动）拖垮回归节奏 → `main.py` 新增 `--fast`
   （只跳 start_wait，其余真人模拟保留），回归驱动默认带 `--force --fast`。
6. **miniyaml 嵌套块序列（`- - type:`）解析缺陷**：本沙箱系统 Python 无 PyYAML，
   测试门禁走 miniyaml 时 any_of 全被解析成畸形 dict → webui 契约测试抓到。
   已修 miniyaml + 新增 `tests/test_miniyaml_nested_seq.py` 6 例。注意：项目 `.venv`
   有 PyYAML，**真机运行时不受影响**，此坑仅打测试门禁。

## 补充：三族引擎 bug 的锁定测试

- tests/test_click_obj_bounds.py 7 例（u2 tuple/.rect 兼容/dry-run/stale 自救/StepError 上抛）
- tests/test_miniyaml_nested_seq.py 6 例（嵌套块序列）
- window_size 族由现有 dry-run/回归链路覆盖（win_wh helper）
- 最终门禁：venv pytest 247 passed（2026-10-21 05:30）
