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
│   ├── history.json        ← Pool der letzten 35 Tage (Ingest/Dedup je Render)
│   └── archive/            ← ausrotierte Monate (history-JJJJ-MM.json)
├── scripts/
│   ├── history.py          ← Pool: Ingest/Dedup, Rotation, Zeitraum-Filter
│   ├── render.py           ← Generator: merged briefing.json in den Pool → schreibt site/
│   ├── update.py           ← optionaler Standalone-Weg zur Recherche (siehe unten)
│   └── test/               ← Unit-Tests (nur Standardbibliothek)
└── site/                   ← generierte statische Seiten (kein JavaScript)
    ├── 7d/ · 14d/ · 30d/   ← Zeitraum-Ansichten (letzte 7/14/30 Tage)
    ├── style.css           ← gemeinsames Stylesheet aller Seiten
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

Liest `data/briefing.json` und schreibt alle Seiten sowie `site/style.css` neu
nach `site/`. Keine Abhängigkeiten außer der Python-Standardbibliothek.

`AI_BRIEFING_ROOT=/pfad` biegt Datenquelle und Ausgabe auf ein anderes
Verzeichnis um. `update.py --dry-run` nutzt das für einen Probelauf in einem
Temp-Verzeichnis, ohne `data/` und `site/` anzufassen.

## Historie & Zeiträume

`render.py` merged bei jedem Lauf die Items aus `briefing.json` in den
kumulativen Pool `data/history.json` (dedupliziert: identischer Titel, oder
gemeinsame Quell-URL plus ähnlicher Titel; idempotent — mehrfaches Rendern
erzeugt keine Duplikate). Vergangene Meldungen gehen beim täglichen Update
damit nicht mehr verloren.

Meldungen, die älter als 35 Tage sind, wandern beim Render aus dem Pool in
Monatsdateien unter `data/archive/` (`history.KEEP_DAYS`). Die größte Ansicht
reicht 30 Tage zurück, ältere Einträge werden also von keiner Seite mehr
gelesen; ohne die Rotation würde der Pool bei jedem Lauf komplett neu
geschrieben und immer weiter wachsen.

Die Seite wird in vier Ansichten gerendert, umschaltbar über die Zeile
„Zeitraum" in der Navigation (reine Links, weiterhin kein JavaScript):

- **Heute** (`site/`) — das aktuelle Tagesbriefing, wie bisher.
- **7 / 14 / 30 Tage** (`site/7d/`, `site/14d/`, `site/30d/`) — Meldungen aus
  dem Pool im jeweiligen Zeitfenster, je Topic neu nummeriert (sortiert nach
  Impact, dann Datum). Lede ist die jüngste Tages-Summary; der
  „Überspringen"-Block erscheint nur in der Heute-Ansicht.

Tests:

```bash
python3 -m unittest discover -s scripts/test -t scripts/test
```

Sie laufen zusätzlich bei jedem Push über `.github/workflows/tests.yml`.

## Inhalt bearbeiten

Alles steckt in `data/briefing.json`:

- `meta` — Titel, Untertitel, Zeitraum (`period`), Intro, Disclaimer.
- `topics[]` — die acht Bereiche. Je Bereich:
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
nicht verwendet. Er recherchiert die Bereiche parallel (`MAX_PARALLEL`, Default 4), gibt
jedem Bereich drei Versuche und erzwingt das Antwortformat über Structured Outputs; der
letzte Versuch fällt bewusst auf freien Text zurück. Ein Bereich, der alle Versuche
verbraucht, behält seinen vorherigen Stand. Exit-Code 1 gibt es nur, wenn kein einziger
Bereich aktualisiert werden konnte.

### Wenn ein Bereich nicht aktualisiert wird

`meta.generated` ist das Datum des Laufs, nicht das Datum der Daten. Fällt die Recherche
für einen Bereich aus, bleiben dessen alte Meldungen stehen, und ohne weitere Angabe
sähe die Seite trotzdem tagesaktuell aus.

`render.py` vergleicht deshalb je Bereich einen Fingerprint des Inhalts (Titel, Datum,
Impact, Kategorie der Meldungen) mit dem Stand des letzten Laufs und merkt sich in
`data/history.json` unter `fingerprints`, seit wann der Inhalt unverändert ist. Weichen
dieses Datum und `meta.generated` voneinander ab, erscheint der Bereich auf der
Übersichtskarte und auf seiner Detailseite als unverändert, mit Datum und Anzahl der Tage.

Der Weg über den Inhalt statt über ein Feld in `briefing.json` ist Absicht: die tägliche
Aktualisierung läuft außerhalb dieses Repos und müsste ein solches Feld sonst selbst
pflegen. Der Hinweis unterscheidet nicht zwischen „Recherche fehlgeschlagen" und „es gab
nichts Neues" — beides steht als Möglichkeit im Text, denn von außen ist das nicht
unterscheidbar.

## Veröffentlichung

Der Workflow `.github/workflows/pages.yml` veröffentlicht bei Änderungen unter `site/`
die statische Seite über GitHub Pages. Lokal genügt das Öffnen von `site/index.html` im
Browser.
