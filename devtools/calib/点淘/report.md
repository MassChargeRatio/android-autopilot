# 校准报告 · 点淘

- 包名: `com.taobao.live`
- 前台包名: `com.taobao.live`
- UI 节点数: 286（已剔除状态栏通知）
- **入口命中率: 0/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 2/7（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 点淘 (com.taobao.live)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=294 前台=com.taobao.live 耗时=10.6s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (972,2164)，点击并等待 7.0s
- 二级页: 节点=64 入口命中=0/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 未命中 | candidates=['任务中心', '天天领', '福利', '领奖']  |
| watch | click_first | 未命中 | candidates=['看直播', '看视频', '任务', '逛直播间']  |
| withdraw | click_first | 未命中 | candidates=['我的', '我']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| collect | 1 | 0 | click_first | 未命中 | candidates=['任务中心', '天天领', '福利', '领奖']  |
| collect | 1 | 1 | think | 无需锚点 | think |
| collect | 1 | 2 | click_first | 命中 | candidates=['领取', '领红包', '去完成'] -> '领取' @(473, 692) |
| watch | 1 | 0 | click_first | 未命中 | candidates=['看直播', '看视频', '任务', '逛直播间']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | swipe | 无需锚点 | swipe |
| watch | 1 | 3 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 未命中 | candidates=['我的', '我']  |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本 -> '50元' |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 立即签到 | `` | (711, 561) | (128, 43) | False | 签到,立即签到 |
| 待领取 | `` | (473, 692) | (105, 47) | False | 领,领取 |
| 去领取 | `` | (980, 692) | (105, 47) | False | 领,领取 |
| 赚元宝兑权益 | `` | (702, 298) | (258, 49) | False | 元 |
| 领券更便宜 | `` | (354, 301) | (175, 40) | False | 领 |
| 最高50元话费 | `` | (949, 301) | (213, 40) | False | 元 |
| 元 | `` | (1014, 1448) | (35, 49) | False | 元 |
| 惊喜加补4.2元 | `` | (145, 2136) | (227, 47) | False | 元 |
| 元 | `` | (503, 2202) | (35, 23) | False | 元 |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (972, 2164)
- 节点数: 64
- **二级页入口命中: 0/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 未命中 | candidates=['任务中心', '天天领', '福利', '领奖']  |
| watch | click_first | 未命中 | candidates=['看直播', '看视频', '任务', '逛直播间']  |
| withdraw | click_first | 未命中 | candidates=['我的', '我']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
