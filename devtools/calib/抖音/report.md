# 校准报告 · 抖音

- 包名: `com.ss.android.ugc.aweme`
- 前台包名: `com.ss.android.ugc.aweme`
- UI 节点数: 285（已剔除状态栏通知）
- **入口命中率: 0/2**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 1/3（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 抖音 (com.ss.android.ugc.aweme)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=279 前台=com.ss.android.ugc.aweme 耗时=26.2s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (972,2199)，点击并等待 8.0s
- 二级页: 节点=262 入口命中=0/2

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| watch | click_first | 未命中 | candidates=['任务', '赚积分', '去完成']  |
| bonus | click_first | 未命中 | candidates=['红包', '领红包']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| watch | 1 | 0 | click_first | 未命中 | candidates=['任务', '赚积分', '去完成']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | swipe | 无需锚点 | swipe |
| watch | 1 | 3 | wait | 无需锚点 | wait |
| bonus | 1 | 0 | click_first | 未命中 | candidates=['红包', '领红包']  |
| bonus | 1 | 1 | think | 无需锚点 | think |
| bonus | 1 | 2 | click_first | 命中 | candidates=['领取', '立即领取'] -> '领取' @(799, 441) |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 打卡成功 领取3金币 | `` | (799, 441) | (326, 48) | False | 打卡,领,领取,金币 |
| 今日可再赚5034金币 | `` | (845, 380) | (419, 61) | False | 金币 |
| 直播，按钮 | `` | (192, 162) | (84, 132) | True |  |
| 团购，按钮 | `` | (303, 162) | (138, 132) | True |  |
| 同城，按钮 | `` | (441, 162) | (138, 132) | True |  |
| 关注，按钮 | `` | (579, 162) | (138, 132) | True |  |
| 商城，按钮 | `` | (717, 162) | (138, 132) | True |  |
| 已选中，推荐，按钮 | `` | (855, 162) | (138, 132) | True |  |
| 侧边栏有0条未读消息 | `` | (66, 162) | (132, 132) | True |  |
| 搜索 | `` | (1002, 162) | (156, 132) | True |  |
| 安森学长 | `com.ss.android.ugc.aweme:id/user_avatar` | (987, 974) | (144, 144) | True |  |
| 暂停视频，按钮 | `com.ss.android.ugc.aweme:id/qbv` | (540, 1033) | (1080, 2067) | True |  |
| 关注 | `com.ss.android.ugc.aweme:id/j5s` | (988, 1047) | (183, 87) | True |  |
| 未点赞，喜欢1.3万，按钮 | `com.ss.android.ugc.aweme:id/gr+` | (990, 1191) | (180, 201) | True |  |
| 1.3万 | `com.ss.android.ugc.aweme:id/grt` | (990, 1257) | (84, 69) | True |  |
| 评论145，按钮 | `com.ss.android.ugc.aweme:id/e2t` | (990, 1392) | (180, 201) | True |  |
| 未选中，收藏2067，按钮 | `com.ss.android.ugc.aweme:id/d_w` | (988, 1591) | (183, 196) | True |  |
| 分享575，按钮 | `com.ss.android.ugc.aweme:id/zvv` | (990, 1789) | (180, 201) | True |  |
| 575 | `com.ss.android.ugc.aweme:id/zqk` | (990, 1855) | (64, 69) | True |  |
| @安森学长 | `com.ss.android.ugc.aweme:id/title` | (160, 1862) | (248, 75) | True |  |
| 职场沟通：一些能大幅提升专业度的沟通技巧...#打工人 #职场... 展开> | `com.ss.android.ugc.aweme:id/desc` | (403, 1964) | (735, 128) | True |  |
| 取消静音 按钮 | `com.ss.android.ugc.aweme:id/s8i` | (987, 1976) | (132, 132) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (972, 2199)
- 节点数: 262
- **二级页入口命中: 0/2**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| watch | click_first | 未命中 | candidates=['任务', '赚积分', '去完成']  |
| bonus | click_first | 未命中 | candidates=['红包', '领红包']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 我的订单 | `` | (747, 1140) | False | 我的 |
| 添加好友 | `` | (192, 174) | True |  |
| 新访客 10按钮 | `` | (612, 174) | True |  |
| 搜索 | `` | (852, 174) | True |  |
| 更多 | `` | (984, 174) | True |  |
| 背景图片 | `com.ss.android.ugc.aweme:id/wdh` | (540, 303) | True |  |
| Mass | `com.ss.android.ugc.aweme:id/tma` | (496, 353) | True |  |
| 切换账号 | `com.ss.android.ugc.aweme:id/oux` | (633, 355) | True |  |
| 抖音号：MassChargeRatio | `com.ss.android.ugc.aweme:id/5vh` | (632, 428) | True |  |
| 我有病你有药吗? | `` | (540, 854) | True |  |
| 添加性别等标签按钮 | `` | (213, 931) | True |  |
| 关闭 | `` | (999, 1238) | True |  |
| 作品,按钮,,, | `` | (108, 1445) | True |  |
| 日常,按钮,,, | `` | (324, 1445) | True |  |
| 推荐,按钮,,, | `` | (540, 1445) | True |  |
| 收藏,按钮,,, | `` | (756, 1445) | True |  |
| 喜欢,按钮,,, | `` | (972, 1445) | True |  |
| 私密作品，2 | `com.ss.android.ugc.aweme:id/v9t` | (242, 1595) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
