# 02 — Hardware Connections & Wiring Guide

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Audience:** Technicians, hardware engineers, students assembling/maintaining the robot

---

## 🔩 Component List

| # | Component | Model / Spec | Qty |
|---|-----------|-------------|-----|
| 1 | Microcontroller | ESP32 (USB Type-C variant) | 2 |
| 2 | Motor Driver | BTS7960 (43A H-Bridge) | 2 |
| 3 | Ultrasonic Sensor | HC-SR04 | 3 |
| 4 | DC Motor (with Encoder) | Standard encoder DC gearmotor | 4 |
| 5 | LiPo Battery | High-current pack for motors | 1 |
| 6 | Buck Converter | Output: 5V regulated | 1 |
| 7 | Battery Pack (5V) | For encoder VCC supply | 1 |
| 8 | USB Power Bank / Charger | For ESP32 power during operation | 2 |
| 9 | Jumper Wires | Male-to-Female, Male-to-Male | Many |
| 10 | USB Type-C Cable (Data) | C-to-C or A-to-C (must be data cable) | 2 |

---

## 🗺️ System-Level Wiring Diagram (Block Diagram)

```
                          ┌─────────────────────────────────────┐
                          │           LiPo Battery Pack          │
                          │   B+ ────────────────────────────── │
                          │   B– ────────────────────────────── │
                          └──────┬─────────────────────┬────────┘
                                 │                     │
                          ┌──────▼──────┐       ┌──────▼──────┐
                          │  BTS7960 B1 │       │  BTS7960 B2 │
                          │ (Left Side) │       │ (Right Side)│
                          │  B+  B– VCC │       │  B+  B– VCC │
                          └──┬───┬──┬──┘       └──┬───┬──┬───┘
                             │   │  │              │   │  │
                           M+  M–  5V            M+  M–  5V
                             │   │                  │   │
                    ┌────────┘   └────────┐ ┌───────┘   └────────┐
                    │                     │ │                     │
               M1 (FL)                M3(RL) M2(FR)            M4(RR)
             (parallel on B1)              (parallel on B2)

    ┌────────────────────────────────────────────────────────────────────┐
    │                         Buck Converter                             │
    │   Input: LiPo B+/B–   →   Output: 5V regulated                    │
    │   Powers: B1 VCC, B1 R_EN, B1 L_EN, B2 VCC, B2 R_EN, B2 L_EN    │
    │           ESP32 #1 GND rail, ESP32 #2 GND rail                    │
    └────────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────┐    ┌──────────────────────────────┐
    │        ESP32 #1            │    │          ESP32 #2             │
    │   GPIO 25 → B1 RPWM       │    │   GPIO 18 → B2 RPWM          │
    │   GPIO 27 → B1 LPWM       │    │   GPIO 19 → B2 LPWM          │
    │   GPIO 32 → S1 TRIG       │    │   GPIO 32 → M2 Encoder A     │
    │   GPIO 33 → S1 ECHO       │    │   GPIO 39 → M4 Encoder A     │
    │   GPIO 14 → S2 TRIG       │    │                              │
    │   GPIO 16 → S2 ECHO       │    │   Powered by:                │
    │   GPIO 13 → S3 TRIG       │    │   Raspberry Pi charger (USB) │
    │   GPIO 17 → S3 ECHO       │    └──────────────────────────────┘
    │   GPIO 34 → M1 Encoder A  │
    │   GPIO 36 → M3 Encoder A  │
    │   Powered by:             │
    │   Samsung charger (USB)   │
    └────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │                    HC-SR04 Sonars                        │
    │   S1 (Left  45°): VCC=5V, GND, TRIG→GPIO32, ECHO→GPIO33│
    │   S2 (Front  0°): VCC=5V, GND, TRIG→GPIO14, ECHO→GPIO16│
    │   S3 (Right 45°): VCC=5V, GND, TRIG→GPIO13, ECHO→GPIO17│
    └─────────────────────────────────────────────────────────┘
```

---

## ⚡ Power Connections

| From | To | Notes |
|------|----|-------|
| LiPo B+ | BTS7960 B1 B+ | Motor power for left side |
| LiPo B+ | BTS7960 B2 B+ | Motor power for right side |
| LiPo B– | BTS7960 B1 B– | Common ground for left driver |
| LiPo B– | BTS7960 B2 B– | Common ground for right driver |
| Buck Converter 5V OUT | B1 VCC, B1 R_EN, B1 L_EN | Logic enable for B1 |
| Buck Converter 5V OUT | B2 VCC, B2 R_EN, B2 L_EN | Logic enable for B2 |
| Buck Converter GND | B1 GND, B2 GND, ESP32 #1 GND, ESP32 #2 GND | Common GND rail |
| Battery Pack 5V | Encoder VCC of all 4 motors | Encoder power supply |
| Battery Pack GND | Common GND rail | All grounds tied together |
| USB Power Bank #1 | ESP32 #1 (USB-C) | Using Samsung charger cable |
| USB Power Bank #2 | ESP32 #2 (USB-C) | Using Raspberry Pi charger cable |

