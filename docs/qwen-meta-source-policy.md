# Qwen und Meta: geprüfte Originalzugänge

Verbindlich für die Assignments `qwen.ai` und `ai.meta.com`; read-only live
geprüft am **19.10.2026**. Die anderen 38 Pflichtquellen, arXiv-/SemiAnalysis-
Regeln und Register 1–5 bleiben unverändert. Keine neue Quelle und keine
Domainmigration: Die Audit-Identität bleibt bestehen; Meta erhält einen eng
begrenzten zusätzlichen, offiziell verlinkten Originalhost.

## Qwen: Index-API, verzögertes Rendering und Code-Releases

1. Der kanonische Einstieg bleibt `https://qwen.ai/research`. Ein Browserabruf
   unmittelbar nach Navigation las nur 494 Zeichen Navigation, obwohl nach
   drei Sekunden Karten und später echte Artikel erschienen. Deshalb verwendet
   `browser_source_fetch.py` Navigation, **wait 3000**, Extraktion und Close in
   einem isolierten Desktop-Chrome-Batch. Die Wartezeit ist keine Volltext- oder
   Aktualitätsgarantie: Cache, Datum und Originalaussagen selbst prüfen.
2. Bei JS-Hülle oder fehlenden Kartenlinks den im Assignment hinterlegten
   `fetch_helper` ausführen; nicht weiter URL-Pfade raten:

   ```sh
   python3 ROOT/scripts/qwen_source_fetch.py --output WORKER/qwen-api-index.json
   python3 ROOT/scripts/qwen_source_fetch.py --code-releases --output WORKER/qwen-code-releases.json
   ```

   ROOT und WORKER durch tatsächliche eigene Pfade ersetzen. Je Route ein
   öffentlicher API-Abruf, 45 Sekunden und 10 MB als feste Grenzen. Kein Login,
   kein Zusatzsuchbudget, keine WAF-/CAPTCHA-Umgehung. Fehler pro Route
   dokumentieren, nicht den übrigen Quellenlauf abbrechen.
3. Die Research-API wurde aus den tatsächlichen Resource-Requests der Research-
   Seite entdeckt: `https://qwen.ai/api/v2/article/retrieval?type=qwen_ai&language=en-US`.
   Sie lieferte 40 Artikel samt Original-HTML und Metadaten; jüngstes Datum war
   **20.09.2026**, nicht Oktober. Die ebenfalls beobachtete ältere
   `api/page_config?code=research.research-list&language=en` war sogar nur bis
   Dezember 2025 gepflegt und ist **kein** gleichwertiger Ersatzindex.[6]
4. Der Helper speichert die gesamte Antwort in `*.raw.json`, die datierten
   Titel/URLs im normalen JSON-Cache (`url`, `retrieved_at`, `text`, `articles`).
   Erfinde keine Vollständigkeit: `discovery_complete: false`, weil die API
   keinen deklarierten Gesamtzähler oder verbindliche Pagination liefert.
   `--from-json DATEI` ist ausschließlich eine Offline-Wiederholung vorhandener
   Daten und kein neuer Live-Abruf.
5. Lies relevante `articles[].url` am Original mit dem Browserhelper, maximal
   drei Originale. Geprüft: `https://qwen.ai/blog?id=qwen-image-2.1` lieferte
   Originaldatum **2026/09/20**, 965 Wörter laut Header und einen tatsächlich
   lesbaren Artikel mit Modell-/Repository-Links. Das repariert den Volltextzugang,
   bestätigt aber **keine** Oktober-Modellveröffentlichung.[4]
6. Der zweite Helper-Aufruf liest ausschließlich die offiziellen Releases unter
   `QwenLM/qwen-code` über die öffentliche GitHub-API, begrenzt auf eine Seite
   mit 30 Einträgen. `published_at` ist das Release-Datum, nicht `created_at`,
   README-Änderungszeit oder Downloadzahl. `prerelease` erhalten; Nightlies,
   Previews, SDK- und Desktop-Tags nicht als neue allgemeine Qwen-Modelle darstellen.
   Quelleigentum und Docs sind im offiziellen Repository nachvollziehbar:
   `https://github.com/QwenLM/qwen-code`. Der veraltete allgemeine Legacy-Blog
   macht dessen separat gepflegte Qwen-Code-Dokumentation nicht automatisch alt.
   **v0.25.3** war am **19.10.2026, 06:06:37 UTC** als stabiles Release mit
   echten Release Notes lesbar; das ist eine aktuelle **Coding-Agent**-Entwicklung,
   keine neue Modellfamilie.[5]

