// Initialize Lucide Icons
lucide.createIcons();

// Global App State
const state = {
  config: null,
  bleStatus: { connected: false, address: null, name: null, status_msg: "Disconnected" },
  activeTab: "tab-dashboard",
  previewMode: "bitmap", // "bitmap" or "text"
  previewBitmap: null,    // 16 rows x N cols [r,g,b]
  minScrollSpeed: 80,
  scrolling: {
    enabled: false,
    direction: "rtl",
    speed: 80,
    offset: 0,
    lastTick: 0,
    hardwareSynced: false
  },
  preview: {
    width: 96,
    height: 16,
    text: "HELLO MATRIX 96x16",
    color: "#FF007F",
    bg_color: "#000000",
    rainbow: true,
    scrollOffset: 0
  }
};

function updateScrollSpeedConstraints(minSpeed) {
  // Speed constraints are disabled per user preference
}

// Canvas Preview Setup
const canvas = document.getElementById("matrix-canvas");
const ctx = canvas.getContext("2d");

function initCanvas() {
  const pixelSize = 8;
  canvas.width = 96 * pixelSize;
  canvas.height = 16 * pixelSize;
}

// Render Virtual 96x16 Matrix Preview
function drawMatrixPreview() {
  const cols = 96;
  const rows = 16;
  const dotSize = 6;
  const gap = 2;
  const step = dotSize + gap;

  // Background
  ctx.fillStyle = "#050508";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // If in bitmap mode and we have preview pixels from Text Message / Image
  if (state.previewMode === "bitmap" && state.previewBitmap && state.previewBitmap.length === rows) {
    const fullCols = state.previewBitmap[0] ? state.previewBitmap[0].length : cols;
    let startCol = 0;

    if (state.scrolling.enabled && fullCols > 0) {
      if (!state.scrolling.hardwareSynced) {
        // Fallback local animation if hardware WebSocket sync is not streaming
        const now = performance.now();
        const speed = Math.max(80, state.scrolling.speed || 80);
        if (!state.scrolling.lastTick) state.scrolling.lastTick = now;
        const elapsed = now - state.scrolling.lastTick;

        if (elapsed >= speed) {
          const spacer = 24;
          const loopUnit = Math.max(cols, fullCols) + spacer;
          const stepsToAdvance = Math.max(1, Math.round(elapsed / speed));
          state.scrolling.lastTick = now;

          if (state.scrolling.direction === "rtl") {
            state.scrolling.offset = (state.scrolling.offset + stepsToAdvance) % loopUnit;
          } else {
            state.scrolling.offset = (state.scrolling.offset - stepsToAdvance + loopUnit) % loopUnit;
          }
        }
      }
      startCol = Math.floor(state.scrolling.offset);
    }

    const spacer = 24;
    const loopUnit = Math.max(cols, fullCols) + spacer;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let rgb = [0, 0, 0];
        if (state.scrolling.enabled) {
          const sampleX = (startCol + c) % loopUnit;
          if (sampleX < fullCols) {
            rgb = state.previewBitmap[r][sampleX] || [0, 0, 0];
          } else {
            // In the 24px spacer region between loops, use background color (first pixel color or black)
            rgb = state.previewBitmap[r][0] || [0, 0, 0];
          }
        } else {
          rgb = state.previewBitmap[r][c] || [0, 0, 0];
        }

        const isLit = rgb && (rgb[0] > 10 || rgb[1] > 10 || rgb[2] > 10);
        const x = c * step + 1;
        const y = r * step + 1;

        ctx.beginPath();
        ctx.arc(x + dotSize / 2, y + dotSize / 2, dotSize / 2, 0, Math.PI * 2);

        if (isLit) {
          const colorStr = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
          ctx.fillStyle = colorStr;
          ctx.shadowColor = colorStr;
          ctx.shadowBlur = 5;
        } else {
          ctx.fillStyle = "#111420";
          ctx.shadowBlur = 0;
        }
        ctx.fill();
      }
    }
  } else {
    // Fallback: Text Marquee Renderer
    const offscreen = document.createElement("canvas");
    offscreen.width = cols * 2;
    offscreen.height = rows;
    const offCtx = offscreen.getContext("2d");

    offCtx.fillStyle = "#000000";
    offCtx.fillRect(0, 0, offscreen.width, offscreen.height);

    offCtx.fillStyle = "#FFFFFF";
    offCtx.font = "bold 13px monospace";
    offCtx.textBaseline = "middle";
    offCtx.fillText(state.preview.text, 2 + state.preview.scrollOffset, rows / 2);

    const imgData = offCtx.getImageData(0, 0, cols, rows).data;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = (r * cols + c) * 4;
        const isLit = imgData[idx] > 64;

        const x = c * step + 1;
        const y = r * step + 1;

        ctx.beginPath();
        ctx.arc(x + dotSize / 2, y + dotSize / 2, dotSize / 2, 0, Math.PI * 2);

        if (isLit) {
          if (state.preview.rainbow) {
            const hue = ((c * 4 + Date.now() / 20) % 360);
            ctx.fillStyle = `hsl(${hue}, 100%, 55%)`;
            ctx.shadowColor = `hsl(${hue}, 100%, 55%)`;
            ctx.shadowBlur = 6;
          } else {
            ctx.fillStyle = state.preview.color;
            ctx.shadowColor = state.preview.color;
            ctx.shadowBlur = 6;
          }
        } else {
          ctx.fillStyle = "#111420";
          ctx.shadowBlur = 0;
        }
        ctx.fill();
      }
    }

    state.preview.scrollOffset -= 0.5;
    if (state.preview.scrollOffset < -250) {
      state.preview.scrollOffset = cols;
    }
  }

  requestAnimationFrame(drawMatrixPreview);
}

// Navigation & Tab Switching
function setupNavigation() {
  const hamburger = document.getElementById("btn-hamburger");
  const sidebar = document.getElementById("sidebar-nav");
  hamburger.addEventListener("click", () => {
    sidebar.classList.toggle("hidden");
  });

  document.querySelectorAll(".nav-item").forEach(item => {
    item.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach(i => {
        i.classList.remove("text-pink-600", "bg-pink-50", "border-pink-200", "font-semibold");
        i.classList.add("text-slate-600", "font-medium");
      });
      item.classList.add("text-pink-600", "bg-pink-50", "border-pink-200", "font-semibold");
      item.classList.remove("text-slate-600", "font-medium");

      const tabId = item.dataset.tab;
      document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
      const targetContent = document.getElementById(tabId);
      if (targetContent) targetContent.classList.remove("hidden");

      if (tabId === "tab-schedule") {
        fetchConfig();
      }

      // Hide simulator on Image Studio, Bluetooth Manager, Python Script Studio, Schedule, and Settings tabs
      const sim = document.getElementById("global-simulator-section");
      if (sim) {
        if (tabId === "tab-images" || tabId === "tab-ble" || tabId === "tab-script" || tabId === "tab-schedule" || tabId === "tab-settings") {
          sim.classList.add("hidden");
        } else {
          sim.classList.remove("hidden");
        }
      }
    });
  });
}

// API Calls & State Sync
async function fetchConfig() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    state.config = data;

    // Sync UI elements safely with null-checks
    if (data.text) {
      const textInp = document.getElementById("text-input") || document.getElementById("msg-text-input");
      if (textInp) textInp.value = data.text.content || "";
      const textCol = document.getElementById("text-color") || document.getElementById("msg-text-color");
      if (textCol) textCol.value = data.text.color || "#FF007F";
      const dashSummary = document.getElementById("dash-active-summary");
      if (dashSummary) dashSummary.textContent = data.text.content || "HELLO MATRIX";
      state.preview.text = data.text.content;
      state.preview.color = data.text.color || "#FF007F";
      state.preview.rainbow = data.text.rainbow_mode === 1;
    }
    if (data.matrix) {
      const quickBright = document.getElementById("quick-brightness");
      if (quickBright) quickBright.value = data.matrix.brightness || 80;
      const brightVal = document.getElementById("brightness-val");
      if (brightVal) brightVal.textContent = `${data.matrix.brightness || 80}%`;
      const resSelect = document.getElementById("matrix-resolution");
      if (resSelect && data.matrix.width && data.matrix.height) {
        resSelect.value = `${data.matrix.width}x${data.matrix.height}`;
      }
      const orientSelect = document.getElementById("matrix-orientation");
      if (orientSelect && data.matrix.orientation !== undefined) {
        orientSelect.value = String(data.matrix.orientation);
      }
    }
    if (data.schedule) {
      const schedEnable = document.getElementById("schedule-enable");
      if (schedEnable) schedEnable.checked = !!data.schedule.enabled;
      const dashSched = document.getElementById("dash-schedule-status");
      if (dashSched) dashSched.textContent = data.schedule.enabled ? "Active" : "Disabled";
      renderScheduleTable(data.schedule.slots || []);
    }
    if (data.min_scroll_speed) {
      updateScrollSpeedConstraints(data.min_scroll_speed);
    }
    if (data.active_text_message) {
      const atm = data.active_text_message;
      if (atm.scroll_enabled) {
        state.scrolling.enabled = true;
        state.scrolling.direction = atm.scroll_direction || "rtl";
        state.scrolling.speed = atm.scroll_speed || 80;
        state.scrolling.frameSkip = !!atm.frame_skip_enabled;
        state.scrolling.frameSkipStep = atm.frame_skip_step || 1;
        state.scrolling.blur = !!atm.blur_enabled;
      }
      // Populate text message composer form inputs from active config
      const msgTextInp = document.getElementById("msg-text-input");
      if (msgTextInp && atm.text) msgTextInp.value = atm.text;
      const msgFontSel = document.getElementById("msg-font-family");
      if (msgFontSel && atm.font_id) msgFontSel.value = atm.font_id;
      const msgFontSize = document.getElementById("msg-font-size");
      if (msgFontSize && atm.font_size) msgFontSize.value = atm.font_size;
      const msgTextColor = document.getElementById("msg-text-color");
      if (msgTextColor && atm.text_color) msgTextColor.value = atm.text_color;
      const msgBgColor = document.getElementById("msg-bg-color");
      if (msgBgColor && atm.bg_color) msgBgColor.value = atm.bg_color;
      const msgScrollEn = document.getElementById("msg-scroll-enabled");
      if (msgScrollEn) msgScrollEn.checked = !!atm.scroll_enabled;
      const msgFrameSkip = document.getElementById("msg-frame-skip-enabled");
      if (msgFrameSkip) msgFrameSkip.checked = !!atm.frame_skip_enabled;
      const msgFrameSkipStep = document.getElementById("msg-frame-skip-step");
      if (msgFrameSkipStep && atm.frame_skip_step) msgFrameSkipStep.value = atm.frame_skip_step;
      const msgBlur = document.getElementById("msg-blur-enabled");
      if (msgBlur) msgBlur.checked = !!atm.blur_enabled;
      const msgScrollSpd = document.getElementById("msg-scroll-speed");
      if (msgScrollSpd && atm.scroll_speed) msgScrollSpd.value = atm.scroll_speed;

      // Trigger preview fetch to initialize state.previewBitmap with blur pixels
      if (typeof window.fetchRenderedPreview === "function") {
        window.fetchRenderedPreview();
      }
    }
    if (data.ble) {
      const b = data.ble;
      const pngMode = b.png_mode || "rgb_max";
      const pacing = b.chunk_pacing_ms !== undefined ? b.chunk_pacing_ms : 1.5;
      const chunkCap = b.max_chunk_size || 509;

      // Update Dashboard Tile
      const dashPngBadge = document.getElementById("dash-ble-png-badge");
      const dashPngLabel = document.getElementById("dash-ble-png-label");
      const dashChunkCap = document.getElementById("dash-ble-chunk-cap");
      const dashPacing = document.getElementById("dash-ble-pacing");

      if (dashPngBadge) dashPngBadge.textContent = pngMode;
      if (dashPngLabel) {
        const labels = {
          rgb_raw: "Uncompressed (Fastest Decode)",
          rgb_max: "Max Compressed (Smallest)",
          palette: "8-Bit Palette (Adaptive)"
        };
        dashPngLabel.textContent = labels[pngMode] || pngMode;
      }
      if (dashChunkCap) dashChunkCap.textContent = `${chunkCap} B (Cap)`;
      if (dashPacing) dashPacing.textContent = `${pacing} ms`;

      // Sync Settings inputs
      const selPngMode = document.getElementById("ble-png-mode");
      if (selPngMode) selPngMode.value = pngMode;
      const inpChunkSize = document.getElementById("ble-chunk-size");
      if (inpChunkSize) inpChunkSize.value = chunkCap;
      const inpPacing = document.getElementById("ble-chunk-pacing");
      if (inpPacing) inpPacing.value = pacing;
    }
  } catch (err) {
    console.error("Error fetching config:", err);
  }
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    state.bleStatus = data;
    const pill = document.getElementById("ble-status-pill");
    const text = document.getElementById("ble-status-text");
    const dashName = document.getElementById("dash-device-name");
    const dashMac = document.getElementById("dash-device-mac");
    const btnRetry = document.getElementById("btn-reconnect-ble");

    if (data.connected) {
      pill.className = "flex items-center gap-2 px-3 py-1.5 rounded-subtle bg-emerald-50 text-emerald-700 border border-emerald-200 text-sm font-medium";
      text.textContent = `Connected: ${data.name || data.address}`;
      dashName.textContent = data.name || "PixelColor Matrix";
      dashMac.textContent = `Address: ${data.address}`;
      if (btnRetry) btnRetry.classList.add("hidden");
    } else {
      pill.className = "flex items-center gap-2 px-3 py-1.5 rounded-subtle bg-amber-50 text-amber-700 border border-amber-200 text-sm font-medium";
      text.textContent = data.status_msg || "Disconnected";
      dashName.textContent = data.address ? (data.name || "Configured (Offline)") : "No Device Paired";
      dashMac.textContent = data.address ? `Address: ${data.address}` : "Address: --:--:--:--:--:--";
      if (btnRetry && data.address) btnRetry.classList.remove("hidden");
    }

    // Update Dashboard BLE Telemetry Tile
    const bleVersionEl = document.getElementById("dash-ble-version");
    const bleThroughputEl = document.getElementById("dash-ble-throughput");
    const bleSignalEl = document.getElementById("dash-ble-signal");
    const bleFirmwareEl = document.getElementById("dash-ble-firmware");

    if (data.ble_info) {
      const b = data.ble_info;
      if (bleVersionEl) bleVersionEl.textContent = b.version || "BLE 4.2";
      if (bleThroughputEl) bleThroughputEl.textContent = b.max_throughput || "~80-100 KB/s";
      if (bleSignalEl) {
        bleSignalEl.textContent = b.signal_quality || "Unknown";
        if (b.rssi && b.rssi < -80) {
          bleSignalEl.className = "font-mono font-semibold text-amber-600";
        } else {
          bleSignalEl.className = "font-mono font-semibold text-emerald-600";
        }
      }
      if (bleFirmwareEl) bleFirmwareEl.textContent = b.mcu_version || "v1.0 (96x16)";
      if (b.chunk_size) {
        const dashChunkCap = document.getElementById("dash-ble-chunk-cap");
        if (dashChunkCap && b.negotiated_mtu) {
          dashChunkCap.textContent = `${b.chunk_size} B (MTU ${b.negotiated_mtu})`;
        }
      }
      if (b.calculated_avg_total_ms || data.min_scroll_speed) {
        updateScrollSpeedConstraints(b.calculated_avg_total_ms || data.min_scroll_speed);
      }
    } else if (!data.connected) {
      if (bleSignalEl) {
        bleSignalEl.textContent = "Offline";
        bleSignalEl.className = "font-mono text-slate-400";
      }
    }

    // Update Live Simulator Scroll Metrics Pill
    const metricsPill = document.getElementById("sim-scroll-metrics");
    if (metricsPill) {
      const sm = data.scroll_metrics;
      if (sm && sm.active) {
        metricsPill.classList.remove("hidden");
        const targetSpeed = document.getElementById("sim-target-speed");
        const pixelShift = document.getElementById("sim-pixel-shift");
        const actualBle = document.getElementById("sim-actual-ble");

        if (targetSpeed) targetSpeed.textContent = `${sm.target_speed_ms}ms`;
        if (pixelShift) pixelShift.textContent = `${sm.pixel_shift}px`;
        if (actualBle) {
          actualBle.textContent = `${sm.actual_ble_ms}ms`;
          if (sm.actual_ble_ms > sm.target_speed_ms * 1.5) {
            actualBle.className = "font-mono text-amber-600 font-bold";
          } else {
            actualBle.className = "font-mono text-emerald-700 font-bold";
          }
        }
      } else if (!state.scrolling.enabled) {
        metricsPill.classList.add("hidden");
      }
    }
  } catch (err) {
    console.error("Error fetching status:", err);
  }
}

