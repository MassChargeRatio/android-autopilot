# 派单卡 AUTOP-2026-10-18：AndroidAutopilot 五步推进

> 产生时间：2026-10-18 12:45 ｜ 派单方：WorkBuddy AI（Host）
> 项目根：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
> 背景：项目自旧机（原根 `D:\ProgramData\WorkBuddyAI\AndroidAutopilot`）经交接包完整迁入本机，
> 307 文件 / 6,909,885 字节已校验一致。交接总览见项目根 `00_交接总览_20260921.md`（先读）。

## 环境现状（Host 已实测，2026-10-18）
- 本机仅 C: 盘；**无 adb**、**无 MuMu 模拟器**、**无 uiautomator2**；Python 3.13.12 可用。
- 真机 192.168.1.54:5555 交接时拒连（需手机端开启无线调试，Host 负责协调）。

## 任务序列（有硬依赖，按序执行；某步 BLOCKED 不中断后续可独立步骤）

### ① 重建 venv + 依赖
- 项目根建 `.venv`；安装 `requirements.txt`（uiautomator2、yaml、flask 等）。
- 追加：安装 Android platform-tools（adb）并加入 PATH 或记录绝对路径。
- 产出证据：`python -m pip list` 关键包版本 + `adb version` 输出，写入报告。
- 完成判据：`python -m pytest tests/ -v` 全 PASS（基线 17/17，tests/ 目录现存 16 个文件，以实际可收集用例数为准，如实回写）。

### ② 真机无线调试
- 尝试 `adb connect 192.168.1.54:5555`；若拒连 → **记 BLOCKED（等待用户在手机端开启无线调试/配对）**，不要反复重试超过 3 次。
- 不要用 `adb pair` 盲试（无配对码必失败）。

### ③ 全量回归
- 前置：①完成 且 ②设备可达（真机或任一可用模拟器）。
- 运行 `python devtools/verify_live.py`，刷新指标，与基线对照（命中率 70.5%、94/94 可校验、STABILITY.json）。
- 设备不可达时本步记 BLOCKED，跳 ④⑤。

### ④ MANUAL_TRIAGE.md 14 处未命中入口
- 前置：③有新鲜数据；否则按现有 MANUAL_TRIAGE.md 离线补锚点方案（改 config/images 前先备份原文件到本项目 `_backup_pre_fix/`）。
- 每个 App 修完必须有探针/回归证据才可标 confirmed；无证据一律标 OPEN。

### ⑤ WebUI 冒烟
- `python webui/server.py` 起服务，浏览器/HTTP 请求验证页面功能；验证 `find_free_port` 修复未回退（bind+listen，allow_reuse_address=False）。
- 证据：HTTP 状态码 + 关键页面片段；结束后关闭服务进程。

## ★ 硬性落盘节奏（上一轮任务因迟迟不落盘被系统判失败 —— 必须遵守）
1. 前 5 个动作内先创建 `<项目根>/dispatch/AUTOP-2026-10-18/REPORT.md`（骨架 + 待办清单即可，哪怕空）。
2. 之后每完成一个子步骤**立即覆盖写**该文件；禁止攒到最后一次性输出。
3. 预算约 120 次工具调用；到预算仍无结论 → 落盘「部分结论 + OPEN/BLOCKED」并结束。
4. 不要停在 requires_action；需要用户许可的操作（如手机端开调试）直接记 BLOCKED 并继续可做的部分。

## 红线
- 资金/金额/支付类操作**强制二次确认，禁止自动执行**。
- 删除/覆盖任何文件前先备份到 `<项目根>/_backup_pre_fix/`。
- 诊断截图 png 不入库，报告以 md/json 为准。
- 直接覆盖目标文件写报告，**不要产生 `<原名>_<时间戳>.md` 副本**。
- 不修改 `handover/`、`docs/` 历史资料（只读背景）。

## 交付格式
REPORT.md 每步一节：`状态(PASS/FAIL/BLOCKED) + 命令 + 关键输出 + 指标`；
末节汇总表：①~⑤ 状态 + 阻塞项清单 + 下一步建议。

## 投递记录
- 派单时间：2026-10-18 12:54 ｜ 通道：marvis_dispatch.dispatch(hold=True, tag='AUTOP-2026-10-18')
- cid：conv_ec596c5dc4484f8487cf852fd4f978b7
- 派单前 marvis 状态：9 会话中 1 个 in_progress（conv_400e433ab4f34d59a62，conversations.get 返回 not_found，判定为重启残留幽灵条目，非真实任务）
- 首响：marvis 复述「先读取派单卡验证 sha256 前 16 位 9e1b0ac45ce4fe54」→ 卡片纪律已生效
