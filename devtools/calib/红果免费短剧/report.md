# 校准报告 · 红果免费短剧

- 包名: `com.phoenix.read`
- 前台包名: `com.phoenix.read`
- UI 节点数: 220（已剔除状态栏通知）
- **入口命中率: 3/4**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 5/10（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 红果免费短剧 (com.phoenix.read)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=202 前台=com.phoenix.read 耗时=28.1s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (950,2129)，点击并等待 7.0s
- 二级页: 节点=264 入口命中=3/4

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '去签到', '每日签到'] -> '签到' @(813, 2109) |
| watch | click_first | 命中 | candidates=['赚钱', '看剧赚钱', '看视频得金币'] -> '赚钱' @(747, 2139) |
| withdraw | click_first | 命中 | candidates=['赚钱', '我的', '我'] -> '赚钱' @(747, 2139) |
| collect | click_first | 未命中 | candidates=['福利', '任务中心', '开宝箱']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 命中 | candidates=['签到', '去签到', '每日签到'] -> '签到' @(813, 2109) |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 命中 | candidates=['立即签到', '领取'] -> '领取' @(966, 717) |
| watch | 1 | 0 | click_first | 命中 | candidates=['赚钱', '看剧赚钱', '看视频得金币'] -> '赚钱' @(747, 2139) |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['看剧', '去完成', '看短剧']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['赚钱', '我的', '我'] -> '赚钱' @(747, 2139) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |
| collect | 1 | 0 | click_first | 未命中 | candidates=['福利', '任务中心', '开宝箱']  |
| collect | 1 | 1 | think | 无需锚点 | think |
| collect | 1 | 2 | click_first | 命中 | candidates=['领取', '开'] -> '领取' @(966, 717) |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 立即领取 | `` | (966, 717) | (155, 55) | True | 领,领取 |
| 送你一场金币雨 | `com.phoenix.read:id/d` | (737, 631) | (282, 52) | False | 金币 |
| 签到 | `com.phoenix.read:id/g37` | (813, 2109) | (73, 48) | False | 签到 |
| 赚钱 | `com.phoenix.read:id/g5_` | (747, 2139) | (96, 65) | False | 赚钱 |
| 我的 | `com.phoenix.read:id/g5_` | (953, 2139) | (96, 65) | False | 我的 |
| @春风 | `com.phoenix.read:id/d4` | (117, 1665) | (138, 65) | True |  |
| 第1季 | `` | (111, 1749) | (126, 54) | True |  |
| 异界 | `` | (246, 1749) | (108, 54) | True |  |
| 43万收藏 | `` | (412, 1749) | (188, 54) | True |  |
| 78万点赞 | `` | (617, 1749) | (186, 54) | True |  |
| 《穿成野神我靠香火斩诸神》 | `com.phoenix.read:id/gsh` | (413, 1837) | (730, 57) | True |  |
| 展开 | `com.phoenix.read:id/tv_expand` | (736, 1837) | (84, 57) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (950, 2129)
- 节点数: 264
- **二级页入口命中: 3/4**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '去签到', '每日签到'] -> '签到' @(813, 2109) |
| watch | click_first | 命中 | candidates=['赚钱', '看剧赚钱', '看视频得金币'] -> '赚钱' @(747, 2139) |
| withdraw | click_first | 命中 | candidates=['赚钱', '我的', '我'] -> '赚钱' @(747, 2139) |
| collect | click_first | 未命中 | candidates=['福利', '任务中心', '开宝箱']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 去领取 | `com.phoenix.read:id/lg` | (138, 752) | False | 领,领取 |
| 领1610金币 | `` | (955, 1400) | True | 领,金币 |
| 提现 | `com.phoenix.read:id/iy` | (846, 693) | False | 提现 |
| 1.50元 | `com.phoenix.read:id/lg` | (857, 752) | False | 元 |
| 签到 | `com.phoenix.read:id/g37` | (813, 2109) | False | 签到 |
| 赚钱 | `com.phoenix.read:id/g5_` | (747, 2139) | False | 赚钱 |
| 我的 | `com.phoenix.read:id/g5_` | (953, 2139) | False | 我的 |
| 用户名50437540 | `com.phoenix.read:id/lm` | (480, 295) | True |  |
| 编辑资料 | `com.phoenix.read:id/k6d` | (924, 536) | True |  |
| 历史 | `` | (132, 935) | True |  |
| 收藏 | `` | (300, 935) | True |  |
| 点赞 | `` | (468, 935) | True |  |
| 预约 | `` | (636, 935) | True |  |
| 动态 | `` | (804, 935) | True |  |
| 全部 | `` | (108, 1067) | True |  |
| 已看完 | `` | (330, 1067) | True |  |
| 未看完 | `` | (582, 1067) | True |  |
| 编辑 | `com.phoenix.read:id/j7y` | (996, 1067) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
