import csv
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import filter_engine as eng
import powerplay_gui
import rare_neutron
from test_powerplay_tool import station
from test_rare_neutron import anchor


@unittest.skipUnless(sys.platform == 'win32' or os.environ.get('DISPLAY'), 'Requires a GUI display')
class RareNeutronGuiTests(unittest.TestCase):
    def setUp(self):
        from test_colonisation_gui import ColonisationGuiTests
        ColonisationGuiTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        from test_colonisation_gui import ColonisationGuiTests
        ColonisationGuiTests.tearDown(self)
        self.temp.cleanup()

    def widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.widgets(child)

    def button(self, win, label):
        return next(w for w in self.widgets(win) if getattr(w, '_raw_text', '') == label)

    def wait_for_result(self, win):
        deadline = time.monotonic() + 4
        while win.rare_state['info'] is None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.02)
        self.assertIsNotNone(win.rare_state['info'])

    @patch.object(powerplay_gui.tool, 'ENABLE_NEUTRON_FILTER', True)
    def test_neutron_filter_controls_results_csv_and_session(self):
        win = powerplay_gui.open_window(self.app, self.gui.data_age)
        self.assertFalse(win.session_variables['neutron_only'].get())
        win.session_variables['neutron_only'].set(True)
        evaluator = rare_neutron.SavingsFilter(anchor_loader=lambda *a, **k: [anchor()])
        with patch.object(eng, 'resolve_ref', return_value=('Ngurii', (0, 0, 0), False)), \
                patch.object(eng, '_http_json', return_value=dict(count=2, results=[station('Good'),
                    station('Other', system_name='System Good', arrival=90)])), \
                patch.object(rare_neutron, 'SavingsFilter', return_value=evaluator) as factory:
            self.button(win, '开始查询').invoke()
            self.wait_for_result(win)
        factory.assert_called_once()
        self.assertTrue(win.rare_state['info']['complete'])
        rows = win.result_tree.get_children()
        self.assertEqual(len(rows), 1)
        self.assertEqual(win.result_tree.item(rows[0], 'values')[6:8], ('Near', 'Near'))
        self.assertIn('out_anchors', win.result_tree.cget('displaycolumns'))
        for key in ('outbound', 'inbound', 'ordinary_min', 'neutron_total', 'saved'):
            self.assertNotIn(key, win.result_tree.cget('columns'))
        self.assertTrue(self.app._state_dict()['tools']['rare_goods']['neutron_only'])
        self.app.set_language('en')
        self.assertEqual(win.result_tree.heading('out_anchors', 'text'), 'Outbound reference neutron star')
        path = Path(self.temp.name) / 'neutron.csv'
        with patch('powerplay_gui.filedialog.asksaveasfilename', return_value=str(path)):
            self.button(win, '导出全部组 CSV').invoke()
        with path.open(encoding='utf-8-sig', newline='') as file:
            exported = list(csv.reader(file))
        from test_export_metadata import assert_provenance
        assert_provenance(self, exported, len(exported[0]))
        from test_export_metadata import assert_english_csv
        assert_english_csv(self, exported)
        exported = exported[6:]
        self.assertEqual(len(exported), 2)
        self.assertEqual(len(exported[0]), 11)
        self.assertEqual(exported[1][10], 'Strict alignment')
        self.assertEqual(exported[1][8:10], ['0.00', '0.00'])
        for heading in ('Estimated outbound jumps', 'Estimated return jumps',
                        'Ordinary round-trip lower bound', 'Estimated neutron round-trip jumps',
                        'Estimated jumps saved'):
            self.assertNotIn(heading, exported[0])
        self.assertNotIn('route_anchor', win.result_tree.cget('columns'))
        self.assertNotIn('Aligned neutron star', exported[0])
        self.assertEqual(exported[1][6:8], ['Near', 'Near'])
        self.assertNotIn('out_landings', win.result_tree.cget('columns'))
        self.assertNotIn('in_landings', win.result_tree.cget('columns'))
        self.assertNotIn('neutron_evaluation_complete', exported[0])
        self.assertNotIn('assumed_jump_ranges', exported[0])
        win.rare_state['info']['complete'] = False
        with patch('powerplay_gui.messagebox.askyesno', return_value=False) as confirm, \
                patch('powerplay_gui.filedialog.asksaveasfilename') as choose:
            self.button(win, '导出全部组 CSV').invoke()
        confirm.assert_called_once()
        choose.assert_not_called()

    def test_filter_disabled_makes_no_route_requests_and_keeps_old_columns(self):
        win = powerplay_gui.open_window(self.app, self.gui.data_age)
        summary = next(w for w in self.widgets(win) if hasattr(w, 'heading') and
                       'systems' in w.cget('columns'))
        self.assertNotIn('stations', summary.cget('columns'))
        self.assertFalse(win.session_variables['neutron_only'].get())
        self.assertTrue(any(getattr(w, '_raw_text', '') == '仅显示顺路中子星辅助目标（实验性功能）'
                             for w in self.widgets(win)))
        with patch.object(eng, 'resolve_ref', return_value=('Ngurii', (0, 0, 0), False)), \
                patch.object(eng, '_http_json', return_value=dict(count=1, results=[station('Good')])), \
                patch.object(rare_neutron, 'SavingsFilter') as factory:
            self.button(win, '开始查询').invoke()
            self.wait_for_result(win)
        factory.assert_not_called()
        self.assertEqual(len(win.result_tree.cget('displaycolumns')), 6)

    def test_zero_model_savings_still_shows_reference_stars(self):
        win = powerplay_gui.open_window(self.app, self.gui.data_age)
        win.session_variables['neutron_only'].set(True)
        win.session_variables['minimum'].set('30')
        win.session_variables['maximum'].set('50')
        evaluate = rare_neutron.SavingsFilter(anchor_loader=lambda *a, **k: [anchor(x=20)])
        with patch.object(eng, 'resolve_ref', return_value=('Ngurii', (0, 0, 0), False)), \
                patch.object(eng, '_http_json', return_value=dict(count=1, results=[station('Good', distance=40)])), \
                patch.object(rare_neutron, 'SavingsFilter', return_value=evaluate):
            self.button(win, '开始查询').invoke()
            self.wait_for_result(win)
        self.assertTrue(win.rare_state['info']['complete'])
        rows = win.result_tree.get_children()
        self.assertEqual(len(rows), 1)
        self.assertEqual(win.result_tree.item(rows[0], 'values')[6:8], ('Near', 'Near'))
        info = next(iter(win.rare_state['groups'].values()))['rows'][0]['_neutron']
        self.assertEqual(info['saved'], 0)
        self.assertEqual(info['status'], 'candidate')
