import threading
import unittest
from unittest.mock import patch

import filter_engine as eng
import powerplay_tool as tool


def station(name, powers=None, arrival=50, distance=210, **extra):
    row = dict(id=name, name=name, system_name="System " + name, system_id64=name,
               system_x=distance, system_y=0, system_z=0, has_large_pad=True,
               is_planetary=False, type="Coriolis Starport", distance_to_arrival=arrival,
               system_power=list(powers or [tool.POWERS[0]]), system_power_state="Unoccupied",
               system_controlling_power="Another Power")
    row.update(extra)
    return row


class PowerplayTests(unittest.TestCase):
    def run_search(self, responses, **kwargs):
        with patch.object(eng, "resolve_ref", return_value=("Ngurii", (0, 0, 0), False)), \
                patch.object(eng, "_http_json", side_effect=responses) as http, \
                patch.object(tool, 'ENABLE_NEUTRON_FILTER', 'neutron_filter' in kwargs):
            result = tool.search_powerplay(**kwargs)
        return result, http

    def test_neutron_feature_enabled_and_switch_still_blocks_requests(self):
        self.assertTrue(tool.ENABLE_NEUTRON_FILTER)
        with patch.object(tool, 'ENABLE_NEUTRON_FILTER', False), patch.object(eng, '_http_json') as http:
            with self.assertRaises(ValueError):
                tool.search_powerplay(neutron_filter=lambda *_: dict(status='saving'))
        http.assert_not_called()

    def test_primary_template_and_exact_ring_boundaries(self):
        candidates = [station("below", distance=199.99), station("lower", distance=200),
                      station("upper", distance=220, arrival=100), station("above", distance=220.01),
                      station("carrier", type="Drake-Class Carrier"), station("surface", is_planetary=True),
                      station("small", has_large_pad=False), station("far", arrival=101),
                      station("controlled", system_power_state="Stronghold")]
        (info, groups), http = self.run_search([dict(count=9, results=candidates)])
        group = groups[tool.POWERS[0]]
        self.assertTrue(info["complete"])
        self.assertEqual([r["name"] for r in group["rows"]], ["lower", "upper"])
        self.assertEqual(group["status"], "标准范围")
        self.assertEqual(http.call_count, 1)
        filters = http.call_args.args[1]["filters"]
        self.assertEqual(filters["system_power"]["value"], [tool.POWERS[0]])
        self.assertEqual(filters["system_power_state"]["value"], ["Unoccupied"])
        self.assertNotIn("system_controlling_power", filters)
        self.assertEqual(filters["distance"], dict(min=200, max=220))

    def test_single_power_fallback_and_no_results(self):
        (info, groups), http = self.run_search([
            dict(count=0, results=[]), dict(count=2, results=[station("edge", arrival=1000),
                                                           station("too-far", arrival=1000.01)])],
            power="Arissa Lavigny-Duval")
        self.assertTrue(info["complete"])
        group = groups[tool.POWERS[0]]
        self.assertEqual(group["arrival_limit"], 1000)
        self.assertEqual([r["name"] for r in group["rows"]], ["edge"])
        self.assertEqual(group["status"], "放宽范围")
        self.assertEqual(http.call_count, 2)
        (info, groups), _ = self.run_search([dict(count=0, results=[]), dict(count=0, results=[])])
        self.assertTrue(info["complete"])
        self.assertEqual(groups[tool.POWERS[0]]["status"], "无结果")

    def test_all_powers_share_primary_and_independent_fallback(self):
        a, b, c = tool.POWERS[:3]
        (info, groups), http = self.run_search([
            dict(count=1, results=[station("shared", [a, b])]),
            dict(count=1, results=[station("fallback", [a, c], arrival=500)])], all_powers=True)
        self.assertTrue(info["complete"])
        self.assertEqual(len(groups), 12)
        self.assertEqual([r["name"] for r in groups[a]["rows"]], ["shared"])
        self.assertEqual([r["name"] for r in groups[b]["rows"]], ["shared"])
        self.assertEqual([r["name"] for r in groups[c]["rows"]], ["fallback"])
        self.assertEqual(groups[a]["arrival_limit"], 100)
        self.assertEqual(groups[c]["arrival_limit"], 1000)
        self.assertEqual(groups[tool.POWERS[-1]]["system_count"], 0)
        self.assertEqual(groups[tool.POWERS[-1]]["status"], "无结果")
        fallback_powers = http.call_args_list[1].args[1]["filters"]["system_power"]["value"]
        self.assertNotIn(a, fallback_powers)
        self.assertNotIn(b, fallback_powers)

    def test_page_limit_does_not_trigger_fallback_for_empty_powers(self):
        rows = [station(str(i)) for i in range(500)]
        (info, groups), http = self.run_search([dict(count=10000, results=rows)],
                                              all_powers=True, max_pages=1)
        self.assertFalse(info["complete"])
        self.assertEqual(http.call_count, 1)
        self.assertEqual(groups[tool.POWERS[1]]["status"], "未完成")
        self.assertIn("未完成", groups[tool.POWERS[0]]["status"])

    def test_unverifiable_fields_block_fallback(self):
        for key in ("has_large_pad", "is_planetary", "system_power_state", "system_power", "type"):
            row = station("missing")
            del row[key]
            (info, groups), http = self.run_search([dict(count=1, results=[row])])
            with self.subTest(key=key):
                self.assertFalse(info["complete"])
                self.assertEqual(groups[tool.POWERS[0]]["status"], "未完成")
                self.assertEqual(http.call_count, 1)

    def test_fallback_page_limit_and_duplicate_station(self):
        rows = [station(str(i), arrival=500) for i in range(500)]
        (info, groups), _ = self.run_search([dict(count=0, results=[]), dict(count=10000, results=rows)],
                                          max_pages=1)
        self.assertFalse(info["complete"])
        self.assertEqual(groups[tool.POWERS[0]]["status"], "放宽范围（未完成）")
        (info, groups), _ = self.run_search([dict(count=2, results=[station("same"), station("same")])])
        self.assertTrue(info["complete"])
        self.assertEqual(groups[tool.POWERS[0]]["system_count"], 1)

    def test_cancellation_and_request_failure(self):
        stop = threading.Event()
        stop.set()
        (info, groups), http = self.run_search([], all_powers=True, stop=stop)
        http.assert_not_called()
        self.assertFalse(info["complete"])
        self.assertEqual(groups[tool.POWERS[0]]["system_count"], 0)
        with self.assertRaisesRegex(RuntimeError, "network"):
            self.run_search([RuntimeError("network")])

    def test_top_five_per_power_sorted_by_exact_ly_then_ls(self):
        a, b = tool.POWERS[:2]
        records = [station("far-low-ls", [a, b], arrival=1, distance=215),
                   station("same-ly-high-ls", [a, b], arrival=80, distance=205),
                   station("same-ly-low-ls", [a, b], arrival=20, distance=205),
                   station("near-high-ls", [a, b], arrival=99, distance=200),
                   station("rounded-far-low-ls", [a, b], arrival=2, distance=210.004),
                   station("rounded-near-high-ls", [a, b], arrival=90, distance=210.001),
                   station("furthest", [a, b], arrival=0, distance=220)]
        for row in records:
            row["distance"] = row["system_x"]
        (info, groups), _ = self.run_search([dict(count=7, results=records),
                                           dict(count=0, results=[])], all_powers=True)
        self.assertTrue(info["complete"])
        for power in (a, b):
            self.assertEqual([r["name"] for r in groups[power]["rows"]],
                             ["near-high-ls", "same-ly-low-ls", "same-ly-high-ls",
                              "rounded-near-high-ls", "rounded-far-low-ls"])
            self.assertEqual(groups[power]["system_count"], 7)
            self.assertEqual(groups[power]["shown_count"], 5)

    def test_colonisation_ships_do_not_occupy_top_five(self):
        ships = [station("System Colonisation Ship", distance=200, type="Planetary Outpost"),
                 station("$EXT_PANEL_ColonisationShip:#index=1;", distance=200),
                 station("System Colonization Ship", distance=200),
                 station("Custom Name", distance=200, real_name="System Colonisation Ship"),
                 station("Typed Ship", distance=200, type="System Colonisation Ship")]
        (info, groups), http = self.run_search([dict(count=6, results=ships + [station("real-station")])])
        self.assertTrue(info["complete"])
        group = groups[tool.POWERS[0]]
        self.assertEqual([r["name"] for r in group["rows"]], ["real-station"])
        self.assertEqual(group["system_count"], 1)
        self.assertEqual(http.call_count, 1)

    def test_only_colonisation_ships_trigger_fallback(self):
        (info, groups), http = self.run_search([
            dict(count=1, results=[station("System Colonisation Ship", arrival=0,
                                           type="Planetary Outpost")]),
            dict(count=1, results=[station("real-station", arrival=500)])])
        self.assertTrue(info["complete"])
        self.assertEqual(info["unverifiable"], 0)
        self.assertEqual(http.call_count, 2)
        group = groups[tool.POWERS[0]]
        self.assertEqual(group["arrival_limit"], 1000)
        self.assertEqual([r["name"] for r in group["rows"]], ["real-station"])

    def test_validation_and_power_alias(self):
        self.assertEqual(tool.normalize_power("Arissa Lavigny-Duval"), tool.POWERS[0])
        for kwargs in (dict(reference=""), dict(power="invalid"), dict(min_ly=221),
                       dict(max_ly=float("inf")), dict(min_ly=float("nan")),
                       dict(min_ly=-1), dict(max_pages=0), dict(max_pages=True)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                tool.search_powerplay(**kwargs)

    def test_neutron_filter_runs_before_top_five_and_reuses_destinations(self):
        rows = [station(str(i), distance=200 + i) for i in range(7)]
        rows.append(station('another-station', system_name='System 6', distance=206))
        def compare(source, destination):
            return dict(status='saving' if destination == 'System 6' else 'not_proven',
                        outbound=3, inbound=2, ordinary_min=11, neutron_total=5, saved=6)
        calls = []
        def counted(source, destination):
            calls.append((source, destination))
            return compare(source, destination)
        (info, groups), _ = self.run_search([dict(count=8, results=rows)], neutron_filter=counted)
        self.assertTrue(info['complete'])
        selected = groups[tool.POWERS[0]]['rows']
        self.assertEqual({r['name'] for r in selected}, {'6'})
        self.assertTrue(all(r['_neutron']['saved'] == 6 for r in selected))
        self.assertEqual(len(calls), 7)

    def test_system_dedup_before_cap_keeps_nearest_station_per_power(self):
        a, b = tool.POWERS[:2]
        rows = [station('duplicate' + str(i), [a, b], arrival=90-i,
                        system_name='Shared System', distance=200) for i in range(8)]
        rows += [station('unique' + str(i), [a, b], distance=201+i) for i in range(5)]
        (info, groups), _ = self.run_search([dict(count=len(rows), results=rows), dict(count=0, results=[])],
                                          all_powers=True)
        self.assertTrue(info['complete'])
        for power in (a, b):
            self.assertEqual(groups[power]['system_count'], 6)
            self.assertEqual(groups[power]['shown_count'], 5)
            self.assertEqual([r['name'] for r in groups[power]['rows']],
                             ['duplicate7', 'unique0', 'unique1', 'unique2', 'unique3'])
            self.assertNotIn('station_count', groups[power])

    def test_neutron_unknown_blocks_fallback_and_marks_incomplete(self):
        (info, groups), http = self.run_search([dict(count=1, results=[station('unknown')])],
            neutron_filter=lambda *_: dict(status='unknown', reason='offline'))
        self.assertFalse(info['complete'])
        self.assertEqual(info['neutron_unknown'], 1)
        self.assertEqual(groups[tool.POWERS[0]]['rows'], [])
        self.assertEqual(groups[tool.POWERS[0]]['status'], '未完成')
        self.assertEqual(http.call_count, 1)

    def test_neutron_no_proven_savings_triggers_arrival_fallback(self):
        def compare(source, destination):
            return dict(status='saving' if destination == 'System fallback' else 'not_proven', saved=1)
        (info, groups), http = self.run_search([
            dict(count=1, results=[station('primary')]),
            dict(count=1, results=[station('fallback', arrival=500)])], neutron_filter=compare)
        self.assertTrue(info['complete'])
        self.assertEqual(http.call_count, 2)
        self.assertEqual(groups[tool.POWERS[0]]['rows'][0]['name'], 'fallback')

    def test_neutron_shared_power_rows_are_compared_once(self):
        a, b = tool.POWERS[:2]
        calls = []
        def compare(source, destination):
            calls.append(destination)
            return dict(status='saving', saved=1)
        (info, groups), _ = self.run_search([
            dict(count=1, results=[station('shared', [a, b])]), dict(count=0, results=[])],
            all_powers=True, neutron_filter=compare)
        self.assertTrue(info['complete'])
        self.assertEqual(calls, ['System shared'])
        self.assertTrue(groups[a]['rows'] and groups[b]['rows'])

    def test_alignment_relaxes_per_power_on_same_scan_without_filling_strict_groups(self):
        calls = []
        tiers = {}
        rows = []
        for index, power in enumerate(tool.POWERS):
            name = 'candidate' + str(index)
            rows.append(station(name, [power]))
            tiers['System ' + name] = index % 3
        rows.append(station('shared-relaxed', list(tool.POWERS[:3])))
        tiers['System shared-relaxed'] = 2
        def compare(source, destination):
            calls.append(destination)
            tier = tiers[destination]
            return dict(status='saving', saved=1, alignment_tier=tier,
                        alignment_label=('优先顺路', '适度绕行', '宽松候选')[tier])
        (info, groups), http = self.run_search([dict(count=len(rows), results=rows)],
                                              all_powers=True, neutron_filter=compare)
        self.assertTrue(info['complete'])
        self.assertEqual(http.call_count, 1)
        self.assertEqual(len(calls), len(rows))
        for index, power in enumerate(tool.POWERS):
            self.assertEqual(groups[power]['alignment_tier'], index % 3)
        self.assertEqual(len(groups[tool.POWERS[0]]['rows']), 1)
        self.assertEqual(len(groups[tool.POWERS[1]]['rows']), 1)
        self.assertEqual(len(groups[tool.POWERS[2]]['rows']), 2)

    def test_relaxed_hits_do_not_replace_station_fallback_for_other_empty_powers(self):
        a, b = tool.POWERS[:2]
        rows = [station('wide', [a])]
        def compare(source, destination):
            return dict(status='saving', saved=1, alignment_tier=2, alignment_label='宽松候选')
        (info, groups), http = self.run_search([
            dict(count=1, results=rows), dict(count=1, results=[station('fallback', [b], arrival=500)])],
            all_powers=True, neutron_filter=compare)
        self.assertTrue(info['complete'])
        self.assertEqual(http.call_count, 2)
        fallback_powers = http.call_args_list[1].args[1]['filters']['system_power']['value']
        self.assertNotIn(a, fallback_powers)
        self.assertEqual(groups[a]['arrival_limit'], 100)
        self.assertEqual(groups[b]['arrival_limit'], 1000)

    def test_partial_relaxed_scan_remains_incomplete_and_does_not_refetch(self):
        rows = [station('partial' + str(i), system_name='Shared') for i in range(500)]
        (info, groups), http = self.run_search([dict(count=10000, results=rows)], max_pages=1,
            neutron_filter=lambda *a: dict(status='saving', saved=1, alignment_tier=2,
                                          alignment_label='宽松候选'))
        self.assertFalse(info['complete'])
        self.assertEqual(http.call_count, 1)
        group = groups[tool.POWERS[0]]
        self.assertIn('未完成', group['status'])
        self.assertEqual(group['alignment_tier'], 2)
        self.assertEqual(group['system_count'], 1)

    def test_zero_saving_candidate_is_not_dropped_or_relaxed(self):
        def compare(source, destination):
            strict = destination == 'System strict'
            return dict(status='candidate', saved=0 if strict else 3,
                        alignment_tier=0 if strict else 2,
                        alignment_label='优先顺路' if strict else '宽松候选')
        (info, groups), http = self.run_search([
            dict(count=2, results=[station('strict'), station('relaxed')])], neutron_filter=compare)
        group = groups[tool.POWERS[0]]
        self.assertTrue(info['complete'])
        self.assertEqual(info['neutron_unknown'], 0)
        self.assertEqual(http.call_count, 1)
        self.assertEqual(group['alignment_tier'], 0)
        self.assertEqual([r['name'] for r in group['rows']], ['strict'])
        self.assertEqual(group['rows'][0]['_neutron']['saved'], 0)

    def test_actual_zero_savings_evaluator_retains_geometric_match(self):
        from rare_neutron import SavingsFilter
        evaluator = SavingsFilter(anchor_loader=lambda *a, **k: [dict(name='Near', coords=(20, 0, 0))])
        (info, groups), http = self.run_search([dict(count=1, results=[station('near', distance=40)])],
            min_ly=30, max_ly=50, neutron_filter=evaluator)
        self.assertTrue(info['complete'])
        self.assertEqual(http.call_count, 1)
        row = groups[tool.POWERS[0]]['rows'][0]
        self.assertEqual(row['_neutron']['saved'], 0)
        self.assertEqual(row['_neutron']['status'], 'candidate')

    def test_neutron_stop_retains_only_finished_comparisons(self):
        stop = threading.Event()
        def compare(source, destination):
            if destination == 'System first':
                return dict(status='saving', saved=1)
            stop.set()
            raise InterruptedError('cancelled')
        (info, groups), http = self.run_search([
            dict(count=2, results=[station('first', distance=200), station('second', distance=201)])],
            neutron_filter=compare, stop=stop)
        self.assertFalse(info['complete'])
        self.assertEqual(http.call_count, 1)
        self.assertEqual([r['name'] for r in groups[tool.POWERS[0]]['rows']], ['first'])


if __name__ == "__main__":
    unittest.main()
