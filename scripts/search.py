"""Deterministic local search export. Never modifies editorial input data."""
import json
from urllib.parse import urlsplit

import history


def text(value):
    return value if isinstance(value, str) else ""


def safe_url(value):
    value = text(value).strip()
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''
    except ValueError:
        return ''


def build_search_index(briefing, pool, archive_dir):
    names = {t['id']: t.get('name', t['id']) for t in briefing.get('topics', [])}
    candidates = []

    def collect(document):
        if not isinstance(document, dict):
            raise ValueError('Search input must be an object')
        for topic in document.get('topics', []):
            if isinstance(topic, dict):
                for item in topic.get('items', []):
                    if isinstance(item, dict):
                        candidates.append(dict(item, topic_id=topic.get('id', '')))
        candidates.extend(document.get('items', []))

    # Current wording wins; retained history and archived dates stay intact.
    collect(briefing)
    collect(pool)
    for path in sorted(archive_dir.glob('*.json')):
        collect(json.loads(path.read_text(encoding='utf-8')))
    rows = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        title, tid = text(item.get('title')), text(item.get('topic_id'))
        date = history.parse_date(item.get('date')) or text(item.get('date'))
        if not title.strip() or not tid:
            continue
        sources = []
        raw_sources = item.get('sources')
        for source in raw_sources if isinstance(raw_sources, list) else []:
            if isinstance(source, dict):
                sources.append({'label': text(source.get('label')), 'url': safe_url(source.get('url'))})
        row = {'title': title, 'summary': text(item.get('summary')), 'topic_id': tid,
               'topic': names.get(tid, tid), 'date': date, 'sources': sources}
        if text(item.get('change_type')):
            row['change_type'] = item['change_type']
        duplicate = next((r for r in rows if r['topic_id'] == tid and history._same_item(r, row)), None)
        if duplicate is not None:
            duplicate['sources'] = history._merge_sources(duplicate['sources'], sources)
            continue
        rows.append(row)
    return sorted(rows, key=lambda r: (r['date'], r['topic_id'], r['title']), reverse=True)


def build_search_page():
    return '''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI-Briefing — Suche</title>
<link rel="stylesheet" href="style.css">
<script src="search.js" defer></script>
</head>
<body><main class="sheet">
<header class="top"><h1>AI-Briefing durchsuchen</h1></header>
<nav class="nav"><a href="index.html">Zur Übersicht</a></nav>
<p>Suche in den gespeicherten Meldungen der aktuellen Ausgabe, der Historie und der vorhandenen Monatsarchive. Keine Suche im gesamten Web oder in den Volltexten der verlinkten Originalartikel.</p>
<form id="search-form" role="search">
<label for="search-query">Suchbegriffe (alle Wörter müssen vorkommen)</label>
<div class="search-controls"><input id="search-query" type="search" name="q" autocomplete="off" aria-describedby="search-help" disabled><button type="submit" disabled>Suchen</button></div>
<p id="search-help" class="sub">Durchsucht Titel, Zusammenfassung, Thema, Originaldatum und Quellen. Groß-/Kleinschreibung und Umlaute werden angeglichen.</p>
</form>
<p id="search-status" role="status" aria-live="polite">Die Suche benötigt JavaScript.</p>
<noscript><p>Die lokale Suche benötigt JavaScript. Alle Übersichts- und Themenseiten funktionieren auch ohne JavaScript. <a href="index.html">Zur Übersicht</a></p></noscript>
<div id="search-results"></div>
<button id="search-more" type="button" hidden>Weitere 50 anzeigen</button>
<footer class="footer">Statische Suche im Browser, ohne Suchdienst oder Analytics.</footer>
</main></body></html>
'''
