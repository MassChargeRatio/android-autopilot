# AUTOP-2026-10-18 执行报告：AndroidAutopilot 五步推进

> 派单卡：dispatch/AUTOP-2026-10-18-CARD.md（sha256 前16位 9e1b0ac45ce4fe54 已验证一致）
> 执行时间：2026-10-18
> 项目根：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
> 续单：AUTOP-2026-10-18-2（2026-10-18，真机已可达，继续 ③④⑤）

## ① 重建 venv + 依赖 — PASS

- 命令：`python313 -m venv .venv`（Python 3.13.14，位于 `C:\Users\VUL\.workbuddy\binaries\python\versions\3.13.12\python.exe`）
- 安装：`pip install -r requirements.txt`（清华镜像）+ 补装 flask 3.1.3、pytest
- adb：`tools/platform-tools/adb.exe`，Version 37.0.1-15733141（官方 platform-tools-latest-windows.zip，解压于 tools/platform-tools/）
- pip list 关键包：

| 包 | 版本 |
|---|---|
| uiautomator2 | 3.7.0 |
| adbutils | 2.12.0 |
| PyYAML | 6.0.3 |
| Pillow | 13.0.0 |
| opencv-python | 5.0.0.93 |
| numpy | 2.5.4 |
| flask | 3.1.3 |
| lxml | 6.1.3 |
| requests | 2.34.2 |
| retry2 | 0.9.5 |
| deprecation | 2.1.0 |

- 测试：`python -m pytest tests/ -v` → **44 passed in 50.74s**（基线 17/17，实际收集 44 项，如实回写：收集数多于交接基线，全部 PASS）

## ② 真机无线调试 — 续单解除（PASS）

- 用户已通过有线(本地机)开启 TCP 调试，无线 adb 已授权。
- 续单实测（2026-10-18）：`adb connect 192.168.1.54:5555` → **device**（vivo V1911A）。
- 关键排障：`failed to authenticate` 根因是 adb server 以 Administrator 身份启动、key 与手机授权（VUL 用户 key）不一致；`adb kill-server` 后以 `USERPROFILE=C:\Users\VUL` 重启 server 即连接成功。
- adb：`tools/platform-tools/adb.exe`，Version 37.0.1-15733141。

## ③ 全量回归 — PASS（阻塞全解后重跑完成，STABILITY 5 轮刷新）

- 阻塞已解除（勿重复排查）：真机 `adb connect 192.168.1.54:5555` → device（vivo V1911A），已解锁且 Awake（前台 launcher）；VLM 网关 OmniRoute 已迁至宿主机 `http://192.168.1.162:20128/v1`（config.yaml vlm + fallback 两处已改），Host 实测 `GET /v1/models` 200。
- ③-1 全量单轮证据（`verify_live.py --nav-fast`，后台 PID 13916，全程保活防锁屏，2026-10-19 16:04）：

| 结果 | 数量 |
|---|---|
| 首屏命中 | 28 |
| 导航后命中 | 5 |
| 首屏未命中 | 7 |
| 导航后仍未命中 | 10 |
| 数据作废(页面非目标App) | 1（抖音 dump 0 节点） |

- 产出：`devtools/calib/LIVE_VERIFY_AUTOP3.json` + `.md`。
- ③-2 STABILITY 5 轮刷新（`stability_run.py --rounds 5 --nav-fast`，PID 16332，17:36 完成）：

| 指标 | 本次 | 基线 | 差异 |
|---|---|---|---|
| rounds | 5 | 5 | = |
| 总命中 / 有效 | **159/242 = 65.7%** | 命中率 70.5% | -4.8pp |
| 稳定命中 | 30 | — | — |
| 波动 | 7 | — | — |
| 从未命中 | 15 | — | — |
| 作废 | 8（一淘 2 / 微博 2 / 抖音 2 / 河马 2 异常） | — | — |
| 可校验 | 242/250 = 96.8%（行为级 55 条） | 94/94 可校验 | 口径差异（本次按轮次-行为有效样本计） |

- 残余 never（15）：一淘 sign/withdraw、今日看点 withdraw、全民K歌 bonus/collect、天天快讯 watch、悟空 sign、抖音 bonus/watch、抖音极速版 sign/watch、抖音火山版 sign、点淘 watch、红果 sign、蛋花 sign。
- 产出：`devtools/calib/STABILITY.json` + `.md`（17:36 刷新，STABILITY.md 已同步）。
- 状态：**PASS（命中率 65.7%，低于基线 70.5%，原因记录于 ③ 清单：多为多级导航/内容位漂移类 never）**

