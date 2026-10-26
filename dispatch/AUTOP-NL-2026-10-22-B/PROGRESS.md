---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 58c070810b91e31b76e5016e97ae2974_81c7bce3cdda11f1b659525400cd780f
    ReservedCode1: M1dgF+s190P/dzGx/3sLh6xFwKKkKqXFoajEcNttqzIv8zQt7Zam+Bg7o+8SS9oXwOgvNCCvdKSZWM5i2aDC6IXXM4dZA6M99lgRyxKuEEVwUS2Or08hoXJP4YFZA/BRcRJA4AIrMvfQ83kbizi3Q74GPm+0M9kPcCjcokaER0+Qt2JJj5+B3VXiKJQ=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 58c070810b91e31b76e5016e97ae2974_81c7bce3cdda11f1b659525400cd780f
    ReservedCode2: M1dgF+s190P/dzGx/3sLh6xFwKKkKqXFoajEcNttqzIv8zQt7Zam+Bg7o+8SS9oXwOgvNCCvdKSZWM5i2aDC6IXXM4dZA6M99lgRyxKuEEVwUS2Or08hoXJP4YFZA/BRcRJA4AIrMvfQ83kbizi3Q74GPm+0M9kPcCjcokaER0+Qt2JJj5+B3VXiKJQ=
---

# PROGRESS — AUTOP-NL-2026-10-22-B（引导式录制 record_flow）

