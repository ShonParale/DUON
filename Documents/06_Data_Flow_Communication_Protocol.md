# 06 — Data Flow & Communication Protocol

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel

---

## 🗺️ System Communication Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (any device on Wi-Fi)                                  │
│  HTML + CSS + JavaScript                                        │
└────────────┬────────────────────────────────────────────────────┘
             │  WebSocket ws://laptop:5000/ws  (JSON messages)
             │  HTTP GET/POST http://laptop:5000
┌────────────▼────────────────────────────────────────────────────┐
│  Laptop — Python FastAPI Server (web_server.py)                 │
│  Port 5000 (browser-facing) | Port 8080 (ESP-facing TCP client) │
└────────────┬──────────────────────────────────┬─────────────────┘
             │  TCP Socket :8080                │  TCP Socket :8080
┌────────────▼──────────┐           ┌───────────▼──────────────┐
│  ESP32 #1             │           │  ESP32 #2                │
│  TCP Server :8080     │           │  TCP Server :8080        │
│  Left motors + Sonars │           │  Right motors only       │
└───────────────────────┘           └──────────────────────────┘
```

---

## 📡 Protocol 1 — Browser ↔ Python (WebSocket)

### Transport Details

| Property | Value |
|----------|-------|
| Protocol | WebSocket (RFC 6455) |
| URL | `ws://[laptop-ip]:5000/ws` |
| Data format | JSON (text frames) |
| Direction | Full duplex (bidirectional) |
| Reconnect | Auto-reconnect after 2 seconds on disconnect |
| Heartbeat | PING/PONG every 5 seconds |

---

### Messages: Browser → Python (Commands)

All commands use the format: `{"cmd": "COMMAND_NAME", ...optional fields}`

#### Drive Commands

| Message | Effect |
|---------|--------|
| `{"cmd": "W"}` | Forward |
| `{"cmd": "S"}` | Backward |
| `{"cmd": "A"}` | Turn left |
| `{"cmd": "D"}` | Turn right |
| `{"cmd": "X"}` | Stop |

#### Connection Commands

| Message | Fields | Effect |
|---------|--------|--------|
| `{"cmd": "CONNECT"}` | `esp: 1 or 2` | Connect to ESP #n |
| `{"cmd": "DISCONNECT"}` | `esp: 1 or 2` | Disconnect from ESP #n |
| `{"cmd": "SET_IPS"}` | `ip1, ip2` | Update ESP IP addresses |
| `{"cmd": "PING"}` | `ts: timestamp_ms` | Latency check |

#### Mapper Commands

| Message | Fields | Effect |
|---------|--------|--------|
| `{"cmd": "MAP_START"}` | — | Start auto-mapping |
| `{"cmd": "MAP_STOP"}` | — | Stop auto-mapping |
| `{"cmd": "MAP_CLEAR"}` | — | Reset map data |
| `{"cmd": "MAP_CFG"}` | `mode, pulse_ms, turn_ms, front_thr, diag_thr` | Update mapper settings |

#### E-Stop Commands

| Message | Fields | Effect |
|---------|--------|--------|
| `{"cmd": "ESTOP_TOGGLE"}` | `enabled: bool` | Arm/disarm auto e-stop |
| `{"cmd": "ESTOP_OVERRIDE"}` | — | Allow 3s reverse window |

#### Advanced Mapping Commands

| Message | Fields | Effect |
|---------|--------|--------|
| `{"cmd": "ADV_MAP_LIST"}` | — | Get list of saved maps |
| `{"cmd": "ADV_MAP_NEW"}` | `name` | Create new map |
| `{"cmd": "ADV_MAP_LOAD"}` | `name` | Load map from disk |
| `{"cmd": "ADV_MAP_SAVE"}` | — | Save current map |
| `{"cmd": "ADV_MAP_CLOSE"}` | — | Close active map |
| `{"cmd": "ADV_MAP_DELETE"}` | `name` | Delete map file |
| `{"cmd": "ADV_SET_ROOM"}` | `width, height` | Set room dimensions (cm) |
| `{"cmd": "ADV_OBS_ADD"}` | `name, x1, y1, x2, y2` | Add obstacle rectangle |
| `{"cmd": "ADV_OBS_UPDATE"}` | `id, name, x1, y1, x2, y2` | Update obstacle |
| `{"cmd": "ADV_OBS_REMOVE"}` | `id` | Remove obstacle |
| `{"cmd": "ADV_HEAT_CLEAR"}` | — | Clear sonar heat-map |
| `{"cmd": "ADV_EXPLORE_START"}` | — | Start autonomous exploration |
| `{"cmd": "ADV_EXPLORE_STOP"}` | — | Stop autonomous exploration |
| `{"cmd": "ADV_GET_STATE"}` | — | Request full map state |
| `{"cmd": "ADV_SET_BOT_POS"}` | `x, y, heading` | Set robot position on map |
| `{"cmd": "ADV_NAV_TO"}` | `tx, ty` | Navigate to target (cm) |
| `{"cmd": "ADV_NAV_STOP"}` | — | Abort navigation |

