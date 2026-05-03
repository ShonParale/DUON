# 04 — ESP2 Code Explanation

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**File Covered:** `2EC/2EC.ino`
**Target Hardware:** ESP32 #2 (Right Side — B2 Motor Driver Only)

---

## 📌 What Does ESP2 Do?

ESP32 #2 is the **secondary controller** of the DUON robot. It is responsible for:

1. **Connecting to the Wi-Fi network** and waiting for the Python server to connect
2. **Receiving motor commands** from the Python server (W/A/S/D/X)
3. **Driving the right-side motors** (M2 Front-Right and M4 Rear-Right) via BTS7960 #2
4. **Correcting motor polarity in software** — due to physical mounting, the right-side motors are wired in reverse direction relative to the left side, so the RPWM/LPWM signals are swapped in code

> **Note:** ESP2 does NOT handle any sonar sensors. All sonar reading is handled exclusively by ESP1. ESP2 is purely a motor controller for the right side.

---

## 📄 Full Code with Line-by-Line Explanation

### Section 1 — File Header & Library Import

```cpp
// ESP32 #2 - B2 RIGHT SIDE - POLARITY CORRECTED IN SOFTWARE
#include <WiFi.h>
```

- The header comment immediately tells you this is for the right side and that polarity correction is applied in code (not by rewiring).
- `#include <WiFi.h>` imports the ESP32 built-in Wi-Fi library.

---

### Section 2 — Configuration Constants

```cpp
const char* ssid     = "Airtel_ShonPraleWiFi";
const char* password = "1#Gswifi05s";
const int   PORT     = 8080;
```

- Same Wi-Fi credentials and port number as ESP1.
- Both ESPs connect to the **same Wi-Fi** and both listen on **port 8080**, but they each have a different IP address (assigned by the router via DHCP).
- The Python server connects to each ESP separately using their individual IP addresses.

---

### Section 3 — BTS7960 #2 Motor Driver Pins

```cpp
const int B2_RPWM = 18;
const int B2_LPWM = 19;
const int PWM_FREQ = 5000, PWM_RES = 8, SPEED = 255;
```

| Constant | Value | Meaning |
|----------|-------|---------|
| `B2_RPWM` | GPIO 18 | PWM pin for Forward direction on BTS7960 #2 |
| `B2_LPWM` | GPIO 19 | PWM pin for Reverse/Backward direction on BTS7960 #2 |
| `PWM_FREQ` | 5000 Hz | Same PWM frequency as ESP1 (5 kHz) |
| `PWM_RES` | 8 bits | 8-bit resolution — values 0–255 |
| `SPEED` | 255 | Full speed (100% duty cycle) |

---

### Section 4 — TCP Server and Client Objects

```cpp
WiFiServer server(PORT);
WiFiClient client;
```

- Identical structure to ESP1.
- `WiFiServer server(PORT)` creates a TCP server on port 8080.
- `WiFiClient client` holds the single active Python connection.

---

### Section 5 — `setup()` Function

```cpp
void setup() {
  Serial.begin(115200);
  Serial.println("\n[BOOT] ESP32 #2 - B2 RIGHT SIDE");

  ledcAttach(B2_RPWM, PWM_FREQ, PWM_RES);
  ledcAttach(B2_LPWM, PWM_FREQ, PWM_RES);
  stopMotors();

  WiFi.begin(ssid, password);
  Serial.print("[WIFI] Connecting");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\n[WIFI] Connected!");
  Serial.print("[WIFI] ESP32 #2 IP: ");
  Serial.println(WiFi.localIP());

  server.begin();
  server.setNoDelay(true);
  Serial.println("[READY] Waiting for Python...");
}
```

**Step-by-step:**
1. **Serial.begin(115200)** — enables serial debugging
2. **ledcAttach()** — initializes GPIO 18 and 19 as hardware PWM channels at 5kHz / 8-bit
3. **stopMotors()** — calls the stop function (note: `stopMotors()` is defined AFTER the `loop()` function in this file — valid in C++ as function prototypes are not required when the full definition exists in the same file)
4. **WiFi.begin()** — connects to Wi-Fi; blocks until connected, printing progress dots
5. **WiFi.localIP()** — prints IP address to Serial Monitor
6. **server.begin()** — starts TCP server on port 8080
7. **server.setNoDelay(true)** — disables Nagle's algorithm, ensuring commands are sent immediately without buffering (reduces latency for real-time motor control)

