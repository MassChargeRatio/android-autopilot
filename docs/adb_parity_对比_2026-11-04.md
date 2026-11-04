# adb_parity 对比（u2 vs adb_backend）— 2026-11-04

> AUTOP-2026-11-04-真机族 任务4（u2 评估阶段 A 后半）。
> 前置：`temp/adb_backend.py`（M1 交付）。红线：只读对比，不切引擎、不改 device_session.py。
> 探针：`temp/adb_parity_probe.py`（v4 双子进程编排定稿）；原始 XML/JSON 落 `temp/parity_*`。

## 结论先行

| 门禁项 | 结果 | 判定 |
|---|---|---|
| 前台包名 100% 一致 | 快手/抖音/美团 3/3 一致（四轮全部通过） | ✅ PASS |
| 首屏文本集 Jaccard ≥ 0.9 | 快手 0.275 / 抖音 0.44(v4有效轮) / 美团 0.71–0.79 | ❌ FAIL（阈值未达） |
| 结构对等：res-id Jaccard ≥ 0.9（**P2 补测，替换文本门禁**） | 快手 0.959 / 美团 0.980 达标；抖音 OPEN（adb 侧 dump 0 B） | ⬜ 2/3 PASS，整体 OPEN（详见「结构对等性」节） |

**判定：严格按门禁 FAIL；但差异根因是「动态 feed 页 + 采样方法论」而非两后端引擎失配。**
两后端同为 uiautomator accessibility 树，同屏稳定 chrome（底栏/功能区/搜索框）完全一致；
文本差来自三处非引擎因素（见下）。**给阶段 B（切换）的关键输入不是 Jaccard，而是两条
工程硬约束（见「工程发现」）——它们才是切换 adb 纯引擎的真实成本。**

## 原始数据（v4/v5 最终轮，2026-11-04 09:20–09:50）

| App | 前台(u2) | 前台(adb) | u2 nodes | adb nodes | adb bytes | u2 文本(滤后) | adb 文本(滤后) | Jaccard(滤后) |
|---|---|---|---|---|---|---|---|---|
| 快手 | com.smile.gifmaker | 同 ✅ | 201 | 124 | 44,318 | 29 | 22 | 0.275 |
| 抖音 | com.ss.android.ugc.aweme | 同 ✅ | 347 | 289 | 105,460(v4轮) | 47 | 43 | 0.436(v4) |
| 美团 | com.sankuai.meituan | 同 ✅ | 228 | 156 | 53,777 | 38 | 39 | 0.711 |

多轮复测：美团 5/5 稳定产出真实 dump；快手 3/5、抖音 1/5（feed idle 失败，见工程发现②）。

## 文本差构成（抽样复核，非引擎失配的证据）

1. **feed 轮播**（主因，双冷启动各采各的视频/推荐卡）：
   快手 @墨菲剪辑 vs @筱柒影院（不同视频的作者/标题/互动数）；
   美团推荐流 塔斯汀/蜜雪冰城 vs 瑞幸（每次冷启动推荐位不同）。
2. **u2 独有系统层条目**：`概览`/`返回`/`电池电量为百分之100`（TalkBack 类播报节点）——
   u2 dump 层级包含 adb 命令行 dump 不含的无障碍服务附加层。
3. 已过滤噪声（两后端可见性不同，与引擎无关）：状态栏时钟/网速/信号/悬挂通知/systemui。

## 工程发现（阶段 B 切换的真实成本，比 Jaccard 更重要）

① **u2 与 adb `uiautomator dump` 设备级互斥**：设备侧 uiautomator2 server（atx-agent）
存活时，adb 侧 dump 冲突失败 → `pull` 拉回**陈旧工件**（v1 三 app 全假数据即此，
`adb_root_pkg=com.taobao.trip` 而前台是快手）。u2 主机连接存活时 kill server 会被即时复活。
→ 切换必须**整会话级**二选一，不存在混跑/影子并跑模式（评估文档 §阶段A「并跑」设想不成立）。

② **adb `uiautomator dump` 在永不 idle 的视频 feed 上概率性失败**（"could not get idle
state" 族）：快手/抖音多次 5 连试全败。u2 的 dump_hierarchy 无此问题。
→ adb 纯引擎必须为 feed 页配 dump 失败重试/截图降级路径（现有 adb_backend 重试不够）。

③ adb_backend.dump 的 stale 防护（3 连同字节数）**首拉不设防**：单次陈旧 pull 直接透传
（本轮 v1 实证）。建议：pull 后校验 root package == foreground() 再返回。

