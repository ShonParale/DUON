# 05 — Python Code Explanation

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Files Covered:** `web_server.py` · `advanced_mapping.py`

---

## 📌 Overview

The Python side of DUON has two files:

| File | Purpose |
|------|---------|
| `web_server.py` | Main FastAPI server — bridges browser ↔ ESPs; handles WebSocket, routes, robot control, and basic mapping |
| `advanced_mapping.py` | Advanced map module — obstacle CRUD, sonar heat-mapping, A* pathfinding, autonomous exploration, A→B navigation |

**Entry point:** Run `web_server.py` (via `start_server.bat` or directly with Python).  
**Port:** 5000 for browser, 8080 for ESP TCP connections.

---

## 📁 `web_server.py` — Section-by-Section

### 1. Imports

```python
import asyncio, json, logging, math, os, socket, sys, threading, time
from collections import deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from advanced_mapping import AdvancedMapManager
```

- **FastAPI** — modern async Python web framework; handles HTTP routes and WebSocket connections
- **WebSocket / WebSocketDisconnect** — real-time bidirectional communication with the browser
- **StaticFiles** — serves the `static/` folder (HTML, CSS, JS) at `/static`
- **threading** — used for ESP TCP connections (blocking I/O runs in background threads)
- **asyncio** — for async WebSocket handling and periodic status broadcasts
- **deque** — efficient sliding-window buffer used in `SonarProcessor`
- **AdvancedMapManager** — imported from `advanced_mapping.py`

---

### 2. Configuration — `load_config()` / `save_config()`

```python
CONFIG_FILE = "robot_config.json"

def load_config() -> dict:
    # loads {"ip1": "...", "ip2": "..."} from robot_config.json
    ...

def save_config(ip1: str, ip2: str):
    # saves ESP IP addresses persistently to robot_config.json
    ...
```

- Saves and restores the ESP32 IP addresses between sessions
- File: `robot_config.json` (in the DUON root folder)
- If the file doesn't exist or is corrupted, defaults to `192.168.1.159` and `192.168.1.162`

---

### 3. SonarProcessor Class

```python
class SonarProcessor:
    WINDOW      = 7      # rolling median window size
    SPIKE_RATIO = 1.8    # ratio threshold to detect spike
    SPIKE_ABS   = 40     # absolute cm jump to detect spike
    JITTER_GATE = 3.0    # ignore changes smaller than 3cm (jitter)
    MAX_VALID   = 380.0  # max believable sonar value (cm)
    MIN_VALID   = 2.0    # min believable sonar value (cm)
```

**Purpose:** Cleans up noisy sonar readings from the HC-SR04 sensor.

**`feed(raw_cm)` method logic:**
1. Clamps input to valid range (2–380 cm); out-of-range values set to 380 cm
2. **Spike detection:** If the new reading jumps more than 40 cm AND the ratio exceeds 1.8× compared to the last stable value → reject it (return last stable value)
3. Otherwise, appends to a 7-reading rolling buffer
4. Computes the **median** of the buffer (median is more robust than average against outliers)
5. **Jitter gate:** Only updates the stable value if the median moved more than 3 cm
6. Returns `(filtered_value, changed_flag)`

**Why this matters:** Raw sonar readings from HC-SR04 can spike wildly, especially without resistor conditioning on the ECHO line. This filter keeps the displayed values and the autonomous mapping algorithm stable.

---

### 4. FastAPI App + Static Files

```python
app = FastAPI(title="DUON")
app.mount("/static", StaticFiles(directory="static"), name="static")
```

- Creates the web application instance
- Mounts the `static/` folder — all files (HTML/CSS/JS) inside are served at `/static/...`

---

### 5. WebSocket State & Broadcast

```python
_main_loop: asyncio.AbstractEventLoop | None = None
_clients: list[WebSocket] = []
_clients_lock = threading.Lock()

async def _broadcast_async(msg: dict): ...
def broadcast(msg: dict): ...
```

- `_clients` — list of all currently connected browser WebSocket sessions
- `_clients_lock` — thread lock to safely modify `_clients` from background threads
- `broadcast(msg)` — **thread-safe** function callable from background threads (ESP receiver threads); it schedules the async broadcast on the main event loop using `asyncio.run_coroutine_threadsafe()`
- `_broadcast_async(msg)` — the actual async sender; loops through all clients, sends JSON; removes dead connections automatically

