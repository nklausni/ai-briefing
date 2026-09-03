# AI-Briefing

Öffentliches, automatisch befülltes Briefing zu acht Themen.

**Themen (Bereiche):**

- AI News
- Lokale LLMs
- Agentic Engineering / Vibe Coding
- AI Tools
- Context Engineering
- AI Security
- AI Governance
- Enterprise

Pro Bereich gibt es eine Detailseite mit einem **Radar** (Ringe = Impact, innen = wichtiger;
Segmente = Kategorie) und den Meldungen im Detail inkl. Quell-Links. Die Übersichtsseite
bündelt die Top-Meldungen aller Bereiche.

## Aufbau

```
AI Briefing/
├── index.html              ← Redirect auf site/index.html
├── data/
│   ├── briefing.json       ← Datenquelle des Tages (Inhalt aller Bereiche)
│   └── history.json        ← kumulativer Pool aller bisherigen Meldungen (Historie)
├── scripts/
│   ├── history.py          ← Pool: Ingest/Dedup, Zeitraum-Filter
│   └── render.py           ← Generator: merged briefing.json in den Pool → schreibt site/
└── site/                   ← generierte statische Seiten (kein JavaScript)
    ├── 7d/ · 14d/ · 30d/   ← Zeitraum-Ansichten (letzte 7/14/30 Tage)
    ├── index.html
    ├── ai-news.html
    ├── lokale-llms.html
    ├── agentic-engineering.html
    ├── ai-tools.html
    ├── context-engineering.html
    ├── ai-security.html
    ├── ai-governance.html
    └── enterprise.html
```

Acht Themenbereiche. Bereiche werden auf der Übersicht nach
`group` gebündelt (Überblick, Praxis, Sicherheit & Recht, Markt & Branchen).

## Neu generieren

```bash
python3 scripts/render.py
```

Liest `data/briefing.json` und schreibt alle Seiten neu nach `site/`. Keine
Abhängigkeiten außer der Python-Standardbibliothek.

## Historie & Zeiträume

`render.py` merged bei jedem Lauf die Items aus `briefing.json` in den
kumulativen Pool `data/history.json` (dedupliziert: identischer Titel, oder
gemeinsame Quell-URL plus ähnlicher Titel; idempotent — mehrfaches Rendern
erzeugt keine Duplikate). Vergangene Meldungen gehen beim täglichen Update
damit nicht mehr verloren.

Die Seite wird in vier Ansichten gerendert, umschaltbar über die Zeile
„Zeitraum" in der Navigation (reine Links, weiterhin kein JavaScript):

- **Heute** (`site/`) — das aktuelle Tagesbriefing, wie bisher.
- **7 / 14 / 30 Tage** (`site/7d/`, `site/14d/`, `site/30d/`) — Meldungen aus
  dem Pool im jeweiligen Zeitfenster, je Topic neu nummeriert (sortiert nach
  Impact, dann Datum). Lede ist die jüngste Tages-Summary; der
  „Überspringen"-Block erscheint nur in der Heute-Ansicht.

Tests: `python3 scripts/test/test_history.py && python3 scripts/test/test_render.py`

## Inhalt bearbeiten

Alles steckt in `data/briefing.json`:

- `meta` — Titel, Untertitel, Zeitraum (`period`), Intro, Disclaimer.
- `topics[]` — die vier Bereiche. Je Bereich:
  - `summary` — Lede-Satz (erscheint auch auf der Übersicht).
  - `angle` — der Blickwinkel, aus dem der Impact bewertet wird.
  - `items[]` — Meldungen, je mit:
    - `n` (Nummer, fortlaufend ab 1, = Punkt im Radar)
    - `title`, `date`, `summary`
    - `category` — eine von: `modelle`, `tools`, `agents`, `lokal`, `security`, `business`
    - `impact` — 2–5 (1 = Routine gehört unter „Überspringen")
    - `sources[]` — `{ "label": "...", "url": "..." }` (beliebig viele)
  - `skip[]` — Themen ohne eigenen Eintrag, je `{ "reason": "...", "text": "..." }`.

Impact-Skala: 2 Nennenswert · 3 Relevant · 4 Stark · 5 Game-Changer.

## Tägliche Aktualisierung

**Aktiver Weg (ohne zusätzlichen Recherche-API-Key):** Ein Hermes-Cronjob
(`ai-briefing-daily`, täglich um 08:00 Uhr Europe/Berlin) recherchiert die Meldungen
der letzten 24 Stunden mit den Hermes-Web-Tools. Er aktualisiert ausschließlich
`data/briefing.json`, führt anschließend `scripts/render.py` aus und pusht die dadurch
aktualisierten Daten und statischen Seiten auf `main`.

`scripts/update.py` ist nur ein optionaler Standalone-Weg und wird von der Hermes-Routine
nicht verwendet.

## Veröffentlichung

Der Workflow `.github/workflows/pages.yml` veröffentlicht bei Änderungen unter `site/`
die statische Seite über GitHub Pages. Lokal genügt das Öffnen von `site/index.html` im
Browser.
