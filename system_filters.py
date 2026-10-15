"""Local system-level counts and existential body/nearest-neighbour conditions.

Detailed data is loaded only after cheap main-window conditions pass. Matching
itself is pure: unprepared or unknown evidence never becomes a positive match.
"""
import json
from concurrent.futures import ThreadPoolExecutor

import colonisation_tool as bodies
from system_filter_fields import COUNT_FIELDS
FACTION_FIELDS = set(COUNT_FIELDS) - {'station_count', 'carrier_count'}


def validate(condition):
    c = dict(condition)
    if not isinstance(c.get('body_groups', []), list) or not isinstance(c.get('ring_groups', []), list):
        raise ValueError('Planet/ring groups must be lists.')
    try:
        checked = bodies.Criteria(
            body_groups=c.get('body_groups', []), ring_groups=c.get('ring_groups', []),
            body_mode=c.get('body_mode', 'AND'), ring_mode=c.get('ring_mode', 'AND'),
            populated_min_distance=c.get('nearest_min'), populated_radius=c.get('nearest_max')).validate()
    except (AttributeError, TypeError) as exc:
        raise ValueError('Invalid system-detail condition.') from exc
    c.update(type='system_details', field='__system_details__', op='matches',
             body_groups=checked.body_groups, ring_groups=checked.ring_groups,
             body_mode=checked.body_mode, ring_mode=checked.ring_mode,
             nearest_min=checked.populated_min_distance, nearest_max=checked.populated_radius)
    c['population_min'] = (bodies.optional_number(c.get('population_min', 1))
                           if c['nearest_min'] is not None or c['nearest_max'] is not None else 1)
    if c['population_min'] is None:
        raise ValueError('The population threshold is required when nearest-distance filtering is enabled.')
    return c


def signature(condition):
    return json.dumps(condition, ensure_ascii=False, sort_keys=True)


def outcome(row, condition):
    return row.get('_detail_outcomes', {}).get(signature(condition))


def faction_counts(row):
    """Count unique names. Unknown allegiance/government affects only its counts."""
    result = {key: None for key in FACTION_FIELDS}
    records = row.get('minor_faction_presences')
    if not isinstance(records, list):
        return result
    unique = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('name'), str) or not record['name'].strip():
            return result
        key = record['name'].strip().casefold()
        values = {field: str(record.get(field) or '').strip().casefold() for field in ('allegiance', 'government')}
        if key not in unique:
            unique[key] = values
        else:
            for field, value in values.items():
                if unique[key][field] != value:
                    unique[key][field] = ''  # Conflicting duplicate evidence is unknown.
    records = list(unique.values())
    result['minor_faction_count'] = len(records)
    allegiance_known = all(r['allegiance'] for r in records)
    government_known = all(r['government'] for r in records)
    eligible = [r for r in records if r['government'] != 'anarchy']
    for faction, label in (('federation', 'federation'), ('empire', 'empire'), ('alliance', 'alliance')):
        if allegiance_known:
            result[f'{faction}_faction_count'] = sum(r['allegiance'] == label for r in records)
    if government_known:
        result['potential_issuer_count'] = len(eligible)
        if allegiance_known:
            for faction in ('federation', 'empire'):
                result[f'{faction}_issuer_count'] = sum(r['allegiance'] == faction for r in eligible)
    return result


