# 校准报告 · 今日看点极速版

- 包名: `com.jinrikd.news`
- 前台包名: `com.jinrikd.news`
- UI 节点数: 8（已剔除状态栏通知）
- **入口命中率: 0/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 0/9（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 今日看点极速版 (com.jinrikd.news)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=71 前台=com.jinrikd.news 耗时=4.8s（节点数达标）
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏最右侧的『我的』标签中心
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏最右侧的『我』标签中心
- probe: VLM 命中『定位屏幕底部导航栏的个人中心（我的）标签中心』-> (945,2138)，点击并等待 8.0s
- 二级页: 节点=32 入口命中=2/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['直接领取', '签到', '立即签到', '每日签到']  |
| watch | click_first | 未命中 | candidates=['看视频', '看视频赚钱', '任务中心', '金币']  |
| withdraw | click_first | 未命中 | candidates=['我的', '我']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['直接领取', '签到', '立即签到', '每日签到']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | reward | 未命中 | pattern='直接领取(?P<amount>[0-9]+)\\s*(?P<unit>金币)' 当前页文本无匹配 |
| sign | 1 | 3 | click_first | 未命中 | candidates=['直接领取322金币', '领取']  |
| watch | 1 | 0 | click_first | 未命中 | candidates=['看视频', '看视频赚钱', '任务中心', '金币']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['看视频领金币', '去完成', '领金币']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 未命中 | candidates=['我的', '我']  |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (945, 2138)
- 节点数: 32
- **二级页入口命中: 2/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['直接领取', '签到', '立即签到', '每日签到'] -> '直接领取' @(540, 1813) |
| watch | click_first | 命中 | candidates=['看视频', '看视频赚钱', '任务中心', '金币'] -> '金币' @(333, 1385) |
| withdraw | click_first | 未命中 | candidates=['我的', '我']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 直接领取322金币 | `com.jinrikd.news:id/b30` | (540, 1813) | True | 领,领取,金币 |
| +6440金币 | `com.jinrikd.news:id/q6` | (333, 1385) | False | 金币 |
| +100.00元 | `com.jinrikd.news:id/c__` | (748, 1385) | False | 元 |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
