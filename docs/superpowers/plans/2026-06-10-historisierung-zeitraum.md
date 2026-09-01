# Historisierung & Zeitraum-Ansichten — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tägliche Briefings werden in einem kumulativen Pool (`data/history.json`) historisiert; die Seite bekommt vier statisch vorgerenderte Zeitraum-Ansichten (Heute · 7 · 14 · 30 Tage) mit Umschalter in der Navigation.

**Architecture:** Neues Modul `scripts/history.py` (Ingest/Dedup/Filter/Periodenformat, nur stdlib). `scripts/render.py` ruft vor dem Rendern den Ingest auf und rendert danach die komplette Seite viermal: nach `site/` (Heute, wie bisher) sowie `site/7d/`, `site/14d/`, `site/30d/`. `data/briefing.json` bleibt unveränderte Schnittstelle des täglichen Updates.

**Tech Stack:** Python 3 Standardbibliothek (json, re, datetime, unittest). Kein JavaScript im Output.

**Spec:** `docs/superpowers/specs/2026-06-10-historisierung-zeitraum-design.md`

**Hinweis Git:** Das Projektverzeichnis ist kein Git-Repository — Commit-Schritte entfallen. Verifikation erfolgt über Testläufe.

---

## Dateistruktur

- Create: `scripts/history.py` — Pool-Verwaltung: Datums-/URL-/Titel-Normalisierung, Ingest (idempotent), Zeitraum-Filter, deutsches Periodenformat. Eine Verantwortung: alles rund um `data/history.json`.
- Create: `scripts/test/test_history.py` — Unit-Tests für history.py.
- Create: `scripts/test/test_render.py` — Smoke-Test des Renderers (4 Varianten, Links).
- Modify: `scripts/render.py` — Ingest-Aufruf in `main()`, Zeitraum-Umschalter, Builder bekommen `range_key`-Parameter, Vier-Varianten-Rendering.
- Modify: `README.md` — Abschnitte Aufbau/Inhalt um Historie & Zeiträume ergänzen.
- Generated: `data/history.json` (beim ersten Lauf), `site/{7d,14d,30d}/*.html`.

Alle Testläufe aus dem Projekt-Root:

```bash
cd "/Users/nikoklausnitzer/Developer/ai-briefing/AI Briefing"
```

---

### Task 1: `history.py` — Normalisierungs-Helfer

**Files:**
- Create: `scripts/history.py`
- Test: `scripts/test/test_history.py`

- [ ] **Step 1: Failing Tests schreiben**

`scripts/test/test_history.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import history


class TestParseDate(unittest.TestCase):
    def test_german_format(self):
        self.assertEqual(history.parse_date("09.06.2026"), "2026-06-09")

    def test_german_single_digit(self):
        self.assertEqual(history.parse_date("9.6.2026"), "2026-06-09")

    def test_iso_passthrough(self):
        self.assertEqual(history.parse_date("2026-06-09"), "2026-06-09")

    def test_invalid(self):
        self.assertIsNone(history.parse_date("Juni 2026"))
        self.assertIsNone(history.parse_date("32.13.2026"))
        self.assertIsNone(history.parse_date(""))
        self.assertIsNone(history.parse_date(None))


class TestDisplayDate(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(history.display_date("2026-06-09"), "09.06.2026")


class TestNormalizeUrl(unittest.TestCase):
    def test_strips_scheme_query_fragment_slash(self):
        self.assertEqual(
            history.normalize_url("https://Example.com/a/b/?utm=x#top"),
            "example.com/a/b")

    def test_equal_after_normalization(self):
        a = history.normalize_url("https://example.com/news/")
        b = history.normalize_url("http://example.com/news?ref=rss")
        self.assertEqual(a, b)


class TestNormalizeTitle(unittest.TestCase):
    def test_case_punctuation_whitespace(self):
        self.assertEqual(
            history.normalize_title("Anthropic veröffentlicht  Claude Fable 5!"),
            "anthropic veröffentlicht claude fable 5")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python3 scripts/test/test_history.py -v`
Expected: FAIL/ERROR mit `ModuleNotFoundError: No module named 'history'`

- [ ] **Step 3: Minimale Implementierung**

`scripts/history.py`:

```python
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
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python3 scripts/test/test_history.py -v`
Expected: alle Tests PASS (`OK`)

---

### Task 2: `history.py` — Laden/Speichern und idempotenter Ingest

