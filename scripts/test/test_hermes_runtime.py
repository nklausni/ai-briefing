import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_hermes_runtime as r


class HermesRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {"delegation": {"max_concurrent_children": 10}}
        self.job = {"enabled": True, "prompt": "current instruction", "workdir": "/opt/data/ai-briefing",
                    "schedule": {"expr": "0 6,7 * * *"}, "script": "ai-briefing-berlin-gate.py"}

    def test_real_deployment_contract_accepts_persistent_runtime_values(self):
        self.assertTrue(all(r.checks(self.cfg, self.job, 1800, 1800, "current instruction").values()))

    def test_both_old_timeout_paths_are_detected(self):
        result = r.checks(self.cfg, self.job, 420, 420, "current instruction")
        self.assertFalse(result["sequential_timeout_resolves"])
        self.assertFalse(result["concurrent_timeout_resolves"])

    def test_stale_job_prompt_and_mismatched_hermes_capacity_fail(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["delegation"]["max_concurrent_children"] = 3
        result = r.checks(cfg, self.job, 1800, 1800, "new instruction")
        self.assertFalse(result["hermes_capacity"])
        self.assertFalse(result["cron_prompt_matches_repo"])

