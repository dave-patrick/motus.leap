function toast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2 w-80';
        document.body.appendChild(container);
    }
    const el = document.createElement('div');
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    const colors = { success: 'bg-green-600', error: 'bg-red-600', warning: 'bg-yellow-600', info: 'bg-[#2f8fc9]' };
    el.className = `flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white text-xs font-medium ${colors[type] || colors.info}`;
    el.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span class="flex-1">${DOMPurify.sanitize(message, {USE_PROFILES: {html: true}})}</span><button onclick="this.parentElement.remove()" class="ml-2 text-white/70 hover:text-white focus:outline-none p-0.5 cursor-pointer" title="Close"><i class="fa-solid fa-xmark text-xs"></i></button>`;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; setTimeout(() => el.remove(), 300); }, duration);
}

async function loadSubscriptions() {
    window._lastSubscriptions = [];
    const list = document.getElementById('subscriptions-list');
    list.innerHTML = '<div class="col-span-full text-center text-gray-400 py-8"><i class="fa-solid fa-spinner fa-spin text-[#2f8fc9]"></i> Loading subscriptions...</div>';
    try {
        const subResp = await authFetch('/api/subscriptions');
        const data = await subResp.json();
        if (!subResp.ok || data.error) throw new Error(data.error || 'Failed to load subscriptions');
        localStorage.setItem('cached_subscriptions', JSON.stringify(data));
        renderSubscriptionsList(data.channels || []);
    } catch (e) {
        list.innerHTML = `<div class="col-span-full text-center text-red-400 py-8">Error: ${DOMPurify.sanitize(e.message || 'Failed to load subscriptions due to a network error.')}</div>`;
        toast(`Error: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
    }
}

function renderSubscriptionsList(channels) {
    const list = document.getElementById('subscriptions-list');
    if (!channels || !channels.length) {
        list.innerHTML = '<div class="col-span-full text-center text-gray-400 py-8">No subscriptions found. Connect YouTube in Settings.</div>';
        return;
    }
    list.innerHTML = channels.map((c) => {
        const safeTitle = (c.title || '').replace(/'/g, "\\'");
        const openUrl = c.channel_url || ('https://www.youtube.com/channel/' + c.id);
        const subId = c.subscription_id || c.id;
        const displayId = c.id || '';
        return `<div class="bento-card p-2.5 w-full flex flex-row gap-3 items-center hover:border-[#2a7db8]/50 transition-colors relative min-h-[96px]">
          <div class="flex-shrink-0 w-14 h-14 rounded-full overflow-hidden bg-[#0f1115]">
            <img src="${DOMPurify.sanitize(c.thumbnail || 'https://picsum.photos/64')}" class="w-full h-full object-cover" loading="lazy" onerror="this.onerror=null; this.src='https://picsum.photos/64'">
          </div>
          <div class="flex-1 min-w-0 flex flex-col gap-0.5">
            <h3 class="text-sm md:text-base font-semibold text-[#2f8fc9] truncate" title="${DOMPurify.sanitize(c.title || '')}">${DOMPurify.sanitize(c.title || '')}</h3>
            <p class="text-[10px] text-gray-500 font-mono truncate" title="${DOMPurify.sanitize(displayId)}">${DOMPurify.sanitize(displayId)}</p>
            <p class="text-xs text-gray-400 truncate">
                ${[c.subscribers !== 'Unknown' ? c.subscribers + ' subs' : '', c.video_count ? c.video_count + ' videos' : ''].filter(Boolean).join(' • ') || 'No statistics available'}
            </p>
            <div class="flex items-center gap-2 mt-1">
              <a href="${openUrl}" target="_blank" rel="noreferrer" class="bg-[#20242c] hover:bg-[#2a2f3a] text-gray-300 text-[10px] font-semibold py-1 px-2 rounded transition-colors flex items-center gap-1" title="Open Channel"><i class="fa-solid fa-external-link text-[9px]"></i> Open</a>
              <button onclick="actionUnsubscribe('${subId}')" class="bg-red-950/20 hover:bg-red-900/30 border border-red-900/30 text-red-400 text-[10px] py-1 px-2 rounded transition-colors flex items-center gap-1" title="Unsubscribe"><i class="fa-solid fa-trash-can text-[9px]"></i> Unsubscribe</button>
            </div>
          </div>
        </div>`;
    }).join('');
}

async function refreshSubscriptions() {
    try {
        await loadSubscriptions();
        toast('Subscriptions refreshed successfully', 'success');
    } catch (e) {
        toast(`Failed to refresh subscriptions: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
    }
}

async function openMaintenance(channelId, channelTitle, mappedPlaylist) {
    const modal = document.getElementById('sub-maint-modal');
    document.getElementById('sub-maint-title').textContent = DOMPurify.sanitize(channelTitle || channelId);
    document.getElementById('sub-maint-playlist').textContent = DOMPurify.sanitize(mappedPlaylist || 'No mapping');
    document.getElementById('sub-maint-dupes').innerHTML = '<div class="text-[10px] text-gray-400">Loading...</div>';
    document.getElementById('sub-maint-misplaced').innerHTML = '<div class="text-[10px] text-gray-400">Loading...</div>';
    document.getElementById('sub-maint-note').textContent = '';
    document.getElementById('sub-maint-next').classList.add('hidden');
    modal.classList.remove('hidden');
    try {
        const resp = await fetch('/api/maintenance');
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Maintenance endpoint failed');
        const safe = (items) => (Array.isArray(items) && items.length ? items.length + ' items' : 'None');
        document.getElementById('sub-maint-dupes').textContent = safe(data.duplicated_videos);
        document.getElementById('sub-maint-misplaced').textContent = safe(data.misplaced_videos);
        document.getElementById('sub-maint-next').classList.toggle('hidden', !((data.duplicated_videos || []).length || (data.misplaced_videos || []).length));
        document.getElementById('sub-maint-note').textContent = data.info || '';
    } catch (e) {
        document.getElementById('sub-maint-dupes').textContent = 'unavailable';
        document.getElementById('sub-maint-misplaced').textContent = 'unavailable';
        document.getElementById('sub-maint-note').textContent = `Could not load maintenance data: ${DOMPurify.sanitize(e.message || 'Network error')}`;
        toast(`Failed to load maintenance data: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
    }
}

function closeMaintenanceModal() {
    document.getElementById('sub-maint-modal').classList.add('hidden');
}

// SPA-safe init: retry if script hasn't loaded yet
function safeLoadSubscriptions() {
    if (typeof loadSubscriptions === 'function') {
        loadSubscriptions();
    } else {
        setTimeout(safeLoadSubscriptions, 100);
    }
}
// DOMContentLoaded may have already fired (SPA navigation). Run init either way.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', safeLoadSubscriptions);
} else {
    safeLoadSubscriptions();
}

async function actionSubscribe() {
    const channelId = prompt("Channel ID or URL:");
    if (!channelId) return;
    const m = channelId.match(/channel\/([A-Za-z0-9_-]+)/) || channelId.match(/([A-Za-z0-9_-]{20,})/);
    const id = m ? m[1] : channelId;
    const resp = await fetch('/api/subscriptions/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_id: id })
    });
    if (resp.ok) refreshSubscriptions();
    else alert('Failed to subscribe');
}

async function actionUnsubscribe(subscriptionId) {
    if (!confirm('Unsubscribe from this channel?')) return;
    const resp = await fetch('/api/subscriptions/unsubscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subscription_id: subscriptionId })
    });
    if (resp.ok) refreshSubscriptions();
    else alert('Failed to unsubscribe');
}
