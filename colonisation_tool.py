"""Colonisation candidates, with existential body/ring groups and strict eligibility."""
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import filter_engine as eng
import pve_cache


BODY_FIELDS = {
    'subtype': '星球类型', 'is_landable': '可着陆',
    'terraforming_state': '地球化状态', 'gravity': '重力 G',
    'distance_to_arrival': '到达距离 Ls', 'surface_temperature': '表面温度 K',
    'surface_pressure': '表面气压 atm', 'atmosphere': '大气类型',
    'volcanism_type': '火山活动类型', 'radius': '半径 km',
    'earth_masses': '地球质量', 'is_rotational_period_tidally_locked': '潮汐锁定',
    'rotational_period': '自转周期 天', 'orbital_period': '公转周期 天',
    'orbital_eccentricity': '轨道偏心率', 'orbital_inclination': '轨道倾角 度',
    'semi_major_axis': '轨道半长轴 AU', 'reserve_level': '储量等级',
    'materials': '地表材料', 'signals': '信号类型', 'signal_count': '信号数量',
    'estimated_mapping_value': '天体估算测绘价值',
    'estimated_scan_value': '天体估算扫描价值',
    '_is_moon': '是卫星', '_has_moons': '拥有卫星', '_is_binary': '互绕成员（关系推定）',
    'ring.type': '星环类型', 'ring.inner_radius': '星环内半径 m',
    'ring.outer_radius': '星环外半径 m', 'ring.mass': '星环质量（源数据单位）',
}
RING_FIELDS = {key: value for key, value in BODY_FIELDS.items()
               if key.startswith('ring.') or key in ('distance_to_arrival', 'reserve_level', 'subtype')}
NUMERIC_FIELDS = set(BODY_FIELDS) - {
    'subtype', 'is_landable', 'terraforming_state', 'atmosphere', 'volcanism_type',
    'is_rotational_period_tidally_locked', 'reserve_level', 'materials', 'signals', 'ring.type'}
BOOL_FIELDS = {'is_landable', 'is_rotational_period_tidally_locked', '_is_moon', '_has_moons', '_is_binary'}
NUMERIC_FIELDS -= BOOL_FIELDS
OPERATORS = ('=', '!=', 'in', '>', '>=', '<', '<=', 'between')
VALUES = {
    'subtype': ['Earth-like world', 'Water world', 'Ammonia world', 'High metal content world',
                'Metal-rich body', 'Rocky body', 'Rocky Ice world', 'Icy body',
                'Class I gas giant', 'Class II gas giant', 'Class III gas giant',
                'Class IV gas giant', 'Class V gas giant', 'Gas giant with water-based life',
                'Gas giant with ammonia-based life', 'Helium-rich gas giant', 'Water giant'],
    'ring.type': ['Metallic', 'Metal Rich', 'Rocky', 'Icy'],
    'terraforming_state': ['Terraformable', 'Terraformed', 'Not terraformable', 'Terraforming'],
    'reserve_level': ['Pristine', 'Major', 'Common', 'Low', 'Depleted'],
    'is_landable': ['true', 'false'], 'is_rotational_period_tidally_locked': ['true', 'false'],
    'signals': ['Biological', 'Geological', 'Human', 'Guardian', 'Thargoid', 'Other'],
    'atmosphere': ['No atmosphere'],
}
VALUES.update({key: ['true', 'false'] for key in BOOL_FIELDS})


def annotate_relationships(bodies):
    """Derive relationships only from immediate parents, never shared stellar ancestry."""
    children = {}
    uncertain = False
    for body in bodies:
        parents = body.get('parents')
        if not isinstance(parents, list) or not parents or not isinstance(parents[0], dict):
            uncertain = uncertain or body.get('type') == 'Planet'
            continue
        parent = parents[0]
        if parent.get('id64') is not None:
            children.setdefault(str(parent['id64']), []).append(body)
    for body in bodies:
        if body.get('type') != 'Planet':
            continue
        body.update(_is_moon=None, _is_binary=None, _relations='')
        own_children = children.get(str(body.get('id64')), []) if body.get('id64') is not None else []
        moons = [child for child in own_children if child.get('type') == 'Planet']
        body['_has_moons'] = True if moons else None if uncertain or body.get('id64') is None else False
        parents = body.get('parents')
        if not isinstance(parents, list) or not parents or not isinstance(parents[0], dict):
            continue
        parent = parents[0]
        body['_is_moon'] = parent.get('type') == 'Planet' if parent.get('type') in ('Planet', 'Star', 'Null') else None
        if parent.get('type') != 'Null':
            body['_is_binary'] = False if parent.get('type') in ('Planet', 'Star') else None
        elif parent.get('id64') is not None:
            siblings = children.get(str(parent['id64']), [])
            if not uncertain and len(siblings) == 2 and all(s.get('type') == 'Planet' for s in siblings):
                periods = [number(s.get('orbital_period')) for s in siblings]
                if None not in periods and all(periods):
                    body['_is_binary'] = math.isclose(abs(periods[0]), abs(periods[1]), rel_tol=1e-6)
                    if body['_is_binary']:
                        body['_relations'] = 'Binary (inferred): ' + ', '.join(s['name'] for s in siblings if s is not body)
        if moons:
            body['_relations'] += ('; ' if body['_relations'] else '') + 'Moons: ' + ', '.join(m['name'] for m in moons)


