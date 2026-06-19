// Toast notification system
function toast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-times-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    const colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        warning: 'bg-yellow-600',
        info: 'bg-blue-600'
    };
    toast.className = `flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white text-xs font-medium animate-slide-in ${colors[type] || colors.info}`;
    toast.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${DOMPurify.sanitize(message, {USE_PROFILES: {html: true}})}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.classList.add('animate-slide-out');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2 w-80';
    document.body.appendChild(container);
    return container;
}

// Store all playlists for manage function
let allPlaylists = [];

// Synchronous render of cached playlists for instant display
function renderCachedPlaylists() {
    const grid = document.getElementById('playlists-grid');
    const cachedPlaylists = localStorage.getItem('cached_playlists');
    if (cachedPlaylists) {
        try {
            const playlists = JSON.parse(cachedPlaylists);
            if (playlists.length) {
                allPlaylists = playlists;
                renderPlaylistsGrid(playlists);
                return true;
            }
        } catch (e) {
            console.error("Error parsing cached playlists", e);
        }
    }
    return false;
}

async function loadPlaylists() {
    const grid = document.getElementById('playlists-grid');
    
    // If we already rendered cached data, skip rendering again unless API returns new data
    const hasCached = renderCachedPlaylists();
    
    try {
        const response = await fetch('/api/playlists');
        if (!response.ok) throw new Error('Failed to load');
        const data = await response.json();
        allPlaylists = data.playlists || [];
        
        // Save to localStorage
        localStorage.setItem('cached_playlists', JSON.stringify(allPlaylists));
        
        // Always re-render with fresh data
        renderPlaylistsGrid(allPlaylists);
    } catch (e) {
        if (!hasCached) {
            grid.innerHTML = '<div class="col-span-full bento-card p-8 text-center text-red-400">Failed to load playlists</div>';
        }
    }
}

function renderPlaylistsGrid(playlists) {
    const grid = document.getElementById('playlists-grid');
    if (!playlists.length) {
        grid.innerHTML = '<div class="col-span-full bento-card p-12 text-center text-gray-400">No playlists found. Create one to get started.</div>';
        return;
    }
    grid.innerHTML = playlists.map(p => `
        <div class="bento-card p-3 flex flex-col cursor-pointer hover:border-blue-500/50 transition-colors h-full relative playlist-card" data-playlist-id="${DOMPurify.sanitize(p.id)}">
            <div class="flex items-start justify-between mb-2">
                <div class="w-12 h-7 bg-gray-700 rounded overflow-hidden flex-shrink-0"><img src="${DOMPurify.sanitize(p.thumbnail || 'https://picsum.photos/160/90')}" class="w-full h-full object-cover"></div>
                <button class="text-[9px] px-1.5 py-0.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors open-youtube-btn" data-playlist-id="${DOMPurify.sanitize(p.id)}" title="Open on YouTube"><i class="fa-solid fa-external-link text-[8px] mr-1"></i> YouTube</button>
            </div>
            <h3 class="text-xs font-semibold text-white truncate mb-0.5">${DOMPurify.sanitize(p.title)}</h3>
            <p class="text-[9px] text-gray-400 mb-2">${DOMPurify.sanitize(p.video_count)} videos</p>
            <div class="flex items-center gap-1 mt-auto pt-1.5 border-t border-[#2a2f3a]">
                <button class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-[10px] py-1 px-2.5 rounded transition-colors rescan-playlist-btn" data-playlist-id="${DOMPurify.sanitize(p.id)}" title="Rescan Videos"><i class="fa-solid fa-arrows-rotate text-[9px]"></i></button>
                <button class="flex-1 bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-[10px] py-1 rounded transition-colors manage-playlist-btn" data-playlist-id="${DOMPurify.sanitize(p.id)}" data-playlist-title="${DOMPurify.sanitize(p.title.replace(/\'/g, "\\'"), {USE_PROFILES: {html: true}})}"><i class="fa-solid fa-cog text-[9px]"></i> Manage</button>
            </div>
        </div>
    `).join('');
}

// Open playlist on YouTube
function openPlaylist(playlistId, event) {
    if (event) event.stopPropagation();
    window.open(`https://www.youtube.com/playlist?list=${DOMPurify.sanitize(playlistId)}`, '_blank');
}

