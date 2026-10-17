import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import field_options as fo
from module_spec_pairs import BUNDLED_MODULE_PAIRS


class ModulePairTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'specs.json'
        self.patches = [patch.object(fo, 'SPECS_FILE', str(self.path)),
                        patch.object(fo, '_specs', None), patch.object(fo, '_specs_dirty', False)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def test_all_153_modules_preserve_real_pairs_without_cross_products(self):
        self.assertEqual(len(BUNDLED_MODULE_PAIRS), 153)
        self.assertEqual(set(BUNDLED_MODULE_PAIRS), set(fo.BUNDLED_MODULE_SPECS))
        for name, pairs in BUNDLED_MODULE_PAIRS.items():
            with self.subTest(name=name):
                self.assertTrue(pairs)
                self.assertEqual(len(pairs), len(set(pairs)))
                self.assertTrue(all(cls in range(9) and rating in 'ABCDEFGHI' for cls, rating in pairs))
                self.assertEqual(fo.get_module_variants(name), [f'{c}{r}' for c, r in sorted(pairs)])

    def test_plasma_railgun_weapons_and_internals(self):
        for name, expected in (
                ('Plasma Accelerator', ['2C', '3B', '4A']), ('Rail Gun', ['1D', '2B']),
                ('Missile Rack', ['1B', '2B', '3A']),
                ('Support Focused Power Distributor', ['3A', '3D', '4A', '4D', '6A']),
                ('Guardian Gauss Cannon', ['1D', '2B'])):
            self.assertEqual(fo.get_module_variants(name), expected)
        self.assertNotIn('2A', fo.get_module_variants('Plasma Accelerator'))
        self.assertNotIn('6D', fo.get_module_variants('Support Focused Power Distributor'))
        self.assertEqual(fo.get_module_variants(['Plasma Accelerator', 'Rail Gun']), ['1D', '2B', '2C', '3B', '4A'])
        self.assertEqual(fo.get_module_variants('Future Module'), [])
        self.assertEqual(fo.get_module_variants([]), [])

    def test_old_independent_lists_do_not_create_fake_pairs(self):
        self.path.write_text(json.dumps({
            'Plasma Accelerator': {'class': [2, 3, 4], 'rating': ['A', 'B', 'C', 'Z']},
            'Old Module': {'class': [3, 5], 'rating': ['A', 'B']},
            'Malformed': {'class': 5, 'rating': False, 'pairs': [None, [True, 'A'], [2, 'Z']]},
        }), encoding='utf-8')
        self.assertEqual(fo.get_module_variants('Plasma Accelerator'), ['2C', '3B', '4A'])
        self.assertEqual(fo.get_module_variants('Old Module'), [])
        self.assertEqual(fo.get_module_variants('Malformed'), [])
        self.assertEqual(fo.get_module_specs('Old Module'), ([3, 5], ['A', 'B']))

    def test_learning_and_roundtrip_preserve_relations_even_with_unchanged_marginals(self):
        fo.learn_module_specs([dict(name='New Module', **{'class': 3, 'rating': 'A'}),
                               dict(name='New Module', **{'class': 5, 'rating': 'B'})])
        self.assertEqual(fo.get_module_variants('New Module'), ['3A', '5B'])
        self.assertTrue(fo.save_module_specs())
        self.assertFalse(fo.save_module_specs())
        self.assertGreater(fo.learn_module_specs([dict(name='New Module', **{'class': 3, 'rating': 'B'})]), 0)
        self.assertTrue(fo.save_module_specs())
        fo._specs = None
        self.assertEqual(fo.get_module_variants('New Module'), ['3A', '3B', '5B'])
        self.assertNotIn('5A', fo.get_module_variants('New Module'))
        self.assertEqual(fo.learn_module_specs([dict(name='New Module', **{'class': 3, 'rating': 'B'})]), 0)

    def test_cache_write_failure_can_be_retried(self):
        fo.learn_module_specs([dict(name='New Module', **{'class': 3, 'rating': 'A'})])
        with patch('builtins.open', side_effect=OSError('read only')):
            self.assertFalse(fo.save_module_specs())
        self.assertTrue(fo.save_module_specs())
