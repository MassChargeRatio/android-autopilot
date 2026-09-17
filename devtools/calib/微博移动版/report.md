# 校准报告 · 微博移动版

- 包名: `com.sina.weibog3`
- 前台包名: `com.sina.weibog3`
- UI 节点数: 160（已剔除状态栏通知）
- **入口命中率: 0/2**（每个行为首个锚点动作是否在落地页命中）
- 全部锚点类动作命中: 2/4（后续步骤需跳转后页面，静态 dump 校验不了）

## 过程日志

- 已启动 微博移动版 (com.sina.weibog3)
- 自适应等待就绪（上限 60.0s，最小节点数 40；不按 BACK）
- 就绪判定: 节点=152 前台=com.sina.weibog3 耗时=11.5s（节点数达标）
- probe: VLM 命中『定位屏幕底部导航栏最右侧的『我的』标签中心』-> (972,2129)，点击并等待 7.0s
- 二级页: 节点=179 入口命中=1/2

## 入口校验（关键）

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 未命中 | candidates=['任务中心', '福利', '赚积分', '做任务']  |
| bonus | click_first | 未命中 | candidates=['红包', '现金奖励', '翻牌']  |

## 全部动作校验

| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |
|---|---|---|---|---|---|
| collect | 1 | 0 | click_first | 未命中 | candidates=['任务中心', '福利', '赚积分', '做任务']  |
| collect | 1 | 1 | think | 无需锚点 | think |
| collect | 1 | 2 | click_first | 命中 | candidates=['领取', '领', '签到'] -> '领取' @(924, 2010) |
| bonus | 1 | 0 | click_first | 未命中 | candidates=['红包', '现金奖励', '翻牌']  |
| bonus | 1 | 1 | think | 无需锚点 | think |
| bonus | 1 | 2 | click_first | 命中 | candidates=['领取', '立即领取'] -> '领取' @(924, 2010) |

## 页面候选锚点（前 40）

| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |
|---|---|---|---|---|---|
| 点击领取 | `com.sina.weibog3:id/complete_bottom_tv` | (924, 2010) | (252, 78) | False | 领,领取 |
| 0.01元 | `com.sina.weibog3:id/complete_amount_tv` | (924, 1942) | (92, 41) | False | 元 |
| 转发20 | `com.sina.weibog3:id/leftButton` | (180, 1665) | (360, 108) | True |  |
| 评论73 | `com.sina.weibog3:id/midButton` | (540, 1665) | (360, 108) | True |  |
| 首页 | `` | (108, 2139) | (216, 132) | True |  |
| 视频 | `` | (324, 2139) | (216, 132) | True |  |
| 发现 | `` | (540, 2139) | (216, 132) | True |  |
| 消息 | `` | (756, 2139) | (216, 132) | True |  |
| 我 | `` | (972, 2139) | (216, 132) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | (240, 126) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | (240, 126) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | (240, 126) | True |  |

## 二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』后）

- VLM 命中坐标: (972, 2129)
- 节点数: 179
- **二级页入口命中: 1/2**

| 行为 | 类型 | 结果 | 详情 |
|---|---|---|---|
| collect | click_first | 命中 | candidates=['任务中心', '福利', '赚积分', '做任务'] -> '任务中心' @(213, 1408) |
| bonus | click_first | 未命中 | candidates=['红包', '现金奖励', '翻牌']  |

| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |
|---|---|---|---|---|
| *&**&*领取1个月VIP | `` | (236, 523) | False | 领,领取 |
| 每日签到 | `` | (150, 1606) | False | 签到,每日签到 |
| 领会员 | `com.sina.weibog3:id/mRightBtnText` | (897, 547) | False | 领 |
| 我的相册 | `com.sina.weibog3:id/icon_info_content` | (158, 1001) | False | 我的 |
| 我的钱包 | `com.sina.weibog3:id/icon_info_content` | (158, 1226) | False | 我的 |
| 任务中心 | `` | (213, 1408) | False | 任务 |
| 今日待领630积分 | `` | (206, 1466) | False | 领 |
| 参与瓜分10万现金 | `` | (723, 1466) | False | 现金 |
| 签到 | `com.sina.weibog3:id/tv_content` | (432, 1636) | False | 签到 |
| 点击领10积分 | `` | (201, 1664) | False | 领 |
| 我的钱包 | `com.sina.weibog3:id/title_title_left` | (150, 1825) | False | 我的 |
| 1000.00元 | `com.sina.weibog3:id/top_rich_desc_cell_title` | (157, 1955) | False | 元 |
| 一元起租 | `` | (412, 2029) | False | 元 |
| Masstochargeratio | `com.sina.weibog3:id/mine_nickname` | (530, 266) | True |  |
| 简介：暂无简介 | `com.sina.weibog3:id/mine_header_desc` | (414, 337) | True |  |
| 首页 | `` | (108, 2139) | True |  |
| 视频 | `` | (324, 2139) | True |  |
| 发现 | `` | (540, 2139) | True |  |
| 消息 | `` | (756, 2139) | True |  |
| 我 | `` | (972, 2139) | True |  |
| 概览 | `com.android.systemui:id/recent_apps` | (270, 2277) | True |  |
| 返回 | `com.android.systemui:id/back` | (825, 2277) | True |  |
| 主屏幕 | `com.android.systemui:id/home` | (540, 2277) | True |  |