---

### Messages: Python → Browser (Updates)

All updates are JSON objects with a `type` field.

#### `type: "init"` — Sent on new WebSocket connection

```json
{
  "type": "init",
  "ip1": "192.168.1.159",
  "ip2": "192.168.1.162",
  "conn": {"esp1": false, "esp2": false}
}
```

#### `type: "conn"` — ESP connection state change

```json
{"type": "conn", "esp1": true, "esp2": false}
```

#### `type: "sonar"` — Sonar reading (every 100ms from ESP1)

```json
{"type": "sonar", "L": 45.2, "F": 120.0, "R": 38.7}
```
- L = Left sonar (cm), F = Front sonar (cm), R = Right sonar (cm)
- Values ≥ 380 mean no object in range

#### `type: "log"` — Terminal log message

```json
{"type": "log", "msg": "[TX] W >> FORWARD"}
```
Log prefixes and their colour coding in the UI:
- `[TX]` → blue (outgoing command)
- `[NET]`, `[CFG]` → green (network events)
- `[ERROR]`, `[ERR]` → red
- `[WARN]`, `[ESTOP]`, `[AUTO]` → orange

#### `type: "status"` — Periodic status (every 2 seconds)

```json
{
  "type": "status",
  "mapping": false,
  "esp1_conn": true,
  "esp2_conn": true,
  "sonar_f": 120.5,
  "esp1_lag": 105,
  "esp2_lag": 98
}
```
- `esp1_lag` / `esp2_lag` = ms since last data received from each ESP

#### `type: "map"` — Mapper page map update

```json
{
  "type": "map",
  "walls": [[x, y], [x, y], ...],
  "free":  [[x, y], [x, y], ...],
  "path":  [[x, y], [x, y], ...],
  "bot":   {"x": 50.0, "y": 120.0, "h": 90.0}
}
```
All coordinates in cm. Maximum 600 path points sent per update.

#### `type: "adv_map"` — Advanced Mapping page update

```json
{
  "type": "adv_map",
  "active_map": "room1",
  "room_width": 400.0,
  "room_height": 400.0,
  "resolution": 10,
  "obstacles": [
    {"id": "abc12345", "name": "Table", "x1": 50, "y1": 50, "x2": 150, "y2": 100}
  ],
  "heat_map": [[100, 80], [105, 85], ...],
  "bot": {"x": 50.0, "y": 30.0, "h": 0.0},
  "exploring": false,
  "navigating": false,
  "nav_path": [[x, y], ...],
  "nav_target": [200.0, 300.0]
}
```

#### `type: "adv_map_list"` — List of saved maps

```json
{"type": "adv_map_list", "maps": ["room1", "room2", "lab"]}
```

#### `type: "estop"` — Emergency stop triggered

```json
{"type": "estop", "reason": "FRONT 8.2 cm"}
```

#### `type: "PONG"` — Ping response

```json
{"type": "PONG", "ts": 1714123456789}
```
Browser calculates latency as `Date.now() - ts`.

#### `type: "encoder"` — Encoder data (future, not yet active)

```json
{"type": "encoder", "M": 1, "C": 1234, "D": "FWD", "ESP": 1}
```

---

## 📡 Protocol 2 — Python ↔ ESP32 (TCP Socket)

### Transport Details

