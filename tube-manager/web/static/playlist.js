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

let allVideos = [];
let selectedVideos = new Set();
let playlistId = window.location.pathname.split('/').pop();
let allPlaylists = []; // To store playlists for dropdown
let currentScanResults = {
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
    const activityLog = document.getElementById('activity-task-desc'); // Use existing activity element
    if (activityLog) activityLog.textContent = 'Rescanning playlist...';
    const btn = document.getElementById('rescan-playlist-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-blue-400"></i> Rescanning...';
    }
    toast('Rescanning playlist videos...', 'info');
    try {
        const resp = await fetch(`/api/youtube/videos?playlist_id=${DOMPurify.sanitize(playlistId)}&force_refresh=true`);
        const data = await resp.json();
        allVideos = data.videos || [];
        
        toast(`Rescan complete - ${DOMPurify.sanitize(allVideos.length)} videos found`, 'success');
        
        // Update metadata count text with real values and keep privacy status badge
        const currentPlaylist = allPlaylists.find(p => p.id === playlistId);
        const privacyBadge = currentPlaylist ? (currentPlaylist.privacy || 'private') : 'private';
        const badgeColor = privacyBadge === 'public' ? 'bg-green-600/20 text-green-400 border-green-600/30' : 
                           privacyBadge === 'unlisted' ? 'bg-yellow-600/20 text-yellow-400 border-yellow-600/30' : 
                           'bg-gray-600/20 text-gray-400 border-gray-600/30';
        
        const metaEl = document.getElementById('playlist-meta');
        if (metaEl) metaEl.innerHTML = `
            ${DOMPurify.sanitize(allVideos.length)} videos • <span class="text-[9px] px-1.5 py-0.5 rounded border uppercase font-bold ${badgeColor}">${DOMPurify.sanitize(privacyBadge)}</span>
        `;
        
        renderVideos();
        if (activityLog) activityLog.textContent = 'Rescan complete.';
    } catch (e) {
        console.error(e);
        toast('Rescan failed', 'error');
        if (activityLog) activityLog.textContent = 'Rescan failed.';
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa-solid fa-arrows-rotate text-blue-400"></i> Rescan Playlist';
        }
    }
}

