// Run with node --test scripts/test/search.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {normalize, matches, safeUrl} = require('../search.js');
const vm = require('node:vm');
const fs = require('node:fs');

function searchPage(query) {
  class Element {
    constructor() { this.children = []; this.listeners = {}; this.disabled = true; this.value = ''; }
    addEventListener(name, callback) { this.listeners[name] = callback; }
    append(...children) { this.children.push(...children); }
    replaceChildren() { this.children = []; }
    get childNodes() { return this.children; }
    querySelector() { return this.button; }
  }
  const ids = Object.fromEntries(['search-query', 'search-form', 'search-status', 'search-results', 'search-more'].map(id => [id, new Element()]));
  ids['search-form'].button = new Element();
  let resolveFetch;
  vm.runInNewContext(fs.readFileSync(require.resolve('../search.js'), 'utf8'), {
    URL, URLSearchParams, location: {search: query},
    document: {getElementById: id => ids[id], createElement: () => new Element()},
    fetch: () => new Promise(resolve => { resolveFetch = resolve; }),
  });
  return {ids, load: async rows => {
    resolveFetch({ok: true, json: async () => rows});
    await new Promise(resolve => setImmediate(resolve));
  }};
}

test('URL q automatically prefills and searches only once the index is loaded; live search stays usable', async () => {
  const {ids, load} = searchPage('?q=Gr%C3%B6%C3%9Fere+Modelle');
  assert.equal(ids['search-query'].disabled, true);
  assert.match(ids['search-status'].textContent, /geladen/);
  await load([{title: 'Größere Modelle', sources: []}, {title: 'Andere Meldung', sources: []}]);
  assert.equal(ids['search-query'].value, 'Größere Modelle');
  assert.equal(ids['search-query'].disabled, false);
  assert.equal(ids['search-form'].button.disabled, false);
  assert.equal(ids['search-results'].children.length, 1);
  assert.equal(ids['search-results'].children[0].children[0].children[0].textContent, 'Größere Modelle');
  assert.equal(ids['search-status'].textContent, '1 Treffer · 1 angezeigt');
  ids['search-query'].value = 'fehlt';
  ids['search-query'].listeners.input();
  assert.match(ids['search-status'].textContent, /Keine Treffer/);
  ids['search-query'].value = 'Andere';
  let prevented = false;
  ids['search-form'].listeners.submit({preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
  assert.equal(ids['search-results'].children.length, 1);
});

test('URL query markup stays input text and does not create result markup', async () => {
  const query = '<img src=x onerror=alert(1)>';
  const {ids, load} = searchPage('?q=' + encodeURIComponent(query));
  await load([{title: query, sources: []}]);
  assert.equal(ids['search-query'].value, query);
  assert.equal(ids['search-results'].children[0].children[0].children[0].textContent, query);
});
test('German spelling, whitespace and all terms across fields', () => {
  const row = {title: 'GRÖẞERE Modelle', summary: 'Neue Lösung', topic: 'AI News', date: '2026-10-15', sources: [{label: 'Quelle', url: 'https://example.org'}]};
  assert.equal(normalize('  FÜR\t grössere '), 'fur grossere');
  assert.ok(matches(row, 'groessere   LÖSUNG quelle 2026'));
  assert.ok(!matches(row, 'modelle fehlt'));
  assert.ok(matches(row, ''));
});
test('only absolute HTTP(S) links', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,x', '//evil.org', '/relative', 'http://[']) assert.equal(safeUrl(url), '');
  assert.equal(safeUrl('https://example.org/a?q=x'), 'https://example.org/a?q=x');
});