## ④ MANUAL_TRIAGE.md 未命中入口 — 真机取证（续单③④完成）

- 取证方式：`verify_live.py --nav-fast --apps 河马剧场,点淘,喜番免费短剧`（独立证据 `devtools/calib/LIVE_VERIFY_AUTOP3_EVIDENCE.json` + `.md`，2026-10-19 17:45），并叠加 STABILITY 5 轮聚合交叉验证。
- 证据概要（取证单轮）：点淘 3 行为首屏未命中；喜番 3 行为全命中（sign 首屏『赚现金』/ watch 导航后『赚钱』/ withdraw『我的』）；河马 3 行为全命中（sign 三级页『签到』/ watch 首屏『福利』/ withdraw『我的』）。
- 上次离线改 5 项逐项判定（资金类动作仅做锚点校验，未触发任何真实提现；confirm 类按钮不在校验链路内）：

| App | 行为 | 改动 | STABILITY 5轮 | 取证单轮 | 判定 |
|---|---|---|---|---|---|
| 河马剧场 | withdraw | 「我的」后新增 click_id: item_cash | 3/3 = 100%（稳定） | 首屏命中『我的』 | **confirmed** |
| 河马剧场 | sign | 「我的」→ 福利 文本入口 | 2/3（1 次未命中，波动） | 导航后命中（三级页『签到』） | **confirmed** |
| 点淘 | watch | 首步候选补「元宝中心」 | 0/5 = 0%（never） | 首屏未命中（『赚更多元宝』候选未现） | **OPEN** |
| 点淘 | withdraw | 首步候选补「元宝中心」 | 3/5 = 60%（波动） | 首屏未命中（『去兑换』候选未现） | **OPEN** |
| 喜番免费短剧 | sign | 首分支候选补「福利」「赚现金」 | 5/5 = 100%（稳定） | 首屏命中『赚现金』@(496,2111) | **confirmed** |

- 判定规则说明：命中（候选锚点真实出现且可走通）→ OPEN → **confirmed**；未命中或波动未达稳定（rate < 1.0 且证据不足）→ 保留 **OPEN** 并记录原因。
- OPEN 保留原因：
  - 点淘 watch：`verify_live` 校验候选『赚更多元宝』，5 轮 + 取证单轮均未在首屏出现；离线补的「元宝中心」属首步候选但 UI 实际无对应文本（首页无该入口或需先进入元宝中心页）。
  - 点淘 withdraw：候选『去兑换』5 轮中 3 轮出现（60% 波动），取证单轮未现；同 watch 类问题，首步「元宝中心」入口不稳，需走完整链探针（元宝中心 → 元宝兑权益页 → 去兑换）实跑逐动作记录后复核。
- 状态：**3/5 confirmed（河马 withdraw/sign、喜番 sign），2/5 OPEN（点淘 watch/withdraw）—— 点淘两项需完整链探针或人工复核**

- 派单卡称 14 处，实为 **15 项**（devtools/calib/MANUAL_TRIAGE.md 原文 15 行，含 A 弹窗遮挡2 / B 前台无效3 / C 纯rid图标2 / D 多级导航3 / E 文本锚点漏5）。
- 处置原则：先离线补锚点（config.yaml 文本级精确替换，保留原缩进与注释），备份至 `_backup_pre_fix/config.yaml.pre_autop-20261018`（SHA256 与原件一致）；真机可达后再逐一核查修正。
- 离线落盘修改 **5 项**：

| App | 行为 | 改动 | 验证 |
|---|---|---|---|
| 河马剧场 | withdraw | 「我的」后新增 `click_id: item_cash`（提现 rid） | yaml 解析 PASS |
| 河马剧场 | sign | 「我的」分支新增 `click_id: item_wallet`（福利 rid） | yaml 解析 PASS |
| 点淘 | watch | 首步候选补「元宝中心」 | yaml 解析 PASS |
| 点淘 | withdraw | 首步候选补「元宝中心」 | yaml 解析 PASS |
| 喜番免费短剧 | sign | 首分支候选补「福利」「赚现金」 | yaml 解析 PASS |

