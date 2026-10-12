"""Elite Dangerous GUI 筛选器: 可不停添加条件, 允许重复, 支持多参考点距离内外过滤.
第三格为下拉+联想: 选项少直接下拉选, 选项多边打边提示, 星系名有联想。
关闭时自动记住条件, 下次打开恢复。
"""
import csv
import json
import os
import queue
import re
import sys
import threading
import tkinter as tk
from datetime import datetime, timezone
from tkinter import filedialog, messagebox, ttk

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from spansh_filter import (STATION_FIELDS, SYSTEM_FIELDS, STATION_FIELDS_CN,
                             SYSTEM_FIELDS_CN, field_label, parse_field_label)
import filter_engine as eng
import field_options as fo
import session_store
from runtime_paths import data_file

OP_LABELS = ["属于其一", "不属于", "等于", "不等于", "包含",
             "<", "<=", ">", ">=", "区间(内)", "范围外", "是", "否"]
OP_MAP = {"属于其一": "in", "不属于": "not in", "等于": "=",
          "不等于": "!=", "包含": "contains", "<": "<", "<=": "<=",
          ">": ">", ">=": ">=", "区间(内)": "between", "范围外": "outside",
          "是": "true", "否": "false"}
SESSION_FILE = data_file("last_session.json")
MULTI_OPS = {"属于其一", "不属于"}
SINGLE_CHOICE_OPS = {"属于其一", "不属于", "等于", "不等于", "包含"}
NUMERIC_OPS = {"<", "<=", ">", ">=", "区间(内)", "范围外"}
# 新鲜度快捷值 (时间字段区间条件用; 相对标记由引擎解析成绝对时间)
FRESH_QUICK = ["近1天", "近7天", "近30天", "近90天"]
FRESH_FIELDS = {"last_updated_at", "market_last_updated_at",
                "shipyard_last_updated_at", "outfitting_last_updated_at"}
# 船/模块名自动纠错字段
AUTOCORRECT_FIELDS = {"ships", "modules"}
# 船/模块行集成新鲜度 (卖X且数据N天内新, 只本地复核)
FRESH_OPTS = ["不限", "近1天", "近7天", "近30天", "近90天"]
FRESH_DAYS = {"近1天": 1, "近7天": 7, "近30天": 30, "近90天": 90}
FRESH_FIELDS_ROWS = {"ships", "modules"}
_FRESH_OPT_RE = re.compile(r"^近(\d+)天$")


def ui_dispatcher(widget):
    """主线程初始化；后台线程只入队，所有 Tk 调用由主线程执行。"""
    root = widget._root()
    if hasattr(root, "_ui_post"):
        return root._ui_post
    pending = queue.Queue()

    def post(owner, callback, *args):
        pending.put((owner, callback, args))

    def drain():
        for _ in range(100):
            try:
                owner, callback, args = pending.get_nowait()
            except queue.Empty:
                break
            if owner.winfo_exists():
                try:
                    callback(*args)
                except Exception:
                    root.report_callback_exception(*sys.exc_info())
        root.after(30, drain)

    root._ui_post = post
    root.after(30, drain)
    return post


def fresh_opt_days(label):
    """新鲜度选项 -> 天数 (不限/非法 -> None)。"""
    days = FRESH_DAYS.get((label or "").strip())
    if days is not None:
        return days
    m = _FRESH_OPT_RE.match((label or "").strip())
    return int(m.group(1)) if m else None


def data_age(ts):
    """更新时间 -> '3天前'/'5小时前'/'刚刚'/'未知'。"""
    if not ts:
        return "未知"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return "未知"
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 0:
        return "未知"
    if secs < 60:
        return "刚刚"
    if secs < 3600:
        return f"{int(secs // 60)}分钟前"
    if secs < 86400:
        return f"{int(secs // 3600)}小时前"
    return f"{int(secs // 86400)}天前"


def open_multi_select(parent, title, options, current):
    """多选弹窗, 返回选中的 list[str] 或 None(取消)."""
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("340x420")
    win.transient(parent)
    cur = [c.strip().lower() for c in current if c.strip()]
    ttk.Label(win, text="输入过滤, 勾选后确定 (多选用 ; 连接)").pack(fill="x", padx=6, pady=4)
    q = tk.StringVar()
    ttk.Entry(win, textvariable=q).pack(fill="x", padx=6)
    lb = tk.Listbox(win, selectmode="multiple", height=18)
    lb.pack(fill="both", expand=True, padx=6, pady=4)
    shown = list(options)

    def refill():
        s = q.get().strip().lower()
        shown.clear()
        shown.extend([o for o in options if not s or s in o.lower()])
        lb.delete(0, "end")
        for o in shown:
            lb.insert("end", o)
            if o.lower() in cur:
                lb.selection_set("end")

    def on_q(*a):
        refill()

    q.trace_add("write", on_q)
    refill()
    picked = {"vals": None}

    def ok():
        picked["vals"] = [shown[i] for i in lb.curselection()]
        win.destroy()

    ttk.Button(win, text="确定", command=ok).pack(pady=4)
    win.bind("<Return>", lambda e: ok())
    parent.wait_window(win)
    return picked["vals"]


class SuggestPopup:
    """单例: 在输入框下方弹出候选列表 (Inara式联想)。
    焦点始终留在输入框, 上下键移动高亮, 回车/Tab/点击选中, Esc关闭。"""
    _inst = None

    @classmethod
    def inst(cls):
        if cls._inst is None:
            cls._inst = SuggestPopup()
        return cls._inst

    def __init__(self):
        self.win = None
        self.lb = None
        self.on_pick = None
        self.anchor = None

    def visible_for(self, widget):
        return self.win is not None and self.anchor is widget

    def show(self, widget, items, on_pick):
        self.hide()
        items = [i for i in items if i][:8]
        if not items or not widget.winfo_exists():
            return
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
        except tk.TclError:
            return
        self.on_pick = on_pick
        self.anchor = widget
        self.win = tk.Toplevel(widget)
        self.win.wm_overrideredirect(True)
        self.win.wm_geometry(f"+{x}+{y}")
        self.win.lift()
        self.lb = tk.Listbox(self.win, height=len(items),
                             width=max(16, min(44, max(len(s) for s in items) + 2)))
        self.lb.pack()
        for it in items:
            self.lb.insert("end", it)
        self.lb.selection_set(0)
        self.lb.bind("<ButtonRelease-1>", lambda e: self._pick())
        # 点击弹窗外部则关闭 (由输入框失焦处理, 这里兜底)
        self.win.bind("<FocusOut>", lambda e: self.hide())

    def move(self, delta):
        if not self.lb or not self.win:
            return False
        sel = self.lb.curselection()
        i = (sel[0] if sel else (-1 if delta > 0 else self.lb.size())) + delta
        i = max(0, min(self.lb.size() - 1, i))
        self.lb.selection_clear(0, "end")
        self.lb.selection_set(i)
        self.lb.see(i)
        return True

    def pick_current(self):
        if not self.lb or not self.win:
            return False
        sel = self.lb.curselection()
        vals = [self.lb.get(i) for i in (sel or (0,))]
        if not vals:
            return False
        cb, val = self.on_pick, vals[0]
        self.hide()
        if cb:
            cb(val)
        return True

    def hide(self, widget=None):
        if widget is not None and self.anchor is not widget:
            return
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self.win = None
        self.lb = None
        self.on_pick = None
        self.anchor = None


