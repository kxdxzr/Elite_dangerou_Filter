import threading
import unittest
from unittest.mock import patch

import colonisation_tool as tool


def condition(field, value, op='='):
    return dict(field=field, value=str(value), op=op)


def planet(name, **kw):
    return dict(type='Planet', name=name, **kw)


def system(name='Candidate', **kw):
    return dict(name=name, population=0, stations=[], needs_permit=False, **kw)


class ColonisationTests(unittest.TestCase):
    def test_blank_and_zero_are_distinct(self):
        blank = tool.Criteria().validate()
        self.assertIsNone(blank.minimum_value)
        self.assertIsNone(blank.populated_radius)
        self.assertIsNone(blank.populated_min_distance)
        zero = tool.Criteria(minimum_value='0', populated_radius='0').validate()
        self.assertEqual((zero.minimum_value, zero.populated_radius), (0, 0))
        for value in ('nan', 'inf', '-1', True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.Criteria(minimum_value=value).validate()
        with self.assertRaises(ValueError):
            tool.Criteria(populated_min_distance=10, populated_radius=5).validate()

    def test_strict_eligibility_and_test_exclusion(self):
        self.assertTrue(tool.eligible(system()))
        for key in ('population', 'stations', 'needs_permit'):
            row = system()
            del row[key]
            self.assertIsNone(tool.eligible(row))
        for row in ({**system(), 'population': False}, {**system(), 'stations': None},
                    {**system(), 'needs_permit': 'false'}):
            self.assertIsNone(tool.eligible(row))
        for row in ({**system(), 'population': 1}, {**system(), 'needs_permit': True},
                    {**system(), 'stations': [{'type': 'Fleet Carrier'}]}, system(name='Test')):
            self.assertFalse(tool.eligible(row))

    def test_conditions_must_match_same_planet(self):
        group = [condition('subtype', 'Water world'), condition('gravity', '1', '<=')]
        bodies = [planet('A', subtype='Water world', gravity=2), planet('B', subtype='Rocky body', gravity=.5)]
        self.assertFalse(tool.match_groups(bodies, [group], 'AND')[0])
        bodies.append(planet('C', subtype='Water world', gravity=.7))
        hit, names = tool.match_groups(bodies, [group], 'AND')
        self.assertTrue(hit)
        self.assertIn('C', names)
        self.assertNotIn('A', names)

    def test_all_or_any_groups_and_reuse(self):
        bodies = [planet('A', subtype='Water world', is_landable=False)]
        a, b = [condition('subtype', 'Water world')], [condition('is_landable', 'true')]
        self.assertFalse(tool.match_groups(bodies, [a, b], 'AND')[0])
        self.assertTrue(tool.match_groups(bodies, [a, b], 'OR')[0])
        self.assertTrue(tool.match_groups(bodies, [a, a], 'AND')[0])
        self.assertTrue(tool.match_groups([], [], 'AND')[0])

    def test_unknown_does_not_match_even_negative_operator(self):
        self.assertIsNone(tool.condition_match({}, condition('subtype', 'Water world', '!=')))
        self.assertIsNone(tool.match_groups([planet('A')], [[condition('subtype', 'Water world')]], 'OR')[0])
        known = [planet('B', subtype='Water world'), planet('A')]
        self.assertTrue(tool.match_groups(known, [[condition('subtype', 'Water world')]], 'OR')[0])

    def test_ring_conditions_use_same_ring_and_parent(self):
        body = planet('A', distance_to_arrival=500, rings=[
            {'name': 'A ring', 'type': 'Metallic', 'mass': 10},
            {'name': 'B ring', 'type': 'Icy', 'mass': 100},
        ])
        group = [condition('ring.type', 'Metallic'), condition('ring.mass', '50', '>')]
        self.assertFalse(tool.match_body_group(body, group))
        self.assertFalse(tool.match_groups([body], [group], 'AND', rings=True)[0])
        independent = [condition('ring.type', 'Metallic'), condition('distance_to_arrival', '1000', '<=')]
        self.assertTrue(tool.match_groups([body], [independent], 'AND', rings=True)[0])
        self.assertFalse(tool.match_body_group(body, [condition('subtype', 'Earth-like world')] + independent))

    def test_relationships_distinguish_binaries_moons_and_siblings(self):
        parent = {'id64': 10, 'type': 'Null'}
        bodies = [planet('A', id64=1, parents=[parent], orbital_period=6),
                  planet('B', id64=2, parents=[parent], orbital_period=6),
                  planet('Moon', id64=3, parents=[{'id64': 1, 'type': 'Planet'}]),
                  planet('C', id64=4, parents=[{'id64': 20, 'type': 'Star'}]),
                  planet('D', id64=5, parents=[{'id64': 20, 'type': 'Star'}])]
        tool.annotate_relationships(bodies)
        self.assertTrue(bodies[0]['_is_binary'])
        self.assertIn('B', bodies[0]['_relations'])
        self.assertTrue(bodies[0]['_has_moons'])
        self.assertTrue(bodies[2]['_is_moon'])
        self.assertFalse(bodies[3]['_is_binary'])
        bodies.append(planet('Unknown'))
        tool.annotate_relationships(bodies)
        self.assertIsNone(bodies[-1]['_is_binary'])
        self.assertIsNone(bodies[0]['_is_binary'])
        bodies.append(dict(type='Star', name='Star', parents=[parent]))
        tool.annotate_relationships(bodies)
        self.assertIsNone(bodies[0]['_is_binary'])

    def test_validation(self):
        tool.Criteria(body_groups=[[condition('gravity', '.5|1', 'between')]]).validate()
        for groups in ([[condition('gravity', '1|.5', 'between')]],
                       [[condition('is_landable', 'yes')]], [[condition('subtype', 'Water', '>')]], [[]]):
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                tool.Criteria(body_groups=groups).validate()

    def test_search_applies_value_locally_and_blanks_skip_detail_requests(self):
        response = {'count': 2, 'results': [system(name='Equal', estimated_mapping_value=100),
                                          system(name='Greater', estimated_mapping_value=101)]}
        with patch.object(tool.eng, '_http_json', return_value=response) as fetch:
            info, rows = tool.search(tool.Criteria(minimum_value=100))
        self.assertEqual([r['name'] for r in rows], ['Greater'])
        self.assertTrue(info['complete'])
        self.assertEqual(fetch.call_count, 1)
        self.assertIn('estimated_mapping_value', fetch.call_args.args[1]['filters'])

    def test_missing_station_list_is_confirmed_not_assumed(self):
        row = system()
        del row['stations']
        with patch.object(tool.eng, '_http_json', return_value={'count': 1, 'results': [row]}), \
                patch.object(tool, 'confirm_station_absence', return_value={'candidate': []}) as verify:
            _, rows = tool.search(tool.Criteria())
        self.assertEqual(len(rows), 1)
        verify.assert_called_once()
        self.assertNotIn('stations', row)
        with patch.object(tool.eng, '_http_json', return_value={'count': 1, 'results': [row]}), \
                patch.object(tool, 'confirm_station_absence', return_value={'candidate': [{'name': 'Carrier'}]}):
            _, rows = tool.search(tool.Criteria())
        self.assertEqual(rows, [])

    def test_populated_neighbour_checks_population_and_actual_distance(self):
        response = {'results': [system(name='One', x=0, y=0, z=0),
                               dict(name='Valid', population=2, x=2, y=0, z=0),
                               dict(name='Far', population=10, x=10, y=0, z=0)]}
        response['results'][0]['population'] = 1
        with patch.object(tool.eng, '_http_json', return_value=response):
            hit, name, population, distance = tool.populated_neighbour(system(x=0, y=0, z=0), 3, 1)
        self.assertEqual((hit, name, population, distance), (True, 'Valid', 2, 2))

    def test_nearest_distance_is_not_existence_in_an_annulus(self):
        candidate = system(x=0, y=0, z=0)
        nearby = {'results': [dict(name='Too close', population=2, x=2, y=0, z=0),
                              dict(name='In interval', population=100, x=8, y=0, z=0)]}

        def fetch(url, payload, **kw):
            if 'reference_coords' in payload:
                self.assertEqual(payload['filters']['distance'], {'max': 10})
                return nearby
            return {'count': 1, 'results': [candidate]}

        with patch.object(tool.eng, '_http_json', side_effect=fetch):
            info, rows = tool.search(tool.Criteria(populated_min_distance=5, populated_radius=10))
        self.assertEqual(rows, [])
        self.assertEqual(info['unknown'], 0)

    def test_nearest_minimum_only_and_inclusive_boundaries(self):
        candidate = system(x=0, y=0, z=0)
        for minimum, maximum, accepted in ((3, None, True), (None, 3, True),
                                           (3, 3, True), (4, None, False), (None, 2, False)):
            def fetch(url, payload, **kw):
                if 'reference_coords' in payload:
                    if maximum is None:
                        self.assertNotIn('distance', payload['filters'])
                    return {'results': [dict(name='Nearest', population=2, x=3, y=0, z=0)]}
                return {'count': 1, 'results': [candidate]}
            with self.subTest(minimum=minimum, maximum=maximum), \
                    patch.object(tool.eng, '_http_json', side_effect=fetch):
                _, rows = tool.search(tool.Criteria(populated_min_distance=minimum, populated_radius=maximum))
            self.assertEqual(bool(rows), accepted)
            if rows:
                self.assertEqual(rows[0]['_neighbour_distance'], 3)

    def test_regional_and_nearest_distance_are_independent_and_anded(self):
        candidates = [system(name='Inside', x=20, y=0, z=0),
                      system(name='Outside', x=60, y=0, z=0)]
        calls = []

        def fetch(url, payload, **kw):
            if 'reference_coords' in payload:
                calls.append(payload)
                return {'results': [dict(name='Neighbour', population=2, x=24, y=0, z=0)]}
            self.assertEqual(payload['reference_system'], 'Sol')
            self.assertEqual(payload['filters']['distance']['max'], 50)
            return {'count': 2, 'results': candidates}

        with patch.object(tool.eng, 'resolve_ref', return_value=('Sol', (0, 0, 0), False)), \
                patch.object(tool.eng, '_http_json', side_effect=fetch):
            _, rows = tool.search(tool.Criteria(reference='Sol', radius=50,
                                               populated_min_distance=3, populated_radius=5))
        self.assertEqual([r['name'] for r in rows], ['Inside'])
        self.assertEqual(rows[0]['distance'], 20)
        self.assertEqual(rows[0]['_neighbour_distance'], 4)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['reference_coords']['x'], 20)

    def test_regional_only_does_not_lookup_populated_neighbours(self):
        with patch.object(tool.eng, 'resolve_ref', return_value=('Sol', (0, 0, 0), False)), \
                patch.object(tool.eng, '_http_json', return_value={'count': 1, 'results': [system(x=1, y=0, z=0)]}) as fetch:
            _, rows = tool.search(tool.Criteria(reference='Sol', radius=1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(rows[0]['_neighbour'], '')

    def test_uncertain_or_unsorted_neighbours_do_not_establish_nearest(self):
        candidate = system(x=0, y=0, z=0)
        nearby = {'results': [dict(name='Unknown', x=1, y=0, z=0),
                              dict(name='Known', population=2, x=3, y=0, z=0)]}
        with patch.object(tool.eng, '_http_json', return_value=nearby):
            self.assertIsNone(tool.populated_neighbour(candidate, 5, 1)[0])
        nearby = {'results': [dict(name='Far', population=2, x=4, y=0, z=0),
                              dict(name='Near', population=2, x=2, y=0, z=0)]}
        with patch.object(tool.eng, '_http_json', return_value=nearby), self.assertRaises(ValueError):
            tool.populated_neighbour(candidate, None, 1)

    def test_body_filters_and_independent_rings_are_anded(self):
        bodies = [planet('Earthlike', subtype='Earth-like world'),
                  planet('Giant', rings=[{'name': 'Ring', 'type': 'Metallic'}])]
        c = tool.Criteria(body_groups=[[condition('subtype', 'Earth-like world')]],
                          ring_groups=[[condition('ring.type', 'Metallic')]])
        with patch.object(tool.eng, '_http_json', return_value={'count': 1, 'results': [system()]}), \
                patch.object(tool, 'load_bodies', return_value={'candidate': bodies}):
            _, rows = tool.search(c)
        self.assertEqual(len(rows), 1)
        self.assertIn('Earthlike', rows[0]['_body_matches'])
        self.assertIn('Giant', rows[0]['_ring_matches'])

    def test_limits_cancellation_and_repeated_pages_are_not_complete(self):
        response = {'count': 1, 'results': [system()]}
        with patch.object(tool.eng, '_http_json', return_value=response):
            info, rows = tool.search(tool.Criteria(want=1))
        self.assertFalse(info['complete'])
        self.assertEqual(len(rows), 1)
        stop = threading.Event()
        stop.set()
        with patch.object(tool.eng, '_http_json') as fetch:
            info, rows = tool.search(tool.Criteria(), stop=stop)
        fetch.assert_not_called()
        self.assertFalse(info['complete'])
        self.assertEqual(rows, [])

    def test_incomplete_body_pages_are_not_treated_as_absent(self):
        bodies = [dict(name=str(i), system_name='Candidate', id64=i) for i in range(500)]
        with patch.object(tool.pve_cache, 'cached', side_effect=lambda k, fn, *a: (fn(), False)), \
                patch.object(tool.eng, '_http_json', return_value={'results': bodies}), self.assertRaises(ValueError):
            tool.load_bodies(['Candidate'])


if __name__ == '__main__':
    unittest.main()
