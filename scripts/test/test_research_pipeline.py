import copy
import io
from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_pipeline as p


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.run = Path(self.temp.name) / "run"
        self.briefing = {"meta": {"generated": "2026-09-18"}, "topics": [{"id": str(i), "items": []} for i in range(8)]}
        p.write(self.root / "data/briefing.json", self.briefing)
        self.manifest = p.prepare(self.root, self.run, "2026-09-19")

    def entry(self, domain, candidates=None):
        return {"domain": domain, "name": domain, "status": "checked", "checked_url": "https://" + domain + "/", "result": "Current source checked; no additional news.", "candidates": candidates or []}

    def candidate(self):
        return {"title": "A verifiable development", "summary": "A factual summary", "url": "https://simonwillison.net/original", "published_at": "2026-09-18", "evidence": [{"url": "https://simonwillison.net/original", "excerpt": "An actual original quotation supporting the development.", "method": "web_extract", "retrieved_at": "2026-09-19T08:05:00+02:00"}]}

    def fill(self, candidate=None):
        for task in self.manifest["tasks"]:
            if task["kind"] == "discovery":
                p.record(self.run, task["id"], {"topics_checked": list(p.TOPICS), "result": "All topics searched", "candidates": []})
            else:
                for source in task["sources"]:
                    p.record(self.run, task["id"], self.entry(source["domain"], [candidate] if candidate and source["domain"] == "simonwillison.net" else []))

    def test_growing_registry_assigns_every_source_exactly_once(self):
        for count in [1, 42, 63, 101]:
            sources = [(f"source-{i}.example", str(i)) for i in range(count)]
            manifest = p.prepare(self.root, self.run / str(count), "2026-09-19", sources)
            packets = [t for t in manifest["tasks"] if t["kind"] == "sources"]
            self.assertTrue(all(len(t["sources"]) <= 9 for t in packets))
            assigned = [s["domain"] for t in packets for s in t["sources"]]
            self.assertEqual(assigned, [d for d, _ in sources])
            self.assertEqual(manifest["tasks"][-1]["kind"], "discovery")
            self.assertEqual(manifest["max_parallel"], 3)

    def test_search_budgets_are_per_task_and_stop_before_hermes_limit(self):
        for i in range(35):
            p.reserve(self.run, "sources-01", f"unique query {i}")
        with self.assertRaisesRegex(ValueError, "budget"):
            p.reserve(self.run, "sources-01", "call 36")
        self.assertEqual(p.reserve(self.run, "sources-02", "first")['remaining'], 34)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            p.reserve(self.run, "sources-02", "first")

    def test_fourth_concurrent_dispatch_and_early_assembly_are_blocked(self):
        for task in ["sources-01", "sources-02", "sources-03"]:
            p.dispatch(self.run, task)
        with self.assertRaisesRegex(ValueError, "Three"):
            p.dispatch(self.run, "sources-04")
        with self.assertRaisesRegex(ValueError, "still running"):
            p.assemble(self.run)
        with self.assertRaisesRegex(ValueError, "still running"):
            p.retry(self.run, "sources-01")
        p.release(self.run, "sources-01")
        p.dispatch(self.run, "sources-04")

    def test_dispatch_next_refills_one_free_slot_without_waiting_for_a_wave(self):
        first = [p.dispatch_next(self.run)["task_id"] for _ in range(3)]
        self.assertEqual(first, ["discovery", "sources-01", "sources-02"])
        self.assertEqual(p.dispatch_next(self.run)["status"], "capacity_full")

        source_task = self.manifest["tasks"][0]
        for source in source_task["sources"]:
            p.record(self.run, source_task["id"], self.entry(source["domain"]))
        p.release(self.run, source_task["id"])

        # Discovery and sources-02 are still running. The free slot must be
        # reused immediately, rather than waiting for the whole first wave.
        self.assertEqual(p.dispatch_next(self.run)["task_id"], "sources-03")
        running = [t["id"] for t in p.read(self.run / "manifest.json")["tasks"] if t.get("state") == "running"]
        self.assertEqual(running, ["sources-02", "sources-03", "discovery"])

    def test_dispatch_next_prioritizes_bounded_retry_over_new_packets(self):
        for _ in range(3):
            p.dispatch_next(self.run)
        p.release(self.run, "sources-01")
        p.retry(self.run, "sources-01")
        self.assertEqual(p.dispatch_next(self.run)["task_id"], "sources-01-retry")
        self.assertEqual(p.read(self.run / "manifest.json")["tasks"][-1]["attempt"], 2)

    def test_preparation_balances_packets_using_completed_historical_runs(self):
        sources = [(f"source-{i:02}.example", str(i)) for i in range(18)]
        prior = self.run.parent / "2026-09-18"
        p.write(prior / "manifest.json", {
            "date": "2026-09-18", "root": str(self.root.resolve()),
            "tasks": [
                {"id": "sources-01", "kind": "sources", "attempt": 1, "state": "complete",
                 "sources": [{"domain": domain} for domain, _ in sources[:9]],
                 "dispatched_at": "2026-09-18T08:00:00+02:00", "finished_at": "2026-09-18T09:30:00+02:00"},
                {"id": "sources-02", "kind": "sources", "attempt": 1, "state": "complete",
                 "sources": [{"domain": domain} for domain, _ in sources[9:]],
                 "dispatched_at": "2026-09-18T08:00:00+02:00", "finished_at": "2026-09-18T08:09:00+02:00"},
            ],
        })
        manifest = p.prepare(self.root, self.run.parent / "2026-09-20", "2026-09-20", sources)
        packets = [task for task in manifest["tasks"] if task["kind"] == "sources"]
        self.assertEqual(len(packets), 2)
        self.assertTrue(all(len(task["sources"]) <= 9 for task in packets))
        self.assertTrue(all(any(s["domain"] in {d for d, _ in sources[:9]} for s in task["sources"]) for task in packets))
        self.assertEqual({s["domain"] for task in packets for s in task["sources"]}, {d for d, _ in sources})

    def test_timing_report_keeps_first_research_and_editorial_checkpoints(self):
        self.fill()
        research = p.assemble(self.run)
        self.assertEqual(p.assemble(self.run)["completed_at"], research["completed_at"])
        p.write(self.run / "editor-decisions.json", [])
        self.briefing["meta"]["generated"] = "2026-09-19"
        p.write(self.root / "data/briefing.json", self.briefing)
        editor = p.check_editor(self.run)
        self.assertEqual(p.check_editor(self.run)["checked_at"], editor["checked_at"])
        report = p.timings(self.run)
        self.assertEqual(report["date"], "2026-09-19")
        self.assertEqual(report["sources"], len(p.SOURCES))
        self.assertEqual(report["searches"], 0)
        self.assertIn("editorial_minutes", report)

    def test_editor_can_add_independent_evidence_without_changing_worker_data(self):
        self.fill(self.candidate())
        p.assemble(self.run)
        candidate = p.read(self.run / "candidates.json")[0]
        evidence = {"url": "https://independent.example/report", "excerpt": "Independent original reporting verifies the development.", "method": "direct", "retrieved_at": "2026-09-19T08:20:00+02:00"}
        p.add_evidence(self.run, {"id": candidate["id"], "evidence": [evidence]})
        self.assertEqual(len(p.read(self.run / "candidates.json")[0]["evidence"]), 2)
        self.assertEqual(len(p.read(p.checkpoint_path(self.run, "simonwillison.net"))["candidates"][0]["evidence"]), 1)

    def test_failed_days_do_not_advance_watermark(self):
        for day, status in [("2026-09-12", "checked"), ("2026-09-18", "unavailable")]:
            p.write(self.root / f"data/research-audit/{day}.json", {"date": day, "sources": [{"domain": "example.org", "status": status}]})
        windows = p.source_windows(self.root, date(2026, 9, 19), [("example.org", "Example"), ("new.org", "New")])
        self.assertEqual(windows["example.org"], "2026-09-11")
        self.assertEqual(windows["new.org"], "2026-09-12")

    def test_resume_and_retry_keep_completed_sources(self):
        task = self.manifest["tasks"][0]
        first = task["sources"][0]["domain"]
        p.record(self.run, task["id"], self.entry(first))
        p.prepare(self.root, self.run, "2026-09-19")
        self.assertNotIn(first, p.missing(self.run, task))
        p.retry(self.run, task["id"])
        _, recovery = p.task_for(self.run, task["id"] + "-retry")
        self.assertNotIn(first, [s["domain"] for s in recovery["sources"]])
        with self.assertRaisesRegex(ValueError, "already"):
            p.retry(self.run, task["id"])
        with self.assertRaisesRegex(ValueError, "already"):
            p.retry(self.run, recovery["id"])

    def test_wrong_owner_and_invalid_status_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "belong"):
            p.record(self.run, "sources-02", self.entry("simonwillison.net"))
        entry = self.entry("simonwillison.net")
        entry["status"] = "success"
        with self.assertRaisesRegex(ValueError, "checked"):
            p.record(self.run, "sources-01", entry)

    def test_search_snippets_and_future_dates_are_not_evidence(self):
        c = self.candidate()
        c["evidence"][0]["method"] = "web_search"
        with self.assertRaisesRegex(ValueError, "snippets"):
            p.record(self.run, "sources-01", self.entry("simonwillison.net", [c]))
        c = self.candidate()
        c["published_at"] = "2026-09-20"
        with self.assertRaisesRegex(ValueError, "window"):
            p.record(self.run, "sources-01", self.entry("simonwillison.net", [c]))

    def test_missing_source_or_discovery_blocks_publication(self):
        with self.assertRaisesRegex(ValueError, "Missing source"):
            p.assemble(self.run)
        self.fill()
        (self.run / "discovery.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing discovery"):
            p.assemble(self.run)

    def test_editor_cannot_silently_drop_candidates_or_add_unverified_urls(self):
        self.fill(self.candidate())
        p.assemble(self.run)
        p.write(self.run / "editor-decisions.json", [])
        with self.assertRaisesRegex(ValueError, "Every candidate"):
            p.check_editor(self.run)
        candidate = p.read(self.run / "candidates.json")[0]
        p.write(self.run / "editor-decisions.json", [{"id": candidate["id"], "decision": "selected", "reason": "Relevant and verified"}])
        briefing = copy.deepcopy(self.briefing)
        briefing["meta"]["generated"] = "2026-09-19"
        briefing["topics"][0]["items"] = [{"title": candidate["title"], "date": "2026-09-18", "impact": 3, "sources": [{"url": candidate["url"]}]}]
        p.write(self.root / "data/briefing.json", briefing)
        self.assertEqual(p.check_editor(self.run)["status"], "ready_to_publish")
        briefing["topics"][0]["items"][0]["sources"].append({"url": "https://unread.example/story"})
        p.write(self.root / "data/briefing.json", briefing)
        with self.assertRaisesRegex(ValueError, "unverified"):
            p.check_editor(self.run)

    def test_no_new_candidates_is_a_valid_completed_research_run(self):
        self.fill()
        p.write(self.run / "editor-decisions.json", [])
        self.briefing["meta"]["generated"] = "2026-09-19"
        p.write(self.root / "data/briefing.json", self.briefing)
        result = p.check_editor(self.run)
        self.assertEqual(result["candidates_reviewed"], 0)
        self.assertEqual(result["status"], "ready_to_publish")

    def test_preserved_same_day_items_can_be_renumbered(self):
        old = {"title": "Existing article", "n": 1, "date": "2026-09-18", "impact": 3, "sources": [{"url": "https://old.example/story"}]}
        self.briefing["topics"][0]["items"] = [old]
        p.write(self.run / "briefing-before.json", self.briefing)
        self.fill()
        p.write(self.run / "editor-decisions.json", [])
        self.briefing["meta"]["generated"] = "2026-09-19"
        self.briefing["topics"][0]["items"][0]["n"] = 2
        p.write(self.root / "data/briefing.json", self.briefing)
        self.assertEqual(p.check_editor(self.run)["status"], "ready_to_publish")

    def test_publication_receipt_requires_matching_committed_data_and_successful_build(self):
        self.fill()
        p.write(self.run / "editor-decisions.json", [])
        self.briefing["meta"]["generated"] = "2026-09-19"
        p.write(self.root / "data/briefing.json", self.briefing)
        p.check_editor(self.run)
        audit = p.read(self.root / "data/research-audit/2026-09-19.json")
        def git_run(args, **kwargs):
            command = args[3]
            if command == "rev-parse": output = "abc123"
            elif command == "ls-remote": output = "abc123\trefs/heads/main"
            elif args[-1].endswith("briefing.json"): output = json.dumps(self.briefing)
            else: output = json.dumps(audit)
            return type("Result", (), {"stdout": output})()
        class Response(io.BytesIO):
            status = 200
        failed = {"workflow_runs": [{"head_sha": "abc123", "status": "completed", "conclusion": "failure", "run_number": 1}]}
        with patch.object(p.subprocess, "run", side_effect=git_run), patch.object(p, "urlopen", return_value=Response(json.dumps(failed).encode())):
            with self.assertRaisesRegex(ValueError, "has not succeeded"):
                p.verify_publication(self.run)
            self.assertFalse((self.run / "publication.json").exists())
        success = copy.deepcopy(failed)
        success["workflow_runs"][0].update(conclusion="success", html_url="https://github.com/example/actions/runs/1")
        with patch.object(p.subprocess, "run", side_effect=git_run), patch.object(p, "urlopen", side_effect=[Response(json.dumps(success).encode()), Response(b"page")]):
            self.assertEqual(p.verify_publication(self.run)["status"], "published")
        self.assertEqual(p.read(self.run / "publication.json")["commit"], "abc123")


if __name__ == "__main__":
    unittest.main()
