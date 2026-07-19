// playlist.js - Playlist specific scripts

// Upgrade a low-res YouTube thumbnail URL to a higher-res variant (no API cost).
function upgradeThumb(url) {
    if (!url) return url;
    return url.replace(/\/vi\/([^/]+)\/default\.jpg/, '/vi/$1/hqdefault.jpg')
              .replace(/=s\d+(-c)?$/, '=s480');
}

var allVideos = [];
var selectedVideos = new Set();
var playlistId = window.location.pathname.split('/').pop();
var allPlaylists = []; // To populate the dropdown, fetched on load
var currentScanResults = {
    duplicates: [],
    misplaced: []
};

function formatDuration(seconds) {
    seconds = parseInt(seconds) || 0;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return h > 0 ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}` : `${m}:${s.toString().padStart(2, '0')}`;
}

async function rescanPlaylist() {
    const btn = document.getElementById('rescan-playlist-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-[#2f8fc9]"></i> Rescanning...';
    }
    toast('Rescanning playlist videos...', 'info');
    try {
        const resp = await fetch(`/api/youtube/videos?playlist_id=${playlistId}&force_refresh=true`);
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || 'Failed to rescan playlist videos');
        }
        
        allVideos = data.videos || [];
        
        toast(`Rescan complete - ${allVideos.length} videos found`, 'success');
        
        // Update metadata count text with real values and keep privacy status badge
        const currentPlaylist = allPlaylists.find(p => p.id === playlistId);
        const privacyBadge = currentPlaylist ? (currentPlaylist.privacy || 'private') : 'private';
        const badgeColor = privacyBadge === 'public' ? 'bg-green-600/20 text-green-400 border-green-600/30' : 
                           privacyBadge === 'unlisted' ? 'bg-yellow-600/20 text-yellow-400 border-yellow-600/30' : 
                           'bg-gray-600/20 text-gray-400 border-gray-600/30';
        
        const metaEl = document.getElementById('playlist-meta');
        if (metaEl) metaEl.innerHTML = `
            ${allVideos.length} videos • <span class="text-[9px] px-1.5 py-0.5 rounded border uppercase font-bold ${badgeColor}">${privacyBadge}</span>
        `;
        
        renderVideos();
    } catch (e) {
        toast(`Rescan failed: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        console.error('Rescan failed:', e);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-arrows-rotate text-[#2f8fc9]"></i> Rescan Playlist';
        }
    }
}