def number(value):
    if isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def optional_number(value):
    if value is None or isinstance(value, str) and not value.strip():
        return None
    n = number(value)
    if n is None or n < 0:
        raise ValueError('Enter a finite non-negative number, or leave blank.')
    return n


@dataclass
class Criteria:
    reference: str = ''
    radius: object = None
    populated_radius: object = None
    populated_min_distance: object = None
    minimum_value: object = None
    value_field: str = 'estimated_mapping_value'
    body_mode: str = 'AND'
    ring_mode: str = 'AND'
    body_groups: list = field(default_factory=list)
    ring_groups: list = field(default_factory=list)
    max_pages: int = 5
    want: int = 100

    def validate(self):
        self.reference = self.reference.strip()
        for key in ('radius', 'populated_radius', 'populated_min_distance', 'minimum_value'):
            setattr(self, key, optional_number(getattr(self, key)))
        if (self.populated_min_distance is not None and self.populated_radius is not None
                and self.populated_min_distance > self.populated_radius):
            raise ValueError('The nearest-populated distance minimum exceeds the maximum.')
        if self.radius is not None and not self.reference:
            raise ValueError('A reference system is required for the regional radius.')
        if self.value_field not in ('estimated_mapping_value', 'estimated_scan_value', 'landmark_value'):
            raise ValueError('Invalid system value field.')
        if self.body_mode not in ('AND', 'OR') or self.ring_mode not in ('AND', 'OR'):
            raise ValueError('Group combination must be AND or OR.')
        for key in ('max_pages', 'want'):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError('Page and result limits must be positive integers.')
        for groups, fields in ((self.body_groups, BODY_FIELDS), (self.ring_groups, RING_FIELDS)):
            for group in groups:
                if not isinstance(group, list) or not group:
                    raise ValueError('Each group needs at least one condition.')
                for condition in group:
                    if condition.get('field') not in fields or condition.get('op') not in OPERATORS:
                        raise ValueError('Invalid body/ring condition.')
                    value = str(condition.get('value', '')).strip()
                    key, op = condition['field'], condition['op']
                    if not value:
                        raise ValueError('Each condition needs a value.')
                    if key in NUMERIC_FIELDS:
                        bounds = value.split('|') if op == 'between' else [value]
                        if op == 'in' or len(bounds) != (2 if op == 'between' else 1) or any(number(v) is None for v in bounds):
                            raise ValueError('Numeric conditions need a number; between uses min|max.')
                        if op == 'between' and float(bounds[0]) > float(bounds[1]):
                            raise ValueError('The lower bound exceeds the upper bound.')
                    elif op not in ('=', '!=', 'in'):
                        raise ValueError('Text and boolean fields use =, != or in.')
                    elif key in BOOL_FIELDS and (op == 'in' or value.casefold() not in ('true', 'false')):
                        raise ValueError('Boolean values must be true or false.')
                    elif op == 'in' and any(not v.strip() for v in value.split('|')):
                        raise ValueError('Separate non-empty choices with |.')
        return self


def combine(values, mode='AND'):
    """Three-valued logic: unknown is never converted to a positive match."""
    if not values:
        return True
    if mode == 'AND':
        return False if False in values else None if None in values else True
    return True if True in values else None if None in values else False


