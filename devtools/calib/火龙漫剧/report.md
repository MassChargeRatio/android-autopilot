# 校准报告 · 火龙漫剧

- 包名: `com.tencent.kairos`
- 前台包名: `com.tencent.kairos`
- UI 节点数: 77（已剔除状态栏通知）
- **入口命中率: 2/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 2/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 火龙漫剧 (com.tencent.kairos)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=71 前台=com.tencent.kairos 耗时=4.8s（节点数达标）
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏最右侧的『我的』标签中心
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我』标签中心』-> (918,2141)，点击并等待 8.0s
- 二级页: 节点=80 入口命中=2/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '每日签到', '去签到', '天天有礼'] -> '签到' @(720, 2093) |
| watch | click_first | 未命中 | candidates=['看剧赚钱', '任务', '赚钱', '福利中心']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(802, 1166) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 命中 | candidates=['签到', '每日签到', '去签到', '天天有礼'] -> '签到' @(720, 2093) |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 未命中 | candidates=['立即签到', '领取']  |
| watch | 1 | 0 | click_first | 未命中 | candidates=['看剧赚钱', '任务', '赚钱', '福利中心']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['看短剧', '看剧', '去完成']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(802, 1166) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 沉睡十万年，我的宗门只剩三个弟子 | `` | (802, 1166) | (471, 132) | False | 我的 |
| 签到 | `` | (720, 2093) | (54, 32) | False | 签到 |
| 福利 | `` | (666, 2130) | (96, 57) | False | 福利 |
| 我的 | `` | (918, 2130) | (96, 57) | False | 我的 |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (918, 2141)
- 节点数: 80
- **二级页入口命中: 2/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '每日签到', '去签到', '天天有礼'] -> '签到' @(720, 2093) |
| watch | click_first | 未命中 | candidates=['看剧赚钱', '任务', '赚钱', '福利中心']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(918, 2130) |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 签到 | `` | (720, 2093) | False | 签到 |
| 福利 | `` | (666, 2130) | False | 福利 |
| 我的 | `` | (918, 2130) | False | 我的 |
| Zheng | `` | (325, 298) | True |  |
| 简介空空的，快来填写吧~ | `` | (540, 525) | True |  |
| 编辑 | `` | (990, 757) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
