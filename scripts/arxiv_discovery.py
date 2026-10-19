#!/usr/bin/env python3
"""Bounded source-owned arXiv title discovery, not paper/fulltext coverage.

Listing dates are evidence of public listing, NOT submission timestamps or an
inferred announcement schedule. See docs/arxiv-source-policy.md.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time as clock_time, timedelta, timezone
from html import unescape
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen

BASE_URL = 'https://arxiv.org/list/cs.AI/recent'


def text(html):
    return ' '.join(unescape(re.sub(r'<[^>]+>', ' ', html)).split())


def parse_listing(html, url):
    changes_day = re.search(r'Showing new listings for (\w+, \d{1,2} \w+ \d{4})', text(html))
    sections = dict(re.findall(r'(New|Cross|Replacement) submissions \(showing \d+ of ([\d,]+) entries\)', text(html)))
    total = re.search(r'Total of\s+([\d,]+)\s+entries', text(html))
    if not total and changes_day and sections:
        declared = sum(int(n.replace(',', '')) for n in sections.values())
    elif total:
        declared = int(total[1].replace(',', ''))
    else:
        raise ValueError('Missing source-declared total (wrong page or changed listing)')
    days, entries = {}, []
    current = None
    kind = None
    paper = None
    for token in re.finditer(r'<h3\b[^>]*>(.*?)</h3>|<dt\b[^>]*>(.*?)</dt>|<dd\b[^>]*>(.*?)</dd>', html, re.S | re.I):
        heading, dt, dd = token.groups()
        if heading is not None:
            label = text(heading)
            if changes_day:
                current = datetime.strptime(changes_day[1], '%A, %d %B %Y').date().isoformat()
                days[current] = declared
                kind = next((value for prefix, value in [('New submissions', 'new'), ('Cross submissions', 'cross'), ('Replacement submissions', 'replace')] if label.startswith(prefix)), None)
                continue
            day = re.match(r'(\w{3}, \d{1,2} \w{3} \d{4})', label)
            count = re.search(r'(?:of\s+)?([\d,]+)\s+entries', label)
            if not day or not count:
                raise ValueError('Unrecognized listing date/count: ' + label)
            current = datetime.strptime(day[1], '%a, %d %b %Y').date().isoformat()
            days[current] = int(count[1].replace(',', ''))
        elif dt is not None:
            match = re.search(r'href\s*=\s*[\'"](?:https://arxiv.org)?/abs/([^\'"\s]+)', dt)
            paper = match[1] if match else None
        elif dd is not None:
            title = re.search(r'<div\b[^>]*class=[\'"][^\'"]*\blist-title\b[^\'"]*[\'"][^>]*>(.*?)</div>', dd, re.S | re.I)
            if not current or not paper or not title:
                raise ValueError('Listing entry missing date, identifier or title')
            entries.append({'id': re.sub(r'v\d+$', '', paper), 'version_id': paper,
                            'title': re.sub(r'^Title:\s*', '', text(title[1])),
                            'url': 'https://arxiv.org/abs/' + paper,
                            'listed_on': current, 'listing_url': url, 'announce_type': kind})
    return {'declared_total': declared, 'days': days, 'entries': entries}


def fetch_page(url, timeout):
    request = Request(url, headers={'User-Agent': 'AI-Briefing/1.0 (read-only source title discovery)'})
    with urlopen(request, timeout=timeout) as response:
        body = response.read(12_000_001)
        if len(body) > 12_000_000:
            raise ValueError('Source response exceeds bounded 12 MB; incomplete listing')
        return body.decode('utf-8')


def collect(since, until, *, fetch=fetch_page, page_size=2000, max_pages=4,
            deadline_seconds=60, pause=3, base_url=BASE_URL, kind='recent'):
    """Return honest partial results on failure; persist before surfacing exit 1."""
    start, end = date.fromisoformat(since), date.fromisoformat(until)
    if start > end or not 1 <= page_size <= 2000 or not 1 <= max_pages <= 8:
        raise ValueError('Invalid window or bounded page settings')
    if kind not in {'recent', 'changes'}:
        raise ValueError('Unknown listing kind')
    if kind == 'changes':
        base_url = 'https://arxiv.org/list/cs.AI/new'
    deadline = time.monotonic() + deadline_seconds
    pages, limitations, days, entries = [], [], {}, {}
    declared, skip = None, 0
    for _ in range(max_pages):
        url = f'{base_url}?skip={skip}&show={page_size}'
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            limitations.append('Source deadline reached')
            break
        try:
            parsed = parse_listing(fetch(url, min(20, remaining)), url)
        except Exception as exc:
            limitations.append(f'{url}: {type(exc).__name__}: {exc}')
            break
        pages.append({'url': url, 'skip': skip, 'received_count': len(parsed['entries']),
                      'declared_total': parsed['declared_total']})
        if declared is not None and declared != parsed['declared_total']:
            limitations.append('Source total changed during pagination')
            break
        declared = parsed['declared_total']
        for day, count in parsed['days'].items():
            if day in days and days[day] != count:
                limitations.append('Source day count changed during pagination: ' + day)
            days[day] = count
        before = len(entries)
        for entry in parsed['entries']:
            key = (entry['listed_on'], entry['id'])
            entries.setdefault(key, entry)
        if len(entries) == declared:
            break
        if len(entries) == before:
            limitations.append('Duplicate or empty page; pagination made no progress')
            break
        skip += len(parsed['entries'])
        if pause:
            time.sleep(min(pause, max(0, deadline - time.monotonic())))
    complete = declared is not None and len(entries) == declared and not limitations
    if not complete and not limitations:
        limitations.append('Page budget exhausted before declared total was collected')
    day_counts = {day: {'declared': count, 'collected': sum(e['listed_on'] == day for e in entries.values())}
                  for day, count in days.items()}
    if any(c['declared'] != c['collected'] for c in day_counts.values()) or sum(days.values()) != declared:
        complete = False
        limitations.append('Source day totals and deduplicated counts do not reconcile')
    # recent is a rolling listing; never imply arbitrary historical coverage.
    window_complete = complete and bool(days) and min(days) <= since and max(days) >= until
    if not window_complete and complete:
        limitations.append('Source listing does not establish the full requested date span; retrieve dated/monthly listings or report a gap')
    titles = [e for e in entries.values() if since <= e['listed_on'] <= until]
    return {'schema_version': 1, 'source_url': base_url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'since': since, 'until': until, 'declared_total': declared, 'collected_count': len(entries),
            'window_count': len(titles), 'complete': complete, 'window_complete': window_complete,
            'coverage_kind': 'titles_only', 'listing_kind': kind, 'days': day_counts, 'pages': pages,
            'next_skip': None if complete else skip, 'limitations': limitations, 'titles': titles}


def collect_updates(since, until, *, fetch=fetch_page, page_size=2000, max_pages=4,
                    deadline_seconds=60, pause=3):
    """API discovery includes seven overlap days; timestamps are not release dates.

    This supplements recent/new listings for replacement recovery. API results
    never establish public-announcement freshness by themselves.
    """
    berlin = ZoneInfo('Europe/Berlin')
    first, last = date.fromisoformat(since), date.fromisoformat(until)
    if first > last or not 1 <= page_size <= 2000 or not 1 <= max_pages <= 8:
        raise ValueError('Invalid window or bounded page settings')
    lower = datetime.combine(first - timedelta(days=7), clock_time.min, berlin).astimezone(timezone.utc)
    upper = (datetime.combine(last + timedelta(days=1), clock_time.min, berlin) - timedelta(minutes=1)).astimezone(timezone.utc)
    query = f'cat:cs.AI AND lastUpdatedDate:[{lower:%Y%m%d%H%M} TO {upper:%Y%m%d%H%M}]'
    source = 'https://export.arxiv.org/api/query'
    ns = {'a': 'http://www.w3.org/2005/Atom', 'os': 'http://a9.com/-/spec/opensearch/1.1/'}
    deadline = time.monotonic() + deadline_seconds
    pages, entries, limitations = [], {}, []
    declared, cursor = None, 0
    for _ in range(max_pages):
        url = source + '?' + urlencode({'search_query': query, 'sortBy': 'lastUpdatedDate',
                                       'sortOrder': 'descending', 'start': cursor, 'max_results': page_size})
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            limitations.append('Source deadline reached')
            break
        try:
            xml = ET.fromstring(fetch(url, min(20, remaining)))
            total = int(xml.findtext('os:totalResults', namespaces=ns))
            start = int(xml.findtext('os:startIndex', namespaces=ns))
            if start != cursor or declared is not None and total != declared:
                raise ValueError('API cursor/total changed during pagination')
            declared = total
            batch = xml.findall('a:entry', ns)
            pages.append({'url': url, 'skip': cursor, 'received_count': len(batch), 'declared_total': total})
            before = len(entries)
            for node in batch:
                original = node.findtext('a:id', namespaces=ns)
                match = re.fullmatch(r'https?://arxiv.org/abs/([^/]+)v(\d+)', original or '')
                if not match:
                    raise ValueError('API entry missing versioned arXiv identifier')
                entries.setdefault(match[1], {'id': match[1], 'version': int(match[2]),
                    'url': 'https://arxiv.org/abs/' + match[1] + 'v' + match[2],
                    'title': ' '.join((node.findtext('a:title', namespaces=ns) or '').split()),
                    'submitted_at': node.findtext('a:published', namespaces=ns),
                    'updated_at': node.findtext('a:updated', namespaces=ns), 'metadata_url': url})
            if len(entries) == declared:
                break
            if len(entries) == before:
                raise ValueError('Duplicate or empty API page; no progress')
            cursor += len(batch)
        except Exception as exc:
            limitations.append(f'{url}: {type(exc).__name__}: {exc}')
            break
        if pause:
            time.sleep(min(pause, max(0, deadline - time.monotonic())))
    complete = declared is not None and len(entries) == declared and not limitations
    if not complete and not limitations:
        limitations.append('API page budget exhausted before declared total was collected')
    return {'schema_version': 1, 'source_url': source, 'listing_kind': 'updates',
            'coverage_kind': 'titles_and_submission_metadata_only', 'since': since, 'until': until,
            'query': query, 'overlap_days': 7, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'declared_total': declared, 'collected_count': len(entries), 'window_count': len(entries),
            'complete': complete, 'window_complete': complete, 'pages': pages,
            'next_skip': None if complete else cursor, 'limitations': limitations, 'titles': list(entries.values())}


def validate_title_discovery(reports):
    """Validate compact persisted coverage claims; partial access is not a run failure."""
    if not isinstance(reports, list) or {r.get('listing_kind') for r in reports if isinstance(r, dict)} != {'recent', 'changes', 'updates'} or len(reports) != 3:
        return ['arxiv.org: title_discovery requires recent, changes and updates reports']
    errors = []
    for report in reports:
        expected = {'recent': BASE_URL, 'changes': 'https://arxiv.org/list/cs.AI/new', 'updates': 'https://export.arxiv.org/api/query'}[report['listing_kind']]
        prefix = 'arxiv.org: title_discovery ' + report['listing_kind'] + ': '
        if report.get('source_url') != expected or not isinstance(report.get('pages'), list):
            errors.append(prefix + 'missing source URL/pages')
        for page in report.get('pages') or []:
            if not isinstance(page, dict) or not isinstance(page.get('url'), str) or not page['url'].startswith(expected + '?') or not isinstance(page.get('skip'), int):
                errors.append(prefix + 'invalid source cursor')
        declared, collected = report.get('declared_total'), report.get('collected_count')
        if not isinstance(collected, int) or collected < 0 or declared is not None and (not isinstance(declared, int) or declared < 0):
            errors.append(prefix + 'invalid counts')
        if type(report.get('complete')) is not bool or type(report.get('window_complete')) is not bool:
            errors.append(prefix + 'explicit completeness flags required')
        if report.get('complete'):
            if declared is None or declared != collected or report.get('next_skip') is not None or not report.get('pages') or report.get('limitations') and report.get('window_complete'):
                errors.append(prefix + 'complete claim contradicts counts/cursors/limitations')
        elif not report.get('limitations'):
            errors.append(prefix + 'incomplete discovery needs declared limitations')
        if report.get('window_complete') and not report.get('complete'):
            errors.append(prefix + 'incomplete listing cannot cover a complete window')
    return errors


def freshness_date(metadata, published_at):
    """Use evidenced release/listing day, while retaining original submission date.

    API published/updated are submission timestamps. RSS Atom published is an
    announcement timestamp. Feed generated/updated timestamps are NOT release dates.
    """
    required = ('submitted_at', 'listed_on', 'listing_url', 'announcement_url', 'announce_type')
    if not isinstance(metadata, dict) or any(not isinstance(metadata.get(field), str) or not metadata[field] for field in required) or type(metadata.get('version')) is not int:
        raise ValueError('arxiv_dates requires submission, listing, announcement provenance and integer version')
    submitted = datetime.fromisoformat(metadata['submitted_at'].replace('Z', '+00:00'))
    release_submission = submitted
    if submitted.tzinfo is None or submitted.date().isoformat() != published_at:
        raise ValueError('Keep published_at equal to the original submission date; require timezone')
    listed = date.fromisoformat(metadata['listed_on'])
    for field in ('listing_url', 'announcement_url'):
        url = urlparse(metadata[field])
        if url.scheme != 'https' or url.hostname not in {'arxiv.org', 'rss.arxiv.org'} or not url.path.startswith(('/list/', '/atom/', '/rss/')):
            raise ValueError('Public release needs source-owned listing/announcement URLs')
    kind = metadata['announce_type']
    version = metadata['version']
    if kind == 'new':
        if version != 1:
            raise ValueError('New release must be version 1, not an update')
    elif kind in {'replace', 'replace-cross'}:
        if not isinstance(version, int) or version < 2 or metadata.get('substantive_update') is not True:
            raise ValueError('Replacement needs a substantive verified version update')
        if not isinstance(metadata.get('updated_at'), str):
            raise ValueError('Replacement needs version submission timestamp updated_at')
        updated = datetime.fromisoformat(metadata['updated_at'].replace('Z', '+00:00'))
        release_submission = updated
        if updated.tzinfo is None or updated < submitted or updated.astimezone(ZoneInfo('Europe/Berlin')).date() > listed:
            raise ValueError('Invalid version update timestamp')
    else:
        raise ValueError('Cross-listing alone is not a new publication or substantive update')
    if submitted.astimezone(ZoneInfo('Europe/Berlin')).date() > listed:
        raise ValueError('Listing precedes submission')
    announced = metadata.get('announced_at')
    if announced:
        instant = datetime.fromisoformat(announced.replace('Z', '+00:00'))
        if instant.tzinfo is None or instant < release_submission or instant.astimezone(ZoneInfo('Europe/Berlin')).date() != listed:
            raise ValueError('Announcement instant and listing day disagree in Europe/Berlin')
    return listed.isoformat()


def title_page(path, offset=0, limit=50):
    """Compact pagination for worker review; full titles, no abstract payloads."""
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError('Invalid title page offset/limit')
    titles = json.loads(Path(path).read_text(encoding='utf-8'))['titles']
    fields = ('id', 'title', 'listed_on', 'announce_type', 'version', 'submitted_at', 'updated_at')
    items = [{key: title[key] for key in fields if key in title} for title in titles[offset:offset + limit]]
    next_offset = offset + len(items)
    return {'file': str(path), 'offset': offset, 'total': len(titles), 'items': items,
            'next_offset': next_offset if next_offset < len(titles) else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--since')
    mode.add_argument('--view')
    parser.add_argument('--until')
    parser.add_argument('--output')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--kind', choices=('recent', 'changes', 'updates'), default='recent')
    args = parser.parse_args()
    if args.view:
        print(json.dumps(title_page(args.view, args.offset, args.limit), ensure_ascii=False))
        return 0
    if not args.until or not args.output:
        parser.error('--since requires --until and --output')
    result = collect_updates(args.since, args.until) if args.kind == 'updates' else collect(args.since, args.until, kind=args.kind)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'titles'}, ensure_ascii=False))
    return 0 if result['complete'] and result['window_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
