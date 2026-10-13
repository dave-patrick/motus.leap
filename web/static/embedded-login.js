(function () {
  if (window.self === window.top) return;
  const link = document.getElementById('back-link');
  if (!link || link.getAttribute('href') !== '/api/auth/google') return;
  const message = document.getElementById('status-message');
  let popup = null;
  let completing = false;
  link.target = '_blank';
  link.addEventListener('click', function (event) {
    event.preventDefault();
    popup = window.open('/api/auth/google', 'motus-embedded-sign-in', 'popup,width=520,height=720');
    message.textContent = popup
      ? 'Finish signing in in the Google window. This view will update automatically.'
      : 'Allow pop-ups for motus.leap, then click Sign in with Google again.';
  });
  window.addEventListener('message', async function (event) {
    if (event.origin !== window.location.origin || !popup || event.source !== popup || completing) return;
    if (event.data?.type !== 'motus-embedded-login' || typeof event.data.token !== 'string') return;
    completing = true;
    try {
      const response = await fetch('/api/auth/me', {headers: {Authorization: 'Bearer ' + event.data.token}});
      if (!response.ok) throw new Error('Sign-in could not be verified. Please try again.');
      localStorage.setItem('token', event.data.token);
      localStorage.setItem('user', JSON.stringify(await response.json()));
      popup.close();
      window.location.replace('/dashboard');
    } catch (error) {
      completing = false;
      message.textContent = error.message;
    }
  });
})();