async function loadPlaylist() {
    const container = document.getElementById('videos-container');
    const skeleton = document.getElementById('videos-skeleton');
    if (skeleton) skeleton.classList.remove('hidden');
    const videosList = document.getElementById('videos-list');
    if (videosList) videosList.classList.add('hidden');
    try {
        // 1. Load playlists list to get metadata (title & privacy) for dropdown and current playlist info
        const plistResp = await fetch('/api/playlists');
        if (plistResp.ok) {
            const plistData = await plistResp.json();
            allPlaylists = plistData.playlists || [];
            
            const currentPlaylist = allPlaylists.find(p => p.id === playlistId);
            if (currentPlaylist) {
                const titleEl = document.getElementById('playlist-title');
                if (titleEl) titleEl.textContent = currentPlaylist.title;
                
                const privacy = currentPlaylist.privacy || 'private';
                const badgeColor = privacy === 'public' ? 'bg-green-600/20 text-green-400 border-green-600/30' : 
                                   privacy === 'unlisted' ? 'bg-yellow-600/20 text-yellow-400 border-yellow-600/30' : 
                                   'bg-gray-600/20 text-gray-400 border-gray-600/30';
                
                const metaEl = document.getElementById('playlist-meta');
                if (metaEl) metaEl.innerHTML = `
                    loading... • <span class="text-[9px] px-1.5 py-0.5 rounded border uppercase font-bold ${badgeColor}">${privacy}</span>
                `;
            }
        }
        
        // 2. Load the videos inside this playlist
        const resp = await fetch(`/api/youtube/videos?playlist_id=${playlistId}`);
        if (!resp.ok) {
            console.error('Videos API error:', resp.status, resp.statusText);
            const container = document.getElementById('videos-container');
            if (container) container.innerHTML = `<div class="text-center p-8 text-red-400">API error: ${resp.status}</div>`;
            return;
        }
        const data = await resp.json();
        if (data.error) {
            console.error('Videos API returned error:', data.error);
            const container = document.getElementById('videos-container');
            if (container) container.innerHTML = `<div class="text-center p-8 text-red-400">${data.error}</div>`;
            return;
        }
        
        allVideos = data.videos || [];

        // 3. Update metadata count text with real values
        const currentPlaylist = allPlaylists.find(p => p.id === playlistId);
        const privacyBadge = currentPlaylist ? (currentPlaylist.privacy || 'private') : 'private';
        const badgeColor = privacyBadge === 'public' ? 'bg-green-600/20 text-green-400 border-green-600/30' : 
                           privacyBadge === 'unlisted' ? 'bg-yellow-600/20 text-yellow-400 border-yellow-600/30' : 
                           'bg-gray-600/20 text-gray-400 border-gray-600/30';
        
        const metaEl = document.getElementById('playlist-meta');
        if (metaEl) metaEl.innerHTML = `
            ${allVideos.length} videos • <span class="text-[9px] px-1.5 py-0.5 rounded border uppercase font-bold ${badgeColor}">${privacyBadge}</span>
        `;
        
        renderVideos();
    } catch (e) {
        console.error('Failed to load playlist:', e);
        toast(`Failed to load playlist: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        const container = document.getElementById('videos-container');
        if (container) container.innerHTML = `<div class="text-center p-8 text-red-400">Failed to load playlist: ${DOMPurify.sanitize(e.message || 'Network error')}</div>`;
    }
}

function renderVideos() {
    const container = document.getElementById('videos-container');
    if (!container) {
        console.error('Videos container not found');
        return;
    }
    if (!allVideos.length) {
        container.innerHTML = '<div class="text-center p-8 text-gray-400">No videos in this playlist</div>';
        return;
    }
    container.innerHTML = `
        <!-- Toolbar -->
        <div class="p-3 border-b border-[#2a2f3a] flex flex-wrap items-center gap-2">
            <div class="flex items-center gap-2 flex-1 min-w-0">
                <span class="text-[10px] text-gray-400 font-medium whitespace-nowrap">${allVideos.length} videos</span>
                <div class="relative flex-1 max-w-sm">
                    <i class="fa-solid fa-search absolute left-2.5 top-1/2 -translate-y-1/2 text-[10px] text-gray-500"></i>
                    <input type="text" id="video-search" placeholder="Search videos..." oninput="filterVideoList()" class="w-full bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-[11px] rounded pl-7 pr-2.5 py-1.5 outline-none focus:border-[#2f8fc9] transition-colors">
                </div>
                <label class="flex items-center gap-1.5 text-[10px] text-gray-400 cursor-pointer select-none">
                    <input type="checkbox" id="select-all-videos" onchange="toggleSelectAll(this)" class="accent-[#2f8fc9]">
                    Select all
                </label>
            </div>
            <select id="target-playlist" onchange="updateMoveButton()" class="bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-[10px] rounded px-2 py-1.5 outline-none min-h-[28px] cursor-pointer">
                <option value="">Move to...</option>
            </select>
            <button id="move-btn" onclick="moveSelectedVideos()" class="hidden bg-[#2f8fc9] hover:bg-[#2a7db8] text-white text-[10px] font-bold px-3 py-1.5 rounded transition-colors flex items-center gap-1.5 cursor-pointer">
                <i class="fa-solid fa-arrow-right-to-bracket"></i> Move
            </button>
            <span id="selected-count" class="text-[10px] text-gray-500 whitespace-nowrap"></span>
        </div>
        <!-- Video grid -->
        <div class="p-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" id="video-grid">
            ${allVideos.map((v, i) => `
                <div class="video-card bg-[#16191f] border border-[#2a2f3a] rounded-xl overflow-hidden hover:border-[#2f8fc9]/50 transition-all flex flex-col group relative" data-video-id="${v.video_id}" data-title="${DOMPurify.sanitize(v.title || '').toLowerCase()}" data-channel="${DOMPurify.sanitize(v.channel_title || '').toLowerCase()}">
                    <div class="relative aspect-video bg-[#0a0c10] overflow-hidden cursor-pointer" onclick="openYouTubeModal('${v.video_id}')">
                        <img src="${v.thumbnail || 'https://i.ytimg.com/vi/' + v.video_id + '/hqdefault.jpg'}" alt="" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy" onerror="this.onerror=null;this.src='https://i.ytimg.com/vi/${v.video_id}/hqdefault.jpg'">
                        <span class="absolute bottom-1.5 right-1.5 bg-black/80 text-white text-[9px] font-mono px-1.5 py-0.5 rounded font-medium">${v.duration || '0:00'}</span>
                        <div class="absolute top-1.5 left-1.5 z-10" onclick="event.stopPropagation()">
                            <input type="checkbox" class="video-checkbox w-4 h-4 rounded accent-[#2f8fc9] cursor-pointer" onchange="toggleVideo('${v.video_id}', this)" ${selectedVideos.has(v.video_id) ? 'checked' : ''} onclick="event.stopPropagation()">
                        </div>
                        <button onclick="deleteSingleVideo('${v.video_id}', event)" class="absolute top-1.5 right-1.5 bg-red-950/80 hover:bg-red-900 border border-red-500/40 text-red-300 hover:text-white text-[10px] w-6 h-6 rounded flex items-center justify-center transition-all opacity-0 group-hover:opacity-100 shadow-md z-10 cursor-pointer" title="Remove video from playlist"><i class="fa-solid fa-trash-can text-[10px]"></i></button>
                        ${selectedVideos.has(v.video_id) ? '<div class="absolute inset-0 border-2 border-[#2f8fc9] rounded-xl pointer-events-none"></div>' : ''}
                    </div>
                    <div class="p-3 flex flex-col flex-1 relative">
                        <h4 class="text-xs font-semibold text-white line-clamp-2 mb-1.5 leading-snug cursor-pointer hover:text-[#2f8fc9] transition-colors pr-6" onclick="openYouTubeModal('${v.video_id}')" title="${DOMPurify.sanitize(v.title || '')}">${DOMPurify.sanitize(v.title || 'Unknown title')}</h4>
                        <p class="text-[10px] text-gray-400 mt-auto truncate">${v.channel_title ? DOMPurify.sanitize(v.channel_title) : ''}</p>
                        <button onclick="openYouTubeModal('${v.video_id}')" class="absolute bottom-2 right-2 bg-black/80 text-white text-[10px] font-mono px-1.5 py-0.5 rounded font-medium hover:bg-black/90 transition-colors" title="Open on YouTube"><i class="fa-solid fa-external-link text-[9px]"></i></button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    loadPlaylistsDropdown();
    updateMoveButton();
}

function filterVideoList() {
    const query = document.getElementById('video-search')?.value?.toLowerCase() || '';
    document.querySelectorAll('.video-card').forEach(card => {
        const title = card.dataset.title || '';
        const channel = card.dataset.channel || '';
        card.style.display = (!query || title.includes(query) || channel.includes(query)) ? '' : 'none';
    });
}

function toggleSelectAll(checkbox) {
    document.querySelectorAll('.video-checkbox').forEach(cb => {
        cb.checked = checkbox.checked;
        const videoId = cb.closest('.video-card')?.dataset?.videoId;
        if (videoId) {
            if (checkbox.checked) selectedVideos.add(videoId);
            else selectedVideos.delete(videoId);
        }
    });
    updateMoveButton();
}

function loadPlaylistsDropdown() {
    const select = document.getElementById('target-playlist');
    if (select) {
        select.innerHTML = '<option value="">Move to...</option>' +
            allPlaylists.filter(p => p.id !== playlistId).map(p => `<option value="${p.id}">${DOMPurify.sanitize(p.title)}</option>`).join('');
    }
}

function toggleVideo(videoId, checkbox) {
    if (checkbox.checked) {
        selectedVideos.add(videoId);
    } else {
        selectedVideos.delete(videoId);
    }
    // Update visual selection border on card
    document.querySelectorAll(`.video-card[data-video-id="${videoId}"]`).forEach(card => {
        const border = card.querySelector('.selected-border');
        if (checkbox.checked) {
            if (!border) {
                const el = document.createElement('div');
                el.className = 'selected-border absolute inset-0 border-2 border-[#2f8fc9] rounded-xl pointer-events-none';
                card.querySelector('.relative.aspect-video').appendChild(el);
            }
        } else {
            border?.remove();
        }
        const topCheckbox = card.querySelector('.video-checkbox');
        if (topCheckbox) topCheckbox.checked = checkbox.checked;
    });
    // Sync the "Select all" checkbox
    const selectAll = document.getElementById('select-all-videos');
    if (selectAll) {
        const allCbs = document.querySelectorAll('.video-checkbox');
        selectAll.checked = allCbs.length > 0 && Array.from(allCbs).every(cb => cb.checked);
    }
    updateMoveButton();
}

function updateMoveButton() {
    const moveBtn = document.getElementById('move-btn');
    const countEl = document.getElementById('selected-count');
    if (countEl) {
        countEl.textContent = selectedVideos.size > 0 ? `${selectedVideos.size} selected` : '';
    }
    if (moveBtn) {
        const targetPlaylistSelected = document.getElementById('target-playlist')?.value;
        moveBtn.classList.toggle('hidden', selectedVideos.size === 0 || !targetPlaylistSelected);
        moveBtn.disabled = selectedVideos.size === 0 || !targetPlaylistSelected;
    }
}

async function moveSelectedVideos() {
    const targetId = document.getElementById('target-playlist')?.value;
    if (!targetId || selectedVideos.size === 0) {
        toast('Please select videos and a target playlist', 'error');
        return;
    }
    const videoIds = Array.from(selectedVideos);
    toast(`Moving ${videoIds.length} video(s)...`, 'info');
    try {
        const resp = await fetch('/api/bulk/move', {
            method: 'POST',
            headers: await authHeaders(),
            body: JSON.stringify({video_ids: videoIds, target_playlist_id: targetId, source_playlist_id: playlistId})
        });
        const result = await resp.json();
        if (resp.ok && (result.operation_id || result.status === 'pending' || result.status === 'completed' || result.status === 'success' || result.succeeded > 0)) {
            toast(`Moved ${videoIds.length} video(s) successfully`, 'success');
            selectedVideos.clear();
            updateMoveButton();
            setTimeout(async () => {
                await loadPlaylist();
            }, 1500);
        } else {
            const errorMessage = result.error || result.detail || resp.statusText || 'Failed to move videos';
            toast(`Failed to move videos: ${DOMPurify.sanitize(errorMessage)}`, 'error');
        }
    } catch (e) {
        toast(`Network error: Failed to move videos: ${DOMPurify.sanitize(e.message || 'Unknown error')}`, 'error');
        console.error('Move videos error:', e);
    }
}

// Scan functions
async function scanForDuplicates() {
    const btn = document.getElementById('btn-scan-dup');
    const origHTML = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-[#2f8fc9]"></i> Scanning...';
    }
    
    try {
        const videoIdToItems = {};
        allVideos.forEach(v => {
            if (!videoIdToItems[v.video_id]) {
                videoIdToItems[v.video_id] = [];
            }
            videoIdToItems[v.video_id].push({
                playlist_item_id: v.playlist_item_id,
                title: v.title,
                channel: v.channel_title,
                thumbnail: v.thumbnail
            });
        });

        currentScanResults.duplicates = [];
        for (const video_id in videoIdToItems) {
            const items = videoIdToItems[video_id];
            if (items.length > 1) {
                const itemsToDelete = items.slice(1);
                itemsToDelete.forEach(item => {
                    currentScanResults.duplicates.push({
                        video_id: video_id,
                        playlist_item_id: item.playlist_item_id,
                        title: item.title,
                        channel: item.channel,
                        thumbnail: item.thumbnail,
                        reason: `Duplicate entry (${items.length} occurrences)`,
                        type: 'duplicate'
                    });
                });
            }
        }

        toast(`Scan complete - ${currentScanResults.duplicates.length} duplicate video(s) found in this playlist`, 'success');
        showScanBox('duplicates');
    } catch (e) {
        toast('Scan failed: ' + e.message, 'error');
        console.error(e);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHTML;
        }
    }
}

async function scanForMisplaced() {
    const btn = document.getElementById('btn-scan-mis');
    const origHTML = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-yellow-500"></i> Scanning...';
    }
    
    try {
        let misplacedList = [];

        // 1. Try server maintenance cache first
        try {
            const resp = await fetch(`/api/youtube/misplaced?playlist_id=${playlistId}`);
            if (resp.ok) {
                const result = await resp.json();
                if (Array.isArray(result.misplaced) && result.misplaced.length > 0) {
                    misplacedList = result.misplaced.map(v => ({
                        video_id: v.video_id || '',
                        title: v.video_title || v.title || 'Untitled Video',
                        channel: v.channel || '',
                        thumbnail: v.video_id ? `https://i.ytimg.com/vi/${v.video_id}/hqdefault.jpg` : '',
                        reason: v.reason || 'Misplaced channel',
                        type: 'misplaced',
                        current_playlist_id: playlistId,
                        current_playlist_title: document.getElementById('playlist-title')?.textContent || playlistId,
                        mapped_playlist_id: v.mapped_playlist_id || '',
                        mapped_playlist_title: v.mapped_playlist_title || v.mapped_playlist_id || ''
                    }));
                }
            }
        } catch (err) {
            console.warn('Server misplaced cache fetch warning:', err);
        }

        // 2. Client-side fallback check against Channel Mappings if server cache yielded no items
        if (misplacedList.length === 0 && allVideos.length > 0) {
            try {
                const mapResp = await fetch('/api/mappings');
                if (mapResp.ok) {
                    const mapData = await mapResp.json();
                    const mappings = mapData.mappings || {};
                    const titles = mapData.playlist_titles || {};

                    allVideos.forEach(v => {
                        const channelId = v.channel_id;
                        if (channelId && mappings[channelId]) {
                            const targetPlId = mappings[channelId];
                            if (targetPlId && targetPlId !== playlistId) {
                                misplacedList.push({
                                    video_id: v.video_id || '',
                                    title: v.title || 'Untitled Video',
                                    channel: v.channel_title || '',
                                    thumbnail: v.thumbnail || '',
                                    reason: `Channel mapped to another playlist`,
                                    type: 'misplaced',
                                    current_playlist_id: playlistId,
                                    current_playlist_title: document.getElementById('playlist-title')?.textContent || playlistId,
                                    mapped_playlist_id: targetPlId,
                                    mapped_playlist_title: titles[targetPlId] || targetPlId
                                });
                            }
                        }
                    });
                }
            } catch (err) {
                console.warn('Live mappings fallback check warning:', err);
            }
        }

        currentScanResults.misplaced = misplacedList;
        toast(`Scan complete - ${currentScanResults.misplaced.length} misplaced video(s) found in this playlist`, 'success');
        showScanBox('misplaced');
    } catch (e) {
        console.error('Error fetching misplaced videos:', e);
        toast(`Failed to fetch misplaced videos: ${e.message || 'Error'}`, 'error');
        currentScanResults.misplaced = [];
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = origHTML;
        }
    }
}