> 🔑 **Key difference from ESP1:** ESP2 uses `server.setNoDelay(true)`. ESP1 does not have this line, but both work fine in practice. `setNoDelay` is a socket-level optimization that is especially useful for small, frequent packets.

---

### Section 6 — `loop()` Function — Part 1: Client Connection Handling

```cpp
void loop() {
  if (!client || !client.connected()) {
    if (client) {
      client.stop();
      stopMotors();
      Serial.println("[CLIENT] Disconnected - waiting...");
    }
    client = server.accept();
    if (client) {
      Serial.println("[CLIENT] Python connected!");
      client.println("[ESP2] B2 Right side ready");
    }
  }
```

**Differences from ESP1's connection handling:**
- ESP2 explicitly calls `client.stop()` when detecting a disconnection — this cleanly closes the old socket
- ESP2 also calls `stopMotors()` on disconnection — a safety measure so that if Python disconnects unexpectedly, the right motors stop (ESP1 relies on the motor command loop already being idle)
- When Python reconnects, ESP2 sends the greeting `[ESP2] B2 Right side ready`

---

### Section 6 — `loop()` Function — Part 2: Motor Command Handler (with Polarity Correction)

```cpp
  if (client && client.connected() && client.available()) {
    char cmd = client.read();
    switch (cmd) {
      case 'W': case 'w':
        // B2 motors reversed - swap RPWM/LPWM
        ledcWrite(B2_RPWM, 0); ledcWrite(B2_LPWM, SPEED);
        Serial.println("[CMD] FORWARD"); client.println("[ESP2] FORWARD");
        break;
      case 'S': case 's':
        ledcWrite(B2_RPWM, SPEED); ledcWrite(B2_LPWM, 0);
        Serial.println("[CMD] BACKWARD"); client.println("[ESP2] BACKWARD");
        break;
      case 'A': case 'a':
        // Left turn: right side forward
        ledcWrite(B2_RPWM, 0); ledcWrite(B2_LPWM, SPEED);
        Serial.println("[CMD] TURN LEFT"); client.println("[ESP2] TURN LEFT");
        break;
      case 'D': case 'd':
        // Right turn: right side backward
        ledcWrite(B2_RPWM, SPEED); ledcWrite(B2_LPWM, 0);
        Serial.println("[CMD] TURN RIGHT"); client.println("[ESP2] TURN RIGHT");
        break;
      case 'X': case 'x': case ' ':
        stopMotors();
        Serial.println("[CMD] STOP"); client.println("[ESP2] STOP");
        break;
      case '\n': case '\r': break;
      default:
        Serial.print("[WARN] Unknown: "); Serial.println(cmd);
    }
  }
}
```

### ⚠️ The Polarity Inversion — Key Concept

This is the most important design decision in ESP2's code. The physical right-side motors (M2, M4) are mounted facing the opposite direction from the left-side motors. This means if you send the same PWM pattern to both sides, the robot would spin in circles instead of going straight.

**Solution:** The RPWM and LPWM signals are **swapped** for right-side forward motion.

| Command | ESP1 Left Side | ESP2 Right Side (after swap) | Robot Movement |
|---------|---------------|------------------------------|----------------|
| `W` Forward | RPWM=255, LPWM=0 | RPWM=0, LPWM=255 | Both sides forward — robot goes straight |
| `S` Backward | RPWM=0, LPWM=255 | RPWM=255, LPWM=0 | Both sides backward — robot goes straight back |
| `A` Turn Left | RPWM=0, LPWM=255 (left reverse) | RPWM=0, LPWM=255 (right forward) | Left reverses, right goes forward → robot pivots left |
| `D` Turn Right | RPWM=255, LPWM=0 (left forward) | RPWM=255, LPWM=0 (right reverse) | Left goes forward, right reverses → robot pivots right |
| `X` Stop | 0, 0 | 0, 0 | All motors stop |

**Visual explanation:**
```
FORWARD (W):
  Left Side (ESP1):  [M1,M3] ←← (RPWM=255)   Robot moves ↑
  Right Side (ESP2): [M2,M4] →→ (LPWM=255)   Robot moves ↑
  Both rotate INWARD toward the centre → straight forward

BACKWARD (S):
  Left Side (ESP1):  [M1,M3] →→ (LPWM=255)   Robot moves ↓
  Right Side (ESP2): [M2,M4] ←← (RPWM=255)   Robot moves ↓

TURN LEFT (A) — Tank Turn:
  Left Side (ESP1):  [M1,M3] →→ backward
  Right Side (ESP2): [M2,M4] →→ forward
  Robot pivots counterclockwise

TURN RIGHT (D) — Tank Turn:
  Left Side (ESP1):  [M1,M3] ←← forward
  Right Side (ESP2): [M2,M4] ←← backward
  Robot pivots clockwise
```

