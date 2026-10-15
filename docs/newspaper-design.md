# Zeitungsgestaltung: Vertrag und Abnahme

Die „The Morning Tab“-Vorschau von [ThariqS/ai-newtab](https://github.com/ThariqS/ai-newtab)
ist die visuelle Referenz: Papierfarbe, großer Serifenkopf, feine/Doppellinien,
redaktionelle Spalten und kleine Metadaten. Eigene HTML-/CSS-Implementierung;
kein Extensioncode, keine Browserhistorie, keine Wetter-/Kalenderattrappen und keine
neuen Dienste. Markenname: **AI Briefing**.

## Gestaltungsvertrag

- Gemeinsamer Zeitungskopf auf Übersicht, Feld-Reports und Suche; Ausgabe aus
  `meta.generated`, nicht aus dem heutigen Systemdatum. Originaldaten bleiben erhalten.
- Aufmacher und zwei weitere Schlagzeilen aus vorhandenen Artikeln. Sortierung:
  Impact absteigend, kanonisches Originaldatum absteigend, Themen-ID, Titel,
  Quellenidentität. Keine Zufallsauswahl und keine neu erzeugten Zusammenfassungen.
- Die hervorgehobenen Teaser werden nicht in den Themenlisten dupliziert.
  Themenzusammenfassungen und alle Feld-Reports bleiben vollständig erreichbar.
- Themenübersicht in drei, auf Tablet zwei, auf schmalen Geräten einer Lesespalte.
  Die rechte Einordnung enthält nur die wirkliche Impactskala.
- Radarfarben und Nummern bleiben erhalten. Zahlenfarbe wird nach dem höheren
  gemessenen Kontrast gewählt; Kategorienamen stehen in dunkler Schrift mit Farbstreifen.
- Systemschriften statt Schrift-CDN; sichtbarer Tastaturfokus, benannte Navigationen,
  Haupt-Lesebereich, echte Links und beschriftete Suchfelder.

## Funktionsmatrix und geprüfter Stand

| Vertrag | Nachweis |
| --- | --- |
| 8 Themen × 4 Ansichten; unveränderte URLs | 36 Inhaltsseiten + Suche; alle lokalen Link-/Assetziele geprüft |
| Heute = Ausgabe; 7/14/30 = Zeiträume | bestehende Datumstests, Browser-Zeitraumwechsel, Originaldatenvergleich |
| Vollständige Artikel, Quellen, Impact, Überspringen | Detail-/Skip-HTML vor/nach gleich, nur Badge-/Zahlenfarben geändert |
| Vollständiges Radar und Legende | SVG-Geometrie, Nummern, Kategorien und Ringfarben vor/nach gleich; nur Zahlenkontrast verbessert |
| Archivsuche, Dedupe, GET `q`, Normalisierung | unveränderte `search.js` und Indexbytes; bestehende Python-/Node-Tests |
| Echte Eingabe + Enter, präzise Anzahl | Browser: `OpenAI` 451 Treffer, 50 angezeigt |
| Weitere 50 | Browser: leere Query 1.977 Treffer, Anzeige 50 → 100 |
| Keine Treffer / Umlaute / Ladefehler | Browser: Nulltreffer, `für` = `fuer` (1.351), blockierter Index mit ehrlichem Fehler |
| Sichere Darstellung | Browser-only Fetch-Fixture: HTML als Text, keine injizierten Bilder/Scripts oder JavaScript-Links |
| Ohne JavaScript | tatsächlich deaktiviertes JavaScript: 8 Themen, 4 Zeiträume, Suchformular und no-JS-Hinweis |
| Responsive | Übersicht, 7-Tage-Übersicht, AI-News-Radar und Suche bei 1.440 / 768 / 390 / 320 px ohne horizontalen Seitenüberlauf |
| Zugänglichkeit | axe-core auf Übersicht, 7-Tage-AI-News und Suche: jeweils 0 bestätigte Verstöße; SVG-/Symbolkontrast zusätzlich manuell und rechnerisch geprüft |
| Editorial-Daten unverändert | identische Hashes aller Dateien unter `data/`; Index mit 1.977 Einträgen identisch |

Baselinevergleich: **51 Artikel in der aktuellen Ausgabe**, 800 im Pool;
**1.321 Artikeldarstellungen über alle vier Ansichten**, **857 unterschiedliche
externe Quellen-URLs** und **1.977 Suchindexeinträge** vor/nach identisch.
Die Darstellungen über Zeiträume sind keine Anzahl einzigartiger Artikel.

Lokale Prüfung: 164 Python-Tests und 4 Node-Tests bestanden. Zusätzliche neue
Layoutverträge stehen in `scripts/test/test_newspaper_layout.py`; nur eine alte
Präsentationsassertion wurde um den zugänglichen Namen der Navigation ergänzt.

```sh
/opt/hermes/.venv/bin/python -m unittest discover -s scripts/test -t scripts/test
node --test scripts/test/search.test.cjs
/opt/hermes/.venv/bin/python scripts/render.py
git diff --check
```

Screenshots/Browserprotokolle dieser Abnahme liegen auf dem Ausführungshost unter
`/opt/data/cache/newspaper-*`, nicht in den redaktionellen Daten. Die genaue
Deployment-SHA und die GitHub-Actions-Läufe werden nach dem Push getrennt geprüft.
Automatische axe-Prüfung ersetzt keine vollständige manuelle Accessibility-Zertifizierung.
