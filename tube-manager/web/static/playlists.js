// playlists.js - Playlists specific scripts

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
        if (!resp.ok) throw new Error('Failed to refresh');
        const data = await resp.json();
        // Instead of directly assigning allVideos, update specific playlist in allPlaylists
        const playlistIndex = allPlaylists.findIndex(p => p.id === playlistId);
        if (playlistIndex !== -1) {
            allPlaylists[playlistIndex].video_count = data.videos?.length || 0;
        }
        
        toast(`Rescan complete - ${data.videos?.length || 0} videos found`, 'success');
        
        // Re-render only necessary parts or refresh all playlists for consistency
        loadPlaylists();
    } catch (e) {
        toast('Rescan failed', 'error');
        console.error(e);
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
            toast(res.detail || 'Rename failed', 'error');
        }
    } catch (e) {
        toast('Failed to rename playlist', 'error');
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
            toast(res.detail || 'Duplication failed', 'error');
        }
    } catch (e) {
        toast('Failed to duplicate playlist', 'error');
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
            toast(res.detail || 'Delete failed', 'error');
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
        const resp = await fetch('/api/youtube/playlists', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title, description, privacy})
        });
        const result = await resp.json();
        toast(`Playlist created: ${result.title || 'New playlist'}`, 'success');
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
            toast(`Sync failed: ${result.error}`, 'error');
        } else {
            toast(`Playlist sync started`, 'info');
        }
    } catch (e) {
        toast(`Sync failed: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-sync"></i> Sync from YouTube';
    }
}

document.addEventListener('DOMContentLoaded', loadPlaylists);