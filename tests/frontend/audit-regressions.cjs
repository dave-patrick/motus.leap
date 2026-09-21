// Run: node --test tests/frontend/audit-regressions.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const read = name => fs.readFileSync(`web/static/${name}.js`, 'utf8');
function element(classes = []) {
  const set = new Set(classes);
  return {
    dataset: {}, attributes: {}, listeners: {}, style: {}, inert: false,
    classList: { add: x => set.add(x), remove: x => set.delete(x), contains: x => set.has(x),
      toggle(x, on) { const yes = on ?? !set.has(x); yes ? set.add(x) : set.delete(x); return yes; } },
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(k, fn) { this.listeners[k] = fn; },
    focus() { this.focused = true; },
    getClientRects: () => [{}],
  };
}
test('mobile menu opens and closes the same overlay and restores focus', () => {
  const sidebar = element(['-translate-x-full']);
  const overlay = element(['hidden']);
  const toggle = element();
  const link = element();
  sidebar.querySelector = () => link;
  sidebar.querySelectorAll = () => [link];
  const document = {readyState: 'complete', activeElement: toggle,
    body: {style: {overflow: 'auto'}}, listeners: {},
    getElementById: id => ({'mobile-sidebar': sidebar, 'mobile-overlay': overlay, 'sidebar-toggle': toggle})[id],
    addEventListener(k, fn) { this.listeners[k] = fn; }};
  const window = {innerWidth: 390, addEventListener() {}};
  vm.runInNewContext(read('mobile-nav'), {document, window});
  assert.equal(sidebar.inert, true);
  toggle.listeners.click();
  assert.equal(overlay.classList.contains('hidden'), false);
  assert.equal(sidebar.inert, false);
  assert.equal(toggle.attributes['aria-expanded'], 'true');
  assert.equal(link.focused, true);
  document.listeners.keydown({key: 'Escape'});
  assert.equal(overlay.classList.contains('hidden'), true);
  assert.equal(document.body.style.overflow, 'auto');
  assert.equal(toggle.focused, true);
});
test('cookie-only session validates on server without a login redirect', async () => {
  const window = {location: {hash: '', href: '/dashboard'}};
  let calls = 0;
  const context = {window, document: {cookie: ''}, localStorage: {getItem: () => null},
    fetch: async () => { calls++; return {status: 200}; }, setTimeout};
  vm.runInNewContext(read('auth-check'), context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 1);
  assert.equal(window.location.href, '/dashboard');
});
test('logout revokes on server before clearing local state', async () => {
  const order = [];
  const window = {location: {href: '/dashboard'}};
  const context = {window, document: {cookie: ''},
    localStorage: {getItem: () => 'token', removeItem: () => order.push('clear')},
    fetch: async (url, options) => { assert.equal(url, '/api/auth/logout'); assert.equal(options.method, 'POST'); order.push('revoke'); return {ok: true}; }};
  vm.createContext(context); vm.runInContext(read('global_scripts'), context);
  await context.logoutUser();
  assert.equal(order[0], 'revoke');
  assert.equal(window.location.href, '/auth');
});
test('service worker ignores private navigation, API and cross-origin requests', () => {
  const listeners = {};
  const context = {URL, self: {location: {origin: 'https://example.test'}, addEventListener: (name, fn) => listeners[name] = fn}};
  vm.runInNewContext(read('sw'), context);
  for (const url of ['https://example.test/dashboard', 'https://example.test/api/stats', 'https://other.test/static/a.js']) {
    listeners.fetch({request: {url, method: 'GET'}, respondWith() { assert.fail('private or foreign request intercepted'); }});
  }
});
function trackerContext(dashboard = false) {
  const sockets = [];
  function WebSocket() { this.readyState = 1; this.sent = []; this.send = msg => this.sent.push(JSON.parse(msg)); sockets.push(this); }
  WebSocket.OPEN = 1; WebSocket.CONNECTING = 0;
  const document = {hidden: false, getElementById: () => null, listeners: {}, addEventListener(name, fn) {this.listeners[name] = fn;}};
  const window = {location: {protocol: 'https:', host: 'example.test'}, addEventListener() {}};
  if (dashboard) window.connectWebSocket = () => {};
  const context = {window, document, WebSocket, console, localStorage: {getItem: () => null},
    fetch: async () => ({ok: true, json: async () => ({})}), setInterval: () => 1, clearInterval() {}, setTimeout: () => 1};
  const source = read('ux-enhancements');
  vm.createContext(context);
  vm.runInContext(source.slice(source.indexOf('function startAgentActivityTracker()'), source.indexOf('// Auto-initialize agent activity tracker')), context);
  context.startAgentActivityTracker();
  return {context, sockets, document};
}
test('shared log stream answers heartbeats and reconnects on tab return', () => {
  const {sockets, document} = trackerContext();
  assert.equal(sockets.length, 1);
  sockets[0].onmessage({data: JSON.stringify({type: 'ping'})});
  assert.equal(sockets[0].sent[0].type, 'pong');
  sockets[0].readyState = 3;
  document.listeners.visibilitychange();
  assert.equal(sockets.length, 2);
});
test('shared tracker does not duplicate the dashboard WebSocket', () => {
  const {context, sockets} = trackerContext(true);
  context.startAgentActivityTracker();
  assert.equal(sockets.length, 0);
});
