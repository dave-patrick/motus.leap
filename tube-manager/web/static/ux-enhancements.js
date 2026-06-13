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
                            <span>Full Cluster Scan</span>
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