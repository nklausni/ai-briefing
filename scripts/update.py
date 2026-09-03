#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update.py — recherchiert die News aller Bereiche per Anthropic-API (web_search),
schreibt das Ergebnis in data/briefing.json und rendert anschließend die Seite neu.

Die Bereiche werden parallel recherchiert; jeder Bereich hat mehrere Versuche.
Scheitern alle, bleibt der vorherige Stand dieses Bereichs erhalten. Weil sich
sein Inhalt dann nicht verändert, erkennt render.py den Bereich als unverändert
und weist auf der Seite darauf hin, statt ihn als aktuell durchgehen zu lassen.

Voraussetzungen:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

Aufruf:
    python3 scripts/update.py                 # letzte 24 Stunden
    ZEITRAUM="letzte 7 Tage" python3 scripts/update.py
    python3 scripts/update.py --dry-run       # ohne API, schreibt in ein Temp-Verzeichnis

Umgebungsvariablen:
    ANTHROPIC_API_KEY  Pflicht im Echtbetrieb.
    CLAUDE_MODEL       optional, sonst DEFAULT_MODEL unten.
    ZEITRAUM           optional, sonst "letzte 24 Stunden".
    MAX_SEARCHES       optional, Obergrenze Websuchen je Bereich (Default 6).
    MAX_PARALLEL       optional, gleichzeitige Bereiche (Default 4).

