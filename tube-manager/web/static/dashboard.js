// dashboard.js - Dashboard specific scripts

let ws = null;
let scanLogs = [];
let queueRunning = false;
let statsLoading = false;
let scanRenderPending = false;

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
        toast(`${action.replace(/_/g, ' ')} started`, 'success');
    } catch (e) {
        logTerminal(`[ERROR] Failed to queue action: ${e.message}`);
        toast(`Action failed: ${action}`, 'error');
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
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to load dashboard stats');
        }

        const statPlaylists = document.getElementById('stat-playlists');
        const statVideos = document.getElementById('stat-videos');
        const statPending = document.getElementById('stat-pending');

        if (statPlaylists) statPlaylists.textContent = data.total_playlists || '--';
        if (statVideos) statVideos.textContent = data.total_videos || '--';
        if (statPending) statPending.textContent = data.pending_actions ?? '--';

        const pendingData = document.getElementById('pending-data');
        const pendingStill = document.getElementById('pending-still');
        const pendingAI = document.getElementById('pending-ai');
        const aiRate = document.getElementById('ai-rate');
        const aiRates = document.getElementById('ai-rates');
        const lastScan = document.getElementById('last-scan');

        if (pendingData) pendingData.textContent = `(${data.pending_actions ?? 0})`;
        if (pendingStill) pendingStill.textContent = `(${data.still_items ?? 0})`;
        if (pendingAI) pendingAI.textContent = `(${data.ai_learning ?? 0})`;
        if (aiRate) aiRate.textContent = data.learning_rate || '--';
        if (aiRates) aiRates.textContent = data.learning_rates || '--';
        if (lastScan) lastScan.textContent = data.last_scan || 'Never';

        const statusLabel = document.getElementById('status-label');
        if (statusLabel) {
            if (data.running_tasks > 0 && data.current_task) {
                statusLabel.innerHTML = `<span class="text-yellow-400 font-bold animate-pulse">● ${data.current_task}</span>`;
                const appStatus = document.getElementById('app-status');
                if (appStatus) {
                    appStatus.className = 'text-[10px] text-yellow-400 font-bold';
                    appStatus.textContent = `🟡 RUNNING: ${data.current_task}`;
                }
            } else {
                statusLabel.innerHTML = `<span class="text-green-400 font-bold">● Idle</span>`;
                const appStatus = document.getElementById('app-status');
                if (appStatus) {
                    appStatus.className = 'text-[10px] text-green-400 font-bold';
                    appStatus.textContent = '🟢 READY';
                }
            }
        }
    } catch (e) {
        console.error('Failed to load dashboard stats:', e);
        toast(`Failed to load dashboard stats: ${DOMPurify.sanitize(e.message || 'Network error')}`, 'error');
        ['stat-playlists', 'stat-videos', 'stat-pending', 'pending-data', 'pending-still', 'pending-ai', 'ai-rate', 'ai-rates', 'last-scan'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '--';
        });
    }
    finally { statsLoading = false; }
}

async function checkSecurityStatus() {
    try {
        const resp = await fetch('/api/auth/security/status');
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.sessions_stable && data.warning) {
            const banner = document.getElementById('security-warning');
            const warningText = document.getElementById('security-warning-text');
            if (banner && warningText) {
                warningText.textContent = data.warning;
                banner.classList.remove('hidden');
            }
        }
    } catch (e) { console.warn('Security status check failed:', e); }
}

function refreshSubscriptions() { toast('Use Subscriptions page for live mapping', 'info'); }

function onWsMessage(raw) {
    try {
        const data = JSON.parse(raw);
        if (data.type === 'log') toast(data.message, 'info');
    } catch (e) {
        console.warn('WS message parse failed:', e);
    }
}

function connectWs() {
    let ws = null;
    try {
        ws = new WebSocket(`${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/terminal`);
        const consoleEl = document.getElementById('console');
        ws.addEventListener('open', () => {
            if (consoleEl) consoleEl.innerHTML += '<div class="log-success">[WS] Connected to agent terminal</div>';
        });
        ws.addEventListener('message', e => onWsMessage(e.data));
        ws.addEventListener('close', () => setTimeout(connectWs, 2000));
    } catch (e) {
        setTimeout(connectWs, 2000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    checkSecurityStatus();
    setInterval(loadDashboardStats, 30000);
    document.querySelectorAll('.action-btn').forEach(btn => btn.addEventListener('click', () => triggerAction(btn.dataset.action)));
});

