// ============================================
// ENHANCED UX: Loading States, Error Handling, Keyboard Shortcuts
// ============================================

// Global state for loading states
const loadingStates = new Map();
const errorQueue = [];

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
            <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
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
    toast.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-4 rounded-lg shadow-2xl z-50 animate-slide-in-right flex flex-col gap-2 max-w-md';
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
    toast.className = 'fixed top-4 right-4 bg-green-500 text-white px-6 py-4 rounded-lg shadow-2xl z-50 animate-slide-in-right flex items-center gap-3 max-w-md';
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
    toast.className = 'fixed top-4 right-4 bg-blue-500 text-white px-6 py-4 rounded-lg shadow-2xl z-50 animate-slide-in-right flex items-center gap-3 max-w-md';
    toast.innerHTML = `
        <i class="fa-solid fa-circle-info text-xl"></i>
        <p class="font-medium">${escapeHtml(message)}</p>
        <button onclick="this.parentElement.remove()" class="flex-shrink-0 text-blue-200 hover:text-white">
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
        } else if (taskName.includes('Watch Later')) {
            estSeconds = 15;
            ratePerSec = 6.6;
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

    pollStats();
    setInterval(pollStats, 5000);
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
        const newAside = doc.querySelector('aside');

        // Update body class if different
        document.body.className = doc.body.className;

        // 1. Keep current aside and global agent drawer, remove all other body children
        const globalDrawer = document.getElementById('global-agent-drawer');
        Array.from(document.body.children).forEach(child => {
            if (child !== currentAside && child !== globalDrawer && child.tagName !== 'SCRIPT') {
                document.body.removeChild(child);
            }
        });

        // 2. Add all new body children except its ASIDE and global drawer
        const scriptsToRun = [];
        Array.from(doc.body.children).forEach(child => {
            if (child.tagName !== 'ASIDE' && child.id !== 'global-agent-drawer') {
                // Find scripts inside the child
                child.querySelectorAll('script').forEach(s => {
                    scriptsToRun.push(s);
                    s.remove(); // Remove from markup so we don't double append
                });
                document.body.appendChild(child);
            }
        });

        // 3. Update the active sidebar link highlighting
        if (currentAside) {
            currentAside.querySelectorAll('nav a').forEach(a => {
                const path = a.getAttribute('href');
                if (path === url || (path === '/' && url === '/dashboard') || (url.startsWith('/playlist') && path === '/playlists')) {
                    a.className = "flex items-center gap-3 px-3 py-2.5 rounded-lg bg-blue-600/20 text-blue-400 text-xs font-semibold border border-blue-500/30";
                } else {
                    a.className = "flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-[#2a2f3a] text-xs font-medium transition-colors";
                }
            });
        }

        // 4. Run scripts in order
        scriptsToRun.forEach(oldScript => {
            const newScript = document.createElement('script');
            Array.from(oldScript.attributes).forEach(attr => newScript.setAttribute(attr.name, attr.value));
            if (oldScript.innerHTML) {
                newScript.appendChild(document.createTextNode(oldScript.innerHTML));
            }
            document.body.appendChild(newScript);
        });

        // 5. Fire DOMContentLoaded to trigger page initializations
        setTimeout(() => {
            document.dispatchEvent(new Event('DOMContentLoaded'));
        }, 50);

    } catch (e) {
        console.error('SPA Navigation error:', e);
        window.location.href = url; // Fallback
    }
}

// Intercept clicks on links or button navigation
document.addEventListener('click', (e) => {
    // 1. Anchor tag clicks
    let link = e.target.closest('a');
    if (link && link.getAttribute('href')) {
        const href = link.getAttribute('href');
        if (href.startsWith('/') && !href.startsWith('/auth') && !href.startsWith('/oauth') && !href.startsWith('/api')) {
            e.preventDefault();
            window.history.pushState(null, '', href);
            navigateSPA(href);
            return;
        }
    }

    // 2. Elements with inline onclick="window.location.href='...'"
    let onclickEl = e.target.closest('[onclick]');
    if (onclickEl) {
        const onclickAttr = onclickEl.getAttribute('onclick');
        const match = onclickAttr.match(/window\.location\.href\s*=\s*['"]([^'"]+)['"]/);
        if (match) {
            const href = match[1];
            if (href.startsWith('/') && !href.startsWith('/auth') && !href.startsWith('/oauth') && !href.startsWith('/api')) {
                e.preventDefault();
                e.stopPropagation();
                window.history.pushState(null, '', href);
                navigateSPA(href);
            }
        }
    }
}, true); // Capture phase to run before inline handlers

// Handle browser back/forward buttons
window.addEventListener('popstate', () => {
    navigateSPA(window.location.pathname);
});


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

function initGlobalAgentDrawer() {
    let drawer = document.getElementById('global-agent-drawer');
    if (!drawer) {
        drawer = document.createElement('div');
        drawer.id = 'global-agent-drawer';
        drawer.className = 'fixed bottom-0 left-0 right-0 h-12 bg-[#16191f] border-t border-[#2a2f3a] z-50 flex flex-col font-sans text-xs transition-all duration-300';
        drawer.innerHTML = `
            <div class="flex items-center justify-between w-full h-12 px-6">
                <!-- Left: Status & Current Task -->
                <div class="flex items-center gap-2.5 min-w-0">
                    <div class="flex items-center gap-1.5 shrink-0">
                        <span class="relative flex h-2 w-2">
                            <span id="agent-ping-animate" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                            <span id="agent-ping-color" class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                        </span>
                        <span class="font-bold text-blue-400 uppercase tracking-wider text-[9px]">Agent Status:</span>
                    </div>
                    <span id="agent-task" class="text-white font-semibold truncate max-w-xs font-mono bg-[#20242c] border border-[#2a2f3a] px-2 py-0.5 rounded text-[10px]">Idle</span>
                </div>
                
                <!-- Center: Live Logs Stream -->
                <div class="flex-1 min-w-0 mx-6 flex items-center gap-2 border-l border-r border-[#2a2f3a]/60 px-4 font-mono text-[9px] text-gray-400 h-full">
                    <i class="fa-solid fa-terminal text-blue-500 shrink-0"></i>
                    <span id="agent-log" class="truncate">Listening to live log stream...</span>
                </div>
                
                <!-- Right: Latest Completed Task Summary & Chevron Toggle -->
                <div class="shrink-0 flex items-center gap-2 text-gray-400 max-w-xs truncate">
                    <span class="text-[9px] uppercase tracking-wider font-bold text-gray-500 shrink-0">Last Task:</span>
                    <span id="agent-summary" class="text-[10px] font-medium text-green-400 truncate">None</span>
                    <button onclick="event.stopPropagation(); toggleAgentDrawer()" id="agent-drawer-toggle" class="text-gray-400 hover:text-white p-1 rounded hover:bg-[#20242c] border border-transparent hover:border-[#2a2f3a] transition-all ml-2" title="Toggle Console">
                        <i id="agent-drawer-toggle-icon" class="fa-solid fa-chevron-up text-[10px]"></i>
                    </button>
                </div>
            </div>
            
            <!-- Hidden full-size scrollable console -->
            <div id="agent-drawer-console" class="hidden w-full h-36 bg-[#0e1014] border-t border-[#2a2f3a] p-3 overflow-y-auto font-mono text-[10px] text-gray-400 space-y-1">
                <div class="text-blue-400/80">[SYSTEM] Live agent console initialized. Logs will stream below...</div>
            </div>
        `;
        document.body.appendChild(drawer);
        
        // Compensate for sticky drawer height
        document.body.style.paddingBottom = '48px';
    }
    
    startAgentActivityTracker();
}

function startAgentActivityTracker() {
    const taskEl = document.getElementById('agent-task');
    const logEl = document.getElementById('agent-log');
    const summaryEl = document.getElementById('agent-summary');
    const pingColor = document.getElementById('agent-ping-color');
    const pingAnimate = document.getElementById('agent-ping-animate');

    let ws = null;
    function connectWS() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/terminal`);
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
                
                // Append log line to expanded console
                const consoleEl = document.getElementById('agent-drawer-console');
                if (consoleEl) {
                    const line = document.createElement('div');
                    line.className = 'border-l-2 border-blue-500/30 pl-2 py-0.5 hover:bg-white/5 transition-colors';
                    const time = new Date().toLocaleTimeString();
                    line.innerHTML = `<span class="text-gray-500 text-[8px] mr-2">[${time}]</span> <span class="text-gray-300">${text}</span>`;
                    consoleEl.appendChild(line);
                    
                    // Limit total logs in console to 100
                    while (consoleEl.children.length > 100) {
                        consoleEl.removeChild(consoleEl.firstChild);
                    }
                    
                    // Auto scroll to bottom
                    consoleEl.scrollTop = consoleEl.scrollHeight;
                }
                
                // Extract task completion status
                if (text.includes('Successfully synchronized') || text.includes('Scan complete') || text.includes('Operation completed') || text.includes('completed') || text.includes('Success')) {
                    if (summaryEl) {
                        summaryEl.textContent = text;
                        summaryEl.classList.remove('text-green-400');
                        void summaryEl.offsetWidth; // Trigger reflow to restart transition
                        summaryEl.classList.add('text-green-400');
                    }
                }
            }
        };
        ws.onclose = () => {
            setTimeout(connectWS, 5000);
        };
        ws.onerror = () => {};
    }

    async function pollStats() {
        try {
            const resp = await fetch('/api/stats');
            if (resp.ok) {
                const data = await resp.json();
                if (taskEl) {
                    taskEl.textContent = data.current_task || 'Idle';
                }
                const isRunning = data.running_tasks > 0 && data.current_task;
                if (pingColor && pingAnimate) {
                    if (isRunning) {
                        pingColor.className = "relative inline-flex rounded-full h-2 w-2 bg-yellow-500";
                        pingAnimate.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-yellow-400 opacity-75";
                    } else {
                        pingColor.className = "relative inline-flex rounded-full h-2 w-2 bg-green-500";
                        pingAnimate.className = "animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75";
                    }
                }
            }
        } catch (e) {
            console.error('Failed to fetch stats', e);
        }
    }

    connectWS();
    pollStats();
    setInterval(pollStats, 5000);
}

