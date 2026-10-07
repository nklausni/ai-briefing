# Redaktioneller Abdeckungsvertrag

Gilt für neue Runs mit `manifest.schema_version=2`. Vergangene Runs bleiben im
alten Format prüfbar. Implementierung: `editorial_coverage.py`; Pflichtprüfungen
je Quelle: `REQUIRED_SOURCE_CHECKS` in `validate_research_audit.py`.

## Recherche: eine Entwicklung je Kandidat

Zerlege Sammelartikel in eigenständige Entwicklungen, jeweils mit eigener Aussage
und Originalstelle. Dieselbe URL darf mehrere Kandidaten belegen. Eine API-Freigabe,
eine neue Anmeldung und ein Security-Produkt sind drei Kandidaten, auch beim selben
DevDay. Ein ergänzendes CLI-Plugin ist eine Integration, keine Ersatzmeldung für
die Veröffentlichung der API.

Zusätzlich zum bisherigen Belegschema braucht jeder Kandidat:

```json
{
  "title": "OpenAI startet Decisions API als öffentliche Beta",
  "development": "Die Decisions API wird nach der begrenzten Preview öffentlich als Beta verfügbar.",
  "change_type": "public_beta",
  "headline_terms": ["Decisions API"]
}
```

`development` beschreibt genau eine Änderung, 10–800 Zeichen. `headline_terms`
enthält 1–4 konkrete Produkt-/Funktionsnamen, je 2–100 Zeichen, die im Kandidatentitel
und in der späteren Meldungsüberschrift stehen müssen. Verwende spezifische Namen
wie „Decisions API“, nicht allgemeine Wörter wie „OpenAI“ oder „KI“ als Ersatz.
Ein Titel mit „Alpha-Plugin“ als Hauptaussage ist für die API-Freigabe unpassend.

`change_type`: `announcement`, `preview`, `public_beta`, `general_availability`,
`update`, `integration`, `research`, `security`, `policy`, `business` oder `other`.
Bestätige den Entwicklungsschritt am Original. Ankündigung, Preview, öffentliche
Beta und GA sind eigenständige Meilensteine; eine frühere Produktnennung deckt eine
neue Freigabe nicht ab. Routineänderungen dürfen sachlich zurückgestellt werden.

## Schlussredaktion: ausdrückliche Zuordnung

Jede neue Meldung in `data/briefing.json` ergänzt das bestehende Schema um:

```json
{
  "title": "OpenAI startet Decisions API als öffentliche Beta",
  "change_type": "public_beta",
  "candidate_ids": ["ID_DES_API_KANDIDATEN"]
}
```

Alle `selected`-Kandidaten müssen genau einer Meldung zugeordnet sein. Mehrere
Kandidaten dürfen dieselbe Meldung belegen, wenn sie dieselbe Entwicklung und
denselben Meilenstein beschreiben. Prüfe dabei sämtliche Namen und Aussagen.
Unterschiedliche Entwicklungen erhalten getrennte Meldungen. Jede zugeordnete
Original-URL muss in genau dieser Meldung stehen; ihre anderen Quellen müssen aus
den Belegen der zugeordneten Kandidaten stammen. Titel und Impact werden nach der
Hauptentwicklung gewählt, nicht nach einem beiläufigen Plugin oder Blogkommentar.

`check-editor` prüft Zuordnung, Überschriftenanker, Entwicklungsschritt und Belege.
Es schreibt `editor-coverage.json` als technische Abnahme. Das ersetzt keine
semantische Gegenprüfung: Belege, neue Informationen und die Gewichtung bleiben
Verantwortung der Schlussredaktion.

## Duplikate: konkrete veröffentlichte Entwicklung

Jede `duplicate`-Entscheidung braucht zusätzlich zu `id`, `decision` und `reason`
genau ein konkretes Ziel:

```json
{"duplicate_of": {"candidate_id": "AUSGEWAEHLTER_KANDIDAT"}}
```

oder:

```json
{"duplicate_of": {"history_id": "h-ID_AUS_EDITOR_CONTEXT_HISTORY"}}
```

Das Kandidatenziel muss selbst `selected` und tatsächlich zugeordnet sein.
Die Historien-ID stammt aus `editor_context.py history/candidate`; deren Daten sind
im `history-before.json` eingefroren. Gemeinsame Quell-URL, Unternehmen oder
Sammelartikel sind keine ausreichende Begründung. `reason` nennt die bereits
veröffentlichte Entwicklung und warum keine neue Information vorliegt.

Bei alten Historieneinträgen ohne `change_type` prüfe den damaligen Meilenstein
an Zusammenfassung/Original und ergänze die Entscheidung um `covered_change_type`.
Beispiel: `"covered_change_type": "preview"`. Weicht er vom neuen Kandidaten ab,
ist die neue Meldung kein Duplikat. Falls der alte Inhalt nicht sicher feststeht,
verwende eine sachlich begründete andere Entscheidung statt einer Vermutung.

Die Historie erhält `change_type` und bewahrt unterschiedliche Freigabeschritte
mit ihren Originaldaten. Bestehende Einträge werden nicht rückwirkend klassifiziert.
