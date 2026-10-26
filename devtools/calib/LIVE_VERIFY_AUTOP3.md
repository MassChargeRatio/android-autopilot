---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 58c070810b91e31b76e5016e97ae2974_441565c1cba411f18078525400de85a5
    ReservedCode1: Ci4dybyxIB/Olh3q+jtce+Cx71qCHtZNbeeZKJLtD0dDunWxvMdnk6ES/OVQ5dOKIgDBSH0HRaNMev46jvBzihTOor+JKhTErFft8iz9lL4XoxIoCfcl88zKgZWXlqwiThbUO36dfWFGSAwfIbkx0sP1bPz+bfSg7X9ntTpBosKqesF/q/Mr0uWkCMQ=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 58c070810b91e31b76e5016e97ae2974_441565c1cba411f18078525400de85a5
    ReservedCode2: Ci4dybyxIB/Olh3q+jtce+Cx71qCHtZNbeeZKJLtD0dDunWxvMdnk6ES/OVQ5dOKIgDBSH0HRaNMev46jvBzihTOor+JKhTErFft8iz9lL4XoxIoCfcl88zKgZWXlqwiThbUO36dfWFGSAwfIbkx0sP1bPz+bfSg7X9ntTpBosKqesF/q/Mr0uWkCMQ=
---

# 实机锚点回归报告

> 生成时间: 2026-10-19 16:04:53
> 设备: 192.168.1.54:5555

## 汇总

- 首屏命中: **28**
- 导航后仍未命中: **10**
- 首屏未命中: **7**
- 导航后命中: **5**
- 数据作废(页面非目标App): **1**

## 星图金融

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| collect | 首屏命中 | text='迎新福利' @(136, 1457) | - |
| bonus | 首屏命中 | text='领红包' @(936, 1013) | - |

<details><summary>执行日志</summary>

```
启动 com.suning.mobile.epa（第 1 次）
就绪判定: 节点=119 前台=com.suning.mobile.epa 耗时=2.3s（节点数达标）
就绪: 节点=119 等待=2.3s
归属校验: dump 主导包=com.xingin.xhs（104 节点） 目标包=0 节点 前台=com.suning.mobile.epa -> 不属于目标 App
归属校验失败，重试一次
启动 com.suning.mobile.epa（第 2 次）
就绪判定: 节点=233 前台=com.suning.mobile.epa 耗时=0.4s（节点数达标）
就绪: 节点=233 等待=0.4s
归属校验: dump 主导包=com.suning.mobile.epa（218 节点） 目标包=218 节点 前台=com.suning.mobile.epa -> 属于目标 App
  collect: 首屏命中 text='迎新福利' @(136, 1457)
  bonus: 首屏命中 text='领红包' @(936, 1013)
```

</details>

## 微博移动版

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| collect | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['任务中心', '福利', '赚积分', '做任务'] 全部未命中） | 二级页: candidates=['任务中心', '福利', '赚积分', '做任务'] 全部未命中 | 有 |
| bonus | 首屏未命中 | candidates=['点击领取', '红包', '现金奖励', '翻牌'] 全部未命中 | - |

<details><summary>执行日志</summary>

```
启动 com.sina.weibog3（第 1 次）
就绪判定: 节点=34 前台=com.sina.weibog3 耗时=2.3s（节点数达标）
就绪: 节点=34 等待=2.3s
归属校验: dump 主导包=com.suning.mobile.epa（19 节点） 目标包=0 节点 前台=com.sina.weibog3 -> 不属于目标 App
归属校验失败，重试一次
启动 com.sina.weibog3（第 2 次）
就绪判定: 节点=88 前台=com.sina.weibog3 耗时=1.7s（节点数达标）
就绪: 节点=88 等待=1.7s
归属校验: dump 主导包=com.sina.weibog3（73 节点） 目标包=73 节点 前台=com.sina.weibog3 -> 属于目标 App
  collect: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  collect: 第1轮导航后 仍未命中 candidates=['任务中心', '福利', '赚积分', '做任务'] 全部未命中
  collect: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  collect: 第2轮导航后页面不属于目标 App（主导包 com.xingin.xhs，188 节点）-> 本轮作废
复位: 第3次 BACK 后已不在目标 App（主导包 ）-> 改走重启
复位: BACK 未能回到顶层页 -> 重启 App
就绪判定: 节点=150 前台=com.sina.weibog3 耗时=12.9s（节点数达标）
  bonus: 首屏未命中（无前置步）candidates=['点击领取', '红包', '现金奖励', '翻牌'] 全部未命中
```

