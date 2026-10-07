"""Regression: a DevDay URL must not stand in for a missing Decisions story."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_pipeline as p
import editor_context as context


class EditorialCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.run = Path(self.temp.name) / "run"
        self.briefing = {"meta": {"generated": "2026-10-06"},
                         "topics": [{"id": str(i), "items": []} for i in range(8)]}
        p.write(self.root / "data/briefing.json", self.briefing)
        self.manifest = p.prepare(self.root, self.run, "2026-10-07")

    def candidate(self, title="OpenAI startet Decisions API als öffentliche Beta",
                  terms=None, url="https://openai.com/index/devday-2026-recap/", change_type="public_beta"):
        return {"title": title, "summary": "Verifizierte eigenständige Entwicklung.",
                "development": "Die Decisions API wechselt von Preview zu öffentlicher Beta.",
                "headline_terms": terms or ["Decisions API"],
                "change_type": change_type,
                "url": url, "published_at": "2026-10-06",
                "evidence": [{"url": url, "excerpt": "The Decisions API is now available in public beta.",
                              "method": "direct", "retrieved_at": "2026-10-07T08:00:00+02:00"}]}

    def fill(self, candidates):
        for task in self.manifest["tasks"]:
            if task["kind"] == "discovery":
                p.record(self.run, task["id"], {"topics_checked": list(p.TOPICS),
                                              "result": "All topics searched", "candidates": []})
            else:
                for source in task["sources"]:
                    entry = {"domain": source["domain"], "name": source["name"],
                             "status": "checked", "checked_url": source["url"],
                             "result": "Original sources checked", "candidates":
                             candidates if source["domain"] == "simonwillison.net" else []}
                    entry["checks"] = [{"url": url, "status": "checked", "result": "Original read"}
                                       for url in source.get("required_checks", [])]
                    p.record(self.run, task["id"], entry)
        p.assemble(self.run)
        return p.read(self.run / "candidates.json")

    def publish(self, candidates, title=None):
        self.briefing["meta"]["generated"] = "2026-10-07"
        self.briefing["topics"][0]["items"] = [{
            "title": title or candidates[0]["title"], "summary": "Verified reporting.",
            "date": "2026-10-06", "impact": 3,
            "candidate_ids": [c["id"] for c in candidates],
            "change_type": candidates[0]["change_type"],
            "sources": [{"url": c["url"]} for c in candidates],
        }]
        p.write(self.root / "data/briefing.json", self.briefing)
        p.write(self.run / "editor-decisions.json", [{"id": c["id"], "decision": "selected",
                                                    "reason": "New and verified"} for c in candidates])

    def test_shared_url_cannot_hide_an_unmapped_selected_development(self):
        candidates = self.fill([self.candidate(), self.candidate("Codex Security Cloud startet", ["Codex Security"])])
        self.publish(candidates, "Codex Security Cloud startet")
        self.briefing["topics"][0]["items"][0]["candidate_ids"] = [candidates[1]["id"]]
        p.write(self.root / "data/briefing.json", self.briefing)
        with self.assertRaisesRegex(ValueError, "Selected candidate.*mapped"):
            p.check_editor(self.run)

    def test_false_mapping_cannot_hide_decisions_under_codex_security(self):
        candidates = self.fill([self.candidate()])
        self.publish(candidates, "Codex Security Cloud startet")
        with self.assertRaisesRegex(ValueError, "headline"):
            p.check_editor(self.run)

    def test_api_launch_cannot_be_buried_under_plugin_headline(self):
        candidates = self.fill([self.candidate()])
        self.publish(candidates, "Alpha-Plugin bringt OpenAI Decisions in das LLM-CLI")
        with self.assertRaisesRegex(ValueError, "headline"):
            p.check_editor(self.run)

    def test_atomic_api_and_security_stories_with_same_url_are_both_preserved(self):
        candidates = self.fill([self.candidate(), self.candidate("Codex Security Cloud startet", ["Codex Security"])])
        self.publish([candidates[0]])
        item = copy.deepcopy(self.briefing["topics"][0]["items"][0])
        item.update(title=candidates[1]["title"], candidate_ids=[candidates[1]["id"]])
        self.briefing["topics"][0]["items"].append(item)
        p.write(self.root / "data/briefing.json", self.briefing)
        p.write(self.run / "editor-decisions.json", [{"id": c["id"], "decision": "selected",
                                                    "reason": "Independent development"} for c in candidates])
        self.assertEqual(p.check_editor(self.run)["selected"], 2)

    def test_duplicate_requires_concrete_published_target(self):
        candidates = self.fill([self.candidate()])
        self.publish(candidates)
        self.briefing["topics"][0]["items"] = []
        p.write(self.root / "data/briefing.json", self.briefing)
        p.write(self.run / "editor-decisions.json", [{"id": candidates[0]["id"],
            "decision": "duplicate", "reason": "Covered by a collective report"}])
        with self.assertRaisesRegex(ValueError, "duplicate_of"):
            p.check_editor(self.run)

    def test_duplicate_target_must_cover_product_in_its_headline(self):
        candidates = self.fill([self.candidate(), self.candidate("Codex Security Cloud startet", ["Codex Security"])])
        self.publish([candidates[1]])
        p.write(self.run / "editor-decisions.json", [
            {"id": candidates[1]["id"], "decision": "selected", "reason": "Verified"},
            {"id": candidates[0]["id"], "decision": "duplicate", "reason": "Same URL",
             "duplicate_of": {"candidate_id": candidates[1]["id"]}},
        ])
        with self.assertRaisesRegex(ValueError, "headline"):
            p.check_editor(self.run)

    def test_valid_duplicate_of_selected_candidate_is_supported(self):
        candidates = self.fill([self.candidate(), self.candidate(
            "Decisions API startet als Beta", url="https://developers.openai.com/api/docs/changelog")])
        self.publish([candidates[0]])
        p.write(self.run / "editor-decisions.json", [
            {"id": candidates[0]["id"], "decision": "selected", "reason": "Verified"},
            {"id": candidates[1]["id"], "decision": "duplicate", "reason": "Same beta launch",
             "duplicate_of": {"candidate_id": candidates[0]["id"]}},
        ])
        self.assertEqual(p.check_editor(self.run)["status"], "ready_to_publish")

    def test_public_beta_is_not_duplicate_of_a_preview_with_same_url_and_headline(self):
        candidates = self.fill([self.candidate(), self.candidate(
            "OpenAI zeigt Decisions API als Preview", change_type="preview")])
        self.publish([candidates[1]])
        p.write(self.run / "editor-decisions.json", [
            {"id": candidates[1]["id"], "decision": "selected", "reason": "Verified preview"},
            {"id": candidates[0]["id"], "decision": "duplicate", "reason": "Same product and URL",
             "duplicate_of": {"candidate_id": candidates[1]["id"]}},
        ])
        with self.assertRaisesRegex(ValueError, "change_type"):
            p.check_editor(self.run)

    def test_valid_history_duplicate_and_invalid_history_target(self):
        item = {"topic_id": "0", "title": "Decisions API als öffentliche Beta", "date": "2026-10-06",
                "change_type": "public_beta", "sources": []}
        p.write(self.run / "history-before.json", {"items": [item]})
        history_id = context.history(self.run)["items"][0]["history_id"]
        candidates = self.fill([self.candidate()])
        self.publish(candidates)
        self.briefing["topics"][0]["items"] = []
        p.write(self.root / "data/briefing.json", self.briefing)
        decision = {"id": candidates[0]["id"], "decision": "duplicate", "reason": "Same public beta release",
                    "duplicate_of": {"history_id": history_id}}
        p.write(self.run / "editor-decisions.json", [decision])
        self.assertEqual(p.check_editor(self.run)["status"], "ready_to_publish")
        decision["duplicate_of"]["history_id"] = "h-nonexistent"
        p.write(self.run / "editor-decisions.json", [decision])
        with self.assertRaisesRegex(ValueError, "unknown history_id"):
            p.check_editor(self.run)

    def test_openai_changelog_is_in_assignment_and_is_a_required_checkpoint(self):
        task = next(t for t in self.manifest["tasks"] if any(
            s["domain"] == "openai.com" for s in t.get("sources", [])))
        source = next(s for s in task["sources"] if s["domain"] == "openai.com")
        self.assertIn("https://developers.openai.com/api/docs/changelog", source.get("required_checks", []))
        entry = {"domain": "openai.com", "name": "OpenAI", "status": "checked",
                 "checked_url": source["url"], "result": "News read", "candidates": []}
        with self.assertRaisesRegex(ValueError, "Pflichtprüfungen"):
            p.record(self.run, task["id"], entry)

    def test_partial_changelog_failure_keeps_the_source_watermark(self):
        p.write(self.root / "data/research-audit/2026-10-06.json", {
            "date": "2026-10-06", "sources": [{"domain": "openai.com", "status": "checked",
                "checks": [{"url": "https://developers.openai.com/api/docs/changelog",
                            "status": "unavailable", "result": "Unavailable after fallback"}]}]})
        self.assertEqual(p.source_windows(self.root, p.date(2026, 10, 7), [("openai.com", "OpenAI")])["openai.com"],
                         "2026-09-30")

    def test_legacy_news_only_check_does_not_claim_changelog_coverage(self):
        p.write(self.root / "data/research-audit/2026-10-06.json", {
            "date": "2026-10-06", "sources": [{"domain": "openai.com", "status": "checked"}]})
        self.assertEqual(p.source_windows(self.root, p.date(2026, 10, 7), [("openai.com", "OpenAI")])["openai.com"],
                         "2026-09-30")

    def test_history_context_exposes_a_stable_duplicate_target(self):
        item = {"topic_id": "0", "title": "Decisions API als Preview", "date": "2026-09-29", "sources": []}
        p.write(self.run / "history-before.json", {"items": [item]})
        view = context.history(self.run)["items"][0]
        self.assertTrue(view.get("history_id"))
        self.assertEqual(view["history_id"], context.history(self.run)["items"][0]["history_id"])

    def test_selected_candidate_cannot_be_mapped_twice(self):
        candidates = self.fill([self.candidate()])
        self.publish(candidates)
        self.briefing["topics"][1]["items"] = copy.deepcopy(self.briefing["topics"][0]["items"])
        p.write(self.root / "data/briefing.json", self.briefing)
        with self.assertRaisesRegex(ValueError, "more than once"):
            p.check_editor(self.run)

    def test_evidence_from_other_selected_story_cannot_be_borrowed(self):
        candidates = self.fill([self.candidate(), self.candidate(
            "Decisions API startet als Beta", url="https://developers.openai.com/api/docs/changelog")])
        self.publish([candidates[0]])
        other = copy.deepcopy(self.briefing["topics"][0]["items"][0])
        other.update(title=candidates[1]["title"], candidate_ids=[candidates[1]["id"]],
                     sources=[{"url": candidates[1]["url"]}])
        self.briefing["topics"][0]["items"].append(other)
        self.briefing["topics"][0]["items"][0]["sources"].append({"url": candidates[1]["url"]})
        p.write(self.root / "data/briefing.json", self.briefing)
        p.write(self.run / "editor-decisions.json", [{"id": c["id"], "decision": "selected",
                                                    "reason": "Verified"} for c in candidates])
        with self.assertRaisesRegex(ValueError, "mapped candidates"):
            p.check_editor(self.run)

    def test_merged_independent_reports_of_same_development_are_supported(self):
        candidates = self.fill([self.candidate(), self.candidate(
            "Decisions API startet als Beta", url="https://developers.openai.com/api/docs/changelog")])
        self.publish(candidates)
        self.assertEqual(p.check_editor(self.run)["candidates_mapped"], 2)

    def test_candidate_requires_specific_atomic_metadata(self):
        candidate = self.candidate()
        del candidate["development"]
        with self.assertRaisesRegex(ValueError, "atomic development"):
            p.record(self.run, "discovery", {"topics_checked": list(p.TOPICS),
                     "result": "All topics searched", "candidates": [candidate]})

    def test_assembly_catches_removed_changelog_checkpoint(self):
        self.fill([])
        path = p.checkpoint_path(self.run, "openai.com")
        entry = p.read(path)
        entry["checks"].pop()
        p.write(path, entry)
        with self.assertRaisesRegex(ValueError, "Invalid source audit"):
            p.assemble(self.run)

    def test_documented_changelog_failure_remains_visible_in_audit(self):
        self.fill([])
        path = p.checkpoint_path(self.run, "openai.com")
        entry = p.read(path)
        entry["checks"][1].update(status="unavailable", result="Original and fallback inaccessible")
        p.write(path, entry)
        p.assemble(self.run)
        audit = p.read(self.root / "data/research-audit/2026-10-07.json")
        source = next(s for s in audit["sources"] if s["domain"] == "openai.com")
        self.assertEqual(source["checks"][1]["status"], "unavailable")
        self.assertEqual(audit["source_checks_version"], 1)

    def test_old_run_stays_verifiable_without_new_metadata(self):
        self.manifest["schema_version"] = 1
        p.write(self.run / "manifest.json", self.manifest)
        candidate = self.candidate()
        for key in ("development", "change_type", "headline_terms"):
            del candidate[key]
        candidates = self.fill([candidate])
        self.briefing["meta"]["generated"] = "2026-10-07"
        self.briefing["topics"][0]["items"] = [{"title": candidate["title"], "date": "2026-10-06",
            "impact": 3, "sources": [{"url": candidate["url"]}]}]
        p.write(self.root / "data/briefing.json", self.briefing)
        p.write(self.run / "editor-decisions.json", [{"id": candidates[0]["id"], "decision": "selected",
                                                    "reason": "Legacy selection"}])
        self.assertNotIn("coverage_version", p.check_editor(self.run))

    def test_frozen_history_target_survives_live_history_mutation(self):
        item = {"title": "Decisions API als Preview", "date": "2026-09-29", "sources": []}
        p.write(self.run / "history-before.json", {"items": [item]})
        before = context.history(self.run)["items"][0]["history_id"]
        p.write(self.root / "data/history.json", {"items": []})
        self.assertEqual(context.history(self.run)["items"][0]["history_id"], before)


if __name__ == "__main__":
    unittest.main()
