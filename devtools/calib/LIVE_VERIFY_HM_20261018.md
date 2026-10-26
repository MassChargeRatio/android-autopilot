# 实机锚点回归报告

> 生成时间: 2026-10-18 18:19:47
> 设备: 192.168.1.54:5555

## 汇总

- 导航后仍未命中: **1**
- 导航后命中: **1**
- 首屏命中: **1**

## 河马剧场

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后仍未命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中） | 二级页: candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中 | 有 |
| watch | 导航后命中 | any_of 全部分支未命中（末次: candidates=['福利', '赚钱', '任务', '看剧赚钱', '福利中心'] 全部未命中） | 二级页: text='福利' @(358, 568) | 有 |
| withdraw | 首屏命中 | text='我的' @(972, 2132) | - |

<details><summary>执行日志</summary>

```
启动 com.dz.hmjc（第 1 次）
就绪判定: 节点=191 前台=com.dz.hmjc 耗时=0.3s（节点数达标）
就绪: 节点=191 等待=0.3s
归属校验: dump 主导包=com.dz.hmjc（176 节点） 目标包=176 节点 前台=com.dz.hmjc -> 属于目标 App
  sign: 首屏未命中，执行前置导航
  sign: 检测到三级导航，中间入口 = [{'type': 'text', 'value': '福利'}, {'type': 'text', 'value': '任务中心'}, {'type': 'text', 'value': '福利中心'}, {'type': 'text', 'value': '我的福利'}, {'type': 'text', 'value': '赚钱'}, {'type': 'text', 'value': '金币'}, {'type': 'text', 'value': '领金币'}, {'type': 'text', 'value': '天天领'}, {'type': 'text', 'value': '做任务'}, {'type': 'text', 'value': '任务'}, {'type': 'text', 'value': '钱包'}, {'type': 'text', 'value': '现金'}, {'type': 'text', 'value': '元宝中心'}, {'type': 'text', 'value': '金币中心'}, {'type': 'text', 'value': '福利商城'}, {'type': 'text', 'value': '任务广场'}, {'type': 'text', 'value': '赚金币'}, {'type': 'text', 'value': '看剧赚钱'}, {'type': 'text', 'value': '看书赚钱'}, {'type': 'text', 'value': '看视频赚钱'}, {'type': 'text', 'value': '我的金币'}, {'type': 'text', 'value': '现金奖励'}]
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 全部未命中
  sign: 点中间入口 text='福利' @(358, 568)
  sign: 三级页不属于目标 App（主导包 com.jingdong.app.mall）
  sign: 第1轮未命中，回退首页重试一次
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第2轮导航后页面不属于目标 App（主导包 com.jingdong.app.mall，31 节点）-> 本轮作废
复位: 第1次 BACK 后已不在目标 App（主导包 com.jingdong.app.mall）-> 改走重启
复位: BACK 未能回到顶层页 -> 重启 App
就绪判定: 节点=48 前台=com.dz.hmjc 耗时=4.4s（节点数达标）
  watch: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  watch: 第1轮导航后 命中 text='福利' @(358, 568)
复位: 已在顶层页，无需 BACK
  withdraw: 首屏命中 text='我的' @(972, 2132)
```

</details>

