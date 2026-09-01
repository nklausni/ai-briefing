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

    def test_rerender_is_idempotent(self):
        render.main()
        h = json.loads(history.HISTORY.read_text(encoding="utf-8"))
        self.assertEqual(len(h["items"]), 1)


if __name__ == "__main__":
    unittest.main()
