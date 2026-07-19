// web/static/shared-shell.js
(function () {
  'use strict';
  const SHELL_VERSION = '20260719b';
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
    const settingsActive = path === '/settings' ? 'text-[#2f8fc9] border-[#2f8fc9]/40' : 'text-gray-400 border-[#2a2f3a]';
    return `<header class="w-full bg-[#1a1d24] px-5 md:px-8 py-3 flex items-center justify-between border-b border-[#2a2f3a] shrink-0 z-20">
        <div class="flex items-center gap-4 pl-14 md:pl-0">
          <img src="/static/logo_icon.png?v=20260717e" alt="motus.leap" class="site-logo" style="height:56px;width:auto;object-fit:contain;">
          <h1 class="text-3xl md:text-5xl font-semibold tracking-tight flex items-baseline leading-none site-title">
            <span class="text-white">m</span><span class="text-white">o</span><span class="text-white">t</span>
            <span class="text-[#2f8fc9]">u</span><span class="text-white">s</span>
            <span class="text-gray-500">.</span>
            <span class="text-white">l</span><span class="text-white">e</span><span class="text-white">a</span><span class="text-white">p</span>
          </h1>
        </div>
        <div class="flex items-center gap-2">
          <a href="/settings" id="settings-gear-btn" aria-label="Settings" title="Settings" class="ml-3 flex items-center justify-center w-10 h-10 rounded-xl bg-[#1a1d24] border ${settingsActive} hover:text-[#2f8fc9] hover:border-[#2f8fc9]/40 transition-all duration-200 hover:scale-105 active:scale-95 shadow-md shadow-black/20"><i class="fa-solid fa-gear text-sm"></i></a>
          <button id="live-console-btn" aria-label="Live Console" title="Live Console" class="ml-3 flex items-center justify-center w-10 h-10 rounded-xl bg-[#1a1d24] border border-[#2a2f3a] text-gray-400 hover:text-[#2f8fc9] hover:border-[#2f8fc9]/40 transition-all duration-200 hover:scale-105 active:scale-95 shadow-md shadow-black/20"><i class="fa-solid fa-terminal text-sm"></i></button>
          <button id="ai-chat-btn" aria-label="Open AI chat" title="Open AI chat" class="ml-3 flex items-center justify-center w-10 h-10 rounded-xl bg-transparent border border-transparent transition-all duration-200 hover:scale-105 active:scale-95 shadow-md shadow-black/40"><img src="/static/images/ai-chat-icon.jpg" alt="AI Chat" class="w-full h-full object-cover rounded-xl"></button>
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
            <div class="flex items-center justify-between ai-group-toggle px-4 py-3 rounded-lg text-sm cursor-pointer select-none transition-colors duration-200 ${path.startsWith('/ai') ? 'bg-[#2f8fc9]/10 text-white font-semibold' : 'text-gray-300 hover:text-white hover:bg-[#2a2f3a]'}" data-group="aihub" onclick="toggleAiGroup('aihub')">
              <a href="/ai" class="flex items-center gap-3" data-ai="hub"><i class="fas fa-robot w-5 text-center"></i> AI Hub</a>
              <i class="fas fa-chevron-down text-[10px] text-gray-500 ai-group-chevron"></i>
            </div>
            <div class="ai-group-items flex flex-col gap-1 mt-1" data-group="aihub">
              <a href="/ai/providers" class="ai-sub ${subActive('/ai/providers')} flex items-center gap-3 pl-11 pr-4 py-2.5 rounded-lg text-gray-400 text-sm transition-colors duration-200" data-ai="providers"><i class="fas fa-plug w-5 text-center"></i> Providers</a>
              <a href="/ai/rules" class="ai-sub ${subActive('/ai/rules')} flex items-center gap-3 pl-11 pr-4 py-2.5 rounded-lg text-gray-400 text-sm transition-colors duration-200" data-ai="rules"><i class="fas fa-sliders w-5 text-center"></i> Rules</a>
              <a href="/ai/jobs" class="ai-sub ${subActive('/ai/jobs')} flex items-center gap-3 pl-11 pr-4 py-2.5 rounded-lg text-gray-400 text-sm transition-colors duration-200" data-ai="jobs"><i class="fas fa-clock w-5 text-center"></i> Scheduled Jobs</a>
            </div>
          </div>
        </nav>
      </aside>`;
  }

  function shellFooter() {
    return `<footer class="fixed inset-x-0 bottom-0 bg-[#121419] border-t border-[#2a2f3a] px-6 py-2 text-[9px] text-gray-500 flex flex-wrap items-center justify-center gap-4 z-10">
      <span>&copy; 2026 motus.leap</span>
      <a href="/terms" data-legal="/terms" class="hover:text-[#2f8fc9]">Terms of Use</a>
      <a href="/privacy" data-legal="/privacy" class="hover:text-[#2f8fc9]">Privacy Policy</a>
      <span>Not affiliated with YouTube or Google.</span>
    </footer>`;
  }

  let _aiPanelInjected = false;
  function injectAISheet() {
    const existing = document.getElementById('ai-chat-panel');
    if (existing) {
      if (window.__aiPanelInjected) return;
      window.__aiPanelInjected = true;

      // Wire up buttons if the panel already exists (e.g. page transition)
      const robotBtn = document.getElementById('robot-button');
      if (robotBtn) {
        robotBtn.addEventListener('click', () => {
          if (typeof existing.show === 'function') existing.show();
        });
      }

      const chatBtn = document.getElementById('ai-chat-btn');
      if (chatBtn) {
        const already = chatBtn.dataset.shellWired === '1';
        chatBtn.addEventListener('click', () => {
          if (typeof existing.show === 'function') existing.show();
        });
        chatBtn.dataset.shellWired = already ? chatBtn.dataset.shellWired : '1';
      }

      return;
    }

    if (_aiPanelInjected) return;
    _aiPanelInjected = true;

    // 1) Create overlay sibling if absent
    let overlay = document.getElementById('ai-chat-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'ai-chat-overlay';
      overlay.className = 'fixed inset-0 bg-black/40 z-[65] hidden';
      document.body.appendChild(overlay);
    }

    // 2) Create panel sheet if absent
    const panel = document.createElement('div');
    panel.id = 'ai-chat-panel';
    panel.className = 'fixed top-0 right-0 h-full w-[400px] max-w-[100vw] bg-[#1a1d24] border-l border-[#2a2f3a] z-[70] flex flex-col transform translate-x-full transition-transform duration-200 ease-in-out font-sans shadow-2xl shadow-black/60';
    
    panel.innerHTML = `
      <div id="ai-chat-body" class="flex-1 overflow-hidden flex flex-col font-sans"></div>
    `;
    document.body.appendChild(panel);

    function show() {
      overlay.classList.remove('hidden');
      panel.classList.remove('translate-x-full');
    }

    function hide() {
      if (panel.classList.contains('docked')) {
        panel.classList.remove('docked');
        const row = document.querySelector('main')?.parentElement;
        if (row) row.style.setProperty('padding-right', '0px', 'important');
      }
      overlay.classList.add('hidden');
      panel.classList.add('translate-x-full');
    }

    const chatBtn = document.getElementById('ai-chat-btn');
    if (chatBtn) {
      chatBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (panel.classList.contains('translate-x-full')) {
          show();
        } else {
          hide();
        }
      });
      chatBtn.setAttribute('data-shell-wired', '1');
    }

    const robotBtn = document.getElementById('robot-button');
    if (robotBtn) {
      robotBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (panel.classList.contains('translate-x-full')) {
          show();
        } else {
          hide();
        }
      });
    }

    overlay.addEventListener('click', hide);

    panel.show = show;
    panel.hide = hide;
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

  function shellStyles() {
    if (document.getElementById('shell-nav-styles')) return '';
    return `<style id="shell-nav-styles">
      @font-face {
        font-family: 'Deltha';
        src: url('/static/Deltha.otf') format('opentype');
        font-weight: normal;
        font-style: normal;
        font-display: swap;
      }
      html, body, input, select, textarea, button {
        font-family: 'Inter', sans-serif;
      }
      .site-title, .site-title * {
        font-family: 'Deltha', serif !important;
      }
      .font-mono, .font-mono * {
        font-family: 'JetBrains Mono', monospace !important;
      }
      .nav-item {
        display: flex;
        align-items: center;
        gap: .75rem;
        padding: .75rem 1rem;
        border-radius: .5rem;
        color: #9ca3af;
        font-size: .875rem;
        transition: background-color .2s, color .2s;
      }
      .nav-item.active {
        background-color: #2f8fc9;
        color: #fff;
        font-weight: 600;
      }
      .nav-item:not(.active):hover {
        background-color: #2a2f3a;
        color: #fff;
      }
      .ai-sub {
        display: flex;
        align-items: center;
        gap: .75rem;
        padding: .6rem 1rem .6rem 2.75rem;
        border-radius: .5rem;
        color: #9ca3af;
        font-size: .875rem;
        border-left: 2px solid transparent;
        transition: background-color .2s, color .2s;
      }
      .ai-sub.active {
        background-color: #2a2f3a;
        color: #fff;
        border-left: 2px solid #2f8fc9;
      }
      .ai-sub:not(.active):hover {
        background-color: #20242c;
        color: #fff;
      }
      .ai-group-toggle {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: .75rem 1rem;
        border-radius: .5rem;
        color: #d1d5db;
        font-size: .875rem;
        cursor: pointer;
        user-select: none;
      }
    </style>`;
  }

  function ensureShellLayout() {
    // 1) Header — create if the page has none (shared-shell is the single source).
    let header = document.querySelector('header');
    if (!header) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellHeader().trim();
      header = tmp.content.firstElementChild;
      header.dataset.shellVersion = SHELL_VERSION;
      document.body.insertBefore(header, document.body.firstChild);
    } else if (!header.dataset.shellVersion) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellHeader().trim();
      const newHeader = tmp.content.firstElementChild;
      newHeader.dataset.shellVersion = SHELL_VERSION;
      header.parentNode.replaceChild(newHeader, header);
    }

    // 2) Sidebar — create if absent.
    let aside = document.getElementById('mobile-sidebar');
    if (!aside) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellSidebar().trim();
      aside = tmp.content.firstElementChild;
      aside.dataset.shellVersion = SHELL_VERSION;
    }

    // 3) Ensure <main> lives inside a flex shell that also contains the sidebar.
    const main = document.querySelector('main');
    if (!main) return;

    const container = main.parentElement;
    const containerIsShell = container && (
      container === aside.parentElement ||
      container.classList.contains('shell-row') ||
      /(^|\s)flex(\s|$)/.test(container.className)
    );

    if (containerIsShell && container !== document.body) {
      // Existing flex wrapper (e.g. ai-hub): drop the sidebar in as its first child.
      if (!container.contains(aside)) container.insertBefore(aside, container.firstChild);
    } else {
      // No usable shell (e.g. dashboard): build one and move main + sidebar into it.
      const row = document.createElement('div');
      row.className = 'shell-row flex flex-1 min-h-0 overflow-hidden';
      main.parentNode.insertBefore(row, main);
      row.appendChild(aside);
      row.appendChild(main);
    }

    // 4) Mobile hamburger toggle + tap overlay (mobile only).
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
    injectAISheet();

    if (!document.getElementById('shell-nav-styles') && shellStyles()) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellStyles().trim();
      document.head.appendChild(tmp.content.firstElementChild);
    }

    document.querySelectorAll('#shell-footer, footer[data-shell-version]').forEach(el => el.remove());

    if (!document.querySelector('footer[data-shell-version]')) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellFooter().trim();
      const footer = tmp.content.firstElementChild;
      footer.id = 'shell-footer';
      footer.dataset.shellVersion = SHELL_VERSION;
      document.body.appendChild(footer);
    }

    if (!document.getElementById('legal-modal')) {
      const modalOverlay = document.createElement('div');
      modalOverlay.id = 'legal-modal';
      modalOverlay.className = 'fixed inset-0 z-[70] hidden';
      modalOverlay.innerHTML = `
        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm"></div>
        <div class="relative z-[71] flex items-center justify-center min-h-screen p-4">
          <div class="bg-[#13161d] border border-[#2a2f3a] rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden">
            <div class="flex items-center justify-between px-4 py-3 border-b border-[#2a2f3a]">
              <div id="legal-modal-title" class="text-sm font-semibold text-white"></div>
              <button id="legal-modal-close" class="text-gray-400 hover:text-white text-xs px-2 py-1">Close</button>
            </div>
            <div id="legal-modal-body" class="p-4 overflow-y-auto max-h-[calc(85vh-48px)] text-xs text-gray-300 space-y-3"></div>
          </div>
        </div>`;
      document.body.appendChild(modalOverlay);

      const close = () => modalOverlay.classList.add('hidden');
      modalOverlay.querySelector('#legal-modal-close').addEventListener('click', close);
      modalOverlay.querySelector('.bg-black\\/70').addEventListener('click', close);
      document.addEventListener('keydown', function onKey(e) {
        if (e.key === 'Escape' && modalOverlay.classList.contains('hidden') === false) close();
      });
    }

    document.querySelectorAll('[data-legal]').forEach(link => {
      if (link.dataset.shellLegalWired) return;
      link.dataset.shellLegalWired = '1';
      link.addEventListener('click', async (e) => {
        const target = link.getAttribute('data-legal');
        if (!target) return;
        e.preventDefault();
        try {
          const resp = await fetch(target);
          if (!resp.ok) throw new Error('HTTP ' + resp.status);
          const html = await resp.text();
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const title = (doc.querySelector('h1')?.textContent || doc.title || 'Page').trim();
          const main = doc.querySelector('main');
          let bodyHtml = '';
          if (main) {
            bodyHtml = main.innerHTML;
          } else {
            const body = doc.querySelector('body');
            bodyHtml = body ? body.innerHTML : html;
          }
          const modal = document.getElementById('legal-modal');
          document.getElementById('legal-modal-title').textContent = title;
          document.getElementById('legal-modal-body').innerHTML = bodyHtml;
          modal.classList.remove('hidden');
        } catch (err) {
          console.error('legal modal failed', err);
          window.location.href = target;
        }
      });
    });
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
