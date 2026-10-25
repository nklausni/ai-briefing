# Ausgeführte Recherche statt Selbstauskunft

Für **neue** Runs ab 25.10.2026 setzt `prepare` `integrity_version: 1`.
Historische Manifeste und gültige Originalcaches bleiben unverändert lesbar.
Die Regel gilt in `record`, Vollständigkeitsprüfung, `assemble`, `check-editor`
und damit auch `verify-publication` – nicht nur als Prompt.

## Suche ausführen

```sh
/opt/hermes/.venv/bin/python ROOT/scripts/research_integrity.py --run-dir RUN --task ID --query 'EXAKTE SUCHE'
```

ROOT/RUN/ID ersetzen. Der Helfer reserviert die Suche, wenn sie noch nicht
reserviert ist, führt `tools.web_tools.web_search_tool` wirklich aus und bindet
unveränderte Rohantwort, Query, Task, Treffer-URLs, Zeit und SHA-256 in einem
unveränderlichen Receipt. Bestehende unbenutzte Reservierungen dürfen damit
**einmal** ausgeführt werden; das Budget wird nicht zurückgesetzt. Eine vorhandene
Antwort wird wiederverwendet. Attempt ohne Receipt = unterbrochen/unbestätigt,
keine erfolgreiche Suche. `success: false` bleibt fehlgeschlagen, auch wenn ein
Modell seinen eigenen Status auf erfolgreich setzen wollte. Kein Providerwechsel
oder Umgehen von Freigaben: Der reguläre Runtime-Helfer verwendet nur seinen
bereits konfigurierten, begrenzten Ersatzweg. Aufruf weiter normal prüfen lassen.

Jedes Quellenobjekt braucht `search_receipts: ["ABSOLUTER_RECEIPT_PFAD"]` mit einer
wirklich ausgeführten, auf diese Domain gerichteten Suche. Discovery benötigt
zusätzlich `topic_searches: {"EXAKTES THEMA": ["RECEIPT"]}` für alle acht Themen
und mindestens acht unterschiedliche Suchbelege. Ein leerer erfolgreicher
Suchlauf ist zulässig, aber **kein** Nachweis, dass keine Nachrichten existieren.
Fehlender Suchzugang/Budget-/Agentenabbruch bleibt pending, kein Quellenausfall.

## Originalabrufe binden

Caches müssen die wirklich abgerufene `url`, `retrieved_at`, `text` sowie etwaige
Fehler erhalten. Nach Kontrolle von Identität, Titel, Originaldatum und Aussagen:

```sh
/opt/hermes/.venv/bin/python ROOT/scripts/research_integrity.py --run-dir RUN --cache CACHE.json --url 'EXAKTE ORIGINAL-URL' --output RECEIPT.json
```

Ein Receipt bindet nur vorhandene Bytes; es darf keine erfundene Textstelle
beglaubigen. Quellenobjekte erhalten `source_receipts` (mindestens die exakte
`checked_url`); jeder Kandidatenbeleg erhält `receipt`. `excerpt` muss eine
wirkliche, zusammenhängende Originalstelle sein (nur Leerraum normalisiert),
keine Paraphrase in Anführungszeichen. Historisch gültige Caches sind wiederverwendbar,
aber mit unverändertem Abrufdatum und ausdrücklich ausgewiesener Herkunft.
Ein aktueller fehlgeschlagener Abruf löscht keinen älteren tatsächlich gelesenen
Beleg und darf selbst nicht als erfolgreich bezeichnet werden.

arXiv-Kandidaten benötigen zusätzlich `original_title` aus der wirklich gelesenen
Paperseite; Titel und URL müssen zusammenpassen. Im arXiv-Checkpoint verweist
`title_discovery_files` auf die drei unveränderten Helferberichte. Die kompakten
`title_discovery`-Objekte müssen **exakt** diesen Originalen ohne `titles`
entsprechen, einschließlich aller Query-/Seiten-URLs. Einen maskierten,
verkürzten oder fremden Paperlink nicht reparieren, indem man ihn als Original
ausgibt. Korrigierte Eingaben gehören in einen autorisierten neuen Recovery-Run,
während der verworfene Checkpoint erhalten bleibt.

## Abnahme und Recovery

Vorhandene Dateien sind allein kein Abschlussbeleg mehr: die Vollständigkeits-
prüfung validiert Receipts erneut. Ein als `integrity-rejection.json` gesperrter
Run darf nicht assembliert/veröffentlicht werden. Bei einer echten Zurückweisung
Originale, Errata, Worker-Tooltraces und Budgets erhalten; nur in einem ausdrücklich
autorisierten neuen Run korrigierte Recherche und validierte Carry-overs nutzen.
Nicht dieselbe unveränderliche Datei überschreiben und nicht alles blind neu suchen.

Grenze: Hashes und Strukturprüfungen verhindern versehentliche unbelegte
Selbstauskünfte und Identitätsfehler. Sie sind keine Garantie gegen einen
böswilligen Schreiber mit Dateisystemzugriff und ersetzen keine semantische
Schlussredaktion oder die Kontrolle von Suchfilter-/Indexlücken.
