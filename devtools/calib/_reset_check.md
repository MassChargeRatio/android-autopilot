# 实机锚点回归报告

> 生成时间: 2026-09-15 00:32:16
> 设备: 192.168.1.54:5555

## 汇总

- 导航后命中: **2**
- 导航可救(建议加前置步): **1**

## 喜番免费短剧

| 行为 | 结果 | 明细 | 前置步 |
|---|---|---|---|
| sign | 导航后命中 | any_of 全部分支未命中（末次: candidates=['签到', '每日签到', '看剧赚金币', '去签到'] 全部未命中） | 二级页: （三级页）text='签到' @(539, 702) | 有 |
| watch | 导航后命中 | any_of 全部分支未命中（末次: candidates=['去看剧', '赚钱', '任务', '看剧赚钱', '福利'] 全部未命中） | 二级页: text='去看剧' @(968, 700) | 有 |
| withdraw | 导航可救(建议加前置步) | candidates=['我的', '我'] 全部未命中 | 二级页: text='我的' @(970, 2145) | - |

<details><summary>执行日志</summary>

```
启动 com.kwai.theater（第 1 次）
就绪判定: 节点=80 前台=com.kwai.theater 耗时=12.4s（节点数达标）
就绪: 节点=80 等待=12.4s
归属校验: dump 主导包=com.kwai.theater（65 节点） 目标包=65 节点 前台=com.kwai.theater -> 属于目标 App
  sign: 首屏未命中，执行前置导航
  sign: 检测到三级导航，中间入口 = [{'type': 'text', 'value': '赚现金'}, {'type': 'text', 'value': '任务中心'}, {'type': 'text', 'value': '福利中心'}, {'type': 'text', 'value': '我的福利'}, {'type': 'text', 'value': '福利'}, {'type': 'text', 'value': '赚钱'}, {'type': 'text', 'value': '金币'}, {'type': 'text', 'value': '领金币'}, {'type': 'text', 'value': '天天领'}, {'type': 'text', 'value': '做任务'}, {'type': 'text', 'value': '任务'}, {'type': 'text', 'value': '钱包'}, {'type': 'text', 'value': '现金'}, {'type': 'text', 'value': '元宝中心'}, {'type': 'text', 'value': '金币中心'}, {'type': 'text', 'value': '福利商城'}, {'type': 'text', 'value': '任务广场'}, {'type': 'text', 'value': '赚金币'}, {'type': 'text', 'value': '看剧赚钱'}, {'type': 'text', 'value': '看书赚钱'}, {'type': 'text', 'value': '看视频赚钱'}, {'type': 'text', 'value': '我的金币'}, {'type': 'text', 'value': '现金奖励'}]
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  sign: 第1轮导航后 仍未命中 candidates=['签到', '每日签到', '看剧赚金币', '去签到'] 全部未命中
  sign: 点中间入口 text='赚现金' @(493, 2106)
  sign: 第1轮三级页 命中 text='签到' @(539, 702)
复位: 第1次 BACK 回到顶层页
  watch: 首屏未命中，执行前置导航
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  watch: 第1轮导航后 命中 text='去看剧' @(968, 700)
复位: 第1次 BACK 后已不在目标 App（主导包 com.vivo.vtouch）-> 改走重启
复位: BACK 未能回到顶层页 -> 重启 App
就绪判定: 节点=47 前台=com.kwai.theater 耗时=3.1s（节点数达标）
  withdraw: 首屏未命中，执行前置导航（probe-nav 探路）
导航: --nav-fast 跳过 VLM，直接用比例坐标
导航: 比例坐标 -> (972,2141)
  withdraw: 第1轮导航后 命中 text='我的' @(970, 2145)
```

</details>

