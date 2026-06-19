// Tab switching logic
function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('[id^="tab-btn-"]').forEach(btn => {
        btn.className = "text-sm font-semibold tracking-wide text-gray-400 hover:text-white pb-2 px-1 focus:outline-none transition-colors border-b-2 border-transparent";
    });
    
    const activePane = document.getElementById(`tab-content-${DOMPurify.sanitize(tabId)}`);
    if (activePane) activePane.classList.remove('hidden');
    
    const activeBtn = document.getElementById(`tab-btn-${DOMPurify.sanitize(tabId)}`);
    if (activeBtn) {
        activeBtn.className = "text-sm font-bold tracking-wide text-white border-b-2 border-blue-500 pb-2 px-1 focus:outline-none transition-colors";
    }
    
    window.location.hash = tabId;
}

// Toast notification system (duplicated from ux-enhancements.js, to be resolved later)
function toast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2 w-80';
        document.body.appendChild(container);
    }
    const el = document.createElement('div');
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    const colors = { success: 'bg-green-600', error: 'bg-red-600', warning: 'bg-yellow-600', info: 'bg-blue-600' };
    el.className = `flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white text-xs font-medium ${colors[type] || colors.info}`;
    el.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${DOMPurify.sanitize(message, {USE_PROFILES: {html: true}})}</span>`;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; setTimeout(() => el.remove(), 300); }, duration);
}

// Settings actions
async function loadPlaylistNames() {
    try {
        const plResp = await fetch('/api/playlists/names');
        if (plResp.ok) {
            const plData = await plResp.json();
            const playlists = plData.playlists || [];
            const select = document.getElementById('watch-later-source');
            if (select) {
                const currentVal = select.value;
                select.innerHTML = '<option value="">-- Auto-detect (Watch Later / Queue / Sort) --</option>';
                playlists.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = DOMPurify.sanitize(p.id);
                    opt.textContent = `${DOMPurify.sanitize(p.title)} (${DOMPurify.sanitize(p.video_count)} videos)`;
                    select.appendChild(opt);
                });
                // Restore selection if the value still exists in the list
                if (currentVal) {
                    const exists = playlists.some(p => p.id === currentVal);
                    if (exists) select.value = currentVal;
                }
            }
        }
    } catch (e) {
        console.warn('Failed to load playlist names', e);
    }
}

async function loadSettings() {
    try {
        // Load all playlists by name for the Watch Later Source dropdown
        await loadPlaylistNames();

        const response = await fetch('/api/settings');
        if (!response.ok) return;
        const data = await response.json();
        if (data.youtube_api_key) {
            document.getElementById('yt-api-key').value = ''; // Clear value on load
            document.getElementById('yt-api-key').placeholder = '•••••••• — previously saved';
        } else {
            document.getElementById('yt-api-key').value = '';
            document.getElementById('yt-api-key').placeholder = 'Enter API key';
        }

        if (data.oauth_client_secret) {
            document.getElementById('oauth-client-secret').value = ''; // Clear value on load
            document.getElementById('oauth-client-secret').placeholder = '•••••••• — previously saved';
        } else {
            document.getElementById('oauth-client-secret').value = '';
            document.getElementById('oauth-client-secret').placeholder = 'Enter OAuth client secret';
        }

        document.getElementById('oauth-client-id').value = DOMPurify.sanitize(data.oauth_client_id || '');
        document.getElementById('max-concurrent').value = DOMPurify.sanitize(data.max_concurrent || 3);
        document.getElementById('auto-sort').checked = data.auto_sort !== false;
        document.getElementById('sync-watch-later').checked = data.sync_watch_later !== false;
        document.getElementById('notify-failures').checked = data.notify_failures === true;
        document.getElementById('dark-mode').checked = data.dark_mode !== false;
        document.getElementById('log-level').value = DOMPurify.sanitize(data.log_level || 'INFO');
        
        if (data.watch_later_playlist_id) {
            const select = document.getElementById('watch-later-source');
            if (select) select.value = DOMPurify.sanitize(data.watch_later_playlist_id);
        }
        
        // AI settings
        const aiProvider = document.getElementById('ai-provider');
        if (aiProvider && data.ai_provider) aiProvider.value = DOMPurify.sanitize(data.ai_provider);
        const aiKey = document.getElementById('ai-api-key');
        if (aiKey) {
            if (data.ai_api_key && data.ai_api_key.startsWith('••••')) {
                aiKey.placeholder = '•••••••• — previously saved';
                aiKey.value = '';
            } else {
                aiKey.placeholder = 'Enter your AI provider API key';
                aiKey.value = DOMPurify.sanitize(data.ai_api_key || '');
            }
        }
        const aiMode = document.getElementById('ai-mode');
        if (aiMode && data.ai_mode) aiMode.value = DOMPurify.sanitize(data.ai_mode);
        const aiPrompt = document.getElementById('ai-prompt');
        if (aiPrompt && data.ai_classification_prompt) aiPrompt.value = DOMPurify.sanitize(data.ai_classification_prompt);
        const aiEndpoint = document.getElementById('ai-custom-endpoint');
        if (aiEndpoint && data.ai_custom_endpoint) aiEndpoint.value = DOMPurify.sanitize(data.ai_custom_endpoint);
        const aiModel = document.getElementById('ai-custom-model');
        if (aiModel && data.ai_custom_model) aiModel.value = DOMPurify.sanitize(data.ai_custom_model);
        toggleCustomAiFields();
        
        // Load AI memory suggestions
        loadAiSuggestions();
        
        if (data.default_privacy) document.getElementById('default-privacy').value = DOMPurify.sanitize(data.default_privacy);
        if (data.scan_interval) document.getElementById('scan-interval').value = DOMPurify.sanitize(data.scan_interval);
        const aiAutoApply = document.getElementById('ai-auto-apply');
        if (aiAutoApply && data.ai_auto_apply_mappings !== undefined) aiAutoApply.checked = data.ai_auto_apply_mappings;

        // Populate storage stats
        document.getElementById('db-size').textContent = DOMPurify.sanitize(data.storage_stats?.db_size || '--');
        document.getElementById('cache-size').textContent = DOMPurify.sanitize(data.storage_stats?.cache_size || '--');
        document.getElementById('thumb-count').textContent = DOMPurify.sanitize(data.storage_stats?.thumb_count || '--');

        // Cookie status
        const cookieStatusEl = document.getElementById('cookie-status');
        if (cookieStatusEl) {
            if (data.browser_cookies_present) {
                cookieStatusEl.innerHTML = '<span class="text-green-500">● YouTube cookies found</span>';
            } else {
                cookieStatusEl.innerHTML = '<span class="text-yellow-500">● No YouTube cookies (browser scraper disabled)</span>';
            }
        }
        const cookieLocationEl = document.getElementById('cookie-location');
        if (cookieLocationEl) {
            cookieLocationEl.textContent = `Path: ${DOMPurify.sanitize(data.browser_cookies_path || 'N/A')}`;
        }

        // Initial tab check from URL hash
        if (window.location.hash) {
            switchTab(window.location.hash.substring(1));
        } else {
            switchTab('general'); // Default to general tab
        }
    } catch (e) {
        console.error(e);
    }
}

async function saveSettings() {
    const ytApiKey = document.getElementById('yt-api-key').value;
    const oauthClientId = document.getElementById('oauth-client-id').value;
    const oauthClientSecret = document.getElementById('oauth-client-secret').value;
    const defaultPrivacy = document.getElementById('default-privacy').value;
    const scanInterval = document.getElementById('scan-interval').value;
    const maxConcurrent = document.getElementById('max-concurrent').value;
    const autoSort = document.getElementById('auto-sort').checked;
    const syncWatchLater = document.getElementById('sync-watch-later').checked;
    const notifyFailures = document.getElementById('notify-failures').checked;
    const darkMode = document.getElementById('dark-mode').checked;
    const logLevel = document.getElementById('log-level').value;
    const watchLaterSource = document.getElementById('watch-later-source').value;

    // AI settings
    const aiProvider = document.getElementById('ai-provider').value;
    const aiApiKey = document.getElementById('ai-api-key').value;
    const aiMode = document.getElementById('ai-mode').value;
    const aiPrompt = document.getElementById('ai-prompt').value;
    const aiCustomEndpoint = document.getElementById('ai-custom-endpoint').value;
    const aiCustomModel = document.getElementById('ai-custom-model').value;
    const aiAutoApply = document.getElementById('ai-auto-apply').checked;

    const payload = {
        youtube_api_key: ytApiKey || undefined, // Only send if not placeholder
        oauth_client_id: oauthClientId || undefined,
        oauth_client_secret: oauthClientSecret || undefined, // Only send if not placeholder
        default_playlist_privacy: defaultPrivacy,
        scan_interval: scanInterval,
        max_concurrent_operations: parseInt(maxConcurrent),
        auto_sort_new_videos: autoSort,
        sync_watch_later_on_scan: syncWatchLater,
        notify_on_failures: notifyFailures,
        dark_mode_only: darkMode,
        log_level: logLevel,
        watch_later_playlist_id: watchLaterSource || undefined,

        ai_provider: aiProvider || undefined,
        ai_api_key: aiApiKey || undefined,
        ai_mode: aiMode || undefined,
        ai_classification_prompt: aiPrompt || undefined,
        ai_custom_endpoint: aiCustomEndpoint || undefined,
        ai_custom_model: aiCustomModel || undefined,
        ai_auto_apply_mappings: aiAutoApply,
    };

    toast('Saving settings...', 'info');
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (response.ok) {
            toast('Settings saved successfully!', 'success');
            await loadSettings(); // Re-load to show saved state and placeholders
        } else {
            const errorData = await response.json();
            toast(`Failed to save settings: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
        }
    } catch (e) {
        toast('Failed to save settings. Network error?', 'error');
    }
}

