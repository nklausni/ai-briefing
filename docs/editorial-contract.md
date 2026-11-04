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

### Öffentlicher Einstieg: Inhalte statt Ausführungsprotokoll

`meta.intro` fasst in ein bis drei kurzen Sätzen konkrete Themen der belegten
Meldungen dieser Ausgabe zusammen. Keine neuen Fakten aus der Zusammenfassung
ableiten. Fehlt ein sinnvoller inhaltlicher Einstieg, Feld weglassen oder leer lassen.
Dies gilt auch für die Themen-`summary`: Nachrichten und relevante Einschränkungen,
nicht den Redaktionsablauf beschreiben.

Keine System-/Redaktionsstatusmeldungen im öffentlichen Intro: weder „bisherige
Ausgabe bleibt erhalten“, „nachgeholte Entwicklungen“ oder „ergänzter Tagesstand“
noch Verweise auf „Tagesaudit“, Quellenlücken, Abrufversuche oder abgeschlossene
Prüfschritte. Solche Betriebsdetails gehören ins Audit bzw. Laufprotokoll.
Der Renderer blockiert bekannte Prozessformulierungen in `meta.intro` vor dem
Schreiben; die semantische Schlussprüfung bleibt erforderlich. Sachliche
Quellenvorbehalte, Originaldaten und Unterschiede zwischen Preview, Beta und GA
an einzelnen Meldungen bleiben erhalten. Historische Audits nicht umschreiben.

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

### Verkürzte historische Überschriften

Neue Meldungen und Kandidaten-Duplikatziele behalten die vollständige
Überschriftenpflicht. Nur bei einem konkreten `history_id` darf eine verkürzte
Altmeldungsüberschrift durch einen ausdrücklichen Beleg ergänzt werden:

```json
{"history_coverage": {
  "summary_quote": "Anthropic erweitert die GSA-Vereinbarung auf 40 Prozent Rabatt für Claude Enterprise, Claude for Government und die Claude API.[17]",
  "development_terms": ["GSA-Vereinbarung", "40 Prozent Rabatt"]
}}
```

Das ist keine pauschale Text- oder URL-Ähnlichkeitsfreigabe. Der Validator verlangt:

- exakte Kandidaten-Original-URL in den Quellen des eingefrorenen Historienziels
  (oder den unten beschriebenen engen, abrufgebundenen Syndikationsbeleg);
- identisches Originaldatum (`published_at`/`date`) und denselben geprüften
  `change_type`; Preview, Beta und GA bleiben getrennt;
- einen vollständigen, unveränderten Satz aus dessen `summary`, der **alle**
  Produktanker gemeinsam enthält; getrennte Produktlisten reichen nicht;
- zwei bis vier konkrete mehrwortige Entwicklungsphrasen, die wortgetreu nach
  Leerraum-/Interpunktionsnormalisierung sowohl in diesem Satz als auch in
  `development`/`summary` des Kandidaten stehen. Sie müssen zusammen mindestens
  fünf unterschiedliche Wörter **außerhalb** der Produktanker belegen.

Die Redaktion prüft weiter, dass diese Phrasen die tatsächliche Änderung und
nicht nur allgemeine Firmen-/Produktnennungen bezeichnen. Lässt sich der enge
Nachweis nicht führen, bleibt die Entscheidung zur konkreten Nachprüfung gesperrt;
keine Umdeklaration zum Umgehen des Gates. Originalentscheidungen und Fehlerbeleg
vor einer autorisierten Ergänzung sichern. Historie, Quellen-Checkpoints und
Suchbudgets bleiben unverändert. Das Belegobjekt gehört nur zur aktuellen
Redaktionsentscheidung, nicht in historische Daten.

### Identische Publisher-Originale und PRNewswire-Syndikation

Nur für `announcement` darf `history_coverage.source_identity` die Original-URL
mit einer bereits historisch zitierten PRNewswire-Syndikation verbinden. Das ist
kein allgemeiner URL-Alias und keine Freigabe für Preview, Beta oder GA:

- `kind: publisher_syndication`, `publisher` und `publisher_domain` binden den
  HTTPS-Originalhost; die Syndikation muss auf `www.prnewswire.com` liegen und
  im gelesenen Text ausdrücklich `SOURCE <publisher>` nennen.
- `original` und `syndicated` enthalten jeweils die **exakte** Ziel-URL, ein gültiges
  unverändertes Retrieval-`receipt`, `excerpt` und `date_quote`. Receipts werden
  einschließlich Cachehash und tatsächlicher Textstelle erneut validiert.
- `release_title` muss in beiden Originaltexten stehen; beide tatsächlichen
  `date_quote`-Textstellen müssen zum unveränderten Kandidaten-/Historientag passen
  (ISO-Datum oder ausgeschriebener englischer Monat).
- Die `excerpt`-Passage muss in beiden Texten wortgleich vorkommen (nur Leerraum
  normalisiert), mindestens 40 Wörter und sämtliche Kandidaten-Produktanker enthalten.
- `stage_quote` muss in beiden Texten stehen, den Produktanker und die ausdrückliche
  Zukunftsverfügbarkeit `will be available` enthalten; `change_type` bleibt
  `announcement`. Die Redaktion prüft den konkreten Fahrplan am Original.
