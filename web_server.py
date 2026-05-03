"""
RoboDash / DUON — FastAPI WebSocket Server
Bridges browser clients ↔ ESP32 TCP sockets (port 8080)
"""

import asyncio
import json
import logging
import math
import os
import socket
import sys
import threading
import time
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from advanced_mapping import AdvancedMapManager

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("DUON")

# ── Config ──────────────────────────────────────────────────
CONFIG_FILE = "robot_config.json"

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"ip1": "192.168.1.159", "ip2": "192.168.1.162"}

def save_config(ip1: str, ip2: str):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"ip1": ip1, "ip2": ip2}, f, indent=2)
    except Exception as e:
        logger.error(f"save_config: {e}")

class ConfigUpdate(BaseModel):
    ip1: str
    ip2: str

# ── SonarProcessor — exact copy from DE.py ─────────────────
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

    def feed(self, raw_cm: float):
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

# ── FastAPI App ─────────────────────────────────────────────
app = FastAPI(title="DUON")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── WebSocket State ──────────────────────────────────────────
_main_loop: asyncio.AbstractEventLoop | None = None
_clients: list[WebSocket] = []
_clients_lock = threading.Lock()

async def _broadcast_async(msg: dict):
    """Broadcast from async context (event loop thread)."""
    dead = []
    for ws in list(_clients):
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    with _clients_lock:
        for ws in dead:
            if ws in _clients:
                _clients.remove(ws)

def broadcast(msg: dict):
    """Thread-safe broadcast from background threads."""
    if _main_loop is None:
        return
    asyncio.run_coroutine_threadsafe(_broadcast_async(msg), _main_loop)

