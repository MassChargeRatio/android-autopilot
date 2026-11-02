# RPC 超时收紧（2026-10-31）

## 一、根因：库默认 300 秒

```
uiautomator2/_proto.py :  HTTP_TIMEOUT = 300
uiautomator2/base.py   :  http_timeout = kwargs.pop('http_timeout', HTTP_TIMEOUT)
```

`base.py` 的 jsonrpc 包装器**每次调用都从模块全局取默认值**，所以
`dump_hierarchy` / `click` / `wait` / `exists` / `screenshot` 全部按 300 秒等。
设备侧 agent 假死时就是干等 300 秒、期间零日志 —— 正好撞上外层 300s 上限，
表现成「莫名其妙超时被杀」。

10-31 全量里抖音火山版、微博移动版各中一次，合计 600 秒。

## 二、改法：改全局，不改调用点

连接时把模块全局改成 `config.device.rpc_timeout`（默认 20）：

```yaml
device:
  rpc_timeout: 20   # dump/click 正常都在 1.5s 内
```

```python
_u2base.HTTP_TIMEOUT = timeout
_u2proto.HTTP_TIMEOUT = timeout
```

为什么不逐个调用点传 `http_timeout=`：调用点太多，漏一个就还是 300s；
改全局是一处生效、可回滚，而且包装器读的就是这个全局（有测试钉住这条）。

## 三、真机验证

| App | 改前 | 改后 |
|---|---|---|
| 微博移动版 | 300s 超时被杀，零日志 | **82s**，且闸门抓到真实故障（见下） |
| 抖音火山版 | 300s 超时被杀，零日志 | **212s** 跑完，5 处步骤失败（正常的元素未命中） |

两个都不再挂死。抖音火山版节点只有 57 但前台正确，闸门没有误杀 —— 说明闸门判的是
「前台是不是目标 App」，不是「页面够不够丰富」。

## 四、顺带抓到一次真实的 deeplink 跳转

微博移动版这次启动后前台是 **支付宝**（`com.eg.android.AlipayGphone`）：

```
08:19:42 页面就绪判定: 节点=133 等待=31.5s 未稳定 前台=com.eg.android.AlipayGphone
08:20:20 页面就绪判定（重启后）: ... 前台=com.eg.android.AlipayGphone
08:20:20 [ERROR] 两次启动后前台仍是 com.eg.android.AlipayGphone，跳过本次全部行为
```

昨天全量里闸门一次没触发，今天第一次单独跑就撞上了 —— 说明这类跳转不是罕见事件，
只是昨天的采样没赶上。

同时修掉一处误导日志：`behavior_runner` 原来把「启动失败」一律写成
「启动失败（未安装）」，这次前台跳到支付宝也被写成「未安装」。已改成
「启动失败，跳过本次全部行为」，具体原因由 `_open_app` 自己记。

## 五、回归

```
pytest tests → 534 passed（530 + 4 新增）
```

新增 `tests/test_rpc_timeout.py` 4 条：
类属性默认 20 / config 取值与脏值回落 / `_apply_rpc_timeout` 改的是库内全局 /
包装器读模块全局（改完对下一次 RPC 立即生效，5s 被透传）。
