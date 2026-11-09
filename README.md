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

## Zeitungsgestaltung

Die Oberfläche nutzt einen gemeinsamen Zeitungskopf, warme Papierfarben, lokale
Systemschriften (Georgia/Serif und System-Sans) und ein responsives Spaltenlayout.
Der Aufmacher folgt dem vorhandenen Impact, dann dem Originaldatum und einer stabilen
Themen-/Artikelidentität. Die drei hervorgehobenen Meldungen werden in der
Themenübersicht nicht noch einmal als Teaser wiederholt; alle Artikel bleiben in den
Feld-Reports erhalten. Radarfarben, Originaldaten, Quellen und lokale Archivsuche
bleiben unverändert verfügbar. Es werden keine externen Schriftendienste geladen.

Designvertrag und Abnahmematrix: [docs/newspaper-design.md](docs/newspaper-design.md).

## Aufbau

```
AI Briefing/
├── index.html              ← Redirect auf site/index.html
├── data/
│   ├── briefing.json       ← Datenquelle des Tages (Inhalt aller Bereiche)
│   ├── history.json        ← Pool der letzten 35 Tage (Ingest/Dedup je Render)
│   ├── archive/            ← ausrotierte Monate (history-JJJJ-MM.json)
│   ├── research-audit/     ← historische Quellenprotokolle der alten Automation
│   └── n8n-audit/          ← Laufprotokolle der aktuellen Automation
├── scripts/
│   ├── history.py          ← Pool: Ingest/Dedup, Rotation, Zeitraum-Filter
│   ├── render.py           ← Generator: merged briefing.json in den Pool → schreibt site/
│   ├── search.py · search.js ← lokale Archivsuche
│   └── test/               ← Unit-Tests (nur Standardbibliothek)
└── site/                   ← generierte statische Seiten
    ├── 7d/ · 14d/ · 30d/   ← Zeitraum-Ansichten (letzte 7/14/30 Tage)
    ├── search.html · search.js · search-index.json ← lokale Volltextsuche
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
Verzeichnis um. Für einen Probelauf `data/` in ein temporäres Verzeichnis kopieren
und dieses als `AI_BRIEFING_ROOT` setzen; die Originaldaten bleiben dann unverändert.

## Historie & Zeiträume

`render.py` merged bei jedem Lauf die Items aus `briefing.json` in den
kumulativen Pool `data/history.json` (dedupliziert: identischer Titel, oder
gemeinsame Quell-URL plus ähnlicher Titel; idempotent — mehrfaches Rendern
erzeugt keine Duplikate). Vergangene Meldungen gehen beim täglichen Update
damit nicht mehr verloren.

Meldungen, die älter als 35 Tage sind, wandern beim Render aus dem Pool in
Monatsdateien unter `data/archive/` (`history.KEEP_DAYS`). Die größte Ansicht
reicht 30 Tage zurück; die Suche liest zusätzlich die vorhandenen Archive; ohne die Rotation würde der Pool bei jedem Lauf komplett neu
geschrieben und immer weiter wachsen.

Die Seite wird in vier Ansichten gerendert, umschaltbar über die Zeile
„Zeitraum" in der Navigation (reine Links, weiterhin kein JavaScript):

- **Neu** zeigt alle Meldungen, die erstmals in der letzten veröffentlichten Ausgabe ins Briefing aufgenommen wurden (`first_seen`). Am Artikel steht das ursprüngliche Veröffentlichungsdatum.
- **7, 14 und 30 Tage** umfassen heute und die jeweils 6, 13 oder 29 vorhergehenden
  Kalendertage. Eine Meldung erscheint in jedem passenden Zeitraum.

Der Renderer übergibt dieselbe Auswahl an Übersicht, Themenberichte und Radar.
Die Auswahl unter **Neu** gilt bis zur nächsten Ausgabe. Die drei Zeiträume
rücken im Browser beim Berliner Datumswechsel weiter. Ohne JavaScript gelten die auf der Seite angegebenen Daten.

Tests:

```bash
python3 -m unittest discover -s scripts/test -t scripts/test
```

Sie laufen zusätzlich bei jedem Push über `.github/workflows/tests.yml`.

## Lokale Suche

„Suche“ ist von jeder Übersicht und Themenseite erreichbar, auch aus 7/14/30 Tagen.
`render.py` erzeugt einen deterministischen JSON-Index aus aktueller Ausgabe,
`history.json` und allen vorhandenen JSON-Archiven (Monatspools sowie ältere
Briefing-Snapshots). Deduplizierung erfolgt je Thema mit der Historien-Identität;
Titel, Zusammenfassung, Thema, Originaldatum und Quellen sind durchsuchbar.
Nicht gespeicherte Meldungen und Volltexte externer Artikel werden nicht durchsucht.

Alle Suchwörter müssen vorkommen; Groß-/Kleinschreibung, Leerraum und deutsche
Umlaute (auch ae/oe/ue und ß/ss) werden angeglichen. Die Anzeige beginnt mit maximal
50 Treffern und bietet „Weitere 50 anzeigen“ samt genauer Gesamtzahl. Die Suche
läuft ausschließlich lokal im Browser, ohne Suchanbieter oder Analytics. Daten
werden als Text gerendert, Quell-Links nur mit HTTP(S) zugelassen. Ladefehler,
keine Treffer und deaktiviertes JavaScript erhalten eigene Hinweise.

Für die Suche lokal einen HTTP-Server nutzen (Browser blockieren `fetch` bei `file://`):

