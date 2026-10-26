# 派单卡 AUTOP-REFACTOR-2026-10-20-2：重构续单（C 收尾 → 门禁复明 → D）

> 时间：2026-10-20 14:30 ｜ 派单方：WorkBuddy AI（Host）
> 前置：AUTOP-REFACTOR-2026-10-19 单已执行 A/B 全批，C 批文件改动已落盘但没收尾；本卡接续。
> Host 已实测事实（不必重复验证，直接用）：
> - A1-A5/B6/B7/B8 完成；D 未开始（无 device_session/locator/behavior_runner）
> - C 已落盘：config.yaml 3215→104 行、config/apps/ 34 份、config_loader.py、_backup_pre_fix/*.pre_C_20261020_090042
> - C 新增测试直跑通过：test_config_loader.py 6/6、test_config_split_parity.py 1/1
> - Host 实跑 pytest tests/ → 66 passed；PROGRESS.md 最后更新 08:55（B8 后），C 段缺失

## 三步顺序执行（严格按序，每步过判据再下一步）

### 第 1 步：C 批收尾
1. 在 dispatch/AUTOP-REFACTOR-2026-10-19/PROGRESS.md 补「批次 C 进度」段：改动文件清单（config_loader.py / split_config.py / main.py / webui×3 / devtools 6 写回工具 / 7 只读方 / config.yaml / config/apps/34）、不变式核对结果、已跑的验证输出、回滚点（pre_C_20261020_090042）。
2. 跑齐 C 门禁并如实记录输出：
   - `.venv/Scripts/python.exe -m pytest tests/ -q`（当前 66，记录全绿）
   - `python main.py --list` 与拆分前对拍：34 App 名/别名/行为逐一一致（拆分前备份在 _backup_pre_fix/config.yaml.pre_C_20261020_090042，可用 config_loader 的兼容分支加载旧文件对比）
   - dry-run：`python main.py --dry-run --app 河马剧场 --task "签到并看视频"`
   - 真机专项：`tools/platform-tools/adb.exe connect 192.168.1.54:5555` 后 `.venv/Scripts/python.exe devtools/verify_live.py --apps 河马剧场,点淘,喜番免费短剧 --nav-fast`；判据：命中计数不回退；手机若锁屏/离线 → 记 BLOCKED 并说明，不许反复重试超过 3 次
3. 重点自查：六个保注释写回工具（apply_candidate_fixes / apply_nav_fixes / plan_anchor_fixes / remove_prelude / to_any_of / patch_nav_vision）是否全部经 config_loader.app_config_path 解析——逐个人工核对，输出核对结论。

### 第 2 步：测试门禁复明（修门禁漏洞）
背景（Host 发现）：项目测试有两派写法——test_*（pytest 可见）与 t_* + __main__ 直跑派（pytest 不可见）。t_* 派现存 19 例：tests/test_reward_pick.py(8) / test_reward_pick_pure.py(4) / test_config_loader.py(6) / test_config_split_parity.py(1)。
方案（二选一，优先 P1）：
- P1：新增 `pytest.ini`：`[pytest] python_files = test_*.py` + `python_functions = test_* t_*`，使 t_* 派进入 pytest 收集；跑 pytest 确认总数 66+19=85 全绿，记录输出。
- P2（若 P1 有副作用）：把上述 4 个文件的 t_* 函数统一改名 test_*（保持 __main__ 直跑块可用）。
- 完成后 grep 全 tests/ 目录确认无遗漏：`grep -L "def test_" tests/*.py | xargs grep -l "def t_"` 输出应为空或全部已注明。

### 第 3 步：D 批 Executor 三分拆
按计划真源（C:/Users/VUL/.workbuddy-ai/plans/toasty-beacon-babbage-jeufPKTo.md，sha16 efb88da9b1400267）D 节执行：
- 先写「门面等价性」测试再搬码（铁律）。
- 新 device_session.py / locator.py / behavior_runner.py；executor.py → ~160 行门面，经 self._xxx 同名可覆盖入口转发（保 tests 实例打桩）。
- 9 处坑位中文注释原文照搬禁润色（计划 D 节清单）。
- 开工前备份 _backup_pre_fix/*.pre_D_<ts>。
- 门禁：pytest 全绿（含第 2 步复明后的全部）+ 导入冒烟 + dry-run + 三 App 真机专项 + 河马剧场单 App 小批真机一轮，对照 devtools/calib/STABILITY.json 无回退。

## 硬性纪律（不变）
- 每步/每批开工前备份 _backup_pre_fix/；跑 pytest 前清 .venv 外 __pycache__（先 print 核对再删）。
- PROGRESS.md 立即更新：本卡三步各自完成后**立即**覆盖写对应段（上一单 C 段漏写导致对话 completed 时无记录——本单严禁），最终补「四批终态 + 偏差说明」。
- 工具调用预算约 300；到预算落盘部分结论 + OPEN/BLOCKED 停步。
- 不停在 requires_action；疑义入 PROGRESS.md 质疑记录段；不碰计划外文件；不 git push。
- 承前教训：B7 曾编辑出 SyntaxError——每步搬码后立即 py_compile 验证再进下一步。

## 投递记录
- 派单时间：2026-10-20 14:36 ｜ tag=AUTOP-REFACTOR-2026-10-20-2
- 派单前 marvis：0 in_progress（空闲）
- cid：conv_371e27c67c214fe8a211e526643a91f9
- 用户原话「并发派单」再次按单 agent 纪律纠正：三步（C收尾→门禁复明→D）有硬依赖，单卡顺序执行。
