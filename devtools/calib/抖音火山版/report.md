# 校准报告 · 抖音火山版

- 包名: `com.ss.android.ugc.live`
- 前台包名: `com.ss.android.ugc.live`
- UI 节点数: 311（已剔除状态栏通知）
- **入口命中率: 1/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 1/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 抖音火山版 (com.ss.android.ugc.live)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=311 前台=com.ss.android.ugc.live 耗时=52.9s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (982,2152)，点击并等待 7.0s
- 二级页: 节点=286 入口命中=1/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '开宝箱', '领金币']  |
| watch | click_first | 未命中 | candidates=['看视频赚金币', '任务中心', '金币']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我' @(403, 1964) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['签到', '每日签到', '开宝箱', '领金币']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 未命中 | candidates=['立即签到', '领取']  |
| watch | 1 | 0 | click_first | 未命中 | candidates=['看视频赚金币', '任务中心', '金币']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['去完成', '看视频']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我' @(403, 1964) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 领火苗，按钮 | `com.ss.android.ugc.live:id/1gr` | (972, 324) | (144, 144) | False | 领 |
| 商城，按钮 | `` | (192, 162) | (84, 132) | True |  |
| 直播，按钮 | `` | (303, 162) | (138, 132) | True |  |
| 同城，按钮 | `` | (441, 162) | (138, 132) | True |  |
| 关注，按钮 | `` | (579, 162) | (138, 132) | True |  |
| 视频，按钮 | `` | (717, 162) | (138, 132) | True |  |
| 已选中，推荐，按钮 | `` | (855, 162) | (138, 132) | True |  |
| 侧边栏 | `` | (66, 162) | (132, 132) | True |  |
| 搜索 | `` | (1002, 162) | (156, 132) | True |  |
| 欢小乐 | `com.ss.android.ugc.live:id/user_avatar` | (987, 773) | (144, 144) | True |  |
| 关注 | `com.ss.android.ugc.live:id/e_n` | (988, 846) | (183, 87) | True |  |
| 未点赞，喜欢31.4万，按钮 | `com.ss.android.ugc.live:id/guc` | (988, 990) | (180, 201) | True |  |
| 暂停视频，按钮 | `com.ss.android.ugc.live:id/jdc` | (540, 1033) | (1080, 2067) | True |  |
| 31.4万 | `com.ss.android.ugc.live:id/dkf` | (987, 1056) | (107, 69) | True |  |
| 评论6262，按钮 | `com.ss.android.ugc.live:id/e4l` | (988, 1191) | (180, 201) | True |  |
| 未选中，收藏5.1万，按钮 | `com.ss.android.ugc.live:id/et6` | (988, 1390) | (183, 196) | True |  |
| 分享48.9万，按钮 | `com.ss.android.ugc.live:id/y65` | (988, 1588) | (180, 201) | True |  |
| 48.9万 | `com.ss.android.ugc.live:id/n02` | (988, 1654) | (112, 69) | True |  |
| 送火苗3.4万，按钮 | `com.ss.android.ugc.live:id/j5u` | (988, 1789) | (180, 201) | True |  |
| @欢小乐 | `com.ss.android.ugc.live:id/title` | (134, 1862) | (197, 75) | True |  |
| 我猜你肯定不知道这是什么歌 #日常分享 #感谢抖音 #穿搭 #... 展开> | `com.ss.android.ugc.live:id/desc` | (403, 1964) | (735, 128) | True |  |
| 取消静音 按钮 | `com.ss.android.ugc.live:id/st+` | (987, 1976) | (132, 132) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (982, 2152)
- 节点数: 286
- **二级页入口命中: 1/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '开宝箱', '领金币']  |
| watch | click_first | 未命中 | candidates=['看视频赚金币', '任务中心', '金币']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我' @(540, 854) |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 领火苗，按钮 | `com.ss.android.ugc.live:id/1gr` | (972, 324) | False | 领 |
| 点击赚钱 | `com.ss.android.ugc.live:id/kvt` | (978, 371) | False | 赚钱 |
| 添加好友 | `` | (192, 174) | True |  |
| 新访客 10按钮 | `` | (612, 174) | True |  |
| 搜索 | `` | (852, 174) | True |  |
| 更多 | `` | (984, 174) | True |  |
| 背景图片 | `com.ss.android.ugc.live:id/vx2` | (540, 303) | True |  |
| Mass | `com.ss.android.ugc.live:id/kj8` | (496, 397) | True |  |
| 切换账号 | `com.ss.android.ugc.live:id/owz` | (633, 399) | True |  |
| 火山号：MassChargeRatio | `com.ss.android.ugc.live:id/4t0` | (632, 472) | True |  |
| 我有病你有药吗? | `` | (540, 854) | True |  |
| 添加性别等标签按钮 | `` | (213, 931) | True |  |
| 关闭 | `` | (999, 1238) | True |  |
| 作品,按钮,,, | `` | (108, 1445) | True |  |
| 日常,按钮,,, | `` | (324, 1445) | True |  |
| 推荐,按钮,,, | `` | (540, 1445) | True |  |
| 收藏,按钮,,, | `` | (756, 1445) | True |  |
| 喜欢,按钮,,, | `` | (972, 1445) | True |  |
| 私密作品，2 | `com.ss.android.ugc.live:id/vqh` | (242, 1595) | True |  |
| 关闭 | `com.ss.android.ugc.live:id/iv_close` | (1008, 1959) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
