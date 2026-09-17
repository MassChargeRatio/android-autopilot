# manual 项根因分类（15 项）

> 依据 `devtools/calib/<app>/screen_after.png` 逐张人工目视 + `ui_after.xml` 结构。
> 结论：**15 个 manual 里只有 4 个是真的「没有锚点」**，其余都是
> 数据质量问题或可用 rid / 文本锚点解决。

## 分类

### A. 弹窗/广告遮挡（dump 抓的是弹窗，不是「我的」页）—— 2 项

| App | 行为 | 证据 | 处置 |
|---|---|---|---|
| 今日看点极速版 | withdraw | `screen_after.png` 是「恭喜获得 +6440金币 +100元」奖励弹窗；`ui_after.xml` 仅 32 节点 | 先关弹窗再重新校准；不是缺锚点 |
| 全民K歌 | bonus | `screen_after.png` 是「百事可乐音乐盛典」全屏广告 | 同上；补 `dismiss_popups` 规则 |

> 这两个说明 `calibrate.py` 的 `dismiss_popups` 覆盖不足，
> 奖励弹窗/开屏广告的关闭按钮文案未收录。

### B. 目标 App 从未进入前台（数据无效）—— 3 项

| App | 行为 | 证据 | 处置 |
|---|---|---|---|
| 天天快讯极速版 | sign / watch / withdraw | `screen_after.png` 是**系统「图片」App**（底部 tab：图片/相册/推荐/搜索） | 数据作废，需重新校准 |

> 与交接文档 §6 提到的「天天快讯极速版 前台是 launcher」一致。
> `calibrate.py` 应在前台校验失败时**直接判失败**，而不是照常 dump。

### C. 入口是「只有 rid 的纯图标」—— 2 项（可直接修）

河马剧场「我的」页顶部五个图标在 dump 里 `text`/`desc` 全空，但 **rid 齐全**：

| rid | 位置 | 语义（目视确认） |
|---|---|---|
| `item_message` | (138,508) | 消息 |
| `item_wallet` | (357,508) | **福利**（带 12.9元 角标） |
| `item_cash` | (576,508) | **提现** |
| `item_mall` | (795,508) | 我的商城 |
| `item_reservation` | (978,508) | 预约 |

| App | 行为 | 处置 |
|---|---|---|
| 河马剧场 | withdraw | 加 `click_id: item_cash` |
| 河马剧场 | sign | 加 `click_id: item_wallet`（福利页内签到） |

> 教训：`plan_anchor_fixes.py` 只扫 `text`/`desc`，漏掉了 **rid 锚点**。
> 应扩展为 text / desc / rid 三语义扫描。

### D. 入口在「二级菜单之后」（需多级导航）—— 3 项

| App | 行为 | 证据 | 处置 |
|---|---|---|---|
| 抖音 | watch / bonus | 「我的」是**纯个人主页**，无金币/任务入口；dump 里有 `desc='更多'` 的 ≡ 汉堡按钮 @(984,174) | 需 我的 → ≡ → 侧边栏 → 金币；现有 prelude 只能一步，**架构需支持多步** |
| 抖音极速版 | watch | 同上 | 同上 |
| 抖音火山版 | sign | 同上 | 同上 |

### E. 有文本锚点、但关键词表没覆盖 —— 5 项（可直接修）

| App | 行为 | 真实入口 | 依据 |
|---|---|---|---|
| 点淘 | withdraw | **元宝中心** | `screen_after.png` 右上「元宝中心」/ 底部金刚位「元宝中心」；dump 里 `gold_common_image` @(964,1015) |
| 点淘 | watch | **元宝中心** | 同上 |
| 喜番免费短剧 | sign | **福利**（底部 tab，带「赚现金」角标） | 底部 tab x≈0.38 |
| 悟空浏览器 | sign | 缺 `ui_after.xml`，未取到二级页 | 需补校准 |
| 蛋花免费小说 | sign | 待目视 `screen_after.png` | 待定 |

## 结论与优先级

| 处置 | 数量 | 项 |
|---|---|---|
| 可直接修（加 rid 或文本锚点） | 4 | 河马剧场 ×2、点淘 ×2 |
| 先修弹窗再重校 | 2 | 今日看点极速版.withdraw、全民K歌.bonus |
| 数据作废需重校 | 4 | 天天快讯极速版 ×3、悟空浏览器.sign |
| 需多级导航（架构改动） | 3 | 抖音 ×2、抖音极速版.watch、抖音火山版.sign |
| 待定 | 1 | 蛋花免费小说.sign |

**下一步动作**
1. 扩展 `plan_anchor_fixes.py` 扫描 rid 语义 → 自动发现 C 类
2. 补 `dismiss_popups` 的关闭按钮文案（奖励弹窗 / 开屏广告）
3. `calibrate.py` 增加「前台包名校验失败即判失败」
4. 抖音系单独做多步导航方案（`click_point` 链：我的 → ≡ → 金币）