**Abdeckungsgrenze:** Qwen-Code-Releases ersetzen weder alle Modell- noch alle
Unternehmensnachrichten. Bleibt der Research-Index außerhalb des Assignment-
Fensters, Datumssuche und breitere Qwen-Zeitfenstersuche im bestehenden Budget
ergänzen. Im `result` technische Lesbarkeit, jüngstes Indexdatum und verbleibende
Entdeckungslücke getrennt nennen; nicht pauschal Entwarnung geben. Bei weiterhin
unvollständiger Gesamtquelle `unavailable`, keine Kandidaten in diesem Checkpoint.
Separat gelesene aktuelle Ersatzkandidaten als Dateien dem Editor zur regulären
Discovery-Validierung übergeben, nicht trotz `unavailable` einschmuggeln.

## Meta: aktuellen Research-Host statt eingefrorenem Blogindex nutzen

- `URL_OVERRIDES['ai.meta.com']` zeigt nun auf **`https://research.meta.ai/`**,
  nicht auf den alten Juli-Blogindex. `https://ai.meta.com/research/` verlinkt
  diesen Host ausdrücklich für aktuelle Research-Originale. Die auf der alten
  Website verlinkte Publications-Ansicht ist als weitere Assignment-Alternative
  hinterlegt (kein Anspruch auf vollständige FAIR-Abdeckung).[1]
- `https://research.meta.ai/` zeigte im gerenderten Browser datierte Oktober-
  Karten und echte Originallinks; **nicht** durch `/blog` ersetzen: dessen
  Web-Extraktion lieferte im Vergleich einen älteren September-Stand.[2]
- Original `https://research.meta.ai/blog/muse-spark-open` war mit **15.10.2026**
  im sichtbaren Header und vollständigem Text lesbar. Direktes HTML enthält
  ebenfalls `article:published_time` und JSON-LD `datePublished` vom 15.10.
  Ein alter Such-/Extraktionscache ist damit kein Primärquellen-Ausfall mehr.[3]
- HTTP/web_extract zuerst; bei unvollständiger Extraktion den gleichen
  `browser_source_fetch.py --url URL --session briefing-meta-ID --output DATEI`
  verwenden. Ein Index und höchstens drei Originale je Quelle; 60 Sekunden pro
  Browser-Aufruf. Die `alternate_urls` sind keine Anweisung, sämtliche Indizes
  jedes Mal zusätzlich gerendert abzurufen.
- Der Validator akzeptiert für **diesen** Quellencheckpoint zusätzlich nur den
  exakten HTTPS-Host `research.meta.ai`, ohne Zugangsdaten oder Sonderport.
  Kein pauschales `meta.ai`-Allowlisting und keine Lockerung von `domain_matches`.
  Die registrierte Quelle heißt weiter `ai.meta.com`.

**Abdeckungsgrenze:** Aktueller Research-Index plus Originaltexte sind repariert;
kein Beweis vollständiger FAIR-, Produkt-, Governance- oder Unternehmensabdeckung.
Bei altem/unvollständigem Index bleiben gezielte Datumssuche **und** breitere
Unternehmenssuche im bestehenden Budget verbindlich. Für nur einzelne gelesene
Artikel nicht den gesamten Zeitraum als abgedeckt ausgeben. Das Originaldatum
15.10. darf bei einem später beginnenden Assignment nicht als frische Meldung
umetikettiert werden. Historien-Deduplizierung bleibt unverändert.

## Abnahme und Aktivierung

Die neuen Routen werden bei `prepare` in **neue** Assignments geschrieben;
bestehende Manifeste und historische Tagesaudits werden nicht migriert.
Der gespeicherte Cron-Prompt lädt die Worker-Anleitung bereits verbindlich;
kein neuer Prompt und keine Live-Job-Änderung sind für diese Zugangsreparatur nötig.
Die read-only Abnahme ist **kein** neuer Tageslauf und keine Veröffentlichung.

Lokale Live-Belege außerhalb Git: `/opt/data/cache/qwen-meta-access-verification.json`
und die darin referenzierten ungekürzten Abrufcaches. HTTP-200, erfolgreiche CLI-
Ausführung und Zeichenzahlen allein beweisen weder Inhalt noch Datum/Abdeckung.

## Sources

[1] https://ai.meta.com/research
[2] https://research.meta.ai
[3] https://research.meta.ai/blog/muse-spark-open
[4] https://qwen.ai/blog?id=qwen-image-2.1
[5] https://github.com/QwenLM/qwen-code/releases/tag/v0.25.3
[6] https://qwen.ai/api/v2/article/retrieval?type=qwen_ai&language=en-US
