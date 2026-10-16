import csv
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == 'win32' or os.environ.get('DISPLAY'), 'Requires a GUI display')
class MainSystemGuiTests(unittest.TestCase):
    def test_visible_copy_actions_across_result_windows(self):
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        self.app.results = [dict(name='Station One', system_name='Sol')]
        item = self.app.tree.insert('', 'end', values=('Station One', 'Sol', '', ''))
        self.app.tree.selection_set(item)
        buttons = {getattr(w, '_raw_text', ''): w for w in descendants(self.root)
                   if isinstance(w, self.gui.ttk.Button)}
        buttons['复制名称'].invoke()
        self.assertEqual(self.root.clipboard_get(), 'Station One')
        buttons['复制星系名'].invoke()
        self.assertEqual(self.root.clipboard_get(), 'Sol')

        for open_tool, title, expected in (
            (self.app.carrier_parking_window, '航母车位查找', {'复制星系名': 'name'}),
            (self.app.midpoint_window, '两系中点 - 离中点最近的星系', {'复制星系名': 'name'}),
            (self.app.rare_goods_window, '稀有商品目标查找器', {'复制星系名': 'system', '复制空间站名': 'station'}),
            (self.app.pve_window, '海盗任务查找器', {'复制目标星系': 'target', '复制任务来源星系': 'source', '复制来源空间站': 'source_station'}),
        ):
            open_tool()
            win = next(w for w in self.root.winfo_children() if getattr(w, '_raw_title', '') == title)
            widgets = list(descendants(win))
            tree = next(w for w in widgets if isinstance(w, self.gui.ttk.Treeview)
                        and set(expected.values()).issubset(w['columns']))
            values = [f'Original {key}' for key in tree['columns']]
            item = tree.insert('', 'end', values=values)
            tree.selection_set(item)
            buttons = {getattr(w, '_raw_text', ''): w for w in widgets if isinstance(w, self.gui.ttk.Button)}
            for label, key in expected.items():
                buttons[label].invoke()
                self.assertEqual(win.clipboard_get(), f'Original {key}')
            win.destroy()

    def setUp(self):
        from test_colonisation_gui import ColonisationGuiTests
        ColonisationGuiTests.setUp(self)

    def tearDown(self):
        from test_colonisation_gui import ColonisationGuiTests
        ColonisationGuiTests.tearDown(self)

    def test_main_details_and_counts_survive_language_session_and_condition_loading(self):
        self.app.kind.set('systems')
        self.app._append_cond(dict(field='station_count', op='=', text=0))
        win = self.app.add_system_details()
        row = self.app.rows[-1]
        win.group_editors['body_groups'].add_group([
            dict(field='is_landable', op='=', value='true'),
            dict(field='gravity', op='<=', value='1')])
        win.group_editors['ring_groups'].add_group([dict(field='ring.type', op='=', value='Metallic')])
        row.variables['population_min'].set('100')
        row.variables['nearest_min'].set('3')
        row.variables['nearest_max'].set('10')
        before = self.app.collect()
        self.app.set_language('en')
        self.assertEqual(win.title(), 'Main-window system details')
        self.assertEqual(self.app.collect(), before)
        state = self.app._state_dict()
        self.app._apply_state(state)
        self.assertEqual(self.app.collect(), before)
        self.app._apply_state(dict(kind='systems', conditions=before))
        self.assertEqual(self.app.collect(), before)
        self.assertIn('station_count', self.gui.parse_field_label(self.app.rows[0].field.get()))
        self.app.kind.set('stations')
        self.app.refresh_fields()
        with self.assertRaises(ValueError):
            self.app.rows[-1].to_cond()

    def test_invalid_group_draft_is_preserved(self):
        self.app.kind.set('systems')
        win = self.app.add_system_details()
        win.group_editors['body_groups'].add_group()
        row = self.app.rows[-1]
        row.variables['nearest_min'].set('unfinished')
        state = self.app._state_dict()
        self.assertEqual(state['rows'][0]['settings']['nearest_min'], 'unfinished')
        self.app._apply_state(state)
        self.assertEqual(self.app.rows[0].editor_state(), state['rows'][0])
        with self.assertRaises(ValueError):
            self.app.collect()

    def test_csv_preserves_full_detail_evidence(self):
        row = dict(name='A', body_data='x' * 10000,
                   _system_details=dict(counts={'station_count': 0}, neighbours=[{'name': 'Nearest'}]))
        self.app.results = [row]
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'results.csv')
            with patch.object(self.gui.filedialog, 'asksaveasfilename', return_value=path):
                self.app.export()
            with open(path, encoding='utf-8-sig', newline='') as file:
                exported = list(csv.DictReader(file))
        self.assertEqual(json.loads(exported[0]['raw_json']), row)

    def test_main_search_renders_prepared_evidence(self):
        import system_filters
        self.app.kind.set('systems')
        self.app._append_cond(dict(field='population', op='>', text=0))
        self.app._append_cond(dict(field='station_count', op='=', text=0))
        self.app._append_cond(dict(type='system_details', body_groups=[[
            dict(field='is_landable', op='=', value='true')]]))
        candidate = dict(name='Populated', population=100, stations=[])
        body = dict(name='Populated 1', type='Planet', is_landable=True)
        with patch.object(self.gui.eng, '_http_json', return_value={'count': 1, 'results': [candidate]}), \
                patch.object(system_filters.bodies, 'load_bodies', return_value={'populated': [body]}):
            self.app.run()
            deadline = time.monotonic() + 5
            while str(self.app.btn_run.cget('state')) != 'normal' and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.02)
        self.assertEqual(str(self.app.btn_run.cget('state')), 'normal')
        self.assertEqual(len(self.app.results), 1)
        items = self.app.tree.get_children()
        self.assertEqual(len(items), 1)
        rendered = self.app.tree.item(items[0], 'values')
        self.assertIn('station_count=0', rendered[2])
        self.assertIn('Populated 1', rendered[2])


if __name__ == '__main__':
    unittest.main()
