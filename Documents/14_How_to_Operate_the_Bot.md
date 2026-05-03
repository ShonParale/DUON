# 14 — How to Operate the Bot

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Audience:** Anyone physically handling and driving the DUON robot.

---

## Before You Start — Safety Checklist

- [ ] Robot is placed on a flat surface with space to move
- [ ] No loose wires hanging below the chassis
- [ ] LiPo battery is sufficiently charged and connected
- [ ] Both ESP32 boards are powered (LEDs on)
- [ ] Python server is running on the laptop
- [ ] Both ESP1 and ESP2 show green in the dashboard
- [ ] Motor power (LiPo) is connected to the BTS7960 drivers

> **Power management tip:** You can test sonar readings without the LiPo connected — the ESPs run on USB power. Only connect the LiPo when you intend to drive the motors.

---

## Part 1 — Manual Driving

### 1.1 Open the Drive Page

In the web dashboard, click **Drive** in the sidebar navigation.

### 1.2 Sonar Status Check

Before driving, check the three sonar gauges at the top of the Drive page:
- **Left gauge (L):** Distance to obstacles on the left-front diagonal
- **Front gauge (F):** Distance to obstacles directly ahead
- **Right gauge (R):** Distance to obstacles on the right-front diagonal

Gauge colours:
- 🟢 **Green** — clear (>30 cm)
- 🟠 **Orange** — caution (11–30 cm)
- 🔴 **Red** — danger (≤10 cm)

If all gauges show `---`, ESP1 is not connected — go to Network page and connect ESP1 before driving.

---

### 1.3 Keyboard Control (PC — Recommended Method)

No click required — keyboard works globally on the Drive page as soon as you navigate to it.

| Key | Action |
|-----|--------|
| `W` or `↑` Arrow | Move Forward |
| `S` or `↓` Arrow | Move Backward |
| `A` or `←` Arrow | Turn Left |
| `D` or `→` Arrow | Turn Right |
| `X` or `Space` | Stop (Emergency) |
| `Numpad 8` | Forward |
| `Numpad 2` | Backward |
| `Numpad 4` | Turn Left |
| `Numpad 6` | Turn Right |
| `Numpad 5` | Stop |

> **Hold behaviour:** Hold a key to keep the robot moving. Release the key to stop. The robot sends a STOP command automatically when any direction key is released.

> **Text field focus:** Keyboard control is automatically disabled when you click inside a text input field (like the IP address fields). Click anywhere else on the page to re-enable.

---

### 1.4 D-Pad On-Screen Buttons

The D-Pad is visible on the Drive page. It works with mouse clicks on desktop and touch on mobile:

- **Press and hold** the button to move
- **Release** to stop
- Supports multi-touch on mobile — hold one direction, release to stop

| Button | Action |
|--------|--------|
| ▲ (Up) | Forward |
| ▼ (Down) | Backward |
| ◀ (Left) | Turn Left |
| ▶ (Right) | Turn Right |
| ■ (Stop/Centre) | Stop |

---

### 1.5 Omni Joystick

The circular joystick on the Drive page supports 8 directions:

- **Drag** the knob from the centre
- Direction is determined by where you drag (up = forward, left = turn left, etc.)
- A **dead zone** in the centre (~24px) sends STOP — releasing joystick also sends STOP
- The current command label is displayed below the joystick
- Works on both mouse and touch

| Drag Direction | Command |
|----------------|---------|
| Up | Forward (W) |
| Down | Backward (S) |
| Left | Turn Left (A) |
| Right | Turn Right (D) |
| Centre / Release | Stop (X) |

---

### 1.6 Dual-Axis Joysticks

Two separate slider joysticks are available for independent forward/back and left/right control:

**Vertical Joystick (Forward / Backward):**
- Drag up → Forward
- Drag down → Backward
- Release → Stop

**Horizontal Joystick (Left / Right):**
- Drag left → Turn Left
- Drag right → Turn Right
- Release → Stop

These work well on touchscreens where you use two thumbs independently.

---

### 1.7 Motor Behaviour Notes

- **Tank steering:** The robot turns by spinning one side forward and the other backward — it pivots on its own axis (not a gentle curve)
- **Turning radius:** The robot turns in place — it does not move forward while turning
- **Speed:** Always at full speed (255/255 PWM) in all directions — no variable speed control currently
- **Motor coast:** When STOP is sent, motors coast to a halt (not an abrupt brake)

---

## Part 2 — Emergency Stop

### 2.1 Manual Emergency Stop

Click the **STOP** button in the top status bar at any time. This immediately sends STOP to both ESPs regardless of any running automation.

Alternatively press `X` or `Space` on keyboard.

---

### 2.2 Auto Emergency Stop (E-Stop)

The automatic emergency stop can be enabled for extra safety:

1. Click the **⚡ AUTO** button in the top status bar — it turns orange when armed
2. Or toggle the E-Stop switch on the Drive page

**When armed:**
- If any sonar reading drops ≤ 10 cm, both motors stop automatically
- An E-Stop modal dialog appears in the browser with the trigger reason (e.g., "FRONT 8.2 cm")
- All further drive commands are blocked until resolved

**To override (move robot away from obstacle):**
1. In the E-Stop modal, click **Override**
2. A 3-second window opens — you can now reverse the robot to clear the obstacle
3. After 3 seconds, E-Stop re-arms automatically

**To disarm:**
- Click the **⚡ AUTO** button again (turns back to normal colour)
- E-Stop state resets; normal driving resumes

---

## Part 3 — Simple Autonomous Mapping (Mapper Page)

### 3.1 When to Use