**Message types broadcast to browser:**

| `type` | Content | Trigger |
|--------|---------|---------|
| `sonar` | `{L, F, R}` | Every sonar packet from ESP1 |
| `conn` | `{esp1, esp2}` | On connect/disconnect events |
| `log` | `{msg}` | Any system event (for terminal log on UI) |
| `map` | `{walls, free, path, bot}` | AutoMapper (Mapper page) updates |
| `adv_map` | Full advanced map state | Mapping page updates |
| `status` | Connection status + lag | Every 2 seconds |
| `estop` | `{reason}` | Emergency stop triggered |
| `encoder` | `{M, C, D, ESP}` | Encoder data (future) |

---

### 6. AutoMapper Class

The `AutoMapper` class powers the **Mapper page** (simple autonomous mapping).

```python
class AutoMapper:
    FRONT_THRESHOLD = 35   # cm — stop/turn if front sonar < this
    DIAG_THRESHOLD  = 25   # cm — pre-turn if diagonal sonar < this
    PULSE_MS        = 400  # ms — forward move pulse duration
    TURN_MS         = 480  # ms — 90° turn duration
    SETTLE_MS       = 350  # ms — wait after stop before next action
    SPEED_CM_S      = 18.0 # estimated forward speed in cm/s
```

**Two mapping modes:**

| Mode | Method | Description |
|------|--------|-------------|
| `pulse` | `_step_pulse()` | Move forward in timed bursts; stop, scan, decide |
| `smooth` | `_step_smooth()` | Keep moving continuously; check sensors in loop |

**Decision logic (pulse mode) — `_step_pulse()`:**
```
Wait for sonar reading →
  If Front clear AND Left+Right clear   → Move forward
  If Front clear BUT Right too close    → Pre-turn Left
  If Front clear BUT Left too close     → Pre-turn Right
  If Front blocked:
    Right open                          → Turn Right
    Left open                           → Turn Left
    Both blocked                        → U-Turn (2× turn right)
```

**Dead-reckoning position tracking:**
- `bot_x`, `bot_y` — estimated position in cm (relative to start)
- `heading` — angle in degrees (0 = North/up)
- Each forward pulse adds `SPEED_CM_S × (PULSE_MS/1000)` cm in the heading direction
- Each turn adds ±90° to heading

**Wall/free space tracking:**
- Sonar readings projected to world coordinates using trigonometry
- Coordinates snapped to 4 cm and 6 cm grids for consistency
- Sent to browser as `{walls: [...], free: [...], path: [...], bot: {...}}`

---

### 7. Robot Class

The `Robot` class manages all communication with ESP32 boards.

```python
class Robot:
    def __init__(self):
        self._sock   = [None, None]   # TCP sockets for ESP1, ESP2
        self._conn   = [False, False] # Connection state
        self.ip1     = "..."          # ESP1 IP address
        self.ip2     = "..."          # ESP2 IP address
        self.last_rx = [0.0, 0.0]    # Timestamps of last received data
        self.sonar_front = None       # Latest front sonar value
        self.estop_enabled  = False   # Is auto e-stop armed?
        self.estop_active   = False   # Is e-stop currently triggered?
        self.estop_override = False   # 3-second override window active?
        self.mapper = AutoMapper(self) # Mapper page controller
```

**Key methods:**

| Method | Description |
|--------|-------------|
| `connect(n)` | Opens TCP socket to ESP #n (runs in background thread) |
| `disconnect(n)` | Closes socket to ESP #n |
| `set_ips(ip1, ip2)` | Updates IP addresses and saves to `robot_config.json` |
| `_rx(s, n)` | Background receive thread — reads lines from ESP; parses SONAR and ENC packets |
| `_parse_sonar(line)` | Parses `[SONAR]L:x,F:x,R:x`; broadcasts to browser; feeds AutoMapper and AdvancedMapManager; checks e-stop |
| `_parse_enc(line, n)` | Parses `[ENC]M:x,C:x,D:FWD` (future encoder data); broadcasts to browser |
| `raw_send(cmd)` | Sends command to **both** ESPs without e-stop check (used by AutoMapper) |
| `send(cmd)` | Sends command to both ESPs **with** e-stop check (used by user input) |

