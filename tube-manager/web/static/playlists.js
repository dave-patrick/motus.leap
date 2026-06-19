// playlists.js - Playlists specific scripts

// Store all playlists for manage function
let allPlaylists = [];

// Synchronous render of cached playlists for instant display
function renderCachedPlaylists() {
    const skeleton = document.getElementById('playlists-skeleton');
    const playlistsList = document.getElementById('playlists-list');

    // Show skeleton initially
    if (skeleton) skeleton.classList.remove('hidden');
    if (playlistsList) playlistsList.classList.add('hidden');

    const raw = localStorage.getItem('playlists') || localStorage.getItem('cached_playlists');
    if (raw) {
        try {
            const playlists = JSON.parse(raw);
            if (Array.isArray(playlists) && playlists.length) {
                allPlaylists = playlists;
                renderPlaylistsGrid(playlists);
                if (skeleton) skeleton.classList.add('hidden');
                if (playlistsList) playlistsList.classList.remove('hidden');
                return true;
            }
        } catch (e) {
            console.error("Error parsing cached playlists", e);
        }
    }
    return false;
}

async function loadPlaylists() {
    const skeleton = document.getElementById('playlists-skeleton');
    const playlistsList = document.getElementById('playlists-list');

    // Show skeleton if no cached data was rendered
    if (skeleton && !playlistsList.classList.contains('hidden')) {
        skeleton.classList.remove('hidden');
        playlistsList.classList.add('hidden');
    }

    try {
        const response = await fetch('/api/playlists');
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load playlists');
        }

        allPlaylists = data.playlists || [];
        
        // Save to localStorage
        localStorage.setItem('cached_playlists', JSON.stringify(allPlaylists));
        
        // Always re-render with fresh data
        renderPlaylistsGrid(allPlaylists);
        if (skeleton) skeleton.classList.add('hidden');
        if (playlistsList) playlistsList.classList.remove('hidden');
    } catch (e) {
        if (skeleton) skeleton.classList.add('hidden'); // Hide skeleton on error
        if (playlistsList) playlistsList.classList.remove('hidden'); // Show actual list (empty or error message)
        playlistsList.innerHTML = `<div class="col-span-full bento-card p-8 text-center text-red-400">Error: ${DOMPurify.sanitize(e.message || 'Failed to load playlists due to a network error.')}</div>`;
        toast(`Error: ${e.message}`, 'error');
    }
}

function renderPlaylistsGrid(playlists) {
    const playlistsList = document.getElementById('playlists-list');
    if (!playlistsList) return; // Safeguard

    if (!playlists.length) {
        playlistsList.innerHTML = '<div class="col-span-full bento-card p-12 text-center text-gray-400">No playlists found. Create one to get started.</div>';
        return;
    }
    playlistsList.innerHTML = playlists.map(p => `
        <div onclick="window.location.href='/playlist/${p.id}'" class="bento-card p-3 flex flex-col cursor-pointer hover:border-blue-500/50 transition-colors h-full relative">
            <div class="flex items-start justify-between mb-2">
                <div class="w-12 h-7 bg-gray-700 rounded overflow-hidden flex-shrink-0"><img src="${p.thumbnail || 'https://picsum.photos/160/90'}" class="w-full h-full object-cover"></div>
                <button onclick="openPlaylist('${p.id}', event)" class="text-[9px] px-1.5 py-0.5 rounded bg-[#20242c] text-gray-400 border border-[#2a2f3a] hover:text-white hover:border-[#374151] transition-colors" title="Open on YouTube"><i class="fa-solid fa-external-link text-[8px] mr-1"></i> YouTube</button>
            </div>
            <h3 class="text-xs font-semibold text-white truncate mb-0.5">${p.title}</h3>
            <p class="text-[9px] text-gray-400 mb-2">${p.video_count} videos</p>
            <div class="flex items-center gap-1 mt-auto pt-1.5 border-t border-[#2a2f3a]" onclick="event.stopPropagation()">
                <button onclick="rescanPlaylist('${p.id}', event)" class="bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-[10px] py-1 px-2.5 rounded transition-colors" title="Rescan Videos"><i class="fa-solid fa-arrows-rotate text-[9px]"></i></button>
                <button onclick="openManagePlaylistModal('${p.id}', \`${p.title.replace(/\'/g, "\\'")}\`, event)" class="flex-1 bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-300 text-[10px] py-1 rounded transition-colors"><i class="fa-solid fa-cog text-[9px]"></i> Manage</button>
            </div>
        </div>
    `).join('');
}

// Open playlist on YouTube
function openPlaylist(playlistId, event) {
    if (event) event.stopPropagation();
    window.open(`https://www.youtube.com/playlist?list=${playlistId}`, '_blank');
}

async function rescanPlaylist(playlistId, event) {
    event.stopPropagation();
    const btn = event.currentTarget;
    const origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-blue-400"></i>';
    
    toast('Rescanning playlist videos...', 'info');
    try {
        const resp = await fetch(`/api/youtube/videos?playlist_id=${playlistId}&force_refresh=true`);
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || 'Failed to refresh playlist videos');
        }

        // Update specific playlist in allPlaylists with new video count
        const playlistIndex = allPlaylists.findIndex(p => p.id === playlistId);
        if (playlistIndex !== -1) {
            allPlaylists[playlistIndex].video_count = data.videos?.length || 0;
        }
        
        toast(`Rescan complete - ${data.videos?.length || 0} videos found`, 'success');
        
        // Re-render all playlists for consistency, which will update the video count badge
        loadPlaylists();
    } catch (e) {
        toast(`Rescan failed: ${DOMPurify.sanitize(e.message)}`, 'error');
        console.error('Rescan failed:', e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHTML;
    }
}