Exit-Code 1 nur, wenn KEIN Bereich aktualisiert werden konnte. Bei Teilausfall
bleibt der Code 0, damit die erfolgreichen Bereiche veröffentlicht werden; der
Ausfall steht dann in der Zusammenfassung am Ende und auf der Seite.
"""

import os, re, sys, json, time, shutil, datetime, tempfile, subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "briefing.json"
RENDER = ROOT / "scripts" / "render.py"

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or "claude-sonnet-5"
ZEITRAUM = os.environ.get("ZEITRAUM", "").strip() or "letzte 24 Stunden"
MAX_SEARCHES = int(os.environ.get("MAX_SEARCHES", "").strip() or "6")
MAX_PARALLEL = int(os.environ.get("MAX_PARALLEL", "").strip() or "4")

WEB_SEARCH_TOOL = "web_search_20260209"
MAX_TOKENS = 16000

# Versuche je Bereich. True = mit Structured Outputs (das Schema erzwingt
# gültiges JSON), False = freier Text als Rückfall. Der letzte Versuch fällt
# absichtlich zurück: sollte das Schema mit dem web_search-Tool oder einem
# älteren, per CLAUDE_MODEL gesetzten Modell nicht zusammengehen, liefert der
# Bereich trotzdem Daten statt auszufallen.
ATTEMPT_MODES = (True, True, False)
RETRY_SLEEP = 4.0

ALLOWED_CATS = {"modelle", "tools", "agents", "lokal", "security", "business"}
MONTHS_DE = ("", "Januar", "Februar", "März", "April", "Mai", "Juni",
             "Juli", "August", "September", "Oktober", "November", "Dezember")

# Bevorzugte Quellen (an die Themenlandkarte aus dem Second Brain angelehnt).
QUELLEN = """
Bevorzugte, verlässliche Quellen (nutze möglichst diese; sonst seriöse Fachmedien):
- simonwillison.net (Simon Willison) — Agentic Engineering, Security, Modelle
- testingcatalog.com, the-decoder.com, marktechpost.com, venturebeat.com
- anthropic.com (news/engineering), openai.com, blog.google, microsoft.ai
- arxiv.org, llm-stats.com, ollama.com, huggingface.co
- techcrunch.com, theverge.com, arstechnica.com, computerworld.com, cnbc.com
- angular.dev/blog, github.blog, thenewstack.io
"""

CATS_HINT = """
Kategorien (genau eine pro Meldung):
- modelle   : Modell-Releases und -Updates (Foundation- wie Open-Weight-Modelle)
- tools     : IDEs, Assistenten, CLIs, Plattformen
- agents    : Coding-Agenten, Agent-Frameworks, Workflows
- lokal     : On-Device-/Open-Weight-Modelle, lokal lauffähig
- security  : Sicherheit, Prompt Injection, Sandboxing, Regulierung/Governance
- business  : Markt, Finanzierung, IPOs, Lizenzen/Preise, Partnerschaften
"""


def resolve_period(raw, today):
    n = re.sub(r"\s+", " ", raw.lower())
    m = re.search(r"(\d+)\s*tag", n)
    if "24" in n or "stunde" in n:
        start = today
    elif "woche" in n:
        start = today - datetime.timedelta(days=6)
    elif m:
        start = today - datetime.timedelta(days=max(1, int(m.group(1))) - 1)
    else:
        start = today
    return start, today


def period_label(start, end):
    if start == end:
        return f"{end.day}. {MONTHS_DE[end.month]} {end.year}"
    if start.month == end.month and start.year == end.year:
        return f"{start.day}.–{end.day}. {MONTHS_DE[end.month]} {end.year}"
    return f"{start.day}. {MONTHS_DE[start.month]}–{end.day}. {MONTHS_DE[end.month]} {end.year}"


def _obj(properties, required=None):
    return {"type": "object", "additionalProperties": False,
            "required": list(required or properties), "properties": properties}


# Schema für Structured Outputs. Erzwingt serverseitig gültiges JSON in der
# erwarteten Form; `enum` deckt zugleich die Wertebereiche ab, die clean_items
# bisher nachträglich prüfen musste.
TOPIC_SCHEMA = _obj({
    "summary": {"type": "string"},
    "items": {"type": "array", "items": _obj({
        "title": {"type": "string"},
        "category": {"type": "string", "enum": sorted(ALLOWED_CATS)},
        "impact": {"type": "integer", "enum": [2, 3, 4, 5]},
        "date": {"type": "string"},
        "summary": {"type": "string"},
        "sources": {"type": "array", "items": _obj({
            "label": {"type": "string"},
            "url": {"type": "string", "format": "uri"},
        })},
    })},
    "skip": {"type": "array", "items": _obj({
        "reason": {"type": "string"},
        "text": {"type": "string"},
    })},
})


def extract_json(text):
    """JSON aus der Modell-Antwort lesen.

    Mit Structured Outputs greift der erste Zweig (die Antwort *ist* das JSON).
    Die Klammersuche bleibt für den Rückfall-Versuch ohne Schema und für den
    Fall, dass web_search der letzten Runde noch einen erklärenden Satz
    voranstellt.
    """
    t = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    starts = [i for i, c in enumerate(t) if c == "{"]
    for s in starts:
        depth = 0
        for e in range(s, len(t)):
            if t[e] == "{":
                depth += 1
            elif t[e] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[s:e + 1])
                    except Exception:
                        break
    raise ValueError("Kein gültiges JSON in der Modell-Antwort gefunden.")


def build_prompt(topic, period_text, window_start, window_end, today):
    return f"""Du bist Redakteur eines privaten AI-Briefings. Recherchiere mit dem web_search-Tool
die nennenswerten Meldungen des Bereichs im genannten Zeitraum.

Heutiges Datum: {today}.
Zeitraum: {period_text} (einschließlich {window_start} bis {window_end}).
Bereich: {topic['name']}.
Blickwinkel (so bewertest du den Impact): {topic.get('angle','')}.
{CATS_HINT}
{QUELLEN}

Regeln:
- Nutze das heutige Datum, nicht dein Gedächtnis. Verifiziere je Meldung das echte
  Veröffentlichungsdatum der Originalquelle; nimm nur Meldungen im Zeitraum auf.
- Bewerte jede Meldung nach Impact aus dem Blickwinkel des Bereichs:
  2 Nennenswert, 3 Relevant, 4 Stark, 5 Game-Changer. Routine (1) gehört NICHT in items,
  sondern als kurzer Hinweis nach "skip".
- Schreibe ruhig, jargonarm, auf Deutsch, ohne KI-Marker-Floskeln.
- War der Zeitraum leer, gib "items": [] und einen ehrlichen "summary"-Satz zurück.

