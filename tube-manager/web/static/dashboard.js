// Refresh token on dashboard load. Auth redirect is handled by auth-check.js
// in the <head>, so this function only issues a new 7-day token when possible.
(async function refreshSessionToken() {
    try {
        const token = localStorage.getItem('token');
        const resp = await fetch('/api/auth/me', {
            headers: { 
                'Accept': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            }
        });
        if (!resp.ok) return;  // auth-check.js will handle redirect if needed
        const refreshResp = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 
                'Accept': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            }
        });
        if (refreshResp.ok) {
            const data = await refreshResp.json();
            localStorage.setItem('token', data.access_token);
            document.cookie = `token=${data.access_token}; path=/; max-age=604800; SameSite=Lax`;
        }
    } catch (e) {
        console.warn('Token refresh failed:', e);
    }
})();

function logout() {
    localStorage.removeItem('user');
    localStorage.removeItem('token'); // Fix: remove redundant token cookie setting in original logout()
    document.cookie = 'token=; path=/; max-age=0; SameSite=Lax';
    window.location.href = '/auth';
}
let ws = null;
let scanLogs = [];
let queueRunning = false;
let statsLoading = false;
let scanRenderPending = false;

function toast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container') || createToastContainer();
    const el = document.createElement('div');
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    const colors = { success: 'bg-green-600', error: 'bg-red-600', warning: 'bg-yellow-600', info: 'bg-blue-600' };
    el.className = `flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white text-xs font-medium animate-slide-in ${colors[type] || colors.info}`;
    el.innerHTML = `<i class=\"fa-solid ${icons[type] || icons.info}\"></i><span>${DOMPurify.sanitize(message, {USE_PROFILES: {html: true}})}</span>`;
    container.appendChild(el);
    setTimeout(() => { el.classList.add('animate-slide-out'); setTimeout(() => el.remove(), 300); }, duration);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2 w-80';
    document.body.appendChild(container);
    return container;
}

function logTerminal(message) {
    console.log(message);
}

async function triggerAction(action, payload = {}) {
    try {
        const statusLabel = document.getElementById('status-label');
        if (statusLabel) statusLabel.textContent = 'Running...';
        const appStatus = document.getElementById('app-status');
        if (appStatus) {
            appStatus.className = 'text-[10px] text-yellow-400 font-bold';
        }
        logTerminal(`[ACTION] Queuing: ${action}`);
        const response = await fetch('/api/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, payload }) });
        const result = await response.json();
        logTerminal(`[ACTION] ${result.status}: ${result.action}`);
        toast(`${DOMPurify.sanitize(action.replace(/_/g, ' '), {USE_PROFILES: {html: true}})} started`, 'success');
    } catch (e) {
        logTerminal(`[ERROR] Failed to queue action: ${DOMPurify.sanitize(e.message, {USE_PROFILES: {html: true}})}`);
        toast(`Action failed: ${DOMPurify.sanitize(action, {USE_PROFILES: {html: true}})}`, 'error');
        const statusLabel = document.getElementById('status-label');
        if (statusLabel) statusLabel.textContent = 'Idle';
        const appStatus = document.getElementById('app-status');
        if (appStatus) {
            appStatus.className = 'text-[10px] text-green-400 font-bold';
        }
    }
}

async function loadDashboardStats() {
    if (statsLoading) return;
    statsLoading = true;
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) return;
        const data = await response.json();
        document.getElementById('stat-playlists').textContent = DOMPurify.sanitize(data.total_playlists || '--');
        document.getElementById('stat-videos').textContent = DOMPurify.sanitize(data.total_videos || '--');
        document.getElementById('stat-pending').textContent = DOMPurify.sanitize(data.pending_actions ?? '--');
        document.getElementById('pending-data').textContent = `(${DOMPurify.sanitize(data.pending_actions ?? 0)})`;
        document.getElementById('pending-still').textContent = `(${DOMPurify.sanitize(data.still_items ?? 0)})`;
        document.getElementById('pending-ai').textContent = `(${DOMPurify.sanitize(data.ai_learning ?? 0)})`;
        document.getElementById('ai-rate').textContent = DOMPurify.sanitize(data.learning_rate || '--');
        document.getElementById('ai-rates').textContent = DOMPurify.sanitize(data.learning_rates || '--');
        document.getElementById('last-scan').textContent = DOMPurify.sanitize(data.last_scan || 'Never');
        const statusLabel = document.getElementById('status-label');
        if (statusLabel) {
            if (data.running_tasks > 0 && data.current_task) {
                statusLabel.innerHTML = `<span class=\"text-yellow-400 font-bold animate-pulse\">● ${DOMPurify.sanitize(data.current_task, {USE_PROFILES: {html: true}})}</span>`;
                document.getElementById('app-status').className = 'text-[10px] text-yellow-400 font-bold';
                document.getElementById('app-status').textContent = `🟡 RUNNING: ${DOMPurify.sanitize(data.current_task, {USE_PROFILES: {html: true}})}`;
            } else {
                statusLabel.innerHTML = `<span class=\"text-green-400 font-bold\">● Idle</span>`;
                document.getElementById('app-status').className = 'text-[10px] text-green-400 font-bold';
                document.getElementById('app-status').textContent = '🟢 READY';
            }
        }
    } catch (e) { console.log('Stats endpoint not available'); }
    finally { statsLoading = false; }
}

async function checkSecurityStatus() {
    try {
        const resp = await fetch('/api/auth/security/status');
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.sessions_stable && data.warning) {
            const banner = document.getElementById('security-warning');
            document.getElementById('security-warning-text').textContent = DOMPurify.sanitize(data.warning);
            banner.classList.remove('hidden');
        }
    } catch (e) { console.warn('Security status check failed:', e); }
}

function refreshSubscriptions() { toast('Use Subscriptions page for live mapping', 'info'); }

async function loadUserAvatar() {
    try {
        const resp = await fetch('/api/auth/me');
        if (!resp.ok) return;
        const data = await resp.json();
        const avatar = document.getElementById('user-avatar');
        if (data.channel_thumbnail) {
            // Sanitize and set src directly for images
            const img = document.createElement('img');
            img.src = DOMPurify.sanitize(data.channel_thumbnail, {FORBID_TAGS: ['script'], FORBID_ATTR: ['onerror']});
            img.className = "w-full h-full object-cover rounded-full";
            avatar.innerHTML = ''; // Clear existing content
            avatar.appendChild(img);
        }
    } catch (e) {
        console.warn('Failed to load user avatar:', e);
    }
}

// Polling optimization: reduce frequency and pause when page is hidden
let statsIntervalId = null;
const STATS_INTERVAL_MS = 2 * 60 * 1000; // 2 minutes

function startStatsPolling() {
    if (statsIntervalId !== null) return;
    statsIntervalId = setInterval(loadDashboardStats, STATS_INTERVAL_MS);
}

function stopStatsPolling() {
    if (statsIntervalId !== null) {
        clearInterval(statsIntervalId);
        statsIntervalId = null;
    }
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
    loadUserAvatar();
    loadDashboardStats();
    checkSecurityStatus();
    startStatsPolling();
    document.querySelectorAll('.action-btn').forEach(btn => btn.addEventListener('click', () => triggerAction(btn.dataset.action)));
});

// Pause polling when page is hidden to reduce unnecessary requests
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopStatsPolling();
    } else {
        startStatsPolling();
    }
});

// Also stop polling when page is unloaded to prevent memory leaks
window.addEventListener('beforeunload', () => {
    stopStatsPolling();
});