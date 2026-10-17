import unittest

from i18n import translate
from main_csv import export_table


class MainCsvTests(unittest.TestCase):
    def table(self, rows, conditions, language='en', kind='stations'):
        return export_table(rows, kind, conditions, language, lambda s: translate(s, language))

    def test_only_requested_fields_aliases_and_actual_values(self):
        headers, rows = self.table([dict(name='Port', system_name='Sol', primary_economy='Industrial',
                                        services=['Repair', 'Refuel'], is_planetary=False, population=99)],
                                  [dict(field='economy'), dict(field='services'), dict(field='planetary'),
                                   dict(field='services')])
        self.assertEqual(len(headers), 5)
        self.assertEqual(rows[0][2:], ['Industrial', 'Repair; Refuel', 'False'])
        self.assertNotIn('Population', headers)

    def test_multiple_distances_missing_values_and_zero(self):
        headers, rows = self.table([dict(name='Sol', _distances={'Sol': 0, 'A': 1234.567})],
                                  [dict(type='distance', ref_system=r) for r in ('Sol', 'A', 'B', 'Sol')])
        self.assertEqual(len(headers), 5)
        self.assertEqual(rows[0][2:], ['0.00', '1,234.57', 'Unknown'])

    def test_details_and_freshness_are_included_only_when_requested(self):
        row = dict(name='A', modules=[dict(name='Drive', **{'class': 5, 'rating': 'A'})],
                   outfitting_updated_at='2026-10-17', _system_details=dict(
                       groups=[dict(condition=1, planets='1: A 1', rings='1: A 2')],
                       neighbours=[dict(condition=1, name='B', population=1234, distance=4.567)]))
        headers, rows = self.table([row], [dict(field='modules', op='=', text='Drive', fresh_days=7),
            dict(type='system_details', body_groups=[[{}]], ring_groups=[[{}]], nearest_max=10)])
        self.assertIn('Outfitting updated at', headers)
        self.assertEqual(rows[0][2:5], ['Drive', '5', 'A'])
        self.assertEqual(rows[0][-5:], ['1: A 1', '1: A 2', 'B', '1,234', '4.57'])

    def test_no_conditions_export_only_identity(self):
        headers, rows = self.table([dict(name='A', diagnostic='unused')], [])
        self.assertEqual(headers, ['Name', 'System'])
        self.assertEqual(rows, [['A', 'A']])

    def test_arrival_distance_uses_ls_in_both_languages(self):
        for language, title in (('zh', '到达距离 ls'), ('en', 'Arrival distance ls')):
            headers, rows = self.table([dict(name='Port', distance_to_arrival=1234.567)],
                                      [dict(field='distance_to_arrival')], language)
            self.assertEqual(headers[-1], title)
            self.assertEqual(rows[0][-1], '1,234.57')
