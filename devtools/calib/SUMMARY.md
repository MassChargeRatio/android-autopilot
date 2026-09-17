# 18 个新 App 校准汇总

> 入口命中率 = 每个行为**首个锚点动作**是否在 App 落地页命中。
> 二级页命中率 = 用 VLM 点进底栏「我的」后再校验同一批入口。
> 后续步骤依赖跳转后的页面，静态 dump 无法校验，需实跑。

| App | 包名 | 首屏入口 | 二级页入口 | 落地页节点 | 前台包名 | 备注 |
|---|---|---|---|---|---|---|
| 今日看点极速版 | `com.jinrikd.news` | 0/3 | 2/3 | 8 | `com.jinrikd.news` |  |
| 全民K歌 | `com.tencent.karaoke` | 0/2 | 1/2 | 218 | `com.tencent.karaoke` |  |
| 天天快讯极速版 | `skysky.cy.kuaixun` | 0/3 | 0/3 | 71 | `com.bbk.launcher2` | ⚠ 前台是 com.bbk.launcher2 |
| 微博移动版 | `com.sina.weibog3` | 0/2 | 1/2 | 160 | `com.sina.weibog3` |  |
| 抖音 | `com.ss.android.ugc.aweme` | 0/2 | 0/2 | 285 | `com.ss.android.ugc.aweme` |  |
| 点淘 | `com.taobao.live` | 0/3 | 0/3 | 286 | `com.taobao.live` |  |
| 今日头条极速版 | `com.ss.android.article.lite` | 1/4 | 2/4 | 124 | `com.ss.android.article.lite` |  |
| 一淘 | `com.taobao.etao` | 1/3 | 2/3 | 234 | `com.taobao.etao` |  |
| 喜番免费短剧 | `com.kwai.theater` | 1/3 | 1/3 | 121 | `com.kwai.theater` |  |
| 悟空浏览器 | `com.cat.readall` | 1/3 | 0/0 | 159 | `com.cat.readall` |  |
| 抖音火山版 | `com.ss.android.ugc.live` | 1/3 | 1/3 | 311 | `com.ss.android.ugc.live` |  |
| 河马剧场 | `com.dz.hmjc` | 1/3 | 1/3 | 139 | `com.dz.hmjc` |  |
| 星图金融 | `com.suning.mobile.epa` | 1/2 | 0/2 | 233 | `com.suning.mobile.epa` |  |
| 抖音极速版 | `com.ss.android.ugc.aweme.lite` | 2/3 | 2/3 | 188 | `com.ss.android.ugc.aweme.lite` |  |
| 梧桐免费小说 | `com.ushaqi.zhuishushenqi.ninenine` | 2/3 | 2/3 | 156 | `com.ushaqi.zhuishushenqi.ninenine` |  |
| 火龙漫剧 | `com.tencent.kairos` | 2/3 | 2/3 | 77 | `com.tencent.kairos` |  |
| 蛋花免费小说 | `com.eggflower.read` | 2/3 | 2/3 | 247 | `com.eggflower.read` |  |
| 红果免费短剧 | `com.phoenix.read` | 3/4 | 3/4 | 220 | `com.phoenix.read` |  |

**首屏入口命中率合计: 18/52 = 35%**  
**二级页入口命中率合计: 22/49 = 45%**

## 需要人工确认

- 天天快讯极速版: 落地时前台为 com.bbk.launcher2（非目标包名，可能被登录页/弹窗/广告占据）

## 各 App 入口明细（首屏 / 二级页）

### 今日看点极速版  (`com.jinrikd.news`)

