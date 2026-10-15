"""Public overview copy is news, not the publisher's execution log."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render


OFFENDING_INTRO = (
    "Ergänzter Tagesstand vom 15. Oktober: Die bisherige Ausgabe bleibt vollständig "
    "erhalten und wird um neu geprüfte sowie nachgeholte Entwicklungen erweitert. "
    "Originaldaten, eingeschränkte Zugänge und Preview-/GA-Meilensteine bleiben "
    "getrennt; verbleibende Quellenlücken stehen im Tagesaudit."
)


class TestPublicIntro(unittest.TestCase):
    def test_execution_log_is_rejected(self):
        for text in (OFFENDING_INTRO, "Details stehen im Tagesaudit.",
                     "Die bisherige Ausgabe bleibt erhalten.",
                     "Heute ergänzen wir nachgeholte Entwicklungen.",
                     "Verbleibende Quellenlücken sind dokumentiert."):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "meta.intro"):
                    render.build_overview({"meta": {"intro": text}, "topics": []})

    def test_substantive_summary_keeps_release_caveats_and_escaping(self):
        text = "HydraFusion Max bleibt Research Preview; A&B ist noch nicht GA."
        self.assertEqual(render.public_intro_html({"intro": text}),
                         '<p class="lede">HydraFusion Max bleibt Research Preview; '
                         'A&amp;B ist noch nicht GA.</p>')

    def test_absent_summary_omits_paragraph(self):
        for meta in ({}, {"intro": ""}, {"intro": "  "}):
            self.assertEqual(render.public_intro_html(meta), "")

    def test_current_issue_has_no_internal_intro(self):
        root = Path(__file__).resolve().parents[2]
        meta = json.loads((root / "data/briefing.json").read_text())["meta"]
        self.assertNotEqual(meta.get("intro"), OFFENDING_INTRO)
        self.assertNotIn("Tagesaudit", meta.get("intro", ""))
        render.public_intro_html(meta)
