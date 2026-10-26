# 派单卡 AUTOP-REGRESS-2026-10-20：12 份新 sign 配置真机回归（verify_live）

> 时间：2026-10-20 21:20 ｜ 派单方：WorkBuddy AI（Host）
> 项目根：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
> 队列位置：第 1 张（回归 → F1/F2 → 自搜寻，链式队列由 Host 守望器控制）
> Host 已实测事实（直接用，不必重复验证）：
> - 2026-10-20 20:50 Host 按用户人工勘察描述重写了 12 份 sign 配置（备份 `_backup_pre_fix/*.pre_S_20261020_2035`）；
>   dry-run 全部 EXIT=0、pytest 212 passed；文案优先 + 坐标兜底（坐标均注释「待真机校准」，是近似值）；
> - 配置路径与人工描述对照：`dispatch/AUTOP-SELFSEARCH-2026-10-20/APP_PATHS.md`（用户原话）+ 12 份 `config/apps/*.yaml` 的 sign 段注释；
> - verify_live CLI：`--apps`（逗号分隔 App 名）、`--behaviors sign`（只跑签到）、`--nav-fast`（跑批必开：跳过 VLM 用比例坐标，本机 VLM 常 90s 超时）、`--out/--json` 自定义输出；
> - 设备：真机 192.168.1.54:5555（vivo Z5x），`tools/platform-tools/adb.exe` 在仓库内；**截至派单时 adb devices 为空——手机当前离线或锁屏**；
> - 红线（不可违反）：资金类弹窗出现立即停手（签到期流程不碰钱）；不修改任何配置文件（本卡只跑不改）；不 git push；每 App 结果立即落盘。

## 任务：把 12 份新 sign 配置在真机上跑一轮，产出逐 App 命中结论 + 坐标校准清单

### 第 1 步：读懂预期（前 5 个动作内同时完成 PROGRESS 骨架）
1. 读 `dispatch/AUTOP-REGRESS-2026-10-20/PROGRESS.md` —— 不存在就创建（骨架：12 App 表格空行 + 待办）；
2. 读 `dispatch/AUTOP-SELFSEARCH-2026-10-20/APP_PATHS.md`（12 App 人工描述，判据来源）；
3. 速读 12 份 sign 配置（只看 sign 段，了解每 App 的步骤与坐标兜底点）。

### 第 2 步：连接设备（离线处理有硬规则）
- `tools/platform-tools/adb.exe connect 192.168.1.54:5555`；
- `adb devices` 未见 `device` 状态 → **重连不超过 3 次**（每次间隔 30s）；仍失败 → PROGRESS 记 **BLOCKED：设备离线**，本卡结束（**不要**反复重试、不要改用模拟器、不要改 config.yaml 的 serial）。

### 第 3 步：跑回归（一条命令，输出落 calib）
```
.venv/Scripts/python.exe devtools/verify_live.py \
  --apps 趣头条,拼多多,京东,美团,快手,百度地图,海马畅听,UC浏览器极速版,飞猪旅行,米读小说,米读极速版,大众点评 \
  --behaviors sign --nav-fast \
  --out devtools/calib/LIVE_VERIFY_SIGN12.md \
  --json devtools/calib/LIVE_VERIFY_SIGN12.json
```
- 跑批中途若某 App 卡死/崩溃中断：对剩余 App 单独重跑（`--apps <单个>`），总重试不超过 2 轮；
- 每完成一个 App 立即把结果写进 PROGRESS（不等全跑完）。

### 第 4 步：逐 App 判定 + 坐标校准清单（本卡核心交付）
对每个 App 产出四列：

| App | 命中? | 断点步骤 | 兜底坐标是否命中 | 校准建议 |

判定规则：
- **命中**：sign 行为任一 reward/ensure 证据或日志显示到达签到动作（以 verify_live 输出与 `devtools/calib/uiprobe/<pkg>/` 截图为准）；
- **断点步骤**：从 LIVE_VERIFY_SIGN12.md 的步骤日志找出第一个失败步（哪一级 any_of 分支、哪个候选、走了文案还是坐标兜底）；
- **兜底坐标校准**：对每个被注释「待真机校准」的 click_point，用截图/dump 量出真实中心的归一化坐标（`devtools/calib/uiprobe/<pkg>/*.xml` 里有 bounds），给出修正值（保留 4 位小数）；
- 校准建议分级：`精确值`（截图能量化）/ `范围估计`（只能估屏幕分区）/ `不可见`（该屏没抓到，说明前置步就断了）。

### 第 5 步：汇总交付
1. PROGRESS.md 补「回归终态」段：12 App 表格 + 设备/时间戳证据 + 校准清单 + 与 `devtools/calib/STABILITY.json` 基线的对照（有基线的 App 标注是否回退）；
2. 若**全部 12 个都未命中且断点相同**（如第一屏全灭）→ 判定为环境问题（锁屏/未登录/风控），记 BLOCKED 并说明，不要逐个反复重跑；
3. 本卡**不修改** `config/apps/` 任何文件——校准清单交给 Host 应用（下一步自搜寻卡会消费它）。

## 硬性纪律（不变）
1. §5.15 落盘节奏：前 5 个动作建 PROGRESS 骨架；每 App 完成立即覆盖写；工具调用预算约 150；超预算落盘部分结论停步；不停 requires_action；疑义入质疑记录段。
2. 跑 pytest 前清 .venv 外 `__pycache__`（先 print 核对再删）——本卡预期不需要改代码，若需要动代码必须单独说明理由并备份。
3. 每步完成后如有代码/配置改动必须 py_compile + 相关测试直跑（预期无改动）。
4. 不 git push；不碰计划外文件；无证据不报 confirmed。
5. 最终 PROGRESS 补「终态 + 偏差说明」表。

## 投递记录

- （待 Host 投递时填写）