```bash
python3 -m http.server 8000 --directory site
node --test scripts/test/search.test.cjs
```

Übersichten, Themen und Zeitraum-Umschaltung funktionieren weiterhin ohne JavaScript.

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

Die aktive Automation liegt im privaten Repository
[ai-briefing-n8n](https://github.com/nklausni/ai-briefing-n8n): drei sichtbare n8n-
Workflows für Recherche, AI-Redaktion, Veröffentlichung und Fehlerbehandlung.
Der tägliche Start ist 08:00 Uhr Europe/Berlin, mit Wiederanlauf um 09:00 und 10:00 Uhr.
Die neue Automation ist ab 5. November 2026 aktiviert; die bisherigen Agent-Crons
sind pausiert. Manuelle n8n-Starts erzeugen nur eine lokale Vorschau.

Dieses Repository enthält ausschließlich Webseite, Renderer, Suche, Inhalte und
Historie. Die alten Agent-Prompts, Recherche-/Review-Orchestratoren, speziellen
Quellenprüfer und der alternative API-Updater wurden entfernt. Frühere Fassungen
bleiben über die Git-Historie verfügbar. Die veröffentlichten historischen
Quellenprotokolle unter `data/research-audit/` bleiben unverändert; neue technische
Laufprotokolle schreibt n8n nach `data/n8n-audit/`.

Der aktuelle Ablauf lautet: Recherche → AI-Redaktion mit Historienabgleich → kurze
Format-, Quellen- und Datumsprüfung → Renderer → Git-Push → Pages-/Live-Prüfung.
Es gibt keine zweite AI-Gegenprüfung jeder Aussage und keine verpflichtenden
Zitat- oder arXiv-Sonderaudits. Einzelne zurückgestellte Meldungen blockieren
andere Meldungen nicht. Die Softwaretests laufen bei Codeänderungen und in CI,
nicht als zusätzliche tägliche Publikationshürde.

## Versionierung und Deployment

Quelländerungen, zugehörige Tests und Dokumentation gemeinsam committen und pushen.
Die n8n-Automation versioniert veröffentlichte Inhalte, Historie und erzeugte Seiten
hier; ihre Workflows, Konfiguration und Adapter bleiben in `ai-briefing-n8n`.
Zugangsdaten, private Hermes-Laufdaten und `.hermes/` gehören nicht ins Repository.

GitHub Actions testet jeden Push. Der Pages-Workflow veröffentlicht das Verzeichnis
`site/`, wenn dessen Dateien oder der Pages-Workflow geändert werden. Reine Änderungen
an Quellcode oder Dokumentation veröffentlichen keine neue Nachrichtenausgabe.