# ── AutoMapper (headless, ported from DE.py) ─────────────────
class AutoMapper:
    FRONT_THRESHOLD = 35
    DIAG_THRESHOLD  = 25
    PULSE_MS        = 400
    TURN_MS         = 480
    SETTLE_MS       = 350
    SPEED_CM_S      = 18.0

    def __init__(self, robot):
        self.robot   = robot
        self.running = False
        self.mode    = "pulse"
        self.bot_x = self.bot_y = self.heading = 0.0
        self._filt_L = self._filt_F = self._filt_R = 400.0
        self._proc_L = SonarProcessor()
        self._proc_F = SonarProcessor()
        self._proc_R = SonarProcessor()
        self._sonar_event = threading.Event()
        self._walls: set = set()
        self._free:  set = set()
        self._path:  list = []

    def apply_config(self, pulse_ms, turn_ms, front_thr, diag_thr):
        self.PULSE_MS        = int(pulse_ms)
        self.TURN_MS         = int(turn_ms)
        self.FRONT_THRESHOLD = int(front_thr)
        self.DIAG_THRESHOLD  = int(diag_thr)

    def update_sonar(self, L, F, R):
        self._filt_L, _ = self._proc_L.feed(L)
        self._filt_F, _ = self._proc_F.feed(F)
        self._filt_R, _ = self._proc_R.feed(R)
        self._sonar_event.set()

    def _project(self, dist, angle_deg):
        r = math.radians(self.heading + angle_deg)
        return self.bot_x + dist * math.sin(r), self.bot_y + dist * math.cos(r)

    def _scan(self):
        L, F, R = self._filt_L, self._filt_F, self._filt_R
        for dist, angle in [(L, -45), (F, 0), (R, 45)]:
            if dist < 399:
                key = (round(self._project(dist, angle)[0]/4)*4,
                       round(self._project(dist, angle)[1]/4)*4)
                self._walls.add(key)
                for d in range(20, int(dist)-10, 20):
                    fk = (round(self._project(d, angle)[0]/6)*6,
                          round(self._project(d, angle)[1]/6)*6)
                    if fk not in self._walls:
                        self._free.add(fk)
        broadcast({
            "type":  "map",
            "walls": list(self._walls),
            "free":  list(self._free),
            "path":  self._path[-600:],
            "bot":   {"x": self.bot_x, "y": self.bot_y, "h": self.heading},
        })

    def _fwd_pulse(self):
        self.robot.raw_send("W"); time.sleep(self.PULSE_MS / 1000)
        self.robot.raw_send("X"); time.sleep(self.SETTLE_MS / 1000)
        r = math.radians(self.heading)
        d = (self.PULSE_MS / 1000) * self.SPEED_CM_S
        self.bot_x += d * math.sin(r); self.bot_y += d * math.cos(r)
        self._path.append((self.bot_x, self.bot_y))

    def _turn(self, direction):
        self.robot.raw_send("A" if direction == "L" else "D")
        time.sleep(self.TURN_MS / 1000)
        self.robot.raw_send("X"); time.sleep(self.SETTLE_MS / 1000)
        self.heading = (self.heading + (90 if direction == "R" else -90)) % 360

    def _uturn(self):
        self._turn("R"); self._turn("R")

    def _wait_sonar(self, timeout=2.0):
        self._sonar_event.clear()
        self._sonar_event.wait(timeout=timeout)

    def _step_pulse(self):
        self._wait_sonar()
        L, F, R = self._filt_L, self._filt_F, self._filt_R
        ft, dt  = self.FRONT_THRESHOLD, self.DIAG_THRESHOLD
        self._scan()
        if F > ft and L > dt and R > dt:
            broadcast({"type": "log", "msg": f"[AUTO] FWD F={F:.0f} L={L:.0f} R={R:.0f}"}); self._fwd_pulse()
        elif F > ft and R <= dt:
            broadcast({"type": "log", "msg": f"[AUTO] PRE-TURN L"}); self._turn("L")
        elif F > ft and L <= dt:
            broadcast({"type": "log", "msg": f"[AUTO] PRE-TURN R"}); self._turn("R")
        elif F <= ft:
            if R > ft:      broadcast({"type": "log", "msg": "[AUTO] TURN R"}); self._turn("R")
            elif L > ft:    broadcast({"type": "log", "msg": "[AUTO] TURN L"}); self._turn("L")
            else:           broadcast({"type": "log", "msg": "[AUTO] U-TURN"}); self._uturn()

    def _step_smooth(self):
        L, F, R = self._filt_L, self._filt_F, self._filt_R
        ft, dt  = self.FRONT_THRESHOLD, self.DIAG_THRESHOLD
        self._scan()
        if F <= ft:
            self.robot.raw_send("X"); time.sleep(0.15)
            self._turn("R" if R > L else "L"); self.robot.raw_send("W")
        elif R <= dt:
            self.robot.raw_send("X"); time.sleep(0.1); self._turn("L"); self.robot.raw_send("W")
        elif L <= dt:
            self.robot.raw_send("X"); time.sleep(0.1); self._turn("R"); self.robot.raw_send("W")
        else:
            dt_s = 0.12; r = math.radians(self.heading)
            self.bot_x += dt_s * self.SPEED_CM_S * math.sin(r)
            self.bot_y += dt_s * self.SPEED_CM_S * math.cos(r)
            self._path.append((self.bot_x, self.bot_y))
            time.sleep(dt_s)

    def _loop(self):
        broadcast({"type": "log", "msg": "=== MAPPING STARTED ==="})
        if self.mode == "smooth": self.robot.raw_send("W")
        while self.running:
            try:
                if self.mode == "pulse": self._step_pulse()
                else:                    self._step_smooth()
            except Exception as e:
                broadcast({"type": "log", "msg": f"[AUTO ERR] {e}"}); time.sleep(0.5)
        self.robot.raw_send("X")
        broadcast({"type": "log", "msg": "=== MAPPING STOPPED ==="})

    def start(self):
        if self.running: return
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False

    def clear(self):
        self._walls.clear(); self._free.clear(); self._path.clear()
        self.bot_x = self.bot_y = self.heading = 0.0
        broadcast({"type": "map", "walls": [], "free": [], "path": [],
                   "bot": {"x": 0, "y": 0, "h": 0}})


