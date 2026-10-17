import threading
import unittest
from unittest.mock import patch

import rare_neutron as neutron


def anchor(name='Near', x=150, arrival=0):
    return dict(name=name, coords=(x, 0, 0), arrival_ls=arrival)


class NeutronSavingsTests(unittest.TestCase):
    def test_directed_round_trip_counts_and_single_source_catalogue(self):
        calls = []
        def loader(source, coords, **kwargs):
            calls.append((source, coords))
            return [anchor()]
        evaluate = neutron.SavingsFilter(anchor_loader=loader)
        answer = evaluate.evaluate('Ngurii', 'Destination', (0, 0, 0), (210, 0, 0))
        self.assertEqual((answer['outbound'], answer['inbound'], answer['ordinary_min'], answer['saved']), (5, 3, 11, 3))
        self.assertEqual(answer['outbound_anchors'], ['Near'])
        self.assertEqual(answer['inbound_anchors'], ['Near'])
        self.assertEqual(evaluate.evaluate('ngurii', 'destination', (0, 0, 0), (210, 0, 0)), answer)
        evaluate.evaluate('Ngurii', 'Another', (0, 0, 0), (220, 0, 0))
        self.assertEqual(calls, [('Ngurii', (0, 0, 0))])

    def test_no_catalogue_means_no_savings_and_no_fifty_destination_limit(self):
        evaluate = neutron.SavingsFilter(anchor_loader=lambda *a, **k: [])
        for i in range(65):
            answer = evaluate.evaluate('Source', str(i), (0, 0, 0), (210, i, 0))
            self.assertEqual(answer['status'], 'not_proven')
        self.assertEqual(evaluate.evaluated, 65)

    def test_full_boost_and_no_boost_on_arrival(self):
        self.assertEqual(neutron.estimate_leg((150, 0, 0), (310, 0, 0), [anchor()], 40)[0], 1)
        self.assertEqual(neutron.estimate_leg((310, 0, 0), (150, 0, 0), [anchor()], 40)[0], 4)
        self.assertEqual(neutron.estimate_leg((0, 0, 0), (0, 0, 0), [], 40)[0], 0)

    def test_chained_anchors_and_source_as_anchor(self):
        anchors = [anchor('First', 40), anchor('Second', 200)]
        count, names = neutron.estimate_leg((0, 0, 0), (360, 0, 0), anchors, 40)
        self.assertEqual((count, names), (3, ['First', 'Second']))
        self.assertEqual(neutron.estimate_leg((40, 0, 0), (200, 0, 0), anchors, 40), (1, ['First']))

    def test_source_change_loads_a_separate_catalogue(self):
        calls = []
        def loader(name, origin, **kwargs):
            calls.append((name, origin))
            return []
        evaluate = neutron.SavingsFilter(anchor_loader=loader)
        evaluate.evaluate('Ngurii', 'D', (169.5, -42.3, 87.1), (210, 0, 0))
        evaluate.evaluate('Lave', 'D', (75, 48, 70), (210, 0, 0))
        self.assertEqual([c[0] for c in calls], ['Ngurii', 'Lave'])

    def test_bad_coordinates_and_failed_catalogue_are_unknown(self):
        calls = []
        def fail(*a, **k):
            calls.append(1)
            raise OSError('offline')
        evaluate = neutron.SavingsFilter(anchor_loader=fail)
        for target in ('One', 'Two'):
            self.assertEqual(evaluate.evaluate('Source', target, (0, 0, 0), (200, 0, 0))['status'], 'unknown')
        self.assertEqual(calls, [1])
        for coords in (None, (True, 0, 0), (float('nan'), 0, 0)):
            self.assertEqual(evaluate.evaluate('Other', repr(coords), (0, 0, 0), coords)['status'], 'unknown')

    def test_cancellation_does_not_load(self):
        stop = threading.Event()
        stop.set()
        with patch.object(neutron, 'load_anchors') as load:
            with self.assertRaises(InterruptedError):
                neutron.SavingsFilter(stop=stop).evaluate('S', 'D', (0, 0, 0), (210, 0, 0))
        load.assert_not_called()

    def test_rounding(self):
        self.assertEqual(neutron.lower_bound(0, 40), 0)
        self.assertEqual(neutron.lower_bound(200 + 1e-10, 40), 5)
        self.assertEqual(neutron.lower_bound(200.01, 40), 6)

    def test_alignment_rejects_reverse_overshoot_angle_and_detour(self):
        origin, target = (0, 0, 0), (210, 0, 0)
        self.assertEqual(neutron.alignment(origin, target, (150, 0, 0)),
                         dict(direction_deg=0, detour_ly=0, detour_ratio=0))
        for coords in ((-1, 0, 0), (211, 0, 0), (5, 3.5, 0), (180, 60, 0)):
            with self.subTest(coords=coords):
                self.assertIsNone(neutron.alignment(origin, target, coords))
        self.assertIsNone(neutron.alignment(origin, origin, (0, 0, 0)))

    def test_moderate_detour_can_pass_but_is_not_labelled_strict(self):
        off = dict(name='Off', coords=(100, 60, 0))
        origin, target = (0, 0, 0), (210, 0, 0)
        out, _ = neutron.estimate_leg(origin, target, [off], 40)
        inbound, _ = neutron.estimate_leg(target, origin, [off], 50)
        self.assertLess(out + inbound, 11)
        answer = neutron.SavingsFilter(anchor_loader=lambda *a, **k: [off]).evaluate('S', 'D', origin, target)
        self.assertEqual(answer['status'], 'candidate')
        self.assertEqual(answer['alignment_tier'], 1)
        self.assertEqual(answer['alignment_label'], '适度绕行')

    def test_relaxed_candidate_and_final_limits(self):
        origin, target = (0, 0, 0), (210, 0, 0)
        for xyz, expected in (((100, 100, 0), 2), ((100, 150, 0), None), ((-10, 0, 0), None),
                              ((211, 0, 0), None)):
            with self.subTest(xyz=xyz):
                evaluate = neutron.SavingsFilter(anchor_loader=lambda *a, **k: [dict(name='N', coords=xyz)])
                answer = evaluate.evaluate('S', 'D', origin, target)
                if expected is None:
                    self.assertEqual(answer['status'], 'not_proven')
                else:
                    self.assertEqual(answer['status'], 'candidate')
                    self.assertEqual(answer['alignment_tier'], expected)

    def test_alignment_passes_even_without_model_savings(self):
        a = anchor(x=20)
        self.assertIsNotNone(neutron.alignment((0, 0, 0), (40, 0, 0), a['coords']))
        answer = neutron.SavingsFilter(anchor_loader=lambda *a, **k: [anchor(x=20)]).evaluate(
            'S', 'D', (0, 0, 0), (40, 0, 0))
        self.assertEqual(answer['status'], 'candidate')
        self.assertEqual(answer['saved'], 0)
        self.assertEqual(answer['route_anchor'], 'Near')

    def test_saving_candidate_prefers_least_detour_and_uses_same_anchor(self):
        anchors = [dict(name='Bent', coords=(140, 10, 0)), anchor('Straight')]
        answer = neutron.SavingsFilter(anchor_loader=lambda *a, **k: anchors).evaluate(
            'S', 'D', (0, 0, 0), (210, 0, 0))
        self.assertEqual(answer['status'], 'candidate')
        self.assertEqual(answer['route_anchor'], 'Straight')
        self.assertEqual(answer['outbound_anchors'], ['Straight'])
        self.assertEqual(answer['inbound_anchors'], ['Straight'])
        self.assertEqual(answer['detour_ly'], 0)

    def test_model_failure_keeps_aligned_candidate_and_cancellation_still_propagates(self):
        evaluate = neutron.SavingsFilter(anchor_loader=lambda *a, **k: [anchor()])
        with patch.object(neutron, 'estimate_leg', side_effect=ValueError('hint unavailable')):
            answer = evaluate.evaluate('S', 'D', (0, 0, 0), (210, 0, 0))
        self.assertEqual(answer['status'], 'candidate')
        self.assertFalse(answer['model_available'])
        self.assertEqual(answer['route_anchor'], 'Near')
        evaluate = neutron.SavingsFilter(anchor_loader=lambda *a, **k: [anchor()])
        with patch.object(neutron, 'estimate_leg', side_effect=InterruptedError('stopped')):
            with self.assertRaises(InterruptedError):
                evaluate.evaluate('S', 'D', (0, 0, 0), (210, 0, 0))

    def test_range_hints_do_not_change_geometric_eligibility(self):
        for outbound, inbound in ((40, 50), (64, 81), (300, 300)):
            with self.subTest(ranges=(outbound, inbound)), \
                    patch.object(neutron, 'OUTBOUND_RANGE', outbound), patch.object(neutron, 'RETURN_RANGE', inbound):
                answer = neutron.SavingsFilter(anchor_loader=lambda *a, **k: [anchor()]).evaluate(
                    'S', 'D', (0, 0, 0), (210, 0, 0))
                self.assertEqual(answer['status'], 'candidate')
                self.assertEqual(answer['alignment_tier'], 0)

    def test_catalogue_center_radius_arrival_and_coordinate_validation(self):
        origin = (169.5, -42.3, 87.1)
        bodies = [dict(system_name=n, name=n, subtype='Neutron Star', distance_to_arrival=ls)
                  for n, ls in [('Primary', 0), ('Boundary', 100), ('FarSecondary', 100.1), ('Outside', 0)]]
        coords = {'Primary': (319.5, -42.3, 87.1), 'Boundary': (369.5, -42.3, 87.1),
                  'Outside': (369.6, -42.3, 87.1)}
        with patch.object(neutron.pve_cache, 'cached', side_effect=lambda key, load, ttl: (load(), {})), \
                patch.object(neutron.eng, '_lookup_exact', side_effect=lambda n: (n, coords[n])), \
                patch.object(neutron.eng, '_http_json', return_value=dict(count=4, results=bodies)) as http:
            result = neutron.load_anchors('Ngurii', origin)
        self.assertEqual({a['name'] for a in result}, {'Primary', 'Boundary'})
        payload = http.call_args.args[1]
        self.assertEqual(payload['reference_coords'], dict(zip(('x', 'y', 'z'), origin)))
        self.assertEqual(payload['filters']['distance']['max'], 200)

    def test_catalogue_failures_are_not_cached_as_empty(self):
        bad = [dict(results=[] , count=2), dict(results=None),
               dict(results=[dict(system_name='Unknown', name='Unknown', subtype='Neutron Star')])]
        for response in bad:
            with self.subTest(response=response), \
                    patch.object(neutron.pve_cache, 'cached', side_effect=lambda key, load, ttl: (load(), {})), \
                    patch.object(neutron.eng, '_http_json', return_value=response):
                with self.assertRaises(ValueError):
                    neutron.load_anchors('Ngurii', (0, 0, 0))