function showScanBox(defaultFilter) {
    const box = document.getElementById('scan-results-box');
    if (!box) return;
    box.classList.remove('hidden');

    const filterSelect = document.getElementById('scan-filter');
    if (filterSelect) filterSelect.value = defaultFilter || 'all';
    
    updateScanSummary();
    filterScanResults();

    const deleteBtn = document.getElementById('delete-duplicates-btn');
    if (deleteBtn) {
        deleteBtn.classList.toggle('hidden', currentScanResults.duplicates.length === 0);
    }
    const moveMisplacedBtn = document.getElementById('move-misplaced-btn');
    if (moveMisplacedBtn) {
        moveMisplacedBtn.classList.toggle('hidden', currentScanResults.misplaced.length === 0);
    }
}

function updateScanSummary() {
    const summary = document.getElementById('scan-results-summary');
    if (!summary) return;
    const dupCount = currentScanResults.duplicates.length;
    const misCount = currentScanResults.misplaced.length;
    summary.textContent = `${dupCount} Duplicates • ${misCount} Misplaced`;
}

function filterScanResults() {
    const filterSelect = document.getElementById('scan-filter');
    const listEl = document.getElementById('scan-results-list');
    if (!listEl) return;
    const filterValue = filterSelect ? filterSelect.value : 'all';
    
    let displayList = [];
    if (filterValue === 'all') {
        displayList = [...currentScanResults.duplicates, ...currentScanResults.misplaced];
    } else if (filterValue === 'duplicates') {
        displayList = currentScanResults.duplicates;
    } else if (filterValue === 'misplaced') {
        displayList = currentScanResults.misplaced;
    }
    
    if (displayList.length === 0) {
        listEl.innerHTML = `<div class="text-center py-4 text-gray-500 text-[10px]">No ${filterValue === 'all' ? 'issues' : filterValue} detected.</div>`;
        return;
    }
    
    listEl.innerHTML = displayList.map(item => {
        const isDup = item.type === 'duplicate';
        const badgeColor = isDup ? 'bg-[#2f8fc9]/10 text-[#2f8fc9] border-[#2f8fc9]/20' : 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
        const badgeLabel = isDup ? 'DUPLICATE' : 'MISPLACED';
        const icon = isDup ? 'fa-copy' : 'fa-triangle-exclamation';

        const safeTitle = DOMPurify.sanitize(String(item.title || 'Untitled Video'));
        const safeChannel = item.channel ? DOMPurify.sanitize(String(item.channel)) + ' • ' : '';
        const safeReason = DOMPurify.sanitize(String(item.reason || 'Misplaced channel'));
        const safeTargetPl = DOMPurify.sanitize(String(item.mapped_playlist_title || item.mapped_playlist_id || 'Other Playlist'));

        let additionalInfo = '';
        if (item.type === 'misplaced') {
            additionalInfo = `\n<div class="text-[9px] text-gray-500 mt-1.5 flex items-center gap-1.5">
                <i class="fa-solid fa-arrow-right-long"></i> 
                Move to: <span class="font-medium text-[#5ba5d6]">${safeTargetPl}</span>
            </div>`;
        }

        return `
            <div class="relative flex items-start gap-3 p-2 bg-[#1a1d24] border border-[#2a2f3a] rounded-lg">
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${badgeColor}"><i class="fa-solid ${icon} mr-1"></i>${badgeLabel}</span>
                <div class="flex-1 min-w-0 pr-8">
                    <div class="font-semibold text-white truncate text-[11px]">${safeTitle}</div>
                    <div class="text-[10px] text-gray-400 truncate">${safeChannel}ID: ${item.video_id || ''}</div>
                    <div class="text-[10px] text-gray-400 mt-1 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full ${isDup ? 'bg-[#2f8fc9]' : 'bg-yellow-500'}"></span><span>Reason: ${safeReason}</span></div>
                    ${additionalInfo}
                </div>
                <button onclick="openYouTubeModal('${item.video_id}')" class="absolute bottom-1.5 right-1.5 bg-black/80 text-white text-[10px] font-mono px-1.5 py-0.5 rounded font-medium hover:bg-black/90 transition-colors" title="Open on YouTube"><i class="fa-solid fa-external-link text-[9px]"></i></button>
            </div>
        `;
    }).join('');

    // Enable/disable action buttons based on displayed results
    const deleteDupBtn = document.getElementById('delete-duplicates-btn');
    if (deleteDupBtn) {
        deleteDupBtn.classList.toggle('hidden', currentScanResults.duplicates.length === 0);
    }
    const moveMisplacedBtn = document.getElementById('move-misplaced-btn');
    if (moveMisplacedBtn) {
        moveMisplacedBtn.classList.toggle('hidden', currentScanResults.misplaced.length === 0);
    }
}

