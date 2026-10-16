import unittest
from unittest.mock import Mock, patch

from result_copy import copy_result


class ResultCopyTests(unittest.TestCase):
    def test_selected_named_column(self):
        window, tree = Mock(), Mock()
        tree.selection.return_value = ('row',)
        tree.set.return_value = 'Sol'
        self.assertTrue(copy_result(window, tree, 'system'))
        tree.set.assert_called_once_with('row', 'system')
        window.clipboard_append.assert_called_once_with('Sol')

    def test_missing_selection_or_value_keeps_clipboard(self):
        for selection, value in (((), 'Sol'), (('row',), ''), (('row',), None), (('row',), '  ')):
            window, tree = Mock(), Mock()
            tree.selection.return_value = selection
            tree.set.return_value = value
            with patch('result_copy.messagebox.showinfo') as prompt:
                self.assertFalse(copy_result(window, tree, 'name'))
            prompt.assert_called_once()
            window.clipboard_clear.assert_not_called()
            window.clipboard_append.assert_not_called()

    def test_raw_name_getter(self):
        window, tree = Mock(), Mock()
        tree.selection.return_value = ('row',)
        getter = Mock(return_value='Cat\'s Paw Sector AQ-Y d110')
        self.assertTrue(copy_result(window, tree, getter=getter))
        getter.assert_called_once_with('row')
        tree.set.assert_not_called()
