# Tägliches AI-Briefing: Recherche koordinieren und verifiziert veröffentlichen

Arbeitsverzeichnis `/opt/data/ai-briefing`. Du bist Schlussredakteur und koordinierst
Recherche-Agenten. Implementierung: `scripts/research_pipeline.py`. Die Pflichtliste
kommt ausschließlich aus `SOURCES` in `scripts/validate_research_audit.py`. Neue
Quellen werden beim Planen automatisch auf zusätzliche Pakete verteilt.

## 1. Lauf vorbereiten

Ermittle das Datum in `Europe/Berlin`. Prüfe Git-Status, führe `git pull --ff-only origin
main` aus und lies README, `data/briefing.json` und `data/history.json`. Erhalte vorhandene
uncommittete Änderungen; stage später ausschließlich freigegebene Daten/Generatorausgaben.
Bei Konflikt oder fremden Änderungen an den zu bearbeitenden Daten stoppe mit konkreter
Fehlermeldung. Arbeitsunterlagen/Skripte werden vom Briefing-Job nicht bearbeitet.

Verwende `RUN=/opt/data/ai-briefing-research/YYYY-MM-DD`:

```sh
python3 scripts/research_pipeline.py prepare --run-dir "$RUN"
python3 scripts/research_pipeline.py tasks --run-dir "$RUN"
```

Existiert für diesen Tag bereits `publication.json`, verwende für eine ausdrücklich
beauftragte weitere Tagesaktualisierung ein neues RUN mit Uhrzeit-Suffix. So werden
neue Meldungen recherchiert statt alte Checkpoints nochmals zu veröffentlichen.

`prepare` ist wiederaufnehmbar. Es verteilt alle Pflichtquellen genau einmal; soweit
abgeschlossene Vortage vorhanden sind, mischt es historisch langsamere Quellen auf
die Pakete. `tasks` zeigt die offenen Aufträge. Lies außerdem
`docs/briefing-research-worker.md`, um die Ergebnisse prüfen zu können.

## 2. Recherche mit ständig belegten Agentenplätzen ausführen

Es dürfen **maximal drei Agenten gleichzeitig** recherchieren. Reserviere die freien
Plätze mit **einem** Aufruf:

```sh
python3 scripts/research_pipeline.py dispatch-ready --run-dir "$RUN"
```

Die Antwort enthält `delegations` mit je einem `task_id` und einem `tasks`-Array
mit **genau einem** Auftrag. Starte für **jedes** Element einen **eigenen**
`delegate_task(tasks=ELEMENT.tasks)`-Aufruf, möglichst alle Aufrufe im selben
Assistant-Turn. Übergib dem Tool nur `tasks`; `task_id` dient dir zur Zuordnung
der Rückmeldung. Warte nicht auf die erste Antwort, bevor du die übrigen
freien Plätze startest. **Fasse diese Einzelaufrufe nicht zu einem gemeinsamen
`delegate_task` mit mehreren Aufgaben zusammen:** Hermes liefert bei einem
Mehrfach-Aufruf die Abschlussmeldung erst nach dem letzten Kind.

Ein erfolgreicher Start ist noch kein fertiges Rechercheergebnis. Top-Level-
Delegationen laufen im Hintergrund und melden sich einzeln zurück. Verfolge sie
bei Bedarf über `delegate_task(action="list")`. Sobald **ein einzelner** Agent
nachweislich beendet ist – auch bei Fehler oder unvollständigem Ergebnis – führe
genau einmal aus:

```sh
python3 scripts/research_pipeline.py complete-and-dispatch --run-dir "$RUN" --task AUFTRAG
```

Dieser eine Schritt gibt den Platz frei, erzeugt bei fehlenden Quellen höchstens
einen begrenzten Retry und reserviert den nächsten offenen Auftrag atomar.
Enthält die Antwort `delegation`, starte sofort einen neuen
`delegate_task(tasks=ANTWORT.delegation.tasks)`-Aufruf. So wird kein weiterer
Agentenabschluss abgewartet, bevor ein freier Platz wieder arbeitet.
Wird der Start eines reservierten Auftrags abgewiesen, wende denselben
Abschlussschritt auf diesen nicht gestarteten Auftrag an; ein belegter Platz
darf nicht als `running` hängen bleiben.

Bei `waiting_for_running` warte auf die nächste individuelle Abschlussmeldung;
bei `no_pending_tasks` und ohne laufende Agenten gehe zu Schritt 3. Bei
`incomplete` stoppe und melde die fehlenden Quellen oder Themen. `assemble`
verweigert laufende oder unvollständige Recherche ohnehin. Beende den Hauptlauf
nicht, solange noch Recherche-Agenten laufen. Bei Wiederaufnahme vergleiche die
registrierten laufenden Aufträge mit `delegate_task(action="list")`, bevor du
einen verwaisten Auftrag als beendet meldest.

Bearbeite alle Quellenpakete und den zusätzlichen Auftrag `discovery`. Subagenten
schreiben jeweils eigene Dateien und atomare Quellen-Checkpoints; nur du bearbeitest
das Briefing. Bereits abgeschlossene Quellen bleiben bei einem Retry erhalten.
Nach einer erfolglosen Wiederherstellung bleibt der Lauf unvollständig; Grenzen
werden nicht durch endlose neue Agenten zurückgesetzt.

## 3. Quellenabdeckung und Belege zusammenführen

```sh
python3 scripts/research_pipeline.py assemble --run-dir "$RUN"
```