**Files:**
- Modify: `scripts/history.py` (Funktionen anhängen)
- Test: `scripts/test/test_history.py` (Testklassen anhängen)

- [ ] **Step 1: Failing Tests schreiben**

In `scripts/test/test_history.py` vor dem `if __name__`-Block anhängen:

```python
def _briefing(items, generated="2026-06-10", summary="Lede.", skip=None):
    return {
        "meta": {"generated": generated},
        "topics": [{
            "id": "ai-news", "name": "AI News",
            "summary": summary, "skip": skip or [],
            "items": items,
        }],
    }


def _item(title="Meldung A", url="https://example.com/a", date="09.06.2026",
          impact=4, category="modelle", summary="Text."):
    return {"n": 1, "title": title, "category": category, "impact": impact,
            "date": date, "summary": summary,
            "sources": [{"label": "Quelle", "url": url}]}


class TestIngest(unittest.TestCase):
    def test_new_item_appended_with_iso_date_and_first_seen(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([_item()]))
        self.assertEqual(len(h["items"]), 1)
        e = h["items"][0]
        self.assertEqual(e["topic_id"], "ai-news")
        self.assertEqual(e["date"], "2026-06-09")
        self.assertEqual(e["first_seen"], "2026-06-10")

    def test_unparseable_date_falls_back_to_generated(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([_item(date="diese Woche")]))
        self.assertEqual(h["items"][0]["date"], "2026-06-10")

    def test_dedup_by_shared_source_url(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([_item(title="Alte Fassung", impact=3)]))
        history.ingest(h, _briefing(
            [_item(title="Neue Fassung", impact=4,
                   url="https://example.com/a/?utm=feed", date="10.06.2026")],
            generated="2026-06-11"))
        self.assertEqual(len(h["items"]), 1)
        e = h["items"][0]
        self.assertEqual(e["title"], "Neue Fassung")   # neuere Fassung gewinnt
        self.assertEqual(e["impact"], 4)
        self.assertEqual(e["date"], "2026-06-09")      # ältestes Datum bleibt
        self.assertEqual(e["first_seen"], "2026-06-10")
        self.assertEqual(len(e["sources"]), 1)         # URL-dedupliziert

    def test_dedup_by_normalized_title_merges_sources(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([_item(title="Claude Fable 5 ist da!")]))
        history.ingest(h, _briefing(
            [_item(title="Claude Fable 5 ist da", url="https://other.com/x")],
            generated="2026-06-11"))
        self.assertEqual(len(h["items"]), 1)
        self.assertEqual(len(h["items"][0]["sources"]), 2)  # Quellen vereinigt

    def test_same_title_different_topic_is_not_deduped(self):
        h = {"items": [], "summaries": []}
        b = _briefing([_item()])
        b["topics"].append({"id": "ai-tools", "name": "AI Tools", "summary": "",
                            "skip": [], "items": [_item(url="https://example.com/b")]})
        history.ingest(h, b)
        self.assertEqual(len(h["items"]), 2)

    def test_ingest_is_idempotent(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([_item()]))
        history.ingest(h, _briefing([_item()]))
        self.assertEqual(len(h["items"]), 1)
        self.assertEqual(len(h["summaries"]), 1)

    def test_summary_and_skip_archived_per_day(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([], summary="Tag 1",
                                    skip=[{"reason": "r", "text": "t"}]))
        history.ingest(h, _briefing([], generated="2026-06-11", summary="Tag 2"))
        self.assertEqual(len(h["summaries"]), 2)
        latest = max(h["summaries"], key=lambda s: s["date"])
        self.assertEqual(latest["summary"], "Tag 2")
        first = min(h["summaries"], key=lambda s: s["date"])
        self.assertEqual(first["skip"], [{"reason": "r", "text": "t"}])


class TestLoadSave(unittest.TestCase):
    def test_load_missing_file_returns_empty_pool(self):
        import tempfile
        old = history.HISTORY
        try:
            history.HISTORY = Path(tempfile.mkdtemp()) / "history.json"
            self.assertEqual(history.load_history(), {"items": [], "summaries": []})
        finally:
            history.HISTORY = old

    def test_save_and_load_roundtrip(self):
        import tempfile
        old = history.HISTORY
        try:
            history.HISTORY = Path(tempfile.mkdtemp()) / "history.json"
            h = {"items": [], "summaries": []}
            history.ingest(h, _briefing([_item()]))
            history.save_history(h)
            self.assertEqual(history.load_history(), h)
        finally:
            history.HISTORY = old

    def test_corrupt_file_rebuilds_empty(self):
        import tempfile
        old = history.HISTORY
        try:
            history.HISTORY = Path(tempfile.mkdtemp()) / "history.json"
            history.HISTORY.write_text("{kaputt", encoding="utf-8")
            self.assertEqual(history.load_history(), {"items": [], "summaries": []})
        finally:
            history.HISTORY = old
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python3 scripts/test/test_history.py -v`
Expected: ERROR `AttributeError: module 'history' has no attribute 'ingest'` (Task-1-Tests weiter PASS)