首屏：
- ❌ `sign` [click_first] candidates=['直接领取', '签到', '立即签到', '每日签到'] 
- ❌ `watch` [click_first] candidates=['看视频', '看视频赚钱', '任务中心', '金币'] 
- ❌ `withdraw` [click_first] candidates=['我的', '我'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [945, 2138]，节点 32）：
- ✅ `sign` [click_first] candidates=['直接领取', '签到', '立即签到', '每日签到'] -> '直接领取' @(540, 1813)
- ✅ `watch` [click_first] candidates=['看视频', '看视频赚钱', '任务中心', '金币'] -> '金币' @(333, 1385)
- ❌ `withdraw` [click_first] candidates=['我的', '我'] 

二级页可用锚点：
  - `直接领取322金币` @[540, 1813] kw=领,领取,金币
  - `+6440金币` @[333, 1385] kw=金币
  - `+100.00元` @[748, 1385] kw=元

### 全民K歌  (`com.tencent.karaoke`)

首屏：
- ❌ `collect` [click_first] candidates=['任务中心', '福利', '每日任务', '做任务'] 
- ❌ `bonus` [click_first] candidates=['红包', '领红包', '抽奖'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [925, 2141]，节点 206）：
- ✅ `collect` [click_first] candidates=['任务中心', '福利', '每日任务', '做任务'] -> '任务中心' @(139, 1174)
- ❌ `bonus` [click_first] candidates=['红包', '领红包', '抽奖'] 

二级页可用锚点：
  - `看视频免费领取100金币` @[357, 1323] kw=领,领取,金币,看视频
  - `0.1元开通` @[869, 911] kw=元
  - `任务中心` @[139, 1174] kw=任务
  - `金币可在用户中心兑换好礼` @[291, 1380] kw=金币
  - `已选中我的` @[924, 2118] kw=我的
  - `我的` @[924, 2168] kw=我的

### 天天快讯极速版  (`skysky.cy.kuaixun`)

首屏：
- ❌ `sign` [click_first] candidates=['立即签到', '签到', '连续签到', '每日签到'] 
- ❌ `watch` [click_first] candidates=['看视频', '看资讯赚钱', '任务中心'] 
- ❌ `withdraw` [click_first] candidates=['我的', '我'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [896, 1684]，节点 72）：
- ❌ `sign` [click_first] candidates=['立即签到', '签到', '连续签到', '每日签到'] 
- ❌ `watch` [click_first] candidates=['看视频', '看资讯赚钱', '任务中心'] 
- ❌ `withdraw` [click_first] candidates=['我的', '我'] 

二级页可用锚点：

### 微博移动版  (`com.sina.weibog3`)

首屏：
- ❌ `collect` [click_first] candidates=['任务中心', '福利', '赚积分', '做任务'] 
- ❌ `bonus` [click_first] candidates=['红包', '现金奖励', '翻牌'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [972, 2129]，节点 179）：
- ✅ `collect` [click_first] candidates=['任务中心', '福利', '赚积分', '做任务'] -> '任务中心' @(213, 1408)
- ❌ `bonus` [click_first] candidates=['红包', '现金奖励', '翻牌'] 

二级页可用锚点：
  - `*&**&*领取1个月VIP` @[236, 523] kw=领,领取
  - `每日签到` @[150, 1606] kw=签到,每日签到
  - `领会员` @[897, 547] kw=领
  - `我的相册` @[158, 1001] kw=我的
  - `我的钱包` @[158, 1226] kw=我的
  - `任务中心` @[213, 1408] kw=任务
  - `今日待领630积分` @[206, 1466] kw=领
  - `参与瓜分10万现金` @[723, 1466] kw=现金
  - `签到` @[432, 1636] kw=签到
  - `点击领10积分` @[201, 1664] kw=领
  - `我的钱包` @[150, 1825] kw=我的
  - `1000.00元` @[157, 1955] kw=元

### 抖音  (`com.ss.android.ugc.aweme`)

首屏：
- ❌ `watch` [click_first] candidates=['任务', '赚积分', '去完成'] 
- ❌ `bonus` [click_first] candidates=['红包', '领红包'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [972, 2199]，节点 262）：
- ❌ `watch` [click_first] candidates=['任务', '赚积分', '去完成'] 
- ❌ `bonus` [click_first] candidates=['红包', '领红包'] 

二级页可用锚点：
  - `我的订单` @[747, 1140] kw=我的

### 点淘  (`com.taobao.live`)

首屏：
- ❌ `collect` [click_first] candidates=['任务中心', '天天领', '福利', '领奖'] 
- ❌ `watch` [click_first] candidates=['看直播', '看视频', '任务', '逛直播间'] 
- ❌ `withdraw` [click_first] candidates=['我的', '我'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [972, 2164]，节点 64）：
- ❌ `collect` [click_first] candidates=['任务中心', '天天领', '福利', '领奖'] 
- ❌ `watch` [click_first] candidates=['看直播', '看视频', '任务', '逛直播间'] 
- ❌ `withdraw` [click_first] candidates=['我的', '我'] 

二级页可用锚点：

### 今日头条极速版  (`com.ss.android.article.lite`)

首屏：
- ❌ `sign` [click_first] candidates=['开宝箱', '签到', '每日签到', '立即签到'] 
- ❌ `watch` [click_first] candidates=['看资讯赚金币', '看视频', '任务中心', '金币'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(972, 2182)
- ❌ `bonus` [click_first] candidates=['限时预约领金币', '预约', '红包'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [970, 2145]，节点 208）：
- ❌ `sign` [click_first] candidates=['开宝箱', '签到', '每日签到', '立即签到'] 
- ✅ `watch` [click_first] candidates=['看资讯赚金币', '看视频', '任务中心', '金币'] -> '金币' @(346, 411)
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(156, 897)
- ❌ `bonus` [click_first] candidates=['限时预约领金币', '预约', '红包'] 

二级页可用锚点：
  - `现金(元)` @[595, 411] kw=元,现金
  - `去提现` @[936, 411] kw=提现,去提现
  - `领现金` @[207, 1182] kw=领,现金
  - `金币` @[346, 411] kw=金币
  - `立领150` @[587, 564] kw=领
  - `现金` @[756, 564] kw=现金
  - `1000元` @[985, 564] kw=元
  - `我的功能` @[156, 897] kw=我的
  - `去完成` @[921, 1861] kw=去完成
  - `>15字且带图和定位，得0.3元` @[337, 1898] kw=元
  - `开宝箱` @[600, 2111] kw=开宝箱
  - `任务` @[540, 2182] kw=任务

### 一淘  (`com.taobao.etao`)

首屏：
- ✅ `sign` [click_first] candidates=['签到', '签到', '每日签到', '立即签到', '天天领'] -> '签到' @(482, 384)
- ❌ `watch` [click_first] candidates=['看视频领金币', '任务中心', '省金币', '今日任务'] 
- ❌ `withdraw` [click_first] candidates=['我的', '我'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [972, 2152]，节点 190）：
- ✅ `sign` [click_first] candidates=['签到', '签到', '每日签到', '立即签到', '天天领'] -> '签到' @(645, 1958)
- ❌ `watch` [click_first] candidates=['看视频领金币', '任务中心', '省金币', '今日任务'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(147, 941)

二级页可用锚点：
  - `什么是签到领钱，如何参加？` @[645, 1958] kw=签到,领
  - `一淘红包` @[668, 445] kw=红包
  - `元` @[190, 523] kw=元
  - `元` @[708, 523] kw=元
  - `赚能量 兑红包` @[786, 607] kw=红包
  - `去福狸中心做任务` @[788, 664] kw=任务
  - `我的订单` @[540, 941] kw=我的
  - `我的订单` @[147, 941] kw=我的
  - `约返0.13元` @[879, 1752] kw=元

### 喜番免费短剧  (`com.kwai.theater`)

首屏：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '看剧赚金币', '去签到'] 
- ❌ `watch` [click_first] candidates=['赚钱', '任务', '看剧赚钱', '福利'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(945, 2145)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [939, 2152]，节点 180）：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '看剧赚金币', '去签到'] 
- ❌ `watch` [click_first] candidates=['赚钱', '任务', '看剧赚钱', '福利'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(970, 2145)

二级页可用锚点：
  - `现金3.47元` @[154, 538] kw=元,现金
  - `提现` @[179, 487] kw=提现
  - `去看剧` @[968, 700] kw=看剧
  - `赚现金` @[496, 2111] kw=现金
  - `我的` @[970, 2145] kw=我的

### 悟空浏览器  (`com.cat.readall`)

首屏：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '阅读赚金币', '立即签到'] 
- ❌ `watch` [click_first] candidates=['任务中心', '看新闻赚钱', '阅读赚钱', '金币'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(960, 2141)

### 抖音火山版  (`com.ss.android.ugc.live`)

首屏：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '开宝箱', '领金币'] 
- ❌ `watch` [click_first] candidates=['看视频赚金币', '任务中心', '金币'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我' @(403, 1964)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [982, 2152]，节点 286）：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '开宝箱', '领金币'] 
- ❌ `watch` [click_first] candidates=['看视频赚金币', '任务中心', '金币'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我' @(540, 854)

二级页可用锚点：
  - `领火苗，按钮` @[972, 324] kw=领
  - `点击赚钱` @[978, 371] kw=赚钱

### 河马剧场  (`com.dz.hmjc`)

首屏：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 
- ❌ `watch` [click_first] candidates=['赚钱', '任务', '看剧赚钱', '福利中心'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(972, 2132)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [966, 2141]，节点 191）：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '看剧得金币', '立即签到'] 
- ❌ `watch` [click_first] candidates=['赚钱', '任务', '看剧赚钱', '福利中心'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(796, 568)

二级页可用锚点：
  - `12.9元` @[409, 458] kw=元
  - `福利` @[358, 568] kw=福利
  - `提现` @[577, 568] kw=提现
  - `我的商城` @[796, 568] kw=我的
  - `2026元津贴活动，限时限量，试试手气！` @[749, 768] kw=元
  - `我的` @[972, 2132] kw=我的

### 星图金融  (`com.suning.mobile.epa`)

首屏：
- ❌ `collect` [click_first] candidates=['人人领', '任务中心', '领好礼', '任务'] 
- ✅ `bonus` [click_first] candidates=['领红包', '红包', '现金红包', '抽奖'] -> '领红包' @(936, 1013)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [961, 2152]，节点 171）：
- ❌ `collect` [click_first] candidates=['人人领', '任务中心', '领好礼', '任务'] 
- ❌ `bonus` [click_first] candidates=['领红包', '红包', '现金红包', '抽奖'] 

二级页可用锚点：
  - `领现金` @[943, 837] kw=领,现金
  - `我的` @[96, 170] kw=我的
  - `我的积分` @[204, 545] kw=我的
  - `早起打卡` @[338, 837] kw=打卡
  - `我的资产` @[168, 982] kw=我的
  - `总资产(元)` @[157, 1081] kw=元
  - `我的` @[972, 2188] kw=我的

### 抖音极速版  (`com.ss.android.ugc.aweme.lite`)

首屏：
- ✅ `sign` [click_first] candidates=['签到', '每日签到', '开宝箱', '领金币'] -> '开宝箱' @(627, 2058)
- ❌ `watch` [click_first] candidates=['刷视频', '看视频赚金币', '任务中心', '金币朋友'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我' @(971, 2141)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [950, 2106]，节点 263）：
- ✅ `sign` [click_first] candidates=['签到', '每日签到', '开宝箱', '领金币'] -> '开宝箱' @(627, 2058)
- ❌ `watch` [click_first] candidates=['刷视频', '看视频赚金币', '任务中心', '金币朋友'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(540, 1140)

二级页可用锚点：
  - `我的订单` @[540, 1140] kw=我的
  - `开宝箱` @[627, 2058] kw=开宝箱

### 梧桐免费小说  (`com.ushaqi.zhuishushenqi.ninenine`)

首屏：
- ✅ `sign` [click_first] candidates=['签到', '每日签到', '看书得金币', '立即签到'] -> '签到' @(604, 2088)
- ❌ `watch` [click_first] candidates=['福利中心', '任务', '看书赚钱', '我的金币'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(972, 2132)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [972, 2124]，节点 92）：
- ✅ `sign` [click_first] candidates=['签到', '每日签到', '看书得金币', '立即签到'] -> '签到' @(604, 2088)
- ❌ `watch` [click_first] candidates=['福利中心', '任务', '看书赚钱', '我的金币'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(196, 567)

二级页可用锚点：
  - `签到领现金` @[604, 2088] kw=签到,领,现金
  - `去提现` @[880, 558] kw=提现,去提现
  - `我的现金：` @[196, 567] kw=现金,我的
  - `元` @[459, 571] kw=元
  - `福利商城` @[888, 834] kw=福利
  - `我的` @[972, 2132] kw=我的

### 火龙漫剧  (`com.tencent.kairos`)

首屏：
- ✅ `sign` [click_first] candidates=['签到', '每日签到', '去签到', '天天有礼'] -> '签到' @(720, 2093)
- ❌ `watch` [click_first] candidates=['看剧赚钱', '任务', '赚钱', '福利中心'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(802, 1166)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [918, 2141]，节点 80）：
- ✅ `sign` [click_first] candidates=['签到', '每日签到', '去签到', '天天有礼'] -> '签到' @(720, 2093)
- ❌ `watch` [click_first] candidates=['看剧赚钱', '任务', '赚钱', '福利中心'] 
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(918, 2130)

二级页可用锚点：
  - `签到` @[720, 2093] kw=签到
  - `福利` @[666, 2130] kw=福利
  - `我的` @[918, 2130] kw=我的

### 蛋花免费小说  (`com.eggflower.read`)

首屏：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '立即签到', '幸运签'] 
- ✅ `watch` [click_first] candidates=['福利', '任务', '看书赚钱', '金币中心'] -> '福利' @(540, 2148)
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(450, 709)

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [939, 2152]，节点 141）：
- ❌ `sign` [click_first] candidates=['签到', '每日签到', '立即签到', '幸运签'] 
- ✅ `watch` [click_first] candidates=['福利', '任务', '看书赚钱', '金币中心'] -> '福利' @(540, 2148)
- ✅ `withdraw` [click_first] candidates=['我的', '我'] -> '我的' @(575, 627)

二级页可用锚点：
  - `领金币` @[606, 2130] kw=领,领金币,金币
  - `我的订单` @[575, 627] kw=我的
  - `我的预约` @[785, 627] kw=我的
  - `我的下载` @[984, 627] kw=我的
  - `金币` @[162, 854] kw=金币
  - `余额(元)` @[565, 854] kw=元
  - `提现` @[930, 855] kw=提现
  - `福利` @[540, 2148] kw=福利
  - `我的` @[953, 2148] kw=我的

### 红果免费短剧  (`com.phoenix.read`)

首屏：
- ✅ `sign` [click_first] candidates=['签到', '去签到', '每日签到'] -> '签到' @(813, 2109)
- ✅ `watch` [click_first] candidates=['赚钱', '看剧赚钱', '看视频得金币'] -> '赚钱' @(747, 2139)
- ✅ `withdraw` [click_first] candidates=['赚钱', '我的', '我'] -> '赚钱' @(747, 2139)
- ❌ `collect` [click_first] candidates=['福利', '任务中心', '开宝箱'] 

二级页（点击『定位屏幕底部导航栏最右侧的『我的』标签中心』-> [950, 2129]，节点 264）：
- ✅ `sign` [click_first] candidates=['签到', '去签到', '每日签到'] -> '签到' @(813, 2109)
- ✅ `watch` [click_first] candidates=['赚钱', '看剧赚钱', '看视频得金币'] -> '赚钱' @(747, 2139)
- ✅ `withdraw` [click_first] candidates=['赚钱', '我的', '我'] -> '赚钱' @(747, 2139)
- ❌ `collect` [click_first] candidates=['福利', '任务中心', '开宝箱'] 

二级页可用锚点：
  - `去领取` @[138, 752] kw=领,领取
  - `领1610金币` @[955, 1400] kw=领,金币
  - `提现` @[846, 693] kw=提现
  - `1.50元` @[857, 752] kw=元
  - `签到` @[813, 2109] kw=签到
  - `赚钱` @[747, 2139] kw=赚钱
  - `我的` @[953, 2139] kw=我的

