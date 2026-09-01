#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update.py — recherchiert die News der vier Bereiche per Anthropic-API (web_search),
schreibt das Ergebnis in data/briefing.json und rendert anschließend die Seite neu.

Damit ist das Update vollständig per Script/Cron aufrufbar — ohne Cowork.

Voraussetzungen:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

Aufruf:
    python3 scripts/update.py                 # letzte 24 Stunden
    ZEITRAUM="letzte 7 Tage" python3 scripts/update.py
    python3 scripts/update.py --dry-run       # ohne API: nur Pipeline/Render testen

Umgebungsvariablen:
    ANTHROPIC_API_KEY  Pflicht im Echtbetrieb.
    CLAUDE_MODEL       optional, sonst DEFAULT_MODEL unten.
    ZEITRAUM           optional, sonst "letzte 24 Stunden".
    MAX_SEARCHES       optional, Obergrenze Websuchen je Bereich (Default 6).
"""

import os, re, sys, json, datetime, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "briefing.json"
RENDER = ROOT / "scripts" / "render.py"

DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or "claude-sonnet-4-6"
ZEITRAUM = os.environ.get("ZEITRAUM", "").strip() or "letzte 24 Stunden"
MAX_SEARCHES = int(os.environ.get("MAX_SEARCHES", "").strip() or "6")

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


def extract_json(text):
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


def call_model(prompt):
    from anthropic import Anthropic
    client = Anthropic()
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_SEARCHES}]
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    kwargs = {"model": DEFAULT_MODEL, "max_tokens": 4000, "tools": tools, "messages": messages}
    resp = client.messages.create(**kwargs)
    while getattr(resp, "stop_reason", "") == "pause_turn":
        messages.append({"role": "assistant", "content": resp.content})
        kwargs["messages"] = messages
        resp = client.messages.create(**kwargs)
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")


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
    for i, e in enumerate(out, 1):
        e["n"] = i
    for e in out:  # n nach vorne sortieren (Lesbarkeit der JSON)
        e_keys = ["n", "title", "category", "impact", "date", "summary", "sources"]
        for k in list(e.keys()):
            if k not in e_keys:
                e.pop(k)
    return [{"n": e["n"], "title": e["title"], "category": e["category"], "impact": e["impact"],
             "date": e["date"], "summary": e["summary"], "sources": e["sources"]} for e in out]


def dry_topic(topic):
    return {"summary": f"Probelauf für {topic['name']} — Platzhalter ohne echte Recherche.",
            "items": [{"title": f"{topic['name']}: Beispiel-Meldung", "category": "modelle",
                       "impact": 3, "date": datetime.date.today().strftime("%d.%m.%Y"),
                       "summary": "Platzhaltertext für den Probelauf.",
                       "sources": [{"label": "Beispiel", "url": "https://example.com"}]}],
            "skip": [{"reason": "Probelauf", "text": "Echtlauf nutzt die Anthropic-API."}]}


def main():
    dry = "--dry-run" in sys.argv
    briefing = json.loads(DATA.read_text(encoding="utf-8"))
    today_date = datetime.date.today()
    start, end = resolve_period(ZEITRAUM, today_date)
    today = today_date.strftime("%d.%m.%Y")

    briefing["meta"]["period"] = period_label(start, end)
    briefing["meta"]["generated"] = today_date.strftime("%Y-%m-%d")

    for topic in briefing["topics"]:
        try:
            if dry:
                data = dry_topic(topic)
            else:
                text = call_model(build_prompt(topic, briefing["meta"]["period"],
                                               start.strftime("%d.%m.%Y"),
                                               end.strftime("%d.%m.%Y"), today))
                data = extract_json(text)
            topic["summary"] = str(data.get("summary", topic.get("summary", ""))).strip()
            topic["items"] = clean_items(data.get("items", []))
            skip = []
            for s in data.get("skip", []):
                if isinstance(s, dict) and s.get("text"):
                    skip.append({"reason": str(s.get("reason", "Hinweis")), "text": str(s["text"])})
            topic["skip"] = skip
            print(f"[ok]   {topic['id']}: {len(topic['items'])} Meldung(en)")
        except Exception as ex:
            print(f"[warn] {topic['id']}: {ex} — vorheriger Stand bleibt erhalten")

    DATA.write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"briefing.json aktualisiert (Zeitraum: {briefing['meta']['period']}).")

    subprocess.run([sys.executable, str(RENDER)], check=True)


if __name__ == "__main__":
    main()