async function rescanPlaylist(playlistId, event) {
    event.stopPropagation();
    const btn = event.currentTarget;
    const origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-blue-400"></i>';
    
    toast('Rescanning playlist videos...', 'info');
    try {
        const resp = await fetch(`/api/youtube/videos?playlist_id=${DOMPurify.sanitize(playlistId)}&force_refresh=true`);
        if (!resp.ok) throw new Error('Failed to refresh');
        const data = await resp.json();
        const count = data.videos?.length || 0;
        toast(`Rescan complete - ${DOMPurify.sanitize(count)} videos found`, 'success');
        loadPlaylists();
    } catch (e) {
        toast('Rescan failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHTML;
    }
}

function closeAllMenus() {
    document.querySelectorAll('[id^="menu-"]').forEach(el => el.classList.add('hidden'));
}

function togglePlaylistMenu(playlistId) {
    const menu = document.getElementById(`menu-${DOMPurify.sanitize(playlistId)}`);
    if (!menu) return;
    document.querySelectorAll('[id^="menu-"]').forEach(el => {
        if (el !== menu) el.classList.add('hidden');
    });
    menu.classList.toggle('hidden');
}

async function renamePlaylistPrompt(playlistId) {
    const current = allPlaylists.find(p => p.id === playlistId);
    const newTitle = prompt('Rename playlist', current ? current.title : '');
    if (newTitle === null || !newTitle.trim()) return;
    try {
        const resp = await fetch('/api/youtube/playlists/rename', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({playlist_id: playlistId, new_title: newTitle.trim()})
        });
        const data = await resp.json();
        toast(DOMPurify.sanitize(data.message || data.error, {USE_PROFILES: {html: true}}), data.status === 'success' ? 'success' : 'error');
        closeAllMenus();
        loadPlaylists();
    } catch (e) {
        toast('Rename failed', 'error');
    }
}

async function duplicatePlaylistPrompt(playlistId) {
    const current = allPlaylists.find(p => p.id === playlistId);
    const newTitle = prompt(`Duplicate playlist: ${DOMPurify.sanitize(current ? current.title : '')}`, `${DOMPurify.sanitize(current ? current.title : 'Playlist')} (copy)`);
    if (newTitle === null || !newTitle.trim()) return;
    try {
        const resp = await fetch('/api/youtube/playlists/duplicate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({playlist_id: playlistId, new_title: newTitle.trim()})
        });
        const data = await resp.json();
        toast(DOMPurify.sanitize(data.message || data.error, {USE_PROFILES: {html: true}}), data.status === 'success' ? 'success' : 'error');
        closeAllMenus();
        loadPlaylists();
    } catch (e) {
        toast('Duplicate failed', 'error');
    }
}

async function deletePlaylistConfirmed(playlistId) {
    if (!confirm('Delete this playlist? This cannot be undone.')) return;
    try {
        const resp = await fetch('/api/youtube/playlists/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({playlist_id: playlistId})
        });
        const data = await resp.json();
        toast(DOMPurify.sanitize(data.message || data.error, {USE_PROFILES: {html: true}}), data.status === 'success' ? 'success' : 'error');
        closeAllMenus();
        loadPlaylists();
    } catch (e) {
        toast('Delete failed', 'error');
    }
}

async function addVideoToPlaylist(playlistId, videoId) {
    const id = prompt('Video ID');
    if (!id) return;
    await fetch('/youtube/actions/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({playlist_id: playlistId, video_id: id})
    });
    toast('Video queued', 'success');
}

async function editPlaylist(playlistId) {
    const title = prompt('Playlist title');
    if (title === null) return;
    await fetch('/youtube/actions/create-playlist', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({title})
    });
    toast('Playlist updated', 'success');
    loadPlaylists();
}

async function deletePlaylist(playlistId) {
    if (!confirm('Delete this playlist?')) return;
    await fetch('/youtube/actions/remove', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({playlist_item_id: playlistId})
    });
    toast('Playlist delete requested', 'success');
    loadPlaylists();
}

function managePlaylist(playlistId) {
    window.location.href = `/playlist/${DOMPurify.sanitize(playlistId)}`;
}

