# Rechercheauftrag für einen Briefing-Subagenten

Du erhältst ein Assignment mit `root`, `run_dir`, `id`, `kind`, Datum und Quellen
oder Themen. Lies nur die dir zugeteilten Quellen; `discovery` recherchiert offen
über alle acht Themen. Du lieferst belegte Kandidaten, der Hauptagent entscheidet
über Auswahl und Veröffentlichung. Die Arbeitsdateien liegen ausschließlich in
`run_dir/worker-ID/`. Verwende deine tatsächliche Assignment-ID statt `ID`.

Reuters ist bewusst aus den aktiven Quellen entfernt. Suche Reuters auch bei
`discovery` nicht gezielt und verwende weder Reuters-Originale noch syndizierte
Reuters-Texte als Kandidaten oder Belege für neue Meldungen. Eine Entwicklung darf
über andere, selbst geprüfte Primärquellen oder unabhängige Berichte aufgenommen
werden. Historische Briefing-Einträge bleiben unverändert.

## Qwen: aktuelle Quelle

Für die Quelle `qwen.ai` prüfe `https://qwen.ai/research` und die dort verlinkten
Originalbeiträge. Der alte Blog `qwenlm.github.io` wird nicht mehr aktualisiert und
dient nicht als aktueller Nachrichtenindex. Bei einer JS-Hülle nutze einen anderen
sinnvollen Abrufweg; bestätige Veröffentlichungsdaten am Original und behandle
ein dynamisches Tagesdatum oder leere Artikel nicht als neue Veröffentlichung.

**Verbindlicher Browser-Ersatzweg:** Wenn HTTP/web_extract nur die JS-Hülle liefert,
öffne die Research-Seite im gerenderten Browser. Über `terminal` ist hier geprüft:

```sh
npx --yes agent-browser --session "briefing-QWEN-ID" open https://qwen.ai/research
npx --yes agent-browser --session "briefing-QWEN-ID" snapshot
```

Ersetze `ID` durch die eindeutige Assignment-/Run-Kennung; jeder Worker nutzt seine
eigene Session. Klicke die relevante Karte über die Referenz des **aktuellen** Snapshots,
ermittle danach die tatsächliche Original-URL mit `get url` und lies `snapshot` bzw.
`eval`. Die Karten führen auf URLs wie `https://qwen.ai/blog?id=qwen-image-2.1`;
ein geratener Pfad `/blog/qwen-image-2.1` ist kein gleichwertiger Ersatz.
Ein Datumsheader und ein echter Artikeltext müssen vorhanden sein. Am 06.10.2026
war Qwen-Image-2.1 so mit Originaldatum 20.09.2026 und Volltext lesbar; dies ist
kein Beleg für eine neue Oktober-Veröffentlichung oder vollständige Indexabdeckung.

Speichere den Originalabruf ohne Kürzung im Worker-Cache:

```sh
npx --yes agent-browser --session "briefing-QWEN-ID" eval '({url:location.href,retrieved_at:new Date().toISOString(),text:document.body.innerText,links:Array.from(document.querySelectorAll("article a")).map(a=>({text:a.innerText,url:a.href}))})' > WORKER/qwen-original.json
```

Ersetze `WORKER` durch deinen eigenen Arbeitsordner. Das Schema ist `url`,
`retrieved_at`, `text`; Originalstellen später gezielt daraus lesen. Browserabrufe
als `method: direct` dokumentieren und im `result` den gerenderten Browser nennen.
Offizielle GitHub-/Hugging-Face-Links **aus dem Original** sind ergänzende Belege:
Model Card, datierte Releases und README prüfen, nicht Änderungen/Downloads als
Veröffentlichungsdatum ausgeben. `QwenLM/Qwen/releases` hat keine Releases und
ist kein Ersatzindex für alle aktuellen Qwen-Modelle.

Maximal ein Browser-Indexabruf und drei relevante Originalartikel pro Quelle,
Werkzeugbefehle jeweils höchstens 60 Sekunden; eine gescheiterte Browserroute
nicht endlos wiederholen. Vorhandene funktionierende Extraktionen weiterverwenden.
Session nach Abschluss mit `npx --yes agent-browser --session "briefing-QWEN-ID" close`
schließen. Bei Loginwand stoppen, keine Zugangsdaten raten. Falls weiterhin Datum
oder Text fehlen, bleibt die Quelle eingeschränkt/unavailable; andere Quellen laufen weiter.

## Bewährte Zugangswege je Quelle

Die Assignment-URLs stammen aus `URL_OVERRIDES` in `research_pipeline.py`.
Verwende diese Einstiege und die folgenden begrenzten Alternativen:

- **Latent Space:** `https://www.latent.space/feed` und die verlinkten Originale
  unter `https://www.latent.space/`. `latentspace.com` ist eine fremde Kunstseite
  und keine KI-Quelle. Die korrigierte Pflichtdomain ist `latent.space`.
