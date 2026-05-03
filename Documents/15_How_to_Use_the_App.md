# 15 — How to Use the App

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Audience:** Anyone using the DUON web dashboard — students, professors, operators, demo viewers.

---

## Opening the Dashboard

| Situation | URL to Open |
|-----------|------------|
| On the same laptop running the server | `http://localhost:5000` |
| On a phone/tablet/another PC on the same Wi-Fi | `http://[laptop-IP]:5000` |
| Via Cloudflare Tunnel (remote) | The public URL shown in terminal |

The laptop IP is shown in the server terminal window when `start_server.bat` is launched. Example: `http://192.168.1.100:5000`.

You can also scan the **QR code** shown on the Network page to open the dashboard on your phone instantly.

---

## Understanding the Top Status Bar

The status bar is always visible at the top of the screen on every page.

```
● LIVE  [ESP1 ●] [ESP2 ●]  F: 120 cm  MAP: OFF  ■ STOP  ⚡ AUTO  88ms
```

| Element | What It Shows |
|---------|--------------|
| **● LIVE / ● DISCONNECTED** | WebSocket connection to Python server |
| **ESP1 ●** | ESP32 #1 connection (green = connected, grey = offline) |
| **ESP2 ●** | ESP32 #2 connection (green = connected, grey = offline) |
| **F: 120 cm** | Live front sonar reading (red if ≤10 cm) |
| **MAP: ON/OFF** | Whether autonomous mapping is currently running |
| **■ STOP** | Emergency stop button — stops motors immediately |
| **⚡ AUTO** | Auto E-Stop toggle — turns orange when armed |
| **88ms** | WebSocket latency (round-trip ping time) |

---

## Page-by-Page Guide

---

### 📋 Overview Page (Home)

**How to access:** Click the DUON logo or the first nav item.

This is the landing page. It contains:
- Project name and description
- Team member names and links
- A brief quick-start guide
- System status at a glance

No controls on this page — it is informational only.

---

### 🌐 Network Page

**How to access:** Click **Network** in the sidebar.

This page manages all connections between the dashboard, Python server, and ESP32 boards.

#### ESP Connection Panel

| Field | What to Enter |
|-------|--------------|
| ESP1 IP | IP address of ESP32 #1 (e.g., `192.168.1.159`) |
| ESP2 IP | IP address of ESP32 #2 (e.g., `192.168.1.162`) |

**Buttons:**
- **Save IPs** — saves the IP addresses (also sent to Python, persisted in `robot_config.json`)
- **Connect Both** — attempts to connect to both ESPs simultaneously
- **Disconnect Both** — closes both TCP connections
- **Connect / Disconnect** (individual) — per-ESP connect/disconnect buttons

**Status indicators:**
- Each ESP card shows a coloured dot (green = online, grey = offline) and Online/Offline text
- The top status bar ESP dots also update instantly

#### QR Code Panel

Displays a QR code of the current dashboard URL. Scan this with a phone camera to instantly open the dashboard on your phone — no typing needed.

Also shows the URL as text for easy copying and sharing.

#### Ping / Latency Panel

Shows three latency values:
- **WebSocket ping** — round-trip time between browser and Python server
- **ESP1 lag** — time since last data received from ESP32 #1
- **ESP2 lag** — time since last data received from ESP32 #2

A high ESP lag (>5000ms) indicates the ESP may have silently disconnected.

#### Connection Log

A scrollable terminal showing all network events with timestamps:
- `[NET]` — connection events (green)
- `[CFG]` — configuration changes (green)
- `[ERROR]` — connection failures (red)
- `[WARN]` — warnings (orange)

---

### 🕹️ Drive Page

**How to access:** Click **Drive** in the sidebar. Keyboard control activates automatically.

This page is your manual robot control centre.

#### Sonar Gauges (Top Section)

Three animated arc gauges showing live distance readings:
- **L** — Left sonar (45° diagonal front-left)
- **F** — Front sonar (straight ahead)
- **R** — Right sonar (45° diagonal front-right)

Gauge arc fills proportionally up to 200cm. Colour coding:
- 🟢 Green = safe (>30 cm)
- 🟠 Orange = caution (11–30 cm)
- 🔴 Red = danger (≤10 cm)