</details>

## 一淘

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 首屏命中 | any_of 分支#1: desc='签到' @(482, 384) | 有 |
| watch | 导航后命中 | any_of 全部分支未命中（末次: candidates=['去福狸中心做任务', '看视频领金币', '任务中心', '省金币', '今日任务'] 全部未命中） | 二级页: text='去福狸中心做任务' @(788, 664) | 有 |
| withdraw | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['我的', '我'] 全部未命中） | 二级页: text='我的' @(147, 941) 但不在底部导航带（y=941），疑似假命中 | 有 |

<details><summary>执行日志</summary>

```
启动 com.taobao.etao（第 1 次）
就绪判定: 节点=235 前台=com.taobao.etao 耗时=0.6s（节点数达标）
就绪: 节点=235 等待=0.6s
归属校验: dump 主导包=com.taobao.etao（220 节点） 目标包=220 节点 前台=com.taobao.etao -> 属于目标 App
  sign: 首屏命中 any_of 分支#1: desc='签到' @(482, 384)
  watch: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  watch: 第1轮导航后 命中 text='去福狸中心做任务' @(788, 664)
复位: BACK 未能回到顶层页 -> 重启 App
就绪判定: 节点=31 前台=com.taobao.etao 耗时=5.6s（节点数达标）
点掉弹窗按钮: 取消 @(664, 1334)
  withdraw: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  withdraw: 第1轮导航后 仍未命中 text='我的' @(147, 941) 但不在底部导航带（y=941），疑似假命中
  withdraw: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  withdraw: 第2轮导航后 仍未命中 text='我的' @(147, 941) 但不在底部导航带（y=941），疑似假命中
```

</details>

## 点淘

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| collect | 首屏未命中 | candidates=['待领取', '任务中心', '天天领', '福利', '领奖'] 全部未命中 | - |
| watch | 首屏未命中 | candidates=['赚更多元宝'] 全部未命中 | - |
| withdraw | 首屏未命中 | candidates=['去兑换'] 全部未命中 | - |

<details><summary>执行日志</summary>

```
启动 com.taobao.live（第 1 次）
就绪判定: 节点=79 前台=com.taobao.live 耗时=8.1s（节点数达标）
就绪: 节点=79 等待=8.1s
归属校验: dump 主导包=com.taobao.etao（64 节点） 目标包=0 节点 前台=com.taobao.live -> 不属于目标 App
归属校验失败，重试一次
启动 com.taobao.live（第 2 次）
就绪判定: 节点=27 前台=com.taobao.live 耗时=0.3s（节点数达标）
就绪: 节点=27 等待=0.3s
归属校验: dump 主导包=com.taobao.live（12 节点） 目标包=12 节点 前台=com.taobao.live -> 属于目标 App
  collect: 首屏未命中（无前置步）candidates=['待领取', '任务中心', '天天领', '福利', '领奖'] 全部未命中
  watch: 首屏未命中（无前置步）candidates=['赚更多元宝'] 全部未命中
  withdraw: 首屏未命中（无前置步）candidates=['去兑换'] 全部未命中
```

</details>

## 火龙漫剧

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '去签到', '天天有礼'] 全部未命中） | 二级页: text='签到' @(720, 2093) | 有 |
| watch | 首屏命中 | any_of 分支#1: text='福利' @(666, 2130) | 有 |
| withdraw | 首屏命中 | any_of 分支#1: text='我的' @(918, 2130) | 有 |

<details><summary>执行日志</summary>

```
启动 com.tencent.kairos（第 1 次）
就绪判定: 节点=26 前台=com.tencent.kairos 耗时=3.8s（节点数达标）
就绪: 节点=26 等待=3.8s
归属校验: dump 主导包=com.tencent.kairos（11 节点） 目标包=11 节点 前台=com.tencent.kairos -> 属于目标 App
  sign: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 命中 text='签到' @(720, 2093)
复位: 已在顶层页，无需 BACK
  watch: 首屏命中 any_of 分支#1: text='福利' @(666, 2130)
  withdraw: 首屏命中 any_of 分支#1: text='我的' @(918, 2130)
```

