// web/static/shared-shell.js
(function () {
  'use strict';
  const SHELL_VERSION = '20261013-collapse';
  if (window.__sharedShellVersion === SHELL_VERSION) return;
  window.__sharedShellVersion = SHELL_VERSION;

  function esc(s) {
    if (s === null || s === undefined) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
  }

  function shellHeader() {
    return `<header id="shell-header" class="w-full bg-[#1a1d24] px-5 md:px-8 py-3 flex items-center justify-between border-b border-[#2a2f3a] shrink-0 z-20">
        <button id="desktop-sidebar-toggle" type="button" aria-label="Collapse navigation" aria-controls="mobile-sidebar" aria-expanded="true" title="Collapse navigation">◀</button>
        <a href="/dashboard" class="flex items-center gap-4 pl-14 md:pl-0 flex-1 cursor-pointer hover:opacity-90 transition-opacity no-underline" title="Go to Dashboard">
          <img src="/static/logo_icon.png?v=20260717e" alt="motus.leap" class="site-logo" style="height:62px;width:auto;object-fit:contain;">
          <h1 class="text-[27px] md:text-[43px] font-semibold tracking-tight flex items-baseline leading-none site-title">
            <span class="text-white">m</span><span class="text-white">o</span><span class="text-white">t</span>
            <span class="text-[#2f8fc9]">u</span><span class="text-white">s</span>
            <span class="text-gray-500">.</span>
            <span class="text-white">l</span><span class="text-white">e</span><span class="text-white">a</span><span class="text-white">p</span>
          </h1>
        </a>
        <div class="flex items-center gap-2">
          <button id="live-console-btn" aria-label="Live Console" title="Live Console" class="ml-3 flex items-center justify-center w-10 h-10 rounded-xl bg-[#1a1d24] border border-[#2a2f3a] text-gray-400 hover:text-[#2f8fc9] hover:border-[#2f8fc9]/40 transition-all duration-200 hover:scale-105 active:scale-95 shadow-md shadow-black/20"><i class="fa-solid fa-terminal text-sm"></i></button>
          <button id="ai-chat-btn" aria-label="Open AI chat" title="Open AI chat" class="ml-3 flex items-center justify-center w-10 h-10 rounded-xl bg-transparent border border-transparent transition-all duration-200 hover:scale-105 active:scale-95 shadow-md shadow-black/40"><img src="/static/images/ai-chat-icon.jpg" alt="AI Chat" class="w-full h-full object-cover rounded-xl"></button>
        </div>
      </header>`;
  }

  function shellSidebar() {
    const path = window.location.pathname;
    const active = (href) => path === href ? 'nav-item active' : 'nav-item';
    const subActive = (href) => path === href || (href !== '/ai' && path.startsWith(href)) ? 'ai-sub active' : 'ai-sub';
    return `<aside id="mobile-sidebar" class="w-60 bg-[#1a1d24] p-3 flex-col border-r border-[#2a2f3a] overflow-hidden shrink-0 fixed md:static inset-y-0 left-0 z-40 -translate-x-full md:translate-x-0 flex">
        <nav class="flex flex-col gap-1.5 flex-1 min-h-0 overflow-y-auto">
          <div class="nav-section-label">Overview</div>
          <a href="/dashboard" class="${active('/dashboard')}" title="Dashboard"><i class="fas fa-th-large w-5 text-center"></i><span class="nav-label">Dashboard</span></a>
          <div class="nav-section-label mt-3">Library</div>
          <a href="/playlists" class="${active('/playlists')}" title="Playlists"><i class="fas fa-list-ul w-5 text-center"></i><span class="nav-label">Playlists</span></a>
          <a href="/subscriptions" class="${active('/subscriptions')}" title="Subscriptions"><i class="fa-solid fa-rss w-5 text-center"></i><span class="nav-label">Subscriptions</span></a>
          <div class="nav-section-label mt-3">Organize</div>
          <a href="/maintenance" class="${active('/maintenance')}" title="Maintenance Queue"><i class="fas fa-wrench w-5 text-center"></i><span class="nav-label">Maintenance Queue</span></a>
          <div class="mt-1.5 pt-1.5 border-t border-[#2a2f3a]/40">
            <div class="flex items-center justify-between ai-group-toggle px-4 py-3 rounded-lg text-sm cursor-pointer select-none transition-colors duration-200 ${path.startsWith('/ai') ? 'bg-[#2f8fc9]/10 text-white font-semibold' : 'text-gray-300 hover:text-white hover:bg-[#2a2f3a]'}" data-group="aihub" onclick="toggleAiGroup('aihub')">
              <a href="/ai" class="flex items-center gap-3" data-ai="hub"><i class="fas fa-robot w-5 text-center"></i><span class="nav-label">AI Hub</span></a>
              <i class="fas fa-chevron-down text-[10px] text-gray-500 ai-group-chevron"></i>
            </div>
            <div class="ai-group-items flex flex-col gap-1 mt-1" data-group="aihub">
              <a href="/ai/providers" class="ai-sub ${subActive('/ai/providers')} flex items-center gap-3 pl-11 pr-4 py-2.5 rounded-lg text-gray-400 text-sm transition-colors duration-200" data-ai="providers"><i class="fas fa-plug w-5 text-center"></i> Providers</a>
              <a href="/ai/rules" class="ai-sub ${subActive('/ai/rules')} flex items-center gap-3 pl-11 pr-4 py-2.5 rounded-lg text-gray-400 text-sm transition-colors duration-200" data-ai="rules"><i class="fas fa-sliders w-5 text-center"></i> Rules</a>
              <a href="/ai/jobs" class="ai-sub ${subActive('/ai/jobs')} flex items-center gap-3 pl-11 pr-4 py-2.5 rounded-lg text-gray-400 text-sm transition-colors duration-200" data-ai="jobs"><i class="fas fa-clock w-5 text-center"></i> Scheduled Jobs</a>
            </div>
          </div>
        </nav>
        <div class="sidebar-footer shrink-0 pt-3 mt-3 border-t border-[#2a2f3a]">
          <a href="/settings" id="settings-gear-btn" class="${active('/settings')}" aria-label="Settings" title="Settings">
            <i class="fa-solid fa-gear w-5 text-center"></i><span class="nav-label">Settings</span>
          </a>
          <button id="sidebar-collapse" class="hidden md:flex w-full items-center gap-3 px-4 py-3 mt-1 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-[#2a2f3a]" aria-label="Collapse navigation" title="Collapse navigation">
            <i class="fa-solid fa-angles-left w-5 text-center"></i><span class="nav-label">Collapse</span>
          </button>
        </div>
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
      html, body {
        height: 100%;
        overflow: hidden;
      }
      body {
        min-height: 100dvh;
        max-height: 100dvh;
      }
      .shell-row,
      body > .flex.flex-1 {
        min-height: 0;
        overflow: hidden;
      }
      main, .shell-row { min-width: 0; }
      main input:not([type="checkbox"]):not([type="radio"]), main select, main textarea { min-width: 0; max-width: 100%; }
      main button, main a.ui-control, main select, main input:not([type="checkbox"]):not([type="radio"]) { min-height: 44px; }
      main label, main .text-xs, main [class*="text-[10px]"], main [class*="text-[11px]"], main [class*="text-[9px]"] { font-size: .875rem; }
      main .text-gray-500, main .text-gray-600 { color: #a3acba; }
      main .text-gray-400 { color: #b8c0cc; }
      main button[class*="bg-[#2f8fc9]"]:not([class*="bg-[#2f8fc9]/"]), main .accent-bg { background-color: #2374a6; }
      main button[class*="bg-[#2f8fc9]"]:hover, main .accent-bg:hover { background-color: #1e6591; }
      main button.bg-green-600 { background-color: #166534; }
      main button.bg-green-600:hover { background-color: #14532d; }
      main button.bg-yellow-600, main button[class*="bg-amber-600"] { background-color: #854d0e; }
      main button.bg-yellow-600:hover, main button[class*="bg-amber-600"]:hover { background-color: #713f12; }
      main button[class*="bg-red-600"]:hover { background-color: #b91c1c; }
      main button:disabled { cursor: not-allowed; opacity: .5; }
      ::selection { background: #2374a6; color: #fff; }
      input, textarea { caret-color: #9bcbff; }
      button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible { outline: 2px solid #9bcbff; outline-offset: 3px; }
      [role="dialog"] { overflow-y: auto; max-height: 100dvh; }
      [role="dialog"] > div:not(.inset-0) { max-height: calc(100dvh - 32px); overflow-y: auto; }
      @media (max-width: 767px) { [role="dialog"] > div:not(.inset-0) { width: calc(100vw - 32px); margin-left: 0; margin-right: 0; } }
      [role="dialog"] button, [role="dialog"] summary { min-height: 44px; }
      .expert-input { margin-top: 8px; font-size: .875rem; color: #b8c0cc; }
      .expert-input summary { cursor: pointer; padding: 10px 0; text-decoration: underline; text-underline-offset: 3px; }
      .video-picker-list { max-height: 320px; overflow-y: auto; color: #b8c0cc; font-size: .875rem; }
      .video-choice { display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 8px 4px; }
      .video-choice input { width: 22px; height: 22px; flex-shrink: 0; }
      .video-choice span { overflow-wrap: anywhere; }
      @media (max-width: 767px) {
        html:has(#shell-header), body:has(#shell-header) { height: auto; max-height: none; overflow: visible; }
        body:has(#shell-header) > .flex.flex-1, .shell-row { overflow: visible; flex: none; }
        body:has(#shell-header) main { overflow: visible; padding: 20px 16px; }
        #shell-header { padding: 10px 12px; gap: 8px; min-height: 64px; }
        #shell-header > a { min-width: 0; gap: 8px; padding-left: 48px; }
        #shell-header .site-logo { display: none; }
        #shell-header .site-title { font-size: clamp(16px, 4.4vw, 24px); white-space: nowrap; }
        #shell-header > div { flex-shrink: 0; gap: 4px; }
        #shell-header button { margin-left: 0; width: 40px; height: 44px; }
        #sidebar-toggle { top: 10px; left: 12px; width: 44px; height: 44px; }
        #shell-footer { position: static; color: #a3acba; font-size: .75rem; gap: 12px; padding: 16px; }
        .mobile-stack { flex-direction: column; align-items: stretch; width: 100%; }
        .mobile-stack > * { min-width: 0; max-width: 100%; white-space: normal; }
        .mobile-stack > .flex { flex-wrap: wrap; }
        .mobile-stack input, .mobile-stack select { flex: none; width: 100%; }
        .mobile-stack button { white-space: normal; justify-content: center; }
        .playlist-context, .playlist-operations { flex-direction: column; align-items: stretch; }
        .playlist-context > div:first-child { flex-wrap: wrap; min-width: 0; }
        .playlist-context #playlist-title { width: 100%; white-space: normal; }
        .playlist-context > div:first-child > span:first-of-type { display: none; }
        .playlist-operations > div:last-child { display: grid; grid-template-columns: minmax(0, 1fr); }
        .playlist-toolbar { position: static !important; box-shadow: none; }
        #selection-bar { flex-wrap: wrap; }
        #selection-bar select { flex-basis: 100%; width: 100%; max-width: none; }
        #scan-results-box > div:first-child { flex-direction: column; align-items: stretch; gap: 12px; }
        #scan-results-box > div:first-child > div { flex-wrap: wrap; }
      }
      #mobile-sidebar {
        max-height: 100%;
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
      .nav-section-label {
        padding: .35rem 1rem;
        color: #788396;
        font-size: .7rem;
        font-weight: 700;
        letter-spacing: .09em;
        text-transform: uppercase;
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
      @media (min-width: 768px) {
        #desktop-sidebar-toggle { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; width: 44px; height: 44px; margin-right: 12px; border: 1px solid #394454; border-radius: 10px; color: #c6d1df; background: #222b38; cursor: pointer; }
        #mobile-sidebar {
          transform: none !important;
          display: flex !important;
        }
        #mobile-sidebar { transition: width .2s ease; }
        #mobile-sidebar.sidebar-collapsed { width: 4.5rem; }
        #mobile-sidebar.sidebar-collapsed .nav-label,
        #mobile-sidebar.sidebar-collapsed .nav-section-label,
        #mobile-sidebar.sidebar-collapsed .ai-group-chevron,
        #mobile-sidebar.sidebar-collapsed .ai-group-items { display: none !important; }
        #mobile-sidebar.sidebar-collapsed .nav-item,
        #mobile-sidebar.sidebar-collapsed .ai-group-toggle,
        #mobile-sidebar.sidebar-collapsed #sidebar-collapse { justify-content: center; padding-left: .75rem; padding-right: .75rem; }
        #mobile-sidebar.sidebar-collapsed #sidebar-collapse i { transform: rotate(180deg); }
      }
      @media (max-width: 767px) { #desktop-sidebar-toggle { display: none; } }
    </style>`;
  }

  function ensureShellLayout() {
    // 1) Global header — keep it above both the sidebar and main content.
    // Page content may use semantic <header> elements, so identify the shell
    // header by ID/version instead of taking the first header in the document.
    let header = document.getElementById('shell-header') || document.querySelector('header[data-shell-version]');
    if (!header) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellHeader().trim();
      header = tmp.content.firstElementChild;
      header.dataset.shellVersion = SHELL_VERSION;
      document.body.insertBefore(header, document.body.firstChild);
    } else if (header.dataset.shellVersion !== SHELL_VERSION) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellHeader().trim();
      const newHeader = tmp.content.firstElementChild;
      newHeader.dataset.shellVersion = SHELL_VERSION;
      header.parentNode.replaceChild(newHeader, header);
      header = newHeader;
    }
    if (header.parentElement !== document.body || header !== document.body.firstElementChild) {
      document.body.insertBefore(header, document.body.firstElementChild);
    }

    // 2) Sidebar — create if absent.
    let aside = document.getElementById('mobile-sidebar');
    if (!aside) {
      const tmp = document.createElement('template');
      tmp.innerHTML = shellSidebar().trim();
      aside = tmp.content.firstElementChild;
      aside.dataset.shellVersion = SHELL_VERSION;
    }

    // 3) Ensure <main> or content container lives inside a flex shell that also contains the sidebar.
    const main = document.querySelector('main') || document.querySelector('.container') || document.getElementById('app-container');
    if (!main) return;
    main.id ||= 'main-content';
    main.setAttribute('tabindex', '-1');
    if (!document.getElementById('skip-to-content')) {
      const skip = document.createElement('a');
      skip.id = 'skip-to-content';
      skip.className = 'skip-link';
      skip.href = '#' + main.id;
      skip.textContent = 'Skip to main content';
      document.body.prepend(skip);
    }
    aside.querySelector('nav')?.setAttribute('aria-label', 'Main navigation');
    aside.querySelectorAll('a').forEach(link => {
      const label = link.textContent.trim();
      if (label) {
        link.setAttribute('aria-label', link.getAttribute('aria-label') || label);
        link.setAttribute('title', link.getAttribute('title') || label);
      }
      const href = link.getAttribute('href');
      if (href && new URL(href, window.location.origin).pathname === window.location.pathname) {
        link.setAttribute('aria-current', 'page');
      }
    });

    const collapseButton = aside.querySelector('#sidebar-collapse');
    const headerCollapseButton = header.querySelector('#desktop-sidebar-toggle');
    const setCollapsed = (collapsed) => {
      aside.classList.toggle('sidebar-collapsed', collapsed);
      collapseButton?.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
      collapseButton?.setAttribute('title', collapsed ? 'Expand navigation' : 'Collapse navigation');
      headerCollapseButton?.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
      headerCollapseButton?.setAttribute('title', collapsed ? 'Expand navigation' : 'Collapse navigation');
      headerCollapseButton?.setAttribute('aria-expanded', String(!collapsed));
      if (headerCollapseButton) headerCollapseButton.textContent = collapsed ? '▶' : '◀';
    };
    try { setCollapsed(localStorage.getItem('motus_sidebar_collapsed') === 'true'); }
    catch { setCollapsed(false); }
    if (headerCollapseButton && !headerCollapseButton.dataset.wired) {
      headerCollapseButton.dataset.wired = '1';
      headerCollapseButton.addEventListener('click', () => {
        const next = !aside.classList.contains('sidebar-collapsed');
        setCollapsed(next);
        try { localStorage.setItem('motus_sidebar_collapsed', String(next)); } catch { /* Session-only preference. */ }
      });
    }
    if (collapseButton && !collapseButton.dataset.wired) {
      collapseButton.dataset.wired = '1';
      collapseButton.addEventListener('click', () => {
        const next = !aside.classList.contains('sidebar-collapsed');
        setCollapsed(next);
        try { localStorage.setItem('motus_sidebar_collapsed', String(next)); } catch { /* Session-only preference. */ }
      });
    }


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

  function checkQuotaBanner() {
    if (document.getElementById('quota-exceeded-banner')) return;
    const isExceeded = localStorage.getItem('quota_exceeded') === 'true';
    if (isExceeded) {
      const header = document.querySelector('header');
      if (!header) return;
      const banner = document.createElement('div');
      banner.id = 'quota-exceeded-banner';
      banner.className = 'w-full bg-amber-950/80 border-b border-amber-500/30 px-4 py-2 text-xs text-amber-200 flex items-center justify-between z-10 shrink-0';
      banner.innerHTML = `
        <div class="flex items-center gap-2">
          <i class="fas fa-exclamation-triangle text-amber-400"></i>
          <span><strong>YouTube API Quota Limit Reached:</strong> Live API sync paused until reset (at midnight PT). Displaying local disk cached data.</span>
        </div>
        <button onclick="this.parentElement.remove()" class="text-amber-300 hover:text-white text-xs px-2 py-0.5" aria-label="Dismiss">✕</button>
      `;
      header.parentNode.insertBefore(banner, header.nextSibling);
    }
  }

  function injectOnce() {
    ensureShellLayout();
    if (!document.getElementById('ui-polish-script')) {
      const script = document.createElement('script');
      script.id = 'ui-polish-script'; script.src = '/static/ui-polish.js?v=20261011a';
      document.body.appendChild(script);
    }
    checkQuotaBanner();
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
  }

  init();
})();
