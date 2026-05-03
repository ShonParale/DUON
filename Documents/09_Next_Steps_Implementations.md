# 09 — Next Steps Implementations

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Purpose:** Detailed guide for the immediate next improvements to be made to the project.

---

## Overview

The following are short-to-medium term improvements that are the logical continuation of the current codebase. These are not experimental ideas — they are planned, partially-prepared features that build directly on what already exists.

Priority order (highest to lowest):
1. Sonar voltage divider fix
2. Encoder implementation
3. Permanent wiring (PCB or solder)
4. Improved mapping algorithm
5. Wired serial communication option
6. Cross-platform support (macOS, Linux, Raspberry Pi)

---

## Next Step 1: Sonar ECHO Voltage Divider

**Why:** HC-SR04 ECHO pin outputs 5V. ESP32 GPIOs are rated 3.3V max. Direct connection risks long-term GPIO damage and causes noisy readings.

**What to do:**

Add a resistor voltage divider on every ECHO line (3 total):

```
HC-SR04 ECHO (5V) ──── R1 (1 kΩ) ──┬──── ESP32 GPIO (3.3V)
                                     │
                                    R2 (2 kΩ)
                                     │
                                    GND
```

This scales 5V → ~3.33V which is safe for ESP32.

**Parts needed:** 6× resistors (3× 1kΩ and 3× 2kΩ) or use 10kΩ and 20kΩ for the same ratio.

**Connections to update:**
- S1 ECHO (GPIO 33): add divider
- S2 ECHO (GPIO 16): add divider
- S3 ECHO (GPIO 17): add divider

**Code changes:** None — the GPIO reading code in `1EC.ino` remains the same.

**Expected benefit:** Reduced sonar reading fluctuation; may allow reducing `SonarProcessor` filter aggressiveness (smaller `SPIKE_ABS`, wider `MIN_VALID` range).

---

## Next Step 2: Encoder Implementation

**Why:** Without encoder feedback, dead-reckoning position tracking drifts. Accurate encoders will dramatically improve autonomous mapping accuracy and make closed-loop motor control possible.

### Part A — Hardware Wiring Fix

Same as sonar, encoder signal lines need resistor signal conditioning since encoder outputs are 5V:

```
Encoder A (5V) ──── R1 (1 kΩ) ──┬──── ESP32 GPIO (3.3V safe)
                                  │
                                 R2 (2 kΩ)
                                  │
                                 GND
```

Apply this to:
- ESP1: GPIO 34 (M1 Enc A), GPIO 36 (M3 Enc A)
- ESP2: GPIO 32 (M2 Enc A), GPIO 39 (M4 Enc A)

Also connect Encoder B channels (currently unconnected) if direction sensing is needed.

### Part B — ESP1 Firmware Changes (`1EC.ino`)

Add encoder interrupt service routines:

```cpp
// Encoder pins (already wired)
const int ENC_M1 = 34;
const int ENC_M3 = 36;

volatile long enc_M1 = 0;
volatile long enc_M3 = 0;

void IRAM_ATTR isr_M1() { enc_M1++; }
void IRAM_ATTR isr_M3() { enc_M3++; }

// In setup():
attachInterrupt(digitalPinToInterrupt(ENC_M1), isr_M1, RISING);
attachInterrupt(digitalPinToInterrupt(ENC_M3), isr_M3, RISING);

// In loop() — report every 200ms:
char encBuf[48];
snprintf(encBuf, sizeof(encBuf), "[ENC]M:1,C:%ld,D:%s", enc_M1, "FWD");
client.println(encBuf);
snprintf(encBuf, sizeof(encBuf), "[ENC]M:3,C:%ld,D:%s", enc_M3, "FWD");
client.println(encBuf);
```

### Part C — ESP2 Firmware Changes (`2EC.ino`)

Same pattern for GPIO 32 (M2) and GPIO 39 (M4).

### Part D — Python Changes (`advanced_mapping.py`)

Replace time-based dead-reckoning with tick-based calculation:

```python
TICKS_PER_REV = 360     # encoder ticks per full wheel revolution
WHEEL_DIAM_CM = 6.5     # measure your wheel diameter
CM_PER_TICK   = (math.pi * WHEEL_DIAM_CM) / TICKS_PER_REV

def update_from_encoder(self, motor_id, ticks):
    dist_cm = ticks * CM_PER_TICK
    # Update bot_x, bot_y based on which motors moved
```

The existing `Robot._parse_enc()` method is already written — it broadcasts encoder data to the browser. Just add the odometry calculation on top.

---

## Next Step 3: Permanent Wiring (Solder / PCB)

**Why:** Jumper cables lose contact during robot movement and vibration. Loose connections cause:
- Random motor stops
- Erratic sonar readings
- Unexplained disconnections

**Options (easiest to most robust):**

### Option A — Solder Wires to Component Pins

