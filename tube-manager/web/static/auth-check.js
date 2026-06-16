/**
 * Auth check for Tube Manager pages.
 * - Extracts token from URL fragment first (OAuth redirect).
 * - Then verifies the token with /api/auth/me.
 * - Redirects to /auth if not authenticated.
 * Include on every page that requires authentication.
 */
(function() {
  // 1. Handle token from URL fragment (OAuth callback redirects here)
  const hash = window.location.hash;
  if (hash && hash.includes('token=')) {
    const token = hash.split('token=')[1].split('&')[0];
    localStorage.setItem('token', token);
    document.cookie = `token=${token}; path=/; max-age=604800; SameSite=Lax`;
    window.location.hash = '';
    // Continue below to validate the token and redirect if invalid
  }

  // 2. Verify stored token
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = '/auth';
    return;
  }

  fetch('/api/auth/me', {
    headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' }
  })
  .then(resp => {
    if (!resp.ok) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      document.cookie = 'token=; path=/; max-age=0';
      window.location.href = '/auth';
    }
  })
  .catch(() => {
    window.location.href = '/auth';
  });
})();