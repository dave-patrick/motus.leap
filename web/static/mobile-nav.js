(function () {
  window.toggleAiGroup = function (group) {
    const items = document.querySelector('.ai-group-items[data-group="' + group + '"]');
    const toggle = document.querySelector('.ai-group-toggle[data-group="' + group + '"]');
    if (!items) return;
    const collapsed = items.classList.toggle('hidden');
    if (toggle) toggle.setAttribute('aria-expanded', String(!collapsed));
    const chevron = toggle?.querySelector('.ai-group-chevron');
    chevron?.classList.toggle('fa-chevron-down', !collapsed);
    chevron?.classList.toggle('fa-chevron-right', collapsed);
  };
  function initMobileNav() {
    const sidebar = document.getElementById('mobile-sidebar');
    const overlay = document.getElementById('mobile-overlay');
    const toggle = document.getElementById('sidebar-toggle');
    if (!sidebar || !overlay || !toggle || toggle.dataset.navWired) return;
    toggle.dataset.navWired = '1';
    toggle.setAttribute('aria-controls', 'mobile-sidebar');
    toggle.setAttribute('aria-expanded', 'false');
    let opened = false;
    let previousFocus;
    let previousOverflow = '';
    function sync() {
      sidebar.inert = window.innerWidth < 768 && !opened;
    }
    function openSidebar() {
      if (opened) return closeSidebar();
      opened = true;
      previousFocus = document.activeElement;
      previousOverflow = document.body.style.overflow;
      sidebar.classList.remove('-translate-x-full');
      overlay.classList.remove('hidden');
      toggle.setAttribute('aria-expanded', 'true');
      document.body.style.overflow = 'hidden';
      sync();
      sidebar.querySelector('a, button')?.focus();
    }
    function closeSidebar() {
      sidebar.classList.add('-translate-x-full');
      overlay.classList.add('hidden');
      toggle.setAttribute('aria-expanded', 'false');
      if (opened) {
        document.body.style.overflow = previousOverflow;
        previousFocus?.focus();
      }
      opened = false;
      sync();
    }
    window.openMobileSidebar = openSidebar;
    window.closeMobileSidebar = closeSidebar;
    toggle.addEventListener('click', openSidebar);
    overlay.addEventListener('click', closeSidebar);
    document.addEventListener('keydown', event => {
      if (!opened) return;
      if (event.key === 'Escape') { closeSidebar(); return; }
      if (event.key !== 'Tab') return;
      const links = [...sidebar.querySelectorAll('a, button, [tabindex="0"]')]
        .filter(el => el.getClientRects().length && !el.disabled);
      if (!links.length) return;
      if (event.shiftKey && document.activeElement === links[0]) {
        event.preventDefault(); links[links.length - 1].focus();
      } else if (!event.shiftKey && document.activeElement === links[links.length - 1]) {
        event.preventDefault(); links[0].focus();
      }
    });
    sidebar.addEventListener('click', event => {
      if (window.innerWidth < 768 && event.target.closest('a')) closeSidebar();
    });
    window.addEventListener('resize', () => {
      if (window.innerWidth >= 768 && opened) closeSidebar();
      sync();
    });
    sync();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileNav, {once: true});
  } else initMobileNav();
})();