---

### Section 7 — `stopMotors()` Function

```cpp
void stopMotors() {
  ledcWrite(B2_RPWM, 0);
  ledcWrite(B2_LPWM, 0);
}
```

> **Note:** In ESP2's file, `stopMotors()` is defined **after** `loop()` — this is valid in C++ (Arduino .ino files) as the Arduino build system generates function prototypes automatically.

Sets both PWM outputs to 0, stopping the right-side motors.

---

## 🔄 Full Execution Flow (Summary)

```
Power ON → setup() runs once
  → Serial debug starts
  → Motor PWM initialized on GPIO 18, 19 (motors off)
  → Wi-Fi connects (prints IP to Serial)
  → TCP server starts on port 8080 (no-delay enabled)
  → Waits for Python connection

loop() runs continuously (forever):
  ┌──────────────────────────────────────────────────────────┐
  │ 1. Check if Python is connected                          │
  │    → If disconnected: stop old socket, stop motors       │
  │    → Accept new connection if available                  │
  │    → On connect: send "[ESP2] B2 Right side ready"       │
  │ 2. If command received from Python:                      │
  │    → Execute POLARITY-CORRECTED motor command            │
  │    → Echo command label back to Python                   │
  │    → Log to Serial Monitor                               │
  └──────────────────────────────────────────────────────────┘
```

---

## 📊 ESP1 vs ESP2 Comparison

| Feature | ESP1 | ESP2 |
|---------|------|------|
| Motor side | Left (M1, M3) | Right (M2, M4) |
| Motor driver | BTS7960 #1 | BTS7960 #2 |
| PWM pins | GPIO 25 (RPWM), GPIO 27 (LPWM) | GPIO 18 (RPWM), GPIO 19 (LPWM) |
| Sonar sensors | Yes — all 3 sensors | No |
| Encoder pins wired | GPIO 34, 36 | GPIO 32, 39 |
| Motor polarity swap | No (natural) | Yes — RPWM/LPWM swapped for forward |
| setNoDelay | Not set | `server.setNoDelay(true)` |
| Disconnect handling | Implicit (waits for new accept) | Explicit `client.stop()` + `stopMotors()` |
| Sonar streaming | Every 100ms to Python | No |
| Code size | ~160 lines | ~85 lines |

---

## 🛠️ How to Upload This Code to ESP32 #2

1. Connect ESP32 #2 to laptop with a **USB data cable** (Type-C)
2. Open Arduino IDE
3. Open file: `2EC/2EC.ino`
4. Go to **Tools → Board** → select **ALKS ESP32** (or ESP32 Dev Module)
5. Go to **Tools → Port** → select the correct COM port (check Device Manager if unsure)
6. Update Wi-Fi credentials if necessary:
   ```cpp
   const char* ssid     = "YourWiFiName";
   const char* password = "YourPassword";
   ```
7. Click **Upload**
8. After upload, open Serial Monitor (Tools → Serial Monitor, baud: **115200**)
9. Press RESET on ESP32 — IP address will be printed after Wi-Fi connects

> ⚠️ **Important:** Make sure the correct COM port is selected. If you have both ESPs connected simultaneously, they will appear as separate COM ports. Flash ESP1 first with its file, then switch to the ESP2 COM port and flash.

---

## ⚠️ Known Issues / Limitations

| Issue | Details |
|-------|---------|
| No encoder code | Encoder pins (GPIO 32, 39) are wired but not read in this firmware |
| Polarity must match physical wiring | If motors are rewired differently, the polarity swap in code must be adjusted accordingly |
| Only one Python client at a time | TCP server accepts one connection — Python server manages both ESPs separately |
| Wi-Fi credentials hardcoded | Changing Wi-Fi requires re-flashing firmware |
| Motors stop on disconnect | This is intentional safety behavior when Python connection drops |

---

## 💡 Tips for Debugging ESP2

- If the robot turns instead of going straight → polarity swap issue. Check that motors M2/M4 are physically mounted in the same orientation as described
- If right motors don't respond → verify B2 R_EN and L_EN are pulled HIGH via the 5V logic supply
- If ESP2 won't connect to Python → check the IP entered in the web dashboard matches what's shown in Serial Monitor
- If ESP2 keeps disconnecting → check Wi-Fi signal strength and power supply stability of the ESP board

---

*Document 4 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