- [ ] **Step 3: Implementierung anhängen**

In `scripts/history.py` anhängen:

```python
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


def _same_item(a, b):
    """Dieselbe Meldung? Gemeinsame Quell-URL oder identischer normalisierter Titel."""
    if _source_urls(a) & _source_urls(b):
        return True
    ta, tb = normalize_title(a.get("title", "")), normalize_title(b.get("title", ""))
    return bool(ta) and ta == tb


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
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python3 scripts/test/test_history.py -v`
Expected: alle Tests PASS (`OK`)

---

### Task 3: `history.py` — Zeitraum-Filter und Periodenformat

**Files:**
- Modify: `scripts/history.py` (Funktionen anhängen)
- Test: `scripts/test/test_history.py` (Testklassen anhängen)

- [ ] **Step 1: Failing Tests schreiben**

In `scripts/test/test_history.py` vor dem `if __name__`-Block anhängen:

```python
class TestItemsForRange(unittest.TestCase):
    def _pool(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([
            _item(title="Alt", url="https://e.com/alt", date="01.06.2026", impact=5),
            _item(title="Genau 7 Tage", url="https://e.com/7", date="04.06.2026", impact=3),
            _item(title="Frisch hoch", url="https://e.com/f1", date="10.06.2026", impact=4),
            _item(title="Frisch niedrig", url="https://e.com/f2", date="10.06.2026", impact=2),
            _item(title="Gestern hoch", url="https://e.com/g", date="09.06.2026", impact=4),
        ]))
        return h

    def test_window_includes_exact_boundary(self):
        # 7-Tage-Fenster bis 10.06. = 04.06.–10.06. (inklusive)
        got = history.items_for_range(self._pool(), "ai-news", "2026-06-10", 7)
        self.assertEqual([e["title"] for e in got],
                         ["Frisch hoch", "Gestern hoch", "Genau 7 Tage", "Frisch niedrig"])

    def test_sorted_impact_desc_then_date_desc_and_renumbered(self):
        got = history.items_for_range(self._pool(), "ai-news", "2026-06-10", 30)
        self.assertEqual([e["n"] for e in got], [1, 2, 3, 4, 5])
        self.assertEqual(got[0]["title"], "Alt")            # Impact 5
        self.assertEqual(got[1]["title"], "Frisch hoch")    # Impact 4, neuer
        self.assertEqual(got[2]["title"], "Gestern hoch")   # Impact 4, älter

    def test_display_date_format(self):
        got = history.items_for_range(self._pool(), "ai-news", "2026-06-10", 7)
        self.assertEqual(got[0]["date"], "10.06.2026")

    def test_other_topic_empty(self):
        self.assertEqual(
            history.items_for_range(self._pool(), "ai-tools", "2026-06-10", 30), [])


class TestLatestSummary(unittest.TestCase):
    def test_returns_most_recent(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([], generated="2026-06-09", summary="Tag 1"))
        history.ingest(h, _briefing([], generated="2026-06-10", summary="Tag 2"))
        self.assertEqual(history.latest_summary(h, "ai-news", "2026-06-10"), "Tag 2")

    def test_empty_when_unknown_topic(self):
        self.assertEqual(history.latest_summary(
            {"items": [], "summaries": []}, "ai-news", "2026-06-10"), "")


class TestFormatPeriod(unittest.TestCase):
    def test_same_month(self):
        self.assertEqual(history.format_period("2026-06-10", 7), "4.–10. Juni 2026")

    def test_cross_month(self):
        self.assertEqual(history.format_period("2026-06-10", 30),
                         "12. Mai – 10. Juni 2026")

    def test_cross_year(self):
        self.assertEqual(history.format_period("2026-01-03", 7),
                         "28. Dezember 2025 – 3. Januar 2026")
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python3 scripts/test/test_history.py -v`
Expected: ERROR `AttributeError: module 'history' has no attribute 'items_for_range'`

