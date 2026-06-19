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
        if (!response.ok) return;
        const data = await response.json();
        document.getElementById('stat-playlists').textContent = data.total_playlists || '--';
        document.getElementById('stat-videos').textContent = data.total_videos || '--';
        document.getElementById('stat-pending').textContent = data.pending_actions ?? '--';
        document.getElementById('pending-data').textContent = `(${data.pending_actions ?? 0})`;
        document.getElementById('pending-still').textContent = `(${data.still_items ?? 0})`;
        document.getElementById('pending-ai').textContent = `(${data.ai_learning ?? 0})`;
        document.getElementById('ai-rate').textContent = data.learning_rate || '--';
        document.getElementById('ai-rates').textContent = data.learning_rates || '--';
        document.getElementById('last-scan').textContent = data.last_scan || 'Never';
        const statusLabel = document.getElementById('status-label');
        if (statusLabel) {
            if (data.running_tasks > 0 && data.current_task) {
                statusLabel.innerHTML = `<span class="text-yellow-400 font-bold animate-pulse">● ${data.current_task}</span>`;
                document.getElementById('app-status').className = 'text-[10px] text-yellow-400 font-bold';
                document.getElementById('app-status').textContent = `🟡 RUNNING: ${data.current_task}`;
            } else {
                statusLabel.innerHTML = `<span class="text-green-400 font-bold">● Idle</span>`;
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
            document.getElementById('security-warning-text').textContent = data.warning;
            banner.classList.remove('hidden');
        }
    } catch (e) { console.warn('Security status check failed:', e); }
}

function refreshSubscriptions() { toast('Use Subscriptions page for live mapping', 'info'); }

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    checkSecurityStatus();
    setInterval(loadDashboardStats, 30000);
    document.querySelectorAll('.action-btn').forEach(btn => btn.addEventListener('click', () => triggerAction(btn.dataset.action)));
});
