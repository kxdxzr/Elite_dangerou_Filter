import copy
import csv
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import route_ship as ship
import route_tool as tool


FSDS = [dict(symbol='Int_Hyperdrive_Size5_Class5', **{'class': 5}, rating='A', optmass=1050,
             maxfuel=5, fuelmul=.012, fuelpower=2.45),
        dict(symbol='Int_Hyperdrive_Overcharge_Size8_Class5_Overchargebooster_MkII',
             **{'class': 8}, rating='A', optmass=4670, maxfuel=6.8, fuelmul=.011, fuelpower=2.5025)]


def build():
    return dict(header=dict(appName='EDSY'), data=dict(UnladenMass=280, FuelCapacity=dict(Main=32, Reserve=.63),
                Modules=[dict(Slot='FrameShiftDrive', Item='Int_Hyperdrive_Size5_Class5'),
                         dict(Slot='Slot1', Item='int_guardianfsdbooster_size5')]))


def jump(name, fuel):
    return dict(name=name, fuel_in_tank=fuel, distance=4.123456, fuel_used=.123456,
                distance_to_destination=0, must_refuel=False, has_neutron=False, must_inject=False)


class Server:
    def __init__(self, fail_leg=None):
        self.requests, self.jobs, self.fail_leg = [], {}, fail_leg

    def __call__(self, url, payload=None):
        if '/field_values/' in url:
            from urllib.parse import parse_qs, urlsplit
            name = parse_qs(urlsplit(url).query)['q'][0]
            return dict(min_max=[dict(name=name, id64={'A': 1, 'B': 2, 'C': 3}[name])])
        if payload is not None:
            self.requests.append(copy.deepcopy(payload))
            leg = len(self.requests)
            self.jobs[str(leg)] = payload
            return dict(status='queued', job=str(leg))
        key = url.rsplit('/', 1)[-1]
        leg = int(key)
        if leg == self.fail_leg:
            return dict(state='failed', error='No route for leg')
        request = self.jobs[key]
        names = {'1': 'A', '2': 'B', '3': 'C'}
        return dict(state='completed', result=dict(jumps=[
            jump(names[request['source']], 32), jump(names[request['destination']], 1.25)]))


