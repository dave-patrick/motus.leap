(function () {
  // Collapsible AI Hub sub-nav group (shared across all SPA pages)
  window.toggleAiGroup = function (group) {
    const items = document.querySelector('.ai-group-items[data-group="' + group + '"]');
    const chevron = document.querySelector('.ai-group-toggle[data-group="' + group + '"] .ai-group-chevron');
    if (!items) return;
    const collapsed = items.classList.toggle('hidden');
    if (chevron) {
      chevron.classList.toggle('fa-chevron-down', !collapsed);
      chevron.classList.toggle('fa-chevron-right', collapsed);
    }
  };

  function initMobileNav() {
    const sidebar = document.getElementById('mobile-sidebar');
    const overlay = document.getElementById('mobile-overlay');
    const toggle = document.getElementById('sidebar-toggle');

    if (!sidebar || !overlay || !toggle) return;

    function openSidebar() {
      sidebar.classList.remove('-translate-x-full');
      overlay.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
      sidebar.classList.add('-translate-x-full');
      overlay.classList.add('hidden');
      document.body.style.overflow = '';
    }

    // Expose to inline onclick handlers in HTML
    window.openMobileSidebar = openSidebar;
    window.closeMobileSidebar = closeSidebar;

    // Use a fresh listener to avoid duplicates
    const newToggle = toggle.cloneNode(true);
    toggle.parentNode.replaceChild(newToggle, toggle);
    newToggle.addEventListener('click', openSidebar);

    const newOverlay = overlay.cloneNode(true);
    overlay.parentNode.replaceChild(newOverlay, overlay);
    newOverlay.addEventListener('click', closeSidebar);

    // Close on Escape
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeSidebar();
    });

    // Close when navigating to a new page on mobile
    sidebar.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth < 768) closeSidebar();
      });
    });
  }

  // Run on DOMContentLoaded or immediately if ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMobileNav);
  } else {
    setTimeout(initMobileNav, 50);
  }
})();
