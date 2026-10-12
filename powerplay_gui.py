"""稀有商品目标查找器；后台仅使用普通Python数据，Tk更新交给App调度器。"""
import csv
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import powerplay_tool as tool
import rare_goods as sources


def open_window(app, data_age):
    win = tk.Toplevel(app.root)
    win.title("稀有商品目标查找器")
    win.geometry("1200x760")
    controls = ttk.Frame(win, padding=8)
    controls.pack(fill="x")
    reference = tk.StringVar(value="Ngurii")
    minimum, maximum = tk.StringVar(value="200"), tk.StringVar(value="220")
    pages = tk.StringVar(value="20")
    ttk.Label(controls, text="商品来源星系").pack(side="left")
    cb_ref = ttk.Combobox(controls, textvariable=reference, width=22,
                          state="readonly", values=sources.SOURCE_SYSTEMS)
    cb_ref.pack(side="left", padx=4)
    for label, variable in (("最小距离 ly", minimum), ("最大距离 ly", maximum),
                            ("每轮最多页数", pages)):
        ttk.Label(controls, text=label).pack(side="left", padx=(8, 0))
        ttk.Entry(controls, textvariable=variable, width=7).pack(side="left", padx=4)
    source_filter = ttk.Frame(win, padding=(8, 4))
    source_filter.pack(fill="x")
    ttk.Label(source_filter, text="筛选来源（星系／商品／站名）").pack(side="left")
    query = tk.StringVar()
    entry_filter = ttk.Entry(source_filter, textvariable=query, width=32)
    entry_filter.pack(side="left", padx=4)
    source_count = tk.StringVar()
    ttk.Label(source_filter, textvariable=source_count, foreground="gray").pack(side="left", padx=6)
    source_info = tk.StringVar()
    ttk.Label(win, textvariable=source_info, wraplength=1160).pack(fill="x", padx=8, pady=4)

    def filter_options(*args):
        candidates = sources.filter_sources(query.get())
        cb_ref.configure(values=candidates)
        source_count.set(f"{len(candidates)}/{len(sources.SOURCE_SYSTEMS)} 个星系；筛选后请从下拉选择")

    def describe_source(*args):
        source_info.set(sources.source_description(reference.get()))

    query.trace_add("write", filter_options)
    reference.trace_add("write", describe_source)
    filter_options()
    describe_source()
    options = ttk.Frame(win, padding=(8, 0))
    options.pack(fill="x")
    ttk.Label(options, text="Power（关联势力）").pack(side="left")
    power = tk.StringVar(value=tool.POWER_LABELS[tool.POWERS[0]])
    cb_power = ttk.Combobox(options, textvariable=power, state="readonly", width=25,
                            values=[tool.POWER_LABELS[p] for p in tool.POWERS])
    cb_power.pack(side="left", padx=4)
    all_powers = tk.BooleanVar(value=False)
    ttk.Checkbutton(options, text="全势力扫描（12个）", variable=all_powers,
                    command=lambda: cb_power.configure(state="disabled" if all_powers.get()
                                                        else "readonly")).pack(side="left", padx=8)
    ttk.Label(win, text="固定条件：大型停机坪、非地面站、排除航母和殖民船、Unoccupied。每个势力先查 ≤100 Ls，确认无结果后查 ≤1000 Ls。",
              wraplength=1160).pack(fill="x", padx=8, pady=(8, 0))
    ttk.Label(win, text=tool.STATE_NOTE + " 使用 Power，不要求由该势力控制。",
              foreground="gray", wraplength=1160).pack(fill="x", padx=8, pady=4)
    status = tk.StringVar(value="每个势力最多显示5站：先按距离 ly、再按到站距离 Ls 从近到远。点击势力汇总查看该组；双击明细复制星系名。")
    ttk.Label(win, textvariable=status, wraplength=1160).pack(fill="x", padx=8)
    progressbar = ttk.Progressbar(win, mode="indeterminate")
    progressbar.pack(fill="x", padx=8, pady=4)

    summary = ttk.Treeview(win, columns=("power", "stations", "systems", "limit", "status"),
                           show="headings", height=6, selectmode="browse")
    for key, width, title in (("power", 250, "关联势力"), ("stations", 90, "命中站点数"),
                              ("systems", 90, "命中星系数"), ("limit", 100, "到站上限 Ls"),
                              ("status", 230, "检索状态")):
        summary.heading(key, text=title)
        summary.column(key, width=width)
    summary.pack(fill="x", padx=8, pady=4)
    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=8, pady=4)
    columns = (("power", 170, "关联势力"), ("system", 150, "星系"),
               ("station", 180, "空间站"), ("ly", 70, "距离 ly"),
               ("ls", 90, "到站距离 Ls"), ("range", 110, "范围"), ("age", 100, "站点记录年龄"))
    tree = ttk.Treeview(frame, columns=[c for c, _, _ in columns], show="headings")
    for key, width, title in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, stretch=False)
    vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)
    state = {"groups": {}, "info": None, "visible": None}
    stop = threading.Event()

    def values(p, row):
        return (tool.POWER_LABELS[p], row.get("system_name", ""), row.get("name", ""),
                row.get("_powerplay_distance", ""), row.get("distance_to_arrival", ""),
                "标准 ≤100 Ls" if row["_powerplay_limit"] == 100 else "放宽 ≤1000 Ls",
                data_age(row.get("updated_at")))

    def show_details(p=None):
        state["visible"] = p
        tree.delete(*tree.get_children())
        for name, group in state["groups"].items():
            if p is None or name == p:
                for row in group["rows"]:
                    tree.insert("", "end", values=values(name, row))

    def selected(event=None):
        selection = summary.selection()
        if selection:
            show_details(selection[0])

    summary.bind("<<TreeviewSelect>>", selected)

    def copy_system(event=None):
        selection = tree.selection()
        if selection:
            win.clipboard_clear()
            win.clipboard_append(tree.item(selection[0], "values")[1])

    tree.bind("<Double-1>", copy_system)

    def export():
        if not state["groups"]:
            messagebox.showinfo("提示", "请先查询", parent=win)
            return
        path = filedialog.asksaveasfilename(parent=win, defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([title for _, _, title in columns])
            for name, group in state["groups"].items():
                for row in group["rows"]:
                    writer.writerow(values(name, row))
                if not group["rows"]:
                    writer.writerow([tool.POWER_LABELS[name]] + [""] * (len(columns) - 1))

    def notes():
        if state["info"]:
            messagebox.showinfo("检索说明", tool.STATE_NOTE + "\n\n" +
                                "\n".join(state["info"]["notes"]), parent=win)

    def finish():
        button.configure(state="normal")
        cb_ref.configure(state="readonly")
        entry_filter.configure(state="normal")
        progressbar.stop()

    def run():
        try:
            name, lo, hi, limit = reference.get().strip(), float(minimum.get()), float(maximum.get()), int(pages.get())
            chosen, scan_all = tool.normalize_power(power.get()), all_powers.get()
            if name not in sources.SOURCE_SYSTEMS or not 0 <= lo <= hi < float("inf") or hi <= 0 or limit < 1:
                raise ValueError()
        except ValueError:
            messagebox.showwarning("参数错误", "请从列表选择来源星系，并填写有效距离区间和正整数页数", parent=win)
            return
        stop.clear()
        state.update(groups={}, info=None, visible=None)
        summary.delete(*summary.get_children())
        tree.delete(*tree.get_children())
        button.configure(state="disabled")
        cb_ref.configure(state="disabled")
        entry_filter.configure(state="disabled")
        progressbar.start(80)
        status.set("查询中...")

        def work():
            try:
                info, groups = tool.search_powerplay(
                    name, chosen, scan_all, lo, hi, limit, stop=stop,
                    progress=lambda msg, detail=None: app._post(win, status.set, msg))

                def show():
                    state.update(groups=groups, info=info)
                    for p, group in groups.items():
                        summary.insert("", "end", iid=p, values=(tool.POWER_LABELS[p],
                            group["station_count"], group["system_count"], group["arrival_limit"], group["status"]))
                    show_details()
                    count = sum(g["station_count"] for g in groups.values())
                    shown = sum(len(g["rows"]) for g in groups.values())
                    text = "检索完成" if info["complete"] else "检索未完成（当前仅部分结果，不代表无命中）"
                    status.set(f"参考 {info['reference']}，{lo:g}–{hi:g} ly：{text}；{len(groups)} 个势力，命中 {count} 条、显示 {shown} 条（每势力最多5条，ly优先、Ls其次）；扫描候选 {info['scanned']} 条。")
                    finish()

                app._post(win, show)
            except Exception as exc:
                def failed(error=str(exc)):
                    status.set("查询失败；不能解释为无结果")
                    finish()
                    messagebox.showerror("查询失败", error, parent=win)
                app._post(win, failed)

        threading.Thread(target=work, daemon=True).start()

    button = ttk.Button(options, text="开始查询", command=run)
    button.pack(side="left", padx=6)
    ttk.Button(options, text="停止", command=stop.set).pack(side="left")
    footer = ttk.Frame(win, padding=8)
    footer.pack(fill="x")
    ttk.Button(footer, text="全部组明细", command=show_details).pack(side="left")
    ttk.Button(footer, text="复制星系名", command=copy_system).pack(side="left", padx=6)
    ttk.Button(footer, text="导出全部组 CSV", command=export).pack(side="left")
    ttk.Button(footer, text="检索说明", command=notes).pack(side="left", padx=6)

    app.bind_tool_state("rare_goods", win, dict(reference=reference, minimum=minimum,
                        maximum=maximum, pages=pages, query=query, power=power, all_powers=all_powers))
    if reference.get() not in sources.SOURCE_SYSTEMS:
        reference.set("Ngurii")
    cb_power.configure(state="disabled" if all_powers.get() else "readonly")

    def close():
        stop.set()
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close)
    return win
