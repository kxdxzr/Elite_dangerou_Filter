import unittest

import field_categories as categories
import field_options as options
import module_slots as slots
from spansh_filter import STATION_FIELDS, SYSTEM_FIELDS
from system_filter_fields import COUNT_FIELDS


class BrowsingCategoryTests(unittest.TestCase):
    def test_each_condition_field_has_one_available_category(self):
        for fields in (STATION_FIELDS, dict(SYSTEM_FIELDS, **COUNT_FIELDS)):
            groups = categories.available_groups(fields)
            flattened = [field for group in groups if group != '不限' for field in categories.fields_for(fields, group)]
            self.assertEqual(sorted(flattened), sorted(fields))
            self.assertEqual(categories.fields_for(fields, '不限'), sorted(fields))
        self.assertEqual(categories.category('system_controlling_power'), '势力派系')
        self.assertEqual(categories.category('modules'), '商品与舰船模组')
        self.assertEqual(categories.category('outfitting_last_updated_at'), '数据时间')

    def test_module_slot_groups_and_unknown_names(self):
        for name in options.BUNDLED_MODULE_SPECS:
            self.assertTrue(slots.groups_for(name))
        for name, group in (('Frame Shift Drive', '核心内部'), ('Fuel Scoop', '可选内部'),
                            ('Beam Laser', '武器挂点'), ('Chaff Launcher', '通用插槽'),
                            ('Unknown future module', '其他／未分类')):
            self.assertIn(group, slots.groups_for(name))
        self.assertEqual(slots.groups_for('Fuel Tank'), {'核心内部', '可选内部'})
        names = ['Frame Shift Drive', 'Fuel Scoop', 'Beam Laser']
        self.assertEqual(slots.options_for(names, '武器挂点'), ['Beam Laser'])
        self.assertEqual(slots.options_for(names, '不限'), names)