**E-Stop logic (`_check_estop`):**
- Only active if `estop_enabled = True`
- If any sonar reading ≤ 10 cm → calls `_trigger()` → sends STOP to both ESPs → broadcasts `estop` message to browser
- `estop_override` — activated for 3 seconds after user presses "Override"; allows reverse movement to escape
- While `estop_active`, the `send()` method blocks all commands except `X` (stop)

---

### 8. HTTP Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Serves `static/index.html` with no-cache headers |
| `/config` | POST | Updates ESP IP addresses (`{ip1, ip2}` JSON body) |
| `/shutdown` | POST | Gracefully kills the Python server after 0.4s delay |

---

### 9. WebSocket Endpoint (`/ws`)

This is the core of the real-time communication. All browser interactions go through here.

**On connection:**
1. Adds browser WebSocket to `_clients` list
2. Sends `init` message with current IPs and connection state
3. Sends current advanced map state

**Command handling (from browser → Python → ESP):**

| Command | Action |
|---------|--------|
| `W/A/S/D/X` | Drive command → `robot.send(cmd)` + `adv_mapper.on_drive_cmd(cmd)` |
| `PING` | Returns `PONG` with timestamp (used for latency measurement) |
| `SET_IPS` | Updates ESP IP addresses |
| `CONNECT` | Connects to ESP #n in background thread |
| `DISCONNECT` | Disconnects from ESP #n |
| `MAP_START/STOP/CLEAR` | Controls AutoMapper (Mapper page) |
| `MAP_CFG` | Updates AutoMapper settings (pulse_ms, turn_ms, thresholds, mode) |
| `ESTOP_TOGGLE` | Arms/disarms the auto e-stop |
| `ESTOP_OVERRIDE` | Activates 3-second override window |
| `ADV_MAP_*` | Advanced Mapping page commands (see table below) |

**Advanced Mapping commands:**

| Command | Action |
|---------|--------|
| `ADV_MAP_LIST` | Returns list of saved map files |
| `ADV_MAP_NEW` | Creates new named map |
| `ADV_MAP_LOAD` | Loads a saved map by name |
| `ADV_MAP_SAVE` | Saves current map to disk |
| `ADV_MAP_CLOSE` | Closes active map (keeps file) |
| `ADV_MAP_DELETE` | Deletes a map file |
| `ADV_SET_ROOM` | Sets room dimensions (width, height in cm) |
| `ADV_OBS_ADD` | Adds obstacle rectangle |
| `ADV_OBS_UPDATE` | Updates existing obstacle |
| `ADV_OBS_REMOVE` | Removes obstacle by ID |
| `ADV_HEAT_CLEAR` | Clears sonar heat-map data |
| `ADV_EXPLORE_START` | Starts autonomous exploration |
| `ADV_EXPLORE_STOP` | Stops autonomous exploration |
| `ADV_GET_STATE` | Returns full map state to this client |
| `ADV_SET_BOT_POS` | Manually set robot position on map |
| `ADV_NAV_TO` | Navigate robot to target (tx, ty) using A* |
| `ADV_NAV_STOP` | Stop active navigation |

---

### 10. Startup & Periodic Status

```python
@app.on_event("startup")
async def startup():
    _main_loop = asyncio.get_event_loop()
    asyncio.create_task(periodic_status())  # runs every 2s
    # Load saved IPs from config
    # Detect LAN IP and print banner to console
```

**`periodic_status()`** — every 2 seconds, broadcasts to all clients:
```json
{
  "type": "status",
  "mapping": true/false,
  "esp1_conn": true/false,
  "esp2_conn": true/false,
  "sonar_f": 120.5,
  "esp1_lag": 105,
  "esp2_lag": 0
}
```
`esp1_lag` / `esp2_lag` — milliseconds since last data received from each ESP (used to detect silent disconnections).

---

## 📁 `advanced_mapping.py` — Section-by-Section

### 1. Constants & Init

```python
MAPS_DIR = "maps"    # folder where map JSON files are stored
GRID_RES = 20        # cm per A* grid cell
GRID_PAD = 1         # safety padding cells around obstacles
```

