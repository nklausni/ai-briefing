# arXiv: vollständige Titelentdeckung und belegte öffentliche Frische

Verbindlich für neue Läufe ab Quellenregister **5**. Audit-Schema 1 und
Manifest-Schema 2 bleiben erhalten. Alte Register, Manifeste, Kandidaten und
Tagesaudits werden nicht umgeschrieben oder mit neuen Anforderungen nachvalidiert.

## 1. Begrenzte, vollständige Entdeckung

Der zuständige Quellen-Worker führt alle drei Abrufe mit seinem tatsächlichen
Assignment-`since` und -Datum aus; nicht pauschal gestern einsetzen:

```sh
python3 ROOT/scripts/arxiv_discovery.py --since SINCE --until DAY --output WORKER/arxiv-recent.json
python3 ROOT/scripts/arxiv_discovery.py --kind changes --since SINCE --until DAY --output WORKER/arxiv-changes.json
python3 ROOT/scripts/arxiv_discovery.py --kind updates --since SINCE --until DAY --output WORKER/arxiv-updates.json
```

`ROOT`, `WORKER`, `SINCE` und `DAY` ersetzen. Kein neuer Provider und kein
Suchmaschinenaufruf: ausschließlich arXiv-eigene Listen/API. Das bestehende
35er-Suchbudget je Worker und sämtliche Browser-/Retry-Grenzen bleiben unverändert.
Je Abruf höchstens vier Seiten mit bis zu 2.000 Einträgen, 60 Sekunden insgesamt,
20 Sekunden je HTTP-Anfrage und drei Sekunden Abstand zwischen Seiten. Keine
Endlosschleife oder Budgeterhöhung bei großen Listen. Der Helfer speichert auch
Teilresultate, URLs, Abrufzeit, Quell-Gesamtzahl, deduplizierte Zählung, Tageszahlen,
Cursor/Seiten, Frischefenster und konkrete Einschränkungen. Exit 1 bedeutet
unvollständige Abdeckung, **nicht** Abbruch aller anderen Quellen.

- `recent`: alle Titel der rollierenden cs.AI-Liste einschließlich Kreuzlistungen.
  Der 19.10.2026 enthielt 174 Titel, nicht nur die ersten 50. Gesamtzahl der
  gesamten rollierenden Liste und Tageszahl sind verschiedene Nenner.
- `changes`: vollständige aktuelle Tagesliste `/list/cs.AI/new`, einschließlich
  **Replacement submissions**, mit `announce_type` aus der tatsächlichen Rubrik.
  `recent` allein deckt diese Ersetzungen nicht ab. Kreuzlistungen sind keine
  neue Erstveröffentlichung. Die Tagesliste belegt nur ihren ausgewiesenen Tag.
- `updates`: vollständig paginierte arXiv-Such-API für `lastUpdatedDate` mit
  sieben zusätzlichen Überlapptagen vor `since`. Berlin-Tagesgrenzen werden vor
  der API-Abfrage nach UTC umgerechnet; `until` ist einschließlich. Dies entdeckt
  auch substantielle neue Versionen bereits älterer Arbeiten. API-Zeitstempel
  sind **Einreichungszeiten**, kein Nachweis der öffentlichen Ankündigung.

Die API-Ergebnisse sind eine absichtlich breitere Entdeckungsmenge, kein Beweis,
dass alle darin enthaltenen Arbeiten frisch sind. Die Tagesliste kann ältere
öffentliche Ankündigungen nicht rekonstruieren. Bei Nachholfenstern, verzögerter
Moderation, fehlender öffentlicher Datierung oder einer Lücke in Listen/API diese
Grenzen benennen; ausgewählte Arbeiten benötigen weiterhin eigene Datumsbelege.
Überlapptage und Quellen-Wasserstand nicht verkürzen. Falls `recent` nicht bis
`since` zurückreicht, ist `window_complete=false`; nötigenfalls datierte/monatliche
Quelllisten im bestehenden Budget nachprüfen, sonst die Lücke ausdrücklich belassen.

Alle gespeicherten `titles` im betreffenden Fenster bzw. in der breiteren
API-Entdeckungsmenge kompakt sichten:

```sh
python3 ROOT/scripts/arxiv_discovery.py --view WORKER/arxiv-recent.json --offset 0
```

Mit dem ausgegebenen `next_offset` fortsetzen, bis er `null` ist; ebenso für
`arxiv-changes.json` und `arxiv-updates.json`. Die Ausgabe enthält vollständige
Titel statt großer Metadaten/Abstract-Payloads; `total` ist die Zahl gespeicherter
Entdeckungstitel, nicht die Gesamtzahl der rollierenden Quellliste. Wiederholte
Titel zwischen den drei Mengen nur einmal inhaltlich sichten, aber deren Datums-/
Versionszuordnung erhalten. `read_file` bleibt für gezielte Quelldetails verfügbar. Keine Titel per Kontext-/50er-Grenze still abschneiden. Abstract und
gegebenenfalls Originalvolltext nur für thematisch relevante Arbeiten lesen.
**Vollständige Titelentdeckung ist niemals vollständige Volltextlektüre.**

## 2. Veröffentlichung, Einreichung und neue Version auseinanderhalten

