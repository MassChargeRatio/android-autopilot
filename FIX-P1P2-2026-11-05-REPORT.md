# FIX-P1P2 报告（2026-11-05）

分支：`feat/fix-p1p2-1105`　基线：`3f53872`　worktree：`AndroidAutopilot-wt-fixp1p2`

| # | 项 | 状态 | 验证 |
|---|----|------|------|
| P1-1 | app.js any_of 分支数 | done | `grep o.branches webui/static/*.js` 无残留；`test_webui.py::t_ops_event_humanizer_translates_action_json` 通过（用例字段名同步改正） |
| P1-2 | adb_backend 错误当成功 | done | `tests/test_adb_backend.py` 52 passed（新增 5 条：_run/_retry/tap·swipe·back/cold_start/window_size） |
| P2-3 | recorder 吞 commit 失败 | done | `test_recorder_batch.py` + `test_record_flow.py` 全过 |
| P2-4 | routes_yaml 回滚 ok | done | `test_webui_yaml_api.py` 全过（前端已按 `body.ok === false` 判失败） |
| P2-5 | server 启动非原子 | done | 新增 `tests/test_jobs_exclusive.py` 3 passed（含 12 线程抢单仅 1 单成功） |
| P2-6 | human lognormal 均值 | done | `test_human_seed.py` 全过 + 1e5 采样均值核对 |
| P2-7 | find 子串（设计权衡） | done（不改默认语义 + 加 exact 开关） | 默认子串行为零变化；`exact=True` 走全等 |
| P2-8 | behavior_runner 空 desc | done | `test_locator_sharing.py` / `test_page_owner.py` / `test_click_first_*` 无新增失败 |
| P2-9 | parity SKIP 静默 | done | mock `_before_apps()->None` 实测抛 AssertionError |
| P3-10 | routes_yaml \x00 | done | 与 `..`/`\` 并列校验 |
| P3-11 | server PAGES 常量 | done | 白名单收敛为模块级 `PAGES`，do_GET/_serve_page 同源 |
| P3-12 | executor backend 规范化 | done | `str(...).strip().lower()` 兜底 u2 |

## 明细

### P1-1 `webui/static/app.js:234` — any_of 分支数永远显示 0
- **现状**：`if (t === 'any_of' && o.branches) bits.push((o.branches || []).length + ' 路')`。
- **根因**：生产端字段名是 `choices`。`behavior_runner._step_any_of` 第 677 行就是
  `choices = act.get("choices") or []`，缺失还会 WARN「any_of 动作缺少 choices」；
  全仓（py/js/yaml/tests）**没有任何代码产出 action 级 `branches`**（`data.py` /
  `app.js:309,314,930` 的 `branches` 是结构层「路径条数」，是另一回事）。
  于是 `o.branches` 恒 undefined → 分支数一直显示 0，「多路径覆盖」在日志里看不见。
- **改法**：`o.branches` → `o.choices`。
- **连带**：`tests/test_webui.py::t_ops_event_humanizer_translates_action_json` 的用例
  正好喂 `{"type":"any_of","branches":[{},{}]}` —— 它用生产端不存在的字段名，
  把字段名错读「测成通过」了（典型的用例对齐 bug 而非行为）。已把该用例改成真实
  字段名 `choices` 并注明原因；改完 node 实跑通过。
- **验证**：`Select-String -Path webui/static/*.js -Pattern "o\.branches"` 无命中；
  该 JS 用例通过。

### P1-2 `adb_backend.py:51-92`（`_run`/`_retry`）+ 调用方 — 错误文本当成功
- **现状**：`_run` 的 `except` 返回 `f"[adb err] {e}"`（**非空串**）；`_retry` 的
  `except` 把 `last` 设成 `f"[{label} err] ..."`，末尾 `return last` → 错误串被当成功返回。
- **根因**：契约含糊 —— 「返回非空」被调用方当作成功。错误串还会被当设备输出继续
  解析（`.strip()` 拿到 "[adb err] ..."）。
- **改法**（建立单一契约：**None = 失败，"" = 成功无输出，其他 = 成功输出**）：
  1. `_run`：`except Exception: return None`；
  2. `_retry`：`except` 分支 `last = None`（异常详情仅 `print` 日志），末尾
     `return last or None`（空串也归一成 None，契约唯一）；
  3. 原语 `tap/swipe/back` 返回 `shell(...) is not None`（True/False 可判定）；
  4. `cold_start`：`am start` 结果 `is not None` 才回 True；
     `AdbDeviceAdapter.app_start` 同理（原来无条件 `return True`）；
  5. 调用方审计：`device_session.py:315` / `webui/data.py:730` 已是 `(... or "")`
     安全写法；`data.py:730` 补 `or ""` 堵 `.strip()` 崩；`dump` 失败回 `""`（既有
     falsy 语义不变）；`resolve_activity` 已 `(out or "")`。
- **验证**：`tests/test_adb_backend.py` 52 passed，新增：
  `test_run_returns_none_on_exception`、`test_retry_returns_none_not_error_string`、
  `test_tap_swipe_back_report_failure`、`test_window_size_none_safe`、
  `test_cold_start_shell_failure_returns_false`。
  另修 `test_cold_start_ok` 的 mock：原来 `lambda cmd: calls.append(cmd)` 回 None，
  等于把「None 也算成功」的旧契约写进了用例；改为回 `""`（真实 adb 成功无输出的返回）。

### P2-3 `recorder.py:83-96` `_flush_ops` — commit 失败仍清 pending
- **现状**：`except: pass` 之后**无条件** `self._pending = 0`。
- **根因**：commit 失败（锁超时/磁盘满）时计数已清零但数据未落库 → 这批 ops 永久
  丢失，且日志无痕。
- **改法**：`self._pending = 0` 移进 `try`（仅 commit 成功才清），`except` 保留 pending
  等下轮 `_maybe_flush_ops` 重试；docstring 同步改写（原「失败保持 except: pass 语义」过时）。
- **验证**：`test_recorder_batch.py`、`test_record_flow.py` 全过。

### P2-4 `webui/routes_yaml.py:206` / `:295` — 回滚误报成功
- **现状**：校验失败回滚后 `return 200, {"ok": True, "action": "rolled_back", ...}`。
- **根因**：回滚是失败路径，`ok:true` 让前端/调用方误判「保存成功」。
- **改法**：两处 `"ok": True` → `"ok": False`，`action` 保持 `rolled_back`（前端已按
  `action` 判定）。**前端消费已核对**：`webui/static/yaml_editor.js:36` 是
  `if (!res.ok || body.ok === false)` 走失败分支；`:115` / `:188` 另有
  `body.action === 'rolled_back'` 的专门提示 → 改 `ok` 后前端正确提示回滚、不再当成功。
- **验证**：`test_webui_yaml_api.py` 全过（其断言的是 `action=='rolled_back'`，未受影响）。

### P2-5 `webui/server.py:300-325` — 判空闲与登记之间有竞态
- **现状**：`active = c.jobs.active()` 检查通过后调 `c.create_app_job(payload)`；两次
  取锁之间是空窗。
- **根因**：并发两个 `POST /api/jobs` 都能看到「无运行中任务」→ 同时登记两个任务抢
  同一台独占设备。
- **改法**：
  1. `webui/jobs.py` 新增 `JobBusy` 异常 + `_active_locked()` / `_create_locked()`
     内部方法，新增 **`create_exclusive()`**：`with self._lock:` 内「判空闲 + 登记」
     一气呵成；忙碌则抛 `JobBusy`（带 active 任务标题）。`create()` 语义不变
     （仅抽 `_create_locked`），`active()` 复用 `_active_locked`。
  2. `server.py`：`create_app_job` 改调 `create_exclusive`；`/api/jobs` 与
     `/api/tools/{id}/run` 去掉外层 `active()` 预检，改 `except J.JobBusy as e →
     self._err(409, str(e))`（对外响应与文案不变）。
- **验证**：新增 `tests/test_jobs_exclusive.py`（3 passed）：
  ① 有运行中任务时抛 JobBusy；② 12 线程并发抢单，**恰好 1 单成功**；③ 前一单结束后
  可正常起下一单（不误锁死）。

### P2-6 `human.py:139-148` — lognormal 均值系统性偏高
- **现状**：`v = exp(gauss(log(mean), sigma))`。
- **根因**：log-normal 期望 = `exp(mu + σ²/2)`，把 mu 取 `ln(mean)` 会让实际均值变成
  `mean·exp(σ²/2)`；σ∈[0.45,0.75] → **偏高 10%~32%**，再被 clamp 截断后整体节奏系统性变慢。
- **改法**：`mu = ln(max(mean,1e-6)) - 0.5*sigma*sigma`，使 `E[v] ≈ mean`；注释改写
  （原「mu 设在区间约 18% 高度处」→ mean 的含义 + 均值校正说明）。
- **验证**：`test_human_seed.py` 全过；1e5 次采样实测（`_rand(1.0, 5.0, lognormal=True)`，
  seed=42）：样本均值 **1.7708 vs 目标 mean 1.7200，相对偏差 +2.96%**（残差来自 clamp
  下界把低端样本抬上来，属预期）；同参数下**旧实现均值 2.0476，偏高 19.0%**。区间仍
  clamp 在 `[lo, hi]`（min=1.000、max=5.000）。

### P2-7 `adb_backend.py:134` `find` — 子串模糊（评审已降级为设计权衡）
- **结论**：**不改默认匹配语义**。子串是**定位特性**：节点文本常带后缀（「签到领100金币」
  必须能被 `pat="签到"` 命中），改精确匹配会直接打断真实定位链。
- **改法（最小化、零行为变化）**：签名 `find(xml, pat, exact=False)`，`exact=True` 时走
  全等；默认仍 `pat in v`。docstring 写清「这是设计权衡，不是缺陷」，防止后来人再「顺手修正」
  把定位改坏。
- **验证**：默认路径所有既有用例未变（`test_click_first_pool` / `test_locate_pick` 等全过）。

### P2-8 `behavior_runner.py:1294` — 空 desc 误判
- **现状**：`if "desc" in act:` —— `desc: ""` 也为 True → 走 desc 分支把 value 定位成空串。
- **根因**：键存在性判断 ≠ 值有效性；空 desc 会 `descriptionContains("")` 命中任意元素。
- **改法**：`if act.get("desc"):`（空串让位给 `text`），保留原二选一语义。
- **验证**：`test_locator_sharing.py`、`test_page_owner.py`、`test_click_first_*`、
  `test_landing*.py` 无新增失败。

### P2-9 `tests/test_config_split_parity.py` — SKIP 静默放过 + 刷新命令带密钥
- **现状**：`if before is None: print("SKIP ..."); return` → `__main__` 把「没抛异常」
  计为通过，护栏静默失效；docstring 刷新命令读整份 `config.yaml`，会把 `vlm.api_key`
  抄进基线（已被 pre-commit 拦过）。
- **改法**：
  1. `before is None` → `raise AssertionError("SKIP 未找到 pre_split 备份——护栏失效，请先建立基线")`；
  2. docstring 刷新命令改为 `cfg = {'apps': load_config('config.yaml')['apps']}` 只写 apps 段。
- **验证**：本 worktree **无 `config.yaml`**（gitignore 不进 worktree），实跑会走 raise
  路径（**属预期**）。已用 mock 构造 `_before_apps()->None` 实测：
  `ASSERT_OK: SKIP 未找到 pre_split 备份——护栏失效，请先建立基线`。真实回归由协调员主树执行。

### P3-10 `webui/routes_yaml.py:73`
- `_app_file` 校验补 `"\x00" in name`（与 `/`、`\`、`..` 并列），堵 NUL 截断绕过。

### P3-11 `webui/server.py`
- 白名单 `("yaml.html",)` 提为模块级常量 `PAGES`，`do_GET` 与 `_serve_page` 同源引用
  （原 do_GET 硬编码 `path == "/yaml.html"`，与 `_serve_page` 的元组两处维护易漂移）。

### P3-12 `executor.py:63`
- `str(... or "u2").strip().lower()`：配置写成 `" ADB "` / 非字符串时也能正确落到
  `adb` / `u2` 兜底。

## 测试实测

运行环境：`python -m pytest`（系统 Python 3.11 + 临时装的 PyYAML 6.0.3；本 worktree 无
`.venv`，`yaml` 缺失先 `pip install pyyaml`）。

- **逐项定向**：
  - `tests/test_jobs_exclusive.py` + `tests/test_adb_backend.py`：**55 passed**（55/55）
  - `tests/test_webui.py`、`test_webui_yaml_api.py`、`test_recorder_batch.py`、
    `test_record_flow.py`、`test_human_seed.py`、`test_locator_sharing.py`、
    `test_page_owner.py`、`test_yaml_editor_static.py`：102 passed / 9 failed
    （9 条与基线**同名同因**，见下）
- **全量对拍**（`pytest tests -q --ignore=tests/test_trajectory_captcha.py`）：
  - 本 worktree：**22 failed / 589 passed**
  - 基线 `3f53872`（独立 worktree 实跑）：**22 failed / 581 passed**
  - **失败集合逐条同名一致 → 0 新增失败；新增 8 个用例全绿**（+8 passed）。
  - `test_trajectory_captcha.py` 因环境缺 `numpy` 无法收集，已在两侧同口径忽略。
- **已知失败（全部为环境/数据缺失，与本单无关，基线同样失败）**：`test_action_contract`
  百度跳转、`test_config_split_parity`（无 config.yaml）、`test_landing` 模板裁剪分、
  `test_page_owner` 污染样本、`test_rpc_overflow`/`test_rpc_timeout`（缺 u2 库/模块）、
  `test_step_model::t_all_app_configs_compile`、`test_unified_steps` 3 条、
  `test_webui` 8 条（无 config.yaml → `app_count`/文案/接口契约相关）。

## 结论

DONE