#### Drive Controls

**D-Pad:** On-screen directional buttons. Press and hold to move, release to stop. Works with mouse on desktop and touch on mobile.

**Omni Joystick:** Circular drag joystick. Pull in any direction to move. Dead zone in the centre prevents accidental commands. Release to stop.

**Vertical Joystick:** Drag up for forward, down for backward. Release to stop.

**Horizontal Joystick:** Drag left to turn left, right to turn right. Release to stop.

**Keyboard** (PC only):
```
W / ↑     = Forward        Numpad 8 = Forward
S / ↓     = Backward       Numpad 2 = Backward
A / ←     = Turn Left      Numpad 4 = Turn Left
D / →     = Turn Right     Numpad 6 = Turn Right
X / Space = Stop           Numpad 5 = Stop
```

#### E-Stop Toggle (Drive Page)

A dedicated toggle switch on the Drive page mirrors the AUTO button in the status bar. Enabling it arms the auto emergency stop:
- If any sonar detects ≤10 cm → motors stop automatically
- E-Stop modal appears with the trigger reason
- **Override** button gives 3 seconds to reverse away from the obstacle

#### Command Log

Scrollable terminal on the Drive page showing all commands sent and received with timestamps.

---

### 🗺️ Mapper Page

**How to access:** Click **Mapper** in the sidebar.

This page lets the robot map a room autonomously using its sonar sensors.

#### Controls

| Button | Action |
|--------|--------|
| **▶ Start Mapping** | Robot begins autonomous navigation and mapping |
| **■ Stop Mapping** | Robot stops; map data is preserved on screen |
| **Clear Map** | Resets all map data and robot position to zero |

#### Mapping Settings

Adjust before starting — changes cannot be applied mid-mapping:

| Setting | Default | Description |
|---------|---------|-------------|
| Mode | Pulse | Pulse = stop/scan/move; Smooth = continuous movement |
| Pulse Duration | 400ms | How long each forward burst lasts |
| Turn Duration | 480ms | How long each 90° turn lasts |
| Front Threshold | 35cm | Distance at which front obstacle triggers a turn |
| Diagonal Threshold | 25cm | Distance at which side obstacle triggers pre-turn |

#### Map Canvas

The canvas updates in real time during mapping:

| Colour | Meaning |
|--------|---------|
| 🟥 Red squares | Detected walls / obstacles (sonar endpoints) |
| 🟩 Green squares | Confirmed free space (along sonar ray path) |
| 🔵 Cyan dots | Robot's travel path |
| 🟡 Yellow arrow | Robot's current position and heading direction |

**Canvas navigation:**
- **Scroll wheel** — Zoom in or out
- **Click + drag** — Pan the map view
- **Double-click** — Reset zoom and pan

#### Robot Pose Display

Shows the robot's estimated position:
- **X** — horizontal position in cm from start
- **Y** — vertical position in cm from start
- **H** — heading in degrees (0° = North/up)

#### Auto Mapping Log

Scrollable terminal showing all autonomous decisions made:
- `[AUTO] FWD F=120 L=80 R=90` — moved forward
- `[AUTO] TURN R` — turned right
- `[AUTO] U-TURN` — executed U-turn

---

### 🗺️ Mapping Page (Advanced)

**How to access:** Click **Mapping** in the sidebar.

This is the full-featured mapping and navigation page.

#### Map File Management

| Action | How |
|--------|-----|
| Create new map | Type name in field → **New Map** |
| Load existing map | Select from dropdown → **Load** |
| Save current map | Click **Save Map** |
| Close map | Click **Close Map** (file stays on disk) |
| Delete map | Select from dropdown → **Delete** |

#### Room Setup

Set the room dimensions (in cm) to define the canvas scale:
- **Width** — room width (default 400cm = 4 metres)
- **Height** — room height (default 400cm = 4 metres)

#### Drawing Obstacles

With a map open:
1. Click and drag on the canvas to draw a rectangle
2. Release to place the obstacle
3. Enter a name for the obstacle in the sidebar
4. Click **Add** to confirm

