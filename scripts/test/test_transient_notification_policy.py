"""Main job must leave durable failure state, not premature recovery notices."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

class NotificationPolicyTests(unittest.TestCase):
    def test_main_keeps_unconfirmed_state_durable_and_telegram_silent(self):
        for name in ["ops/ai-briefing-cron-prompt.txt", "docs/briefing-orchestrator.md"]:
            with self.subTest(name=name):
                text = (ROOT / name).read_text()
                self.assertIn("[SILENT]", text)
                self.assertIn("publication-blocker.json", text)
                self.assertIn("deadline", text)
                self.assertNotIn("Erste Zeile: Veröffentlichung bestätigt oder ehrlich unbestätigter Stand", text)

    def test_daily_editor_requires_executable_isolation_before_strict_check(self):
        text = (ROOT / "docs/briefing-orchestrator.md").read_text()
        self.assertIn("research_pipeline.py review-queue", text)
        self.assertLess(text.index("research_pipeline.py finalize-editor"), text.index("research_pipeline.py check-editor"))

if __name__ == "__main__":
    unittest.main()
