# 锚点修补建议（基于真机校准 dump）

> 由 `devtools/propose_anchors.py` 生成，**只读不改配置**。
> 「跨语义命中」= 候选文案虽然在 text 里找不到，但在 content-desc 里找到了。
> 这类锚点只需给候选加一条 `type: desc` 即可修复，无需重新截图。

## 一淘  (`com.taobao.etao`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 未命中 | desc:签到领钱 @(482, 384) | 加候选 `{type: desc, value: "签到"}` |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `天天领` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看视频领金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `省金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `今日任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 今日头条极速版  (`com.ss.android.article.lite`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `开宝箱` | 未命中 | desc:开宝箱 @(600, 2111) | 加候选 `{type: desc, value: "开宝箱"}` |
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看资讯赚金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看视频` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 命中 | text:我的 @(972, 2182) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:我的 @(972, 2182) | 无需修改 |
| bonus | click_first | `限时预约领金币` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `预约` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `红包` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 今日看点极速版  (`com.jinrikd.news`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `直接领取` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `看视频` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看视频赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 全民K歌  (`com.tencent.karaoke`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| collect | click_first | `任务中心` | 未命中 | desc:任务中心 @(108, 171) | 加候选 `{type: desc, value: "任务中心"}` |
| collect | click_first | `福利` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `每日任务` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `做任务` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `红包` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `领红包` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `抽奖` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 喜番免费短剧  (`com.kwai.theater`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `看剧赚金币` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `去签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看剧赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `福利` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 命中 | text:我的 @(945, 2145) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:我的 @(945, 2145) | 无需修改 |

## 天天快讯极速版  (`skysky.cy.kuaixun`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `连续签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `看视频` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看资讯赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 命中 | text:我的 @(972, 2192) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:我的 @(972, 2192) | 无需修改 |

## 微博移动版  (`com.sina.weibog3`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| collect | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `福利` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `赚积分` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `做任务` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| bonus | click_first | `红包` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `现金奖励` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `翻牌` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 悟空浏览器  (`com.cat.readall`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `阅读赚金币` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看新闻赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `阅读赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 抖音  (`com.ss.android.ugc.aweme`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| watch | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `赚积分` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `去完成` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| bonus | click_first | `红包` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `领红包` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 抖音极速版  (`com.ss.android.ugc.aweme.lite`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `开宝箱` | 命中 | text:开宝箱 @(627, 2058) | 无需修改 |
| sign | click_first | `领金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `刷视频` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看视频赚金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `金币朋友` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我` | 命中 | text:我 @(971, 2141) | 无需修改 |

## 抖音火山版  (`com.ss.android.ugc.live`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `开宝箱` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `领金币` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `看视频赚金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 星图金融  (`com.suning.mobile.epa`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| collect | click_first | `人人领` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `领好礼` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| bonus | click_first | `领红包` | 命中 | text:天天领红包 @(936, 1013) | 无需修改 |
| bonus | click_first | `红包` | 命中 | text:红包签到 @(675, 451) | 无需修改 |
| bonus | click_first | `现金红包` | 未命中 | - | 落地页无此锚点 |
| bonus | click_first | `抽奖` | 未命中 | - | 落地页无此锚点 |

## 梧桐免费小说  (`com.ushaqi.zhuishushenqi.ninenine`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 命中 | text:签到领现金 @(604, 2088) | 无需修改 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `看书得金币` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `福利中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看书赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `我的金币` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 命中 | text:我的 @(972, 2132) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:我的 @(972, 2132) | 无需修改 |

## 河马剧场  (`com.dz.hmjc`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `看剧得金币` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看剧赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `福利中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 命中 | text:我的 @(972, 2132) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:我的 @(972, 2132) | 无需修改 |

## 火龙漫剧  (`com.tencent.kairos`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 命中 | text:签到 @(720, 2093) | 无需修改 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `去签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `天天有礼` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看剧赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `福利中心` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| withdraw | click_first | `我的` | 命中 | text:我的 @(918, 2130) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:我的 @(918, 2130) | 无需修改 |

## 点淘  (`com.taobao.live`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| collect | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `天天领` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `福利` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `领奖` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `看直播` | 命中 | text:看直播，得惊喜。更多玩法来临，新版本已经准备好，快来更新点淘吧 @(540, 1120) | 无需修改 |
| watch | click_first | `看视频` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `逛直播间` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我的` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 红果免费短剧  (`com.phoenix.read`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 命中 | text:签到 @(813, 2109) | 无需修改 |
| sign | click_first | `去签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `赚钱` | 命中 | text:赚钱 @(747, 2139) | 无需修改 |
| watch | click_first | `看剧赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看视频得金币` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `赚钱` | 命中 | text:赚钱 @(747, 2139) | 无需修改 |
| withdraw | click_first | `我的` | 命中 | text:我的 @(953, 2139) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:我的 @(953, 2139) | 无需修改 |
| collect | click_first | `福利` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `任务中心` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `开宝箱` | 未命中 | - | 落地页无此锚点 |
| collect | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |

## 蛋花免费小说  (`com.eggflower.read`)

| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |
|---|---|---|---|---|---|
| sign | click_first | `签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `每日签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `立即签到` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `幸运签` | 未命中 | - | 落地页无此锚点 |
| sign | click_first | `—` | — | — | ⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM) |
| watch | click_first | `福利` | 命中 | text:福利 @(540, 2148) | 无需修改 |
| watch | click_first | `任务` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `看书赚钱` | 未命中 | - | 落地页无此锚点 |
| watch | click_first | `金币中心` | 未命中 | - | 落地页无此锚点 |
| withdraw | click_first | `我的` | 命中 | text:凡人修仙：我的身体状态每日刷新 @(450, 709) | 无需修改 |
| withdraw | click_first | `我` | 命中 | text:凡人修仙：我的身体状态每日刷新 @(450, 709) | 无需修改 |

## 统计

- 入口有可用文本锚点的行为: **20**
- 落地页无文本锚点、需坐标/VLM 的行为: **32**