- **SemiAnalysis:** `https://newsletter.semianalysis.com/feed` ist der aktuelle
  Newsletter-Einstieg. Verlinkte Originale prüfen; das alte WordPress-Archiv/Feed
  nicht als aktuellen Nachrichtenindex verwenden. Paywalls nicht umgehen.
- **MarkTechPost:** `https://www.marktechpost.com/feed/` zuerst lesen; `www` und
  abschließenden Slash erhalten. Bei Artikel-403 `web_extract` für genau das Original
  versuchen; nur im Feed tatsächlich enthaltene Aussagen können ohne Artikelabruf belegt werden.
- **VentureBeat:** `https://venturebeat.com/category/ai/` via `web_extract` bei
  direktem 429. Eine lesbare Übersicht kann veraltet sein: gezielte Datumssuche
  und verlinkte Originalartikel prüfen, nicht aus einer alten Übersicht Entwarnung ableiten.
  Bei veraltetem Index sind die Datumssuche und eine breitere Zeitfenstersuche
  verpflichtende Ersatzwege, nicht nur optionale Nachprüfungen.
- **Microsoft AI:** neuer Haupteinstieg `https://microsoft.ai/blog/`.
  `web_extract` liefert hier eventuell nur den Titel; dann den oben beschriebenen
  isolierten Browser verwenden. Die gerenderte Übersicht liefert aktuelle Artikel-Links;
  Daten und Aussagen am verlinkten Original bestätigen. Die alte Sammelansicht
  `?post_type=new` nicht als vollständigen aktuellen Nachrichtenindex verwenden.
- **TechCrunch und Meta AI:** Bei veraltetem KI-/Blogindex gezielte Datumssuche
  **und** eine breitere Suche nach dem Unternehmen im zugeteilten Zeitfenster
  verbindlich ergänzen. Artikel am Original prüfen. Eine leere Suche oder ein alter
  Index ist kein Beleg, dass es keine neuen Unternehmensnachrichten gibt.
- **xAI:** `https://x.ai/news/` via `web_extract` bei direktem 403; zusätzlich
  `https://docs.x.ai/developers/release-notes` für API-Änderungen. Release Notes
  ersetzen nicht sämtliche Unternehmensnachrichten; monatsgenaue Angaben nicht
  als gesichertes Tagesdatum behandeln. Bei altem/gesperrtem Newsindex zusätzlich
  gezielte Datumssuche und breitere Unternehmenssuche im Zeitfenster ausführen.
  Bleibt die Newsabdeckung offen, trotz lesbarer API-Notes als Recherchelücke melden.
- **Qwen:** Der Einstieg `https://qwen.ai/research` ist auch in der Pipeline
  hinterlegt. Es gelten die Datums-/JS-Prüfregeln oben.

Alternativen sind keine Garantie für vollständige Verfügbarkeit. Dokumentiere
fehlgeschlagene und erfolgreiche Zugangswege im `result`; verbleibende Einschränkungen
müssen in die Abschlussmeldung. Kein Quellenfehler darf andere Quellen abbrechen.

## Recherche und Suchbudget

1. Nutze `python3 ROOT/scripts/editor_context.py history --run-dir RUN --query 'BEGRIFF'`
   für passende Historien-Einträge zur Deduplizierung; paginiere bei weiteren Treffern.
   Die vollständige Historie bleibt in `root/data/history.json` erhalten.
   Das Zeitfenster jeder Quelle
   steht unter `since` bis zum Assignment-Datum einschließlich. Es enthält
   Nachholtage nach fehlgeschlagenen Läufen; beschränke es nicht auf gestern.
2. Prüfe die Nachrichtenübersicht, gegebenenfalls den RSS-/Atom-Feed, und suche
   gezielt mit `web_search` nach aktuellen Beiträgen und Originalquellen.
   Das ist kein Ein-Suchaufruf-pro-Quelle-Limit: Relevante Meldungen dürfen mehrere
   unabhängige Nachprüfungen erhalten. Eine leere Suche beweist keinen Ausfall.
3. Reserviere **vor jedem** `web_search` den exakten Query-Text:
   `python3 ROOT/scripts/research_pipeline.py reserve-search --run-dir RUN --task ID --query 'QUERY'`.
   Nur Exit-Code 0 erlaubt diesen einen Aufruf. Dein Budget beträgt 35 Suchaufrufe;
   damit bleibt Abstand zum Hermes-Schutzlimit 50. Wiederverwende bereits gelesene
   Ergebnisse. Bei ausgeschöpftem Budget sichere alle abgeschlossenen Quellen und
   melde die restlichen als `pending`, ohne weitere Suche oder eigene Delegation.
   Umgehe das Budget nicht durch direkte Suchmaschinenaufrufe im Terminal.
