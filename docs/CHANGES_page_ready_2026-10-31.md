# 页面就绪：前台包名闸门（2026-10-31）

## 一、真因不是「等得不够久」

立卡时我以为是「页面就绪判定太宽松」。采样京东冷启动 35 秒后，看到的是另一回事：

```
  1.0s n=  64 .MainFrameActivity                                        ← 京东自己的壳
  7.6s n= 162 com.xingin.matrix.detail.activity.DetailFeedActivity      ← 小红书！
 35.3s n=  78 com.xingin.matrix.detail.activity.DetailFeedActivity      ← 还在小红书
```

**开屏广告 deeplink 直接把前台跳到了小红书**。而 `_open_app` 原来的写法是
`_wait_page_ready(...)` 拿回 `(n, waited, stable)` 就无条件打印「已启动 京东」往下走
—— 后面整条 sign 链的盲点坐标全部打在小红书里。

这和 2026-10-30 早些时候「趣头条未安装 → 坐标打进微信」是同一类事故：
**设备层已经跑偏，上层却当成成功**。区别只在于这次不是「没装」，是「被广告带走了」。

顺带否掉一个原本想做的方案：用节点数判断「页面是否够丰富」。实测节点数不可用 ——
河马剧场 47 节点就稳定可用，京东 63 节点是启动页，两者无法用阈值分开。

## 二、改了什么

1. `_wait_page_ready` 多返回一个**前台包名**（第 4 位），日志也带上：
   ```
   页面就绪判定: 节点=488 等待=9.4s 已稳定 前台=com.jingdong.app.mall
   ```
2. `_open_app` 校验前台包名：不是目标包 → **冷启动重启一次**；重启后仍不是 →
   记 ERROR 并 `return False`，`behavior_runner` 用 `is False` 整单跳过。

稳定性判定本身（连续两次节点数变化 ≤10%、波动型页面过半预算提前放行）**一行没动**
—— 那 17 个「提前放行」的 app 行为完全不变。

## 三、真机验证（故障注入，因为广告是概率事件）

京东连跑 3 次都没再复现 deeplink（广告频控），所以改成主动注入 HOME 抢前台。
脚本：`temp/fault_inject_foreground.py`

### 注入一次 → 重启后成功

```
[06:27:31] 冷启动（launch_reset）
>>> [注入-1] 已按 HOME，当前前台: com.bbk.launcher2
[06:28:07] 页面就绪判定: 节点=119 等待=31.0s 未稳定 前台=com.bbk.launcher2
[06:28:07] 启动后前台是 com.bbk.launcher2（不是 com.jingdong.app.mall），疑似开屏广告 deeplink 跳出，重启一次
[06:28:23] 页面就绪判定（重启后）: 节点=489 等待=9.8s 已稳定 前台=com.jingdong.app.mall
[06:28:23] 已启动 京东
→ _open_app 返回 True，53.3s
```

### 注入两次 → 跳过整个 App

```
[06:30:50] 启动后前台是 com.bbk.launcher2（...），重启一次
>>> [注入-2] 已按 HOME
[06:31:27] 页面就绪判定（重启后）: 节点=119 等待=32.4s 未稳定 前台=com.bbk.launcher2
[06:31:27] [ERROR] 两次启动后前台仍是 com.bbk.launcher2，跳过本次全部行为（否则盲点坐标会落到别的 App 上）
→ _open_app 返回 False，72.3s
```

### 正常路径（无注入，连跑 3 次）

`节点=488~502 等待=7.1~11.0s 已稳定 前台=com.jingdong.app.mall`，
sign 链 0 处「步骤失败」（改前是 1 处 `text_nodes=FAIL`），单次 56s。

## 四、代价

闸门触发时要多等一个完整 `max_wait`（30s），最坏 60s+。这是安全换时间：
盲点坐标打进别人的 App 比多等 30 秒严重得多。

## 五、回归

```
pytest tests → 530 passed（524 + 6 新增）
```

新增 `tests/test_open_app_foreground.py` 6 条：
前台正确→放行 / 跑偏一次→冷启动重启后放行 / 两次跑偏→False 且不打印「已启动」/
前台取不到（空）→同样跳过 / dry-run 不碰设备 / runner 收到 False 整单跳过。

同时更新 `tests/test_page_ready.py` 8 处解包（3 元组 → 4 元组）。

## 六、还没做的

- 「提前放行」判据（过半预算 + 节点≥80）本身没改。它在 17 个 app 上生效，
  目前没有证据说它是错的 —— 快手 14:32 那次点空更可能是同类的「前台跑偏」，
  只是当时没有这个日志，无法回查。等闸门跑一段时间，看还有没有点空。
- 抖音两个 300s 超时（RPC 无超时）仍未修，是独立问题。
