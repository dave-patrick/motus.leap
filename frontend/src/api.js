/**
 * API client helper with auth credentials & CSRF headers.
 */
export async function apiFetch(endpoint, options = {}) {
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'X-CSRF-Token': getCsrfToken(),
  };

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
  };

  const response = await fetch(endpoint, config);
  
  if (response.status === 401) {
    // Auth error — redirect if needed
    window.location.href = '/auth';
    throw new Error('Authentication required');
  }

  return response;
}

function getCsrfToken() {
  const name = 'csrf_access_token=';
  const decodedCookies = decodeURIComponent(document.cookie);
  const ca = decodedCookies.split(';');
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i].trim();
    if (c.indexOf(name) === 0) {
      return c.substring(name.length, c.length);
    }
  }
  return '';
}
