# 三级导航探针报告

> 生成时间: 2026-09-14 19:58:34
> 设备: 192.168.1.54:5555
> 三级页命中: 2/8；二级页即命中: 1；找到二级入口: 7

| App | 行为 | 二级页即命中 | 二级入口 | 三级锚点 | 截图 |
|---|---|---|---|---|---|
| 一淘 | sign | - | text=去福狸中心做任务 | - | `deep_sign_L3.png` |
| 今日看点极速版 | sign | text=喝水打卡 | - | - | `deep_sign_L2.png` |
| 天天快讯极速版 | sign | - | text=福利中心 | text=去签到 | `deep_sign_L3.png` |
| 蛋花免费小说 | sign | - | text=福利 | - | `deep_sign_L3.png` |
| 喜番免费短剧 | sign | - | text=赚现金 | text=立即签到 | `deep_sign_L3.png` |
| 河马剧场 | sign | - | text=福利 | - | `deep_sign_L3.png` |
| 悟空浏览器 | sign | - | text=赚钱 | - | `deep_sign_L3.png` |
| 抖音火山版 | sign | - | text=点击赚钱 | - | `deep_sign_L3.png` |

<details><summary>一淘.sign</summary>

```
就绪判定: 节点=57 前台=com.taobao.etao 耗时=9.0s（节点数达标）
就绪: 节点=57 等待=9.0s
归属校验: 主导包=com.ss.android.article.lite（42 节点） 目标包=0 节点 前台=com.taobao.etao -> 不属于
归属校验失败，重试
就绪判定: 节点=31 前台=com.taobao.etao 耗时=0.3s（节点数达标）
就绪: 节点=31 等待=0.3s
点掉弹窗按钮: 取消 @(664, 1334)
归属校验: 主导包=com.taobao.etao（16 节点） 目标包=16 节点 前台=com.taobao.etao -> 属于目标 App
点『我的』(972,2141)
二级页节点=190 主导包=com.taobao.etao
二级页入口: text='去福狸中心做任务' @(788, 664)，点进去
三级页节点=25 主导包=com.taobao.etao
三级页未找到目标锚点
```
</details>

<details><summary>今日看点极速版.sign</summary>

```
就绪判定: 节点=107 前台=com.jinrikd.news 耗时=27.4s（节点数达标）
就绪: 节点=107 等待=27.4s
归属校验: 主导包=com.jinrikd.news（92 节点） 目标包=92 节点 前台=com.jinrikd.news -> 属于目标 App
点『我的』(972,2141)
二级页节点=103 主导包=com.jinrikd.news
★ 二级页即命中: text='喝水打卡' @(412, 969)（无需三级导航）
```
</details>

<details><summary>天天快讯极速版.sign</summary>

```
就绪判定: 节点=123 前台=skysky.cy.kuaixun 耗时=25.2s（节点数达标）
就绪: 节点=123 等待=25.2s
归属校验: 主导包=skysky.cy.kuaixun（108 节点） 目标包=108 节点 前台=skysky.cy.kuaixun -> 属于目标 App
点『我的』(972,2141)
二级页节点=105 主导包=skysky.cy.kuaixun
二级页入口: text='福利中心' @(166, 1031)，点进去
三级页节点=209 主导包=skysky.cy.kuaixun
★ 三级页命中: text='去签到' @(906, 1338)
```
</details>

<details><summary>蛋花免费小说.sign</summary>

```
就绪判定: 节点=67 前台=com.eggflower.read 耗时=13.2s（节点数达标）
就绪: 节点=67 等待=13.2s
归属校验: 主导包=com.eggflower.read（52 节点） 目标包=52 节点 前台=com.eggflower.read -> 属于目标 App
点『我的』(972,2141)
二级页节点=243 主导包=com.eggflower.read
二级页入口: text='福利' @(540, 2148)，点进去
三级页节点=113 主导包=com.eggflower.read
三级页未找到目标锚点
```
</details>

<details><summary>喜番免费短剧.sign</summary>

```
就绪判定: 节点=116 前台=com.kwai.theater 耗时=34.0s（节点数达标）
就绪: 节点=116 等待=34.0s
归属校验: 主导包=com.kwai.theater（101 节点） 目标包=101 节点 前台=com.kwai.theater -> 属于目标 App
点『我的』(972,2141)
二级页节点=180 主导包=com.kwai.theater
二级页入口: text='赚现金' @(496, 2111)，点进去
三级页节点=218 主导包=com.kwai.theater
★ 三级页命中: text='立即签到' @(896, 2020)
```
</details>

<details><summary>河马剧场.sign</summary>

```
就绪判定: 节点=191 前台=com.dz.hmjc 耗时=13.0s（节点数达标）
就绪: 节点=191 等待=13.0s
归属校验: 主导包=com.dz.hmjc（176 节点） 目标包=176 节点 前台=com.dz.hmjc -> 属于目标 App
点『我的』(972,2141)
二级页节点=191 主导包=com.dz.hmjc
二级页入口: text='福利' @(358, 568)，点进去
三级页节点=66 主导包=com.dz.hmjc
三级页未找到目标锚点
```
</details>

<details><summary>悟空浏览器.sign</summary>

```
就绪判定: 节点=161 前台=com.cat.readall 耗时=26.0s（节点数达标）
就绪: 节点=161 等待=26.0s
归属校验: 主导包=com.cat.readall（146 节点） 目标包=146 节点 前台=com.cat.readall -> 属于目标 App
点『我的』(972,2141)
二级页节点=142 主导包=com.cat.readall
二级页入口: text='赚钱' @(540, 2141)，点进去
三级页节点=130 主导包=com.cat.readall
三级页未找到目标锚点
```
</details>

<details><summary>抖音火山版.sign</summary>

```
就绪判定: 节点=325 前台=com.ss.android.ugc.live 耗时=53.1s（节点数达标）
就绪: 节点=325 等待=53.1s
归属校验: 主导包=com.ss.android.ugc.live（310 节点） 目标包=310 节点 前台=com.ss.android.ugc.live -> 属于目标 App
点『我的』(972,2141)
二级页节点=266 主导包=com.ss.android.ugc.live
二级页入口: text='点击赚钱' @(978, 371)，点进去
三级页节点=16 主导包=com.ss.android.ugc.live
三级页未找到目标锚点
```
</details>