Solder connection wire ends directly to:
- BTS7960 signal pins (RPWM, LPWM, GND)
- HC-SR04 pins (TRIG, ECHO, VCC, GND)
- Encoder motor connector pins

Pros: Cheap, quick, reliable.  
Cons: Hard to modify later.

### Option B — Custom Screw Terminal Board

Create a simple breakout board with screw terminals for each connection group. Wire once to the terminals, then use screws to secure wires.

Pros: Easy to service and modify.  
Cons: Requires some fabrication.

### Option C — Custom PCB

Design a PCB that:
- Mounts directly on the robot chassis
- Has sockets for ESP32 boards
- Includes onboard resistor dividers for sonar and encoder signals
- Has screw terminals for motor wires
- Has mounting holes for BTS7960 drivers

Tools: EasyEDA (free, web-based) or KiCad. Export Gerber files and order from JLCPCB or PCBWay.

Pros: Professional, clean, reliable, repeatable.  
Cons: Takes 2–4 weeks, small upfront cost.

---

## Next Step 4: Improved Mapping Algorithm

**Why:** Current dead-reckoning + simple sonar projection gives approximate maps. Improvements will make maps more accurate and useful for navigation.

### Improvement A — Sonar Fusion

Use all 3 sonars together to triangulate obstacle positions rather than treating each as independent. When two overlapping readings agree, the confidence in that obstacle location increases.

### Improvement B — Occupancy Grid with Probability

Replace the current binary wall/free set with a probabilistic occupancy grid:
- Each cell has a value 0.0–1.0 (probability of being occupied)
- Each sonar reading updates the probability (Bayesian update)
- Only cells above a threshold (e.g., 0.7) are drawn as walls
- Cells that are consistently seen as free decrease in probability

### Improvement C — Loop Closure Detection

When the robot returns to a previously mapped area (detectable by matching sonar patterns), apply a correction to reduce accumulated drift. This is a simplified form of SLAM (Simultaneous Localisation and Mapping).

### Improvement D — Encoder-Corrected Path

Once encoders are implemented (Next Step 2), integrate encoder ticks into the dead-reckoning to replace the time-based estimates. This alone will significantly improve map accuracy.

---

## Next Step 5: Wired Serial Communication Option

**Why:** Wi-Fi is sometimes unavailable (labs without routers, no hotspot) or unreliable. A wired USB-serial fallback would allow operation without Wi-Fi.

**Approach:**

1. Add a serial command parser to ESP firmware alongside the Wi-Fi TCP server:
```cpp
if (Serial.available()) {
  char cmd = Serial.read();
  // Same switch-case as TCP handler
}
```

2. In Python, add a serial mode alongside the TCP socket mode:
```python
import serial
ser = serial.Serial('COM3', 115200, timeout=0.1)
ser.write(b'W')
```

3. In the web dashboard Network page, add a "Serial Mode" toggle with COM port selector.

**Constraint:** Cannot run Arduino Serial Monitor and Python simultaneously on the same COM port — user must choose one.

---

## Next Step 6: Cross-Platform Support

**Why:** Currently tested and documented for Windows only. Many developers and labs use macOS or Linux.

### macOS

| Difference | Fix |
|------------|-----|
| `start_server.bat` is Windows only | Create `start_server.sh`: `python3 -m uvicorn web_server:app --host 0.0.0.0 --port 5000` |
| `setup.bat` is Windows only | Create `setup.sh`: `pip3 install fastapi uvicorn websockets pydantic python-multipart` |
| COM port naming | macOS uses `/dev/cu.usbserial-*` instead of `COM3` |
| `os._exit(0)` in shutdown | Works on macOS too — no change needed |

### Linux / Ubuntu

Same as macOS differences. Additionally:
- May need `sudo` for USB serial port access (or add user to `dialout` group)
- `python3` instead of `python` depending on distro

### Raspberry Pi OS

The full Python server can run on Raspberry Pi, making the laptop unnecessary:
1. Install Python 3 + pip on Pi
2. Copy DUON folder to Pi
3. Run `setup.sh` on Pi
4. Connect Pi to same Wi-Fi as ESPs
5. Open browser on any device → `http://[pi-ip]:5000`

This is a major milestone — the robot becomes fully self-contained with Pi onboard instead of needing a laptop.

---

## Implementation Priority Summary

| # | Task | Effort | Impact | Hardware Needed |
|---|------|--------|--------|----------------|
| 1 | Sonar voltage dividers | 1 hour | High — reduces noise | 6 resistors |
| 2 | Encoder firmware + code | 1–2 days | Very High — accurate mapping | Resistors for signal lines |
| 3 | Solder connections | 2–4 hours | High — reliability | Solder, iron |
| 4 | Improved mapping algorithm | 3–5 days | High — map quality | Software only |
| 5 | Wired serial option | 1 day | Medium — fallback mode | Software + USB cables |
| 6 | Cross-platform scripts | 2–3 hours | Medium — portability | Software only |

---

*Document 9 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
