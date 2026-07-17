// ============================================
// ENHANCED UX: Loading States, Error Handling, Keyboard Shortcuts
// ============================================

// Global state for loading states
var loadingStates = new Map();
var errorQueue = [];

// ============================================
// LOADING STATES
// ============================================

/**
 * Show loading skeleton for a section
 * @param {string} elementId - Element to show skeleton in
 */
function showSkeletonLoader(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;

    element.innerHTML = `
        <div class="skeleton-loader">
            <div class="skeleton-item skeleton-header"></div>
            <div class="skeleton-item skeleton-content"></div>
            <div class="skeleton-item skeleton-content"></div>
            <div class="skeleton-item skeleton-content"></div>
        </div>
        <style>
            .skeleton-loader {
                animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
            }
            .skeleton-item {
                background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
                background-size: 200% 100%;
                border-radius: 4px;
            }
            .skeleton-header {
                height: 32px;
                width: 60%;
                margin-bottom: 16px;
            }
            .skeleton-content {
                height: 16px;
                width: 100%;
                margin-bottom: 8px;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
        </style>
    `;
}

/**
 * Hide loading skeleton
 * @param {string} elementId - Element to hide skeleton from
 */
function hideSkeletonLoader(elementId) {
    const element = document.getElementById(elementId);
    if (!element) return;
    // Remove skeleton, content will be injected by API response
}

/**
 * Show loading overlay
 * @param {string} message - Loading message
 */
function showLoadingOverlay(message = "Loading...") {
    const overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50';
    overlay.innerHTML = `
        <div class="bg-gray-800 rounded-lg p-6 flex flex-col items-center gap-4 shadow-2xl">
            <div class="w-12 h-12 border-4 border-[#2f8fc9] border-t-transparent rounded-full animate-spin"></div>
            <p class="text-white font-medium">${escapeHtml(message)}</p>
            <button onclick="hideLoadingOverlay()" class="text-gray-400 hover:text-white text-sm">Cancel</button>
        </div>
    `;
    document.body.appendChild(overlay);
}

/**
 * Hide loading overlay
 */
function hideLoadingOverlay() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.remove();
    }
}

/**
 * Show loading indicator on button
 * @param {string} buttonId - Button ID
 * @param {string} originalText - Original button text
 */
function showButtonLoading(buttonId, originalText) {
    const button = document.getElementById(buttonId);
    if (!button) return;

    button.disabled = true;
    button.innerHTML = `
        <span class="inline-flex items-center gap-2">
            <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
            <span>Loading...</span>
        </span>
    `;
    button.dataset.originalText = originalText;
}

/**
 * Reset button to original state
 * @param {string} buttonId - Button ID
 */
function hideButtonLoading(buttonId) {
    const button = document.getElementById(buttonId);
    if (!button) return;

    button.disabled = false;
    button.textContent = button.dataset.originalText || 'Submit';
}

// ============================================
// ERROR HANDLING
// ============================================

/**
 * Show error toast
 * @param {string} title - Error title
 * @param {string} message - Error message
 * @param {string} action - Action button text (optional)
 * @param {function} actionCallback - Action callback (optional)
 */
function showErrorToast(title, message, action = null, actionCallback = null) {
    const toast = document.createElement('div');
    toast.className = 'fixed top-24 right-4 bg-red-500 text-white px-6 py-4 rounded-lg shadow-2xl z-50 animate-slide-in-right flex flex-col gap-2 max-w-md';
    toast.innerHTML = `
        <div class="flex items-start gap-3">
            <div class="flex-shrink-0">
                <i class="fa-solid fa-circle-exclamation text-xl"></i>
            </div>
            <div class="flex-1">
                <h4 class="font-bold text-lg">${escapeHtml(title)}</h4>
                <p class="text-sm text-red-100">${escapeHtml(message)}</p>
            </div>
            <button onclick="this.parentElement.parentElement.remove()" class="flex-shrink-0 text-red-200 hover:text-white">
                <i class="fa-solid fa-xmark"></i>
            </button>
        </div>
        ${action ? `
            <button class="mt-2 bg-white text-red-500 px-4 py-2 rounded font-medium hover:bg-red-50 transition-colors text-sm" onclick="${actionCallback ? `(${actionCallback.toString()})()` : ''}">
                ${escapeHtml(action)}
            </button>
        ` : ''}
    `;

    document.body.appendChild(toast);

    // Auto-dismiss after 8 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 8000);
}

/**
 * Show success toast
 * @param {string} message - Success message
 */
function showSuccessToast(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed top-24 right-4 bg-green-500 text-white px-6 py-4 rounded-lg shadow-2xl z-50 animate-slide-in-right flex items-center gap-3 max-w-md';
    toast.innerHTML = `
        <i class="fa-solid fa-circle-check text-xl"></i>
        <p class="font-medium">${escapeHtml(message)}</p>
        <button onclick="this.parentElement.remove()" class="flex-shrink-0 text-green-200 hover:text-white">
            <i class="fa-solid fa-xmark"></i>
        </button>
    `;

    document.body.appendChild(toast);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

/**
 * Show info toast
 * @param {string} message - Info message
 */
function showInfoToast(message) {
    const toast = document.createElement('div');
    toast.className = 'fixed top-24 right-4 bg-[#2f8fc9] text-white px-6 py-4 rounded-lg shadow-2xl z-50 animate-slide-in-right flex items-center gap-3 max-w-md';
    toast.innerHTML = `
        <i class="fa-solid fa-circle-info text-xl"></i>
        <p class="font-medium">${escapeHtml(message)}</p>
        <button onclick="this.parentElement.remove()" class="flex-shrink-0 text-[#a8d4f0] hover:text-white">
            <i class="fa-solid fa-xmark"></i>
        </button>
    `;

    document.body.appendChild(toast);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.remove();
        }
    }, 5000);
}

/**
 * Handle API error
 * @param {Error} error - Error object
 * @param {string} context - Context of error
 */
function handleApiError(error, context = 'API request') {
    console.error(`[${context}] Error:`, error);

    // Get user-friendly message
    let message = error.message || 'An unexpected error occurred';

    // Check for specific error types
    if (error.message?.includes('401')) {
        message = 'You need to reconnect to YouTube. Please click the Connect button.';
        showErrorToast('Authentication Required', message, 'Reconnect', () => window.location.href = '/oauth/start');
        return;
    }

    if (error.message?.includes('403') || error.message?.includes('quota')) {
        message = 'YouTube API quota exceeded. Please try again later.';
        showErrorToast('Quota Exceeded', message);
        return;
    }

    if (error.message?.includes('network') || error.message?.includes('ECONNREFUSED')) {
        message = 'Network error. Please check your connection and try again.';
        showErrorToast('Network Error', message, 'Retry', () => window.location.reload());
        return;
    }

    // Generic error
    showErrorToast('Error', message, 'Retry', () => window.location.reload());
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} - Escaped text
 */
