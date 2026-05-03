# DUON — Dynamic Ultrasonic Operations & Navigations 🤖

Welcome to the **DUON** repository! 

DUON is a 4-wheel drive autonomous mobile robot built with dual ESP32 microcontrollers, a Python FastAPI backend, and a real-time web-based control dashboard. It features autonomous mapping, A* pathfinding, live sonar telemetry, and manual controls accessible from any device on the network.

**Authors:** Shon Parale & Vedant Patel  
**Institution:** SRM Institute of Science & Technology (Semester 6 Minor Project)

---

## 📚 Documentation

**We have prepared extensive, professional documentation for this project.** 

Instead of cluttering this README, **all documentation is located inside the [`Documents/`](./Documents/) folder.** 

Please head over there to find everything you need to understand, build, and run the robot. The documents are numbered for easy reading:

*   **`00` / `01` / `11` / `12`** — Project overviews and deep-dive knowledge transfers.
*   **`13_How_to_Setup_and_Run.md`** — Step-by-step instructions to get the Python server and ESPs running.
*   **`14_How_to_Operate_the_Bot.md`** — Guidelines for driving and mapping.
*   **`02_Hardware_Connections_Wiring_Guide.md`** — Full pinouts and wiring schematics.
*   **`03` / `04` / `05`** — Detailed, line-by-line code explanations for the ESPs and Python backend.
*   **`06_Data_Flow_Communication_Protocol.md`** — WebSocket & TCP message schemas.
*   **`07_Troubleshooting_Known_Issues.md`** — Solutions to common hardware and network issues.

**👉 Start here:** [Go to the Documents Folder](./Documents/)

---

## 🚀 Quick Start (TL;DR)

If you already have the hardware wired according to Document `02`:
1. Ensure Python 3 is installed.
2. Run `setup.bat` to install the required Python packages.
3. Flash `1EC.ino` and `2EC.ino` to your respective ESP32 boards with your Wi-Fi credentials.
4. Run `start_server.bat`.
5. Open your browser to `http://localhost:5000`.

---
*Built with ❤️ using ESP32, Python, FastAPI, and Vanilla JS.*
