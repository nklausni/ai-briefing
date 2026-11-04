"""Historical holding is not duplicate verification or source completion."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
import test_editorial_coverage as base
import research_pipeline as p
from editorial_coverage import history_id


class QuarantineTests(unittest.TestCase):
    setUp = base.EditorialCoverageTests.setUp
    candidate = base.EditorialCoverageTests.candidate
    fill = base.EditorialCoverageTests.fill
    publish = base.EditorialCoverageTests.publish

    def conflict(self, kind="research", historical="other", anchor=False):
        good = self.candidate("Nova Compute startet", ["Nova Compute"], change_type="announcement")
        old = self.candidate("Orion Study und Orion Tiny: Ergebnisse", ["Orion Study", "Orion Tiny"],
                             url="https://example.org/orion", change_type=kind)
        item = {"title": "Orion Study: neue Ergebnisse" if anchor else old["title"],
                "summary": "Orion Study prüft Orion Tiny in einem begrenzten Experiment.",
                "date": old["published_at"], "change_type": historical,
                "sources": [{"url": old["url"]}]}
        p.write(self.run / "history-before.json", {"items": [item]})
        cs = self.fill([good, old])
        self.publish([cs[0]])
        ds = p.read(self.run / "editor-decisions.json") + [{"id": cs[1]["id"], "decision": "duplicate",
            "reason": "Same dated study, historical classification unresolved",
            "duplicate_of": {"history_id": history_id(item)}}]
        p.write(self.run / "editor-decisions.json", ds)
        return cs, ds, item

    def test_nonpublished_historical_conflict_is_held_without_blocking_valid_news(self):
        cs, ds, item = self.conflict()
        with self.assertRaisesRegex(ValueError, "change_type"):
            p.check_editor(self.run)
        before = (self.run / "history-before.json").read_bytes()
        result = p.finalize_editor(self.run)
        self.assertEqual(result["deferred"], 1)
        decisions = p.read(self.run / "editor-decisions.json")
        held = decisions[1]
        self.assertEqual(held["decision"], "deferred")
        self.assertEqual(held["quarantine"]["proposed_decision"], ds[1])
        self.assertIn("change_type", held["quarantine"]["validator_error"])
        self.assertEqual(p.check_editor(self.run)["selected"], 1)
        coverage = p.read(self.run / "editor-coverage.json")
        self.assertEqual(coverage["duplicates"], 0)
        self.assertEqual(len(coverage["mapped"]), 1)
        self.assertEqual((self.run / "history-before.json").read_bytes(), before)


    def test_cli_is_idempotent_and_next_day_does_not_freshen_queue(self):
        self.conflict(anchor=True, historical="research")
        command = [sys.executable, str(Path(p.__file__)), "finalize-editor", "--run-dir", str(self.run)]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        paths = [self.run / "editor-decisions.json", self.run / "editor-quarantine.json",
                 self.run.parent / "editor-review-queue.json", self.run / "history-before.json"]
        before = [path.read_bytes() for path in paths]
        artifacts = sorted(p.name for p in self.run.glob("editor-proposals-*.json"))
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(sorted(p.name for p in self.run.glob("editor-proposals-*.json")), artifacts)
        self.assertEqual([path.read_bytes() for path in paths], before)
        manifest = p.read(self.run / "manifest.json")
        manifest["date"] = "2026-10-08"
        p.write(self.run / "manifest.json", manifest)
        self.briefing["meta"]["generated"] = "2026-10-08"
        p.write(self.root / "data/briefing.json", self.briefing)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(paths[2].read_bytes(), before[2])
        queue = json.loads(before[2])
        self.assertEqual(len(queue["items"]), 1)
        self.assertEqual(next(iter(queue["items"].values()))["original_date"], "2026-10-06")


    def test_direct_checker_cannot_accept_empty_held_only_publication(self):
        cs, ds, _ = self.conflict()
        p.finalize_editor(self.run)
        decisions = p.read(self.run / "editor-decisions.json")
        decisions[0] = {"id": cs[0]["id"], "decision": "below_threshold", "reason": "routine"}
        self.briefing["topics"][0]["items"] = []
        p.write(self.root / "data/briefing.json", self.briefing)
        p.write(self.run / "editor-decisions.json", decisions)
        with self.assertRaisesRegex(ValueError, "empty publication"):
            p.check_editor(self.run)

    def test_release_milestone_conflicts_remain_fatal(self):
        for kind, historical in [("public_beta", "preview"), ("announcement", "general_availability")]:
            with self.subTest(kind=kind):
                self.setUp()
                self.conflict(kind=kind, historical=historical)
                before = (self.run / "editor-decisions.json").read_bytes()
                with self.assertRaisesRegex(ValueError, "milestones"):
                    p.finalize_editor(self.run)
                self.assertEqual((self.run / "editor-decisions.json").read_bytes(), before)

    def test_selected_and_source_failures_are_not_downgraded(self):
        self.conflict()
        self.briefing["topics"][0]["items"][0]["title"] = "Unrelated headline"
        p.write(self.root / "data/briefing.json", self.briefing)
        with self.assertRaisesRegex(ValueError, "headline"):
            p.finalize_editor(self.run)
        path = p.checkpoint_path(self.run, "openai.com")
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing source"):
            p.finalize_editor(self.run)
        self.assertFalse((self.run / "editor-quarantine.json").exists())

    def test_held_record_cannot_be_forged_or_used_as_a_published_candidate(self):
        cs, _, _ = self.conflict()
        p.finalize_editor(self.run)
        decisions = p.read(self.run / "editor-decisions.json")
        decisions[1]["quarantine"]["validator_error"] = "invented reason"
        p.write(self.run / "editor-decisions.json", decisions)
        with self.assertRaisesRegex(ValueError, "reproduced conflict"):
            p.check_editor(self.run)
        decisions[1]["quarantine"]["validator_error"] = "Duplicate change_type differs: preview, beta and GA are separate developments"
        p.write(self.run / "editor-decisions.json", decisions)
        self.briefing["topics"][0]["items"][0]["candidate_ids"].append(cs[1]["id"])
        p.write(self.root / "data/briefing.json", self.briefing)
        with self.assertRaisesRegex(ValueError, "unselected"):
            p.check_editor(self.run)

    def test_quarantine_never_changes_source_coverage_or_watermarks(self):
        self.conflict()
        audit_path = self.root / "data/research-audit/2026-10-07.json"
        before = audit_path.read_bytes()
        windows = p.source_windows(self.root, p.date(2026, 10, 8), [("openai.com", "OpenAI")])
        p.finalize_editor(self.run)
        self.assertEqual(audit_path.read_bytes(), before)
        self.assertEqual(p.source_windows(self.root, p.date(2026, 10, 8), [("openai.com", "OpenAI")]), windows)

    def test_unrelated_history_or_wrong_original_date_still_blocks(self):
        from editorial_coverage import deferred_record
        cs, ds, item = self.conflict()
        for changes in [{"date": "2026-10-05"}, {"sources": [{"url": "https://example.org/unrelated"}]},
                        {"title": "Unrelated product", "summary": "Nothing in common"}]:
            with self.subTest(changes=changes):
                old = {**item, **changes}
                proposal = {**ds[1], "duplicate_of": {"history_id": history_id(old)}}
                with self.assertRaises(ValueError):
                    deferred_record(cs[1], proposal, [old])


    def test_review_queue_is_bounded_read_only_and_same_event_keeps_identity(self):
        cs, _, _ = self.conflict()
        p.finalize_editor(self.run)
        path = self.run.parent / "editor-review-queue.json"
        before = path.read_bytes()
        command = [sys.executable, str(Path(p.__file__)), "review-queue", "--run-dir", str(self.run)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        review = json.loads(result.stdout)
        self.assertEqual(len(review["review"]), 1)
        self.assertEqual(path.read_bytes(), before)
        # A rewritten candidate summary/development is NOT a fresh queue event.
        source = p.checkpoint_path(self.run, "simonwillison.net")
        checkpoint = p.read(source)
        checkpoint["candidates"][1]["development"] += " Weitere Einordnung."
        p.write(source, checkpoint)
        # Reproduce from the unchanged proposal with the new candidate fingerprint.
        ds = p.read(self.run / "editor-decisions.json")
        ds[1] = ds[1]["quarantine"]["proposed_decision"]
        p.write(self.run / "editor-decisions.json", ds)
        p.finalize_editor(self.run)
        self.assertEqual(path.read_bytes(), before)


    def test_legacy_contract_cannot_accept_unvalidated_deferred_state(self):
        self.conflict()
        p.finalize_editor(self.run)
        manifest = p.read(self.run / "manifest.json")
        manifest["schema_version"] = 1
        p.write(self.run / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "coverage contract v2"):
            p.check_editor(self.run)

    def test_six_holds_are_rejected_even_without_using_finalization(self):
        with self.assertRaisesRegex(ValueError, "limit exceeded"):
            p.validate_coverage({}, [{"id": str(i), "decision": "deferred"} for i in range(6)], [], [], [])

    def test_unsupported_selected_date_and_tampered_identity_proof_still_fail(self):
        cs, ds, item = self.conflict()
        self.briefing["topics"][0]["items"][0]["date"] = "2027-01-01"
        p.write(self.root / "data/briefing.json", self.briefing)
        with self.assertRaisesRegex(ValueError, "future date"):
            p.finalize_editor(self.run)
        from editorial_coverage import deferred_record
        ds[1]["history_coverage"] = {"source_identity": {"kind": "invented"}}
        with self.assertRaisesRegex(ValueError, "publisher_syndication"):
            deferred_record(cs[1], ds[1], [item])


    def test_strict_tampered_cache_is_fatal_before_local_isolation(self):
        import research_integrity as ri
        self.conflict()
        def search(task, query):
            return ri.search(self.run, task, query, backend=lambda *a, **k: {"success": True, "data": {"web": []}})
        for task in self.manifest["tasks"]:
            if task["kind"] == "discovery":
                path = self.run / "discovery.json"
                entry = p.read(path)
                mapping = {topic: [search(task["id"], "fixture " + topic)] for topic in p.TOPICS}
                entry.update(topic_searches=mapping, search_receipts=[v[0] for v in mapping.values()])
                p.write(path, entry)
                continue
            for source in task["sources"]:
                path = p.checkpoint_path(self.run, source["domain"])
                entry = p.read(path)
                cache = self.run / (source["domain"] + "-index.json")
                p.write(cache, {"url": source["url"], "text": "Actual deterministic fixture source index"})
                entry["source_receipts"] = [ri.attest_cache(cache, source["url"], cache.with_suffix(".receipt.json"))]
                entry["search_receipts"] = [search(task["id"], "site:" + source["domain"] + " fixture")]
                for c in entry["candidates"]:
                    for index, e in enumerate(c["evidence"]):
                        raw = self.run / (c["id"] + str(index) + "-original.json")
                        p.write(raw, {"url": e["url"], "text": e["excerpt"]})
                        e["receipt"] = ri.attest_cache(raw, e["url"], raw.with_suffix(".receipt.json"))
                if source["domain"] == "arxiv.org":
                    entry["title_discovery_files"] = []
                    for index, report in enumerate(entry["title_discovery"]):
                        report_path = self.run / ("arxiv-report-" + str(index) + ".json")
                        p.write(report_path, report)
                        entry["title_discovery_files"].append(str(report_path))
                p.write(path, entry)
        self.manifest["integrity_version"] = 1
        p.write(self.run / "manifest.json", self.manifest)
        self.assertEqual(p.finalize_editor(self.run)["deferred"], 1)
        decisions_before = (self.run / "editor-decisions.json").read_bytes()
        entry = p.read(p.checkpoint_path(self.run, "simonwillison.net"))
        receipt = p.read(entry["candidates"][1]["evidence"][0]["receipt"])
        p.write(Path(receipt["raw_path"]), {"url": "https://evil.example/", "text": "tampered"})
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            p.finalize_editor(self.run)
        self.assertEqual((self.run / "editor-decisions.json").read_bytes(), decisions_before)


if __name__ == "__main__":
    unittest.main()
