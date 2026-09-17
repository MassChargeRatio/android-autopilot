# 校准报告 · 悟空浏览器

- 包名: `com.cat.readall`
- 前台包名: `com.cat.readall`
- UI 节点数: 159（已剔除状态栏通知）
- **入口命中率: 1/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 1/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 悟空浏览器 (com.cat.readall)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=172 前台=com.cat.readall 耗时=14.0s（节点数达标）
- 点掉弹窗按钮: 关闭 @(967, 1905)
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏最右侧的『我的』标签中心
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏最右侧的『我』标签中心
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏的个人中心（我的）标签中心
- probe: 提示词未命中，尝试下一个 -> 定位屏幕右下角的个人中心头像/图标中心
- probe: 全部提示词均未命中

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '阅读赚金币', '立即签到']  |
| watch | click_first | 未命中 | candidates=['任务中心', '看新闻赚钱', '阅读赚钱', '金币']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(960, 2141) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['签到', '每日签到', '阅读赚金币', '立即签到']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 未命中 | candidates=['领取', '领金币']  |
| watch | 1 | 0 | click_first | 未命中 | candidates=['任务中心', '看新闻赚钱', '阅读赚钱', '金币']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['去完成', '阅读', '看视频']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(960, 2141) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 看剧 | `com.cat.readall:id/mp` | (330, 2141) | (96, 57) | False | 看剧 |
| 赚钱 | `com.cat.readall:id/mp` | (540, 2141) | (96, 57) | False | 赚钱 |
| 我的 | `com.cat.readall:id/mp` | (960, 2141) | (96, 57) | False | 我的 |
| 找剧 | `` | (102, 304) | (156, 99) | True |  |
| 小说 | `` | (426, 304) | (156, 99) | True |  |
| 漫剧 | `` | (582, 304) | (156, 99) | True |  |
| 短剧 | `` | (738, 304) | (156, 99) | True |  |
| 影视 | `` | (894, 304) | (156, 99) | True |  |
| 动漫 | `` | (1026, 304) | (108, 99) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |
