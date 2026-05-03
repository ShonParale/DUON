# 03 — ESP1 Code Explanation

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**File Covered:** `1EC/1EC.ino`
**Target Hardware:** ESP32 #1 (Left Side — B1 Motor Driver + All 3 Sonar Sensors)

---

## 📌 What Does ESP1 Do?

ESP32 #1 is the **primary controller** of the DUON robot. It is responsible for:

1. **Connecting to the Wi-Fi network** and waiting for the Python server to connect
2. **Receiving motor commands** from the Python server (W/A/S/D/X)
3. **Driving the left-side motors** (M1 Front-Left and M3 Rear-Left) via BTS7960 #1
4. **Reading all 3 ultrasonic (sonar) sensors** in a non-blocking manner
5. **Streaming sonar data** back to the Python server every 100 ms

---

## 📄 Full Code with Line-by-Line Explanation

### Section 1 — File Header & Library Import

```cpp
// ============================================================
//  ESP32 #1 - B1 LEFT SIDE (M1+M3) + ALL 3 SONARS
//  MANUAL DRIVE: UNCHANGED (W/A/S/D/X/SPACE)
//  NEW: Non-blocking sonar reads, streamed as [SONAR]L:xx,F:xx,R:xx
// ============================================================
#include <WiFi.h>
```

- The comment block describes what this file does at a glance.
- `#include <WiFi.h>` imports the ESP32 WiFi library, which allows connecting to Wi-Fi and creating a TCP server — this is a built-in library in the Arduino ESP32 package.

---

### Section 2 — Configuration Constants

```cpp
const char* ssid     = "Airtel_ShonPraleWiFi";
const char* password = "1#Gswifi05s";
const int   PORT     = 8080;
```

- `ssid` and `password` are the Wi-Fi network credentials. **These must be updated** if deploying on a different Wi-Fi network.
- `PORT = 8080` is the TCP port on which ESP1 will listen for incoming connections from the Python server.
- Both ESP1 and ESP2 use the **same port number (8080)** but different IP addresses (one per device).

---

### Section 3 — BTS7960 Motor Driver Pins

```cpp
const int B1_RPWM = 25;
const int B1_LPWM = 27;
const int PWM_FREQ = 5000, PWM_RES = 8, SPEED = 255;
```

| Constant | Value | Meaning |
|----------|-------|---------|
| `B1_RPWM` | GPIO 25 | PWM pin for Forward direction on BTS7960 #1 |
| `B1_LPWM` | GPIO 27 | PWM pin for Reverse/Backward direction on BTS7960 #1 |
| `PWM_FREQ` | 5000 Hz | PWM signal frequency (5 kHz — suitable for motor drivers) |
| `PWM_RES` | 8 bits | PWM resolution — 8 bits means values 0–255 |
| `SPEED` | 255 | Full speed (100%) — maximum value for 8-bit PWM |

The ESP32 uses its `ledcWrite()` hardware PWM to output signals on these pins.

---

### Section 4 — Sonar Sensor Pin Definitions

```cpp
const int S1_TRIG = 32, S1_ECHO = 33;  // Left  (45 deg diagonal)
const int S2_TRIG = 14, S2_ECHO = 16;  // Front (straight)
const int S3_TRIG = 13, S3_ECHO = 17;  // Right (45 deg diagonal)
```

Three HC-SR04 sensors are connected to ESP1:

| Sensor | TRIG GPIO | ECHO GPIO | Physical Position | Angle |
|--------|-----------|-----------|-------------------|-------|
| S1 | 32 | 33 | Left side | 45° diagonal front-left |
| S2 | 14 | 16 | Center | Straight ahead (0°) |
| S3 | 13 | 17 | Right side | 45° diagonal front-right |

All three are read sequentially using a **non-blocking state machine** (explained below).

---

### Section 5 — TCP Server and Client Objects

```cpp
WiFiServer server(PORT);
WiFiClient client;
```

- `WiFiServer server(PORT)` — creates a TCP server listening on port 8080. The Python program will connect as a client.
- `WiFiClient client` — holds the active connection from the Python server. Only one client at a time is supported.

---

### Section 6 — Non-Blocking Sonar State Machine Variables

```cpp
const int TRIG_PINS[3] = {S1_TRIG, S2_TRIG, S3_TRIG};
const int ECHO_PINS[3] = {S1_ECHO, S2_ECHO, S3_ECHO};

int     sonarIdx       = 0;
bool    trigSent       = false;
unsigned long trigTime = 0;
float   dist_cm[3]     = {0, 0, 0};  // L, F, R

unsigned long lastSonarReport = 0;
const unsigned long SONAR_INTERVAL = 100; // ms between reports to Python
```

| Variable | Purpose |
|----------|---------|
| `TRIG_PINS[3]` | Array of trigger pin numbers for all 3 sensors |
| `ECHO_PINS[3]` | Array of echo pin numbers for all 3 sensors |
| `sonarIdx` | Which sensor (0=Left, 1=Front, 2=Right) is currently being measured |
| `trigSent` | Boolean — has a trigger pulse been fired for the current sensor? |
| `trigTime` | Microsecond timestamp of when the trigger was sent |
| `dist_cm[3]` | Stores the latest measured distance (cm) for each of the 3 sensors |
| `lastSonarReport` | Millisecond timestamp of last sonar data packet sent to Python |
| `SONAR_INTERVAL` | How often (in ms) to send sonar data to Python — currently 100ms (10 times/sec) |

> **Why non-blocking?** If we used `pulseIn()` (the simple blocking method), the ESP32 would be stuck waiting for an echo — possibly for up to 25ms per sensor. With 3 sensors, that's 75ms of blocking per cycle, causing laggy motor response. The state machine approach allows sonar reading to happen in the background without freezing motor command handling.

---

### Section 7 — `triggerSonar()` Function

```cpp
void triggerSonar(int idx) {
  digitalWrite(TRIG_PINS[idx], LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PINS[idx], HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PINS[idx], LOW);
  trigTime = micros();
  trigSent = true;
}
```

This follows the **HC-SR04 trigger sequence**:
1. Pull TRIG LOW for 2µs (ensure clean start)
2. Pull TRIG HIGH for 10µs (this fires the ultrasonic burst)
3. Pull TRIG LOW again
4. Record current microsecond time as `trigTime`
5. Set `trigSent = true` to signal that we're now waiting for the echo

---

### Section 8 — `readEcho()` Function

```cpp
float readEcho(int idx) {
  unsigned long elapsed = micros() - trigTime;
  int pin = ECHO_PINS[idx];
  if (digitalRead(pin) == LOW) {
    if (elapsed > 25000) return -1; // timeout = no object in range
    return 0;                       // still waiting for echo
  }
  unsigned long pulseStart = micros();
  while (digitalRead(pin) == HIGH) {
    if (micros() - pulseStart > 25000) break;
  }
  unsigned long pulseEnd = micros();
  float cm = (pulseEnd - pulseStart) / 58.0;
  return (cm > 400) ? 400 : cm;
}
```

**What this does:**
1. Checks if the ECHO pin is still LOW (echo not received yet)
2. If elapsed time > 25,000 µs (25ms) and still no echo → return `-1` (timeout, no object detected — treated as 400cm/max range)
3. If ECHO is still LOW but timeout not reached → return `0` (still waiting — loop again next iteration)
4. Once ECHO goes HIGH, measures how long it stays HIGH (the pulse width)
5. Converts pulse width to distance: `cm = pulse_duration_µs / 58.0`
   - This formula comes from: speed of sound ≈ 343 m/s → round trip / 2 → 58 µs per cm
6. Caps the maximum at 400 cm (valid range for HC-SR04)

**Return values:**
| Return | Meaning |
|--------|---------|
| `> 0` | Valid distance in cm |
| `0` | Echo not yet received — wait and check again |
| `-1` | Timeout — object too far or out of range |

---

### Section 9 — `stopMotors()` Function

```cpp
void stopMotors() {
  ledcWrite(B1_RPWM, 0);
  ledcWrite(B1_LPWM, 0);
}
```

Sets both PWM channels to 0 — this sends no signal to the motor driver, causing the motors to coast to a stop (not a hard brake).

---

### Section 10 — `setup()` Function

```cpp
void setup() {
  Serial.begin(115200);
  Serial.println("\n[BOOT] ESP32 #1 - B1 LEFT SIDE + SONARS");

  // Motor PWM setup
  ledcAttach(B1_RPWM, PWM_FREQ, PWM_RES);
  ledcAttach(B1_LPWM, PWM_FREQ, PWM_RES);
  stopMotors();

  // Sonar pin setup
  for (int i = 0; i < 3; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    pinMode(ECHO_PINS[i], INPUT);
    digitalWrite(TRIG_PINS[i], LOW);
  }

  WiFi.begin(ssid, password);
  Serial.print("[WIFI] Connecting");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\n[WIFI] Connected!");
  Serial.print("[WIFI] ESP32 #1 IP: ");
  Serial.println(WiFi.localIP());

  server.begin();
  Serial.println("[READY] Waiting for Python...");
}
```

**Step-by-step:**
1. **Serial.begin(115200)** — starts serial communication at 115200 baud for debugging via Arduino IDE Serial Monitor
2. **ledcAttach()** — attaches GPIO pins 25 and 27 to the ESP32 hardware PWM controller with 5kHz frequency and 8-bit resolution
3. **stopMotors()** — ensures motors are off on startup (safety)
4. **Sonar pin setup loop** — sets TRIG pins as OUTPUT (we send the pulse) and ECHO pins as INPUT (we receive the pulse); initializes TRIG pins LOW
5. **WiFi.begin()** — starts Wi-Fi connection using stored credentials; blocks in a while loop printing dots until connected
6. **WiFi.localIP()** — prints the assigned IP address to Serial Monitor (useful for finding the ESP's IP)
7. **server.begin()** — starts the TCP server on port 8080, ready to accept a Python connection

---

### Section 11 — `loop()` Function — Part 1: Client Connection Handling

```cpp
void loop() {
  // 1. Handle client connection
  if (!client || !client.connected()) {
    client = server.accept();
    if (client) {
      Serial.println("[CLIENT] Python connected!");
      client.println("[ESP1] B1 Left side ready");
    }
  }
```

- Checks if there is an active client connected; if not, waits for a new connection
- `server.accept()` — non-blocking; returns a valid client object if a new connection arrived, otherwise returns nothing
- When Python connects, ESP1 sends the greeting message `[ESP1] B1 Left side ready`

---

### Section 11 — `loop()` Function — Part 2: Motor Command Handler

```cpp
  if (client && client.connected() && client.available()) {
    char cmd = client.read();
    switch (cmd) {
      case 'W': case 'w':
        ledcWrite(B1_RPWM, SPEED); ledcWrite(B1_LPWM, 0);
        break;
      case 'S': case 's':
        ledcWrite(B1_RPWM, 0); ledcWrite(B1_LPWM, SPEED);
        break;
      case 'A': case 'a':
        ledcWrite(B1_RPWM, 0); ledcWrite(B1_LPWM, SPEED);
        break;
      case 'D': case 'd':
        ledcWrite(B1_RPWM, SPEED); ledcWrite(B1_LPWM, 0);
        break;
      case 'X': case 'x': case ' ':
        stopMotors();
        break;
      case '\n': case '\r': break;
      default:
        Serial.print("[WARN] Unknown: "); Serial.println(cmd);
    }
  }
```

**Command table for Left Motors (B1):**

| Command | RPWM | LPWM | Left Motor Action |
|---------|------|------|-------------------|
| W (Forward) | 255 | 0 | Spin forward |
| S (Backward) | 0 | 255 | Spin backward |
| A (Turn Left) | 0 | 255 | Left motors backward (tank turn left) |
| D (Turn Right) | 255 | 0 | Left motors forward (tank turn right) |
| X / Space (Stop) | 0 | 0 | Motors off |

> **Tank steering explanation:** To turn left, the left motors reverse while the right motors (on ESP2) go forward — this pivots the robot on its own axis. To turn right, it's the opposite.

---

### Section 11 — `loop()` Function — Part 3: Non-Blocking Sonar Cycling

```cpp
  if (!trigSent) {
    triggerSonar(sonarIdx);
  } else {
    float result = readEcho(sonarIdx);
    if (result > 0 || result == -1) {
      dist_cm[sonarIdx] = (result == -1) ? 400 : result;
      trigSent = false;
      sonarIdx = (sonarIdx + 1) % 3;
    }
    // result == 0 means echo not arrived yet, loop continues
  }
```

**State machine flow:**
```
[trigSent = false] → triggerSonar(sonarIdx)   → [trigSent = true]
                                                        ↓
                                              readEcho(sonarIdx)
                                                        ↓
                                          ┌─────────────────────────┐
                                          │ result > 0 (valid)      │→ store in dist_cm
                                          │ result == -1 (timeout)  │→ store 400cm
                                          │ result == 0 (waiting)   │→ loop again
                                          └─────────────────────────┘
                                              ↓ (when complete)
                                          sonarIdx = (sonarIdx+1) % 3
                                          (moves to next sensor: 0→1→2→0→...)
```

This cycles through all 3 sensors continuously, storing the latest distance in `dist_cm[0]`, `dist_cm[1]`, `dist_cm[2]`.

---

### Section 11 — `loop()` Function — Part 4: Sonar Data Streaming

```cpp
  if (client && client.connected()) {
    unsigned long now = millis();
    if (now - lastSonarReport >= SONAR_INTERVAL) {
      lastSonarReport = now;
      char buf[48];
      snprintf(buf, sizeof(buf), "[SONAR]L:%.1f,F:%.1f,R:%.1f",
               dist_cm[0], dist_cm[1], dist_cm[2]);
      client.println(buf);
    }
  }
}
```

Every 100ms, sends a formatted packet to the Python server:
```
[SONAR]L:45.2,F:120.5,R:38.7
```

- `L` = Left sonar (S1, 45° angle)
- `F` = Front sonar (S2, straight)
- `R` = Right sonar (S3, 45° angle)
- Values are in centimetres, one decimal place
- Python parses this string and broadcasts the values to all connected browsers via WebSocket

---

## 🔄 Full Execution Flow (Summary)

```
Power ON → setup() runs once
  → Serial debug starts
  → Motor PWM initialized (motors off)
  → Sonar pins configured
  → Wi-Fi connects (prints IP to Serial)
  → TCP server starts on port 8080
  → Waits for Python connection

loop() runs continuously (forever):
  ┌──────────────────────────────────────────────────────────┐
  │ 1. Check if Python is connected — accept if not          │
  │ 2. If command received from Python:                      │
  │    → Execute motor command (W/A/S/D/X)                   │
  │    → Echo command label back to Python                   │
  │ 3. Non-blocking sonar step:                              │
  │    → Fire trigger (if not sent yet) OR read echo         │
  │    → Cycle to next sensor when reading complete          │
  │ 4. Every 100ms: send [SONAR]L:x,F:x,R:x to Python       │
  └──────────────────────────────────────────────────────────┘
```

---

## 🛠️ How to Upload This Code to ESP32 #1

1. Connect ESP32 #1 to laptop with a **USB data cable** (Type-C)
2. Open Arduino IDE
3. Open file: `1EC/1EC.ino`
4. Go to **Tools → Board** → select **ALKS ESP32** (or ESP32 Dev Module)
5. Go to **Tools → Port** → select the COM port that appears (e.g., COM3, COM4)
6. Update Wi-Fi credentials if necessary:
   ```cpp
   const char* ssid     = "YourWiFiName";
   const char* password = "YourPassword";
   ```
7. Click **Upload** (right arrow button)
8. After upload, open Serial Monitor (Tools → Serial Monitor, baud: 115200)
9. Press RESET on the ESP32 — you will see it connect to Wi-Fi and print its IP address

> ⚠️ If Serial Monitor is open in Arduino IDE, close it before launching the Python server (they share the serial port).

---

## ⚠️ Known Issues / Limitations

| Issue | Details |
|-------|---------|
| Sonar readings can fluctuate | HC-SR04 ECHO pin is 5V; ESP32 GPIO is 3.3V max — voltage divider needed |
| No encoder code | Encoder pins (GPIO 34, 36) are wired but not read in this firmware yet |
| Single client only | Only one Python connection supported at a time |
| Wi-Fi credentials hardcoded | Changing Wi-Fi network requires re-flashing the firmware |
| Baud rate mismatch | Serial Monitor must also be at 115200 or output will appear garbled |

---

*Document 3 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
