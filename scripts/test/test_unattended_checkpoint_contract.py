"""Regression for unattended briefing checkpoint instructions."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class UnattendedCheckpointContractTests(unittest.TestCase):
    def test_runtime_preflight_runs_before_research_preparation(self):
        text = (ROOT / 'docs/briefing-orchestrator.md').read_text()
        preparation = text.index('scripts/research_pipeline.py prepare')
        for command in (
            '/opt/hermes/.venv/bin/python scripts/check_hermes_runtime.py',
            '/opt/hermes/.venv/bin/python -m unittest discover -s scripts/test -t scripts/test',
            'node --test scripts/test/search.test.cjs',
        ):
            with self.subTest(command=command):
                position = text.find(command)
                self.assertGreaterEqual(position, 0, 'Missing runtime preflight command')
                self.assertLess(position, preparation)
        self.assertIn('keine Implementierung oder Tests im Cron-Lauf ändern', text)

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