def attach_system_suggest(cb, textvar):
    post = ui_dispatcher(cb)
    """给任意星系输入框接下方候选弹窗 (打字即弹, 上下选, 回车/点击确认)。"""
    state = {"seq": 0, "hits": []}
    pop = SuggestPopup.inst()

    def pick(val):
        textvar.set(val)

    def on_key(event):
        if event.keysym in ("Down", "Up"):
            if pop.visible_for(cb):
                pop.move(1 if event.keysym == "Down" else -1)
                return
            if state["hits"]:
                pop.show(cb, state["hits"], pick)
            return
        if event.keysym in ("Return", "Tab"):
            if pop.visible_for(cb) and pop.pick_current():
                return
            return
        if event.keysym == "Escape":
            pop.hide(cb)
            return
        if state.get("timer"):
            try:
                cb.after_cancel(state["timer"])
            except tk.TclError:
                pass
            state["timer"] = None

        def fire():
            state["timer"] = None
            state["seq"] += 1
            seq = state["seq"]
            text = textvar.get()

            def work():
                sug = fo.suggest_systems(text)

                def apply():
                    if seq != state["seq"] or not cb.winfo_exists():
                        return
                    state["hits"] = sug
                    if sug:
                        cb["values"] = sug
                        try:
                            focused = cb.focus_get() == cb
                        except tk.TclError:
                            focused = False
                        if focused:
                            pop.show(cb, sug, pick)
                    else:
                        pop.hide(cb)
                post(cb, apply)
            threading.Thread(target=work, daemon=True).start()

        try:
            state["timer"] = cb.after(250, fire)
        except tk.TclError:
            pass

    cb.bind("<KeyRelease>", on_key)
    cb.bind("<<ComboboxSelected>>", lambda e: pop.hide(cb))
    cb.bind("<FocusOut>", lambda e: pop.hide(cb))


