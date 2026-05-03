

***

## ⚡ Power

| From | To |
| :-- | :-- |
| LiPo B+ | B1 B+ and B2 B+ |
| LiPo B– | B1 B– and B2 B– |
| Buck 5V | B1 VCC, B1 R_EN, B1 L_EN, B2 VCC, B2 R_EN, B2 L_EN |
| Buck GND | B1 GND, B2 GND, ESP32\#1 GND, ESP32\#2 GND |
| Battery pack 5V | Encoder + of all 4 motors |
| Battery pack GND | Same common GND rail |


***

## 🤖 ESP32 \#1 — Left Side

| GPIO | Connected To |
| :-- | :-- |
| 25 | B1 RPWM |
| 27 | B1 LPWM |
| 32 | S1 TRIG (Left sonar) |
| 33 | S1 ECHO (Left sonar) |
| 14 | S2 TRIG (Front sonar) |
| 16 | S2 ECHO (Front sonar) |
| 13 | S3 TRIG (Right sonar) |
| 17 | S3 ECHO (Right sonar) |
| 34 | M1 Encoder A |
| 36 | M3 Encoder A |


***

## 🤖 ESP32 \#2 — Right Side

| GPIO | Connected To |
| :-- | :-- |
| 18 | B2 RPWM |
| 19 | B2 LPWM |
| 32 | M2 Encoder A |
| 39 | M4 Encoder A |


***

## 🔧 Motors

| Motor | Connected To |
| :-- | :-- |
| M1 Front Left + M3 Rear Left | B1 M+ and M– (parallel) |
| M2 Front Right + M4 Rear Right | B2 M+ and M– (parallel) |


***

## 🔌 Encoders

| Motor | VCC | GND | A Pin | B Pin |
| :-- | :-- | :-- | :-- | :-- |
| M1 | Battery 5V | Common GND | ESP32\#1 GPIO 34 | **Not connected** |
| M3 | Battery 5V | Common GND | ESP32\#1 GPIO 36 | **Not connected** |
| M2 | Battery 5V | Common GND | ESP32\#2 GPIO 32 | **Not connected** |
| M4 | Battery 5V | Common GND | ESP32\#2 GPIO 39 | **Not connected** |
| All Index pins | — | — | **Not connected** | — |


***

## 🖥️ ESP32 Power

| ESP32 | Power |
| :-- | :-- |
| ESP32 \#1 | Samsung charger via USB |
| ESP32 \#2 | Raspberry Pi charger via USB |