async function deleteDuplicateItems() {
    const btn = document.getElementById('delete-duplicates-btn');
    console.debug('[DUP-DELETE] button:', btn, 'scanResults:', currentScanResults?.duplicates?.length);
    console.debug('[DUP-DELETE] duplicates array:', currentScanResults.duplicates);
    console.debug('[DUP-DELETE] playlistId:', playlistId);
    
    if (!btn) { 
        console.error('[DUP-DELETE] Delete button not found');
        toast('Delete duplicates button not found', 'error'); 
        return; 
    }
    if (!confirm(`Are you sure you want to delete ${currentScanResults?.duplicates?.length || 0} duplicate videos from this playlist? This action cannot be undone.`)) return;
    if (!currentScanResults.duplicates.length) return;

    toast(`Deleting ${currentScanResults.duplicates.length} duplicates...`, 'info');
    const videoIds = currentScanResults.duplicates.map(item => item.video_id).filter(Boolean);
    console.debug('[DUP-DELETE] extracted videoIds:', videoIds);
    
    if (!videoIds.length) {
        console.error('[DUP-DELETE] No valid video ids to delete');
        toast('No valid video ids to delete', 'error');
        return;
    }

    try {
        console.debug('[DUP-DELETE] Making request to /api/bulk/delete with:', {playlist_id: playlistId, video_ids: videoIds});
        const resp = await fetch('/api/bulk/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({playlist_id: playlistId, video_ids: videoIds})
        });
        console.debug('[DUP-DELETE] Response status:', resp.status);
        const result = await resp.json();
        console.debug('[DUP-DELETE] Response body:', result);
        
        if (resp.ok) {
            toast(`Deleted duplicates successfully`, 'success');
            currentScanResults.duplicates = [];
            await loadPlaylist();
        } else {
            console.error('[DUP-DELETE] API error:', result);
            toast(`Failed to delete duplicates: ${DOMPurify.sanitize(result.error || resp.statusText || 'Unknown error')}`, 'error');
        }
    } catch (e) {
        console.error('[DUP-DELETE] Network error:', e);
        toast(`Network error: Failed to delete duplicates: ${DOMPurify.sanitize(e.message || 'Unknown error')}`, 'error');
    } finally {
        showScanBox(document.getElementById('scan-filter').value);
 await loadPlaylist();
    }
}