function escapeHtml(text) {
    if (typeof text !== 'string') return text;

    return DOMPurify.sanitize(text, {
        ALLOWED_TAGS: [],
        ALLOWED_ATTR: []
    });
}

// ============================================
// KEYBOARD SHORTCUTS
// ============================================

/**
 * Initialize keyboard shortcuts
 */
function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // Ignore if in input field
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        const key = e.key.toLowerCase();
        const modifiers = [];

        if (e.ctrlKey) modifiers.push('ctrl');
        if (e.metaKey) modifiers.push('meta');
        if (e.shiftKey) modifiers.push('shift');
        if (e.altKey) modifiers.push('alt');

        const combo = [...modifiers, key].join('+');

        // Prevent default for registered shortcuts
        switch (combo) {
            // Navigation
            case 'g+d': // Ctrl+G D → Dashboard
            case 'meta+d':
                e.preventDefault();
                window.location.href = '/dashboard';
                break;

            case 'g+p': // Ctrl+G P → Playlists
            case 'meta+p':
                e.preventDefault();
                window.location.href = '/playlists';
                break;

            case 'g+s': // Ctrl+G S → Subscriptions
            case 'meta+s':
                e.preventDefault();
                window.location.href = '/subscriptions';
                break;

            case 'g+r': // Ctrl+G R → Rules
            case 'meta+r':
                e.preventDefault();
                window.location.href = '/rules';
                break;

            case 'g+a': // Ctrl+G A → AI
            case 'meta+a':
                e.preventDefault();
                window.location.href = '/ai';
                break;

            // Actions
            case 'f': // F → Focus search
                e.preventDefault();
                focusSearch();
                break;

            case '/': // / → Focus search
                e.preventDefault();
                focusSearch();
                break;

            case 'escape': // Escape → Clear search
                clearSearch();
                break;

            case 'n': // N → New action
                e.preventDefault();
                triggerNewAction();
                break;

            case 'r': // R → Refresh
                e.preventDefault();
                refreshCurrentPage();
                break;

            case 's': // S → Save
                e.preventDefault();
                saveCurrentPage();
                break;

            case '?': // ? → Show shortcuts help
                e.preventDefault();
                showShortcutsHelp();
                break;

            // Dashboard specific
            case 'ctrl+f': // Ctrl+F → Full scan
            case 'meta+f':
                if (window.location.pathname === '/dashboard') {
                    e.preventDefault();
                    triggerFullScan();
                }
                break;

            case 'ctrl+a': // Ctrl+A → Auto-sort
            case 'meta+a':
                if (window.location.pathname === '/dashboard') {
                    e.preventDefault();
                    triggerAutoSort();
                }
                break;
        }
    });
}

/**
 * Focus search input
 */
function focusSearch() {
    const searchInput = document.querySelector('input[type="search"], input[placeholder*="Search"]');
    if (searchInput) {
        searchInput.focus();
        showInfoToast('Press Enter to search, Esc to clear');
    }
}

/**
 * Clear search
 */
function clearSearch() {
    const searchInput = document.querySelector('input[type="search"], input[placeholder*="Search"]');
    if (searchInput) {
        searchInput.value = '';
        searchInput.dispatchEvent(new Event('input'));
        showInfoToast('Search cleared');
    }
}

/**
 * Trigger new action
 */
function triggerNewAction() {
    // Show action menu or modal
    const actionButton = document.querySelector('[data-action="new"]');
    if (actionButton) {
        actionButton.click();
    } else {
        showInfoToast('No action available on this page');
    }
}

/**
 * Refresh current page
 */
function refreshCurrentPage() {
    showLoadingOverlay('Refreshing...');
    window.location.reload();
}

/**
 * Save current page
 */
function saveCurrentPage() {
    // Look for save button
    const saveButton = document.querySelector('button[onclick*="save"], button[data-action="save"]');
    if (saveButton) {
        saveButton.click();
        showInfoToast('Saving...');
    } else {
        showInfoToast('Nothing to save on this page');
    }
}

/**
 * Show keyboard shortcuts help modal
 */
function showShortcutsHelp() {
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50';
    modal.innerHTML = `
        <div class="bg-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4 shadow-2xl max-h-[80vh] overflow-y-auto">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-2xl font-bold text-white">Keyboard Shortcuts</h2>
                <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-white">
                    <i class="fa-solid fa-xmark text-xl"></i>
                </button>
            </div>

            <div class="space-y-6">
                <div>
                    <h3 class="text-lg font-semibold text-white mb-2">Navigation</h3>
                    <ul class="space-y-2">
                        <li class="flex justify-between text-gray-300">
                            <span>Go to Dashboard</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">G + D</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Go to Playlists</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">G + P</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Go to Subscriptions</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">G + S</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Go to Rules</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">G + R</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Go to AI</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">G + A</kbd>
                        </li>
                    </ul>
                </div>

                <div>
                    <h3 class="text-lg font-semibold text-white mb-2">Actions</h3>
                    <ul class="space-y-2">
                        <li class="flex justify-between text-gray-300">
                            <span>Focus search</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">F</kbd> or <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">/</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Clear search</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">Esc</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>New action</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">N</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Refresh</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">R</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Save</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">S</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Show help</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">?</kbd>
                        </li>
                    </ul>
                </div>

                <div>
                    <h3 class="text-lg font-semibold text-white mb-2">Dashboard</h3>
                    <ul class="space-y-2">
                        <li class="flex justify-between text-gray-300">
                            <span>Full Playlist Sync</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">Ctrl + F</kbd>
                        </li>
                        <li class="flex justify-between text-gray-300">
                            <span>Force Auto-Sort</span>
                            <kbd class="bg-gray-700 px-2 py-1 rounded text-sm">Ctrl + A</kbd>
                        </li>
                    </ul>
                </div>
            </div>

            <div class="mt-6 text-center text-gray-400 text-sm">
                Press <kbd class="bg-gray-700 px-2 py-1 rounded">Esc</kbd> to close
            </div>
        </div>
    `;

    // Close on escape
    modal.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            modal.remove();
        }
    });

    // Close on background click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });

    document.body.appendChild(modal);
}

// ============================================
// SEARCH & FILTERING
// ============================================

/**
 * Initialize search and filtering
 */
function initSearch() {
    const searchInputs = document.querySelectorAll('input[type="search"], input[placeholder*="Search"]');

    searchInputs.forEach(input => {
        // Real-time search
        input.addEventListener('input', debounce((e) => {
            const query = e.target.value.trim();
            performSearch(query);
        }, 300));

        // Enter key search
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const query = e.target.value.trim();
                performSearch(query);
            }
        });
    });
}

/**
 * Perform search
 * @param {string} query - Search query
 */
