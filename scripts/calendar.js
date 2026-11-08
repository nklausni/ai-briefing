// Between daily builds the published windows can only lose older stories.
(() => {
  const { edition, days } = document.currentScript.dataset;
  const berlinDate = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Berlin' });
  const display = new Intl.DateTimeFormat('de-DE', { dateStyle: 'long', timeZone: 'UTC' });
  let lastDay = edition;

  function update() {
    const today = berlinDate.format(new Date());
    if (today <= lastDay) return;
    lastDay = today;
    const end = new Date(today + 'T00:00:00Z');
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - Number(days) + 1);
    const since = start.toISOString().slice(0, 10);
    const includes = date => since <= date && date <= today;
    const period = Number(days) === 1 ? display.format(end) : display.formatRange(start, end);
    const label = document.querySelector('.range-period');
    if (label) {
      document.title = document.title.replace(label.textContent, period);
      label.textContent = period;
    }

    document.querySelectorAll('[data-date]').forEach(node => {
      if (!includes(node.dataset.date)) node.remove();
    });
    document.querySelectorAll('.lede, .ov-summary, .ov-stale, .stale, .skip').forEach(node => {
      if (node.matches('.skip')) node.previousElementSibling?.remove();
      node.remove();
    });

    for (const card of document.querySelectorAll('.ov-card')) {
      const count = card.dataset.dates.split(' ').filter(includes).length;
      card.querySelector('.ov-count').textContent = count + (count === 1 ? ' Meldung' : ' Meldungen');
      card.querySelector('.ov-empty')?.remove();
      if (count === 0) {
        const message = document.createElement('p');
        message.className = 'ov-empty';
        message.textContent = 'In diesem Zeitraum keine eigenständigen Meldungen.';
        card.querySelector('.ov-link').before(message);
      }
    }
    const front = document.querySelector('.front-page');
    if (front && !front.querySelector('article')) front.remove();

    const list = document.querySelector('.detail-list');
    if (list && !list.querySelector('.dcard, .range-empty')) {
      const message = document.createElement('p');
      message.className = 'range-empty';
      message.textContent = 'Für diesen Zeitraum liegen keine Meldungen vor.';
      list.append(message);
    }
  }

  update();
  window.addEventListener('pageshow', update);
  document.addEventListener('visibilitychange', update);
  function nextMinute() {
    setTimeout(() => { update(); nextMinute(); }, 60000 - Date.now() % 60000);
  }
  nextMinute();
})();
