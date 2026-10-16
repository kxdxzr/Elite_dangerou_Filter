"""Local ship favourites and Spansh online, ordered multi-leg exact routing."""
import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, simpledialog

from localized_tk import ttk, messagebox, Toplevel
from result_copy import copy_result
from search_progress import SearchProgress
import route_ship
import route_tool as tool


def open_window(app):
    win = Toplevel(app.root)
    win.title('中子星跳跃规划器')
    win.geometry('1400x850')
    store = tool.Favorites()
    tr = app.localizer.tr
    selected = tk.StringVar(win)
    source, destination, waypoint = (tk.StringVar(win, value=v) for v in ('Sol', '', ''))
    cargo, reserve = tk.StringVar(win, value='0'), tk.StringVar(win, value='0')
    algorithm, injection = tk.StringVar(win, value='优先少跳'), tk.StringVar(win, value='不使用')
    algorithms = {'优先少跳': 'optimistic', '优先计算速度': 'pessimistic'}
    injections = {'不使用': 'never', '仅在需要时': 'required', '始终使用': 'always'}
    flags = {key: tk.BooleanVar(win, value=value) for key, value in (
        ('supercharge', True), ('already_supercharged', False), ('exclude_secondary', False), ('refuel_every_scoopable', False))}
    stop, events = threading.Event(), queue.Queue()
    state = {'busy': False, 'info': None, 'points': []}

    ships = ttk.LabelFrame(win, text='舰船配置收藏', padding=6)
    ships.pack(fill='x', padx=8, pady=6)
    chooser = ttk.Combobox(ships, textvariable=selected, state='readonly', width=35)
    chooser.pack(side='left', padx=4)

    def error(exc):
        messagebox.showerror('操作失败', str(exc), parent=win)

    def reload_favorites(name=None):
        try:
            names = sorted(store.load(), key=str.casefold)
            chooser.configure(values=names)
            selected.set(name if name in names else names[0] if names else '')
        except (OSError, ValueError, TypeError) as exc:
            chooser.configure(values=[])
            selected.set('')
            error(exc)

    def editor(existing=None):
        dialog = Toplevel(win)
        dialog.title('编辑舰船配置')
        dialog.geometry('850x570')
        name = tk.StringVar(dialog, value=existing or '')
        header = ttk.Frame(dialog, padding=6)
        header.pack(fill='x')
        ttk.Label(header, text='收藏名称').pack(side='left')
        ttk.Entry(header, textvariable=name, width=36).pack(side='left', padx=6)
        ttk.Label(dialog, text='粘贴 Coriolis 配船 JSON 或 EDSY SLEF；不接受网页链接。', wraplength=800).pack(fill='x', padx=8)
        text = tk.Text(dialog, wrap='none', undo=True)
        text.pack(fill='both', expand=True, padx=8, pady=6)
        if existing:
            try:
                text.insert('1.0', store.load()[existing])
            except (OSError, ValueError, KeyError) as exc:
                error(exc)
                dialog.destroy()
                return

        def import_json():
            path = filedialog.askopenfilename(parent=dialog, filetypes=[('JSON', '*.json'), ('All', '*.*')])
            if path:
                try:
                    with open(path, encoding='utf-8-sig') as file:
                        raw = file.read(route_ship.MAX_BUILD_BYTES + 1)
                    route_ship.decode_build(raw)
                    text.delete('1.0', 'end')
                    text.insert('1.0', raw)
                except (OSError, ValueError) as exc:
                    error(exc)

        def save():
            try:
                raw = text.get('1.0', 'end-1c')
                route_ship.decode_build(raw)
                target = name.get().strip()
                names = store.load()
                duplicate = next((n for n in names if n.casefold() == target.casefold()), None)
                if duplicate is not None and not messagebox.askyesno('确认', '覆盖同名舰船配置？', parent=dialog):
                    return
                # Save-as is deliberate: renaming has its own explicit action.
                store.put(target, raw, replace=duplicate is not None)
                reload_favorites(target)
                dialog.destroy()
            except (OSError, ValueError, TypeError) as exc:
                error(exc)

        buttons = ttk.Frame(dialog, padding=6)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='导入 JSON 文件', command=import_json).pack(side='left')
        ttk.Button(buttons, text='保存舰船配置', command=save).pack(side='right')
        dialog.json_text, dialog.name_variable, dialog.save_build = text, name, save
        return dialog

    def rename():
        if not selected.get():
            return
        name = simpledialog.askstring(tr('重命名'), tr('收藏名称'), initialvalue=selected.get(), parent=win)
        if name is not None:
            try:
                store.rename(selected.get(), name)
                reload_favorites(name.strip())
            except (OSError, ValueError) as exc:
                error(exc)

    def delete():
        if selected.get() and messagebox.askyesno('确认', '删除所选舰船配置？', parent=win):
            try:
                store.delete(selected.get())
                reload_favorites()
            except (OSError, ValueError) as exc:
                error(exc)

    for label, command in (('新增舰船配置', editor), ('编辑舰船配置', lambda: editor(selected.get()) if selected.get() else editor()),
                           ('重命名', rename), ('删除收藏', delete)):
        ttk.Button(ships, text=label, command=command).pack(side='left', padx=4)
    ttk.Label(win, text='收藏仅保存在本地；开始规划后，舰船配置和航点将发送至 Spansh。首次解析需要联网获取 FSD 数据。',
              wraplength=1360, foreground='gray').pack(fill='x', padx=8)

    endpoints = ttk.Frame(win, padding=8)
    endpoints.pack(fill='x')
    from filter_gui import attach_system_suggest
    for label, variable in (('起点星系', source), ('终点星系', destination)):
        ttk.Label(endpoints, text=label).pack(side='left')
        box = ttk.Combobox(endpoints, textvariable=variable, width=32)
        box.pack(side='left', padx=6)
        attach_system_suggest(box, variable)

    points_frame = ttk.LabelFrame(win, text='有序途经点', padding=6)
    points_frame.pack(fill='x', padx=8)
    box = ttk.Combobox(points_frame, textvariable=waypoint, width=35)
    box.grid(row=0, column=0, sticky='w')
    attach_system_suggest(box, waypoint)
    points = ttk.Treeview(points_frame, columns=('order', 'name'), show='headings', height=3, selectmode='browse')
    points.heading('order', text='序号')
    points.heading('name', text='星系')
    points.column('order', width=55, stretch=False)
    points.column('name', width=380)
    points.grid(row=1, column=0, columnspan=5, sticky='ew', pady=4)
    points_frame.columnconfigure(0, weight=1)

    def render_points(select=None):
        points.delete(*points.get_children())
        for index, name in enumerate(state['points']):
            points.insert('', 'end', iid=str(index), values=(index + 1, name))
        if select is not None and 0 <= select < len(state['points']):
            points.selection_set(str(select))

    def add_point():
        name = waypoint.get().strip()
        if name:
            state['points'].append(name)
            render_points(len(state['points']) - 1)
            waypoint.set('')

    def edit_point(move=None):
        picked = points.selection()
        if not picked:
            return
        index = int(picked[0])
        if move is None:
            state['points'].pop(index)
            render_points(min(index, len(state['points']) - 1))
        elif 0 <= index + move < len(state['points']):
            state['points'][index], state['points'][index + move] = state['points'][index + move], state['points'][index]
            render_points(index + move)

    for col, (label, action) in enumerate((('添加途经点', add_point), ('上移', lambda: edit_point(-1)),
                                         ('下移', lambda: edit_point(1)), ('删除途经点', edit_point)), 1):
        ttk.Button(points_frame, text=label, command=action).grid(row=0, column=col, padx=3)

    settings = ttk.Frame(win, padding=8)
    settings.pack(fill='x')
    for label, variable in (('货物 t', cargo), ('储备燃油 t', reserve)):
        ttk.Label(settings, text=label).pack(side='left')
        ttk.Entry(settings, textvariable=variable, width=8).pack(side='left', padx=5)
    ttk.Label(settings, text='注入策略').pack(side='left')
    ttk.Combobox(settings, textvariable=injection, values=list(injections), state='readonly', width=10).pack(side='left', padx=5)
    ttk.Label(settings, text='规划算法').pack(side='left')
    ttk.Combobox(settings, textvariable=algorithm, values=list(algorithms), state='readonly', width=14).pack(side='left', padx=5)
    flags_frame = ttk.Frame(win, padding=(8, 0))
    flags_frame.pack(fill='x')
    for key, label in (('supercharge', '使用中子增压'), ('already_supercharged', '第一段已增压'),
                       ('exclude_secondary', '排除副星'), ('refuel_every_scoopable', '遇可补油恒星即补油')):
        ttk.Checkbutton(flags_frame, text=label, variable=flags[key]).pack(side='left', padx=4)
    ttk.Label(win, text=tool.FULL_TANK_NOTE, foreground='#a05a00', wraplength=1360).pack(fill='x', padx=8, pady=4)

    status = tk.StringVar(win, value='选择收藏舰船，填写起终点；途经点按列表顺序规划。')
    ttk.Label(win, textvariable=status, wraplength=1360).pack(fill='x', padx=8)
    bar = ttk.Progressbar(win, mode='determinate')
    bar.pack(fill='x', padx=8)
    progress_text = tk.StringVar(win)
    ttk.Label(win, textvariable=progress_text).pack(fill='x', padx=8)
    tracker = SearchProgress(bar, progress_text, app.localizer)
    actions = ttk.Frame(win, padding=8)
    actions.pack(fill='x')
    table = ttk.Frame(win)
    table.pack(fill='both', expand=True, padx=8, pady=4)
    tree = ttk.Treeview(table, columns=[key for key, _ in tool.COLUMNS], show='headings')
    for key, title in tool.COLUMNS:
        tree.heading(key, text=title)
        tree.column(key, width=300 if key in ('name', 'assumption') else 150, stretch=False)
    yscroll = ttk.Scrollbar(table, orient='vertical', command=tree.yview)
    xscroll = ttk.Scrollbar(table, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    tree.grid(row=0, column=0, sticky='nsew')
    yscroll.grid(row=0, column=1, sticky='ns')
    xscroll.grid(row=1, column=0, sticky='ew')
    table.rowconfigure(0, weight=1)
    table.columnconfigure(0, weight=1)

    def render_results():
        if not win.winfo_exists():
            return
        selection = tree.selection()
        tree.delete(*tree.get_children())
        if state['info']:
            for index, values in enumerate(tool.display_rows(state['info'], app.localizer.tr)):
                tree.insert('', 'end', iid=str(index), values=values)
            for item in selection:
                if tree.exists(item):
                    tree.selection_add(item)
            info = state['info']
            en = app.localizer.language == 'en'
            status.set((f"Completed legs: {len(info['segments']):,}/{info['planned_segments']:,}; " if en else
                        f"已完成分段：{len(info['segments']):,}/{info['planned_segments']:,}；") + app.localizer.tr(info['reason']))
    app.localizer.register(render_results)

    def run():
        if state['busy']:
            return
        try:
            raw = store.load().get(selected.get())
            if raw is None:
                raise ValueError(tr('请先选择舰船配置'))
            route_points = [source.get().strip(), *state['points'], destination.get().strip()]
            if any(not p for p in route_points):
                raise ValueError(tr('请填写起点和终点星系'))
            options = tool.Options(cargo=cargo.get(), reserve=reserve.get(), injection=injections[injection.get()],
                                   algorithm=algorithms[algorithm.get()], **{k: v.get() for k, v in flags.items()}).validate()
        except (OSError, ValueError) as exc:
            error(exc)
            return
        if len(route_points) > 2 and not messagebox.askyesno('多段航线确认',
                '每一段都按起点满油独立计算，不继承上一段剩余燃油或增压状态。途经点不保证能补油，请确认下一段出发前可以补满。继续？', parent=win):
            return
        stop.clear()
        state.update(busy=True, info=None)
        tree.delete(*tree.get_children())
        start_button.configure(state='disabled')
        stop_button.configure(state='normal')
        tracker.update()
        status.set('正在提交联网航线规划…')
        def worker():
            try:
                result = tool.plan(raw, route_points, options, stop,
                                   lambda text, detail: events.put(('progress', (text, detail))))
            except Exception as exc:
                result = dict(complete=False, rows=[], segments=[], planned_segments=len(route_points) - 1,
                              reason=str(exc), failed_segment=None)
            events.put(('done', result))
        threading.Thread(target=worker, daemon=True).start()

    def export():
        info = state['info']
        if not info or not info['rows']:
            messagebox.showinfo('提示', '暂无结果', parent=win)
            return
        if not info['complete'] and not messagebox.askyesno('确认', '航线未完成，仅导出已完成分段？', parent=win):
            return
        path = filedialog.asksaveasfilename(parent=win, defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if path:
            try:
                tool.export_csv(path, info, app.localizer.tr)
            except OSError as exc:
                error(exc)

    start_button = ttk.Button(actions, text='规划航线', command=run)
    start_button.pack(side='left')
    stop_button = ttk.Button(actions, text='停止', command=stop.set, state='disabled')
    stop_button.pack(side='left', padx=5)
    ttk.Button(actions, text='复制星系名', command=lambda: copy_result(win, tree, 'name')).pack(side='left', padx=5)
    ttk.Button(actions, text='导出 CSV', command=export).pack(side='left', padx=5)
    poll_id = None
    def poll():
        nonlocal poll_id
        if not win.winfo_exists():
            return
        try:
            while True:
                event, result = events.get_nowait()
                if event == 'progress':
                    text, detail = result
                    status.set(text)
                    tracker.update(text, detail)
                else:
                    state.update(busy=False, info=result)
                    start_button.configure(state='normal')
                    stop_button.configure(state='disabled')
                    tracker.finish(result['complete'])
                    render_results()
        except queue.Empty:
            pass
        poll_id = win.after(100, poll)

    def dispose(event):
        if event.widget is win:
            stop.set()
            app.localizer.callbacks.discard(render_results)
            if poll_id is not None:
                win.after_cancel(poll_id)
    win.bind('<Destroy>', dispose, add='+')
    poll_id = win.after(100, poll)
    win.route_state, win.result_tree, win.waypoint_tree = state, tree, points
    win.route_variables = dict(source=source, destination=destination, waypoint=waypoint, selected=selected)
    win.build_editor, win.reload_favorites = editor, reload_favorites
    reload_favorites()
    return win
