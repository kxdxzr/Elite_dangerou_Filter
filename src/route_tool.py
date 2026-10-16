"""Spansh online exact routes, local ship favourites and independent full-tank legs."""
import copy
import csv
import gzip
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

import route_ship
import session_store
from runtime_paths import data_file
from result_format import format_ly, format_number

BASE = 'https://spansh.co.uk/api'
FULL_TANK_NOTE = '本段起点按满油计算；途经点不保证能补油'


def http_json(url, payload=None):
    data = urllib.parse.urlencode(payload).encode('utf-8') if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={
        'User-Agent': 'EliteDangerousFilter/0.1.2', 'Accept-Encoding': 'gzip',
        'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(32 * 1024 * 1024 + 1)
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError('Route response is too large.')
        if response.headers.get('Content-Encoding') == 'gzip':
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
                raw = compressed.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024:
                raise ValueError('Decompressed route response is too large.')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError('Invalid route server response.')
        return result


class Favorites:
    def __init__(self, path=None):
        self.path = path or data_file('route_ship_favorites.json')

    def load(self):
        if not os.path.exists(self.path):
            return {}
        with open(self.path, encoding='utf-8') as file:
            data = json.load(file)
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('ships'), dict):
            raise ValueError('Invalid ship favourites file; it has not been overwritten.')
        for name, raw in data['ships'].items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError('Invalid favourite name.')
            route_ship.decode_build(raw)
        return data['ships']

    def save(self, ships):
        session_store.save(self.path, dict(version=1, ships=ships))

    def put(self, name, raw, replace=False):
        name = name.strip()
        if not name:
            raise ValueError('A ship favourite name is required.')
        route_ship.decode_build(raw)
        ships = self.load()
        existing = next((n for n in ships if n.casefold() == name.casefold()), None)
        if existing is not None and not replace:
            raise ValueError('That favourite name already exists.')
        if existing is not None:
            del ships[existing]
        ships[name] = raw
        self.save(ships)

    def rename(self, old, new):
        new = new.strip()
        ships = self.load()
        if old not in ships or not new or any(n != old and n.casefold() == new.casefold() for n in ships):
            raise ValueError('Invalid or duplicate favourite name.')
        ships[new] = ships.pop(old)
        self.save(ships)

    def delete(self, name):
        ships = self.load()
        if name not in ships:
            raise ValueError('Favourite not found.')
        del ships[name]
        self.save(ships)


@dataclass
class Options:
    cargo: float = 0
    reserve: float = 0
    supercharge: bool = True
    already_supercharged: bool = False
    injection: str = 'never'
    exclude_secondary: bool = False
    refuel_every_scoopable: bool = False
    algorithm: str = 'optimistic'

    def validate(self):
        self.cargo = route_ship.numeric(self.cargo, 'Cargo')
        self.reserve = route_ship.numeric(self.reserve, 'Reserve fuel')
        if self.injection not in ('never', 'required', 'always') or self.algorithm not in ('optimistic', 'pessimistic'):
            raise ValueError('Invalid routing option.')
        for field in ('supercharge', 'already_supercharged', 'exclude_secondary', 'refuel_every_scoopable'):
            if type(getattr(self, field)) is not bool:
                raise ValueError('Routing switches must be true or false.')
        return self


def check_stop(stop):
    if stop is not None and stop.is_set():
        raise InterruptedError('Route planning cancelled.')


def resolve(name, http=http_json):
    data = http(BASE + '/systems/field_values/system_names?q=' + urllib.parse.quote(name, safe=''))
    for row in data.get('min_max', []):
        if isinstance(row, dict) and str(row.get('name', '')).casefold() == name.casefold():
            ident = str(row.get('id64', ''))
            if ident.isdigit():
                return dict(name=row['name'], id64=ident)
    raise ValueError(f'No exact recorded system match: {name}')


def payload(ship, raw, source, destination, options, leg):
    if options.reserve >= ship['tank_size']:
        raise ValueError('Reserve fuel must be less than main tank capacity.')
    return dict(ship, source=source['id64'], destination=destination['id64'], ship_build=raw,
                cargo=options.cargo, reserve_size=options.reserve, max_time=60,
                is_supercharged=int(options.already_supercharged and leg == 1),
                use_supercharge=int(options.supercharge), use_injections=int(options.injection == 'always'),
                use_injections_when_required=int(options.injection == 'required'),
                exclude_secondary=int(options.exclude_secondary), refuel_every_scoopable=int(options.refuel_every_scoopable),
                algorithm=options.algorithm)


def plot_leg(request, stop=None, progress=None, http=http_json, timeout=600, wait=None):
    check_stop(stop)
    response = http(BASE + '/generic/route', request)
    job = str(response.get('job', ''))
    if not re.fullmatch(r'[A-Za-z0-9-]{1,100}', job) or response.get('status') == 'error':
        raise ValueError(str(response.get('error') or 'Spansh did not return a valid route job.'))
    deadline, delay = time.monotonic() + timeout, 2
    while time.monotonic() < deadline:
        check_stop(stop)
        response = http(BASE + '/results/' + job)
        if response.get('state') in ('failed', 'error') or response.get('status') == 'error':
            raise ValueError(str(response.get('error') or 'Spansh route job failed.'))
        if response.get('state') == 'completed' or response.get('status') == 'ok':
            result = response.get('result')
            jumps = result.get('jumps') if isinstance(result, dict) else None
            if not isinstance(jumps, list) or not jumps:
                raise ValueError('Completed route has no jump list.')
            return job, jumps
        state = response.get('state') or response.get('status')
        if state not in ('queued', 'unstarted', 'started', 'running'):
            raise ValueError('Unknown route job state: ' + str(state))
        if progress:
            progress(str(state))
        if wait:
            wait(delay)
        elif stop is not None:
            if stop.wait(delay):
                check_stop(stop)
        else:
            time.sleep(delay)
        delay = min(10, delay * 1.5)
    raise TimeoutError('Spansh route job timed out; no automatic resubmission was made.')