Use the Mapper page when you want the robot to explore a room on its own and build a basic sonar map. Good for quick room scanning. No map is saved to disk from this page.

### 3.2 Setting Up

1. Navigate to the **Mapper** page
2. Place the robot in an open area with room to move
3. Ensure ESP1 is connected (sonar data required for autonomous mode)
4. **Optional:** Adjust mapping settings:
   - **Mode:** Pulse (recommended for accuracy) or Smooth (faster, less precise turns)
   - **Pulse Duration:** How long each forward burst lasts (default 400ms)
   - **Turn Duration:** How long each 90° turn takes (default 480ms)
   - **Front Threshold:** Distance at which front obstacle triggers a turn (default 35cm)
   - **Diagonal Threshold:** Distance at which side obstacles trigger a pre-turn (default 25cm)

### 3.3 Starting Mapping

1. Click **▶ Start Mapping**
2. The robot begins moving autonomously
3. The canvas updates in real time:
   - 🟥 **Red squares** = detected walls and obstacles
   - 🟩 **Green squares** = confirmed free space
   - 🔵 **Cyan dots** = robot travel path
   - 🟡 **Yellow arrow** = current robot position and heading

### 3.4 Navigating the Canvas

- **Scroll wheel** = Zoom in/out
- **Click and drag** = Pan the view
- **Double-click** = Reset zoom and pan to default

### 3.5 Stopping Mapping

Click **■ Stop Mapping** — the robot stops moving. The map remains visible.

Click **Clear Map** to reset the map and robot position back to zero.

### 3.6 Autonomous Decision Logic

The robot follows this logic each step:
```
Front clear AND sides clear     → Move forward (pulse)
Front clear BUT right too close → Pre-turn left
Front clear BUT left too close  → Pre-turn right
Front blocked, right open       → Turn right 90°
Front blocked, left open        → Turn left 90°
All sides blocked               → U-turn (two right 90° turns)
```

---

## Part 4 — Advanced Mapping & Navigation (Mapping Page)

### 4.1 Creating a New Map

1. Navigate to the **Mapping** page
2. In the map management panel, type a map name (e.g., "Lab Room")
3. Click **New Map**
4. Set room dimensions (width × height in cm)

### 4.2 Setting Bot Starting Position

1. Click the **Set Bot Position** button
2. Click on the canvas where the robot currently is in the room
3. The yellow robot marker moves to that position

### 4.3 Drawing Obstacles Manually

1. Click-drag on the canvas to draw an obstacle rectangle (like MS Paint)
2. Release to place the obstacle
3. Name the obstacle in the panel
4. Obstacles appear as filled rectangles on the canvas
5. You can resize, rename, or delete obstacles from the obstacle list panel

### 4.4 Live Sonar Heat-Map

When the map is active and ESP1 is connected, every sonar reading automatically projects onto the map as a heat-map dot — showing where each sensor detected an obstacle at the robot's current estimated position.

### 4.5 Autonomous Exploration

1. Click **Start Explore** — robot navigates autonomously (same logic as Mapper page)
2. Heat-map fills in as the robot moves
3. Click **Stop Explore** to halt

### 4.6 A* Point-to-Point Navigation

1. Draw obstacles on the map first (or rely on heat-map for obstacle data)
2. Set the bot's starting position
3. Click a destination point on the canvas → click **Navigate Here**
4. A planned path appears as a coloured line on the canvas
5. The robot follows the path waypoint by waypoint
6. If a new obstacle is detected during travel, the robot replans automatically
7. Click **Stop Navigation** to abort at any time

### 4.7 Saving and Loading Maps

- **Save:** Click **Save Map** — writes to `maps/MapName.json` on the laptop
- **Load:** Select a map from the dropdown → click **Load Map**
- **Delete:** Select a map from the dropdown → click **Delete Map**
- **Close:** Click **Close Map** — clears canvas but keeps the file on disk

---

## Part 5 — Physical Handling Guidelines

### Picking Up the Robot

- Always lift from the chassis frame — not by the wires or ESP boards
- Before lifting, press STOP in the dashboard
- If motors are running when lifted, they will continue — always STOP first

### Placing the Robot

- Place on a flat, firm surface — carpet significantly reduces speed and increases motor load
- Keep the sonar sensors clear of obstructions (pointing forward)
- Do not block the sonar sensors with cables or hands during mapping

### Charging / Battery Management

- Charge LiPo battery using a dedicated LiPo charger — never overcharge
- Charge USB power banks as needed
- If an ESP32 becomes very hot during operation, disconnect it immediately
- If the BTS7960 driver cuts out (protection triggered), allow 2–3 minutes before resetting the ESP

### After Each Session

- Press STOP before powering down
- Disconnect the LiPo battery first (motors)
- Then disconnect USB power from ESPs
- Close the Python server (Settings → Shutdown, or close the terminal)

---

## Quick Reference Card

```
START SESSION:
  1. Power ESP32s (USB banks)  2. Connect LiPo (motors)
  3. Start start_server.bat   4. Open browser → localhost:5000
  5. Network page → Enter IPs → Connect Both

DRIVE:
  Keyboard WASD or Arrow keys (hold to move, release to stop)
  D-Pad / Joystick on touchscreen

EMERGENCY:
  STOP button (top bar) | X key | Space key
  Auto E-Stop: ⚡ AUTO button → arms auto-halt at <10cm

MAPPING:
  Mapper page → Start Mapping (simple, no save)
  Mapping page → New Map → Draw obstacles → Explore / Navigate

END SESSION:
  STOP → Disconnect ESPs → Close server → Disconnect LiPo
```

---

*Document 14 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
