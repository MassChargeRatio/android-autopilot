# 锚点修补计划（数据驱动）

> 依据 `devtools/calib/<app>/ui.xml`（首屏）与 `ui_after.xml`（二级页）。
> `prelude` = 在行为最前面插一步导航到「我的」；`candidate` = 追加候选；
> `rid` = 纯图标按钮，用 resource-id 锚定；`manual` = 需人工给坐标/VLM。

## 一淘  (`com.taobao.etao`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | keep | 首屏已命中 desc=签到 |
| watch | prelude | 首屏无、二级页命中 text=去福狸中心做任务 |
| withdraw | prelude | 首屏无、二级页命中 text=我的 |

## 今日头条极速版  (`com.ss.android.article.lite`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | keep | 首屏已命中 desc=开宝箱 |
| watch | prelude | 首屏无、二级页命中 text=金币 |
| withdraw | keep | 首屏已命中 text=我的 |
| bonus | prelude | 首屏无、二级页命中 text=完成挑战得奖励 |

## 今日看点极速版  (`com.jinrikd.news`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | prelude | 首屏无、二级页命中 text=直接领取 |
| watch | prelude | 首屏无、二级页命中 text=金币 |
| withdraw | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |

## 全民K歌  (`com.tencent.karaoke`)

| 行为 | 处置 | 依据 |
|---|---|---|
| collect | keep | 首屏已命中 desc=任务中心 |
| bonus | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |

## 喜番免费短剧  (`com.kwai.theater`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| watch | prelude | 首屏无、二级页命中 text=去看剧 |
| withdraw | keep | 首屏已命中 text=我的 |

## 天天快讯极速版  (`skysky.cy.kuaixun`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| watch | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| withdraw | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |

## 微博移动版  (`com.sina.weibog3`)

| 行为 | 处置 | 依据 |
|---|---|---|
| collect | prelude | 首屏无、二级页命中 text=任务中心 |
| bonus | keep | 首屏已命中 text=点击领取 |

## 悟空浏览器  (`com.cat.readall`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| watch | keep | 首屏已命中 text=看剧 |
| withdraw | keep | 首屏已命中 text=我的 |

## 抖音  (`com.ss.android.ugc.aweme`)

| 行为 | 处置 | 依据 |
|---|---|---|
| watch | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| bonus | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |

## 抖音极速版  (`com.ss.android.ugc.aweme.lite`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | keep | 首屏已命中 text=开宝箱 |
| watch | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| withdraw | keep | 首屏已命中 text=我 |

## 抖音火山版  (`com.ss.android.ugc.live`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| watch | prelude | 首屏无、二级页命中 text=点击赚钱 |
| withdraw | keep | 首屏已命中 text=我 |

## 星图金融  (`com.suning.mobile.epa`)

| 行为 | 处置 | 依据 |
|---|---|---|
| collect | keep | 首屏已命中 text=迎新福利 |
| bonus | keep | 首屏已命中 text=领红包 |

## 梧桐免费小说  (`com.ushaqi.zhuishushenqi.ninenine`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | keep | 首屏已命中 text=签到 |
| watch | prelude | 首屏无、二级页命中 text=福利商城 |
| withdraw | keep | 首屏已命中 text=我的 |

## 河马剧场  (`com.dz.hmjc`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| watch | prelude | 首屏无、二级页命中 text=福利 |
| withdraw | keep | 首屏已命中 text=我的 |

## 火龙漫剧  (`com.tencent.kairos`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | keep | 首屏已命中 text=签到 |
| watch | keep | 首屏已命中 text=福利 |
| withdraw | keep | 首屏已命中 text=我的 |

## 点淘  (`com.taobao.live`)

| 行为 | 处置 | 依据 |
|---|---|---|
| collect | keep | 首屏已命中 text=待领取 |
| watch | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| withdraw | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |

## 红果免费短剧  (`com.phoenix.read`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | keep | 首屏已命中 text=签到 |
| watch | keep | 首屏已命中 text=赚钱 |
| withdraw | keep | 首屏已命中 text=赚钱 |
| collect | prelude | 首屏无、二级页命中 text=去领取 |

## 蛋花免费小说  (`com.eggflower.read`)

| 行为 | 处置 | 依据 |
|---|---|---|
| sign | manual | 两页均无可用文本/rid 锚点，需 click_point 坐标 / VLM 专项 |
| watch | keep | 首屏已命中 text=福利 |
| withdraw | keep | 首屏已命中 text=我的 |

## 统计

- 保持不动: 25
- 加导航前置步(prelude): 12
- 追加候选(candidate): 0
- rid 锚点(rid): 0
- 需人工(manual): 15