| Property | Value |
|----------|-------|
| Protocol | TCP (raw socket) |
| Port | 8080 (ESP32 acts as SERVER) |
| Data format | Plain text, newline-delimited |
| Connection | Python connects TO the ESP (ESP is server) |
| Reconnect | Manual — user clicks Connect in web dashboard |
| Timeout | 5 seconds on initial connect attempt |

---

### Messages: Python → ESP32 (Motor Commands)

Single character, sent as raw bytes:

| Byte | Command | Action |
|------|---------|--------|
| `W` or `w` | Forward | Both ESPs drive motors forward |
| `S` or `s` | Backward | Both ESPs drive motors backward |
| `A` or `a` | Turn Left | Left motors backward, right motors forward |
| `D` or `d` | Turn Right | Left motors forward, right motors backward |
| `X`, `x`, or ` ` | Stop | All motors off |

- Commands are sent to **both ESP1 and ESP2 simultaneously**
- `robot.send(cmd)` checks e-stop before sending
- `robot.raw_send(cmd)` bypasses e-stop (used by AutoMapper/Explorer)

---

### Messages: ESP1 → Python (Data)

Newline-terminated strings sent periodically:

#### Sonar Data (every 100ms)

```
[SONAR]L:45.2,F:120.0,R:38.7\n
```

Parsed by `Robot._parse_sonar()`:
```python
parts = dict(p.split(":") for p in line.replace("[SONAR]", "").strip().split(","))
L = float(parts["L"])
F = float(parts["F"])
R = float(parts["R"])
```

#### Command Echo (on each command received)

```
[ESP1] FORWARD\n
[ESP1] BACKWARD\n
[ESP1] TURN LEFT\n
[ESP1] TURN RIGHT\n
[ESP1] STOP\n
```

These are logged to the browser terminal but not otherwise processed.

#### Boot/Connection Messages

```
[ESP1] B1 Left side ready\n
```

---

### Messages: ESP2 → Python (Data)

#### Command Echo (on each command received)

```
[ESP2] FORWARD\n
[ESP2] BACKWARD\n
[ESP2] TURN LEFT\n
[ESP2] TURN RIGHT\n
[ESP2] STOP\n
```

#### Boot/Connection Message

```
[ESP2] B2 Right side ready\n
```

> ESP2 sends NO sensor data — only command confirmations.

---

### Future Message Format — Encoder (Not Yet Active)

When encoder code is implemented, the planned format is:

```
[ENC]M:1,C:1234,D:FWD\n
```

- `M` = Motor number (1–4)
- `C` = Encoder tick count
- `D` = Direction (`FWD` or `REV`)

Already handled in `Robot._parse_enc()` — just needs the ESP firmware to send it.

---

## 🔄 Complete Data Flow Scenarios

### Scenario 1: User Presses 'W' (Forward)

```
1. Browser keydown event fires
2. main.js keymap maps 'w' → 'W'
3. send({cmd: 'W'}) → WebSocket frame to Python
4. ws_endpoint receives {"cmd": "W"}
5. robot.send("W"):
   a. Checks estop_active — if active, blocks and logs
   b. Sends b"W" to ESP1 TCP socket
   c. Sends b"W" to ESP2 TCP socket
   d. Broadcasts {"type":"log","msg":"[TX] W >> FORWARD"}
6. adv_mapper.on_drive_cmd("W") — starts dead-reckoning timer
7. ESP1 receives 'W':
   a. ledcWrite(B1_RPWM, 255), ledcWrite(B1_LPWM, 0)
   b. Left motors spin forward
   c. Sends "[ESP1] FORWARD\n" back to Python
8. ESP2 receives 'W':
   a. ledcWrite(B2_RPWM, 0), ledcWrite(B2_LPWM, 255)  [polarity swapped]
   b. Right motors spin forward
   c. Sends "[ESP2] FORWARD\n" back to Python
9. Robot moves forward ✓
```

### Scenario 2: Sonar Reading Arrives

