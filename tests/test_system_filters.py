import copy
import threading
import unittest
from unittest.mock import patch

import filter_engine as eng
import system_filters as details


def spec(**kw):
    return dict(type='system_details', **kw)


def body_condition(field, value, op='='):
    return dict(field=field, value=str(value), op=op)


def count(field, text, op='='):
    return dict(type='field', field=field, op=op, text=text)


class SystemFilterTests(unittest.TestCase):
    def test_local_fields_and_groups_never_reach_server_payload(self):
        conditions = [count('population', 0), count('station_count', 0),
                      spec(body_groups=[[body_condition('subtype', 'Water world')]])]
        payload = eng.build_server_payload('systems', conditions)
        self.assertEqual(set(payload['filters']), {'population'})

    def test_station_counts_include_carriers_and_reject_unknown_types_for_carrier_count(self):
        rows = [dict(name='A', stations=[{'type': 'Fleet Carrier'}, {'type': 'Coriolis Starport'}]),
                dict(name='B', stations=[]), dict(name='C', stations=[{}]), dict(name='D', stations=None)]
        details.prepare(rows, [count('station_count', 0), count('carrier_count', 0)])
        self.assertEqual([(r['station_count'], r['carrier_count']) for r in rows],
                         [(2, 1), (0, 0), (1, None), (None, None)])

    def test_station_absence_is_verified(self):
        rows = [dict(name='A')]
        with patch.object(details.bodies, 'confirm_station_absence', return_value={'a': []}) as verify:
            details.prepare(rows, [count('station_count', 0)])
        verify.assert_called_once()
        self.assertEqual(rows[0]['station_count'], 0)

    def test_faction_counts_are_deduplicated_and_distinguish_anarchy(self):
        row = dict(minor_faction_presences=[
            dict(name='One', allegiance='Federation', government='Democracy'),
            dict(name='ONE', allegiance='Federation', government='Democracy'),
            dict(name='Two', allegiance='Federation', government='Anarchy'),
            dict(name='Three', allegiance='Empire', government='Corporate'),
            dict(name='Four', allegiance='Alliance', government='Cooperative')])
        result = details.faction_counts(row)
        self.assertEqual(result['minor_faction_count'], 4)
        self.assertEqual(result['federation_faction_count'], 2)
        self.assertEqual(result['empire_faction_count'], 1)
        self.assertEqual(result['alliance_faction_count'], 1)
        self.assertEqual(result['potential_issuer_count'], 3)
        self.assertEqual(result['federation_issuer_count'], 1)
        self.assertEqual(result['empire_issuer_count'], 1)

    def test_missing_and_conflicting_faction_data_are_not_zero(self):
        self.assertIsNone(details.faction_counts({})['minor_faction_count'])
        self.assertEqual(details.faction_counts({'minor_faction_presences': []})['minor_faction_count'], 0)
        row = dict(minor_faction_presences=[dict(name='A', allegiance='Empire'),
                                           dict(name='a', allegiance='Federation')])
        result = details.faction_counts(row)
        self.assertEqual(result['minor_faction_count'], 1)
        self.assertIsNone(result['empire_faction_count'])
        self.assertIsNone(result['potential_issuer_count'])

    def test_groups_do_not_impose_colonisation_eligibility(self):
        raw = dict(name='Populated', population=10000, needs_permit=True,
                   stations=[{'type': 'Starport'}])
        original = copy.deepcopy(raw)
        conditions = [spec(body_groups=[[body_condition('subtype', 'Water world')]])]
        body = dict(name='Populated 1', type='Planet', subtype='Water world')
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [raw]}), \
                patch.object(details.bodies, 'load_bodies', return_value={'populated': [body]}):
            rows, _, _ = eng.search('systems', conditions)
        self.assertEqual(len(rows), 1)
        self.assertIn('Populated 1', rows[0]['_system_details']['groups'][0]['planets'])
        self.assertEqual(raw, original)

    def test_cheap_conditions_precede_detail_requests(self):
        conditions = [spec(body_groups=[[body_condition('subtype', 'Water world')]]), count('population', 0)]
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [dict(name='A', population=10)]}), \
                patch.object(details.bodies, 'load_bodies') as load:
            rows, _, scanned = eng.search('systems', conditions)
        self.assertEqual(rows, [])
        self.assertEqual(scanned, 1)
        load.assert_not_called()

    def test_count_rejections_also_skip_body_requests(self):
        conditions = [spec(body_groups=[[body_condition('subtype', 'Water world')]]), count('station_count', 0)]
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [dict(name='A', stations=[{}])]}), \
                patch.object(details.bodies, 'load_bodies') as load:
            rows, _, _ = eng.search('systems', conditions)
        self.assertEqual(rows, [])
        load.assert_not_called()

    def test_result_limit_is_applied_after_advanced_verification(self):
        conditions = [spec(body_groups=[[body_condition('subtype', 'Water world')]])]
        records = {'a': [dict(name='A 1', type='Planet', subtype='Icy body')],
                   'b': [dict(name='B 1', type='Planet', subtype='Water world')]}
        with patch.object(eng, '_http_json', return_value={'count': 2, 'results': [dict(name='A'), dict(name='B')]}), \
                patch.object(details.bodies, 'load_bodies', return_value=records):
            rows, _, scanned = eng.search('systems', conditions, want=1)
        self.assertEqual([r['name'] for r in rows], ['B'])
        self.assertEqual(scanned, 2)

    def test_unknown_groups_and_fake_derived_fields_do_not_match(self):
        notes = []
        row = dict(name='A', station_count=0, stations=None)
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [row]}):
            rows, _, _ = eng.search('systems', [count('station_count', 0)], notes=notes)
        self.assertEqual(rows, [])
        self.assertTrue(any('station_count' in note for note in notes))
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [dict(name='A')]}), \
                patch.object(details.bodies, 'load_bodies', return_value={'a': []}):
            rows, _, _ = eng.search('systems', [spec(body_groups=[[body_condition('subtype', 'Water world', '!=')]])])
        self.assertEqual(rows, [])

    def test_nearest_population_threshold_and_annulus_semantics(self):
        candidate = dict(name='A', x=0, y=0, z=0)

        def fetch(url, payload, **kw):
            if 'reference_coords' in payload:
                self.assertEqual(payload['filters']['population']['value'][0], 101)
                self.assertEqual(payload['filters']['distance'], {'max': 10})
                return {'results': [dict(name='Low', population=100, x=1, y=0, z=0),
                                    dict(name='Nearest', population=101, x=2, y=0, z=0),
                                    dict(name='Farther', population=1000, x=8, y=0, z=0)]}
            return {'count': 1, 'results': [candidate]}

        with patch.object(eng, '_http_json', side_effect=fetch):
            rows, _, _ = eng.search('systems', [spec(population_min=100, nearest_min=5, nearest_max=10)])
        self.assertEqual(rows, [])
        with patch.object(eng, '_http_json', side_effect=fetch):
            rows, _, _ = eng.search('systems', [spec(population_min=100, nearest_min=2, nearest_max=10)])
        neighbour = rows[0]['_system_details']['neighbours'][0]
        self.assertEqual((neighbour['name'], neighbour['population'], neighbour['distance']), ('Nearest', 101, 2))

    def test_blank_nearest_does_not_query_and_invalid_ranges_fail_before_network(self):
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [dict(name='A')]}) as fetch:
            rows, _, _ = eng.search('systems', [spec(population_min='unfinished')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(fetch.call_count, 1)
        for condition in (spec(nearest_min=5, nearest_max=2), spec(nearest_max=10, population_min='nan'),
                          count('station_count', 'yes'), dict(field='carrier_count', op='true')):
            with self.subTest(condition=condition), patch.object(eng, '_http_json') as fetch, self.assertRaises(ValueError):
                eng.search('systems', [condition])
            fetch.assert_not_called()

    def test_system_only_conditions_reject_station_mode(self):
        for condition in (spec(), count('station_count', 0)):
            with self.subTest(condition=condition), patch.object(eng, '_http_json') as fetch, self.assertRaises(ValueError):
                eng.search('stations', [condition])
            fetch.assert_not_called()

    def test_multiple_detail_rows_and_diagnostics(self):
        conditions = [count('station_count', 0), spec(nearest_max=10), spec(nearest_min=3)]
        candidate = dict(name='A', stations=[], x=0, y=0, z=0)
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [candidate]}), \
                patch.object(details.bodies, 'populated_neighbour', return_value=(True, 'Neighbour', 200, 4)):
            rows, _, _ = eng.search('systems', conditions)
            stats, total = eng.diagnose('systems', conditions, pages=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]['_detail_outcomes']), 2)
        self.assertEqual(total, 1)
        self.assertTrue(all(hit == 1 for _, hit, _ in stats))

    def test_cancellation_does_not_accept_unverified_candidates(self):
        stop, notes = threading.Event(), []
        with patch.object(eng, '_http_json', return_value={'count': 1, 'results': [dict(name='A')]}), \
                patch.object(details.bodies, 'load_bodies', side_effect=InterruptedError):
            rows, _, _ = eng.search('systems', [spec(body_groups=[[body_condition('is_landable', 'true')]])],
                                    stop=stop, notes=notes)
        self.assertEqual(rows, [])
        self.assertTrue(any('已手动停止' in note for note in notes))


if __name__ == '__main__':
    unittest.main()
