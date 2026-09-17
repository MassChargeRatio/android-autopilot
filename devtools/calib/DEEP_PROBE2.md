# 三级导航探针报告

> 生成时间: 2026-09-14 20:07:14
> 设备: 192.168.1.54:5555
> 三级页命中: 1/6；二级页即命中: 0；找到二级入口: 1

| App | 行为 | 二级页即命中 | 尝试过的二级入口 | 命中的入口 | 三级锚点 |
|---|---|---|---|---|---|
| 一淘 | sign | - | text=去福狸中心做任务 → ✗ 未命中<br>text=返利钱包 → ✗ 未命中<br>text=什么是返利钱包？ → ✗ 未命中 | - | - |
| 今日看点极速版 | sign | - | text=金币收益 → ✗ 未命中<br>text=我的钱包 → ✗ 未命中<br>text=现金收益 → ✗ 未命中 | - | - |
| 蛋花免费小说 | sign | - | text=福利 → ✗ 未命中<br>text=金币 → ✗ 未命中 | - | - |
| 河马剧场 | sign | - | text=福利 → text=去签到 | text=福利 | text=去签到 |
| 悟空浏览器 | sign | - | text=赚钱 → ✗ 未命中<br>text=已赚金币 → ✗ 未命中 | - | - |
| 抖音火山版 | sign | - | text=点击赚钱 → ✗ 未命中 | - | - |

<details><summary>一淘.sign</summary>

```
就绪判定: 节点=25 前台=com.taobao.etao 耗时=0.9s（节点数达标）
就绪: 节点=25 等待=0.9s
归属校验: 主导包=com.taobao.etao（10 节点） 目标包=10 节点 前台=com.taobao.etao -> 属于目标 App
点『我的』(972,2141)
二级页节点=190 主导包=com.taobao.etao
二级页候选入口 3 个: ['去福狸中心做任务@(788, 664)', '返利钱包@(150, 445)', '什么是返利钱包？@(314, 607)']
[1/3] 点入口 text='去福狸中心做任务' @(788, 664)
  三级页节点=28 主导包=com.taobao.etao
  三级页未找到目标锚点
[2/3] 点入口 text='返利钱包' @(150, 445)
  三级页节点=63 主导包=com.taobao.etao
  三级页未找到目标锚点
[3/3] 点入口 text='什么是返利钱包？' @(314, 607)
  三级页节点=53 主导包=com.taobao.etao
  三级页未找到目标锚点
```
</details>

<details><summary>今日看点极速版.sign</summary>

```
就绪判定: 节点=81 前台=com.jinrikd.news 耗时=26.7s（节点数达标）
就绪: 节点=81 等待=26.7s
归属校验: 主导包=com.jinrikd.news（66 节点） 目标包=66 节点 前台=com.jinrikd.news -> 属于目标 App
点『我的』(972,2141)
二级页节点=103 主导包=com.jinrikd.news
二级页候选入口 3 个: ['金币收益@(198, 416)', '我的钱包@(922, 969)', '现金收益@(696, 416)']
[1/3] 点入口 text='金币收益' @(198, 416)
  三级页节点=32 主导包=com.jinrikd.news
  三级页未找到目标锚点
[2/3] 点入口 text='我的钱包' @(922, 969)
  三级页节点=32 主导包=com.jinrikd.news
  三级页未找到目标锚点
[3/3] 点入口 text='现金收益' @(696, 416)
  三级页节点=75 主导包=com.jinrikd.news
  三级页未找到目标锚点
```
</details>

<details><summary>蛋花免费小说.sign</summary>

```
就绪判定: 节点=75 前台=com.eggflower.read 耗时=4.6s（节点数达标）
就绪: 节点=75 等待=4.6s
归属校验: 主导包=com.jinrikd.news（60 节点） 目标包=0 节点 前台=com.eggflower.read -> 不属于
归属校验失败，重试
就绪判定: 节点=247 前台=com.eggflower.read 耗时=0.8s（节点数达标）
就绪: 节点=247 等待=0.8s
归属校验: 主导包=com.eggflower.read（232 节点） 目标包=232 节点 前台=com.eggflower.read -> 属于目标 App
点『我的』(972,2141)
二级页节点=138 主导包=com.eggflower.read
二级页候选入口 2 个: ['福利@(540, 2148)', '金币@(162, 854)']
[1/2] 点入口 text='福利' @(540, 2148)
  三级页节点=50 主导包=com.eggflower.read
  三级页未找到目标锚点
[2/2] 点入口 text='金币' @(162, 854)
  三级页节点=34 主导包=com.eggflower.read
  三级页未找到目标锚点
```
</details>

<details><summary>河马剧场.sign</summary>

```
就绪判定: 节点=34 前台=com.dz.hmjc 耗时=4.5s（节点数达标）
就绪: 节点=34 等待=4.5s
归属校验: 主导包=com.eggflower.read（19 节点） 目标包=0 节点 前台=com.dz.hmjc -> 不属于
归属校验失败，重试
就绪判定: 节点=140 前台=com.dz.hmjc 耗时=1.8s（节点数达标）
就绪: 节点=140 等待=1.8s
归属校验: 主导包=com.dz.hmjc（125 节点） 目标包=125 节点 前台=com.dz.hmjc -> 属于目标 App
点『我的』(972,2141)
二级页节点=191 主导包=com.dz.hmjc
二级页候选入口 1 个: ['福利@(358, 568)']
[1/1] 点入口 text='福利' @(358, 568)
  三级页节点=150 主导包=com.dz.hmjc
  ★ 三级页命中: text='去签到' @(912, 1062)
```
</details>

<details><summary>悟空浏览器.sign</summary>

```
就绪判定: 节点=157 前台=com.cat.readall 耗时=22.3s（节点数达标）
就绪: 节点=157 等待=22.3s
归属校验: 主导包=com.cat.readall（142 节点） 目标包=142 节点 前台=com.cat.readall -> 属于目标 App
点『我的』(972,2141)
二级页节点=142 主导包=com.cat.readall
二级页候选入口 2 个: ['赚钱@(540, 2141)', '已赚金币@(153, 375)']
[1/2] 点入口 text='赚钱' @(540, 2141)
  三级页节点=133 主导包=com.cat.readall
  三级页未找到目标锚点
[2/2] 点入口 text='已赚金币' @(153, 375)
  三级页节点=104 主导包=com.cat.readall
  三级页未找到目标锚点
```
</details>

<details><summary>抖音火山版.sign</summary>

```
就绪判定: 节点=313 前台=com.ss.android.ugc.live 耗时=54.9s（节点数达标）
就绪: 节点=313 等待=54.9s
归属校验: 主导包=com.ss.android.ugc.live（298 节点） 目标包=298 节点 前台=com.ss.android.ugc.live -> 属于目标 App
点『我的』(972,2141)
二级页节点=266 主导包=com.ss.android.ugc.live
二级页候选入口 1 个: ['点击赚钱@(978, 371)']
[1/1] 点入口 text='点击赚钱' @(978, 371)
  三级页节点=80 主导包=com.ss.android.ugc.live
  三级页未找到目标锚点
```
</details>

