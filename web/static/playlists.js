// playlists.js - Playlists specific scripts

// Store all playlists for manage function
var allPlaylists = [];

// Upgrade a low-res YouTube thumbnail URL to a higher-res variant (no API cost).
// default.jpg is 120x90; hqdefault.jpg is 480x360; maxresdefault.jpg is 1280x720.
function upgradeThumb(url) {
    if (!url) return url;
    return url.replace(/\/vi\/([^/]+)\/default\.jpg/, '/vi/$1/hqdefault.jpg')
              .replace(/=s\d+(-c)?$/, '=s480');
}

function renderCachedPlaylists() {
    const skeleton = document.getElementById("playlists-skeleton");
    const playlistsList = document.getElementById("playlists-list");

    if (skeleton) skeleton.classList.remove("hidden");
    if (playlistsList) playlistsList.classList.add("hidden");

    const raw = localStorage.getItem("playlists") || localStorage.getItem("cached_playlists");
    if (raw) {
        try {
            const playlists = JSON.parse(raw);
            if (Array.isArray(playlists) && playlists.length) {
                allPlaylists = playlists;
                renderPlaylistsGrid(playlists);
                if (skeleton) skeleton.classList.add("hidden");
                if (playlistsList) playlistsList.classList.remove("hidden");
                return true;
            }
        } catch (e) {
            console.error("Error parsing cached playlists", e);
        }
    }
    return false;
}

async function loadPlaylists() {
    const skeleton = document.getElementById("playlists-skeleton");
    const playlistsList = document.getElementById("playlists-list");

    // Only show skeleton when we have no cached content to paint
    if (skeleton && playlistsList && playlistsList.classList.contains("hidden") && !playlistsList.children.length) {
        skeleton.classList.remove("hidden");
        playlistsList.classList.add("hidden");
    }

    try {
        const response = await authFetch("/api/playlists");
        const data = await response.json();

        if (!response.ok || (data && data.error)) {
            throw new Error((data && data.error) || "Failed to load playlists");
        }

        const rawList = Array.isArray(data) ? data : ((data && data.playlists) || []);
        allPlaylists = rawList.map(p => ({
            id: p.id || (p.url ? (p.url.split('list=')[1] || '').split('&')[0] : ''),
            title: p.title || p.name || 'Untitled',
            name: p.name || p.title || 'Untitled',
            video_count: p.video_count !== undefined ? p.video_count : (p.videos ? p.videos.length : 0),
            thumbnail: p.thumbnail || (p.videos && p.videos[0] ? p.videos[0].thumbnail : ''),
            url: p.url || (p.id ? `https://www.youtube.com/playlist?list=${p.id}` : '')
        }));
        localStorage.setItem("cached_playlists", JSON.stringify(allPlaylists));
        renderPlaylistsGrid(allPlaylists);
    } catch (e) {
        // If we already painted a cached grid, keep it instead of erroring over it
        const hasContent = playlistsList && playlistsList.children.length > 0;
        if (!hasContent) {
            playlistsList.innerHTML = `<div class="col-span-full bento-card p-8 text-center text-red-400">Error: ${DOMPurify.sanitize(e.message || "Failed to load playlists due to a network error.")}</div>`;
            toast(`Error: ${e.message}`, "error");
        }
    } finally {
        if (skeleton) skeleton.classList.add("hidden");
        if (playlistsList) playlistsList.classList.remove("hidden");
    }
}

function thumbMarkup(p) {
    // Default graphic for empty playlists (inline SVG: no network, no CSP issues)
    if (!p.video_count) {
        return `
        <svg viewBox="0 0 160 90" class="w-full h-full" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg" aria-label="No videos yet">
            <rect width="160" height="90" fill="#0f1115"/>
            <circle cx="80" cy="38" r="21" fill="none" stroke="#2f8fc9" stroke-width="2" opacity="0.6"/>
            <path d="M73 29 L92 38 L73 47 Z" fill="#2f8fc9" opacity="0.85"/>
            <text x="80" y="74" text-anchor="middle" fill="#5b6573" font-size="10" font-family="sans-serif" letter-spacing="0.5">No videos yet</text>
        </svg>`;
    }
    const thumb = upgradeThumb(p.thumbnail || 'https://picsum.photos/160/90');
    return `<img src="${thumb}" class="w-full h-full object-cover" loading="lazy" onerror="this.onerror=null; this.src='https://picsum.photos/160/90'">`;
}

