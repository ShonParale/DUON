# 07 — Troubleshooting & Known Issues

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel

---

## 🔴 Known Hardware Issues

### Issue 1: Sonar Readings Fluctuating / Erratic

**Status:** Active known issue  
**Root Cause:** The HC-SR04 ECHO pin outputs 5V logic, but ESP32 GPIO pins are rated for 3.3V maximum. Directly connecting the ECHO pin to the ESP32 can cause noisy readings and risks damaging the GPIO over time. Additionally, jumper cables add capacitance and pick up electrical noise from motor driver switching.

**Current Mitigation:** `SonarProcessor` class in `web_server.py` applies a 7-reading rolling median filter with spike rejection (±40cm / 1.8× ratio) and a 3cm jitter gate.

**Permanent Fix (Next Step):** Add a resistor voltage divider on each ECHO line:
```
Sonar ECHO (5V) ──── R1 (1kΩ) ──┬──── ESP32 GPIO (max 3.3V)
                                  │
                                 R2 (2kΩ)
                                  │
                                 GND
```

---

### Issue 2: Jumper Wire Connections Loose / Intermittent

**Status:** Active known issue  
**Root Cause:** Jumper cables have friction-fit connections that loosen over time, especially with robot vibration during movement.

**Symptoms:**
- Sonar readings suddenly drop to 0 or 400
- Motors stop or behave erratically
- ESP32 appears connected but motors don't respond

**Fix:** Check and reseat all jumper connections. Long-term: solder wires to component pins or design a custom PCB.

---

### Issue 3: BTS7960 Driver Cuts Out

**Status:** By design (protection feature), known operational issue  
**Root Cause:** BTS7960 has built-in overcurrent and overtemperature protection that shuts it down on fault.

**Symptoms:**
- Motors on one side stop responding
- No error on Python side (TCP still connected)

**Recovery:**
1. Stop sending drive commands (press X or stop button)
2. Wait 2–3 minutes for driver to cool
3. Press RESET button on the respective ESP32
4. Re-connect in the web dashboard if needed

**Prevention:**
- Do not run motors at full speed (255 PWM) on hard surfaces for extended periods
- Check motor wiring polarity — reverse polarity can cause high current draw

---

### Issue 4: Encoder Not Functional

**Status:** Known — not yet implemented  
**Root Cause:** Encoder signal conditioning (resistor dividers) not installed; encoder reading code not written in firmware.

**Impact:** Dead-reckoning position tracking drifts over time; mapping accuracy degrades with distance from start.

---

## 🟠 Known Software Issues

### Issue 5: Dead-Reckoning Position Drift

**Status:** Active known issue (architecture limitation)  
**Root Cause:** Position is estimated using `time × estimated_speed`. Actual speed varies based on:
- Battery charge level
- Surface friction (carpet vs tile vs wood)
- Motor-to-motor variation
- Load (turning radius varies)

**Symptoms:**
- Bot indicator on Mapper/Mapping canvas drifts from actual robot position over time
- Autonomous mapping produces distorted maps after several minutes

**Mitigation:** Reset bot position manually after noticing drift. Short mapping sessions are more accurate.

**Fix:** Encoder-based odometry (Next Step).

---

### Issue 6: Mapper Page Map Not Saved to Disk

**Status:** By design on Mapper page; known limitation  
**Clarification:** The **Mapper page** (simple mapping) does NOT persist map data — it resets on MAP_CLEAR or page reload. Only the **Mapping page** (advanced) saves maps as JSON files.

---

### Issue 7: Multiple Browser Tabs / Devices — Command Conflicts

**Status:** Known limitation  
**Root Cause:** All WebSocket clients receive all broadcasts, but all clients can also send commands. If two users on different devices send contradictory commands simultaneously, the robot receives both.

**Current Behaviour:** Last command received wins. No session locking.

**Mitigation:** Designate one device as the "controller" during operation.

---

### Issue 8: WebSocket Reconnect During Mapping

**Status:** Known edge case  
**Behaviour:** If the browser disconnects and reconnects during autonomous mapping or navigation, the new session immediately receives the current map state via `ADV_GET_STATE` on connection. However, the Mapper page (simple) state is NOT restored — only the live data stream resumes.

---

### Issue 9: Python IDLE / Terminal Encoding on Windows

**Status:** Known platform issue  
**Root Cause:** Windows default code page may cause Unicode characters in print statements to fail.

**Fix:** `start_server.bat` includes `chcp 65001` to set UTF-8 code page before running.

