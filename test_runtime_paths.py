import os
import unittest
from unittest.mock import patch

import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_source_data_stays_in_project(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(runtime_paths.sys, "frozen", False, create=True):
            self.assertEqual(runtime_paths.data_directory(), os.path.dirname(os.path.abspath(runtime_paths.__file__)))

    def test_frozen_data_is_outside_unpack_directory(self):
        local = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        with patch.dict(os.environ, {"LOCALAPPDATA": local}, clear=True), \
                patch.object(runtime_paths.sys, "frozen", True, create=True):
            self.assertEqual(runtime_paths.data_directory(), os.path.join(local, "EliteDangerousFilter"))

    def test_override_for_isolated_execution(self):
        directory = os.path.join(os.path.expanduser("~"), "isolated-data")
        with patch.dict(os.environ, {"ELITE_FILTER_DATA_DIR": directory}, clear=True):
            self.assertEqual(runtime_paths.data_directory(), os.path.abspath(directory))


if __name__ == "__main__":
    unittest.main()
