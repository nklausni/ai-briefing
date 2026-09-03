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
            for page in ("index.html", "ai-news.html"):
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
        # "Überspringen kannst du" ist die Überschrift des Skip-Blocks (das Wort
        # "Überspringen" allein steht auch in der Impact-Skala jeder Seite).
        root = (render.SITE / "ai-news.html").read_text(encoding="utf-8")
        self.assertIn("Überspringen kannst du", root)
        sub = (render.SITE / "7d" / "ai-news.html").read_text(encoding="utf-8")
        self.assertNotIn("Überspringen kannst du", sub)

    def test_switcher_and_period_in_header_meta(self):
        for page in ("index.html", "ai-news.html"):
            root = (render.SITE / page).read_text(encoding="utf-8")
            self.assertNotIn("Zeitraum: ", root, page)   # alte Label-Zeile bleibt weg
            # Umschalter samt Periodenzeile steht im meta-right-Block
            meta_block = root.split('class="meta-right"', 1)[1].split("</header>", 1)[0]
            self.assertIn('<nav class="range-sw">', meta_block, page)
            self.assertIn('<div class="range-period">9.–10. Juni 2026</div>',
                          meta_block, page)
        sub = (render.SITE / "7d" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="range-period">4.–10. Juni 2026</div>', sub)

    def test_generated_date_appears_in_every_page_footer(self):
        expected = "Zuletzt aktualisiert: 10. Juni 2026"
        for sub in ("", "7d", "14d", "30d"):
            for page in ("index.html", "ai-news.html"):
                rendered = (render.SITE / sub / page).read_text(encoding="utf-8")
                footer = rendered.split('<div class="footer">', 1)[1].split("</div>", 1)[0]
                self.assertIn(expected, footer, f"fehlt: {sub}/{page}")

    def test_footer_omits_update_text_for_missing_or_invalid_generated_date(self):
        for generated in (None, "", "10.06.2026", "2026-02-30"):
            meta = {"disclaimer": "D."}
            if generated is not None:
                meta["generated"] = generated
            with self.subTest(generated=generated):
                self.assertNotIn("Zuletzt aktualisiert:", render.footer_html(meta))

    def test_rerender_is_idempotent(self):
        render.main()
        h = json.loads(history.HISTORY.read_text(encoding="utf-8"))
        self.assertEqual(len(h["items"]), 1)


class TestSharedStylesheet(unittest.TestCase):
    """Das CSS liegt in site/style.css statt 36-mal inline in den Seiten."""

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

    def test_stylesheet_written_once(self):
        css = render.SITE / "style.css"
        self.assertTrue(css.exists())
        self.assertIn("--blue:#0075de", css.read_text(encoding="utf-8"))

    def test_pages_link_stylesheet_with_correct_depth(self):
        root = (render.SITE / "ai-news.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="stylesheet" href="style.css">', root)
        for sub in ("7d", "14d", "30d"):
            page = (render.SITE / sub / "index.html").read_text(encoding="utf-8")
            self.assertIn('<link rel="stylesheet" href="../style.css">', page)

    def test_no_inline_style_block_remains(self):
        for sub in ("", "7d"):
            for page in ("index.html", "ai-news.html"):
                rendered = (render.SITE / sub / page).read_text(encoding="utf-8")
                self.assertNotIn("<style>", rendered, f"{sub}/{page}")


class TestStaleTopicMarking(unittest.TestCase):
    """Ein Bereich, dessen Meldungen der Lauf nicht verändert hat, muss
    sichtbar sein. Der Pool bringt dafür einen älteren Fingerprint mit,
    der zum unveränderten Inhalt passt."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "data").mkdir()
        (self.tmp / "data" / "briefing.json").write_text(
            json.dumps(BRIEFING, ensure_ascii=False), encoding="utf-8")
        self._orig = (render.DATA, render.SITE, history.HISTORY)
        render.DATA = self.tmp / "data" / "briefing.json"
        render.SITE = self.tmp / "site"
        history.HISTORY = self.tmp / "data" / "history.json"
        history.HISTORY.write_text(json.dumps({
            "items": [], "summaries": [],
            "fingerprints": {"ai-news": {
                "hash": history.fingerprint(BRIEFING["topics"][0]),
                "date": "2026-06-08",           # Lauf ist der 10.06.
            }},
        }), encoding="utf-8")
        render.main()

    def tearDown(self):
        render.DATA, render.SITE, history.HISTORY = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_notice_on_topic_page(self):
        page = (render.SITE / "ai-news.html").read_text(encoding="utf-8")
        self.assertIn("Die Meldungen dieses Bereichs sind seit dem 8. Juni 2026 "
                      "unverändert (seit 2 Tagen).", page)

    def test_badge_on_overview_card(self):
        page = (render.SITE / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="ov-stale">Unverändert seit 8. Juni 2026</div>', page)

    def test_item_count_stays_visible(self):
        page = (render.SITE / "index.html").read_text(encoding="utf-8")
        self.assertIn('<span class="ov-count">1 Meldung</span>', page)

    def test_not_shown_in_range_views(self):
        # Die Zeitraum-Ansichten zeigen Meldungen mehrerer Tage aus dem Pool;
        # dort wäre der Hinweis irreführend.
        for sub in ("7d", "14d", "30d"):
            for page in ("index.html", "ai-news.html"):
                rendered = (render.SITE / sub / page).read_text(encoding="utf-8")
                self.assertNotIn("unverändert", rendered, f"{sub}/{page}")


class TestStaleDetection(unittest.TestCase):
    def test_stale_when_data_older_than_run(self):
        self.assertTrue(render.is_stale({"_data_date": "2026-06-08"},
                                        {"generated": "2026-06-10"}))

    def test_not_stale_when_equal(self):
        self.assertFalse(render.is_stale({"_data_date": "2026-06-10"},
                                         {"generated": "2026-06-10"}))

    def test_missing_data_date_is_not_stale(self):
        # Unbekannt ist nicht dasselbe wie alt.
        self.assertFalse(render.is_stale({}, {"generated": "2026-06-10"}))

    def test_invalid_dates_are_not_stale(self):
        self.assertFalse(render.is_stale({"_data_date": "08.06.2026"},
                                         {"generated": "2026-06-10"}))
        self.assertFalse(render.is_stale({"_data_date": "2026-06-08"}, {}))

    def test_age_text_singular(self):
        self.assertEqual(
            render.stale_age_text({"_data_date": "2026-06-09", "items": [{}]},
                                  {"generated": "2026-06-10"}),
            "seit dem 9. Juni 2026 unverändert (1 Tag)")

    def test_age_text_for_topic_without_items(self):
        # "unverändert" passt nicht auf einen Bereich, der nie Meldungen hatte.
        self.assertEqual(
            render.stale_age_text({"_data_date": "2026-06-08", "items": []},
                                  {"generated": "2026-06-10"}),
            "ohne Meldungen seit dem 8. Juni 2026 (2 Tage)")

    def test_notice_wording_for_topic_without_items(self):
        html = render.stale_notice_html(
            {"_data_date": "2026-06-08", "items": []},
            {"generated": "2026-06-10"}, "today")
        self.assertIn("keine Meldungen bekommen (seit 2 Tagen)", html)
        self.assertNotIn("unverändert", html)


if __name__ == "__main__":
    unittest.main()
