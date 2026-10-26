# 派单卡 AUTOP-REFACTOR-2026-10-19：四批重构执行

> 产生时间：2026-10-19 22:10 ｜ 派单方：WorkBuddy AI（Host）
> 项目根：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
> 计划真源：`C:\Users\VUL\.workbuddy-ai\plans\toasty-beacon-babbage-jeufPKTo.md`
> 计划 sha256 前16位：`efb88da9b1400267`（不符则停手回报）
> 开工前必读：计划全文 + 本卡 + 项目 `00_交接总览_20260921.md` 第 8 节（纪律口径）

## 唯一任务
按计划真源执行 **A → B → C → D 四批重构**，严格顺序，每批过了门禁才进下一批。
禁止跳批、禁止并行改同一文件、禁止顺手重构计划外代码。

## 每批门禁（不过不算完成，不许进下一批）
1. `cd 项目根 && .venv/Scripts/python.exe -m pytest tests/ -q` → 全绿（基线 44 + 本批新增）
2. 导入冒烟：`python -c "import executor,main,recorder,human,ui_page,pick_locate"`（批次对应）
3. dry-run 冒烟：`python main.py --dry-run --app 河马剧场 --task "签到并看视频"`
4. B/C/D 批必跑真机专项：`.venv/Scripts/python.exe devtools/verify_live.py --apps 河马剧场,点淘,喜番免费短剧 --nav-fast`
   （真机 adb：`tools/platform-tools/adb.exe connect 192.168.1.54:5555`，掉线重连；判据：命中计数不回退）
5. 更新本批进度段（见落盘纪律）

## 硬性纪律
1. **每批开工前备份**：`_backup_pre_fix/<file>.pre_<batch>_<YYYYMMDD_HHMMSS>`（计划内有清单，不弹确认）。
2. **跑 pytest 前清 pyc**：清 `.venv` 外全部 `__pycache__`（先 print 列表核对，再删）。
3. **坑位注释迁移铁律**：计划 D 批有清单的 9 处中文踩坑注释（_reset_to_landing / _wait_page_ready / _at_top_level / _locate / _pick_best / _vision_click / _step_any_of / _reward_candidates / _step_click_point / _step_click_first / __init__ 的 _probe_no_vision），**原文照搬或压缩改写，禁止润色、禁止删减**。
4. **日志文案零漂移**：A/B 批各函数的不变式清单逐条核对（计划文件内）。
5. **config 写回工具**（C 批）：apply_candidate_fixes / apply_nav_fixes / plan_anchor_fixes / remove_prelude / to_any_of / patch_nav_vision 六个必须全部适配 config_loader.app_config_path，漏一个即整批失败。
6. 不碰 handover/、docs/ 只读资料；不 git push；不动资金类行为语义。
7. **不要产生 `<原名>_<时间戳>.md` 副本**，直接覆盖目标文件。

## ★ 硬性落盘节奏（上一轮任务因不落盘被系统判失败）
1. 前 5 个动作内先创建 `dispatch/AUTOP-REFACTOR-2026-10-19/PROGRESS.md`（批次总表 + 待办即可）。
2. 每完成一个子步骤立即覆盖写 PROGRESS.md（状态/命令输出/门禁结果）；本批全过则追加「批次结论」段。
3. 预算约 400 次工具调用；到预算无结论 → 落盘部分结论 + OPEN/BLOCKED 并停在批次边界。
4. 不要停在 requires_action；需要用户许可的操作（如手机亮屏）直接记 BLOCKED 并继续可做的部分。

## 交付格式
PROGRESS.md 分 A/B/C/D 四段，每段：
`改动文件清单 / 不变式核对结果 / 门禁命令+输出 / 新增测试清单 / 回滚点`。
末段汇总：四批终态 + 遗留 + 与计划原文的偏差说明（如有）。

## 边界
- 只改计划列出的文件；发现计划有错先落盘「质疑记录」到 PROGRESS.md，按计划最小解释执行，不要自行扩大范围。
- D 批门面等价性测试先写再搬码。
- 若某批次内某文件的修改量 >300 行，先落盘中间态再继续。

## 投递记录
- 派单时间：2026-10-19 22:20 ｜ 通道：marvis_dispatch.dispatch(hold=True, tag='AUTOP-REFACTOR-2026-10-19')
- cid：conv_461a221dd7254f3a82df2208388a0004
- 派单前 marvis 状态：8 会话 0 in_progress（空闲）
- 计划真源 sha256 前16位：efb88da9b1400267（派单前实测）
- 用户原话「并行派单」已按单 agent 纪律纠正为**单卡顺序执行**：四批 A→B→C→D 每批门禁通过才进下一批（并行改同一 executor.py 会冲突/双写，且计划本身有硬依赖 A→B→D、C 错峰）
