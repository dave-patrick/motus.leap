// Headless smoke test for shared-shell injection contract across page variants.
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const web = path.join(__dirname, 'web');
const shellCode = fs.readFileSync(path.join(web, 'static', 'shared-shell.js'), 'utf8');
const navCode = fs.readFileSync(path.join(web, 'static', 'mobile-nav.js'), 'utf8');

function run(page, label) {
  const html = fs.readFileSync(path.join(web, page), 'utf8');
  const dom = new JSDOM(html, { runScripts: 'outside-only', pretendToBeVisual: true,
    url: 'https://tube-manager.onrender.com/' + page });
  const { window } = dom;
  window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener(){}, removeListener(){} }));
  const results = [];
  const check = (n, c) => results.push([n, !!c]);
  try {
    new window.Function(shellCode).call(window);
    new window.Function(navCode).call(window);
    window.document.dispatchEvent(new window.Event('DOMContentLoaded'));
  } catch (e) { console.error(`[${label}] THREW:`, e.message); }
  const d = window.document;
  check('header injected/created', d.querySelector('header .site-title'));
  check('#mobile-sidebar CREATED', d.getElementById('mobile-sidebar'));
  check('#sidebar-toggle CREATED', d.getElementById('sidebar-toggle'));
  check('#mobile-overlay CREATED', d.getElementById('mobile-overlay'));
  check('main present (NOT wiped)', d.querySelector('main'));
  const main = d.querySelector('main');
  check('main inside flex shell with sidebar', main && main.parentElement && main.parentElement.contains(d.getElementById('mobile-sidebar')));
  check('footer injected', d.querySelector('footer[data-shell-version]'));
  check('sidebar md:translate-x-0 (visible on desktop)', (() => { const s=d.getElementById('mobile-sidebar'); return s && s.className.includes('md:translate-x-0'); })());
  check('mobile-nav toggle click no-throw', (() => { try { d.getElementById('sidebar-toggle').click(); return true; } catch(e){ return false; } })());
  let pass = 0;
  console.log(`\n=== ${label} (${page}) ===`);
  for (const [n, ok] of results) { console.log((ok ? 'PASS' : 'FAIL') + ' - ' + n); if (ok) pass++; }
  console.log(`${pass}/${results.length} passed`);
  return pass === results.length;
}

const a = run('dashboard.html', 'dashboard (no wrapper, unclosed header)');
const b = run('ai-hub.html', 'ai-hub (existing flex wrapper, no header)');
process.exit(a && b ? 0 : 2);