// Quick Header Controls (Power & Brightness)
function setupHeaderControls() {
  const quickBrightness = document.getElementById("quick-brightness");
  if (quickBrightness) {
    quickBrightness.addEventListener("input", async (e) => {
      const val = parseInt(e.target.value, 10);
      const bVal = document.getElementById("brightness-val");
      if (bVal) bVal.textContent = `${val}%`;
      await fetch(`/api/brightness?level=${val}`, { method: "POST" });
    });
  }

  const btnPower = document.getElementById("btn-power-toggle");
  if (btnPower) {
    btnPower.addEventListener("click", async () => {
      const currentPower = state.config?.matrix?.power ?? true;
      const nextPower = !currentPower;
      await fetch(`/api/power?on=${nextPower}`, { method: "POST" });
      if (state.config && state.config.matrix) state.config.matrix.power = nextPower;
    });
  }

  const btnReconnect = document.getElementById("btn-reconnect-ble");
  if (btnReconnect) {
    btnReconnect.addEventListener("click", async () => {
      btnReconnect.textContent = "Connecting...";
      const target = state.config?.device?.address;
      if (target) {
        await fetch("/api/ble/connect", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ address: target, name: state.config?.device?.name })
        });
      }
      fetchStatus();
    });
  }
}

// Python Script Studio Controls
function setupScriptControls() {
  const btnTest = document.getElementById("btn-test-script");
  const btnCheckSyntax = document.getElementById("btn-check-syntax");
  const btnFixIndent = document.getElementById("btn-fix-indent");
  const btnSave = document.getElementById("btn-save-script");
  const btnDelete = document.getElementById("btn-delete-script");
  const scriptNameInput = document.getElementById("script-name-input");
  const codeArea = document.getElementById("python-code");
  const outputBox = document.getElementById("script-output");
  const picker = document.getElementById("script-preset-picker");
  const btnLoad = document.getElementById("btn-load-script");

  async function refreshScriptsDropdown(selectedId = "") {
    try {
      const res = await fetch("/api/scripts");
      const list = await res.json();
      picker.innerHTML = `<option value="">-- Load Script --</option>`;
      list.forEach(s => {
        const opt = document.createElement("option");
        opt.value = s.id;
        opt.textContent = `${s.name || s.id} (${s.id}.py)`;
        if (selectedId && s.id === selectedId) opt.selected = true;
        picker.appendChild(opt);
      });
      // Also sync to Text Message script tag dropdown
      const msgScriptSelect = document.getElementById("msg-script-tag-select");
      if (msgScriptSelect) {
        msgScriptSelect.innerHTML = `<option value="">-- Script --</option>`;
        list.forEach(s => {
          const opt = document.createElement("option");
          opt.value = `${s.id}.py`;
          opt.textContent = `${s.id}.py`;
          msgScriptSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error("Failed loading scripts:", e);
    }
  }

  btnLoad.addEventListener("click", async () => {
    const scriptId = picker.value;
    if (!scriptId) return;
    const res = await fetch(`/api/scripts/${scriptId}`);
    if (res.ok) {
      const data = await res.json();
      codeArea.value = data.code;
      scriptNameInput.value = data.id;
    }
  });

  btnTest.addEventListener("click", async () => {
    outputBox.textContent = "Validating and executing...";
    const res = await fetch("/api/scripts/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: codeArea.value })
    });
    const result = await res.json();
    if (result.success) {
      outputBox.innerHTML = `<span class="text-emerald-600 font-semibold">✓ Valid! Result:</span> "${result.output}"`;
    } else {
      outputBox.innerHTML = `<span class="text-red-600 font-semibold">✗ Error:</span> ${result.error}`;
    }
  });

  if (btnCheckSyntax) {
    btnCheckSyntax.addEventListener("click", async () => {
      outputBox.textContent = "Checking Python syntax...";
      const res = await fetch("/api/scripts/check-syntax", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: codeArea.value })
      });
      const result = await res.json();
      if (result.success) {
        outputBox.innerHTML = `<span class="text-emerald-600 font-semibold">✓ ${result.message}</span>`;
      } else {
        outputBox.innerHTML = `<span class="text-red-600 font-semibold">✗ ${result.message}</span>`;
      }
    });
  }

  if (btnFixIndent) {
    btnFixIndent.addEventListener("click", async () => {
      outputBox.textContent = "Checking & fixing indentation...";
      const res = await fetch("/api/scripts/fix-indent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: codeArea.value })
      });
      const result = await res.json();
      if (result.success) {
        if (result.code) {
          codeArea.value = result.code;
        }
        outputBox.innerHTML = `<span class="text-indigo-600 font-semibold">✓ Indentation Normalized (4 spaces):</span> ${result.report}`;
      } else {
        outputBox.innerHTML = `<span class="text-red-600 font-semibold">✗ Error normalizing indentation:</span> ${result.report || 'Unknown error'}`;
      }
    });
  }

  btnSave.addEventListener("click", async () => {
    const rawName = scriptNameInput.value.trim();
    if (!rawName) {
      alert("Please provide a name for the script.");
      return;
    }
    const cleanId = rawName.replace(/\.py$/i, "").toLowerCase().replace(/[^a-z0-9_-]/g, "_");

    const res = await fetch("/api/scripts/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: cleanId,
        name: rawName,
        description: "Dynamic Python text function",
        code: codeArea.value
      })
    });
    const result = await res.json();
    if (result.success) {
      alert(`Script saved successfully as '${cleanId}.py'!`);
      refreshScriptsDropdown(cleanId);
    } else {
      alert(`Error saving script: ${result.error}`);
    }
  });

  if (btnDelete) {
    btnDelete.addEventListener("click", async () => {
      const scriptId = picker.value || scriptNameInput.value.replace(/\.py$/i, "").trim();
      if (!scriptId) {
        alert("Select or load a script to delete.");
        return;
      }
      if (confirm(`Delete script '${scriptId}.py'?`)) {
        await fetch(`/api/scripts/${scriptId}`, { method: "DELETE" });
        refreshScriptsDropdown();
      }
    });
  }

  refreshScriptsDropdown();
}

// BLE Device Scanning & Pairing
function setupBLEControls() {
  const btnScan = document.getElementById("btn-scan-ble");
  const container = document.getElementById("ble-devices-container");

  btnScan.addEventListener("click", async () => {
    container.innerHTML = `<div class="p-4 bg-slate-50 border border-slate-200 rounded-subtle text-center text-xs text-slate-600 flex items-center justify-center gap-2">
      <span class="w-4 h-4 border-2 border-pink-500 border-t-transparent rounded-full animate-spin"></span>
      Scanning for nearby Bluetooth devices (6 seconds)...
    </div>`;

    const res = await fetch("/api/ble/scan");
    const data = await res.json();
    const devices = data.devices || [];

    if (devices.length === 0) {
      container.innerHTML = `<div class="p-4 bg-slate-50 border border-slate-200 rounded-subtle text-center text-xs text-slate-500">
        No Bluetooth devices found in range. Ensure display is powered on.
      </div>`;
      return;
    }

    container.innerHTML = "";
    devices.forEach(dev => {
      const item = document.createElement("div");
      item.className = "flex items-center justify-between p-3 card-3d bg-white";
      item.innerHTML = `
        <div>
          <div class="flex items-center gap-2">
            <span class="font-bold text-sm text-slate-800">${dev.name}</span>
            ${dev.recommended ? '<span class="rainbow-badge text-[10px]">Matrix Matched</span>' : ''}
          </div>
          <div class="text-xs font-mono text-slate-500">${dev.address} • RSSI: ${dev.rssi} dBm</div>
        </div>
        <button class="btn-3d btn-action-rainbow text-xs py-1.5 px-3 font-semibold" onclick="connectToDevice('${dev.address}', '${dev.name}')">
          Connect
        </button>
      `;
      container.appendChild(item);
    });
  });
}

window.connectToDevice = async function (address, name) {
  const res = await fetch("/api/ble/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address, name })
  });
  const data = await res.json();
  if (data.success) {
    alert(`Connected to ${name || address}!`);
    fetchStatus();
  } else {
    const errorMsg = data.status?.status_msg || data.error || "Connection failed";
    alert(`Connection failed: ${errorMsg}`);
    fetchStatus();
  }
};