If running manually from CMD, run `chcp 65001` first or use Windows Terminal which handles UTF-8 natively.

---

## 🟡 Connectivity Troubleshooting

### ESP32 Not Connecting to Wi-Fi

| Check | Action |
|-------|--------|
| Wi-Fi band | Confirm router/hotspot broadcasts **2.4 GHz** (ESP32 does NOT support 5 GHz) |
| Credentials | SSID and password in `.ino` files must match exactly — case sensitive |
| Distance | Move ESP closer to router/hotspot during initial testing |
| Router channel | Try changing Wi-Fi channel if many networks are on same channel |
| Serial output | Connect via USB, open Serial Monitor @ 115200 baud, press RESET — watch for error messages |

**Common Serial Monitor error patterns:**

```
[WIFI] Connecting.....  (keeps going → wrong SSID/password or 5GHz)
```
If dots appear endlessly — almost always wrong credentials or 5 GHz band.

---

### Python Cannot Connect to ESP32

| Check | Action |
|-------|--------|
| IP address | Verify ESP IP in dashboard matches what's shown in Serial Monitor |
| Same network | Laptop must be on the same Wi-Fi network as the ESPs |
| Firewall | Windows Firewall may block port 8080 — add an exception |
| ESP running | Confirm ESP is powered and has connected to Wi-Fi (check Serial Monitor) |
| Timeout | Give it 10 seconds; TCP connect timeout is 5 seconds |

**How to find the correct IP:**
1. Connect ESP via USB cable
2. Open Arduino IDE → Tools → Serial Monitor → 115200 baud
3. Press RESET button on ESP32
4. IP prints after Wi-Fi connects: `[WIFI] ESP32 #1 IP: 192.168.1.xxx`

---

### ESP Connects Then Immediately Disconnects

| Cause | Fix |
|-------|-----|
| Power instability on ESP32 | Check USB power bank cable and charge; try different cable |
| Wi-Fi signal weak | Move bot closer to router during operation |
| Multiple Python instances | Check Task Manager — kill stale Python processes, then restart |
| Python server crash | Run via IDLE to see full error traceback |

---

### Browser Cannot Open Dashboard

| Check | Action |
|-------|--------|
| Server running? | Confirm `start_server.bat` or Python is running in terminal |
| Correct URL? | Use `http://localhost:5000` on same machine, or `http://[laptop-ip]:5000` from another device |
| Port 5000 in use? | Another instance may be running — check Task Manager; kill and restart |
| Firewall? | Allow Python through Windows Defender Firewall |
| HTTPS error? | Always use `http://` — not `https://` for local access |

---

### WebSocket Keeps Disconnecting in Browser

| Check | Action |
|-------|--------|
| Python server crashed? | Check terminal / IDLE for errors |
| Sleep/suspend? | Laptop going to sleep kills the server — disable sleep |
| Long idle? | Some browsers throttle background tabs — keep dashboard tab active |
| Network change? | Laptop switching Wi-Fi networks drops all connections |

---

## 🟡 Motor / Drive Troubleshooting

### Robot Moves in Circles Instead of Straight

**Cause:** Motor polarity mismatch — one side motors are running backwards.

**Diagnose:**
1. Send `W` command
2. Watch which side goes forward and which reverses

**Fix:**
- If LEFT side is reversed: swap B1_RPWM and B1_LPWM values in `1EC.ino`
- If RIGHT side is reversed: swap B2_RPWM and B2_LPWM values in `2EC.ino`
- Or physically swap motor wires on the BTS7960 M+ and M– terminals

---

### Only Left or Only Right Motors Respond

| Check | Action |
|-------|--------|
| ESP connection | Check if both ESP1 and ESP2 show green in dashboard |
| Motor power | Check LiPo battery charge and connection to BTS7960 |
| Enable pins | Confirm R_EN and L_EN on faulty BTS7960 are connected to 5V |
| BTS7960 fault | BTS7960 may have tripped — see Issue 3 recovery steps |

---

### Motors Twitch / Stutter

| Cause | Fix |
|-------|-----|
| Wi-Fi latency spikes | Normal during heavy network traffic; use dedicated hotspot |
| Multiple drive commands queued | Only one command at a time — ensure key release sends STOP |
| Power supply issues | Check USB cable quality for ESP; check battery charge |

---

## 🟡 Sonar / Mapping Troubleshooting

### All Sonar Values Show `---` on Drive Page

**Cause:** ESP1 not connected to Python server.

**Fix:** Go to Network page → Connect ESP1. Sonar data is only sent by ESP1.

---

