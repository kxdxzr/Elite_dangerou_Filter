"""Minor faction name suggestions, never an assertion of presence or control."""
import difflib
import re
import threading
import time
import urllib.parse
from collections import OrderedDict

import filter_engine as eng

_lock = threading.Lock()
_known = {}
_queries = OrderedDict()
TTL = 900


def key(name):
    return ' '.join(re.findall(r'\w+', str(name).casefold()))


def remember(names):
    with _lock:
        for name in names:
            if isinstance(name, str) and name.strip():
                _known.setdefault(name.strip().casefold(), name.strip())


def rank_names(names, query, limit=20):
    q = key(query)
    if len(q) < 2:
        return []
    acronym = len(q.split()) > 1 and all(len(word) == 1 for word in q.split())
    unique = {}
    for name in names:
        if isinstance(name, str) and name.strip():
            unique.setdefault(name.strip().casefold(), name.strip())
    def score(name):
        normalized = key(name)
        compact, compact_name = q.replace(' ', ''), normalized.replace(' ', '')
        if normalized == q or compact_name == compact:
            return (0, 0, name.casefold())
        if normalized.startswith(q) or compact_name.startswith(compact):
            return (1, len(normalized), name.casefold())
        if all(word in normalized if len(word) > 1 else word in normalized.split() for word in q.split()):
            return (2, len(normalized), name.casefold())
        if not acronym and compact in compact_name:
            return (3, len(normalized), name.casefold())
        return (4, -difflib.SequenceMatcher(None, compact, compact_name).ratio(), name.casefold())
    scored = [(score(name), name) for name in unique.values()]
    threshold = 0.8 if len(q.replace(' ', '')) <= 4 else 0.45
    return [name for order, name in sorted(scored) if order[0] < 4 or -order[1] >= threshold][:max(0, limit)]


def _fetch(query):
    data = eng._http_json(eng.SPansh_BASE + '/systems/field_values/minor_factions?q=' +
                          urllib.parse.quote(query), timeout=15)
    values = data.get('values') if isinstance(data, dict) else data
    if not isinstance(values, list):
        raise ValueError('Invalid minor-faction suggestion response')
    return [name if isinstance(name, str) else name.get('name', '')
            for name in values if isinstance(name, (str, dict))]


def suggest_factions(query, limit=20):
    q = key(query)
    # Preserve punctuation in the server's literal substring search. Normalized
    # tokens are for ranking only (e.g. People's / T.O.C. are real names).
    request_query = ' '.join(str(query).strip().casefold().split())
    if len(q) < 2:
        return []
    with _lock:
        cached = _queries.get(request_query)
        if cached and time.monotonic() - cached[0] < TTL:
            _queries.move_to_end(request_query)
            return rank_names(cached[1], q, limit)
        local = list(_known.values())
    try:
        names = _fetch(request_query)
        if not rank_names(names, q, limit) and re.search(r'[^\w\s]', request_query):
            compact_query = q.replace(' ', '')
            if len(compact_query) >= 2:
                names += _fetch(compact_query)
        # A misspelling often misses substring search; broaden only when needed.
        if not rank_names(names, q, limit) and len(q) > 2:
            prefix = q.replace(' ', '')[:2]
            names += _fetch(prefix)
    except Exception:
        local_hits = rank_names(local, q, limit)
        if local_hits:
            return local_hits
        raise  # UI distinguishes service failure from no names found.
    remember(names)
    result = rank_names(names + local, q, limit)
    with _lock:
        _queries[request_query] = (time.monotonic(), names + local)
        _queries.move_to_end(request_query)
        while len(_queries) > 128:
            _queries.popitem(last=False)
    return result
