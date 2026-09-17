# 校准报告 · 蛋花免费小说

- 包名: `com.eggflower.read`
- 前台包名: `com.eggflower.read`
- UI 节点数: 247（已剔除状态栏通知）
- **入口命中率: 2/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 3/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 蛋花免费小说 (com.eggflower.read)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=247 前台=com.eggflower.read 耗时=13.3s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (939,2152)，点击并等待 8.0s
- 二级页: 节点=141 入口命中=2/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '立即签到', '幸运签']  |
| watch | click_first | 命中 | candidates=['福利', '任务', '看书赚钱', '金币中心'] -> '福利' @(540, 2148) |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(450, 709) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['签到', '每日签到', '立即签到', '幸运签']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 命中 | candidates=['领取', '领金币'] -> '领金币' @(606, 2130) |
| watch | 1 | 0 | click_first | 命中 | candidates=['福利', '任务', '看书赚钱', '金币中心'] -> '福利' @(540, 2148) |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['去看书', '去完成', '阅读']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(450, 709) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 领金币 | `com.eggflower.read:id/g1x` | (606, 2130) | (73, 54) | False | 领,领金币,金币 |
| 凡人修仙：我的身体状态每日刷新 | `com.eggflower.read:id/g3x` | (450, 709) | (336, 115) | False | 我的 |
| 全民公路求生：我的房车无限进化 | `com.eggflower.read:id/g3x` | (960, 709) | (168, 115) | False | 我的 |
| 福利 | `com.eggflower.read:id/g3y` | (540, 2148) | (96, 65) | False | 福利 |
| 我的 | `com.eggflower.read:id/g3y` | (953, 2148) | (96, 65) | False | 我的 |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (939, 2152)
- 节点数: 141
- **二级页入口命中: 2/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '立即签到', '幸运签']  |
| watch | click_first | 命中 | candidates=['福利', '任务', '看书赚钱', '金币中心'] -> '福利' @(540, 2148) |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(575, 627) |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 领金币 | `com.eggflower.read:id/g1x` | (606, 2130) | False | 领,领金币,金币 |
| 我的订单 | `com.eggflower.read:id/dqf` | (575, 627) | False | 我的 |
| 我的预约 | `com.eggflower.read:id/dqf` | (785, 627) | False | 我的 |
| 我的下载 | `com.eggflower.read:id/dqf` | (984, 627) | False | 我的 |
| 金币 | `` | (162, 854) | False | 金币 |
| 余额(元) | `` | (565, 854) | False | 元 |
| 提现 | `com.eggflower.read:id/jyh` | (930, 855) | False | 提现 |
| 福利 | `com.eggflower.read:id/g3y` | (540, 2148) | False | 福利 |
| 我的 | `com.eggflower.read:id/g3y` | (953, 2148) | False | 我的 |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
