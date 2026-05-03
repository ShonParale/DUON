# 12 — Detailed Project Overview

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Institution:** University Engineering Project — Semester 6

---

## 1. Project Background & Motivation

Robotics education often stays at the theory level. This project was built to bridge theory and practice — to design, wire, code, and deploy a working autonomous robot from scratch using accessible, affordable hardware.

The goal was not just to make a robot move, but to build a **complete system**: embedded firmware, a networked server, a web dashboard, and intelligent autonomous behaviour — all integrated together and accessible wirelessly from any device.

DUON addresses real engineering challenges:
- How do you make a robot responsive in real time over a network?
- How do you handle sensor noise from cheap ultrasonic sensors?
- How do you build autonomous navigation without expensive sensors like LiDAR?
- How do you make a complex system usable by someone who is not a developer?

---

## 2. System Architecture

DUON is built as a **three-tier architecture**:

```
┌──────────────────────────────────────────────────────────────────┐
│  TIER 3 — PRESENTATION                                           │
│  Web Browser (any device on Wi-Fi)                               │
│  Single-page HTML dashboard — real-time updates via WebSocket    │
└────────────────────────┬─────────────────────────────────────────┘
                         │ WebSocket (JSON) + HTTP
┌────────────────────────▼─────────────────────────────────────────┐
│  TIER 2 — APPLICATION LOGIC                                      │
│  Python FastAPI Server (Laptop / PC)                             │
│  web_server.py  +  advanced_mapping.py                           │
│  Handles: routing, WebSocket, TCP bridging, mapping, A*          │
└────────────┬──────────────────────────────┬──────────────────────┘
             │ TCP Socket (port 8080)        │ TCP Socket (port 8080)
┌────────────▼──────────────┐  ┌────────────▼──────────────────────┐
│  TIER 1 — HARDWARE         │  │  TIER 1 — HARDWARE                │
│  ESP32 #1 (Left side)      │  │  ESP32 #2 (Right side)            │
│  BTS7960 B1 → M1 + M3     │  │  BTS7960 B2 → M2 + M4            │
│  HC-SR04 ×3 (all sonars)  │  │  (motors only — no sensors)        │
└────────────────────────────┘  └───────────────────────────────────┘
```

---

## 3. Hardware — Detailed Description

### 3.1 Robot Chassis & Motors

The robot uses a 4WD chassis with one DC gearmotor with encoder at each wheel position:

| Position | Motor Label | Controlled By |
|----------|-------------|--------------|
| Front-Left | M1 | ESP32 #1 via BTS7960 B1 |
| Rear-Left | M3 | ESP32 #1 via BTS7960 B1 |
| Front-Right | M2 | ESP32 #2 via BTS7960 B2 |
| Rear-Right | M4 | ESP32 #2 via BTS7960 B2 |

M1 and M3 are wired in parallel to B1's output terminals. M2 and M4 are wired in parallel to B2's output terminals. Both motors on each side always move together, effectively acting as one per side.

**Steering method:** Tank steering — to turn left, the left motors reverse while right motors go forward; to turn right, the opposite.

### 3.2 BTS7960 Motor Drivers

Two BTS7960 43A H-Bridge drivers — one per side. This split was intentional: early testing showed that running both drivers from one ESP32 caused reliability issues. Separating them (one ESP per driver) solved the problem and also doubled the processing capacity.

The BTS7960 has built-in overcurrent and overtemperature protection. If triggered, the driver shuts off and requires the respective ESP to be reset to recover.

Motor power comes from a LiPo battery. The driver logic pins (VCC, R_EN, L_EN) are powered from a 5V buck converter derived from the same battery.

### 3.3 ESP32 Microcontrollers

Both are USB Type-C ESP32 DevKit boards. Key specifications:
- Dual-core Xtensa LX6 @ 240 MHz
- 802.11 b/g/n Wi-Fi — **2.4 GHz only**
- Hardware LEDC PWM controller — drives motor pins at 5 kHz, 8-bit resolution (0–255)
- GPIO voltage: 3.3V (sonar ECHO and encoder signals are 5V — voltage dividers needed, not yet installed)

**ESP32 #1** (Left side + All sensors):
- GPIO 25, 27: BTS7960 B1 RPWM/LPWM
- GPIO 32/33, 14/16, 13/17: TRIG/ECHO for sonars S1 (Left 45°), S2 (Front 0°), S3 (Right 45°)
- GPIO 34, 36: M1/M3 encoder A channel (wired, not yet active in firmware)

**ESP32 #2** (Right side motors only):
- GPIO 18, 19: BTS7960 B2 RPWM/LPWM
- GPIO 32, 39: M2/M4 encoder A channel (wired, not yet active in firmware)

### 3.4 Ultrasonic Sensors (HC-SR04)

