"""Tray icon + settings window."""
import ctypes
import logging
import queue
import sys
import threading
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

import pystray
from PIL import Image, ImageDraw, ImageTk

from . import __version__, autostart
from .audio import STYLES
from .effects import EFFECTS
from .engine import MODES, Engine
from .settings import Settings, app_dir

log = logging.getLogger(__name__)


def make_icon(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stops = [(255, 60, 60), (255, 180, 0), (60, 220, 120), (60, 140, 255), (200, 80, 255)]
    for i, c in enumerate(stops):  # glow ring
        a0 = i * 360 / len(stops)
        d.arc((4, 4, size - 4, size - 4), a0, a0 + 360 / len(stops), fill=c, width=size // 8)
    d.rounded_rectangle((size * 0.28, size * 0.3, size * 0.72, size * 0.62), radius=3, fill=(30, 30, 36))
    return img


def single_instance():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.restype = ctypes.c_void_p
    handle = k32.CreateMutexW(None, False, "Local\\EvniaAmbiglow")
    return handle if ctypes.get_last_error() != 183 else None  # ERROR_ALREADY_EXISTS


class App:
    def __init__(self, start_hidden):
        self.settings = Settings()
        self.engine = Engine(self.settings)
        self.engine.start()
        self.events = queue.Queue()
        self._save_job = None

        self.root = tk.Tk()
        self.root.title("Evnia Ambiglow")
        self.root.resizable(False, False)
        self.icon_img = make_icon()
        self.root.iconphoto(True, ImageTk.PhotoImage(self.icon_img))
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._build()
        if start_hidden:
            self.root.withdraw()

        self.tray = pystray.Icon("EvniaAmbiglow", self.icon_img, "Evnia Ambiglow", self._tray_menu())
        self.tray.run_detached()
        self.root.after(100, self._poll)
        self.root.after(500, self._refresh_status)

    # --- UI ------------------------------------------------------------------
    def _build(self):
        s = self.settings
        pad = {"padx": 12, "pady": 4}
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both")

        head = ttk.Frame(main)
        head.pack(fill="x", **pad)
        ttk.Label(head, text="Evnia Ambiglow", font=("Segoe UI Semibold", 14)).pack(side="left")
        ttk.Label(head, text=f"v{__version__}", foreground="#888").pack(side="left", padx=6, pady=(4, 0))
        self.status = ttk.Label(main, text="", foreground="#666")
        self.status.pack(fill="x", **pad)

        mode_box = ttk.LabelFrame(main, text="Mode", padding=8)
        mode_box.pack(fill="x", **pad)
        self.mode_var = tk.StringVar(value=s.get("mode"))
        for i, (key, label) in enumerate(MODES.items()):
            ttk.Radiobutton(mode_box, text=label, value=key, variable=self.mode_var,
                            command=self._mode_changed).grid(row=i // 3, column=i % 3, sticky="w", padx=6, pady=2)

        gen = ttk.Frame(main)
        gen.pack(fill="x", **pad)
        self._scale(gen, "Brightness", "brightness", 0, 100, 100, "{:.0f}%")

        self.frames = {}
        f = self.frames["screen"] = ttk.LabelFrame(main, text="Follow screen", padding=8)
        self._scale(f, "Saturation", "saturation", 0, 200, 100, "{:.0f}%")
        self._scale(f, "Smoothing", "smoothing_ms", 0, 100, 1, "{:.0f} ms")
        self._scale(f, "Black level", "black_level", 0, 40, 1, "{:.0f}")
        self._scale(f, "Sampling area", "spread", 4, 30, 100, "{:.0f}%")
        row = ttk.Frame(f)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text="Display", width=14).pack(side="left")
        out_var = tk.IntVar(value=s.get("output"))
        ttk.Spinbox(row, from_=0, to=5, width=4, textvariable=out_var,
                    command=lambda: self._set("output", out_var.get())).pack(side="left")
        ttk.Label(row, text="(0 = main display)", foreground="#888").pack(side="left", padx=6)

        f = self.frames["color"] = ttk.LabelFrame(main, text="Color", padding=8)
        row = ttk.Frame(f)
        row.pack(fill="x")
        self.swatch = tk.Label(row, width=6, bg=s.get("color"), relief="groove")
        self.swatch.pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Pick color...", command=self._pick_color).pack(side="left")

        f = self.frames["effect"] = ttk.LabelFrame(main, text="Effect", padding=8)
        self._choice(f, "Effect", "effect", EFFECTS)
        self._scale(f, "Speed", "effect_speed", 10, 300, 100, "{:.1f}x", shown_scale=0.01)

        f = self.frames["music"] = ttk.LabelFrame(main, text="Music", padding=8)
        self._choice(f, "Style", "music_style", STYLES)
        self._scale(f, "Sensitivity", "music_sensitivity", 30, 300, 100, "{:.1f}x", shown_scale=0.01)
        ttk.Label(f, text="Reacts to whatever your PC is playing (default output device).",
                  foreground="#888").pack(anchor="w", pady=(4, 0))

        self.frame_anchor = ttk.Frame(main)
        self.frame_anchor.pack(fill="x")

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", padx=12, pady=(8, 0))
        self.auto_var = tk.BooleanVar(value=autostart.is_enabled())
        ttk.Checkbutton(bottom, text="Start with Windows", variable=self.auto_var,
                        command=self._autostart_changed).pack(side="left")
        ttk.Button(bottom, text="Quit", command=self.quit).pack(side="right")
        ttk.Button(bottom, text="Hide to tray", command=self.hide).pack(side="right", padx=6)
        self.bottom = bottom
        self._show_mode_frames()

    def _scale(self, parent, label, key, lo, hi, factor, fmt, shown_scale=None):
        """Slider for settings[key]; slider value = setting * factor."""
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        var = tk.DoubleVar(value=self.settings.get(key) * factor)
        value = ttk.Label(row, width=7, anchor="e")
        shown = shown_scale if shown_scale is not None else 1

        def changed(*_):
            value.configure(text=fmt.format(var.get() * shown))
            self._set(key, var.get() / factor)

        ttk.Scale(row, from_=lo, to=hi, variable=var, length=220,
                  command=lambda _v: changed()).pack(side="left", padx=4)
        value.pack(side="left")
        value.configure(text=fmt.format(var.get() * shown))

    def _choice(self, parent, label, key, options):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=14).pack(side="left")
        keys, labels = list(options), list(options.values())
        current = self.settings.get(key)
        var = tk.StringVar(value=options.get(current, labels[0]))
        box = ttk.Combobox(row, values=labels, textvariable=var, state="readonly", width=22)
        box.pack(side="left", padx=4)
        box.bind("<<ComboboxSelected>>", lambda _e: self._set(key, keys[labels.index(var.get())]))

    def _show_mode_frames(self):
        mode = self.settings.get("mode")
        wanted = {"screen": ["screen"], "static": ["color"], "effect": ["effect", "color"],
                  "music": ["music", "color"]}.get(mode, [])
        for f in self.frames.values():
            f.pack_forget()
        for name in wanted:
            self.frames[name].pack(fill="x", padx=12, pady=4, before=self.frame_anchor)

    # --- actions ---------------------------------------------------------------
    def _set(self, key, value):
        self.settings.set(key, value)
        if self._save_job:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(500, self.settings.save)

    def _mode_changed(self):
        self._set("mode", self.mode_var.get())
        self._show_mode_frames()
        self.tray.update_menu()

    def _pick_color(self):
        _, hex_color = colorchooser.askcolor(self.settings.get("color"), parent=self.root,
                                             title="Ambiglow color")
        if hex_color:
            self.swatch.configure(bg=hex_color)
            self._set("color", hex_color)

    def _autostart_changed(self):
        try:
            autostart.set_enabled(self.auto_var.get())
        except OSError as e:
            messagebox.showerror("Evnia Ambiglow", f"Could not change autostart:\n{e}")
            self.auto_var.set(autostart.is_enabled())

    def _refresh_status(self):
        self.status.configure(text=self.engine.status)
        self.root.after(500, self._refresh_status)

    # --- tray ------------------------------------------------------------------
    def _tray_menu(self):
        items = [pystray.MenuItem("Settings", lambda: self.events.put(("show",)), default=True),
                 pystray.Menu.SEPARATOR]
        def select(key):  # pystray rejects callbacks with extra (default) parameters
            return lambda _icon, _item: self.events.put(("mode", key))

        def is_selected(key):
            return lambda _item: self.settings.get("mode") == key

        for key, label in MODES.items():
            items.append(pystray.MenuItem(label, select(key), checked=is_selected(key), radio=True))
        items += [pystray.Menu.SEPARATOR, pystray.MenuItem("Quit", lambda: self.events.put(("quit",)))]
        return pystray.Menu(*items)

    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                if ev[0] == "show":
                    self.show()
                elif ev[0] == "mode":
                    self.mode_var.set(ev[1])
                    self._mode_changed()
                elif ev[0] == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self):
        self.root.withdraw()

    def quit(self):
        self.settings.save()
        self.engine.stop()
        self.tray.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def setup_logging():
    logging.basicConfig(filename=app_dir() / "log.txt", level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    sys.excepthook = lambda *exc: log.error("uncaught", exc_info=exc)
    threading.excepthook = lambda a: log.error("thread %s crashed", a.thread, exc_info=(a.exc_type, a.exc_value, a.exc_traceback))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    setup_logging()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp UI on high-DPI screens
    except (AttributeError, OSError):
        pass
    mutex = single_instance()
    if not mutex:
        messagebox.showinfo("Evnia Ambiglow", "Evnia Ambiglow is already running (see the tray icon).")
        return
    log.info("starting v%s", __version__)
    App(start_hidden="--tray" in argv).run()