function renderPlaylistsGrid(playlists) {
    const playlistsList = document.getElementById("playlists-list");
    if (!playlistsList) return;

    if (!playlists.length) {
        playlistsList.innerHTML = `<div class="col-span-full flex items-center justify-center min-h-[60vh]">
            <div class="bento-card p-12 text-center text-gray-400 text-base">No playlists found. Create one to get started.</div>
        </div>`;
        return;
    }
    playlistsList.innerHTML = playlists.map(p => {
        const title = p.title || p.name || 'Untitled';
        const playlistId = p.id || (p.url ? (p.url.split('list=')[1] || '').split('&')[0] : '');
        return `
        <a href="/playlist/${playlistId}" class="bento-card p-2.5 w-full flex flex-row gap-3 items-center cursor-pointer hover:border-[#2a7db8]/50 transition-colors relative block min-h-[76px]">
          <div class="flex-shrink-0 w-20 h-14 rounded-lg overflow-hidden bg-[#0f1115]">
            ${thumbMarkup(p)}
          </div>
          <div class="flex-1 min-w-0 flex flex-col gap-0.5">
            <h3 class="text-base md:text-lg font-semibold text-[#2f8fc9] truncate">${title}</h3>
            <p class="text-xs text-gray-400">${p.video_count} videos</p>
            <div class="flex items-center gap-2 mt-0.5" onclick="event.stopPropagation()">
              <button onclick="event.preventDefault(); event.stopPropagation(); rescanPlaylist('${playlistId}', event)" class="bg-[#20242c] hover:bg-[#2a2f3a] text-gray-300 text-[11px] py-1 px-1.5 rounded transition-colors" title="Rescan Videos"><i class="fa-solid fa-arrows-rotate text-[9px]"></i></button>
              <button onclick="event.preventDefault(); event.stopPropagation(); openPlaylist('${playlistId}', event)" class="text-[11px] p-1 rounded bg-[#20242c] text-gray-400 hover:text-white hover:bg-[#2a2f3a] transition-colors flex-shrink-0" title="Open on YouTube"><i class="fa-solid fa-external-link text-[9px]"></i></button>
            </div>
          </div>
        </a>
      `;
    }).join('');
}
function openPlaylist(playlistId, event) {
    if (event) event.stopPropagation();
    window.open(`https://www.youtube.com/playlist?list=${playlistId}`, "_blank");
}

async function rescanPlaylist(playlistId, event) {
    event.stopPropagation();
    const btn = event.currentTarget;
    const origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = "<i class=\"fa-solid fa-spinner fa-spin text-[#2f8fc9]\"></i>";
    
    toast("Rescanning playlist videos...", "info");
    try {
        const resp = await authFetch(`/api/youtube/videos?playlist_id=${playlistId}&force_refresh=true`);
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || "Failed to refresh playlist videos");
        }

        const playlistIndex = allPlaylists.findIndex(item => item.id === playlistId);
        if (playlistIndex !== -1) {
            allPlaylists[playlistIndex].video_count = data.videos?.length || 0;
        }
        
        toast(`Rescan complete - ${data.videos?.length || 0} videos found`, "success");
        loadPlaylists();
    } catch (e) {
        toast(`Rescan failed: ${DOMPurify.sanitize(e.message)}`, "error");
        console.error("Rescan failed:", e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = origHTML;
    }
}

function closeAllMenus() {
    document.querySelectorAll("[id^=\"menu-\"]").forEach(el => el.classList.add("hidden"));
}

function togglePlaylistMenu(playlistId) {
    const menu = document.getElementById(`menu-${playlistId}`);
    if (!menu) return;
    document.querySelectorAll("[id^=\"menu-\"]").forEach(el => {
        if (el !== menu) el.classList.add("hidden");
    });
    menu.classList.toggle("hidden");
}

async function deletePlaylistConfirmed(playlistId) {
    if (!confirm("Delete this playlist? This cannot be undone.")) return;
    try {
        const resp = await authFetch("/api/youtube/playlists/delete", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({playlist_id: playlistId})
        });
        const data = await resp.json();
        toast(data.message || data.error, data.status === "success" ? "success" : "error");
        loadPlaylists();
    } catch (e) {
        toast("Delete failed", "error");
    }
}