Three sensors mounted on the front of the robot:
- **S1 (Left):** Angled 45° to the front-left — detects obstacles approaching from that diagonal
- **S2 (Front):** Straight ahead — primary obstacle detection for forward motion
- **S3 (Right):** Angled 45° to the front-right — detects obstacles on that diagonal

Range: 2 cm – 400 cm. Readings are updated every 100ms (10 Hz). All three are read by ESP32 #1 using a non-blocking state machine — this means sonar reading never blocks motor command handling.

Raw sonar readings can be noisy due to the 5V ECHO signal directly on 3.3V GPIO (voltage divider not yet installed). A software filter (`SonarProcessor`) applies rolling median, spike rejection, and jitter gating to clean the data.

### 3.5 Power System

```
LiPo Battery (motor power)
  ├── B+ → BTS7960 B1 + B2 (motor power rails)
  └── → Buck Converter → 5V
        ├── BTS7960 B1/B2 VCC, R_EN, L_EN (logic enable)
        └── Common GND rail (ESPs share this ground)

USB Power Banks (ESP power — independent)
  ├── Power Bank #1 → ESP32 #1 (USB-C)
  └── Power Bank #2 → ESP32 #2 (USB-C)

Battery Pack (5V) → Encoder VCC all 4 motors
```

Motor power and ESP power are completely separate circuits. You can power the ESPs without the LiPo (for code upload / sonar testing) and vice versa.

---

## 4. Software — Detailed Description

### 4.1 ESP Firmware

Both ESP firmwares follow the same pattern:
1. Connect to hardcoded Wi-Fi credentials
2. Start TCP server on port 8080
3. Wait for Python to connect
4. Loop: receive motor commands → execute PWM → respond

ESP32 #1 additionally cycles through all 3 sonars using a non-blocking state machine and sends formatted sonar data (`[SONAR]L:x,F:x,R:x`) to Python every 100ms.

The key firmware design decision for ESP32 #2 is **polarity inversion in software**: because the right-side motors are physically mounted facing the opposite direction, RPWM and LPWM signals are swapped in code to achieve correct straight-line motion without rewiring.

### 4.2 Python Server (`web_server.py`)

The main application server. Built on **FastAPI** with **Uvicorn** ASGI server. Runs on port 5000.

**Core components:**

| Component | Description |
|-----------|-------------|
| `SonarProcessor` | Noise filter: 7-reading rolling median + spike rejection + 3cm jitter gate |
| `Robot` class | Manages TCP sockets to both ESPs; motor command dispatch; sonar/encoder parsing; e-stop logic |
| `AutoMapper` class | Autonomous mapping engine: pulse/smooth modes, dead-reckoning, wall/free tracking |
| `AdvancedMapManager` | Advanced mapping: obstacle CRUD, heat-map, A* pathfinding, autonomous exploration, A→B navigation |
| WebSocket endpoint `/ws` | Receives all browser commands; routes to Robot/Mapper/AdvancedMapManager |
| `broadcast()` | Thread-safe JSON broadcast to all connected browsers |
| Periodic status task | Broadcasts connection status and latency every 2 seconds |

**Threading model:**
- Main thread: FastAPI async event loop (handles all WebSocket and HTTP)
- Per-ESP: 1 background receive thread each (blocking TCP reads)
- AutoMapper/Exploration/Navigation: daemon threads when running

### 4.3 Advanced Mapping Module (`advanced_mapping.py`)

Handles everything for the Mapping page:

**Dead-reckoning:** Tracks robot position by integrating time × estimated speed from drive commands. No encoder data used yet (drifts over time). Position is clamped to room boundaries.

**Sonar heat-map:** When a map is active, every sonar reading is projected from the robot's estimated position using trigonometry. The endpoint of each sonar ray (where it hit an obstacle) is stored as a heat-map point. Kept as a rolling list of max 800 points.

**A* Pathfinding:**
- Converts obstacle rectangles to a boolean occupancy grid (20cm cell size)
- Adds 1-cell safety padding around each obstacle
- Runs A* with Manhattan heuristic and 8-directional movement
- If goal cell is blocked, finds nearest free cell within 2-cell radius
- Converts grid path back to world coordinates (cm)

**A→B Navigation:**
- Plans path from current position to target
- Executes waypoints: compute heading, turn proportionally, move proportionally
- Checks front sonar before each move; replans if obstacle detected
- Broadcasts planned route to browser so it can be visualised on canvas

### 4.4 Web Frontend

A single HTML file (`static/index.html`) containing all page layouts. JavaScript and CSS are in separate files served from the `static/` folder.

**Pages:**