def validate_jumps(jumps, source, destination):
    if any(not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name'].strip() for row in jumps):
        raise ValueError('Invalid jump identity in route response.')
    if jumps[0]['name'].casefold() != source['name'].casefold() or jumps[-1]['name'].casefold() != destination['name'].casefold():
        raise ValueError('Route endpoints do not match the requested leg.')
    for row in jumps:
        for key in ('distance', 'distance_to_destination', 'fuel_in_tank', 'fuel_used'):
            if key in row and row[key] is not None:
                route_ship.numeric(row[key], key)


def plan(raw, points, options, stop=None, progress=None, http=http_json, fsds=None, wait=None):
    options = copy.deepcopy(options).validate()
    if len(points) < 2 or any(not isinstance(p, str) or not p.strip() for p in points):
        raise ValueError('Enter a start, destination and non-empty waypoints.')
    points = [p.strip() for p in points]
    if any(a.casefold() == b.casefold() for a, b in zip(points, points[1:])):
        raise ValueError('Adjacent route points must be different.')
    info = dict(complete=False, rows=[], segments=[], planned_segments=len(points) - 1,
                failed_segment=None, reason='', full_tank_each_segment=True)
    def emit(text, done=0):
        if progress:
            progress(text, dict(done=done, work_total=len(points) - 1, stage='航线分段'))
    try:
        check_stop(stop)
        emit('准备舰船参数与航点')
        ship = route_ship.parse_ship(raw, fsds if fsds is not None else route_ship.catalog(http))
        resolved, memo = [], {}
        for name in points:
            check_stop(stop)
            if name.casefold() not in memo:
                memo[name.casefold()] = resolve(name, http)
            resolved.append(memo[name.casefold()])
        for leg, (source, destination) in enumerate(zip(resolved, resolved[1:]), 1):
            info['failed_segment'] = leg
            check_stop(stop)
            emit(f"{source['name']} → {destination['name']}", leg - 1)
            request = payload(ship, raw, source, destination, options, leg)
            job, jumps = plot_leg(request, stop, lambda state: emit(f"{source['name']} → {destination['name']}: {state}", leg - 1), http, wait=wait)
            validate_jumps(jumps, source, destination)
            check_stop(stop)
            rows = [dict(copy.deepcopy(row), segment=leg, job=job, waypoint=False,
                         departure_segment='', departure_fuel='', full_tank_start=False) for row in jumps]
            rows[0].update(departure_segment=leg, departure_fuel=ship['tank_size'], full_tank_start=True)
            rows[-1]['waypoint'] = leg < len(points) - 1
            if info['rows']:
                boundary = info['rows'][-1]
                # Keep previous-leg arrival fuel and next-leg assumed departure fuel separate.
                boundary.update(departure_segment=leg, departure_fuel=ship['tank_size'], full_tank_start=True)
                boundary['_next_leg_start'] = copy.deepcopy(jumps[0])
                # Departure actions must come from the next leg, not the old terminal
                # row. Otherwise merging could silently drop a required injection.
                for key in ('must_refuel', 'has_neutron', 'must_inject'):
                    boundary[key] = jumps[0].get(key)
                rows = rows[1:]
            info['rows'].extend(rows)
            info['segments'].append(dict(number=leg, source=source['name'], destination=destination['name'], job=job))
            emit(f"{source['name']} → {destination['name']}", leg)
        info.update(complete=True, failed_segment=None, reason='航线规划完成')
    except InterruptedError as exc:
        info['reason'] = str(exc)
    except Exception as exc:
        info['reason'] = str(exc)
    return info


COLUMNS = [('step', '序号'), ('segment', '分段编号'), ('name', '星系'), ('distance', '跳跃距离 ly'),
           ('distance_to_destination', '距本段终点 ly'), ('fuel_in_tank', '本段到达剩余燃油 t'),
           ('fuel_used', '本跳燃油 t'), ('must_refuel', '需要补油'), ('has_neutron', '中子星'),
           ('must_inject', '需要注入'), ('waypoint', '途经点'), ('departure_segment', '出发分段'),
           ('departure_fuel', '假定出发燃油 t'), ('assumption', '分段出发假设')]


def display_rows(info, tr=lambda x: x):
    def flag(value):
        return tr('是' if value is True or value == 1 else '否' if value is False or value == 0 else '情况未知')
    output = []
    for step, row in enumerate(info['rows'], 1):
        data = dict(row, step=f'{step:,}', assumption=tr(FULL_TANK_NOTE) if row['full_tank_start'] else '')
        for key in ('distance', 'distance_to_destination'):
            data[key] = format_ly(row.get(key))
        for key in ('fuel_in_tank', 'fuel_used', 'departure_fuel'):
            data[key] = format_number(row.get(key))
        for key in ('must_refuel', 'has_neutron', 'must_inject', 'waypoint'):
            data[key] = flag(row.get(key))
        output.append([data.get(key, '') for key, _ in COLUMNS])
    return output


def export_csv(path, info, tr=lambda x: x):
    with open(path, 'w', encoding='utf-8-sig', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([tr(title) for _, title in COLUMNS] + ['route_complete', 'failed_segment', 'route_status'])
        for values in display_rows(info, tr):
            row = values + [info['complete'], info['failed_segment'] or '', info['reason']]
            writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v for v in row])
