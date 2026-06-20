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
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/logs?token=${token}`);

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
document.getElementById('btn-watch-later').addEventListener('click', () => callAction('sync_watch_later'));
document.getElementById('btn-maintenance').addEventListener('click', () => callAction('run_maintenance'));
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

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    connectWebSocket();
});