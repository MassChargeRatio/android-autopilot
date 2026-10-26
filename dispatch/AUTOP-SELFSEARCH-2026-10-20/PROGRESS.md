# AUTOP-SELFSEARCH-2026-10-20 派单进度（marvis 执行 · Host 守望）

> CID: `conv_610600793eb5493cab95ff8e71f7a6ea` ｜ 投递：2026-10-21 09:50 ｜ 派单方：Host

## 状态总览

| 步骤 | 状态 | 说明 |
|---|---|---|
| 1. 全局分类候选词表（candidates.py 四表 + extra_candidates） | ✅ 完成 | 四表 SIGN/TASK_CENTER/NAV_TAB/WITHDRAW；APP_PATHS 12 条 32 个独立文案全覆盖；config_loader.extra_candidates 只读读取（别名命中）；test_selfsearch_candidates 6 passed |
| 2. click_first 滚动重试（scroll_retry） | ✅ 完成 | 默认 0 旧行为零滑动；>0 仅全 miss 后自然滑动重试，最多 N 次；首轮命中不滑；test_click_first_scroll 4 passed（先行红 3 failed） |
| 3. 位置先验（zone 权重 → _pick_best） | ✅ 完成 | tab_zone/top_right/right_edge 三区；test_zone_pick 9 passed（先行红 ImportError） |
| 4. behavior 时间窗（window start/end → BLOCKED） | ✅ 完成 | 超窗 WARN 跳过(BLOCKED)不报错不打断；test_window_gate 通过 |
| 5. PLAYBOOK 文档 + 12 配置收敛 | ✅ 完成 | docs/SELF_SEARCH_PLAYBOOK.md；12 份 sign 链路接 candidates_from/zone；坐标兜底全保留，命中面不降；test_selfsearch_inject 6 passed |

## 时间线

