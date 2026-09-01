# Design: Historisierung & Zeitraum-Ansichten

**Datum:** 2026-06-10
**Status:** Entwurf zur Review

## Ziel

Das AI-Briefing soll historisierbar werden: Tägliche Updates dürfen vergangene
Meldungen nicht mehr verwerfen. Zusätzlich soll man auf der Seite einen Zeitraum
für die anzuzeigenden Einträge wählen können: **Heute · 7 Tage · 14 Tage · 30 Tage**.

Randbedingungen:

- `data/briefing.json` bleibt unverändert die Schnittstelle für den täglichen
  Cowork-Task (`ai-briefing-daily`) und `scripts/update.py` — kein Eingriff dort.
- Die Seite bleibt **rein statisch, ohne JavaScript** (bestehendes Prinzip).
- `python3 scripts/render.py` bleibt der einzige Aufruf zum Generieren.

## Datenmodell: kumulativer Item-Pool

Neue Datei `data/history.json`:

```json
{
  "items": [
    {
      "topic_id": "ai-news",
      "title": "…",
      "category": "modelle",
      "impact": 5,
      "date": "2026-06-09",
      "summary": "…",
      "sources": [{ "label": "…", "url": "…" }],
      "first_seen": "2026-06-10"
    }
  ],
  "summaries": [
    {
      "topic_id": "ai-news",
      "date": "2026-06-10",
      "summary": "Lede-Text des Tages …",
      "skip": [{ "reason": "…", "text": "…" }]
    }
  ]
}
```

- `items[].date` wird intern als ISO-Datum gespeichert (Eingabeformat
  `TT.MM.JJJJ` aus `briefing.json` wird beim Ingest normalisiert).
- `first_seen` = `meta.generated` des Briefings, in dem das Item erstmals
  auftauchte (Fallback für Items ohne parsebares `date`).
- Die laufende Nummer `n` wird NICHT gespeichert — sie wird je Ansicht beim
  Rendern neu vergeben.
- `summaries` archiviert pro Topic und Tag die Lede (`summary`) und die
  `skip`-Liste aus `briefing.json`.
- Topic-Stammdaten (`id`, `name`, `group`, `angle`) und `trending` kommen
  weiterhin live aus `briefing.json`, werden nicht historisiert.
- Keine Aufbewahrungsgrenze (kann später ergänzt werden, YAGNI).

## Ingest (Teil von render.py)

Vor dem Rendern führt `render.py` einen Merge-Schritt aus:

1. `history.json` laden (existiert sie nicht: leer initialisieren).
2. Für jedes Item aus `briefing.json`: per Matching-Logik prüfen, ob es bereits
   im Pool ist. Wenn ja → bestehenden Eintrag aktualisieren (neuere Fassung
   gewinnt bei Summary/Impact/Quellen); wenn nein → mit `first_seen` anhängen.
3. Tages-Summary + Skip je Topic unter dem Datum `meta.generated` ablegen
   (gleicher Tag wird überschrieben, damit mehrfaches Rendern idempotent ist).
4. `history.json` zurückschreiben.

**Dedup-Matching:** Dieselbe Meldung kann an mehreren Tagen im Tages-Briefing
stehen. Verglichen wird nur innerhalb desselben Topics. Zwei Items gelten als
dieselbe Meldung, wenn sie mindestens eine Quell-URL teilen (normalisiert:
ohne Trailing-Slash und Query-Parameter) ODER ihr normalisierter Titel
(lowercase, Satzzeichen entfernt) identisch ist. Bei einem Match gewinnt die
neuere Fassung für `title`, `summary`, `impact` und `category`; die
`sources`-Listen werden vereinigt (URL-dedupliziert); `date` und `first_seen`
behalten den ältesten Wert. *(Diese Logik ist die im Pairing zu gestaltende
Stelle — die genannten Regeln sind der abgestimmte Default.)*

Der Ingest ist **idempotent**: `render.py` mehrfach am selben Tag aufzurufen
darf keine Duplikate erzeugen.

## Zeitraum-Ansichten

Vier statisch vorgerenderte Varianten der kompletten Seite:

```
site/
├── index.html, ai-news.html, …        ← „Heute“ (Standard, wie bisher)
├── 7d/index.html, 7d/ai-news.html, …  ← letzte 7 Tage
├── 14d/…                              ← letzte 14 Tage
└── 30d/…                              ← letzte 30 Tage
```

- Stichtag ist `meta.generated`. „Heute“ = Items mit `date` == `meta.generated`
  ∪ Items des aktuellen `briefing.json` (das Tagesbriefing bleibt vollständig
  sichtbar, auch wenn ein Item auf den Vortag datiert ist — wie bisher).
  „N Tage“ = Items mit `date` > Stichtag − N Tage.
- **Zeitraum-Umschalter** in der Navigation jeder Seite: `Heute · 7 Tage ·
  14 Tage · 30 Tage` — reine Links auf die jeweilige Variante derselben Seite,
  aktiver Zeitraum hervorgehoben.
- Nav-Links innerhalb einer Variante nutzen relative Pfade mit Präfix
  (`../` bzw. `7d/` etc.).
- Items je Topic werden pro Ansicht neu nummeriert: sortiert nach Impact
  absteigend, dann Datum absteigend. Radar funktioniert unverändert.
- **Lede/Summary** in Mehrtages-Ansichten: jüngste archivierte Tages-Summary
  des Topics. **Skip-Block:** nur in der Heute-Ansicht (tagesbezogen).
- **Trending:** Wochendaten, in allen Ansichten identisch gerendert.
- `meta.period` der Heute-Ansicht kommt aus `briefing.json`; für 7d/14d/30d
  wird der Zeitraum berechnet und deutsch formatiert (z.B. „4.–10. Juni 2026“).
- PDF-Ordner `site/pdf/` bleibt unberührt (das Löschen alter Dateien in
  `render.py` betrifft weiterhin nur `*.html` auf oberster Ebene plus die
  Range-Unterordner).

## Migration & Kompatibilität

- Erster Lauf: `history.json` wird automatisch aus dem aktuellen
  `briefing.json` initialisiert — keine manuelle Migration.
- Cowork-Task-Prompt und `update.py` bleiben unverändert.
- README wird um Historie/Zeiträume ergänzt.

## Fehlerbehandlung

- Nicht parsebares `date` ⇒ Fallback auf `first_seen`; Item geht nie verloren.
- Fehlende/korrupte `history.json` ⇒ Warnung, Neuaufbau aus `briefing.json`
  (schlimmster Fall: Historie ab heute neu).
- Leere Zeiträume rendern wie bisher den Leerzustand („keine eigenständigen
  Meldungen“).

## Tests

- Ingest: neues Item wird angehängt; bekanntes Item (gleiche Quell-URL) wird
  aktualisiert statt dupliziert; doppelter Lauf am selben Tag ist idempotent.
- Datums-Normalisierung `TT.MM.JJJJ` → ISO inkl. Fehlerfall.
- Zeitraum-Filter: Grenzfälle (Item genau N Tage alt, Item ohne Datum).
- Render-Smoke-Test: alle vier Varianten entstehen, Links/Präfixe stimmen.