arXiv unterscheidet die Einreichung von der späteren öffentlichen Ankündigung.
Moderation/Ankündigungsplan können mehrere Tage dazwischenlegen. Nicht aus
Wochentagen oder dem API-Feldnamen `published` ein öffentliches Datum errechnen.
Insbesondere eine Einreichung am Freitag, 16.10.2026 darf trotz `since=17.10.`
nicht verworfen werden, wenn die erste öffentliche Liste am Montag, 19.10.
belegt ist. Das Original-Einreichungsdatum bleibt dabei 16.10.

Für jeden neuen arXiv-Kandidaten (auch aus `discovery`) zusätzlich `arxiv_dates`
liefern. Beispielstruktur mit dem tatsächlich gelesenen Original 2610.23845:

```json
{
  "published_at": "2026-10-16",
  "arxiv_dates": {
    "submitted_at": "2026-10-16T17:57:55Z",
    "listed_on": "2026-10-19",
    "listing_url": "https://arxiv.org/list/cs.AI/recent?skip=0&show=2000",
    "announcement_url": "https://arxiv.org/list/cs.AI/new?skip=0&show=2000",
    "announce_type": "new",
    "version": 1
  }
}
```

Das ist ein Datumsbeispiel, **keine redaktionelle Aufnahmeentscheidung**. Titel,
Abstract und jede aufgenommene Aussage weiterhin am Original prüfen. Sowohl
`listing_url` als auch `announcement_url` müssen mit tatsächlich gelesenen
Originalstellen in `evidence` vorkommen; dazu wie bisher das Kandidaten-Original.
`announce_type=new` muss durch die New-Rubrik oder einen offiziellen Feed belegt
sein, nicht nur aus `v1` oder der Listenzugehörigkeit geraten werden.

Bei `replace`/`replace-cross`: ursprüngliches `submitted_at` und `published_at`
behalten, zusätzlich `updated_at` der betreffenden Version, `version >= 2` und
`substantive_update: true` liefern. Die konkrete substantielle Änderung am
Original und gegebenenfalls Versionsvergleich belegen; reine Metadatenänderung,
Journalreferenz oder Kreuzlistung reicht nicht. Ein Update nicht als erste
Veröffentlichung darstellen. Öffentlicher Listing-/Ankündigungstag ist die
Frischegrundlage; optionale genaue `announced_at`-Zeit muss nach Europe/Berlin
denselben Listentag ergeben. Bei ungeklärter öffentlicher Datierung zurückstellen.

`record`, `assemble` und `add-evidence` prüfen ab Register 5 das Zeitfenster gegen
diese öffentliche Frische (`freshness_date`), nicht nur gegen die Einreichung.
Die Editoransicht zeigt beide Daten und die Provenienz. Die Schlussredaktion
prüft Semantik und Originalstellen. Ein öffentlicher Meldungstag darf den
belegten neuen öffentlichen Schritt darstellen; Einreichung/Versionsdatum im
Text ausdrücklich getrennt benennen, nicht ein altes Submission-Datum umetikettieren.
Historische Kandidaten ohne diese Zusatzfelder bleiben nach ihren alten Regeln gültig.

## 3. Ehrlicher Quellen-Checkpoint

Im arXiv-Quellenobjekt `title_discovery` als Liste der drei Helferberichte
(`recent`, `changes`, `updates`) **ohne deren großes `titles`-Feld** speichern.
Die vollständigen Titeldateien bleiben im Worker-Cache. Mit `write_file` eine
prüffähige Record-Eingabe erstellen. `result` nennt Zähler, tatsächlich gesichtete
Titel, ausgewählte Originallektüre, Dateien/URLs sowie verbleibende Grenzen.

Ein neuer `checked`-Checkpoint ohne diese Berichte oder mit falscher
Vollständigkeitsbehauptung wird abgelehnt. Ein ehrliches `complete=false` mit
Einschränkung ist zulässig und blockiert nicht die restlichen Pflichtquellen.
`checked` heißt dann geprüft, nicht lückenlos abgedeckt. Bei vollständigem
Zugangsausfall wie bisher `unavailable` und keine Kandidaten. Budget-/Agentenabbruch
bleibt `pending`, kein erfundener Quellenfehler. Partielle Titelabdeckung schiebt
den Quellen-Wasserstand nicht vor. Das Tagesaudit erhält die kompakten Berichte;
keine historischen Audit-Dateien ändern. Optionale SemiAnalysis-Entdeckung gehört
nicht in diesen Pflicht-Checkpoint.

## Offizielle Datumsdefinitionen (am 19.10.2026 gelesen)

- https://info.arxiv.org/help/availability.html — Moderation und öffentliche
  Ankündigung sind von der Einreichung getrennt; Plan nicht als Einzelbeleg verwenden.
- https://info.arxiv.org/help/api/user-manual.html — Such-API: Entry `published`
  ist die Einreichung von Version 1; Entry `updated` die Einreichung der gelieferten
  Version. `opensearch:totalResults` und `startIndex` liefern Zählung/Cursor.
- https://info.arxiv.org/help/atom_specifications.html — **RSS-Atom**, nicht
  Such-API: Entry `published` ist das Ankündigungsdatum; `announce_type` trennt
  new/replace/cross. Feed-/Entry-`updated` hier ist nur die Feed-Erzeugungszeit.
- https://arxiv.org/abs/2610.23845 — konkrete v1-Einreichung am 16.10.2026,
  zusammen mit tatsächlicher New-Liste vom 19.10.2026 als getrennter Datumsbeleg.
