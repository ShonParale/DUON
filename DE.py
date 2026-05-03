import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import socket
import threading
import time
import math
import json
import os
from collections import deque

CONFIG_FILE = "robot_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"ip1": "192.168.1.159", "ip2": "192.168.1.162"}

def save_config(ip1, ip2):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"ip1": ip1, "ip2": ip2}, f)
    except:
        pass

BG     = "#1a1a2e"
CARD   = "#16213e"
ACCENT = "#0f3460"
GREEN  = "#27ae60"
RED    = "#e74c3c"
CYAN   = "#00d4ff"
FG     = "#e0e0e0"
ORANGE = "#f39c12"
YELLOW = "#f1c40f"
DARK   = "#0d0d0d"
PURPLE = "#9b59b6"


class SonarProcessor:
    WINDOW      = 7
    SPIKE_RATIO = 1.8
    SPIKE_ABS   = 40
    JITTER_GATE = 3.0
    MAX_VALID   = 380.0
    MIN_VALID   = 2.0

    def __init__(self):
        self._buf    = deque(maxlen=self.WINDOW)
        self._stable = None

    def feed(self, raw_cm):
        if raw_cm < self.MIN_VALID or raw_cm > self.MAX_VALID:
            raw_cm = self.MAX_VALID
        if self._stable is not None:
            jump  = abs(raw_cm - self._stable)
            ratio = raw_cm / max(self._stable, 1)
            if jump > self.SPIKE_ABS and (ratio > self.SPIKE_RATIO or ratio < 1 / self.SPIKE_RATIO):
                return self._stable, False
        self._buf.append(raw_cm)
        median = sorted(self._buf)[len(self._buf) // 2]
        if self._stable is None:
            self._stable = median
            return median, True
        if abs(median - self._stable) < self.JITTER_GATE:
            return self._stable, False
        self._stable = median
        return median, True

    def reset(self):
        self._buf.clear()
        self._stable = None


def make_log_box(parent, height=8):
    frame = tk.Frame(parent, bg=CARD, highlightbackground=ACCENT, highlightthickness=2)
    box = scrolledtext.ScrolledText(frame, font=("Courier", 8), bg=DARK,
                                    fg="#00ff88", insertbackground="#00ff88",
                                    state=tk.DISABLED, height=height)
    box.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
    return frame, box

def append_log(box, msg):
    ts = time.strftime("%H:%M:%S")
    box.config(state=tk.NORMAL)
    box.insert(tk.END, f"[{ts}] {msg}\n")
    box.see(tk.END)
    box.config(state=tk.DISABLED)

def clear_log_box(box):
    box.config(state=tk.NORMAL)
    box.delete(1.0, tk.END)
    box.config(state=tk.DISABLED)

def copy_log_box(box):
    try:
        content = box.get(1.0, tk.END).strip()
        box.clipboard_clear()
        box.clipboard_append(content)
    except:
        pass

def log_btn_row(parent, box):
    row = tk.Frame(parent, bg=BG)
    row.pack(fill=tk.X, pady=(2, 0))
    tk.Button(row, text="Copy", command=lambda: copy_log_box(box),
              font=("Arial", 8), bg=ACCENT, fg=FG,
              relief=tk.FLAT, cursor="hand2", padx=6).pack(side=tk.RIGHT, padx=(2, 0))
    tk.Button(row, text="Clear", command=lambda: clear_log_box(box),
              font=("Arial", 8), bg=ACCENT, fg=FG,
              relief=tk.FLAT, cursor="hand2", padx=6).pack(side=tk.RIGHT)


class AutoMapper:
    FRONT_THRESHOLD = 35
    DIAG_THRESHOLD  = 25
    PULSE_MS        = 400
    TURN_MS         = 480
    SETTLE_MS       = 350
    CM_PER_PIXEL    = 2
    SPEED_CM_S      = 18.0

    def __init__(self, parent_frame, controller):
        self.ctrl    = controller
        self.frame   = parent_frame
        self.running = False
        self.auto_thread = None

        self.bot_x = self.bot_y = self.heading = 0.0

        self._raw_L = self._raw_F = self._raw_R = 400.0
        self._filt_L = self._filt_F = self._filt_R = 400.0
        self._proc_L = SonarProcessor()
        self._proc_F = SonarProcessor()
        self._proc_R = SonarProcessor()
        self._sonar_fresh = threading.Event()

        self._wall_world = set()
        self._free_world = set()
        self._path_world = []

        self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0
        self._drag_start = None
        self._bot_marker = self._heading_line = None

        self._build_ui()

    def _build_ui(self):
        self.frame.configure(bg=BG)

        top_bar = tk.Frame(self.frame, bg=ACCENT, height=38)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)
        tk.Label(top_bar, text="SONAR MAPPER", font=("Arial", 12, "bold"),
                 bg=ACCENT, fg=CYAN).pack(side=tk.LEFT, padx=12, pady=6)
        self.run_btn = tk.Button(top_bar, text="▶ START", font=("Arial", 10, "bold"),
                                 width=12, bg=GREEN, fg="white", relief=tk.FLAT,
                                 cursor="hand2", command=self.toggle_mapping)
        self.run_btn.pack(side=tk.LEFT, padx=6, pady=4)
        tk.Button(top_bar, text="🗑 Clear", font=("Arial", 9), bg=ACCENT, fg=FG,
                  relief=tk.FLAT, cursor="hand2", command=self.clear_map
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(top_bar, text="⟳ Reset View", font=("Arial", 9), bg=ACCENT, fg=FG,
                  relief=tk.FLAT, cursor="hand2", command=self._reset_view
                  ).pack(side=tk.LEFT, padx=2)
        self.map_status = tk.Label(top_bar, text="● IDLE", font=("Arial", 10, "bold"),
                                   bg=ACCENT, fg="#aaa")
        self.map_status.pack(side=tk.LEFT, padx=10)
        self.zoom_lbl = tk.Label(top_bar, text="Zoom: 1.0×", font=("Arial", 8),
                                 bg=ACCENT, fg=FG)
        self.zoom_lbl.pack(side=tk.RIGHT, padx=10)

        body = tk.Frame(self.frame, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(body, bg=BG, width=210)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        canvas_area = tk.Frame(body, bg=BG)
        canvas_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 4), pady=4)

        self._build_left_panel(left)
        self._build_canvas(canvas_area)

    def _build_left_panel(self, parent):
        scroll_frame = tk.Frame(parent, bg=BG)
        scroll_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_frame, bg=BG, highlightthickness=0)
        vbar = tk.Scrollbar(scroll_frame, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

        def sec(t):
            tk.Label(inner, text=t, font=("Arial", 8, "bold"), bg=BG, fg=CYAN
                     ).pack(anchor="w", pady=(8, 1), padx=4)
            tk.Frame(inner, bg=ACCENT, height=1).pack(fill=tk.X, padx=4)

        sec("MOVEMENT MODE")
        self.mode_var = tk.StringVar(value="pulse")
        for v, t in [("pulse", "Pulse (stop→scan)"), ("smooth", "Smooth (continuous)")]:
            tk.Radiobutton(inner, text=t, variable=self.mode_var, value=v,
                           font=("Arial", 8), bg=BG, fg=FG, selectcolor=ACCENT,
                           activebackground=BG, activeforeground=CYAN
                           ).pack(anchor="w", padx=8, pady=1)

        def slider_row(lbl_txt, var, from_, to_, default, color, suffix, resolution=1):
            sec(lbl_txt)
            row = tk.Frame(inner, bg=BG); row.pack(fill=tk.X, padx=4)
            lbl = tk.Label(row, text=f"{default}{suffix}", font=("Arial", 8, "bold"),
                           bg=BG, fg=color, width=6)
            lbl.pack(side=tk.RIGHT)
            tk.Scale(row, from_=from_, to=to_, orient=tk.HORIZONTAL, variable=var,
                     bg=BG, fg=FG, highlightthickness=0, troughcolor=ACCENT, length=120,
                     resolution=resolution, showvalue=False,
                     command=lambda v, l=lbl, s=suffix: l.config(text=f"{float(v):.0f}{s}")
                     ).pack(side=tk.LEFT)

        self.pulse_var     = tk.IntVar(value=self.PULSE_MS)
        self.turn_var      = tk.IntVar(value=self.TURN_MS)
        self.front_thr_var = tk.IntVar(value=self.FRONT_THRESHOLD)
        self.diag_thr_var  = tk.IntVar(value=self.DIAG_THRESHOLD)
        self.jitter_var    = tk.DoubleVar(value=SonarProcessor.JITTER_GATE)

        slider_row("PULSE (ms)",     self.pulse_var,     150, 900, self.PULSE_MS,        ORANGE, "ms")
        slider_row("TURN (ms)",      self.turn_var,      250, 900, self.TURN_MS,         ORANGE, "ms")
        slider_row("FRONT THR (cm)", self.front_thr_var, 10,  80,  self.FRONT_THRESHOLD, RED,    "cm")
        slider_row("DIAG THR (cm)",  self.diag_thr_var,  10,  60,  self.DIAG_THRESHOLD,  RED,    "cm")

        sec("NOISE GATE (cm)")
        jrow = tk.Frame(inner, bg=BG); jrow.pack(fill=tk.X, padx=4)
        self.jitter_lbl = tk.Label(jrow, text=f"{SonarProcessor.JITTER_GATE:.1f}cm",
                                   font=("Arial", 8, "bold"), bg=BG, fg=ORANGE, width=6)
        self.jitter_lbl.pack(side=tk.RIGHT)
        tk.Scale(jrow, from_=1, to=15, resolution=0.5, orient=tk.HORIZONTAL,
                 variable=self.jitter_var, bg=BG, fg=FG,
                 highlightthickness=0, troughcolor=ACCENT, length=120, showvalue=False,
                 command=self._on_jitter_change).pack(side=tk.LEFT)

        sec("SONAR  filtered / raw")
        sg = tk.Frame(inner, bg=BG); sg.pack(fill=tk.X, padx=4, pady=2)
        self._auto_sonar_lbls = {}
        self._raw_sonar_lbls  = {}
        for i, (tag, col) in enumerate([("L", CYAN), ("F", GREEN), ("R", CYAN)]):
            tk.Label(sg, text=tag, font=("Arial", 8, "bold"), bg=BG, fg=col, width=4
                     ).grid(row=0, column=i*2, padx=2)
            fl = tk.Label(sg, text="---", font=("Arial", 11, "bold"), bg=CARD, fg=FG, width=5)
            fl.grid(row=1, column=i*2, padx=2, pady=1)
            self._auto_sonar_lbls[tag] = fl
            rl = tk.Label(sg, text="---", font=("Arial", 8), bg=BG, fg="#666", width=5)
            rl.grid(row=2, column=i*2, padx=2)
            self._raw_sonar_lbls[tag] = rl

        sec("BOT POSE")
        pg = tk.Frame(inner, bg=BG); pg.pack(fill=tk.X, padx=4, pady=2)
        for i, (tag, attr) in enumerate([("X cm", "pose_x"), ("Y cm", "pose_y"), ("HDG°", "pose_h")]):
            tk.Label(pg, text=tag, font=("Arial", 7), bg=BG, fg="#aaa", width=5
                     ).grid(row=0, column=i, padx=3)
            lbl = tk.Label(pg, text="0", font=("Arial", 10, "bold"), bg=CARD, fg=FG, width=5)
            lbl.grid(row=1, column=i, padx=3, pady=1)
            setattr(self, f"{attr}_lbl", lbl)

        sec("AUTO LOG")
        log_frame, self.auto_log = make_log_box(inner, height=7)
        log_frame.pack(fill=tk.X, padx=4, pady=(2, 0))
        log_btn_row(inner, self.auto_log)

    def _build_canvas(self, parent):
        hint = tk.Frame(parent, bg=BG)
        hint.pack(fill=tk.X)
        tk.Label(hint, text="Scroll=Zoom  |  Drag=Pan  |  Double-click=Reset View",
                 font=("Arial", 7), bg=BG, fg="#555").pack(side=tk.LEFT)

        c_frame = tk.Frame(parent, bg=CARD, highlightbackground=ACCENT, highlightthickness=2)
        c_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(c_frame, bg="#0a0a1a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        legend = tk.Frame(parent, bg=BG)
        legend.pack(fill=tk.X, pady=(2, 0))
        for colour, text in [("#e74c3c", "● Wall"), ("#00d4ff", "● Path"),
                              (YELLOW, "◆ Bot"), ("#1a5c35", "● Free space")]:
            tk.Label(legend, text=text, font=("Arial", 8), bg=BG, fg=colour
                     ).pack(side=tk.LEFT, padx=8)

        self.canvas.bind("<MouseWheel>",      self._on_mousewheel)
        self.canvas.bind("<Button-4>",        self._on_scroll_up)
        self.canvas.bind("<Button-5>",        self._on_scroll_down)
        self.canvas.bind("<ButtonPress-1>",   self._on_pan_start)
        self.canvas.bind("<B1-Motion>",       self._on_pan_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_pan_end)
        self.canvas.bind("<Double-Button-1>", lambda e: self._reset_view())
        self.canvas.bind("<Configure>",       lambda e: self._redraw_all())

    def _on_jitter_change(self, val):
        v = float(val)
        self.jitter_lbl.config(text=f"{v:.1f}cm")
        for p in (self._proc_L, self._proc_F, self._proc_R):
            p.JITTER_GATE = v

    def _on_mousewheel(self, e):   self._apply_zoom(1.1 if e.delta > 0 else 0.9, e.x, e.y)
    def _on_scroll_up(self, e):    self._apply_zoom(1.1, e.x, e.y)
    def _on_scroll_down(self, e):  self._apply_zoom(0.9, e.x, e.y)

    def _apply_zoom(self, factor, cx, cy):
        nz = max(0.2, min(8.0, self._zoom * factor))
        if nz == self._zoom: return
        r = nz / self._zoom
        self._pan_x = cx - r * (cx - self._pan_x)
        self._pan_y = cy - r * (cy - self._pan_y)
        self._zoom  = nz
        self.zoom_lbl.config(text=f"Zoom: {self._zoom:.1f}×")
        self._redraw_all()

    def _on_pan_start(self, e): self._drag_start = (e.x, e.y)
    def _on_pan_end(self, e):   self._drag_start = None

    def _on_pan_drag(self, e):
        if not self._drag_start: return
        self._pan_x += e.x - self._drag_start[0]
        self._pan_y += e.y - self._drag_start[1]
        self._drag_start = (e.x, e.y)
        self._redraw_all()

    def _reset_view(self):
        self._zoom = 1.0; self._pan_x = self._pan_y = 0.0
        self.zoom_lbl.config(text="Zoom: 1.0×")
        self._redraw_all()

    def _cw(self): return self.canvas.winfo_width()  or 600
    def _ch(self): return self.canvas.winfo_height() or 500

    def _world_to_canvas(self, wx, wy):
        W, H = self._cw(), self._ch()
        bx = W/2 + wx / self.CM_PER_PIXEL
        by = H/2 - wy / self.CM_PER_PIXEL
        cx = (bx - W/2) * self._zoom + W/2 + self._pan_x
        cy = (by - H/2) * self._zoom + H/2 + self._pan_y
        return cx, cy

    def _project_point(self, dist_cm, angle_offset_deg):
        ar = math.radians(self.heading + angle_offset_deg)
        return self.bot_x + dist_cm * math.sin(ar), self.bot_y + dist_cm * math.cos(ar)

    def _redraw_all(self):
        self.canvas.delete("all")
        self._draw_grid()
        for (wx, wy) in self._wall_world:
            cx, cy = self._world_to_canvas(wx, wy)
            self.canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill="#e74c3c", outline="")
        for (wx, wy) in self._free_world:
            cx, cy = self._world_to_canvas(wx, wy)
            self.canvas.create_oval(cx-1, cy-1, cx+1, cy+1, fill="#1a5c35", outline="")
        for (wx, wy) in self._path_world:
            cx, cy = self._world_to_canvas(wx, wy)
            self.canvas.create_oval(cx-2, cy-2, cx+2, cy+2, fill="#00d4ff", outline="")
        self._bot_marker = self._heading_line = None
        self._update_bot_marker()

    def _draw_grid(self):
        W, H = self._cw(), self._ch()
        ox = W/2 + self._pan_x
        oy = H/2 + self._pan_y
        for step_cm, col in [(50, "#1a1a3a"), (100, "#1e1e4a")]:
            sp = (step_cm / self.CM_PER_PIXEL) * self._zoom
            x = ox % sp - sp
            while x < W:
                self.canvas.create_line(x, 0, x, H, fill=col, width=1); x += sp
            y = oy % sp - sp
            while y < H:
                self.canvas.create_line(0, y, W, y, fill=col, width=1); y += sp
        self.canvas.create_line(ox, 0, ox, H, fill="#0f3460", width=2)
        self.canvas.create_line(0, oy, W, oy, fill="#0f3460", width=2)
        self.canvas.create_oval(ox-4, oy-4, ox+4, oy+4, fill=YELLOW, outline="")
        sp = (100 / self.CM_PER_PIXEL) * self._zoom
        self.canvas.create_line(10, H-18, 10+sp, H-18, fill="#334", width=2)
        self.canvas.create_text(10+sp/2, H-6, anchor="s", text="100cm", fill="#334", font=("Arial", 7))

    def _plot_wall(self, wx, wy):
        key = (round(wx / 4) * 4, round(wy / 4) * 4)
        if key not in self._wall_world:
            self._wall_world.add(key)
            cx, cy = self._world_to_canvas(*key)
            self.canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill="#e74c3c", outline="")

    def _plot_free(self, wx, wy):
        key = (round(wx / 6) * 6, round(wy / 6) * 6)
        if key not in self._free_world and key not in self._wall_world:
            self._free_world.add(key)
            cx, cy = self._world_to_canvas(*key)
            self.canvas.create_oval(cx-1, cy-1, cx+1, cy+1, fill="#1a5c35", outline="")

    def _plot_path(self, wx, wy):
        self._path_world.append((wx, wy))
        cx, cy = self._world_to_canvas(wx, wy)
        self.canvas.create_oval(cx-2, cy-2, cx+2, cy+2, fill="#00d4ff", outline="")

    def _update_bot_marker(self):
        cx, cy = self._world_to_canvas(self.bot_x, self.bot_y)
        r = max(5, int(7 * self._zoom))
        if self._bot_marker:   self.canvas.delete(self._bot_marker)
        if self._heading_line: self.canvas.delete(self._heading_line)
        pts = [cx, cy-r, cx+r, cy, cx, cy+r, cx-r, cy]
        self._bot_marker = self.canvas.create_polygon(pts, fill=YELLOW, outline="#fff", width=1)
        ar = math.radians(self.heading)
        al = max(16, int(20 * self._zoom))
        self._heading_line = self.canvas.create_line(
            cx, cy, cx + al * math.sin(ar), cy - al * math.cos(ar),
            fill=YELLOW, width=2, arrow=tk.LAST)
        self.pose_x_lbl.config(text=f"{self.bot_x:.0f}")
        self.pose_y_lbl.config(text=f"{self.bot_y:.0f}")
        self.pose_h_lbl.config(text=f"{self.heading % 360:.0f}°")

    def _scan_and_plot(self):
        L, F, R = self._filt_L, self._filt_F, self._filt_R
        def _draw():
            for dist, angle in [(L, -45), (F, 0), (R, 45)]:
                if dist < 399:
                    self._plot_wall(*self._project_point(dist, angle))
                    for d in range(20, int(dist) - 10, 20):
                        self._plot_free(*self._project_point(d, angle))
            self._update_bot_marker()
        self.ctrl.root.after(0, _draw)

    def _move_forward_pulse(self):
        ms = self.pulse_var.get()
        self.ctrl._send_raw("W"); time.sleep(ms / 1000)
        self.ctrl._send_raw("X"); time.sleep(self.SETTLE_MS / 1000)
        ar = math.radians(self.heading)
        d  = (ms / 1000) * self.SPEED_CM_S
        self.bot_x += d * math.sin(ar); self.bot_y += d * math.cos(ar)
        self.ctrl.root.after(0, lambda: self._plot_path(self.bot_x, self.bot_y))

    def _turn(self, direction):
        ms = self.turn_var.get()
        self.ctrl._send_raw("A" if direction == "L" else "D")
        time.sleep(ms / 1000)
        self.ctrl._send_raw("X"); time.sleep(self.SETTLE_MS / 1000)
        self.heading = (self.heading + (90 if direction == "R" else -90)) % 360

    def _uturn(self): self._turn("R"); self._turn("R")

    def _alog(self, msg):
        self.ctrl.root.after(0, lambda: append_log(self.auto_log, msg))

    def _wait_fresh_sonar(self, timeout=2.0):
        self._sonar_fresh.clear(); self._sonar_fresh.wait(timeout=timeout)

    def _nav_step_pulse(self):
        self._wait_fresh_sonar()
        L, F, R = self._filt_L, self._filt_F, self._filt_R
        ft, dt  = self.front_thr_var.get(), self.diag_thr_var.get()
        self._scan_and_plot()
        if F > ft and L > dt and R > dt:
            self._alog(f"FWD F={F:.0f} L={L:.0f} R={R:.0f}")
            self._move_forward_pulse()
        elif F > ft and R <= dt:
            self._alog(f"PRE-TURN L R={R:.0f}"); self._turn("L")
        elif F > ft and L <= dt:
            self._alog(f"PRE-TURN R L={L:.0f}"); self._turn("R")
        elif F <= ft:
            if R > ft:   self._alog(f"TURN R F={F:.0f}"); self._turn("R")
            elif L > ft: self._alog(f"TURN L F={F:.0f}"); self._turn("L")
            else:        self._alog(f"U-TURN"); self._uturn()

    def _nav_step_smooth(self):
        L, F, R = self._filt_L, self._filt_F, self._filt_R
        ft, dt  = self.front_thr_var.get(), self.diag_thr_var.get()
        self._scan_and_plot()
        if F <= ft:
            self.ctrl._send_raw("X"); time.sleep(0.15)
            self._turn("R" if R > L else "L"); self.ctrl._send_raw("W")
        elif R <= dt:
            self.ctrl._send_raw("X"); time.sleep(0.1)
            self._turn("L"); self.ctrl._send_raw("W")
        elif L <= dt:
            self.ctrl._send_raw("X"); time.sleep(0.1)
            self._turn("R"); self.ctrl._send_raw("W")
        else:
            dt_s = 0.12
            ar = math.radians(self.heading)
            self.bot_x += dt_s * self.SPEED_CM_S * math.sin(ar)
            self.bot_y += dt_s * self.SPEED_CM_S * math.cos(ar)
            self.ctrl.root.after(0, lambda: self._plot_path(self.bot_x, self.bot_y))
            time.sleep(dt_s)

    def _auto_loop(self):
        self._alog("=== MAPPING STARTED ===")
        if self.mode_var.get() == "smooth": self.ctrl._send_raw("W")
        while self.running:
            try:
                if self.mode_var.get() == "pulse": self._nav_step_pulse()
                else: self._nav_step_smooth()
            except Exception as e:
                self._alog(f"[ERR] {e}"); time.sleep(0.5)
        self.ctrl._send_raw("X")
        self._alog("=== MAPPING STOPPED ===")

    def toggle_mapping(self):
        if not self.running:
            if not (self.ctrl.conn1 and self.ctrl.conn2):
                messagebox.showwarning("Not Connected", "Connect BOTH ESP32s first.")
                return
            self.running = True
            self.run_btn.config(text="■ STOP", bg=RED)
            self.map_status.config(text="● MAPPING", fg=GREEN)
            self.auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
            self.auto_thread.start()
        else:
            self.running = False
            self.run_btn.config(text="▶ START", bg=GREEN)
            self.map_status.config(text="● IDLE", fg="#aaa")

    def update_sonar(self, raw_L, raw_F, raw_R):
        fL, _ = self._proc_L.feed(raw_L)
        fF, _ = self._proc_F.feed(raw_F)
        fR, _ = self._proc_R.feed(raw_R)
        self._raw_L, self._raw_F, self._raw_R     = raw_L, raw_F, raw_R
        self._filt_L, self._filt_F, self._filt_R  = fL, fF, fR
        self._sonar_fresh.set()
        def _fmt(v): return "---" if v >= 399 else f"{v:.0f}"
        def _r():
            self._auto_sonar_lbls["L"].config(text=_fmt(fL))
            self._auto_sonar_lbls["F"].config(text=_fmt(fF))
            self._auto_sonar_lbls["R"].config(text=_fmt(fR))
            self._raw_sonar_lbls["L"].config(text=_fmt(raw_L))
            self._raw_sonar_lbls["F"].config(text=_fmt(raw_F))
            self._raw_sonar_lbls["R"].config(text=_fmt(raw_R))
            if not self.running: self._update_bot_marker()
        self.ctrl.root.after(0, _r)

    def clear_map(self):
        self.canvas.delete("all")
        self._wall_world = set()
        self._free_world = set()
        self._path_world = []
        self.bot_x = self.bot_y = self.heading = 0.0
        self._bot_marker = self._heading_line = None
        for p in (self._proc_L, self._proc_F, self._proc_R): p.reset()
        self._draw_grid()
        self._update_bot_marker()
        append_log(self.auto_log, "Map cleared.")

    def stop(self): self.running = False


