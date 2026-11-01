import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_policy_fixtures import title_discovery_fixture
import research_integrity as ri


class ArxivCompactExportTests(unittest.TestCase):
    def test_export_preserves_every_original_query_and_page_in_new_record(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            originals = title_discovery_fixture()
            originals[2]['query'] = 'cat:cs.AI AND lastUpdatedDate:[202610212200 TO 202611012259]'
            originals[2]['pages'][0]['url'] += '&literal=%2A%2A%2A&start=0'
            originals[2]['pages'].append({**originals[2]['pages'][0], 'skip': 2000,
                                         'url': originals[2]['pages'][0]['url'] + '&cursor=second'})
            paths = []
            for report in originals:
                path = folder / (report['listing_kind'] + '.json')
                path.write_text(json.dumps({**report, 'titles': [{'title': 'Example fixture'}]}))
                paths.append(str(path))
            entry = {'domain': 'arxiv.org', 'title_discovery_files': paths,
                     'result': 'Honest source limitation retained.', 'candidates': [],
                     'title_discovery': copy.deepcopy(originals)}
            entry['title_discovery'][2]['pages'][0]['url'] += '&wrong=1'
            source = folder / 'rejected.json'
            source.write_text(json.dumps(entry))
            protected = {path: Path(path).read_bytes() for path in paths + [str(source)]}
            target = folder / 'new-record.json'
            command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'arxiv_discovery.py'),
                       '--compact-input', str(source), '--output', str(target)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            exported = json.loads(target.read_text())
            ri.validate_reports(exported)
            self.assertEqual(exported['title_discovery'], originals)
            self.assertEqual({k: v for k, v in exported.items() if k != 'title_discovery'},
                             {k: v for k, v in entry.items() if k != 'title_discovery'})
            self.assertEqual({path: Path(path).read_bytes() for path in protected}, protected)
            # Neither the rejected input nor an existing export may be overwritten.
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            with self.assertRaisesRegex(ValueError, 'helper report'):
                ri.validate_reports(entry)


if __name__ == '__main__':
    unittest.main()
