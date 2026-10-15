import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import browser_source_fetch as b
class BrowserSourceTests(unittest.TestCase):
    def test_command_uses_single_batch_and_desktop_user_agent(self):
        cmd = b.command('https://x.ai/news/', 'test-session')
        self.assertIn('--user-agent', cmd)
        self.assertNotIn('HeadlessChrome', cmd[cmd.index('--user-agent')+1])
        self.assertIn('batch', cmd)
        self.assertEqual(cmd[-1], 'close')
    def test_nested_browser_json_is_decoded(self):
        import json
        page = {'url':'https://x.ai/news','text':'News body','ua':b.UA}
        raw = 'Opened\n' + json.dumps(json.dumps(page)) + '\nClosed\n'
        self.assertEqual(b.decode(raw), page)
    def test_blank_tab_is_not_a_success(self):
        import json
        with self.assertRaises(ValueError):
            b.decode(json.dumps(json.dumps({'url':'about:blank','text':''})))
