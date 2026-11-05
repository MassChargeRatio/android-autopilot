// yaml_editor.js - WebUI YAML 编辑器 + 自然语言生成（AUTOP-WEBUI-YAML-2026-10-22）
// marvis B 卡会话 failed 零产物，由 Host 接手实现。
// 契约：GET /api/yaml/{apps,app,fragment}  POST /api/yaml/{app,generate,apply}
// 写操作必须带 X-Auth-Token（<meta name="console-token">）；前端不做 CRLF/LF 转换。
//
// AUTOP-WEBUI-YAML-2026-11-05-A：并入控制台 shell 第 8 个 tab（#/yaml）。
// 与 app.js 同页共存，故整体包进 IIFE，避免顶层 TOKEN/$/api/state 重名把 app.js 打崩；
// 对外只暴露 window.YamlEditor = { init }，由 app.js 的 hash router 首次进入该视图时懒加载。
'use strict';

(function () {

  const TOKEN = (document.querySelector('meta[name="console-token"]') || {}).content || '';
  const $ = (s, r) => (r || document).querySelector(s);

  const state = { apps: [], current: null, dirty: false, actions: null };

  let booted = false;   // 幂等：router 每次切回该 tab 都会调 init()

  function status(msg, kind) {
    const el = $('#yStatus');
    if (el) { el.textContent = msg; el.className = 'muted' + (kind ? ' ' + kind : ''); }
  }

  function msg(text, kind) {
    const el = $('#yMsg');
    if (!el) return;
    el.textContent = text || '';
    el.className = 'ymsg' + (kind ? ' ' + kind : '');
  }

  async function api(path, opts) {
    const res = await fetch(path, Object.assign({ headers: { 'X-Auth-Token': TOKEN } }, opts || {}));
    let body = null;
    try { body = await res.json(); } catch (e) { body = { ok: false, error: '响应不是 JSON' }; }
    if (!res.ok || body.ok === false) {
      throw new Error((body && body.error) || ('HTTP ' + res.status));
    }
    return body;
  }

  // ---------- App 列表 ----------

  async function loadApps() {
    status('加载 App 列表…');
    const body = await api('/api/yaml/apps');
    state.apps = body.apps || [];
    renderAppList();
    status('共 ' + state.apps.length + ' 个 App');
  }

  function renderAppList() {
    const ul = $('#yAppList');
    const kw = (($('#yAppFilter') || {}).value || '').trim().toLowerCase();
    ul.innerHTML = '';
    state.apps
      .filter(a => !kw || (a.name || '').toLowerCase().includes(kw))
      .forEach(a => {
        const li = document.createElement('li');
        li.textContent = a.name + '（' + (a.behaviors || []).join('/') + '）';
        li.dataset.name = a.name;
        if (state.current === a.name) li.className = 'on';
        li.onclick = () => selectApp(a.name);
        ul.appendChild(li);
      });
  }

  // ---------- 编辑器 ----------

  async function selectApp(name) {
    if (state.dirty && !confirm('当前改动尚未保存，切换 App 会丢失，继续？')) return;
    state.current = name;
    state.dirty = false;
    state.actions = null;
    renderAppList();
    status('载入 ' + name + ' …');
    const body = await api('/api/yaml/app?name=' + encodeURIComponent(name));
    $('#yEditor').value = body.text;
    renderBehaviors(name);
    msg('已载入 ' + body.file + '（eol=' + JSON.stringify(body.eol) + '）', 'dim');
    status('已载入 ' + name);
  }

  function renderBehaviors(name) {
    const app = state.apps.find(a => a.name === name);
    const sel = $('#yBehavior');
    sel.innerHTML = '';
    (app && app.behaviors ? app.behaviors : ['sign']).forEach(b => {
      const opt = document.createElement('option');
      opt.value = b;
      opt.textContent = b;
      sel.appendChild(opt);
    });
  }

  async function saveApp() {
    const name = state.current;
    if (!name) return msg('请先选择 App', 'bad');
    const text = $('#yEditor').value;
    if (state.dirty && !confirm('保存对 ' + name + ' 的修改？')) return;
    status('保存中…');
    try {
      const body = await api('/api/yaml/app', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, text: text }),
      });
      state.dirty = false;
      const extra = body.backup ? '（备份 ' + body.backup.split(/[\\/]/).pop() + '）' : '';
      if (body.action === 'saved') {
        msg('已保存 ' + extra + '\n' + (body.diff || ''), 'ok');
        await loadApps();
      } else if (body.action === 'unchanged') {
        msg('内容无变化，未写盘', 'dim');
      } else if (body.action === 'rolled_back') {
        msg('写后复验失败，已回滚：' + (body.warnings || []).join('; '), 'bad');
      } else {
        msg('action=' + body.action + ' ' + (body.warnings || []).join('; '), 'dim');
      }
      status('保存完成：' + body.action);
    } catch (e) {
      msg('保存失败：' + e.message, 'bad');
      status('保存失败');
    }
  }

  // ---------- 自然语言生成 ----------

  function genPayload() {
    const p = {
      name: state.current,
      behavior: $('#yBehavior').value || 'sign',
      text: ($('#yNlText').value || '').trim(),
    };
    const gv = id => (($(id) || {}).value || '').trim();
    ['tab_text', 'tab_xy', 'hub_text', 'hub_xy', 'anchor_text', 'anchor_xy',
     'ball_xy', 'xy'].forEach(k => {
      const v = gv('#yOpt-' + k);
      if (v) p[k] = v;
    });
    const h5 = $('#yOpt-h5');
    if (h5 && h5.checked) { p.h5 = true; p.h5_offset = gv('#yOpt-h5_offset') || 60; }
    return p;
  }

  async function generate() {
    const p = genPayload();
    if (!p.name) return msg('请先选择 App', 'bad');
    if (!p.text) return msg('请先输入自然语言描述', 'bad');
    status('生成中…');
    try {
      const body = await api('/api/yaml/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(p),
      });
      state.actions = body.actions;
      const warns = (body.warnings || []).map(w => '⚠ ' + w).join('\n');
      $('#yNlOut').textContent = (warns ? warns + '\n\n' : '') + body.fragment;
      $('#yApply').disabled = false;
      msg('已生成 entry=' + body.entry + '，可点「写入配置」', 'ok');
      status('生成完成 entry=' + body.entry);
    } catch (e) {
      msg('生成失败：' + e.message, 'bad');
      status('生成失败');
    }
  }

  async function applyActions(force) {
    if (!state.actions) return msg('请先生成片段', 'bad');
    const p = genPayload();
    p.actions = state.actions;
    p.force = !!force;
    status('写入中…');
    try {
      const body = await api('/api/yaml/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(p),
      });
      const extra = body.backup ? '（备份 ' + body.backup.split(/[\\/]/).pop() + '）' : '';
      if (body.action === 'inserted' || body.action === 'replaced') {
        msg('已' + (body.action === 'inserted' ? '插入' : '替换') + ' ' + p.behavior + ' ' + extra, 'ok');
        await selectApp(p.name);
      } else if (body.action === 'skipped') {
        msg('该行为已存在' + ((body.warnings || []).length ? '：' + body.warnings.join('; ') : '')
          + '\n确认覆盖请勾选「强制替换」后再点写入。', 'dim');
      } else if (body.action === 'rolled_back') {
        msg('写后复验失败，已回滚：' + (body.warnings || []).join('; '), 'bad');
      } else {
        msg('action=' + body.action, 'dim');
      }
      status('写入完成：' + body.action);
    } catch (e) {
      msg('写入失败：' + e.message, 'bad');
      status('写入失败');
    }
  }

  // ---------- 启动 ----------

  function bind() {
    $('#yAppFilter').oninput = renderAppList;
    $('#ySave').onclick = saveApp;
    $('#yReload').onclick = () => state.current && selectApp(state.current);
    $('#yEditor').oninput = () => { state.dirty = true; };
    $('#yGen').onclick = generate;
    $('#yApply').onclick = () => applyActions($('#yForce').checked);
  }

  /* 幂等入口：shell 内由 app.js 的 router 在首次激活 #/yaml 时调用；
     独立页 yaml.html 在 DOMContentLoaded 自行调用。 */
  function init() {
    if (booted) return;
    if (!$('#yAppList') || !$('#yEditor')) return;   // 页面内无编辑器节点，静默跳过
    booted = true;
    bind();
    loadApps().catch(e => {
      status('加载失败：' + e.message, 'bad');
      msg(String(e), 'bad');
    });
  }

  window.YamlEditor = { init: init, isBooted: () => booted };

  // 独立页（<body class="yaml-page">）沿用原有语义自动启动；shell 内交给 router 懒加载。
  document.addEventListener('DOMContentLoaded', () => {
    if (document.body && document.body.classList.contains('yaml-page')) init();
  });

})();