**`AdvancedMapManager.__init__(broadcast_fn)`:**
- Takes the `broadcast` function as a parameter (dependency injection)
- Creates `maps/` directory if not present
- Initializes all state: active map, room dimensions, obstacles, heat map, robot pose, drive tracking, explore/navigate flags
- Starts a background broadcast loop thread (`_bcast_loop`) that pushes state every 400ms when a map is active

---

### 2. Dead-Reckoning (`_flush_motion`)

```python
def _flush_motion(self):
    elapsed = time.time() - self._drive_start
    cmd = self._drive_cmd
    if cmd == 'W':
        d = elapsed * SPEED_CM_S
        bot_x += d * sin(heading_rad)
        bot_y += d * cos(heading_rad)
    elif cmd == 'S':
        # Subtract (reverse)
    elif cmd == 'A':
        heading -= (90/TURN_90_MS) * elapsed * 1000   # degrees
    elif cmd == 'D':
        heading += ...
    # Clamp to room bounds
```

- Called every time a new command arrives or state is requested
- Integrates elapsed time × speed/angular_rate into position estimate
- This is how the robot tracks its position on the map without encoders

**Limitation:** Dead-reckoning drifts over time. Actual distance and turn angle depend on battery level, surface friction, and motor variance.

---

### 3. Sonar Heat-Map (`_project_heat`)

```python
def _project_heat(self):
    for dist, angle_deg in [
        (sonar_L, -45),
        (sonar_F,   0),
        (sonar_R,  45),
    ]:
        if dist < 375:
            hx = bot_x + dist * sin(heading + angle_deg)
            hy = bot_y + dist * cos(heading + angle_deg)
            pt = [round(hx/5)*5, round(hy/5)*5]
            heat_map.append(pt)  # max 800 points kept
```

Projects each sonar ray into world coordinates and adds the endpoint to the heat map — showing where obstacles were detected relative to the robot's estimated position. Snapped to a 5 cm grid. Keeps only the latest 800 points.

---

### 4. Map Lifecycle (CRUD)

| Method | Description |
|--------|-------------|
| `list_maps()` | Returns sorted list of `.json` filenames in `maps/` |
| `new_map(name)` | Resets state, sets name, saves blank map, pushes state |
| `load_map(name)` | Reads `maps/<name>.json`; restores room size, obstacles, heat map |
| `save_map()` | Writes current state to `maps/<active_map>.json` |
| `close_map()` | Clears state in memory; keeps the file on disk |
| `delete_map(name)` | Removes the file; clears state if it was the active map |

**Map JSON format:**
```json
{
  "width": 400,
  "height": 400,
  "resolution": 10,
  "obstacles": [
    {"id": "abc12345", "name": "Wall", "x1": 50, "y1": 50, "x2": 150, "y2": 60}
  ],
  "heat_map": [[100, 80], [105, 85], ...]
}
```

---

### 5. Obstacle CRUD

Each obstacle is a named rectangle defined by two corner points (x1,y1) and (x2,y2) in cm.

```python
add_obstacle(name, x1, y1, x2, y2)   # Generates UUID id, appends to list
update_obstacle(id, name, x1,y1,x2,y2) # Finds by id, updates fields
remove_obstacle(id)                    # Filters out by id
```

Obstacles are drawn manually by the user in the **Mapping page** canvas (like MS Paint).

---

### 6. Autonomous Exploration (`start_explore` / `_explore_loop`)

Runs in a background thread. Uses the same reactive decision logic as AutoMapper:

```
Loop while self._exploring:
  Read sonar L, F, R
  If Front clear AND diagonals clear → pulse forward (PULSE_MS)
  If Front clear AND right blocked   → turn left (PULSE_MS)
  If Front clear AND left blocked    → turn right (PULSE_MS)
  If Front blocked:
    Right open → turn right 90°
    Left open  → turn left 90°
    Both blocked → U-turn (2× right 90°)
  → Dead-reckoning updates via on_drive_cmd()
```

Each movement call uses `robot.raw_send()` (bypasses e-stop check — the explore loop manages its own safety via sonar thresholds).

---

### 7. A* Pathfinding

#### `_build_grid()`

Converts obstacles to a boolean occupancy grid:
- Grid cell size = `GRID_RES` (20 cm per cell)
- Each obstacle rectangle is rasterised into the grid with 1-cell safety padding (`GRID_PAD`)
- Returns `grid[col][row]` where `True` = occupied

