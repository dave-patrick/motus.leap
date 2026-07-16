/* ai-hub.js — motus.leap AI Management UI (P1+P2+P3 wired to live backend).
 * CSP-safe: no inline handlers, all binding via addEventListener.
 * Security: DOMPurify on every provider/rule/chat/job-derived string. */
(function () {
  'use strict';

  const APP = {
    base: '',
    token: null,
  };

  // ---- helpers -------------------------------------------------------------
  function getToken() {
    const m = document.cookie.match(/(?:^|;\s*)token=([^;]+)/);
    if (m) return m[1];
    return localStorage.getItem('token') || null;
  }
  function sanitize(v) {
    if (v === null || v === undefined) return '';
    return DOMPurify.sanitize(String(v), { USE_PROFILES: { html: true } });
  }
  function esc(v) {
    return sanitize(v);
  }
  async function api(path, opts) {
    opts = opts || {};
    const headers = Object.assign(
      { 'Content-Type': 'application/json', Origin: window.location.origin },
      opts.headers || {}
    );
    const t = getToken();
    if (t) headers['Authorization'] = 'Bearer ' + t;
    let resp;
    try {
      resp = await fetch(APP.base + path, { method: opts.method || 'GET', headers, body: opts.body });
    } catch (e) {
      throw new Error('Network error — is the server up?');
    }
    let data = null;
    try { data = await resp.json(); } catch (_) {}
    if (!resp.ok) {
      const msg = (data && (data.detail || data.error)) || ('HTTP ' + resp.status);
      const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
      err.status = resp.status;
      err.data = data;
      throw err;
    }
    return data;
  }
  function $(sel) { return document.querySelector(sel); }
  function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

  function toast(msg, kind) {
    kind = kind || 'info';
    const color = kind === 'error' ? '#dc2626' : (kind === 'success' ? '#16a34a' : '#2f8fc9');
    const el = document.createElement('div');
    el.style.cssText = 'position:fixed;top:14px;right:14px;z-index:9999;background:#1a1d24;border:1px solid ' +
      color + ';color:' + color + ';padding:10px 14px;border-radius:10px;font-size:12px;max-width:320px;box-shadow:0 4px 10px rgba(0,0,0,.4)';
    el.innerHTML = sanitize(msg);
    document.body.appendChild(el);
    setTimeout(() => { el.remove(); }, 3500);
  }

  // ---- sub-nav routing -----------------------------------------------------
  const PANELS = ['hub', 'providers', 'rules', 'jobs'];
  function showPanel(name) {
    PANELS.forEach(p => {
      const panel = document.getElementById('panel-' + p);
      if (panel) panel.classList.toggle('hidden', p !== name);
    });
    $all('.ai-sub').forEach(a => a.classList.toggle('active', a.getAttribute('data-ai') === name));
    $all('.ai-tab').forEach(b => b.classList.toggle('bg-[#2a2f3a]', b.getAttribute('data-ai') === name));
    $all('.ai-tab').forEach(b => b.classList.toggle('text-white', b.getAttribute('data-ai') === name));
    // refresh data for the panel
    if (name === 'hub') loadHub();
    else if (name === 'providers') loadProviders();
    else if (name === 'rules') loadRules();
    else if (name === 'jobs') { loadJobs(); /* do not auto-open form */ }
  }

  // ---- HUB -----------------------------------------------------------------
  async function loadHub() {
    const stats = $('#hub-stats');
    const provBox = $('#hub-providers');
    const jobsBox = $('#hub-jobs');
    stats.innerHTML = '<div class="bento-card p-4 text-xs text-gray-500">Loading…</div>';
    try {
      const [provResp, rulesResp, jobsResp] = await Promise.all([
        api('/api/ai/providers'),
        api('/api/ai/rules').catch(() => ({ rules: [] })),
        api('/api/ai/jobs').catch(() => ({ jobs: [] })),
      ]);
      const providers = provResp.providers || [];
      const rules = rulesResp.rules || [];
      const jobs = jobsResp.jobs || [];
      const connected = providers.filter(p => p.status === 'active' || p.status === 'enabled' || p.is_active).length;
      const activeModels = providers.reduce((s, p) => s + (p.active_model_count || 0), 0);
      const enabledRules = rules.filter(r => r.enabled).length;
      const nextJob = jobs.filter(j => j.enabled && j.next_run).sort((a, b) => a.next_run.localeCompare(b.next_run))[0];
      stats.innerHTML =
        statCard('Providers', connected + ' / ' + providers.length, 'info') +
        statCard('Active models', String(activeModels), 'info') +
        statCard('Rules', rules.length + ' (' + enabledRules + ' on)', 'info') +
        statCard('Scheduled jobs', (jobs || []).length + (nextJob ? ' · next ' + shortTime(nextJob.next_run) : ''), 'info');

      if (!providers.length) {
        provBox.innerHTML = emptyState('No providers connected', 'Add one from the Providers tab.');
      } else {
        provBox.innerHTML = providers.map(p => {
          const status = (p.status === 'active' || p.status === 'enabled' || p.is_active);
          return '<div class="flex items-center justify-between bento-card !bg-transparent border border-[#2a2f3a] px-3 py-2">' +
            '<div class="min-w-0"><div class="text-[13px] text-gray-200 truncate">' + esc(p.name) + '</div>' +
            '<div class="text-[10px] text-gray-500 font-mono truncate">' + esc(p.base_url || p.type) + '</div></div>' +
            '<span class="pill ' + (status ? 'pill-success' : 'pill-error') + '">' + (status ? 'Connected' : esc(p.status || 'error')) + '</span>' +
            '</div>';
        }).join('');
      }

      if (!jobs || !jobs.length) {
        jobsBox.innerHTML = emptyState('No scheduled jobs yet', 'Create one from the Scheduled Jobs tab.');
      } else {
        jobsBox.innerHTML = jobs.slice(0, 4).map(j => {
          return '<div class="flex items-center justify-between bento-card !bg-transparent border border-[#2a2f3a] px-3 py-2">' +
            '<div class="min-w-0"><div class="text-[13px] text-gray-200 truncate">' + esc(j.name) + '</div>' +
            '<div class="text-[10px] text-gray-500 font-mono">' + esc(j.cron) + (j.enabled ? '' : ' · paused') + '</div></div>' +
            '<span class="text-[10px] text-gray-400">' + (j.next_run ? 'next ' + shortTime(j.next_run) : '—') + '</span>' +
            '</div>';
        }).join('');
      }
    } catch (e) {
      stats.innerHTML = '<div class="bento-card p-4 text-xs text-[#dc2626]">' + sanitize(e.message) + '</div>';
    }
  }
  function statCard(label, val, kind) {
    return '<div class="bento-card p-4"><div class="text-[10px] uppercase tracking-wide text-gray-500">' + esc(label) + '</div>' +
      '<div class="text-lg font-semibold text-white mt-1">' + esc(val) + '</div></div>';
  }
  function emptyState(title, sub) {
    return '<div class="text-center text-gray-500 text-xs py-6"><i class="fas fa-inbox block text-lg mb-1"></i>' +
      esc(title) + '<div class="text-gray-600 mt-1">' + esc(sub) + '</div></div>';
  }
  function shortTime(iso) {
    try { const d = new Date(iso); return d.toLocaleString(); } catch (_) { return iso; }
  }

  // ---- PROVIDERS -----------------------------------------------------------
  async function loadProviders() {
    const box = $('#prov-list');
    box.innerHTML = '<div class="bento-card p-4 text-xs text-gray-500">Loading…</div>';
    try {
      const { providers } = await api('/api/ai/providers');
      if (!providers.length) {
        box.innerHTML = '<div class="bento-card p-4">' + emptyState('No providers connected', 'Click “Add Provider” to connect OpenAI, Anthropic, Groq, Google or a custom endpoint.') + '</div>';
        return;
      }
      // Pull the full per-provider model list (discovered + active + default) from
      // the models endpoint — this is the source of truth, not the aggregate
      // /api/ai/models which only returns already-selected models.
      const modelInfos = await Promise.all(providers.map(p =>
        api('/api/ai/providers/' + p.id + '/models').then(d => ({ id: p.id, data: d })).catch(() => ({ id: p.id, data: { models: [], active: [], default: null } }))
      ));
      const modelsByProv = {};
      modelInfos.forEach(m => { modelsByProv[m.id] = m.data; });

      box.innerHTML = providers.map(p => {
        const ok = (p.status === 'active' || p.status === 'enabled' || p.is_active);
        const grp = modelsByProv[p.id] || {};
        const mlist = grp.models || [];
        const activeSet = new Set((grp.active && grp.active.length) ? grp.active : []);
        const def = grp.default || null;
        let modelsHtml = '<div class="text-[11px] text-gray-500 mt-2">No models discovered.</div>';
        if (mlist.length) {
          modelsHtml = '<div class="mt-2 space-y-1 border-t border-[#2a2f3a] pt-2">' +
            mlist.map(m => {
              const id = m.id;
              const checked = activeSet.has(id);
              return '<div class="flex items-center gap-2 text-[11px] ' + (checked ? 'text-gray-200' : 'text-gray-500') + '">' +
                '<i class="fas ' + (checked ? 'fa-check-square text-[#2f8fc9]' : 'fa-square text-gray-600') + '"></i>' +
                '<span class="font-mono truncate">' + esc(m.name || id) + '</span>' +
                (def === id ? ' <span class="text-[9px] text-[#16a34a]">default</span>' : '') +
                '</div>';
            }).join('') +
            '</div>';
        }
        return '<div class="bento-card p-4 flex flex-col gap-3">' +
          '<div class="flex items-center justify-between"><div class="min-w-0"><div class="text-sm font-medium text-gray-100 truncate">' + esc(p.name) + '</div>' +
          '<div class="text-[10px] text-gray-500 font-mono truncate">' + esc(p.base_url || p.type) + '</div></div>' +
          '<span class="pill ' + (ok ? 'pill-success' : 'pill-error') + '">' + (ok ? 'Connected' : esc(p.status || 'error')) + '</span></div>' +
          '<div class="flex items-center justify-between text-[11px] text-gray-400"><span>' + (p.active_model_count || activeSet.size) + ' / ' + (p.discovered_model_count || mlist.length) + ' models active</span>' +
          '<div class="flex gap-3">' +
          '<button class="prov-rescan text-[#2f8fc9] hover:underline" data-id="' + esc(p.id) + '"><i class="fas fa-sync"></i> Rescan</button>' +
          '<button class="prov-manage text-[#2f8fc9] hover:underline" data-id="' + esc(p.id) + '">Manage</button>' +
          '</div></div>' +
          modelsHtml +
          '<button class="prov-del bg-[#20242c] border border-[#2a2f3a] text-[#dc2626] text-xs px-3 py-2 rounded-lg" data-id="' + esc(p.id) + '">Disconnect</button>' +
          '</div>';
      }).join('');
      $all('.prov-del').forEach(b => b.addEventListener('click', () => deleteProvider(b.getAttribute('data-id'))));
      $all('.prov-manage').forEach(b => b.addEventListener('click', () => { switchTab('models'); loadModels(b.getAttribute('data-id')); }));
      $all('.prov-rescan').forEach(b => b.addEventListener('click', () => rescanProvider(b.getAttribute('data-id'))));
    } catch (e) {
      box.innerHTML = '<div class="bento-card p-4 text-xs text-[#dc2626]">' + sanitize(e.message) + '</div>';
    }
  }
  async function rescanProvider(id) {
    try {
      await api('/api/ai/providers/' + id + '/models?refresh=1', { method: 'GET' });
      toast('Models rescanned', 'success');
      loadProviders(); loadHub();
    } catch (e) { toast(e.message, 'error'); }
  }
  async function deleteProvider(id) {
    if (!confirm('Disconnect this provider? Rules using its models will be disabled.')) return;
    try {
      await api('/api/ai/providers/' + id, { method: 'DELETE' });
      toast('Provider disconnected', 'success');
      loadProviders(); loadHub();
    } catch (e) { toast(e.message, 'error'); }
  }

  // Add provider modal
  let pendingProviderId = null;
  function openProvModal() {
    pendingProviderId = null;
    $('#prov-step1').classList.remove('hidden');
    $('#prov-step2').classList.add('hidden');
    $('#prov-step2-dot').className = 'w-2 h-2 rounded-full bg-[#374151]';
    $('#prov-step1-dot').className = 'w-2 h-2 rounded-full bg-[#2f8fc9]';
    $('#prov-name').value = ''; $('#prov-key').value = ''; $('#prov-base').value = '';
    $('#prov-type').value = 'openai';
    $('#prov-step1-msg').textContent = ''; $('#prov-step2-msg').textContent = '';
    updateProvType(); // apply initial type state
    const m = $('#prov-modal'); m.classList.remove('hidden'); m.classList.add('flex');
  }
  function closeProvModal() { const m = $('#prov-modal'); m.classList.add('hidden'); m.classList.remove('flex'); }
  async function connectProvider() {
    const name = $('#prov-name').value.trim();
    const type = $('#prov-type').value;
    const apiKey = $('#prov-key').value.trim();
    const baseUrl = $('#prov-base').value.trim();
    if (!name) { $('#prov-step1-msg').textContent = 'Name is required.'; return; }
    if (!apiKey && type !== 'custom') { $('#prov-step1-msg').textContent = 'API key required for this provider type.'; return; }
    if (type === 'custom' && !baseUrl) { $('#prov-step1-msg').textContent = 'Base URL required for custom providers.'; return; }
    const btn = $('#prov-connect'); const old = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner spinner"></i> Connecting…';
    try {
      const res = await api('/api/ai/providers', {
        method: 'POST',
        body: JSON.stringify({ name, type, api_key: apiKey, base_url: baseUrl || undefined }),
      });
      pendingProviderId = res.id;
      // Step 2: discover + select
      $('#prov-step1').classList.add('hidden');
      $('#prov-step2').classList.remove('hidden');
      $('#prov-step2-dot').className = 'w-2 h-2 rounded-full bg-[#2f8fc9]';
      await loadModelChecklist(pendingProviderId);
    } catch (e) {
      $('#prov-step1-msg').textContent = e.message;
    } finally { btn.disabled = false; btn.innerHTML = old; }
  }
  async function loadModelChecklist(pid) {
    const box = $('#prov-models-checklist');
    box.innerHTML = '<div class="text-xs text-gray-500">Discovering models…</div>';
    try {
      const data = await api('/api/ai/providers/' + pid + '/models');
      const models = (data.models || []);
      if (!models.length) {
        // No models discovered (e.g. provider has no /v1/models, or empty).
        // Offer manual entry so the user is never stuck (they can paste a model id).
        const hint = (data.error && data.error.indexOf('Anthropic') >= 0) ? 'a curated catalog is used' : 'enter a model id manually';
        const manualMsg = sanitize((data.error || 'No models discovered') + ' — ' + hint + '.');
        box.innerHTML =
          '<div class="text-xs text-gray-500 mb-2">' + manualMsg + '</div>' +
          '<input id="prov-manual-model" type="text" placeholder="e.g. grok-4-latest" class="w-full bg-[#20242c] border border-[#2a2f3a] rounded-lg px-3 py-2 text-sm text-gray-200" />' +
          '<div class="text-[10px] text-gray-500 mt-1">Separate multiple model ids with commas if needed.</div>';
        return;
      }
      // Pre-check models that were previously selected (active) and mark the
      // default. Fall back to first model checked when nothing is saved yet.
      const active = (data.active && data.active.length) ? data.active : null;
      const isDefault = (id) => data.default && (data.default === id || (active && active[0] === id));
      box.innerHTML = models.map((m) => {
        const id = m.id;
        const checked = active ? active.includes(id) : false;
        const def = isDefault(id);
        return '<label class="flex items-center gap-2 text-xs text-gray-300 py-1 cursor-pointer">' +
          '<input type="checkbox" class="prov-model-chk accent-[#2f8fc9]" value="' + esc(id) + '"' + (checked ? ' checked' : '') + '>' +
          '<span class="font-mono">' + esc(m.name || id) + '</span>' +
          (def ? ' <span class="text-[9px] text-[#2f8fc9]">default</span>' : '') + '</label>';
      }).join('');
    } catch (e) {
      box.innerHTML = '<div class="text-xs text-[#dc2626]">' + sanitize(e.message) + '</div>';
    }
  }
  async function saveProviderModels() {
    let chks = $all('.prov-model-chk:checked').map(c => c.value);
    const manual = $('#prov-manual-model');
    if (!chks.length && manual && manual.value.trim()) {
      chks = manual.value.split(',').map(s => s.trim()).filter(Boolean);
    }
    if (!chks.length) { $('#prov-step2-msg').textContent = 'Select or enter at least one model.'; return; }
    try {
      await api('/api/ai/providers/' + pendingProviderId + '/models', {
        method: 'PUT',
        body: JSON.stringify({ active: chks, default: chks[0] }),
      });
      toast('Provider connected', 'success');
      closeProvModal(); loadProviders(); loadHub();
    } catch (e) { $('#prov-step2-msg').textContent = e.message; }
  }

  // ---- MODELS --------------------------------------------------------------
  async function loadModels(highlightId) {
    const box = $('#models-list');
    box.innerHTML = '<div class="bento-card p-4 text-xs text-gray-500">Loading…</div>';
    try {
      const [provResp, all] = await Promise.all([api('/api/ai/providers'), api('/api/ai/models').catch(() => null)]);
      const providers = provResp.providers || [];
      if (!providers.length) {
        box.innerHTML = '<div class="bento-card p-4">' + emptyState('No providers', 'Connect a provider first.') + '</div>';
        return;
      }
      const grouped = (all && all.providers) || providers.map(p => ({ id: p.id, name: p.name, models: [] }));
      box.innerHTML = grouped.map(g => {
        return '<div class="bento-card p-4"><div class="flex items-center justify-between mb-2">' +
          '<div class="text-sm text-gray-100">' + esc(g.name) + '</div>' +
          '<button class="models-refresh text-[11px] text-[#2f8fc9] hover:underline" data-id="' + esc(g.id) + '">Refresh</button></div>' +
          '<div class="models-box space-y-1" data-id="' + esc(g.id) + '"><div class="text-xs text-gray-500">Loading models…</div></div></div>';
      }).join('');
      for (const g of grouped) {
        await renderProviderModels(g.id);
      }
      $all('.models-refresh').forEach(b => b.addEventListener('click', () => renderProviderModels(b.getAttribute('data-id'), true)));
      if (highlightId) {
        const el = document.querySelector('.models-box[data-id="' + CSS.escape(highlightId) + '"]');
        if (el) el.scrollIntoView({ block: 'center' });
      }
    } catch (e) {
      box.innerHTML = '<div class="bento-card p-4 text-xs text-[#dc2626]">' + sanitize(e.message) + '</div>';
    }
  }
  async function renderProviderModels(pid, refresh) {
    const box = document.querySelector('.models-box[data-id="' + (pid ? CSS.escape(pid) : '') + '"]');
    if (!box) return;
    try {
      const data = await api('/api/ai/providers/' + pid + '/models' + (refresh ? '?refresh=1' : ''));
      const models = data.models || [];
      // Backend GET returns {models, manual_entry} without active/default, so
      // derive a sensible default when absent: first model checked + default.
      const active = new Set((data.active && data.active.length ? data.active : [models[0] && (models[0].id || models[0])]).map(a => a.id || a));
      const def = data.default || (models.find(m => active.has(m.id)) || models[0] || {}).id;
      if (!models.length) { box.innerHTML = '<div class="text-xs text-gray-500">No models discovered for this provider.</div>'; return; }
      box.innerHTML = models.map(m =>
        '<div class="flex items-center justify-between text-xs py-1">' +
        '<label class="flex items-center gap-2 text-gray-300 cursor-pointer min-w-0">' +
        '<input type="checkbox" class="model-chk accent-[#2f8fc9]" data-pid="' + esc(pid) + '" value="' + esc(m.id) + '"' + (active.has(m.id) ? ' checked' : '') + '>' +
        '<span class="font-mono truncate">' + esc(m.name || m.id) + '</span></label>' +
        '<button class="model-default text-[11px] ' + (def === m.id ? 'text-[#16a34a] font-semibold' : 'text-[#2f8fc9] hover:underline') + '" data-pid="' + esc(pid) + '" data-mid="' + esc(m.id) + '">' + (def === m.id ? 'DEFAULT' : 'Set default') + '</button>' +
        '</div>'
      ).join('');
      $all('.model-chk').forEach(c => c.addEventListener('change', () => persistModels(c.getAttribute('data-pid'))));
      $all('.model-default').forEach(b => b.addEventListener('click', () => setDefault(b.getAttribute('data-pid'), b.getAttribute('data-mid'))));
    } catch (e) { box.innerHTML = '<div class="text-xs text-[#dc2626]">' + sanitize(e.message) + '</div>'; }
  }
  function collectModels(pid) {
    const chks = $all('.model-chk[data-pid="' + CSS.escape(pid) + '"]:checked');
    const active = chks.map(c => c.value);
    const defBtn = document.querySelector('.model-default[data-pid="' + CSS.escape(pid) + '"][data-mid]');
    let def = defBtn ? defBtn.getAttribute('data-mid') : (active[0] || '');
    return { active, default: def };
  }
  async function persistModels(pid) {
    const { active, default: def } = collectModels(pid);
    try {
      await api('/api/ai/providers/' + pid + '/models', { method: 'PUT', body: JSON.stringify({ active, default: def }) });
      loadHub();
    } catch (e) { toast(e.message, 'error'); }
  }
  async function setDefault(pid, mid) {
    const { active } = collectModels(pid);
    const arr = active.includes(mid) ? active : [mid, ...active];
    try {
      await api('/api/ai/providers/' + pid + '/models', { method: 'PUT', body: JSON.stringify({ active: arr, default: mid }) });
      await renderProviderModels(pid);
      toast('Default model set', 'success');
    } catch (e) { toast(e.message, 'error'); }
  }

  // ---- RULES ---------------------------------------------------------------
  let editingRuleId = null;
  async function loadRules() {
    const box = $('#rules-list');
    box.innerHTML = '<div class="bento-card p-4 text-xs text-gray-500">Loading…</div>';
    try {
      const { rules } = await api('/api/ai/rules');
      if (!rules.length) {
        box.innerHTML = '<div class="bento-card p-4">' + emptyState('No rules yet', 'Create one, or describe it in AI Chat.') + '</div>';
        return;
      }
      box.innerHTML = rules.map(r => {
        return '<div class="bento-card p-4 flex flex-col gap-2">' +
          '<div class="flex items-start justify-between"><div class="min-w-0">' +
          '<div class="text-sm font-medium text-gray-100 truncate">' + esc(r.name) + '</div>' +
          '<span class="pill pill-info mt-1">' + esc(r.playlist_name || r.target_playlist || '—') + '</span></div>' +
          '<label class="relative inline-flex items-center cursor-pointer">' +
          '<input type="checkbox" class="rule-toggle accent-[#2f8fc9]" data-id="' + esc(r.id) + '"' + (r.enabled ? ' checked' : '') + '>' +
          '<span class="ml-2 text-[10px] text-gray-400">' + (r.enabled ? 'on' : 'off') + '</span></label></div>' +
          '<div class="text-[11px] text-gray-400 whitespace-pre-wrap break-words">' + esc(r.description || '') + '</div>' +
          (r.model ? '<div class="text-[10px] text-gray-500 font-mono">model: ' + esc(r.model) + '</div>' : '') +
          (r.matched_count != null ? '<div class="text-[10px] text-gray-500">matched ' + esc(r.matched_count) + '×</div>' : '') +
          '<div class="flex gap-2 pt-1"><button class="rule-edit bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs px-3 py-1.5 rounded-lg" data-id="' + esc(r.id) + '">Edit</button>' +
          '<button class="rule-del bg-[#20242c] border border-[#2a2f3a] text-[#dc2626] text-xs px-3 py-1.5 rounded-lg" data-id="' + esc(r.id) + '">Delete</button></div>' +
          '</div>';
      }).join('');
      $all('.rule-toggle').forEach(c => c.addEventListener('change', () => toggleRule(c.getAttribute('data-id'), c.checked)));
      $all('.rule-edit').forEach(b => b.addEventListener('click', () => openRuleModal(b.getAttribute('data-id'))));
      $all('.rule-del').forEach(b => b.addEventListener('click', () => deleteRule(b.getAttribute('data-id'))));
    } catch (e) {
      box.innerHTML = '<div class="bento-card p-4 text-xs text-[#dc2626]">' + sanitize(e.message) + '</div>';
    }
  }
  async function toggleRule(id, enabled) {
    try { await api('/api/ai/rules/' + id, { method: 'PATCH', body: JSON.stringify({ enabled }) }); loadHub(); }
    catch (e) { toast(e.message, 'error'); loadRules(); }
  }
  async function deleteRule(id) {
    if (!confirm('Delete this rule?')) return;
    try { await api('/api/ai/rules/' + id, { method: 'DELETE' }); toast('Rule deleted', 'success'); loadRules(); loadHub(); }
    catch (e) { toast(e.message, 'error'); }
  }
  function openRuleModal(id) {
    editingRuleId = id || null;
    $('#rule-conflict').classList.add('hidden');
    $('#rule-form-msg').textContent = '';
    if (id) {
      $('#rule-modal-title').textContent = 'Edit Rule';
      api('/api/ai/rules/' + id).then(r => {
        $('#rule-name').value = r.name || ''; $('#rule-playlist').value = r.target_playlist || '';
        $('#rule-desc').value = r.description || ''; $('#rule-model').value = r.model || '';
        $('#rule-enabled').checked = !!r.enabled;
      }).catch(e => toast(e.message, 'error'));
    } else {
      $('#rule-modal-title').textContent = 'New Rule';
      $('#rule-name').value = ''; $('#rule-playlist').value = ''; $('#rule-desc').value = ''; $('#rule-model').value = ''; $('#rule-enabled').checked = true;
    }
    const m = $('#rule-modal'); m.classList.remove('hidden'); m.classList.add('flex');
  }
  function closeRuleModal() { const m = $('#rule-modal'); m.classList.add('hidden'); m.classList.remove('flex'); }
  async function saveRule() {
    const payload = {
      name: $('#rule-name').value.trim(),
      target_playlist: $('#rule-playlist').value.trim(),
      description: $('#rule-desc').value.trim(),
      model: $('#rule-model').value.trim() || undefined,
      enabled: $('#rule-enabled').checked,
    };
    if (!payload.name || !payload.target_playlist) { $('#rule-form-msg').textContent = 'Name and target playlist required.'; $('#rule-form-msg').className = 'text-[11px] text-[#dc2626]'; return; }
    try {
      if (editingRuleId) {
        await api('/api/ai/rules/' + editingRuleId, { method: 'PATCH', body: JSON.stringify(payload) });
      } else {
        await api('/api/ai/rules', { method: 'POST', body: JSON.stringify(payload) });
      }
      toast('Rule saved', 'success'); closeRuleModal(); loadRules(); loadHub();
    } catch (e) {
      if (e.status === 409 && e.data && e.data.playlist_name) {
        const c = $('#rule-conflict');
        c.classList.remove('hidden');
        c.innerHTML = sanitize('“' + e.data.playlist_name + '” already has a rule — edit or delete it first.');
      } else {
        $('#rule-form-msg').textContent = e.message; $('#rule-form-msg').className = 'text-[11px] text-[#dc2626]';
      }
    }
  }

  // ---- CHAT ----------------------------------------------------------------
  let chatHistory = [];
  function chatBubble(role, text, modelUsed, fallback, errorMsg) {
    const wrap = document.createElement('div');
    wrap.className = 'flex ' + (role === 'user' ? 'justify-end' : 'justify-start');
    const inner = document.createElement('div');
    if (errorMsg) {
      inner.className = 'max-w-[85%] rounded-lg px-3 py-2 text-[13px] bg-[#3a1d1d] border border-[#7f1d1d] text-[#fca5a5]';
      inner.innerHTML = '<i class="fas fa-exclamation-triangle mr-1"></i>' + sanitize(errorMsg);
      wrap.appendChild(inner);
      return wrap;
    }
    inner.className = 'max-w-[85%] rounded-lg px-3 py-2 text-[13px] ' +
      (role === 'user' ? 'bg-[#2f8fc9] text-white' : 'bg-[#20242c] border border-[#2a2f3a] text-gray-200');
    inner.innerHTML = sanitize(text);
    if (role === 'ai' && modelUsed) {
      const foot = document.createElement('div');
      foot.className = 'text-[10px] text-gray-500 mt-1';
      foot.innerHTML = 'answered by <span class="font-mono">' + sanitize(modelUsed) + '</span>' + (fallback ? ' <span class="pill pill-warn">fallback</span>' : '');
      inner.appendChild(foot);
    }
    wrap.appendChild(inner);
    return wrap;
  }
  async function sendChat() {
    const input = $('#chat-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    const log = $('#chat-log');
    log.appendChild(chatBubble('user', text));
    chatHistory.push({ role: 'user', content: text });
    const btn = $('#chat-send'); btn.disabled = true;
    const typing = chatBubble('ai', '<i class="fas fa-spinner spinner"></i>');
    log.appendChild(typing); log.scrollTop = log.scrollHeight;
    try {
      const res = await api('/api/ai/chat', { method: 'POST', body: JSON.stringify({ message: text, conversation_id: window.__aiConv || undefined }) });
      typing.remove();
      if (res.error) {
        // Backend returned an error payload (e.g. provider failed). Surface it
        // in a red bubble instead of a blank assistant message.
        log.appendChild(chatBubble('ai', '', null, false, res.error));
      } else {
        log.appendChild(chatBubble('ai', res.reply || '(no response)', res.model_used, res.fallback));
      }
      chatHistory.push({ role: 'assistant', content: res.reply || '' });
      if (res.pending_actions && res.pending_actions.length) renderChatActions(res.pending_actions);
    } catch (e) {
      typing.remove();
      log.appendChild(chatBubble('ai', '', null, false, e.message));
    } finally { btn.disabled = false; log.scrollTop = log.scrollHeight; }
  }
  function renderChatActions(actions) {
    const zone = $('#chat-confirm-zone');
    zone.innerHTML = ''; zone.classList.remove('hidden');
    actions.forEach(a => {
      const card = document.createElement('div');
      card.className = 'bento-card p-3 border border-[#dc2626]/40 space-y-2';
      const title = document.createElement('div');
      title.className = 'text-[12px] text-gray-200 font-medium';
      title.innerHTML = sanitize(a.type || 'Action');
      card.appendChild(title);
      if (a.preview) {
        const prev = document.createElement('div');
        prev.className = 'text-[11px] text-gray-400 whitespace-pre-wrap break-words';
        prev.innerHTML = sanitize(a.preview);
        card.appendChild(prev);
      }
      const banner = document.createElement('div');
      banner.className = 'text-[11px] text-[#dc2626]';
      banner.innerHTML = '<i class="fas fa-triangle-exclamation"></i> Destructive action — confirmation required';
      card.appendChild(banner);
      const row = document.createElement('div'); row.className = 'flex gap-2';
      const confirm = document.createElement('button');
      confirm.className = 'bg-[#2f8fc9] hover:bg-[#2a7db8] text-white text-xs px-3 py-1.5 rounded-lg';
      confirm.textContent = 'Confirm';
      confirm.addEventListener('click', () => executeAction(a.id, zone));
      const cancel = document.createElement('button');
      cancel.className = 'bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs px-3 py-1.5 rounded-lg';
      cancel.textContent = 'Cancel';
      cancel.addEventListener('click', () => { zone.classList.add('hidden'); zone.innerHTML = ''; });
      row.appendChild(confirm); row.appendChild(cancel);
      card.appendChild(row);
      zone.appendChild(card);
    });
  }
  async function executeAction(actionId, zone) {
    try {
      const res = await api('/api/ai/chat/confirm', { method: 'POST', body: JSON.stringify({ action_id: actionId }) });
      toast('Action executed', 'success');
      const log = $('#chat-log');
      log.appendChild(chatBubble('ai', (res.result && (res.result.summary || JSON.stringify(res.result))) || 'Done.'));
      zone.classList.add('hidden'); zone.innerHTML = '';
    } catch (e) { toast(e.message, 'error'); }
  }

  // ---- JOBS ----------------------------------------------------------------
  async function loadJobs() {
    const box = $('#jobs-list');
    box.innerHTML = '<div class="bento-card p-4 text-xs text-gray-500">Loading…</div>';
    try {
      const { jobs } = await api('/api/ai/jobs');
      if (!jobs.length) {
        box.innerHTML = '<div class="bento-card p-4">' + emptyState('No scheduled jobs', 'Click “New Job” to schedule a scan or cleanup.') + '</div>';
        return;
      }
      box.innerHTML = jobs.map(j => {
        const destr = ['move_video', 'delete_video', 'remove_duplicates'].includes(j.task && j.task.type);
        return '<div class="bento-card p-4 flex flex-col gap-2">' +
          '<div class="flex items-start justify-between"><div class="min-w-0">' +
          '<div class="text-sm font-medium text-gray-100 truncate">' + esc(j.name) + '</div>' +
          '<div class="text-[11px] text-gray-500 font-mono">' + esc(j.cron) + ' · ' + esc((j.task && j.task.type) || '') + '</div></div>' +
          '<span class="pill ' + (j.enabled ? 'pill-success' : 'pill-warn') + '">' + (j.enabled ? 'on' : 'paused') + '</span></div>' +
          (j.last_status ? '<div class="text-[10px] text-gray-500">last: ' + esc(j.last_status) + (j.last_run ? ' @ ' + shortTime(j.last_run) : '') + '</div>' : '') +
          '<div class="text-[10px] text-gray-400">next: ' + (j.next_run ? esc(shortTime(j.next_run)) : '—') + '</div>' +
          (destr ? '<div class="text-[10px] text-[#ca8a04]"><i class="fas fa-triangle-exclamation"></i> destructive — runs unattended on schedule</div>' : '') +
          '<div class="flex gap-2 pt-1">' +
          '<button class="job-run bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs px-3 py-1.5 rounded-lg" data-id="' + esc(j.id) + '">Run now</button>' +
          '<button class="job-toggle bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs px-3 py-1.5 rounded-lg" data-id="' + esc(j.id) + '" data-en="' + (!j.enabled) + '">' + (j.enabled ? 'Pause' : 'Resume') + '</button>' +
          '<button class="job-cancel bg-[#20242c] border border-[#2a2f3a] text-[#ca8a04] text-xs px-3 py-1.5 rounded-lg" data-id="' + esc(j.id) + '">Hard-cancel</button>' +
          '<button class="job-del bg-[#20242c] border border-[#2a2f3a] text-[#dc2626] text-xs px-3 py-1.5 rounded-lg" data-id="' + esc(j.id) + '">Delete</button>' +
          '</div></div>';
      }).join('');
      $all('.job-run').forEach(b => b.addEventListener('click', () => runJob(b.getAttribute('data-id'))));
      $all('.job-toggle').forEach(b => b.addEventListener('click', () => toggleJob(b.getAttribute('data-id'), b.getAttribute('data-en') === 'true')));
      $all('.job-cancel').forEach(b => b.addEventListener('click', () => hardCancelJob(b.getAttribute('data-id'))));
      $all('.job-del').forEach(b => b.addEventListener('click', () => deleteJob(b.getAttribute('data-id'))));
    } catch (e) {
      box.innerHTML = '<div class="bento-card p-4 text-xs text-[#dc2626]">' + sanitize(e.message) + '</div>';
    }
  }
  async function runJob(id) {
    try {
      const res = await api('/api/ai/jobs/' + id + '/run', { method: 'POST' });
      if (res.pending_action_id) {
        toast('Destructive run held — confirm in AI Chat', 'info');
        switchTab('chat');
      } else {
        toast('Job started', 'success');
      }
      loadJobs();
    } catch (e) { toast(e.message, 'error'); }
  }
  async function toggleJob(id, enabled) {
    try { await api('/api/ai/jobs/' + id, { method: 'PATCH', body: JSON.stringify({ enabled }) }); loadJobs(); }
    catch (e) { toast(e.message, 'error'); }
  }
  async function hardCancelJob(id) {
    try {
      const res = await api('/api/ai/jobs/' + id + '/cancel', { method: 'POST' });
      toast(res.cancelled ? 'In-flight run cancelled' : 'No run in flight', res.cancelled ? 'success' : 'info');
    } catch (e) { toast(e.message, 'error'); }
  }
  async function deleteJob(id) {
    if (!confirm('Delete this scheduled job?')) return;
    try { await api('/api/ai/jobs/' + id, { method: 'DELETE' }); toast('Job deleted', 'success'); loadJobs(); }
    catch (e) { toast(e.message, 'error'); }
  }
  function openJobForm() {
    $('#job-form').classList.remove('hidden');
    $('#job-form-msg').textContent = '';
    $('#job-priv-warn').classList.add('hidden');
  }
  function closeJobForm() { $('#job-form').classList.add('hidden'); }
  async function parseJobNL() {
    const text = $('#job-nl').value.trim();
    if (!text) return;
    try {
      const res = await api('/api/ai/jobs/parse', { method: 'POST', body: JSON.stringify({ text }) });
      if (res.cron) $('#job-cron').value = res.cron;
      if (res.task && res.task.type) {
        const sel = $('#job-task');
        for (const o of sel.options) { if (o.value === res.task.type) { o.selected = true; break; } }
      }
      if (res.task && res.task.payload && res.task.payload.playlist_id) $('#job-playlist').value = res.task.payload.playlist_id;
      updateJobPrivWarn();
      toast('Parsed', 'success');
    } catch (e) { toast(e.message, 'error'); }
  }
  function updateJobPrivWarn() {
    const t = $('#job-task').value;
    const destr = ['move_video', 'delete_video', 'remove_duplicates'].includes(t);
    $('#job-priv-warn').classList.toggle('hidden', !destr);
  }
  async function createJob() {
    const name = $('#job-name').value.trim();
    const cron = $('#job-cron').value.trim();
    const task = $('#job-task').value;
    const playlist = $('#job-playlist').value.trim();
    if (!name || !cron) { $('#job-form-msg').textContent = 'Name and cron required.'; return; }
    if (!/^[*,\d/\-\s]+$/.test(cron) || cron.split(/\s+/).length !== 5) { $('#job-form-msg').textContent = 'Cron must be 5 fields.'; return; }
    const payload = {};
    if (playlist && task !== 'apply_rules') payload.playlist_id = playlist;
    const destr = ['move_video', 'delete_video', 'remove_duplicates'].includes(task);
    const body = { name, cron, task: { type: task, payload }, enabled: $('#job-enabled').checked, confirm_destructive: destr };
    try {
      await api('/api/ai/jobs', { method: 'POST', body: JSON.stringify(body) });
      toast('Job created', 'success'); closeJobForm(); loadJobs(); loadHub();
    } catch (e) { $('#job-form-msg').textContent = e.message; }
  }

  // ---- init ----------------------------------------------------------------
  function switchTab(name) {
    if (PANELS.indexOf(name) >= 0) {
      showPanel(name);
      // reflect in URL without reload
      try { history.replaceState(null, '', '/ai/' + (name === 'hub' ? '' : name)); } catch (_) {}
    }
  }
  function init() {
    APP.token = getToken();
    window.__aiConv = 'c_' + Date.now();
    // sub-nav buttons
    $all('.ai-tab').forEach(b => b.addEventListener('click', () => switchTab(b.getAttribute('data-ai'))));
    $all('.ai-sub').forEach(a => a.addEventListener('click', (e) => { if (a.getAttribute('href')) return; }));
    // collapsible sidebar groups (AI Hub etc.)
    $all('.ai-group-toggle').forEach(t => {
      const name = t.getAttribute('data-group');
      const items = document.querySelector('.ai-group-items[data-group="' + name + '"]');
      const chev = t.querySelector('.ai-group-chevron');
      // restore persisted state
      if (localStorage.getItem('nav_collapse_' + name) === '1') {
        items.classList.add('hidden'); chev.classList.replace('fa-chevron-down', 'fa-chevron-right');
      }
      t.addEventListener('click', (e) => {
        // don't toggle when clicking the actual link (let it navigate)
        if (e.target.closest('a')) return;
        const hidden = items.classList.toggle('hidden');
        chev.classList.toggle('fa-chevron-down', !hidden);
        chev.classList.toggle('fa-chevron-right', hidden);
        localStorage.setItem('nav_collapse_' + name, hidden ? '1' : '0');
      });
    });

    $('#hub-open-chat') && $('#hub-open-chat').addEventListener('click', () => switchTab('chat'));

    // mobile sidebar (CSP-clean: no inline onclick)
    const sidebar = document.getElementById('mobile-sidebar');
    const overlay = document.getElementById('mobile-overlay');
    const toggle = document.getElementById('sidebar-toggle');
    function openMobileSidebar() { sidebar.classList.remove('-translate-x-full'); overlay.classList.remove('hidden'); }
    function closeMobileSidebar() { sidebar.classList.add('-translate-x-full'); overlay.classList.add('hidden'); }
    toggle && toggle.addEventListener('click', openMobileSidebar);
    overlay && overlay.addEventListener('click', closeMobileSidebar);
    // close sidebar after navigating via a sub-nav link on mobile
    $all('.ai-sub').forEach(a => a.addEventListener('click', () => { if (window.innerWidth < 768) closeMobileSidebar(); }));
    const logoutLink = document.getElementById('logout-link');
    logoutLink && logoutLink.addEventListener('click', (e) => { e.preventDefault(); if (typeof window.logout === 'function') window.logout(); });

    // providers
    $('#prov-rescan-all') && $('#prov-rescan-all').addEventListener('click', () => {
      // rescan every connected provider in parallel
      api('/api/ai/providers').then(r => {
        const ids = (r.providers || []).map(p => p.id);
        return Promise.all(ids.map(id => api('/api/ai/providers/' + id + '/models?refresh=1', { method: 'GET' }).catch(() => null)));
      }).then(() => { toast('All providers rescanned', 'success'); loadProviders(); loadHub(); })
        .catch(e => toast(e.message, 'error'));
    });
    $('#prov-add-btn') && $('#prov-add-btn').addEventListener('click', openProvModal);
    $('#prov-modal-close') && $('#prov-modal-close').addEventListener('click', closeProvModal);
    $('#prov-connect') && $('#prov-connect').addEventListener('click', connectProvider);
    $('#prov-save') && $('#prov-save').addEventListener('click', saveProviderModels);
    // Provider type UI: pre-fill base URL, hints, presets
    const PROV_URLS = {
      openai: 'https://api.openai.com',
      anthropic: 'https://api.anthropic.com',
      groq: 'https://api.groq.com',
      grok: 'https://api.x.ai',
      google: 'https://generativelanguage.googleapis.com',
    };
    const PROV_HINTS = {
      openai: 'Get your API key at platform.openai.com — GPT-4o, o1, o3 and more.',
      anthropic: 'Get your API key at console.anthropic.com — Claude 3.5 Sonnet, Haiku, Opus.',
      groq: 'Get a free API key at console.groq.com — blazing fast open-source model inference.',
      grok: 'Get your API key at console.x.ai — Grok-3, Grok-2 and beta models.',
      google: 'Get a Gemini API key at aistudio.google.com — Gemini 2.5 Pro, Flash and more.',
      custom: 'Any OpenAI-compatible endpoint (Ollama, LM Studio, Together AI, Mistral, OpenRouter…). Needs a /v1/models route for automatic discovery.',
    };
    function updateProvType() {
      const typeEl = $('#prov-type');
      if (!typeEl) return;
      const type = typeEl.value;
      const baseEl = $('#prov-base');
      const hintEl = $('#prov-type-hint');
      const presetsEl = $('#prov-presets');
      const lockEl = $('#prov-base-lock');
      const keyOptEl = $('#prov-key-optional');
      if (baseEl) {
        baseEl.value = PROV_URLS[type] || '';
        if (lockEl) lockEl.textContent = PROV_URLS[type] ? 'pre-filled · override if needed' : 'required';
      }
      if (hintEl) {
        const hint = PROV_HINTS[type] || '';
        hintEl.textContent = hint;
        hintEl.classList.toggle('hidden', !hint);
      }
      if (presetsEl) presetsEl.classList.toggle('hidden', type !== 'custom');
      if (keyOptEl) keyOptEl.classList.toggle('hidden', type !== 'custom');
      const namePh = { openai: 'My OpenAI', anthropic: 'My Claude', groq: 'My Groq', grok: 'My Grok', google: 'My Gemini', custom: 'My LLM' };
      const nameEl = $('#prov-name');
      if (nameEl) nameEl.placeholder = namePh[type] || 'Provider name';
    }
    $('#prov-type') && $('#prov-type').addEventListener('change', updateProvType);
    // Preset quick-fill
    $all('.prov-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        const baseEl = $('#prov-base');
        if (baseEl) baseEl.value = btn.getAttribute('data-url') || '';
        const n = btn.getAttribute('data-name') || '';
        const nameEl = $('#prov-name');
        if (n && nameEl && !nameEl.value) nameEl.value = n;
        const k = btn.getAttribute('data-key') || '';
        const keyEl = $('#prov-key');
        if (k && keyEl && !keyEl.value) keyEl.value = k;
        $all('.prov-preset').forEach(b => b.classList.remove('border-[#2f8fc9]', 'text-white'));
        btn.classList.add('border-[#2f8fc9]', 'text-white');
      });
    });

    // rules
    $('#rule-new-btn') && $('#rule-new-btn').addEventListener('click', () => openRuleModal(null));
    $('#rule-modal-close') && $('#rule-modal-close').addEventListener('click', closeRuleModal);
    $('#rule-modal-cancel') && $('#rule-modal-cancel').addEventListener('click', closeRuleModal);
    $('#rule-save') && $('#rule-save').addEventListener('click', saveRule);

    // chat
    $('#chat-send') && $('#chat-send').addEventListener('click', sendChat);
    $('#chat-input') && $('#chat-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChat(); });

    // jobs
    $('#job-new-btn') && $('#job-new-btn').addEventListener('click', openJobForm);
    $('#job-form-cancel') && $('#job-form-cancel').addEventListener('click', closeJobForm);
    $('#job-parse') && $('#job-parse').addEventListener('click', parseJobNL);
    $('#job-create') && $('#job-create').addEventListener('click', createJob);
    $('#job-task') && $('#job-task').addEventListener('change', updateJobPrivWarn);

    // initial panel from URL
    const path = window.location.pathname.replace(/^\/ai\/?/, '');
    const initial = PANELS.includes(path) ? path : 'hub';
    showPanel(initial);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
