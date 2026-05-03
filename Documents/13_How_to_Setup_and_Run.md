# 13 — How to Set Up & Run the Project

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel
**Audience:** Anyone setting up DUON for the first time on a new machine or new network.

---

## Prerequisites — What You Need Before Starting

### Hardware Checklist

- [ ] Robot chassis assembled with 4 motors
- [ ] 2× BTS7960 motor drivers mounted and wired to motors
- [ ] 2× ESP32 (USB Type-C) boards
- [ ] 3× HC-SR04 ultrasonic sensors mounted and wired to ESP32 #1
- [ ] LiPo battery connected to both BTS7960 drivers via buck converter
- [ ] 2× USB power banks (for ESP32 boards during operation)
- [ ] 2× USB-C data cables (NOT charge-only)
- [ ] Wi-Fi router or mobile hotspot broadcasting on **2.4 GHz**

### Software Checklist

- [ ] Windows 10 or Windows 11 laptop / PC
- [ ] Python 3.8 or higher installed (with "Add to PATH" checked)
- [ ] Arduino IDE 2.x installed (only needed for flashing firmware)
- [ ] A web browser (Chrome, Edge, Firefox, or Safari)

---

## Part 1 — One-Time Setup (Do This Once)

### Step 1.1 — Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the latest Python 3.x installer
3. Run the installer
4. **Critical:** Check ✅ **"Add Python to PATH"** before clicking Install

**Verify installation:**
Open Command Prompt (Win + R → `cmd`) and run:
```cmd
python --version
```
You should see something like `Python 3.11.4`. If you get an error, Python is not in PATH — reinstall and check the box.

---

### Step 1.2 — Install Python Packages

1. Open File Explorer and navigate to the DUON project folder
2. Double-click **`setup.bat`**
3. A terminal window opens and installs all required packages
4. Wait until you see "Done! Run start_server.bat to launch DUON."
5. Press any key to close

If `setup.bat` fails, open Command Prompt, navigate to the DUON folder, and run manually:
```cmd
pip install fastapi uvicorn websockets pydantic python-multipart
```

---

### Step 1.3 — Install Arduino IDE & ESP32 Board Package

> Skip this step if you are not modifying or re-flashing the ESP32 firmware.