- Fehlt der volle Produktanker auch im unveränderten historischen Zusammenfassungssatz,
  müssen konkrete mehrwortige `development_subjects` in genau diesem Satz, im
  Kandidaten und in der gemeinsamen Originalpassage stehen (z.B. `AI Discovery`).
  Alle bisherigen `development_terms`-Prüfungen bleiben zusätzlich aktiv: gemeinsamer
  Mechanismus, mindestens fünf verschiedene Wörter jenseits der Produktanker,
  ein vollständiger unveränderter Historien-Satz. Produktlisten allein reichen nicht.

Alte Entscheidungen werden vor Ergänzung unverändert gesichert. Historie, Kandidaten,
Quellenbelege und Budgets werden nicht umgeschrieben; vorhandene echte Receipts
werden mit ursprünglichem Abrufdatum verwendet. Ohne diesen eng geführten Beleg
bleibt die bisherige exakte URL-/Überschriftenregel bestehen.

Die Historie erhält `change_type` und bewahrt unterschiedliche Freigabeschritte
mit ihren Originaldaten. Bestehende Einträge werden nicht rückwirkend klassifiziert.

## Nicht veröffentlicht: audited `deferred` statt Gesamtblockade

`deferred` ist ausdrücklich **weder** verifiziertes Duplikat **noch** ein Qualitätsurteil,
`unverified`, `below_threshold` oder ein neuer veröffentlichter Inhalt. Jeder Kandidat
bleibt mit genau einer Entscheidung erfasst. Ein Hold zählt nur zur administrativen
Entscheidungsabrechnung, nie zu `mapped`, verifizierten Duplikaten, vollständiger
inhaltlicher Kandidaten-/Quellenabdeckung oder einem fortgeschriebenen Wasserzeichen.
Keine geringe Meldungszahl oder Holds als Beleg eines ruhigen Nachrichtentages verwenden.

Der verbindliche normale Schritt `research_pipeline.py finalize-editor --run-dir RUN`
führt zuerst das unveränderte `assemble` einschließlich aller Quellen-, Receipt-,
Budget-, Cache-, arXiv- und Frischeprüfungen aus. Danach isoliert er ausschließlich
bereits **nicht ausgewählte** historische Duplikatvorschläge mit reproduziertem
Klassifikations- oder Überschriftenankerfehler. Voraussetzungen:

- konkretes existierendes eingefrorenes `history_id`, identisches Originaldatum;
- gleiche Source-URL (nur Query-Unterschiede sind zur HOLD-Identifikation zulässig,
  niemals als Freigabe der strengeren Duplikat-/URL-Regeln);
- sämtliche konkreten Kandidaten-Produktanker in unveränderter historischer
  Überschrift/Zusammenfassung; keine bloße Firmen- oder Produktähnlichkeit;
- weder Kandidat noch Historie noch vorgeschlagener historischer Schritt ist
  Preview, öffentliche Beta oder GA. Diese Meilensteine bleiben blockierend;
- genau der tatsächliche lokale `change_type`-/Headlinefehler ist erneut nachweisbar.
  Receipt-/Cache-/Syndikationsbelege werden außerhalb der Fehlerisolation validiert.
  Andere Fehler, unbekannte Ziele, falsche Daten oder Quellen bleiben fatal.

Maximal fünf Holds pro Ausgabe; mindestens eine regulär ausgewählte, vollständig
validierte Meldung. Auch ein direktes `check-editor` erzwingt diese Grenzen und
reproduziert jeden Hold aus unverändertem Kandidaten und Originalvorschlag. Ein
Hold kann nicht in `candidate_ids` einer Meldung, als Kandidaten-Duplikatziel oder
als historischer Inhalt erscheinen. Sämtliche Regeln für ausgewählte Inhalte,
Quellenqualität, Originaldatum, Approval und Belege bleiben unverändert.

Der Helfer sichert `editor-proposals-SHA.json`, schreibt `editor-quarantine.json`
und bewahrt je Hold Originalvorschlag, tatsächlichen Validatorfehler, Kandidatenhash,
Original-URL und Originaldatum im `quarantine`-Objekt der Entscheidung. Erst eine
vollständig erfolgreiche Schlussprüfung schreibt die neuen Entscheidungen; keine
verdeckte Umklassifizierung. Historie und Recherchebelege werden nicht repariert.

Die persistente lokale `RUN/../editor-review-queue.json` ist nach Source-Pfad,
Originaldatum und eingefrorenem historischem Ereignis geschlüsselt, nicht nach dem
heutigen Datum oder umformuliertem Kandidatentext. Wiederholung ist idempotent.
`research_pipeline.py review-queue --run-dir RUN` zeigt höchstens fünf offene Holds
für die vorhandene tägliche Schlussredaktion. Nur tatsächlich neue bereits vorhandene
Belege können eine erneute Entscheidung begründen; sonst Hold und ursprüngliches
Datum erhalten. Keine Zusatz-LLM-Cronjobs, Suchbudgetresets oder automatische
Neuveröffentlichung. Eine alte offene Warteschlange blockiert spätere Ausgaben nicht
und wird nicht als neue Recherche injiziert. Eine spätere korrigierte Entscheidung
braucht wiederum alle regulären Gates und einen eigenen auditierten Vorschlag.