// IMAGE STUDIO CONTROLLER (CMS, CROP, RESIZE, BG REMOVAL)
function setupImageStudio() {
  const uploadInput = document.getElementById("studio-upload-input");
  const imagesList = document.getElementById("studio-images-list");
  const imageCount = document.getElementById("studio-image-count");
  const btnRefresh = document.getElementById("btn-refresh-images");

  const activeFilenameSpan = document.getElementById("editor-active-filename");
  const saveNameInput = document.getElementById("editor-save-name");
  const btnSaveProcessed = document.getElementById("btn-editor-save");

  const previewImg = document.getElementById("editor-preview-img");
  const placeholder = document.getElementById("editor-placeholder");

  const resizeW = document.getElementById("resize-w");
  const resizeH = document.getElementById("resize-h");
  const resizeAntialias = document.getElementById("resize-antialias");

  const cropX0 = document.getElementById("crop-x0");
  const cropY0 = document.getElementById("crop-y0");
  const cropX1 = document.getElementById("crop-x1");
  const cropY1 = document.getElementById("crop-y1");
  const btnSquareCrop = document.getElementById("btn-crop-square");

  const bgEnable = document.getElementById("bg-remove-enable");
  const bgKeyColor = document.getElementById("bg-key-color");
  const bgTolerance = document.getElementById("bg-tolerance");
  const bgToleranceVal = document.getElementById("bg-tolerance-val");

  const swapEnable = document.getElementById("swap-color-enable");
  const swapSrcColor = document.getElementById("swap-src-color");
  const swapDstColor = document.getElementById("swap-dst-color");
  const swapTolerance = document.getElementById("swap-tolerance");
  const swapToleranceVal = document.getElementById("swap-tolerance-val");

  const btnApply = document.getElementById("btn-editor-apply");
  const btnUndo = document.getElementById("btn-editor-undo");
  const btnRevert = document.getElementById("btn-editor-revert");
  const historyCountSpan = document.getElementById("editor-history-count");
  const statusText = document.getElementById("editor-status-text");

  let activeImage = null;
  let currentWorkingFile = null; // Current cumulative working image file
  let originalImageMeta = null;
  let historyStack = []; // Stack of { workingFile, imageSrc, formState } snapshots

  bgTolerance.addEventListener("input", (e) => {
    bgToleranceVal.textContent = `${e.target.value}%`;
  });

  swapTolerance.addEventListener("input", (e) => {
    swapToleranceVal.textContent = `${e.target.value}%`;
  });

  // Upload handler
  uploadInput.addEventListener("change", async (e) => {
    if (!e.target.files.length) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("/api/images/upload", {
      method: "POST",
      body: formData
    });
    if (res.ok) {
      const data = await res.json();
      await fetchImages();
      selectImageForEditing(data.filename);
    }
  });

  btnRefresh.addEventListener("click", fetchImages);

  async function fetchImages() {
    try {
      const res = await fetch("/api/images");
      const list = await res.json();
      imageCount.textContent = list.length;
      imagesList.innerHTML = "";

      list.forEach(img => {
        const item = document.createElement("div");
        item.className = "card-3d p-2 bg-white flex items-center justify-between gap-2 hover:border-pink-300 transition cursor-pointer";
        item.innerHTML = `
          <div class="flex items-center gap-2 overflow-hidden">
            <img src="/api/images/${img.filename}?t=${Date.now()}" alt="${img.filename}" class="w-8 h-8 object-contain bg-slate-900 rounded p-0.5 border border-slate-700">
            <div class="truncate">
              <p class="text-xs font-bold text-slate-800 font-mono truncate">${img.filename}</p>
              <p class="text-[10px] text-slate-500">${img.width}x${img.height} px</p>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button class="btn-load-img btn-3d btn-load text-xs px-2 py-0.5 font-semibold" title="Edit in Studio">Edit</button>
            <button class="btn-del-img btn-3d btn-del text-xs px-2 py-0.5 font-semibold" title="Delete Image">
              <i data-lucide="trash-2" class="w-3 h-3"></i>
            </button>
          </div>
        `;

        item.querySelector(".btn-load-img").addEventListener("click", (e) => {
          e.stopPropagation();
          selectImageForEditing(img.filename, img);
        });

        item.querySelector(".btn-del-img").addEventListener("click", async (e) => {
          e.stopPropagation();
          if (confirm(`Delete image '${img.filename}'?`)) {
            await fetch(`/api/images/delete?filename=${img.filename}`, { method: "DELETE" });
            fetchImages();
          }
        });

        item.addEventListener("click", () => selectImageForEditing(img.filename, img));
        imagesList.appendChild(item);
      });
    } catch (e) {
      console.error("Failed loading image list:", e);
    }
  }

  function updateHistoryUI() {
    if (historyCountSpan) historyCountSpan.textContent = historyStack.length;
    if (btnUndo) btnUndo.disabled = (historyStack.length === 0);
  }

  function getFormState() {
    return {
      resizeW: resizeW.value,
      resizeH: resizeH.value,
      cropX0: cropX0.value,
      cropY0: cropY0.value,
      cropX1: cropX1.value,
      cropY1: cropY1.value,
      bgEnable: bgEnable.checked,
      bgKeyColor: bgKeyColor.value,
      bgTolerance: bgTolerance.value,
      swapEnable: swapEnable.checked,
      swapSrcColor: swapSrcColor.value,
      swapDstColor: swapDstColor.value,
      swapTolerance: swapTolerance.value,
      resizeAntialias: resizeAntialias.checked
    };
  }

  function restoreFormState(state) {
    if (!state) return;
    resizeW.value = state.resizeW;
    resizeH.value = state.resizeH;
    cropX0.value = state.cropX0;
    cropY0.value = state.cropY0;
    cropX1.value = state.cropX1;
    cropY1.value = state.cropY1;
    bgEnable.checked = state.bgEnable;
    bgKeyColor.value = state.bgKeyColor;
    bgTolerance.value = state.bgTolerance;
    bgToleranceVal.textContent = `${state.bgTolerance}%`;
    swapEnable.checked = state.swapEnable;
    swapSrcColor.value = state.swapSrcColor;
    swapDstColor.value = state.swapDstColor;
    swapTolerance.value = state.swapTolerance;
    swapToleranceVal.textContent = `${state.swapTolerance}%`;
    resizeAntialias.checked = state.resizeAntialias;
  }

  function selectImageForEditing(filename, imgMeta = null) {
    activeImage = filename;
    currentWorkingFile = filename;
    originalImageMeta = imgMeta ? { ...imgMeta } : null;
    historyStack = [];
    updateHistoryUI();

    activeFilenameSpan.textContent = filename;
    saveNameInput.value = filename;

    previewImg.src = `/api/images/${filename}?t=${Date.now()}`;
    previewImg.style.display = "block";
    placeholder.style.display = "none";
    if (statusText) statusText.textContent = `Loaded '${filename}'.`;

    previewImg.onload = () => {
      const containerW = 600;
      const containerH = 320;
      const naturalW = previewImg.naturalWidth || 16;
      const naturalH = previewImg.naturalHeight || 16;

      const scale = Math.min(containerW / naturalW, containerH / naturalH);
      const displayW = Math.round(naturalW * scale);
      const displayH = Math.round(naturalH * scale);

      previewImg.style.width = `${displayW}px`;
      previewImg.style.height = `${displayH}px`;
    };

    if (imgMeta) {
      resizeW.value = imgMeta.width;
      resizeH.value = imgMeta.height;
      cropX0.value = 0;
      cropY0.value = 0;
      cropX1.value = imgMeta.width;
      cropY1.value = imgMeta.height;
    }
  }

  // Apply Adjustments (Strict Layering: operates on currentWorkingFile and stores snapshot in historyStack)
  btnApply.addEventListener("click", async () => {
    if (!currentWorkingFile) {
      alert("Select an image to adjust first.");
      return;
    }

    btnApply.disabled = true;
    btnApply.innerHTML = `<i data-lucide="loader" class="w-3.5 h-3.5 mr-1.5 animate-spin"></i> Processing...`;
    lucide.createIcons();

    // Push current state into history stack before applying new operation
    historyStack.push({
      workingFile: currentWorkingFile,
      imageSrc: previewImg.src,
      formState: getFormState()
    });
    updateHistoryUI();

    const tempOutput = `__temp_layer_${Date.now()}.png`;

    const payload = {
      source_filename: currentWorkingFile, // Layer onto current cumulative working image
      output_filename: tempOutput,
      crop_box: (cropX0.value && cropX1.value && (cropX0.value !== "0" || cropY0.value !== "0" || cropX1.value !== resizeW.value || cropY1.value !== resizeH.value)) ? [
        parseInt(cropX0.value, 10),
        parseInt(cropY0.value, 10),
        parseInt(cropX1.value, 10),
        parseInt(cropY1.value, 10)
      ] : null,
      resize_dim: [parseInt(resizeW.value, 10), parseInt(resizeH.value, 10)],
      remove_bg: bgEnable.checked,
      bg_key_hex: bgKeyColor.value,
      bg_tolerance: parseInt(bgTolerance.value, 10),
      swap_color_enabled: swapEnable.checked,
      swap_src_hex: swapSrcColor.value,
      swap_dst_hex: swapDstColor.value,
      swap_tolerance: parseInt(swapTolerance.value, 10),
      antialias: resizeAntialias.checked,
      is_temporary: true
    };

    try {
      const res = await fetch("/api/images/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        currentWorkingFile = data.image.filename; // Next adjustment layers on top of this!
        previewImg.src = `/api/images/${data.image.filename}?t=${Date.now()}`;

        // Reset transient one-time checkboxes so subsequent clicks apply clean new steps
        bgEnable.checked = false;
        swapEnable.checked = false;

        // Update resize and crop dimensions to new dimensions
        resizeW.value = data.image.width;
        resizeH.value = data.image.height;
        cropX0.value = 0;
        cropY0.value = 0;
        cropX1.value = data.image.width;
        cropY1.value = data.image.height;

        if (statusText) statusText.innerHTML = `<span class="text-emerald-600 font-semibold">✓ Step applied to history!</span> (${historyStack.length} layers). Dimensions: ${data.image.width}x${data.image.height}px.`;
      } else {
        alert("Failed to apply adjustment: " + data.detail);
        historyStack.pop();
        updateHistoryUI();
      }
    } catch (e) {
      alert("Apply failed: " + e.message);
      historyStack.pop();
      updateHistoryUI();
    } finally {
      btnApply.disabled = false;
      btnApply.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5 mr-1.5 text-emerald-400"></i> Apply Adjustments`;
      lucide.createIcons();
    }
  });

  // Undo single step in history
  btnUndo.addEventListener("click", () => {
    if (historyStack.length === 0) return;

    const previousStep = historyStack.pop();
    updateHistoryUI();

    currentWorkingFile = previousStep.workingFile;
    previewImg.src = previousStep.imageSrc;
    restoreFormState(previousStep.formState);
    if (statusText) statusText.textContent = `Undid last step (${historyStack.length} remaining in history).`;
  });

  // Revert all to original image
  btnRevert.addEventListener("click", () => {
    if (!activeImage) return;

    historyStack = [];
    currentWorkingFile = activeImage;
    updateHistoryUI();

    previewImg.src = `/api/images/${activeImage}?t=${Date.now()}`;
    if (originalImageMeta) {
      resizeW.value = originalImageMeta.width;
      resizeH.value = originalImageMeta.height;
      cropX0.value = 0;
      cropY0.value = 0;
      cropX1.value = originalImageMeta.width;
      cropY1.value = originalImageMeta.height;
    }
    bgEnable.checked = false;
    swapEnable.checked = false;
    if (statusText) statusText.textContent = `Reset all adjustments to original image '${activeImage}'.`;
  });

  btnSquareCrop.addEventListener("click", () => {
    const w = parseInt(cropX1.value || resizeW.value, 10);
    const h = parseInt(cropY1.value || resizeH.value, 10);
    const minDim = Math.min(w, h);
    cropX0.value = Math.max(0, Math.floor((w - minDim) / 2));
    cropY0.value = Math.max(0, Math.floor((h - minDim) / 2));
    cropX1.value = parseInt(cropX0.value, 10) + minDim;
    cropY1.value = parseInt(cropY0.value, 10) + minDim;
  });

  // Save Processed Image
  btnSaveProcessed.addEventListener("click", async () => {
    if (!activeImage) {
      alert("Select an image to process first.");
      return;
    }
    const outName = saveNameInput.value.trim() || activeImage;

    const payload = {
      source_filename: currentWorkingFile || activeImage,
      output_filename: outName,
      crop_box: null, // Already cropped in prior layer steps
      resize_dim: [parseInt(resizeW.value, 10), parseInt(resizeH.value, 10)],
      remove_bg: bgEnable.checked,
      bg_key_hex: bgKeyColor.value,
      bg_tolerance: parseInt(bgTolerance.value, 10),
      swap_color_enabled: swapEnable.checked,
      swap_src_hex: swapSrcColor.value,
      swap_dst_hex: swapDstColor.value,
      swap_tolerance: parseInt(swapTolerance.value, 10),
      antialias: resizeAntialias.checked
    };

    try {
      const res = await fetch("/api/images/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        alert(`Saved processed image as '${data.image.filename}'!`);
        await fetchImages();
        selectImageForEditing(data.image.filename);
      } else {
        alert("Processing error: " + data.detail);
      }
    } catch (e) {
      alert("Processing failed: " + e.message);
    }
  });

  fetchImages();
}