- [ ] **Step 3: Implementierung anhängen**

In `scripts/history.py` anhängen:

```python
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
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python3 scripts/test/test_history.py -v`
Expected: alle Tests PASS (`OK`)

---

### Task 4: `render.py` — Ingest, Zeitraum-Umschalter, vier Varianten

**Files:**
- Modify: `scripts/render.py`
- Test: `scripts/test/test_render.py`

- [ ] **Step 1: Failing Smoke-Test schreiben**

`scripts/test/test_render.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import history
import render


BRIEFING = {
    "meta": {"title": "AI-Briefing", "subtitle": "Test", "period": "9.–10. Juni 2026",
             "generated": "2026-06-10", "intro": "Intro.", "disclaimer": "D.", "host": "N"},
    "topics": [{
        "id": "ai-news", "name": "AI News", "group": "Überblick",
        "angle": "Test-Blickwinkel", "summary": "Heute-Lede.",
        "items": [{"n": 1, "title": "Meldung", "category": "modelle", "impact": 4,
                   "date": "09.06.2026", "summary": "Text.",
                   "sources": [{"label": "Q", "url": "https://example.com/a"}]}],
        "skip": [{"reason": "Grund", "text": "Text"}],
    }],
    "trending": {"title": "GitHub Trending", "note": "Hinweis.",
                 "repos": [{"name": "a/b", "url": "https://github.com/a/b",
                            "language": "Python", "stars": "1k", "updated": "gestern",
                            "area": "Agents", "description": "Repo."}]},
}


class TestRenderVariants(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "data").mkdir()
        (self.tmp / "data" / "briefing.json").write_text(
            json.dumps(BRIEFING, ensure_ascii=False), encoding="utf-8")
        self._orig = (render.DATA, render.SITE, history.HISTORY)
        render.DATA = self.tmp / "data" / "briefing.json"
        render.SITE = self.tmp / "site"
        history.HISTORY = self.tmp / "data" / "history.json"
        render.main()

    def tearDown(self):
        render.DATA, render.SITE, history.HISTORY = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_four_variants_rendered(self):
        for sub in ("", "7d", "14d", "30d"):
            base = render.SITE / sub
            for page in ("index.html", "ai-news.html", "trending.html"):
                self.assertTrue((base / page).exists(), f"fehlt: {sub}/{page}")

    def test_history_json_created(self):
        h = json.loads(history.HISTORY.read_text(encoding="utf-8"))
        self.assertEqual(len(h["items"]), 1)
        self.assertEqual(h["items"][0]["date"], "2026-06-09")

    def test_range_switcher_links(self):
        root = (render.SITE / "ai-news.html").read_text(encoding="utf-8")
        self.assertIn('href="7d/ai-news.html"', root)
        self.assertIn('href="14d/ai-news.html"', root)
        sub = (render.SITE / "7d" / "ai-news.html").read_text(encoding="utf-8")
        self.assertIn('href="../ai-news.html"', sub)
        self.assertIn('href="../30d/ai-news.html"', sub)
        self.assertIn('href="../14d/ai-news.html"', sub)

    def test_range_view_filters_and_renumbers(self):
        sub = (render.SITE / "7d" / "ai-news.html").read_text(encoding="utf-8")
        self.assertIn("Meldung", sub)
        self.assertIn("4.–10. Juni 2026", sub)   # berechnete Periode

    def test_skip_block_only_in_today_view(self):
        root = (render.SITE / "ai-news.html").read_text(encoding="utf-8")
        self.assertIn("Überspringen", root)
        sub = (render.SITE / "7d" / "ai-news.html").read_text(encoding="utf-8")
        self.assertNotIn("Überspringen", sub)

    def test_rerender_is_idempotent(self):
        render.main()
        h = json.loads(history.HISTORY.read_text(encoding="utf-8"))
        self.assertEqual(len(h["items"]), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `python3 scripts/test/test_render.py -v`
Expected: FAIL (Varianten-Verzeichnisse existieren nicht, Switcher-Links fehlen)

- [ ] **Step 3: render.py anpassen**

Änderung A — Import ergänzen (nach `from pathlib import Path`, Zeile ~19):

```python
import history as history_mod
```

Änderung B — Zeitraum-Definition + Switcher (nach der `CSS`-Konstante einfügen):

```python
RANGES = [
    ("today", "Heute", None),
    ("7d", "7 Tage", 7),
    ("14d", "14 Tage", 14),
    ("30d", "30 Tage", 30),
]


