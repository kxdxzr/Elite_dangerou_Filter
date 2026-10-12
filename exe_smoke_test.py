"""离线验证实际打包程序能创建主界面、加载辅助窗口和内置候选。"""
import json
import os
import sys
import time


def run(gui, report_path):
    report = {"ok": False, "frozen": bool(getattr(sys, "frozen", False))}
    root = None
    try:
        import field_options as fo
        import powerplay_gui
        import rare_goods
        from runtime_paths import data_directory

        # 只验证加载和控件，不发起网络查询。
        fo.prefetch_common = lambda *args, **kwargs: None
        fo.get_options = lambda kind, field: list(fo.BUNDLED_OPTIONS.get(f"{kind}/{field}", []))
        root = gui.tk.Tk()
        root.withdraw()
        callback_errors = []
        root.report_callback_exception = lambda *args: callback_errors.append(str(args[1]))
        app = gui.App(root)
        root.withdraw()
        app.clear()
        row = gui.Row(app.inner, "stations")
        row.field.set(gui.field_label("stations", "modules"))
        row.val.set("Fuel Scoop")
        row.refresh_options()
        assert tuple(row.ent_class["values"]) == tuple(str(i) for i in range(1, 9))
        assert tuple(row.ent_rating["values"]) == tuple("ABCDE")
        window = powerplay_gui.open_window(app, gui.data_age)
        assert window.title() == "稀有商品目标查找器"
        app.carrier_parking_window()
        app.midpoint_window()
        end = time.monotonic() + 0.3
        while time.monotonic() < end:
            root.update()
            time.sleep(0.01)
        assert not callback_errors, callback_errors
        assert len(rare_goods.GOODS) == 142
        assert len(rare_goods.SOURCE_SYSTEMS) == 138
        assert len(fo.BUNDLED_OPTIONS["stations/modules"]) == 153
        report.update(ok=True, data_directory=data_directory(), session_file=gui.SESSION_FILE,
                      cache_file=fo.CACHE_FILE, specs_file=fo.SPECS_FILE,
                      goods=142, sources=138, modules=153,
                      windows=[w.title() for w in root.winfo_children() if isinstance(w, gui.tk.Toplevel)])
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if root is not None:
            root.destroy()
        # 调用者提供已存在的报告目录；不向单文件解包目录写入用户数据。
        with open(os.path.abspath(report_path), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    return 0 if report["ok"] else 1
