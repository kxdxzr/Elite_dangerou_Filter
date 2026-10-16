"""Consistent copy actions for result tables; never clear valid clipboard on empty data."""
from localized_tk import messagebox


def copy_result(window, tree, column=None, getter=None):
    selected = tree.selection()
    if not selected:
        messagebox.showinfo('提示', '请先选择一条结果', parent=window)
        return False
    item = selected[0]
    value = getter(item) if getter is not None else tree.set(item, column)
    if value is None or not str(value).strip():
        messagebox.showinfo('提示', '所选结果没有可复制的信息', parent=window)
        return False
    window.clipboard_clear()
    window.clipboard_append(str(value))
    return True
