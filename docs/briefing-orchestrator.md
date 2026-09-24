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

Es dürfen **maximal drei Agenten gleichzeitig** recherchieren. Hole jeden freien
Platz mit `python3 scripts/research_pipeline.py dispatch-next --run-dir "$RUN"`.
Ein erfolgreicher Aufruf reserviert genau einen Auftrag und liefert dessen `task_id`,
`goal`, `context` und `output_schema`. Übergib nur die letzten drei Felder an
`delegate_task`, merke dir `task_id` für `release` und starte den Agenten sofort.
Wiederhole `dispatch-next`, bis `capacity_full`, `waiting_for_running`
oder `no_pending_tasks` zurückkommt. Der Planner priorisiert einen nötigen Retry,
startet die offene Themensuche früh und verteilt danach die Quellenpakete.

Hermes startet Top-Level-Delegationen asynchron. Verfolge die tatsächlichen
Ergebnisse über `delegate_task(action="list")` und warte auf den **nächsten
einzelnen** abgeschlossenen Agenten, nicht auf die gesamte Startgruppe. Eine
Bestätigung des Starts ist kein Ergebnis. Beende den Hauptlauf nicht, solange
noch Recherche-Agenten laufen.

Nach bestätigtem Ende jedes Subagenten führe `python3 scripts/research_pipeline.py release
--run-dir "$RUN" --task AUFTRAG` aus. Auch ein fehlgeschlagener Start wird so freigegeben.
`dispatch-next` verweigert einen vierten gleichzeitig registrierten Auftrag; `assemble`
verweigert die Zusammenführung, solange ein Auftrag als laufend registriert ist.
Bei Wiederaufnahme vergleiche registrierte laufende Aufträge mit der tatsächlichen
Hermes-Agentenliste, bevor du verwaiste Aufträge freigibst.

Bearbeite alle Quellenpakete und den zusätzlichen Auftrag `discovery`. Subagenten
schreiben jeweils eigene Dateien und atomare Quellen-Checkpoints; nur du bearbeitest das
Briefing. Arbeite keine ausgefallenen großen Pakete selbst durch: für ein beendetes
unvollständiges Paket erzeugt

`python3 scripts/research_pipeline.py retry --run-dir "$RUN" --task AUFTRAG`

genau einen Wiederherstellungsauftrag nur für noch offene Quellen. Vergewissere dich
vorher, dass der ursprüngliche Agent beendet ist. Bereits abgeschlossene Quellen bleiben
erhalten. Nach einer erfolglosen Wiederherstellung bleibt der Lauf unvollständig und wird
als solcher gemeldet. Grenzen werden nicht durch endlose neue Agenten zurückgesetzt.
Erzeuge den Retry direkt nach `release` des unvollständigen Auftrags. Rufe dann
`dispatch-next` auf, um den freien Platz sofort neu zu belegen; dieser reserviert
den Retry bevorzugt. Wiederhole das nach **jedem** Agentenabschluss, bis alle
Aufträge beendet sind. Auch `waiting_for_running` heißt: weiter auf laufende
Agenten warten. Erst bei `no_pending_tasks` und ohne laufende Agenten zu Schritt 3.

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