document.addEventListener('DOMContentLoaded', initGlobalAgentDrawer);


// ============================================
// SINGLE PAGE APPLICATION (SPA) ROUTER
// ============================================

async function loadPageContent(url) {
    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            window.location.href = url; // Fallback to normal load
            return;
        }
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        
        // 1. Update document title
        document.title = doc.title || 'motus.leap';
        
        // 2. Update main section
        const newMain = doc.querySelector('main');
        const currentMain = document.querySelector('main');
        if (newMain && currentMain) {
            currentMain.innerHTML = newMain.innerHTML;
        }
        
        // 3. Highlight the active link in sidebar
        document.querySelectorAll('aside a').forEach(a => {
            const href = a.getAttribute('href');
            if (href === url || (url === '/' && href === '/') || (url.startsWith('/playlist') && href === '/playlists')) {
                a.className = "flex items-center gap-3 px-3 py-2.5 rounded-lg bg-blue-600/20 text-blue-400 text-xs font-semibold border border-blue-500/30";
            } else {
                a.className = "flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-[#2a2f3a] text-xs font-medium transition-colors";
            }
        });
        
        // 4. Load and execute page-specific scripts
        const docScripts = doc.querySelectorAll('script');
        docScripts.forEach(oldScript => {
            const src = oldScript.getAttribute('src');
            if (src && (
                src.includes('tailwindcss') || 
                src.includes('font-awesome') || 
                src.includes('dompurify') || 
                src.includes('auth-check') || 
                src.includes('ux-enhancements')
            )) {
                return;
            }
            const newScript = document.createElement('script');
            if (src) {
                newScript.src = src;
            } else {
                newScript.textContent = oldScript.textContent;
            }
            document.body.appendChild(newScript);
        });
        
        // 5. Re-run initGlobalAgentDrawer so WebSocket and Stats poll are wired to the new elements
        if (typeof initGlobalAgentDrawer === 'function') {
            initGlobalAgentDrawer();
        }
        
    } catch (e) {
        console.error('SPA Navigation error:', e);
        window.location.href = url; // Fallback
    }
}

// Intercept clicks on local links
document.addEventListener('click', (e) => {
    const link = e.target.closest('a');
    if (!link) return;
    
    const href = link.getAttribute('href');
    if (!href || href.startsWith('http') || href.startsWith('//') || link.getAttribute('target') === '_blank') return;
    if (href.startsWith('javascript:')) return;
    
    // Skip external OAuth/callback/disconnect routes
    if (href.includes('/auth/google') || href.includes('/auth/youtube') || href.includes('/api/youtube/disconnect')) return;
    
    e.preventDefault();
    loadPageContent(href);
    window.history.pushState(null, '', href);
});

// Handle browser Back/Forward buttons
window.addEventListener('popstate', () => {
    loadPageContent(window.location.pathname);
});