function performSearch(query) {
    if (!query) {
        // Show all items
        showAllItems();
        return;
    }

    // Filter items based on query
    const items = document.querySelectorAll('[data-searchable]');
    const queryLower = query.toLowerCase();

    let visibleCount = 0;

    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        if (text.includes(queryLower)) {
            item.style.display = '';
            visibleCount++;
        } else {
            item.style.display = 'none';
        }
    });

    showInfoToast(`Found ${visibleCount} results for "${escapeHtml(query)}"`);
}

/**
 * Show all items
 */
function showAllItems() {
    const items = document.querySelectorAll('[data-searchable]');
    items.forEach(item => {
        item.style.display = '';
    });
}

/**
 * Debounce function
 * @param {function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {function} - Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ============================================
// INITIALIZATION
// ============================================

/**
 * Initialize all UX enhancements
 */
function initUXEnhancements() {
    // Keyboard shortcuts
    initKeyboardShortcuts();

    // Search and filtering
    initSearch();

    // Add loading states to buttons
    document.querySelectorAll('button[data-action]').forEach(button => {
        button.addEventListener('click', (e) => {
            const action = button.dataset.action;
            showButtonLoading(button.id, button.textContent);
        });
    });

    // Show help tooltip on first visit
    if (!localStorage.getItem('shortcutsHelpShown')) {
        setTimeout(() => {
            showInfoToast('Press ? to see keyboard shortcuts');
            localStorage.setItem('shortcutsHelpShown', 'true');
        }, 2000);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initUXEnhancements);


// ============================================
// SYSTEM ACTIVITY BOX CONTROLLER
// ============================================

function initSystemActivityController() {
    const box = document.getElementById('system-activity-box');
    if (!box) return;

    const taskDescEl = document.getElementById('activity-task-desc');
    const taskEl = document.getElementById('activity-task');
    const pingColor = document.getElementById('activity-ping-color');
    const pingAnimate = document.getElementById('activity-ping-animate');
    
    // Progress elements
    const progressContainer = document.getElementById('activity-progress-container');
    const progressBar = document.getElementById('activity-progress-bar');
    const progressText = document.getElementById('activity-progress-text');
    const timeEstimate = document.getElementById('activity-time-estimate');

    let progressInterval = null;
    let currentPercent = 0;
    let currentTaskName = '';

    function startProgress(taskName) {
        if (progressInterval && currentTaskName === taskName) return;
        
        clearInterval(progressInterval);
        currentTaskName = taskName;
        currentPercent = 0;
        
        if (progressContainer) progressContainer.classList.remove('hidden');
        
        let estSeconds = 30;
        let ratePerSec = 3.3;
        
        if (taskName.includes('Full Playlist') || taskName.includes('Sync')) {
            estSeconds = 45;
            ratePerSec = 2.2;
} else if (taskName.includes('Scan') || taskName.includes('Duplicate') || taskName.includes('Misplaced')) {
            estSeconds = 5;
            ratePerSec = 20;
        }
        
        if (timeEstimate) timeEstimate.textContent = `Est: ~${estSeconds}s`;
        
        progressInterval = setInterval(() => {
            if (currentPercent < 90) {
                currentPercent += ratePerSec;
            } else if (currentPercent < 98) {
                currentPercent += 0.2; // slow down crawl as we get close
            }
            
            const percentRounded = Math.min(Math.round(currentPercent), 99);
            if (progressBar) progressBar.style.width = `${percentRounded}%`;
            if (progressText) progressText.textContent = `Progress: ${percentRounded}%`;
            
            const remaining = Math.max(0, Math.round(estSeconds - (currentPercent / ratePerSec)));
            if (timeEstimate && remaining > 0) {
                timeEstimate.textContent = `Est: ~${remaining}s`;
            }
        }, 1000);
    }

    function stopProgress(isComplete = true) {
        clearInterval(progressInterval);
        progressInterval = null;
        
        if (isComplete && currentPercent > 0) {
            if (progressBar) progressBar.style.width = '100%';
            if (progressText) progressText.textContent = 'Progress: 100%';
            if (timeEstimate) timeEstimate.textContent = 'Complete';
            
            setTimeout(() => {
                if (progressContainer) progressContainer.classList.add('hidden');
                if (progressBar) progressBar.style.width = '0%';
                currentPercent = 0;
                currentTaskName = '';
            }, 3000);
        } else {
            if (progressContainer) progressContainer.classList.add('hidden');
            currentPercent = 0;
            currentTaskName = '';
        }
    }

    async function pollStats() {
        try {
            const resp = await fetch('/api/stats');
            if (resp.ok) {
                const data = await resp.json();
                const activeTask = data.current_task || '';
                const isRunning = data.running_tasks > 0 && activeTask;
                
                if (taskEl) taskEl.textContent = activeTask || 'Idle';
                
                if (isRunning) {
                    if (taskDescEl) {
                        taskDescEl.textContent = `${activeTask} • In progress...`;
                    }
                    if (pingColor) pingColor.className = "relative inline-flex rounded-full h-2 w-2 bg-yellow-500";
                    if (pingAnimate) pingAnimate.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75";
                    
                    startProgress(activeTask);
                } else {
                    if (taskDescEl) {
                        taskDescEl.textContent = currentPercent > 0 ? 'Idle • Complete!' : 'Idle • System is ready.';
                    }
                    if (pingColor) pingColor.className = "relative inline-flex rounded-full h-2 w-2 bg-green-500";
                    if (pingAnimate) pingAnimate.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75";
                    
                    stopProgress(true);
                }
            }
        } catch (e) {
            console.error('Failed to fetch stats', e);
        }
    }

        let statsIntervalId = null;
    const STATS_INTERVAL_MS = 30 * 1000; // 30 seconds

    function startStatsPolling() {
        if (statsIntervalId !== null) return;
        statsIntervalId = setInterval(pollStats, STATS_INTERVAL_MS);
    }

    function stopStatsPolling() {
        if (statsIntervalId !== null) {
            clearInterval(statsIntervalId);
            statsIntervalId = null;
        }
    }

    // Initial load
    pollStats();
    startStatsPolling();

    // Also refresh scan details panel on each poll cycle
    if (window.refreshScanDetails) window.refreshScanDetails();

    // Pause polling when page is hidden
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
}

document.addEventListener('DOMContentLoaded', initSystemActivityController);


// ============================================
// SINGLE PAGE APPLICATION (SPA) ROUTER
// ============================================

async function navigateSPA(url) {
    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            window.location.href = url; // Fallback to normal navigation
            return;
        }
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const currentAside = document.querySelector('aside');
        const currentHeader = document.querySelector('header');
        const newAside = doc.querySelector('aside');
        const newHeader = doc.querySelector('header');

        // Update body class if different
        document.body.className = doc.body.className;

        // 1. Keep current aside, header, and global agent drawer; remove all other body children
        const globalDrawer = document.getElementById('global-agent-drawer');
        Array.from(document.body.children).forEach(child => {
            if (child !== currentAside && child !== currentHeader && child !== globalDrawer && child.tagName !== 'SCRIPT') {
                document.body.removeChild(child);
            }
        });

        // 2. Add all new body children except its ASIDE, HEADER, and global drawer
        const scriptsToRun = [];
        Array.from(doc.body.children).forEach(child => {
            if (child.tagName !== 'ASIDE' && child.tagName !== 'HEADER' && child.id !== 'global-agent-drawer') {
                // Find scripts inside the child
                child.querySelectorAll('script').forEach(s => {
                    scriptsToRun.push(s);
                    s.remove(); // Remove from markup so we don't double append
                });
                document.body.appendChild(child);
            }
        });

        // 3. Re-insert preserved header at the top of body (where new header would have been)
        if (currentHeader) {
            document.body.insertBefore(currentHeader, document.body.firstChild);
        }

        if (currentAside) {
            const flexWrapper = document.querySelector('.flex.flex-1');
            const mainEl = document.querySelector('main');
            if (flexWrapper && mainEl) {
                flexWrapper.insertBefore(currentAside, mainEl);
            } else {
                document.body.appendChild(currentAside);
            }
        }

        // 4. Update the active sidebar link highlighting
        if (currentAside) {
            currentAside.querySelectorAll('nav a').forEach(a => {
                const path = a.getAttribute('href');
                if (path === url || (path === '/' && url === '/dashboard') || (url.startsWith('/playlist') && path === '/playlists')) {
                    a.className = "flex items-center gap-3 px-3 py-2.5 rounded-lg bg-[#2f8fc9]/20 text-[#2f8fc9] text-xs font-semibold border border-[#2f8fc9]/30";
                } else {
                    a.className = "flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-[#2a2f3a] text-xs font-medium transition-colors";
                }
            });
        }

        // 5. Run scripts in order
        scriptsToRun.forEach(oldScript => {
            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
            if (oldScript.innerHTML) {
                newScript.appendChild(document.createTextNode(oldScript.innerHTML));
            }
            document.body.appendChild(newScript);
        });

        // 6. Fire DOMContentLoaded to trigger page initializations
        setTimeout(() => {
            document.dispatchEvent(new Event('DOMContentLoaded'));
        }, 50);

    } catch (e) {
        console.error('SPA Navigation error:', e);
        window.location.href = url; // Fallback
    }
}

