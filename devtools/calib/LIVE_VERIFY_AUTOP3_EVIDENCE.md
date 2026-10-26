---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 58c070810b91e31b76e5016e97ae2974_45d092eecba411f18078525400de85a5
    ReservedCode1: aY0Qro94nQVph4n6jeVZaF6R8GVkTHWRTcBju7a2Mq0V0kxYZKtITh7XSgEXTPqf3xn55ueSN/DOYB/vo7rkJbkLLqo+XKsbByhUGLAiPP+mHdmt0+CPAo6tqpU0zfd7C7CYXn4YCS5rM1pVjeFfNi4WARUMnccw6eL6dUg8ZlbLKbwkay7gEAE1l3U=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 58c070810b91e31b76e5016e97ae2974_45d092eecba411f18078525400de85a5
    ReservedCode2: aY0Qro94nQVph4n6jeVZaF6R8GVkTHWRTcBju7a2Mq0V0kxYZKtITh7XSgEXTPqf3xn55ueSN/DOYB/vo7rkJbkLLqo+XKsbByhUGLAiPP+mHdmt0+CPAo6tqpU0zfd7C7CYXn4YCS5rM1pVjeFfNi4WARUMnccw6eL6dUg8ZlbLKbwkay7gEAE1l3U=
---

# 实机锚点回归报告

> 生成时间: 2026-10-19 17:49:37
> 设备: 192.168.1.54:5555

## 汇总

- 首屏命中: **4**
- 首屏未命中: **3**
- 导航后命中: **2**

## 点淘

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| collect | 首屏未命中 | candidates=['待领取', '任务中心', '天天领', '福利', '领奖'] 全部未命中 | - |
| watch | 首屏未命中 | candidates=['赚更多元宝'] 全部未命中 | - |
| withdraw | 首屏未命中 | candidates=['去兑换'] 全部未命中 | - |

<details><summary>执行日志</summary>

```
启动 com.taobao.live（第 1 次）
就绪判定: 节点=31 前台=com.taobao.live 耗时=8.0s（节点数达标）
就绪: 节点=31 等待=8.0s
点掉弹窗按钮: 取消 @(664, 1334)
归属校验: dump 主导包=com.taobao.etao（16 节点） 目标包=0 节点 前台=com.taobao.live -> 不属于目标 App
归属校验失败，重试一次
启动 com.taobao.live（第 2 次）
就绪判定: 节点=265 前台=com.taobao.live 耗时=0.7s（节点数达标）
就绪: 节点=265 等待=0.7s
点掉弹窗按钮: 关闭 @(1038, 1982)
归属校验: dump 主导包=com.taobao.live（250 节点） 目标包=250 节点 前台=com.taobao.live -> 属于目标 App
  collect: 首屏未命中（无前置步）candidates=['待领取', '任务中心', '天天领', '福利', '领奖'] 全部未命中
  watch: 首屏未命中（无前置步）candidates=['赚更多元宝'] 全部未命中
  withdraw: 首屏未命中（无前置步）candidates=['去兑换'] 全部未命中
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
就绪判定: 节点=121 前台=com.kwai.theater 耗时=7.1s（节点数达标）
就绪: 节点=121 等待=7.1s
归属校验: dump 主导包=com.taobao.live（106 节点） 目标包=0 节点 前台=com.kwai.theater -> 不属于目标 App
归属校验失败，重试一次
启动 com.kwai.theater（第 2 次）
就绪判定: 节点=137 前台=com.kwai.theater 耗时=1.4s（节点数达标）
就绪: 节点=137 等待=1.4s
归属校验: dump 主导包=com.kwai.theater（122 节点） 目标包=122 节点 前台=com.kwai.theater -> 属于目标 App
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
| sign | 导航后命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '看剧得金币', '立即签到', '去签到'] 全部未命中） | 二级页: （三级页）text='签到' @(912, 1011) | 有 |
| watch | 首屏命中 | any_of 分支#1: text='福利' @(160, 161) | 有 |
| withdraw | 首屏命中 | text='我的' @(972, 2132) | - |

<details><summary>执行日志</summary>

```
启动 com.dz.hmjc（第 1 次）
就绪判定: 节点=85 前台=com.dz.hmjc 耗时=5.9s（节点数达标）
就绪: 节点=85 等待=5.9s
归属校验: dump 主导包=com.kwai.theater（70 节点） 目标包=0 节点 前台=com.dz.hmjc -> 不属于目标 App
归属校验失败，重试一次
启动 com.dz.hmjc（第 2 次）
就绪判定: 节点=140 前台=com.dz.hmjc 耗时=2.1s（节点数达标）
就绪: 节点=140 等待=2.1s
归属校验: dump 主导包=com.dz.hmjc（125 节点） 目标包=125 节点 前台=com.dz.hmjc -> 属于目标 App
  sign: 首屏未命中，执行前置导航
  sign: 检测到三级导航，中间入口 = [{'type': 'text', 'value': '福利'}, {'type': 'text', 'value': '福利中心'}]
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中
  sign: 点中间入口 text='福利' @(358, 568)
  sign: 第1轮三级页 命中 text='签到' @(912, 1011)
复位: 已在顶层页，无需 BACK
  watch: 首屏命中 any_of 分支#1: text='福利' @(160, 161)
  withdraw: 首屏命中 text='我的' @(972, 2132)
```

</details>

*（内容由AI生成，仅供参考）*
