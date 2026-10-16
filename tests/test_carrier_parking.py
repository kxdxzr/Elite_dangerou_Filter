import threading
import unittest
from unittest.mock import patch

import filter_engine as engine


def system(name, count, x=1, permit=False):
    return dict(name=name, id64=name, x=x, y=0, z=0, needs_permit=permit,
                stations=[dict(name=str(i), type="Drake-Class Carrier" if i == 0
                               else "Settlement") for i in range(count)])


class CarrierParkingTests(unittest.TestCase):
    def test_carriers_counted_independently_of_station_total(self):
        for count in (0, 9, 10, 19, 20, 100):
            with self.subTest(count=count):
                total, carriers, actual, _ = engine.carrier_parking_summary(system("A", count))
                self.assertEqual((total, carriers, actual), (count, int(count > 0), "已收录"))

    def test_missing_types_are_unknown_not_zero(self):
        for station in ({}, {'type': None}, {'type': 1}, {'type': '  '}):
            self.assertEqual(engine.carrier_parking_summary(dict(stations=[station]))[:3],
                             (1, None, '未知'))

    def test_inclusive_count_bounds_and_unknown_exclusion(self):
        records = [system('zero', 0), system('one', 25),
                   {**system('two', 0), 'stations': [{'type': 'Fleet Carrier'}, {'type': 'Drake-Class Carrier'}]},
                   {**system('unknown', 0), 'stations': [{}]}]
        with patch.object(engine, 'resolve_ref', return_value=('Sol', (0, 0, 0), False)), \
                patch.object(engine, '_http_json', return_value=dict(count=4, results=records)):
            _, rows = engine.carrier_parking_search('Sol', min_carriers=1, max_carriers=2)
            self.assertEqual([r['name'] for r in rows], ['one', 'two'])
            _, rows = engine.carrier_parking_search('Sol', max_carriers=0)
            self.assertEqual([r['name'] for r in rows], ['zero'])
            info, rows = engine.carrier_parking_search('Sol')
            self.assertEqual(len(rows), 4)
            self.assertEqual(info['unknown'], 1)

    def test_invalid_count_bounds(self):
        for bounds in (dict(min_carriers=-1), dict(max_carriers=True), dict(min_carriers=1.5),
                       dict(max_carriers='2'), dict(max_carriers=float('nan')),
                       dict(min_carriers=3, max_carriers=2)):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                engine.carrier_parking_search('Sol', **bounds)

    def test_missing_and_invalid_stations_are_unknown(self):
        for value in (None, 0, {}, [None], ["carrier"]):
            self.assertEqual(engine.carrier_parking_summary(dict(stations=value))[:3],
                             (None, None, "未知"))
        self.assertIsNone(engine.carrier_parking_summary({})[0])

    def test_radius_filter_permit_filter_and_sort(self):
        records = [system("far", 19, 5), system("near", 9, 1),
                   system("crowded", 20, 2), system("permit", 1, 3, True),
                   system("unknown-permit", 1, 2, None), system("outside", 1, 31),
                   dict(name="unknown", id64="unknown", x=2, y=0, z=0, needs_permit=False)]
        with patch.object(engine, "resolve_ref", return_value=("Sol", (0, 0, 0), False)), \
                patch.object(engine, "_http_json", return_value=dict(count=7, results=records)) as http:
            info, rows = engine.carrier_parking_search("Sol", 30)
        self.assertEqual([r["name"] for r in rows], ["near", "crowded", "unknown", "far"])
        self.assertEqual([r["_station_count"] for r in rows], [9, 20, None, 19])
        self.assertEqual(rows[0]["_parking_distance"], 1)
        self.assertTrue(info["complete"])
        self.assertEqual(info["unknown"], 1)
        payload = http.call_args.args[1]
        self.assertEqual(payload["filters"]["distance"]["max"], 30)
        self.assertNotIn("stations", payload["filters"])

    def test_all_mode_keeps_unknown_crowded_and_permit(self):
        records = [system("crowded", 20), system("permit", 1, permit=True),
                   dict(name="unknown", id64="unknown", x=1, y=0, z=0)]
        with patch.object(engine, "resolve_ref", return_value=("Sol", (0, 0, 0), False)), \
                patch.object(engine, "_http_json", return_value=dict(count=3, results=records)):
            _, rows = engine.carrier_parking_search("Sol", exclude_permit=False)
        self.assertEqual(len(rows), 3)
        unknown = next(r for r in rows if r["name"] == "unknown")
        self.assertIsNone(unknown["_station_count"])
        self.assertEqual(unknown["_parking_category"], "未知")

    def test_pagination_limit_and_deduplication(self):
        first = [system(str(i), 0) for i in range(500)]
        second = [first[0], system("new", 10)]
        with patch.object(engine, "resolve_ref", return_value=("Sol", (0, 0, 0), False)), \
                patch.object(engine, "_http_json", side_effect=[dict(count=10000, results=first),
                                                                dict(count=10000, results=second)]):
            info, rows = engine.carrier_parking_search("Sol", max_pages=2)
        self.assertTrue(info["complete"])
        self.assertEqual(len(rows), 501)
        with patch.object(engine, "resolve_ref", return_value=("Sol", (0, 0, 0), False)), \
                patch.object(engine, "_http_json", return_value=dict(count=10000, results=first)):
            info, rows = engine.carrier_parking_search("Sol", max_pages=1)
        self.assertFalse(info["complete"])
        self.assertEqual(len(rows), 500)

    def test_validation_and_cancel_before_request(self):
        for radius in (0, -1, 50.01, 51, float("nan"), float("inf"), "bad", True):
            with self.assertRaises(ValueError):
                engine.carrier_parking_search("Sol", radius)
        for pages in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                engine.carrier_parking_search("Sol", max_pages=pages)
        with self.assertRaises(ValueError):
            engine.carrier_parking_search("")
        stop = threading.Event()
        stop.set()
        with patch.object(engine, "_http_json") as http:
            info, rows = engine.carrier_parking_search("Sol", stop=stop)
        http.assert_not_called()
        self.assertFalse(info["complete"])
        self.assertEqual(rows, [])

    def test_maximum_radius_is_accepted(self):
        with patch.object(engine, "resolve_ref", return_value=("Sol", (0, 0, 0), False)), \
                patch.object(engine, "_http_json", return_value=dict(count=1, results=[system("edge", 0, 50)])) as http:
            info, rows = engine.carrier_parking_search("Sol", 50)
        self.assertEqual(info["radius"], 50)
        self.assertEqual([r["name"] for r in rows], ["edge"])
        self.assertEqual(http.call_args.args[1]["filters"]["distance"]["max"], 50)


if __name__ == "__main__":
    unittest.main()