</details>

## 梧桐免费小说

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '看书得金币', '立即签到'] 全部未命中） | 二级页: text='签到' @(604, 2088) | 有 |
| watch | 首屏命中 | any_of 分支#1: text='福利商城' @(888, 834) | 有 |
| withdraw | 首屏命中 | text='我的' @(972, 2132) | - |

<details><summary>执行日志</summary>

```
启动 com.ushaqi.zhuishushenqi.ninenine（第 1 次）
就绪判定: 节点=42 前台=com.ushaqi.zhuishushenqi.ninenine 耗时=4.8s（节点数达标）
就绪: 节点=42 等待=4.8s
归属校验: dump 主导包=com.tencent.kairos（27 节点） 目标包=0 节点 前台=com.ushaqi.zhuishushenqi.ninenine -> 不属于目标 App
归属校验失败，重试一次
启动 com.ushaqi.zhuishushenqi.ninenine（第 2 次）
就绪判定: 节点=67 前台=com.ushaqi.zhuishushenqi.ninenine 耗时=10.5s（节点数达标）
就绪: 节点=67 等待=10.5s
归属校验: dump 主导包=com.ushaqi.zhuishushenqi.ninenine（52 节点） 目标包=52 节点 前台=com.ushaqi.zhuishushenqi.ninenine -> 属于目标 App
  sign: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 命中 text='签到' @(604, 2088)
复位: 已在顶层页，无需 BACK
  watch: 首屏命中 any_of 分支#1: text='福利商城' @(888, 834)
  withdraw: 首屏命中 text='我的' @(972, 2132)
```

</details>

## 今日看点极速版

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 首屏命中 | any_of 分支#1: text='签到' @(486, 1569) | 有 |
| watch | 首屏命中 | any_of 分支#1: text='看视频' @(353, 614) | 有 |
| withdraw | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['我的', '我'] 全部未命中） | 二级页: text='我的' @(922, 969) 但不在底部导航带（y=969），疑似假命中 | 有 |

<details><summary>执行日志</summary>

```
启动 com.jinrikd.news（第 1 次）
就绪判定: 节点=76 前台=com.jinrikd.news 耗时=33.7s（节点数达标）
就绪: 节点=76 等待=33.7s
归属校验: dump 主导包=com.jinrikd.news（61 节点） 目标包=61 节点 前台=com.jinrikd.news -> 属于目标 App
  sign: 首屏命中 any_of 分支#1: text='签到' @(486, 1569)
  watch: 首屏命中 any_of 分支#1: text='看视频' @(353, 614)
  withdraw: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  withdraw: 第1轮导航后 仍未命中 candidates=['我的', '我'] 全部未命中
  withdraw: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  withdraw: 第2轮导航后 仍未命中 text='我的' @(922, 969) 但不在底部导航带（y=969），疑似假命中
```

</details>

## 天天快讯极速版

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 首屏命中 | any_of 分支#1: text='签到' @(649, 952) | 有 |
| watch | 首屏命中 | text='看视频' @(723, 1419) | - |
| withdraw | 导航后命中 | any_of 全部分支未命中（末次: candidates=['我的', '我'] 全部未命中） | 二级页: text='我的' @(972, 2192) | 有 |

<details><summary>执行日志</summary>

```
启动 skysky.cy.kuaixun（第 1 次）
就绪判定: 节点=55 前台=skysky.cy.kuaixun 耗时=36.5s（节点数达标）
就绪: 节点=55 等待=36.5s
归属校验: dump 主导包=skysky.cy.kuaixun（40 节点） 目标包=40 节点 前台=skysky.cy.kuaixun -> 属于目标 App
  sign: 首屏命中 any_of 分支#1: text='签到' @(649, 952)
  watch: 首屏命中 text='看视频' @(723, 1419)
  withdraw: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  withdraw: 第1轮导航后 仍未命中 candidates=['我的', '我'] 全部未命中
  withdraw: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  withdraw: 第2轮导航后 命中 text='我的' @(972, 2192)
```

</details>

