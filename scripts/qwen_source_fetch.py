#!/usr/bin/env python3
"""Read Qwen's public site-backing API, not its stale legacy page_config list.

Observed in qwen.ai/research's resource requests on 2026-10-19. A successful
request proves retrieval only, never absence of newer releases or full coverage.
"""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import signal
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from browser_source_fetch import UA

INDEX_URL = 'https://qwen.ai/api/v2/article/retrieval?type=qwen_ai&language=en-US'


def parse_index(payload):
    if payload.get('success') is not True or not isinstance(payload.get('data', {}).get('articles'), list):
        raise ValueError('Qwen API did not return an article list')
    articles = []
    for item in payload['data']['articles']:
        published = item.get('extra', {}).get('date')
        if not isinstance(published, str):
            raise ValueError('Qwen article has no source publication date')
        if datetime.fromisoformat(published.replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('Qwen source timestamp requires timezone')
        articles.append({'path': item['path'], 'title': item['title'],
                         'published_at': published,
                         'url': 'https://qwen.ai/blog?' + urlencode({'id': item['path']})})
    if len({item['path'] for item in articles}) != len(articles):
        raise ValueError('Duplicate Qwen article paths; do not claim a reconciled count')
    articles.sort(key=lambda item: datetime.fromisoformat(item['published_at'].replace('Z', '+00:00')), reverse=True)
    return {'url': INDEX_URL, 'article_count': len(articles), 'articles': articles,
            'latest_published_at': articles[0]['published_at'] if articles else None,
            'discovery_complete': False,
            'limitation': 'No declared total or pagination contract; list retrieval is not complete current-source coverage.'}


CODE_RELEASES_URL = 'https://api.github.com/repos/QwenLM/qwen-code/releases?per_page=30'


def parse_code_releases(payload):
    if not isinstance(payload, list):
        raise ValueError('GitHub did not return public Qwen Code releases')
    articles = []
    for item in payload:
        if item.get('draft'):
            continue
        published = item.get('published_at')
        if not isinstance(published, str):
            raise ValueError('Qwen Code release has no publication date')
        datetime.fromisoformat(published.replace('Z', '+00:00'))
        url = item['html_url']
        if not url.startswith('https://github.com/QwenLM/qwen-code/releases/tag/'):
            raise ValueError('Unexpected release owner')
        articles.append({'path': item['tag_name'], 'title': item.get('name') or item['tag_name'],
                         'published_at': published, 'url': url,
                         'prerelease': item['prerelease'], 'text': item.get('body') or ''})
    articles.sort(key=lambda item: item['published_at'], reverse=True)
    return {'url': CODE_RELEASES_URL, 'articles': articles, 'article_count': len(articles),
            'latest_published_at': articles[0]['published_at'] if articles else None,
            'discovery_complete': False,
            'limitation': 'Only one bounded release page; Qwen Code is not complete Qwen model/company coverage.'}


def retrieve_payload(url, timeout=45):
    """Bound connection and body retrieval together (Linux CLI/main thread)."""
    def deadline_expired(signum, frame):
        raise TimeoutError('Qwen network retrieval exceeded total deadline')

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    started = time.monotonic()
    try:
        signal.signal(signal.SIGALRM, deadline_expired)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        with urlopen(Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'}), timeout=timeout) as response:
            raw = response.read(10_000_001)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        remaining, interval = previous_timer
        if remaining:
            remaining = max(0.000001, remaining - (time.monotonic() - started))
        signal.setitimer(signal.ITIMER_REAL, remaining, interval)
    if len(raw) > 10_000_000:
        raise ValueError('Qwen response exceeds 10 MB bound; coverage remains incomplete')
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--from-json', help='Offline replay of saved raw JSON; retrieval time is unknown')
    parser.add_argument('--code-releases', action='store_true', help='Read QwenLM/qwen-code public release notes')
    args = parser.parse_args()
    url = CODE_RELEASES_URL if args.code_releases else INDEX_URL
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    raw_path = Path(args.from_json) if args.from_json else output.with_suffix('.raw.json')
    if args.from_json:
        payload = json.loads(raw_path.read_text(encoding='utf-8'))
        provenance = {'offline': True, 'replayed_at': datetime.now(timezone.utc).isoformat(),
                      'retrieved_at': None}
    else:
        payload = retrieve_payload(url)
        provenance = {'offline': False, 'retrieved_at': datetime.now(timezone.utc).isoformat()}
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = parse_code_releases(payload) if args.code_releases else parse_index(payload)
    report.update(provenance)
    report.update(raw_cache=str(raw_path),
                  text='\n'.join(f"{item['published_at']} {item['title']} {item['url']}\n{item.get('text', '')}" for item in report['articles']))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('url', 'article_count', 'latest_published_at', 'discovery_complete', 'limitation')}))


if __name__ == '__main__':
    main()