async function loadPlaylist() {
    try {
        // 1. Load playlists list to get metadata (title & privacy)
        const plistResp = await fetch('/api/playlists');
        if (plistResp.ok) {
            const plistData = await plistResp.json();
            allPlaylists = plistData.playlists || [];
            
            const currentPlaylist = allPlaylists.find(p => p.id === playlistId);
            if (currentPlaylist) {
                const titleEl = document.getElementById('playlist-title');
                if (titleEl) titleEl.textContent = DOMPurify.sanitize(currentPlaylist.title);
                
                const privacy = currentPlaylist.privacy || 'private';
                const badgeColor = privacy === 'public' ? 'bg-green-600/20 text-green-400 border-green-600/30' : 
                                   privacy === 'unlisted' ? 'bg-yellow-600/20 text-yellow-400 border-yellow-600/30' : 
                                   'bg-gray-600/20 text-gray-400 border-gray-600/30';
                
                const metaEl = document.getElementById('playlist-meta');
                if (metaEl) metaEl.innerHTML = `
                    loading... • <span class="text-[9px] px-1.5 py-0.5 rounded border uppercase font-bold ${badgeColor}">${DOMPurify.sanitize(privacy)}</span>
                `;
            }
        }
        
        // 2. Load the videos inside this playlist
        const resp = await fetch(`/api/youtube/videos?playlist_id=${DOMPurify.sanitize(playlistId)}`);
        if (!resp.ok) {
            console.error('Videos API error:', resp.status, resp.statusText);
            const container = document.getElementById('videos-container');
            if (container) container.innerHTML = `<div class="text-center p-8 text-red-400">API error: ${DOMPurify.sanitize(resp.statusText)}</div>`;
            return;
        }
        const data = await resp.json();
        if (data.error) {
            console.error('Videos API returned error:', data.error);
            const container = document.getElementById('videos-container');
            if (container) container.innerHTML = `<div class="text-center p-8 text-red-400">${DOMPurify.sanitize(data.error)}</div>`;
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
            ${DOMPurify.sanitize(allVideos.length)} videos • <span class="text-[9px] px-1.5 py-0.5 rounded border uppercase font-bold ${badgeColor}">${DOMPurify.sanitize(privacyBadge)}</span>
        `;
        
        renderVideos();
    } catch (e) {
        console.error(e);
        const container = document.getElementById('videos-container');
        if (container) container.innerHTML = '<div class="text-center p-8 text-red-400">Failed to load playlist</div>';
    }
}

function renderVideos() {
    const container = document.getElementById('videos-container');
    if (!allVideos.length) {
        container.innerHTML = '<div class="text-center p-8 text-gray-400">No videos in this playlist</div>';
        return;
    }
    container.innerHTML = `
        <div class="p-3 border-b border-[#2a2f3a] flex items-center justify-between">
            <span class="text-[10px] text-gray-400">Select videos to move (click checkboxes)</span>
            <select id="target-playlist" class="bg-[#20242c] border border-[#2a2f3a] text-gray-300 text-[10px] rounded px-2 py-1 outline-none">
                <option value="">Select target playlist...</option>
            </select>
        </div>
        ${allVideos.map((v, i) => `
            <div class="video-row flex items-center gap-2 py-1" data-video-id="${DOMPurify.sanitize(v.video_id)}">
                <input type="checkbox" class="video-checkbox w-4 h-4 rounded" data-video-id="${DOMPurify.sanitize(v.video_id)}">
                <img src="${DOMPurify.sanitize(v.thumbnail || 'https://picsum.photos/160/90')}" class="w-24 h-14 rounded object-cover flex-shrink-0">
                <div class="flex-1 min-w-0">
                    <div class="text-[11px] text-white truncate">${DOMPurify.sanitize(v.title || 'Unknown title')}</div>
                    <div class="text-[9px] text-gray-400">${DOMPurify.sanitize(v.channel_title || 'Unknown channel')}</div>
                </div>
                <span class="text-[9px] text-gray-300 font-mono bg-[#20242c] px-1.5 py-0.5 rounded">${formatDuration(v.duration)}</span>
                <span class="text-[9px] text-gray-500 w-12 text-right">${DOMPurify.sanitize(i + 1)}</span>
            </div>
        `).join('')}
    `;
    loadPlaylistsDropdown();
}

function loadPlaylistsDropdown() {
    const select = document.getElementById('target-playlist');
    if (select) {
        select.innerHTML = '<option value="">Select target playlist...</option>' + 
            allPlaylists.map(p => `<option value="${DOMPurify.sanitize(p.id)}">${DOMPurify.sanitize(p.title)}</option>`).join('');
    }
}

function toggleVideo(videoId, checkbox) {
    if (checkbox.checked) {
        selectedVideos.add(videoId);
    } else {
        selectedVideos.delete(videoId);
    }
    updateMoveButton();
}

function updateMoveButton() {
    const moveBtn = document.getElementById('move-btn');
    moveBtn.classList.toggle('hidden', selectedVideos.size === 0);
}

async function moveSelectedVideos() {
    const targetId = document.getElementById('target-playlist').value;
    if (!targetId || selectedVideos.size === 0) {
        toast('Please select videos and target playlist', 'error');
        return;
    }
    const videoIds = Array.from(selectedVideos);
    try {
        const resp = await fetch('/api/bulk/move', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({video_ids: videoIds, target_playlist_id: targetId, source_playlist_id: playlistId})
        });
        const result = await resp.json();
        toast(`Moved ${DOMPurify.sanitize(videoIds.length)} videos`, 'success');
        selectedVideos.clear();
        updateMoveButton();
        loadPlaylist();
    } catch (e) {
        toast('Failed to move videos', 'error');
    }
}

async function performFullScan() {
    // 1. Client-side duplicate detection
    const videoIdToItems = {};
    allVideos.forEach(v => {
        if (!videoIdToItems[v.video_id]) {
            videoIdToItems[v.video_id] = [];
        }
        videoIdToItems[v.video_id].push({
            playlist_item_id: v.playlist_item_id,
            title: v.title,
            channel: v.channel_title
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
                    reason: `Duplicate entry (${items.length} occurrences)`,
                    type: 'duplicate'
                });
            });
        }
    }

    // 2. Misplaced detection via API
    const resp = await fetch(`/api/youtube/misplaced?playlist_id=${DOMPurify.sanitize(playlistId)}`);
    if (!resp.ok) throw new Error('Misplaced API failed');
    const result = await resp.json();
    
    currentScanResults.misplaced = (result.misplaced || []).map(v => ({
        video_id: v.video_id,
        title: v.title,
        channel: v.channel || '',
        reason: v.reason || 'Misplaced channel',
        type: 'misplaced'
    }));
}

async function scanForDuplicates() {
    const btn = document.getElementById('btn-scan-dup');
    const origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-blue-400"></i> Scanning...';
    
    toast(`Scanning playlist for duplicates and misplaced videos...`, 'info');
    try {
        await performFullScan();
        toast(`Scan complete - ${DOMPurify.sanitize(currentScanResults.duplicates.length)} duplicates, ${DOMPurify.sanitize(currentScanResults.misplaced.length)} misplaced found`, 'success');
        showScanBox('duplicates');
    } catch (e) {
        toast('Scan failed', 'error');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHTML;
    }
}

async function scanForMisplaced() {
    const btn = document.getElementById('btn-scan-mis');
    const origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-yellow-500"></i> Scanning...';
    
    toast(`Scanning playlist for duplicates and misplaced videos...`, 'info');
    try {
        await performFullScan();
        toast(`Scan complete - ${DOMPurify.sanitize(currentScanResults.duplicates.length)} duplicates, ${DOMPurify.sanitize(currentScanResults.misplaced.length)} misplaced found`, 'success');
        showScanBox('misplaced');
    } catch (e) {
        toast('Scan failed', 'error');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHTML;
    }
}

function showScanBox(defaultFilter) {
    const box = document.getElementById('scan-results-box');
    box.classList.remove('hidden');
    
    const filterSelect = document.getElementById('scan-filter');
    filterSelect.value = defaultFilter || 'all';
    
    updateScanSummary();
    filterScanResults();

    // Show/hide the delete duplicates button
    const deleteBtn = document.getElementById('delete-duplicates-btn');
    if (deleteBtn) {
        deleteBtn.classList.toggle('hidden', currentScanResults.duplicates.length === 0);
    }
}

function updateScanSummary() {
    const summary = document.getElementById('scan-results-summary');
    const dupCount = currentScanResults.duplicates.length;
    const misCount = currentScanResults.misplaced.length;
    summary.textContent = `${DOMPurify.sanitize(dupCount)} Duplicates • ${DOMPurify.sanitize(misCount)} Misplaced`;
}

function filterScanResults() {
    const filterValue = document.getElementById('scan-filter').value;
    const listEl = document.getElementById('scan-results-list');
    
    let displayList = [];
    if (filterValue === 'all') {
        displayList = [...currentScanResults.duplicates, ...currentScanResults.misplaced];
    } else if (filterValue === 'duplicates') {
        displayList = currentScanResults.duplicates;
    } else if (filterValue === 'misplaced') {
        displayList = currentScanResults.misplaced;
    }
    
    if (displayList.length === 0) {
        listEl.innerHTML = `<div class="text-center py-4 text-gray-500 text-[10px]">No ${DOMPurify.sanitize(filterValue === 'all' ? 'issues' : filterValue)} detected.</div>`;
        return;
    }
    
    listEl.innerHTML = displayList.map(item => {
        const isDup = item.type === 'duplicate';
        const badgeColor = isDup ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20';
        const badgeLabel = isDup ? 'DUPLICATE' : 'MISPLACED';
        const icon = isDup ? 'fa-copy' : 'fa-triangle-exclamation';
        
        return `
            <div class="flex items-start gap-3 p-2 bg-[#1a1d24] border border-[#2a2f3a] rounded-lg">
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${badgeColor}"><i class="fa-solid ${icon} mr-1"></i>${badgeLabel}</span>
                <div class="flex-1 min-w-0">
                    <div class="font-semibold text-white truncate text-[11px]">${DOMPurify.sanitize(item.title)}</div>
                    <div class="text-[10px] text-gray-400 truncate">${DOMPurify.sanitize(item.channel ? item.channel + ' • ' : '')}ID: ${DOMPurify.sanitize(item.video_id)}</div>
                    <div class="text-[10px] text-gray-400 mt-1 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full ${isDup ? 'bg-blue-400' : 'bg-yellow-500'}"></span><span>Reason: ${DOMPurify.sanitize(item.reason)}</span></div>
                </div>
            </div>
        `;
    }).join('');
}

async function deleteDuplicateItems() {
    const itemsToDelete = currentScanResults.duplicates;
    if (itemsToDelete.length === 0) {
        toast('No duplicates to delete', 'info');
        return;
    }

    if (!confirm(`Are you sure you want to delete ${itemsToDelete.length} duplicate video entries from this playlist? This cannot be undone.`)) {
        return;
    }

    const activityLog = document.getElementById('activity-task-desc'); // Corrected ID
    if (activityLog) activityLog.textContent = `Deleting ${itemsToDelete.length} duplicates...`;
    toast(`Deleting ${itemsToDelete.length} duplicates...`, 'info');
    
    let successCount = 0;
    let errorCount = 0;

    for (const item of itemsToDelete) {
        try {
            const resp = await fetch('/api/youtube/playlistitems/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    playlist_item_id: item.playlist_item_id,
                    playlist_id: playlistId
                })
            });
            if (resp.ok) {
                successCount++;
            } else {
                errorCount++;
            }
        } catch (e) {
            errorCount++;
            console.error('Failed to delete item', item.playlist_item_id, e);
        }
    }

    if (errorCount > 0) {
        toast(`${successCount} duplicates deleted, but ${errorCount} failed.`, 'warning');
    } else {
        toast(`Successfully deleted ${successCount} duplicates.`, 'success');
    }

    if (activityLog) activityLog.textContent = 'Duplicate deletion complete.';

    // Hide the scan box and rescan the playlist to show the cleaned list
    const box = document.getElementById('scan-results-box');
    if(box) box.classList.add('hidden');
    rescanPlaylist();
}

document.addEventListener('DOMContentLoaded', () => {
    loadPlaylist();

    // Event listeners for top-level buttons
    document.querySelector('.back-to-playlists-btn')?.addEventListener('click', () => {
        window.location.href = '/playlists';
    });
    document.getElementById('move-btn')?.addEventListener('click', moveSelectedVideos);
    document.getElementById('rescan-playlist-btn')?.addEventListener('click', rescanPlaylist);
    document.getElementById('btn-scan-dup')?.addEventListener('click', scanForDuplicates);
    document.getElementById('btn-scan-mis')?.addEventListener('click', scanForMisplaced);
    document.getElementById('delete-duplicates-btn')?.addEventListener('click', deleteDuplicateItems);
    document.getElementById('scan-filter')?.addEventListener('change', filterScanResults);

    // Event delegation for video checkboxes and links within the videos-container
    const videosContainer = document.getElementById('videos-container');
    if (videosContainer) {
        videosContainer.addEventListener('change', (event) => {
            if (event.target.classList.contains('video-checkbox')) {
                toggleVideo(event.target.dataset.videoId, event.target);
            }
        });

        videosContainer.addEventListener('click', (event) => {
            if (event.target.closest('a')) {
                // Allow links to work naturally, but stop propagation if needed for nested elements
                event.stopPropagation();
            }
        });
    }

    // Listen for target playlist dropdown changes
    document.getElementById('target-playlist')?.addEventListener('change', updateMoveButton);
});