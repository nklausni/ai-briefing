"""Regression for unattended briefing checkpoint instructions."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class UnattendedCheckpointContractTests(unittest.TestCase):
    def test_worker_explains_pending_approval_without_disabling_safety(self):
        text = (ROOT / 'docs/briefing-research-worker.md').read_text()
        self.assertIn('pending_approval', text)
        self.assertIn('write_file', text)
        self.assertIn('Freigabesicherung nicht deaktivieren', text)
        self.assertIn('read_file', text)

    def test_orchestrator_and_live_template_require_file_based_writes(self):
        for relative in ('docs/briefing-orchestrator.md', 'ops/ai-briefing-cron-prompt.txt'):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text()
                self.assertIn('pending_approval', text)
                self.assertIn('write_file', text)
                self.assertIn('gespeicherten Checkpoints', text)

if __name__ == '__main__':
    unittest.main()
