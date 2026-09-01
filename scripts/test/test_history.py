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

    def test_dedup_by_shared_source_url_and_similar_title(self):
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing(
            [_item(title="Claude Fable 5 veröffentlicht", impact=3)]))
        history.ingest(h, _briefing(
            [_item(title="Claude Fable 5 veröffentlicht – Details zur Preisstruktur",
                   impact=4, url="https://example.com/a/?utm=feed", date="10.06.2026")],
            generated="2026-06-11"))
        self.assertEqual(len(h["items"]), 1)
        e = h["items"][0]
        self.assertEqual(e["title"],                    # neuere Fassung gewinnt
                         "Claude Fable 5 veröffentlicht – Details zur Preisstruktur")
        self.assertEqual(e["impact"], 4)
        self.assertEqual(e["date"], "2026-06-09")      # ältestes Datum bleibt
        self.assertEqual(e["first_seen"], "2026-06-10")
        self.assertEqual(len(e["sources"]), 1)         # URL-dedupliziert

    def test_distinct_items_sharing_announcement_url_not_merged(self):
        # Eine große Ankündigung erzeugt mehrere eigenständige Items mit
        # derselben Primärquelle — die dürfen NICHT zusammengelegt werden.
        h = {"items": [], "summaries": []}
        history.ingest(h, _briefing([
            _item(title="Fable 5 mit neuen Sicherheits-Klassifizierern",
                  url="https://anthropic.com/news/fable-5"),
            _item(title="Dual-Use bei Biologie und neue 30-Tage-Datenaufbewahrung",
                  url="https://anthropic.com/news/fable-5"),
        ]))
        self.assertEqual(len(h["items"]), 2)

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


if __name__ == "__main__":
    unittest.main()
