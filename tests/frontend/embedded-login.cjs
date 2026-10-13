const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../web/static/embedded-login.js'), 'utf8');

function setup({blocked = false, valid = true} = {}) {
  const handlers = {}, saved = new Map();
  const popup = {close() { this.closed = true; }};
  const link = {getAttribute: () => '/api/auth/google', addEventListener: (_, cb) => handlers.click = cb};
  const message = {};
  const window = {self: {}, top: {}, location: {origin: 'https://tubemanager.onrender.com', replace(url) {this.destination = url;}},
    open(url) {this.opened = url; return blocked ? null : popup;}, addEventListener: (_, cb) => handlers.message = cb};
  let requests = 0;
  vm.runInNewContext(source, {window, document: {getElementById: id => id === 'back-link' ? link : message},
    localStorage: {setItem: (k,v) => saved.set(k,v)}, fetch: async () => {requests++; return {ok: valid, json: async () => ({username: 'test'})};}});
  handlers.click({preventDefault() {}});
  return {handlers, saved, popup, window, message, requests: () => requests};
}

test('Google opens outside the iframe and verified login returns to dashboard', async () => {
  const s = setup();
  assert.equal(s.window.opened, '/api/auth/google');
  await s.handlers.message({origin: s.window.location.origin, source: s.popup, data: {type: 'motus-embedded-login', token: 'test-token'}});
  assert.equal(s.saved.get('token'), 'test-token');
  assert.equal(s.window.location.destination, '/dashboard');
  assert.equal(s.popup.closed, true);
});
test('Rejects messages from another origin or another window', async () => {
  const s = setup();
  for (const event of [{origin: 'https://example.com', source: s.popup}, {origin: s.window.location.origin, source: {}}]) {
    await s.handlers.message({...event, data: {type: 'motus-embedded-login', token: 'test-token'}});
  }
  assert.equal(s.requests(), 0);
  assert.equal(s.saved.size, 0);
});
test('Invalid sessions are not saved and blocked popups have recovery instructions', async () => {
  const s = setup({valid: false});
  await s.handlers.message({origin: s.window.location.origin, source: s.popup, data: {type: 'motus-embedded-login', token: 'invalid'}});
  assert.equal(s.saved.size, 0);
  assert.match(s.message.textContent, /could not be verified/);
  assert.match(setup({blocked: true}).message.textContent, /Allow pop-ups/);
});