class Row:
    def __init__(self, master, kind, rowtype="field"):
        self._post = ui_dispatcher(master)
        self.type = rowtype
        self.kind = kind
        self._options = []      # 全量候选
        self._seq = 0           # 异步刷新序号, 防旧结果覆盖新字段
        self.frame = ttk.Frame(master, padding=2, relief="groove")
        self.frame.pack(fill="x", pady=2)
        if rowtype == "distance":
            ttk.Label(self.frame, text="到星系距离", width=10).pack(side="left")
            self.ref = tk.StringVar(value="Sol")
            self.cb_ref = ttk.Combobox(self.frame, textvariable=self.ref, width=16)
            self.cb_ref.pack(side="left", padx=2)
            self.cb_ref.bind("<KeyRelease>", self._on_ref_key)
            self._ref_seq = 0
            self.cb_ref.bind("<<ComboboxSelected>>",
                             lambda e: SuggestPopup.inst().hide(self.cb_ref))
            ttk.Label(self.frame, text="最小LY").pack(side="left")
            self.vmin = tk.StringVar()
            ttk.Entry(self.frame, textvariable=self.vmin, width=8).pack(side="left")
            ttk.Label(self.frame, text="最大LY").pack(side="left")
            self.vmax = tk.StringVar(value="50")
            ttk.Entry(self.frame, textvariable=self.vmax, width=8).pack(side="left")
            self.mode = tk.StringVar(value="范围内")
            ttk.Combobox(self.frame, textvariable=self.mode, width=8,
                         values=["范围内", "范围外"], state="readonly").pack(side="left", padx=4)
            self.ref_info = tk.StringVar(value="")
            self.lbl_ref = ttk.Label(self.frame, textvariable=self.ref_info,
                                     foreground="gray")
            self.lbl_ref.pack(side="left", padx=4)
            self.cb_ref.bind("<FocusOut>", lambda e: (SuggestPopup.inst().hide(self.cb_ref),
                                                          self.validate_ref()))
        else:
            self.field = tk.StringVar()
            self.op = tk.StringVar(value="属于其一")
            self.val = tk.StringVar()
            self.cb_field = ttk.Combobox(self.frame, textvariable=self.field,
                                         width=30, state="readonly")
            self.cb_field.pack(side="left", padx=2)
            self.cb_field.bind("<<ComboboxSelected>>", lambda e: self.refresh_options())
            self.cb_op = ttk.Combobox(self.frame, textvariable=self.op, width=10,
                                      values=OP_LABELS, state="readonly")
            self.cb_op.pack(side="left")
            self.cb_op.bind("<<ComboboxSelected>>", lambda e: self.refresh_options())
            self.cb_val = ttk.Combobox(self.frame, textvariable=self.val, width=30)
            self.cb_val.pack(side="left", padx=4, fill="x", expand=True)
            self.cb_val.bind("<KeyRelease>", self._on_val_key)
            self.cb_val.bind("<<ComboboxSelected>>",
                             lambda e: (SuggestPopup.inst().hide(self.cb_val),
                                        self.validate_val()))
            self.cb_val.bind("<FocusOut>", lambda e: (SuggestPopup.inst().hide(self.cb_val),
                                                      self.validate_val()))
            self.btn_pick = ttk.Button(self.frame, text="选值…", width=6,
                                       command=self.pick_values)
            self.btn_pick.pack(side="left")
            # 模块规格: 仅 modules 字段 + 属于/等于/包含时显示 (等级如 5/3;5, 级别如 A/A;B)
            self.lbl_mclass = ttk.Label(self.frame, text="等级")
            self.v_class = tk.StringVar()
            self.ent_class = ttk.Combobox(self.frame, textvariable=self.v_class, width=8,
                                          postcommand=self._refresh_spec_options)
            self.lbl_mrating = ttk.Label(self.frame, text="级别")
            self.v_rating = tk.StringVar()
            self.ent_rating = ttk.Combobox(self.frame, textvariable=self.v_rating, width=6,
                                           postcommand=self._refresh_spec_options)
            # 集成新鲜度: 仅 ships/modules + 属于/等于/包含时显示
            self.lbl_fresh = ttk.Label(self.frame, text="新鲜度")
            self.v_fresh = tk.StringVar(value="不限")
            self.cb_fresh = ttk.Combobox(self.frame, textvariable=self.v_fresh, width=8,
                                         values=FRESH_OPTS, state="readonly")
            self.opt_info = tk.StringVar(value="")
            self.lbl_opt = ttk.Label(self.frame, textvariable=self.opt_info, width=10,
                                     foreground="gray")
            self.lbl_opt.pack(side="left")
            self._opt_base = ""
            self.set_fields(kind)
            self.refresh_options()
        ttk.Button(self.frame, text="删除", width=6,
                   command=self.destroy).pack(side="right")

    # ---- 距离参考点联想 (Inara式): 打字即在下方弹候选 ----
    def _on_ref_key(self, event):
        pop = SuggestPopup.inst()
        if event.keysym in ("Down", "Up"):
            if pop.visible_for(self.cb_ref):
                pop.move(1 if event.keysym == "Down" else -1)
                return
            # 没弹窗时按↓: 用上次结果直接弹
            if getattr(self, "_ref_hits", None):
                pop.show(self.cb_ref, self._ref_hits, self._pick_ref)
            return
        if event.keysym in ("Return", "Tab"):
            if pop.visible_for(self.cb_ref) and pop.pick_current():
                return
            return
        if event.keysym == "Escape":
            pop.hide(self.cb_ref)
            return
        if getattr(self, "_ref_timer", None):
            try:
                self.frame.after_cancel(self._ref_timer)
            except tk.TclError:
                pass
            self._ref_timer = None

        def fire():
            self._ref_timer = None
            self._ref_seq += 1
            seq = self._ref_seq
            text = self.ref.get()

            def work():
                sug = fo.suggest_systems(text)

                def apply():
                    if seq != self._ref_seq or not self.cb_ref.winfo_exists():
                        return
                    self._ref_hits = sug
                    if sug:
                        self.cb_ref["values"] = sug
                        if self.cb_ref.focus_get() == self.cb_ref:
                            pop.show(self.cb_ref, sug, self._pick_ref)
                    else:
                        pop.hide(self.cb_ref)
                self._post(self.frame, apply)
            threading.Thread(target=work, daemon=True).start()

        try:
            self._ref_timer = self.frame.after(250, fire)
        except tk.TclError:
            pass
    def _pick_ref(self, val):
        self.ref.set(val)
        self.validate_ref()

    # ---- 参考星系失焦即校验: 存在打勾, 打错自动纠, 不存在报错+建议 ----
    def validate_ref(self):
        if self.type != "distance":
            return
        name = self.ref.get().strip()
        if not name:
            self.ref_info.set("请填星系")
            self.lbl_ref["foreground"] = "red"
            return
        self._ref_vseq = getattr(self, "_ref_vseq", 0) + 1
        seq = self._ref_vseq

        def work():
            try:
                canon, _, fixed = eng.resolve_ref(name)
            except ValueError as e:
                msg = str(e)
                def apply_err():
                    if seq != self._ref_vseq or not self.frame.winfo_exists():
                        return
                    self.ref_info.set(msg[:70])
                    self.lbl_ref["foreground"] = "red"
                self._post(self.frame, apply_err)
                return

            def apply_ok():
                if seq != self._ref_vseq or not self.frame.winfo_exists():
                    return
                if fixed:
                    self.ref.set(canon)
                    self.ref_info.set(f"已纠正为 {canon}")
                else:
                    self.ref_info.set(f"✓ {canon}")
                self.lbl_ref["foreground"] = "green"
            self._post(self.frame, apply_ok)
        threading.Thread(target=work, daemon=True).start()

    # ---- 第三格: 下拉 + 联想 ----
    def set_fields(self, kind):
        if self.type != "field":
            return
        self.kind = kind
        keys = sorted(STATION_FIELDS if kind == "stations" else SYSTEM_FIELDS)
        labels = [field_label(kind, k) for k in keys]
        self.cb_field["values"] = labels
        cur_en = parse_field_label(self.field.get())
        if cur_en not in keys:
            first = keys[0] if keys else ""
            self.field.set(field_label(kind, first) if first else "")

    def _toggle_module_sub(self):
        """模块规格输入显隐: 仅 stations.modules + 属于/等于/包含时显示。"""
        show = (self.type == "field" and self.kind == "stations"
                and parse_field_label(self.field.get().strip()) == "modules"
                and self.op.get() in ("属于其一", "等于", "包含"))
        for w in (self.lbl_mclass, self.ent_class, self.lbl_mrating, self.ent_rating):
            if show:
                w.pack(side="left", padx=(4, 0))
            else:
                w.pack_forget()
        if show:
            self._refresh_spec_options()
        self._toggle_fresh()
        return show

    def _single_module_name(self):
        """当前模块值是单个确切模块名时返回其标准名，否则 None（多值不联动）。"""
        if self.type != "field" or self.kind != "stations":
            return None
        if parse_field_label(self.field.get().strip()) != "modules":
            return None
        segs = [s.strip() for s in self.val.get().replace("，", ";").replace(",", ";").split(";")
                if s.strip()]
        if len(segs) != 1:
            return None
        low = segs[0].casefold()
        for o in self._options or fo.get_options("stations", "modules"):
            if str(o).casefold() == low:
                return str(o)
        return None

    def _refresh_spec_options(self):
        """等级/级别下拉联动：学过该模块的规格就只给已见子集，否则给全集。"""
        name = self._single_module_name()
        self.ent_class["values"] = fo.get_module_classes(name)
        self.ent_rating["values"] = fo.get_module_ratings(name)

    def _toggle_fresh(self):
        """集成新鲜度显隐: ships/modules + 属于/等于/包含时显示。"""
        show = (self.type == "field" and self.kind == "stations"
                and parse_field_label(self.field.get().strip()) in FRESH_FIELDS_ROWS
                and self.op.get() in ("属于其一", "等于", "包含"))
        for w in (self.lbl_fresh, self.cb_fresh):
            if show:
                w.pack(side="left", padx=(4, 0))
            else:
                w.pack_forget()
        return show

    def refresh_options(self):
        if self.type != "field":
            return
        self._toggle_module_sub()
        op = self.op.get()
        if op in ("是", "否"):
            self.cb_val.set("")
            self.cb_val["state"] = "disabled"
            self.btn_pick["state"] = "disabled"
            self.opt_info.set("无需填写")
            return
        self.cb_val["state"] = "normal"
        field = parse_field_label(self.field.get().strip())
        if field in FRESH_FIELDS and op in ("区间(内)", "范围外"):
            # 新鲜度快捷: 可选近N天, 也可手填日期区间
            self.cb_val["values"] = list(FRESH_QUICK)
            self._options = list(FRESH_QUICK)
            self.btn_pick["state"] = "normal"
            self.opt_info.set("快捷或手填日期")
            self._opt_base = self.opt_info.get()
            self.lbl_opt["foreground"] = "gray"
            return
        if op in NUMERIC_OPS:
            self.cb_val["values"] = []
            self.btn_pick["state"] = "disabled"
            if field in FRESH_FIELDS:
                self.opt_info.set("填日期或近N天")
            else:
                self.opt_info.set("填数字/min~max")
            return
        # 枚举/文本类: 异步取候选
        kind = self.kind
        self._seq += 1
        seq = self._seq
        self.opt_info.set("加载中…")
        self.btn_pick["state"] = "normal"

        def work():
            opts = fo.get_options(kind, field)
            def apply():
                if seq != self._seq or not self.frame.winfo_exists():
                    return
                self._options = opts
                if opts:
                    self.cb_val["values"] = opts[:50] if len(opts) > 50 else opts
                    if len(opts) <= 30:
                        self.opt_info.set(f"{len(opts)}个可下拉")
                    else:
                        self.opt_info.set(f"{len(opts)}个打字筛")
                else:
                    self.cb_val["values"] = []
                    self.opt_info.set("自由输入")
                self._opt_base = self.opt_info.get()
                self.lbl_opt["foreground"] = "gray"
            self._post(self.frame, apply)
        threading.Thread(target=work, daemon=True).start()

    def _on_val_key(self, event):
        pop = SuggestPopup.inst()
        if event.keysym in ("Down", "Up"):
            if pop.visible_for(self.cb_val):
                pop.move(1 if event.keysym == "Down" else -1)
                return
            if getattr(self, "_val_hits", None):
                pop.show(self.cb_val, self._val_hits, self._pick_val)
            return
        if event.keysym in ("Return", "Tab"):
            if pop.visible_for(self.cb_val) and pop.pick_current():
                return
            return
        if event.keysym == "Escape":
            pop.hide(self.cb_val)
            return
        if not self._options or self.op.get() in NUMERIC_OPS:
            pop.hide(self.cb_val)
            return
        # 只对当前正在输入的一段(按 ; 分)做过滤, 并在下方弹出
        text = self.val.get()
        seg = text.replace("，", ";").split(";")[-1].strip().lower()
        if not seg:
            hit = self._options[:50]
        else:
            hit = [o for o in self._options if seg in o.lower()][:30]
        self._val_hits = hit
        self.cb_val["values"] = hit
        if hit and self.cb_val.focus_get() == self.cb_val:
            pop.show(self.cb_val, hit, self._pick_val)
        else:
            pop.hide(self.cb_val)

    def _pick_val(self, val):
        if self.op.get() in MULTI_OPS:
            # 多选: 只替换正在输入的最后一段
            parts = self.val.get().replace("，", ";").split(";")
            parts[-1] = val
            self.val.set("; ".join(p.strip() for p in parts if p.strip()))
        else:
            self.val.set(val)
        self._refresh_spec_options()

    def validate_val(self):
        """船/模块名失焦即校验: 未知标红+建议, 可纠正提示将自动纠 (实际纠正在运行时)。"""
        if self.type != "field" or not self.frame.winfo_exists():
            return
        f = parse_field_label(self.field.get().strip())
        if self.kind != "stations" or f not in AUTOCORRECT_FIELDS:
            return
        if self.op.get() in NUMERIC_OPS:
            return
        segs = [s.strip() for s in self.val.get().replace("，", ";").replace(",", ";").split(";")
                if s.strip()]
        if not segs:
            self.opt_info.set(self._opt_base)
            self.lbl_opt["foreground"] = "gray"
            return
        bad, fixes = [], []
        for s in segs:
            try:
                canon, fixed = eng.resolve_option("stations", f, s)
                if fixed:
                    fixes.append((s, canon))
            except ValueError:
                sims = (fo.similar_modules(s) if f == "modules"
                        else fo.similar_ships(s))
                bad.append((s, sims[0][0] if sims else "无"))
        if bad:
            s, sug = bad[0]
            self.opt_info.set(f"未知:{s}→{sug}?"[:24])
            self.lbl_opt["foreground"] = "red"
            return
        if fixes:
            self.opt_info.set("、".join(f"{a}→{b}" for a, b in fixes)[:24])
            self.lbl_opt["foreground"] = "orange"
            return
        self._refresh_spec_options()
        if self.op.get() in ("属于其一", "等于", "包含"):
            try:
                for seg in [x.strip() for x in self.v_class.get().replace("，", ";").replace(",", ";").split(";") if x.strip()]:
                    eng.parse_module_class(seg, "等级")
                for seg in [x.strip() for x in self.v_rating.get().replace("，", ";").replace(",", ";").split(";") if x.strip()]:
                    eng.parse_module_rating(seg, "级别")
            except ValueError as e:
                self.opt_info.set(str(e)[:24])
                self.lbl_opt["foreground"] = "red"
                return
        self.opt_info.set(self._opt_base)
        self.lbl_opt["foreground"] = "gray"

    def pick_values(self):
        if not self._options:
            messagebox.showinfo("提示", "该字段无预置选项, 直接输入即可 (星系/派系名支持模糊)。")
            return
        cur = self.val.get().replace("，", ";").replace(",", ";").split(";")
        cur = [c.strip() for c in cur if c.strip()]
        if self.op.get() in MULTI_OPS:
            picked = open_multi_select(self.frame, f"多选 {self.field.get()}",
                                       self._options, cur)
            if picked is not None:
                if not picked:
                    messagebox.showwarning("提示", "未勾选任何值")
                    return
                self.val.set("; ".join(picked))
        else:
            picked = open_multi_select(self.frame, f"单选 {self.field.get()}",
                                       self._options, cur[:1])
            if picked:
                self.val.set(picked[0])

    def destroy(self):
        pop = SuggestPopup.inst()
        if pop.anchor in (getattr(self, "cb_ref", None), getattr(self, "cb_val", None)):
            pop.hide()
        self.frame.destroy()

    def editor_state(self):
        """保存原始输入，未填完整或暂时非法的条件也能继续编辑。"""
        if self.type == "distance":
            return dict(type="distance", ref=self.ref.get(), min=self.vmin.get(),
                        max=self.vmax.get(), mode=self.mode.get())
        return dict(type="field", field=parse_field_label(self.field.get()), op=self.op.get(),
                    value=self.val.get(), **{"class": self.v_class.get(),
                    "rating": self.v_rating.get(), "fresh": self.v_fresh.get()})

    def to_cond(self):
        if self.type == "distance":
            def num(s):
                s = s.strip()
                return float(s) if s else None
            if not self.ref.get().strip():
                raise ValueError("距离条件请填写参考星系")
            return {"type": "distance", "ref_system": self.ref.get().strip(),
                    "min_ly": num(self.vmin.get()), "max_ly": num(self.vmax.get()),
                    "mode": "inside" if self.mode.get() == "范围内" else "outside"}
        f = parse_field_label(self.field.get().strip())
        op_label = self.op.get()
        op = OP_MAP[op_label]
        raw = self.val.get().strip().replace("，", ";").replace(",", ";")

        def split_list(s):
            return [x.strip() for x in s.replace("，", ";").replace(",", ";").split(";")
                    if x.strip()]

        def module_spec(d):
            # 模块规格原文透传 (等级如 5/5级, 级别如 A), 引擎统一校验
            if f == "modules" and op in ("in", "=", "contains"):
                rc = split_list(self.v_class.get())
                rr = split_list(self.v_rating.get())
                if rc:
                    d["class"] = rc
                if rr:
                    d["rating"] = rr
            # 船/模块集成新鲜度 (卖X且数据N天内新)
            if f in FRESH_FIELDS_ROWS and op in ("in", "=", "contains"):
                days = fresh_opt_days(self.v_fresh.get())
                if days:
                    d["fresh_days"] = days
            return d

        if op in ("true", "false"):
            return {"type": "field", "field": f, "op": op}
        if op in ("in", "not in"):
            vals = [v.strip() for v in raw.split(";") if v.strip()]
            if not vals:
                raise ValueError(f"{f}: 请下拉选择或输入至少一个值, 多个用 ; 分隔")
            return module_spec({"type": "field", "field": f, "op": op, "values": vals})
        if op in ("=", "!=", "contains"):
            if not raw:
                raise ValueError(f"{f}: 请下拉选择或输入内容")
            return module_spec({"type": "field", "field": f, "op": op,
                                "text": raw.split(";")[0].strip()})
        if op in ("<", "<=", ">", ">="):
            if not raw:
                raise ValueError(f"{f}: 请填写数字")
            value = raw.split(";")[0]
            return {"type": "field", "field": f, "op": op,
                    "text": value if f in eng.TIMESTAMP_KEYS else float(value)}
        if op in ("between", "outside"):
            s = raw.replace("～", "~")
            if "~" not in s and "-" in s and f not in eng.TIMESTAMP_KEYS:
                s = s.replace("-", "~", 1)
            if "~" not in s:
                if f in eng.TIMESTAMP_KEYS and "-" not in s:
                    a, b = s, ""  # 时间快捷值 (如近7天) 默认只封下限
                else:
                    raise ValueError(f"{f}: 区间格式为 最小~最大, 如 0~1000, 空一边表示不封口")
            else:
                a, b = s.split("~", 1)
            def num(x):
                x = x.strip()
                return (x if f in eng.TIMESTAMP_KEYS else float(x)) if x else None
            return {"type": "field", "field": f, "op": op,
                    "min": num(a), "max": num(b)}
        raise ValueError(f"未知操作: {op_label}")


