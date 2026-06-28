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

document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    connectWebSocket();
});