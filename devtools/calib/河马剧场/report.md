# 校准报告 · 河马剧场

- 包名: `com.dz.hmjc`
- 前台包名: `com.dz.hmjc`
- UI 节点数: 139（已剔除状态栏通知）
- **入口命中率: 1/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 1/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 河马剧场 (com.dz.hmjc)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=138 前台=com.dz.hmjc 耗时=6.7s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (966,2141)，点击并等待 8.0s
- 二级页: 节点=191 入口命中=1/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '看剧得金币', '立即签到']  |
| watch | click_first | 未命中 | candidates=['赚钱', '任务', '看剧赚钱', '福利中心']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(972, 2132) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['签到', '每日签到', '看剧得金币', '立即签到']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 未命中 | candidates=['领取', '领金币']  |
| watch | 1 | 0 | click_first | 未命中 | candidates=['赚钱', '任务', '看剧赚钱', '福利中心']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['看剧', '去完成']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(972, 2132) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 得129金币 | `com.dz.hmjc:id/tv_welfare_receive` | (953, 880) | (166, 60) | True | 金币 |
| 我的 | `com.dz.hmjc:id/textView_only` | (972, 2132) | (92, 54) | False | 我的 |
| 在追 | `` | (295, 161) | (148, 138) | True |  |
| 剧单 | `` | (443, 161) | (148, 138) | True |  |
| 短视频 | `` | (614, 161) | (194, 138) | True |  |
| 推荐 | `` | (785, 161) | (148, 138) | True |  |
| 日久见君心 | `com.dz.hmjc:id/tv_name_new` | (142, 1699) | (215, 58) | True |  |
| 演员·雷艺昊 | `com.dz.hmjc:id/tvActorFirst` | (157, 1774) | (244, 59) | True |  |
| 展开 | `com.dz.hmjc:id/tvCollapse` | (833, 1842) | (80, 53) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (966, 2141)
- 节点数: 191
- **二级页入口命中: 1/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '看剧得金币', '立即签到']  |
| watch | click_first | 未命中 | candidates=['赚钱', '任务', '看剧赚钱', '福利中心']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(796, 568) |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 12.9元 | `com.dz.hmjc:id/tv_bubble` | (409, 458) | False | 元 |
| 福利 | `com.dz.hmjc:id/tv` | (358, 568) | False | 福利 |
| 提现 | `com.dz.hmjc:id/tv` | (577, 568) | False | 提现 |
| 我的商城 | `com.dz.hmjc:id/tv` | (796, 568) | False | 我的 |
| 2026元津贴活动，限时限量，试试手气！ | `com.dz.hmjc:id/tv_title` | (749, 768) | False | 元 |
| 我的 | `com.dz.hmjc:id/textView_only` | (972, 2132) | False | 我的 |
| 怦然北极熊 | `com.dz.hmjc:id/tv_account` | (355, 268) | True |  |
| ID: 2402026264 | `com.dz.hmjc:id/tv_id` | (339, 331) | True |  |
| 浏览记录 | `` | (185, 998) | True |  |
| 在追 | `` | (381, 998) | True |  |
| 点赞 | `` | (531, 998) | True |  |
| 发布 | `` | (681, 998) | True |  |
| 编辑 | `com.dz.hmjc:id/btn_edit_enter` | (976, 998) | True |  |
| 全部 | `com.dz.hmjc:id/tv_category` | (139, 1101) | True |  |
| 七天内 | `com.dz.hmjc:id/tv_category` | (332, 1101) | True |  |
| 三十天内 | `com.dz.hmjc:id/tv_category` | (565, 1101) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