# ── Robot Controller ────────────────────────────────────────
class Robot:
    def __init__(self):
        self._sock   = [None, None]
        self._conn   = [False, False]
        self.ip1     = "192.168.1.159"
        self.ip2     = "192.168.1.162"
        self.last_rx = [0.0, 0.0]     # timestamp of last data from each ESP
        self.sonar_front = None        # latest front sonar reading

        self.estop_enabled  = False
        self.estop_active   = False
        self.estop_override = False
        self.estop_until    = 0.0

        self.mapper = AutoMapper(self)

    @property
    def conn1(self): return self._conn[0]
    @property
    def conn2(self): return self._conn[1]

    def _ip(self, n): return self.ip1 if n == 1 else self.ip2

    def connect(self, n: int):
        idx = n - 1
        if self._conn[idx]:
            broadcast({"type": "log", "msg": f"[NET] ESP32 #{n} already connected"})
            return
        ip = self._ip(n)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((ip, 8080))
            s.settimeout(None)
            self._sock[idx] = s
            self._conn[idx] = True
            broadcast({"type": "log",  "msg":  f"[NET] ESP32 #{n} connected — {ip}:8080"})
            broadcast({"type": "conn", "esp1": self._conn[0], "esp2": self._conn[1]})
            threading.Thread(target=self._rx, args=(s, n), daemon=True).start()
        except Exception as e:
            broadcast({"type": "log",  "msg":  f"[ERROR] ESP32 #{n} @ {ip} — {e}"})
            broadcast({"type": "conn", "esp1": self._conn[0], "esp2": self._conn[1]})

    def disconnect(self, n: int):
        idx = n - 1
        try:
            if self._sock[idx]: self._sock[idx].close()
        except Exception: pass
        self._sock[idx] = None
        self._conn[idx] = False
        broadcast({"type": "log",  "msg":  f"[NET] ESP32 #{n} disconnected"})
        broadcast({"type": "conn", "esp1": self._conn[0], "esp2": self._conn[1]})

    def set_ips(self, ip1: str, ip2: str):
        self.ip1 = ip1.strip(); self.ip2 = ip2.strip()
        save_config(self.ip1, self.ip2)
        broadcast({"type": "log", "msg": f"[CFG] IPs saved — {self.ip1} | {self.ip2}"})

    def _rx(self, s: socket.socket, n: int):
        buf = ""
        try:
            while True:
                chunk = s.recv(512)
                if not chunk: break
                self.last_rx[n-1] = time.time()
                buf += chunk.decode("utf-8", errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line: continue
                    if line.startswith("[SONAR]") and n == 1:
                        self._parse_sonar(line)
                    elif line.startswith("[ENC]"):
                        self._parse_enc(line, n)
        except Exception:
            pass
        finally:
            self._conn[n-1] = False
            self._sock[n-1] = None
            broadcast({"type": "log",  "msg":  f"[WARN] ESP32 #{n} connection lost"})
            broadcast({"type": "conn", "esp1": self._conn[0], "esp2": self._conn[1]})

    def _parse_sonar(self, line: str):
        try:
            parts = dict(p.split(":") for p in line.replace("[SONAR]", "").strip().split(","))
            L, F, R = float(parts["L"]), float(parts["F"]), float(parts["R"])
            self.sonar_front = F
            broadcast({"type": "sonar", "L": L, "F": F, "R": R})
            adv_mapper.update_sonar(L, F, R)
            self.mapper.update_sonar(L, F, R)
            self._check_estop(L, F, R)
        except Exception as e:
            logger.debug(f"sonar parse: {e}")

    def _parse_enc(self, line: str, n: int):
        try:
            parts = dict(p.split(":") for p in line.replace("[ENC]", "").strip().split(","))
            broadcast({"type": "encoder", "M": int(parts["M"]),
                       "C": int(parts["C"]), "D": parts.get("D", "FWD"), "ESP": n})
        except Exception as e:
            logger.debug(f"enc parse: {e}")

    def _check_estop(self, L, F, R):
        if not self.estop_enabled or self.estop_active: return
        if self.estop_override:
            if time.time() > self.estop_until: self.estop_override = False
            return
        T = 10.0
        if   L <= T: self._trigger("LEFT",  L)
        elif F <= T: self._trigger("FRONT", F)
        elif R <= T: self._trigger("RIGHT", R)

    def _trigger(self, where: str, dist: float):
        if self.estop_active: return
        self.estop_active = True
        self.raw_send("X")
        reason = f"{where} {dist:.1f} cm"
        broadcast({"type": "log",   "msg":    f"[ESTOP] TRIGGERED — {reason}"})
        broadcast({"type": "estop", "reason": reason})

    def raw_send(self, cmd: str):
        for idx in range(2):
            if self._conn[idx] and self._sock[idx]:
                try: self._sock[idx].sendall(cmd.encode())
                except Exception as e: broadcast({"type": "log", "msg": f"[ERROR] ESP{idx+1}: {e}"})

    def send(self, cmd: str):
        if self.estop_active and cmd not in ("X", " "):
            broadcast({"type": "log", "msg": "[ESTOP] Command blocked"}); return
        sent = False
        for idx in range(2):
            if self._conn[idx] and self._sock[idx]:
                try: self._sock[idx].sendall(cmd.encode()); sent = True
                except Exception as e: broadcast({"type": "log", "msg": f"[ERROR] ESP{idx+1}: {e}"})
        if sent:
            lbl = {"W":"FORWARD","S":"BACKWARD","A":"TURN LEFT","D":"TURN RIGHT","X":"STOP"}.get(cmd, cmd)
            broadcast({"type": "log", "msg": f"[TX] {cmd} >> {lbl}"})


robot = Robot()

# ── Advanced Map Manager ────────────────────────────────────
adv_mapper = AdvancedMapManager(broadcast)

# ── Periodic status broadcaster (async) ─────────────────────
async def periodic_status():
    while True:
        await asyncio.sleep(2)
        now = time.time()
        msg: dict = {
            "type":      "status",
            "mapping":   robot.mapper.running,
            "esp1_conn": robot.conn1,
            "esp2_conn": robot.conn2,
            "sonar_f":   robot.sonar_front,
        }
        if robot.last_rx[0] > 0:
            msg["esp1_lag"] = int((now - robot.last_rx[0]) * 1000)
        if robot.last_rx[1] > 0:
            msg["esp2_lag"] = int((now - robot.last_rx[1]) * 1000)
        await _broadcast_async(msg)

# ── Routes ──────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    from fastapi.responses import Response
    with open(os.path.join("static", "index.html"), encoding="utf-8") as f:
        content = f.read()
    return Response(
        content=content,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )

@app.post("/config")
async def post_config(cfg: ConfigUpdate):
    robot.set_ips(cfg.ip1, cfg.ip2)
    return {"status": "ok"}

@app.post("/shutdown")
async def shutdown():
    def _kill():
        time.sleep(0.4)
        os._exit(0)
    threading.Thread(target=_kill, daemon=True).start()
    return {"status": "shutting down"}

# ── WebSocket Endpoint ───────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global _main_loop
    _main_loop = asyncio.get_event_loop()
    await ws.accept()
    with _clients_lock:
        _clients.append(ws)
    try:
        cfg = load_config()
        await ws.send_json({
            "type": "init",
            "ip1":  robot.ip1 or cfg.get("ip1", ""),
            "ip2":  robot.ip2 or cfg.get("ip2", ""),
            "conn": {"esp1": robot.conn1, "esp2": robot.conn2},
        })
        # Send initial advanced map state to new client
        await ws.send_json(adv_mapper.get_state())
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            cmd = data.get("cmd", "")

            if cmd in ("W", "A", "S", "D", "X"):
                robot.send(cmd)
                adv_mapper.on_drive_cmd(cmd)
            elif cmd == "PING":
                await ws.send_json({"type": "PONG", "ts": data.get("ts", 0)})
            elif cmd == "SET_IPS":
                robot.set_ips(data.get("ip1", ""), data.get("ip2", ""))
            elif cmd == "CONNECT":
                n = int(data.get("esp", 1))
                threading.Thread(target=robot.connect, args=(n,), daemon=True).start()
            elif cmd == "DISCONNECT":
                n = int(data.get("esp", 1))
                threading.Thread(target=robot.disconnect, args=(n,), daemon=True).start()
            elif cmd == "MAP_START":
                robot.mapper.start()
            elif cmd == "MAP_STOP":
                robot.mapper.stop()
            elif cmd == "MAP_CLEAR":
                robot.mapper.clear()
            elif cmd == "MAP_CFG":
                robot.mapper.mode = data.get("mode", "pulse")
                robot.mapper.apply_config(
                    pulse_ms  = data.get("pulse_ms", 400),
                    turn_ms   = data.get("turn_ms",  480),
                    front_thr = data.get("front_thr", 35),
                    diag_thr  = data.get("diag_thr",  25),
                )
            elif cmd == "ESTOP_TOGGLE":
                robot.estop_enabled = bool(data.get("enabled", False))
                if not robot.estop_enabled:
                    robot.estop_active = robot.estop_override = False
                state = "ENABLED" if robot.estop_enabled else "DISABLED"
                broadcast({"type": "log", "msg": f"[ESTOP] Auto E-Stop {state}"})
            # ── Advanced Mapping Commands ───────────────────────────
            elif cmd == "ADV_MAP_LIST":
                await ws.send_json({"type": "adv_map_list", "maps": adv_mapper.list_maps()})
            elif cmd == "ADV_MAP_NEW":
                adv_mapper.new_map(data.get("name", "untitled"))
                st = adv_mapper.get_state(); st["maps_list"] = adv_mapper.list_maps()
                await ws.send_json(st)
            elif cmd == "ADV_MAP_LOAD":
                adv_mapper.load_map(data.get("name", ""))
                st = adv_mapper.get_state(); st["maps_list"] = adv_mapper.list_maps()
                await ws.send_json(st)
            elif cmd == "ADV_MAP_SAVE":
                adv_mapper.save_map()
            elif cmd == "ADV_MAP_CLOSE":
                adv_mapper.close_map()
                st = adv_mapper.get_state(); st["maps_list"] = adv_mapper.list_maps()
                await ws.send_json(st)
            elif cmd == "ADV_MAP_DELETE":
                adv_mapper.delete_map(data.get("name", ""))
                st = adv_mapper.get_state(); st["maps_list"] = adv_mapper.list_maps()
                await ws.send_json(st)
            elif cmd == "ADV_SET_ROOM":
                adv_mapper.set_room(data.get("width", 400), data.get("height", 400))
            elif cmd == "ADV_OBS_ADD":
                adv_mapper.add_obstacle(
                    data.get("name", "Obstacle"),
                    data.get("x1", 0), data.get("y1", 0),
                    data.get("x2", 0), data.get("y2", 0),
                )
            elif cmd == "ADV_OBS_UPDATE":
                adv_mapper.update_obstacle(
                    data.get("id", ""),
                    data.get("name", ""),
                    data.get("x1", 0), data.get("y1", 0),
                    data.get("x2", 0), data.get("y2", 0),
                )
            elif cmd == "ADV_OBS_REMOVE":
                adv_mapper.remove_obstacle(data.get("id", ""))
            elif cmd == "ADV_HEAT_CLEAR":
                adv_mapper.clear_heat()
            elif cmd == "ADV_EXPLORE_START":
                threading.Thread(target=adv_mapper.start_explore, args=(robot,), daemon=True).start()
            elif cmd == "ADV_EXPLORE_STOP":
                adv_mapper.stop_explore(robot)
            elif cmd == "ADV_GET_STATE":
                await ws.send_json(adv_mapper.get_state())
            elif cmd == "ADV_SET_BOT_POS":
                adv_mapper.set_bot_pos(
                    data.get("x", 0), data.get("y", 0), data.get("heading", None)
                )
                await ws.send_json(adv_mapper.get_state())
            elif cmd == "ADV_NAV_TO":
                threading.Thread(
                    target=adv_mapper.navigate_to,
                    args=(robot, float(data.get("tx", 0)), float(data.get("ty", 0))),
                    daemon=True,
                ).start()
            elif cmd == "ADV_NAV_STOP":
                adv_mapper.stop_navigate(robot)

            elif cmd == "ESTOP_OVERRIDE":
                robot.estop_active   = False
                robot.estop_override = True
                robot.estop_until    = time.time() + 3.0
                broadcast({"type": "log", "msg": "[ESTOP] Override — 3s reverse window"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        with _clients_lock:
            if ws in _clients: _clients.remove(ws)

# ── Startup ──────────────────────────────────────────────────
import warnings as _w; _w.filterwarnings("ignore", category=DeprecationWarning)
@app.on_event("startup")
async def startup():
    global _main_loop
    _main_loop = asyncio.get_event_loop()
    asyncio.create_task(periodic_status())

    cfg = load_config()
    robot.ip1 = cfg.get("ip1", "192.168.1.159")
    robot.ip2 = cfg.get("ip2", "192.168.1.162")

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "127.0.0.1"

    sep = "-" * 50
    print(f"\n  {sep}")
    print(f"  DUON Mission Control Server")
    print(f"  {sep}")
    print(f"  Local:   http://localhost:5000")
    print(f"  Network: http://{lan_ip}:5000  <-- open on phone/iPad")
    print(f"  {sep}\n")

# ── Run directly: python web_server.py ───────────────────────
if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    import uvicorn
    PORT = 5000
    # Check if port is already in use
    _test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _test.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        _test.bind(('0.0.0.0', PORT))
        _test.close()
    except OSError:
        print(f"\n  ERROR: Port {PORT} is already in use!")
        print(f"  Another instance of DUON may already be running.")
        print(f"  Close it first, then run this script again.\n")
        input("Press Enter to exit...")
        sys.exit(1)
    uvicorn.run(
        "web_server:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )
