import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_source_data_stays_in_project(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(runtime_paths.sys, "frozen", False, create=True):
            self.assertEqual(runtime_paths.data_directory(), str(runtime_paths.PROJECT / 'data'))
            self.assertEqual(runtime_paths.cache_directory(), str(runtime_paths.PROJECT / 'cache'))

    def test_frozen_data_is_outside_unpack_directory(self):
        local = os.path.join(os.path.expanduser("~"), "AppData", "Local")
        with patch.dict(os.environ, {"LOCALAPPDATA": local}, clear=True), \
                patch.object(runtime_paths.sys, "frozen", True, create=True):
            self.assertEqual(runtime_paths.data_directory(), os.path.join(local, "EliteDangerousFilter"))
            self.assertEqual(runtime_paths.cache_directory(), runtime_paths.data_directory())

    def test_override_for_isolated_execution(self):
        directory = os.path.join(os.path.expanduser("~"), "isolated-data")
        with patch.dict(os.environ, {"ELITE_FILTER_DATA_DIR": directory}, clear=True):
            self.assertEqual(runtime_paths.data_directory(), os.path.abspath(directory))
            self.assertEqual(runtime_paths.cache_directory(), os.path.abspath(directory))

    def test_legacy_files_move_without_changing_contents(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), \
                patch.object(runtime_paths.sys, 'frozen', False, create=True), \
                patch.object(runtime_paths, 'PROJECT', Path(directory)):
            root = Path(directory)
            files = {'last_session.json': b'{"personal":true}', 'route_ship_favorites.json': b'{"ships":{}}',
                     'field_values_cache.json': b'fields', 'module_specs_cache.json': b'modules',
                     'route_module_cache.json': b'drives', 'pve_cache_123.json': b'pve'}
            for name, content in files.items():
                (root / name).write_bytes(content)
            report = runtime_paths.migrate_legacy_files()
            self.assertEqual(report, dict(moved=6, conflicts=[]))
            for name, content in files.items():
                folder = 'cache' if runtime_paths.is_cache(name) else 'data'
                self.assertEqual((root / folder / name).read_bytes(), content)
                self.assertFalse((root / name).exists())
                self.assertEqual(runtime_paths.data_file(name), str(root / folder / name))
            self.assertEqual(runtime_paths.migrate_legacy_files()['moved'], 0)

    def test_lazy_migration_preserves_conflicting_copies(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), \
                patch.object(runtime_paths.sys, 'frozen', False, create=True), \
                patch.object(runtime_paths, 'PROJECT', Path(directory)):
            root = Path(directory)
            (root / 'last_session.json').write_bytes(b'old')
            target = Path(runtime_paths.data_file('last_session.json'))
            self.assertEqual(target.read_bytes(), b'old')
            (root / 'last_session.json').write_bytes(b'conflict')
            self.assertEqual(runtime_paths.data_file('last_session.json'), str(target))
            self.assertEqual(target.read_bytes(), b'old')
            self.assertEqual(runtime_paths.migrate_legacy_files()['conflicts'], ['last_session.json'])
            self.assertEqual((root / 'last_session.json').read_bytes(), b'conflict')

    def test_override_does_not_migrate_project_files(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'ELITE_FILTER_DATA_DIR': directory}, clear=True):
            self.assertEqual(runtime_paths.data_file('pve_cache_123.json'), os.path.join(directory, 'pve_cache_123.json'))
            self.assertEqual(runtime_paths.migrate_legacy_files(), dict(moved=0, conflicts=[]))

    def test_failed_copy_keeps_original_and_cleans_partial_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'old.json', Path(directory) / 'data' / 'new.json'
            source.write_bytes(b'original')
            with patch.object(runtime_paths.shutil, 'copyfileobj', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    runtime_paths._migrate_file(source, target)
            self.assertEqual(source.read_bytes(), b'original')
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