def range_nav_html(page, active_key):
    """Zeitraum-Umschalter: Links auf dieselbe Seite in den anderen Ansichten."""
    to_root = "" if active_key == "today" else "../"
    links = []
    for key, label, _ in RANGES:
        cls = ' class="active"' if key == active_key else ""
        href = f"{to_root}{page}.html" if key == "today" else f"{to_root}{key}/{page}.html"
        links.append(f'<a href="{href}"{cls}>{label}</a>')
    return ('<nav class="nav nav-range"><span class="range-k">Zeitraum</span>'
            + "".join(links) + '</nav>')
```

Änderung C — CSS ergänzen: in der `CSS`-Konstante nach der Zeile
`.nav a.active{color:var(--wg100);font-weight:700}` einfügen:

```css
  .nav-range{margin-top:6px}
  .nav-range .range-k{color:var(--wg60);font-weight:600;margin-right:12px;font-size:11px;
    letter-spacing:0.06em;text-transform:uppercase}
```

Änderung D — `build_topic_page` bekommt `range_key="today"` als Parameter; der
Switcher wird nach der Topic-Nav eingefügt:

```python
def build_topic_page(topic, meta, topics, range_key="today"):
```

und im Template direkt nach `{nav_html(topics, topic["id"])}`:

```python
  {range_nav_html(topic["id"], range_key)}
```

Änderung E — analog `build_overview(briefing, range_key="today")`: Switcher nach
`{nav_html(topics, "index")}` einfügen als `{range_nav_html("index", range_key)}`.
Und `build_trending_page(briefing, topics, range_key="today")`: Switcher nach
`{nav_html(topics, "trending")}` als `{range_nav_html("trending", range_key)}`.

Änderung F — `main()` komplett ersetzen:

```python
def main():
    briefing = json.loads(DATA.read_text(encoding="utf-8"))

    # Ingest: aktuelles Briefing in den kumulativen Pool mergen (idempotent)
    hist = history_mod.load_history()
    history_mod.ingest(hist, briefing)
    history_mod.save_history(hist)

    SITE.mkdir(exist_ok=True)
    dirs = [SITE] + [SITE / key for key, _, _ in RANGES[1:]]
    for d in dirs:
        d.mkdir(exist_ok=True)
        for old in d.glob("*.html"):
            try:
                old.unlink()
            except OSError:
                pass  # Mount erlaubt evtl. kein unlink; write_text überschreibt ohnehin

    topics = briefing["topics"]

    # Heute-Ansicht: aktuelles Briefing unverändert (wie bisher)
    (SITE / "index.html").write_text(build_overview(briefing), encoding="utf-8")
    for t in topics:
        (SITE / f'{t["id"]}.html').write_text(
            build_topic_page(t, briefing["meta"], topics), encoding="utf-8")
    if briefing.get("trending"):
        (SITE / "trending.html").write_text(
            build_trending_page(briefing, topics), encoding="utf-8")

    # Zeitraum-Ansichten aus dem Pool
    end_iso = history_mod.parse_date(briefing["meta"].get("generated")) \
        or datetime.date.today().isoformat()
    for key, _, days in RANGES[1:]:
        rmeta = dict(briefing["meta"], period=history_mod.format_period(end_iso, days))
        rtopics = []
        for t in topics:
            rt = dict(t)
            rt["items"] = history_mod.items_for_range(hist, t["id"], end_iso, days)
            rt["summary"] = history_mod.latest_summary(hist, t["id"], end_iso) \
                or t.get("summary", "")
            rt["skip"] = []  # Skip-Block ist tagesbezogen → nur in der Heute-Ansicht
            rtopics.append(rt)
        rbriefing = {"meta": rmeta, "topics": rtopics,
                     "trending": briefing.get("trending")}
        outdir = SITE / key
        (outdir / "index.html").write_text(
            build_overview(rbriefing, range_key=key), encoding="utf-8")
        for rt in rtopics:
            (outdir / f'{rt["id"]}.html').write_text(
                build_topic_page(rt, rmeta, rtopics, range_key=key), encoding="utf-8")
        if briefing.get("trending"):
            (outdir / "trending.html").write_text(
                build_trending_page(rbriefing, rtopics, range_key=key), encoding="utf-8")

    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(len(t.get("items", [])) for t in topics)
    n_repos = len(briefing.get("trending", {}).get("repos", []))
    n_hist = len(hist["items"])
    print(f"Fertig: 4 Ansichten (Heute/7d/14d/30d), {total} Meldungen heute, "
          f"{n_hist} im Pool, {n_repos} Trending-Repos.")
    for t in topics:
        print(f"  [{t['id']}] {len(t.get('items', []))} Meldung(en) heute")
