/* ============================================================
   Android Autopilot 控制台 — 前端逻辑
   纯原生 JS，无框架、无 CDN
   ============================================================ */
'use strict';

const TOKEN = (document.querySelector('meta[name=console-token]') || {}).content || '';
const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

/* ---------------- 基础工具 ---------------- */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
function hhmmss(ts) {
  if (!ts) return '—';
  const d = new Date(ts * 1000);
  return d.toTimeString().slice(0, 8);
}
function toast(msg, kind) {
  const el = $('#toast');
  el.className = 'toast ' + (kind || '');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), 4200);
}

async function api(path, opts) {
  const o = Object.assign({ headers: {} }, opts || {});
  if (o.body !== undefined) {
    o.method = o.method || 'POST';
    o.headers['Content-Type'] = 'application/json';
    o.headers['X-Auth-Token'] = TOKEN;
    o.body = JSON.stringify(o.body);
  }
  const r = await fetch(path, o);
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await r.json() : await r.text();
  if (!r.ok) {
    const msg = (data && data.error) ? data.error : ('HTTP ' + r.status);
    throw new Error(msg);
  }
  return data;
}

/* ============================================================
   全局状态
   ============================================================ */
const S = {
  overview: null,
  plan: {},            // name -> Set(behaviorId)
  open: {},            // name -> bool 展开
  jobs: [],
  activeJob: null,
  logOffset: 0,
  logCarry: '',
  toolJob: null,
  toolOffset: 0,
  toolCarry: '',
  shotTimer: null,
  device: null,
  calib: null,
  pinnedJob: null,     // 用户手动点开的历史任务：不被后台轮询切走
  toolPrefill: null,   // 从校准页带过来的待跑工具参数
};

/* ============================================================
   路由
   ============================================================ */
const VIEWS = ['overview', 'tasks', 'earnings', 'device', 'calib', 'tools', 'config'];

/* 任务/步骤状态 -> 中文。任务与步骤共用同一套状态取值。 */
const STATE_LABEL = { pending: '等待', running: '运行中', done: '成功',
                      failed: '失败', stopped: '已停止' };
function route() {
  const raw = location.hash.replace('#/', '') || 'overview';
  const [v, query] = raw.split('?');
  const view = VIEWS.includes(v) ? v : 'overview';
  // 支持 `#/tasks?q=一淘&beh=sign` 深链：便于把「某个 App 的某类行为」
  // 直接分享/存书签（34 个 App 全展开没法看）。
  const q = new URLSearchParams(query || '');
  if (view === 'tasks') {
    if (q.has('q')) $('#appSearch').value = q.get('q');
    if (q.has('beh')) $('#behFilter').value = q.get('beh');
  }
  VIEWS.forEach(x => $('#view-' + x).classList.toggle('on', x === view));
  $$('#nav a').forEach(a => a.classList.toggle('on', a.dataset.view === view));
  if (view === 'overview') loadOverview();
  if (view === 'tasks') loadTasks();
  if (view === 'earnings') loadEarnings();
  if (view === 'device') { loadDevice().then(takeShot); }
  if (view === 'calib') loadCalib();
  if (view === 'tools') loadTools();
  if (view === 'config') loadConfig();
  if (view !== 'device') stopShot();
}
window.addEventListener('hashchange', route);

/* ============================================================
   总览
   ============================================================ */
async function loadOverview() {
  try {
    const [ov, ops, er] = await Promise.all([
      api('/api/overview'), api('/api/ops?limit=25'), api('/api/earnings?days=7'),
    ]);
    S.overview = ov;
    renderOverviewCards(ov, er);
    renderChart(er.series || []);
    renderOverviewDevice();
    renderOps(ops);
    renderIssues('#ovIssues', ov.issues || [], 6);
    $('#verTxt').textContent = `${ov.app_count} App · ${ov.behavior_count} 行为`;
  } catch (e) { toast('总览加载失败：' + e.message, 'err'); }
}

function renderOverviewCards(ov, er) {
  const errs = (ov.issues || []).filter(i => i.level === 'ERROR').length;
  const warns = (ov.issues || []).filter(i => i.level === 'WARN').length;
  const sum = (er.summary || []);
  const gold = sum.find(x => x.unit && /币|积分|分/.test(x.unit));
  const cash = sum.find(x => x.unit && /元|¥/.test(x.unit));
  const cov = ov.verify_coverage || {};
  const cards = [
    { k: '配置 App', v: ov.app_count, s: `行为 ${ov.behavior_count} 项 · 资金类 ${ov.money_behavior_count} 项`, c: 'acc' },
    { k: '近 7 日收益记录', v: er.total_rows || 0, s: cash ? `现金 ${cash.total.toFixed(2)}${cash.unit}` : '尚无现金入账', c: '' },
    { k: '金币/积分', v: gold ? gold.total.toFixed(0) : '0', s: gold ? `单位「${gold.unit}」· ${gold.count} 笔` : '尚无金币入账', c: '' },
    { k: '配置体检', v: errs ? errs + ' 错误' : '通过', s: warns ? `另有 ${warns} 条警告` : '无警告', c: errs ? 'err' : (warns ? 'warn' : 'ok') },
    { k: '实机可校验行为', v: `${cov.verifiable || 0}/${cov.total || 0}`,
      s: cov.image_only ? `另有 ${cov.image_only} 个仅图像锚点 · 未度量`
        : (cov.unverifiable ? `另有 ${cov.unverifiable} 个无法校验` : '全部可校验'),
      c: cov.unverifiable ? 'warn' : 'ok' },
  ];
  $('#ovCards').innerHTML = cards.map(c => `
    <div class="stat"><div class="k">${esc(c.k)}</div>
      <div class="v ${c.c}">${esc(c.v)}</div>
      <div class="s">${esc(c.s)}</div></div>`).join('');
}