- 09:50 Host 投递，marvis 应答开始读卡（busy=0 确认后派）
- 10:08 第1步完成：candidates.py 四表 + config_loader.extra_candidates；测试先红（ModuleNotFoundError）后绿 6 passed；config/parity 相关 11 passed；备份 _backup_pre_fix/config_loader.py.pre_S_20261021100808
- 10:20 第2步完成：behavior_runner._step_click_first 增加 scroll_retry 循环（默认0旧行为零滑动；>0 全 miss 后自然滑动重试最多 N 次；首轮命中不滑）；test_click_first_scroll 4 passed（先行红 3 failed）
- 10:35 第3步完成：pick_locate.py 增加位置先验三区常量 ZONE_BOTTOM_BAND=0.92 / ZONE_TOP_BAND=0.18 / ZONE_RIGHT_RATIO=0.70 与 zone 加权（tab_zone/top_right +150、right_edge +100；仅多匹配择优，不硬过滤；缺坐标/未知屏尺寸中性；旧签名 pick_best(entries,target,kind,screen_h,log) 兼容）；locator._locate/_pick_best 透传 zone/screen_w 并在 entries 增加 left/right；test_zone_pick 9 passed（先行红 ImportError）；全量 266 passed；py_compile=0；备份 _backup_pre_fix/pick_locate.py.pre_S_20261021103500、locator.py.pre_S_20261021103500
- 10:39 第4步完成：behavior_runner._window_open/_behavior_window/_in_window/_parse_hhmm 时间窗门控（window 缺失/解析失败 -> True 不堵行为；窗口外 WARN「跳过(BLOCKED)」）；behaviors[bid] 双形态（list / {window, actions}）；test_window_gate 通过
- 11:08 第5步前半完成：behavior_runner._step_click_first 注入 candidates_from（显式优先、词表追加、去重、extra_candidates 并入、未知分类 WARN）；_app_extras 惰性读取 config/apps extra_candidates；zone 仅配置时透传 _locate；先行红 test_selfsearch_inject（5 failed, 1 passed）后全量绿；docs/SELF_SEARCH_PLAYBOOK.md 落盘；备份 config/apps 34 份 _backup_pre_fix/*.pre_S_20261021110837
- 11:37 第5步后半完成：08/05-13 八份配置 sign/task_center/nav_tab 链路接 candidates_from + zone（删重复文案、坐标兜底全保留）；webui/data.py._anchor_of 增加 candidates_from 回退（契约测试锚点 key 非空）；parity 基线刷新；dry-run 验收趣头条/美团 EXIT=0；备份 _backup_pre_fix/data.py.pre_S_20261021113730
- 11:38 终态落盘本表

## 五步终态

| 步骤 | 产出物 | 回归 | 回滚点 |
|---|---|---|---|
| 1. 词表 | candidates.py（SIGN/TASK_CENTER/NAV_TAB/WITHDRAW 四表）；config_loader.extra_candidates（别名命中只读） | test_selfsearch_candidates 6 passed | _backup_pre_fix/config_loader.py.pre_S_20261021100808 |
| 2. scroll_retry | behavior_runner._step_click_first 滚动重试 | test_click_first_scroll 4 passed（先行红 3 failed） | _backup_pre_fix/behavior_runner.py.pre_S_20261021100808 |
| 3. zone | pick_locate 三区加权；locator zone/screen_w 透传 | test_zone_pick 9 passed（先行红 ImportError） | _backup_pre_fix/pick_locate.py.pre_S_20261021100808、locator.py.pre_S_20261021100808 |
| 4. 时间窗 | behavior_runner 窗口门控 + behaviors 双形态 | test_window_gate 通过 | _backup_pre_fix/behavior_runner.py.pre_S_20261021100808 |
| 5. 收敛+文档 | docs/SELF_SEARCH_PLAYBOOK.md；12 份 config/apps 收敛；webui/data.py 锚点 key 回退 | test_selfsearch_inject 6 passed；webui 34 passed | _backup_pre_fix/*.pre_S_20261021110837（34 份配置）、data.py.pre_S_20261021113730 |

## 回归报数与偏差

- 回归：`./.venv/Scripts/python.exe -m pytest tests/ -q` = **280 passed**（基线 247，净增 33：selfsearch_candidates 6 + click_first_scroll 4 + zone_pick 9 + inject 6 + window_gate 若干）；py_compile=0；12 份 yaml 全量可解析；`main.py --dry-run --app 趣头条/美团 --task 签到 --force` 均 EXIT=0
- parity：`config.yaml.split_baseline` 已按 load_config 产出刷新（有意变更后刷新），parity 相关测试绿
- 偏差说明：
  1. 收敛口径=「显式候选优先 + 词表追加/纯化 + 坐标兜底全保留」，未删任何坐标兜底；仅删除被词表完全覆盖的重复文案（如「今日签到/立即签到/签到」→ candidates_from: sign），等价收敛不降命中面
  2. webui/data.py 增加 candidates_from 回退：契约测试要求锚点 key 非空，纯词表锚点 key 取词表类别（如 sign），未改任何既有断言
  3. 提现组（withdraw）本期仅建词表 WITHDRAW，未接入 12 份执行链（用户明确暂略）
  4. 候选「不靠外部描述自搜寻」的上限=词表分类命中；纯自搜寻时如词表词全部 miss 且无坐标兜底，记 _last_fail 返回 False（B6 语义），不臆造按钮
- 既有测试断言：0 修改（仅生产代码 behavior_runner/webui/data.py 与新增测试）

## 验收口径（Host 侧）

1. PROGRESS.md 终态表：五步状态 + 偏差说明 + 回滚点
2. `./.venv/Scripts/python.exe -m pytest tests/ -q` ≥ 247 passed
3. `main.py --dry-run --app 趣头条 --task 签到` 与 `--app 美团 --task 签到` EXIT=0（带 --force）
4. 干预期检查：`_backup_pre_fix/*.pre_S_*` 备份存在；既有测试断言未被改绿

## 质疑记录段

- （无）

## Host 验收纪要（2026-10-21 11:50）

| 验收项 | 结果 | 证据 |
|---|---|---|
| PROGRESS 终态表（五步+偏差+回滚点） | ✅ 齐备 | 本文件 §五步终态 |
| venv pytest 全量 | ✅ **280 passed** | Host 独立复跑 106.22s（基线 247，净增 33） |
| dry-run 趣头条/美团 `--force` | ✅ 双 EXIT=0 | Host 独立复跑 |
| 备份存在 | ✅ 41 个 pre_S_20261021 | 34 配置 + behavior_runner/config_loader/locator/pick_locate/executor + data.py |
| 既有测试断言 0 修改 | ✅ | tests/ 今日改动仅 5 个新测试文件，无旧文件 |
| 配置收敛不降命中面 | ✅ **34 份 images/click_point 计数零删除** | 对比 pre_S_20261021110837；显式 value 减少项均为词表覆盖的重复文案；坐标兜底全保留 |
| F1/F2 接线完好 | ✅ | `_maybe_sweep_popups`/`human.tap`/`_relocate_candidate` 在位 |
| candidates.py 四表对拍 | ✅ | P3 数据源 + APP_PATHS 补全（现金签到/里程签到/能量红包/首页），docstring 说明独立成模块理由 |

观察项（不违规，记录在案）：
- `temp/dryrun_selfsearch_20261021.py` 探针留在 temp/（与 LIVE_VERIFY 系列同区，项目惯例）；
- executor.py 做了预防性备份但零改动；
- marvis 执行中有少量空转轮次（重复读卡/自修注释），预算消耗偏大但无逾矩。

**结论：卡C 验收通过，五步全部生效。**

- 2026-10-21 09:52:43 轮询 status=in_progress

## 守望终态

- 2026-10-21 11:44:04 marvis 会话 status=completed
