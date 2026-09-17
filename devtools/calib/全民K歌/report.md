# 校准报告 · 全民K歌

- 包名: `com.tencent.karaoke`
- 前台包名: `com.tencent.karaoke`
- UI 节点数: 218（已剔除状态栏通知）
- **入口命中率: 0/2**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 0/4（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 全民K歌 (com.tencent.karaoke)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=209 前台=com.tencent.karaoke 耗时=33.4s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (925,2141)，点击并等待 7.0s
- 二级页: 节点=206 入口命中=1/2

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 未命中 | candidates=['任务中心', '福利', '每日任务', '做任务']  |
| bonus | click_first | 未命中 | candidates=['红包', '领红包', '抽奖']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| collect | 1 | 0 | click_first | 未命中 | candidates=['任务中心', '福利', '每日任务', '做任务']  |
| collect | 1 | 1 | think | 无需锚点 | think |
| collect | 1 | 2 | click_first | 未命中 | candidates=['领取', '去完成']  |
| bonus | 1 | 0 | click_first | 未命中 | candidates=['红包', '领红包', '抽奖']  |
| bonus | 1 | 1 | think | 无需锚点 | think |
| bonus | 1 | 2 | click_first | 未命中 | candidates=['立即领取', '领取']  |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 金币提现实验组用户触达的按钮 | `` | (540, 1002) | (834, 1001) | False | 提现,金币 |
| 任务中心 | `com.tencent.karaoke:id/okm` | (108, 171) | (84, 84) | False | 任务 |
| 未选中我的 | `com.tencent.karaoke:id/j3n` | (924, 2118) | (162, 144) | True | 我的 |
| 我的 | `com.tencent.karaoke:id/j3m` | (924, 2168) | (162, 44) | False | 我的 |
| AI唱 | `` | (227, 171) | (142, 150) | True |  |
| 推荐 | `` | (370, 171) | (144, 150) | True |  |
| 关注 | `` | (514, 171) | (144, 150) | True |  |
| 直播 | `` | (658, 171) | (144, 150) | True |  |
| 同城 | `` | (802, 171) | (144, 150) | True |  |
| 短剧 | `` | (914, 171) | (80, 150) | True |  |
| 搜索 | `com.tencent.karaoke:id/dij` | (990, 171) | (72, 72) | True |  |
| 筛选 | `com.tencent.karaoke:id/bei` | (360, 596) | (168, 81) | True |  |
| 知否知否 | `com.tencent.karaoke:id/pzj` | (331, 704) | (266, 69) | True |  |
| 头像 | `com.tencent.karaoke:id/l1u` | (108, 730) | (120, 120) | True |  |
| 查看详情 按钮 | `` | (540, 1084) | (1080, 888) | True |  |
| 送礼 | `com.tencent.karaoke:id/e9n` | (357, 1420) | (78, 46) | True |  |
| 点赞0 | `com.tencent.karaoke:id/dc6` | (750, 1420) | (132, 72) | True |  |
| 评论0 | `com.tencent.karaoke:id/dbz` | (882, 1420) | (132, 72) | True |  |
| 分享 | `com.tencent.karaoke:id/dhp` | (1014, 1420) | (132, 72) | True |  |
| 沙墟 | `com.tencent.karaoke:id/pzj` | (283, 1592) | (170, 69) | True |  |
| 关闭 按钮 | `` | (540, 1607) | (104, 209) | True |  |
| 头像 | `com.tencent.karaoke:id/l1u` | (108, 1618) | (120, 120) | True |  |
| 查看详情 按钮 | `` | (540, 1787) | (1080, 518) | True |  |
| 发动态 | `com.tencent.karaoke:id/di9` | (904, 1965) | (279, 108) | True |  |
| 已选中动态 | `com.tencent.karaoke:id/j3n` | (156, 2118) | (162, 144) | True |  |
| 未选中歌房 | `com.tencent.karaoke:id/j3n` | (348, 2118) | (162, 144) | True |  |
| 未选中消息未读1 | `com.tencent.karaoke:id/j3n` | (732, 2118) | (162, 144) | True |  |
| 未选中录歌 | `com.tencent.karaoke:id/j3n` | (540, 2130) | (192, 168) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (925, 2141)
- 节点数: 206
- **二级页入口命中: 1/2**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 命中 | candidates=['任务中心', '福利', '每日任务', '做任务'] -> '任务中心' @(139, 1174) |
| bonus | click_first | 未命中 | candidates=['红包', '领红包', '抽奖']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 看视频免费领取100金币 | `com.tencent.karaoke:id/pw7` | (357, 1323) | False | 领,领取,金币,看视频 |
| 0.1元开通 | `com.tencent.karaoke:id/azb` | (869, 911) | True | 元 |
| 任务中心 | `com.tencent.karaoke:id/k8v` | (139, 1174) | False | 任务 |
| 金币可在用户中心兑换好礼 | `com.tencent.karaoke:id/pw6` | (291, 1380) | False | 金币 |
| 已选中我的 | `com.tencent.karaoke:id/j3n` | (924, 2118) | True | 我的 |
| 我的 | `com.tencent.karaoke:id/j3m` | (924, 2168) | False | 我的 |
| 设置 | `com.tencent.karaoke:id/fv8` | (78, 171) | True |  |
| 更多 | `` | (990, 171) | True |  |
| 封面图 | `com.tencent.karaoke:id/qal` | (540, 306) | True |  |
| 切换账号 | `com.tencent.karaoke:id/qlz` | (556, 368) | True |  |
| 头像 | `com.tencent.karaoke:id/qaj` | (149, 404) | True |  |
| 财富等级 | `` | (180, 583) | True |  |
| 用户等级 | `` | (255, 583) | True |  |
| 勋章墙 2 | `com.tencent.karaoke:id/qg6` | (200, 649) | True |  |
| 礼物墙 0 | `com.tencent.karaoke:id/qg3` | (498, 649) | True |  |
| 点击设置自己的个性签名 | `com.tencent.karaoke:id/qly` | (540, 751) | True |  |
| 资料 | `` | (111, 1539) | True |  |
| 动态 | `` | (273, 1539) | True |  |
| 作品 | `` | (435, 1539) | True |  |
| 待合唱 | `` | (622, 1539) | True |  |
| 查看 | `com.tencent.karaoke:id/q_r` | (855, 1680) | True |  |
| 未选中动态 | `com.tencent.karaoke:id/j3n` | (156, 2118) | True |  |
| 未选中歌房 | `com.tencent.karaoke:id/j3n` | (348, 2118) | True |  |
| 未选中消息未读1 | `com.tencent.karaoke:id/j3n` | (732, 2118) | True |  |
| 未选中录歌 | `com.tencent.karaoke:id/j3n` | (540, 2130) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