1. Download Arduino IDE 2.x from [arduino.cc/en/software](https://www.arduino.cc/en/software)
2. Run the installer
3. Open Arduino IDE
4. Go to **File → Preferences**
5. In the **"Additional boards manager URLs"** field, paste:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
6. Click OK
7. Go to **Tools → Board → Boards Manager**
8. Search for `esp32`
9. Find **"esp32 by Espressif Systems"** → click **Install**
10. Wait for installation to complete

---

### Step 1.4 — Flash ESP32 #1 Firmware

1. Open the DUON folder → open `1EC` folder → double-click **`1EC.ino`** (opens in Arduino IDE)
2. **Update Wi-Fi credentials** in the code:
   ```cpp
   const char* ssid     = "YourWiFiName";
   const char* password = "YourWiFiPassword";
   ```
3. Connect ESP32 #1 to laptop using a **USB-C data cable**
4. In Arduino IDE:
   - **Tools → Board** → select `ALKS ESP32` or `ESP32 Dev Module`
   - **Tools → Port** → select the COM port that appeared (check Device Manager if unsure)
5. Click the **Upload** button (→ arrow icon)
6. Wait for "Done uploading" message
7. Open **Tools → Serial Monitor**, set baud to **115200**, press RESET on the ESP
8. You should see the ESP connect to Wi-Fi and print its IP address — **note this IP**

---

### Step 1.5 — Flash ESP32 #2 Firmware

1. Open `2EC` folder → double-click **`2EC.ino`**
2. Update the same Wi-Fi credentials:
   ```cpp
   const char* ssid     = "YourWiFiName";
   const char* password = "YourWiFiPassword";
   ```
3. Disconnect ESP32 #1 from laptop (or select the correct COM port)
4. Connect ESP32 #2 to laptop via USB-C data cable
5. In Arduino IDE:
   - **Tools → Port** → select the new COM port for ESP32 #2
6. Click **Upload**
7. Open Serial Monitor → 115200 baud → press RESET on ESP32 #2
8. Note its IP address

---

### Step 1.6 — Record IP Addresses

Write down both ESP IP addresses. You will enter these in the web dashboard. Example:

| Device | Example IP |
|--------|-----------|
| ESP32 #1 | 192.168.1.159 |
| ESP32 #2 | 192.168.1.162 |

> These IPs may change if you connect to a different Wi-Fi network or if your router assigns new addresses. Always verify via Serial Monitor when unsure.

---

## Part 2 — Starting the System (Every Session)

### Step 2.1 — Power the ESP32 Boards

Connect both ESP32 boards to USB power banks (or laptop USB during testing):
- USB Power Bank #1 → ESP32 #1 (USB-C cable)
- USB Power Bank #2 → ESP32 #2 (USB-C cable)

The ESP boards will automatically boot, connect to the saved Wi-Fi network, and start their TCP servers.

> If the ESP was previously connected to a laptop for firmware upload, disconnect that cable first so the power bank can take over.

---

### Step 2.2 — Power the Motors (Optional for Testing)

Connect the LiPo battery to the BTS7960 motor drivers. This powers the motors. You can skip this step if you only want to test sonar readings without driving the robot.

---

### Step 2.3 — Make Sure You're on the Right Wi-Fi

The laptop (running the Python server) must be on the **same Wi-Fi network** as the ESPs.

- If using a mobile hotspot: Connect laptop to the hotspot. ESPs are already configured to connect to it.
- If using a home router: Connect laptop to the same router the ESPs are configured for.
- **Never use 5 GHz Wi-Fi for ESPs** — they only support 2.4 GHz.

---

### Step 2.4 — Start the Python Server

1. Open the DUON project folder in File Explorer
2. Double-click **`start_server.bat`**
3. A terminal window opens showing:
   ```
   ==================================================
   DUON Mission Control Server
   ==================================================
   Local:   http://localhost:5000
   Network: http://192.168.1.xxx:5000  <-- open on phone/iPad
   ==================================================
   ```
4. Leave this terminal window **open** — closing it stops the server

---

### Step 2.5 — Open the Dashboard in Browser

On the **same laptop:**
```
http://localhost:5000
```

On a **phone, tablet, or another PC** on the same Wi-Fi:
```
http://[laptop-ip]:5000
```
Use the network IP shown in the terminal (e.g., `http://192.168.1.100:5000`)

Or scan the QR code from the **Network page** of the dashboard.

---

### Step 2.6 — Connect to ESP32 Boards

1. In the browser dashboard, click **Network** in the sidebar
2. Enter ESP32 #1 IP address in the "ESP1 IP" field
3. Enter ESP32 #2 IP address in the "ESP2 IP" field
4. Click **Save IPs**
5. Click **Connect Both** (or connect each individually)
6. Watch the status indicators at the top — both ESP1 and ESP2 dots should turn green
7. Check the terminal log panel — you should see:
   ```
   [NET] ESP32 #1 connected — 192.168.1.159:8080
   [NET] ESP32 #2 connected — 192.168.1.162:8080
   ```

---

### Step 2.7 — Verify Sonar Readings

1. Navigate to the **Drive** page
2. The three sonar gauges (Left, Front, Right) should show live values
3. Wave your hand in front of each sensor — the corresponding gauge should respond
4. If gauges show `---`, ESP1 is not connected — go back to Network page and connect ESP1

---

## Part 3 — Stopping the System

### To Stop the Robot Only

Press **STOP** button in the top status bar, or press **X** / **Space** on keyboard.

### To Stop the Server

**Option A:** In the Settings page of the dashboard → click **Shutdown Server**

**Option B:** Click the `X` on the `start_server.bat` terminal window

**Option C:** In the terminal, press `Ctrl + C`

### To Disconnect ESPs

Go to Network page → click **Disconnect Both** (or disconnect individually). This closes TCP sockets; the ESPs keep running and their motors stop.

---

## Part 4 — Moving to a New Wi-Fi Network

When you change Wi-Fi networks (e.g., from home to university lab), you need to:

1. **Update ESP firmware** with the new Wi-Fi credentials:
   - Open `1EC.ino` and `2EC.ino`
   - Update `ssid` and `password`
   - Re-flash both ESPs (Steps 1.4 and 1.5)

2. **Find new IP addresses:**
   - Connect each ESP via USB → Serial Monitor → reset → note new IPs

3. **Update dashboard:**
   - Enter new IPs in the Network page → Save IPs

> The Python server (`web_server.py`) adapts automatically to any network — no changes needed.

---

## Part 5 — Running on a Different Laptop

The DUON project folder is completely self-contained and portable. Copy the entire `DUON` folder to the new laptop, then:

1. Install Python on the new laptop (Step 1.1)
2. Run `setup.bat` to install packages (Step 1.2)
3. Run `start_server.bat` and open browser (Steps 2.4–2.5)
4. Enter ESP IPs in Network page (Step 2.6)
5. ESPs do NOT need to be re-flashed — they connect to the same Wi-Fi

---

## Troubleshooting Quick Reference

| Problem | First thing to check |
|---------|---------------------|
| `setup.bat` fails | Python not in PATH — reinstall Python with PATH checkbox |
| Dashboard won't open | Is `start_server.bat` still running? Port 5000 in use? |
| ESP dots stay red | Correct IP entered? Both on same Wi-Fi (2.4 GHz)? |
| Sonar shows `---` | ESP1 not connected — connect ESP1 in Network page |
| Motors don't move | Motor battery (LiPo) connected? BTS7960 enable pins HIGH? |
| Upload fails | Wrong COM port? Charge-only cable? Python holding serial port? |

> For full troubleshooting, refer to **Document 07 — Troubleshooting & Known Issues**.

---

*Document 13 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
