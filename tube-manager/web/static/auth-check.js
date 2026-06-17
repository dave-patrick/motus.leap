/**
 * Auth check for Tube Manager pages.
 * - Extracts token from URL fragment (OAuth redirect).
 * - Verifies the token with /api/auth/me.
 * - Redirects to /auth only when the token is confirmed invalid.
 * - Retries once on transient network errors (e.g., Render waking from cold start)
 *   to avoid kicking users out when the tab regains focus.
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
    // Continue below to validate the token
  }

  // 2. Verify stored token
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = '/auth';
    return;
  }

  function clearAuthAndRedirect() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    document.cookie = 'token=; path=/; max-age=0';
    window.location.href = '/auth';
  }

  function validateToken(attempt) {
    fetch('/api/auth/me', {
      headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' }
    })
    .then(resp => {
      if (resp.status === 401) {
        // Confirmed invalid/expired token
        clearAuthAndRedirect();
      }
      // For 2xx: authenticated, stay on page.
      // For 5xx: server error (possibly waking up); do not redirect.
    })
    .catch(() => {
      // Network error — may be transient during Render cold start or tab refocus.
      if (attempt < 1) {
        setTimeout(() => validateToken(attempt + 1), 1500);
      }
      // If retry also fails, leave user on page; dashboard renewSession will retry.
    });
  }

  validateToken(0);
})();
