import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_pipeline as p
import research_integrity as ri


class IntegrityTests(unittest.TestCase):
    def test_publication_rejects_stale_live_bytes(self):
        self.assertTrue(hasattr(p,'verify_live_bytes'),'exact live-byte gate is missing')
        with self.assertRaisesRegex(ValueError,'Live site bytes'):
            p.verify_live_bytes(b'old issue',b'new issue')

    def test_reserved_but_never_executed_search_cannot_pass_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, run = Path(tmp)/'repo', Path(tmp)/'run'
            p.write(root/'data/briefing.json', {'topics': []})
            manifest = p.prepare(root, run, '2026-10-25')
            task = next(t for t in manifest['tasks'] if t['kind']=='sources')
            source = task['sources'][0]
            p.reserve(run, task['id'], 'site:'+source['domain']+' October 2026')
            entry = {'domain':source['domain'], 'name':source['name'], 'status':'checked',
                     'checked_url':source['url'], 'result':'Search checked, no new stories.', 'candidates':[]}
            with self.assertRaisesRegex(ValueError, 'receipt'):
                p.record(run, task['id'], entry)
            self.assertFalse(p.checkpoint_path(run,source['domain']).exists())

    def test_tool_failure_receipt_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, run = Path(tmp)/'repo', Path(tmp)/'run'
            p.write(root/'data/briefing.json', {'topics': []})
            p.prepare(root,run,'2026-10-25')
            path=ri.search(run,'sources-01','actual failed query',backend=lambda *a,**k:{'success':False,'error':'backend unavailable'})
            with self.assertRaisesRegex(ValueError,'not a successful'):
                ri.load_receipt(path,'search')

    def test_unrelated_arxiv_paper_cannot_supply_original_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'paper.json'
            p.write(cache,{'url':'https://arxiv.org/abs/2610.11111','text':'Title: Unrelated paper. An actual source quotation long enough.'})
            self.assertTrue(hasattr(ri,'attest_cache'), 'source-cache URL identity validation is missing')
            with self.assertRaisesRegex(ValueError,'URL identity'):
                ri.attest_cache(cache,'https://arxiv.org/abs/2610.22222',Path(tmp)/'receipt.json')

    def test_arxiv_original_title_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'paper.json'
            p.write(cache,{'url':'https://arxiv.org/abs/2610.22222','text':'Title: A completely unrelated paper. A valid original quotation.'})
            receipt=ri.attest_cache(cache,'https://arxiv.org/abs/2610.22222',Path(tmp)/'receipt.json')
            candidate={'url':'https://arxiv.org/abs/2610.22222','original_title':'Expected agent-memory paper',
                       'evidence':[{'url':'https://arxiv.org/abs/2610.22222','excerpt':'A valid original quotation.','receipt':receipt}]}
            self.assertTrue(hasattr(ri,'validate_candidate_identity'),'candidate original identity validation is missing')
            with self.assertRaisesRegex(ValueError,'title/URL identity'):
                ri.validate_candidate_identity(candidate)

    def test_rejected_run_cannot_assemble_even_with_legacy_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)
            p.write(run/'manifest.json',{'registry':p.SOURCES,'tasks':[]})
            p.write(run/'integrity-rejection.json',{'reason':'Unexecuted searches falsely claimed'})
            with self.assertRaisesRegex(ValueError,'integrity-rejected'):
                p.assemble(run)

    def test_failure_raw_response_cannot_be_relabelled_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw.json';p.write(raw,{'success':False,'error':'no provider'})
            receipt=Path(tmp)/'receipt.json'
            p.write(receipt,{'kind':'search','status':'success','raw_path':str(raw),'raw_sha256':ri.digest(raw)})
            with self.assertRaisesRegex(ValueError,'raw response'):
                ri.load_receipt(receipt,'search')

    def test_arxiv_helper_report_cannot_change_its_original_page_url(self):
        self.assertTrue(hasattr(ri,'validate_reports'),'helper report binding is missing')
        with tempfile.TemporaryDirectory() as tmp:
            report=Path(tmp)/'report.json'
            p.write(report,{'pages':[{'url':'https://export.arxiv.org/api/query?start=0'}],'titles':[]})
            with self.assertRaisesRegex(ValueError,'helper report'):
                ri.validate_reports({'title_discovery_files':[str(report)],'title_discovery':[{'pages':[{'url':'https://export.arxiv.org/api/query?start=FAKE'}]}]})

    def test_assembly_rechecks_receipts_without_retroactively_rejecting_old_runs(self):
        from source_policy_fixtures import title_discovery_fixture
        with tempfile.TemporaryDirectory() as tmp:
            root,run=Path(tmp)/'repo',Path(tmp)/'run'
            p.write(root/'data/briefing.json',{'topics':[]})
            manifest=p.prepare(root,run,'2026-09-19')
            for task in manifest['tasks']:
                if task['kind']=='discovery':
                    p.record(run,task['id'],{'topics_checked':list(p.TOPICS),'result':'Historical discovery','candidates':[]})
                else:
                    for source in task['sources']:
                        entry={'domain':source['domain'],'status':'checked','checked_url':source['url'],'result':'Historical valid source result','candidates':[],
                               'checks':[{'url':u,'status':'checked','result':'Original checked'} for u in source['required_checks']]}
                        if source['domain']=='arxiv.org':entry['title_discovery']=title_discovery_fixture()
                        p.record(run,task['id'],entry)
            self.assertEqual(p.assemble(run)['status'],'research_complete')
            manifest['integrity_version']=1;p.write(run/'manifest.json',manifest)
            with self.assertRaisesRegex(ValueError,'receipt'):
                p.assemble(run)
            self.assertTrue(p.missing(run,manifest['tasks'][0]), 'invalid existing checkpoint cannot count complete')


if __name__ == '__main__':
    unittest.main()