class ShipTests(unittest.TestCase):
    def test_ship_identity_for_both_formats_and_unknown_models(self):
        data = build()
        data['data'].update(Ship='diamondbackxl', ShipName='My Explorer', ShipIdent='AB-12')
        self.assertEqual(ship.ship_identity(json.dumps([data])),
                         dict(model='Diamondback Explorer', name='My Explorer', ident='AB-12'))
        data['data']['Ship'] = 'future_ship'
        self.assertEqual(ship.ship_identity(json.dumps(data))['model'], 'future_ship')
        coriolis = dict(ship='Asp Explorer', name='Test build', components={}, stats={})
        self.assertEqual(ship.ship_identity(json.dumps(coriolis)),
                         dict(model='Asp Explorer', name='Test build', ident=''))

    def test_full_tank_range_cargo_and_neutron_multiplier(self):
        params = dict(base_mass=100, tank_size=20, max_fuel_per_jump=5, optimal_mass=120,
                      fuel_multiplier=5, fuel_power=2, range_boost=10, supercharge_multiplier=4)
        original = copy.deepcopy(params)
        values = ship.jump_attributes(params)
        self.assertEqual((values['normal_range'], values['neutron_range']), (11, 44))
        self.assertEqual(values['total_mass'], 120)
        laden = ship.jump_attributes(params, 120)
        self.assertEqual((laden['normal_range'], laden['neutron_range']), (10.5, 42))
        self.assertEqual(params, original)
        params['supercharge_multiplier'] = 6
        self.assertEqual(ship.jump_attributes(params)['neutron_range'], 66)
        params['tank_size'] = 2
        small = ship.jump_attributes(params)
        self.assertEqual(small['fuel_per_jump'], 2)
        self.assertAlmostEqual(small['normal_range'], 120 / 102 * (2 / 5) ** .5 + 10)
        for cargo in (-1, 'nan', 'bad', True):
            with self.subTest(cargo=cargo), self.assertRaises(ValueError):
                ship.jump_attributes(params, cargo)

    def test_guardian_booster_size_three_is_7_75_ly(self):
        self.assertEqual(ship.booster('int_guardianfsdbooster_size3'), 7.75)

    def test_slef_engineering_and_booster(self):
        data = build()
        data['data']['Modules'][0]['Engineering'] = dict(Modifiers=[
            dict(Label='FSDOptimalMass', Value=1700.123456), dict(Label='MaxFuelPerJump', Value=5.5)])
        params = ship.parse_ship(json.dumps([data]), FSDS)
        self.assertAlmostEqual(params['base_mass'], 280.63)
        self.assertEqual(params['optimal_mass'], 1700.123456)
        self.assertEqual(params['max_fuel_per_jump'], 5.5)
        self.assertEqual(params['range_boost'], 10.5)

    def test_mkii_uses_distinct_fuel_and_supercharge(self):
        data = build()
        data['data']['Modules'][0]['Item'] = FSDS[1]['symbol']
        params = ship.parse_ship(json.dumps(data), FSDS)
        self.assertEqual((params['fuel_multiplier'], params['fuel_power'], params['supercharge_multiplier']), (.011, 2.5025, 6))

    def test_coriolis_modification_and_experimental(self):
        data = dict(ship='Asp Explorer', stats=dict(unladenMass=280, fuelCapacity=32), components=dict(
            standard=dict(frameShiftDrive=dict(symbol=FSDS[0]['symbol'], modifications=dict(optmass=5500),
                blueprint=dict(special=dict(edname='special_fsd_heavy')))),
            internal=[dict(group='Guardian Frame Shift Drive Booster', **{'class': 5})]))
        params = ship.parse_ship(json.dumps(data), FSDS)
        self.assertAlmostEqual(params['optimal_mass'], 1050 * 1.55 * 1.04)
        self.assertEqual(params['range_boost'], 10.5)
        data['ship'] = 'Unknown ship'
        with self.assertRaises(ValueError):
            ship.parse_ship(json.dumps(data), FSDS)

    def test_invalid_or_unknown_ship_is_not_guessed(self):
        for raw in ('bad', '{}', '[]', '[{},{}]', '"url"'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                ship.decode_build(raw)
        for value in (True, -1, 'nan', 'inf', None):
            data = build()
            data['data']['FuelCapacity']['Main'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                ship.parse_ship(json.dumps(data), FSDS)
        data = build()
        data['data']['Modules'][0]['Item'] = 'unknown_fsd'
        with self.assertRaises(ValueError):
            ship.parse_ship(json.dumps(data), FSDS)

    def test_favourites_crud_and_corrupt_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ships.json'
            store = tool.Favorites(str(path))
            raw = json.dumps(build())
            store.put('探索船', raw)
            self.assertEqual(tool.Favorites(str(path)).load(), {'探索船': raw})
            with self.assertRaises(ValueError):
                store.put('探索船', raw)
            store.rename('探索船', 'Explorer')
            with self.assertRaises(ValueError):
                store.put('explorer', raw)
            store.put('Explorer', raw, replace=True)
            store.delete('Explorer')
            self.assertEqual(store.load(), {})
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                store.put('Test', raw)
            self.assertEqual(path.read_text(encoding='utf-8'), '{broken')


class RouteTests(unittest.TestCase):
    def test_multi_leg_full_tank_and_boundary_merge(self):
        server, events = Server(), []
        info = tool.plan(json.dumps(build()), ['A', 'B', 'C'], tool.Options(already_supercharged=True),
                         http=server, fsds=FSDS, progress=lambda text, detail: events.append(detail))
        self.assertTrue(info['complete'], info['reason'])
        self.assertEqual([r['name'] for r in info['rows']], ['A', 'B', 'C'])
        self.assertEqual([r['is_supercharged'] for r in server.requests], [1, 0])
        self.assertEqual([r['tank_size'] for r in server.requests], [32, 32])
        boundary = info['rows'][1]
        self.assertEqual((boundary['fuel_in_tank'], boundary['departure_fuel']), (1.25, 32))
        self.assertEqual(boundary['departure_segment'], 2)
        self.assertTrue(boundary['waypoint'])
        self.assertEqual(events[-1]['done'], 2)
        self.assertIn('full tank', tool.display_rows(info, lambda x: 'full tank' if x == tool.FULL_TANK_NOTE else x)[1][-1])

    def test_failed_later_leg_preserves_only_confirmed_prefix(self):
        info = tool.plan(json.dumps(build()), ['A', 'B', 'C'], tool.Options(), http=Server(fail_leg=2), fsds=FSDS)
        self.assertFalse(info['complete'])
        self.assertEqual(info['failed_segment'], 2)
        self.assertEqual([r['name'] for r in info['rows']], ['A', 'B'])
        self.assertFalse(info['rows'][-1]['full_tank_start'])

    def test_shared_endpoint_retains_next_leg_departure_actions(self):
        server = Server()
        def http(url, payload=None):
            response = server(url, payload)
            if url.endswith('/results/2'):
                response['result']['jumps'][0].update(must_inject=True, has_neutron=True)
            return response
        info = tool.plan(json.dumps(build()), ['A', 'B', 'C'], tool.Options(), http=http, fsds=FSDS)
        boundary = info['rows'][1]
        self.assertTrue(boundary['must_inject'])
        self.assertTrue(boundary['has_neutron'])
        self.assertEqual(boundary['fuel_in_tank'], 1.25)
        self.assertEqual(boundary['_next_leg_start']['fuel_in_tank'], 32)

    def test_wrong_endpoints_are_not_exported_as_valid_leg(self):
        server = Server()
        def wrong(url, payload=None):
            response = server(url, payload)
            if 'result' in response:
                response['result']['jumps'][-1]['name'] = 'Wrong'
            return response
        info = tool.plan(json.dumps(build()), ['A', 'B'], tool.Options(), http=wrong, fsds=FSDS)
        self.assertFalse(info['complete'])
        self.assertEqual(info['rows'], [])

    def test_cancel_and_input_validation(self):
        stop, server = threading.Event(), Server()
        stop.set()
        info = tool.plan(json.dumps(build()), ['A', 'B'], tool.Options(), stop=stop, http=server, fsds=FSDS)
        self.assertFalse(info['complete'])
        self.assertEqual(server.requests, [])
        with self.assertRaises(ValueError):
            tool.plan(json.dumps(build()), ['A', 'a'], tool.Options(), http=server, fsds=FSDS)
        with self.assertRaises(ValueError):
            tool.Options(cargo=True).validate()
        with self.assertRaises(ValueError):
            tool.Options(injection='invalid').validate()

    def test_cancellation_between_legs_identifies_next_leg(self):
        stop, server = threading.Event(), Server()
        def progress(text, detail):
            if detail['done'] == 1:
                stop.set()
        info = tool.plan(json.dumps(build()), ['A', 'B', 'C'], tool.Options(), stop=stop,
                         http=server, fsds=FSDS, progress=progress)
        self.assertFalse(info['complete'])
        self.assertEqual(info['failed_segment'], 2)
        self.assertEqual(len(server.requests), 1)
        self.assertEqual(len(info['segments']), 1)

    def test_polling_cancel_and_unknown_state(self):
        stop = threading.Event()
        calls = []
        def http(url, payload=None):
            calls.append(url)
            return dict(job='abc', status='queued') if payload is not None else dict(state='queued')
        with self.assertRaises(InterruptedError):
            tool.plot_leg({}, stop, http=http, wait=lambda seconds: stop.set())
        self.assertEqual(len(calls), 2)
        with self.assertRaises(ValueError):
            tool.plot_leg({}, http=lambda url, payload=None: dict(job='abc') if payload is not None else dict(state='surprise'))

    def test_csv_formats_distances_and_labels_partial_full_tank(self):
        info = tool.plan(json.dumps(build()), ['A', 'B', 'C'], tool.Options(), http=Server(fail_leg=2), fsds=FSDS)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'route.csv'
            tool.export_csv(path, info)
            rows = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
        self.assertIn('4.12', rows[7])
        self.assertIn(tool.FULL_TANK_NOTE, rows[7])
        from test_export_metadata import assert_provenance
        assert_provenance(self, rows, len(rows[0]))
        self.assertEqual(len(rows[-1]), len(tool.COLUMNS))
        for field in ('route_complete', 'failed_segment', 'route_status'):
            self.assertNotIn(field, rows[6])
        self.assertEqual(info['rows'][0]['distance'], 4.123456)

    def test_english_csv_translates_status_and_footer(self):
        info = tool.plan(json.dumps(build()), ['A', 'B'], tool.Options(), http=Server(), fsds=FSDS)
        self.assertTrue(info['complete'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'english.csv'
            tool.export_csv(path, info, language='en')
            rows = list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
        from test_export_metadata import assert_english_csv, assert_provenance
        assert_provenance(self, rows, len(rows[0]))
        assert_english_csv(self, rows)
