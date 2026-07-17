// web/static/shared-shell.js
(function () {
  'use strict';
  const SHELL_VERSION = '20260717a';
  if (window.__sharedShellVersion === SHELL_VERSION) return;
  window.__sharedShellVersion = SHELL_VERSION;

  function esc(s) {
    if (s === null || s === undefined) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  function shellHeader() {
    const path = window.location.pathname;
    const settingsActive = path === '/settings' ? ' text-[#2f8fc9]' : ' text-gray-300';
    const terminalActive = path === '/dashboard' ? ' text-[#2f8fc9]' : ' text-gray-300';
    return `<header class="w-full bg-[#1a1d24] px-5 md:px-8 py-3 flex items-center justify-between border-b border-[#2a2f3a] shrink-0 z-20">
        <div class="flex items-center gap-4 pl-14 md:pl-0">
          <img src="/static/logo_icon.png?v=3" alt="motus.leap" class="site-logo" style="height:56px;width:auto;object-fit:contain;">
          <h1 class="text-3xl md:text-5xl font-semibold tracking-tight flex items-baseline leading-none site-title">
            <span class="text-white">m</span><span class="text-white">o</span><span class="text-white">t</span>
            <span class="text-[#2f8fc9]">u</span><span class="text-white">s</span>
            <span class="text-gray-500">.</span>
            <span class="text-white">l</span><span class="text-white">e</span><span class="text-white">a</span><span class="text-white">p</span>
          </h1>
        </div>
        <div class="flex items-center gap-2">
          <a href="/settings" aria-label="Settings" title="Settings" class="ml-3 flex items-center justify-center w-9 h-9 rounded-lg border border-[#2a2f3a]${settingsActive} hover:text-white hover:border-[#2f8fc9] transition-colors">&#9881;</a>
          <a href="/dashboard" aria-label="Terminal" title="Terminal" class="ml-3 flex items-center justify-center w-9 h-9 rounded-lg border border-[#2a2f3a]${terminalActive} hover:text-white hover:border-[#2f8fc9] transition-colors">&gt;_</a>
          <button id="robot-button" aria-label="Open AI chat" title="Open AI chat" class="ml-3 flex items-center justify-center w-9 h-9 rounded-lg border border-[#2a2f3a] text-gray-300 hover:text-white hover:border-[#2f8fc9] transition-colors">&#129302;</button>
        </div>
      </header>`;
  }

  function shellSidebar() {
    const path = window.location.pathname;
    const active = (href) => path === href ? 'nav-item active' : 'nav-item';
    const subActive = (href) => path === href || (href !== '/ai' && path.startsWith(href)) ? 'ai-sub active' : 'ai-sub';
    return `<aside id="mobile-sidebar" class="w-60 bg-[#1a1d24] p-3 flex-col border-r border-[#2a2f3a] overflow-y-auto shrink-0 fixed md:static inset-y-0 left-0 z-40 -translate-x-full md:translate-x-0 flex">
        <nav class="flex flex-col gap-1.5">
          <a href="/dashboard" class="${active('/dashboard')} flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-colors duration-200"><i class="fas fa-th-large w-5 text-center"></i> Dashboard</a>
          <a href="/playlists" class="${active('/playlists')} flex items-center gap-3 px-4 py-3 rounded-lg text-gray-400 text-sm transition-colors duration-200"><i class="fas fa-list-ul w-5 text-center"></i> Playlists</a>
          <a href="/subscriptions" class="${active('/subscriptions')} flex items-center gap-3 px-4 py-3 rounded-lg text-gray-400 text-sm transition-colors duration-200"><i class="fab fa-youtube w-5 text-center"></i> Subscriptions</a>
          <a href="/maintenance" class="${active('/maintenance')} flex items-center gap-3 px-4 py-3 rounded-lg text-gray-400 text-sm transition-colors duration-200"><i class="fas fa-wrench w-5 text-center"></i> Maintenance Queue</a>
          <div class="mt-1.5 pt-1.5 border-t border-[#2a2f3a]/40">
            <div class="flex items-center justify-between ai-group-toggle px-4 py-3 rounded-lg text-gray-300 text-sm cursor-pointer select-none" data-group="aihub" onclick="toggleAiGroup('aihub')">
              <a href="/ai" class="${subActive('/ai')}" data-ai="hub"><i class="fas fa-robot w-5 text-center"></i> AI Hub</a>
              <i class="fas fa-chevron-down text-[10px] text-gray-500 ai-group-chevron"></i>
            </div>
            <div class="ai-group-items flex flex-col gap-1 mt-1" data-group="aihub">
              <a href="/ai/providers" class="${subActive('/ai/providers')}" data-ai="providers"><i class="fas fa-plug w-5 text-center"></i> Providers</a>
              <a href="/ai/rules" class="${subActive('/ai/rules')}" data-ai="rules"><i class="fas fa-sliders w-5 text-center"></i> Rules</a>
              <a href="/ai/jobs" class="${subActive('/ai/jobs')}" data-ai="jobs"><i class="fas fa-clock w-5 text-center"></i> Scheduled Jobs</a>
            </div>
          </div>
        </nav>
      </aside>`;
  }

  function shellFooter() {
    return `<footer class="fixed inset-x-0 bottom-0 bg-[#121419] border-t border-[#2a2f3a] px-6 py-2 text-[9px] text-gray-500 flex flex-wrap items-center justify-center gap-4 z-10">
      <span>&copy; 2026 motus.leap</span>
      <a href="/terms" class="hover:text-[#2f8fc9]">Terms of Use</a>
      <a href="/privacy" class="hover:text-[#2f8fc9]">Privacy Policy</a>
      <span>Not affiliated with YouTube or Google.</span>
    </footer>`;
  }

  let _aiPanelInjected = false;
  function injectAISheet() {
    if (_aiPanelInjected) return;
    _aiPanelInjected = true;

    const btn = document.getElementById('robot-button');
    if (!btn) return;
    btn.setAttribute('data-shell-wired', '1');

    const old = document.getElementById('ai-chat-btn');
    if (old) old.remove();

    const panel = document.createElement('div');
    panel.id = 'ai-chat-panel';
    panel.className = 'fixed inset-0 z-[60]';

    const overlay = document.createElement('div');
    overlay.id = 'ai-chat-overlay';
    overlay.className = 'absolute inset-0 bg-black/60 hidden';

    const sheet = document.createElement('div');
    sheet.className = 'absolute right-0 top-0 h-full w-[360px] max-w-[100vw] bg-[#141720] border-l border-[#232834] shadow-2xl translate-x-full transition-transform duration-200';
    sheet.innerHTML = `
      <div class="flex items-center justify-between px-4 py-3 border-b border-[#2a2f3a]">
        <div class="font-semibold text-sm text-white">Shared AI Chat</div>
        <button id="ai-chat-close" class="px-2 py-1 text-xs text-gray-400 hover:text-white">Close</button>
      </div>
      <div id="ai-chat-drop" class="p-3 text-xs text-gray-500">Drop-in AI chat shell.</div>
    `;

    panel.appendChild(overlay);
    panel.appendChild(sheet);
    document.body.appendChild(panel);

    let open = false;
    function show() {
      open = true;
      overlay.classList.remove('hidden');
      sheet.classList.remove('translate-x-full');
    }
    function hide() {
      open = false;
      overlay.classList.add('hidden');
      sheet.classList.add('translate-x-full');
    }

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      open ? hide() : show();
    });
    overlay.addEventListener('click', hide);
    sheet.querySelector('#ai-chat-close').addEventListener('click', hide);
  }

  function shellHamburger() {
    return `<button id="sidebar-toggle" aria-label="Open menu" title="Menu"
      class="md:hidden fixed top-4 left-3 z-40 flex items-center justify-center w-9 h-9 rounded-lg
             bg-[#1a1d24] border border-[#2a2f3a] text-gray-300 hover:text-white">
      <i class="fas fa-bars"></i></button>`;
  }

  function shellOverlay() {
    return `<div id="mobile-overlay" class="fixed inset-0 bg-black/50 z-30 hidden md:hidden"></div>`;
  }

  function ensureShellLayout() {
    // Create the off-canvas sidebar if it does not exist on this page.
    let aside = document.getElementById('mobile-sidebar');
    if (!aside) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellSidebar().trim();
      aside = tmp.content.firstElementChild;
      aside.dataset.shellVersion = SHELL_VERSION;
    }

    const main = document.querySelector('main');
    if (!main) return;

    // Wrap header(main) inside a flex-row shell holding [sidebar][main] so the
    // desktop sidebar and the mobile off-canvas drawer both have a home.
    if (!main.parentElement || !main.parentElement.classList.contains('shell-row')) {
      const row = document.createElement('div');
      row.className = 'shell-row flex flex-1 min-h-0 overflow-hidden';
      main.parentNode.insertBefore(row, main);
      row.appendChild(aside);
      row.appendChild(main);
    } else {
      // shell-row already present — make sure the sidebar lives inside it.
      if (!main.parentElement.contains(aside)) main.parentElement.insertBefore(aside, main);
    }

    // Mobile hamburger toggle (header, mobile only) + tap overlay.
    if (!document.getElementById('sidebar-toggle')) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellHamburger().trim();
      document.body.appendChild(tmp.content.firstElementChild);
    }
    if (!document.getElementById('mobile-overlay')) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellOverlay().trim();
      document.body.appendChild(tmp.content.firstElementChild);
    }

    // Default mobile state: sidebar off-screen, overlay hidden.
    aside.classList.add('-translate-x-full');
  }

  function injectOnce() {
    const header = document.querySelector('header');
    if (header && !header.dataset.shellVersion) {
      header.innerHTML = shellHeader();
      header.dataset.shellVersion = SHELL_VERSION;
    }

    ensureShellLayout();

    document.querySelectorAll('#shell-footer, footer[data-shell-version]').forEach(el => el.remove());

    if (!document.querySelector('footer[data-shell-version]')) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellFooter().trim();
      const footer = tmp.content.firstElementChild;
      footer.id = 'shell-footer';
      footer.dataset.shellVersion = SHELL_VERSION;
      document.body.appendChild(footer);
    }

    const btn = document.getElementById('robot-button');
    if (btn && btn.getAttribute('data-shell-wired') !== '1') {
      btn.setAttribute('data-shell-wired', '1');
      btn.addEventListener('click', () => {
        const drawer = document.getElementById('global-agent-drawer');
        if (!drawer) return;
        drawer.classList.toggle('hidden');
      });
    }
  }
  function init() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectOnce);
    } else {
      injectOnce();
    }
    document.addEventListener('DOMContentLoaded', injectOnce);
  }

  init();
})();