async function moveMisplacedItems() {
    if (!confirm(`Are you sure you want to move ${currentScanResults.misplaced.length} misplaced videos to their mapped playlists? This action cannot be undone.`)) return;

    toast(`Moving ${currentScanResults.misplaced.length} misplaced videos...`, 'info');
    const moveOperations = currentScanResults.misplaced.map(item => ({
        video_id: item.video_id,
        target_playlist_id: item.mapped_playlist_id,
        source_playlist_id: playlistId // Current playlist is the source
    }));

    try {
        // Bulk move API expects individual video_ids and a single target_playlist_id.
        // We need to group by target_playlist_id and make multiple calls if videos go to different destinations.
        const groupedMoves = {};
        moveOperations.forEach(op => {
            if (!groupedMoves[op.target_playlist_id]) {
                groupedMoves[op.target_playlist_id] = [];
            }
            groupedMoves[op.target_playlist_id].push(op.video_id);
        });

        let succeededMoves = 0;
        let failedMoves = 0;

        for (const targetPlaylistId in groupedMoves) {
            const videoIdsToMove = groupedMoves[targetPlaylistId];
            const resp = await fetch('/api/bulk/move', {
                method: 'POST',
                headers: await authHeaders(),
                body: JSON.stringify({
                    video_ids: videoIdsToMove,
                    target_playlist_id: targetPlaylistId,
                    source_playlist_id: playlistId
                })
            });
            const result = await resp.json();
            if (resp.ok && (result.operation_id || result.status === 'pending' || result.status === 'completed' || result.status === 'success' || result.succeeded > 0)) {
                succeededMoves += videoIdsToMove.length;
            } else {
                failedMoves += videoIdsToMove.length;
                const errorMessage = result.error || result.detail || resp.statusText || 'Failed to move videos';
                console.error(`Failed to move to ${targetPlaylistId}: ${errorMessage}`);
                toast(`Failed to move videos to ${targetPlaylistId}: ${DOMPurify.sanitize(errorMessage)}`, 'error');
            }
        }

        toast(`Moved ${succeededMoves} video(s), failed ${failedMoves}`, 'success');
        currentScanResults.misplaced = []; // Clear misplaced after successful moves
        await loadPlaylist(); // Refresh playlist and re-run scan to update UI
    } catch (e) {
        toast(`Network error: Failed to move misplaced videos: ${DOMPurify.sanitize(e.message || 'Unknown error')}`, 'error');
        console.error('Move misplaced error:', e);
    } finally {
        showScanBox(document.getElementById('scan-filter').value); // Re-render scan results
    }
}

