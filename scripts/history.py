#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
history.py — kumulativer Item-Pool des AI-Briefings (data/history.json).

Beim Rendern werden die Items des aktuellen briefing.json dedupliziert in den
Pool gemerged (Ingest, idempotent). Aus dem Pool lassen sich Zeitraum-Ansichten
(7/14/30 Tage) filtern. Keine Abhängigkeiten außer der Standardbibliothek.
"""

import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.json"

MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]


def parse_date(s):
    """'09.06.2026' oder '2026-06-09' → ISO-String; sonst None."""
    if not s:
        return None
    s = str(s).strip()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime.date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    return None


def display_date(iso):
    """ISO → 'TT.MM.JJJJ' für die Anzeige."""
    d = datetime.date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def normalize_url(url):
    """URL ohne Schema, Query, Fragment, Trailing-Slash — für den Dedup-Vergleich."""
    u = str(url).strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = u.split("?", 1)[0].split("#", 1)[0]
    return u.rstrip("/")


def normalize_title(title):
    """Titel lowercase, ohne Satzzeichen, Whitespace kollabiert."""
    t = str(title).lower()
    t = re.sub(r"[^\w\s]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def load_history():
    """Pool laden; bei fehlender/korrupter Datei leerer Pool (Warnung)."""
    if HISTORY.exists():
        try:
            h = json.loads(HISTORY.read_text(encoding="utf-8"))
            if isinstance(h, dict) and isinstance(h.get("items"), list) \
                    and isinstance(h.get("summaries"), list):
                return h
            print("Warnung: history.json hat unerwartetes Format — wird neu aufgebaut.")
        except (json.JSONDecodeError, OSError):
            print("Warnung: history.json unlesbar — wird neu aufgebaut.")
    return {"items": [], "summaries": []}


def save_history(history):
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")


def _source_urls(item):
    return {normalize_url(s["url"]) for s in item.get("sources") or [] if s.get("url")}


def _similar_titles(ta, tb):
    """Sind zwei normalisierte Titel ähnlich genug, um dieselbe Meldung zu sein?

    Wird nur gerufen, wenn die Items bereits eine Quell-URL teilen. Muss
    Folge-Berichterstattung mit umformuliertem Titel erkennen (→ True), aber
    verschiedene Meldungen zur selben Ankündigung auseinanderhalten (→ False).

    Jaccard-Ähnlichkeit der Wortmengen; 0.5 trennt die beiden Fälle in den
    Tests deutlich (≈0.57 vs. ≈0.0).
    """
    wa, wb = set(ta.split()), set(tb.split())
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= 0.5


def _same_item(a, b):
    """Dieselbe Meldung? Identischer normalisierter Titel — oder gemeinsame
    Quell-URL UND ähnlicher Titel (eine Ankündigung kann mehrere
    eigenständige Items speisen, die URL allein genügt daher nicht)."""
    ta, tb = normalize_title(a.get("title", "")), normalize_title(b.get("title", ""))
    if bool(ta) and ta == tb:
        return True
    if _source_urls(a) & _source_urls(b):
        return _similar_titles(ta, tb)
    return False


def _merge_sources(old, new):
    seen, out = set(), []
    for s in (old or []) + (new or []):
        key = normalize_url(s.get("url", ""))
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def ingest(history, briefing):
    """Merged das aktuelle briefing.json in den Pool. Idempotent. Gibt history zurück."""
    generated = parse_date(briefing.get("meta", {}).get("generated")) \
        or datetime.date.today().isoformat()
    for topic in briefing.get("topics", []):
        tid = topic["id"]
        for item in topic.get("items", []):
            incoming = {
                "topic_id": tid,
                "title": item.get("title", ""),
                "category": item.get("category", ""),
                "impact": int(item.get("impact", 0)),
                "date": parse_date(item.get("date")) or generated,
                "summary": item.get("summary", ""),
                "sources": item.get("sources") or [],
                "first_seen": generated,
            }
            existing = next((e for e in history["items"]
                             if e["topic_id"] == tid and _same_item(e, incoming)), None)
            if existing:
                # Neuere Fassung gewinnt; Quellen vereinigt; ältestes Datum bleibt.
                existing.update(
                    title=incoming["title"], summary=incoming["summary"],
                    impact=incoming["impact"], category=incoming["category"],
                    sources=_merge_sources(existing.get("sources"), incoming["sources"]),
                    date=min(existing["date"], incoming["date"]),
                    first_seen=min(existing["first_seen"], incoming["first_seen"]),
                )
            else:
                history["items"].append(incoming)
        history["summaries"] = [s for s in history["summaries"]
                                if not (s["topic_id"] == tid and s["date"] == generated)]
        history["summaries"].append({
            "topic_id": tid, "date": generated,
            "summary": topic.get("summary", ""), "skip": topic.get("skip") or [],
        })
    return history


def items_for_range(history, topic_id, end_iso, days):
    """Items eines Topics der letzten `days` Tage (inkl. end_iso),
    sortiert nach Impact ↓ dann Datum ↓, neu nummeriert ab 1,
    Datum für die Anzeige als TT.MM.JJJJ."""
    end = datetime.date.fromisoformat(end_iso)
    start = (end - datetime.timedelta(days=days - 1)).isoformat()
    picked = [e for e in history["items"]
              if e["topic_id"] == topic_id and start <= e["date"] <= end_iso]
    picked.sort(key=lambda e: e["date"], reverse=True)
    picked.sort(key=lambda e: -int(e.get("impact", 0)))   # stabil → Datum bleibt Tiebreaker
    out = []
    for i, e in enumerate(picked, 1):
        c = dict(e)
        c["n"] = i
        c["date"] = display_date(e["date"])
        out.append(c)
    return out


def latest_summary(history, topic_id, end_iso):
    """Jüngste archivierte Tages-Summary eines Topics bis einschließlich end_iso."""
    cands = [s for s in history["summaries"]
             if s["topic_id"] == topic_id and s["date"] <= end_iso]
    if not cands:
        return ""
    return max(cands, key=lambda s: s["date"]).get("summary", "")


def format_period(end_iso, days):
    """Deutscher Zeitraum, z.B. '4.–10. Juni 2026' oder '12. Mai – 10. Juni 2026'."""
    end = datetime.date.fromisoformat(end_iso)
    start = end - datetime.timedelta(days=days - 1)
    if start.year != end.year:
        return (f"{start.day}. {MONTHS_DE[start.month - 1]} {start.year} – "
                f"{end.day}. {MONTHS_DE[end.month - 1]} {end.year}")
    if start.month != end.month:
        return (f"{start.day}. {MONTHS_DE[start.month - 1]} – "
                f"{end.day}. {MONTHS_DE[end.month - 1]} {end.year}")
    return f"{start.day}.–{end.day}. {MONTHS_DE[end.month - 1]} {end.year}"