> ⚠️ **Important:** Motor power (LiPo) and ESP32 power (USB banks) are SEPARATE. You can turn off motor power during code testing — the ESPs will still run on USB power.

---

## 🤖 ESP32 #1 — GPIO Pin Map (Left Side + All Sonars)

| GPIO Pin | Direction | Connected To | Function |
|----------|-----------|-------------|---------|
| **25** | OUTPUT | B1 RPWM | Left motor driver — Forward PWM |
| **27** | OUTPUT | B1 LPWM | Left motor driver — Reverse PWM |
| **32** | OUTPUT | S1 TRIG | Sonar 1 (Left 45°) — Trigger |
| **33** | INPUT | S1 ECHO | Sonar 1 (Left 45°) — Echo |
| **14** | OUTPUT | S2 TRIG | Sonar 2 (Front 0°) — Trigger |
| **16** | INPUT | S2 ECHO | Sonar 2 (Front 0°) — Echo |
| **13** | OUTPUT | S3 TRIG | Sonar 3 (Right 45°) — Trigger |
| **17** | INPUT | S3 ECHO | Sonar 3 (Right 45°) — Echo |
| **34** | INPUT | M1 Encoder A | Front-Left Motor encoder (not yet active) |
| **36** | INPUT | M3 Encoder A | Rear-Left Motor encoder (not yet active) |
| GND | — | Common GND rail | Ground |
| 5V/3.3V | — | Sonar VCC | Sensor power |

---

## 🤖 ESP32 #2 — GPIO Pin Map (Right Side Motors Only)

| GPIO Pin | Direction | Connected To | Function |
|----------|-----------|-------------|---------|
| **18** | OUTPUT | B2 RPWM | Right motor driver — Forward PWM |
| **19** | OUTPUT | B2 LPWM | Right motor driver — Reverse PWM |
| **32** | INPUT | M2 Encoder A | Front-Right Motor encoder (not yet active) |
| **39** | INPUT | M4 Encoder A | Rear-Right Motor encoder (not yet active) |
| GND | — | Common GND rail | Ground |

---

## 🔧 Motor Connections

| Motor Label | Physical Position | Connected To | Direction Role |
|------------|-------------------|-------------|----------------|
| M1 | Front-Left (FL) | B1 M+ and M– | Left side motors |
| M3 | Rear-Left (RL) | B1 M+ and M– (parallel with M1) | Left side motors |
| M2 | Front-Right (FR) | B2 M+ and M– | Right side motors |
| M4 | Rear-Right (RR) | B2 M+ and M– (parallel with M2) | Right side motors |

> **Note:** M1 and M3 are wired in **parallel** to B1's motor output terminals. Similarly M2 and M4 are wired in **parallel** to B2. Both motors on each side always move together.

---

## 📡 Ultrasonic Sensor (HC-SR04) Connections

All 3 sensors are connected to **ESP32 #1 only**.

| Sensor | Position | Angle | VCC | GND | TRIG (GPIO) | ECHO (GPIO) |
|--------|----------|-------|-----|-----|-------------|-------------|
| S1 | Left | 45° diagonal front-left | 5V | GND | 32 | 33 |
| S2 | Center | 0° straight front | 5V | GND | 14 | 16 |
| S3 | Right | 45° diagonal front-right | 5V | GND | 13 | 17 |

> **⚠️ Known Issue:** HC-SR04 ECHO pin outputs 5V, but ESP32 GPIO is 3.3V tolerant maximum. A voltage divider (resistor network) should be placed on the ECHO line. **This has NOT been implemented yet** and is flagged as a Next Step.

### Recommended Voltage Divider (Future Fix)
```
Sonar ECHO (5V) ──── R1 (1kΩ) ──┬──── ESP32 GPIO (3.3V safe)
                                  │
                                 R2 (2kΩ)
                                  │
                                 GND
```

---

## 🔌 Encoder Connections (Wired but NOT Active in Code)

| Motor | VCC | GND | Encoder A Pin | Encoder B Pin | Index Pin |
|-------|-----|-----|---------------|---------------|-----------|
| M1 (FL) | Battery 5V | Common GND | ESP32 #1 GPIO 34 | **Not connected** | **Not connected** |
| M3 (RL) | Battery 5V | Common GND | ESP32 #1 GPIO 36 | **Not connected** | **Not connected** |
| M2 (FR) | Battery 5V | Common GND | ESP32 #2 GPIO 32 | **Not connected** | **Not connected** |
| M4 (RR) | Battery 5V | Common GND | ESP32 #2 GPIO 39 | **Not connected** | **Not connected** |

> **Note:** Only the A channel is wired. B channel and Index are left disconnected. Encoder integration into the firmware is a **Next Step** — requires resistor signal conditioning on encoder signal lines too.

---

## 🖥️ ESP32 Power Source (During Operation)

| ESP32 | Power Source | Cable Type |
|-------|-------------|------------|
| ESP32 #1 | Samsung USB charger / Power bank | USB-C |
| ESP32 #2 | Raspberry Pi USB charger / Power bank | USB-C |

