const API_BASE = '/api/auth';

// Handle token from URL fragment (after OAuth redirect) FIRST
(function() {
    const hash = window.location.hash;
    if (hash && hash.includes('token=')) {
        const token = hash.split('token=')[1].split('&')[0];
        if (token) {
            localStorage.setItem('token', token);
            document.cookie = `token=${token}; path=/; max-age=604800; SameSite=Lax`;
            window.location.hash = '';
            window.location.replace('/dashboard');
            return; // Exit after successful token processing
        }
    }
})();

function showForm(form) {
    if (form === 'login') {
        document.getElementById('login-form').classList.remove('hidden');
        document.getElementById('register-form').classList.add('hidden');
        document.getElementById('login-tab').classList.add('bg-blue-600', 'text-white');
        document.getElementById('login-tab').classList.remove('bg-[#2a2f3a]', 'text-gray-400');
        document.getElementById('register-tab').classList.remove('bg-blue-600', 'text-white');
        document.getElementById('register-tab').classList.add('bg-[#2a2f3a]', 'text-gray-400');
    } else {
        document.getElementById('register-form').classList.remove('hidden');
        document.getElementById('login-form').classList.add('hidden');
        document.getElementById('register-tab').classList.add('bg-blue-600', 'text-white');
        document.getElementById('register-tab').classList.remove('bg-[#2a2f3a]', 'text-gray-400');
        document.getElementById('login-tab').classList.remove('bg-blue-600', 'text-white');
        document.getElementById('login-tab').classList.add('bg-[#2a2f3a]', 'text-gray-400');
    }
}

async function handleLogin() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');

    if (!email || !password) {
        errorEl.textContent = 'Please fill in all fields';
        errorEl.classList.remove('hidden');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: email, password })
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('user', JSON.stringify(data.user));
            localStorage.setItem('token', data.access_token);
            // Set cookie for server-side auth
            document.cookie = `token=${data.access_token}; path=/; max-age=604800; SameSite=Lax`;
            window.location.href = '/dashboard';
        } else {
            errorEl.textContent = DOMPurify.sanitize(data.detail || 'Login failed');
            errorEl.classList.remove('hidden');
        }
    } catch (error) {
        errorEl.textContent = 'Network error. Please try again.';
        errorEl.classList.remove('hidden');
    }
}

async function handleRegister() {
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const errorEl = document.getElementById('register-error');

    if (!username || !email || !password) {
        errorEl.textContent = 'Please fill in all fields';
        errorEl.classList.remove('hidden');
        return;
    }

    if (password.length < 8) {
        errorEl.textContent = 'Password must be at least 8 characters';
        errorEl.classList.remove('hidden');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('user', JSON.stringify(data.user));
            localStorage.setItem('token', data.access_token);
            document.cookie = `token=${data.access_token}; path=/; max-age=604800; SameSite=Lax`;
            window.location.href = '/dashboard';
        } else {
            errorEl.textContent = DOMPurify.sanitize(data.detail || 'Registration failed');
            errorEl.classList.remove('hidden');
        }
    } catch (error) {
        errorEl.textContent = 'Network error. Please try again.';
        errorEl.classList.remove('hidden');
    }
}

// Check if already logged in
(async function checkSession() {
    try {
        const token = localStorage.getItem('token');
        const resp = await fetch(`${API_BASE}/me`, {
            headers: {
                'Accept': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
        });
        if (resp.ok) {
            window.location.href = '/dashboard';
        } else {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            // Stay on /auth for fresh login, but clear any 'reason' param if it exists
            const url = new URL(window.location.href);
            if (url.searchParams.has('reason')) {
                url.searchParams.delete('reason');
                window.history.replaceState({}, document.title, url.toString());
            }
        }
    } catch (e) {
        console.error("Session check failed:", e);
        // Stay on /auth
    }
})();

function handleGoogleLogin() {
    // Pass the current URL as redirect_uri to the backend
    const redirectUri = window.location.origin + window.location.pathname;
    fetch(`/api/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`)
        .then(response => response.json())
        .then(data => {
            if (data.auth_url) {
                window.location.href = data.auth_url;
            } else {
                alert(DOMPurify.sanitize(data.error || 'Google OAuth not configured'));
            }
        })
        .catch(error => {
            console.error('Google login error:', error);
            alert('Failed to initiate Google login');
        });
}

// Logout function
function logout() {
    localStorage.removeItem('user');
    localStorage.removeItem('token');
    document.cookie = 'token=; path=/; max-age=0';
    window.location.href = '/auth';
}

// Event listeners for tabs
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('login-tab')?.addEventListener('click', () => showForm('login'));
    document.getElementById('register-tab')?.addEventListener('click', () => showForm('register'));
    document.getElementById('google-login-btn')?.addEventListener('click', handleGoogleLogin);
    document.getElementById('login-btn')?.addEventListener('click', handleLogin);
    document.getElementById('register-account-btn')?.addEventListener('click', handleRegister);

    // Check for reason in URL and display if present
    const urlParams = new URLSearchParams(window.location.search);
    const reason = urlParams.get('reason');
    if (reason) {
        const errorEl = document.getElementById('login-error');
        if (errorEl) {
            let message = 'Authentication required.';
            if (reason === 'expired') {
                message = 'Your session has expired. Please log in again.';
            } else if (reason === 'unauthenticated') {
                message = 'You are not authenticated. Please log in.';
            } else if (reason === 'disabled') {
                message = 'Your account is disabled. Please contact support.';
            } else if (reason === 'error') {
                message = 'An unexpected authentication error occurred. Please try again.';
            }
            errorEl.textContent = DOMPurify.sanitize(message);
            errorEl.classList.remove('hidden');
        }
    }
});
