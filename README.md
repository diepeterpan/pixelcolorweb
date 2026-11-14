# PyPixelColor Web Application & Studio

A modern, light, 3D tactile Web UI and background automation service for controlling Bluetooth Low Energy (BLE) **iPixel / PixelColor LED Matrix Displays** (specialized for **16x96** matrices and compatible models) powered by [`lucagoc/pypixelcolor`](https://github.com/lucagoc/pypixelcolor).

---

## 1. Key Features

- **Light 3D & Vivid Rainbow Design:**
  - Soft-tactile 3D cards, physical button press feedback, and slightly rounded corners (`6px`).
  - Vivid rainbow spectrum gradients reflecting the full RGB LED matrix color capability.
  - Hamburger menu navigation with a real-time 16x96 virtual LED matrix simulator.
- **Dedicated "Text message" Studio (Proportional PIL & Emojis):**
  - Renders mixed custom text, color emojis, and custom inline images directly to static 16x96 hardware images.
  - Interactive **Emoji Canvas** with categorized standard emojis including **Food & Drink (🍌, 🍆, 🥑, 🍕, etc.)**, **Smileys**, **Animals/Nature (🐶, 🌲)**, **Activities/Cool (🔥, 🚀)**, and **Objects**, plus live search filtering.
  - **Inline Image Tags:** Embed custom icons and graphics using `<filename.png>` tags anywhere in your message (e.g. `HI 🍌 <holi.png> 🚀`).
  - Choice of multiple proportional fonts (`Press Start 2P`, `Silkscreen`, `DejaVu Sans`, `VT323`, `Unifont`).
  - Font size controls (6px - 16px) and color pickers.
  - On-screen alignment toggle: **Left**, **Center**, or **Right**.
  - Toggleable **Anti-Aliasing** (`draw.fontmode = 'L'` vs `'1'` and `LANCZOS` vs `NEAREST`).
  - Live hardware width limit meter (`Width: X / 96 px`) alerting if content overflows.
  - Consolidated top toolbar: Configuration name, preset loader, save, delete, and direct "Send Image to Matrix".
  - Real-time bitmapped sync to top virtual LED matrix hardware simulator.
- **Image Studio CMS & Editor:**
  - Complete image content management system to upload, crop, resize, and remove background colors.
  - **Chroma/Color Key Transparency:** Select any background color (white, black, custom) with an adjustable tolerance slider (0-100%) to create transparent icons.
  - List of all uploaded images with instant reload into the editor for further adjustments.
- **BLE Hardware Management:**
  - Background daemon that connects to the display, keeps state synchronized, and auto-starts on container boot.
  - Interactive BLE scanner in the UI to discover and connect to nearby LED matrices.
- **Dynamic Python Script Studio:**
  - In-browser code editor with AST syntax checking and validation.
  - Define custom `def get_text():` functions returning real-time strings (clocks, greetings, countdowns, custom telemetry).
  - Ability to save, load, and activate scripts for live display cycles.
- **Typography & Font Engine:**
  - Unifont, Google Fonts / pixel fonts support with custom colors, speeds, and rainbow effects.
- **Image Studio & Converter:**
  - Upload PNG, JPG, GIF, BMP, and automatically crop, resize, and convert to 16x96 matrix dimensions.
  - Text-to-Image banner generator with icon stamping.
- **Timeline Scheduler:**
  - Time-of-day and date-based scheduling rules for alternating text, scripts, and image media.
- **Full JSON Persistence:**
  - All configurations, uploaded images, scripts, and scheduled slots are saved to `data/config.json`.

---

## 2. Architecture & File Structure

```
pixelcolorweb/
├── docker/
│   ├── Dockerfile             # Container definition with BlueZ, DBus & Python 3.12
│   └── docker-compose.yml     # Host network + BLE DBus socket passthrough
├── src/
│   └── pixelweb/
│       ├── main.py            # FastAPI web server and REST/WS endpoints
│       ├── ble_worker.py      # Async background queue & BLE hardware client
│       ├── config_manager.py  # Persistent config.json engine
│       ├── script_runner.py   # Safe AST validation & Python script executor
│       ├── image_processor.py # PIL cropping, scaling, and text-image generation
│       ├── scheduler.py       # Time-based schedule evaluation daemon
│       ├── static/            # CSS, JS, and UI assets (Tailwind, Lucide, 3D styles)
│       └── templates/         # Clean HTML5 Single Page Application
├── data/                      # Persistent state (config.json, uploads, fonts, scripts)
├── pypixelcolor/              # Underlying BLE hardware protocol driver
└── README.md                  # Complete product and deployment guide
```

---

## 3. Deployment & Quick Start

### 3.1 Running with Docker Compose (Recommended)

1. Ensure the host Linux system has BlueZ running and Bluetooth enabled (`systemctl status bluetooth`).
2. Navigate to the `docker/` folder and build/run:
   ```bash
   cd docker
   docker compose up --build -d
   ```
3. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

### 3.2 Running in a Local Python Virtual Environment (`venv`)

You can launch the application with a single command using `start.sh`:
```bash
./start.sh
```
The script will:
- Check if port 8080 is in use, display process information, and prompt to terminate it if desired.
- Automatically verify and create `.venv` (with all required dependencies and `pypixelcolor`) if it doesn't already exist.
- Start the application on `http://localhost:8080`.

---

## 4. Usage Guide

1. **Pairing the BLE Display:**
   - Open the **Hamburger Menu** -> **Bluetooth Device Manager**.
   - Click **Scan Devices**. Once your matrix display appears, click **Connect**.
   - The device address is permanently saved to `data/config.json` and will automatically reconnect whenever the container starts.
2. **Sending Text & Formatting:**
   - Go to **Text & Typography**.
   - Type your text, select primary and background colors, choose whether **Rainbow Spectrum Mode** is active, adjust scroll speed, and click **Send to Matrix**.
3. **Running Custom Python Text Generators:**
   - Go to **Python Script Studio**.
   - Select an existing preset (e.g., *Live Digital Clock & Date*) or write your own `def get_text():` function.
   - Click **Test Run & Validate** to check syntax and view output.
   - Click **Save & Activate** to stream output to the LED matrix.
4. **Uploading and Converting Images:**
   - Go to **Image Studio & Crop**.
   - Drag and drop or browse for an image. The system will convert and crop the media to fit the 16x96 resolution.
   - Click **Send** next to any image in the gallery.
5. **Configuring Schedules:**
   - Go to **Schedule & Timeline**.
   - Check **Enable Schedule**, specify start and end hours (HH:MM), enter message content, and click **Add Slot**.

