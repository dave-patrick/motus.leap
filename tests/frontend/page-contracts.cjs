const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const pages = ['dashboard', 'playlists', 'playlist', 'subscriptions', 'maintenance', 'bulk', 'settings', 'ai-hub'];

for (const page of pages) {
  test(`${page} uses the production shell and compiled CSS`, () => {
    const html = fs.readFileSync(`web/${page}.html`, 'utf8');
    assert.match(html, /\/static\/shared-shell\.js/);
    assert.match(html, /\/static\/tailwind\.css/);
    assert.doesNotMatch(html, /cdn\.tailwindcss\.com/);
    assert.match(html, /<main[\s>]/);
  });
}

test('compiled CSS stays within the production asset budget', () => {
  const bytes = fs.statSync('web/static/tailwind.css').size;
  assert.ok(bytes < 400_000, `tailwind.css is ${bytes} bytes`);
});

test('global shell header is distinct from page section headers', () => {
  const shell = fs.readFileSync('web/static/shared-shell.js', 'utf8');
  assert.match(shell, /id="shell-header"/);
  assert.match(shell, /getElementById\('shell-header'\)/);
  assert.doesNotMatch(shell, /let header = document\.querySelector\('header'\)/);
});

test('settings stays in the fixed sidebar footer instead of the top header', () => {
  const shell = fs.readFileSync('web/static/shared-shell.js', 'utf8');
  const header = shell.match(/function shellHeader\(\) \{([\s\S]*?)\n  \}/)?.[1] || '';
  assert.doesNotMatch(header, /id="settings-gear-btn"/);
  assert.match(shell, /class="sidebar-footer[^\"]*"[\s\S]*id="settings-gear-btn"[\s\S]*id="sidebar-collapse"/);
  assert.match(shell, /<nav class="[^"]*overflow-y-auto[^"]*">/);
});

test('playlist routes use a full navigation so page data always initializes', () => {
  const router = fs.readFileSync('web/static/ux-enhancements.js', 'utf8');
  assert.match(router, /function requiresFullPageNavigation\(url\)/);
  assert.match(router, /url\.startsWith\('\/playlist'\)/);
  assert.match(router, /if \(requiresFullPageNavigation\(url\)\) \{\s*window\.location\.href = url;/);
  assert.match(router, /!requiresFullPageNavigation\(href\)/);
});

test('maintenance exposes separate rescans and per-video removal', () => {
  const html = fs.readFileSync('web/maintenance.html', 'utf8');
  assert.match(html, /id="btn-rescan-playlists"/);
  assert.match(html, /id="btn-run-scan"[^>]*>[\s\S]*?Rescan queue/);
  assert.match(html, /function rescanPlaylistsFromMaintenance\(\)/);
  assert.match(html, /function maintDeleteVideo\(/);
});

test('playlist videos support visible single and selected removal', () => {
  const script = fs.readFileSync('web/static/playlist.js', 'utf8');
  assert.match(script, /aria-label="Remove video from playlist"/);
  assert.match(script, /id="delete-selected-btn"/);
  assert.match(script, /async function deleteSelectedVideos\(\)/);
  assert.match(script, /fetch\('\/api\/bulk\/delete'/);
});