def condition_match(record, condition):
    key, op, expected = condition['field'], condition['op'], str(condition['value']).strip()
    key = key.removeprefix('ring.')
    actual = record.get(key)
    if actual is None:
        return None
    if condition['field'] in NUMERIC_FIELDS:
        actual = number(actual)
        if actual is None:
            return None
        if op == 'between':
            lo, hi = map(float, expected.split('|'))
            return lo <= actual <= hi
        target = float(expected)
        return {'=': actual == target, '!=': actual != target, '>': actual > target,
                '>=': actual >= target, '<': actual < target, '<=': actual <= target}[op]
    if condition['field'] in BOOL_FIELDS:
        if type(actual) is not bool:
            return None
        return (actual == (expected.casefold() == 'true')) != (op == '!=')
    if isinstance(actual, list):
        if any(not isinstance(v, dict) or not isinstance(v.get('name'), str) for v in actual):
            return None
        actual = [v['name'].casefold() for v in actual]
    elif isinstance(actual, str):
        actual = [actual.casefold()]
    else:
        return None
    choices = expected.split('|') if op == 'in' else [expected]
    hit = any(v.strip().casefold() in actual for v in choices)
    return not hit if op == '!=' else hit


def match_body_group(body, group):
    if body.get('type') != 'Planet':
        return False if body.get('type') else None
    basic = [c for c in group if not c['field'].startswith('ring.')]
    rings = [c for c in group if c['field'].startswith('ring.')]
    values = [condition_match(body, c) for c in basic]
    if rings:
        records = body.get('rings')
        values.append(None if not isinstance(records, list) else combine([
            combine([condition_match(ring, c) for c in rings]) if isinstance(ring, dict) else None
            for ring in records], 'OR') if records else False)
    return combine(values)


def match_groups(bodies, groups, mode, rings=False):
    matches, outcomes = [], []
    for index, group in enumerate(groups, 1):
        names, values = [], []
        for body in bodies:
            if rings:
                records = body.get('rings')
                if not isinstance(records, list):
                    values.append(None)
                    continue
                for ring in records:
                    hit = combine([condition_match(ring if c['field'].startswith('ring.') else body, c)
                                   for c in group]) if isinstance(ring, dict) else None
                    values.append(hit)
                    if hit is True:
                        names.append(f"{body['name']} / {ring.get('name', '?')}")
            else:
                hit = match_body_group(body, group)
                values.append(hit)
                if hit is True:
                    names.append(body['name'])
        outcomes.append(combine(values, 'OR') if values else None)
        if names:
            matches.append(f"{index}: " + ', '.join(names))
    return combine(outcomes, mode), '; '.join(matches)


def eligible(system):
    population, stations, permit = system.get('population'), system.get('stations'), system.get('needs_permit')
    if eng.is_excluded_system('systems', system):
        return False
    if number(population) is not None and number(population) != 0 or isinstance(stations, list) and stations or permit is True:
        return False
    if number(population) is None or not isinstance(stations, list) or type(permit) is not bool:
        return None
    return True


def check_stop(stop):
    if stop is not None and stop.is_set():
        raise InterruptedError('Search cancelled; results are incomplete.')


def confirm_station_absence(names, refresh=False, stop=None):
    def load():
        targets = {name.casefold(): [] for name in names}
        seen = set()
        for page in range(100):
            check_stop(stop)
            data = eng._http_json(eng.SPansh_BASE + '/stations/search', {
                'filters': {'system_name': {'value': names}}, 'size': 500, 'page': page}, compressed=True)
            rows = data.get('results') if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ValueError('Invalid station response; absence cannot be confirmed.')
            added = 0
            for row in rows:
                if not isinstance(row, dict) or not row.get('system_name') or not row.get('name'):
                    raise ValueError('Missing station identity; coverage unknown.')
                key = row['system_name'].casefold()
                if key not in targets:
                    raise ValueError('Unexpected system in station response.')
                ident = str(row.get('id', (key, row['name'])))
                if ident not in seen:
                    seen.add(ident)
                    added += 1
                    targets[key].append(row)
            if rows and not added:
                raise ValueError('Repeated station page; coverage incomplete.')
            if len(rows) < 500:
                count = data.get('count')
                if isinstance(count, (int, float)) and count < 10000 and count > len(seen):
                    raise ValueError('Station count exceeds returned coverage.')
                return targets
        raise ValueError('Station page limit reached; coverage incomplete.')
    key = 'colonisation-stations-v1:' + '\n'.join(sorted(n.casefold() for n in names))
    return pve_cache.cached(key, load, 300, refresh)[0]


