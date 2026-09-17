# 校准报告 · 梧桐免费小说

- 包名: `com.ushaqi.zhuishushenqi.ninenine`
- 前台包名: `com.ushaqi.zhuishushenqi.ninenine`
- UI 节点数: 156（已剔除状态栏通知）
- **入口命中率: 2/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 3/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 梧桐免费小说 (com.ushaqi.zhuishushenqi.ninenine)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=156 前台=com.ushaqi.zhuishushenqi.ninenine 耗时=26.8s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (972,2124)，点击并等待 7.0s
- 二级页: 节点=92 入口命中=2/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '每日签到', '看书得金币', '立即签到'] -> '签到' @(604, 2088) |
| watch | click_first | 未命中 | candidates=['福利中心', '任务', '看书赚钱', '我的金币']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(972, 2132) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 命中 | candidates=['签到', '每日签到', '看书得金币', '立即签到'] -> '签到' @(604, 2088) |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 命中 | candidates=['签到领', '领取'] -> '签到领' @(604, 2088) |
| watch | 1 | 0 | click_first | 未命中 | candidates=['福利中心', '任务', '看书赚钱', '我的金币']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['继续看书', '阅读赚钱', '去完成']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(972, 2132) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='可提现(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 签到领现金 | `com.ushaqi.zhuishushenqi.ninenine:id/tips` | (604, 2088) | (163, 49) | False | 签到,领,现金 |
| 去赚钱 | `com.ushaqi.zhuishushenqi.ninenine:id/prompt` | (948, 625) | (108, 42) | False | 赚钱 |
| 换现金 | `com.ushaqi.zhuishushenqi.ninenine:id/action` | (948, 774) | (174, 72) | False | 现金 |
| 我的 | `com.ushaqi.zhuishushenqi.ninenine:id/mineTabText` | (972, 2132) | (108, 63) | False | 我的 |
| 推荐 | `` | (93, 159) | (164, 110) | True |  |
| 男生 | `` | (279, 159) | (186, 126) | True |  |
| 女生 | `` | (465, 159) | (164, 110) | True |  |
| 听书 | `` | (651, 159) | (164, 110) | True |  |
| 经典 | `` | (837, 159) | (164, 110) | True |  |
| 推荐榜 | `` | (165, 480) | (210, 96) | True |  |
| 热读榜 | `` | (399, 480) | (210, 96) | True |  |
| 飙升榜 | `` | (633, 480) | (210, 96) | True |  |
| 完结榜 | `` | (792, 480) | (60, 96) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (972, 2124)
- 节点数: 92
- **二级页入口命中: 2/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 命中 | candidates=['签到', '每日签到', '看书得金币', '立即签到'] -> '签到' @(604, 2088) |
| watch | click_first | 未命中 | candidates=['福利中心', '任务', '看书赚钱', '我的金币']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(196, 567) |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 签到领现金 | `com.ushaqi.zhuishushenqi.ninenine:id/tips` | (604, 2088) | False | 签到,领,现金 |
| 去提现 | `` | (880, 558) | False | 提现,去提现 |
| 我的现金： | `com.ushaqi.zhuishushenqi.ninenine:id/new_task_he` | (196, 567) | False | 现金,我的 |
| 元 | `` | (459, 571) | False | 元 |
| 福利商城 | `` | (888, 834) | False | 福利 |
| 我的 | `com.ushaqi.zhuishushenqi.ninenine:id/mineTabText` | (972, 2132) | False | 我的 |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
