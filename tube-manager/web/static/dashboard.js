const consoleOutput = document.getElementById('console-output');
const token = localStorage.getItem('token') || '';
let ws = null;
let pingInterval = null;
let pongTimeout = null;
let missedPongs = 0;
let statsIntervalId = null; // H3 FIX: Track single stats poller

// H4/H18 FIX: Fetch wrapper with retry logic for mobile network failures
async function fetchWithRetry(url, options = {}, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            const resp = await fetch(url, options);
            if (resp.ok) return resp;
            if (resp.status < 500) return resp; // Don't retry client errors
        } catch (e) {
            if (i === retries - 1) throw e;
            await new Promise(r => setTimeout(r, 1000 * (i + 1)));
        }
    }
}

function logConsole(text, type = 'info') {
    const line = document.createElement('div');
    const time = new Date().toLocaleTimeString();
    line.className = `console-line ${type}`;
    line.textContent = `[${time}] ${text}`;
    consoleOutput.appendChild(line);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

async function apiCall(url, options = {}) {
    const resp = await fetch(url, {
        ...options,
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
            ...(options.headers || {})
        }
    });
    return resp;
}

async function loadStats() {
    try {
        const [plResp, wlResp, subResp] = await Promise.all([
            apiCall('/api/playlists'),
            apiCall('/api/watch-later'),
            apiCall('/api/subscriptions')
        ]);
        if (plResp.ok) {
            const plData = await plResp.json();
            const playlists = plData.playlists || [];
            document.getElementById('stat-playlists').textContent = playlists.length;
            document.getElementById('stat-videos').textContent = playlists.reduce((a, p) => a + (p.video_count || 0), 0);
        }
        if (wlResp.ok) {
            const wlData = await wlResp.json();
            document.getElementById('stat-watch-later').textContent = (wlData.items || []).length;
        }
        if (subResp.ok) {
            const subData = await subResp.json();
            document.getElementById('stat-subscriptions').textContent = (subData.channels || []).length;
        }
    } catch (e) {
        console.warn('Failed to load stats', e);
    }
}

function connectWebSocket() {
    if (ws) ws.close();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/terminal?token=${token}`);

    ws.onopen = () => {
        logConsole('WebSocket connected.', 'success');
        missedPongs = 0;
        // H3 FIX: Clear existing ping interval before setting new one
        if (pingInterval) clearInterval(pingInterval);
        pingInterval = setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'ping'}));
                pongTimeout = setTimeout(() => {
                    missedPongs++;
                    if (missedPongs >= 3) {
                        logConsole('WebSocket unresponsive; reconnecting...', 'error');
                        ws.close();
                    }
                }, 10000);
            }
        }, 30000);
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'pong') {
                clearTimeout(pongTimeout);
                missedPongs = 0;
                return;
            }
            if (msg.type === 'ping') {
                ws.send(JSON.stringify({type: 'pong'}));
                return;
            }
            logConsole(msg.text || msg.message || JSON.stringify(msg), msg.level || 'info');
        } catch {
            logConsole(event.data, 'info');
        }
    };

    ws.onerror = () => logConsole('WebSocket error.', 'error');
    ws.onclose = () => {
        clearInterval(pingInterval);
        logConsole('WebSocket disconnected.', 'warn');
        // H16 FIX: Only reconnect if tab is visible (save mobile battery)
        if (!document.hidden) {
            setTimeout(connectWebSocket, 3000);
        }
    };
}

// H16 FIX: Resume WebSocket when tab becomes visible again
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && (!ws || ws.readyState !== WebSocket.OPEN)) {
        connectWebSocket();
    }
});

async function callAction(action, payload = null) {
    try {
        const options = { method: 'POST', body: JSON.stringify({action, payload}) };
        const resp = await apiCall('/api/action', options);
        const data = await resp.json().catch(() => ({}));
        if (resp.ok) logConsole(`${action} initiated.`, 'success');
        else logConsole(`${action} failed: ${data.detail || data.error || resp.status}`, 'error');
    } catch (e) {
        logConsole(`${action} error: ${e.message}`, 'error');
    }
}

document.getElementById('btn-fetch-all').addEventListener('click', () => callAction('sync_playlists'));
document.getElementById('btn-watch-later').addEventListener('click', () => callAction('sync_watch_later'));
// Maintenance action removed — use sync_playlists for data refresh.
document.getElementById('btn-cancel').addEventListener('click', async () => {
    try {
        const resp = await apiCall('/api/action/cancel', {method: 'POST', body: JSON.stringify({})});
        if (resp.ok) logConsole('Cancel request sent.', 'success');
        else logConsole('Cancel request failed.', 'error');
    } catch (e) {
        logConsole(`Cancel error: ${e.message}`, 'error');
    }
});

document.getElementById('btn-copy-console').addEventListener('click', () => {
    const text = Array.from(consoleOutput.children).map(c => c.textContent).join('\n');
    navigator.clipboard.writeText(text).then(() => logConsole('Console copied to clipboard.', 'success'));
});

document.getElementById('btn-export-console').addEventListener('click', () => {
    const text = Array.from(consoleOutput.children).map(c => c.textContent).join('\n');
    const blob = new Blob([text], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `motus-console-${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    logConsole('Console exported.', 'success');
});

