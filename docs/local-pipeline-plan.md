# Lokale Briefing-Pipeline mit Qwen 3.6 — Implementierungsplan

Stand: 2026-06-09 · Ziel: tägliche Befüllung von `data/briefing.json` **ohne
Anthropic-API**, vollständig lokal auf dem AI-Server (der Qwen 3.6 hostet),
ausgelöst per **systemd-Timer/Cron**. Datenschutz: außer den (öffentlichen)
Quell-Abrufen verlässt nichts die Maschine.

## Grundprinzip: Sammeln ≠ Synthese

Das lokale Modell kann nicht selbst im Web suchen und soll keine Tools
orchestrieren. Die Pipeline trennt daher zwei Schichten:

- **Collect-Layer (deterministisch, kein LLM):** Quellen abrufen, aufs
  Datumsfenster filtern, Volltext holen → eine normalisierte Kandidatenliste.
- **Synthese-Layer (Qwen):** sieht nur den kuratierten Text und macht, was es
  gut kann — pro Bereich clustern, deduplizieren, Impact bewerten, ruhige
  deutsche Summaries, JSON nach Schema.

Vorteil: kein Tool-Calling nötig, jede Schicht einzeln testbar, modell-agnostisch.

## Modul-Layout (Vorschlag)

```
scripts/
  llm.py            # dünner OpenAI-kompatibler Client (base_url, model, JSON-Mode)
  collect/
    rss.py          # Feeds der Quellenliste pollen, Datumsfilter, Volltext
    trending.py     # requests-Fetcher fürs Trending-HTML + vorhandener Parser
    obsidian.py     # Collana-Ordner lesen, Notizen im Fenster extrahieren
    collect.py      # orchestriert alles → candidates.json
  synthesize.py     # candidates.json + Prompt → Qwen → briefing.json (validiert)
  pipeline.py       # archive → collect → synthesize → validate → render → deploy
  render.py         # UNVERÄNDERT
  fetch_trending.py # UNVERÄNDERT (Parser wird von collect/trending.py genutzt)
config/
  sources.yaml      # Feed-URLs je Bereich, Fenstergröße, Modellname, Endpoint
data/
  briefing.json     # Output wie bisher
  archive/          # Tagesausgaben (für History-Feature)
```

## Datenfluss

1. **collect.py**
   - Pro Quelle in `sources.yaml`: RSS holen (`feedparser`), Einträge mit
     `published` im Fenster `[meta.generated_letzter_Lauf … heute]` behalten.
   - Volltext: Artikel-URL holen, Boilerplate strippen
     (`trafilatura`/`readability`), auf ~2–4k Token kürzen.
   - Trending: HTML holen (`requests`) → `fetch_trending.py`-Parser → Repos.
   - Obsidian: Collana-Ordner, Notizen mit Datum im Fenster, Links extrahieren.
   - Output `candidates.json`: Liste von
     `{source, url, title, published, text, topic_hints}`.
2. **synthesize.py**
   - Pro Bereich (8×) **ein** Qwen-Aufruf mit: Bereichs-`angle`, grob
     vorgefilterten Kandidaten, Schema, einem Few-shot-Beispiel.
   - JSON erzwingen (`format:"json"` bzw. Grammar) → valides `items[]`.
   - Dedup über URL/Titel, Impact 2–5, deutsche Summaries, **Quellen nur aus
     den Kandidaten** (keine erfundenen URLs).
   - Zusammensetzen zu vollständigem `briefing.json` (`meta.period/generated`,
     `topics`, `trending`).
3. **pipeline.py**: Vortag nach `data/archive/<datum>.json` sichern → collect →
   synthesize → Schema-Validierung → `render.py` → Auslieferung (rsync in den
   Nginx-Webroot). Mit Logging.

## Qwen-Anbindung (`llm.py`)