// Event listeners
async function initPlaylistPage() {
    // Load global scripts here if not already in head
    // const script = document.createElement('script');
    // script.src = '/static/global_scripts.js';
    // document.head.appendChild(script);

    await loadPlaylist();
    
    document.getElementById('rescan-playlist-btn')?.addEventListener('click', rescanPlaylist);
    document.getElementById('btn-scan-dup')?.addEventListener('click', scanForDuplicates);
    document.getElementById('btn-scan-mis')?.addEventListener('click', scanForMisplaced);
    document.getElementById('delete-duplicates-btn')?.addEventListener('click', deleteDuplicateItems);
    document.getElementById('move-misplaced-btn')?.addEventListener('click', moveMisplacedItems);
    document.getElementById('scan-filter')?.addEventListener('change', filterScanResults);

    // Back to playlists button
    document.querySelector('.back-to-playlists-btn')?.addEventListener('click', () => {
        window.location.href = '/playlists';
    });
}

// DOMContentLoaded may have already fired (SPA navigation). Run init either way.
// SPA-safe init: retry if script hasn't loaded yet (SPA fires DOMContentLoaded before external scripts finish)
function safeInitPlaylistPage() {
    if (typeof initPlaylistPage === 'function') {
        initPlaylistPage();
    } else {
        setTimeout(safeInitPlaylistPage, 100);
    }
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', safeInitPlaylistPage);
} else {
    safeInitPlaylistPage();
}



