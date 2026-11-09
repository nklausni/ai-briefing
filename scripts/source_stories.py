"""Group angles on a dated source article for display without altering editorial records."""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

from history import parse_date

# A section, feed or continuously updated listing does not identify a single story.
LISTINGS = {'news', 'blog', 'articles', 'feed', 'rss', 'changelog', 'release-notes',
            'releases', 'archive', 'index', 'index.html', 'recent', 'latest', 'updates'}
MILESTONES = {'announcement', 'preview', 'public_beta', 'general_availability'}


def article_key(item):
    sources = item.get('sources') or []
    date = parse_date(item.get('date'))
    if not sources or not date:
        return None
    try:
        url = urlsplit(sources[0].get('url', ''))
    except ValueError:
        return None
    if url.scheme not in ('https', 'http') or not url.hostname:
        return None
    path = url.path.rstrip('/')
    query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    if (not path or path.split('/')[-1].lower() in LISTINGS) and not query:
        return None
    # Multi-product roundups can be evidence for several independent events.
    if re.search(r'/(?:list/|tags?/|categor(?:y|ies)/)|(?:daily-digest|radar-brief-|/aidevpulse-20)', path, re.I):
        return None
    stage = item.get('change_type')
    return (date, url.netloc.lower(), path, urlencode(query), url.fragment,
            stage if stage in MILESTONES else '')


def grouped(items):
    """First row is the lead. Further angles retain their sources, text and topic."""
    leads, seen = [], {}
    for item in items:
        key = article_key(item)
        if key is not None and key in seen:
            seen[key].setdefault('angles', []).append(item)
        else:
            lead = dict(item)
            leads.append(lead)
            if key is not None:
                seen[key] = lead
    return leads