The obstacle appears as a filled block on the canvas.

**Managing obstacles:**
- **Edit** — resize or rename an existing obstacle (select it in the list)
- **Remove** — delete selected obstacle

#### Setting Robot Position

1. Click **Set Bot Position** button
2. Click on the canvas where the robot currently is physically
3. The yellow robot marker moves to that point
4. Optionally set the heading direction

#### Sonar Heat-Map

While a map is open and ESP1 is connected, every sonar reading automatically plots a dot on the canvas at the estimated obstacle location. These dots form a heat-map showing where the sonars have detected objects as the robot moves.

Click **Clear Heat-Map** to erase heat-map data without clearing obstacles.

#### Autonomous Exploration

1. Click **Start Explore** — robot moves autonomously, building the heat-map as it goes
2. Watch the canvas as heat-map dots appear
3. Click **Stop Explore** to halt the robot

#### A* Pathfinding Navigation

1. Ensure obstacles are drawn (or heat-map has been built)
2. Set the robot's starting position
3. Click **Set Target** then click the destination point on canvas
4. Click **Navigate** — the robot calculates and follows the optimal path
5. The planned route appears as a coloured line on the canvas
6. The robot travels waypoint by waypoint
7. If an obstacle is detected mid-route, the robot replans automatically
8. Click **Stop Navigation** to abort

---

### ⚙️ Settings Page

**How to access:** Click **Settings** in the sidebar.

#### Theme Toggle

Switch between **Light** and **Dark** mode. Your preference is saved in the browser and persists across sessions.

Dark mode uses deep navy/dark backgrounds; light mode uses clean white/light backgrounds.

#### Keyboard Shortcut Guide

Displays a reference of all keyboard shortcuts available on the Drive page.

#### Shutdown Server

Clicking **Shutdown Server** shows a confirmation dialog. If confirmed:
- The Python server is gracefully stopped
- The browser tab attempts to close
- The `start_server.bat` terminal window closes

Use this to cleanly stop the application. Do not just close the terminal window while the robot is moving — always STOP the robot first.

---

## Theme System

The dashboard fully supports light and dark mode. The theme applies across all pages simultaneously.

| Feature | Light Mode | Dark Mode |
|---------|-----------|-----------|
| Background | White / light grey | Deep navy / dark blue-grey |
| Text | Dark | Light |
| Sonar gauges | Blue/green on white | Blue/green on dark |
| Map canvas | Light grey background | Very dark background |
| Status indicators | Coloured on white | Coloured on dark |

Toggle via: Settings page → Theme toggle, or the moon/sun icon in the status bar.

---

## Accessing From Multiple Devices

Because DUON runs as a web server on your laptop's local network, multiple devices can open the dashboard simultaneously:

1. Make sure all devices are on the same Wi-Fi network
2. All devices open: `http://[laptop-IP]:5000`
3. All devices receive the same real-time updates (sonar, connection status, map data)
4. All devices can send commands — the last command received by the server wins

**Tip:** Use the QR code on the Network page to quickly share the URL with others in the room.

---

## Browser Compatibility

| Browser | Status | Notes |
|---------|--------|-------|
| Chrome (desktop/Android) | ✅ Fully supported | Recommended |
| Edge | ✅ Fully supported | |
| Firefox | ✅ Fully supported | |
| Safari (macOS/iOS) | ✅ Supported | Touch joysticks work well |
| Samsung Internet | ✅ Supported | |
| Internet Explorer | ❌ Not supported | Use any modern browser |

---

## App Keyboard Shortcut Reference Card

```
NAVIGATION:
  Click sidebar items = navigate pages

DRIVE (from Drive page, no click needed):
  W / ↑  = Forward          S / ↓  = Backward
  A / ←  = Turn Left        D / →  = Turn Right
  X / Space = STOP

NUMPAD:
  8 = Forward    2 = Backward
  4 = Left       6 = Right
  5 = STOP

JOYSTICKS (mouse or touch):
  Omni = any direction    VJ = forward/back    HJ = left/right

EMERGENCY:
  STOP button (always visible top bar)
  X key / Space key (anywhere on Drive page)
```

---

*Document 15 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
