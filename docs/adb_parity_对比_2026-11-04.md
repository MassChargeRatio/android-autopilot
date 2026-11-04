# adb_parity 对比（u2 vs adb_backend）— 2026-11-04

> AUTOP-2026-11-04-真机族 任务4（u2 评估阶段 A 后半）。
> 前置：`temp/adb_backend.py`（M1 交付）。红线：只读对比，不切引擎、不改 device_session.py。
> 探针：`temp/adb_parity_probe.py`（v4 双子进程编排定稿）；原始 XML/JSON 落 `temp/parity_*`。

## 结论先行

| 门禁项 | 结果 | 判定 |
|---|---|---|
| 前台包名 100% 一致 | 快手/抖音/美团 3/3 一致（四轮全部通过） | ✅ PASS |
| 首屏文本集 Jaccard ≥ 0.9 | 快手 0.275 / 抖音 0.44(v4有效轮) / 美团 0.71–0.79 | ❌ FAIL（阈值未达） |

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

## 对阶段 B 的建议

1. 前台包名/截图/坐标类原语：对等已证，可切。
2. dump 类原语：切换前先解决 ②（feed 页 idle 失败路径）与 ③（stale 首拉校验）；
   文本集 Jaccard 门禁改在**静态页**（如设置页/美团类稳定页）执行，或改用
   「稳定 chrome 元素覆盖率」类指标（动态 feed 内容不可复现，文本集全量比对无判别力）。
3. 混跑/影子并跑不可行（①），影子验证只能按「同一页面先后两会话」方式做（本探针 v4 即此）。
