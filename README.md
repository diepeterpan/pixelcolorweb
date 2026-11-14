# PyPixelColor Web Application & Studio

> [!IMPORTANT]
> **Pre-Release Notice**: This software is currently in active **Pre-Release** status. It is fully functional, but features and APIs are subject to rapid iteration.
> 
> **Hardware Support**: Currently, this application **exclusively supports 96x16** (Width: 96, Height: 16) LED matrix displays. Connecting to devices with other dimensions or resolutions is not supported at this stage.

A modern, responsive, 3D tactile Web UI and background automation service for controlling Bluetooth Low Energy (BLE) **iPixel / PixelColor LED Matrix Displays** (tailored specifically for **96x16** widescreen matrices) powered by [`lucagoc/pypixelcolor`](https://github.com/lucagoc/pypixelcolor).

---

## 1. Key Features & Latest Updates

- **Unified Light 3D Tactile Styling & Semantic Button System:**
  - Soft-tactile 3D cards with physical button-press feedback (`.btn-3d`).
  - **Consistent Button Theming:**
    - `[Save]` buttons unified across all screens in crisp emerald green (`.btn-save`).
    - `[Load]` / `[Edit]` buttons unified in a clean slate neutral aesthetic (`.btn-load`).
    - `[Delete]` buttons styled in soft danger red (`.btn-del`).
    - Core primary actions (`Send to Matrix`, `Upload`, `Scan Devices`, `Apply Adjustments`, `Test Run`, etc.) feature a rich, vibrant **full-spectrum rainbow gradient** (`.btn-action-rainbow`) spanning Crimson &rarr; Orange &rarr; Gold &rarr; Emerald &rarr; Cyan &rarr; Royal Blue &rarr; Violet &rarr; Magenta.
- **Dedicated "Text message" Studio (Proportional PIL & Color Emojis):**
  - Renders mixed text, full-color emojis, and inline images pixel-perfectly into 96x16 frames.
  - **Interactive Emoji Canvas:**
    - Dedicated **🎄 Christmas** holiday category (`🎄`, `🎅`, `🤶`, `🧑‍🎄`, `⛄`, `❄️`, `🎁`, `🔔`, `🕯️`, `🦌`, `🛷`, `🍪`, `🥛`, etc.).
    - Categorized pallets for **Food (🍌, 🍆, 🥑)**, **Smileys**, **Nature (🐶, 🌲)**, **Cool (🔥, 🚀)**, **Objects**, and **Symbols**.
    - **Real-Time Word & Keyword Search:** Search through hundreds of emojis by name or descriptive keywords (e.g. searching "santa", "gift", "tree", "fire", "dog", "food" immediately filters the palette).
    - Double-height emoji buttons (`w-12 h-12 text-2xl`) for comfortable touch and desktop selection.
  - **Inline Image & Script Tags:** Embed custom icons and graphics using `<filename.png>` or live script output using `<script.py>` directly in the text message composer.
  - Multiple proportional pixel fonts (`Press Start 2P`, `Silkscreen`, `DejaVu Sans`, `VT323`, `Unifont`) with font size selection and text/background color pickers.
  - Horizontal alignment (**Left**, **Center**, **Right**) and Vertical alignment (**Top**, **Middle**, **Bottom**).
  - Toggleable anti-aliasing and live content width meter (`Width: X / 96 px`) alerting if content overflows the 96-pixel hardware boundary.
- **Image Studio CMS & Visual Editor:**
  - Complete image management: upload, preview, crop, resize, and fine-tune graphics.
  - **Chroma/Color Key Transparency & Color Swapping:** Select any background color with adjustable tolerance sliders to produce transparent sprites.
  - Step-by-step **Undo** stack and one-click **Reset to Original**.
  - Streamlined action toolbar with compact **`[Save]`** and **`[Upload]`** buttons.
- **Schedule & Timeline Automation:**
  - Automated time-of-day rotation between saved text message presets and graphics.
  - Collapsible **`[Add Slot]`** drawer with inline start/end times (`HH:MM`).
  - Chronological slot ordering, inline **`[Edit]`**, and unique ID-based **`[Delete]`**.
- **Python Script Studio:**
  - In-browser code editor with AST syntax checking (`[Check Syntax]`) and automatic 4-space tab indentation formatting (`[Fix Indentation]`).
  - Write custom `def get_text():` routines streaming dynamic data (clocks, network status, telemetry).
- **Settings & BLE Hardware Manager:**
  - Streamlined single-row Hardware Settings with compact `96x16` indicator, orientation selection (**Normal (0°)** and **Rotate 180°**), and immediate persistence via **`[Save]`**.
  - Interactive BLE scanner discovering nearby displays and automatic reconnection to paired matrix addresses on service boot.
  - Top hardware simulator hidden automatically on non-canvas tabs (`Settings`, `Schedule & Timeline`, `Image Studio`, `Bluetooth Manager`, `Python Script Studio`).

---

## 2. Architecture & File Structure

```
pixelcolorweb/
├── docker/
│   ├── Dockerfile             # Container definition with BlueZ, DBus & Python 3.12
│   └── docker-compose.yml     # Host network + BLE DBus socket passthrough
├── src/
│   └── pixelweb/
│       ├── main.py            # FastAPI server, REST routes, AST tools, and static mounting
│       ├── ble_worker.py      # Async background queue & BLE hardware client
│       ├── config_manager.py  # Persistent config.json engine
│       ├── script_runner.py   # Safe AST validation & Python script executor
│       ├── image_processor.py # PIL manipulation, chroma keying, and scaling
│       ├── scheduler.py       # Time-based timeline scheduler daemon
│       ├── text_message_renderer.py # Multi-run text, emoji, and inline tag renderer
│       ├── static/            # CSS, JS, and UI assets (Tailwind, Lucide, tactile styles)
│       └── templates/         # Clean HTML5 Single Page Application (index.html)
├── data/                      # Persistent state (config.json, uploads, fonts, scripts)
├── requirements.txt           # Python application dependencies
├── start.sh                   # Convenient local execution script
└── README.md                  # Project documentation
```

---

## 3. Quick Start & Deployment

### 3.1 Running in a Local Python Virtual Environment (`venv`)

Use the included helper script `start.sh`:
```bash
./start.sh
```
The script will:
- Check if port 8080 is already occupied, display process information, and prompt to terminate it if desired.
- Automatically setup `.venv` with all required dependencies if not already created.
- Launch the application on `http://localhost:8080`.

To start with debug logging:
```bash
./start.sh --debug
```

### 3.2 Running with Docker Compose

1. Verify Bluetooth and DBus are active on the host Linux machine (`systemctl status bluetooth`).
2. Run inside the `docker/` folder:
   ```bash
   cd docker
   docker compose up --build -d
   ```
3. Access the web interface at `http://localhost:8000`.

---

## 4. Usage Guide

1. **Bluetooth Pairing:**
   - Navigate to **Bluetooth Manager** from the hamburger menu.
   - Click **`[Scan Devices]`**, locate your 96x16 matrix display, and click **`[Connect]`**. The MAC address is saved to `data/config.json` and reconnects automatically.
2. **Composing Text & Emojis:**
   - Open **Text message**.
   - Type your text, click emojis from the palette (e.g. from the **`🎄 Christmas`** or **`🍌 Food`** tabs), or type in the search bar to locate specific emojis.
   - Tag uploaded images via the `<image.png>` selector or scripts via `<script.py>`.
   - Adjust typography (font, alignment, color, size), check the width badge, and click **`[Send to Matrix]`**.
3. **Automating with Schedules:**
   - Go to **Schedule & Timeline**.
   - Toggle **Enable Schedule**, click **`[Add Slot]`**, specify active times (`HH:MM`) and assign a saved text message preset.
4. **Orientation and Display Settings:**
   - Go to **Settings** to select **Normal (0°)** or **Rotate 180°** and press **`[Save]`**.
