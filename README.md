# PyPixelColor Web Application & Studio

> [!IMPORTANT]
> **Pre-Release Notice**: This software is currently in active **Pre-Release** status. It is fully functional, but features and APIs are subject to rapid iteration.
> 
> **Hardware Support**: Currently, this application **exclusively supports 96x16** (Width: 96, Height: 16) LED matrix displays. Connecting to devices with other dimensions or resolutions is not supported at this stage.

A modern, responsive, 3D tactile Web UI and background automation service for controlling Bluetooth Low Energy (BLE) **iPixel / PixelColor LED Matrix Displays** (tailored specifically for **96x16** widescreen matrices) powered by [`lucagoc/pypixelcolor`](https://github.com/lucagoc/pypixelcolor).

---

## 1. Key Features & Latest Updates

- **Unified Light 3D Tactile Styling & Responsive Layout:**
  - Soft-tactile 3D cards with physical button-press feedback (`.btn-3d`).
  - **Single-Row 5-Tile Dashboard Overview:** Compacted live telemetry metrics below the hardware simulator:
    1. **Active Content:** Live headline and detail tracking the currently playing message, graphic, clock, or scheduled slot.
    2. **Target BLE Device:** Paired device name, address, and live connectivity status.
    3. **BLE Link & Speed:** BLE generation, negotiated throughput, RSSI signal rating, and MCU firmware version.
    4. **Transmission Profile:** Compression mode (`rgb_raw`, `rgb_max`, `palette`), MTU-bounded payload chunk cap, and pacing delay.
    5. **Automation:** Live scheduler status and slot counts formatted by type (`X time • Y seq`).
  - **Consistent Button Theming:**
    - `[Save]` buttons unified across all screens in crisp emerald green (`.btn-save`).
    - `[Load]` / `[Edit]` buttons unified in a clean slate neutral aesthetic (`.btn-load`).
    - `[Delete]` buttons styled in soft danger red (`.btn-del`).
    - Core primary actions (`Send to Matrix`, `Upload`, `Scan Devices`, `Apply Adjustments`, `Test Run`, etc.) feature a rich, vibrant **full-spectrum rainbow gradient** (`.btn-action-rainbow`).
  - Default collapsed sidebar menu on startup for a distraction-free widescreen view.

- **Dedicated "Text message" Studio (Proportional PIL & Color Emojis):**
  - Renders mixed text, full-color emojis, and inline images pixel-perfectly into 96x16 frames.
  - **Multi-line Text & Page Break Handling (Static vs. Scrolling):**
    - **Static Mode (`scroll_enabled` off):** Text containing CR (`\r`), LF (`\n`), CRLF (`\r\n`), or LFCR (`\n\r`) is split into clean segments without blank gaps. Each segment displays sequentially for a user-configurable duration between **1s and 10s** (`page_duration`), automatically cycling continuously.
    - **Scrolling Mode (`scroll_enabled` on):** Any CR / LF / CRLF / LFCR sequences are cleanly replaced with a single space, allowing seamless, continuous horizontal banner scrolling.
    - **Embedded Script Multi-line Support:** Dynamic output from `<script.py>` containing line breaks is also automatically expanded and split into timed pages in static mode.
  - **Dynamic Software Scrolling Engine:**
    - Bi-directional scrolling (**Scroll Left** and **Scroll Right**).
    - Configurable scroll intervals down to 10ms with zero artificial locks.
    - **Frame Skip Control:** Dynamic adaptive frame dropping (1–5 step columns) with auto-speed scaling.
    - **Motion Blur / Phosphor Decay Trailing:** Simulates retro phosphor trailing behind moving text and emojis with gap-aware decay.
  - **Interactive Emoji Canvas & Categories:**
    - Dedicated **🎄 Christmas** holiday category (`🎄`, `🎅`, `🤶`, `🧑‍🎄`, `⛄`, `❄️`, `🎁`, `🔔`, `🕯️`, `🦌`, `🛷`, `🍪`, `🥛`, etc.).
    - Categorized palettes for **Food (🍌, 🍆, 🥑)**, **Smileys**, **Nature (🐶, 🌲)**, **Cool (🔥, 🚀)**, **Objects**, and **Symbols**.
    - **Real-Time Word & Keyword Search:** Search through hundreds of emojis by name or descriptive keywords.
  - **Inline Image & Script Tags:** Embed custom icons and graphics using `<filename.png>` or live script output using `<script.py>` directly in the text message composer.
  - **Embedded Script Emoji Rendering:** Script outputs (such as live weather routines returning temperature and weather conditions) automatically parse embedded Unicode and emoji escape sequences into full-color Twemoji graphics rather than falling back to monochrome font missing-glyph boxes.
  - Multiple proportional pixel fonts (`Press Start 2P`, `Silkscreen`, `DejaVu Sans`, `VT323`, `Unifont`) with font size selection and text/background color pickers.
  - Horizontal alignment (**Left**, **Center**, **Right**) and Vertical alignment (**Top**, **Middle**, **Bottom**).
  - Toggleable anti-aliasing and live content width meter (`Width: X / 96 px`).

- **Hybrid Schedule & Timeline Automation Engine:**
  - **Dual Playback Modes:**
    1. **Time-Window Overrides:** Schedule slots active during specified time ranges (`HH:MM` start and end times). Automatically take highest priority and override sequential playback.
    2. **Sequential Playback Playlist (Carousel):** Operates on a defined duration (in seconds) for each slot whenever no fixed time-window slot is active.
  - **Slot-Level Enable / Disable & Batch Management:**
    - Inline toggle switch on each schedule slot (both Time Window and Sequential tables) to quickly enable or disable individual slots without deleting them.
    - Multi-select row checkboxes and a master header checkbox for bulk operations.
    - Contextual bulk action toolbar providing one-click **`[Enable]`** and **`[Disable]`** for all selected slots.
    - Muted visual styling and struck-through text for disabled slots.
  - **Reorderable Sequential Carousel:** Full up/down reordering controls for sequential items.
  - **Automatic Fallback & Resume:** Seamlessly reverts back to the sequential playlist when a time-window slot completes, resuming where it left off.
  - Two distinct management tables in the Schedule tab for clear overview and editing.

- **High-Performance BLE Engine & Optimization:**
  - **Dynamic MTU Negotiation:** Automatically requests up to 517-byte MTU (509-byte payload cap) for high-speed frame streaming.
  - **Transmission Profiles:** Supports `rgb_raw` (uncompressed 16-bit RGB565), `rgb_max` (RLE compression), and `palette` modes.
  - **Configurable Inter-Chunk Pacing:** Microsecond-level transmission pacing (0.5ms – 5.0ms) with Write Without Response (`response=False`) for maximum throughput.
  - **Built-in Benchmark Utility:** In-browser benchmark testing different packet sizes, pacing delays, and payload sizes with live transmission speed measurements.

- **Image Studio CMS & Visual Editor:**
  - Complete image management: upload, preview, crop, resize, and fine-tune graphics.
  - **Chroma/Color Key Transparency & Color Swapping:** Select any background color with adjustable tolerance sliders to produce transparent sprites.
  - Step-by-step **Undo** stack and one-click **Reset to Original**.
  - Streamlined action toolbar with compact **`[Save]`** and **`[Upload]`** buttons.

- **Python Script Studio:**
  - In-browser code editor with AST syntax checking (`[Check Syntax]`) and automatic 4-space tab indentation formatting (`[Fix Indentation]`).
  - Write custom `def get_text():` routines streaming dynamic data (clocks, network status, telemetry).

- **Settings & Persistent State:**
  - Persistent brightness, orientation, power state, and paired BLE hardware addresses saved across reboots in `data/config.json`.
  - **In-Memory Active Dispatch & Wear Prevention:** Ephemeral active text message playback and scheduler transitions operate strictly in-memory (`persist=False`), preventing continuous disk writes and flash storage wear.
  - **Graceful Startup Display:** Automatic fallback to configured default text or the active schedule playlist on matrix connection.
  - Automatic hardware re-synchronization on BLE reconnect.

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
│       ├── ble_worker.py      # Async background queue, dynamic MTU & fast-path BLE GATT client
│       ├── config_manager.py  # Persistent config.json engine
│       ├── script_runner.py   # Safe AST validation & Python script executor
│       ├── image_processor.py # PIL manipulation, chroma keying, and scaling
│       ├── scheduler.py       # Hybrid timeline scheduler (Time-window & Sequential Carousel)
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
3. Access the web interface at `http://localhost:8080`.

#### Useful Docker Environment Variables

You can configure these variables in `docker/docker-compose.yml`:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TZ` | `Africa/Johannesburg` | Host timezone for schedule time-windows, clocks, and dynamic Python scripts. |
| `LOG_LEVEL` | `INFO` | Logging level verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `PORT` | `8080` | Web server port. |
| `HOST` | `0.0.0.0` | Listening network interface address. |
| `PYTHONUNBUFFERED`| `1` | Ensures standard output and errors are immediately flushed to `docker compose logs`. |

---

## 4. Usage Guide

1. **Bluetooth Pairing:**
   - Navigate to **Bluetooth Manager** from the hamburger menu.
   - Click **`[Scan Devices]`**, locate your 96x16 matrix display, and click **`[Connect]`**. The MAC address is saved to `data/config.json` and reconnects automatically.
2. **Composing Text & Emojis:**
   - Open **Text message**.
   - Type your text, click emojis from the palette (e.g. from the **`🎄 Christmas`** or **`🍌 Food`** tabs), or type in the search bar to locate specific emojis.
   - Tag uploaded images via the `<image.png>` selector or scripts via `<script.py>`.
   - Press `Enter` to create multi-page static messages (each page displays for 1–10 seconds configured under **Page Duration**), or check **Enable Scrolling** to automatically replace line breaks with spaces and scroll as a banner.
   - Adjust typography (font, alignment, color, size), check the width badge, enable scrolling/motion blur if desired, and click **`[Send to Matrix]`**.
3. **Automating with Schedules:**
   - Go to **Schedule & Timeline**.
   - Toggle **Enable Schedule** and click **`[Add Slot]`**.
   - Choose between **Fixed Time Window** (`HH:MM` start/end) or **Sequential Playlist** (duration in seconds).
   - Enable or disable specific slots on demand using the inline toggle switches or multi-select batch action toolbar.
   - Reorder sequential items using the **Up** / **Down** buttons to set playback order.
4. **Brightness & Hardware Controls:**
   - Adjust matrix brightness directly from the persistent header slider.
   - Go to **Settings** to select **Normal (0°)** or **Rotate 180°**, adjust BLE MTU/transmission pacing, or run transmission benchmarks.
