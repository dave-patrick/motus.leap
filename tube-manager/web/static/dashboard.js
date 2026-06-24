const consoleOutput = document.getElementById('console-output');
const token = localStorage.getItem('token') || '';
let ws = null;
let pingInterval = null;
let pongTimeout = null;
let missedPongs = 0;

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
            document.getElementById('stat-subscriptions').textContent = (subData.subscriptions || []).length;
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
        pingInterval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
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
        setTimeout(connectWebSocket, 3000);
    };
}

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
document.getElementById('btn-watch-later').addEventListener('click', () => callAction('watch_later_sync'));
document.getElementById('btn-maintenance').addEventListener('click', () => callAction('apply_maintenance'));
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


// Track progress locally since API doesn't provide real progress
let progressValue = 0;
let wasRunning = false;

// Poll task status to update activity bar, scan details, and cancel button
async function pollTaskStatus() {
    try {
        const resp = await apiCall('/api/stats');
        if (!resp.ok) return;
        const data = await resp.json();
        const isRunning = data.running_tasks > 0 && data.current_task;
        const taskName = data.current_task || '';
        const pendingActions = data.pending_actions || 0;

        // Update Scan Details card
        const scanStatus = document.getElementById('scan-status');
        const lastScan = document.getElementById('last-scan');
        const queuedTasks = document.getElementById('queued-tasks');
        const activeWorkers = document.getElementById('active-workers');

        if (scanStatus) {
            if (isRunning) {
                scanStatus.innerHTML = '<span class="text-yellow-400 animate-pulse">\u25cf ' +
                    DOMPurify.sanitize(taskName, {USE_PROFILES: {html: true}}) + '</span>';
            } else {
                scanStatus.textContent = 'Idle';
                scanStatus.className = 'text-[#2f8fc9] font-medium';
            }
        }
        if (queuedTasks) queuedTasks.textContent = isRunning ? pendingActions : 0;
        if (activeWorkers) activeWorkers.textContent = isRunning ? 1 : 0;

        // Last scan timestamp: update when a task finishes
        if (isRunning) {
            wasRunning = true;
        } else if (wasRunning) {
            wasRunning = false;
            if (lastScan) lastScan.textContent = new Date().toLocaleString();
        } else if (lastScan && data.last_scan && data.last_scan !== 'Never') {
            lastScan.textContent = data.last_scan;
        }

        // Animated progress bar — smoothly increases while running, resets when idle
        const activityBar = document.getElementById('activity-bar');
        const activityPct = document.getElementById('activity-pct');
        if (activityBar && activityPct) {
            if (isRunning) {
                progressValue = Math.min(95, progressValue + Math.random() * 3 + 2);
                activityBar.style.width = Math.round(progressValue) + '%';
                activityPct.textContent = Math.round(progressValue) + '%';
            } else {
                if (progressValue > 0) {
                    activityBar.style.width = '100%';
                    activityPct.textContent = '100%';
                    setTimeout(() => {
                        activityBar.style.width = '0%';
                        activityPct.textContent = '0%';
                    }, 2000);
                }
                progressValue = 0;
            }
        }

        // Cancel button: show in Scan Details card when running
        const scanCancelBtn = document.getElementById('scan-cancel-btn');
        if (scanCancelBtn) {
            if (isRunning) scanCancelBtn.classList.remove('hidden');
            else scanCancelBtn.classList.add('hidden');
        }
    } catch (e) {
        console.warn('Failed to fetch task status', e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    connectWebSocket();
    pollTaskStatus();
    setInterval(pollTaskStatus, 5000);
});