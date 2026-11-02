# CHANGES · v6 S1（编译层）

日期：2026-10-29
范围：**只做第 1 步（别名层 + `step_model.py`）**。配置一行未改，执行路径未变。

---

## 一、新增文件

### 1. `step_model.py`（编译层，约 480 行）

把 step dict 规范化成不可变 `Step`。v1（只有 `type`）与 v2（`action`/`flow`/`macro`）
两套写法都能编译；**执行层仍用 `step.raw`**，这是"零行为变化"的实现方式。

对外接口：`compile_step` / `compile_actions` / `project` / `lint` / `Target` / `Step` / `LEGACY_TO_V2`。

### 2. `tests/test_step_model.py`（24 条，全绿）

其中 `t_all_app_configs_compile` 是**最强的一条**：拿 34 份真配置全量编译，
断言 `389 步 / 0 失败 / 112 WARN / legacy={ensure:1, scroll_to:1}`。
合成用例测不出"某个 type 忘了登记映射"，只有真配置能测出。

---

## 二、`behavior_runner.py` 改动（3 处，共约 30 行）

| # | 位置 | 改动 | 行为影响 |
|---|---|---|---|
| 1 | import 块 | 增加 `from step_model import Step, compile_step` | 无 |
| 2 | `_run_actions` | 每步先 `_validate_step(act, app)` 做编译校验 | **无**（只记日志） |
| 3 | `_run_kind` | 入参可为 `Step`，内部取 `step.raw` 执行 | 无（现有调用全传 dict） |

新增 `_validate_step()`：编译失败记 WARN，**然后照旧用原 dict 执行**。

---

## 三、与任务书/方案不一致的 5 处（都是实测逼出来的）

### 1. 编译失败**不跳过**执行（方案写的是 `continue`）

方案 `_run_actions` 里，编译抛异常时 `continue` 跳过该步。这会让「新加了 type 但忘了
登记映射」的步骤**静默不执行**，日志只留一句 WARN —— 最难查的故障形态。
改为：记 WARN，继续用原 dict 执行，由 `_run_kind` 的分派表决定命运
（未知 type 仍会被记「未知动作类型」并返回 False）。

### 2. `click_text/click_id/click_desc` 的映射写错，会导致 40+ 步全部编译失败

方案写 `("action", "click", "text", "text")`，kind 是 `action`，于是走进
`_compile_action_from_v1`——而该函数只认 swipe/press/wait/extract，直接抛
`内部映射错误: name=click`。叠加第 1 条（跳过执行），**40+ 个点击步骤会全部不执行**。
已改为 `("action+field", "click", "text", "text")`。

### 3. 坐标**不许取整**（方案 `int(x)` 会把 0.9 变成 0）

方案 `_compile_click_point` 写 `((int(x), int(y)),)`。`click_point` 的 x/y 是 0~1
比例值，`int(0.9)=0` → 兜底坐标变成 `(0,0)` = 屏幕左上角。实测有 8 个步骤是
「图像锚 + 坐标兜底」写法，取整等于让它们的兜底**点错位置**（左上角通常是广告位/返回区，
比不兜底更危险）。已改为保留 `float`。

方案自带的测试对这点是放水的：`assert s.target.fallback == ((0,0),) or ...` —— 
用 `or` 把错误值也放过。已换成精确断言 `== ((0.9, 0.138),)`。

### 4. `click_point` 的 x/y **不是必填**（方案当成了必填）

方案无条件 `_xy(act)`，但实测 72 个顶层 `click_point` 里有 53 个**只写 `images` 没有坐标**
（纯视觉锚点，命中不了就算未命中，没有兜底可言）。按方案会 **24 个 routine 编译失败**。
已改为：有锚点时 x/y 可选，有才生成 `fallback`。

### 5. `flow` 无 branches 不等于配置错误

方案把「flow 没有 branches」一律判 ERROR。但 `click_first` 可以不写静态 `candidates`、
靠 `candidates_from: sign` 在运行期从词池取候选 —— 实测 2 处（飞猪旅行、米读极速版的
sign 链）。已加 `Step.pool_from` 字段，lint 判 INFO 而非 ERROR。

> 这 5 处如果不改，按方案跑出来的结果是：24 个 routine 编译失败 + 40+ 步被跳过执行 +
> 8 个兜底坐标指向左上角。`pytest` 仍会"通过"，因为这些都是静默的。

---

## 四、6 个待决定问题（按任务书"我倾向"逐条落实）

| 问题 | 决定 | 说明 |
|---|---|---|
| Q1 海马畅听孤儿 `open` | **B 删除** | S2 执行 |
| Q2 死 `optional` 112 处 | **A 只打 WARN** | 本轮已在 lint 实现，配置未动 |
| Q3 `sign_evidence` | **A 不动** | 本轮未触碰 |
| Q4 幂等入口 | **B 先做 sign 28 条** | S4 执行 |
| Q5 终态检查原语化 | **A 做成原语，延后到 S2** | 先做 28 条，从里面归纳词表 |
| Q6 `daily_report` 0 实现 | **A 接受** | S2 立意图、不写链 |

---

## 五、实测结果（本机，无设备）

| 项 | 结果 |
|---|---|
| `pytest tests/test_step_model.py` | **24 passed** |
| `pytest tests`（全量） | 见下节 |
| 34 份配置全量编译 | **389 步 / 0 失败** |
| lint | **0 ERROR / 112 WARN / 4 INFO** |
| 112 WARN 与独立测量的一致性 | 独立统计「死 optional」= 37+72+2+1 = **112**，与 lint 完全吻合 |

`legacy` 只剩 2 处待折叠：`ensure`（1）、`scroll_to`（1）—— 都在 S2 处理。

---

## 六、S2 之前必须先做的事

1. 真机跑一周，观察「步骤失败」条数是否如期下降（S0.5 的 `any_of` 放行修正 +
   `click_first` 落地校验修正应该让报告变干净）。**用数据确认 S0.5 没漏别的 bug**。
2. 如果 `_validate_step` 在真机上刷出 WARN，先修配置，别急着开 S2 ——
   那些 WARN 就是"配置里写了但跑起来必然静默失败"的步骤。