def load_bodies(names, refresh=False, stop=None):
    """Fetch complete full-record pages; cache only successful reads."""
    def load():
        result = {name.casefold(): [] for name in names}
        seen = set()
        for page in range(100):
            check_stop(stop)
            data = eng._http_json(eng.SPansh_BASE + '/bodies/search', {
                'filters': {'system_name': {'value': names}}, 'size': 500, 'page': page}, compressed=True)
            rows = data.get('results') if isinstance(data, dict) else None
            if not isinstance(rows, list):
                raise ValueError('Invalid body response; coverage unknown.')
            added = 0
            for body in rows:
                if not isinstance(body, dict) or not body.get('system_name') or not body.get('name'):
                    raise ValueError('Missing body identity; coverage unknown.')
                key = body['system_name'].casefold()
                if key not in result:
                    raise ValueError('Unexpected system in body response.')
                ident = (key, str(body.get('id64', body['name'])))
                if ident not in seen:
                    seen.add(ident)
                    added += 1
                    result[key].append(body)
            if rows and not added:
                raise ValueError('Repeated body page; coverage incomplete.')
            if len(rows) < 500:
                count = data.get('count')
                if isinstance(count, (int, float)) and count < 10000 and count > len(seen):
                    raise ValueError('Body count exceeds returned coverage.')
                return result
        raise ValueError('Body page limit reached; coverage incomplete.')
    key = 'colonisation-bodies-v1:' + '\n'.join(sorted(name.casefold() for name in names))
    return pve_cache.cached(key, load, 300, refresh)[0]


def populated_neighbour(system, radius, max_pages, stop=None, population_min=1):
    """Find the nearest system above the population threshold, not an annulus.

    The server sorts from the candidate's coordinates. Verify that order using
    actual coordinates before accepting the nearest hit; uncertain records or
    incomplete pages without a hit cannot establish a nearest neighbour.
    """
    coords = tuple(number(system.get(axis)) for axis in ('x', 'y', 'z'))
    if None in coords:
        return None, '', None, None
    seen, uncertain, previous_distance = set(), False, None
    for page in range(max_pages):
        check_stop(stop)
        filters = eng.build_server_payload('systems', [
            {'field': 'population', 'op': 'between', 'min': math.floor(population_min) + 1, 'max': eng.BIG}])['filters']
        if radius is not None:
            filters['distance'] = {'max': radius}
        data = eng._http_json(eng.SPansh_BASE + '/systems/search', {
            'filters': filters,
            'reference_coords': dict(zip(('x', 'y', 'z'), coords)),
            'sort': [{'distance': {'direction': 'asc'}}], 'size': 50, 'page': page}, compressed=True)
        rows = data.get('results') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise ValueError('Invalid populated-system response.')
        added, hits = 0, []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Invalid populated-system record.')
            ident = row.get('id64', row.get('name'))
            if ident in seen:
                continue
            seen.add(ident)
            added += 1
            if eng.is_excluded_system('systems', row):
                continue
            population = number(row.get('population'))
            xyz = tuple(number(row.get(axis)) for axis in ('x', 'y', 'z'))
            if population is None or None in xyz or not row.get('name'):
                uncertain = True
                continue
            distance = eng.dist3(coords, xyz)
            if previous_distance is not None and distance < previous_distance - 1e-7:
                raise ValueError('Populated systems are not sorted by coordinate distance; nearest is unknown.')
            previous_distance = distance
            if population > population_min and (radius is None or distance <= radius):
                hits.append((distance, row['name'], population))
        if hits:
            if uncertain:
                return None, '', None, None
            distance, name, population = min(hits)
            return True, name, population, distance
        if len(rows) < 50:
            return (None if uncertain else False), '', None, None
        if not added:
            break
    return None, '', None, None