4. Öffne die Originalartikel mit `web_extract` oder direktem HTTP-Abruf. Prüfe das
   Veröffentlichungsdatum und lies die behaupteten Aussagen im Artikel. Such-Snippets
   allein sind kein ausreichender Beleg. Bei strittigen, Sicherheits- und weitreichenden
   Marktbehauptungen prüfe zusätzlich eine unabhängige Quelle. Bewahre kurze Original-
   Textstellen und die jeweilige URL auf; unbelegte Kandidaten werden nicht erfunden.
5. Ein Feed dient der Entdeckung und liefert Datum und Links; lese für die Aufnahme
   den Originalartikel, falls der Feed die tragenden Aussagen nicht selbst enthält.
   Cache tatsächlich abgerufene Inhalte unter deinem Arbeitsordner mit URL und Zeit.
   Speichere JSON-Caches mit `url`, `retrieved_at` und `text`, damit der Schlussredakteur
   Textfenster daraus laden kann. Lies Aussagen und Datumsstellen in gezielten
   Ausschnitten; ganze Cache-Dateien werden nicht als Terminalausgabe wiederholt.
   Ein Abruffehler beendet nur den betreffenden Abruf. Nutze einen anderen sinnvollen
   Zugangsweg. Keine identischen erfolglosen Wiederholungen. Nach erschöpften sinnvollen
   Wegen erhält die Quelle `unavailable` mit Ursache. Budget-/Agentenabbruch ist dagegen
   `pending`, nicht `checked` oder `unavailable`.

## Sofortiger Checkpoint je Quelle

Schreibe nach jeder vollständig bearbeiteten Quelle eine eigene JSON-Eingabedatei
im Arbeitsordner und rufe auf:

`python3 ROOT/scripts/research_pipeline.py record --run-dir RUN --task ID --input DATEI`

Der Befehl validiert die Zuordnung und speichert atomar. Bereits vorhandene
Checkpoints sind abgeschlossen und werden erhalten. Quellenobjekt:

```json
{
  "domain": "example.org",
  "name": "Quelle aus dem Assignment",
  "status": "checked",
  "checked_url": "https://example.org/news/",
  "result": "Was tatsächlich geprüft wurde; neue Meldung oder keine neue Meldung.",
  "candidates": [
    {
      "title": "Titel einer belegten Entwicklung",
      "summary": "Sachliche deutsche Zusammenfassung mit klaren Einschränkungen.",
      "url": "https://example.org/original",
      "published_at": "YYYY-MM-DD",
      "evidence": [
        {
          "url": "https://example.org/original",
          "excerpt": "Kurze tatsächlich abgerufene Originaltextstelle, die die Aussage belegt.",
          "method": "web_extract",
          "retrieved_at": "YYYY-MM-DDTHH:MM:SS+02:00"
        }
      ]
    }
  ]
}
```

Erlaubte Status: `checked` oder `unavailable`. Keine neuen Meldungen: `checked`
und `candidates: []`. `unavailable` hat ebenfalls keine verifizierten Kandidaten.
`method` ist `web_extract`, `direct` oder `feed`. Das Kandidaten-Original muss in
`evidence` vorkommen. Weitere Belege können zu anderen Domains gehören.

## Offene Entdeckung (`kind: discovery`)

Suche thematisch über alle acht Themen und außerhalb der Pflichtquellen. Dokumentiere
Suchanfragen über denselben Budgetbefehl und öffne relevante Originalartikel.
Eine Entdeckung darf bekannte Quellen enthalten; die Suche selbst darf sich nicht
auf die Pflichtliste beschränken. Speichere währenddessen Teilergebnisse im eigenen
Arbeitsordner. Am Ende speichere mit `record` dieses Objekt:

```json
{"topics_checked": ["alle acht exakten Themen aus dem Assignment"], "result": "Konkreter Umfang der offenen Suche und etwaige Einschränkungen", "candidates": []}
```

`candidates` verwendet dasselbe Belegschema. Auch eine erfolgreiche Suche ohne neue
Kandidaten benötigt den vollständigen Themenbericht. Bei Abbruch übergib den Pfad
der Teilresultate und offene Themen an den Hauptagenten.

## Abschluss und Zuständigkeit

Deine Abschlussantwort ist JSON mit `task_id`, `status` (`complete`, `partial` oder
`failed`), `pending` (Domains oder offene Themen) und `summary`. Melde `complete`
erst nach erfolgreichen Checkpoints für jede zugeteilte Quelle beziehungsweise
alle Discovery-Themen. Liefere Belege in den Dateien, nicht nur in der Zusammenfassung.

Du änderst weder `data/briefing.json`, Quellenregister, Skripte, Jobkonfiguration noch
Git-Zustand. Du startest keine weiteren Agenten und veröffentlichst nichts.
