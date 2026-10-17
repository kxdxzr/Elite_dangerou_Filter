import os
import sys
import tkinter as tk
import unittest

from i18n import Localizer
from localized_tk import ttk
from result_sort import cell_key, sorted_cells


class ResultSortTests(unittest.TestCase):
    def test_numbers_units_negative_zero_and_unknowns_last_in_both_directions(self):
        values = [('big', '1,234.50 ls'), ('ten', '10.00'), ('two', '2'), ('zero', '0'),
                  ('negative', '-3.5'), ('percent', '15%'), ('price', 'Cr 2,000'),
                  ('empty', ''), ('unknown', '情况未知'), ('missing', None), ('nan', 'NaN')]
        expected = ['negative', 'zero', 'two', 'ten', 'percent', 'big', 'price']
        unknown = ['empty', 'unknown', 'missing', 'nan']
        self.assertEqual(sorted_cells(values), expected + unknown)
        self.assertEqual(sorted_cells(values, True), expected[::-1] + unknown)
        self.assertEqual(sorted_cells([('a', '1e3'), ('b', '999')]), ['b', 'a'])

    def test_natural_names_stable_ties_and_lists_are_not_scalar_numbers(self):
        self.assertEqual(sorted_cells([('a', 'HIP 10'), ('b', 'hip 2'), ('c', 'HIP 2')]), ['b', 'c', 'a'])
        self.assertEqual(sorted_cells([('a', '2.0'), ('b', '2.00')], True), ['a', 'b'])
        self.assertEqual(cell_key('1,2')[0], 2)
        self.assertEqual(cell_key('15; 20')[0], 2)
        self.assertEqual(cell_key('²')[0], 2)
        self.assertEqual(cell_key('nan'), None)

    def test_dates_are_compared_in_utc_not_by_timezone_text(self):
        values = [('later', '2026-10-17T02:00:00Z'), ('earlier', '2026-10-17T09:00:00+08:00'),
                  ('midnight', '2026-10-17'), ('unknown', 'Unknown')]
        self.assertEqual(sorted_cells(values), ['midnight', 'earlier', 'later', 'unknown'])


@unittest.skipUnless(sys.platform == 'win32' or os.environ.get('DISPLAY'), 'Requires a GUI display')
class SortableTreeTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(str(args[1]))
        self.localizer = Localizer(self.root)
        self.tree = ttk.Treeview(self.root, columns=('name', 'distance'), show='headings')
        self.tree.heading('name', text='名称')
        self.tree.heading('distance', text='到达距离 ls')

    def tearDown(self):
        self.root.destroy()
        self.assertEqual(self.errors, [])

    def click(self, column):
        self.tree.tk.call(self.tree.heading(column, 'command'))

    def test_click_toggles_numeric_order_without_changing_ids_selection_or_values(self):
        rows = [('ten', ('Shop 10', '10.00')), ('two', ('Shop 2', '2.00')),
                ('unknown', ('Shop 3', '情况未知'))]
        for item, values in rows:
            self.tree.insert('', 'end', iid=item, values=values)
        self.tree.selection_set('ten')
        self.tree.focus('ten')
        self.click('distance')
        self.assertEqual(self.tree.get_children(), ('two', 'ten', 'unknown'))
        self.assertTrue(self.tree.heading('distance', 'text').endswith('▲'))
        self.click('distance')
        self.assertEqual(self.tree.get_children(), ('ten', 'two', 'unknown'))
        self.assertTrue(self.tree.heading('distance', 'text').endswith('▼'))
        self.assertEqual(self.tree.selection(), ('ten',))
        self.assertEqual(self.tree.focus(), 'ten')
        self.assertEqual(self.tree.item('ten', 'values'), rows[0][1])
        self.click('name')
        self.assertEqual(self.tree.get_children(), ('two', 'unknown', 'ten'))

    def test_active_sort_survives_language_switch_streaming_and_same_schema_rerender(self):
        self.tree.insert('', 'end', iid='ten', values=('A', '10'))
        self.tree.insert('', 'end', iid='unknown', values=('B', '情况未知'))
        self.click('distance')
        self.tree.insert('', 'end', iid='two', values=('C', '2'))
        self.root.update_idletasks()
        self.assertEqual(self.tree.get_children(), ('two', 'ten', 'unknown'))
        self.localizer.set_language('en')
        self.root.update_idletasks()
        self.assertTrue(self.tree.heading('distance', 'text').endswith('▲'))
        self.assertEqual(self.tree.get_children(), ('two', 'ten', 'unknown'))
        self.tree.delete(*self.tree.get_children())
        self.tree.set_columns(('name', 'distance'))
        self.tree.heading('name', text='名称')
        self.tree.heading('distance', text='到达距离 ls')
        self.tree.insert('', 'end', iid='20', values=('D', '20'))
        self.tree.insert('', 'end', iid='3', values=('E', '3'))
        self.root.update_idletasks()
        self.assertEqual(self.tree.get_children(), ('3', '20'))

    def test_dynamic_schema_reset_opt_out_custom_commands_and_pending_destroy(self):
        self.click('distance')
        self.tree.delete(*self.tree.get_children())
        self.tree.set_columns(('name',))
        self.tree.heading('name', text='名称')
        self.assertIsNone(self.tree._sort_column)
        self.tree.insert('', 'end', values=('A',))
        self.localizer.set_language('en')
        self.root.update_idletasks()
        calls = []
        self.tree.heading('name', command=lambda: calls.append(True))
        self.click('name')
        self.assertEqual(calls, [True])
        editor = ttk.Treeview(self.root, columns=('name',), sortable=False)
        editor.heading('name', text='名称')
        self.assertEqual(editor.heading('name', 'command'), '')
        self.tree.sort_by('name')
        self.tree.insert('', 'end', values=('B',))
        self.tree.destroy()
        self.root.update_idletasks()

    def test_hierarchical_sort_keeps_children_under_their_parent(self):
        self.tree.insert('', 'end', iid='parent', values=('Parent', '0'))
        self.tree.insert('parent', 'end', iid='ten', values=('A', '10'))
        self.tree.insert('parent', 'end', iid='two', values=('B', '2'))
        self.click('distance')
        self.assertEqual(self.tree.get_children(), ('parent',))
        self.assertEqual(self.tree.get_children('parent'), ('two', 'ten'))
