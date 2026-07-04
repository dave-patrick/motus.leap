// Global scripts for motus.leap
function toast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container') || createToastContainer();
    const el = document.createElement('div');
    const icons = { success: 'fa-check-circle', error: 'fa-times-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
    const colors = { success: 'bg-green-600', error: 'bg-red-600', warning: 'bg-yellow-600', info: 'bg-[#2f8fc9]' };
    el.className = 'flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-white text-xs font-medium animate-slide-in ' + (colors[type] || colors.info);
    el.innerHTML = '<i class="fa-solid ' + (icons[type] || icons.info) + '"></i><span>' + DOMPurify.sanitize(message, {USE_PROFILES: {html: true}}) + '</span>';
    container.appendChild(el);
    setTimeout(() => { el.classList.add('animate-slide-out'); setTimeout(() => el.remove(), 300); }, duration);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2 w-80';
    document.body.appendChild(container);
    return container;
}

function logoutUser() {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    document.cookie = 'token=; path=/; max-age=0; SameSite=Lax';
    document.cookie = 'token=; path=/; max-age=0; SameSite=Strict';
    document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
    window.location.href = '/auth';
}

function getCookie(name) {
    const value = '; ' + document.cookie;
    const parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

function getAuthToken() {
    return getCookie('token') || localStorage.getItem('token');
}

async function authFetch(url, options = {}) {
    const token = getAuthToken();
    const headers = {};
    if (token) {
        headers['Authorization'] = 'Bearer ' + token;
    }

    // Merge options.headers while preserving existing headers (e.g., Content-Type)
    const mergedHeaders = {
        ...headers,
        ...(options.headers || {})
    };

    const fetchOptions = {
        ...options,
        headers: mergedHeaders
    };

    const response = await fetch(url, fetchOptions);

    if (response.status === 401) {
        // Clear authentication
        localStorage.removeItem('user');
        localStorage.removeItem('token');
        document.cookie = 'token=; path=/; max-age=0';
        document.cookie = 'token=; path=/; max-age=0; SameSite=Lax';
        document.cookie = 'token=; path=/; max-age=0; SameSite=Strict';
        document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;';
        
        // Redirect to '/auth'
        window.location.href = '/auth';
        throw new Error('Unauthorized');
    }

    return response;
}

// Ensure global accessibility in all contexts
window.getCookie = getCookie;
window.getAuthToken = getAuthToken;
window.authFetch = authFetch;
