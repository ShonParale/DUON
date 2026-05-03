# 00 — Detailed Knowledge Transfer

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Purpose:** In-depth technical knowledge transfer for developers, students, and maintainers.

---

## 👥 Team Profiles

| Name | Role | GitHub | LinkedIn | Portfolio |
|------|------|--------|----------|-----------|
| Shon Parale | Lead Developer | [ShonParale](https://github.com/ShonParale) | [linkedin.com/in/shonparale](https://www.linkedin.com/in/shonparale/) | [Portfolio](https://sites.google.com/view/shonparale/home) |
| Vedant Patel | Developer | [vedu007lol](https://github.com/vedu007lol) | [linkedin.com/in/-vedantpatel](https://www.linkedin.com/in/-vedantpatel/) | [Portfolio](https://drive.google.com/file/d/1U9l_l_AUNgH8ZVXr-0SING72Od8F5QmS/view?usp=sharing) |

---

## 🧠 Project Concept & Philosophy

DUON stands for **Dynamic Ultrasonic Operations & Navigations**. The project is a 4-wheel drive robot built for a university robotics/engineering course. The core idea is:

- **Wireless control** over local Wi-Fi from any device (PC, phone, tablet) via a web browser — no app installs needed
- **Sensor-driven awareness** via 3 ultrasonic sensors giving the robot spatial perception
- **Dual-processor architecture** — two ESP32s share the processing load; one per motor driver side
- **Layered autonomy** — from pure manual driving to sonar-aided mapping to full A* pathfinding navigation
- **Portable and self-contained** — the entire project folder can be copied to any Windows laptop and run immediately after `setup.bat`

The project is intentionally designed to be **extendable**: encoders are pre-wired, camera integration is planned, and the web architecture supports Cloudflare Tunnel for remote access without changing any code.

---

## 🏗️ Architecture — Deep Dive

### Three-Tier Design

```
TIER 1: Hardware
  ESP32 #1  ←→  BTS7960 B1  ←→  M1 + M3 (Left motors)
  ESP32 #1  ←→  HC-SR04 ×3  (All sonar sensors)
  ESP32 #2  ←→  BTS7960 B2  ←→  M2 + M4 (Right motors)

TIER 2: Backend (Laptop)
  web_server.py    — FastAPI + WebSocket server (port 5000)
  advanced_mapping.py — Map lifecycle, A*, exploration

TIER 3: Frontend (Browser — any device on Wi-Fi)
  static/index.html    — Single-page application
  static/js/main.js    — WebSocket, controls, Mapper canvas
  static/js/mapping.js — Advanced Mapping page logic
  static/css/style.css — Full theming system (dark/light)
```

### Communication Layers

| Layer | Protocol | Port | Direction | Purpose |
|-------|----------|------|-----------|---------|
| Browser ↔ Python | WebSocket (ws://) | 5000 | Bidirectional | Real-time commands and data |
| Python ↔ ESP32 | TCP Socket | 8080 | Bidirectional | Motor commands + sonar data |
| Browser → Python | HTTP GET | 5000 | One-way | Serve HTML/CSS/JS |
| Browser → Python | HTTP POST | 5000 | One-way | `/config`, `/shutdown` |

### Why These Technology Choices?

| Choice | Reason |
|--------|--------|
| ESP32 over Arduino Uno | Built-in Wi-Fi, dual-core, hardware PWM, more GPIOs |
| TCP Socket for ESP comms | Native ESP32 support; reliable on LAN; no broker needed |
| WebSocket for browser | Real-time bidirectional; avoids polling latency |
| FastAPI over Flask | Async support; WebSocket built-in; faster; modern |
| Single HTML file | Easy deployment; no build step; portable |
| 2 ESPs (1 per driver) | Prevents BTS7960 conflict; doubles processing capacity |

---

## ⚙️ Hardware — Deep Dive

### ESP32 Details

- **Model:** Generic ESP32 DevKit with USB Type-C port
- **CPU:** Dual-core Xtensa LX6 @ 240 MHz
- **Wi-Fi:** 802.11 b/g/n — **2.4 GHz only** (5 GHz not supported)
- **PWM:** Hardware LEDC controller used for motor PWM signals
- **GPIO voltage:** 3.3V logic (important for HC-SR04 ECHO which outputs 5V)
- **Flash:** 4MB (more than enough for firmware)
- **Programming:** Arduino C++ via Arduino IDE

### BTS7960 Motor Driver Details

- **Max continuous current:** 43A
- **Operating voltage:** 6–27V motor side, 5V logic side
- **PWM frequency supported:** Up to 25 kHz (we use 5 kHz)
- **Built-in protection:** Overcurrent, overtemperature, undervoltage lockout
- **Fail-safe behavior:** Driver shuts off on fault; manual reset (ESP32 restart) required
- **Control:** RPWM = forward PWM signal, LPWM = reverse PWM signal; R_EN and L_EN must be HIGH to enable

### HC-SR04 Ultrasonic Sensor Details

- **Operating voltage:** 5V
- **Trigger:** 10µs HIGH pulse on TRIG pin
- **Echo:** HIGH pulse on ECHO pin; duration proportional to distance
- **Range:** 2 cm – 400 cm
- **Formula:** `distance_cm = pulse_duration_µs / 58.0`
- **Update rate:** ~10 Hz per sensor (100ms cycle in firmware)
- **⚠️ Issue:** ECHO outputs 5V but ESP32 GPIO max is 3.3V — voltage divider required (not yet implemented)

### Motor & Encoder Details

- **Type:** DC gearmotor with quadrature encoder
- **Encoder output:** A/B channels + Index; only A channel is currently wired
- **Encoder VCC:** Separate 5V battery pack supply
- **Current status:** Encoders are wired but **not active in firmware**
- **Why needed:** Without encoder feedback, position tracking relies on dead-reckoning (time × estimated speed), which drifts

### Power System

```
LiPo Battery
  ├── B+ → BTS7960 B1 B+  (left motor power)
  ├── B+ → BTS7960 B2 B+  (right motor power)
  ├── B– → Common GND rail
  └── → Buck Converter (5V regulated)
        ├── → BTS7960 B1 VCC, R_EN, L_EN
        ├── → BTS7960 B2 VCC, R_EN, L_EN
        └── → Common GND

Battery Pack (5V)
  └── → Encoder VCC (all 4 motors)

USB Power Bank #1 → ESP32 #1 (via USB-C)
USB Power Bank #2 → ESP32 #2 (via USB-C)

NOTE: Motor power and ESP32 power are intentionally SEPARATE.
      You can safely turn off motor power during code upload/testing.
```

---

## 💻 Software — Deep Dive

### `web_server.py` — Architecture

The main Python file is structured into these logical sections:

1. **Config management** — Load/save ESP IP addresses to `robot_config.json`
2. **SonarProcessor** — Rolling median filter with spike rejection and jitter gating for cleaning raw HC-SR04 data
3. **FastAPI app** — Mounts static files, defines routes
4. **WebSocket broadcast system** — Thread-safe broadcast to all connected browsers
5. **AutoMapper** — Autonomous mapping engine for the Mapper page (pulse & smooth modes)
6. **Robot class** — Manages TCP sockets to both ESPs; handles motor commands, sonar parsing, encoder parsing, and emergency stop logic
7. **HTTP routes** — `/` (serve HTML), `/config` (update IPs), `/shutdown` (kill server)
8. **WebSocket endpoint `/ws`** — Receives all browser commands; routes them to Robot/AutoMapper/AdvancedMapManager
9. **Startup event** — Loads config, detects LAN IP, starts periodic status task

### `advanced_mapping.py` — Architecture

1. **Dead-reckoning engine** — Tracks bot X/Y/heading by integrating time × speed from drive commands
2. **Sonar heat-map** — Projects sonar ray endpoints to world coordinates; stored as 2D point list (max 800 points)
3. **Obstacle CRUD** — Named rectangle obstacles with UUID IDs; stored in map JSON
4. **Map lifecycle** — Create/save/load/close/delete maps as JSON files in `maps/` folder
5. **Autonomous exploration** — Reactive wall-following logic identical to AutoMapper
6. **A* pathfinding** — Grid-based occupancy map from obstacles; Manhattan heuristic; 8-directional movement; goal fallback if target cell is blocked
7. **A→B navigation** — Plans path, executes waypoint-by-waypoint, replans dynamically if obstacle detected
8. **State broadcast** — Periodic 400ms push to all browsers when map/explore/navigate is active

### `static/js/main.js` — Architecture

1. **Theme system** — Dark/light toggle stored in localStorage; applies `data-theme` attribute to root
2. **Page navigation** — Single-page app; shows/hides `.page` divs; lazy-initialises canvas on Mapper/Mapping pages
3. **WebSocket client** — Connects to `ws://host/ws`; auto-reconnects every 2s on disconnect; PING/PONG latency measurement every 5s
4. **Message handler** — Routes incoming WebSocket messages by `type` field to correct UI update function
5. **D-Pad controls** — Mouse/touch events; sends command on press, sends `X` on release
6. **Keyboard handler** — Global keydown/keyup listener; supports WASD, Arrow keys, Numpad 8/4/6/2/5; prevents re-fire on key hold
7. **Omni joystick** — Pointer events; 8-directional with dead zone; sends command only on direction change
8. **Vertical joystick** — Forward/backward axis slider
9. **Horizontal joystick** — Left/right axis slider
10. **Sonar gauges** — SVG arc progress indicators; colour-coded (green/orange/red based on distance thresholds)
11. **Mapper canvas** — HTML5 Canvas; draws grid, free space (green), path (cyan), walls (red), bot (yellow arrow); supports pan (drag) and zoom (scroll wheel); double-click resets view
12. **QR code generator** — Uses `qrcode.min.js` (local, no internet); generates QR from current URL for easy phone access
13. **E-Stop system** — Manual stop button; auto e-stop toggle; modal dialog on trigger; 3-second override window

### `static/js/mapping.js` — Architecture

Handles the entire **Mapping page** (advanced):
- Room canvas with configurable dimensions
- Draw obstacles by click-drag (MS Paint style)
- Obstacle list CRUD panel
- Sonar heat-map overlay rendering
- Bot position display and manual set
- Autonomous exploration start/stop controls
- A→B navigation: click to set start, click to set goal, navigate
- Map file management panel (New/Save/Load/Close/Delete)
- Sends all `ADV_*` WebSocket commands

---

## 🌐 Network — Deep Dive

### Local Network Setup

```
Wi-Fi Router / Mobile Hotspot (2.4 GHz)
  ├── Laptop (Python server on port 5000) — IP: e.g. 192.168.1.100
  ├── ESP32 #1                            — IP: e.g. 192.168.1.159
  ├── ESP32 #2                            — IP: e.g. 192.168.1.162
  └── Phone/iPad (browser client)         — Any IP on same subnet
```

### Connection Sequence

```
1. ESP32 boots → connects to Wi-Fi → starts TCP server on port 8080
2. Python server boots → reads saved IP from robot_config.json
3. Browser opens → WebSocket connects to ws://laptop:5000/ws
4. User enters ESP IPs in Network page → clicks Connect
5. Python opens TCP socket to ESP1 (ip1:8080) in background thread
6. Python opens TCP socket to ESP2 (ip2:8080) in background thread
7. ESPs send greeting: "[ESP1] B1 Left side ready" / "[ESP2] B2 Right side ready"
8. Python broadcasts conn status to browser → indicators turn green
```

### Cloudflare Tunnel (Remote Access)

```bash
cloudflared tunnel --url http://localhost:5000
```
- Generates a public HTTPS URL (e.g. `https://xxxx.trycloudflare.com`)
- Any device on the internet can control the robot
- Latency increases depending on internet speed
- No code changes required — works out of the box

---

## 🕹️ Control System — Deep Dive

### Motor Commands

| Char | Label | ESP1 Left (B1) | ESP2 Right (B2) | Robot Motion |
|------|-------|---------------|-----------------|-------------|
| `W` | Forward | RPWM=255, LPWM=0 | RPWM=0, LPWM=255 | Straight forward |
| `S` | Backward | RPWM=0, LPWM=255 | RPWM=255, LPWM=0 | Straight backward |
| `A` | Turn Left | RPWM=0, LPWM=255 | RPWM=0, LPWM=255 | Tank pivot left |
| `D` | Turn Right | RPWM=255, LPWM=0 | RPWM=255, LPWM=0 | Tank pivot right |
| `X` | Stop | 0, 0 | 0, 0 | All motors off |

> ESP2 swaps RPWM/LPWM vs ESP1 because right-side motors are physically mounted mirrored.

### Input Methods

| Method | How | Device |
|--------|-----|--------|
| Keyboard WASD | Global keydown/up listener | PC |
| Arrow Keys | Same listener | PC |
| Numpad 8/4/6/2/5 | NumLock-independent via `e.code` | PC |
| D-Pad buttons | Mouse/touch events | PC, Phone, Tablet |
| Omni Joystick | Pointer events + dead zone | PC, Phone, Tablet |
| Vertical Joystick | Pointer drag | PC, Phone, Tablet |
| Horizontal Joystick | Pointer drag | PC, Phone, Tablet |
| AutoMapper | Python AutoMapper class | Automatic |
| A* Navigator | AdvancedMapManager | Automatic |

### Emergency Stop System

```
E-Stop Armed (user toggles AUTO button)
       ↓
Sonar reading ≤ 10cm on any sensor
       ↓
Python: raw_send("X") → both ESPs stop immediately
Python: broadcast {type: "estop", reason: "FRONT 8.2 cm"}
       ↓
Browser: E-Stop modal appears
User clicks "Override" → 3-second window to reverse
After 3s: E-Stop re-arms automatically
```

---

## 🗺️ Mapping System — Deep Dive

### Mapper Page (Simple)

- Uses `AutoMapper` class in `web_server.py`
- Bot position tracked by dead-reckoning
- Two modes:
  - **Pulse:** Stop-scan-move-stop cycle. More precise turns.
  - **Smooth:** Continuous movement. Faster exploration.
- Map displayed as HTML Canvas:
  - 🟥 Red squares = detected walls (sonar endpoints)
  - 🟩 Green squares = confirmed free space (sonar ray path)
  - 🔵 Cyan dots = robot travel path
  - 🟡 Yellow arrow = current robot position and heading
- Configurable: pulse duration, turn duration, front/diagonal thresholds
- Map data NOT saved to disk — resets on clear or page reload

### Mapping Page (Advanced)

- Uses `AdvancedMapManager` in `advanced_mapping.py`
- Full map lifecycle: create, name, save, load, edit, delete
- Maps stored as JSON in `maps/` directory
- Features:
  - **Draw obstacles** manually on canvas (click-drag rectangles)
  - **Sonar heat-map** — live overlay of where sonars detected objects
  - **Manual bot placement** — click to set start position
  - **Autonomous exploration** — same reactive logic as AutoMapper
  - **A→B navigation** — click start, click goal, robot finds path and drives
  - **A* pathfinding** — 20cm grid resolution, safety padding around obstacles, dynamic replanning on obstacle detection

---

## 📋 File Inventory

| File | Size | Purpose |
|------|------|---------|
| `web_server.py` | 25 KB | Main FastAPI server |
| `advanced_mapping.py` | 26 KB | Advanced mapping module |
| `static/index.html` | 42 KB | Full web dashboard (single page) |
| `static/js/main.js` | 28 KB | Frontend JS — controls, Mapper, WS |
| `static/js/mapping.js` | 27 KB | Frontend JS — Advanced Mapping page |
| `static/js/qrcode.min.js` | 20 KB | Local QR code generator |
| `static/css/style.css` | 42 KB | Full theme system |
| `1EC/1EC.ino` | 5 KB | ESP32 #1 firmware |
| `2EC/2EC.ino` | 2.5 KB | ESP32 #2 firmware |
| `DE.py` | 66 KB | Legacy desktop app (not primary) |
| `robot_config.json` | <1 KB | Saved ESP IP addresses |
| `connections.md` | 1.6 KB | Hardware wiring reference |
| `setup.bat` | <1 KB | Install Python dependencies |
| `start_server.bat` | <1 KB | Start server via uvicorn |

---

## 🔄 State Management

### Python-Side State (Runtime)

| Variable | Location | Holds |
|----------|----------|-------|
| `robot.ip1/ip2` | Robot class | Current ESP IP addresses |
| `robot._conn[0/1]` | Robot class | TCP connection state per ESP |
| `robot._sock[0/1]` | Robot class | TCP socket objects |
| `robot.sonar_front` | Robot class | Latest front sonar reading |
| `robot.estop_*` | Robot class | E-Stop state flags |
| `robot.mapper.*` | AutoMapper | Mapper page state |
| `adv_mapper.*` | AdvancedMapManager | Advanced mapping state |
| `_clients` | Global | List of active WebSocket sessions |

### Browser-Side State (Runtime)

| Variable | Location | Holds |
|----------|----------|-------|
| `espState` | main.js | `{esp1: bool, esp2: bool}` |
| `mapState` | main.js | Walls/free/path/bot for Mapper canvas |
| `autoEStopEnabled` | main.js | Whether auto e-stop is armed |
| `wsLatencyMs` | main.js | WebSocket round-trip latency |
| `theme` | main.js + localStorage | Current UI theme (dark/light) |
| `advState` | mapping.js | Full advanced map state from server |

### Persistent State (On Disk)

| File | Contents | When Updated |
|------|----------|-------------|
| `robot_config.json` | ESP IP addresses | On SET_IPS command |
| `maps/<name>.json` | Room size, obstacles, heat-map | On ADV_MAP_SAVE command |
| `localStorage['duon-theme']` | UI theme preference | On theme toggle |

---

## ⚠️ Critical Operational Notes

### Always Remember

1. **2.4 GHz ONLY** — ESP32 cannot connect to 5 GHz Wi-Fi under any circumstances
2. **Data USB cables only** — Charge-only cables will not transfer firmware; test cables before use
3. **Serial port conflict** — Arduino Serial Monitor and Python cannot both access ESP serial simultaneously; close one before using the other
4. **Separate power** — Motor battery (LiPo) and ESP power (USB bank) are independent; can safely power one without the other
5. **BTS7960 protection** — If driver cuts out due to fault, wait 2–3 minutes then reset the respective ESP32

### Wi-Fi Troubleshooting Checklist

- [ ] Router/hotspot is broadcasting on 2.4 GHz (not 5 GHz only)
- [ ] SSID and password in `.ino` files match exactly (case-sensitive)
- [ ] ESP32 is within range of Wi-Fi signal
- [ ] Laptop is on the same network subnet as the ESPs
- [ ] ESP IP in web dashboard matches actual IP (check via Serial Monitor or router admin)

### Application Troubleshooting Checklist

- [ ] `setup.bat` has been run at least once to install dependencies
- [ ] `start_server.bat` is running (or `web_server.py` via IDLE)
- [ ] Browser points to correct URL (`http://localhost:5000` or network IP)
- [ ] Port 5000 is not blocked by Windows Firewall
- [ ] No other instance of DUON is already running on port 5000

---

## 🔮 Architecture for Future Developers

### Adding New Sensor Types

1. Read sensor data in ESP firmware (or directly in Python if USB-connected)
2. Define a new message format string (like `[SONAR]` → e.g., `[IMU]`)
3. Add parsing in `Robot._rx()` in `web_server.py`
4. Add a new broadcast type (e.g., `{"type": "imu", ...}`)
5. Handle in `handleMsg()` in `main.js`

### Adding a New Dashboard Page

1. Add a new `<div class="page" id="page-newname">` in `index.html`
2. Add nav item with `data-page="newname"` attribute
3. Add handler in `navigate()` function in `main.js` if page needs init
4. Add new WebSocket command handling in `ws_endpoint()` in `web_server.py` if needed

### Upgrading to Encoder-Based Odometry

1. Implement encoder ISR in ESP firmware (count pulses on GPIO 34/36 for ESP1, 32/39 for ESP2)
2. Add resistor signal conditioning on encoder signal lines (similar to sonar fix)
3. Send encoder data as `[ENC]M:1,C:1234,D:FWD` (format already supported in Python parser)
4. Replace dead-reckoning in `advanced_mapping.py` with encoder tick-based position calculation

---

## 📚 Learning Resources

| Topic | Resource |
|-------|---------|
| ESP32 Arduino | https://docs.espressif.com/projects/arduino-esp32 |
| FastAPI | https://fastapi.tiangolo.com |
| WebSocket API (browser) | https://developer.mozilla.org/en-US/docs/Web/API/WebSocket |
| HC-SR04 HC-SR04 | HC-SR04 datasheet (any electronics reference) |
| BTS7960 | BTS7960 datasheet from Infineon |
| A* algorithm | https://www.redblobgames.com/pathfinding/a-star/introduction.html |
| Cloudflare Tunnel | https://developers.cloudflare.com/cloudflare-one/connections/connect-networks |

---

*Document 0 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