- OpenAI-kompatibel: `base_url` z.B. `http://<ai-server>:11434/v1` (Ollama;
  vLLM/LM-Studio analog), `model="qwen3.6:27b"`.
- JSON erzwingen: Ollama `format:"json"`, bei vLLM JSON-Schema/GBNF-Grammar.
- Robust: niedrige Temperatur (0.2–0.4), Timeout, Retry, großzügige
  `max_tokens`.
- Prompt-Disziplin spiegelt den bestehenden Task: „nur aus gelieferten
  Kandidaten, keine URLs erfinden, leeres `items[]` an ruhigen Tagen erlaubt".

## Qualitäts- & Halluzinations-Sicherungen

- **Quellen-Whitelist:** `synthesize.py` verwirft jedes Item, dessen
  `sources`-URLs nicht in den Kandidaten vorkommen.
- **Datumsfenster im Code erzwungen**, nicht dem Modell überlassen.
- **`jsonschema`-Validierung** der kompletten `briefing.json` vor `render.py`;
  bei Fehler Retry, sonst Abbruch ohne Überschreiben.
- Optional ein zweiter „Kritiker"-Pass (gleiche Qwen) für Impact/Doppler.

## Quellen über RSS (kein Such-API nötig)

Die bevorzugten Medien (simonwillison, the-decoder, MarkTechPost, The Verge,
Ars Technica, TechCrunch, github.blog, thenewstack.io …) bieten fast alle
RSS-Feeds. `sources.yaml` mappt Feed-URL → Bereich(e). Eine offene
Such-Entdeckung entfällt damit, aber für ein kuratiertes Briefing ist die feste
Quellenliste ohnehin der Kern. GitHub Trending kommt über den Parser, der
Second Brain über den Ordner.

## Scheduling & Betrieb (systemd-Timer)

- `ai-briefing.service` (Type=oneshot, `ExecStart=…/pipeline.py`,
  `EnvironmentFile` mit Endpoint/Pfaden) + `ai-briefing.timer`
  (`OnCalendar=*-*-* 07:00`, `Persistent=true` → holt verpasste Läufe nach).
  Robuster als Cron, Logs via journald.
- Fehler-Benachrichtigung (Mail/Matrix/Healthchecks-Ping).
- `venv` oder Container; Abhängigkeiten rein offen: `feedparser`,
  `trafilatura`, `requests`, `jsonschema`, `pyyaml` — keine proprietären SDKs.

## Auslieferung

- Nach dem Lauf `rsync site/` → Nginx-Webroot (intern), Zugriffsschutz per
  Basic-Auth/VPN. Archiv-Seiten (History-Feature) werden mitgerendert.

## Offene Punkte (von dir)

1. **Endpoint + Modellname exakt:** Ollama oder vLLM? Host/Port, evtl.
   API-Key/Reverse-Proxy?
2. **RSS-Feeds:** Ich bereite eine `sources.yaml`-Vorlage mit Feed-URLs der
   bevorzugten Quellen vor — du bestätigst/ergänzt.
3. **Obsidian-Vault:** liegt der Collana-Ordner auf dem AI-Server oder muss er
   gemountet/synchronisiert werden?
4. **History gleich mit?** Archiv-Schritt direkt in `pipeline.py`, oder separat
   nach dem Render-Umbau?
5. **Budget pro Bereich:** wie viele Kandidaten max. an Qwen (Token-Länge).

## Umsetzungsreihenfolge (Vorschlag)

1. `llm.py` + Smoke-Test gegen euren Qwen (ein Bereich, Dummy-Kandidaten →
   valides `items[]`).
2. `collect/rss.py` mit 3–4 Feeds, Datumsfilter, Volltext.
3. `synthesize.py` mit Schema-Validierung + Quellen-Whitelist.
4. `collect/trending.py` (requests-Fetcher + Parser) + `collect/obsidian.py`.
5. `pipeline.py` + systemd-Unit + Auslieferung.
6. History/Archiv integrieren.
