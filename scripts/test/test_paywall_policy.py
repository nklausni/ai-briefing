from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
class PaywallPolicyTests(unittest.TestCase):
    def test_worker_requires_readable_alternative_evidence(self):
        text = (ROOT / 'docs/briefing-research-worker.md').read_text()
        self.assertIn('## Aboschranken und freie Ersatzquellen', text)
        self.assertIn('keine tragenden Aussagen allein aus Teasern', text)
        self.assertIn('tatsächlich gelesenen Ersatzquellen', text)
        self.assertIn('Reuters', text)
    def test_orchestrator_keeps_source_failures_separate(self):
        text = (ROOT / 'docs/briefing-orchestrator.md').read_text()
        self.assertIn('Aboschranke ist kein Gesamtstopp', text)
        self.assertIn('keine neue Pflichtquelle', text)
