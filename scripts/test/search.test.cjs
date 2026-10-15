// Run with node --test scripts/test/search.test.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {normalize, matches, safeUrl} = require('../search.js');
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