function closeAllMenus() {
    document.querySelectorAll('[id^="menu-"]').forEach(el => el.classList.add('hidden'));
}

function togglePlaylistMenu(playlistId) {
    const menu = document.getElementById(`menu-${playlistId}`);
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
        toast(data.message || data.error, data.status === 'success' ? 'success' : 'error');
        closeAllMenus();
        loadPlaylists();
    } catch (e) {
        toast('Rename failed', 'error');
    }
}

async function duplicatePlaylistPrompt(playlistId) {
    const current = allPlaylists.find(p => p.id === playlistId);
    const newTitle = prompt(`Duplicate playlist: ${current ? current.title : ''}`, `${current ? current.title : 'Playlist'} (copy)`);
    if (newTitle === null || !newTitle.trim()) return;
    try {
        const resp = await fetch('/api/youtube/playlists/duplicate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({playlist_id: playlistId, new_title: newTitle.trim()})
        });
        const data = await resp.json();
        toast(data.message || data.error, data.status === 'success' ? 'success' : 'error');
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
        toast(data.message || data.error, data.status === 'success' ? 'success' : 'error');
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
    window.location.href = `/playlist/${playlistId}`;
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
                    <p class="text-sm font-bold text-white truncate">${playlistTitle}</p>
                </div>
                <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-white p-1 transition-colors"><i class="fa-solid fa-xmark"></i></button>
            </div>
            
            <div class="space-y-2.5">
                <button onclick="actionRenamePlaylist('${playlistId}', \`${playlistTitle.replace(/\'/g, "\\'")}\`); this.closest('.fixed').remove()" class="w-full bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-pen-to-square text-blue-400 w-4 text-center"></i> Rename Playlist
                </button>
                <button onclick="actionDuplicatePlaylist('${playlistId}', \`${playlistTitle.replace(/\'/g, "\\'")}\`); this.closest('.fixed').remove()" class="w-full bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-copy text-green-400 w-4 text-center"></i> Duplicate Playlist
                </button>
                <button onclick="actionDeletePlaylist('${playlistId}', \`${playlistTitle.replace(/\'/g, "\\'")}\`); this.closest('.fixed').remove()" class="w-full bg-red-950/20 hover:bg-red-900/30 border border-red-900/30 text-red-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
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
            toast(res.message, 'success');
            loadPlaylists();
        } else {
            const errorMessage = res.detail || res.error || 'Rename failed';
            toast(`Rename failed: ${DOMPurify.sanitize(errorMessage)}`, 'error');
        }
    } catch (e) {
        toast(`Failed to rename playlist: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        console.error('Rename failed:', e);
    }
}

async function actionDuplicatePlaylist(playlistId, currentTitle) {
    const newTitle = prompt('Duplicate Playlist - Enter name for duplicate:', `${currentTitle} Copy`);
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
            toast(res.message, 'success');
            loadPlaylists();
        } else {
            const errorMessage = res.detail || res.error || 'Duplication failed';
            toast(`Duplication failed: ${DOMPurify.sanitize(errorMessage)}`, 'error');
        }
    } catch (e) {
        toast(`Failed to duplicate playlist: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        console.error('Duplicate failed:', e);
    }
}

async function actionDeletePlaylist(playlistId, title) {
    if (!confirm(`Are you absolutely sure you want to delete '${title}' from YouTube?\n\nThis action cannot be undone.`)) return;
    
    toast('Deleting playlist...', 'info');
    try {
        const resp = await fetch('/api/youtube/playlists/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ playlist_id: playlistId })
        });
        const res = await resp.json();
        if (resp.ok) {
            toast(res.message, 'success');
            loadPlaylists();
        } else {
            const errorMessage = res.detail || res.error || 'Delete failed';
            toast(`Delete failed: ${DOMPurify.sanitize(errorMessage)}`, 'error');
        }
    } catch (e) {
        toast(`Failed to delete playlist: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        console.error('Delete failed:', e);
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
    
    toast('Creating playlist...', 'info');
    try {
        const resp = await fetch('/api/youtube/playlists', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title, description, privacy})
        });
        const result = await resp.json();
        if (resp.ok) {
            toast(`Playlist created: ${result.title || 'New playlist'}`, 'success');
            loadPlaylists();
        } else {
            const errorMessage = result.detail || result.error || 'Failed to create playlist';
            toast(`Failed to create playlist: ${DOMPurify.sanitize(errorMessage)}`, 'error');
        }
    } catch (e) {
        toast(`Failed to create playlist: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        console.error('Create playlist failed:', e);
    }
}

async function syncPlaylists(e) {
    const btn = e.target.closest('button') || e.target;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Syncing...';
    toast('Initiating playlist sync...', 'info');
    try {
        const resp = await fetch('/api/action', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'sync_playlists'})
        });
        const result = await resp.json();
        if (resp.ok) {
            if (result.error) {
                toast(`Sync failed: ${DOMPurify.sanitize(result.error)}`, 'error');
            } else {
                toast(`Playlist sync started`, 'info');
            }
        } else {
            const errorMessage = result.detail || result.error || 'Sync initiation failed';
            toast(`Sync initiation failed: ${DOMPurify.sanitize(errorMessage)}`, 'error');
        }
    } catch (e) {
        toast(`Sync failed: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        console.error(`Sync failed:`, e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-sync"></i> Sync from YouTube';
    }
}

document.addEventListener('DOMContentLoaded', loadPlaylists);