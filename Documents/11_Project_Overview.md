# 11 — Project Overview

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Institution:** University Engineering Project — Semester 6

---

## What is DUON?

DUON is a **4-wheel drive autonomous robot** built as a university robotics project. It combines embedded systems, networking, and web technology to create a robot that can be controlled and monitored from any device — phone, tablet, or PC — through a web browser, with no app installation needed.

The name stands for **Dynamic Ultrasonic Operations & Navigations**, reflecting the robot's use of ultrasonic sensors for spatial awareness and its ability to navigate autonomously.

---

## The Robot

| Property | Details |
|----------|---------|
| Drive type | 4-Wheel Drive (4WD) — tank steering |
| Motors | 4× DC motors with encoders (2 per side) |
| Motor drivers | 2× BTS7960 H-Bridge (one per side) |
| Sensors | 3× HC-SR04 ultrasonic sensors |
| Controllers | 2× ESP32 microcontrollers |
| Control range | Unlimited on same Wi-Fi network |
| Power | LiPo battery (motors) + USB power banks (ESPs) |

---

## The System

The DUON system has three layers working together:

### Layer 1 — Robot Hardware (ESP32 Firmware)
Two ESP32 microcontrollers run Arduino C++ firmware. Each ESP connects to the same Wi-Fi network and waits for the Python server to connect via TCP. They receive single-character motor commands (`W/A/S/D/X`) and execute them on their respective motor drivers. ESP32 #1 additionally reads all 3 ultrasonic sensors and streams distance data back to Python every 100ms.

### Layer 2 — Python Server (Laptop / PC)
A FastAPI web server runs on a laptop on the same Wi-Fi network. It acts as the bridge between the browser and the robots. It receives commands from browsers via WebSocket, forwards them to the ESPs via TCP, receives sensor data from the ESPs, and broadcasts all updates to all connected browsers in real time. It also handles the mapping and pathfinding logic.

### Layer 3 — Web Dashboard (Browser)
A single-page web application is served by the Python server. Any device on the same Wi-Fi can open it in a browser. It provides live telemetry, manual controls, autonomous mapping, and A* navigation — all updating in real time without page reloads.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Multi-device access** | Open dashboard on phone, tablet, or PC simultaneously |
| **Manual drive** | Keyboard (WASD, Arrows, Numpad), D-Pad buttons, 3 joystick types |
| **Live sonar display** | 3 animated gauges showing distance in real time |
| **Auto emergency stop** | Automatically halts robot if any sonar detects obstacle < 10cm |
| **Simple mapping** | Robot maps a room autonomously using sonar |
| **Advanced mapping** | Draw maps manually, save/load maps, explore autonomously, A* navigate |
| **QR code sharing** | Scan QR code to instantly open dashboard on phone |
| **Dark / Light theme** | Full UI theme support with persistent preference |
| **Cloudflare Tunnel** | Optional: expose dashboard publicly for remote control |

---

## Technology at a Glance

| Layer | Technology |
|-------|-----------|
| ESP Firmware | C++ / Arduino IDE |
| Python Server | Python 3 · FastAPI · WebSocket · TCP Sockets |
| Web Frontend | HTML · CSS · JavaScript (vanilla) |
| Pathfinding | A* algorithm (implemented in Python) |
| Communication | WebSocket (browser↔server) · TCP Socket (server↔ESP) |
| Deployment | Local LAN · Optional Cloudflare Tunnel for internet access |

---

## Team

| Name | GitHub | LinkedIn |
|------|--------|----------|
| Shon Parale | [ShonParale](https://github.com/ShonParale) | [linkedin.com/in/shonparale](https://www.linkedin.com/in/shonparale/) |
| Vedant Patel | [vedu007lol](https://github.com/vedu007lol) | [linkedin.com/in/-vedantpatel](https://www.linkedin.com/in/-vedantpatel/) |

---

## Project Status

| Area | Status |
|------|--------|
| Manual drive | ✅ Complete and working |
| Sonar readings | ✅ Complete and working |
| Auto emergency stop | ✅ Complete and working |
| Simple mapping (Mapper) | ✅ Complete and working |
| Advanced mapping + A* | ✅ Complete and working |
| Web dashboard | ✅ Complete and working |
| Encoder feedback | 🔲 Wired but not yet implemented |
| Sonar voltage dividers | 🔲 Planned (next step) |
| Cross-platform (Mac/Linux/Pi) | 🔲 Future scope |
| Camera integration | 🔲 Future scope |
| LiDAR integration | 🔲 Future scope |

---

*Document 11 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
