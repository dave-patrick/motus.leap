document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('mobile-sidebar');
  const overlay = document.getElementById('mobile-overlay');
  if (!sidebar || !overlay) return;

  window.openMobileSidebar = () => {
    sidebar.classList.remove('-translate-x-full');
    overlay.classList.remove('hidden');
  };
  window.closeMobileSidebar = () => {
    sidebar.classList.add('-translate-x-full');
    overlay.classList.add('hidden');
  };

  window.addEventListener('resize', () => {
    if (window.innerWidth >= 768) {
      overlay.classList.add('hidden');
      sidebar.classList.remove('-translate-x-full');
    }
  });
});
