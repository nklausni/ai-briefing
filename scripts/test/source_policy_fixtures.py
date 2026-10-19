"""Explicit synthetic coverage fixture for tests, never production evidence."""


def title_discovery_fixture():
    return [{'listing_kind': kind, 'source_url': ('https://export.arxiv.org/api/query' if kind == 'updates' else 'https://arxiv.org/list/cs.AI/' + suffix),
             'declared_total': 0, 'collected_count': 0, 'window_count': 0,
             'complete': True, 'window_complete': True, 'limitations': [],
             'pages': [{'url': ('https://export.arxiv.org/api/query' if kind == 'updates' else 'https://arxiv.org/list/cs.AI/' + suffix) + '?skip=0&show=2000', 'skip': 0}],
             'next_skip': None} for kind, suffix in [('recent', 'recent'), ('changes', 'new'), ('updates', 'updates')]]
