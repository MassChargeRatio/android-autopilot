# 校准报告 · 抖音极速版

- 包名: `com.ss.android.ugc.aweme.lite`
- 前台包名: `com.ss.android.ugc.aweme.lite`
- UI 节点数: 188（已剔除状态栏通知）
- **入口命中率: 2/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 3/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 抖音极速版 (com.ss.android.ugc.aweme.lite)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=188 前台=com.ss.android.ugc.aweme.lite 耗时=36.5s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (950,2106)，点击并等待 7.0s
- 二级页: 节点=263 入口命中=2/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '每日签到', '开宝箱', '领金币'] -> '开宝箱' @(627, 2058) |
| watch | click_first | 未命中 | candidates=['刷视频', '看视频赚金币', '任务中心', '金币朋友']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我' @(971, 2141) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 命中 | candidates=['签到', '每日签到', '开宝箱', '领金币'] -> '开宝箱' @(627, 2058) |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 命中 | candidates=['立即签到', '领取', '开'] -> '开' @(627, 2058) |
| watch | 1 | 0 | click_first | 未命中 | candidates=['刷视频', '看视频赚金币', '任务中心', '金币朋友']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['去完成', '看视频']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我' @(971, 2141) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 开宝箱 | `` | (627, 2058) | (108, 42) | False | 开宝箱 |
| 同城，按钮 | `` | (198, 162) | (96, 132) | True |  |
| 团购，按钮 | `` | (315, 162) | (138, 132) | True |  |
| 关注，按钮 | `` | (453, 162) | (138, 132) | True |  |
| 商城，按钮 | `` | (591, 162) | (138, 132) | True |  |
| 推荐，已选中，按钮 | `` | (729, 162) | (138, 132) | True |  |
| 侧边栏 | `` | (66, 162) | (132, 132) | True |  |
| 拍摄 | `` | (864, 162) | (132, 132) | True |  |
| 搜索 | `` | (1005, 162) | (150, 132) | True |  |
| 点击进入直播间，按钮 | `com.ss.android.ugc.aweme.lite:id/g_x` | (540, 1033) | (1080, 2067) | True |  |
| @小初bb（9.9..） | `com.ss.android.ugc.aweme.lite:id/qza` | (263, 1913) | (455, 68) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (950, 2106)
- 节点数: 263
- **二级页入口命中: 2/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '每日签到', '开宝箱', '领金币'] -> '开宝箱' @(627, 2058) |
| watch | click_first | 未命中 | candidates=['刷视频', '看视频赚金币', '任务中心', '金币朋友']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(540, 1140) |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 我的订单 | `` | (540, 1140) | False | 我的 |
| 开宝箱 | `` | (627, 2058) | False | 开宝箱 |
| 添加好友 | `` | (192, 174) | True |  |
| 新访客 10按钮 | `` | (612, 174) | True |  |
| 搜索 | `` | (852, 174) | True |  |
| 更多 | `` | (984, 174) | True |  |
| 背景图片 | `com.ss.android.ugc.aweme.lite:id/m0-` | (540, 303) | True |  |
| Mass | `com.ss.android.ugc.aweme.lite:id/h5l` | (496, 397) | True |  |
| 抖音号：MassChargeRatio | `com.ss.android.ugc.aweme.lite:id/rt6` | (632, 472) | True |  |
| 我有病你有药吗? | `` | (540, 854) | True |  |
| 添加性别等标签按钮 | `` | (213, 931) | True |  |
| 关闭 | `` | (999, 1238) | True |  |
| 作品,按钮,,, | `` | (108, 1445) | True |  |
| 日常,按钮,,, | `` | (324, 1445) | True |  |
| 推荐,按钮,,, | `` | (540, 1445) | True |  |
| 收藏,按钮,,, | `` | (756, 1445) | True |  |
| 喜欢,按钮,,, | `` | (972, 1445) | True |  |
| 私密作品，2 | `com.ss.android.ugc.aweme.lite:id/mv3` | (242, 1595) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