## 蛋花免费小说

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '立即签到', '幸运签'] 全部未命中） | 二级页: candidates=['签到', '每日签到', '立即签到', '幸运签'] 全部未命中 | 有 |
| watch | 首屏命中 | any_of 分支#1: text='福利' @(540, 2148) | 有 |
| withdraw | 首屏命中 | any_of 分支#1: text='我的' @(953, 2148) | 有 |

<details><summary>执行日志</summary>

```
启动 com.eggflower.read（第 1 次）
就绪判定: 节点=105 前台=com.eggflower.read 耗时=11.5s（节点数达标）
就绪: 节点=105 等待=11.5s
归属校验: dump 主导包=skysky.cy.kuaixun（90 节点） 目标包=0 节点 前台=com.eggflower.read -> 不属于目标 App
归属校验失败，重试一次
启动 com.eggflower.read（第 2 次）
就绪判定: 节点=272 前台=com.eggflower.read 耗时=1.2s（节点数达标）
就绪: 节点=272 等待=1.2s
归属校验: dump 主导包=com.eggflower.read（257 节点） 目标包=257 节点 前台=com.eggflower.read -> 属于目标 App
  sign: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '立即签到', '幸运签'] 全部未命中
  sign: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第2轮导航后 仍未命中 candidates=['签到', '每日签到', '立即签到', '幸运签'] 全部未命中
复位: 已在顶层页，无需 BACK
  watch: 首屏命中 any_of 分支#1: text='福利' @(540, 2148)
  withdraw: 首屏命中 any_of 分支#1: text='我的' @(953, 2148)
```

</details>

## 喜番免费短剧

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 首屏命中 | any_of 分支#1: text='赚现金' @(496, 2111) | 有 |
| watch | 导航后命中 | any_of 全部分支未命中（末次: candidates=['去看剧', '赚钱', '任务', '看剧赚钱', '福利'] 全部未命中） | 二级页: text='赚钱' @(968, 756) | 有 |
| withdraw | 首屏命中 | text='我的' @(970, 2145) | - |

<details><summary>执行日志</summary>

```
启动 com.kwai.theater（第 1 次）
就绪判定: 节点=130 前台=com.kwai.theater 耗时=21.7s（节点数达标）
就绪: 节点=130 等待=21.7s
归属校验: dump 主导包=com.kwai.theater（115 节点） 目标包=115 节点 前台=com.kwai.theater -> 属于目标 App
  sign: 首屏命中 any_of 分支#1: text='赚现金' @(496, 2111)
  watch: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  watch: 第1轮导航后 命中 text='赚钱' @(968, 756)
复位: 已在顶层页，无需 BACK
  withdraw: 首屏命中 text='我的' @(970, 2145)
```

</details>

## 河马剧场

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '看剧得金币', '立即签到', '去签到'] 全部未命中） | 二级页: candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中 | 有 |
| watch | 首屏命中 | any_of 分支#1: text='赚钱' @(416, 455) | 有 |
| withdraw | 首屏命中 | text='我' @(972, 2141) | - |

<details><summary>执行日志</summary>

```
启动 com.dz.hmjc（第 1 次）
就绪判定: 节点=150 前台=com.dz.hmjc 耗时=7.8s（节点数达标）
就绪: 节点=150 等待=7.8s
点掉弹窗按钮: 我知道了 @(540, 2046)
归属校验: dump 主导包=com.dz.hmjc（135 节点） 目标包=135 节点 前台=com.dz.hmjc -> 属于目标 App
  sign: 首屏未命中，执行前置导航
  sign: 检测到三级导航，中间入口 = [{'type': 'text', 'value': '福利'}, {'type': 'text', 'value': '福利中心'}]
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中
  sign: 点中间入口 text='福利' @(358, 568)
  sign: 第1轮三级页 仍未命中 candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中
  sign: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第2轮导航后 仍未命中 candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中
  sign: 第2轮二级页未找到中间入口 candidates 全部未命中
复位: 第1次 BACK 后已不在目标 App（主导包 ）-> 改走重启
复位: BACK 未能回到顶层页 -> 重启 App
达到最大等待 75s 仍未就绪，节点=299，按当前页继续
  watch: 首屏命中 any_of 分支#1: text='赚钱' @(416, 455)
  withdraw: 首屏命中 text='我' @(972, 2141)
```

</details>