async function connectYouTube() {
    toast('Redirecting to YouTube for OAuth...', 'info');
    try {
        const response = await fetch('/api/auth/google');
        const data = await response.json();
        if (data.auth_url) {
            window.location.href = data.auth_url;
        } else {
            toast(DOMPurify.sanitize(data.error || 'Failed to get YouTube OAuth URL.'), 'error');
        }
    } catch (e) {
        toast('Failed to initiate YouTube connection. Network error?', 'error');
    }
}

async function disconnectYouTube() {
    if (!confirm('Are you sure you want to disconnect your YouTube account?')) return;
    toast('Disconnecting YouTube account...', 'info');
    try {
        const response = await fetch('/api/auth/disconnect', { method: 'POST' });
        if (response.ok) {
            toast('YouTube account disconnected.', 'success');
            await loadSettings();
        } else {
            const errorData = await response.json();
            toast(`Failed to disconnect: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
        }
    } catch (e) {
        toast('Failed to disconnect YouTube. Network error?', 'error');
    }
}

function toggleCustomAiFields() {
    const providerSelect = document.getElementById('ai-provider');
    const customFields = document.getElementById('ai-custom-fields');
    if (providerSelect.value === 'custom') {
        customFields.classList.remove('hidden');
    } else {
        customFields.classList.add('hidden');
    }
}

// Function to reset AI prompt to default
function resetPrompt() {
    const defaultPrompt = "Classify this YouTube video into one of my playlists based on its title and description. Return ONLY the playlist name, nothing else. If unsure, return 'UNSURE'.";
    document.getElementById('ai-prompt').value = defaultPrompt;
    toast('AI prompt reset to default.', 'info');
}

async function loadChannelMappings() {
    const mappingsList = document.getElementById('mappings-list');
    if (!mappingsList) return;
    mappingsList.innerHTML = '<div class="text-center py-4 text-gray-500"><i class="fa-solid fa-spinner fa-spin mr-2"></i>Loading mappings...</div>';

    try {
        const resp = await fetch('/api/rules/mappings');
        if (!resp.ok) throw new Error('Failed to load mappings');
        const data = await resp.json();

        if (!data.mappings || data.mappings.length === 0) {
            mappingsList.innerHTML = '<div class="text-center py-4 text-gray-500">No channel mappings found.</div>';
            return;
        }

        mappingsList.innerHTML = data.mappings.map(m => `
            <div class="flex items-center justify-between p-2 hover:bg-[#1f2229] rounded">
                <span class="text-[10px] text-gray-300 truncate w-1/2">${DOMPurify.sanitize(m.channel_title || m.channel)}</span>
                <i class="fa-solid fa-arrow-right text-gray-500 text-[8px] mx-2"></i>
                <span class="text-[10px] text-blue-400 truncate w-1/2 text-right">${DOMPurify.sanitize(m.playlist_title || m.playlist)}</span>
            </div>
        `).join('');

    } catch (e) {
        mappingsList.innerHTML = `<div class="text-center py-4 text-red-400">Failed to load mappings: ${DOMPurify.sanitize(e.message)}</div>`;
        console.error('Failed to load channel mappings:', e);
    }
}

async function saveMappings() {
    const mappingsList = document.getElementById('mappings-list');
    if (!mappingsList) return;

    const newMappings = {};
    // In a real app, you'd have input fields to edit these mappings.
    // For now, we'll just fetch the current config's mappings and resave them as a placeholder.
    toast('Saving mappings (feature in development)...', 'info');
    // Actual save logic will be implemented here once editable UI is present.
}

async function validateRules() {
    const rulesEditor = document.getElementById('rules-editor');
    if (!rulesEditor) return;
    const rules = rulesEditor.value;

    try {
        JSON.parse(rules);
        toast('JSON rules are valid!', 'success');
    } catch (e) {
        toast(`JSON parsing error: ${DOMPurify.sanitize(e.message)}`, 'error');
    }
}

async function applyRules() {
    const rulesEditor = document.getElementById('rules-editor');
    if (!rulesEditor) return;
    const rules = rulesEditor.value;

    try {
        JSON.parse(rules); // Validate first
        toast('Applying rules...', 'info');
        const response = await fetch('/api/rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rules_json: rules })
        });

        if (response.ok) {
            toast('Rules applied successfully!', 'success');
        } else {
            const errorData = await response.json();
            toast(`Failed to apply rules: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
        }
    } catch (e) {
        toast(`Failed to apply rules: ${DOMPurify.sanitize(e.message)}`, 'error');
    }
}

async function loadAiSuggestions() {
    const aiSuggestionsEl = document.getElementById('ai-suggestions');
    const aiMemoryCountEl = document.getElementById('ai-memory-count');
    if (!aiSuggestionsEl || !aiMemoryCountEl) return;

    aiSuggestionsEl.innerHTML = '<div class="text-[10px] text-gray-500 italic text-center py-4">Loading AI suggestions...</div>';

    try {
        const resp = await fetch('/api/ai/suggestions');
        if (!resp.ok) throw new Error('Failed to load AI suggestions');
        const data = await resp.json();

        const totalMoves = data.total_moves || 0;
        aiMemoryCountEl.textContent = `${DOMPurify.sanitize(totalMoves)} moves`;

        if (!data.suggestions || data.suggestions.length === 0) {
            aiSuggestionsEl.innerHTML = '<div class="text-[10px] text-gray-500 italic">Move videos to build up training data. Suggestions will appear here after 3+ moves from the same channel to the same playlist.</div>';
            return;
        }

        aiSuggestionsEl.innerHTML = data.suggestions.map(s => `
            <div class="flex items-center gap-2 p-2 bg-[#1a1d24] border border-[#2a2f3a] rounded-lg">
                <i class="fa-solid fa-lightbulb text-yellow-500 text-[10px]"></i>
                <div class="flex-1 min-w-0">
                    <div class="font-semibold text-white truncate text-[11px]">Channel: ${DOMPurify.sanitize(s.channel_title)}</div>
                    <div class="text-[10px] text-gray-400">Suggests: <span class="text-blue-400">${DOMPurify.sanitize(s.playlist_name)}</span> (moved ${DOMPurify.sanitize(s.move_count)} times)</div>
                </div>
                <button class="text-[9px] px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white apply-ai-suggestion-btn" data-channel-id="${DOMPurify.sanitize(s.channel_id)}" data-playlist-id="${DOMPurify.sanitize(s.playlist_id)}" data-channel-title="${DOMPurify.sanitize(s.channel_title)}" data-playlist-name="${DOMPurify.sanitize(s.playlist_name)}">Apply</button>
            </div>
        `).join('');

    } catch (e) {
        aiSuggestionsEl.innerHTML = `<div class="text-[10px] text-red-400 italic text-center py-4">Failed to load AI suggestions: ${DOMPurify.sanitize(e.message)}</div>`;
        console.error('Failed to load AI suggestions:', e);
    }
}

async function applyAiSuggestion(channelId, playlistId, channelTitle, playlistName) {
    toast(`Applying suggestion: ${channelTitle} -> ${playlistName}`, 'info');
    try {
        const response = await fetch('/api/rules/mappings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mappings: [{ channel: channelId, playlist: playlistId }] })
        });
        if (response.ok) {
            toast('Mapping applied!', 'success');
            await loadSettings(); // Reload settings to update mappings list
        } else {
            const errorData = await response.json();
            toast(`Failed to apply mapping: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
        }
    } catch (e) {
        toast(`Failed to apply mapping: ${DOMPurify.sanitize(e.message)}`, 'error');
    }
}

// Diagnostics functions (from dashboard.js, to be refined)
async function runDiagnose() {
    toast('Running diagnostics...', 'info');
    const diagLog = document.getElementById('diag-log');
    if (diagLog) diagLog.textContent = 'Running diagnostics...';
    try {
        const resp = await fetch('/api/diagnose');
        const data = await resp.json();
        if (diagLog) diagLog.textContent = DOMPurify.sanitize(JSON.stringify(data, null, 2));
        toast('Diagnostics complete.', 'success');
    } catch (e) {
        if (diagLog) diagLog.textContent = `Failed to run diagnostics: ${DOMPurify.sanitize(e.message)}`;
        toast('Diagnostics failed.', 'error');
    }
}

async function runSurface() {
    toast('Surfacing diagnostics...', 'info');
    const diagLog = document.getElementById('diag-log');
    if (diagLog) diagLog.textContent = 'Surfacing diagnostics...';
    try {
        const resp = await fetch('/api/surface'); // Assuming this endpoint exists
        const data = await resp.json();
        if (diagLog) diagLog.textContent = DOMPurify.sanitize(JSON.stringify(data, null, 2));
        toast('Surface diagnostics complete.', 'success');
    } catch (e) {
        if (diagLog) diagLog.textContent = `Failed to surface diagnostics: ${DOMPurify.sanitize(e.message)}`;
        toast('Surface diagnostics failed.', 'error');
    }
}

async function viewSystemLogs() {
    toast('Fetching system logs...', 'info');
    const diagLog = document.getElementById('diag-log');
    if (diagLog) diagLog.textContent = 'Fetching logs...';
    try {
        const resp = await fetch('/api/logs'); // Assuming this endpoint exists
        const data = await resp.text();
        if (diagLog) diagLog.textContent = DOMPurify.sanitize(data);
        toast('System logs loaded.', 'success');
    } catch (e) {
        if (diagLog) diagLog.textContent = `Failed to load logs: ${DOMPurify.sanitize(e.message)}`;
        toast('Failed to load logs.', 'error');
    }
}

async function resetAllSettings() {
    if (!confirm('Are you sure you want to reset all settings to default? This cannot be undone.')) return;
    toast('Resetting settings...', 'warning');
    try {
        const response = await fetch('/api/settings/reset', { method: 'POST' });
        if (response.ok) {
            toast('All settings reset to default.', 'success');
            await loadSettings();
        } else {
            const errorData = await response.json();
            toast(`Failed to reset settings: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
        }
    } catch (e) {
        toast('Failed to reset settings. Network error?', 'error');
    }
}

async function clearThumbnailCache() {
    if (!confirm('Are you sure you want to clear the thumbnail cache?')) return;
    toast('Clearing thumbnail cache...', 'info');
    try {
        const response = await fetch('/api/storage/clear-thumbnails', { method: 'POST' });
        if (response.ok) {
            toast('Thumbnail cache cleared.', 'success');
            await loadSettings();
        } else {
            const errorData = await response.json();
            toast(`Failed to clear cache: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
        }
    } catch (e) {
        toast('Failed to clear cache. Network error?', 'error');
    }
}

async function exportAllData() {
    toast('Exporting all data...', 'info');
    try {
        const response = await fetch('/api/bulk/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ resource_type: 'all', format: 'json' })
        });
        if (response.ok) {
            const data = await response.json();
            const blob = new Blob([JSON.stringify(data.data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `motus.leap_export_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            toast('Data exported successfully!', 'success');
        } else {
            const errorData = await response.json();
            toast(`Failed to export data: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
        }
    } catch (e) {
        toast('Failed to export data. Network error?', 'error');
    }
}

async function uploadCookies() {
    const fileInput = document.getElementById('cookie-file');
    const file = fileInput.files[0];
    if (!file) {
        toast('Please select a JSON cookie file to upload.', 'warning');
        return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const cookies = JSON.parse(e.target.result);
            toast('Uploading cookies...', 'info');
            const response = await fetch('/api/browser/cookies', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cookies: cookies })
            });

            if (response.ok) {
                toast('YouTube cookies uploaded and saved!', 'success');
                await loadSettings();
            } else {
                const errorData = await response.json();
                toast(`Failed to upload cookies: ${DOMPurify.sanitize(errorData.detail || response.statusText)}`, 'error');
            }
        } catch (parseError) {
            toast(`Invalid JSON file: ${DOMPurify.sanitize(parseError.message)}`, 'error');
        }
    };
    reader.readAsText(file);
}

function toggleSecretVisibility(inputId, button) {
    const input = document.getElementById(inputId);
    const icon = button.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();

    // Event listeners for tab buttons
    document.getElementById('tab-btn-general')?.addEventListener('click', () => switchTab('general'));
    document.getElementById('tab-btn-rules')?.addEventListener('click', () => switchTab('rules'));
    document.getElementById('tab-btn-ai')?.addEventListener('click', () => switchTab('ai'));

    // Event listeners for action buttons
    document.getElementById('save-settings-btn')?.addEventListener('click', saveSettings);
    document.getElementById('connect-youtube-btn')?.addEventListener('click', connectYouTube);
    document.getElementById('disconnect-youtube-btn')?.addEventListener('click', disconnectYouTube);
    document.getElementById('run-diagnose-btn')?.addEventListener('click', runDiagnose);
    document.getElementById('run-surface-btn')?.addEventListener('click', runSurface);
    document.getElementById('clear-thumbnail-cache-btn')?.addEventListener('click', clearThumbnailCache);
    document.getElementById('export-all-data-btn')?.addEventListener('click', exportAllData);
    document.getElementById('upload-cookies-btn')?.addEventListener('click', uploadCookies);
    document.getElementById('view-system-logs-btn')?.addEventListener('click', viewSystemLogs);
    document.getElementById('reset-all-settings-btn')?.addEventListener('click', resetAllSettings);
    document.getElementById('beautify-json-btn')?.addEventListener('click', beautifyJson);
    document.getElementById('apply-rules-btn')?.addEventListener('click', applyRules);
    document.getElementById('validate-json-btn')?.addEventListener('click', validateRules);
    document.getElementById('load-channel-mappings-btn')?.addEventListener('click', loadChannelMappings);
    document.getElementById('save-mappings-btn')?.addEventListener('click', saveMappings);
    document.getElementById('ai-provider')?.addEventListener('change', toggleCustomAiFields);
    document.getElementById('reset-ai-prompt-btn')?.addEventListener('click', resetPrompt);
    document.getElementById('load-ai-suggestions-btn')?.addEventListener('click', loadAiSuggestions);
    document.getElementById('watch-later-set-manual-id-btn')?.addEventListener('click', () => {
        const manualId = document.getElementById('watch-later-id-manual').value;
        if (manualId) {
            document.getElementById('watch-later-source').value = manualId;
            toast('Manual ID set', 'success');
        }
    });

    // Event delegation for AI suggestions (apply button)
    document.getElementById('ai-suggestions')?.addEventListener('click', (event) => {
        const target = event.target;
        if (target.classList.contains('apply-ai-suggestion-btn') || target.closest('.apply-ai-suggestion-btn')) {
            event.stopPropagation();
            const btn = target.closest('.apply-ai-suggestion-btn');
            const channelId = btn.dataset.channelId;
            const playlistId = btn.dataset.playlistId;
            const channelTitle = btn.dataset.channelTitle;
            const playlistName = btn.dataset.playlistName;
            applyAiSuggestion(channelId, playlistId, channelTitle, playlistName);
        }
    });
});

function beautifyJson() {
    const editor = document.getElementById('rules-editor');
    if (editor) {
        try {
            const parsed = JSON.parse(editor.value);
            editor.value = JSON.stringify(parsed, null, 2);
            toast('JSON beautified.', 'info');
        } catch (e) {
            toast(`Invalid JSON: ${DOMPurify.sanitize(e.message)}`, 'error');
        }
    }
}