class App:
    def __init__(self, root):
        self._post = ui_dispatcher(root)
        self.root = root
        root.title("Elite 星系/空间站全条件筛选器")
        root.geometry("1120x720")
        self.rows = []
        self.results = []
        self._tool_states = {}
        self._tool_collectors = {}
        self._last_session_state = None
        self._closing = False

        top = ttk.Frame(root, padding=(6, 6, 6, 2))
        top.pack(fill="x")
        ttk.Label(top, text="类型").pack(side="left")
        self.kind = tk.StringVar(value="stations")
        self.cb_kind = ttk.Combobox(top, textvariable=self.kind, width=10,
                                    values=["stations", "systems"], state="readonly")
        self.cb_kind.pack(side="left", padx=4)
        self.cb_kind.bind("<<ComboboxSelected>>", lambda e: self.refresh_fields())
        ttk.Label(top, text="要几条").pack(side="left", padx=(8, 0))
        self.want = tk.StringVar(value="200")
        ttk.Entry(top, textvariable=self.want, width=6).pack(side="left")
        ttk.Label(top, text="最多翻页").pack(side="left", padx=(8, 0))
        self.maxpages = tk.StringVar(value="25")
        ttk.Entry(top, textvariable=self.maxpages, width=4).pack(side="left")
        ttk.Button(top, text="+ 普通条件", command=self.add_field).pack(side="left", padx=4)
        ttk.Button(top, text="+ 距离条件", command=self.add_distance).pack(side="left")
        ttk.Button(top, text="清空条件", command=self.clear).pack(side="left", padx=4)
        ttk.Button(top, text="保存条件", command=self.save).pack(side="left")
        ttk.Button(top, text="读取条件", command=self.load).pack(side="left", padx=4)
        self.btn_run = ttk.Button(top, text="运行搜索", command=self.run)
        self.btn_run.pack(side="left")
        self.btn_stop = ttk.Button(top, text="停止", command=self.stop_search,
                                   state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        ttk.Button(top, text="诊断", command=self.diagnose).pack(side="left")
        ttk.Button(top, text="导出CSV", command=self.export).pack(side="left", padx=4)

        extra = ttk.Frame(root, padding=(6, 0, 6, 6))
        extra.pack(fill="x")
        ttk.Label(extra, text="额外功能：", foreground="gray").pack(side="left")
        ttk.Button(extra, text="两系中点", command=self.midpoint_window).pack(side="left")
        ttk.Button(extra, text="航母车位", command=self.carrier_parking_window).pack(side="left", padx=4)
        ttk.Button(extra, text="稀有商品目标查找器", command=self.rare_goods_window).pack(side="left", padx=4)

        self.hint_var = tk.StringVar(
            value="第三格可下拉/打字联想/点“选值…”多选 (选项≤30个直接下拉)。船/模块名打字联想+自动纠错，行内自带新鲜度选择。")
        ttk.Label(root, textvariable=self.hint_var, foreground="gray").pack(fill="x", padx=6)

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True, padx=6)
        self.canvas = tk.Canvas(body, height=220)
        vsb = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.inner = ttk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.status = tk.StringVar(value="就绪")
        ttk.Label(root, textvariable=self.status).pack(fill="x", padx=6)
        progfrm = ttk.Frame(root)
        progfrm.pack(fill="x", padx=6, pady=(0, 2))
        self.prog = ttk.Progressbar(progfrm, mode="determinate", maximum=100, value=0)
        self.prog.pack(side="left", fill="x", expand=True)
        self.prog_pct = tk.StringVar(value="")
        ttk.Label(progfrm, textvariable=self.prog_pct, width=8).pack(side="left", padx=(4, 0))

        cols = ("name", "place", "info", "extra")
        self.tree = ttk.Treeview(root, columns=cols, show="headings", height=16)
        for c, w, t in [("name", 220, "名称"), ("place", 180, "星系/位置"),
                        ("info", 400, "关键信息"), ("extra", 260, "各参考点距离")]:
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=6, pady=4)

        # 后台预热常见字段候选值
        fo.prefetch_common("stations", ["allegiance", "government", "primary_economy",
                                        "type", "services", "material_trader",
                                        "system_power_state"])
        fo.prefetch_common("systems", ["allegiance", "primary_economy", "security", "power"])
        # 恢复上次关闭时的条件; 没有则从空开始
        self.restore_session()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(1500, self._autosave_session)

    def refresh_fields(self):
        self.rows = [r for r in self.rows if r.frame.winfo_exists()]
        for r in self.rows:
            r.set_fields(self.kind.get())
            r.refresh_options()

    def add_field(self):
        self.rows.append(Row(self.inner, self.kind.get(), "field"))
        self.rows[-1].frame.winfo_toplevel().update_idletasks()

    def add_distance(self):
        self.rows.append(Row(self.inner, self.kind.get(), "distance"))

    def clear(self):
        for r in self.rows:
            r.destroy()
        self.rows = []

    def collect(self):
        conds = []
        for r in self.rows:
            if r.frame.winfo_exists():
                conds.append(r.to_cond())
        self.rows = [r for r in self.rows if r.frame.winfo_exists()]
        if not conds:
            raise ValueError("请先添加至少一个条件")
        return conds

    def save(self):
        try:
            conds = self.collect()
        except ValueError as e:
            messagebox.showwarning("提示", str(e))
            return
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                         filetypes=[("JSON", "*.json")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"kind": self.kind.get(), "conditions": conds},
                          f, ensure_ascii=False, indent=1)
            self.status.set(f"已保存 {p}")

    def _append_cond(self, c):
        """按一条条件字典建行 (读取文件/恢复会话共用), 条目损坏则跳过。"""
        if c.get("type") == "distance":
            r = Row(self.inner, self.kind.get(), "distance")
            r.ref.set(str(c.get("ref_system") or "Sol"))
            r.vmin.set("" if c.get("min_ly") is None else str(c["min_ly"]))
            r.vmax.set("" if c.get("max_ly") is None else str(c["max_ly"]))
            r.mode.set("范围内" if c.get("mode", "inside") == "inside" else "范围外")
            self.rows.append(r)
            return
        if not c.get("field") or not c.get("op"):
            return
        r = Row(self.inner, self.kind.get(), "field")
        r.field.set(field_label(self.kind.get(), c["field"]))
        inv = {v: k for k, v in OP_MAP.items()}
        r.op.set(inv.get(c["op"], "属于其一"))
        if c["op"] in ("in", "not in"):
            r.val.set("; ".join(str(v) for v in c.get("values", [])))
        elif c["op"] in ("between", "outside"):
            a = "" if c.get("min") is None else str(c["min"])
            b = "" if c.get("max") is None else str(c["max"])
            r.val.set(f"{a}~{b}")
        elif c["op"] not in ("true", "false"):
            r.val.set(str(c.get("text", "")))
        if c.get("field") == "modules":
            r.v_class.set("; ".join(str(v) for v in c.get("class", [])))
            r.v_rating.set("; ".join(str(v) for v in c.get("rating", [])))
        if c.get("field") in FRESH_FIELDS_ROWS and c.get("fresh_days"):
            try:
                fd = int(c["fresh_days"])
            except (TypeError, ValueError):
                fd = None
            inv_fresh = {v: k for k, v in FRESH_DAYS.items()}
            r.v_fresh.set(inv_fresh.get(fd, f"近{fd}天" if fd else "不限"))
        r.refresh_options()
        self.rows.append(r)

    def _apply_state(self, d):
        self.clear()
        if d.get("kind") in ("stations", "systems"):
            self.kind.set(d["kind"])
        if isinstance(d.get("rows"), list):
            for saved in d["rows"]:
                if not isinstance(saved, dict) or saved.get("type") not in ("field", "distance"):
                    continue
                r = Row(self.inner, self.kind.get(), saved["type"])
                if saved["type"] == "distance":
                    for variable, key in ((r.ref, "ref"), (r.vmin, "min"),
                                          (r.vmax, "max"), (r.mode, "mode")):
                        if isinstance(saved.get(key), str):
                            variable.set(saved[key])
                else:
                    r.field.set(field_label(self.kind.get(), str(saved.get("field") or "name")))
                    for variable, key in ((r.op, "op"), (r.val, "value"), (r.v_class, "class"),
                                          (r.v_rating, "rating"), (r.v_fresh, "fresh")):
                        if isinstance(saved.get(key), str):
                            variable.set(saved[key])
                    r.refresh_options()
                self.rows.append(r)
        else:
            for c in d.get("conditions", []):
                if isinstance(c, dict):
                    self._append_cond(c)
        if isinstance(d.get("tools"), dict):
            self._tool_states.update({key: value for key, value in d["tools"].items()
                                      if isinstance(value, dict)})
        if d.get("want") is not None:
            self.want.set(str(d["want"]))
        if d.get("maxpages") is not None:
            self.maxpages.set(str(d["maxpages"]))

    def _state_dict(self):
        try:
            conds = self.collect()
        except (ValueError, KeyError):
            # conditions保留旧格式；完整编辑状态另存rows，不丢弃草稿行。
            conds = [c for r in self.rows if r.frame.winfo_exists()
                     for c in [self._try_cond(r)] if c is not None]
        for key, collector in self._tool_collectors.items():
            self._tool_states[key] = collector()
        return {"kind": self.kind.get(), "conditions": conds,
                "want": self.want.get(), "maxpages": self.maxpages.get(),
                "rows": [r.editor_state() for r in self.rows if r.frame.winfo_exists()],
                "tools": dict(self._tool_states)}

    def bind_tool_state(self, key, window, variables):
        """统一保存辅助窗口；关子窗口和关主窗口都能保存当前参数。"""
        saved = self._tool_states.get(key, {})
        for name, variable in variables.items():
            value = saved.get(name)
            if isinstance(variable, tk.BooleanVar):
                if isinstance(value, bool):
                    variable.set(value)
            elif isinstance(value, str):
                variable.set(value)
        collector = lambda: {name: variable.get() for name, variable in variables.items()}
        self._tool_collectors[key] = collector
        window.session_variables = variables

        def destroyed(event):
            if event.widget is not window or self._closing:
                return
            self._tool_states[key] = collector()
            if self._tool_collectors.get(key) is collector:
                del self._tool_collectors[key]
            self.save_session()

        window.bind("<Destroy>", destroyed, add="+")

    @staticmethod
    def _try_cond(r):
        try:
            return r.to_cond()
        except (ValueError, AttributeError, TypeError, KeyError, tk.TclError):
            return None

    def save_session(self):
        try:
            state = self._state_dict()
            if state != self._last_session_state or not os.path.exists(SESSION_FILE):
                session_store.save(SESSION_FILE, state)
                self._last_session_state = state
            return True
        except (OSError, ValueError, tk.TclError) as exc:
            self.status.set(f"会话保存失败：{exc}")
            return False

    def _autosave_session(self):
        if not self._closing:
            self.save_session()
            self.root.after(1500, self._autosave_session)

    def restore_session(self):
        d = session_store.load(SESSION_FILE)
        if d:
            self._apply_state(d)

    def on_close(self):
        if not self.save_session():
            messagebox.showerror("会话保存失败", f"未关闭程序，请检查目录权限后重试。\n{SESSION_FILE}", parent=self.root)
            return
        self._closing = True
        fo.save_module_specs()
        self.root.destroy()

    def load(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not p:
            return
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        self._apply_state(d)

    def run(self):
        try:
            conds = self.collect()
            want = max(1, min(2000, int(self.want.get())))
            maxpages = max(1, min(50, int(self.maxpages.get())))
        except ValueError as e:
            messagebox.showwarning("条件有误", str(e))
            return
        kind = self.kind.get()
        try:
            p0 = eng.build_server_payload(kind, conds)
            blind = not p0["filters"] and "reference_system" not in p0
        except eng.Contradiction as ce:
            messagebox.showinfo("无需检索", str(ce) + "\n(条件自相矛盾，一次请求都没发)")
            return
        except ValueError as exc:
            messagebox.showwarning("条件有误", str(exc))
            return
        if blind and not messagebox.askyesno(
                "确认", "没有任何条件能推给服务器，将逐页硬扫全库\n(慢，且翻页上限内未必扫全)，继续吗？"):
            return
        self._stop = threading.Event()
        self.btn_run["state"] = "disabled"
        self.btn_stop["state"] = "normal"
        self.status.set("查询中...")
        self.prog.stop()
        self.prog["mode"] = "indeterminate"
        self.prog.start(80)
        self.prog_pct.set("准备中")
        self.results = []
        self.tree.delete(*self.tree.get_children())

        def work():
            try:
                corr = []
                notes = []
                rows, total, scanned = eng.search(
                    kind, conds, want=want, max_pages=maxpages,
                    progress=lambda msg, info=None: self._post(
                        self.root, self._apply_progress, msg, info or {}),
                    corrections=corr,
                    stop=self._stop, notes=notes)
                self.results = rows
                # 反哺规格学习库: 结果行里的在售条目自带 (name, class, rating)
                for r in rows:
                    fo.learn_module_specs(r.get("modules"))
                fo.save_module_specs()
                fixes = dict(corr)
                dist_refs = list(dict.fromkeys(fixes.get(c["ref_system"], c["ref_system"])
                                              for c in conds if c.get("type") == "distance"))
                # 把纠正应用回界面条件 (距离参考点 + 船/模块值段落), 展示用纠正后的值
                for old, new in corr:
                    for c in conds:
                        if c.get("type") == "distance":
                            if c.get("ref_system") == old:
                                c["ref_system"] = new
                        elif c.get("op") in ("in", "not in") and "values" in c:
                            c["values"] = [new if str(v).casefold() == old.casefold() else v
                                           for v in c["values"]]
                        elif isinstance(c.get("text"), str) and c["text"].casefold() == old.casefold():
                            c["text"] = new
                wanted_ships = set()
                for c in conds:
                    if c.get("type") == "distance":
                        continue
                    if c.get("field") == "ships" and c.get("op") in ("in", "="):
                        vals = c.get("values", []) if c["op"] == "in" else [c.get("text", "")]
                        wanted_ships.update(str(v).casefold() for v in vals)
                # 展示用归一化副本 (规格解析为整数/大写, 与引擎口径一致)
                try:
                    dconds = eng.normalize_conditions(kind, conds)
                except (ValueError, eng.Contradiction):
                    dconds = conds
                mod_conds = [c for c in dconds
                             if c.get("type") != "distance" and c.get("field") == "modules"
                             and c.get("op") in ("in", "=")]

                def mod_tags(row):
                    """在售模块 -> [(小写名, 展示名, 等级, 级别)]。"""
                    out = []
                    for it in row.get("modules") or []:
                        if not isinstance(it, dict) or not it.get("name"):
                            continue
                        try:
                            cls = int(it.get("class"))
                        except (TypeError, ValueError):
                            cls = None
                        rat = str(it.get("rating") or "").upper() or None
                        disp = str(it["name"])
                        if cls is not None:
                            disp += f" {cls}"
                        if rat:
                            disp += rat
                        out.append((str(it["name"]).casefold(), disp, cls, rat))
                    return out

                def show():
                    for old, new in corr:
                        for rr in self.rows:
                            if not rr.frame.winfo_exists():
                                continue
                            if (getattr(rr, "type", "") == "distance"
                                    and rr.ref.get().strip() == old):
                                rr.ref.set(new)
                                rr.ref_info.set(f"已纠正为 {new}")
                                rr.lbl_ref["foreground"] = "green"
                            elif (getattr(rr, "type", "") == "field"
                                    and parse_field_label(rr.field.get()) in AUTOCORRECT_FIELDS):
                                parts = rr.val.get().replace("，", ";").split(";")
                                if any(p.strip().casefold() == old.casefold() for p in parts):
                                    rr.val.set("; ".join(
                                        new if p.strip().casefold() == old.casefold() else p.strip()
                                        for p in parts if p.strip()))
                    for r in rows:
                        if kind == "stations":
                            extra = ", ".join(
                                f"{ref}:{r.get('_distances', {}).get(ref, '?')}ly"
                                for ref in dist_refs)
                            actual_ships = eng._names(r.get("ships"), "ships")
                            actual_mods = eng._names(r.get("modules"), "modules")
                            tags = mod_tags(r)
                            if wanted_ships or mod_conds:
                                hit = [n for n in actual_ships if n.casefold() in wanted_ships]
                                for c in mod_conds:
                                    names = {str(v).casefold()
                                             for v in (c.get("values", []) if c["op"] == "in"
                                                       else [c.get("text", "")])}
                                    classes = set(c.get("class") or [])
                                    ratings = {str(v).upper() for v in (c.get("rating") or [])}
                                    for low, disp, cls, rat in tags:
                                        if low in names and (not classes or cls in classes) \
                                                and (not ratings or rat in ratings):
                                            hit.append(disp)
                                hit = list(dict.fromkeys(hit))
                                if not hit:
                                    # 服务端精确下推但行内缺明细: 显示条件原文+规格
                                    fb = sorted(wanted_ships)
                                    for c in mod_conds:
                                        spec = eng.module_spec_suffix(c)
                                        vals = c.get("values", []) if c["op"] == "in" \
                                            else [c.get("text", "")]
                                        fb.extend(f"{v}{spec}" for v in vals)
                                    hit = sorted(set(fb))
                                sell = "卖:" + "、".join(hit[:3])
                                if len(hit) > 3:
                                    sell += f"等{len(hit)}项"
                            else:
                                sell = f"在售{len(actual_ships)}船/{len(actual_mods)}模块"
                            self.tree.insert("", "end", values=(
                                r.get("name"), r.get("system_name"),
                                f"{r.get('type')} | {r.get('primary_economy')} | "
                                f"{r.get('distance_to_arrival')}ls | "
                                f"市场{r.get('has_market')}/船厂{r.get('has_shipyard')} | "
                                f"{sell} | 船厂{data_age(r.get('shipyard_updated_at'))}/"
                                f"改装{data_age(r.get('outfitting_updated_at'))}",
                                extra))
                        else:
                            extra = ", ".join(
                                f"{ref}:{r.get('_distances', {}).get(ref, '?')}ly"
                                for ref in dist_refs)
                            self.tree.insert("", "end", values=(
                                r.get("name"), f"pop {r.get('population')}",
                                f"{r.get('allegiance')} | {r.get('primary_economy')} | "
                                f"{r.get('security')}", extra))
                    msg = f"服务器候选计数 {total}, 已复核 {scanned} 条, 命中 {len(rows)} 条"
                    if corr:
                        msg += "；" + "、".join(f"'{a}'→'{b}'" for a, b in corr) + "已自动纠正"
                    if notes:
                        msg += "；" + "、".join(notes)
                    self.status.set(msg)
                    self.btn_run["state"] = "normal"
                    self.btn_stop["state"] = "disabled"
                    self.prog.stop()
                    self.prog["mode"] = "determinate"
                    if any("已达到所需结果数" in n or "候选分页已取完" in n for n in notes):
                        self.prog["value"] = 100
                        self.prog_pct.set("完成")
                    elif any("已手动停止" in n for n in notes):
                        self.prog_pct.set("已停止")
                    else:
                        self.prog_pct.set("未完成")
                self._post(self.root, show)
            except Exception as e:
                self._post(self.root, lambda error=str(e): (
                    messagebox.showerror("查询失败", error),
                    self.status.set("失败"),
                    self.prog.stop(),
                    self.prog.configure(mode="determinate"),
                    self.prog_pct.set("失败"),
                    self.btn_run.__setitem__("state", "normal"),
                    self.btn_stop.__setitem__("state", "disabled")))

        threading.Thread(target=work, daemon=True).start()

    def _apply_progress(self, msg, info):
        """工作线程经 root.after 回调: 更新状态文本 + 进度条。
        info: {phase, scanned, hits, total, page, pages, per, want}。
        resolve=解析参考星系, fetch=单页请求等待中, page=一页完成。"""
        self.status.set(msg)
        if info.get("phase") in ("resolve", "fetch"):
            if str(self.prog["mode"]) != "indeterminate":
                self.prog["mode"] = "indeterminate"
                self.prog.start(80)
            if info.get("phase") == "resolve":
                self.prog_pct.set("准备中")
            else:
                hits = info.get("hits", 0)
                want = info.get("want", 0)
                extra = f"命中 {hits}/{want}" if want else f"命中 {hits}"
                self.prog_pct.set(f"请求中 {extra}")
            return
        self.prog.stop()
        self.prog["mode"] = "determinate"
        try:
            scanned = max(0, int(info.get("scanned", 0) or 0))
            total = int(info.get("total", 0) or 0)
            pages = max(1, int(info.get("pages", 1) or 1))
            per = max(1, int(info.get("per", 100) or 100))
        except (TypeError, ValueError):
            return
        expected = pages * per
        if total > 0:
            expected = min(total, expected)
        pct = min(100.0, scanned * 100.0 / expected) if expected > 0 else 0.0
        self.prog["value"] = pct
        hits = info.get("hits", 0)
        want = info.get("want", 0)
        extra = f"命中 {hits}/{want}" if want else f"命中 {hits}"
        self.prog_pct.set(f"{pct:.0f}% {extra}")

    def stop_search(self):
        if getattr(self, "_stop", None):
            self._stop.set()
            self.status.set("正在停止...")
            self.prog_pct.set("停止中")

    def diagnose(self):
        try:
            conds = self.collect()
        except ValueError as e:
            messagebox.showwarning("条件有误", str(e))
            return
        kind = self.kind.get()
        self.status.set("诊断中: 取前3页样本统计各条件通过率...")
        self.prog.stop()
        self.prog["mode"] = "indeterminate"
        self.prog.start(80)
        self.prog_pct.set("诊断中")

        def work():
            try:
                stats, n = eng.diagnose(kind, conds, pages=3)
                lines = [f"样本 {n} 条 (服务器前3页候选):"]
                for desc, hit, _ in stats:
                    pct = hit * 100.0 / n if n else 0
                    flag = "  <-- 最严, 优先放宽它" if hit == 0 else ""
                    lines.append(f"{pct:5.1f}% 通过 ({hit}/{n})  {desc}{flag}")
                lines.append("")
                lines.append("通过率仅针对这些候选样本；0% 不代表全库无结果。多距离组合注意两圈是否有交集。")
                self._post(self.root, lambda: (
                    messagebox.showinfo("诊断", "\n".join(lines)),
                    self.status.set("诊断完成"),
                    self.prog.stop(),
                    self.prog.configure(mode="determinate"),
                    self.prog_pct.set("")))
            except eng.Contradiction as ce:
                self._post(self.root, lambda error=str(ce): (
                    messagebox.showinfo("诊断", error),
                    self.status.set("诊断完成"),
                    self.prog.stop(),
                    self.prog.configure(mode="determinate"),
                    self.prog_pct.set("")))
            except Exception as e:
                self._post(self.root, lambda error=str(e): (
                    messagebox.showerror("诊断失败", error),
                    self.status.set("失败"),
                    self.prog.stop(),
                    self.prog.configure(mode="determinate"),
                    self.prog_pct.set("失败")))

        threading.Thread(target=work, daemon=True).start()

    def rare_goods_window(self):
        from powerplay_gui import open_window
        open_window(self, data_age)

    def carrier_parking_window(self):
        win = tk.Toplevel(self.root)
        win.title("航母车位查找")
        win.geometry("1060x580")
        controls = ttk.Frame(win, padding=8)
        controls.pack(fill="x")
        ttk.Label(controls, text="参考星系").pack(side="left")
        reference = tk.StringVar(value="Sol")
        cb = ttk.Combobox(controls, textvariable=reference, width=24)
        cb.pack(side="left", padx=4)
        attach_system_suggest(cb, reference)
        radius = tk.StringVar(value="30")
        pages = tk.StringVar(value="20")
        for label, variable in (("半径 ly (≤50)", radius), ("最多页数", pages)):
            ttk.Label(controls, text=label).pack(side="left", padx=(8, 0))
            ttk.Entry(controls, textvariable=variable, width=7).pack(side="left", padx=4)
        options = ttk.Frame(win, padding=(8, 0))
        options.pack(fill="x")
        candidates = tk.BooleanVar(value=True)
        no_permit = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text="只显示站点少于20的星系", variable=candidates).pack(side="left")
        ttk.Checkbutton(options, text="只显示确认免许可的星系", variable=no_permit).pack(side="left", padx=8)
        ttk.Label(win, text="站点总数包含航母及地面站：<10 大概率有靠近主星的车位；10–19 大概率有车位。数据为 Spansh 已收录记录，实际车位以游戏为准。",
                  wraplength=1020, foreground="gray").pack(fill="x", padx=8, pady=6)
        status = tk.StringVar(value="输入参考星系后查询；双击结果复制星系名。")
        ttk.Label(win, textvariable=status, wraplength=1020).pack(fill="x", padx=8)
        columns = [("name", 210, "星系"), ("distance", 90, "距离 ly"),
                   ("stations", 90, "站点总数"), ("carriers", 80, "航母数"),
                   ("parking", 250, "车位判断"), ("permit", 80, "许可"),
                   ("age", 110, "星系记录年龄")]
        results_frame = ttk.Frame(win)
        results_frame.pack(fill="both", expand=True, padx=8, pady=6)
        tree = ttk.Treeview(results_frame, columns=[c for c, _, _ in columns], show="headings")
        for column, width, title in columns:
            tree.heading(column, text=title)
            tree.column(column, width=width)
        tree.tag_configure("主星附近", foreground="#16803c")
        tree.tag_configure("有车位", foreground="#996600")
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)
        stop = threading.Event()

        def copy_name(event=None):
            selected = tree.selection()
            if selected:
                win.clipboard_clear()
                win.clipboard_append(tree.item(selected[0], "values")[0])

        tree.bind("<Double-1>", copy_name)

        def export_rows():
            if not tree.get_children():
                messagebox.showinfo("提示", "暂无结果", parent=win)
                return
            path = filedialog.asksaveasfilename(parent=win, defaultextension=".csv",
                                                filetypes=[("CSV", "*.csv")])
            if path:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow([title for _, _, title in columns])
                    writer.writerows(tree.item(i, "values") for i in tree.get_children())

        def run():
            try:
                name, distance, limit = reference.get().strip(), float(radius.get()), int(pages.get())
                if not name or not 0 < distance <= 50 or limit < 1:
                    raise ValueError()
            except ValueError:
                messagebox.showwarning("参数错误", "请填参考星系、半径 (大于0且不超过50 ly) 和正整数页数", parent=win)
                return
            only, exclude = candidates.get(), no_permit.get()
            stop.clear()
            button["state"] = "disabled"
            tree.delete(*tree.get_children())
            status.set("查询中...")

            def work():
                try:
                    info, rows = eng.carrier_parking_search(
                        name, distance, candidates_only=only, exclude_permit=exclude,
                        max_pages=limit, stop=stop,
                        progress=lambda msg, detail=None: self._post(win, status.set, msg))

                    def show():
                        reference.set(info["reference"])
                        for row in rows:
                            permit = row.get("needs_permit")
                            tree.insert("", "end", tags=(row["_parking_category"],), values=(
                                row.get("name"), row["_parking_distance"],
                                row["_station_count"] if row["_station_count"] is not None else "未知",
                                row["_carrier_count"] if row["_carrier_count"] is not None else "未知",
                                row["_parking_label"], "需许可" if permit else ("免许可" if permit is False else "未知"),
                                data_age(row.get("updated_at"))))
                        state = "范围内分页已取完" if info["complete"] else "检索未完成，当前为部分结果"
                        status.set(f"{info['reference']} 周围 {info['radius']:g} ly：扫描 {info['scanned']} 个星系，显示 {len(rows)} 个；{state}。站点数据未知 {info['unknown']} 个。")
                        button["state"] = "normal"

                    self._post(win, show)
                except Exception as exc:
                    def failed(error=str(exc)):
                        status.set("查询失败")
                        button["state"] = "normal"
                        messagebox.showerror("查询失败", error, parent=win)
                    self._post(win, failed)

            threading.Thread(target=work, daemon=True).start()

        button = ttk.Button(controls, text="查找车位", command=run)
        button.pack(side="left", padx=6)
        ttk.Button(controls, text="停止", command=stop.set).pack(side="left")
        ttk.Button(controls, text="导出 CSV", command=export_rows).pack(side="left", padx=6)
        self.bind_tool_state("carrier_parking", win, dict(reference=reference, radius=radius,
                             pages=pages, candidates_only=candidates, exclude_permit=no_permit))
        def close():
            stop.set()
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", close)

    def midpoint_window(self):
        """两系中点工具: 输入 A、B, 找离中点最近的星系。"""
        win = tk.Toplevel(self.root)
        win.title("两系中点 - 离中点最近的星系")
        win.geometry("780x560")
        frm = ttk.Frame(win, padding=8)
        frm.pack(fill="x")
        ttk.Label(frm, text="A星系").grid(row=0, column=0, sticky="e")
        va = tk.StringVar(value="Sol")
        cba = ttk.Combobox(frm, textvariable=va, width=26)
        cba.grid(row=0, column=1, padx=4, pady=2)
        attach_system_suggest(cba, va)
        ttk.Label(frm, text="B星系").grid(row=0, column=2, sticky="e")
        vb = tk.StringVar(value="Shinrarta Dezhra")
        cbb = ttk.Combobox(frm, textvariable=vb, width=26)
        cbb.grid(row=0, column=3, padx=4, pady=2)
        attach_system_suggest(cbb, vb)
        ttk.Label(frm, text="要几条").grid(row=1, column=0, sticky="e")
        want = tk.StringVar(value="20")
        ttk.Entry(frm, textvariable=want, width=8).grid(row=1, column=1, sticky="w", padx=4)
        pop_only = tk.BooleanVar(value=False)
        no_permit = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="仅有人星系", variable=pop_only).grid(row=1, column=2)
        ttk.Checkbutton(frm, text="排除需许可", variable=no_permit).grid(row=1, column=3, sticky="w")
        btn = ttk.Button(frm, text="查找")
        btn.grid(row=1, column=4, padx=8)
        status = tk.StringVar(value="输入两星系名后点查找 (支持联想, 打错自动纠)。")
        ttk.Label(win, textvariable=status, foreground="gray").pack(fill="x", padx=8)
        cols = ("name", "dmid", "da", "db", "info")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=18)
        for c, w, t in [("name", 200, "星系"), ("dmid", 90, "距中点ly"),
                        ("da", 90, "距A ly"), ("db", 90, "距B ly"),
                        ("info", 280, "人口/阵营/许可")]:
            tree.heading(c, text=t)
            tree.column(c, width=w)
        tree.pack(fill="both", expand=True, padx=8, pady=4)

        def run():
            try:
                n = max(1, min(200, int(want.get())))
            except ValueError:
                messagebox.showwarning("提示", "要几条请填数字", parent=win)
                return
            if not va.get().strip() or not vb.get().strip():
                messagebox.showwarning("提示", "请填写 A、B 星系", parent=win)
                return
            btn["state"] = "disabled"
            status.set("查询中...")
            tree.delete(*tree.get_children())
            a, b = va.get(), vb.get()
            populated, exclude = pop_only.get(), no_permit.get()

            def work():
                try:
                    corr = []
                    info, rows = eng.midpoint_search(
                        a, b, want=n,
                        populated_only=populated,
                        exclude_permit=exclude, corrections=corr)

                    def show():
                        for r in rows:
                            permit = "需许可" if r.get("needs_permit") else "免许可"
                            tree.insert("", "end", values=(
                                r.get("name"), r.get("_d_mid"),
                                r.get("_d_a"), r.get("_d_b"),
                                f"pop {r.get('population')} | "
                                f"{r.get('allegiance')} | {permit}"))
                        va.set(info["a"])
                        vb.set(info["b"])
                        msg = (f"{info['a']} ↔ {info['b']} 相距 {info['ab']}ly, "
                               f"中点{info['mid']}, 找到 {len(rows)} 条")
                        if corr:
                            msg += "；" + "、".join(f"'{a}'→'{b}'" for a, b in corr) + "已自动纠正"
                        status.set(msg)
                        btn["state"] = "normal"
                    self._post(win, show)
                except Exception as e:
                    self._post(win, lambda error=str(e): (
                        messagebox.showerror("查找失败", error, parent=win),
                        status.set("失败"),
                        btn.__setitem__("state", "normal")))

            threading.Thread(target=work, daemon=True).start()

        btn["command"] = run
        self.bind_tool_state("midpoint", win, dict(a=va, b=vb, want=want,
                             populated_only=pop_only, exclude_permit=no_permit))

    def export(self):
        if not self.results:
            messagebox.showinfo("提示", "暂无结果, 先运行搜索")
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")])
        if not p:
            return
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["name", "system", "detail", "distances_json", "raw_json"])
            for r in self.results:
                w.writerow([r.get("name"), r.get("system_name") or r.get("name"),
                            f"{r.get('type', '')} {r.get('primary_economy', '')}",
                            json.dumps(r.get("_distances", {}), ensure_ascii=False),
                            json.dumps(r, ensure_ascii=False)[:8000]])
        self.status.set(f"已导出 {p}")


if __name__ == "__main__":
    if "--session-test" in sys.argv:
        from exe_session_test import run
        index = sys.argv.index("--session-test")
        if index + 2 >= len(sys.argv):
            raise SystemExit("--session-test requires write/read and a JSON report path")
        raise SystemExit(run(sys.modules[__name__], sys.argv[index + 1], sys.argv[index + 2]))
    if "--smoke-test" in sys.argv:
        from exe_smoke_test import run
        index = sys.argv.index("--smoke-test")
        if index + 1 >= len(sys.argv):
            raise SystemExit("--smoke-test requires a JSON report path")
        raise SystemExit(run(sys.modules[__name__], sys.argv[index + 1]))
    root = tk.Tk()
    App(root)
    root.mainloop()
