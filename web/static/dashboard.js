var consoleOutput = document.getElementById('console-output');
var token = localStorage.getItem('token') || '';

// Redirect to auth if no token present
if (!token) {
    window.location.href = '/auth';
}

var ws = null;
var pingInterval = null;
var pongTimeout = null;
var missedPongs = 0;
var statsIntervalId = null; // H3 FIX: Track single stats poller

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
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };
    // Only add Bearer header if we have a token in localStorage.
    // Otherwise, rely on the HttpOnly cookie (sent automatically).
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const resp = await fetch(url, {
        ...options,
        headers
    });
    return resp;
}

async function loadStats() {
    try {
        const statsResp = await apiCall('/api/stats').catch(() => null);
        if (statsResp && statsResp.ok) {
            const s = await statsResp.json().catch(() => ({}));
            const elPlaylists = document.getElementById('stat-playlists');
            const elVideos = document.getElementById('stat-videos');
            const elSubs = document.getElementById('stat-subscriptions');
            if (elPlaylists) elPlaylists.textContent = s.total_playlists ?? '--';
            if (elVideos) elVideos.textContent = s.total_videos ?? '--';
            if (elSubs) elSubs.textContent = s.total_subscriptions ?? '--';
        }
    } catch (e) {
        console.warn('Failed to load stats', e);
    }
}

// H4 FIX: define loadDashboardStats() (was an undefined ReferenceError on every action dispatch).
// Re-fetches dashboard counts (stats + duplicate/misplaced scan results) and updates the UI.
async function loadDashboardStats() {
    try {
        const [statsResp, dupResp, misResp] = await Promise.all([
            apiCall('/api/stats').catch(() => null),
            apiCall('/api/youtube/duplicates').catch(() => null),
            apiCall('/api/youtube/misplaced').catch(() => null)
        ]);
        const s = (statsResp && statsResp.ok) ? await statsResp.json().catch(() => ({})) : {};
        if (s.last_scan) {
            const lastScanEl = document.getElementById('last-scan');
            if (lastScanEl) lastScanEl.textContent = new Date(s.last_scan).toLocaleTimeString();
        }
        const dupCount = (dupResp && dupResp.ok) ? ((await dupResp.json().catch(() => ({}))).duplicates || 0) : 0;
        const misCount = (misResp && misResp.ok) ? ((await misResp.json().catch(() => ({}))).misplaced?.length || 0) : 0;
        const dupEl = document.getElementById('stat-duplicates');
        const misEl = document.getElementById('stat-misplaced');
        if (dupEl) dupEl.textContent = String(dupCount);
        if (misEl) misEl.textContent = String(misCount);
        const statusEl = document.getElementById('scan-status');
        const totalIssues = dupCount + misCount;
        if (statusEl) {
            if (totalIssues === 0) {
                statusEl.textContent = 'Clean';
                statusEl.className = 'text-green-400 font-medium';
            } else if (totalIssues <= 5) {
                statusEl.textContent = `${dupCount} duplicate${dupCount !== 1 ? 's' : ''}, ${misCount} misplaced`;
                statusEl.className = 'text-yellow-400 font-medium';
            } else {
                statusEl.textContent = `${dupCount} duplicates · ${misCount} misplaced`;
                statusEl.className = 'text-yellow-400 font-medium';
            }
        }
    } catch (e) {
        console.warn('loadDashboardStats failed', e);
    }
}

// Handle OAuth popup callback messages
window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'youtube-oauth-success') {
        // Extract token from URL if provided
        const params = new URLSearchParams(window.location.search);
        const token = params.get('token') || e.data.token;
        if (token) {
            localStorage.setItem('token', token);
            window.location.reload();
        } else {
            // Token was set as cookie by server — reload to pick it up
            window.location.reload();
        }
    }
});