// Intercept clicks on links or button navigation
// DISABLED: SPA body-rebuild caused duplicate <aside> navs and skeleton-stuck
// races on cold load. Full-page navigation is reliable (verified on reload).
// document.addEventListener('click', (e) => {
//     const closestButton = e.target.closest('button');
//     const closestLink = e.target.closest('a');
//     if (closestLink && closestLink.getAttribute('href')) {
//         const href = closestLink.getAttribute('href');
//         const isNavLink = closestLink.classList.contains('nav-item') ||
//                           closestLink.closest('nav') ||
//                           closestLink.closest('aside');
//         if (isNavLink && href.startsWith('/') && !href.startsWith('/auth') && !href.startsWith('/oauth') && !href.startsWith('/api')) {
//             e.preventDefault();
//             window.history.pushState(null, '', href);
//             navigateSPA(href);
//             return;
//         }
//     }
// }, true); // Capture phase to run before inline handlers
//
// window.addEventListener('popstate', () => {
//     navigateSPA(window.location.pathname);
// });


// ============================================
// GLOBAL AGENT DRAWER CONTROLLER
// ============================================

window.toggleAgentDrawer = function() {
    const drawer = document.getElementById('global-agent-drawer');
    const consoleEl = document.getElementById('agent-drawer-console');
    const icon = document.getElementById('agent-drawer-toggle-icon');
    if (!drawer || !consoleEl || !icon) return;
    
    const isExpanded = drawer.classList.contains('h-48');
    if (isExpanded) {
        drawer.className = 'fixed bottom-0 left-0 right-0 h-12 bg-[#16191f] border-t border-[#2a2f3a] z-50 flex flex-col font-sans text-xs transition-all duration-300';
        consoleEl.classList.add('hidden');
        icon.className = 'fa-solid fa-chevron-up text-[10px]';
        document.body.style.paddingBottom = '48px';
    } else {
        drawer.className = 'fixed bottom-0 left-0 right-0 h-48 bg-[#16191f] border-t border-[#2a2f3a] z-50 flex flex-col font-sans text-xs transition-all duration-300';
        consoleEl.classList.remove('hidden');
        icon.className = 'fa-solid fa-chevron-down text-[10px]';
        document.body.style.paddingBottom = '192px';
        // Auto scroll console to bottom
        consoleEl.scrollTop = consoleEl.scrollHeight;
    }
};

window.toggleAgentCard = function() {
    const body = document.getElementById('agent-card-body');
    const chevron = document.getElementById('agent-card-chevron');
    if (!body) return;
    const collapsed = body.classList.toggle('hidden');
    chevron.style.transform = collapsed ? 'rotate(180deg)' : 'rotate(0deg)';
};



