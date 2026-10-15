import unittest
from unittest.mock import patch

import filter_engine as eng


class ExcludedSystemTests(unittest.TestCase):
    def test_specific_record_and_station_system_only(self):
        for row in ({"name": "Test"}, {"name": "TEST"},
                    {"id64": 7780433924818}, {"id64": "7780433924818"}):
            self.assertTrue(eng.is_excluded_system("systems", row))
        self.assertTrue(eng.is_excluded_system("stations", {"system_name": "Test"}))
        self.assertTrue(eng.is_excluded_system("stations", {"system_id64": 7780433924818}))
        for row in ({"name": "Test Station", "system_name": "Sol"},
                    {"name": "Test", "system_name": "Sol"}):
            self.assertFalse(eng.is_excluded_system("stations", row))
        for name in ("Sol", "Testimony", "Testing", "Test Sector AA-A a1"):
            self.assertFalse(eng.is_excluded_system("systems", {"name": name}))

    def test_excluded_row_does_not_fill_requested_result_count(self):
        response = {"count": 2, "results": [
            {"name": "Test", "id64": 7780433924818},
            {"name": "Sol", "id64": 10477373803},
        ]}
        with patch.object(eng, "_http_json", return_value=response):
            rows, total, scanned = eng.search("systems", [], want=1)
        self.assertEqual([row["name"] for row in rows], ["Sol"])
        self.assertEqual((total, scanned), (2, 2))

    def test_midpoint_excludes_test_before_result_limit(self):
        response = {"count": 2, "results": [
            {"name": "Test", "x": -1, "y": 0, "z": 0},
            {"name": "Sol", "x": 0, "y": 0, "z": 0},
        ]}
        with patch.object(eng, "resolve_ref", return_value=("Sol", (0, 0, 0), False)), \
                patch.object(eng, "_http_json", return_value=response):
            _, rows = eng.midpoint_search("Sol", "Sol", want=1)
        self.assertEqual([row["name"] for row in rows], ["Sol"])


if __name__ == "__main__":
    unittest.main()
