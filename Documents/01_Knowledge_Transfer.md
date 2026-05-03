# 01 — Knowledge Transfer Document

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Purpose:** Complete knowledge transfer for anyone taking over, maintaining, or studying this project.

---

## 👥 Team

| Name | Role | GitHub | LinkedIn | Portfolio |
|------|------|--------|----------|-----------|
| Shon Parale | Developer | [ShonParale](https://github.com/ShonParale) | [LinkedIn](https://www.linkedin.com/in/shonparale/) | [Portfolio](https://sites.google.com/view/shonparale/home) |
| Vedant Patel | Developer | [vedu007lol](https://github.com/vedu007lol) | [LinkedIn](https://www.linkedin.com/in/-vedantpatel/) | [Portfolio](https://drive.google.com/file/d/1U9l_l_AUNgH8ZVXr-0SING72Od8F5QmS/view?usp=sharing) |

---

## 🧠 What is DUON?

DUON (Dynamic Ultrasonic Operations & Navigations) is a **4-wheel drive robot** that can be:
- **Manually driven** via a web dashboard (keyboard, on-screen D-Pad, or joystick)
- **Autonomously mapped** — the robot explores and builds a room map using 3 ultrasonic (sonar) sensors
- **Navigated A→B** — given a start and goal position on the map, the robot calculates the shortest path (A*) and travels autonomously

The system runs on **two ESP32 microcontrollers** (firmware in C/Arduino) and a **Python-based web server** hosted on a laptop. Any device on the same Wi-Fi network can open the web dashboard in a browser.

---

## 🏗️ System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Web Browser                          │
│          (Any device on same WiFi — Phone, PC, iPad)        │
│         index.html + CSS + JavaScript (WebSocket)           │
└──────────────────────────────┬──────────────────────────────┘
                               │  WebSocket (ws://laptop:5000/ws)
┌──────────────────────────────▼──────────────────────────────┐
│                    Laptop / PC                               │
│        Python FastAPI  web_server.py  (Port 5000)           │
│        advanced_mapping.py — A*, map mgmt, exploration      │
└──────┬────────────────────────────────────────────┬─────────┘
       │  TCP Socket (Port 8080)                    │  TCP Socket (Port 8080)
┌──────▼──────────┐                      ┌──────────▼──────────┐
│   ESP32 #1      │                      │   ESP32 #2           │
│  (Left Side)    │                      │  (Right Side)        │
│  BTS7960 B1     │                      │  BTS7960 B2          │
│  M1 + M3        │                      │  M2 + M4             │
│  3× HC-SR04     │                      │  (No sensors here)   │
│  Sonar sensors  │                      │                      │
└──────┬──────────┘                      └──────────┬──────────┘
       │                                            │
    M1 (FL) + M3 (RL)                          M2 (FR) + M4 (RR)
    (Left motors via B1)                      (Right motors via B2)
```

**Data flow summary:**
1. User sends command via browser → WebSocket to Python server
2. Python forwards command character (`W/A/S/D/X`) to both ESPs via TCP
3. ESP1 controls left motors AND reads all 3 sonar sensors
4. ESP2 controls right motors only
5. ESP1 sends sonar readings back to Python every 100ms as `[SONAR]L:xx,F:xx,R:xx`
6. Python broadcasts sonar data to all connected browsers via WebSocket

---

## ⚙️ Hardware Components

| Component | Quantity | Purpose |
|-----------|----------|---------|
| ESP32 (Type-C) | 2 | Microcontrollers — motor & sensor control |
| BTS7960 Motor Driver | 2 | High-current DC motor driver (one per side) |
| HC-SR04 Ultrasonic Sensor | 3 | Distance measurement (Left, Front, Right) |
| DC Motor with Encoder | 4 | Drive motors (encoders not yet used in code) |
| LiPo Battery | 1 | Power for motors via BTS7960 drivers |
| Buck Converter (5V) | 1 | Steps down battery voltage to 5V for logic |
| Power Bank / USB Charger | 2 | Power for ESP32 boards independently |

---

## 💻 Software Stack

| Layer | Technology | Details |
|-------|------------|---------|
| ESP Firmware | C / Arduino IDE | `1EC.ino` (ESP1), `2EC.ino` (ESP2) |
| Backend Server | Python 3 + FastAPI | `web_server.py` — runs on port 5000 |
| Advanced Mapping | Python | `advanced_mapping.py` — A*, exploration, map management |
| Web Frontend | HTML + CSS + JavaScript | `static/index.html` — single-page dashboard |
| Communication | WebSocket + TCP Sockets | Browser↔Python (WS), Python↔ESP (TCP) |

---

## 📶 Network Requirements

- **Wi-Fi standard:** 2.4 GHz ONLY — ESP32 does NOT support 5 GHz
- **All devices must be on the same Wi-Fi network** (laptop, phone, ESPs)
- Tested on mobile hotspot (2.4 GHz band) and home router
- **LAN only** by default; can be exposed publicly using Cloudflare Tunnel (`cloudflared`)

---

## 🚀 How to Start the Project (Quick Summary)

1. Flash `1EC.ino` to ESP32 #1, `2EC.ino` to ESP32 #2 using Arduino IDE
2. Update Wi-Fi credentials (SSID and password) in both `.ino` files
3. On the laptop, run `setup.bat` once to install Python dependencies
4. Run `start_server.bat` to start the DUON web server
5. Open browser → `http://localhost:5000` (or the network IP shown in terminal)
6. In the web app → **Network page** → enter ESP IP addresses → Connect

> **Tip:** If ESP IP is unknown, connect ESP via USB cable, open Arduino Serial Monitor at 115200 baud, reset the ESP — the IP will be printed.

---

## 🌐 Web Dashboard Pages

| Page | Description |
|------|-------------|
| **Network** | Enter ESP IPs, connect/disconnect, see live connection status, QR code for sharing |
| **Drive** | Manual control with D-Pad, WASD/Arrow keys, joystick; live sonar readings shown |
| **Mapper** | Simple autonomous mapping — bot moves, sonar builds a grid map in real-time |
| **Mapping** | Advanced mapping — draw obstacles manually (MS-Paint style), autonomous explore, A* pathfinding, save/load/delete maps |
| **Settings** | Theme toggle (dark/light), shutdown server, user guide |

### Top Status Bar (always visible)
- Live ESP1 and ESP2 connection indicator
- Manual STOP button (stops motors immediately)
- Auto Emergency Stop (E-Stop) toggle — stops bot if sonar detects < 10 cm obstacle

---

## 🔑 Key Design Decisions

| Decision | Reason |
|----------|--------|
| 1 ESP per BTS7960 driver | Testing showed 2 BTS drivers do not work reliably on 1 ESP; splitting also provides more processing headroom |
| All 3 sonars on ESP1 | Simpler wiring; sonar data needed for front obstacle detection handled by ESP1 which controls left motors |
| WebSocket for browser comms | Real-time, bidirectional; avoids polling |
| TCP sockets for ESP comms | Simple, reliable on local LAN; ESP32 natively supports TCP server |
| Single-char motor commands | Minimal packet size, fast transmission: W=forward, S=backward, A=left, D=right, X=stop |
| FastAPI + Uvicorn | Modern async Python framework, efficient WebSocket support |

---

## ⚠️ Known Issues & Limitations (Current State)

| Issue | Details |
|-------|---------|
| **Sonar fluctuation** | HC-SR04 should ideally be connected via resistor divider for signal conditioning — not done yet |
| **Encoder not used** | All 4 motors have encoders wired but encoder reading code is not implemented — next step |
| **Wiring reliability** | Jumper cables can come loose; solder connections or use a PCB for permanent setup |
| **Mapping accuracy** | Dead-reckoning (time-based position estimate) drifts; no encoder feedback to correct it |
| **Windows only** | Application tested on Windows; macOS/Linux/Raspberry Pi compatibility is a future goal |
| **Serial port conflict** | Arduino Serial Monitor and Python cannot both access the ESP's serial port simultaneously |

---

## 🔮 Next Steps (Short-term)

1. Implement encoder reading code on both ESPs (requires resistor dividers on signal lines)
2. Add resistor signal conditioning for sonar sensors
3. Solder permanent connections or design a custom PCB
4. Improve mapping algorithm accuracy using encoder feedback
5. Test on macOS, Linux, and Raspberry Pi OS

## 🚀 Future Scope (Long-term)

1. 2D/3D LiDAR integration for accurate mapping
2. Camera-based vision system (USB, ESP-CAM, Raspberry Pi camera, or phone)
3. Upgrade processing unit to Raspberry Pi or edge AI processor
4. Predictive maintenance and sensor diagnostics dashboard page
5. Remote access via Cloudflare Tunnel (already supported — just run `cloudflared`)

---

## 📁 Project Folder Structure

```
DUON/
├── 1EC/
│   └── 1EC.ino              ← ESP32 #1 firmware (left motors + all sonars)
├── 2EC/
│   └── 2EC.ino              ← ESP32 #2 firmware (right motors only)
├── Documents/
│   ├── Things_To_Know_For_Documentation.txt
│   ├── 01_Knowledge_Transfer.md        ← THIS FILE
│   ├── 02_Hardware_Connections_Wiring_Guide.md
│   ├── 03_ESP1_Code_Explanation.md
│   ├── 04_ESP2_Code_Explanation.md
│   └── 05_Python_Code_Explanation.md
├── maps/                    ← Saved map JSON files
├── static/
│   ├── index.html           ← Full web dashboard (single-page app)
│   ├── css/                 ← Stylesheets
│   └── js/                  ← JavaScript modules
├── advanced_mapping.py      ← A*, exploration, map CRUD
├── web_server.py            ← FastAPI server (main Python entry point)
├── DE.py                    ← Legacy desktop app (kept for reference)
├── robot_config.json        ← Saved ESP IP addresses
├── connections.md           ← Hardware wiring reference
├── setup.bat                ← Install Python dependencies
└── start_server.bat         ← Start the DUON server
```

---

## 🛠️ Tools Required

| Tool | Purpose | Required? |
|------|---------|-----------|
| Python 3.x + pip | Run web server | ✅ Mandatory |
| Arduino IDE | Flash firmware to ESP32 | ✅ For firmware changes |
| Web browser | Access dashboard | ✅ Mandatory |
| Arduino ESP32 board package | Board support in Arduino IDE | ✅ For Arduino IDE |
| Windows OS | Current primary platform | ✅ Currently |

### Installing Arduino ESP32 Board Package
In Arduino IDE → File → Preferences → Additional Boards Manager URLs, add:
```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```
Then go to Tools → Board → Boards Manager → search "esp32" → install.
Select board: **ALKS ESP32** (or generic ESP32 Dev Module).

---

## 📌 Important Notes for Maintainers

- Always use **data-capable USB cables** — charging-only cables will NOT transfer firmware to ESP32
- ESP32 boards are **USB Type-C** — use C-to-C or A-to-C cables accordingly
- If the web app is unresponsive, right-click `web_server.py` → **Edit with IDLE** → Run in IDLE to see full error output
- Both ESPs can run on a power bank attached to the underside of the robot
- Motor power (LiPo) can be disconnected during firmware upload/testing to save power
- **Never connect to 5 GHz Wi-Fi** — ESP32 will fail to connect
- BTS7960 has built-in protection; if it cuts out, manually reset the respective ESP32

---

*Document 1 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
