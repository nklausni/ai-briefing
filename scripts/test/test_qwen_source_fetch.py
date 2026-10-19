"""Small synthetic API fixtures model the observed public Qwen response shape."""
import importlib
import io
import json
import signal
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.request import urlopen as real_urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class QwenSourceFetchTests(unittest.TestCase):
    def helper(self):
        self.assertTrue((Path(__file__).resolve().parents[1] / 'qwen_source_fetch.py').exists(),
                        'A reusable public Qwen API fetcher is missing')
        return importlib.import_module('qwen_source_fetch')

    def test_total_network_deadline_includes_headers_and_dripping_body(self):
        q = self.helper()

        class SlowHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    if self.path == '/headers':
                        time.sleep(0.6)
                    self.send_response(200)
                    self.send_header('Content-Length', '30')
                    self.end_headers()
                    for _ in range(30):
                        self.wfile.write(b' ')
                        self.wfile.flush()
                        time.sleep(0.04)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), SlowHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path in ('/headers', '/body'):
                def local_open(request, timeout):
                    self.assertEqual(request.full_url, q.INDEX_URL)
                    return real_urlopen(f'http://127.0.0.1:{server.server_port}{path}', timeout=timeout)

                with self.subTest(path=path), patch.object(q, 'urlopen', side_effect=local_open):
                    started = time.monotonic()
                    with self.assertRaises(TimeoutError):
                        q.retrieve_payload(q.INDEX_URL, timeout=0.2)
                    self.assertLess(time.monotonic() - started, 0.5)
                    self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_oversized_body_is_rejected_with_bounded_read(self):
        q = self.helper()
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b' ' * 10_000_001
        with patch.object(q, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, '10 MB'):
                q.retrieve_payload(q.INDEX_URL)
        response.__enter__.return_value.read.assert_called_once_with(10_000_001)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_prior_alarm_is_restored_on_success_and_error(self):
        q = self.helper()
        original_handler = signal.getsignal(signal.SIGALRM)
        original_timer = signal.getitimer(signal.ITIMER_REAL)
        handler = lambda signum, frame: None
        try:
            signal.signal(signal.SIGALRM, handler)
            for raw in (b'{}', b'invalid json'):
                signal.setitimer(signal.ITIMER_REAL, 10, 3)
                with patch.object(q, 'urlopen', return_value=io.BytesIO(raw)):
                    if raw == b'{}':
                        self.assertEqual(q.retrieve_payload(q.INDEX_URL), {})
                    else:
                        with self.assertRaises(ValueError):
                            q.retrieve_payload(q.INDEX_URL)
                self.assertIs(signal.getsignal(signal.SIGALRM), handler)
                remaining, interval = signal.getitimer(signal.ITIMER_REAL)
                self.assertGreater(remaining, 9)
                self.assertLessEqual(remaining, 10)
                self.assertEqual(interval, 3)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, original_handler)
            signal.setitimer(signal.ITIMER_REAL, *original_timer)

    def test_live_retrieval_keeps_real_retrieval_timestamp(self):
        q = self.helper()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'index.json'
            before = datetime.now().astimezone()
            with patch.object(sys, 'argv', [q.__file__, '--output', str(output)]), \
                    patch.object(q, 'urlopen', return_value=io.BytesIO(
                        b'{"success": true, "data": {"articles": []}}')):
                q.main()
            saved = json.loads(output.read_text())
            self.assertFalse(saved['offline'])
            self.assertNotIn('replayed_at', saved)
            self.assertGreaterEqual(datetime.fromisoformat(saved['retrieved_at']), before)
            self.assertLessEqual(datetime.fromisoformat(saved['retrieved_at']), datetime.now().astimezone())

    def test_unexpected_code_release_owner_is_rejected(self):
        q = self.helper()
        with self.assertRaisesRegex(ValueError, 'Unexpected release owner'):
            q.parse_code_releases([{
                'tag_name': 'v1', 'published_at': '2026-10-19T06:06:37Z',
                'html_url': 'https://github.com/other/qwen-code/releases/tag/v1',
                'draft': False, 'prerelease': False}])

    def test_code_release_dates_and_prerelease_status_come_from_github(self):
        q = self.helper()
        self.assertTrue(hasattr(q, 'parse_code_releases'), 'Qwen Code has no durable dated release route')
        report = q.parse_code_releases([
            {'tag_name': 'v0.25.3', 'name': 'Release v0.25.3', 'published_at': '2026-10-19T06:06:37Z',
             'created_at': '2026-10-17T00:00:00Z', 'prerelease': False, 'draft': False,
             'html_url': 'https://github.com/QwenLM/qwen-code/releases/tag/v0.25.3', 'body': 'Synthetic release body'},
            {'tag_name': 'preview', 'name': 'Preview', 'published_at': '2026-10-16T18:28:53Z',
             'prerelease': True, 'draft': False,
             'html_url': 'https://github.com/QwenLM/qwen-code/releases/tag/preview', 'body': 'Synthetic preview body'}])
        self.assertEqual(report['articles'][0]['published_at'], '2026-10-19T06:06:37Z')
        self.assertFalse(report['articles'][0]['prerelease'])
        self.assertTrue(report['articles'][1]['prerelease'])
        self.assertIn('Synthetic release body', report['articles'][0]['text'])
        self.assertFalse(report['discovery_complete'])

    def test_duplicate_paths_are_not_counted_as_distinct_articles(self):
        q = self.helper()
        item = {'path': 'duplicate', 'title': 'Synthetic', 'extra': {'date': '2026-09-20T20:00:00+08:00'}}
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            q.parse_index({'success': True, 'data': {'articles': [item, item]}})

    def test_source_timestamp_requires_timezone_not_just_a_day(self):
        q = self.helper()
        with self.assertRaisesRegex(ValueError, 'timezone'):
            q.parse_index({'success': True, 'data': {'articles': [
                {'path': 'synthetic', 'title': 'Synthetic', 'extra': {'date': '2026-09-20'}}]}})

    def test_api_error_and_missing_publication_date_fail_closed(self):
        q = self.helper()
        for payload in ({'success': False, 'data': {'articles': []}},
                        {'success': True, 'data': {'articles': [{'path': 'missing-date', 'title': 'Synthetic'}]}}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                q.parse_index(payload)
        with self.assertRaises(ValueError):
            q.parse_code_releases({'message': 'API rate limit exceeded'})

    def test_cli_replays_a_saved_public_response_without_network(self):
        q = self.helper()
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'raw.json'
            output = Path(directory) / 'index.json'
            source.write_text(json.dumps({'success': True, 'data': {'articles': []}}))
            proc = subprocess.run([sys.executable, q.__file__, '--from-json', str(source),
                                   '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(output.exists(), 'CLI must produce the requested evidence artifact')
            saved = json.loads(output.read_text())
            self.assertEqual(saved['raw_cache'], str(source))
            self.assertEqual(saved['article_count'], 0)
            self.assertIsNone(saved['retrieved_at'])
            self.assertTrue(saved['offline'])
            self.assertIsNotNone(datetime.fromisoformat(saved['replayed_at']).tzinfo)
            self.assertIn('text', saved)
            source.write_text('[]')
            proc = subprocess.run([sys.executable, str(q.__file__), '--code-releases', '--from-json', str(source),
                                   '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(output.read_text())['url'], q.CODE_RELEASES_URL)

    def test_index_preserves_source_dates_and_never_claims_complete_discovery(self):
        q = self.helper()
        payload = {'success': True, 'data': {'articles': [
            {'path': 'older', 'title': 'Older release', 'extra': {'date': '2026-06-16T08:00:00+08:00'}},
            {'path': 'qwen-image-2.1', 'title': 'Qwen-Image-2.1',
             'extra': {'date': '2026-09-20T20:00:00+08:00'}}]}}
        report = q.parse_index(payload)
        self.assertEqual(report['latest_published_at'], '2026-09-20T20:00:00+08:00')
        self.assertEqual(report['articles'][0]['url'], 'https://qwen.ai/blog?id=qwen-image-2.1')
        self.assertEqual(report['article_count'], 2)
        self.assertFalse(report['discovery_complete'])
        self.assertIn('total', report['limitation'])


if __name__ == '__main__':
    unittest.main()