function openManagePlaylistModal(playlistId, playlistTitle, event) {
    if (event) event.stopPropagation();
    
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs';
    modal.innerHTML = `
        <div class="bg-[#1a1d24] border border-[#2a2f3a] rounded-xl p-5 w-full max-w-sm mx-4 shadow-2xl" onclick="event.stopPropagation()">
            <div class="flex items-center justify-between mb-4">
                <div class="min-w-0">
                    <h3 class="text-xs font-bold text-gray-400 uppercase tracking-wider">Manage Playlist</h3>
                    <p class="text-sm font-bold text-white truncate">${DOMPurify.sanitize(playlistTitle)}</p>
                </div>
                <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-white p-1 transition-colors"><i class="fa-solid fa-xmark"></i></button>
            </div>
            
            <div class="space-y-2.5">
                <button onclick="actionRenamePlaylist('${DOMPurify.sanitize(playlistId)}', \`${DOMPurify.sanitize(playlistTitle.replace(/\'/g, "\\'"), {USE_PROFILES: {html: true}})}\`); this.closest('.fixed').remove()" class="w-full bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-pen-to-square text-blue-400 w-4 text-center"></i> Rename Playlist
                </button>
                <button onclick="actionDuplicatePlaylist('${DOMPurify.sanitize(playlistId)}', \`${DOMPurify.sanitize(playlistTitle.replace(/\'/g, "\\'"), {USE_PROFILES: {html: true}})}\`); this.closest('.fixed').remove()" class="w-full bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-copy text-green-400 w-4 text-center"></i> Duplicate Playlist
                </button>
                <button onclick="actionDeletePlaylist('${DOMPurify.sanitize(playlistId)}', \`${DOMPurify.sanitize(playlistTitle.replace(/\'/g, "\\'"), {USE_PROFILES: {html: true}})}\`); this.closest('.fixed').remove()" class="w-full bg-red-950/20 hover:bg-red-900/30 border border-red-900/30 text-red-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-trash-can text-red-500 w-4 text-center"></i> Delete Playlist
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function actionRenamePlaylist(playlistId, currentTitle) {
    const newTitle = prompt('Rename Playlist - Enter new title:', currentTitle);
    if (!newTitle || newTitle === currentTitle) return;
    
    toast('Renaming playlist...', 'info');
    try {
        const resp = await fetch('/api/youtube/playlists/rename', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ playlist_id: playlistId, new_title: newTitle })
        });
        const res = await resp.json();
        if (resp.ok) {
            toast(DOMPurify.sanitize(res.message, {USE_PROFILES: {html: true}}), 'success');
            loadPlaylists();
        } else {
            toast(DOMPurify.sanitize(res.detail || 'Rename failed', {USE_PROFILES: {html: true}}), 'error');
        }
    } catch (e) {
        toast('Failed to rename playlist', 'error');
    }
}

async function actionDuplicatePlaylist(playlistId, currentTitle) {
    const newTitle = prompt('Duplicate Playlist - Enter name for duplicate:', `${DOMPurify.sanitize(currentTitle, {USE_PROFILES: {html: true}})} Copy`);
    if (!newTitle) return;
    
    toast('Initiating playlist duplication...', 'info');
    try {
        const resp = await fetch('/api/youtube/playlists/duplicate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ playlist_id: playlistId, new_title: newTitle })
        });
        const res = await resp.json();
        if (resp.ok) {
            toast(DOMPurify.sanitize(res.message, {USE_PROFILES: {html: true}}), 'success');
            loadPlaylists();
        } else {
            toast(DOMPurify.sanitize(res.detail || 'Duplication failed', {USE_PROFILES: {html: true}}), 'error');
        }
    } catch (e) {
        toast('Failed to duplicate playlist', 'error');
    }
}

async function actionDeletePlaylist(playlistId, title) {
    if (!confirm(`Are you absolutely sure you want to delete '${DOMPurify.sanitize(title, {USE_PROFILES: {html: true}})}' from YouTube?\n\nThis action cannot be undone.`)) return;
    
    toast('Deleting playlist...', 'info');
    try {
        const resp = await fetch('/api/youtube/playlists/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ playlist_id: playlistId })
        });
        const res = await resp.json();
        if (resp.ok) {
            toast(DOMPurify.sanitize(res.message, {USE_PROFILES: {html: true}}), 'success');
            loadPlaylists();
        } else {
            toast(DOMPurify.sanitize(res.detail || 'Delete failed', {USE_PROFILES: {html: true}}), 'error');
        }
    } catch (e) {
        toast('Failed to delete playlist', 'error');
    }
}

// Create new playlist modal
function openNewPlaylistModal() {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/50';
    modal.innerHTML = `
        <div class="bg-[#1a1d24] border border-[#2a2f3a] rounded-lg p-6 w-full max-w-md mx-4">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-lg font-bold text-white">Create New Playlist</h3>
                <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark"></i></button>
            </div>
            <div class="space-y-4">
                <div>
                    <label class="text-[10px] text-gray-400 mb-1 block">Title</label>
                    <input type="text" id="new-playlist-title" placeholder="My Playlist" class="w-full bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs rounded px-3 py-2 outline-none">
                </div>
                <div>
                    <label class="text-[10px] text-gray-400 mb-1 block">Description</label>
                    <textarea id="new-playlist-desc" placeholder="Playlist description..." class="w-full bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs rounded px-3 py-2 outline-none" rows="3"></textarea>
                </div>
                <div>
                    <label class="text-[10px] text-gray-400 mb-1 block">Privacy</label>
                    <select id="new-playlist-privacy" class="w-full bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-xs rounded px-3 py-2 outline-none">
                        <option value="private">Private</option>
                        <option value="unlisted">Unlisted</option>
                        <option value="public">Public</option>
                    </select>
                </div>
                <div class="flex gap-2 pt-2">
                    <button onclick="createPlaylist(); this.closest('.fixed').remove()" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white text-xs py-2 rounded">Create</button>
                    <button onclick="this.closest('.fixed').remove()" class="flex-1 bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-xs py-2 rounded">Cancel</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function createPlaylist() {
    const title = document.getElementById('new-playlist-title').value;
    const description = document.getElementById('new-playlist-desc').value;
    const privacy = document.getElementById('new-playlist-privacy').value;
    
    if (!title) {
        toast('Title is required', 'error');
        return;
    }
    
    try {
        const resp = await fetch('/youtube/actions/create-playlist', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title, description, privacy})
        });
        const result = await resp.json();
        toast(`Playlist created: ${DOMPurify.sanitize(result.title || 'New playlist', {USE_PROFILES: {html: true}})}`, 'success');
        loadPlaylists();
    } catch (e) {
        toast('Failed to create playlist', 'error');
    }
}

