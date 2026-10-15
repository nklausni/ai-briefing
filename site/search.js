'use strict';
// Local-only matching: German umlaut transliterations and accents are equivalent.
function normalize(value) {
  return String(value ?? '').toLowerCase().replace(/ß/g, 'ss')
    .replace(/ae/g, 'a').replace(/oe/g, 'o').replace(/ue/g, 'u')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim();
}
function matches(row, query) {
  const content = normalize([row.title, row.summary, row.topic, row.topic_id, row.date,
    ...(row.sources || []).flatMap(s => [s.label, s.url])].join(' '));
  return normalize(query).split(' ').filter(Boolean).every(term => content.includes(term));
}
function safeUrl(value) {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch { return ''; }
}
if (typeof module !== 'undefined') module.exports = {normalize, matches, safeUrl};

if (typeof document !== 'undefined') {
  const input = document.getElementById('search-query');
  const form = document.getElementById('search-form');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const more = document.getElementById('search-more');
  status.textContent = 'Suchindex wird geladen …';
  let index = [], found = [], limit = 50;
  function element(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }
  function render() {
    results.replaceChildren();
    const shown = found.slice(0, limit);
    status.textContent = found.length
      ? `${found.length} Treffer · ${shown.length} angezeigt`
      : 'Keine Treffer. Bitte andere Suchbegriffe verwenden.';
    for (const row of shown) {
      const card = element('article', undefined, 'dcard');
      const body = element('div', undefined, 'dbody');
      body.append(element('h2', row.title, 'dtitle'),
        element('p', `${row.date || 'Datum unbekannt'} · ${row.topic}`, 'dmeta'),
        element('p', row.summary));
      const sources = element('div', undefined, 'dsources');
      for (const source of row.sources || []) {
        const href = safeUrl(source.url);
        if (href) {
          const link = element('a', source.label || 'Quelle', 'dlink');
          link.href = href;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          sources.append(link);
        } else if (source.label) sources.append(element('span', source.label));
      }
      if (!sources.childNodes.length) sources.append(element('span', 'Keine verlinkte Quelle gespeichert.'));
      body.append(sources);
      card.append(body);
      results.append(card);
    }
    more.hidden = found.length <= limit;
  }
  function search() {
    found = index.filter(row => matches(row, input.value));
    limit = 50;
    render();
  }
  form.addEventListener('submit', event => { event.preventDefault(); search(); });
  input.addEventListener('input', search);
  more.addEventListener('click', () => { limit += 50; render(); });
  fetch('search-index.json').then(response => {
    if (!response.ok) throw new Error('Index unavailable');
    return response.json();
  }).then(data => {
    if (!Array.isArray(data)) throw new Error('Invalid index');
    index = data;
    input.disabled = false;
    form.querySelector('button').disabled = false;
    input.value = new URLSearchParams(location.search).get('q') || '';
    search();
  }).catch(() => {
    status.textContent = 'Suchindex konnte nicht geladen werden. Bitte die Seite neu laden oder die Übersicht nutzen.';
  });
}