### Sonar Values Are Frozen (Not Updating)

| Check | Action |
|-------|--------|
| ESP1 still connected? | Check ESP1 status indicator in top bar |
| `esp1_lag` value | Check status bar ping — if lag > 5000ms, ESP1 may have silently disconnected |
| Sonar wiring | One or more TRIG/ECHO wires may be loose |

---

### Mapper Map Looks Distorted / Wrong Shape

| Cause | Fix |
|-------|-----|
| Dead-reckoning drift | Reset position and remap shorter sections |
| Pulse/turn timing wrong | Adjust pulse_ms and turn_ms sliders on Mapper page |
| Speed estimate wrong | If SPEED_CM_S doesn't match actual speed, map will stretch/compress |
| Surface change | Mapping on carpet vs tile gives different effective speeds |

---

### Autonomous Exploration Gets Stuck in Corner

**Cause:** All 3 sonar thresholds are met simultaneously (front, left, right all blocked).

**Behaviour:** Robot executes U-turn (2× right 90° turns). If still blocked after U-turn, may loop.

**Fix:**
- Manually stop exploration (MAP_STOP or ADV_EXPLORE_STOP)
- Reverse robot manually out of corner
- Restart exploration

---

### A* Navigation — "No path found"

| Cause | Fix |
|-------|-----|
| Target inside an obstacle | Click goal position on open floor area |
| All paths blocked by obstacles | Remove or resize obstacles to leave passage |
| Start position invalid | Ensure bot position is set to a free cell |
| Room too small vs grid resolution | Increase room dimensions in Mapping page settings |

---

## 🟡 Code Upload / Arduino IDE Troubleshooting

### Upload Fails — "Port Not Found"

| Check | Action |
|-------|--------|
| USB cable | Replace with known-good data cable (not charge-only) |
| Driver installed | Install CP210x or CH340 USB driver if ESP32 not detected |
| COM port | Go to Device Manager → Ports → find the new COM port |
| Board selected | Tools → Board → must be ESP32 variant (ALKS ESP32 or ESP32 Dev Module) |
| Python using port | Close Python app and IDLE before uploading firmware |

---

### Serial Monitor Shows Garbled Text

**Fix:** Set Serial Monitor baud rate to exactly **115200** — must match `Serial.begin(115200)` in firmware.

---

### Serial Monitor Not Working (No Output)

**Cause:** Python app may be running in background and holding the serial port.

**Fix:**
1. Open Task Manager → find Python process → End Task
2. Close and reopen Arduino IDE
3. Reopen Serial Monitor

---

## 🟡 Python / Server Troubleshooting

### `ModuleNotFoundError` on Launch

**Fix:** Run `setup.bat` first to install all required packages:
```
pip install fastapi uvicorn websockets pydantic python-multipart
```

---

### `Port 5000 already in use`

**Cause:** A previous DUON instance is still running.

**Fix:**
1. Open Task Manager → find Python → End Task
2. Re-run `start_server.bat`

---

### Server Starts But Dashboard Won't Load

**Fix sequence:**
1. Confirm URL is `http://localhost:5000` (not https)
2. Check Windows Firewall — allow Python/uvicorn on port 5000
3. Try a different browser
4. Run `web_server.py` via IDLE (right-click → Edit with IDLE → F5) to see full error

---

### How to See Full Python Error Logs

**Method 1 — IDLE:**
Right-click `web_server.py` → Open with → IDLE → Run → Run Module (F5)

> If "Edit with IDLE" not visible: right-click → Show more options → Edit with IDLE

**Method 2 — Command Prompt:**
```cmd
cd /d "path\to\DUON"
python web_server.py
```

Both methods show full tracebacks in the console.

---

## 📋 Quick Diagnostic Checklist

Run this checklist in order when the system is not working:

```
□ 1. Is Python server running? (start_server.bat or IDLE)
□ 2. Can browser open http://localhost:5000?
□ 3. Is WebSocket connected? (status bar shows LIVE)
□ 4. Are ESPs powered and LED blinking normally?
□ 5. Did ESPs connect to Wi-Fi? (check Serial Monitor)
□ 6. Is ESP IP in dashboard correct?
□ 7. Is laptop on same Wi-Fi network as ESPs?
□ 8. Did you click Connect in Network page?
□ 9. Are ESP1 and ESP2 dots green in status bar?
□ 10. Is motor battery (LiPo) charged and connected?
□ 11. Are all jumper wires seated firmly?
□ 12. Is e-stop active? (check AUTO button state)
```

---

*Document 7 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