function openManagePlaylistModal(playlistId, playlistTitle, event) {
    if (event) event.stopPropagation();
    
    const modal = document.createElement("div");
    modal.className = "fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs";
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
                <button onclick="actionRenamePlaylist('${playlistId}', \`${safeTitle}\`); this.closest('.fixed').remove()" class="w-full bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-pen-to-square text-[#2f8fc9] w-4 text-center"></i> Rename Playlist
                </button>
                <button onclick="actionDuplicatePlaylist('${playlistId}', \`${safeTitle}\`); this.closest('.fixed').remove()" class="w-full bg-[#20242c] hover:bg-[#2a2f3a] border border-[#2a2f3a] text-gray-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-copy text-green-400 w-4 text-center"></i> Duplicate Playlist
                </button>
                <button onclick="actionDeletePlaylist('${playlistId}', \`${safeTitle}\`); this.closest('.fixed').remove()" class="w-full bg-red-950/20 hover:bg-red-900/30 border border-red-900/30 text-red-200 text-xs font-semibold py-2.5 rounded-lg flex items-center gap-2.5 px-4 transition-colors">
                    <i class="fa-solid fa-trash-can text-red-500 w-4 text-center"></i> Delete Playlist
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function actionRenamePlaylist(playlistId, currentTitle) {
    const newTitle = prompt("Rename Playlist - Enter new title:", currentTitle);
    if (!newTitle || newTitle === currentTitle) return;
    
    toast("Renaming playlist...", "info");
    try {
        const resp = await authFetch("/api/youtube/playlists/rename", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ playlist_id: playlistId, new_title: newTitle })
        });
        const res = await resp.json();
        if (resp.ok) {
            toast(res.message, "success");
            loadPlaylists();
        } else {
            const errorMessage = res.detail || res.error || "Rename failed";
            toast(`Rename failed: ${DOMPurify.sanitize(errorMessage)}`, "error");
        }
    } catch (e) {
        toast(`Failed to rename playlist: ${DOMPurify.sanitize(e.message || "Network error")}`, "error");
        console.error("Rename failed:", e);
    }
}

async function actionDuplicatePlaylist(playlistId, currentTitle) {
    const newTitle = prompt("Duplicate Playlist - Enter name for duplicate:", `${currentTitle} Copy`);
    if (!newTitle) return;
    
    toast("Initiating playlist duplication...", "info");
    try {
        const resp = await authFetch("/api/youtube/playlists/duplicate", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ playlist_id: playlistId, new_title: newTitle })
        });
        const res = await resp.json();
        if (resp.ok) {
            toast(res.message, "success");
            loadPlaylists();
        } else {
            const errorMessage = res.detail || res.error || "Duplication failed";
            toast(`Duplication failed: ${DOMPurify.sanitize(errorMessage)}`, "error");
        }
    } catch (e) {
        toast(`Failed to duplicate playlist: ${DOMPurify.sanitize(e.message || "Network error")}`, "error");
        console.error("Duplicate failed:", e);
    }
}

async function actionCreatePlaylist() {
    const title = prompt("Playlist title:");
    if (!title) return;
    const resp = await authFetch("/api/youtube/playlists/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title })
    });
    if (resp.ok) loadPlaylists();
    else alert("Failed to create playlist");
}

async function actionDeletePlaylist(playlistId, title) {
    if (!confirm(`Are you absolutely sure you want to delete '${title}' from YouTube?\\n\\nThis action cannot be undone.`)) return;
    
    toast("Deleting playlist...", "info");
    try {
        const resp = await authFetch("/api/youtube/playlists/delete", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ playlist_id: playlistId })
        });
        const res = await resp.json();
        if (resp.ok) {
            toast(res.message, "success");
            loadPlaylists();
        } else {
            const errorMessage = res.detail || res.error || "Delete failed";
            toast(`Delete failed: ${DOMPurify.sanitize(errorMessage)}`, "error");
        }
    } catch (e) {
        toast(`Failed to delete playlist: ${DOMPurify.sanitize(e.message || "Network error")}`, "error");
        console.error("Delete failed:", e);
    }
}

// SPA-safe init: render cache instantly, then refresh from API
function safeLoadPlaylists() {
    if (typeof loadPlaylists === "function") {
        loadPlaylists();
    } else {
        setTimeout(safeLoadPlaylists, 100);
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        renderCachedPlaylists(); // paint instantly from cache
        safeLoadPlaylists();     // then fetch fresh
    });
} else {
    renderCachedPlaylists();
    safeLoadPlaylists();
}


async function syncPlaylists(e) {
    const btn = e.target.closest("button") || e.target;
    btn.disabled = true;
    btn.innerHTML = "<i class=\"fa-solid fa-spinner fa-spin\"></i> Syncing...";
    toast("Initiating playlist sync...", "info");
    try {
        const resp = await authFetch("/api/action", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({action: "sync_playlists"})
        });
        const result = await resp.json();
        if (resp.ok) {
            if (result.error) {
                toast(`Sync failed: ${DOMPurify.sanitize(result.error)}`, "error");
            } else {
                toast("Playlist sync started", "info");
            }
        } else {
            const errorMessage = result.detail || result.error || "Sync initiation failed";
            toast(`Sync initiation failed: ${DOMPurify.sanitize(errorMessage)}`, "error");
        }
    } catch (e) {
        toast(`Sync failed: ${DOMPurify.sanitize(e.message || "Network error")}`, "error");
        console.error("Sync failed:", e);
    } finally {
        btn.disabled = false;
        btn.innerHTML = "<i class=\"fa-solid fa-sync\"></i> Sync from YouTube";
    }
}
