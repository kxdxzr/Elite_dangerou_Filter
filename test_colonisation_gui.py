import gc
import os
import sys
import time
import unittest
from unittest.mock import patch


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
        self.app._tool_states['colonisation'] = {'populated_radius': '12'}
        win = self.app.colonisation_window()
        criteria = win.criteria()
        self.assertEqual(criteria.populated_radius, 12)
        self.assertIsNone(criteria.populated_min_distance)
        self.assertEqual(criteria.reference, '')

    def test_worker_search_result_copy_and_language_switch(self):
        import colonisation_tool as tool
        win = self.app.colonisation_window()
        row = dict(name='Candidate', estimated_mapping_value=10,
                   _neighbour='', _neighbour_population=None, _neighbour_distance=None,
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
        win.result_tree.selection_set('0')
        next(b for b in buttons if b._raw_text == '复制星系名').invoke()
        self.assertEqual(win.clipboard_get(), 'Candidate')
        self.app.set_language('en')
        self.assertEqual(win.result_tree.item('0', 'values')[0], 'Candidate')


if __name__ == '__main__':
    unittest.main()
