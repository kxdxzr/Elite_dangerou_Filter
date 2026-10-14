"""Localized ttk adapters: display strings are separate from canonical model variables.

No tkinter monkey patches. Only this application's imported widgets are adapted.
"""
import tkinter as tk
from tkinter import ttk as base, messagebox as dialogs
from types import SimpleNamespace


def manager(widget):
    return getattr(widget._root(), '_localizer', None)


class TextMixin:
    def __init__(self, master=None, **kw):
        self._raw_text = kw.get('text')
        self._raw_values = tuple(kw.get('values', ()))
        self._raw_width = kw.get('width')
        self._model = kw.get('textvariable')
        self._display = None
        self._busy = False
        super().__init__(master, **kw)
        self._manager = manager(self)
        if self._manager:
            if isinstance(self._model, tk.StringVar):
                self._display = tk.StringVar(self)
                super().configure(textvariable=self._display)
                self._model_trace = self._model.trace_add('write', self._model_changed)
                self._display_trace = self._display.trace_add('write', self._display_changed)
            self._manager.register(self._render)
            self.bind('<Destroy>', self._cleanup, add='+')

    def _cleanup(self, event):
        if event.widget is self:
            self._manager.callbacks.discard(self._render)
            if self._display is not None:
                self._model.trace_remove('write', self._model_trace)
                self._display.trace_remove('write', self._display_trace)

    def _model_changed(self, *args):
        if not self._busy:
            self._render()

    def _display_changed(self, *args):
        if self._busy or not isinstance(self, base.Combobox):
            return
        value = self._display.get()
        inverse = {self._manager.tr(v): v for v in self._raw_values}
        self._busy = True
        try:
            self._model.set(inverse.get(value, value))
        finally:
            self._busy = False

    def _render(self):
        if not self.winfo_exists():
            return
        if self._raw_text is not None:
            super().configure(text=self._manager.tr(self._raw_text))
        if isinstance(self, base.Combobox):
            values = [self._manager.tr(v) for v in self._raw_values]
            super().configure(values=values)
            if self._raw_width is not None:
                changed = any(str(a) != str(b) for a, b in zip(self._raw_values, values))
                width = max(self._raw_width, min(42, max((len(str(v)) + 2 for v in values), default=0))) if changed else self._raw_width
                super().configure(width=width)
        if self._display is not None:
            self._busy = True
            try:
                self._display.set(self._manager.tr(self._model.get()))
            finally:
                self._busy = False

    def configure(self, cnf=None, **kw):
        if isinstance(cnf, dict):
            kw = dict(cnf, **kw)
            cnf = None
        if 'text' in kw:
            self._raw_text = kw['text']
            if getattr(self, '_manager', None):
                kw['text'] = self._manager.tr(kw['text'])
        if 'values' in kw:
            self._raw_values = tuple(kw['values'])
            if getattr(self, '_manager', None):
                kw['values'] = [self._manager.tr(v) for v in self._raw_values]
        result = super().configure(cnf, **kw)
        return result

    config = configure


class Combobox(TextMixin, base.Combobox):
    def set(self, value):
        if self._display is not None:
            self._model.set(value)
        else:
            super().set(value)

    def get(self):
        return self._model.get() if self._display is not None else super().get()


class Treeview(base.Treeview):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._manager = manager(self)
        self._headings, self._items = {}, {}
        if self._manager:
            self._manager.register(self._render)
            self.bind('<Destroy>', lambda e: self._manager.callbacks.discard(self._render)
                      if e.widget is self else None, add='+')

    def heading(self, column, option=None, **kw):
        if 'text' in kw:
            self._headings[column] = kw['text']
            if self._manager:
                kw['text'] = self._manager.tr(kw['text'])
        return super().heading(column, option, **kw)

    def insert(self, parent, index, iid=None, **kw):
        raw = kw.get('values', ())
        if self._manager:
            kw['values'] = self._display_values(raw)
        item = super().insert(parent, index, iid, **kw)
        self._items[item] = tuple(raw)
        return item

    def _display_values(self, values):
        identifiers = {'name', 'source', 'target', 'system', 'station', 'power',
                       'source_controller', 'target_controller', 'source_power', 'target_power'}
        columns = self.cget('columns')
        return [value if index < len(columns) and columns[index] in identifiers else self._manager.tr(value)
                for index, value in enumerate(values)]

    def delete(self, *items):
        for item in items:
            self._items.pop(item, None)
        super().delete(*items)

    def _render(self):
        for key, text in self._headings.items():
            super().heading(key, text=self._manager.tr(text))
        for key, values in self._items.items():
            if self.exists(key):
                super().item(key, values=self._display_values(values))


class Toplevel(tk.Toplevel):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self._raw_title = ''
        self._manager = manager(self)
        if self._manager:
            self._manager.register(self._render_title)
            self.bind('<Destroy>', lambda e: self._manager.callbacks.discard(self._render_title)
                      if e.widget is self else None, add='+')

    def _render_title(self):
        super().title(self._manager.tr(self._raw_title))

    def title(self, string=None):
        if string is not None:
            self._raw_title = string
            loc = getattr(self, '_manager', None)
            return super().title(loc.tr(string) if loc else string)
        return super().title()


ttk = SimpleNamespace(**{name: getattr(base, name) for name in dir(base) if not name.startswith('_')})
for _name in ('Label', 'Button', 'Checkbutton', 'Radiobutton', 'LabelFrame'):
    setattr(ttk, _name, type(_name, (TextMixin, getattr(base, _name)), {}))
ttk.Combobox, ttk.Treeview = Combobox, Treeview


def _dialog(name):
    def show(title=None, message=None, **kw):
        root = kw.get('parent') or tk._default_root
        loc = manager(root) if root is not None else None
        return getattr(dialogs, name)(loc.tr(title) if loc else title,
                                    loc.tr(message) if loc else message, **kw)
    return show


messagebox = SimpleNamespace(**{name: _dialog(name) for name in
    ('showinfo', 'showwarning', 'showerror', 'askyesno', 'askokcancel')})
