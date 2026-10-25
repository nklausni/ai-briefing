#!/usr/bin/env python3
"""Executable research receipts. Reservations are not executions.

Raw responses and source caches remain local, immutable and hash-bound. This
prevents accidental unsupported attestations, not a malicious writer with disk access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import re
from datetime import datetime, timezone

POLICY_DATE = '2026-10-25'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def search(run, task, query, limit=6, backend=None):
    """Execute a reserved query exactly once and persist its actual raw return."""
    from research_pipeline import reserve, read, locked
    run = Path(run)
    key = hashlib.sha256((task+'\n'+query).encode()).hexdigest()[:24]
    receipt_path = run/'receipts'/('search-'+key+'.json')
    with locked(run):
        if receipt_path.exists():
            return str(receipt_path)
    reservations = read(run/'searches'/f'{task}.json') if (run/'searches'/f'{task}.json').exists() else []
    if not any(r['query']==query for r in reservations):
        reserve(run, task, query)
    # Exclusive attempt marker prevents duplicate calls after interruption/concurrency.
    marker = run/'receipts'/('attempt-'+key+'.json')
    save(marker, {'task':task,'query':query,'started_at':datetime.now(timezone.utc).isoformat()})
    try:
        if backend is None:
            sys.path.insert(0, '/opt/hermes')
            from tools.web_tools import web_search_tool
            backend = web_search_tool
        raw = backend(query, limit=limit)
        data = json.loads(raw) if isinstance(raw,str) else raw
    except Exception as exc:
        data = {'success':False,'error':str(exc)}
    raw_path = run/'receipts'/('response-'+key+'.json')
    save(raw_path, data)
    ok = isinstance(data,dict) and data.get('success') is True and isinstance(data.get('data',{}).get('web'),list)
    receipt = {'kind':'search','task':task,'query':query,'status':'success' if ok else 'failed',
               'retrieved_at':datetime.now(timezone.utc).isoformat(),'raw_path':str(raw_path),
               'raw_sha256':digest(raw_path),'results':data.get('data',{}).get('web',[]) if isinstance(data,dict) else []}
    save(receipt_path,receipt)
    return str(receipt_path)


def load_receipt(path, kind):
    r=json.loads(Path(path).read_text())
    if r.get('kind')!=kind or r.get('status')!='success':
        raise ValueError(kind+' receipt is not a successful execution')
    raw=Path(r['raw_path'])
    if digest(raw)!=r['raw_sha256']:
        raise ValueError('receipt raw hash mismatch')
    data=json.loads(raw.read_text())
    if kind=='search' and (data.get('success') is not True or not isinstance(data.get('data',{}).get('web'),list)):
        raise ValueError('Search raw response was not successful')
    return r


def attest_cache(cache_path, expected_url, receipt_path):
    """Bind an existing, actually retrieved cache without changing its contents."""
    data=json.loads(Path(cache_path).read_text())
    if data.get('url')!=expected_url:
        raise ValueError('Source-cache URL identity mismatch')
    text=data.get('text','')
    ok=bool(isinstance(text,str) and text.strip()) and not data.get('error')
    receipt={'kind':'retrieval','url':expected_url,'status':'success' if ok else 'failed',
             'raw_path':str(Path(cache_path).resolve()),'raw_sha256':digest(cache_path),
             'retrieved_at':data.get('retrieved_at')}
    save(Path(receipt_path),receipt)
    return str(receipt_path)


def normalized(text):
    return re.sub(r'\s+',' ',text).strip()


def validate_evidence(item):
    if not item.get('receipt'):
        raise ValueError('Original evidence retrieval receipt required')
    receipt=load_receipt(item['receipt'],'retrieval')
    if receipt.get('url')!=item['url']:
        raise ValueError('Evidence URL identity mismatch')
    source=json.loads(Path(receipt['raw_path']).read_text())
    if source.get('url')!=item['url']:
        raise ValueError('Original cache URL identity mismatch')
    if normalized(item['excerpt']) not in normalized(source.get('text','')):
        raise ValueError('Evidence excerpt absent from retrieved original')
    return source


def validate_candidate_identity(candidate):
    originals=[]
    for item in candidate.get('evidence',[]):
        source=validate_evidence(item)
        if item['url']==candidate['url']:
            originals.append(source)
    if not originals:
        raise ValueError('Candidate original retrieval receipt missing')
    if re.match(r'https?://(?:www\.)?arxiv.org/(?:abs|html)/',candidate['url']):
        title=candidate.get('original_title','')
        if not title or not any(normalized(title).casefold() in normalized(s.get('text','')).casefold() for s in originals):
            raise ValueError('arXiv original title/URL identity mismatch')


def validate_reports(entry):
    reports=entry.get('title_discovery_files',[])
    actual=[{k:v for k,v in json.loads(Path(path).read_text()).items() if k!='titles'} for path in reports]
    if not reports or actual!=entry.get('title_discovery'):
        raise ValueError('arXiv helper report URL/content mismatch')


def validate_entry(run, task, entry):
    """Called by both record and assemble, not merely worker instructions."""
    searches=entry.get('search_receipts',[])
    if not searches:
        raise ValueError('Executed search receipt required; a reservation is not evidence')
    reservations=json.loads((Path(run)/'searches'/f"{task['id']}.json").read_text())
    queries={r['query'] for r in reservations}
    for path in searches:
        r=load_receipt(path,'search')
        if r['task']!=task['id'] or r['query'] not in queries:
            raise ValueError('Search receipt task/query does not match reservation')
    if task['kind']=='sources' and not any(entry['domain'] in load_receipt(path,'search')['query'] for path in searches):
        raise ValueError('Search receipt does not target assigned source')
    if task['kind']=='sources':
        refs=entry.get('source_receipts',[])
        if not refs:
            raise ValueError('Source retrieval receipt required')
        bound=[]
        for path in refs:
            r=json.loads(Path(path).read_text())
            if r.get('kind')!='retrieval' or digest(r['raw_path'])!=r['raw_sha256']:
                raise ValueError('Invalid source retrieval receipt')
            bound.append(r)
        if not any(r.get('url')==entry['checked_url'] for r in bound):
            raise ValueError('Source checked URL identity mismatch')
        if entry['status']=='checked' and not any(r.get('status')=='success' for r in bound):
            raise ValueError('Failed retrieval cannot count as checked')
    for candidate in entry.get('candidates',[]):
        validate_candidate_identity(candidate)
    if entry.get('domain')=='arxiv.org' and entry.get('status')=='checked':
        validate_reports(entry)
    if task['kind']=='discovery':
        mapping=entry.get('topic_searches',{})
        if set(mapping)!=set(task['topics']) or any(not refs or not set(refs)<=set(searches) for refs in mapping.values()):
            raise ValueError('Every discovery topic needs executed search receipts')
        if len({ref for refs in mapping.values() for ref in refs})<len(task['topics']):
            raise ValueError('Distinct thematic searches required for all topics')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir',type=Path,required=True)
    ap.add_argument('--task')
    ap.add_argument('--query')
    ap.add_argument('--cache',type=Path)
    ap.add_argument('--url')
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    if args.cache:
        if not args.url or not args.output:ap.error('--cache needs --url and --output')
        print(attest_cache(args.cache,args.url,args.output))
    else:
        if not args.task or not args.query:ap.error('search needs --task and --query')
        print(search(args.run_dir,args.task,args.query))

if __name__=='__main__':main()