class EncoderPage:
    PPR         = 20
    WHEEL_CIRC  = 21.0
    TRACK_WIDTH = 15.0

    def __init__(self, parent_frame, controller):
        self.ctrl  = controller
        self.frame = parent_frame

        self._counts   = [0, 0, 0, 0]
        self._prev_counts = [0, 0, 0, 0]
        self._speeds   = [0.0, 0.0, 0.0, 0.0]
        self._dist     = [0.0, 0.0, 0.0, 0.0]
        self._dirs     = ["---", "---", "---", "---"]
        self._total_dist = [0.0, 0.0, 0.0, 0.0]
        self._lock     = threading.Lock()

        self._last_ts  = [time.time()] * 4
        self._speed_buf = [deque(maxlen=5) for _ in range(4)]

        self._update_running = True
        self._build_ui()
        self._schedule_update()

    def _build_ui(self):
        self.frame.configure(bg=BG)

        top = tk.Frame(self.frame, bg=ACCENT, height=38)
        top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="ENCODER DIAGNOSTICS", font=("Arial", 12, "bold"),
                 bg=ACCENT, fg=CYAN).pack(side=tk.LEFT, padx=12, pady=6)

        tk.Button(top, text="⟳ Reset All Counts",
                  font=("Arial", 9), bg="#333", fg=FG,
                  relief=tk.FLAT, cursor="hand2",
                  command=self._reset_counts
                  ).pack(side=tk.LEFT, padx=6, pady=5)

        self.ppr_var = tk.IntVar(value=self.PPR)
        tk.Label(top, text="PPR:", font=("Arial", 9), bg=ACCENT, fg=FG
                 ).pack(side=tk.LEFT, padx=(16, 2))
        tk.Spinbox(top, from_=1, to=1000, textvariable=self.ppr_var,
                   width=5, font=("Arial", 9), bg="#222", fg=FG,
                   buttonbackground=ACCENT, relief=tk.FLAT
                   ).pack(side=tk.LEFT)
        tk.Label(top, text="  Wheel circ (cm):", font=("Arial", 9),
                 bg=ACCENT, fg=FG).pack(side=tk.LEFT, padx=(10, 2))
        self.circ_var = tk.DoubleVar(value=self.WHEEL_CIRC)
        tk.Spinbox(top, from_=1, to=200, increment=0.5, textvariable=self.circ_var,
                   width=6, font=("Arial", 9), bg="#222", fg=FG,
                   buttonbackground=ACCENT, relief=tk.FLAT
                   ).pack(side=tk.LEFT)

        self.enc_status = tk.Label(top, text="● Waiting for data",
                                   font=("Arial", 9, "bold"), bg=ACCENT, fg="#aaa")
        self.enc_status.pack(side=tk.LEFT, padx=16)

        body = tk.Frame(self.frame, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left  = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_motor_cards(left)
        self._build_right_panel(right)

    def _build_motor_cards(self, parent):
        top_row = tk.Frame(parent, bg=BG)
        top_row.pack(fill=tk.BOTH, expand=True)
        top_row.columnconfigure(0, weight=1)
        top_row.columnconfigure(1, weight=1)
        top_row.rowconfigure(0, weight=1)
        top_row.rowconfigure(1, weight=1)

        labels = [
            ("M1 — Front Left",  "ESP32 #1", CYAN),
            ("M2 — Front Right", "ESP32 #2", ORANGE),
            ("M3 — Rear Left",   "ESP32 #1", CYAN),
            ("M4 — Rear Right",  "ESP32 #2", ORANGE),
        ]
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]

        self._motor_widgets = []

        for idx, ((title, esp, col), (row, col_n)) in enumerate(zip(labels, positions)):
            card = tk.Frame(top_row, bg=CARD,
                            highlightbackground=col, highlightthickness=2)
            card.grid(row=row, column=col_n, sticky="nsew", padx=4, pady=4)

            header = tk.Frame(card, bg=col)
            header.pack(fill=tk.X)
            tk.Label(header, text=title, font=("Arial", 10, "bold"),
                     bg=col, fg=BG).pack(side=tk.LEFT, padx=8, pady=3)
            tk.Label(header, text=esp, font=("Arial", 8),
                     bg=col, fg=BG).pack(side=tk.RIGHT, padx=8)

            grid = tk.Frame(card, bg=CARD)
            grid.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

            def make_field(g, label, row_, col_, fg_color=FG, big=False):
                tk.Label(g, text=label, font=("Arial", 8), bg=CARD, fg="#888",
                         anchor="e", width=14).grid(row=row_, column=col_*2, sticky="e", padx=(4,2), pady=2)
                size = ("Arial", 14, "bold") if big else ("Arial", 10, "bold")
                lbl = tk.Label(g, text="---", font=size, bg=CARD, fg=fg_color,
                               anchor="w", width=10)
                lbl.grid(row=row_, column=col_*2+1, sticky="w", padx=(0,8))
                return lbl

            w = {}
            w["count"]     = make_field(grid, "Pulse Count:",  0, 0, YELLOW, big=True)
            w["speed"]     = make_field(grid, "Speed (cm/s):", 1, 0, GREEN,  big=True)
            w["dist"]      = make_field(grid, "Distance (cm):",2, 0, CYAN)
            w["total"]     = make_field(grid, "Total Dist (cm):", 3, 0, CYAN)
            w["rpm"]       = make_field(grid, "RPM:",          0, 1, ORANGE)
            w["direction"] = make_field(grid, "Direction:",    1, 1, FG)
            w["revs"]      = make_field(grid, "Revolutions:",  2, 1, FG)
            w["status"]    = make_field(grid, "Status:",       3, 1, GREEN)

            rst_btn = tk.Button(card, text="Reset",
                                font=("Arial", 8), bg=ACCENT, fg=FG,
                                relief=tk.FLAT, cursor="hand2",
                                command=lambda i=idx: self._reset_one(i))
            rst_btn.pack(anchor="e", padx=6, pady=(0, 4))

            self._motor_widgets.append(w)

        summary = tk.Frame(parent, bg=CARD,
                           highlightbackground=ACCENT, highlightthickness=1)
        summary.pack(fill=tk.X, padx=4, pady=(2, 0))

        tk.Label(summary, text="COMBINED STATS", font=("Arial", 9, "bold"),
                 bg=CARD, fg=CYAN).pack(side=tk.LEFT, padx=10, pady=4)

        self._sum_widgets = {}
        for tag, label in [("avg_speed", "Avg Speed (cm/s):"),
                            ("left_speed", "Left Side avg:"),
                            ("right_speed", "Right Side avg:"),
                            ("drift", "L/R Drift (cm):")]:
            tk.Label(summary, text=label, font=("Arial", 8), bg=CARD, fg="#888"
                     ).pack(side=tk.LEFT, padx=(12, 2))
            lbl = tk.Label(summary, text="---", font=("Arial", 10, "bold"),
                           bg=CARD, fg=YELLOW)
            lbl.pack(side=tk.LEFT, padx=(0, 8))
            self._sum_widgets[tag] = lbl

    def _build_right_panel(self, parent):
        tk.Label(parent, text="DRIVE CONTROLS", font=("Arial", 9, "bold"),
                 bg=BG, fg=CYAN).pack(pady=(0, 4))
        self._build_enc_dpad(parent)

        tk.Frame(parent, bg=ACCENT, height=1).pack(fill=tk.X, pady=6)

        tk.Label(parent, text="ENCODER LOG", font=("Arial", 9, "bold"),
                 bg=BG, fg=CYAN).pack(anchor="w")
        log_frame, self.enc_log = make_log_box(parent, height=20)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        log_btn_row(parent, self.enc_log)

    def _build_enc_dpad(self, parent):
        card = tk.Frame(parent, bg=CARD, padx=8, pady=8,
                        highlightbackground=ACCENT, highlightthickness=2)
        card.pack()
        pad = tk.Frame(card, bg=CARD); pad.pack()

        btn_cfg = dict(width=7, height=2, relief=tk.RAISED, bg=ACCENT, fg=FG,
                       font=("Arial", 10, "bold"), cursor="hand2")

        def make_btn(text, row, col, cmd, lbl_text):
            b = tk.Button(pad, text=text, **btn_cfg)
            b.grid(row=row, column=col, padx=3, pady=3)
            b.bind("<ButtonPress-1>",   lambda e, c=cmd, l=lbl_text: self._enc_btn_press(c, l, b))
            b.bind("<ButtonRelease-1>", lambda e: self._enc_btn_release(b))
            return b

        self.enc_w = make_btn("▲\nFWD",   0, 1, "W", "FORWARD")
        self.enc_a = make_btn("◀\nLEFT",  1, 0, "A", "TURN LEFT")
        self.enc_s = make_btn("▼\nBACK",  1, 1, "S", "BACKWARD")
        self.enc_d = make_btn("▶\nRIGHT", 1, 2, "D", "TURN RIGHT")

        stop_b = tk.Button(pad, text="⬛  STOP", width=26, height=2,
                           relief=tk.FLAT, bg="#2c2c54", fg=FG,
                           font=("Arial", 10, "bold"), cursor="hand2",
                           command=lambda: self.ctrl.send("X", "STOP"))
        stop_b.grid(row=2, column=0, columnspan=3, padx=3, pady=3)
        self.enc_stop = stop_b

        self.enc_btn_map = {
            "w": self.enc_w, "s": self.enc_s,
            "a": self.enc_a, "d": self.enc_d,
            "space": self.enc_stop
        }

        tk.Label(card, text="WASD / Arrows / Numpad 8426",
                 font=("Arial", 7), bg=CARD, fg="#555").pack(pady=(3, 0))

    def _enc_btn_press(self, cmd, label, btn):
        btn.config(bg=YELLOW, fg=BG)
        self.ctrl.send(cmd, label)

    def _enc_btn_release(self, btn):
        btn.config(bg=ACCENT, fg=FG)
        self.ctrl.send("X", "STOP")

    def update_encoder(self, motor_idx, count, direction):
        with self._lock:
            now = time.time()
            dt  = now - self._last_ts[motor_idx]
            dt  = max(dt, 0.001)

            prev  = self._counts[motor_idx]
            delta = abs(count - prev)

            ppr  = max(1, self.ppr_var.get())
            circ = self.circ_var.get()

            dist_delta = (delta / ppr) * circ
            speed_raw  = dist_delta / dt

            self._speed_buf[motor_idx].append(speed_raw)
            avg_speed = sum(self._speed_buf[motor_idx]) / len(self._speed_buf[motor_idx])

            self._counts[motor_idx]   = count
            self._speeds[motor_idx]   = avg_speed
            self._dist[motor_idx]     = (count / ppr) * circ
            self._total_dist[motor_idx] += dist_delta
            self._dirs[motor_idx]     = direction
            self._last_ts[motor_idx]  = now

    def _schedule_update(self):
        if self._update_running:
            self._refresh_display()
            self.frame.after(100, self._schedule_update)

    def _refresh_display(self):
        with self._lock:
            counts = list(self._counts)
            speeds = list(self._speeds)
            dists  = list(self._dist)
            totals = list(self._total_dist)
            dirs   = list(self._dirs)

        ppr  = max(1, self.ppr_var.get())
        circ = self.circ_var.get()

        any_active = any(s > 0.1 for s in speeds)
        if any_active:
            self.enc_status.config(text="● Receiving encoder data", fg=GREEN)
        else:
            self.enc_status.config(text="● Motors idle / no data", fg="#aaa")

        for i, w in enumerate(self._motor_widgets):
            spd   = speeds[i]
            cnt   = counts[i]
            dist  = dists[i]
            total = totals[i]
            rpm   = (spd / circ) * 60.0 if circ > 0 else 0
            revs  = cnt / ppr

            if spd > 0.5:
                status_txt, status_col = "MOVING", GREEN
            elif spd > 0.1:
                status_txt, status_col = "SLOW", ORANGE
            else:
                status_txt, status_col = "IDLE", "#aaa"

            w["count"].config(text=f"{cnt}")
            w["speed"].config(text=f"{spd:.1f}")
            w["dist"].config(text=f"{dist:.1f}")
            w["total"].config(text=f"{total:.1f}")
            w["rpm"].config(text=f"{rpm:.1f}")
            w["direction"].config(text=dirs[i])
            w["revs"].config(text=f"{revs:.2f}")
            w["status"].config(text=status_txt, fg=status_col)

            spd_col = GREEN if spd > 1.0 else ("#aaa" if spd < 0.1 else ORANGE)
            w["speed"].config(fg=spd_col)

        left_avg  = (speeds[0] + speeds[2]) / 2
        right_avg = (speeds[1] + speeds[3]) / 2
        avg_all   = sum(speeds) / 4
        left_dist = (dists[0] + dists[2]) / 2
        right_dist= (dists[1] + dists[3]) / 2
        drift     = left_dist - right_dist

        self._sum_widgets["avg_speed"].config(text=f"{avg_all:.1f}")
        self._sum_widgets["left_speed"].config(text=f"{left_avg:.1f}")
        self._sum_widgets["right_speed"].config(text=f"{right_avg:.1f}")
        drift_col = RED if abs(drift) > 5 else (ORANGE if abs(drift) > 2 else GREEN)
        self._sum_widgets["drift"].config(text=f"{drift:+.1f}", fg=drift_col)

    def _reset_one(self, idx):
        with self._lock:
            self._counts[idx]     = 0
            self._speeds[idx]     = 0.0
            self._dist[idx]       = 0.0
            self._total_dist[idx] = 0.0
            self._dirs[idx]       = "---"
            self._speed_buf[idx].clear()
        append_log(self.enc_log, f"[RESET] M{idx+1} counters cleared")

    def _reset_counts(self):
        with self._lock:
            self._counts      = [0, 0, 0, 0]
            self._speeds      = [0.0, 0.0, 0.0, 0.0]
            self._dist        = [0.0, 0.0, 0.0, 0.0]
            self._total_dist  = [0.0, 0.0, 0.0, 0.0]
            self._dirs        = ["---", "---", "---", "---"]
            for b in self._speed_buf: b.clear()
        append_log(self.enc_log, "[RESET] All encoder counters cleared")

    def on_key_press(self, key, btn_map):
        bk = {"up":"w","down":"s","left":"a","right":"d",
              "kp_8":"w","kp_2":"s","kp_4":"a","kp_6":"d"}.get(key, key)
        if bk in btn_map:
            btn_map[bk].config(bg=YELLOW, fg=BG)

    def on_key_release(self, key, btn_map):
        bk = {"up":"w","down":"s","left":"a","right":"d",
              "kp_8":"w","kp_2":"s","kp_4":"a","kp_6":"d"}.get(key, key)
        if bk in btn_map:
            btn_map[bk].config(bg=ACCENT, fg=FG)

    def stop(self):
        self._update_running = False