```

Hinweis: `build_overview` liest `briefing["meta"]` und `briefing["topics"]` —
für die Range-Ansichten wird das vorbereitete `rbriefing` übergeben, die
Funktion selbst braucht außer dem neuen Parameter keine Änderung. Gleiches gilt
für `build_trending_page` (nutzt `briefing["meta"]` mit der bereits ersetzten
`period`).

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python3 scripts/test/test_render.py -v` und `python3 scripts/test/test_history.py -v`
Expected: alle Tests PASS (`OK`)

- [ ] **Step 5: Echten Render-Lauf machen und Ergebnis prüfen**

```bash
python3 scripts/render.py
ls site/7d site/14d site/30d
python3 - <<'EOF'
import json
h = json.load(open("data/history.json"))
print(len(h["items"]), "Items,", len(h["summaries"]), "Summaries")
EOF
```

Expected: Erfolgsmeldung mit „4 Ansichten“, alle drei Unterordner enthalten
`index.html`, alle Topic-Seiten und `trending.html`; `history.json` enthält
die Items des aktuellen Briefings (10) und 8 Summaries. Danach
`site/index.html` im Browser öffnen und den Umschalter durchklicken.

---

### Task 5: README aktualisieren

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Abschnitt „Aufbau“ ergänzen**

Im Verzeichnisbaum unter `│   └── briefing.json …` ergänzen:

```
│   └── history.json        ← kumulativer Pool aller bisherigen Meldungen (Historie)
```

und unter `└── site/` den Hinweis ergänzen:

```
    ├── 7d/ · 14d/ · 30d/    ← Zeitraum-Ansichten (letzte 7/14/30 Tage)
```

- [ ] **Step 2: Neuen Abschnitt „Historie & Zeiträume“ einfügen** (nach „Neu generieren“)

```markdown
## Historie & Zeiträume

`render.py` merged bei jedem Lauf die Items aus `briefing.json` in den
kumulativen Pool `data/history.json` (dedupliziert über Quell-URLs bzw.
Titel; idempotent — mehrfaches Rendern erzeugt keine Duplikate). Vergangene
Meldungen gehen beim täglichen Update damit nicht mehr verloren.

Die Seite wird in vier Ansichten gerendert, umschaltbar über die Zeile
„Zeitraum“ in der Navigation (reine Links, weiterhin kein JavaScript):

- **Heute** (`site/`) — das aktuelle Tagesbriefing, wie bisher.
- **7 / 14 / 30 Tage** (`site/7d/`, `site/14d/`, `site/30d/`) — Meldungen aus
  dem Pool im jeweiligen Zeitfenster, je Topic neu nummeriert (sortiert nach
  Impact, dann Datum). Lede ist die jüngste Tages-Summary; der
  „Überspringen“-Block erscheint nur in der Heute-Ansicht.

Tests: `python3 scripts/test/test_history.py && python3 scripts/test/test_render.py`
```

- [ ] **Step 3: Verifikation**

Run: `python3 scripts/test/test_history.py && python3 scripts/test/test_render.py && python3 scripts/render.py`
Expected: beide Testläufe `OK`, Render-Lauf erfolgreich.

---

## Self-Review (durchgeführt)

- **Spec-Abdeckung:** Datenmodell/Ingest (Task 1–2), Filter/Periode (Task 3), vier Ansichten + Switcher + Skip-nur-heute + Trending überall + berechnete Periode (Task 4), Migration = automatischer Erstlauf (Task 4 Step 5), README (Task 5), Fehlerfälle: korrupte history.json (Task 2), unparsebares Datum (Task 2), leere Zeiträume rendern den vorhandenen Leerzustand (bestehender Code in `ov_card`). ✓
- **Platzhalter:** keine. ✓
- **Konsistenz:** `history_mod`-Aliase, Signaturen (`range_key`), Pfade und Testnamen stimmen zwischen den Tasks überein; `render.py` importiert `datetime` bereits (Zeile 18). ✓
