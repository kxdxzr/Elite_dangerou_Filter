import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from test_route_tool import build, FSDS, Server
import route_tool as tool


@unittest.skipUnless(sys.platform == 'win32' or os.environ.get('DISPLAY'), 'Requires a GUI display')
class RouteGuiTests(unittest.TestCase):
    def setUp(self):
        from test_colonisation_gui import ColonisationGuiTests
        ColonisationGuiTests.setUp(self)
        self.directory = tempfile.TemporaryDirectory()
        self.store = tool.Favorites(str(Path(self.directory.name) / 'ships.json'))
        self.factory = patch.object(tool, 'Favorites', return_value=self.store)
        self.factory.start()

    def tearDown(self):
        from test_colonisation_gui import ColonisationGuiTests
        ColonisationGuiTests.tearDown(self)
        self.factory.stop()
        self.directory.cleanup()

    def widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.widgets(child)

    def test_build_editor_waypoint_order_and_bilingual_results(self):
        win = self.app.route_window()
        editor = win.build_editor()
        editor.name_variable.set('Explorer')
        editor.json_text.insert('1.0', json.dumps(build()))
        editor.save_build()
        self.assertEqual(win.route_variables['selected'].get(), 'Explorer')
        buttons = {getattr(w, '_raw_text', ''): w for w in self.widgets(win) if isinstance(w, self.gui.ttk.Button)}
        for point in ('C', 'B'):
            win.route_variables['waypoint'].set(point)
            buttons['添加途经点'].invoke()
        win.waypoint_tree.selection_set('1')
        buttons['上移'].invoke()
        self.assertEqual(win.route_state['points'], ['B', 'C'])
        buttons['删除途经点'].invoke()
        self.assertEqual(win.route_state['points'], ['C'])
        buttons['删除途经点'].invoke()
        win.route_variables['source'].set('A')
        win.route_variables['destination'].set('B')
        original = tool.plan
        def offline(raw, points, options, stop, progress):
            return original(raw, points, options, stop, progress, http=Server(), fsds=FSDS)
        with patch.object(tool, 'plan', side_effect=offline):
            buttons['规划航线'].invoke()
            deadline = time.monotonic() + 4
            while win.route_state['busy'] and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.02)
        self.assertTrue(win.route_state['info']['complete'])
        self.assertEqual(len(win.result_tree.get_children()), 2)
        win.result_tree.selection_set('1')
        buttons['复制星系名'].invoke()
        self.assertEqual(win.clipboard_get(), 'B')
        self.app.set_language('en')
        self.assertEqual(win.title(), 'Neutron jump planner')
        self.assertIn('full tank', win.result_tree.item('0', 'values')[-1])
        path = str(Path(self.directory.name) / 'route.csv')
        with patch('route_gui.filedialog.asksaveasfilename', return_value=path):
            buttons['导出 CSV'].invoke()
        self.assertIn('Jump distance ly', Path(path).read_text(encoding='utf-8-sig'))

    def test_multileg_warning_can_cancel_before_network(self):
        self.store.put('Explorer', json.dumps(build()))
        win = self.app.route_window()
        win.route_variables['destination'].set('C')
        win.route_state['points'][:] = ['B']
        button = next(w for w in self.widgets(win) if getattr(w, '_raw_text', '') == '规划航线')
        with patch('route_gui.messagebox.askyesno', return_value=False) as warning, patch.object(tool, 'plan') as plan:
            button.invoke()
        warning.assert_called_once()
        plan.assert_not_called()
        self.assertFalse(win.route_state['busy'])
