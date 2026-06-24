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
    el.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${message}</span>`;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; setTimeout(() => el.remove(), 300); }, duration);
}

async function loadSubscriptions() {
    window._lastSubscriptions = [];
    const list = document.getElementById('subscriptions-list');
    list.innerHTML = '<div class="text-center text-gray-400 py-8"><i class="fa-solid fa-spinner fa-spin text-[#2f8fc9]"></i> Loading subscriptions...</div>';
    try {
        const response = await fetch('/api/subscriptions');
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Failed to load subscriptions');
        localStorage.setItem('cached_subscriptions', JSON.stringify(data));
        renderSubscriptionsList(data.channels || []);
    } catch (e) {
        list.innerHTML = `<div class="text-center text-red-400 py-8">Error: ${DOMPurify.sanitize(e.message || 'Failed to load subscriptions due to a network error.')}</div>`;
        toast(`Error: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
    }
}

function renderSubscriptionsList(channels) {
    const list = document.getElementById('subscriptions-list');
    if (!channels || !channels.length) {
        list.innerHTML = '<div class="text-center text-gray-400 py-8">No subscriptions found. Connect YouTube in Settings.</div>';
        return;
    }
    list.innerHTML = channels.map((c) => {
        const saved = localStorage.getItem('sub-channel-' + c.id) || '';
        return `<div class="flex items-center justify-between p-2 hover:bg-[#20242c] rounded transition-colors">
            <div class="flex items-center gap-3">
                <img src="${c.thumbnail || 'https://picsum.photos/32'}" class="w-8 h-8 rounded-full object-cover">
                <div>
                    <div class="text-sm font-medium text-white">${c.title}</div>
                    <div class="text-[10px] text-gray-400 flex items-center gap-2">
                        <a class="text-[#2f8fc9] hover:underline" href="${c.channel_url || ('https://www.youtube.com/channel/' + c.id)}" target="_blank" rel="noreferrer">Open channel</a>
                        ${c.description ? '<span class="text-gray-500">•</span><span class="text-gray-500 truncate max-w-[220px]">' + c.description.replace(/</g, '&lt;') + '</span>' : ''}
                        ${c.subscribers !== 'Unknown' || c.video_count ? '<span class="text-gray-500">•</span><span class="text-gray-500">' + [c.subscribers !== 'Unknown' ? c.subscribers + ' subs' : '', c.video_count ? c.video_count + ' videos' : ''].filter(Boolean).join(' • ') + '</span>' : ''}
                    </div>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <input type="text" id="map-${c.id}" value="${saved}" class="bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs rounded px-2 py-1 outline-none w-28" placeholder="Playlist ID" onchange="saveMapping('${c.id}', this.value)">
                <button onclick="saveMapping('${c.id}', document.getElementById('map-${c.id}').value)" class="bg-[#2f8fc9] hover:bg-[#2a7db8] text-white text-xs px-3 py-1.5 rounded">Map</button>
                <button onclick="openMaintenance('${c.id}', '${(c.title || '').replace(/'/g, "\\'")}', '${saved}')" class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-xs px-3 py-1.5 rounded">Unsubscribe</button><button onclick="openMaintenance('${c.id}', '${(c.title || '').replace(/'/g, "\\'")}', '${saved}')" class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-xs px-3 py-1.5 rounded">Manage</button>
            </div>
        </div>`;
    }).join('');
}

async function saveMapping(channelId, playlistId) {
    try {
        const maps = await fetch('/api/mappings').then(r => r.json()).catch(() => ({ mappings: {} }));
        const payload = { mappings: { ...(maps.mappings || {}), [channelId]: playlistId } };
        const resp = await fetch('/api/mappings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.error || 'Failed to save mapping');
        localStorage.setItem('sub-channel-' + channelId, playlistId || '');
        toast(`Mapping saved for ${DOMPurify.sanitize(channelId)}`, 'success');
    } catch (e) {
        toast(`Failed to save mapping: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
    }
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

// DOMContentLoaded may have already fired (SPA navigation). Run init either way.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadSubscriptions);
} else {
    loadSubscriptions();
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