class RobotController:
    def __init__(self, root):
        self.root = root
        self.root.title("4WD Robot Controller")

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.resizable(True, True)
        try:
            if os.name == "nt":
                self.root.state("zoomed")
            else:
                self.root.attributes("-zoomed", True)
        except:
            pass

        cfg = load_config()

        self.sock1 = self.sock2 = None
        self.conn1 = self.conn2 = False
        self.pressed_keys = set()

        self.sonar_L = tk.StringVar(value="--- cm")
        self.sonar_F = tk.StringVar(value="--- cm")
        self.sonar_R = tk.StringVar(value="--- cm")
        self._sonar_val_labels = []

        self.estop_enabled        = tk.BooleanVar(value=False)
        self.estop_active         = False
        self.estop_override       = False
        self.estop_override_until = 0

        self.root.configure(bg=BG)

        self._build_global_bar()

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook", background=BG, borderwidth=0)
        style.configure("Dark.TNotebook.Tab", background=ACCENT, foreground=FG,
                        font=("Arial", 10, "bold"), padding=[12, 5])
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", CYAN)],
                  foreground=[("selected", BG)])

        self.notebook = ttk.Notebook(self.root, style="Dark.TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_conn    = tk.Frame(self.notebook, bg=BG)
        self.tab_manual  = tk.Frame(self.notebook, bg=BG)
        self.tab_auto    = tk.Frame(self.notebook, bg=BG)
        self.tab_encoder = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_conn,    text="  🔌 CONNECTION  ")
        self.notebook.add(self.tab_manual,  text="  🕹 MANUAL CONTROL  ")
        self.notebook.add(self.tab_auto,    text="  🗺 SONAR MAPPER  ")
        self.notebook.add(self.tab_encoder, text="  ⚙ ENCODER  ")

        self.ip1 = tk.StringVar(value=cfg.get("ip1", "192.168.1.159"))
        self.ip2 = tk.StringVar(value=cfg.get("ip2", "192.168.1.162"))

        self._build_conn_tab()
        self._build_manual_tab()

        self.root.bind("<KeyPress>",   self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.focus_set()

        self.auto_mapper   = AutoMapper(self.tab_auto, self)
        self.encoder_page  = EncoderPage(self.tab_encoder, self)

        self._tick_clock()

    def _build_global_bar(self):
        bar = tk.Frame(self.root, bg="#0a0a18", height=36)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)

        tk.Button(bar, text="✕ Close App",
                  font=("Arial", 9, "bold"), bg="#333", fg=FG,
                  relief=tk.FLAT, cursor="hand2",
                  command=self.close_app
                  ).pack(side=tk.RIGHT, padx=8, pady=4)

        self.clock_lbl = tk.Label(bar, text="", font=("Arial", 9),
                                   bg="#0a0a18", fg=FG)
        self.clock_lbl.pack(side=tk.RIGHT, padx=12)

        tk.Button(bar, text="🛑 MANUAL E-STOP",
                  font=("Arial", 10, "bold"), bg="#7b0000", fg="white",
                  relief=tk.FLAT, cursor="hand2",
                  command=self.manual_estop
                  ).pack(side=tk.LEFT, padx=6, pady=3)

        self.auto_estop_btn = tk.Button(bar, text="⚡ AUTO E-STOP: OFF",
                                        font=("Arial", 9, "bold"), bg="#555", fg=FG,
                                        relief=tk.FLAT, cursor="hand2",
                                        command=self.toggle_auto_estop)
        self.auto_estop_btn.pack(side=tk.LEFT, padx=4, pady=3)

        self.auto_estop_status = tk.Label(bar, text="", font=("Arial", 9, "bold"),
                                          bg="#0a0a18", fg="#aaa")
        self.auto_estop_status.pack(side=tk.LEFT, padx=4)

        tk.Frame(bar, bg="#333", width=2).pack(side=tk.LEFT, fill=tk.Y, pady=4, padx=6)

        self.state_lbl = tk.Label(bar, text="IDLE", font=("Arial", 12, "bold"),
                                   bg="#0a0a18", fg="#2980b9")
        self.state_lbl.pack(side=tk.LEFT, padx=8)

    def close_app(self):
        self.auto_mapper.stop()
        self.encoder_page.stop()
        self._send_raw("X")
        self.root.after(200, self.root.destroy)

    def _tick_clock(self):
        self.clock_lbl.config(text=time.strftime("%H:%M:%S  %d %b %Y"))
        self.root.after(1000, self._tick_clock)

    def _build_conn_tab(self):
        title = tk.Frame(self.tab_conn, bg=ACCENT, height=40)
        title.pack(fill=tk.X)
        title.pack_propagate(False)
        tk.Label(title, text="CONNECTION MANAGER", font=("Arial", 12, "bold"),
                 bg=ACCENT, fg=CYAN).pack(side=tk.LEFT, padx=16, pady=8)

        body = tk.Frame(self.tab_conn, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG, width=360)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.grid_propagate(False)

        tk.Label(left, text="ESP32 DEVICES", font=("Arial", 10, "bold"),
                 bg=BG, fg=CYAN).pack(anchor="w", pady=(0, 6))

        for n in [1, 2]:
            side = "Left (M1+M3) + Sonars" if n == 1 else "Right (M2+M4)"
            f = tk.LabelFrame(left, text=f" ESP32 #{n} — {side} ",
                              font=("Arial", 9, "bold"), bg=CARD, fg=FG,
                              bd=1, relief=tk.GROOVE)
            f.pack(fill=tk.X, pady=5, ipady=6)

            r1 = tk.Frame(f, bg=CARD); r1.pack(fill=tk.X, padx=10, pady=(4, 2))
            tk.Label(r1, text="IP:", font=("Arial", 10), bg=CARD, fg=FG).pack(side=tk.LEFT)
            ip_var = self.ip1 if n == 1 else self.ip2
            tk.Entry(r1, textvariable=ip_var, width=16, font=("Arial", 10),
                     bg="#2c2c2c", fg=FG, insertbackground=FG,
                     relief=tk.FLAT).pack(side=tk.LEFT, padx=6)
            tk.Label(r1, text="Port: 8080", font=("Arial", 9), bg=CARD, fg="#aaa"
                     ).pack(side=tk.LEFT)

            r2 = tk.Frame(f, bg=CARD); r2.pack(fill=tk.X, padx=10, pady=(2, 4))
            btn = tk.Button(r2, text="Connect", width=11,
                            bg=GREEN, fg="white", font=("Arial", 10, "bold"),
                            relief=tk.FLAT, cursor="hand2",
                            command=lambda nn=n: self.toggle(nn))
            btn.pack(side=tk.LEFT)
            lbl = tk.Label(r2, text="● OFFLINE", fg=RED,
                           font=("Arial", 10, "bold"), bg=CARD)
            lbl.pack(side=tk.LEFT, padx=10)
            if n == 1: self.btn1, self.lbl1 = btn, lbl
            else:      self.btn2, self.lbl2 = btn, lbl

        tk.Frame(left, bg=ACCENT, height=1).pack(fill=tk.X, pady=10)
        tk.Button(left, text="💾  Save IPs",
                  font=("Arial", 10, "bold"), bg=GREEN, fg="white",
                  relief=tk.FLAT, cursor="hand2",
                  command=self._save_ips).pack(anchor="w")
        tk.Label(left, text="IPs auto-save on connect.\nGet IP from Arduino Serial Monitor.",
                 font=("Arial", 8), bg=BG, fg=ORANGE, justify=tk.LEFT
                 ).pack(anchor="w", pady=(6, 0))

        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="CONNECTION LOG", font=("Arial", 10, "bold"),
                 bg=BG, fg=CYAN).pack(anchor="w", pady=(0, 4))
        log_frame, self.conn_log = make_log_box(right, height=20)
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_btn_row(right, self.conn_log)

    def _save_ips(self):
        save_config(self.ip1.get().strip(), self.ip2.get().strip())
        self.log_msg("[CONFIG] IPs saved.")

    def _build_manual_tab(self):
        title = tk.Frame(self.tab_manual, bg=ACCENT, height=40)
        title.pack(fill=tk.X)
        title.pack_propagate(False)
        tk.Label(title, text="MANUAL CONTROL", font=("Arial", 12, "bold"),
                 bg=ACCENT, fg=CYAN).pack(side=tk.LEFT, padx=16, pady=8)

        main = tk.Frame(self.tab_manual, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.columnconfigure(2, weight=2)
        main.rowconfigure(0, weight=1)

        left   = tk.Frame(main, bg=BG); left.grid(  row=0, column=0, sticky="nsew", padx=(0, 6))
        center = tk.Frame(main, bg=BG); center.grid(row=0, column=1, sticky="nsew", padx=(0, 6))
        right  = tk.Frame(main, bg=BG); right.grid( row=0, column=2, sticky="nsew")

        self._build_sonar_panel(left)

        tk.Label(center, text="D-PAD CONTROLS", font=("Arial", 9, "bold"),
                 bg=BG, fg=CYAN).pack(pady=(0, 3))
        self._build_dpad(center)
        tk.Frame(center, bg=ACCENT, height=1).pack(fill=tk.X, pady=6)
        tk.Label(center, text="JOYSTICKS", font=("Arial", 9, "bold"),
                 bg=BG, fg=CYAN).pack(pady=(0, 3))
        self._build_joysticks(center)

        tk.Label(right, text="LIVE LOG", font=("Arial", 9, "bold"),
                 bg=BG, fg=CYAN).pack(anchor="w", pady=(0, 3))
        log_frame, self.log = make_log_box(right, height=30)
        log_frame.pack(fill=tk.BOTH, expand=True)
        log_btn_row(right, self.log)

    def _build_sonar_panel(self, parent):
        tk.Label(parent, text="SONAR (HC-SR04)", font=("Arial", 9, "bold"),
                 bg=BG, fg=CYAN).pack(anchor="w", pady=(0, 3))
        card = tk.Frame(parent, bg=CARD, padx=6, pady=8,
                        highlightbackground=ACCENT, highlightthickness=2)
        card.pack(fill=tk.X)
        inner = tk.Frame(card, bg=CARD); inner.pack()
        for i, (label, var, col) in enumerate([
            ("LEFT 45°", self.sonar_L, CYAN),
            ("FRONT 0°", self.sonar_F, GREEN),
            ("RIGHT 45°", self.sonar_R, CYAN)
        ]):
            cell = tk.Frame(inner, bg=CARD, padx=10, pady=6)
            cell.grid(row=0, column=i, padx=6)
            tk.Label(cell, text=label, font=("Arial", 8, "bold"),
                     bg=CARD, fg=col).pack()
            lbl = tk.Label(cell, textvariable=var, font=("Arial", 16, "bold"),
                           bg=CARD, fg=FG, width=7, anchor="center")
            lbl.pack(pady=2)
            self._sonar_val_labels.append(lbl)

    def _build_dpad(self, parent):
        card = tk.Frame(parent, bg=CARD, padx=8, pady=8,
                        highlightbackground=ACCENT, highlightthickness=2)
        card.pack()
        pad = tk.Frame(card, bg=CARD); pad.pack()

        btn_cfg = dict(width=7, height=2, relief=tk.RAISED, bg=ACCENT, fg=FG,
                       font=("Arial", 10, "bold"), cursor="hand2")

        def make_btn(text, row, col, cmd, lbl_text):
            b = tk.Button(pad, text=text, **btn_cfg)
            b.grid(row=row, column=col, padx=3, pady=3)
            b.bind("<ButtonPress-1>",   lambda e, c=cmd, l=lbl_text: self._btn_press(c, l, b))
            b.bind("<ButtonRelease-1>", lambda e: self._btn_release(b))
            return b

        self.w_btn = make_btn("▲\nFWD",   0, 1, "W", "FORWARD")
        self.a_btn = make_btn("◀\nLEFT",  1, 0, "A", "TURN LEFT")
        self.s_btn = make_btn("▼\nBACK",  1, 1, "S", "BACKWARD")
        self.d_btn = make_btn("▶\nRIGHT", 1, 2, "D", "TURN RIGHT")

        stop_btn = tk.Button(pad, text="⬛  STOP",
                             width=26, height=2, relief=tk.FLAT,
                             bg="#2c2c54", fg=FG, font=("Arial", 10, "bold"),
                             cursor="hand2",
                             command=lambda: self.send("X", "STOP"))
        stop_btn.grid(row=2, column=0, columnspan=3, padx=3, pady=3)
        self.spc_btn = stop_btn

        self.btn_map = {"w": self.w_btn, "s": self.s_btn,
                        "a": self.a_btn, "d": self.d_btn, "space": self.spc_btn}

        tk.Label(card, text="WASD / Arrows / Numpad 8426 / Click",
                 font=("Arial", 7), bg=CARD, fg="#555").pack(pady=(3, 0))

    def _btn_press(self, cmd, label, btn):
        btn.config(bg=YELLOW, fg=BG)
        self.send(cmd, label)

    def _btn_release(self, btn):
        btn.config(bg=ACCENT, fg=FG)
        self.send("X", "STOP")

    def _build_joysticks(self, parent):
        jframe = tk.Frame(parent, bg=BG); jframe.pack(fill=tk.X)
        tk.Label(jframe, text="Omni Joystick", font=("Arial", 8), bg=BG, fg="#aaa").pack()
        self._build_omni_joystick(jframe)
        tk.Frame(jframe, bg=ACCENT, height=1).pack(fill=tk.X, pady=4)
        split = tk.Frame(jframe, bg=BG); split.pack()
        lf = tk.Frame(split, bg=BG); lf.pack(side=tk.LEFT, padx=16)
        rf = tk.Frame(split, bg=BG); rf.pack(side=tk.LEFT, padx=16)
        tk.Label(lf, text="FWD/BACK", font=("Arial", 8), bg=BG, fg="#aaa").pack()
        self._build_vertical_joystick(lf)
        tk.Label(rf, text="L/R", font=("Arial", 8), bg=BG, fg="#aaa").pack()
        self._build_horizontal_joystick(rf)

    def _build_omni_joystick(self, parent):
        SIZE = 120; DEAD = 18
        c = tk.Canvas(parent, width=SIZE, height=SIZE, bg=CARD,
                      highlightbackground=ACCENT, highlightthickness=2)
        c.pack(pady=3)
        cx, cy = SIZE//2, SIZE//2
        c.create_oval(4, 4, SIZE-4, SIZE-4, outline="#333", width=2)
        c.create_oval(cx-DEAD, cy-DEAD, cx+DEAD, cy+DEAD, outline="#555", width=1)
        c.create_line(cx, 4, cx, SIZE-4, fill="#222")
        c.create_line(4, cy, SIZE-4, cy, fill="#222")
        knob = c.create_oval(cx-11, cy-11, cx+11, cy+11, fill=CYAN, outline="white", width=2)
        state = {"active": False, "cmd": None}

        def _move(ex, ey):
            dx = ex-cx; dy = ey-cy
            dist = math.sqrt(dx*dx+dy*dy)
            r = SIZE//2-13
            if dist > r: dx=dx*r/dist; dy=dy*r/dist
            c.coords(knob, cx+dx-11, cy+dy-11, cx+dx+11, cy+dy+11)
            if dist < DEAD: cmd, lbl = "X","STOP"
            elif abs(dx) >= abs(dy):
                cmd, lbl = ("D","TURN RIGHT") if dx>0 else ("A","TURN LEFT")
            else:
                cmd, lbl = ("S","BACKWARD") if dy>0 else ("W","FORWARD")
            if cmd != state["cmd"]: state["cmd"]=cmd; self.send(cmd, lbl)

        def _reset():
            c.coords(knob, cx-11, cy-11, cx+11, cy+11)
            if state["cmd"] not in (None,"X"): self.send("X","STOP")
            state["cmd"] = None

        c.bind("<ButtonPress-1>",   lambda e: (_move(e.x,e.y), state.__setitem__("active",True)))
        c.bind("<B1-Motion>",       lambda e: _move(e.x,e.y) if state["active"] else None)
        c.bind("<ButtonRelease-1>", lambda e: (_reset(), state.__setitem__("active",False)))

    def _build_vertical_joystick(self, parent):
        W, H = 54, 120; DEAD = 16
        c = tk.Canvas(parent, width=W, height=H, bg=CARD,
                      highlightbackground=ACCENT, highlightthickness=2)
        c.pack(pady=3)
        cx, cy = W//2, H//2
        c.create_line(cx, 4, cx, H-4, fill="#333", width=2)
        c.create_oval(cx-DEAD//2, cy-DEAD//2, cx+DEAD//2, cy+DEAD//2, outline="#555")
        knob = c.create_oval(cx-11, cy-11, cx+11, cy+11, fill=GREEN, outline="white", width=2)
        state = {"cmd": None}

        def _move(ey):
            dy = max(13, min(H-13, ey))-cy
            r  = H//2-13; dy = max(-r, min(r, dy))
            c.coords(knob, cx-11, cy+dy-11, cx+11, cy+dy+11)
            if abs(dy)<DEAD: cmd,lbl="X","STOP"
            elif dy<0: cmd,lbl="W","FORWARD"
            else:      cmd,lbl="S","BACKWARD"
            if cmd!=state["cmd"]: state["cmd"]=cmd; self.send(cmd,lbl)

        def _reset():
            c.coords(knob, cx-11, cy-11, cx+11, cy+11)
            if state["cmd"] not in (None,"X"): self.send("X","STOP")
            state["cmd"] = None

        c.bind("<ButtonPress-1>",   lambda e: _move(e.y))
        c.bind("<B1-Motion>",       lambda e: _move(e.y))
        c.bind("<ButtonRelease-1>", lambda e: _reset())

    def _build_horizontal_joystick(self, parent):
        W, H = 120, 54; DEAD = 16
        c = tk.Canvas(parent, width=W, height=H, bg=CARD,
                      highlightbackground=ACCENT, highlightthickness=2)
        c.pack(pady=3)
        cx, cy = W//2, H//2
        c.create_line(4, cy, W-4, cy, fill="#333", width=2)
        c.create_oval(cx-DEAD//2, cy-DEAD//2, cx+DEAD//2, cy+DEAD//2, outline="#555")
        knob = c.create_oval(cx-11, cy-11, cx+11, cy+11, fill=ORANGE, outline="white", width=2)
        state = {"cmd": None}

        def _move(ex):
            dx = max(13, min(W-13, ex))-cx
            r  = W//2-13; dx = max(-r, min(r, dx))
            c.coords(knob, cx+dx-11, cy-11, cx+dx+11, cy+11)
            if abs(dx)<DEAD: cmd,lbl="X","STOP"
            elif dx<0: cmd,lbl="A","TURN LEFT"
            else:      cmd,lbl="D","TURN RIGHT"
            if cmd!=state["cmd"]: state["cmd"]=cmd; self.send(cmd,lbl)

        def _reset():
            c.coords(knob, cx-11, cy-11, cx+11, cy+11)
            if state["cmd"] not in (None,"X"): self.send("X","STOP")
            state["cmd"] = None

        c.bind("<ButtonPress-1>",   lambda e: _move(e.x))
        c.bind("<B1-Motion>",       lambda e: _move(e.x))
        c.bind("<ButtonRelease-1>", lambda e: _reset())

    def manual_estop(self):
        self._send_raw("X")
        self.state_lbl.config(text="MANUAL E-STOP!", fg=RED)
        self.log_msg("[ESTOP] *** MANUAL EMERGENCY STOP ***")

    def toggle_auto_estop(self):
        if self.estop_enabled.get():
            self.estop_enabled.set(False)
            self.estop_active = self.estop_override = False
            self.auto_estop_btn.config(text="⚡ AUTO E-STOP: OFF", bg="#555")
            self.auto_estop_status.config(text="", fg="#aaa")
            self.log_msg("[ESTOP] Auto E-Stop DISABLED")
        else:
            self.estop_enabled.set(True)
            self.auto_estop_btn.config(text="⚡ AUTO E-STOP: ON", bg=GREEN)
            self.auto_estop_status.config(text="ARMED", fg=GREEN)
            self.log_msg("[ESTOP] Auto E-Stop ENABLED (threshold: 10 cm)")

    def _trigger_estop(self, where, dist):
        if self.estop_active or self.estop_override: return
        self.estop_active = True
        self._send_raw("X")
        self.log_msg(f"[ESTOP] TRIGGERED — {where} = {dist:.1f} cm")
        self.state_lbl.config(text="AUTO E-STOP!", fg=RED)
        self.auto_estop_status.config(text="TRIGGERED", fg=RED)
        self.auto_estop_btn.config(bg=RED)
        self.root.after(0, self._show_estop_dialog)

    def _show_estop_dialog(self):
        messagebox.showwarning("AUTO EMERGENCY STOP",
                               "Obstacle <= 10 cm!\nBot stopped.\n\nClick OK for 3s reverse window.")
        self.estop_active = False
        self.estop_override = True
        self.estop_override_until = time.time() + 3.0
        self.auto_estop_status.config(text="OVERRIDE 3s", fg=ORANGE)
        self.auto_estop_btn.config(bg=ORANGE)
        self.log_msg("[ESTOP] Override 3s — reverse now!")
        self.state_lbl.config(text="OVERRIDE", fg=ORANGE)
        self.root.after(3100, self._estop_rearm)

    def _estop_rearm(self):
        if self.estop_override and self.estop_enabled.get():
            self.estop_override = self.estop_active = False
            self.auto_estop_status.config(text="ARMED", fg=GREEN)
            self.auto_estop_btn.config(bg=GREEN)
            self.log_msg("[ESTOP] Re-armed.")
            self.state_lbl.config(text="IDLE", fg="#2980b9")

    def _check_estop(self, l, f, r):
        if not self.estop_enabled.get() or self.estop_active: return
        if self.estop_override:
            if time.time() > self.estop_override_until: self.estop_override = False
            return
        T = 10.0
        if   l <= T: self._trigger_estop("LEFT",  l)
        elif f <= T: self._trigger_estop("FRONT", f)
        elif r <= T: self._trigger_estop("RIGHT", r)

    def toggle(self, n):
        ip_var = self.ip1  if n == 1 else self.ip2
        btn    = self.btn1 if n == 1 else self.btn2
        lbl    = self.lbl1 if n == 1 else self.lbl2
        conn   = self.conn1 if n == 1 else self.conn2
        if not conn:
            try:
                ip = ip_var.get().strip()
                s  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5); s.connect((ip, 8080)); s.settimeout(None)
                if n == 1: self.sock1 = s; self.conn1 = True
                else:      self.sock2 = s; self.conn2 = True
                btn.config(text="Disconnect", bg=RED)
                lbl.config(text="● ONLINE", fg=GREEN)
                save_config(self.ip1.get().strip(), self.ip2.get().strip())
                self.log_msg(f"[NET] ESP32 #{n} connected — {ip}:8080")
                threading.Thread(target=self.rx, args=(s, n), daemon=True).start()
            except Exception as e:
                self.log_msg(f"[ERROR] ESP32 #{n}: {e}")
        else:
            s = self.sock1 if n == 1 else self.sock2
            try: s.close()
            except: pass
            if n == 1: self.sock1 = None; self.conn1 = False
            else:      self.sock2 = None; self.conn2 = False
            btn.config(text="Connect", bg=GREEN)
            lbl.config(text="● OFFLINE", fg=RED)
            self.log_msg(f"[NET] ESP32 #{n} disconnected")

    def rx(self, s, n):
        try:
            buf = ""
            while True:
                data = s.recv(512)
                if not data: break
                buf += data.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line: continue
                    if line.startswith("[SONAR]") and n == 1:
                        self._parse_sonar(line)
                    elif line.startswith("[ENC]"):
                        self._parse_encoder(line, n)
                    else:
                        self.log_msg(f"[ESP{n}] {line}")
        except:
            self.log_msg(f"[WARN] ESP32 #{n} dropped")

    def _parse_sonar(self, line):
        try:
            body  = line.replace("[SONAR]", "")
            parts = dict(p.split(":") for p in body.split(","))
            l, f, r = float(parts["L"]), float(parts["F"]), float(parts["R"])
            def fmt(v): return "--- cm" if v >= 399 else f"{v:.1f} cm"
            def col(v):
                if v <= 10: return "#ff0000"
                if v < 20:  return RED
                if v < 50:  return ORANGE
                return "#00ff88"
            self.root.after(0, lambda: self._apply_sonar(
                fmt(l), fmt(f), fmt(r), col(l), col(f), col(r)))
            self._check_estop(l, f, r)
            self.auto_mapper.update_sonar(l, f, r)
        except:
            pass

    def _parse_encoder(self, line, esp_num):
        try:
            body  = line.replace("[ENC]", "")
            parts = dict(p.split(":") for p in body.split(","))
            motor_id  = int(parts["M"])
            count     = int(parts["C"])
            direction = parts.get("D", "FWD")
            idx = motor_id - 1
            if 0 <= idx <= 3:
                self.encoder_page.update_encoder(idx, count, direction)
                self.root.after(0, lambda: append_log(
                    self.encoder_page.enc_log,
                    f"[ESP{esp_num}] M{motor_id} count={count} dir={direction}"))
        except:
            pass

    def _apply_sonar(self, l, f, r, cl, cf, cr):
        self.sonar_L.set(l); self.sonar_F.set(f); self.sonar_R.set(r)
        if self._sonar_val_labels:
            self._sonar_val_labels[0].config(fg=cl)
            self._sonar_val_labels[1].config(fg=cf)
            self._sonar_val_labels[2].config(fg=cr)

    def _send_raw(self, cmd):
        for n, s, c in [(1,self.sock1,self.conn1),(2,self.sock2,self.conn2)]:
            if c and s:
                try: s.sendall(cmd.encode())
                except Exception as e: self.log_msg(f"[ERROR] ESP{n}: {e}")

    def send(self, cmd, label):
        if self.estop_active and cmd not in (" ", "X"):
            self.log_msg("[ESTOP] Blocked"); return
        sent = False
        for n, s, c in [(1,self.sock1,self.conn1),(2,self.sock2,self.conn2)]:
            if c and s:
                try: s.sendall(cmd.encode()); sent = True
                except Exception as e: self.log_msg(f"[ERROR] ESP{n}: {e}")
        if sent:
            if not self.estop_active:
                self.state_lbl.config(text=label, fg=RED if "STOP" in label else GREEN)
            self.log_msg(f"[TX] '{cmd}' >> {label}")
        else:
            self.log_msg("[WARN] No ESP32 connected")

    def on_key_press(self, event):
        key = event.keysym.lower()
        if key in self.pressed_keys: return
        self.pressed_keys.add(key)
        cmd_map = {
            "w":("W","FORWARD"),     "up":("W","FORWARD"),
            "s":("S","BACKWARD"),    "down":("S","BACKWARD"),
            "a":("A","TURN LEFT"),   "left":("A","TURN LEFT"),
            "d":("D","TURN RIGHT"),  "right":("D","TURN RIGHT"),
            "space":("X","STOP"),    "x":("X","STOP"),
            "kp_8":("W","FORWARD"),  "kp_2":("S","BACKWARD"),
            "kp_4":("A","TURN LEFT"),"kp_6":("D","TURN RIGHT"),
            "kp_5":("X","STOP"),
        }
        if key in cmd_map:
            cmd, label = cmd_map[key]
            self.send(cmd, label)
            bk = {"up":"w","down":"s","left":"a","right":"d",
                  "kp_8":"w","kp_2":"s","kp_4":"a","kp_6":"d"}.get(key, key)
            for bmap in [self.btn_map, self.encoder_page.enc_btn_map]:
                if bk in bmap:
                    bmap[bk].config(bg=YELLOW, fg=BG)

    def on_key_release(self, event):
        key = event.keysym.lower()
        self.pressed_keys.discard(key)
        bk = {"up":"w","down":"s","left":"a","right":"d",
              "kp_8":"w","kp_2":"s","kp_4":"a","kp_6":"d"}.get(key, key)
        for bmap in [self.btn_map, self.encoder_page.enc_btn_map]:
            if bk in bmap:
                bmap[bk].config(bg=ACCENT, fg=FG)
        move_keys = {"w","s","a","d","up","down","left","right","kp_8","kp_2","kp_4","kp_6"}
        if key in move_keys and not (self.pressed_keys & move_keys):
            self.send("X", "STOP")

    def log_msg(self, msg):
        def _u():
            for box in [self.log, self.conn_log]:
                try: append_log(box, msg)
                except: pass
        self.root.after(0, _u)


if __name__ == "__main__":
    root = tk.Tk()
    app  = RobotController(root)
    root.mainloop()
