# 校准报告 · 今日头条极速版

- 包名: `com.ss.android.article.lite`
- 前台包名: `com.ss.android.article.lite`
- UI 节点数: 124（已剔除状态栏通知）
- **入口命中率: 1/4**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 2/12（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 今日头条极速版 (com.ss.android.article.lite)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 达到最大等待 60.0s 仍未就绪，节点=15，按当前页继续
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (970,2145)，点击并等待 7.0s
- 二级页: 节点=208 入口命中=2/4

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['开宝箱', '签到', '每日签到', '立即签到']  |
| watch | click_first | 未命中 | candidates=['看资讯赚金币', '看视频', '任务中心', '金币']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(972, 2182) |
| bonus | click_first | 未命中 | candidates=['限时预约领金币', '预约', '红包']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['开宝箱', '签到', '每日签到', '立即签到']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | reward | 未命中 | pattern='最高(?P<amount>[0-9]+)\\s*(?P<unit>金币)' 当前页文本无匹配 |
| sign | 1 | 3 | click_first | 命中 | candidates=['开', '去开宝箱', '领取'] -> '开' @(540, 1683) |
| watch | 1 | 0 | click_first | 未命中 | candidates=['看资讯赚金币', '看视频', '任务中心', '金币']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['去完成', '领取']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(972, 2182) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |
| bonus | 1 | 0 | click_first | 未命中 | candidates=['限时预约领金币', '预约', '红包']  |
| bonus | 1 | 1 | think | 无需锚点 | think |
| bonus | 1 | 2 | click_text | 未命中 | text='去预约' 候选数=0 |
| bonus | 1 | 3 | click_first | 未命中 | candidates=['领取', '立即领取']  |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 开宝箱 | `com.ss.android.article.lite:id/eyv` | (600, 2111) | (96, 47) | False | 开宝箱 |
| 任务 | `com.ss.android.article.lite:id/kp` | (540, 2182) | (54, 39) | False | 任务 |
| 我的 | `com.ss.android.article.lite:id/kp` | (972, 2182) | (54, 39) | False | 我的 |
| 发布，按钮 | `com.ss.android.article.lite:id/gmo` | (873, 174) | (96, 96) | True |  |
| 豆包 AI，按钮 | `com.ss.android.article.lite:id/i_z` | (999, 174) | (96, 96) | True |  |
| 关注 | `` | (77, 306) | (155, 108) | True |  |
| 推荐 | `` | (232, 306) | (155, 108) | True |  |
| 热榜 | `` | (387, 306) | (154, 108) | True |  |
| 短剧 | `` | (540, 306) | (152, 108) | True |  |
| 影视 | `` | (693, 306) | (154, 108) | True |  |
| 发现 | `` | (847, 306) | (155, 108) | True |  |
| 视频 | `` | (944, 306) | (38, 108) | True |  |
| 听一听开关 | `com.ss.android.article.lite:id/bkp` | (1021, 306) | (117, 108) | True |  |
| 近镜头｜金砖之约，共绘全球南方新图景 文章 | `com.ss.android.article.lite:id/adk` | (540, 402) | (1080, 81) | True |  |
| 习近平就深化金砖合作提出5项倡议 文章 | `com.ss.android.article.lite:id/adk` | (540, 479) | (1080, 72) | True |  |
| 智能时代，山东如何织密这张“安全网”？ 文章 | `com.ss.android.article.lite:id/adk` | (540, 551) | (1080, 72) | True |  |
| 保丰产、护生态，助力希望的田野增产增收 文章 | `com.ss.android.article.lite:id/adk` | (540, 623) | (1080, 72) | True |  |
| 活力中国调研行 | 河南农机群星闪耀 文章 | `com.ss.android.article.lite:id/adk` | (540, 696) | (1080, 74) | True |  |
| 山东枣庄70岁小学老师，来京照看孙辈，退休金让人不敢相信！ | `com.ss.android.article.lite:id/in0` | (540, 844) | (984, 138) | True |  |
| 播放视频 | `com.ss.android.article.lite:id/ll` | (540, 1201) | (144, 144) | True |  |
| 不感兴趣 | `` | (1017, 1510) | (30, 30) | True |  |
| 摸臀事件都被网友拍成段子，脑洞大开不得不服太有才了 | `com.ss.android.article.lite:id/in0` | (540, 1683) | (984, 138) | True |  |
| 播放视频 | `com.ss.android.article.lite:id/ll` | (540, 2025) | (144, 114) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (970, 2145)
- 节点数: 208
- **二级页入口命中: 2/4**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['开宝箱', '签到', '每日签到', '立即签到']  |
| watch | click_first | 命中 | candidates=['看资讯赚金币', '看视频', '任务中心', '金币'] -> '金币' @(346, 411) |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(156, 897) |
| bonus | click_first | 未命中 | candidates=['限时预约领金币', '预约', '红包']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 现金(元) | `com.ss.android.article.lite:id/g7z` | (595, 411) | False | 元,现金 |
| 去提现 | `com.ss.android.article.lite:id/g94` | (936, 411) | True | 提现,去提现 |
| 领现金 | `com.ss.android.article.lite:id/ekx` | (207, 1182) | False | 领,现金 |
| 金币 | `com.ss.android.article.lite:id/g97` | (346, 411) | False | 金币 |
| 立领150 | `` | (587, 564) | False | 领 |
| 现金 | `` | (756, 564) | False | 现金 |
| 1000元 | `` | (985, 564) | False | 元 |
| 我的功能 | `com.ss.android.article.lite:id/g8y` | (156, 897) | False | 我的 |
| 去完成 | `com.ss.android.article.lite:id/m3z` | (921, 1861) | True | 去完成 |
| >15字且带图和定位，得0.3元 | `com.ss.android.article.lite:id/m41` | (337, 1898) | False | 元 |
| 开宝箱 | `com.ss.android.article.lite:id/eyv` | (600, 2111) | False | 开宝箱 |
| 任务 | `com.ss.android.article.lite:id/kp` | (540, 2182) | False | 任务 |
| 我的 | `com.ss.android.article.lite:id/kp` | (972, 2182) | False | 我的 |
| 扫一扫 | `com.ss.android.article.lite:id/lrj` | (96, 162) | True |  |
| 来访 | `com.ss.android.article.lite:id/gas` | (720, 162) | True |  |
| 发布 | `com.ss.android.article.lite:id/gap` | (852, 162) | True |  |
| 设置 | `com.ss.android.article.lite:id/gay` | (984, 162) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
