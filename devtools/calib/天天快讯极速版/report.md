# 校准报告 · 天天快讯极速版

- 包名: `skysky.cy.kuaixun`
- 前台包名: `com.bbk.launcher2`
- UI 节点数: 71（已剔除状态栏通知）
- **入口命中率: 0/3**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 0/9（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 天天快讯极速版 (skysky.cy.kuaixun)
- 自适应等待就绪（上限 90.0s，最小节点数 40；不按 BACK）
- 达到最大等待 90.0s 仍未就绪，节点=71，按当前页继续
- ⚠ 当前前台包名 com.bbk.launcher2 != 目标 skysky.cy.kuaixun（可能被弹窗/广告占据）
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏最右侧的『我的』标签中心
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏最右侧的『我』标签中心
- probe: 提示词未命中，尝试下一个 -> 定位屏幕底部导航栏的个人中心（我的）标签中心
- probe: VLM 命中『定位屏幕右下角的个人中心头像/图标中心』-> (896,1684)，点击并等待 8.0s
- 二级页: 节点=72 入口命中=0/3

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['立即签到', '签到', '连续签到', '每日签到']  |
| watch | click_first | 未命中 | candidates=['看视频', '看资讯赚钱', '任务中心']  |
| withdraw | click_first | 未命中 | candidates=['我的', '我']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| sign | 1 | 0 | click_first | 未命中 | candidates=['立即签到', '签到', '连续签到', '每日签到']  |
| sign | 1 | 1 | think | 无需锚点 | think |
| sign | 1 | 2 | reward | 未命中 | pattern='领(?P<amount>[0-9]+)\\s*(?P<unit>金币)' 当前页文本无匹配 |
| sign | 1 | 3 | click_first | 未命中 | candidates=['立即签到领2888金币', '领取']  |
| watch | 1 | 0 | click_first | 未命中 | candidates=['看视频', '看资讯赚钱', '任务中心']  |
| watch | 1 | 1 | think | 无需锚点 | think |
| watch | 1 | 2 | click_first | 未命中 | candidates=['去完成', '领取']  |
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
| 17:23 | `com.vivo.doubletimezoneclock:id/single_time_layo` | (254, 358) | (330, 199) | True |  |
| 时钟天气·经典 | `` | (539, 372) | (984, 270) | True |  |
| 薛城区 | `com.vivo.doubletimezoneclock:id/city` | (926, 393) | (126, 57) | True |  |
| 9月14日 星期一 | `com.vivo.doubletimezoneclock:id/date_week_apm` | (242, 468) | (306, 63) | True |  |
| 微信 | `` | (170, 642) | (246, 270) | True |  |
| 小红书 | `` | (416, 642) | (246, 270) | True |  |
| 知乎 | `` | (662, 642) | (246, 270) | True |  |
| 购物 | `` | (908, 642) | (246, 270) | True |  |
| 支付宝 | `` | (170, 912) | (246, 270) | True |  |
| 转账 | `` | (416, 912) | (246, 270) | True |  |
| 雪球 | `` | (662, 912) | (246, 270) | True |  |
| 理财 | `` | (908, 912) | (246, 270) | True |  |
| 主屏幕 1 | `` | (540, 1170) | (1080, 2340) | True |  |
| v2rayNG | `` | (170, 1182) | (246, 270) | True |  |
| Play 商店 | `` | (416, 1182) | (246, 270) | True |  |
| 身份验证器 | `` | (662, 1182) | (246, 270) | True |  |
| Edge | `` | (908, 1182) | (246, 270) | True |  |
| 通讯 | `` | (170, 1452) | (246, 270) | True |  |
| 其他 | `` | (416, 1452) | (246, 270) | True |  |
| vivo 工具 | `` | (662, 1452) | (246, 270) | True |  |
| vivo app | `` | (908, 1452) | (246, 270) | True |  |
| 设置 | `` | (170, 1722) | (246, 270) | True |  |
| 应用商店 | `` | (416, 1722) | (246, 270) | True |  |
| 文件管理 | `` | (662, 1722) | (246, 270) | True |  |
| 相册 | `` | (908, 1722) | (246, 270) | True |  |
| 电话 | `` | (129, 2137) | (196, 246) | True |  |
| 信息，760条通知 | `` | (334, 2137) | (196, 246) | True |  |
| 相机 | `` | (539, 2137) | (196, 246) | True |  |
| 电子邮件，189条通知 | `` | (744, 2137) | (196, 246) | True |  |
| 浏览器 | `` | (949, 2137) | (196, 246) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (896, 1684)
- 节点数: 72
- **二级页入口命中: 0/3**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| sign | click_first | 未命中 | candidates=['立即签到', '签到', '连续签到', '每日签到']  |
| watch | click_first | 未命中 | candidates=['看视频', '看资讯赚钱', '任务中心']  |
| withdraw | click_first | 未命中 | candidates=['我的', '我']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| 更多 | `` | (972, 222) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
