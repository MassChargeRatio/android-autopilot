# 派单卡 AUTOP-REFINE-2026-10-21：架构体检三项修复（Host 体检 → marvis 执行）

> 时间：2026-10-21 14:22 ｜ 派单方：WorkBuddy AI（Host）
> 项目根：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
> 来源：Host 14:16 架构体检结论（用户问「都优化完了吗」后复查），三项为唯一待修清单；④⑤（909 行单文件/run_app_flow 61 行）经评估维持现状不修。

## Host 已实测事实（直接用）

- 门禁基线：`./.venv/Scripts/python.exe -m pytest tests/ -q` = **280 passed**（沙箱系统 Python 无 pytest/numpy，必须用 venv）
- 引擎新 API 约定（前几轮实证）：`d.window_size()` 回 plain tuple（用 `device_session.win_wh`）；`_locate` 回 `LocateResult`（判 `hit` 取 `obj`，禁 `is None`）；u2 `UiObject` 无 `.rect`（用 `.bounds()` tuple，见 `locator._click_obj` 兼容写法）
- 备份纪律：`_backup_pre_fix/<file>.pre_R_<yyyymmdd_hhmmss>`（本卡用 `pre_R_` 前缀与 SELFSEARCH 的 `pre_S_` 区分）
- parity 活基线：`_backup_pre_fix/config.yaml.split_baseline` 为合并态（本卡不动配置则无需刷新）

## 修复项（三项，按序执行，互有上下文邻接不可拆并发）

### R1：`_step_click_first` 去重 + 瘦身（behavior_runner.py L502，96 行）

现状问题：显式 candidates 的知识库展开（L514-520）与词表 candidates 的知识库展开（L543-549）为两段各约 10 行的几乎相同代码（`_kb_candidates` → `_parse_sel` → 去重入 pool）。

修法：
1. 抽 helper `def _expand_kb_pool(self, app_name, pool, primary)`：查 kb → 无记录返回 False；否则把 kb_cands 逐个 `_parse_sel`、按 `(k, v)` 去重追加 `(k, v, primary or None)`，返回 True；
2. 显式段与词表段都改调该 helper；
3. 函数总行目标 ≤ 60；语义零变化（含 `primary=None` 当知识库无记录时的传递、词表优先排在显式之后的顺序）；
4. 先写锁定测试 `tests/test_click_first_pool.py`（可红）：同一候选经 kb 展开只入池一次；词表候选追加在显式之后；kb disabled 候选被跳过。写完全量应绿。

### R2:pick_best zone 分支抽纯函数（pick_locate.py L73-94）

现状问题：zone 加分嵌套过深——`ok_zone` 对 `right_edge` 恒真、`xc is None` 双重 elif 路径隐晦（「缺 x 坐标中性」语义埋在控制流里）。

修法：
1. 抽 `def _zone_score(ent, zone, screen_w, screen_h, bonus) -> int`：返回加分/扣分/0（中性）；把 `right_edge` 恒真 ok_zone、缺 left/right 时 xc=None→中性、`top_right/right_edge` 需 x ≥ 0.70w 等规则写成显式 if 序列 + 注释；
2. `pick_best` 内改为 `score += _zone_score(ent, zone, screen_w, screen_h, zone_bonus)`；
3. **打分行为逐案对拍不变**（用现有 `tests/test_zone_pick.py` 9 例护航，另补 4 例锁定边界：缺 x 中性/right_edge 无 x 不扣分/越界 top/tab_zone 命中线 0.92h）；
4. 签名 `pick_best(entries, target, kind, screen_h, log)` 旧五参兼容不许破坏。

### R3：`_app_extras` 去双层包装（behavior_runner.py L529 + candidates.py）

现状问题：`candidates_for(from_, {"extra_candidates": self._app_extras(app_name)})`——`_app_extras` 返回的已是 extras dict，调用方再包一层 `{"extra_candidates": ...}`，语义绕。

修法（最小侵入，二选一并说明理由）：
- 方案 A：`candidates_for(category, app_cfg=None, extras=None)` 增可选参；有 extras 时直接用于合并，`app_cfg` 保持旧语义；调用点改 `candidates_for(from_, extras=self._app_extras(app_name))`；
- 方案 B：不动 candidates.py，runner 侧 `extras = self._app_extras(app_name)` 后 `candidates_for(from_, {"extra_candidates": extras})`（仅去中间括号嵌套、加注释）。
- 旧签名（只传 category / category+app_cfg）行为与现有测试断言不变；未知 category ValueError 保持。

## 硬性纪律

1. 逐项 R1→R2→R3；每项：备份（`pre_R_<ts>`）→ 先写/补测试 → 实现 → 单测文件自跑 → py_compile → 立即落盘 `dispatch/AUTOP-REFINE-2026-10-21/PROGRESS.md`；
2. 测试必须能红：每项至少 1 例「先红后绿」记录进 PROGRESS（R1 新测试文件先行；R2/R3 用断言冻结+变异）；
3. 不改既有测试断言使其变绿；不 git push；不碰计划外文件（R1-R3 之外一律不动，executor.py/Human.__init__/run_app_flow 明确不修）；
4. 每项完成后跑一次全量 `pytest tests/ -q`（允许中间态红，终态必须 ≤ 当前 280 的减少，即 ≥280）；
5. 最终 PROGRESS 补「三项终态 + 行数变化 + 偏差说明 + 回滚点」表。

## 验收口径（Host 侧）

1. PROGRESS 终态表齐备；2. venv `pytest tests/ -q` ≥ 280 passed（Host 复跑）；3. `main.py --dry-run --force --app 趣头条 --task 签到` EXIT=0；4. `_step_click_first` ≤ 60 行；5. `_backup_pre_fix/*.pre_R_*` 存在且回滚点写明；6. 既有测试断言 0 修改。

## 投递记录

- **2026-10-21 14:38 Host 投递 marvis**（busy=0 确认；token 09:49 后已轮换为 0f96fba0-*，取日志最后一条）
  - CID：`conv_3e8110fbaa6b4d76be91a5cc88b1b243`（tag: AUTOP-REFINE-2026-10-21）
  - 派单消息含：卡路径、三项一句话任务、Host 前置状态（280 基线/venv 必须/三条引擎 API 防旧坑/pre_R_ 前缀）、六条纪律
  - marvis 首应答：读卡中
  - Host 守望：轮询至终态后按六项验收口径复验（pytest ≥280 / dry-run EXIT=0 / ≤60 行 / 备份在位 / 断言 0 修改 / PROGRESS 终态表）
