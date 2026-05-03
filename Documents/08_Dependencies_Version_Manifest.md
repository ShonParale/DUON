# 08 — Dependencies & Version Manifest

**Project:** DUON — Dynamic Ultrasonic Operations & Navigations
**Authors:** Shon Parale · Vedant Patel

---

## 🖥️ System Requirements

| Requirement | Minimum | Recommended | Notes |
|-------------|---------|-------------|-------|
| Operating System | Windows 10 | Windows 10/11 | macOS/Linux support is a future goal |
| Python | 3.8+ | 3.10 or 3.11 | Must be added to system PATH |
| RAM | 2 GB | 4 GB | Server is lightweight |
| Disk Space | 200 MB | 500 MB | Includes Python + packages |
| Network | Wi-Fi 2.4 GHz | Dedicated hotspot | 5 GHz will not work for ESPs |
| Browser | Any modern | Chrome / Edge | WebSocket + Canvas required |

---

## 🐍 Python Dependencies

### Installed via `setup.bat`

```batch
pip install fastapi uvicorn websockets pydantic python-multipart
```

| Package | Version Used | Purpose | PyPI |
|---------|-------------|---------|------|
| `fastapi` | 0.100+ | Web framework — HTTP routes, WebSocket endpoint | [pypi.org/project/fastapi](https://pypi.org/project/fastapi/) |
| `uvicorn` | 0.22+ | ASGI server — runs FastAPI application | [pypi.org/project/uvicorn](https://pypi.org/project/uvicorn/) |
| `websockets` | 11.0+ | WebSocket protocol implementation | [pypi.org/project/websockets](https://pypi.org/project/websockets/) |
| `pydantic` | 1.x or 2.x | Data validation for API models (`ConfigUpdate`) | [pypi.org/project/pydantic](https://pypi.org/project/pydantic/) |
| `python-multipart` | 0.0.6+ | Form data parsing (required by FastAPI) | [pypi.org/project/python-multipart](https://pypi.org/project/python-multipart/) |

### Python Standard Library (No Install Needed)

| Module | Used For |
|--------|---------|
| `asyncio` | Async event loop, WebSocket handling, periodic tasks |
| `json` | JSON encoding/decoding for WebSocket messages and config files |
| `logging` | Server-side log output |
| `math` | Trigonometry for sonar projection and dead-reckoning |
| `os` | File path operations, `os._exit()` for shutdown |
| `socket` | Raw TCP sockets for ESP32 communication; LAN IP detection |
| `sys` | `sys.exit()` for error handling |
| `threading` | Background threads for ESP TCP receivers, AutoMapper, navigation |
| `time` | Timing for pulse durations, settle delays, e-stop timeout |
| `collections.deque` | Rolling buffer in `SonarProcessor` |
| `heapq` | Priority queue for A* pathfinding |
| `uuid` | Generating unique IDs for obstacles |

---

## 🔧 Arduino / ESP32 Dependencies

### Arduino IDE

| Tool | Version | Download |
|------|---------|----------|
| Arduino IDE | 2.x (recommended) or 1.8.x | [arduino.cc/en/software](https://www.arduino.cc/en/software) |

### ESP32 Board Package

Install via Arduino IDE → File → Preferences → Additional Boards Manager URLs:

```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

Then: Tools → Board → Boards Manager → search "esp32" → Install

| Package | Version | Board Selected |
|---------|---------|---------------|
| esp32 by Espressif Systems | 2.x or 3.x | **ALKS ESP32** or **ESP32 Dev Module** |

### Arduino Libraries Used in Firmware

| Library | Source | Purpose |
|---------|--------|---------|
| `WiFi.h` | Built-in (ESP32 package) | Wi-Fi connection + TCP server/client |

> No external Arduino libraries are required. All functionality uses the built-in ESP32 Arduino core.

---

## 🌐 Frontend Dependencies (Browser)

All frontend assets are **served locally** — no internet connection required at runtime.

| File | Version | Source | Purpose |
|------|---------|--------|---------|
| `static/js/qrcode.min.js` | 1.5.x | [github.com/davidshimjs/qrcodejs](https://github.com/davidshimjs/qrcodejs) | QR code generation (locally bundled) |
| `static/js/main.js` | Custom | DUON codebase | Dashboard logic, WebSocket, controls |
| `static/js/mapping.js` | Custom | DUON codebase | Advanced Mapping page logic |
| `static/css/style.css` | Custom | DUON codebase | Full theme system (dark/light) |
| `static/index.html` | Custom | DUON codebase | Single-page application shell |

### Browser Requirements

| Feature | Used For | Minimum Support |
|---------|---------|----------------|
| WebSocket API | Real-time communication | All modern browsers |
| HTML5 Canvas 2D | Mapper and Mapping page visualization | All modern browsers |
| CSS Custom Properties | Dark/light theme system | Chrome 49+, Firefox 31+, Edge 16+ |
| Pointer Events API | Joystick touch input | Chrome 55+, Firefox 59+, Edge 79+ |
| localStorage | Theme preference persistence | All modern browsers |
| `fetch()` API | Shutdown endpoint call | All modern browsers |
| ES6+ JavaScript | `const`, `let`, arrow functions, template literals | Chrome 49+, Firefox 45+ |

---

## 📦 Installing Dependencies — Step by Step

### Step 1: Install Python

1. Download Python from [python.org/downloads](https://www.python.org/downloads/)
2. Run installer — **check "Add Python to PATH"** during installation
3. Verify: open CMD → `python --version` → should show 3.8 or higher

### Step 2: Install Python Packages

1. Navigate to DUON folder in File Explorer
2. Double-click `setup.bat`
3. Wait for all packages to install
4. You should see "Successfully installed" for each package

**Manual alternative (CMD):**
```cmd
cd /d "C:\path\to\DUON"
pip install fastapi uvicorn websockets pydantic python-multipart
```

### Step 3: Install Arduino IDE (for firmware only)

1. Download from [arduino.cc/en/software](https://www.arduino.cc/en/software)
2. Run installer
3. Open Arduino IDE
4. File → Preferences → paste ESP32 boards URL → OK
5. Tools → Board → Boards Manager → search "esp32" → Install

### Step 4: Verify Everything Works

```cmd
cd /d "C:\path\to\DUON"
python -c "import fastapi, uvicorn, websockets, pydantic; print('All OK')"
```
Should print: `All OK`

---

## 🔍 Checking Installed Versions

Run in CMD or PowerShell:

```cmd
python --version
pip show fastapi
pip show uvicorn
pip show websockets
pip show pydantic
```

Or to list all installed packages:
```cmd
pip list
```

---

## 📋 Full `requirements.txt`

For reproducible installs (can be created and used with `pip install -r requirements.txt`):

```
fastapi>=0.100.0
uvicorn>=0.22.0
websockets>=11.0.0
pydantic>=1.10.0
python-multipart>=0.0.6
```

> **Note:** `pydantic` v1.x and v2.x have API differences. FastAPI 0.100+ supports both. If you encounter Pydantic deprecation warnings, they are non-critical and do not affect functionality.

---

## 🆚 Dependency Notes & Compatibility

| Issue | Details |
|-------|---------|
| Pydantic v1 vs v2 | `web_server.py` uses `BaseModel` — compatible with both versions |
| uvicorn vs gunicorn | DUON uses uvicorn only; gunicorn is not required |
| asyncio event loop | Uses `asyncio.get_event_loop()` — DeprecationWarning suppressed in code |
| Python 3.12+ | `asyncio.get_event_loop()` deprecated; upgrade to `asyncio.get_running_loop()` if issues arise |
| ESP32 Arduino core v3 | `ledcAttach()` API changed from v2 — firmware uses new v3 API |

---

## 🖨️ Hardware Component Datasheets / References

| Component | Reference |
|-----------|-----------|
| ESP32 | [espressif.com/en/products/socs/esp32](https://www.espressif.com/en/products/socs/esp32) |
| BTS7960 | Infineon BTS7960 datasheet |
| HC-SR04 | HC-SR04 ultrasonic sensor datasheet |
| Buck Converter (generic 5V) | Refer to specific module used |

---

*Document 8 of 15 | DUON Project Documentation*
*Prepared by: Shon Parale & Vedant Patel*