def search(criteria, progress=None, stop=None, refresh=False):
    c = criteria.validate()
    if stop is not None and stop.is_set():
        return dict(scanned=0, total=0, complete=False, unknown=0,
                    reason='Search cancelled; results are incomplete.', value_field=c.value_field), []
    conditions = [{'field': 'population', 'op': 'between', 'min': 0, 'max': 0},
                  {'field': 'needs_permit', 'op': 'false'}]
    if c.minimum_value is not None:
        conditions.append({'field': c.value_field, 'op': '>', 'text': c.minimum_value})
    if c.reference:
        conditions.append({'type': 'distance', 'ref_system': c.reference,
                           'min_ly': None, 'max_ly': c.radius, 'mode': 'inside'})
    payload = eng.build_server_payload('systems', conditions, size=500)
    reference_coords = None
    if c.reference:
        canonical, reference_coords, _ = eng.resolve_ref(c.reference)
        payload['reference_system'] = canonical
    rows, seen, scanned, unknown = [], set(), 0, 0
    complete, reason = False, 'Page limit reached; results are incomplete.'
    total = 0
    try:
        for page in range(c.max_pages):
            check_stop(stop)
            if progress:
                progress(f'Page {page + 1}/{c.max_pages}; scanned {scanned}; matches {len(rows)}')
            data = eng._http_json(eng.SPansh_BASE + '/systems/search', dict(payload, page=page), compressed=True)
            candidates = data.get('results') if isinstance(data, dict) else None
            if not isinstance(candidates, list):
                raise ValueError('Invalid system response.')
            if page == 0:
                total = data.get('count', 0)
            missing_stations = [s['name'] for s in candidates if isinstance(s, dict) and s.get('name')
                                and number(s.get('population')) == 0 and s.get('needs_permit') is False
                                and 'stations' not in s and not eng.is_excluded_system('systems', s)]
            confirmed = {}
            for start in range(0, len(missing_stations), 16):
                confirmed.update(confirm_station_absence(missing_stations[start:start + 16], refresh, stop))
            accepted, added = [], 0
            for system in candidates:
                if not isinstance(system, dict) or not system.get('name'):
                    raise ValueError('Missing system identity.')
                ident = system.get('id64', system['name'].casefold())
                if ident in seen:
                    continue
                seen.add(ident)
                scanned += 1
                added += 1
                if system['name'].casefold() in confirmed:
                    system = dict(system, stations=confirmed[system['name'].casefold()])
                hit = eligible(system)
                if hit is None:
                    unknown += 1
                if hit is not True:
                    continue
                if c.minimum_value is not None:
                    value = number(system.get(c.value_field))
                    if value is None:
                        unknown += 1
                        continue
                    if value <= c.minimum_value:
                        continue
                if c.radius is not None:
                    xyz = tuple(number(system.get(axis)) for axis in ('x', 'y', 'z'))
                    if None in xyz:
                        unknown += 1
                        continue
                    distance = eng.dist3(xyz, reference_coords)
                    if distance > c.radius:
                        continue
                    system = dict(system, distance=distance)
                accepted.append(system)
            bodies = {}
            if c.body_groups or c.ring_groups:
                chunks = [[r['name'] for r in accepted[i:i + 8]] for i in range(0, len(accepted), 8)]
                with ThreadPoolExecutor(max_workers=4) as pool:
                    for start in range(0, len(chunks), 4):
                        check_stop(stop)
                        futures = [pool.submit(load_bodies, chunk, refresh, stop) for chunk in chunks[start:start + 4]]
                        for future in futures:
                            bodies.update(future.result())
                        if progress:
                            progress(f'Body batches {min(start + 4, len(chunks))}/{len(chunks)}; matches {len(rows)}')
            for system in accepted:
                check_stop(stop)
                records = bodies.get(system['name'].casefold(), [])
                annotate_relationships(records)
                body_hit, body_names = match_groups(records, c.body_groups, c.body_mode)
                ring_hit, ring_names = match_groups(records, c.ring_groups, c.ring_mode, rings=True)
                hit = combine([body_hit, ring_hit])
                if hit is None:
                    unknown += 1
                if hit is not True:
                    continue
                neighbour, population, distance = '', None, None
                if c.populated_radius is not None or c.populated_min_distance is not None:
                    hit, neighbour, population, distance = populated_neighbour(system, c.populated_radius, c.max_pages, stop)
                    if hit is None:
                        unknown += 1
                    if hit is not True:
                        continue
                    if c.populated_min_distance is not None and distance < c.populated_min_distance:
                        continue
                row = dict(system, _body_matches=body_names, _ring_matches=ring_names,
                           _relations='; '.join(f"{b['name']}: {b['_relations']}" for b in records if b.get('_relations')),
                           _neighbour=neighbour, _neighbour_population=population,
                           _neighbour_distance=distance)
                rows.append(row)
                if len(rows) >= c.want:
                    reason = 'Result limit reached; results are incomplete.'
                    break
            if len(rows) >= c.want:
                break
            if candidates and not added:
                reason = 'Repeated system page; results are incomplete.'
                break
            if len(candidates) < 500:
                complete = True
                reason = 'All supplied candidate pages fetched.'
                break
    except InterruptedError as exc:
        reason = str(exc)
    return dict(scanned=scanned, total=total, complete=complete, unknown=unknown,
                reason=reason, value_field=c.value_field), rows