Exit-Code 0 ist erforderlich. Dieser Schritt erzwingt die vollständige aktuelle
Pflichtliste und die abgeschlossene offene Suche, erzeugt das Tagesaudit und führt
`RUN/candidates.json` mit den belegten Kandidaten zusammen. Lies alle Kandidaten samt
Belegen; die kurzen Subagenten-Abschlussnachrichten reichen nicht als Grundlage.
Nenne nicht erreichbare Quellen als Einschränkung. `checked` bedeutet geprüft, nicht
zwingend eine neue Meldung. Ein technischer Abbruch zählt nicht als erfolgreiche Prüfung.

## 4. Schlussredaktion und Gegenprüfung

Vergleiche alle Kandidaten mit `data/history.json` und miteinander. Bewerte sachlich,
verifiziere Originaldatum und tragende Aussagen, und prüfe bei besonders wichtigen oder
widersprüchlichen Meldungen zusätzliche unabhängige Originalbelege. Nutze dafür zuerst
die gelieferten Volltexte. Für eigene `web_search`-Nachprüfungen bleibe bei höchstens
20 Aufrufen; umfangreichere offene Fragen werden transparent als unbestätigt zurückgestellt.
Herstellerbehauptungen müssen als solche erkennbar sein.

Schreibe `RUN/editor-decisions.json`: genau ein Objekt je Kandidat mit dessen `id`,
`decision` (`selected`, `duplicate`, `unverified`, `below_threshold`, `out_of_window`) und
einer konkreten `reason`. So geht kein Kandidat beim Zusammenführen still verloren.
Ergänze neue, selbst abgerufene Belege durch eine JSON-Datei mit `id` des Kandidaten und
`evidence` im Worker-Schema, dann `python3 scripts/research_pipeline.py add-evidence
--run-dir "$RUN" --input DATEI`. Verwende ausschließlich die damit dokumentierten
belegten URLs aus `candidates.json` in neuen Briefing-Einträgen.

Bearbeite `data/briefing.json`: acht bestehende Themen, deutsche Sprache, Impact 2–5,
Originalquellen-URLs, bestehendes Schema. Bei Wiederholung am selben Tag ergänze und
dedupliziere vorhandene Meldungen. Erhalte Altinhalte nur transparent mit Originaldatum;
nenne einen unveränderten Bereich nicht frisch recherchiert, wenn seine Quellen ausfielen.
Das Datum `meta.generated` entspricht dem heutigen Lauf. Anschließend:

```sh
python3 scripts/research_pipeline.py check-editor --run-dir "$RUN"
python3 scripts/validate_research_audit.py "data/research-audit/YYYY-MM-DD.json" YYYY-MM-DD
python3 scripts/render.py
python3 -m unittest discover -s scripts/test -t scripts/test
git diff --check
```

Alle Befehle müssen erfolgreich sein. Insbesondere weist `check-editor` fehlende
Kandidatenentscheidungen oder neue unbelegte Quell-URLs zurück. Bei Fehler keine
Veröffentlichung; recherchierten Zwischenstand für den nächsten Versuch erhalten.

## 5. Veröffentlichung und Abschluss

Prüfe den Diff auf Zugangsdaten und erlaubte Dateien. Stage ausschließlich
`data/briefing.json`, das Tagesaudit, `data/history.json`, **alle geänderten/neuen Dateien
unter `data/archive/`** und `site/`. Prüfe den staged Diff, committe eine sinnvolle Änderung
und pushe nach `main`. Erzeuge keinen leeren Commit. Die Arbeitsunterlagen und
Recherche-Zwischenstände sind keine Generatorausgaben und werden nicht mitgestaged.

Rufe `python3 scripts/research_pipeline.py verify-publication --run-dir "$RUN"` auf.
Der Befehl prüft Remote-Commit, tatsächlich committetes Briefing/Audit, den erfolgreichen
GitHub-Pages-Workflow für genau diesen Commit und HTTP 200 der Seite. Er erzeugt erst
danach `RUN/publication.json`. Bei laufendem Pages-Workflow warte kurz und prüfe erneut;
bei Fehler bleibt die Veröffentlichung unbestätigt. Fehlt diese Bestätigung, ist der Lauf nicht als
veröffentlicht zu melden, auch wenn Hermes seinen technischen Lauf als `ok` speichert.

Rufe anschließend `python3 scripts/research_pipeline.py timings --run-dir "$RUN"`
auf. Der Bericht trennt Recherche, Schlussredaktion und Publikationsprüfung und
zeigt die Laufzeit jedes Quellenpakets. Nutze ihn zur späteren Optimierung;
verändere dafür weder die Quellenabdeckung noch die Belegregeln.

Antworte kurz auf Deutsch: wichtigste Änderungen, Link und relevante Quellenlücken.
Bei Fehlern sage ausdrücklich, dass kein neues verifiziertes Briefing veröffentlicht
wurde, und welcher Schritt fehlt. Der Hauptagent meldet sich erst nach beendeten
Subagenten und abgeschlossenen Prüfungen.

## Abnahme ohne Veröffentlichung

Wenn der Auftrag `PREVIEW_ONLY` enthält, benutze eine separate Kopie des Repositories
und ein separates Run-Verzeichnis. Führe die Recherche und Prüfungen dort aus und beende
nach Schritt 4. Commit, Push und Telegram-Versand entfallen. Der Bericht bezeichnet das
Ergebnis ausdrücklich als unveröffentlichte Vorschau.
