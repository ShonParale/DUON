# 10 — Future Scope Implementations

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Purpose:** Long-term vision and potential expansions beyond current next steps.

---

## Overview

These are larger-scale upgrades and new capabilities that would transform DUON from a university project into a more capable research or product-grade platform. Each scope item is independent and can be implemented in any order based on interest and resources.

---

## Future Scope 1: 2D LiDAR Integration

**What:** Replace or supplement the 3 HC-SR04 sonars with a 360° rotating 2D LiDAR sensor (e.g., RPLIDAR A1 or YDLIDAR X4).

**Why:**
- LiDAR provides 360° distance data at ~10 Hz vs 3 fixed-angle sonar readings at 10 Hz
- Range: up to 6–12 metres with <1cm accuracy (vs sonar's 4m with ±3cm at best)
- No moving-part noise; more reliable in varying lighting/temperature
- Standard input for professional SLAM algorithms (GMapping, Hector SLAM, Cartographer)

**Integration approach:**
- Connect LiDAR to USB on laptop (or Raspberry Pi when onboard)
- Use Python library `rplidar` or `PyLidar` to read scan data
- Replace sonar heat-map with full 360° point cloud rendered on Mapping canvas
- Feed into SLAM algorithm for real-time map generation with automatic drift correction

**Hardware cost estimate:** RPLIDAR A1 ~$100, YDLIDAR X4 ~$60.

---

## Future Scope 2: 3D LiDAR Integration

**What:** Upgrade to a 3D LiDAR sensor (e.g., Livox MID-360, Ouster OS0) for full volumetric environment mapping.

**Why:**
- Enables 3D obstacle detection (detects objects at different heights)
- Opens possibilities for stair detection, ramp detection, object avoidance in 3D space
- Data usable for 3D map visualisation and point cloud processing

**Complexity:** High — requires significantly more processing power (Raspberry Pi 4 or higher, or a dedicated edge computing module). 3D visualisation needs a 3D canvas renderer (Three.js) replacing the 2D canvas.

---

## Future Scope 3: Camera Vision System

Multiple camera options depending on hardware available:

### Option A — USB Camera (Simplest)

Connect a USB webcam to the laptop or Raspberry Pi.

```python
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
# MJPEG stream to browser via FastAPI endpoint
```

Add a `/stream` HTTP endpoint to web_server.py that serves MJPEG frames. Add a `<img>` tag on the Drive page pointing to this stream.

### Option B — ESP32-CAM

Replace or supplement one ESP32 with an ESP32-CAM module. The camera streams MJPEG over Wi-Fi natively via its own web server. Add the stream URL as an embedded iframe on the Drive page.

**Pros:** No extra laptop processing; wireless.  
**Cons:** Separate IP to manage; moderate resolution only.

### Option C — Raspberry Pi Camera Module

When Raspberry Pi is onboard as the main processor:
- Use `picamera2` Python library
- Stream via FastAPI to browser

### Option D — Phone Camera (Creative Approach)

Mount a smartphone on the robot's front. The phone connects to the same Wi-Fi hotspot. Use a screen mirroring or IP camera app (e.g., DroidCam, IP Webcam) to broadcast the camera as an RTSP or HTTP MJPEG stream. Python or browser reads the stream.

**Pros:** No extra hardware — reuse an old phone.  
**Cons:** Phone must stay in mount position; battery management needed.

---

## Future Scope 4: AI Object Detection & Classification

**What:** Add real-time AI inference on the camera feed for object detection, obstacle classification, or specific task recognition.

**Pipeline:**

```
Camera frame
    ↓
Python (on laptop or Raspberry Pi)
    ↓
AI Model (YOLO, MobileNet SSD, etc.)
    ↓
Detections overlay on video stream
    ↓
Browser shows annotated live feed
```

**Frameworks:**
- `ultralytics` (YOLOv8) — pip installable, runs on CPU and CUDA GPU
- OpenCV DNN module — lighter weight, no GPU required
- TensorFlow Lite — optimised for Raspberry Pi

**Use cases for DUON:**
- Detect people in the robot's path (auto-stop if person detected)
- Identify and label objects in the mapped room
- Read QR codes or ArUco markers placed around the room for localisation correction (eliminates dead-reckoning drift without encoders)

---

## Future Scope 5: Upgrade to Raspberry Pi (Onboard Processor)

**What:** Move the Python server from the laptop to a Raspberry Pi mounted on the robot chassis.

**Benefits:**
- Robot becomes fully self-contained — no laptop needed for operation
- Reduce latency (server is physically on the robot, not communicating over Wi-Fi from a laptop)
- Enable onboard processing for camera and sensor fusion
- Can still be accessed from any device browser

**Hardware needed:**
- Raspberry Pi 4 (2 GB RAM minimum, 4 GB recommended) or Raspberry Pi 5
- MicroSD card (32 GB+)
- Power: Buck converter from robot battery to 5V 3A for Pi

**Software steps:**
1. Install Raspberry Pi OS (Lite or Desktop)
2. Install Python 3 + pip
3. Copy DUON folder to Pi
4. Run `setup.sh` on Pi
5. Configure `start_server.sh` to auto-start on boot (systemd service)
6. Connect Pi to same Wi-Fi as ESPs
7. Access `http://[pi-ip]:5000` from any browser on the network

**Auto-start on boot (systemd):**
```ini
[Unit]
Description=DUON Robot Server
After=network.target

[Service]
WorkingDirectory=/home/pi/DUON
ExecStart=/usr/bin/python3 -m uvicorn web_server:app --host 0.0.0.0 --port 5000
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

---

## Future Scope 6: Predictive Maintenance & Sensor Diagnostics Page

**What:** Add a dedicated dashboard page that monitors the health of all hardware components and predicts potential failures.

**Dashboard features:**
- Motor runtime counter (track hours of use per motor)
- Sonar signal quality graph (detect degrading sensors by tracking noise variance over time)
- ESP32 connection stability log (track number of disconnects per session)
- Motor temperature estimate (derived from current draw if current sensor added)
- Maintenance reminders (e.g., "Jumper wires: check after 5 sessions")
- Battery voltage monitoring (add voltage divider on battery line to ADC pin)

**Implementation:** New page in `index.html` + new `type: "diagnostics"` WebSocket message from Python + periodic hardware health checks in `web_server.py`.

---

## Future Scope 7: Multi-Robot Control

**What:** Extend the DUON architecture to control multiple robots from a single dashboard.

**Concept:**
- Each robot gets a unique identifier (Robot 1, Robot 2, etc.)
- Each robot has its own pair of ESPs and its own Python server (or one Python server manages all)
- Dashboard shows multiple robot panels simultaneously
- Commands can be sent to individual robots or broadcast to all

**Architecture change:** The current single `robot` object in `web_server.py` becomes a dictionary `robots = {"robot1": Robot(), "robot2": Robot()}`. WebSocket commands include a `robot_id` field.

---

## Future Scope 8: Remote Access via Cloudflare Tunnel

**What:** Expose the local DUON server to the public internet without port-forwarding or VPN.

**Status:** Already supported — no code changes needed. This is purely an operational step.

**How:**
1. Install Cloudflare Tunnel: `cloudflared tunnel --url http://localhost:5000`
2. A public HTTPS URL is generated (e.g., `https://random-name.trycloudflare.com`)
3. Share this URL — anyone on the internet can access and control the robot
4. The web dashboard's QR code and URL display will automatically show the public URL if accessed externally

**Considerations:**
- Latency increases (depends on internet speed — typically 100–500ms extra)
- Security: anyone with the URL can control the robot — use with caution in public environments
- For persistent public access: set up a named Cloudflare tunnel with authentication

---

## Future Scope 9: Wireless Battery Monitoring

**What:** Add real-time battery voltage and charge level display on the dashboard.

**Hardware:** Voltage divider (100kΩ + 47kΩ resistors) from battery positive to a free ADC pin on ESP32.

```
Battery B+ ──── R1 (100kΩ) ──┬──── ESP32 ADC pin
                               │
                              R2 (47kΩ)
                               │
                              GND
```

**Firmware addition (ESP1):**
```cpp
int adcVal = analogRead(ADC_PIN);   // 0–4095 (12-bit)
float battV = adcVal * (3.3 / 4095) * ((100 + 47) / 47.0);
// Include in periodic telemetry: "[BATT]V:11.2\n"
```

**Dashboard addition:** Battery icon with percentage, voltage display, low battery warning alert.

---

## Future Scope 10: Voice Control Integration

**What:** Control the robot using voice commands via the browser's Web Speech API.

**Implementation:**
```javascript
const recognition = new webkitSpeechRecognition();
recognition.onresult = (e) => {
  const word = e.results[0][0].transcript.toLowerCase();
  if (word.includes('forward')) send({cmd: 'W'});
  if (word.includes('stop'))    send({cmd: 'X'});
  // etc.
};
```

Requires HTTPS connection (microphone access blocked on HTTP except localhost). Use Cloudflare Tunnel for HTTPS remote access.

---

## Technology Upgrade Path Summary

```
Current State
  2× ESP32 + 3× Sonar + BTS7960 + Laptop
  Wi-Fi control + Manual drive + Basic autonomous mapping
       ↓
Near-Term (Next Steps)
  + Encoder feedback + Voltage dividers + Soldered wiring
  + Accurate dead-reckoning + Stable connections
       ↓
Mid-Term (Future Scope A)
  + 2D LiDAR + Camera
  + Real-time SLAM + Live video feed
       ↓
Mid-Term (Future Scope B)
  + Raspberry Pi onboard + Auto-boot server
  + Fully cordless, laptop-free operation
       ↓
Long-Term (Future Scope C)
  + AI vision + Predictive maintenance
  + Multi-robot + 3D mapping
  + Full autonomous indoor navigation platform
```

---

## Summary Table

| Scope | Effort | Cost | Impact | Prerequisite |
|-------|--------|------|--------|-------------|
| 2D LiDAR | Medium | ~$60–100 | Very High | None |
| Camera (USB) | Low | ~$15–40 | High | None |
| Camera (AI detection) | High | ~$0 (software) | High | Camera first |
| Raspberry Pi onboard | Medium | ~$60–100 | Very High | None |
| Encoder feedback | Medium | ~$0 (hardware exists) | Very High | Signal wiring fix |
| Predictive maintenance page | Medium | ~$0 | Medium | None |
| Remote access (Cloudflare) | Minimal | Free | High | None |
| Battery monitoring | Low | ~$1 (resistors) | Medium | None |
| Voice control | Low | ~$0 | Medium | HTTPS needed |
| Multi-robot | High | Cost of extra robots | High | Architecture redesign |
| 3D LiDAR | Very High | $300+ | Very High | Raspberry Pi first |

---

*Document 10 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