function connectWebSocket() {
    if (ws) ws.close();
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/terminal?token=${token}`);

    ws.onopen = () => {
        logConsole('WebSocket connected.', 'success');
        missedPongs = 0;
        // Re-sync the Scan Details indicators from the server on (re)connect so a
        // scan that started while disconnected shows the correct live state.
        loadScanDetails();
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
            // Live worker status — drives Queued Tasks / Active Workers / System Activity
            if (msg.type === 'status') {
                applyWorkerStatus(msg);
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
        if (resp.ok) {
            logConsole(`${action} initiated.`, 'success');
            // Refresh dashboard stats + scan details after action completes
            setTimeout(() => {
                loadDashboardStats();
                const dupEl = document.getElementById('stat-duplicates');
                const misEl = document.getElementById('stat-misplaced');
                if (dupEl) dupEl.textContent = '...';
                if (misEl) misEl.textContent = '...';
            }, 3000);
        } else {
            logConsole(`${action} failed: ${data.detail || data.error || resp.status}`, 'error');
        }
    } catch (e) {
        logConsole(`${action} error: ${e.message}`, 'error');
    }
}

document.getElementById('btn-fetch-all').addEventListener('click', () => callAction('sync_playlists'));
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
            apiCall('/api/youtube/duplicates').catch(() => null),
            apiCall('/api/youtube/misplaced').catch(() => null),
            apiCall('/api/stats').catch(() => null)
        ]);

        const dupData = (dupResp && dupResp.ok) ? await dupResp.json().catch(() => ({})) : {};
        const misData = (misResp && misResp.ok) ? await misResp.json().catch(() => ({})) : {};
        const statsData = (statsResp && statsResp.ok) ? await statsResp.json().catch(() => ({})) : {};

        const dupCount = dupData.duplicates || 0;
        const misCount = misData.misplaced?.length || misData.count || 0;
        const totalIssues = dupCount + misCount;

        // Last scan time from server (or "Never" if not yet scanned)
        const lastScan = statsData.last_scan || 'Never';
        const lastScanEl = document.getElementById('last-scan');
        if (lastScanEl) {
            lastScanEl.textContent = lastScan === 'Never' ? 'Never' : new Date(lastScan).toLocaleTimeString();
        }

        // Status — show scan result severity with a clear, meaningful label.
        // Duplicates are informational (warning), misplaced are actionable (warn/red).
        const statusEl = document.getElementById('scan-status');
        if (statusEl) {
            if (totalIssues === 0) {
                statusEl.textContent = 'Clean';
                statusEl.className = 'text-green-400 font-medium';
            } else if (totalIssues <= 5) {
                statusEl.textContent = `${dupCount} duplicate${dupCount !== 1 ? 's' : ''}, ${misCount} misplaced`;
                statusEl.className = 'text-yellow-400 font-medium';
            } else {
                statusEl.textContent = `${dupCount} duplicates · ${misCount} misplaced`;
                statusEl.className = 'text-yellow-400 font-medium';
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

        // System Activity bar — reflect real worker load, never a fake 10%.
        // When idle → 0%. When a scan is running → indeterminate pulsing state.
        updateActivityBar((statsData.running_tasks || 0) > 0 || (statsData.pending_actions || 0) > 0);

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

// Live worker status handler — driven by the {"type":"status",...} WebSocket message.
// Keeps Queued Tasks / Active Workers / System Activity live during a scan instead of
// relying on a single /api/stats poll that can miss an in-flight task.
function applyWorkerStatus(status) {
    const queued = Number(status.pending || 0);
    const running = Number(status.running || 0);

    const queuedEl = document.getElementById('queued-tasks');
    if (queuedEl) queuedEl.textContent = queued;

    const workersEl = document.getElementById('active-workers');
    if (workersEl) workersEl.textContent = running;

    // Cancel button visible only while a task is in flight
    const cancelBtn = document.getElementById('scan-cancel-btn');
    if (cancelBtn) cancelBtn.classList.toggle('hidden', running === 0);

    // Status label reflects current task while running
    const statusEl = document.getElementById('scan-status');
    if (statusEl) {
        if (running > 0) {
            const taskName = (status.current_task || '').replace(/_/g, ' ');
            statusEl.textContent = taskName ? `Scanning… (${taskName})` : 'Scanning…';
            statusEl.className = 'text-[#2f8fc9] font-medium';
        } else if (queued > 0) {
            statusEl.textContent = 'Queued';
            statusEl.className = 'text-yellow-400 font-medium';
        } else {
            // Idle — leave the result severity label to loadScanDetails/loadDashboardStats;
            // only override if it currently shows a transient scanning state.
            if (statusEl.textContent === 'Scanning…' || statusEl.textContent.startsWith('Scanning…') || statusEl.textContent === 'Queued') {
                statusEl.textContent = 'Idle';
                statusEl.className = 'text-gray-300 font-medium';
            }
        }
    }

    // System Activity bar — pulsing indeterminate when busy, 0% when idle.
    updateActivityBar(running > 0 || queued > 0);
}

// Update the System Activity progress bar. When `busy`, show an indeterminate
// pulsing "Scanning…" state; otherwise collapse to a meaningful 0% idle bar.
function updateActivityBar(busy) {
    const actPctEl = document.getElementById('activity-pct');
    const actBarEl = document.getElementById('activity-bar');
    if (actBarEl) {
        actBarEl.classList.toggle('activity-scanning', busy);
        actBarEl.style.width = busy ? '100%' : '0%';
    }
    if (actPctEl) {
        actPctEl.textContent = busy ? 'Scanning…' : '0%';
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
            // Reflect scan state immediately (before the first WS status arrives)
            const statusEl = document.getElementById('scan-status');
            if (statusEl) { statusEl.textContent = 'Scanning…'; statusEl.className = 'text-[#2f8fc9] font-medium'; }
            updateActivityBar(true);
            const cancelBtn = document.getElementById('scan-cancel-btn');
            if (cancelBtn) cancelBtn.classList.remove('hidden');

            // Safety verify-poll: refresh details until the worker reports idle.
            // The WS status stream drives live updates; this covers reconnect gaps.
            startScanVerifyPoll();
        } else {
            logConsole(`Scan failed: ${data.error || data.detail || resp.status}`, 'error');
        }
    } catch (e) {
        logConsole(`Scan error: ${e.message}`, 'error');
    }
}

// Poll /api/stats while a scan is believed to be running, stopping once idle.
let scanVerifyTimer = null;
function startScanVerifyPoll() {
    if (scanVerifyTimer) return; // already polling
    scanVerifyTimer = setInterval(async () => {
        try {
            const r = await apiCall('/api/stats').catch(() => null);
            if (!r || !r.ok) return;
            const s = await r.json().catch(() => ({}));
            const busy = (s.running_tasks || 0) > 0 || (s.pending_actions || 0) > 0;
            // Use the WS-driven handler for consistency; fall back to direct update.
            applyWorkerStatus({
                state: busy ? 'running' : 'idle',
                current_task: s.current_task,
                running: s.running_tasks || 0,
                pending: s.pending_actions || 0
            });
            if (!busy) {
                clearInterval(scanVerifyTimer);
                scanVerifyTimer = null;
                // Scan finished — refresh results (counts + Clean/severity status)
                // and settle the indicators into a correct idle state. Must run AFTER
                // applyWorkerStatus so the result severity label wins over "Idle".
                loadScanDetails();
            }
        } catch { /* ignore */ }
    }, 2000);
    // Stop the poll on its own after 90s no matter what (safety net).
    setTimeout(() => {
        if (scanVerifyTimer) { clearInterval(scanVerifyTimer); scanVerifyTimer = null; }
    }, 90000);
}

// Make available globally for button click and stats refresh
window.refreshScanDetails = loadScanDetails;
window.runScan = runScan;