// YouTube modal functions
let youtubeModal = null;

function openYouTubeModal(videoId) {
    if (youtubeModal) {
        youtubeModal.remove();
        youtubeModal = null;
    }
    
    // Create modal overlay
    youtubeModal = document.createElement('div');
    youtubeModal.className = 'fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm';
    youtubeModal.innerHTML = `
        <div class="bg-[#1a1d24] border border-[#2a2f3a] rounded-xl w-full max-w-4xl mx-4 shadow-2xl overflow-hidden">
            <div class="flex items-center justify-between p-4 border-b border-[#2a2f3a]">
                <h3 class="text-white font-semibold">YouTube Video</h3>
                <button onclick="this.closest('.fixed').remove(); youtubeModal = null" class="text-gray-400 hover:text-white p-2 transition-colors">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
            <div class="aspect-video bg-black">
                <iframe 
                    src="https://www.youtube.com/embed/${videoId}" 
                    frameborder="0" 
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                    allowfullscreen
                    class="w-full h-full">
                </iframe>
            </div>
        </div>
    `;
    
    youtubeModal.onclick = function(e) {
        if (e.target === youtubeModal) {
            youtubeModal.remove();
            youtubeModal = null;
        }
    };
    
    document.body.appendChild(youtubeModal);
}

async function deleteSingleVideo(videoId, event) {
    if (event) event.stopPropagation();
    if (!confirm('Remove this video from the playlist?')) return;
    toast('Removing video...', 'info');
    try {
        const targetVideo = allVideos.find(v => v.video_id === videoId);
        const playlistItemId = targetVideo ? targetVideo.playlist_item_id : null;
        const resp = await fetch('/api/youtube/playlistitems/delete', {
            method: 'POST',
            headers: await authHeaders(),
            body: JSON.stringify({ playlist_id: playlistId, video_id: videoId, playlist_item_id: playlistItemId })
        });
        const data = await resp.json();
        if (resp.ok && (data.status === 'success' || data.success)) {
            toast('Video removed successfully', 'success');
            allVideos = allVideos.filter(v => v.video_id !== videoId);
            renderVideos();
        } else {
            toast('Failed to remove video: ' + (data.detail || data.error || 'Unknown error'), 'error');
        }
    } catch (e) {
        toast('Failed to remove video: ' + e.message, 'error');
    }
}