## 红果免费短剧

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['签到', '去签到', '每日签到'] 全部未命中） | 二级页: candidates=['签到', '去签到', '每日签到'] 全部未命中 | 有 |
| watch | 首屏命中 | any_of 分支#1: text='赚钱' @(747, 2139) | 有 |
| withdraw | 首屏命中 | text='赚钱' @(747, 2139) | - |
| collect | 首屏命中 | any_of 分支#1: text='去领取' @(582, 752) | 有 |

<details><summary>执行日志</summary>

```
启动 com.phoenix.read（第 1 次）
就绪判定: 节点=203 前台=com.phoenix.read 耗时=26.8s（节点数达标）
就绪: 节点=203 等待=26.8s
归属校验: dump 主导包=com.phoenix.read（188 节点） 目标包=188 节点 前台=com.phoenix.read -> 属于目标 App
  sign: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '去签到', '每日签到'] 全部未命中
  sign: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第2轮导航后 仍未命中 candidates=['签到', '去签到', '每日签到'] 全部未命中
复位: 已在顶层页，无需 BACK
  watch: 首屏命中 any_of 分支#1: text='赚钱' @(747, 2139)
  withdraw: 首屏命中 text='赚钱' @(747, 2139)
  collect: 首屏命中 any_of 分支#1: text='去领取' @(582, 752)
```

</details>

## 悟空浏览器

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '阅读赚金币', '立即签到'] 全部未命中） | 二级页: candidates=['签到', '每日签到', '阅读赚金币', '立即签到'] 全部未命中 | 有 |
| watch | 首屏命中 | text='看剧' @(330, 2141) | - |
| withdraw | 首屏命中 | text='我的' @(960, 2141) | - |

<details><summary>执行日志</summary>

```
启动 com.cat.readall（第 1 次）
达到最大等待 75s 仍未就绪，节点=15，按当前页继续
就绪: 节点=15 等待=82.9s
归属校验: dump 主导包=（0 节点） 目标包=0 节点 前台= -> 不属于目标 App
归属校验失败，重试一次
启动 com.cat.readall（第 2 次）
就绪判定: 节点=146 前台=com.cat.readall 耗时=15.6s（节点数达标）
就绪: 节点=146 等待=15.6s
归属校验: dump 主导包=com.cat.readall（131 节点） 目标包=131 节点 前台=com.cat.readall -> 属于目标 App
  sign: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '阅读赚金币', '立即签到'] 全部未命中
  sign: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第2轮导航后 仍未命中 candidates=['签到', '每日签到', '阅读赚金币', '立即签到'] 全部未命中
复位: 第3次 BACK 回到顶层页
  watch: 首屏命中 text='看剧' @(330, 2141)
  withdraw: 首屏命中 text='我的' @(960, 2141)
```

</details>

## 全民K歌

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| collect | 首屏未命中 | candidates=['任务中心', '任务中心', '福利', '每日任务', '做任务'] 全部未命中 | - |
| bonus | 首屏未命中 | candidates=['红包', '领红包', '抽奖'] 全部未命中 | - |

<details><summary>执行日志</summary>

```
启动 com.tencent.karaoke（第 1 次）
就绪判定: 节点=46 前台=com.tencent.karaoke 耗时=15.5s（节点数达标）
就绪: 节点=46 等待=15.5s
归属校验: dump 主导包=com.tencent.karaoke（31 节点） 目标包=31 节点 前台=com.tencent.karaoke -> 属于目标 App
  collect: 首屏未命中（无前置步）candidates=['任务中心', '任务中心', '福利', '每日任务', '做任务'] 全部未命中
  bonus: 首屏未命中（无前置步）candidates=['红包', '领红包', '抽奖'] 全部未命中
```

</details>

## 抖音极速版

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中） | 二级页: candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中 | 有 |
| watch | 首屏未命中 | candidates=['刷视频', '看视频赚金币', '任务中心', '金币朋友'] 全部未命中 | - |
| withdraw | 首屏命中 | text='我' @(971, 2141) | - |

<details><summary>执行日志</summary>