def prepare(rows, conditions, *, stop=None, max_pages=25, progress=None):
    """Enrich supplied cheap-filter survivors in place; never impose colony rules."""
    fields = {c.get('field') for c in conditions} & COUNT_FIELDS.keys()
    specs = [c for c in conditions if c.get('type') == 'system_details']
    for row in rows:
        row.pop('_detail_outcomes', None)
        row.pop('_system_details', None)
        for key in fields:
            row[key] = None  # Never trust a server-provided value for derived fields.
    if fields & {'station_count', 'carrier_count'}:
        missing = [r['name'] for r in rows if 'stations' not in r and r.get('name')]
        confirmed = {}
        for start in range(0, len(missing), 16):
            bodies.check_stop(stop)
            confirmed.update(bodies.confirm_station_absence(missing[start:start + 16], stop=stop))
        for row in rows:
            stations = confirmed.get(row.get('name', '').casefold(), row.get('stations'))
            if not isinstance(stations, list) or any(not isinstance(s, dict) for s in stations):
                continue
            if 'station_count' in fields:
                row['station_count'] = len(stations)
            if 'carrier_count' in fields and all(isinstance(s.get('type'), str) and s['type'].strip() for s in stations):
                row['carrier_count'] = sum('carrier' in s['type'].casefold() for s in stations)
    if fields & FACTION_FIELDS:
        for row in rows:
            counts = faction_counts(row)
            row.update({key: counts[key] for key in fields & FACTION_FIELDS})
    count_conditions = [c for c in conditions if c.get('field') in fields]
    detail_rows = [row for row in rows if all(bodies.eng.match_field('systems', row, c) for c in count_conditions)]
    detail_ids = {id(row) for row in detail_rows}
    full_bodies = {}
    if any(c['body_groups'] or c['ring_groups'] for c in specs):
        names = sorted({r['name'] for r in detail_rows if r.get('name')}, key=str.casefold)
        chunks = [names[i:i + 8] for i in range(0, len(names), 8)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for start in range(0, len(chunks), 4):
                bodies.check_stop(stop)
                futures = [pool.submit(bodies.load_bodies, chunk, stop=stop) for chunk in chunks[start:start + 4]]
                for future in futures:
                    full_bodies.update(future.result())
                if progress:
                    progress()
    for row in rows:
        bodies.check_stop(stop)
        if id(row) not in detail_ids:
            row['_system_details'] = dict(counts={key: row.get(key) for key in sorted(fields)}, groups=[], neighbours=[])
            continue
        records = full_bodies.get(row.get('name', '').casefold(), [])
        bodies.annotate_relationships(records)
        evidence = dict(counts={key: row.get(key) for key in sorted(fields)}, groups=[], neighbours=[])
        memo = {}
        for index, c in enumerate(specs, 1):
            body_hit, planets = bodies.match_groups(records, c['body_groups'], c['body_mode'])
            ring_hit, rings = bodies.match_groups(records, c['ring_groups'], c['ring_mode'], rings=True)
            values = [body_hit, ring_hit]
            if bodies.combine(values) is not False and (c['nearest_min'] is not None or c['nearest_max'] is not None):
                key = (c['population_min'], c['nearest_max'])
                if key not in memo:
                    memo[key] = bodies.populated_neighbour(row, c['nearest_max'], max_pages,
                                                         stop, population_min=c['population_min'])
                hit, name, population, distance = memo[key]
                if hit is True:
                    hit = c['nearest_min'] is None or distance >= c['nearest_min']
                    evidence['neighbours'].append(dict(condition=index, population_min=c['population_min'],
                                                        name=name, population=population, distance=distance))
                values.append(hit)
            row.setdefault('_detail_outcomes', {})[signature(c)] = bodies.combine(values)
            if planets or rings:
                evidence['groups'].append(dict(condition=index, planets=planets, rings=rings))
        evidence['relationships'] = '; '.join(f"{b['name']}: {b['_relations']}" for b in records if b.get('_relations'))
        row['_system_details'] = evidence


def summary(row):
    details = row.get('_system_details', {})
    parts = [f'{key}={value}' for key, value in details.get('counts', {}).items()]
    for group in details.get('groups', []):
        for field in ('planets', 'rings'):
            if group[field]:
                parts.append(f"{field}[{group['condition']}]: {group[field]}")
    for neighbour in details.get('neighbours', []):
        parts.append(f"nearest(pop>{neighbour['population_min']:g}): {neighbour['name']} "
                     f"/ pop {neighbour['population']:g} / {neighbour['distance']:.3f} ly")
    if details.get('relationships'):
        parts.append(details['relationships'])
    return ' | '.join(parts)