document.getElementById('btn-clear-console').addEventListener('click', () => {
    consoleOutput.innerHTML = '';
    logConsole('Console cleared.', 'info');
});

document.getElementById('btn-maintenance')?.addEventListener('click', function() {
    window.location.href = '/maintenance';
});

document.getElementById('btn-run-scan')?.addEventListener('click', () => {
    if (window.runScan) window.runScan();
});

document.getElementById('scan-cancel-btn')?.addEventListener('click', async () => {
    try {
        const resp = await apiCall('/api/action/cancel', { method: 'POST', body: JSON.stringify({}) });
        if (resp.ok) logConsole('Task cancelled.', 'success');
        else logConsole('Cancel request failed.', 'error');
    } catch (e) {
        logConsole(`Cancel error: ${e.message}`, 'error');
    }
});

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    connectWebSocket();
    loadScanDetails();
});

// Scan Details — fetch duplicate/misplaced scan results + worker status
async function loadScanDetails() {
    try {
        // Use apiCall (sends auth header) — both endpoints require authentication.
        // Also fetch /api/stats for last_scan, queue size, and worker count.
        const [dupResp, misResp, statsResp] = await Promise.all([
            apiCall('/api/youtube/duplicates'),
            apiCall('/api/youtube/misplaced'),
            apiCall('/api/stats')
        ]);

        const dupData = await dupResp.json().catch(() => ({}));
        const misData = await misResp.json().catch(() => ({}));
        const statsData = await statsResp.json().catch(() => ({}));

        const dupCount = dupData.duplicates || 0;
        const misCount = misData.misplaced?.length || misData.count || 0;
        const totalIssues = dupCount + misCount;

        // Last scan time from server (or "Never" if not yet scanned)
        const lastScan = statsData.last_scan || 'Never';
        const lastScanEl = document.getElementById('last-scan');
        if (lastScanEl) {
            lastScanEl.textContent = lastScan === 'Never' ? 'Never' : new Date(lastScan).toLocaleTimeString();
        }

        // Status — show scan result severity
        const statusEl = document.getElementById('scan-status');
        if (statusEl) {
            if (totalIssues === 0) {
                statusEl.textContent = 'Clean';
                statusEl.className = 'text-green-400 font-medium';
            } else if (totalIssues <= 5) {
                statusEl.textContent = `${totalIssues} issue${totalIssues > 1 ? 's' : ''}`;
                statusEl.className = 'text-yellow-400 font-medium';
            } else {
                statusEl.textContent = `${totalIssues} issues`;
                statusEl.className = 'text-red-400 font-medium';
            }
        }

        // Queued tasks & active workers from /api/stats
        const queuedEl = document.getElementById('queued-tasks');
        if (queuedEl) queuedEl.textContent = statsData.pending_actions ?? 0;

        const workersEl = document.getElementById('active-workers');
        if (workersEl) workersEl.textContent = statsData.running_tasks ?? 0;

        // Show/hide cancel button when a task is running
        const cancelBtn = document.getElementById('scan-cancel-btn');
        if (cancelBtn) {
            const isRunning = (statsData.running_tasks || 0) > 0;
            cancelBtn.classList.toggle('hidden', !isRunning);
        }

        // Activity bar — base on worker load (running tasks + queue) with issues as a modifier
        const load = (statsData.running_tasks || 0) + (statsData.pending_actions || 0);
        const activityPct = Math.min(load * 15 + (totalIssues > 0 ? 10 : 0), 100);
        const actPctEl = document.getElementById('activity-pct');
        const actBarEl = document.getElementById('activity-bar');
        if (actPctEl) actPctEl.textContent = activityPct + '%';
        if (actBarEl) actBarEl.style.width = activityPct + '%';

        // Log results
        if (totalIssues > 0) {
            logConsole(`Scan: ${dupCount} duplicate${dupCount !== 1 ? 's' : ''}, ${misCount} misplaced.`, 'warn');
        } else {
            logConsole('Scan: No issues found.', 'success');
        }
    } catch (e) {
        const statusEl = document.getElementById('scan-status');
        if (statusEl) {
            statusEl.textContent = 'Error';
            statusEl.className = 'text-red-400 font-medium';
        }
        console.warn('loadScanDetails failed', e);
    }
}

// Run Scan button handler — triggers background scan via /api/action
async function runScan() {
    try {
        const resp = await apiCall('/api/action', {
            method: 'POST',
            body: JSON.stringify({ action: 'scan_duplicates' })
        });
        const data = await resp.json().catch(() => ({}));
        if (resp.ok && data.status === 'started') {
            logConsole('Duplicate scan started in background.', 'success');
            // Also kick off misplaced scan
            await apiCall('/api/action', {
                method: 'POST',
                body: JSON.stringify({ action: 'scan_misplaced' })
            });
            // Refresh details after a short delay to pick up results
            const statusEl = document.getElementById('scan-status');
            if (statusEl) { statusEl.textContent = 'Scanning…'; statusEl.className = 'text-blue-400 font-medium'; }
            setTimeout(loadScanDetails, 4000);
        } else {
            logConsole(`Scan failed: ${data.error || data.detail || resp.status}`, 'error');
        }
    } catch (e) {
        logConsole(`Scan error: ${e.message}`, 'error');
    }
}

// Make available globally for button click and stats refresh
window.refreshScanDetails = loadScanDetails;
window.runScan = runScan;