function renderChart(series) {
  const box = $('#ovChart');
  const hasData = series.some(d => d.total > 0);
  if (!series.length || !hasData) {
    box.innerHTML = '<div class="empty">近 7 日暂无收益入账 —— 执行任务并识别到收益后会出现</div>';
    return;
  }
  const W = 640, H = 190, pad = { l: 34, r: 10, t: 12, b: 24 };
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
  const max = Math.max(1, ...series.map(d => d.total));
  const bw = iw / series.length;
  let bars = '', labels = '';
  series.forEach((d, i) => {
    const h = Math.round(ih * (d.total / max));
    const x = pad.l + i * bw + bw * 0.18;
    const y = pad.t + ih - h;
    bars += `<rect class="bar" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(bw * 0.64).toFixed(1)}" height="${Math.max(h, d.total > 0 ? 2 : 0)}" rx="3"><title>${esc(d.date)}：${d.total.toFixed(2)}（${d.count} 笔）</title></rect>`;
    if (d.total > 0) {
      bars += `<text class="vallabel" x="${(x + bw * 0.32).toFixed(1)}" y="${(y - 4).toFixed(1)}" text-anchor="middle">${d.total.toFixed(0)}</text>`;
    }
    labels += `<text class="axlabel" x="${(pad.l + i * bw + bw / 2).toFixed(1)}" y="${H - 7}" text-anchor="middle">${esc(d.date.slice(5))}</text>`;
  });
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <line class="axis" x1="${pad.l}" y1="${pad.t + ih}" x2="${W - pad.r}" y2="${pad.t + ih}"/>
    <text class="axlabel" x="${pad.l - 6}" y="${pad.t + 8}" text-anchor="end">${max.toFixed(0)}</text>
    <text class="axlabel" x="${pad.l - 6}" y="${pad.t + ih}" text-anchor="end">0</text>
    ${bars}${labels}</svg>`;
}

function renderOverviewDevice() {
  const d = S.device || {};
  const box = $('#ovDevice');
  if (!S.device) {
    box.innerHTML = '<div class="empty">正在检测设备…</div>';
    loadDevice(true).then(renderOverviewDevice);
    return;
  }
  box.innerHTML = kv([
    ['状态', d.online ? '<span style="color:var(--ok)">● 在线</span>' : `<span style="color:var(--err)">● 离线</span> ${esc(d.error || '')}`],
    ['设备地址', d.serial || '—'],
    ['型号', d.model || '—'],
    ['分辨率', d.size || '—'],
    ['前台 App', d.foreground || '—'],
    ['adb', d.adb_path || '—'],
  ]);
}

/* 事件原文里混着大量动作 JSON（{"type":"click_first","candidates":[...]}）。
   直接铺在总览上等于把日志塞给用户看 —— 这里翻译成人话，原文留在 title 备查。
   动作类型取自 executor.py 的分发表，别只写日志里恰好出现过的那几个。 */
const ACTION_LABEL = {
  click_text: '点文案', click_desc: '点描述', click_id: '点控件',
  click_first: '点首个命中', click_point: '点坐标', any_of: '分支',
  wait: '等待', think: '停顿', swipe: '滑动', swipe_natural: '拟人滑动',
  scroll_to: '滚动到', back: '返回', home: '回桌面', reward: '读收益',
  ensure: '确保在前台', captcha: '滑块', random: '随机', input: '输入',
};
function humanEvent(ev) {
  const raw = String(ev == null ? '' : ev).trim();
  // 计划 dump 里的动作 JSON 常带列表前缀（`- {...}`）。
  // 不摘掉前缀就会走不进下面的 JSON 分支，界面继续显示裸 JSON（实测踩过）。
  const m = raw.match(/^([-*•]\s+)([\s\S]*)$/);
  const lead = m ? m[1] : '';
  const body = (m ? m[2] : raw).trim();
  if (!body || !/^[[{]/.test(body)) return raw;     // 已经是人话，原样返回
  let o;
  try { o = JSON.parse(body); } catch (e) { return raw; }
  if (Array.isArray(o)) return lead + o.map(humanEvent).join(' → ');
  if (typeof o !== 'object' || o === null) return raw;
  const t = o.type || '';
  const lab = ACTION_LABEL[t] || t || '动作';
  const bits = [];
  if (o.text) bits.push('「' + o.text + '」');
  if (o.desc) bits.push('「' + o.desc + '」');
  if (o.res_id) bits.push(o.res_id);
  if (o.candidates) bits.push('[' + (o.candidates || [])
    .map(x => (x && x.value) || x).join('/') + ']');
  if (o.images) bits.push('图像×' + (o.images || []).length);
  if (o.seconds) bits.push(o.seconds + 's');
  if (o.x != null && o.y != null) bits.push(`(${o.x},${o.y})`);
  if (t === 'any_of' && o.branches) bits.push((o.branches || []).length + ' 路');
  // reward 的 pattern 是提取余额用的正则，正是排查「读不到收益」要看的东西
  if (o.pattern) bits.push('匹配 ' + String(o.pattern).slice(0, 32));
  return lead + lab + (bits.length ? ' ' + bits.join(' ') : '');
}

function renderOps(ops) {
  const rows = (ops && ops.rows) || [];
  $('#ovOpsHint').textContent = ops && ops.stats ? `累计 ${ops.stats.total} 条 · 最近 ${ops.stats.last_ts || '—'}` : '';
  if (!rows.length) { $('#ovOps').innerHTML = '<div class="empty">暂无事件</div>'; return; }
  $('#ovOps').innerHTML = rows.map(r => {
    const raw = String(r.event == null ? '' : r.event);
    const nice = humanEvent(raw);
    return `
    <div class="op ${esc(r.level || 'INFO')}">
      <span class="t">${esc((r.ts || '').slice(5))}</span>
      <span class="a">${esc(r.app || '-')}</span>
      <span class="m" title="${esc(raw)}">${esc(nice)}</span>
    </div>`;
  }).join('');
}

function renderIssues(sel, issues, limit) {
  const box = $(sel);
  const list = limit ? issues.slice(0, limit) : issues;
  if (!list.length) { box.innerHTML = '<div class="empty">未发现问题 ✓</div>'; return; }
  box.innerHTML = list.map(i => `
    <div class="issue"><span class="lv ${esc(i.level)}">${esc(i.level)}</span>
      <span><span class="ap">${esc(i.app)}</span> <span class="ms">${esc(i.msg)}</span></span>
    </div>`).join('') + (limit && issues.length > limit
      ? `<div class="tiny" style="padding:4px 2px">另有 ${issues.length - limit} 条，见「配置」页</div>` : '');
}

function kv(pairs) {
  return '<div class="kv">' + pairs.map(([k, v]) =>
    `<div class="k">${esc(k)}</div><div class="v">${v}</div>`).join('') + '</div>';
}

/* ============================================================
   任务编排
   ============================================================ */
async function loadTasks() {
  if (!S.overview) {
    try { S.overview = await api('/api/overview'); } catch (e) { toast(e.message, 'err'); return; }
  }
  const apps = S.overview.apps || [];
  apps.forEach(a => { if (!S.plan[a.name]) S.plan[a.name] = new Set(a.behaviors.map(b => b.id)); });
  $('#serialInput').placeholder = '设备 serial（留空用 config：' +
    ((S.overview.device || {}).serial || '未配置') + '）';
  renderAppList();
  refreshJobs();
}

function renderAppList() {
  const kw = ($('#appSearch').value || '').trim().toLowerCase();
  const bf = $('#behFilter').value;
  const apps = (S.overview.apps || []).filter(a => {
    if (bf && !a.behaviors.some(b => b.id === bf)) return false;
    if (!kw) return true;
    return (a.name + ' ' + a.package + ' ' + (a.aliases || []).join(' '))
      .toLowerCase().includes(kw);
  });
  const box = $('#appList');
  if (!apps.length) { box.innerHTML = '<div class="empty">没有匹配的 App</div>'; }
  else {
    box.innerHTML = apps.map(a => {
      const sel = S.plan[a.name] || new Set();
      const on = sel.size > 0;
      // 34 个 App 默认全收起；一旦按关键词/行为筛选，命中数已经很少，
      // 再让人逐个点开看徽章就是折磨 —— 筛选态直接展开。
      const open = (S.open[a.name] || kw || bf) ? ' open' : '';
      const behs = a.behaviors.map(b => {
        const c = sel.has(b.id) ? ' on' : '';
        const money = b.money ? ' money' : '';
        const lv = b.levels >= 3 ? `<span class="badge l3">三级</span>` : '';
        const br = b.branches > 1 ? `<span class="badge">${b.branches} 路</span>` : '';
        // 纯图像锚点：能执行，但现有验证器（只认 click_text/id/desc/first）
        // 校验不到，属于「未度量」区间 —— 必须让人看得见。
        const imgOnly = b.vias.length === 1 && b.vias[0] === '图像';
        const im = imgOnly ? `<span class="badge img" title="仅靠图像模板匹配定位，现有实机验证器校验不到（未度量）">图像</span>` : '';
        const tip = `锚点 ${b.anchors.length} 个（${b.vias.join('/')}） · 层级 ${b.levels} · 路径 ${b.branches}`
          + `\n` + b.anchors.map(x => `· ${x.via}: ${x.key || '(空)'}`).join('\n');
        return `<label class="beh${c}${money}" title="${esc(tip)}">
          <input type="checkbox" data-app="${esc(a.name)}" data-beh="${esc(b.id)}" ${sel.has(b.id) ? 'checked' : ''}>
          ${esc(b.trigger)}${b.money ? '（资金）' : ''} ${lv}${br}${im}</label>`;
      }).join('') || '<span class="tiny">（无行为）</span>';
      return `<div class="appblock${open}" data-app="${esc(a.name)}">
        <div class="apphead" data-toggle="${esc(a.name)}">
          <input type="checkbox" data-appall="${esc(a.name)}" ${on ? 'checked' : ''}>
          <span class="appname">${esc(a.name)}</span>
          <span class="pkg">${esc(a.package)}</span>
          <span class="caret">▶</span>
        </div>
        <div class="appbody"><div class="behs">${behs}</div></div>
      </div>`;
    }).join('');
  }
  updatePickHint();
}

function updatePickHint() {
  const picked = Object.entries(S.plan).filter(([, s]) => s.size > 0);
  const behCount = picked.reduce((n, [, s]) => n + s.size, 0);
  const money = picked.filter(([n]) => {
    const a = (S.overview.apps || []).find(x => x.name === n);
    return a && a.behaviors.some(b => b.money && S.plan[n].has(b.id));
  });
  $('#pickHint').textContent = `已选 ${picked.length} App / ${behCount} 行为`
    + (money.length ? ` · 含提现 ${money.length} 个` : '');
  $('#taskCount').textContent = `共 ${(S.overview.apps || []).length} 个 App 可编排`;
}

$('#appList').addEventListener('click', e => {
  const t = e.target.closest('[data-toggle]');
  if (t && !e.target.matches('input')) {
    const n = t.dataset.toggle;
    S.open[n] = !S.open[n];
    t.parentElement.classList.toggle('open', !!S.open[n]);
  }
});
$('#appList').addEventListener('change', e => {
  const el = e.target;
  if (el.dataset.appall !== undefined) {
    const n = el.dataset.appall;
    const a = (S.overview.apps || []).find(x => x.name === n);
    S.plan[n] = el.checked ? new Set(a.behaviors.map(b => b.id)) : new Set();
  } else if (el.dataset.app !== undefined && el.dataset.beh !== undefined) {
    const n = el.dataset.app, b = el.dataset.beh;
    if (!S.plan[n]) S.plan[n] = new Set();
    el.checked ? S.plan[n].add(b) : S.plan[n].delete(b);
  } else return;
  renderAppList();
});
$('#appSearch').addEventListener('input', renderAppList);
$('#behFilter').addEventListener('change', renderAppList);

function setPlan(pred) {
  (S.overview.apps || []).forEach(a => {
    S.plan[a.name] = new Set(a.behaviors.filter(pred).map(b => b.id));
  });
  renderAppList();
}
$('#selAll').onclick  = () => setPlan(() => true);
$('#selNone').onclick = () => setPlan(() => false);
$('#selSign').onclick = () => setPlan(b => b.id === 'sign');
$('#selMain').onclick = () => setPlan(b => ['sign', 'watch', 'bonus'].includes(b.id));

function currentPlan() {
  return Object.entries(S.plan)
    .filter(([, s]) => s.size > 0)
    .map(([name, s]) => ({ name, behaviors: Array.from(s) }));
}

async function startJob(dry) {
  const plan = currentPlan();
  if (!plan.length) { toast('请至少勾选一个 App 的行为', 'err'); return; }
  const money = plan.filter(p => p.behaviors.includes('withdraw')).map(p => p.name);
  if (money.length) {
    // 资金类二次确认（服务端也会强制校验，这里只是前置提示）
    $('#moneyApps').innerHTML = money.map(n => `<li>${esc(n)}</li>`).join('');
    $('#moneyModal').classList.remove('hidden');
    $('#moneyOk').onclick = () => {
      $('#moneyModal').classList.add('hidden');
      doStart(dry, true);
    };
    return;
  }
  doStart(dry, false);
}

async function doStart(dry, confirmMoney) {
  try {
    const r = await api('/api/jobs', {
      body: {
        plan: currentPlan(),
        dry_run: !!dry,
        force: $('#optForce').checked,
        serial: $('#serialInput').value.trim(),
        confirm_money: !!confirmMoney,
      },
    });
    toast((dry ? '预览' : '执行') + '已启动：' + r.job.title, 'ok');
    S.pinnedJob = null;               // 新任务启动 → 解除历史钉住，回到跟随
    await attachJob(r.job.id, true);
  } catch (e) { toast('启动失败：' + e.message, 'err'); }
}

$('#btnRun').onclick = () => startJob(false);
$('#btnPreview').onclick = () => startJob(true);
$('#moneyCancel').onclick = () => $('#moneyModal').classList.add('hidden');
$('#btnStop').onclick = async () => {
  try { await api('/api/jobs/stop', { body: {} }); toast('已请求停止', 'ok'); }
  catch (e) { toast(e.message, 'err'); }
};
$('#clearLog').onclick = () => { resetLog(); };

function resetLog() {
  S.logOffset = 0; S.logCarry = '';
  $('#logBox').textContent = '';
}

/* ---------------- 任务轮询 ---------------- */
async function refreshJobs() {
  try {
    const r = await api('/api/jobs');
    S.jobs = r.jobs || [];
    // 有活动任务就跟随；否则挂载**最近一次**任务 ——
    // 否则刷新页面后进度与日志全空，用户看不到刚才跑的结果。
    // 但用户手动点过历史条目（pinnedJob）时不要把他拽回最新任务，
    // 否则「翻旧日志」会被后台轮询打断。
    const latest = (S.jobs[0] || {}).id || null;
    if (r.active) {
      if (S.activeJob !== r.active) await attachJob(r.active, true);
    } else if (latest && !S.pinnedJob && S.activeJob !== latest) {
      await attachJob(latest, false);
    }
    renderJobHist();
  } catch (e) { /* 静默 */ }
}

/* 任务历史：JobManager 保留最近 30 条，但此前界面只能看「最近一次」，
   跑完一轮再想回头翻上一条的日志就没入口了。 */
function renderJobHist() {
  const jobs = S.jobs || [];
  const box = $('#jobHist');
  if (jobs.length < 2) { box.classList.add('hidden'); return; }
  box.classList.remove('hidden');
  box.innerHTML = '<span class="jhlab tiny">历史</span>' + jobs.slice(0, 12).map(j => {
    const live = j.state === 'pending' || j.state === 'running';
    return `<button class="jchip${j.id === S.activeJob ? ' on' : ''}${live ? ' live' : ''}"
      data-job="${esc(j.id)}" title="${esc(j.title)}">
      <span class="st ${esc(j.state)}">${esc(STATE_LABEL[j.state] || j.state)}</span>
      <span class="jt">${esc(j.title)}</span></button>`;
  }).join('');
}

$('#jobHist').addEventListener('click', async e => {
  // 变量别叫 b：通用护栏把 `b.*` 当成「行为对象」的字段读取，撞名会误报。
  const btn = e.target.closest('[data-job]');
  if (!btn) return;
  S.pinnedJob = btn.dataset.job;    // 钉住，别被后台轮询拽走
  await attachJob(S.pinnedJob, false);
  renderJobHist();
  $('#logBox').scrollTop = 0;
});

async function attachJob(jobId, follow) {
  S.activeJob = jobId;
  S.logOffset = 0;
  S.logCarry = '';
  $('#logBox').textContent = '';
  await pullJob(follow);
}

async function pullJob(follow) {
  if (!S.activeJob) return;
  try {
    const [job, lg] = await Promise.all([
      api('/api/jobs/' + S.activeJob),
      api(`/api/jobs/${S.activeJob}/log?offset=${S.logOffset}`),
    ]);
    renderJob(job);
    if (lg.text) { appendLog(lg.text); }
    S.logOffset = lg.next;
    const running = job.state === 'pending' || job.state === 'running';
    $('#btnStop').disabled = !running;
    if (follow && running) {
      setTimeout(() => pullJob(true), 900);
    } else if (follow) {
      toast('任务结束：' + job.state, job.state === 'done' ? 'ok' : 'err');
      refreshJobs();
    }
  } catch (e) {
    if (follow) setTimeout(() => pullJob(true), 1500);
  }
}

function pollJob() { return pullJob(true); }

function renderJob(job) {
  const p = job.progress || { total: 0, done: 0 };
  const pct = p.total ? Math.round(p.done / p.total * 100) : 0;
  $('#jobBar').classList.remove('hidden');
  $('#pbFill').style.width = pct + '%';
  $('#jobBarTxt').textContent = `${job.title} · ${job.state} · ${p.done}/${p.total}`
    + (p.current ? ` · 正在：${p.current}` : '') + ` · ${job.seconds}s`;
  const label = STATE_LABEL;
  $('#stepList').innerHTML = (job.steps || []).map(s => `
    <div class="step">
      <span class="st ${esc(s.state)}">${esc(label[s.state] || s.state)}</span>
      <span class="nm" title="${esc(s.cmd.join(' '))}">${esc(s.title)}</span>
      <span class="tiny">${s.rc === null || s.rc === undefined ? '' : 'rc=' + s.rc} ${s.seconds ? s.seconds + 's' : ''}</span>
    </div>`).join('');
}

/* ---------------- 日志着色 ---------------- */
const LOG_RE = /^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*\[(\w+)\]\s*\[([^\]]*)\]\s*(.*)$/;
function appendLog(text) {
  const s = S.logCarry + text;
  const lines = s.split('\n');
  S.logCarry = lines.pop();
  const box = $('#logBox');
  const frag = document.createDocumentFragment();
  for (const ln of lines) frag.appendChild(logLine(ln));
  box.appendChild(frag);
  if ($('#autoScroll').checked) box.scrollTop = box.scrollHeight;
}
function logLine(ln) {
  const span = document.createElement('span');
  span.textContent = ln + '\n';
  const m = ln.match(LOG_RE);
  if (m) {
    const lv = m[2].toUpperCase();
    const cls = { INFO: 'l-info', DEBUG: 'l-debug', WARN: 'l-warn', ERROR: 'l-error', GAIN: 'l-gain' }[lv] || 'l-info';
    span.className = cls + (m[3] === 'sys' ? ' l-sys' : '');
  } else if (/^[▶=—]|^\[控制台\]|^\[启动失败\]|^\[读取输出异常\]/.test(ln)) {
    span.className = 'l-hd';
  } else if (ln.startsWith('$ ')) {
    span.className = 'l-cmd';
  }
  return span;
}

/* ============================================================
   收益
   ============================================================ */
async function loadEarnings() {
  try {
    const days = $('#erDays').value;
    const er = await api('/api/earnings?days=' + days + '&limit=1000');
    renderEarnings(er);
  } catch (e) { toast('收益加载失败：' + e.message, 'err'); }
}

function renderEarnings(er) {
  const sum = er.summary || [];
  if (!sum.length) {
    // 空态：一张通栏卡，而不是让单张卡孤零零挤在第一列
    $('#erCards').innerHTML =
      '<div class="stat" style="grid-column:1/-1"><div class="k">收益</div>'
      + '<div class="v">0.00</div><div class="s">所选区间内没有任何收益入账'
      + ' —— 执行任务并识别到收益后会自动记账</div></div>';
  } else {
    $('#erCards').innerHTML = sum
      .map(x => `<div class="stat"><div class="k">${esc(x.unit || '（无单位）')}</div>
        <div class="v acc">${Number(x.total).toFixed(2)}</div>
        <div class="s">今日 ${Number(x.today).toFixed(2)} · 共 ${x.count} 笔</div></div>`).join('');
  }

  const by = er.by_app || [];
  $('#erByAppHint').textContent = `${by.length} 组`;
  $('#erByApp').innerHTML = by.length ? table(
    ['App', '单位', '合计', '笔数'],
    by.map(x => [esc(x.app), esc(x.unit), `<span class="num">${Number(x.total).toFixed(2)}</span>`, `<span class="num">${x.count}</span>`]),
    ['', '', 'num', 'num']) : '<div class="empty">暂无数据</div>';

  const rows = er.rows || [];
  $('#erRowsHint').textContent = `${rows.length} 条（最多 1000）`;
  $('#erRows').innerHTML = rows.length ? table(
    ['时间', 'App', '动作', '数量', '单位', '备注'],
    rows.map(r => [esc(r.ts), esc(r.app), esc(r.action),
      `<span class="num">${Number(r.amount).toFixed(2)}</span>`,
      esc(r.unit), esc(r.detail)]),
    ['', '', '', 'num', '', '']) : '<div class="empty">暂无收益记录 —— 执行任务并识别到收益后会出现</div>';
}

function table(head, rows, cls) {
  return `<table><thead><tr>${head.map((h, i) =>
    `<th class="${cls[i] || ''}">${esc(h)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(r => `<tr>${r.map((c, i) =>
      `<td class="${cls[i] || ''}">${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

$('#erDays').onchange = loadEarnings;
$('#erRefresh').onclick = loadEarnings;

/* ============================================================
   设备
   ============================================================ */
async function loadDevice(quiet) {
  try {
    const d = await api('/api/device?deep=1');
    S.device = d;
    const pill = $('#devPill .dot');
    pill.className = 'dot ' + (d.online ? 'ok' : 'bad');
    $('#devPillTxt').textContent = d.online ? (d.serial || '在线') : '离线';
    if ($('#view-device').classList.contains('on')) {
      $('#devHint').textContent = d.online ? '在线' : '离线';
      $('#devInfo').innerHTML = kv([
        ['状态', d.online ? '<span style="color:var(--ok)">● 在线</span>' : `<span style="color:var(--err)">● 离线</span>`],
        ['设备地址', d.serial || '—'],
        ['型号', d.model || '—'],
        ['分辨率', d.size || '—'],
        ['前台 App', d.foreground || '—'],
        ['前台 Activity', d.foreground_activity || '—'],
        ['adb 路径', d.adb_path || '—'],
        ['错误', d.error ? esc(d.error) : '—'],
      ]);
    }
    return d;
  } catch (e) {
    if (!quiet) toast('设备检测失败：' + e.message, 'err');
  }
}

async function takeShot() {
  const img = $('#shot');
  try {
    const r = await fetch('/api/device/screen.png?t=' + Date.now());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const blob = await r.blob();
    if (img.dataset.url) URL.revokeObjectURL(img.dataset.url);
    const url = URL.createObjectURL(blob);
    img.dataset.url = url;
    img.src = url;
    $('#shotEmpty').style.display = 'none';
    $('#shotHint').textContent = '更新于 ' + new Date().toTimeString().slice(0, 8);
  } catch (e) {
    $('#shotHint').textContent = '截图失败：' + e.message;
  }
}
$('#btnShot').onclick = () => { takeShot(); loadDevice(true); };
$('#btnReconnect').onclick = async () => {
  await loadDevice();
  toast(S.device && S.device.online ? '设备在线：' + S.device.serial : '设备仍离线', S.device && S.device.online ? 'ok' : 'err');
};
function startShot() {
  stopShot();
  const ms = parseInt($('#shotEvery').value, 10);
  S.shotTimer = setInterval(takeShot, ms);
}
function stopShot() { if (S.shotTimer) { clearInterval(S.shotTimer); S.shotTimer = null; } }
$('#autoShot').onchange = e => { e.target.checked ? (takeShot(), startShot()) : stopShot(); };
$('#shotEvery').onchange = () => { if ($('#autoShot').checked) startShot(); };

/* ============================================================
   校准与稳定性
   ------------------------------------------------------------
   数据来自 devtools/calib/STABILITY*.json（stability_run.py 的产物）。
   设计要点：**「未度量」必须与「未命中」分开显示** ——
   命中率的分母只含 verify_live.py 能校验的行为，另有 30 个行为
   （仅图像锚点）从未被度量。两者混在一起会把 70% 误读成覆盖率。
   ============================================================ */
function pct(x) { return (x == null) ? '—' : (x * 100).toFixed(1) + '%'; }

function stamp(ms) {
  if (!ms) return '—';
  const d = new Date(ms * 1000), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const KIND_CLASS = { '稳定': 'ok', '波动': 'warn', '从未命中': 'err', '未度量': 'dim' };

async function loadCalib() {
  try {
    S.calib = await api('/api/calib');
    renderCalib();
  } catch (e) {
    toast('校准报告加载失败：' + e.message, 'err');
  }
}

function renderCalib() {
  // 变量刻意叫 cb 而不是 c：`c` 在总览卡片里已用作「卡片对象」，
  // 混用会让「前端只读接口已提供字段」的护栏无法区分两者。
  const cb = S.calib;
  if (!cb) return;
  if (!cb.available) {
    $('#cbBody').classList.add('hidden');
    $('#cbEmpty').classList.remove('hidden');
    $('#cbEmptyTxt').textContent = cb.hint || '暂无稳定性报告';
    return;
  }
  $('#cbEmpty').classList.add('hidden');
  $('#cbBody').classList.remove('hidden');

  const t = cb.total || {}, n = cb.counts || {};
  const cards = [
    { k: '总命中率', v: pct(t.rate), s: `${t.hits || 0}/${t.valid || 0} 轮次 · ${cb.rounds || 0} 轮`, c: 'ok' },
    { k: '稳定命中', v: n.stable || 0, s: `每轮都中 · 共 ${n.behaviors || 0} 个行为`, c: 'ok' },
    { k: '波动', v: n.flaky || 0, s: '需多路径覆盖（any_of）', c: n.flaky ? 'warn' : '' },
    { k: '从未命中', v: n.never || 0, s: '锚点或路径问题', c: n.never ? 'err' : 'ok' },
    { k: '作废轮次', v: t.void || 0, s: '测量无效 · 不进分母', c: t.void ? 'warn' : '' },
  ];
  $('#cbCards').innerHTML = cards.map(x => `
    <div class="stat"><div class="k">${esc(x.k)}</div>
      <div class="v ${x.c}">${esc(x.v)}</div>
      <div class="s">${esc(x.s)}</div></div>`).join('');

  renderCalibCover(cb);
  renderCalibChain(cb.chain || []);
  renderCalibRows();
}

function renderCalibCover(cb) {
  const cov = cb.verify_coverage || {}, n = cb.counts || {};
  const rows = [
    ['配置里的行为总数', `${cov.total || 0} 个`, ''],
    ['实机可校验（进命中率分母）', `${cov.verifiable || 0} 个`,
      `本页矩阵共 ${n.behaviors || 0} 行 = 覆盖到的行为`],
    ['仅图像锚点 · 从未被度量', `${cov.image_only || 0} 个`,
      'verify_live.py 认不出这类锚点会记「无锚点动作」，stability_run 再把它当作废'],
  ];
  $('#cbCover').innerHTML = kv(rows.map(([k, v, s]) => [k,
    `<b>${esc(v)}</b>${s ? ` <span class="tiny">${esc(s)}</span>` : ''}`]))
    + (cov.image_only ? `<div class="warnline">⚠️ 命中率 <b>${esc(pct((cb.total || {}).rate))}</b>
        只覆盖 ${esc(cov.verifiable || 0)} 个行为；另有 <b>${esc(cov.image_only)}</b> 个行为
        （${esc(((cov.image_only / (cov.total || 1)) * 100).toFixed(0))}%）完全没被度量 ——
        「未度量」不等于「未命中」，别把命中率当成覆盖率。</div>` : '');
}

function renderCalibChain(chain) {
  $('#cbChainHint').textContent = chain.length
    ? `${chain.length} 个版本 · 最后一次 ${stamp(Math.max(...chain.map(x => x.mtime || 0)))}`
    : '';
  if (!chain.length) {
    $('#cbChain').innerHTML = '<div class="empty">暂无版本备份</div>';
    return;
  }
  const best = Math.max(...chain.map(x => x.rate || 0));
  $('#cbChain').innerHTML = chain.map(x => {
    const cls = x.current ? 'cur' : '';
    const top = (x.rate != null && x.rate === best && !x.current) ? ' <span class="tiny">历史最佳</span>' : '';
    return `<div class="cbit ${cls}">
      <div class="cbname">${esc(x.label)}${x.current ? '<span class="tag">当前</span>' : ''}${top}</div>
      <div class="cbnum"><b>${esc(pct(x.rate))}</b>
        <span class="tiny">${x.hits}/${x.valid}</span></div>
      <div class="cbsub tiny">稳定 ${x.stable} · 波动 ${x.flaky} · 从未 ${x.never} · ${esc(stamp(x.mtime))}</div>
    </div>`;
  }).join('');
}

function renderCalibRows() {
  const cb = S.calib;
  if (!cb || !cb.available) return;
  const want = $('#cbFilter').value;
  const all = cb.behaviors || [];
  const rows = want ? all.filter(x => x.kind === want) : all;
  $('#cbRowsHint').textContent =
    `${rows.length}/${all.length} 个行为` + (want ? ` · 筛「${want}」` : '');

  if (!rows.length) {
    $('#cbRows').innerHTML = '<div class="empty">没有符合条件的行为</div>';
    return;
  }
  const head = ['App', '行为', '分类', '命中率', '各轮状态', ''];
  const cls = ['', '', '', 'num', '', 'num'];
  const body = rows.map(x => {
    const rate = x.rate == null ? '<span class="tiny">未度量</span>'
      : `${(x.rate * 100).toFixed(0)}%`;
    const sts = (x.statuses || []).map(s => {
      const k = /命中/.test(s) && !/未命中/.test(s) ? 'ok'
        : (/^数据作废/.test(s) ? 'dim' : 'err');
      return `<span class="st ${k}">${esc(s)}</span>`;
    }).join(' ');
    // 只有「需要修」的行才给诊断入口：稳定命中没什么可查的。
    const act = x.kind === '稳定' ? ''
      : `<button class="btn ghost sm" data-diag="${esc(x.app)}"
           title="带着「${esc(x.app)}」跳到诊断工具的单 App 锚点回归">诊断 →</button>`;
    return [
      esc(x.app), `<code>${esc(x.behavior)}</code>`,
      `<span class="tag ${KIND_CLASS[x.kind] || ''}">${esc(x.kind)}</span>`,
      `<span class="${x.kind === '稳定' ? 'ok' : (x.kind === '从未命中' ? 'err' : '')}">${rate}</span>`,
      sts,
      act,
    ];
  });
  $('#cbRows').innerHTML = table(head, body, cls);
}

/* 校准 → 诊断 的闭环：度量发现问题后，此前必须手抄 App 名再去工具页重打一遍。
   这里只**预填参数并跳转**，不代跑 —— 让用户先看清要跑什么再点「运行」。 */
function gotoDiagnose(appName) {
  S.toolPrefill = { id: 'verify_live', args: `--apps ${appName}` };
  location.hash = '#/tools';
}

$('#cbRows').addEventListener('click', e => {
  const btn = e.target.closest('[data-diag]');
  if (btn) gotoDiagnose(btn.dataset.diag);
});

$('#cbFilter').onchange = renderCalibRows;
$('#cbRefresh').onclick = loadCalib;

/* ============================================================
   工具
   ============================================================ */
/* 从校准页跳进来时，把待跑的参数填进对应工具并高亮，省掉手抄 App 名。 */
function applyToolPrefill() {
  const pf = S.toolPrefill;
  if (!pf) return;
  S.toolPrefill = null;
  const inp = $(`[data-arg="${pf.id}"]`);
  if (!inp) return;
  inp.value = pf.args;
  const card = inp.closest('.tool');
  if (card) {
    card.classList.add('flash');
    setTimeout(() => card.classList.remove('flash'), 1600);
    card.scrollIntoView({ block: 'center' });
  }
  toast('已填入参数：' + pf.args + ' —— 确认后点「运行」', 'ok');
}

async function loadTools() {
  try {
    const r = await api('/api/tools');
    $('#toolList').innerHTML = (r.tools || []).map(t => `
      <div class="tool">
        <h4>${esc(t.title)}</h4>
        <p>${esc(t.desc)}</p>
        <div class="row">
          <input class="inp" data-arg="${esc(t.id)}" placeholder="${esc(t.argHint || '无需参数')}">
          <button class="btn" data-run="${esc(t.id)}">运行</button>
        </div>
      </div>`).join('');
    applyToolPrefill();
  } catch (e) { toast(e.message, 'err'); }
}

$('#toolList').addEventListener('click', async e => {
  const btn = e.target.closest('[data-run]');
  if (!btn) return;
  const id = btn.dataset.run;
  const inp = $(`[data-arg="${id}"]`);
  const args = (inp.value || '').trim() ? inp.value.trim().split(/\s+/) : [];
  try {
    const r = await api('/api/tools/' + id + '/run', { body: { args } });
    S.toolJob = r.job.id; S.toolOffset = 0; S.toolCarry = '';
    $('#toolLog').textContent = '';
    $('#toolStop').disabled = false;
    toast('已启动：' + r.job.title, 'ok');
    pollTool();
  } catch (err) { toast('启动失败：' + err.message, 'err'); }
});
$('#toolStop').onclick = async () => {
  if (!S.toolJob) return;
  try { await api(`/api/jobs/${S.toolJob}/stop`, { body: {} }); } catch (e) { /* ignore */ }
};

async function pollTool() {
  if (!S.toolJob) return;
  try {
    const [job, lg] = await Promise.all([
      api('/api/jobs/' + S.toolJob),
      api(`/api/jobs/${S.toolJob}/log?offset=${S.toolOffset}`),
    ]);
    if (lg.text) { appendToolLog(lg.text); }
    S.toolOffset = lg.next;
    const p = job.progress || { total: 0, done: 0 };
    $('#toolBar').classList.remove('hidden');
    $('#toolPbFill').style.width = (p.total ? Math.round(p.done / p.total * 100) : 0) + '%';
    $('#toolBarTxt').textContent = `${job.title} · ${job.state} · ${job.seconds}s`;
    if (job.state === 'pending' || job.state === 'running') setTimeout(pollTool, 900);
    else { $('#toolStop').disabled = true; toast('工具结束：' + job.state, job.state === 'done' ? 'ok' : 'err'); }
  } catch (e) { setTimeout(pollTool, 1500); }
}
function appendToolLog(text) {
  const s = S.toolCarry + text;
  const lines = s.split('\n');
  S.toolCarry = lines.pop();
  const box = $('#toolLog');
  const frag = document.createDocumentFragment();
  for (const ln of lines) frag.appendChild(logLine(ln));
  box.appendChild(frag);
  box.scrollTop = box.scrollHeight;
}

/* ============================================================
   配置
   ============================================================ */
async function loadConfig() {
  try {
    const ov = await api('/api/overview');
    S.overview = ov;
    const errs = (ov.issues || []).filter(i => i.level === 'ERROR').length;
    const warns = (ov.issues || []).filter(i => i.level === 'WARN').length;
    $('#cfgCards').innerHTML = [
      { k: 'App', v: ov.app_count, s: `包名 ${ov.apps.filter(a => a.package).length} 个已填` },
      { k: '行为', v: ov.behavior_count, s: `资金类 ${ov.money_behavior_count} 项` },
      { k: '配置错误', v: errs, s: errs ? '需修复' : '无', c: errs ? 'err' : 'ok' },
      { k: '配置警告', v: warns, s: warns ? '建议检查' : '无', c: warns ? 'warn' : 'ok' },
    ].map(c => `<div class="stat"><div class="k">${esc(c.k)}</div>
      <div class="v ${c.c || ''}">${esc(c.v)}</div><div class="s">${esc(c.s)}</div></div>`).join('');

    $('#cfgIssuesHint').textContent = `共 ${(ov.issues || []).length} 条`;
    renderIssues('#cfgIssues', ov.issues || [], 0);

    $('#cfgAppsHint').textContent = `设备 ${(ov.device || {}).serial || '未配置'} · VLM ${ov.vision_enabled ? '开' : '关'} · 滑块 ${ov.captcha_enabled ? '开' : '关'}`;
    $('#cfgApps').innerHTML = (ov.apps || []).map(a => `
      <div class="cfgapp">
        <div class="h"><b>${esc(a.name)}</b><span class="pkg">${esc(a.package)}</span>
          ${(a.aliases || []).length ? `<span class="tiny">别名 ${esc(a.aliases.join('、'))}</span>` : ''}</div>
        <div class="anchors">${a.behaviors.map(b => `
          <div class="anch">▸ <b>${esc(b.id)}</b>（${esc(b.trigger)}）
            · 层级 ${b.levels} · 路径 ${b.branches}${b.has_prelude ? ' · 含导航前置步' : ''}
            ${b.money ? ' · <span style="color:#ffb3ae">资金类</span>' : ''}
            <br>${b.anchors.map(x => '&nbsp;&nbsp;&nbsp;↳ [' + esc(x.via) + '] '
              + esc(x.key || '(未配置定位依据)')
              + (x.candidates.length > 1 ? ' <span class="tiny">候选 ' + esc(x.candidates.join(' / ')) + '</span>' : '')
              + (x.images ? ' <span class="tiny">参考图 ' + x.images + ' 张</span>' : '')
            ).join('<br>')}
          </div>`).join('') || '<div class="tiny">（无行为）</div>'}</div>
      </div>`).join('');
  } catch (e) { toast('配置加载失败：' + e.message, 'err'); }
}

$('#cfgReload').onclick = async () => {
  try { await api('/api/overview/reload', { body: {} }); toast('配置已重新载入', 'ok'); loadConfig(); }
  catch (e) { toast(e.message, 'err'); }
};
$('#cfgOpen').onclick = async () => {
  try { await api('/api/config/open', { body: {} }); toast('已用系统默认程序打开', 'ok'); }
  catch (e) { toast('打开失败：' + e.message, 'err'); }
};

/* ============================================================
   启动
   ============================================================ */
$('#ovRefresh').onclick = loadOverview;
loadDevice(true);
route();
refreshJobs();
setInterval(() => { if ($('#view-overview').classList.contains('on')) loadOverview(); }, 30000);