## 结构对等性（resource-id 集合，P2 补测，2026-11-04）

> 目的：文本 Jaccard 受 feed 轮播/双冷启动内容噪声干扰，无法判别引擎是否失配；
> resource-id 集合与页面内容无关（同一静态 chrome 的元素 id 恒定），是结构对等性的可用指标。
> 数据来源：仅 `temp/parity_*` 已采集 XML（不连设备）。

统计脚本：`temp/parity_resid_jaccard.py`（只读 `temp/parity_*` XML，无设备连接）。
口径：**app 自身包名域 resource-id**（`<pkg>:id/*`），剔除 u2 多窗口 dump 带入的
`com.android.systemui` / `com.vivo.upslide` overlay 节点；节点数按 ElementTree 解析计。

| App | u2 nodes | adb nodes | u2 res-id(app) | adb res-id(app) | 交集 | 并集 | Jaccard | 判定(≥0.9) |
|---|---|---|---|---|---|---|---|---|
| 快手 | 194 | 124 | 74 | 71 | 71 | 74 | **0.959** | ✅ PASS |
| 抖音 | 340 | — (adb XML 0 B) | — | — | — | — | **OPEN** | ⬜ OPEN（缺 adb 侧 dump） |
| 美团 | 228 | 156 | 50 | 51 | 50 | 51 | **0.980** | ✅ PASS |

参考：若按**全量 res-id**（不剔 overlay 窗口）计，快手 0.603 / 美团 0.526 —— 该差异 100% 来自
u2 的 dump_hierarchy 是**多窗口** dump（含 systemui 通知栏、vivo 上滑层），adb 的
`uiautomator dump` 是**单窗口** dump；与引擎定位能力无关，故门禁指标必须用 app 域口径。

**结构门禁（res-id Jaccard ≥ 0.9，三 app 全过）**：**未通过（OPEN，非 FAIL）**。
可算的 2/3 均大幅高于阈值（0.959 / 0.980），抖音因 adb 侧 XML 0 字节无数据，不下通过结论。

### 差集明细（为什么不是 1.0）

- 快手 only-u2 3 个：`slide_play_photo_disclaimer_container/_icon_left/_text`（图片轮播放映免责层，
  仅在特定 feed 卡片出现，内容相关、结构无关）；only-adb **0 个**。
- 美团 only-adb 1 个：`bae7`（混淆短 id，adb 抓到时存在、u2 侧未渲染）；only-u2 **0 个**。
- 抖音：仅 u2 侧 XML 可用（340 nodes，含 aweme 域 res-id），adb 侧 `parity_抖音_adb.json.xml` 为 0 B，
  与「工程发现②」记录一致——`uiautomator dump` 在抖音永不 idle 的 feed 上失败，未产出工件。

### 结构对等性的结论价值

1. **两后端元素结构对等（app 域 res-id 重合度 ≥0.959）**：定位原语（selector 解析、res-id 定位）
   在两边指向同一批节点，任务 4 文本 Jaccard 未达阈（0.275/0.436/0.711）**确认属内容噪声，非引擎失配**。
2. 快手/美团两项达标即足够支撑「结构对等」的判断；抖音的缺口属于**采集可用性**问题（feed idle 失败），
   不是结构不对等——但按红线，仍标 OPEN，不用推断补数。
3. 抖音若要闭合 OPEN：需一次 adb 侧成功 dump（本卡禁连设备，不在本卡范围；建议随阶段 B 的
   feed 页 dump 重试/截图降级路径一并验证）。

> ⚠️ 数据源勘误：`temp/parity_result.json` 中的 `jaccard_resid` 字段值（快手 0.0 / 抖音 1.0 / 美团 0.0）
> **不可用**——抖音 adb 侧为 0 节点却得 1.0，快手/美团有 100+ res-id 却得 0.0，说明原探针 res-id
> 提取口径有 bug（疑对 adb 侧 XML 取不到属性后按空集比较）。本节数据全部来自独立脚本重算，
> 不复用该字段；后续引用请以本节表为准。

## 对阶段 B 的建议

1. 前台包名/截图/坐标类原语：对等已证，可切。
2. dump 类原语：切换前先解决 ②（feed 页 idle 失败路径）与 ③（stale 首拉校验）；
   文本集 Jaccard 门禁改在**静态页**（如设置页/美团类稳定页）执行，或改用
   「稳定 chrome 元素覆盖率」类指标（动态 feed 内容不可复现，文本集全量比对无判别力）。
3. 混跑/影子并跑不可行（①），影子验证只能按「同一页面先后两会话」方式做（本探针 v4 即此）。