#### `_astar(grid, cols, rows, sx, sy, gx, gy)`

Standard A* implementation:
- **Heuristic:** Manhattan distance
- **Directions:** 8-directional (including diagonals; diagonal step cost = 1.414)
- **Goal adjustment:** If target cell is blocked, finds nearest free cell within 2-cell radius
- Returns list of `(col, row)` grid cells from start to goal

#### `_plan_path(tx, ty)`

Wrapper that builds grid, converts world coordinates to grid cells, runs A*, and converts grid path back to world coordinates (cell centres in cm).

---

### 8. A→B Navigation (`navigate_to` / `_navigate_loop`)

```
Plan path from current bot position to (tx, ty)
If no path → abort

For each waypoint in path:
  1. Check front sonar:
     If obstacle ahead (< FRONT_THR):
       Turn away from blocked side
       Replan path from current position
       Restart waypoint loop
  2. _move_to_waypoint(robot, wx, wy):
       Compute needed heading (atan2)
       Turn to face waypoint (proportional to angle difference)
       Move forward for calculated time
  3. Push state update to browser

On completion → broadcast "Reached target"
On stop → send X command, clear path
```

**`_move_to_waypoint(robot, wx, wy)`:**
1. Computes distance to waypoint; skips if < 12 cm (already close)
2. Computes required heading using `atan2(dx, dy)`
3. Turns proportionally: `turn_ms = (angle_diff / 90°) × TURN_90_MS`
4. Moves forward: `move_ms = (dist / SPEED_CM_S) × 1000` (capped at 4× PULSE_MS)

---

### 9. State Broadcasting

```python
def _state_dict(self):
    return {
        'type': 'adv_map',
        'active_map': ..., 'room_width': ..., 'room_height': ...,
        'obstacles': [...], 'heat_map': [...last 500...],
        'bot': {'x': bot_x, 'y': bot_y, 'h': heading},
        'exploring': ..., 'navigating': ...,
        'nav_path': [...], 'nav_target': [tx, ty],
    }
```

`get_state()` adds `maps_list` to `_state_dict()` — used when a new browser connects so it immediately gets the full picture.

`_bcast_loop()` — background thread that calls `_push_state()` every 400ms while a map is active, exploring, or navigating.

---

## 🔄 End-to-End Data Flow Summary

```
User presses 'W' on keyboard
     ↓
Browser (JavaScript) → WebSocket → Python /ws endpoint
     ↓
ws_endpoint receives {"cmd": "W"}
     ↓
robot.send("W") → sends b"W" to ESP1 TCP socket
               → sends b"W" to ESP2 TCP socket
               → adv_mapper.on_drive_cmd("W")
     ↓
ESP1 receives 'W' → left motors forward
ESP2 receives 'W' → right motors forward (polarity-swapped)
     ↓
ESP1 reads sonars → sends "[SONAR]L:x,F:x,R:x\n" every 100ms
     ↓
robot._rx() thread receives line → robot._parse_sonar()
     ↓
broadcast({"type":"sonar","L":x,"F":x,"R":x})
     ↓
All connected browsers receive sonar update via WebSocket
     ↓
JavaScript updates sonar display gauges in Drive page
```

---

## 🛠️ Running & Debugging

| Situation | Action |
|-----------|--------|
| App not starting | Right-click `web_server.py` → Edit with IDLE → Run (F5) to see full errors |
| Port 5000 in use | Another DUON instance running — close it via Task Manager |
| Python + Arduino IDE serial conflict | Close Arduino Serial Monitor before running Python (and vice versa) |
| ESP not connecting to Python | Check IP address; try resetting ESP; restart Python server |
| WebSocket error in browser | Open browser DevTools (F12) → Console for error details |

---

## 📦 Python Dependencies

Install via `setup.bat` or manually:

```
pip install fastapi uvicorn websockets pydantic python-multipart
```

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework for HTTP + WebSocket |
| `uvicorn` | ASGI server that runs FastAPI |
| `websockets` | WebSocket protocol support |
| `pydantic` | Data validation for API request models |
| `python-multipart` | Form data support (required by FastAPI) |

All standard library modules (`asyncio`, `socket`, `threading`, `json`, `math`, `heapq`, `uuid`, etc.) require no installation.

---

*Document 5 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
