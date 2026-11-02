"""Strict receipt ownership must survive a bounded task retry."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import research_pipeline as p
import research_integrity as ri


class StrictRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'repo'
        self.run=Path(self.tmp.name)/'run'
        p.write(self.root/'data/briefing.json',{'topics':[]})
        self.manifest=p.prepare(self.root,self.run,'2026-11-02')
        self.batch=p.dispatch_ready(self.run)['batch']

    def search(self,task,query):
        return ri.search(self.run,task,query,backend=lambda *a,**k:{'success':True,'data':{'web':[]}})

    def source(self,task,source):
        cache=self.run/(task+'-'+source['domain']+'-cache.json')
        p.write(cache,{'url':source['url'],'retrieved_at':'2026-11-02T08:00:00Z','text':'Fixture unavailable source response.','error':'fixture unavailable'})
        receipt=ri.attest_cache(cache,source['url'],cache.with_suffix('.receipt.json'))
        return {'domain':source['domain'],'status':'unavailable','checked_url':source['url'],
                'result':'Fixture source unavailable after bounded retrieval attempts.','candidates':[],
                'checks':[{'url':u,'status':'unavailable','result':'Fixture retrieval failed.'} for u in source['required_checks']],
                'source_receipts':[receipt],'search_receipts':[self.search(task,'site:'+source['domain']+' fixture')]}

    def discovery(self,task):
        mapping={topic:[self.search(task,'fixture '+topic)] for topic in p.TOPICS}
        return {'topics_checked':list(p.TOPICS),'result':'Fixture eight-topic search completed.',
                'candidates':[],'topic_searches':mapping,'search_receipts':[v[0] for v in mapping.values()]}

    def test_retry_checkpoint_satisfies_original_source_task_without_relabelling_receipts(self):
        original=next(t for t in self.manifest['tasks'] if t['kind']=='sources')
        source=original['sources'][0]
        p.complete_batch_and_dispatch(self.run,self.batch['task_ids'])
        retry=p.task_for(self.run,original['id']+'-retry')[1]
        entry=self.source(retry['id'],source)
        p.record(self.run,retry['id'],entry)
        self.assertNotIn(source['domain'],p.missing(self.run,original))
        self.assertNotIn(source['domain'],p.missing(self.run,retry))
        saved=p.read(p.checkpoint_path(self.run,source['domain']))
        self.assertEqual(saved['task_id'],retry['id'])
        self.assertEqual(ri.load_receipt(saved['search_receipts'][0],'search')['task'],retry['id'])
        # Same bytes with an unrelated packet owner are never accepted.
        saved['task_id']='sources-02'
        p.write(p.checkpoint_path(self.run,source['domain']),saved)
        self.assertIn(source['domain'],p.missing(self.run,original))

    def test_retry_discovery_assembles_with_its_actual_executed_receipts(self):
        for task in self.manifest['tasks']:
            if task['kind']=='sources':
                for source in task['sources']:
                    p.record(self.run,task['id'],self.source(task['id'],source))
        next_batch=p.complete_batch_and_dispatch(self.run,self.batch['task_ids'])['batch']
        self.assertEqual(next_batch['task_ids'],['discovery-retry'])
        entry=self.discovery('discovery-retry')
        p.record(self.run,'discovery-retry',entry)
        completion=p.complete_batch_and_dispatch(self.run,['discovery-retry'])
        self.assertEqual(completion['status'],'no_pending_tasks')
        self.assertEqual(p.assemble(self.run)['status'],'research_complete')
        saved=p.read(self.run/'discovery.json')
        self.assertEqual(saved['task_id'],'discovery-retry')
        # Hash-bound receipt failures remain fatal even through the retry path.
        raw=Path(ri.load_receipt(saved['search_receipts'][0],'search')['raw_path'])
        p.write(raw,{'success':False,'error':'tampered fixture'})
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            p.assemble(self.run)

if __name__=='__main__':unittest.main()
