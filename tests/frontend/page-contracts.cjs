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
