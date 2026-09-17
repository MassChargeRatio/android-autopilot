# 校准报告 · 喜番免费短剧

- 包名: `com.kwai.theater`
- 前台包名: `com.kwai.theater`
- UI 节点数: 121（已剔除状态栏通知）
- **入口命中率: 1/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 1/8（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 喜番免费短剧 (com.kwai.theater)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=117 前台=com.kwai.theater 耗时=20.8s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (939,2152)，点击并等待 8.0s
- 二级页: 节点=180 入口命中=1/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '看剧赚金币', '去签到']  |
| watch | click_first | 未命中 | candidates=['赚钱', '任务', '看剧赚钱', '福利']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(945, 2145) |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['签到', '每日签到', '看剧赚金币', '去签到']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | click_first | 未命中 | candidates=['立即签到', '领取']  |
| watch | 1 | 0 | click_first | 未命中 | candidates=['赚钱', '任务', '看剧赚钱', '福利']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['看剧', '去完成', '看短剧']  |
| watch | 1 | 3 | swipe | 无需锚点 | swipe |
| watch | 1 | 4 | wait | 无需锚点 | wait |
| withdraw | 1 | 0 | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(945, 2145) |
| withdraw | 1 | 1 | think | 无需锚点 | think |
| withdraw | 1 | 2 | click_text | 未命中 | text='提现' 候选数=0 |
| withdraw | 1 | 3 | reward | 未命中 | pattern='(?P<amount>[0-9]+(?:\\.[0-9]+)?)\\s*(?P<unit>元)' 当前页文本无匹配 |
| withdraw | 1 | 4 | click_text | 未命中 | text='立即提现' 候选数=0 |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 赚现金 | `com.kwai.theater:id/home_tab_tip` | (496, 2111) | (87, 37) | False | 现金 |
| 我的 | `com.kwai.theater:id/unselect_tab_text` | (945, 2145) | (92, 46) | False | 我的 |
| 热剧 | `` | (119, 191) | (168, 127) | True |  |
| 找剧 | `` | (287, 191) | (168, 127) | True |  |
| 推荐 | `` | (455, 191) | (168, 127) | True |  |
| 追剧 | `com.kwai.theater:id/slide_detail_favorite_button` | (993, 1571) | (70, 44) | True |  |
| 14.9万 | `com.kwai.theater:id/ksad_photo_like_count_text` | (993, 1772) | (105, 46) | True |  |
| 第1集｜无论起点是晴空万里，还是偶有阴云遮蔽，我都始终向阳而生、砥… | `com.kwai.theater:id/ksad_bottom_content_describe` | (431, 1801) | (792, 111) | True |  |
| 展开 | `com.kwai.theater:id/theater_expanded_text` | (784, 1828) | (86, 58) | True |  |
| 分享 | `com.kwai.theater:id/share_text` | (993, 1970) | (70, 47) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (939, 2152)
- 节点数: 180
- **二级页入口命中: 1/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['签到', '每日签到', '看剧赚金币', '去签到']  |
| watch | click_first | 未命中 | candidates=['赚钱', '任务', '看剧赚钱', '福利']  |
| withdraw | click_first | 命中 | candidates=['我的', '我'] -> '我的' @(970, 2145) |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 现金3.47元 | `com.kwai.theater:id/sub_title` | (154, 538) | False | 元,现金 |
| 提现 | `com.kwai.theater:id/title` | (179, 487) | False | 提现 |
| 去看剧 | `com.kwai.theater:id/login_pendant_bottom_text` | (968, 700) | False | 看剧 |
| 赚现金 | `com.kwai.theater:id/home_tab_tip` | (496, 2111) | False | 现金 |
| 我的 | `com.kwai.theater:id/select_tab_text` | (970, 2145) | False | 我的 |
| 历史 | `` | (98, 704) | True |  |
| 在追 | `` | (254, 704) | True |  |
| 点赞 | `` | (410, 704) | True |  |
| 已购 | `` | (566, 704) | True |  |
| 下载 | `` | (722, 704) | True |  |
| 全部 | `` | (101, 825) | True |  |
| 短剧 | `` | (256, 825) | True |  |
| 漫剧 | `` | (411, 825) | True |  |
| 小说 | `` | (566, 825) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