```
启动 com.ss.android.ugc.aweme.lite（第 1 次）
就绪判定: 节点=306 前台=com.ss.android.ugc.aweme.lite 耗时=40.2s（节点数达标）
就绪: 节点=306 等待=40.2s
归属校验: dump 主导包=com.ss.android.ugc.aweme.lite（291 节点） 目标包=291 节点 前台=com.ss.android.ugc.aweme.lite -> 属于目标 App
  sign: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中
  sign: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第2轮导航后 仍未命中 candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中
复位: 已在顶层页，无需 BACK
  watch: 首屏未命中（无前置步）candidates=['刷视频', '看视频赚金币', '任务中心', '金币朋友'] 全部未命中
  withdraw: 首屏命中 text='我' @(971, 2141)
```

</details>

## 抖音火山版

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中） | 二级页: candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中 | 有 |
| watch | 首屏命中 | any_of 分支#1: text='点击赚钱' @(978, 371) | 有 |
| withdraw | 首屏命中 | text='我' @(971, 2141) | - |

<details><summary>执行日志</summary>

```
启动 com.ss.android.ugc.live（第 1 次）
就绪判定: 节点=124 前台=com.ss.android.ugc.live 耗时=62.1s（节点数达标）
就绪: 节点=124 等待=62.1s
归属校验: dump 主导包=com.ss.android.ugc.live（109 节点） 目标包=109 节点 前台=com.ss.android.ugc.live -> 属于目标 App
  sign: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中
  sign: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第2轮导航后 仍未命中 candidates=['签到', '每日签到', '开宝箱', '领金币'] 全部未命中
复位: 已在顶层页，无需 BACK
  watch: 首屏命中 any_of 分支#1: text='点击赚钱' @(978, 371)
  withdraw: 首屏命中 text='我' @(971, 2141)
```

</details>

## 抖音

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| - | 数据作废(页面非目标App) | 期望 com.ss.android.ugc.aweme；dump 主导包 （0 节点），目标包 0 节点；前台 com.ss.android.ugc.aweme | - |

<details><summary>执行日志</summary>

```
启动 com.ss.android.ugc.aweme（第 1 次）
达到最大等待 75s 仍未就绪，节点=15，按当前页继续
就绪: 节点=15 等待=89.6s
归属校验: dump 主导包=（0 节点） 目标包=0 节点 前台= -> 不属于目标 App
归属校验失败，重试一次
启动 com.ss.android.ugc.aweme（第 2 次）
达到最大等待 75s 仍未就绪，节点=15，按当前页继续
就绪: 节点=15 等待=101.9s
归属校验: dump 主导包=（0 节点） 目标包=0 节点 前台=com.ss.android.ugc.aweme -> 不属于目标 App
归属校验失败
归属校验最终失败 -> 本轮结果作废（dump 主导包 ，前台 com.ss.android.ugc.aweme）
```

</details>

## 今日头条极速版

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 首屏命中 | any_of 分支#1: desc='开宝箱' @(600, 2111) | 有 |
| watch | 首屏命中 | any_of 分支#1: text='看视频' @(327, 2000) | 有 |
| withdraw | 首屏命中 | text='我的' @(972, 2182) | - |
| bonus | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['完成挑战得奖励', '限时预约领金币', '预约', '红包'] 全部未命中） | 二级页: candidates=['完成挑战得奖励', '限时预约领金币', '预约', '红包'] 全部未命中 | 有 |

<details><summary>执行日志</summary>

```
启动 com.ss.android.article.lite（第 1 次）
就绪判定: 节点=71 前台=com.ss.android.article.lite 耗时=35.0s（节点数达标）
就绪: 节点=71 等待=35.0s
归属校验: dump 主导包=com.ss.android.article.lite（56 节点） 目标包=56 节点 前台=com.ss.android.article.lite -> 属于目标 App
  sign: 首屏命中 any_of 分支#1: desc='开宝箱' @(600, 2111)
  watch: 首屏命中 any_of 分支#1: text='看视频' @(327, 2000)
  withdraw: 首屏命中 text='我的' @(972, 2182)
  bonus: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  bonus: 第1轮导航后 仍未命中 candidates=['完成挑战得奖励', '限时预约领金币', '预约', '红包'] 全部未命中
  bonus: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  bonus: 第2轮导航后 仍未命中 candidates=['完成挑战得奖励', '限时预约领金币', '预约', '红包'] 全部未命中
```

</details>

*（内容由AI生成，仅供参考）*