- 任务卡片：dispatch/AUTOP-NL-2026-10-22-B-CARD.md
- 目标：新建 `devtools/record_flow.py` + `tests/test_record_flow.py`（NL 指令 → 执行 → 记录 → YAML）
- 环境：必须使用 `./.venv/Scripts/python.exe`
- 禁碰：candidates.py / behavior_runner.py / executor.py / main.py / config.yaml / config/apps/** / devtools/yaml_writer.py / devtools/nl_to_steps.py / 任何既有测试
- 软依赖：nl_to_steps.py 尚不存在 → try/except import 兜底生效，**BLOCKED-DEP 已记录**

## 节奏约定
1. 每完成一个函数 → 立即覆盖写本文件（签名 + 测试命令 + 真实输出）
2. 预算约 250 次工具调用；超预算落盘 OPEN/BLOCKED 并结束
3. 不停止在 requires_action

## 执行状态

### 阶段 0：环境探查（完成）
- venv Python 3.13.14；`devtools/nl_to_steps.py` 不存在（软依赖未就绪）
- `devtools/yaml_writer.py` 存在；接口：insert_behavior / replace_behavior(force=True) / WriteResult(path,action,backup,diff,warnings)
- `devtools/calibrate.py` 提供 parse_nodes / match_selector / dominant_package / connect_device / BOUNDS_RE / safe_name（只读复用）
- click_point 既有格式：x/y 归一化坐标(0-1) + timeout/optional/vision/desc
- 测试基线：`pytest --collect-only -q` = **316 tests collected**

### 阶段 1：devtools/record_flow.py（已完成主体）
- py_compile：`.\.venv\Scripts\python.exe -m py_compile devtools\record_flow.py` → **COMPILE_OK**

已实现函数清单：
- `_fallback_parse_line(cmd)`：兜底极简动词剥离（点/上滑/下滑/左滑/右滑/滑动/等/返回），不复制 A 卡逻辑
- `_split_cmd(cmd)`：统一 (verb, target, pos)；A 卡就绪走真 parse_line
- `_match_pos(target)`：方位词 → 归一化坐标（_POS 表）
- `_parse_seconds(target)`：等N秒解析
- `Step` dataclass：seq/cmd/verb/target/pos/hit_kind/hit_value/bounds/point_norm/act_before/act_after/delta/confirmed/note
- `ui_digest(xml) -> frozenset`：可点节点 (text,desc,id,bounds) 集合，顺序不敏感
- `page_delta(a,b) -> float`：1 - Jaccard；同页=0、全换=1、双空=0
- `step_to_action(step) -> dict|None`：text/desc/id→click_first；point→click_point；swipe/wait/back
- `steps_to_actions(steps) -> (actions, warnings)`：丢弃未确认并汇总 warnings
- `guess_entry(steps) -> str`：首个 text/desc/id 命中值；无则 auto
- `is_money_step(step, money_words) -> bool`：资金红线
- `assemble_actions(steps, entry_hops) -> (actions, warnings)`：entry hops 在前
- `FlowRecorder`：start/_connect/_execute/_machine_check/record_step/undo/show_trace/finish/close/_snapshot/_show_step/_render_hops/_resolve_entry/_screen_size/_activity/_dump
- `main()` CLI：--app/--package/--serial/--behavior/--entry/--max-steps/--allow-money/--apply

BLOCKED-DEP（已解除）：探查时 `nl_to_steps.py` 不存在；编写测试时发现 **A 卡产物已就绪**（parse_line 返回 `(steps: list[dict], warnings: list)`），`_split_cmd` 已适配真 parse_line，`NL_TO_STEPS_READY=True` 生效。兜底 `_fallback_parse_line` 保留（防御）。

### 阶段 2：tests/test_record_flow.py（完成）
- 测试命令：`.\.venv\Scripts\python.exe -m pytest tests\test_record_flow.py -q` → **29 passed in 0.18s**
- 覆盖：ui_digest 顺序不敏感/惰节点剔除 / page_delta(0/1/双空/部分) / step_to_action(text/desc/id/point/swipe/wait/back/未确认/未命中) / steps_to_actions 丢弃与 warnings / guess_entry / is_money_step / assemble_actions hops 在前 / machine_check(跳包/低delta/ok/资金fatal) / record_step(ok入trace/跳包默认拒绝/低delta默认拒绝/资金拒绝/allow_money保留/方位词坐标/A卡坐标) / finish 合并顺序 / finish 已存在行为 fallback replace
- 关键适配：A 卡 parse_line 真实结构 `(steps, warnings)` 与 pos 为 `(x,y)` tuple（非方位词字符串），已按真实结构修正 `_split_cmd` / `Step.pos` / `_execute`

### 阶段 3：回归验证（完成）
- 全量 pytest：`.\.venv\Scripts\python.exe -m pytest -q` → **345 passed in 90.07s**（基线 316 + 新增 29，≥291 满足）
- 禁词：`grep "今日签到|立即签到|任务中心" devtools/record_flow.py` → **0 命中**
- config/apps/*.yaml：本轮未触碰；终态 sha256 34 个文件已存档（见上，与本任务无关）
- CLI 冒烟：`python devtools/record_flow.py --help` → 正常列出全部参数
- 禁碰复核：candidates.py / behavior_runner.py / executor.py / main.py / config.yaml / config/apps/** / yaml_writer.py / nl_to_steps.py（只读）/ 既有测试均未改动；仅新增 devtools/record_flow.py 与 tests/test_record_flow.py
- 误生成文件 PROGRESS_20261022_103917_264.md 已删除（回收站）

## 终态表

| 文件 | 状态 | 说明 |
|---|---|---|
| devtools/record_flow.py | ✅ 新建 | 引导式录制：NL → 执行 → 记录 → YAML；29 项单测覆盖 |
| tests/test_record_flow.py | ✅ 新建 | 29 passed（mock 设备，无真机依赖） |
| dispatch/AUTOP-NL-2026-10-22-B/PROGRESS.md | ✅ 维护 | 本文件 |
| 禁碰文件 | ✅ 未动 | 见阶段 3 |

## 验收清单
1. [x] `pytest tests/test_record_flow.py -q` 全绿 → 29 passed
2. [x] 全量 ≥ 291 → 345 passed
3. [x] `config/apps/*.yaml` 未改（sha256 已存档）
4. [x] `grep "今日签到\|立即签到\|任务中心" devtools/record_flow.py` 零命中 → 0
5. [x] PROGRESS 终态表（本表）

## 遗留
- BLOCKED-DEP 已解除：nl_to_steps.py 就绪后按真实结构适配（parse_line 返回 (steps, warnings)）
- record_step 为单步录制语义：一条 NL 拆出多步时仅取首步并打印提示
- 资金红线词表 MONEY_WORDS 固定，允许 --allow-money 放开
- 录制快照目录：devtools/calib/record/<pkg>/<ts>/NN_before.xml|png（start 时创建）
*（内容由AI生成，仅供参考）*
