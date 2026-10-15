import gc
import os
import sys
import time
import unittest
from unittest.mock import patch, mock_open


@unittest.skipUnless(sys.platform == 'win32' or os.environ.get('DISPLAY'), 'Requires a GUI display')
class ColonisationGuiTests(unittest.TestCase):
    def setUp(self):
        import filter_gui as gui
        self.gui = gui
        self.patches = [patch.object(gui.fo, 'prefetch_common', lambda *a: None),
                        patch.object(gui.App, 'restore_session', lambda *a: None)]
        for item in self.patches:
            item.start()
        self.root = gui.tk.Tk()
        self.root.withdraw()
        self.app = gui.App(self.root)
        self.app._closing = True
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(str(args[1]))

    def tearDown(self):
        for callback in self.root.tk.splitlist(self.root.tk.call('after', 'info')):
            # Each widget owns its Tcl commands; cancel scripts without deleting
            # a child widget's command through the root's command registry.
            self.root.tk.call('after', 'cancel', callback)
        self.root.destroy()
        gc.collect()
        for item in reversed(self.patches):
            item.stop()
        self.assertEqual(self.errors, [])

    def test_groups_language_and_session_restore_preserve_raw_conditions(self):
        win = self.app.colonisation_window()
        body = win.group_editors['body_groups']
        body.add_group([{'field': 'subtype', 'op': 'in', 'value': 'Water world|Earth-like world'},
                        {'field': '_is_binary', 'op': '=', 'value': 'true'}])
        ring = win.group_editors['ring_groups']
        ring.add_group([{'field': 'ring.type', 'op': '=', 'value': 'Metallic'}])
        win.session_variables['body_mode'].set('OR')
        win.session_variables['reference'].set('Sol')
        win.session_variables['radius'].set('50')
        win.session_variables['populated_min_distance'].set('3')
        win.session_variables['populated_radius'].set('10')
        before = win.criteria()
        self.app.set_language('en')
        self.root.update()
        self.assertEqual(win.title(), 'Colonisation candidate finder')
        self.assertEqual(before.body_groups, win.criteria().body_groups)
        saved = self.app._state_dict()['tools']['colonisation']
        self.app._tool_states['colonisation'] = saved
        win.destroy()
        restored = self.app.colonisation_window()
        after = restored.criteria()
        self.assertEqual(before.body_groups, after.body_groups)
        self.assertEqual(before.ring_groups, after.ring_groups)
        self.assertEqual(after.body_mode, 'OR')
        self.assertEqual((after.reference, after.radius), ('Sol', 50))
        self.assertEqual((after.populated_min_distance, after.populated_radius), (3, 10))
        self.app.set_language('zh')
        self.assertEqual(restored.title(), '殖民候选星系查找器')

    def test_older_maximum_only_session_restores(self):
        self.app._tool_states['colonisation'] = {'populated_radius': '12', 'max_pages': '1'}
        win = self.app.colonisation_window()
        criteria = win.criteria()
        self.assertEqual(criteria.populated_radius, 12)
        self.assertIsNone(criteria.populated_min_distance)
        self.assertEqual(criteria.reference, '')
        self.assertNotIn('max_pages', win.session_variables)
        self.assertIsNone(criteria.max_pages)

    def test_worker_search_result_copy_and_language_switch(self):
        import colonisation_tool as tool
        win = self.app.colonisation_window()
        row = dict(name='Candidate', estimated_mapping_value=1234567.0, distance=1234.56789,
                   _top_scan_planets=[dict(name='Candidate 1', subtype='Water world', estimated_scan_value=55000)],
                   _top_scan_complete=True,
                   _neighbour='Neighbour', _neighbour_population=1234567.0, _neighbour_distance=4.41789,
                   _neighbour_pad='L',
                   _body_matches='', _ring_matches='', _relations='')
        info = dict(scanned=1, unknown=0, complete=True, value_field='estimated_mapping_value',
                    reason='All supplied candidate pages fetched.')
        from tkinter import ttk

        def children(widget):
            for child in widget.winfo_children():
                yield child
                yield from children(child)

        buttons = [w for w in children(win) if isinstance(w, ttk.Button)]
        search = next(b for b in buttons if b._raw_text == '查询')
        with patch.object(tool, 'search', return_value=(info, [row])) as query:
            search.invoke()
            deadline = time.monotonic() + 5
            while not win.search_state['info'] and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.02)
        query.assert_called_once()
        self.assertFalse(win.search_state['busy'])
        self.assertEqual(len(win.result_tree.get_children()), 1)
        self.assertEqual(win.result_tree.item('0', 'values')[1:6],
                         ('1,234,567', '1,234.57', 'Neighbour', '4.42', 'L'))
        self.assertNotIn('population', win.result_tree['columns'])
        self.assertEqual(win.result_tree.heading('neighbour', 'text'), '最近有人星系')
        self.assertIn('Candidate 1 | Water world | 55,000 Cr', win.result_tree.item('0', 'values'))
        win.result_tree.selection_set('0')
        next(b for b in buttons if b._raw_text == '复制星系名').invoke()
        self.assertEqual(win.clipboard_get(), 'Candidate')
        next(b for b in buttons if b._raw_text == '复制最近有人星系').invoke()
        self.assertEqual(win.clipboard_get(), 'Neighbour')
        self.app.set_language('en')
        self.assertEqual(win.result_tree.item('0', 'values')[0], 'Candidate')
        self.assertEqual(win.result_tree.heading('scan1', 'text'), 'Scan value #1 (planet / type / Cr)')
        self.assertEqual(win.result_tree.heading('neighbour', 'text'), 'Nearest populated system')
        self.assertIn('No more planets', win.result_tree.item('0', 'values'))
        output = mock_open()
        with patch('colonisation_gui.filedialog.asksaveasfilename', return_value='scan-values.csv'), \
                patch('builtins.open', output):
            next(b for b in buttons if b._raw_text == '导出CSV').invoke()
        written = ''.join(c.args[0] for c in output().write.call_args_list)
        self.assertIn('scan1,scan2,scan3,scan_status', written)
        self.assertNotIn(',population,', written)
        self.assertIn('near_distance,neighbour_pad', written)
        self.assertIn('55,000 Cr', written)
        self.assertIn('"1,234.57"', written)
        self.assertIn('"1,234,567"', written)
        self.assertEqual(row['_neighbour_distance'], 4.41789)


if __name__ == '__main__':
    unittest.main()