| Page ID | Name | Content |
|---------|------|---------|
| `home` | Overview | Project intro, team info, quick-start guide |
| `network` | Network | ESP IP fields, connect/disconnect buttons, QR code, URL display, ping metrics |
| `drive` | Drive | 3 sonar gauges, D-Pad, Omni joystick, dual-axis joystick, terminal log, e-stop toggle |
| `mapper` | Mapper | HTML5 Canvas map (pan/zoom), mapping config sliders, start/stop controls, auto-log |
| `mapping` | Mapping | Advanced canvas with obstacle drawing, map file management, exploration, A* navigation |
| `settings` | Settings | Theme toggle, shutdown button, keyboard guide |

**Status bar (always visible at top):**
- WebSocket live/disconnected indicator
- ESP1 and ESP2 connection dots
- Front sonar reading (colour-coded: green/orange/red)
- Map running indicator
- Manual STOP button
- Auto E-Stop toggle button
- WebSocket ping (ms)

**Control inputs:**

| Input Method | Trigger | Commands |
|-------------|---------|---------|
| WASD keys | keydown/keyup | W/A/S/D; keyup sends X |
| Arrow keys | keydown/keyup | W/A/S/D; keyup sends X |
| Numpad 8/4/6/2/5 | keydown/keyup | W/A/S/D/X; NumLock-independent |
| D-Pad buttons | mousedown/mouseup/touch | W/A/S/D/X |
| Omni joystick | pointer drag with dead zone | W/A/S/D/X based on direction |
| Vertical joystick | pointer drag | W/S/X |
| Horizontal joystick | pointer drag | A/D/X |

---

## 5. Communication Protocols

### Browser ↔ Python (WebSocket)

- Protocol: WebSocket (ws://)
- Format: JSON text frames
- Direction: Full duplex
- Auto-reconnect: 2 seconds after disconnect

Browser sends commands as `{"cmd": "COMMAND", ...fields}`.
Python broadcasts updates as `{"type": "TYPE", ...data}`.

### Python ↔ ESP32 (TCP Socket)

- Protocol: Raw TCP
- Port: 8080 (ESP is server, Python is client)
- Format: Single ASCII characters (commands) and newline-terminated strings (data)
- Commands: `W`, `S`, `A`, `D`, `X` (single bytes)
- Sonar data: `[SONAR]L:45.2,F:120.0,R:38.7\n` (every 100ms from ESP1)

---

## 6. Autonomous Capabilities

### 6.1 Auto Emergency Stop

- User arms the e-stop toggle in the top status bar or Drive page
- If any sonar reading drops ≤ 10cm, the robot stops immediately
- A modal appears in the browser with the trigger reason
- User can click "Override" for a 3-second window to reverse away from the obstacle
- E-stop re-arms automatically after override expires

### 6.2 Simple Autonomous Mapping (Mapper Page)

The `AutoMapper` class implements reactive navigation:
- **Pulse mode:** Robot moves in short timed bursts, stops, scans, decides direction
- **Smooth mode:** Robot moves continuously, checking sensors on the fly

Decision tree: if front is clear → move forward; if front is blocked → turn to clearest side; if all sides blocked → U-turn.

The robot's path, detected walls, and confirmed free space are visualised on the Mapper canvas in real time.

### 6.3 Advanced Mapping + A* Navigation (Mapping Page)

The `AdvancedMapManager` provides:
- **Manual map drawing:** Click-drag to draw obstacle rectangles on canvas
- **Sonar heat-map overlay:** Live sensor projection onto the map
- **Autonomous exploration:** Same reactive logic as Mapper but tied to the Mapping page's map state
- **A* pathfinding:** Computes optimal route avoiding all drawn obstacles
- **A→B navigation:** Executes the planned path waypoint-by-waypoint with dynamic obstacle avoidance and replanning

Maps are saved as JSON files and can be loaded, edited, and deleted.

---

## 7. Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Portable** | Copy folder anywhere — runs on any Windows machine after `setup.bat` |
| **No app install** | Browser-based dashboard — works on phones, tablets, PCs |
| **Resilient** | Auto-reconnect WebSocket; e-stop on sensor threshold; BTS7960 hardware protection |
| **Extensible** | Clean WebSocket command API; easy to add new sensors, pages, or robots |
| **Accessible** | Multiple input methods for different users and devices |
| **Observable** | Live terminal log, sonar gauges, ping metrics, connection status — always visible |

---

## 8. Limitations (Current Version)

| Limitation | Impact | Planned Fix |
|------------|--------|------------|
| Dead-reckoning only (no encoders active) | Map accuracy degrades over time | Encoder implementation (Next Step) |
| Sonar voltage dividers missing | Increased sensor noise | Resistor fix (Next Step) |
| Jumper wire connections | Occasional loose connections | Solder / PCB (Next Step) |
| Windows only (tested) | Not portable to Mac/Linux/Pi | Cross-platform scripts (Future Scope) |
| No camera | No visual feedback | Camera integration (Future Scope) |
| Single laptop dependency | Laptop must run server | Raspberry Pi onboard (Future Scope) |

---

*Document 12 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
