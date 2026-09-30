import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import editor_context as e
import research_pipeline as p


class EditorContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.run = Path(self.temp.name) / "run"
        p.write(self.root / "data/briefing.json", {
            "meta": {"generated": "2026-09-30"},
            "topics": [{"id": str(i), "items": []} for i in range(8)],
        })
        p.prepare(self.root, self.run, "2026-10-01")
        self.candidate = {
            "id": "candidate-1", "title": "A new model", "summary": "Verified facts.",
            "url": "https://example.org/article", "published_at": "2026-09-30",
            "evidence": [{"url": "https://example.org/article", "excerpt": "Original statement.",
                          "method": "direct", "retrieved_at": "2026-10-01T08:00:00+02:00"}],
        }
        p.write(self.run / "candidates.json", [self.candidate])

    def test_pages_cover_every_candidate_without_mutating_research(self):
        candidates = []
        for i in range(67):
            c = copy.deepcopy(self.candidate)
            c["id"] = str(i)
            c["summary"] = "Long factual summary " * 800
            c["evidence"] *= 12
            candidates.append(c)
        p.write(self.run / "candidates.json", candidates)
        before = (self.run / "candidates.json").read_bytes()
        seen, offset = [], 0
        while offset is not None:
            result = e.candidates(self.run, offset=offset)
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), e.MAX_OUTPUT_CHARS)
            seen.extend(c["id"] for c in result["items"])
            offset = result["next_offset"]
        self.assertEqual(seen, [str(i) for i in range(67)])
        self.assertEqual(before, (self.run / "candidates.json").read_bytes())

    def test_detail_lists_all_evidence_in_pages_and_marks_shortened_excerpts(self):
        self.candidate["evidence"] *= 15
        for evidence in self.candidate["evidence"]:
            evidence["excerpt"] = "Source text " * 500
        p.write(self.run / "candidates.json", [self.candidate])
        seen, offset = [], 0
        while offset is not None:
            result = e.candidate(self.run, "candidate-1", offset=offset)
            self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), e.MAX_OUTPUT_CHARS)
            seen.extend(result["items"])
            offset = result["next_offset"]
        self.assertEqual(len(seen), 15)
        self.assertTrue(all(x["excerpt_truncated"] for x in seen))

    def test_targeted_cached_text_preserves_the_complete_article_off_context(self):
        text = "Old paragraph. " * 3000 + "IMPORTANT VERIFIED CLAIM." + " Tail." * 3000
        path = self.run / "worker-sources-01/cache/article.json"
        p.write(path, {"url": self.candidate["url"], "text": text})
        result = e.evidence(self.run, "candidate-1", query="IMPORTANT VERIFIED CLAIM")
        self.assertEqual(result["source"], "cached_article")
        self.assertIn("IMPORTANT VERIFIED CLAIM", result["text"])
        self.assertLessEqual(len(result["text"]), 4000)
        self.assertEqual(json.loads(path.read_text())["text"], text)

    def test_evidence_windows_can_recover_the_full_stored_excerpt(self):
        text = "Verbatim source evidence. " * 500
        self.candidate["evidence"][0]["excerpt"] = text
        p.write(self.run / "candidates.json", [self.candidate])
        parts, offset = [], 0
        while offset is not None:
            result = e.evidence(self.run, "candidate-1", offset=offset)
            self.assertEqual(result["source"], "stored_excerpt")
            parts.append(result["text"])
            offset = result["next_offset"]
        self.assertEqual("".join(parts), text)

    def test_history_matches_and_pagination_do_not_silently_discard_items(self):
        history = [{"title": "Earlier model", "date": "2026-09-29", "sources": [{"url": self.candidate["url"]}]}]
        history += [{"title": f"Other {i}", "date": "2026-09-28", "sources": []} for i in range(40)]
        p.write(self.root / "data/history.json", {"items": history})
        result = e.candidate(self.run, "candidate-1")
        self.assertEqual(result["history_matches"][0]["title"], "Earlier model")
        seen, offset = [], 0
        while offset is not None:
            result = e.history(self.run, offset=offset)
            seen.extend(result["items"])
            offset = result["next_offset"]
        self.assertEqual(len(seen), 41)

    def test_overview_preserves_topic_ids_without_dumping_full_history(self):
        p.write(self.root / "data/history.json", {"items": [{"summary": "x" * 100000}]})
        result = e.overview(self.run)
        self.assertEqual([t["id"] for t in result["topics"]], [str(i) for i in range(8)])
        self.assertEqual(result["history_items"], 1)
        self.assertNotIn("x" * 100, json.dumps(result))

    def test_unknown_candidates_invalid_pages_and_missing_queries_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "Unknown candidate"):
            e.candidate(self.run, "missing")
        with self.assertRaises(ValueError):
            e.candidates(self.run, offset=-1)
        with self.assertRaisesRegex(ValueError, "not found"):
            e.evidence(self.run, "candidate-1", query="nonexistent phrase")


if __name__ == "__main__":
    unittest.main()
