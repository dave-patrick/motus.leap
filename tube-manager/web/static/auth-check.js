/**
 * Auth check for Tube Manager pages.
 * Redirects to /auth if token is missing or invalid.
 * Include on every page that requires authentication.
 */
(function() {
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = '/auth';
    return;
  }
  // Verify token is still valid by calling /api/auth/me
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
      // Network error — stay on page
    });
})();
