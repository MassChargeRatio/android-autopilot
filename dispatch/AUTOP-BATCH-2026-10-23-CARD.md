# 派单卡：17 个带 sign 的 App 真机带跑验证（AUTOP-BATCH-2026-10-23）

派单编号：`AUTOP-BATCH-2026-10-23`
工作目录：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
设备：`192.168.1.54:5555`（vivo V1911A，Android，1080x2340）
环境：**必须** `./.venv/Scripts/python.exe`（系统 python / uv python 均无依赖）

## 1. 任务

对下列 17 个 App **逐个**执行一次签到，记录真实命中情况：

```
01_趣头条  com.jifen.qukan
02_拼多多  com.xunmeng.pinduoduo
03_京东    com.jingdong.app.mall
04_美团    com.sankuai.meituan
05_快手    com.smile.gifmaker
06_百度地图 com.baidu.BaiduMap
07_海马畅听 com.hm.hmct2025
08_UC浏览器极速版 com.ucmobile.lite
09_飞猪旅行 com.taobao.trip
10_米读小说 com.lechuan.midunovel
11_米读极速版 com.lechuan.mdwz
13_大众点评 com.dianping.v1
22_天天快讯极速版 skysky.cy.kuaixun
23_蛋花免费小说 com.eggflower.read
24_喜番免费短剧 com.kwai.theater
25_河马剧场 com.dz.hmjc
26_红果免费短剧 com.phoenix.read
27_悟空浏览器 com.cat.readall
29_抖音极速版 com.ss.android.ugc.aweme.lite
30_抖音火山版 com.ss.android.ugc.live
32_今日头条极速版 com.ss.android.article.lite
34_京东理财 com.jd.jrapp
```

**实际执行 17 个即可**：从上表按序取前 17 个（到 `26_红果免费短剧` 为止）。
若某 App 的 `package` 未安装（`adb shell pm list packages | grep <pkg>` 为空），记 `SKIP-NOT-INSTALLED` 并继续下一个。

单次命令模板：

```bash
./.venv/Scripts/python.exe main.py --app "<App名>" --task 签到 --force --fast
```

## 2. 环境前置（必做，否则全部失败）

本机 adb daemon 会被回收，且 **uiautomator2 用的是 venv 内置 adb**，与项目 `tools/platform-tools/adb.exe` 不是同一个：

```bash
.venv/Lib/site-packages/adbutils/binaries/adb.exe connect 192.168.1.54:5555
.venv/Lib/site-packages/adbutils/binaries/adb.exe devices   # 必须看到 device
```

**每次跑之前**都要先执行这条 connect（daemon 可能已被回收）。
若出现 `device '192.168.1.54:5555' not found` → 重新 connect，最多重试 3 次，仍失败记 `BLOCKED-DEVICE` 并停止整批。

## 3. 红线（违反即返工）

1. **不改任何配置**：`config/apps/**`、`config.yaml` 只读；不得用 `--apply`、不得调 `yaml_writer` 写盘。
2. **不改代码**：`*.py` 全部只读（本卡只做「跑 + 记录」）。
3. **不碰资金**：出现「提现 / 确认提现 / 支付 / 立即支付 / 输入密码 / 验证码」一律**不点**，记 `SKIP-MONEY` 并继续下一个 App。
4. **遇登录页/验证码/滑块**：不尝试破解，记 `SKIP-LOGIN` 或 `SKIP-CAPTCHA`，继续下一个。
5. **不卸载、不清数据、不改系统设置**。
6. 单 App 超时上限 **150 秒**（`timeout 150`），超时记 `TIMEOUT` 并继续。

## 4. 交付物（硬性）

1. `dispatch/AUTOP-BATCH-2026-10-23/PROGRESS.md`：
   - 一张 17 行结果表，列：`App | 结果 | 命中方式 | 失败步骤 | 备注`
   - 结果取值：`PASS`（签到链走完且命中）｜`PARTIAL`（部分步骤命中，链未走完）｜`FAIL`｜`SKIP-*`｜`TIMEOUT`
   - 命中方式写实际日志里的 `(text)签到` / `(desc)…` / `点击坐标 (x,y)` / `未命中`
   - 表下附「共性问题」3–6 条（如某类 App 普遍需要坐标兜底、某类弹窗清扫失效等）
2. `dispatch/AUTOP-BATCH-2026-10-23/logs/<序号>_<App>.log`：每个 App 一份原始输出
   （`main.py … 2>&1 | grep -v DEBUG > logs/…log`）
3. 跑完在 PROGRESS 末尾写「终态表」：17 个 App 的 PASS/PARTIAL/FAIL/SKIP 计数 + 总耗时。

## 5. 硬性节奏（上一轮两卡都因「只读不写」被判失败，必须遵守）

1. **前 3 个工具调用内**创建 `dispatch/AUTOP-BATCH-2026-10-23/PROGRESS.md`（表头 + 17 行空行）和 `logs/` 目录。
2. **每跑完 1 个 App 立即追加一行**到结果表（含真实日志摘录），禁止攒到最后一次性写。
3. 预算约 250 次工具调用；到预算落盘「部分结论 + 剩余清单」并结束。
4. 不要停在 `requires_action`；设备异常按 §2 重试，仍不行记 BLOCKED 收尾。

## 6. 验收（Host 会复核，不看自述看实跑）

1. PROGRESS 表 17 行齐全，且每行有对应 `logs/*.log` 文件；
2. Host 随机抽 3 个标记 `PASS` 的 App **亲自复跑**，结果需一致；
3. `sha256sum -c dispatch/AUTOP-WEBUI-YAML-2026-10-22/baseline_sha256.txt` 全 OK（配置零改动）；
4. 禁碰文件 mtime 不变（`main.py`、`behavior_runner.py`、`config/apps/**`）。

## 7. 已知坑（直接照做，别重复踩）

- **星图金融**首页有广告弹窗，`back` 会直接退出 App；本批不含它。
- **微博移动版**视图树过深，`dump_hierarchy` 抛 `RPCStackOverflowError`，按文案定位全废；本批不含它。
- 部分 App 首页有 banner 轮播，坐标会漂移 ±40px；本批配置里已有坐标兜底，若 miss 就记 `PARTIAL` 并在备注写「疑似 banner 漂移」，**不要自行改坐标**。
- 弹窗清扫遇到「支付」字样会熔断（设计如此，防误点付款），日志里出现 `弹窗清扫熔断` 属正常，继续跑即可。

## 8. 投递记录

（Host 填：cid / 时间 / 首响）

| 项 | 值 |
|---|---|
| cid | `conv_fb0b7dc1f8604b92ba5ba8de688d618e` |
| 时间 | 2026-10-23 08:36 |
| 首响 | 「我先读取任务卡片，了解完整任务要求。」 |