Antworte am ENDE mit GENAU EINEM JSON-Objekt und NICHTS sonst (kein Markdown, keine Fences):
{{
  "summary": "ein ruhiger Lede-Satz zum Zeitraum in diesem Bereich",
  "items": [
    {{
      "title": "jargonfreie deutsche Überschrift",
      "category": "modelle|tools|agents|lokal|security|business",
      "impact": 4,
      "date": "TT.MM.JJJJ",
      "summary": "zwei bis drei ruhige Sätze",
      "sources": [{{"label": "Quellenname", "url": "https://…"}}]
    }}
  ],
  "skip": [{{"reason": "kurzer Grund", "text": "eine Zeile, warum kein eigener Eintrag"}}]
}}
Sortiere items nach impact absteigend."""


def make_client():
    """Ein Client für alle Bereiche. Der Import liegt in der Funktion, damit
    --dry-run ohne installiertes SDK läuft."""
    from anthropic import Anthropic
    return Anthropic()


def call_model(client, prompt, structured=True):
    tools = [{"type": WEB_SEARCH_TOOL, "name": "web_search", "max_uses": MAX_SEARCHES}]
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    kwargs = {"model": DEFAULT_MODEL, "max_tokens": MAX_TOKENS,
              "tools": tools, "messages": messages}
    if structured:
        kwargs["output_config"] = {"format": {"type": "json_schema",
                                              "schema": TOPIC_SCHEMA}}
    resp = client.messages.create(**kwargs)
    while getattr(resp, "stop_reason", "") == "pause_turn":
        messages.append({"role": "assistant", "content": resp.content})
        kwargs["messages"] = messages
        resp = client.messages.create(**kwargs)
    # Ein abgeschnittenes JSON würde sonst als Parse-Fehler auftauchen und die
    # eigentliche Ursache verstecken.
    if getattr(resp, "stop_reason", "") == "max_tokens":
        raise ValueError(f"Antwort in max_tokens ({MAX_TOKENS}) gelaufen, JSON unvollständig")
    return "".join(getattr(b, "text", "") for b in resp.content
                   if getattr(b, "type", "") == "text")


def research_topic(client, topic, period_text, window_start, window_end, today):
    """Recherchiert einen Bereich mit mehreren Versuchen. Wirft die letzte
    Ausnahme, wenn alle Versuche scheitern."""
    prompt = build_prompt(topic, period_text, window_start, window_end, today)
    last = None
    for attempt, structured in enumerate(ATTEMPT_MODES, start=1):
        try:
            return extract_json(call_model(client, prompt, structured=structured))
        except Exception as ex:
            last = ex
            if attempt < len(ATTEMPT_MODES):
                print(f"[retry] {topic['id']}: Versuch {attempt} fehlgeschlagen ({ex})")
                time.sleep(RETRY_SLEEP * attempt)
    raise last


def clean_items(items):
    out = []
    for e in items:
        if e.get("category") not in ALLOWED_CATS:
            continue
        try:
            imp = int(e.get("impact", 0))
        except (TypeError, ValueError):
            continue
        if imp < 2 or imp > 5:
            continue
        srcs = [s for s in (e.get("sources") or []) if str(s.get("url", "")).startswith("http")]
        if not srcs:
            continue
        out.append({
            "title": str(e.get("title", "")).strip(),
            "category": e["category"],
            "impact": imp,
            "date": str(e.get("date", "")).strip(),
            "summary": str(e.get("summary", "")).strip(),
            "sources": [{"label": str(s.get("label", "Quelle")), "url": s["url"]} for s in srcs],
        })
    out.sort(key=lambda x: -x["impact"])
    # n zuerst, damit die JSON-Datei lesbar bleibt.
    return [{"n": i, "title": e["title"], "category": e["category"], "impact": e["impact"],
             "date": e["date"], "summary": e["summary"], "sources": e["sources"]}
            for i, e in enumerate(out, 1)]


def dry_topic(topic):
    return {"summary": f"Probelauf für {topic['name']} — Platzhalter ohne echte Recherche.",
            "items": [{"title": f"{topic['name']}: Beispiel-Meldung", "category": "modelle",
                       "impact": 3, "date": datetime.date.today().strftime("%d.%m.%Y"),
                       "summary": "Platzhaltertext für den Probelauf.",
                       "sources": [{"label": "Beispiel", "url": "https://example.com"}]}],
            "skip": [{"reason": "Probelauf", "text": "Echtlauf nutzt die Anthropic-API."}]}


def apply_result(topic, data):
    """Übernimmt ein Rechercheergebnis in das Topic-Dict.

    Kein Datum je Bereich: welcher Bereich sich verändert hat, leitet
    render.py aus dem Inhalt ab (history.data_dates). Das funktioniert auch
    für die externe Aktualisierung, die dieses Script nicht benutzt.
    """
    topic["summary"] = str(data.get("summary", topic.get("summary", ""))).strip()
    topic["items"] = clean_items(data.get("items", []))
    topic["skip"] = [{"reason": str(s.get("reason", "Hinweis")), "text": str(s["text"])}
                     for s in data.get("skip", [])
                     if isinstance(s, dict) and s.get("text")]


def dry_run_sandbox():
    """Kopie von data/ in einem Temp-Verzeichnis, damit der Probelauf die
    echten Daten nicht überschreibt. Gibt (Zielpfad, Env für render.py) zurück."""
    tmp = Path(tempfile.mkdtemp(prefix="ai-briefing-dry-"))
    shutil.copytree(DATA.parent, tmp / "data",
                    ignore=shutil.ignore_patterns("*.bak", "*.bak.*"))
    print(f"Probelauf: schreibt nach {tmp}; data/ und site/ bleiben unberührt.")
    return tmp / "data" / "briefing.json", {**os.environ, "AI_BRIEFING_ROOT": str(tmp)}


def main():
    dry = "--dry-run" in sys.argv
    briefing = json.loads(DATA.read_text(encoding="utf-8"))
    out_data, render_env = (dry_run_sandbox() if dry else (DATA, None))
    today_date = datetime.date.today()
    start, end = resolve_period(ZEITRAUM, today_date)
    today = today_date.strftime("%d.%m.%Y")
    today_iso = today_date.strftime("%Y-%m-%d")

    # meta.generated ist das Datum des Laufs, topic.generated das Datum der
    # Daten. Bei Teilausfall laufen die beiden auseinander, und genau daraus
    # erzeugt der Renderer den Hinweis.
    briefing["meta"]["period"] = period_label(start, end)
    briefing["meta"]["generated"] = today_iso

    topics = briefing["topics"]
    client = None if dry else make_client()

    def research(topic):
        if dry:
            return dry_topic(topic)
        return research_topic(client, topic, briefing["meta"]["period"],
                              start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y"), today)

    # submit statt map: so bleibt ein gescheiterter Bereich auf seinen eigenen
    # Future beschränkt, statt beim Auspacken den ganzen Lauf abzubrechen.
    with ThreadPoolExecutor(max_workers=max(1, MAX_PARALLEL)) as pool:
        futures = [pool.submit(research, t) for t in topics]

    failed = []
    for topic, future in zip(topics, futures):
        try:
            apply_result(topic, future.result())
            print(f"[ok]   {topic['id']}: {len(topic['items'])} Meldung(en)")
        except Exception as ex:
            failed.append(topic["id"])
            print(f"[warn] {topic['id']}: {ex} — vorheriger Stand bleibt erhalten")

    out_data.write_text(json.dumps(briefing, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"{out_data.name} aktualisiert (Zeitraum: {briefing['meta']['period']}).")

    subprocess.run([sys.executable, str(RENDER)], check=True, env=render_env)

    if failed:
        print(f"ACHTUNG: {len(failed)} von {len(topics)} Bereichen nicht aktualisiert: "
              f"{', '.join(failed)}")
    if failed and len(failed) == len(topics):
        print("Kein einziger Bereich konnte aktualisiert werden.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
