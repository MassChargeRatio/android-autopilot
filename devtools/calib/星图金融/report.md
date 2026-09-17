# 校准报告 · 星图金融

- 包名: `com.suning.mobile.epa`
- 前台包名: `com.suning.mobile.epa`
- UI 节点数: 233（已剔除状态栏通知）
- **入口命中率: 1/2**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 1/4（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 星图金融 (com.suning.mobile.epa)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=235 前台=com.suning.mobile.epa 耗时=6.1s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (961,2152)，点击并等待 7.0s
- 二级页: 节点=171 入口命中=0/2

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 未命中 | candidates=['人人领', '任务中心', '领好礼', '任务']  |
| bonus | click_first | 命中 | candidates=['领红包', '红包', '现金红包', '抽奖'] -> '领红包' @(936, 1013) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| collect | 1 | 0 | click_first | 未命中 | candidates=['人人领', '任务中心', '领好礼', '任务']  |
| collect | 1 | 1 | think | 无需锚点 | think |
| collect | 1 | 2 | click_text | 未命中 | text='立即领取' 候选数=0 |
| bonus | 1 | 0 | click_first | 命中 | candidates=['领红包', '红包', '现金红包', '抽奖'] -> '领红包' @(936, 1013) |
| bonus | 1 | 1 | think | 无需锚点 | think |
| bonus | 1 | 2 | click_text | 未命中 | text='立即领取' 候选数=0 |
| bonus | 1 | 3 | wait | 无需锚点 | wait |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 天天领红包 | `com.suning.mobile.epa:id/title` | (936, 1013) | (200, 93) | False | 领,领红包,红包 |
| 红包签到 | `com.suning.mobile.epa:id/item_text` | (675, 451) | (168, 57) | False | 签到,红包 |
| 领现金 | `com.suning.mobile.epa:id/item_text` | (945, 451) | (126, 57) | False | 领,现金 |
| 抽红包 | `com.suning.mobile.epa:id/title` | (136, 1013) | (200, 93) | False | 红包 |
| 早起打卡 | `com.suning.mobile.epa:id/title` | (136, 1235) | (200, 93) | False | 打卡 |
| 迎新福利 | `com.suning.mobile.epa:id/title` | (136, 1457) | (200, 93) | False | 福利 |
| A股收评：大盘震荡整理，培育钻石、创新药、MLCC领涨！ | `com.suning.mobile.epa:id/system_notice_content` | (648, 1573) | (672, 48) | False | 领 |
| 福利 | `com.suning.mobile.epa:id/indicator_title` | (918, 1732) | (90, 61) | False | 福利 |
| 可借(元) | `com.suning.mobile.epa:id/loan_product_num_desc_t` | (284, 1889) | (112, 41) | False | 元 |
| 可用(元) | `com.suning.mobile.epa:id/loan_product_num_desc_t` | (869, 1889) | (112, 41) | False | 元 |
| 我的 | `com.suning.mobile.epa:id/tab_name` | (972, 2188) | (60, 41) | False | 我的 |
| 搜索 | `com.suning.mobile.epa:id/new_head_search_immedia` | (618, 171) | (72, 48) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (961, 2152)
- 节点数: 171
- **二级页入口命中: 0/2**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 未命中 | candidates=['人人领', '任务中心', '领好礼', '任务']  |
| bonus | click_first | 未命中 | candidates=['领红包', '红包', '现金红包', '抽奖']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 领现金 | `com.suning.mobile.epa:id/icon_name` | (943, 837) | False | 领,现金 |
| 我的 | `com.suning.mobile.epa:id/tv_title` | (96, 170) | True | 我的 |
| 我的积分 | `com.suning.mobile.epa:id/tv_right_name` | (204, 545) | False | 我的 |
| 早起打卡 | `com.suning.mobile.epa:id/icon_name` | (338, 837) | False | 打卡 |
| 我的资产 | `com.suning.mobile.epa:id/total_assets_title` | (168, 982) | False | 我的 |
| 总资产(元) | `com.suning.mobile.epa:id/total_assets_desc` | (157, 1081) | False | 元 |
| 我的 | `com.suning.mobile.epa:id/tab_name` | (972, 2188) | False | 我的 |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