// Schedule Table
function renderScheduleTable(slots) {
  const tbody = document.getElementById("schedule-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!slots || !slots.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="p-4 text-center text-slate-400 italic">No scheduled content slots configured. Click "+ Add Slot" above to create one.</td></tr>`;
    return;
  }

  // Sort slots by start_time followed by end_time
  const sortedSlots = [...slots].sort((a, b) => {
    const startComp = (a.start_time || "").localeCompare(b.start_time || "");
    if (startComp !== 0) return startComp;
    return (a.end_time || "").localeCompare(b.end_time || "");
  });

  sortedSlots.forEach((s) => {
    const slotId = s.id || "";
    const tr = document.createElement("tr");
    tr.className = "border-b border-slate-100 hover:bg-slate-50 transition-colors";
    const displayContent = s.config_name || s.config_id || s.content || s.script_id || '-';
    tr.innerHTML = `
      <td class="p-3 font-semibold text-slate-800">${s.name || 'Slot'}</td>
      <td class="p-3 font-mono text-indigo-700 font-semibold">${s.start_time || '00:00'} - ${s.end_time || '00:00'}</td>
      <td class="p-3 uppercase font-mono text-[11px] text-slate-500">${s.type || 'text_message'}</td>
      <td class="p-3 font-mono truncate max-w-xs text-slate-700 font-medium">${displayContent}</td>
      <td class="p-3 text-right">
        <div class="inline-flex items-center gap-1.5">
          <button class="btn-3d btn-load text-xs py-1 px-2.5 rounded inline-flex items-center gap-1 font-semibold cursor-pointer" onclick="editSlot('${slotId}')">
            <i data-lucide="edit-2" class="w-3.5 h-3.5"></i> Edit
          </button>
          <button class="btn-3d btn-del text-xs py-1 px-2.5 rounded inline-flex items-center gap-1 font-semibold cursor-pointer" onclick="removeSlot('${slotId}', '${(s.name || 'Slot').replace(/'/g, "\\'")}')">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i> Delete
          </button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  try {
    if (window.lucide) {
      window.lucide.createIcons();
    }
  } catch (err) {
    console.error("Lucide icon generation error:", err);
  }
}

async function populateScheduleConfigDropdown(selectedId = "") {
  const select = document.getElementById("slot-text-msg-select");
  if (!select) return;
  try {
    const res = await fetch("/api/text-message/configs");
    if (res.ok) {
      const configs = await res.json();
      select.innerHTML = "";
      if (configs.length === 0) {
        select.innerHTML = `<option value="">(No saved text messages found)</option>`;
        return;
      }
      configs.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = `${c.name || c.id} ("${c.text || ''}")`;
        if (selectedId && c.id === selectedId) opt.selected = true;
        select.appendChild(opt);
      });
    }
  } catch (e) {
    console.error("Error populating schedule config dropdown:", e);
  }
}

function setupScheduleControls() {
  populateScheduleConfigDropdown();

  const drawer = document.getElementById("schedule-slot-drawer");
  const drawerTitle = document.getElementById("slot-drawer-title");
  const saveBtnLabel = document.getElementById("slot-btn-save-label");
  const editIdInput = document.getElementById("slot-edit-id");
  const btnToggleDrawer = document.getElementById("btn-toggle-slot-drawer");
  const btnCloseDrawer = document.getElementById("btn-close-slot-drawer");
  const btnCancelSlot = document.getElementById("btn-cancel-slot");
  const btnAddSlot = document.getElementById("btn-add-slot");

  const openDrawer = (isEdit = false) => {
    if (drawer) {
      drawer.classList.remove("hidden");
      if (!isEdit) {
        if (editIdInput) editIdInput.value = "";
        if (drawerTitle) drawerTitle.innerHTML = `<i data-lucide="plus-circle" class="w-3.5 h-3.5 text-pink-600"></i> Create Schedule Slot`;
        if (saveBtnLabel) saveBtnLabel.textContent = "Save Slot";
        document.getElementById("slot-name").value = "";
        document.getElementById("slot-start").value = "08:00";
        document.getElementById("slot-end").value = "12:00";
        populateScheduleConfigDropdown();
      }
      const nameInput = document.getElementById("slot-name");
      if (nameInput) nameInput.focus();
      try { if (window.lucide) window.lucide.createIcons(); } catch (e) { }
    }
  };

  const closeDrawer = () => {
    if (drawer) drawer.classList.add("hidden");
    if (editIdInput) editIdInput.value = "";
  };

  if (btnToggleDrawer) btnToggleDrawer.addEventListener("click", () => openDrawer(false));
  if (btnCloseDrawer) btnCloseDrawer.addEventListener("click", closeDrawer);
  if (btnCancelSlot) btnCancelSlot.addEventListener("click", closeDrawer);

  window.editSlot = async function (slotId) {
    if (!slotId) return;
    const slots = state.config?.schedule?.slots || [];
    const slot = slots.find(s => s.id === slotId);
    if (!slot) return;

    if (editIdInput) editIdInput.value = slot.id;
    if (drawerTitle) drawerTitle.innerHTML = `<i data-lucide="edit-2" class="w-3.5 h-3.5 text-indigo-600"></i> Edit Schedule Slot`;
    if (saveBtnLabel) saveBtnLabel.textContent = "Update Slot";

    document.getElementById("slot-name").value = slot.name || "";
    document.getElementById("slot-start").value = slot.start_time || "08:00";
    document.getElementById("slot-end").value = slot.end_time || "12:00";
    await populateScheduleConfigDropdown(slot.config_id);

    if (drawer) drawer.classList.remove("hidden");
    const nameInput = document.getElementById("slot-name");
    if (nameInput) nameInput.focus();
    try { if (window.lucide) window.lucide.createIcons(); } catch (e) { }
  };

  if (btnAddSlot) {
    btnAddSlot.addEventListener("click", async () => {
      const name = document.getElementById("slot-name").value.trim() || "Slot";
      const start_time = document.getElementById("slot-start").value;
      const end_time = document.getElementById("slot-end").value;
      const select = document.getElementById("slot-text-msg-select");
      const config_id = select ? select.value : "";
      const selectedText = select && select.selectedOptions.length ? select.selectedOptions[0].textContent : config_id;
      const existingId = editIdInput ? editIdInput.value : "";

      if (!config_id) {
        alert("Please select a saved Text Message configuration for this slot.");
        return;
      }

      if (!start_time || !end_time) {
        alert("Please provide both Start Time and End Time.");
        return;
      }

      const slot = {
        id: existingId || ("slot_" + Date.now()),
        name,
        start_time,
        end_time,
        type: "text_message",
        config_id: config_id,
        config_name: selectedText
      };

      try {
        const res = await fetch("/api/schedule/slot", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(slot)
        });
        if (res.ok) {
          const respData = await res.json();
          closeDrawer();
          document.getElementById("slot-name").value = "";
          if (respData && respData.slots) {
            renderScheduleTable(respData.slots);
          }
          await fetchConfig();
        } else {
          alert("Failed to save schedule slot.");
        }
      } catch (err) {
        alert("Error saving slot: " + err.message);
      }
    });
  }

  const schedToggle = document.getElementById("schedule-enable");
  if (schedToggle) {
    schedToggle.addEventListener("change", async (e) => {
      await fetch(`/api/schedule/toggle?enabled=${e.target.checked}`, { method: "POST" });
      fetchConfig();
    });
  }
}

window.removeSlot = async function (slotId, name = "Slot") {
  if (confirm(`Are you sure you want to delete scheduled slot '${name}'?`)) {
    try {
      const res = await fetch(`/api/schedule/slot/${slotId}`, { method: "DELETE" });
      if (res.ok) {
        const respData = await res.json();
        if (respData && respData.slots) {
          renderScheduleTable(respData.slots);
        }
        await fetchConfig();
      } else {
        alert("Failed to delete slot.");
      }
    } catch (e) {
      alert("Error deleting slot: " + e.message);
    }
  }
};

// COMPREHENSIVE EMOJI DATA SET & SEARCH DICTIONARY
const EMOJI_SETS = {
  "food": [
    "🍌",
    "🍆",
    "🥑",
    "🍎",
    "🍏",
    "🍐",
    "🍊",
    "🍋",
    "🍉",
    "🍇",
    "🍓",
    "🫐",
    "🍈",
    "🍒",
    "🍑",
    "🥭",
    "🍍",
    "🥥",
    "🥝",
    "🍅",
    "🫒",
    "🌽",
    "🌶️",
    "🫑",
    "🥒",
    "🥬",
    "🥦",
    "🧄",
    "🧅",
    "🥜",
    "🌰",
    "🍞",
    "🥐",
    "🥖",
    "🫓",
    "🥨",
    "🥯",
    "🥞",
    "🧇",
    "🧀",
    "🍖",
    "🍗",
    "🥩",
    "🥓",
    "🍔",
    "🍟",
    "🍕",
    "🌭",
    "🥪",
    "🌮",
    "🌯",
    "🫔",
    "🥙",
    "🧆",
    "🥚",
    "🍳",
    "🥘",
    "🍲",
    "🫕",
    "🥣",
    "🥗",
    "🍿",
    "🧈",
    "🧂",
    "🥫",
    "🍱",
    "🍘",
    "🍙",
    "🍚",
    "🍛",
    "🍜",
    "🍝",
    "🍠",
    "🍢",
    "🍣",
    "🍤",
    "🍥",
    "🥮",
    "🍡",
    "🥟",
    "🥠",
    "🥡",
    "🍦",
    "🍧",
    "🍨",
    "🍩",
    "🍪",
    "🎂",
    "🍰",
    "🧁",
    "🥧",
    "🍫",
    "🍬",
    "🍭",
    "🍮",
    "🍯",
    "🍼",
    "🥛",
    "☕",
    "🫖",
    "🍵",
    "🍶",
    "🍾",
    "🍷",
    "🍸",
    "🍹",
    "🍺",
    "🍻",
    "🥂",
    "🥃"
  ],
  "smileys": [
    "😀",
    "😃",
    "😄",
    "😁",
    "😆",
    "😅",
    "😂",
    "🤣",
    "😊",
    "😇",
    "🙂",
    "🙃",
    "😉",
    "😌",
    "😍",
    "🥰",
    "😘",
    "😗",
    "😙",
    "😚",
    "😋",
    "😛",
    "😝",
    "😜",
    "🤪",
    "🤨",
    "🧐",
    "🤓",
    "😎",
    "🤩",
    "🥳",
    "😏",
    "😒",
    "😞",
    "😔",
    "😟",
    "😕",
    "🙁",
    "😣",
    "😖",
    "😫",
    "😩",
    "🥺",
    "😢",
    "😭",
    "😤",
    "😠",
    "😡",
    "🤬",
    "🤯",
    "😳",
    "🥵",
    "🥶",
    "😱",
    "😨",
    "😰",
    "😥",
    "😓",
    "🤗",
    "🤔",
    "🤭",
    "🤫",
    "🤥",
    "😶",
    "😐",
    "😑",
    "😬",
    "🙄",
    "😯",
    "😦",
    "😧",
    "😮",
    "😲",
    "🥱",
    "😴",
    "🤤",
    "😪",
    "😵",
    "🤐",
    "🥴",
    "🤢",
    "🤮",
    "🤧",
    "😷",
    "🤒",
    "🤕"
  ],
  "nature": [
    "🐶",
    "🐱",
    "🐭",
    "🐹",
    "🐰",
    "🦊",
    "🐻",
    "🐼",
    "🐨",
    "🐯",
    "🦁",
    "🐮",
    "🐷",
    "🐸",
    "🐵",
    "🐔",
    "🐧",
    "🐦",
    "🦆",
    "🦅",
    "🦉",
    "🦇",
    "🐺",
    "🐗",
    "🐴",
    "🦄",
    "🐝",
    "🐛",
    "🦋",
    "🐌",
    "🐞",
    "🐜",
    "🦟",
    "🦗",
    "🕷️",
    "🦂",
    "🐢",
    "🐍",
    "🦎",
    "🦖",
    "🐙",
    "🦑",
    "🦐",
    "🦞",
    "🦀",
    "🐡",
    "🐠",
    "🐟",
    "🐬",
    "🐳",
    "🦈",
    "🐊",
    "🐅",
    "🐆",
    "🦓",
    "🦍",
    "🦧",
    "🐘",
    "🦛",
    "🦏",
    "🐪",
    "🐫",
    "🦒",
    "🦘",
    "🐃",
    "🐂",
    "🐄",
    "🐎",
    "🐖",
    "🐏",
    "🐑",
    "🦙",
    "🐐",
    "🦌",
    "🐕",
    "🐩",
    "🐈",
    "🐓",
    "🦃",
    "🦚",
    "🦜",
    "🦢",
    "🦩",
    "🕊️",
    "🐇",
    "🦝",
    "🦨",
    "🦡",
    "🦦",
    "🦥",
    "🐁",
    "🐀",
    "🐿️",
    "🦔",
    "🌲",
    "🌳",
    "🌴",
    "🌵",
    "🌶️",
    "🌷",
    "🌸",
    "🌹",
    "🌺",
    "🌻",
    "🌼"
  ],
  "activities": [
    "🔥",
    "✨",
    "🎉",
    "🎊",
    "⚡",
    "💥",
    "⭐",
    "🌟",
    "💫",
    "💯",
    "🏆",
    "🥇",
    "🥈",
    "🥉",
    "⚽",
    "🏀",
    "🏈",
    "⚾",
    "🎾",
    "🎮",
    "🕹️",
    "🎯",
    "🎲",
    "🎸",
    "🎵",
    "🎶",
    "🎤",
    "🎧",
    "🎨",
    "🎬",
    "🎤",
    "🎧",
    "🎼",
    "🎹",
    "🥁",
    "🎷",
    "🎺",
    "🎸",
    "🪕",
    "🎻",
    "🎳",
    "🏓",
    "🏸",
    "🥊",
    "🥋",
    "🥅",
    "⛳",
    "⛸️",
    "🎣",
    "🤿",
    "🎽",
    "🎿",
    "🛷",
    "🥌"
  ],
  "objects": [
    "🚀",
    "✈️",
    "🚗",
    "🏎️",
    "🚲",
    "🛵",
    "🛸",
    "🛰️",
    "⛵",
    "🚢",
    "⚓",
    "💡",
    "💻",
    "📱",
    "⌚",
    "⏰",
    "⏱️",
    "⏳",
    "🔔",
    "📢",
    "📣",
    "💎",
    "🔑",
    "🔒",
    "🔓",
    "🔋",
    "🔌",
    "⚙️",
    "🔧",
    "🔨",
    "📦",
    "📬",
    "📮",
    "🏷️",
    "📌",
    "📍",
    "✂️",
    "🖊️",
    "✏️",
    "📁",
    "📂",
    "💼",
    "📅",
    "📊",
    "📈",
    "📉",
    "📜",
    "💳",
    "💰",
    "🪙",
    "💵"
  ],
  "symbols": [
    "❤️",
    "🧡",
    "💛",
    "💚",
    "💙",
    "💜",
    "🖤",
    "🤍",
    "🤎",
    "💔",
    "❣️",
    "💕",
    "💞",
    "💓",
    "💗",
    "💖",
    "💘",
    "💝",
    "💟",
    "☮️",
    "✝️",
    "☪️",
    "🕉️",
    "☸️",
    "✡️",
    "🔯",
    "🕎",
    "☯️",
    "☦️",
    "🛐",
    "⛎",
    "♈",
    "♉",
    "♊",
    "♋",
    "♌",
    "♍",
    "♎",
    "♏",
    "♐",
    "♑",
    "♒",
    "♓",
    "🆔",
    "⚛️",
    "🉑",
    "☢️",
    "☣️",
    "📴",
    "📳",
    "🈶",
    "🈚",
    "🈸",
    "🈺",
    "🈷️",
    "✴️",
    "❇️",
    "©️",
    "®️",
    "™️",
    "🔟",
    "💯",
    "🔠",
    "🔡",
    "🔢",
    "🔣",
    "🔤",
    "🅰️",
    "🆎",
    "🅱️",
    "🆑",
    "🆒",
    "🆓",
    "ℹ️",
    "🆔",
    "Ⓜ️",
    "🆕",
    "🆖",
    "🅾️",
    "🆗",
    "🅿️",
    "🆘",
    "🆙",
    "🆚"
  ],
  "christmas": [
    "🎄",
    "🎅",
    "🤶",
    "🧑‍🎄",
    "⛄",
    "☃️",
    "❄️",
    "🎁",
    "🔔",
    "🕯️",
    "🦌",
    "🛷",
    "⭐",
    "🌟",
    "✨",
    "🍪",
    "🥛",
    "🍬",
    "🍭",
    "🍫",
    "🎀",
    "🧣",
    "🧤",
    "🧦",
    "🪵",
    "🔥",
    "🎉",
    "🎊",
    "👼",
    "⛪",
    "🍷",
    "🥂",
    "🍾",
    "🥧",
    "🧁",
    "🍰",
    "🪅",
    "🎵",
    "🎶",
    "✝️"
  ]
};

const EMOJI_KEYWORDS = {
  "🍌": "banana banana fruit yellow food monkey potassium",
  "🍆": "aubergine",
  "🥑": "avocado",
  "🍎": "red apple red apple fruit food healthy harvest",
  "🍏": "green apple",
  "🍐": "pear",
  "🍊": "tangerine",
  "🍋": "lemon",
  "🍉": "watermelon",
  "🍇": "grapes",
  "🍓": "strawberry",
  "🫐": "blueberries",
  "🍈": "melon",
  "🍒": "cherries",
  "🍑": "peach",
  "🥭": "mango",
  "🍍": "pineapple",
  "🥥": "coconut",
  "🥝": "kiwifruit",
  "🍅": "tomato",
  "🫒": "olive",
  "🌽": "ear of maize",
  "🌶️": "hot pepper",
  "🫑": "bell pepper",
  "🥒": "cucumber",
  "🥬": "leafy green",
  "🥦": "broccoli",
  "🧄": "garlic",
  "🧅": "onion",
  "🥜": "peanuts",
  "🌰": "chestnut",
  "🍞": "bread",
  "🥐": "croissant",
  "🥖": "baguette bread",
  "🫓": "flatbread",
  "🥨": "pretzel",
  "🥯": "bagel",
  "🥞": "pancakes",
  "🧇": "waffle",
  "🧀": "cheese wedge",
  "🍖": "meat on bone",
  "🍗": "poultry leg",
  "🥩": "cut of meat",
  "🥓": "bacon",
  "🍔": "hamburger burger hamburger cheeseburger fast food beef grill",
  "🍟": "french fries fries french fries potato fast food snack",
  "🍕": "slice of pizza pizza slice pie cheese pepperoni italian food",
  "🌭": "hot dog",
  "🥪": "sandwich",
  "🌮": "taco",
  "🌯": "burrito",
  "🫔": "tamale",
  "🥙": "stuffed flatbread",
  "🧆": "falafel",
  "🥚": "egg",
  "🍳": "cooking",
  "🥘": "shallow pan of food",
  "🍲": "pot of food",
  "🫕": "fondue",
  "🥣": "bowl with spoon",
  "🥗": "green salad",
  "🍿": "popcorn",
  "🧈": "butter",
  "🧂": "salt shaker",
  "🥫": "canned food",
  "🍱": "bento box",
  "🍘": "rice cracker",
  "🍙": "rice ball",
  "🍚": "cooked rice",
  "🍛": "curry and rice",
  "🍜": "steaming bowl",
  "🍝": "spaghetti",
  "🍠": "roasted sweet potato",
  "🍢": "oden",
  "🍣": "sushi",
  "🍤": "fried shrimp",
  "🍥": "fish cake with swirl design",
  "🥮": "moon cake",
  "🍡": "dango",
  "🥟": "dumpling",
  "🥠": "fortune cookie",
  "🥡": "takeout box",
  "🍦": "soft ice cream",
  "🍧": "shaved ice",
  "🍨": "ice cream",
  "🍩": "doughnut",
  "🍪": "cookie cookie gingerbread biscuit snack treat food christmas",
  "🎂": "birthday cake",
  "🍰": "shortcake cake shortcake sweet slice dessert celebration birthday",
  "🧁": "cupcake cupcake dessert sweet treat cake bakery",
  "🥧": "pie pie mince pie holiday food dessert pastry",
  "🍫": "chocolate bar chocolate bar candy sweet food dessert",
  "🍬": "candy candy sweet sugar treat christmas candy cane",
  "🍭": "lollipop lollipop sweet candy sugar treat sucker",
  "🍮": "custard",
  "🍯": "honey pot",
  "🍼": "baby bottle",
  "🥛": "glass of milk milk glass of milk drink dairy santa",
  "☕": "hot beverage coffee hot drink tea cup mug cafe espresso",
  "🫖": "teapot",
  "🍵": "teacup without handle",
  "🍶": "sake bottle and cup",
  "🍾": "bottle with popping cork bottle popping cork champagne prosecco celebration new year drink",
  "🍷": "wine glass wine glass red wine drink alcohol celebration cheer",
  "🍸": "cocktail glass",
  "🍹": "tropical drink",
  "🍺": "beer mug",
  "🍻": "clinking beer mugs",
  "🥂": "clinking glasses clinking glasses champagne toast cheers celebration party",
  "🥃": "tumbler glass",
  "😀": "grinning face grinning face happy smile laugh smiley beaming",
  "😃": "smiling face with open mouth",
  "😄": "smiling face with open mouth and smiling eyes",
  "😁": "grinning face with smiling eyes",
  "😆": "smiling face with open mouth and tightly-closed eyes",
  "😅": "smiling face with open mouth and cold sweat",
  "😂": "face with tears of joy",
  "🤣": "rolling on the floor laughing",
  "😊": "smiling face with smiling eyes",
  "😇": "smiling face with halo",
  "🙂": "slightly smiling face",
  "🙃": "upside-down face",
  "😉": "winking face",
  "😌": "relieved face",
  "😍": "smiling face with heart-shaped eyes",
  "🥰": "smiling face with smiling eyes and three hearts",
  "😘": "face throwing a kiss",
  "😗": "kissing face",
  "😙": "kissing face with smiling eyes",
  "😚": "kissing face with closed eyes",
  "😋": "face savouring delicious food",
  "😛": "face with stuck-out tongue",
  "😝": "face with stuck-out tongue and tightly-closed eyes",
  "😜": "face with stuck-out tongue and winking eye",
  "🤪": "grinning face with one large and one small eye",
  "🤨": "face with one eyebrow raised",
  "🧐": "face with monocle",
  "🤓": "nerd face",
  "😎": "smiling face with sunglasses",
  "🤩": "grinning face with star eyes",
  "🥳": "face with party horn and party hat",
  "😏": "smirking face",
  "😒": "unamused face",
  "😞": "disappointed face",
  "😔": "pensive face",
  "😟": "worried face",
  "😕": "confused face",
  "🙁": "slightly frowning face",
  "😣": "persevering face",
  "😖": "confounded face",
  "😫": "tired face",
  "😩": "weary face",
  "🥺": "face with pleading eyes",
  "😢": "crying face",
  "😭": "loudly crying face",
  "😤": "face with look of triumph",
  "😠": "angry face",
  "😡": "pouting face",
  "🤬": "serious face with symbols covering mouth",
  "🤯": "shocked face with exploding head",
  "😳": "flushed face",
  "🥵": "overheated face",
  "🥶": "freezing face",
  "😱": "face screaming in fear",
  "😨": "fearful face",
  "😰": "face with open mouth and cold sweat",
  "😥": "disappointed but relieved face",
  "😓": "face with cold sweat",
  "🤗": "hugging face",
  "🤔": "thinking face",
  "🤭": "smiling face with smiling eyes and hand covering mouth",
  "🤫": "face with finger covering closed lips",
  "🤥": "lying face",
  "😶": "face without mouth",
  "😐": "neutral face",
  "😑": "expressionless face",
  "😬": "grimacing face",
  "🙄": "face with rolling eyes",
  "😯": "hushed face",
  "😦": "frowning face with open mouth",
  "😧": "anguished face",
  "😮": "face with open mouth",
  "😲": "astonished face",
  "🥱": "yawning face",
  "😴": "sleeping face",
  "🤤": "drooling face",
  "😪": "sleepy face",
  "😵": "dizzy face",
  "🤐": "zipper-mouth face",
  "🥴": "face with uneven eyes and wavy mouth",
  "🤢": "nauseated face",
  "🤮": "face with open mouth vomiting",
  "🤧": "sneezing face",
  "😷": "face with medical mask",
  "🤒": "face with thermometer",
  "🤕": "face with head-bandage",
  "🐶": "dog face",
  "🐱": "cat face",
  "🐭": "mouse face",
  "🐹": "hamster face",
  "🐰": "rabbit face",
  "🦊": "fox face",
  "🐻": "bear face",
  "🐼": "panda face",
  "🐨": "koala",
  "🐯": "tiger face",
  "🦁": "lion face",
  "🐮": "cow face",
  "🐷": "pig face",
  "🐸": "frog face",
  "🐵": "monkey face",
  "🐔": "chicken",
  "🐧": "penguin",
  "🐦": "bird",
  "🦆": "duck",
  "🦅": "eagle",
  "🦉": "owl",
  "🦇": "bat",
  "🐺": "wolf face",
  "🐗": "boar",
  "🐴": "horse face",
  "🦄": "unicorn face",
  "🐝": "honeybee",
  "🐛": "bug",
  "🦋": "butterfly",
  "🐌": "snail",
  "🐞": "lady beetle",
  "🐜": "ant",
  "🦟": "mosquito",
  "🦗": "cricket",
  "🕷️": "spider",
  "🦂": "scorpion",
  "🐢": "turtle",
  "🐍": "snake",
  "🦎": "lizard",
  "🦖": "t-rex",
  "🐙": "octopus",
  "🦑": "squid",
  "🦐": "shrimp",
  "🦞": "lobster",
  "🦀": "crab",
  "🐡": "blowfish",
  "🐠": "tropical fish",
  "🐟": "fish",
  "🐬": "dolphin",
  "🐳": "spouting whale",
  "🦈": "shark",
  "🐊": "crocodile",
  "🐅": "tiger",
  "🐆": "leopard",
  "🦓": "zebra face",
  "🦍": "gorilla",
  "🦧": "orangutan",
  "🐘": "elephant",
  "🦛": "hippopotamus",
  "🦏": "rhinoceros",
  "🐪": "dromedary camel",
  "🐫": "bactrian camel",
  "🦒": "giraffe face",
  "🦘": "kangaroo",
  "🐃": "water buffalo",
  "🐂": "ox",
  "🐄": "cow",
  "🐎": "horse",
  "🐖": "pig",
  "🐏": "ram",
  "🐑": "sheep",
  "🦙": "llama",
  "🐐": "goat",
  "🦌": "deer deer reindeer rudolph buck caribou stag",
  "🐕": "dog",
  "🐩": "poodle",
  "🐈": "cat",
  "🐓": "rooster",
  "🦃": "turkey",
  "🦚": "peacock",
  "🦜": "parrot",
  "🦢": "swan",
  "🦩": "flamingo",
  "🕊️": "dove of peace",
  "🐇": "rabbit",
  "🦝": "raccoon",
  "🦨": "skunk",
  "🦡": "badger",
  "🦦": "otter",
  "🦥": "sloth",
  "🐁": "mouse",
  "🐀": "rat",
  "🐿️": "chipmunk",
  "🦔": "hedgehog",
  "🌲": "evergreen tree",
  "🌳": "deciduous tree",
  "🌴": "palm tree",
  "🌵": "cactus",
  "🌷": "tulip",
  "🌸": "cherry blossom",
  "🌹": "rose",
  "🌺": "hibiscus",
  "🌻": "sunflower",
  "🌼": "blossom",
  "🔥": "fire fire flame fireplace hearth warm campfire lit hot blaze",
  "✨": "sparkles sparkles sparkle magic celebration glitter shine",
  "🎉": "party popper party popper celebration tinsel confetti celebrate congrats new year holiday",
  "🎊": "confetti ball confetti ball celebration party fiesta celebrate",
  "⚡": "high voltage sign",
  "💥": "collision symbol",
  "⭐": "white medium star star christmas star gold yellow",
  "🌟": "glowing star glowing star sparkle shining bright nativity",
  "💫": "dizzy symbol",
  "💯": "hundred points symbol",
  "🏆": "trophy",
  "🥇": "first place medal",
  "🥈": "second place medal",
  "🥉": "third place medal",
  "⚽": "soccer ball",
  "🏀": "basketball and hoop",
  "🏈": "american football",
  "⚾": "baseball",
  "🎾": "tennis racquet and ball",
  "🎮": "video game",
  "🕹️": "joystick",
  "🎯": "direct hit",
  "🎲": "game die",
  "🎸": "guitar",
  "🎵": "musical note musical note carol song music sing",
  "🎶": "multiple musical notes musical notes carols songs music choir singing",
  "🎤": "microphone",
  "🎧": "headphone",
  "🎨": "artist palette",
  "🎬": "clapper board",
  "🎼": "musical score",
  "🎹": "musical keyboard",
  "🥁": "drum with drumsticks",
  "🎷": "saxophone",
  "🎺": "trumpet",
  "🪕": "banjo",
  "🎻": "violin",
  "🎳": "bowling",
  "🏓": "table tennis paddle and ball",
  "🏸": "badminton racquet and shuttlecock",
  "🥊": "boxing glove",
  "🥋": "martial arts uniform",
  "🥅": "goal net",
  "⛳": "flag in hole",
  "⛸️": "ice skate",
  "🎣": "fishing pole and fish",
  "🤿": "diving mask",
  "🎽": "running shirt with sash",
  "🎿": "ski and ski boot",
  "🛷": "sled sled sleigh snow toboggan winter ride",
  "🥌": "curling stone",
  "🚀": "rocket",
  "✈️": "airplane",
  "🚗": "automobile",
  "🏎️": "racing car",
  "🚲": "bicycle",
  "🛵": "motor scooter",
  "🛸": "flying saucer",
  "🛰️": "satellite",
  "⛵": "sailboat",
  "🚢": "ship",
  "⚓": "anchor",
  "💡": "electric light bulb",
  "💻": "personal computer",
  "📱": "mobile phone",
  "⌚": "watch",
  "⏰": "alarm clock",
  "⏱️": "stopwatch",
  "⏳": "hourglass with flowing sand",
  "🔔": "bell bell jingle bells chimes ring christmas chime",
  "📢": "public address loudspeaker",
  "📣": "cheering megaphone",
  "💎": "gem stone",
  "🔑": "key",
  "🔒": "lock",
  "🔓": "open lock",
  "🔋": "battery",
  "🔌": "electric plug",
  "⚙️": "gear",
  "🔧": "wrench",
  "🔨": "hammer",
  "📦": "package",
  "📬": "open mailbox with raised flag",
  "📮": "postbox",
  "🏷️": "label",
  "📌": "pushpin",
  "📍": "round pushpin",
  "✂️": "black scissors",
  "🖊️": "lower left ballpoint pen",
  "✏️": "pencil",
  "📁": "file folder",
  "📂": "open file folder",
  "💼": "briefcase",
  "📅": "calendar",
  "📊": "bar chart",
  "📈": "chart with upwards trend",
  "📉": "chart with downwards trend",
  "📜": "scroll",
  "💳": "credit card",
  "💰": "money bag",
  "🪙": "coin",
  "💵": "banknote with dollar sign",
  "❤️": "heavy black heart red heart love like romance valentine affection",
  "🧡": "orange heart",
  "💛": "yellow heart",
  "💚": "green heart",
  "💙": "blue heart",
  "💜": "purple heart",
  "🖤": "black heart",
  "🤍": "white heart",
  "🤎": "brown heart",
  "💔": "broken heart",
  "❣️": "heavy heart exclamation mark ornament",
  "💕": "two hearts",
  "💞": "revolving hearts",
  "💓": "beating heart",
  "💗": "growing heart",
  "💖": "sparkling heart",
  "💘": "heart with arrow",
  "💝": "heart with ribbon",
  "💟": "heart decoration",
  "☮️": "peace symbol",
  "✝️": "latin cross cross latin cross christianity jesus nativity faith holy",
  "☪️": "star and crescent",
  "🕉️": "om symbol",
  "☸️": "wheel of dharma",
  "✡️": "star of david",
  "🔯": "six pointed star with middle dot",
  "🕎": "menorah with nine branches",
  "☯️": "yin yang",
  "☦️": "orthodox cross",
  "🛐": "place of worship",
  "⛎": "ophiuchus",
  "♈": "aries",
  "♉": "taurus",
  "♊": "gemini",
  "♋": "cancer",
  "♌": "leo",
  "♍": "virgo",
  "♎": "libra",
  "♏": "scorpius",
  "♐": "sagittarius",
  "♑": "capricorn",
  "♒": "aquarius",
  "♓": "pisces",
  "🆔": "squared id",
  "⚛️": "atom symbol",
  "🉑": "circled ideograph accept",
  "☢️": "radioactive sign",
  "☣️": "biohazard sign",
  "📴": "mobile phone off",
  "📳": "vibration mode",
  "🈶": "squared cjk unified ideograph-6709",
  "🈚": "squared cjk unified ideograph-7121",
  "🈸": "squared cjk unified ideograph-7533",
  "🈺": "squared cjk unified ideograph-55b6",
  "🈷️": "squared cjk unified ideograph-6708",
  "✴️": "eight pointed black star",
  "❇️": "sparkle",
  "©️": "copyright sign",
  "®️": "registered sign",
  "™️": "trade mark sign",
  "🔟": "keycap ten",
  "🔠": "input symbol for latin capital letters",
  "🔡": "input symbol for latin small letters",
  "🔢": "input symbol for numbers",
  "🔣": "input symbol for symbols",
  "🔤": "input symbol for latin letters",
  "🅰️": "negative squared latin capital letter a",
  "🆎": "negative squared ab",
  "🅱️": "negative squared latin capital letter b",
  "🆑": "squared cl",
  "🆒": "squared cool",
  "🆓": "squared free",
  "ℹ️": "information source",
  "Ⓜ️": "circled latin capital letter m",
  "🆕": "squared new",
  "🆖": "squared ng",
  "🅾️": "negative squared latin capital letter o",
  "🆗": "squared ok",
  "🅿️": "negative squared latin capital letter p",
  "🆘": "squared sos",
  "🆙": "squared up with exclamation mark",
  "🆚": "squared vs",
  "🎄": "christmas tree christmas tree xmas holiday pine evergreen fir noel yule",
  "🎅": "father christmas santa claus saint nick father christmas xmas noel yule",
  "🤶": "mother christmas mrs claus mother christmas xmas noel",
  "🧑‍🎄": "adult christmas tree santa mx claus xmas noel",
  "⛄": "snowman without snow snowman winter frost snow cold frosty",
  "☃️": "snowman snowman snow winter frosty cold",
  "❄️": "snowflake snowflake cold ice snow winter freeze flurry blizzard",
  "🎁": "wrapped present gift present box wrapped christmas surprise package birthday holiday",
  "🕯️": "candle candle light advent flame wax burn",
  "🎀": "ribbon ribbon bow decoration gift wrapping present pink holiday",
  "🧣": "scarf scarf winter cold warm clothing neck warmer",
  "🧤": "gloves gloves mittens winter clothing warm hands",
  "🧦": "socks socks stocking christmas stocking warm clothing",
  "🪵": "wood wood log yule log fireplace hearth fire timber",
  "👼": "baby angel angel cherub nativity baby halo heavenly",
  "⛪": "church church cathedral chapel nativity christmas eve building",
  "🪅": "pinata pinata celebration party fiesta festive"
};

// TEXT MESSAGE STUDIO CONTROLLER
function setupTextMessageStudio() {
  const textInput = document.getElementById("msg-text-input");
  const configNameInput = document.getElementById("msg-config-name");
  const fontSelect = document.getElementById("msg-font-family");
  const fontSizeInput = document.getElementById("msg-font-size");
  const antialiasCheckbox = document.getElementById("msg-antialias");
  const textColorInput = document.getElementById("msg-text-color");
  const bgColorInput = document.getElementById("msg-bg-color");
  const previewImg = document.getElementById("msg-rendered-preview-img");
  const widthBadge = document.getElementById("msg-width-badge");
  const fitWarning = document.getElementById("msg-fit-warning");

  const btnSaveConfig = document.getElementById("btn-save-msg-config");
  const btnSendMatrix = document.getElementById("btn-send-msg-matrix");
  const configPicker = document.getElementById("saved-msg-configs");
  const btnLoadConfig = document.getElementById("btn-load-msg-config");
  const btnDeleteConfig = document.getElementById("btn-delete-msg-config");

  const imageTagSelect = document.getElementById("msg-image-tag-select");
  const btnInsertTag = document.getElementById("btn-insert-image-tag");
  const scriptTagSelect = document.getElementById("msg-script-tag-select");
  const btnInsertScriptTag = document.getElementById("btn-insert-script-tag");
  const refreshIntervalInput = document.getElementById("msg-refresh-interval");
  const refreshValSpan = document.getElementById("msg-refresh-val");
  const emojiSearch = document.getElementById("emoji-search-input");

  // Horizontal Scrolling Controls
  const scrollEnabledCheckbox = document.getElementById("msg-scroll-enabled");
  const frameSkipToggleContainer = document.getElementById("container-frame-skip-toggle");
  const frameSkipCheckbox = document.getElementById("msg-frame-skip-enabled");
  const blurToggleContainer = document.getElementById("container-blur-toggle");
  const blurCheckbox = document.getElementById("msg-blur-enabled");
  const scrollRateContainer = document.getElementById("scroll-rate-container");
  const containerScrollSpeed = document.getElementById("container-scroll-speed");
  const containerFrameSkipStep = document.getElementById("container-frame-skip-step");
  const scrollSpeedInput = document.getElementById("msg-scroll-speed");
  const frameSkipStepInput = document.getElementById("msg-frame-skip-step");
  const scrollDirContainer = document.getElementById("scroll-direction-container");
  const btnScrollRtl = document.getElementById("btn-scroll-rtl");
  const btnScrollLtr = document.getElementById("btn-scroll-ltr");

  function syncScrollUiVisibility() {
    const isScrolling = scrollEnabledCheckbox ? scrollEnabledCheckbox.checked : false;
    const isFrameSkip = frameSkipCheckbox ? frameSkipCheckbox.checked : false;

    if (frameSkipToggleContainer) {
      if (isScrolling) frameSkipToggleContainer.classList.remove("hidden");
      else frameSkipToggleContainer.classList.add("hidden");
    }
    if (blurToggleContainer) {
      if (isScrolling && isFrameSkip) blurToggleContainer.classList.remove("hidden");
      else blurToggleContainer.classList.add("hidden");
    }
    if (scrollRateContainer) {
      if (isScrolling) scrollRateContainer.classList.remove("hidden");
      else scrollRateContainer.classList.add("hidden");
    }
    if (scrollDirContainer) {
      if (isScrolling) scrollDirContainer.classList.remove("hidden");
      else scrollDirContainer.classList.add("hidden");
    }

    if (isScrolling) {
      if (isFrameSkip) {
        if (containerScrollSpeed) containerScrollSpeed.classList.add("hidden");
        if (containerFrameSkipStep) containerFrameSkipStep.classList.remove("hidden");
      } else {
        if (containerScrollSpeed) containerScrollSpeed.classList.remove("hidden");
        if (containerFrameSkipStep) containerFrameSkipStep.classList.add("hidden");
      }
    }
  }

  let currentAlignment = "center";
  let currentVAlignment = "middle";
  let currentScrollDirection = "rtl";
  let currentCategory = "christmas";
  let livePreviewTimer = null;
  let bottomPreviewCanvas = null;
  let bottomPreviewAnimFrame = null;

  if (refreshIntervalInput) {
    refreshIntervalInput.addEventListener("input", (e) => {
      const val = parseInt(e.target.value, 10) || 0;
      if (refreshValSpan) {
        refreshValSpan.textContent = val > 0 ? `Every ${val}s` : "";
      }
      setupLivePreviewTimer(val);
    });
  }

  function setupLivePreviewTimer(seconds) {
    if (livePreviewTimer) clearInterval(livePreviewTimer);
    if (seconds > 0) {
      livePreviewTimer = setInterval(() => {
        // Automatically re-render preview if message contains dynamic scripts
        if (textInput.value.includes(".py>")) {
          fetchRenderedPreview();
        }
      }, seconds * 1000);
    }
  }

  // Emoji Canvas Population
  const emojiGrid = document.getElementById("emoji-canvas-grid");
  function loadEmojiCategory(cat, query = "") {
    emojiGrid.innerHTML = "";
    let list = [];
    const q = (query || "").trim().toLowerCase();

    if (q) {
      // Search across all unique emojis using name & keyword index
      const allUnique = Array.from(new Set(Object.values(EMOJI_SETS).flat()));
      list = allUnique.filter(emoji => {
        const kw = (EMOJI_KEYWORDS[emoji] || "").toLowerCase();
        return kw.includes(q) || emoji === q;
      });

      if (list.length === 0) {
        emojiGrid.innerHTML = `<div class="p-4 text-xs text-slate-400 w-full text-center">No emojis matching "${query}"</div>`;
        return;
      }
    } else {
      list = EMOJI_SETS[cat] || EMOJI_SETS.christmas || EMOJI_SETS.smileys;
    }

    list.forEach(emoji => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "w-12 h-12 text-2xl flex items-center justify-center hover:bg-white rounded transition hover:scale-110 select-none shadow-xs";
      btn.textContent = emoji;
      btn.title = EMOJI_KEYWORDS[emoji] || emoji;
      btn.addEventListener("click", () => {
        const start = textInput.selectionStart;
        const end = textInput.selectionEnd;
        const val = textInput.value;
        textInput.value = val.substring(0, start) + emoji + val.substring(end);
        textInput.selectionStart = textInput.selectionEnd = start + emoji.length;
        textInput.focus();
        triggerPreview();
      });
      emojiGrid.appendChild(btn);
    });
  }

  // Emoji category buttons
  document.querySelectorAll(".emoji-cat-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".emoji-cat-btn").forEach(b => {
        b.className = "emoji-cat-btn px-1.5 py-0.5 rounded text-slate-600 hover:bg-slate-100";
      });
      btn.className = "emoji-cat-btn px-1.5 py-0.5 rounded bg-pink-100 text-pink-700 font-semibold";
      currentCategory = btn.dataset.cat;
      if (emojiSearch) emojiSearch.value = "";
      loadEmojiCategory(currentCategory);
    });
  });

  if (emojiSearch) {
    emojiSearch.addEventListener("input", (e) => {
      const q = e.target.value.trim();
      loadEmojiCategory(currentCategory, q);
    });
  }

  loadEmojiCategory("christmas");

  // Populate Image Tag Selector
  async function refreshImageTagDropdown() {
    try {
      const res = await fetch("/api/images");
      const list = await res.json();
      imageTagSelect.innerHTML = `<option value="">-- Choose Image --</option>`;
      list.forEach(img => {
        const opt = document.createElement("option");
        opt.value = img.filename;
        opt.textContent = `${img.filename} (${img.width}x${img.height})`;
        imageTagSelect.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed to load images for tags:", e);
    }
  }

  btnInsertTag.addEventListener("click", () => {
    const val = imageTagSelect.value;
    if (!val) return;
    const tag = `<${val}>`;
    const start = textInput.selectionStart;
    const end = textInput.selectionEnd;
    const currentText = textInput.value;
    textInput.value = currentText.substring(0, start) + tag + currentText.substring(end);
    textInput.selectionStart = textInput.selectionEnd = start + tag.length;
    textInput.focus();
    triggerPreview();
  });

  if (btnInsertScriptTag) {
    btnInsertScriptTag.addEventListener("click", () => {
      const val = scriptTagSelect.value;
      if (!val) return;
      const tag = `<${val}>`;
      const start = textInput.selectionStart;
      const end = textInput.selectionEnd;
      const currentText = textInput.value;
      textInput.value = currentText.substring(0, start) + tag + currentText.substring(end);
      textInput.selectionStart = textInput.selectionEnd = start + tag.length;
      textInput.focus();
      triggerPreview();
    });
  }

  // Alignment buttons
  document.querySelectorAll(".btn-alignment").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-alignment").forEach(b => {
        b.className = "btn-alignment btn-3d bg-white text-slate-700 text-xs py-1 px-1.5 border";
      });
      btn.className = "btn-alignment btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-1 px-1.5";
      currentAlignment = btn.dataset.align;
      triggerPreview();
    });
  });

  // Scroll direction toggles
  if (btnScrollRtl && btnScrollLtr) {
    btnScrollRtl.addEventListener("click", () => {
      currentScrollDirection = "rtl";
      btnScrollRtl.className = "btn-scroll-dir btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-0.5 px-2 text-center";
      btnScrollLtr.className = "btn-scroll-dir btn-3d bg-white text-slate-700 border-slate-200 text-xs py-0.5 px-2 text-center";
      state.scrolling.direction = "rtl";
      triggerPreview();
    });
    btnScrollLtr.addEventListener("click", () => {
      currentScrollDirection = "ltr";
      btnScrollLtr.className = "btn-scroll-dir btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-0.5 px-2 text-center";
      btnScrollRtl.className = "btn-scroll-dir btn-3d bg-white text-slate-700 border-slate-200 text-xs py-0.5 px-2 text-center";
      state.scrolling.direction = "ltr";
      triggerPreview();
    });
  }

  if (scrollEnabledCheckbox) {
    scrollEnabledCheckbox.addEventListener("change", () => {
      state.scrolling.enabled = scrollEnabledCheckbox.checked;
      syncScrollUiVisibility();
      triggerPreview();
    });
  }

  if (frameSkipCheckbox) {
    frameSkipCheckbox.addEventListener("change", () => {
      state.scrolling.frameSkip = frameSkipCheckbox.checked;
      syncScrollUiVisibility();
      triggerPreview();
    });
  }

  if (blurCheckbox) {
    blurCheckbox.addEventListener("change", () => {
      state.scrolling.blur = blurCheckbox.checked;
      triggerPreview();
    });
  }

  if (frameSkipStepInput) {
    frameSkipStepInput.addEventListener("input", () => {
      state.scrolling.frameSkipStep = Math.max(1, parseInt(frameSkipStepInput.value, 10) || 1);
    });
  }

  if (scrollSpeedInput) {
    scrollSpeedInput.addEventListener("input", () => {
      const spd = Math.max(10, parseInt(scrollSpeedInput.value, 10) || 80);
      state.scrolling.speed = spd;
    });
  }

  // Vertical alignment buttons
  document.querySelectorAll(".btn-valign").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-valign").forEach(b => {
        b.className = "btn-valign btn-3d bg-white text-slate-700 text-xs py-1 px-1.5 border";
      });
      btn.className = "btn-valign btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-1 px-1.5";
      currentVAlignment = btn.dataset.valign;
      triggerPreview();
    });
  });

  // Debounced live preview fetch
  let previewTimeout = null;
  function triggerPreview() {
    clearTimeout(previewTimeout);
    previewTimeout = setTimeout(fetchRenderedPreview, 120);
  }

  // Animate bottom-right preview when scrolling is active
  let bottomPreviewOffset = 0;
  let bottomPreviewLastTime = 0;
  let bottomFullImg = null;

  function runBottomPreviewLoop() {
    if (bottomPreviewAnimFrame) cancelAnimationFrame(bottomPreviewAnimFrame);

    function stepPreview(time) {
      if (!state.scrolling.enabled || !bottomFullImg) {
        return;
      }
      const speed = Math.max(80, state.scrolling.speed || 80);
      if (!bottomPreviewLastTime) bottomPreviewLastTime = time;
      const elapsed = time - bottomPreviewLastTime;

      if (elapsed >= speed) {
        const spacer = 24;
        const loopUnit = Math.max(96, bottomFullImg.width) + spacer;
        const steps = Math.max(1, Math.round(elapsed / speed));
        bottomPreviewLastTime = time;

        if (state.scrolling.direction === "rtl") {
          bottomPreviewOffset = (bottomPreviewOffset + steps) % loopUnit;
        } else {
          bottomPreviewOffset = (bottomPreviewOffset - steps + loopUnit) % loopUnit;
        }

        // Draw slice onto hidden 96x16 canvas and set previewImg.src
        if (!bottomPreviewCanvas) {
          bottomPreviewCanvas = document.createElement("canvas");
          bottomPreviewCanvas.width = 96;
          bottomPreviewCanvas.height = 16;
        }
        const bCtx = bottomPreviewCanvas.getContext("2d");
        bCtx.fillStyle = bgColorInput.value || "#000000";
        bCtx.fillRect(0, 0, 96, 16);

        const curX = Math.floor(bottomPreviewOffset);
        // Draw primary instance
        bCtx.drawImage(bottomFullImg, -curX, 0);
        // Draw secondary instance for continuous wrap
        bCtx.drawImage(bottomFullImg, loopUnit - curX, 0);

        previewImg.src = bottomPreviewCanvas.toDataURL("image/png");
      }
      bottomPreviewAnimFrame = requestAnimationFrame(stepPreview);
    }
    bottomPreviewAnimFrame = requestAnimationFrame(stepPreview);
  }

  async function fetchRenderedPreview() {
    const isScrolling = scrollEnabledCheckbox ? scrollEnabledCheckbox.checked : false;
    const isFrameSkip = frameSkipCheckbox ? frameSkipCheckbox.checked : false;
    const isBlur = blurCheckbox ? blurCheckbox.checked : false;
    const skipStep = frameSkipStepInput ? Math.max(1, parseInt(frameSkipStepInput.value, 10) || 1) : 1;
    const scrollSpd = scrollSpeedInput ? Math.max(10, parseInt(scrollSpeedInput.value, 10) || 80) : 80;

    const payload = {
      name: configNameInput.value.trim() || "untitled",
      text: textInput.value || " ",
      font_id: fontSelect.value,
      font_size: parseInt(fontSizeInput.value, 10) || 8,
      text_color: textColorInput.value,
      bg_color: bgColorInput.value,
      alignment: currentAlignment,
      v_alignment: currentVAlignment,
      antialias: antialiasCheckbox.checked,
      scroll_enabled: isScrolling,
      scroll_direction: currentScrollDirection,
      scroll_speed: scrollSpd,
      frame_skip_enabled: isFrameSkip,
      frame_skip_step: skipStep,
      blur_enabled: isBlur
    };

    try {
      const res = await fetch("/api/text-message/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        widthBadge.textContent = `Width: ${data.content_width} / 96 px`;

        // Sync to state
        state.scrolling.enabled = isScrolling;
        state.scrolling.direction = currentScrollDirection;
        state.scrolling.speed = scrollSpd;

        // Sync to top hardware simulator
        state.previewMode = "bitmap";
        state.previewBitmap = data.pixels;
        const modeTag = document.getElementById("preview-mode-tag");
        if (modeTag) modeTag.textContent = "";
        const renderInfo = document.getElementById("preview-render-info");
        if (renderInfo) renderInfo.textContent = "";

        if (isScrolling) {
          widthBadge.className = "rainbow-badge text-[10px]";
          fitWarning.className = "text-[11px] text-pink-600 mt-1 font-semibold";
          fitWarning.textContent = `⇄ Scrolling Active (${data.content_width}px message loops seamlessly)`;

          // Setup bottom preview animation
          bottomFullImg = new Image();
          bottomFullImg.onload = () => {
            runBottomPreviewLoop();
          };
          bottomFullImg.src = data.preview_url;
        } else {
          if (bottomPreviewAnimFrame) cancelAnimationFrame(bottomPreviewAnimFrame);
          previewImg.src = data.preview_url;
          if (data.fits_hardware) {
            widthBadge.className = "rainbow-badge text-[10px]";
            fitWarning.className = "text-[11px] text-emerald-600 mt-1 font-semibold";
            fitWarning.textContent = `✓ Fits hardware bounds (${data.content_width}px / 96px)`;
          } else {
            widthBadge.className = "bg-red-500 text-white font-bold px-2 py-0.5 rounded text-[10px]";
            fitWarning.className = "text-[11px] text-red-500 mt-1 font-semibold";
            fitWarning.textContent = `⚠ Overflow by ${data.content_width - 96}px! Text will clip in static mode.`;
          }
        }
      }
    } catch (e) {
      console.error("Preview render failed:", e);
    }
  }

  // Trigger preview on input changes
  textInput.addEventListener("input", triggerPreview);
  fontSelect.addEventListener("change", triggerPreview);
  fontSizeInput.addEventListener("input", triggerPreview);
  antialiasCheckbox.addEventListener("change", triggerPreview);
  textColorInput.addEventListener("input", triggerPreview);
  bgColorInput.addEventListener("input", triggerPreview);

  // Send Image to Matrix
  btnSendMatrix.addEventListener("click", async () => {
    btnSendMatrix.disabled = true;
    btnSendMatrix.innerHTML = `<i data-lucide="loader" class="w-3.5 h-3.5 mr-1.5 animate-spin"></i> Sending...`;
    lucide.createIcons();

    const intervalVal = refreshIntervalInput ? (parseInt(refreshIntervalInput.value, 10) || 0) : 0;
    const isScrolling = scrollEnabledCheckbox ? scrollEnabledCheckbox.checked : false;
    const isFrameSkip = frameSkipCheckbox ? frameSkipCheckbox.checked : false;
    const isBlur = blurCheckbox ? blurCheckbox.checked : false;
    const skipStep = frameSkipStepInput ? Math.max(1, parseInt(frameSkipStepInput.value, 10) || 1) : 1;
    const scrollSpd = scrollSpeedInput ? Math.max(10, parseInt(scrollSpeedInput.value, 10) || 80) : 80;

    const payload = {
      name: configNameInput.value.trim() || "untitled",
      text: textInput.value || " ",
      font_id: fontSelect.value,
      font_size: parseInt(fontSizeInput.value, 10) || 8,
      text_color: textColorInput.value,
      bg_color: bgColorInput.value,
      alignment: currentAlignment,
      v_alignment: currentVAlignment,
      antialias: antialiasCheckbox.checked,
      refresh_interval: intervalVal,
      scroll_enabled: isScrolling,
      scroll_direction: currentScrollDirection,
      scroll_speed: scrollSpd,
      frame_skip_enabled: isFrameSkip,
      frame_skip_step: skipStep,
      blur_enabled: isBlur
    };

    try {
      const res = await fetch("/api/text-message/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        // Sync simulator directly
        state.previewMode = "bitmap";
        state.previewBitmap = data.pixels;
        state.scrolling.enabled = isScrolling;
        state.scrolling.direction = currentScrollDirection;
        state.scrolling.speed = scrollSpd;

        const scrollInfo = isScrolling ? ` (scrolling ${currentScrollDirection.toUpperCase()} @ ${scrollSpd}ms)` : "";
        const msgInfo = intervalVal > 0 ? ` (auto-refreshing every ${intervalVal}s)` : "";
        alert(`Image rendered and dispatched to matrix display!${scrollInfo}${msgInfo}`);
        document.getElementById("dash-active-summary").textContent = payload.text;
        document.getElementById("dash-active-detail").textContent = `Rendered Image (${payload.font_id})${scrollInfo}${msgInfo}`;
      } else {
        alert("Matrix communication failed or display is disconnected.");
      }
    } catch (e) {
      alert("Error sending to matrix: " + e.message);
    } finally {
      btnSendMatrix.disabled = false;
      btnSendMatrix.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5 mr-1.5"></i> Send to Matrix`;
      lucide.createIcons();
    }
  });

  // Save Configuration to Disk
  btnSaveConfig.addEventListener("click", async () => {
    const name = configNameInput.value.trim();
    if (!name) {
      alert("Please provide a name for this configuration.");
      return;
    }
    const intervalVal = refreshIntervalInput ? (parseInt(refreshIntervalInput.value, 10) || 0) : 0;
    const isScrolling = scrollEnabledCheckbox ? scrollEnabledCheckbox.checked : false;
    const isFrameSkip = frameSkipCheckbox ? frameSkipCheckbox.checked : false;
    const isBlur = blurCheckbox ? blurCheckbox.checked : false;
    const skipStep = frameSkipStepInput ? Math.max(1, parseInt(frameSkipStepInput.value, 10) || 1) : 1;
    const scrollSpd = scrollSpeedInput ? Math.max(10, parseInt(scrollSpeedInput.value, 10) || 80) : 80;

    const payload = {
      name: name,
      id: name.toLowerCase().replace(/[^a-z0-9_-]/g, "_"),
      text: textInput.value,
      font_id: fontSelect.value,
      font_size: parseInt(fontSizeInput.value, 10) || 8,
      text_color: textColorInput.value,
      bg_color: bgColorInput.value,
      alignment: currentAlignment,
      v_alignment: currentVAlignment,
      antialias: antialiasCheckbox.checked,
      refresh_interval: intervalVal,
      scroll_enabled: isScrolling,
      scroll_direction: currentScrollDirection,
      scroll_speed: scrollSpd,
      frame_skip_enabled: isFrameSkip,
      frame_skip_step: skipStep,
      blur_enabled: isBlur
    };

    const res = await fetch("/api/text-message/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      alert(`Configuration '${name}' saved to disk!`);
      loadSavedConfigsList(payload.id);
    } else {
      alert("Failed saving configuration.");
    }
  });

  // Load Saved Configurations List
  async function loadSavedConfigsList(selectId) {
    try {
      const res = await fetch("/api/text-message/configs");
      const list = await res.json();
      configPicker.innerHTML = `<option value="">-- Presets --</option>`;
      list.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c.id;
        opt.textContent = c.name || c.id;
        if (selectId && c.id === selectId) opt.selected = true;
        configPicker.appendChild(opt);
      });
    } catch (e) {
      console.error("Failed loading saved configs list:", e);
    }
  }

  // Load selected configuration
  btnLoadConfig.addEventListener("click", async () => {
    const id = configPicker.value;
    if (!id) return;
    try {
      const res = await fetch(`/api/text-message/configs/${id}`);
      if (res.ok) {
        const c = await res.json();
        configNameInput.value = c.name || id;
        textInput.value = c.text || "";
        fontSelect.value = c.font_id || "DejaVuSans";
        fontSizeInput.value = c.font_size || 11;
        textColorInput.value = c.text_color || "#FFFFFF";
        bgColorInput.value = c.bg_color || "#000000";
        antialiasCheckbox.checked = !!c.antialias;
        currentAlignment = c.alignment || "center";
        currentVAlignment = c.v_alignment || "middle";
        if (refreshIntervalInput) {
          const iv = c.refresh_interval || 0;
          refreshIntervalInput.value = iv;
          if (refreshValSpan) refreshValSpan.textContent = iv > 0 ? `Every ${iv}s` : "";
          setupLivePreviewTimer(iv);
        }

        document.querySelectorAll(".btn-alignment").forEach(b => {
          if (b.dataset.align === currentAlignment) {
            b.className = "btn-alignment btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-1 px-1.5";
          } else {
            b.className = "btn-alignment btn-3d bg-white text-slate-700 text-xs py-1 px-1.5 border";
          }
        });

        document.querySelectorAll(".btn-valign").forEach(b => {
          if (b.dataset.valign === currentVAlignment) {
            b.className = "btn-valign btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-1 px-1.5";
          } else {
            b.className = "btn-valign btn-3d bg-white text-slate-700 text-xs py-1 px-1.5 border";
          }
        });

        // Load scrolling parameters
        if (scrollEnabledCheckbox) {
          scrollEnabledCheckbox.checked = !!c.scroll_enabled;
          state.scrolling.enabled = !!c.scroll_enabled;
        }
        if (frameSkipCheckbox) {
          frameSkipCheckbox.checked = !!c.frame_skip_enabled;
          state.scrolling.frameSkip = !!c.frame_skip_enabled;
        }
        if (blurCheckbox) {
          blurCheckbox.checked = !!c.blur_enabled;
          state.scrolling.blur = !!c.blur_enabled;
        }
        if (frameSkipStepInput) {
          const stepVal = c.frame_skip_step || 1;
          frameSkipStepInput.value = stepVal;
          state.scrolling.frameSkipStep = stepVal;
        }
        if (scrollSpeedInput) {
          const spd = Math.max(10, c.scroll_speed || 80);
          scrollSpeedInput.value = spd;
          state.scrolling.speed = spd;
        }
        syncScrollUiVisibility();
        currentScrollDirection = c.scroll_direction === "ltr" ? "ltr" : "rtl";
        state.scrolling.direction = currentScrollDirection;
        if (btnScrollRtl && btnScrollLtr) {
          if (currentScrollDirection === "ltr") {
            btnScrollLtr.className = "btn-scroll-dir btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-0.5 px-2 text-center";
            btnScrollRtl.className = "btn-scroll-dir btn-3d bg-white text-slate-700 border-slate-200 text-xs py-0.5 px-2 text-center";
          } else {
            btnScrollRtl.className = "btn-scroll-dir btn-3d bg-pink-100 text-pink-700 border-pink-300 font-semibold text-xs py-0.5 px-2 text-center";
            btnScrollLtr.className = "btn-scroll-dir btn-3d bg-white text-slate-700 border-slate-200 text-xs py-0.5 px-2 text-center";
          }
        }

        triggerPreview();
      }
    } catch (e) {
      alert("Error loading configuration: " + e.message);
    }
  });

  // Delete configuration
  btnDeleteConfig.addEventListener("click", async () => {
    const id = configPicker.value;
    if (!id) {
      alert("Select a saved configuration to delete.");
      return;
    }
    if (confirm(`Delete configuration '${id}'?`)) {
      await fetch(`/api/text-message/configs/${id}`, { method: "DELETE" });
      loadSavedConfigsList();
    }
  });

  // Make fetchRenderedPreview available globally for state restoration
  window.fetchRenderedPreview = fetchRenderedPreview;

  loadSavedConfigsList();
  refreshImageTagDropdown();
  triggerPreview();
}

