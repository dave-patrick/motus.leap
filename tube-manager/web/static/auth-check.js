(function() {
  // 1. Handle token from URL fragment (OAuth callback redirects here)
  const hash = window.location.hash;
  if (hash && hash.includes('token=')) {
    const token = hash.split('token=')[1].split('&')[0];
    document.cookie = `token=${token}; path=/; max-age=604800; SameSite=Lax`;
    window.location.hash = '';
    // Continue below to validate the token
  }

  // 2. Verify token from cookie
  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
  }
  
  const token = getCookie('token');
  if (!token) {
    window.location.href = '/auth';
    return;
  }

  function clearAuthAndRedirect() {
    localStorage.removeItem('user');
    document.cookie = 'token=; path=/; max-age=0';
    window.location.href = '/auth';
  }

  function validateToken(attempt) {
    fetch('/api/auth/me', {
      headers: { 'Accept': 'application/json' }
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