async function syncPlaylists(e) {
    const btn = e.target.closest('button') || e.target;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Syncing...';
    try {
        const resp = await fetch('/api/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'sync_playlists'})
        });
        const result = await resp.json();
        if (result.error) {
            toast(`Sync failed: ${DOMPurify.sanitize(result.error, {USE_PROFILES: {html: true}})}`, 'error');
        } else {
            toast(`Sync started. Check dashboard for progress.`, 'success');
        }
    } catch (e) {
        toast('Failed to start sync', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-sync"></i> Sync from YouTube';
    }
}

function openWatchLaterModal() {
    // This will navigate to the watch-later page, no modal needed here
    window.location.href = '/watch-later';
}

document.addEventListener('DOMContentLoaded', () => {
    loadPlaylists();

    // Event listeners for top-level buttons
    document.getElementById('view-watch-later-btn')?.addEventListener('click', openWatchLaterModal);
    document.getElementById('sync-playlists-btn')?.addEventListener('click', syncPlaylists);
    document.getElementById('new-playlist-btn')?.addEventListener('click', openNewPlaylistModal);

    // Event delegation for playlist cards and their buttons
    const playlistsGrid = document.getElementById('playlists-grid');
    if (playlistsGrid) {
        playlistsGrid.addEventListener('click', (event) => {
            const target = event.target;

            // Handle playlist card click (navigation)
            const playlistCard = target.closest('.playlist-card');
            if (playlistCard && !target.closest('button')) { // Don't navigate if a button inside the card was clicked
                window.location.href = `/playlist/${DOMPurify.sanitize(playlistCard.dataset.playlistId)}`;
                return;
            }

            // Handle buttons within playlist cards
            if (target.classList.contains('open-youtube-btn') || target.closest('.open-youtube-btn')) {
                event.stopPropagation();
                const btn = target.closest('.open-youtube-btn');
                openPlaylist(btn.dataset.playlistId, event);
            } else if (target.classList.contains('rescan-playlist-btn') || target.closest('.rescan-playlist-btn')) {
                event.stopPropagation();
                const btn = target.closest('.rescan-playlist-btn');
                rescanPlaylist(btn.dataset.playlistId, event);
            } else if (target.classList.contains('manage-playlist-btn') || target.closest('.manage-playlist-btn')) {
                event.stopPropagation();
                const btn = target.closest('.manage-playlist-btn');
                openManagePlaylistModal(btn.dataset.playlistId, btn.dataset.playlistTitle, event);
            }
        });
    }
});