> The power banks can be physically attached to the underside of the robot chassis using double-sided tape, velcro, or cable ties for a cordless setup.

---

## 🖥️ ESP32 Power Source (During Code Upload / Development)

| ESP32 | Power Source | Cable Type |
|-------|-------------|------------|
| ESP32 #1 | Laptop USB port | USB-C (must be DATA cable, not charge-only) |
| ESP32 #2 | Laptop USB port | USB-C (must be DATA cable, not charge-only) |

> ⚠️ **Critical:** Some USB-C cables are charge-only and will NOT communicate data. Always use cables labelled "data" or test them. The code will not upload if the cable is charge-only.

---

## 🔄 BTS7960 Motor Driver Pin Reference

| BTS7960 Pin | Function | Connected To |
|-------------|---------|-------------|
| B+ | Battery positive | LiPo B+ |
| B– | Battery negative | LiPo B– (GND) |
| VCC | Logic supply (5V) | Buck converter 5V |
| GND | Logic ground | Common GND rail |
| R_EN | Right enable (active HIGH) | Buck converter 5V (always enabled) |
| L_EN | Left enable (active HIGH) | Buck converter 5V (always enabled) |
| RPWM | Right PWM (forward) | ESP32 GPIO (25 for B1, 18 for B2) |
| LPWM | Left PWM (reverse) | ESP32 GPIO (27 for B1, 19 for B2) |
| M+ | Motor positive output | Motor terminals (parallel M1+M3 or M2+M4) |
| M– | Motor negative output | Motor terminals (parallel M1+M3 or M2+M4) |

### BTS7960 Direction Logic

| RPWM | LPWM | Motor Action |
|------|------|-------------|
| PWM (>0) | 0 | Forward |
| 0 | PWM (>0) | Backward / Reverse |
| 0 | 0 | Stop (Coast) |
| PWM | PWM | AVOID — Short circuit risk |

> **Polarity note:** Due to how motors M2/M4 are physically mounted (mirrored), the firmware for ESP32 #2 **swaps RPWM and LPWM** signals in software to achieve correct forward direction without rewiring.

---

## 📶 Wi-Fi / Network Connections

| Device | Network | Band | Notes |
|--------|---------|------|-------|
| ESP32 #1 | Same Wi-Fi as laptop | **2.4 GHz ONLY** | Hardcoded SSID & password in firmware |
| ESP32 #2 | Same Wi-Fi as laptop | **2.4 GHz ONLY** | Hardcoded SSID & password in firmware |
| Laptop | Same Wi-Fi | 2.4 or 5 GHz | Hosts Python server on port 5000 |
| Phone/iPad | Same Wi-Fi | 2.4 or 5 GHz | Opens dashboard in browser |

> ⚠️ **5 GHz will NOT work for ESPs.** If your router/hotspot only broadcasts 5 GHz, the ESP32 will not connect. Use a 2.4 GHz hotspot or a router that broadcasts both bands separately.

---

## 🔍 How to Find the ESP32 IP Address

**Method 1 — Arduino Serial Monitor:**
1. Connect ESP32 via USB data cable to laptop
2. Open Arduino IDE → Tools → Serial Monitor → Baud rate: **115200**
3. Press the RESET button on the ESP32
4. Watch the output — the IP address will be printed after connecting to Wi-Fi

**Method 2 — Router Admin Panel:**
1. Connect to the same Wi-Fi on laptop
2. Open browser → go to your router's gateway IP (usually `192.168.1.1` or `192.168.0.1`)
3. Log in (usually admin/admin)
4. Look at connected devices list — find entries starting with "Espressif"

**Method 3 — Wi-Fi app on phone:**
1. Some phones/apps (e.g., Fing) can scan the network and list all connected devices with IPs

---

## ⚠️ Safety & Maintenance Notes

| Concern | Action Required |
|---------|----------------|
| ESP32 getting hot | Immediately disconnect power — may indicate short circuit or overcurrent |
| BTS7960 cutout | Wait a few minutes, then reset the respective ESP32 manually (press RESET button) |
| Jumper wires loose | Check and reseat; for permanent fix, solder or use a custom PCB |
| Sonar readings erratic | Expected — voltage divider not installed; plan to add resistor divider on ECHO pins |
| Motor not responding | Check LiPo battery charge and connections; check BTS7960 enable signals (R_EN, L_EN must be HIGH) |
| ESP won't connect to Wi-Fi | Verify SSID/password in firmware; ensure 2.4 GHz band; check router/hotspot settings |

---

## 🔧 Periodic Maintenance Checklist

- [ ] Check all jumper wire connections are seated firmly
- [ ] Verify motor terminal screws on BTS7960 are tight
- [ ] Test all 3 sonar sensors respond (check Drive page sonar display)
- [ ] Confirm both ESPs connect to Wi-Fi after reset
- [ ] Check power bank charge levels before long operation
- [ ] Inspect motor cables for wear or strain

---

*Document 2 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