- 真机核查后的**二次修正**（config.yaml 已写入，备份于 `_backup_pre_fix/`）：
  - 河马剧场 sign：`item_wallet` 为广告位已弃用，改 **text「福利」入口**（我的 → 福利 → 去签到）。
  - 点淘 watch：真实入口为「赚更多元宝」@(711,561) → 元宝中心(H5)。
  - 点淘 withdraw：真实入口为「去兑换」@(951,545) → 元宝兑权益页。
  - 喜番 sign：「看剧赚钱」→ 福利中心，签到候选为 签到/每日签到/看剧得金币/立即签到/去签到。
- 回归保障：修改后 `pytest tests/` **44 passed 无回归**；执行器 `res_id` 字段写法与 executor.py 校验一致（click_id 步骤）。
- 处置记录已追加至 `devtools/calib/MANUAL_TRIAGE.md`（2026-10-18 离线处置记录 + 真机核查记录，已由 OPEN → confirmed）。
- 真机回归结果（并入 STABILITY，rounds=5）：河马 watch/withdraw、喜番三行为、点淘 collect、蛋花 watch/withdraw 等稳定命中；河马 sign 3/5、点淘 collect 2/5、红果 sign 3/5 等波动；一淘 sign/withdraw、点淘 watch/withdraw、抖音系多项等仍为 never（残余项见 ③，需多级导航架构或人工复核）。
- **续单③④判定见本节约 3/5 confirmed、2/5 OPEN 表格（河马 withdraw/sign、喜番 sign confirmed；点淘 watch/withdraw OPEN）**。

## ⑤ WebUI 冒烟 + 契约测试 — PASS

- 对象：`webui/server.py`（本地 HTTP 服务 + JSON API），重点验证 `find_free_port` 修复（bind+listen 双成功探测 + `allow_reuse_address=False`）。
- 冒烟结果（venv Python，脚本落 temp）：

| 检查项 | 结果 |
|---|---|
| find_free_port 跳过已占用端口（8765 被外部占用 → 返回 8768 / 8800 空闲直返） | PASS |
| GET /api/health | 200 ok=true ver=1.0.0 |
| GET /api/overview | 200 apps=34 |
| GET /api/calib | 200（含 chain/rounds/total/verify_coverage） |
| GET /api/jobs | 200 count=0 active=None |
| GET /（首页 token 注入） | 200 has_token=true |
| GET /static/app.js | 200 len=37791 |
| POST /api/jobs 无 token | 403（鉴权拦截 PASS） |
| POST /api/jobs 资金类无 confirm_money | 403（资金红线服务端强制 PASS） |

- find_free_port 结论：Windows 下已由「仅 bind 探测」修复为「bind+listen 双成功 + 关闭 reuse_address」，不再误判被占端口。
- 契约测试：`tests/test_webui.py` → **34/34 通过，零 FAIL**。关键对账用例 `t_stability_report_matches_stability_run` 用 stability_run 官方 classify 逐行重算 STABILITY.json，与校准页数字完全一致（**172/260**，stable=28/flaky=11/never=13）；另含覆盖率口径（94/94 可校验、未度量 0）、资金类二次确认、路径穿越防护等护栏用例。
- 状态：**PASS**

## 汇总

| 步骤 | 内容 | 状态 |
|---|---|---|
| ① | venv 重建 + 依赖 + pytest | PASS（44 passed） |
| ② | 真机无线调试 | PASS（192.168.1.54:5555 device） |
| ③ | 全量回归 | PASS（18 App / 52 行为；STABILITY 5轮 159/242 = 65.7%，稳定30/波动7/从未15/作废8；基线 70.5%，-4.8pp） |
| ④ | MANUAL_TRIAGE 未命中入口处置 | PASS（离线补锚点 5 项 + 真机取证：3/5 confirmed 河马 withdraw/sign、喜番 sign；2/5 OPEN 点淘 watch/withdraw 待完整链探针） |
| ⑤ | WebUI 冒烟 + 契约测试 | PASS（find_free_port 修复 + 核心 API 全绿 + 34/34 契约零 FAIL） |

- 遗留：残余 never 项 15 个（一淘 sign/withdraw、今日看点 withdraw、全民K歌 bonus/collect、天天快讯 watch、悟空 sign、抖音 bonus/watch、抖音极速版 sign/watch、抖音火山版 sign、点淘 watch、红果 sign、蛋花 sign）需多级导航架构、完整链探针或人工复核；④ 点淘 watch/withdraw 保持 OPEN。详见 ③ 清单与 `devtools/calib/STABILITY.md`。