// Hardware Settings & Presets Controller
function setupSettingsControls() {
  const resSelect = document.getElementById("matrix-resolution");
  const orientSelect = document.getElementById("matrix-orientation");
  const btnSave = document.getElementById("btn-save-settings");
  const statusMsg = document.getElementById("settings-status-msg");

  if (!btnSave) return;

  btnSave.addEventListener("click", async () => {
    btnSave.disabled = true;

    try {
      const payload = {
        resolution: resSelect ? resSelect.value : "96x16",
        orientation: orientSelect ? parseInt(orientSelect.value, 10) : 0
      };

      const res = await fetch("/api/matrix/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        if (statusMsg) {
          statusMsg.textContent = "✓ Settings persisted and orientation sent to device!";
          statusMsg.className = "text-xs text-center text-emerald-600 font-semibold";
          setTimeout(() => { if (statusMsg) statusMsg.textContent = ""; }, 4000);
        }
        await fetchConfig();
      } else {
        alert("Failed to save settings.");
      }
    } catch (e) {
      alert("Error saving settings: " + e.message);
    } finally {
      btnSave.disabled = false;
      btnSave.textContent = "Save";
    }
  });

  // BLE Transmission & Image Encoding Controls
  const selPngMode = document.getElementById("ble-png-mode");
  const inpChunkSize = document.getElementById("ble-chunk-size");
  const inpPacing = document.getElementById("ble-chunk-pacing");
  const btnSaveBle = document.getElementById("btn-save-ble-settings");
  const bleStatusMsg = document.getElementById("ble-settings-status-msg");
  const btnBenchmark = document.getElementById("btn-run-benchmark");

  if (btnSaveBle) {
    btnSaveBle.addEventListener("click", async () => {
      btnSaveBle.disabled = true;
      try {
        const payload = {
          ble: {
            png_mode: selPngMode ? selPngMode.value : "rgb_raw",
            max_chunk_size: inpChunkSize ? parseInt(inpChunkSize.value, 10) : 509,
            chunk_pacing_ms: inpPacing ? parseFloat(inpPacing.value) : 1.5
          }
        };

        const res = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          if (bleStatusMsg) {
            bleStatusMsg.textContent = "✓ BLE transmission settings saved!";
            bleStatusMsg.className = "text-xs text-emerald-600 font-semibold";
            setTimeout(() => { if (bleStatusMsg) bleStatusMsg.textContent = ""; }, 4000);
          }
          await fetchConfig();
        } else {
          alert("Failed to save BLE settings.");
        }
      } catch (err) {
        alert("Error saving BLE settings: " + err.message);
      } finally {
        btnSaveBle.disabled = false;
      }
    });
  }

  if (btnBenchmark) {
    btnBenchmark.addEventListener("click", async () => {
      btnBenchmark.disabled = true;
      const prevHtml = btnBenchmark.innerHTML;
      btnBenchmark.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Running (3 runs each)...`;
      if (window.lucide) lucide.createIcons();

      const resultsBox = document.getElementById("benchmark-results-box");
      const tableBody = document.getElementById("benchmark-table-body");
      const badge = document.getElementById("benchmark-status-badge");

      try {
        const res = await fetch("/api/ble/benchmark?iterations=3", { method: "POST" });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Benchmark failed");
        }

        if (resultsBox) resultsBox.classList.remove("hidden");
        if (badge) {
          badge.textContent = `Completed (${data.active_mode || "BLE 4.2"})`;
        }

        if (tableBody && data.results) {
          const modeLabels = {
            rgb_raw: "Uncompressed (compress_level=0)",
            rgb_max: "Max Compressed (compress_level=9)",
            palette: "8-Bit Palette (mode='P')"
          };

          const resultsList = Array.isArray(data.results) ? data.results : Object.entries(data.results).map(([m, r]) => ({ mode: m, ...r }));

          tableBody.innerHTML = resultsList.map(r => {
            const m = r.mode;
            const label = modeLabels[m] || m;
            const txVal = r.tx_ms !== undefined ? r.tx_ms : (r.avg_tx_ms !== undefined ? r.avg_tx_ms : '--');
            const ackVal = r.ack_ms !== undefined ? r.ack_ms : (r.avg_ack_ms !== undefined ? r.avg_ack_ms : '--');
            const totalVal = r.total_ms !== undefined ? r.total_ms : (r.avg_total_ms !== undefined ? r.avg_total_ms : '--');
            const bytesVal = r.bytes !== undefined ? r.bytes : (r.png_bytes !== undefined ? r.png_bytes : '--');

            return `
              <tr class="hover:bg-slate-50">
                <td class="py-1.5 font-bold">${m} <span class="text-[10px] text-slate-500 font-normal">(${label})</span></td>
                <td class="py-1.5">${bytesVal} B</td>
                <td class="py-1.5 text-indigo-600 font-semibold">${txVal !== '--' ? txVal + ' ms' : '--'}</td>
                <td class="py-1.5 text-amber-600 font-semibold">${ackVal !== '--' ? ackVal + ' ms' : '--'}</td>
                <td class="py-1.5 text-emerald-700 font-bold">${totalVal !== '--' ? totalVal + ' ms' : '--'}</td>
              </tr>
            `;
          }).join("");

          const curMode = selPngMode ? selPngMode.value : "rgb_raw";
        }
      } catch (err) {
        alert("Benchmark error: " + err.message);
      } finally {
        btnBenchmark.disabled = false;
        btnBenchmark.innerHTML = prevHtml;
        if (window.lucide) lucide.createIcons();
      }
    });
  }
}

// WebSocket Hardware Matrix Sync Client
let matrixSyncSocket = null;
let lastSyncEventTime = 0;

function connectMatrixSyncWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/matrix-sync`;

  try {
    matrixSyncSocket = new WebSocket(wsUrl);

    matrixSyncSocket.onopen = () => {
      // Periodic ping keepalive every 20s
      if (!matrixSyncSocket._pingInterval) {
        matrixSyncSocket._pingInterval = setInterval(() => {
          if (matrixSyncSocket && matrixSyncSocket.readyState === WebSocket.OPEN) {
            matrixSyncSocket.send("ping");
          }
        }, 20000);
      }
    };

    matrixSyncSocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "frame_sync") {
          lastSyncEventTime = performance.now();
          state.scrolling.hardwareSynced = true;

          // Direct alignment: offset lockstep with physical matrix frame ACK
          state.scrolling.offset = msg.offset;

          // Update metrics badge in simulator header in exact real-time
          const metricsPill = document.getElementById("sim-scroll-metrics");
          if (metricsPill) {
            metricsPill.classList.remove("hidden");
            const targetSpeed = document.getElementById("sim-target-speed");
            const pixelShift = document.getElementById("sim-pixel-shift");
            const actualBle = document.getElementById("sim-actual-ble");

            if (targetSpeed) targetSpeed.textContent = msg.frame_skip ? `Skip: ${msg.pixel_shift}f` : `${msg.target_speed_ms}ms`;
            if (pixelShift) pixelShift.textContent = `${msg.pixel_shift}px`;
            if (actualBle) {
              actualBle.textContent = `${msg.actual_ble_ms}ms`;
              if (msg.actual_ble_ms > msg.target_speed_ms * 1.5) {
                actualBle.className = "font-mono text-amber-600 font-bold";
              } else {
                actualBle.className = "font-mono text-emerald-700 font-bold";
              }
            }
          }
        }
      } catch (e) {
        console.error("Error processing matrix sync packet:", e);
      }
    };

    matrixSyncSocket.onclose = () => {
      state.scrolling.hardwareSynced = false;
      if (matrixSyncSocket && matrixSyncSocket._pingInterval) {
        clearInterval(matrixSyncSocket._pingInterval);
        matrixSyncSocket._pingInterval = null;
      }
      // Reconnect after 3 seconds
      setTimeout(connectMatrixSyncWebSocket, 3000);
    };

    matrixSyncSocket.onerror = () => {
      state.scrolling.hardwareSynced = false;
    };
  } catch (err) {
    state.scrolling.hardwareSynced = false;
    setTimeout(connectMatrixSyncWebSocket, 5000);
  }
}