function startAgentActivityTracker() {
    const pillStatus = document.getElementById('agent-pill-status');
    const pillDot = document.getElementById('agent-pill-dot');
    const logEl = document.getElementById('agent-log');
    const summaryEl = document.getElementById('agent-summary');

    let ws = null;
    function connectWS() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        try {
            const token = localStorage.getItem('token') || '';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/terminal?token=${encodeURIComponent(token)}`);
        } catch (e) {
            console.warn('[AgentDrawer] WebSocket connection failed:', e.message);
            if (logEl) logEl.textContent = 'WebSocket not available. Using polling.';
            return;
        }
        ws.onopen = () => {
            if (logEl) logEl.textContent = 'Agent connected. Streaming telemetry...';
        };
        ws.onmessage = (event) => {
            let msg;
            try {
                msg = JSON.parse(event.data);
            } catch (e) {
                if (logEl) logEl.textContent = event.data;
                return;
            }
            if (msg.type === 'log') {
                const text = msg.message;
                if (logEl) logEl.textContent = text;

                const logContent = document.getElementById('agent-drawer-log-content');
                if (logContent) {
                    const line = document.createElement('div');
                    line.className = 'border-l-2 border-[#2f8fc9]/30 pl-2 py-0.5 hover:bg-white/5 transition-colors';
                    const time = new Date().toLocaleTimeString();
                    const safeText = String(text)
                        .replace(/&/g, '&amp;')
                        .replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;');
                    line.innerHTML = `<span class="text-gray-500 text-[8px] mr-2">[${time}]</span> <span class="text-gray-300">${safeText}</span>`;
                    logContent.appendChild(line);

                    while (logContent.children.length > 100) {
                        logContent.removeChild(logContent.firstChild);
                    }

                    logContent.scrollTop = logContent.scrollHeight;
                }

                if (text.includes('Successfully synchronized') || text.includes('Scan complete') || text.includes('Operation completed') || text.includes('completed') || text.includes('Success')) {
                    if (summaryEl) {
                        summaryEl.textContent = text;
                        summaryEl.classList.remove('text-green-400');
                        void summaryEl.offsetWidth;
                        summaryEl.classList.add('text-green-400');
                    }
                }
            }
        };
        let wsFailed = false;
        ws.onclose = () => {
            if (!wsFailed) {
                wsFailed = true;
                console.warn('[AgentDrawer] WebSocket closed. Will not retry.');
                if (logEl) logEl.textContent = 'Agent connection closed. Telemetry unavailable.';
            }
        };
        ws.onerror = () => {
            wsFailed = true;
            console.warn('[AgentDrawer] WebSocket error. Will not retry.');
            if (logEl) logEl.textContent = 'Agent connection failed. Telemetry unavailable.';
        };
    }

    async function pollStats() {
        try {
            const resp = await fetch('/api/stats');
            if (resp.ok) {
                const data = await resp.json();
                if (pillStatus) {
                    pillStatus.textContent = data.current_task || 'Idle';
                }
                const isRunning = data.running_tasks > 0 && data.current_task;
                if (pillDot) {
                    pillDot.className = isRunning
                        ? 'rounded-full h-2.5 w-2.5 bg-yellow-500'
                        : 'rounded-full h-2.5 w-2.5 bg-green-500';
                }
            }
        } catch (e) {
            console.error('Failed to fetch stats', e);
        }
    }

    connectWS();
        let statsIntervalId = null;
    const STATS_INTERVAL_MS = 30 * 1000; // 30 seconds

    function startStatsPolling() {
        if (statsIntervalId !== null) return;
        statsIntervalId = setInterval(pollStats, STATS_INTERVAL_MS);
    }

    function stopStatsPolling() {
        if (statsIntervalId !== null) {
            clearInterval(statsIntervalId);
            statsIntervalId = null;
        }
    }

    // Initial load
    pollStats();
    startStatsPolling();

    // Also refresh scan details panel on each poll cycle
    if (window.refreshScanDetails) window.refreshScanDetails();

    // Pause polling when page is hidden
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
}

// Cancel current task
window.cancelCurrentTask = async function() {
    const btn = document.getElementById('agent-cancel-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-[8px]"></i> Cancelling...';
    }
    try {
        await fetch('/api/action/cancel', { method: 'POST' });
        toast('Task cancelled', 'warning');
    } catch (e) {
        console.error('Cancel failed:', e);
    }
    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-stop-circle text-[8px]"></i> Cancel';
        btn.classList.add('hidden');
    }
};

// Export and clear log functions
window.exportLogs = function() {
    const logContent = document.getElementById('agent-drawer-log-content');
    if (!logContent) return;
    const lines = [];
    for (let i = 0; i < logContent.children.length; i++) {
        const text = logContent.children[i].textContent || '';
        if (text) lines.push(text.replace(/^\[[\d:]+\]\s*/, '')); // strip timestamp prefix
    }
    if (!lines.length) { toast('No logs to export', 'info'); return; }
    const blob = new Blob([lines.join('\n')], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent-logs-${new Date().toISOString().slice(0,19).replace(/[:]/g,'-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast(`Exported ${lines.length} log lines`, 'success');
};

window.clearLogs = function() {
    const logContent = document.getElementById('agent-drawer-log-content');
    if (!logContent || !logContent.children.length) return;
    logContent.innerHTML = '<div class="text-gray-500">[SYSTEM] Console cleared.</div>';
    toast('Logs cleared', 'info');
};

// ============================================================
// Global Live Console Widget — terminal button + slide-in panel
// ============================================================
(function () {
    'use strict';

    function initLiveConsoleWidget() {
        if (document.getElementById('live-console-panel')) return;

        // ---- Floating terminal button (left of AI Chat button) ----
        let btn = document.getElementById('live-console-btn');
        if (!btn) {
            btn = document.createElement('button');
            btn.id = 'live-console-btn';
            btn.title = 'Live Console';
            btn.setAttribute('aria-label', 'Open Live Console');
            btn.className = [
                'fixed top-[13px] right-[60px] z-[60]',
                'w-10 h-10 rounded-xl',
                'bg-[#1a1d24] hover:bg-[#20242c]',
                'border border-[#2a2f3a] hover:border-[#2f8fc9]/40',
                'text-gray-400 hover:text-[#2f8fc9]',
                'flex items-center justify-center',
                'shadow-lg shadow-black/30',
                'transition-all duration-200 hover:scale-105 active:scale-95',
            ].join(' ');
            btn.innerHTML = '<i class="fa-solid fa-terminal text-sm"></i>';
            document.body.appendChild(btn);
        }

        // ---- Settings gear button (left of Live Console button) ----
        // Kept in the global header (matching the circular >_ and robot buttons)
        // per product decision; the sidebar Settings link is removed on all pages.
        let settingsBtn = document.getElementById('settings-gear-btn');
        if (!settingsBtn) {
            settingsBtn = document.createElement('a');
            settingsBtn.id = 'settings-gear-btn';
            settingsBtn.href = '/settings';
            settingsBtn.title = 'Settings';
            settingsBtn.setAttribute('aria-label', 'Open Settings');
            settingsBtn.className = [
                'fixed top-[13px] right-[112px] z-[60]',
                'w-10 h-10 rounded-xl',
                'bg-[#1a1d24] hover:bg-[#20242c]',
                'border border-[#2a2f3a] hover:border-[#2f8fc9]/40',
                'text-gray-400 hover:text-[#2f8fc9]',
                'flex items-center justify-center',
                'shadow-lg shadow-black/30',
                'transition-all duration-200 hover:scale-105 active:scale-95',
            ].join(' ');
            settingsBtn.innerHTML = '<i class="fa-solid fa-gear text-sm"></i>';
            document.body.appendChild(settingsBtn);
        }

        // ---- Backdrop ----
        const overlay = document.createElement('div');
        overlay.id = 'live-console-overlay';
        overlay.className = 'fixed inset-0 bg-black/40 z-[65] hidden';
        document.body.appendChild(overlay);

        // ---- Slide-in panel ----
        const panel = document.createElement('div');
        panel.id = 'live-console-panel';
        panel.className = [
            'fixed top-0 right-0 h-full w-[520px] max-w-[100vw]',
            'bg-[#1a1d24] border-l border-[#2a2f3a]',
            'z-[70] flex flex-col',
            'transform translate-x-full transition-transform duration-300 ease-in-out',
            'font-sans shadow-2xl shadow-black/60',
        ].join(' ');

        panel.innerHTML = `
            <!-- Header -->
            <div class="px-5 py-3.5 border-b border-[#2a2f3a] flex items-center justify-between shrink-0 bg-[#171920]">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-xl bg-[#2f8fc9]/10 border border-[#2f8fc9]/25 flex items-center justify-center shrink-0">
                        <i class="fa-solid fa-terminal text-[#2f8fc9] text-xs"></i>
                    </div>
                    <div>
                        <div class="text-sm font-semibold text-white leading-tight">Live Console</div>
                        <div class="text-[10px] text-gray-500 mt-0.5">Real-time agent log stream</div>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button id="live-console-dock"
                        class="px-2 py-1 text-[11px] text-gray-400 hover:text-white">Dock</button>
                    <button id="btn-copy-console" title="Copy logs"
                        class="w-8 h-8 rounded-lg bg-[#20242c] border border-[#2a2f3a] text-gray-400 hover:text-white flex items-center justify-center transition-colors text-[11px]">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button id="btn-clear-console" title="Clear console"
                        class="w-8 h-8 rounded-lg bg-[#20242c] border border-[#2a2f3a] text-gray-400 hover:text-red-400 flex items-center justify-center transition-colors text-[11px]">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button id="live-console-close"
                        class="w-8 h-8 rounded-lg bg-[#20242c] border border-[#2a2f3a] text-gray-400 hover:text-white flex items-center justify-center transition-colors">
                        <i class="fa-solid fa-xmark text-xs"></i>
                    </button>
                </div>
            </div>
            <!-- Log output -->
            <div id="console-output" class="flex-1 bg-[#0a0c10] p-4 font-mono text-[11px] text-gray-400 overflow-y-auto space-y-1">
                <div class="console-line info">Console ready.</div>
            </div>
        `;

        document.body.appendChild(panel);

        // ---- Events ----
        btn.addEventListener('click', _openConsole);
        overlay.addEventListener('click', _closeConsole);
        panel.querySelector('#live-console-close').addEventListener('click', _closeConsole);

        // Copy button
        panel.querySelector('#btn-copy-console').addEventListener('click', function () {
            const lines = Array.from(
                document.querySelectorAll('#console-output .console-line, #console-output div')
            ).map(el => el.textContent.trim()).filter(Boolean);
            navigator.clipboard.writeText(lines.join('\n')).then(() => {
                if (typeof toast === 'function') toast('Logs copied', 'success');
            }).catch(() => {});
        });

        // Clear button
        panel.querySelector('#btn-clear-console').addEventListener('click', function () {
            const out = document.getElementById('console-output');
            if (out) out.innerHTML = '<div class="console-line info">[SYSTEM] Console cleared.</div>';
            if (typeof toast === 'function') toast('Console cleared', 'info');
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') _closeConsole();
        });
    }

    function _openConsole() {
        document.getElementById('live-console-panel')?.classList.remove('translate-x-full');
        document.getElementById('live-console-overlay')?.classList.remove('hidden');
    }

    function _closeConsole() {
        if (panel.dataset.docked === '1') return;
        document.getElementById('live-console-panel')?.classList.add('translate-x-full');
        document.getElementById('live-console-overlay')?.classList.add('hidden');
    }

    // ---- Dock helpers ----------------------------------------------------
function dockPanel(opts){
    var _p=document.getElementById(opts.panelId); if(!_p)return;
    var _o=opts.overlayId?document.getElementById(opts.overlayId):null;
    function _apply(dock){
        _p.classList.toggle('docked',dock);
        _p.classList.toggle('translate-x-full',!dock);
        if(_o) _o.classList.toggle('hidden',dock);
        _p.dataset.docked=dock?'1':'0';
        var sum=0;
        ['live-console-panel','ai-chat-panel'].forEach(function(id){
            var el=document.getElementById(id); if(el&&el.classList.contains('docked')) sum+=(id==='live-console-panel'?520:360);
        });
        var row=document.querySelector('main')?.parentElement;
        if(row) row.style.setProperty('padding-right',sum+'px','important');
    }
    document.getElementById(opts.panelId+'-dock')?.addEventListener('click',function(){
        var dock=document.getElementById(opts.panelId).classList.contains('docked')?false:true;
        _apply(dock);
        this.textContent=dock?'Undock':'Dock';
    });
    document.querySelector('#'+opts.closeId)?.addEventListener('click',function(){
        if(_p.classList.contains('docked')){ _apply(false); return; }
        _p.classList.add('translate-x-full'); if(_o) _o.classList.add('hidden');
    });
}

    document.addEventListener('DOMContentLoaded', initLiveConsoleWidget);
})();



// NOTE: A second SPA router (loadPageContent) previously lived here and
// registered its own click + popstate handlers. It conflicted with the
// primary `navigateSPA` router above (double click interception, duplicate
// history.pushState calls, and two popstate listeners causing back/forward
// to fire twice). It has been removed; navigateSPA is now the sole SPA
// router.

// ============================================================
// Global AI Chat Widget — persistent button + slide-in panel
// ============================================================
(function () {
    'use strict';

    let _convId = null;
    let _selectedModel = null; // { provider_id, model_id, label }
    let _providersLoaded = false;

    function _getToken() {
        const m = document.cookie.match(/(?:^|;\s*)token=([^;]+)/);
        if (m) return m[1];
        return localStorage.getItem('token') || null;
    }

    async function _api(path, opts) {
        opts = opts || {};
        const headers = { 'Content-Type': 'application/json' };
        const t = _getToken();
        if (t) headers['Authorization'] = 'Bearer ' + t;
        let resp;
        try {
            resp = await fetch(path, { method: opts.method || 'GET', headers, body: opts.body });
        } catch (e) {
            throw new Error('Network error — is the server up?');
        }
        let data = null;
        try { data = await resp.json(); } catch (_) {}
        if (!resp.ok) {
            const msg = (data && (data.detail || data.error)) || ('HTTP ' + resp.status);
            throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
        }
        return data;
    }

    function _esc(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // ---- Inject DOM ----------------------------------------------------------
    function initAIChatWidget() {
        if (document.getElementById('ai-chat-panel')) return;

        // ---- Floating button (top-right, beside logout) ----
        let btn = document.getElementById('ai-chat-btn');
        if (!btn) {
            btn = document.createElement('button');
            btn.id = 'ai-chat-btn';
            btn.title = 'AI Chat';
            btn.setAttribute('aria-label', 'Open AI Chat');
            btn.className = [
                'fixed top-[13px] right-4 z-[60]',
                'w-10 h-10 rounded-xl',
                'bg-transparent border border-transparent',
                'flex items-center justify-center',
                'shadow-lg shadow-black/40',
                'transition-all duration-200 hover:scale-105 active:scale-95',
            ].join(' ');
            btn.innerHTML = '<img src="/static/images/ai-chat-icon.jpg" alt="AI Chat" class="w-full h-full object-cover rounded-xl">';
            document.body.appendChild(btn);
        }

        // ---- Backdrop ----
        const overlay = document.createElement('div');
        overlay.id = 'ai-chat-overlay';
        overlay.className = 'fixed inset-0 bg-black/50 z-[65] hidden';
        document.body.appendChild(overlay);

        // ---- Slide-in panel ----
        const panel = document.createElement('div');
        panel.id = 'ai-chat-panel';
        panel.className = [
            'fixed top-0 right-0 h-full w-[400px] max-w-[100vw]',
            'bg-[#1a1d24] border-l border-[#2a2f3a]',
            'z-[70] flex flex-col',
            'transform translate-x-full transition-transform duration-300 ease-in-out',
            'font-sans shadow-2xl shadow-black/60',
        ].join(' ');

        panel.innerHTML = `
            <!-- Header -->
            <div class="px-5 py-4 border-b border-[#2a2f3a] flex items-center justify-between shrink-0 bg-[#171920]">
                <div class="flex items-center gap-3">
                    <div class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0">
                        <img src="/static/images/ai-chat-icon.jpg" alt="AI" class="w-full h-full object-cover rounded-xl">
                    </div>
                    <div>
                        <div class="text-sm font-semibold text-white leading-tight">AI Chat</div>
                        <div id="ai-chat-subtitle" class="text-[10px] text-gray-500 mt-0.5">Loading…</div>
                    </div>
                </div>
                <button id="ai-chat-close"
                    class="w-9 h-9 rounded-xl bg-[#20242c] border border-[#2a2f3a] text-gray-400 hover:text-white flex items-center justify-center transition-colors">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>

            <!-- Model selector bar (shown only when models available) -->
            <div id="ai-chat-model-bar" class="hidden px-4 py-2.5 border-b border-[#2a2f3a]/60 bg-[#13161d] flex items-center gap-2.5 shrink-0">
                <i class="fa-solid fa-microchip text-[#2f8fc9] text-[10px] shrink-0"></i>
                <span class="text-[10px] text-gray-500 shrink-0">Model</span>
                <select id="ai-chat-model-select"
                    class="flex-1 bg-[#20242c] border border-[#2a2f3a] hover:border-[#2f8fc9]/50 text-gray-200 text-[11px] rounded-lg px-2.5 py-1.5 outline-none cursor-pointer transition-colors font-mono">
                </select>
                <button id="ai-chat-new-conv" title="New conversation"
                    class="w-7 h-7 rounded-lg bg-[#20242c] border border-[#2a2f3a] text-gray-400 hover:text-[#2f8fc9] flex items-center justify-center transition-colors shrink-0">
                    <i class="fa-solid fa-rotate-right text-[10px]"></i>
                </button>
            </div>

            <!-- No-provider CTA -->
            <div id="ai-chat-no-provider" class="hidden flex-1 flex flex-col items-center justify-center p-8 text-center gap-5">
                <div class="w-20 h-20 rounded-3xl bg-[#2f8fc9]/10 border border-[#2f8fc9]/20 flex items-center justify-center">
                    <i class="fa-solid fa-plug text-[#2f8fc9] text-3xl"></i>
                </div>
                <div class="space-y-1.5">
                    <div class="text-sm font-semibold text-white">No AI Model Configured</div>
                    <div class="text-[12px] text-gray-400 leading-relaxed max-w-[240px]">
                        Connect a provider and activate at least one model before you can chat.
                    </div>
                </div>
                <a href="/ai/providers"
                    class="inline-flex items-center gap-2 bg-[#2f8fc9] hover:bg-[#2a7db8] text-white text-xs font-semibold px-5 py-2.5 rounded-xl transition-all shadow-lg shadow-[#2f8fc9]/20 hover:scale-105">
                    <i class="fa-solid fa-arrow-right-to-bracket text-[10px]"></i>
                    Configure Providers
                </a>
                <div class="text-[10px] text-gray-600">You'll be redirected to AI Hub → Providers</div>
            </div>

            <!-- Chat log -->
            <div id="ai-chat-log" class="hidden flex-1 overflow-y-auto p-4 space-y-3">
                <!-- Welcome bubble injected by JS -->
            </div>

            <!-- Input area -->
            <div id="ai-chat-input-area" class="hidden px-3.5 py-3 border-t border-[#2a2f3a] bg-[#13161d] flex items-end gap-2.5 shrink-0">
                <textarea id="ai-chat-input" rows="1"
                    placeholder="Ask anything…"
                    class="flex-1 bg-[#20242c] border border-[#2a2f3a] focus:border-[#2f8fc9]/50 text-gray-200 text-[12px] rounded-xl px-3.5 py-2.5 outline-none resize-none leading-relaxed transition-colors overflow-hidden"
                    style="height:42px; min-height:42px; max-height:120px;"></textarea>
                <button id="ai-chat-send"
                    class="w-10 h-10 rounded-xl bg-[#2f8fc9] hover:bg-[#2a7db8] text-white flex items-center justify-center shrink-0 transition-all hover:scale-105 active:scale-95 shadow-md shadow-[#2f8fc9]/20 mb-0.5">
                    <i class="fa-solid fa-paper-plane text-[11px]"></i>
                </button>
            </div>
        `;

        document.body.appendChild(panel);

        // ---- Wire events ----
        btn.addEventListener('click', _openPanel);
        overlay.addEventListener('click', _closePanel);
        document.getElementById('ai-chat-close').addEventListener('click', _closePanel);
        document.getElementById('ai-chat-send').addEventListener('click', _send);
        document.getElementById('ai-chat-new-conv').addEventListener('click', _newConversation);
        document.getElementById('ai-chat-model-select').addEventListener('change', function () {
            try {
                _selectedModel = JSON.parse(this.value);
                _convId = null; // reset conversation when model changes
                _updateSubtitle();
            } catch (_) {}
        });

        const ta = document.getElementById('ai-chat-input');
        ta.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _send(); }
        });
        ta.addEventListener('input', function () {
            this.style.height = '42px';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') _closePanel();
        });
    }

    // ---- Panel open / close --------------------------------------------------
    async function _openPanel() {
        document.getElementById('ai-chat-panel').classList.remove('translate-x-full');
        document.getElementById('ai-chat-overlay').classList.remove('hidden');
        document.getElementById('ai-chat-input')?.focus();
        if (!_providersLoaded) await _loadProviders();
    }

    function _closePanel() {
        document.getElementById('ai-chat-panel')?.classList.add('translate-x-full');
        document.getElementById('ai-chat-overlay')?.classList.add('hidden');
    }

    function _newConversation() {
        _convId = null;
        const log = document.getElementById('ai-chat-log');
        if (log) { log.innerHTML = ''; _appendWelcome(); }
    }

    // ---- Load providers + build model dropdown --------------------------------
    async function _loadProviders() {
        _providersLoaded = true;
        const subtitle = document.getElementById('ai-chat-subtitle');
        const modelBar = document.getElementById('ai-chat-model-bar');
        const modelSelect = document.getElementById('ai-chat-model-select');
        const noProvider = document.getElementById('ai-chat-no-provider');
        const chatLog = document.getElementById('ai-chat-log');
        const inputArea = document.getElementById('ai-chat-input-area');

        try {
            const data = await _api('/api/ai/providers');
            const providers = (data.providers || []).filter(
                p => p.status === 'active' || p.status === 'enabled' || p.is_active
            );

            if (!providers.length) {
                _showState('no-provider');
                subtitle.textContent = 'No model configured';
                return;
            }

            // Fetch active models for each provider in parallel
            const modelInfos = await Promise.all(
                providers.map(p =>
                    _api('/api/ai/providers/' + p.id + '/models')
                        .then(d => ({ provider: p, data: d }))
                        .catch(() => ({ provider: p, data: { models: [], active: [] } }))
                )
            );

            // Build <option> list from active models only
            modelSelect.innerHTML = '';
            let totalOptions = 0;
            modelInfos.forEach(({ provider: p, data: d }) => {
                const allModels = d.models || [];
                const activeSet = new Set((d.active && d.active.length) ? d.active : []);
                const defaultId = d.default || null;
                // Use active models; fall back to first model if none are marked active
                const usable = allModels.filter(m => activeSet.has(m.id) || (!activeSet.size && allModels.indexOf(m) === 0));
                usable.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = JSON.stringify({ provider_id: p.id, model_id: m.id });
                    opt.textContent = (p.name || p.type) + ' / ' + (m.name || m.id);
                    if (m.id === defaultId) opt.textContent += ' ★';
                    modelSelect.appendChild(opt);
                    totalOptions++;
                });
                // If no usable models found, add provider-level fallback
                if (!usable.length) {
                    const opt = document.createElement('option');
                    opt.value = JSON.stringify({ provider_id: p.id, model_id: null });
                    opt.textContent = (p.name || p.type) + ' — default model';
                    modelSelect.appendChild(opt);
                    totalOptions++;
                }
            });

            if (!totalOptions) {
                _showState('no-provider');
                subtitle.textContent = 'No active models found';
                return;
            }

            // Set initial selection
            try { _selectedModel = JSON.parse(modelSelect.value); } catch (_) {}
            _updateSubtitle();

            // Show chat UI
            _showState('chat');
            modelBar.classList.toggle('hidden', totalOptions <= 1);
            _appendWelcome();

        } catch (e) {
            subtitle.textContent = 'Error: ' + e.message;
            _showState('no-provider');
        }
    }

    function _showState(state) {
        const noProvider = document.getElementById('ai-chat-no-provider');
        const chatLog = document.getElementById('ai-chat-log');
        const inputArea = document.getElementById('ai-chat-input-area');

        if (state === 'no-provider') {
            noProvider.classList.remove('hidden'); noProvider.classList.add('flex');
            chatLog.classList.add('hidden');
            inputArea.classList.add('hidden');
        } else {
            noProvider.classList.add('hidden'); noProvider.classList.remove('flex');
            chatLog.classList.remove('hidden');
            inputArea.classList.remove('hidden');
        }
    }

    function _updateSubtitle() {
        const select = document.getElementById('ai-chat-model-select');
        const subtitle = document.getElementById('ai-chat-subtitle');
        if (select && select.selectedIndex >= 0) {
            subtitle.textContent = select.options[select.selectedIndex].textContent.replace(' ★', '');
        }
    }

    function _appendWelcome() {
        _appendBubble('ai',
            'Hello! I can help you manage playlists, create rules, or answer questions about your library. What would you like to do?',
            false
        );
    }

    // ---- Chat bubbles --------------------------------------------------------
    function _appendBubble(role, content, isHtml) {
        const log = document.getElementById('ai-chat-log');
        if (!log) return null;
        const wrap = document.createElement('div');

        if (role === 'user') {
            wrap.className = 'flex justify-end';
            wrap.innerHTML = `<div class="bg-[#2f8fc9]/20 border border-[#2f8fc9]/30 rounded-2xl rounded-tr-sm px-4 py-2.5 text-[12px] text-gray-100 max-w-[85%] leading-relaxed whitespace-pre-wrap">${isHtml ? content : _esc(content)}</div>`;
        } else {
            wrap.className = 'flex items-start gap-2.5';
            wrap.innerHTML = `
                <div class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5">
                    <img src="/static/images/ai-chat-icon.jpg" alt="AI" class="w-full h-full object-cover rounded-full">
                </div>
                <div class="bg-[#20242c] border border-[#2a2f3a] rounded-2xl rounded-tl-sm px-4 py-2.5 text-[12px] text-gray-200 max-w-[85%] leading-relaxed whitespace-pre-wrap">${isHtml ? content : _esc(content)}</div>
            `;
        }

        log.appendChild(wrap);
        log.scrollTop = log.scrollHeight;
        return wrap;
    }

    // ---- Send ----------------------------------------------------------------
    async function _send() {
        const input = document.getElementById('ai-chat-input');
        const sendBtn = document.getElementById('ai-chat-send');
        const text = (input?.value || '').trim();
        if (!text) return;

        input.value = '';
        input.style.height = '42px';
        _appendBubble('user', text);

        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-[11px]"></i>';

        const typing = _appendBubble('ai',
            '<i class="fa-solid fa-ellipsis fa-fade text-gray-500 text-sm"></i>',
            true
        );

        try {
            const body = { message: text };
            if (_convId) body.conversation_id = _convId;
            if (_selectedModel) {
                if (_selectedModel.provider_id) body.provider_id = _selectedModel.provider_id;
                if (_selectedModel.model_id) body.model = _selectedModel.model_id;
            }

            const res = await _api('/api/ai/chat', { method: 'POST', body: JSON.stringify(body) });
            typing.remove();

            if (res.error) {
                _appendBubble('ai',
                    `<span class="text-red-400"><i class="fa-solid fa-triangle-exclamation mr-1.5"></i>${_esc(res.error)}</span>`,
                    true
                );
            } else {
                if (res.conversation_id) _convId = res.conversation_id;
                _appendBubble('ai', res.reply || '(no response)');
            }
        } catch (e) {
            typing.remove();
            _appendBubble('ai',
                `<span class="text-red-400"><i class="fa-solid fa-triangle-exclamation mr-1.5"></i>${_esc(e.message)}</span>`,
                true
            );
        } finally {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fa-solid fa-paper-plane text-[11px]"></i>';
            input?.focus();
        }
    }

    document.addEventListener('DOMContentLoaded', initAIChatWidget);
})();