```
1. ESP1 non-blocking sonar state machine completes a read cycle
2. Every 100ms: snprintf("[SONAR]L:45.2,F:120.0,R:38.7") → TCP send to Python
3. Robot._rx() background thread receives data
4. Line parsed by Robot._parse_sonar():
   a. Values extracted: L=45.2, F=120.0, R=38.7
   b. robot.sonar_front = 120.0
   c. broadcast({"type":"sonar","L":45.2,"F":120.0,"R":38.7})
   d. adv_mapper.update_sonar(45.2, 120.0, 38.7) — heat map updated
   e. robot.mapper.update_sonar(45.2, 120.0, 38.7) — AutoMapper updated
   f. _check_estop(45.2, 120.0, 38.7) — e-stop check
5. All browsers receive {"type":"sonar",...} via WebSocket
6. main.js handleMsg() → updateGauges(45.2, 120.0, 38.7)
7. SVG arc gauges animate to new values, colour-coded by proximity
```

### Scenario 3: Emergency Stop Triggers

```
1. estop_enabled = True (user armed auto e-stop)
2. Sonar update arrives: F = 8.2 cm
3. _check_estop(L, F=8.2, R) called
4. F <= 10.0 → _trigger("FRONT", 8.2)
5. estop_active = True
6. raw_send("X") → motors stop immediately on both ESPs
7. broadcast({"type":"log","msg":"[ESTOP] TRIGGERED — FRONT 8.2 cm"})
8. broadcast({"type":"estop","reason":"FRONT 8.2 cm"})
9. Browser shows E-Stop modal dialog
10. Any further drive commands blocked (robot.send() checks estop_active)
11. User clicks "Override":
    a. Browser sends {"cmd":"ESTOP_OVERRIDE"}
    b. estop_active = False, estop_override = True
    c. estop_until = now + 3.0 seconds
    d. broadcast log: "Override — 3s reverse window"
    e. User can reverse robot to clear obstacle
12. After 3 seconds: estop_override = False, e-stop re-arms
```

### Scenario 4: A* Navigation

```
1. User sets bot start position on Mapping page canvas
2. User clicks goal point → ADV_NAV_TO {tx, ty} sent to Python
3. AdvancedMapManager.navigate_to(robot, tx, ty) called
4. Background thread starts _navigate_loop(robot, tx, ty):
   a. _plan_path(tx, ty):
      - _build_grid() — obstacles → boolean occupancy grid
      - _astar() — finds path on grid (A*, Manhattan heuristic, 8-dir)
      - Grid cells → world coordinates (cm)
   b. nav_path broadcast to browser (canvas shows planned route)
   c. For each waypoint:
      - Check sonar_F: if < 35cm → turn away, replan
      - _move_to_waypoint(robot, wx, wy):
        * Compute heading delta (atan2)
        * Turn command (proportional to angle)
        * Forward command (proportional to distance)
      - Push state update to browser
5. Reach final waypoint → broadcast "Reached target"
6. Motors stop, nav_path cleared
```

---

## ⚡ Timing & Latency Reference

| Event | Typical Interval | Notes |
|-------|-----------------|-------|
| Sonar reading per sensor | ~33ms | 3 sensors cycling continuously |
| Sonar packet to Python | 100ms | Fixed interval in ESP1 firmware |
| Sonar update to browser | ~100ms | As soon as Python receives from ESP |
| Status broadcast | 2000ms | Periodic task in Python |
| Adv map state broadcast | 400ms | While map/explore/navigate is active |
| WebSocket ping | 5000ms | Latency measurement |
| Motor command latency | <50ms | Keyboard → browser → Python → ESP |
| TCP connect timeout | 5000ms | If ESP is unreachable |
| E-Stop override window | 3000ms | After user clicks override |

---

## 🔐 Data Validation & Error Handling

| Layer | Validation |
|-------|-----------|
| Python WebSocket | `json.loads()` in try/except; malformed JSON silently discarded |
| Python sonar parse | try/except; parse errors logged at DEBUG level only |
| Python encoder parse | try/except; parse errors logged at DEBUG level only |
| Python TCP connect | 5s timeout; exception caught; error broadcast to browser |
| Python ESP send | Exception caught per-socket; logs error, continues to next ESP |
| Browser WebSocket | try/catch in `handleMsg()`; parse errors logged to console only |
| ESP32 echo timeout | 25ms timeout per sonar reading → treated as 400cm (no object) |
| ESP32 client drop | TCP read returns empty → `_conn[n]` cleared; disconnect broadcast |

---

*Document 6 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