// Fallback watchdog: if hardware sync packets pause for > 2 seconds while scrolling, return to local preview
setInterval(() => {
  if (state.scrolling.hardwareSynced && performance.now() - lastSyncEventTime > 2000) {
    state.scrolling.hardwareSynced = false;
  }
}, 1000);

// App Initialization
window.addEventListener("DOMContentLoaded", () => {
  try { initCanvas(); } catch (e) { console.error("initCanvas error:", e); }
  try { drawMatrixPreview(); } catch (e) { console.error("drawMatrixPreview error:", e); }
  try { setupNavigation(); } catch (e) { console.error("setupNavigation error:", e); }
  try { setupHeaderControls(); } catch (e) { console.error("setupHeaderControls error:", e); }
  try { setupTextMessageStudio(); } catch (e) { console.error("setupTextMessageStudio error:", e); }
  try { setupScriptControls(); } catch (e) { console.error("setupScriptControls error:", e); }
  try { setupBLEControls(); } catch (e) { console.error("setupBLEControls error:", e); }
  try { setupImageStudio(); } catch (e) { console.error("setupImageStudio error:", e); }
  try { setupScheduleControls(); } catch (e) { console.error("setupScheduleControls error:", e); }
  try { setupSettingsControls(); } catch (e) { console.error("setupSettingsControls error:", e); }
  try { connectMatrixSyncWebSocket(); } catch (e) { console.error("connectMatrixSyncWebSocket error:", e); }

  fetchConfig().then(() => {
    if (typeof window.fetchRenderedPreview === "function") {
      window.fetchRenderedPreview();
    }
  });
  fetchStatus();
  setInterval(fetchStatus, 4000);
});

