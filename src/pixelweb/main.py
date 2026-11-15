import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from fastapi import FastAPI, File, HTTPException, UploadFile, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .logger_config import setup_logging
from .config_manager import config_manager
from .script_runner import script_manager
from .image_processor import image_manager, UPLOAD_DIR, encode_matrix_png
from .ble_worker import ble_worker
from .scheduler import scheduler_service, apply_motion_blur
from .text_message_renderer import (
    AVAILABLE_FONTS,
    render_text_message,
    list_text_message_configs,
    get_text_message_config,
    save_text_message_config,
    delete_text_message_config,
    TEXT_MESSAGES_DIR
)
import base64
from io import BytesIO

setup_logging()

app = FastAPI(title="PyPixelColor Web UI", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Models
class TextPayload(BaseModel):
    content: str
    color: str = "#FF007F"
    bg_color: Optional[str] = "#000000"
    animation: int = 1
    rainbow_mode: int = 1
    speed: int = 80
    font: str = "UNIFONT"

class ScriptTestPayload(BaseModel):
    code: str

class ScriptSavePayload(BaseModel):
    id: str
    name: str
    description: str
    code: str

class ConnectPayload(BaseModel):
    address: str
    name: Optional[str] = None

class TextImagePayload(BaseModel):
    text: str
    text_color: str = "#FFFFFF"
    bg_color: str = "#000000"
    font_name: Optional[str] = None
    icon_filename: Optional[str] = None

class ImageProcessPayload(BaseModel):
    source_filename: str
    output_filename: str
    crop_box: Optional[List[int]] = None # [x0, y0, x1, y1]
    resize_dim: Optional[List[int]] = None # [w, h]
    remove_bg: bool = False
    bg_key_hex: str = "#FFFFFF"
    bg_tolerance: int = 30
    swap_color_enabled: bool = False
    swap_src_hex: str = "#FF0000"
    swap_dst_hex: str = "#00FF00"
    swap_tolerance: int = 30
    color_swaps: Optional[List[Dict[str, Any]]] = None
    antialias: bool = True
    is_temporary: bool = False

class TextMessageRenderPayload(BaseModel):
    name: Optional[str] = "custom_message"
    text: str = "HELLO 🔥 MATRIX"
    font_id: str = "PressStart2P"
    font_size: int = 8
    text_color: str = "#FFFFFF"
    bg_color: str = "#000000"
    alignment: str = "center" # "left", "center", "right"
    antialias: bool = False
    v_alignment: str = "middle" # "top", "middle", "bottom"
    refresh_interval: int = 0 # In seconds, 0 = static (no dynamic refresh)
    scroll_enabled: bool = False
    scroll_direction: str = "rtl" # "rtl" (Right to Left) or "ltr" (Left to Right)
    scroll_speed: int = 80 # Milliseconds per pixel step (min 80)
    frame_skip_enabled: bool = False
    frame_skip_step: int = 1 # Number of pixels/frames to shift when frame skip is enabled
    blur_enabled: bool = False # Motion blur / trailing phosphor decay

@app.on_event("startup")
async def on_startup():
    await ble_worker.start()
    await scheduler_service.start()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    fav_path = STATIC_DIR / "favicon.ico"
    if fav_path.exists():
        return FileResponse(str(fav_path))
    raise HTTPException(status_code=404)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

# Configuration Endpoints
@app.get("/api/config")
async def get_config():
    return config_manager.get()

@app.post("/api/config")
async def update_config(updates: Dict[str, Any]):
    return config_manager.update(updates)

# Status & Hardware
@app.get("/api/status")
async def get_status():
    status = dict(ble_worker.last_status)
    status["scroll_metrics"] = scheduler_service.scroll_metrics
    if "ble_info" in status and isinstance(status["ble_info"], dict):
        status["ble_info"]["chunk_size"] = ble_worker.effective_chunk_size
        status["ble_info"]["negotiated_mtu"] = ble_worker.negotiated_mtu
        status["ble_info"]["last_transfer"] = ble_worker.last_transfer_metrics
    return status

# WebSocket Connection Manager for Live Hardware Simulator Synchronization
active_ws_clients: Set[WebSocket] = set()

def _on_scheduler_frame_sync(event_data: Dict[str, Any]):
    if not active_ws_clients:
        return
    # Broadcast asynchronously without blocking the BLE thread
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            for ws in list(active_ws_clients):
                asyncio.create_task(ws.send_json(event_data))
    except Exception:
        pass

scheduler_service.register_sync_listener(_on_scheduler_frame_sync)

@app.websocket("/ws/matrix-sync")
async def websocket_matrix_sync(websocket: WebSocket):
    await websocket.accept()
    active_ws_clients.add(websocket)
    try:
        while True:
            # Keepalive receiver
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        active_ws_clients.discard(websocket)

@app.post("/api/power")
async def set_power(on: bool = True):
    config_manager.update({"matrix": {"power": on}})
    await ble_worker.set_power(on)
    return {"success": True, "power": on}

@app.post("/api/brightness")
async def set_brightness(level: int):
    level = max(0, min(100, level))
    config_manager.update({"matrix": {"brightness": level}})
    await ble_worker.set_brightness(level)
    return {"success": True, "brightness": level}

@app.post("/api/orientation")
async def set_orientation(orientation: int):
    orientation = max(0, min(3, orientation))
    config_manager.update({"matrix": {"orientation": orientation}})
    await ble_worker.set_orientation(orientation)
    return {"success": True, "orientation": orientation}

@app.post("/api/matrix/settings")
async def update_matrix_settings(payload: Dict[str, Any]):
    resolution = payload.get("resolution", "96x16")
    orientation = int(payload.get("orientation", 0))
    w, h = 96, 16
    if "x" in resolution:
        parts = resolution.split("x")
        try:
            w, h = int(parts[0]), int(parts[1])
        except Exception:
            pass

    config_manager.update({
        "matrix": {
            "width": w,
            "height": h,
            "orientation": orientation
        }
    })
    await ble_worker.set_orientation(orientation)
    return {"success": True, "width": w, "height": h, "orientation": orientation}

# BLE Endpoints
@app.get("/api/ble/scan")
async def scan_ble():
    devices = await ble_worker.scan_devices()
    return {"devices": devices}

@app.post("/api/ble/connect")
async def connect_ble(payload: ConnectPayload):
    ok = await ble_worker.connect_device(payload.address, payload.name)
    return {"success": ok, "status": ble_worker.last_status}

@app.post("/api/ble/disconnect")
async def disconnect_ble():
    await ble_worker.disconnect()
    return {"success": True}

@app.post("/api/ble/benchmark")
async def benchmark_ble_modes():
    """Run an automated benchmark comparing PNG compression modes on matrix."""
    if not ble_worker.connected or not ble_worker.client:
        raise HTTPException(status_code=400, detail="Matrix display not connected via BLE")

    from PIL import Image, ImageDraw
    import time

    # Generate a realistic text test pattern image (96x16)
    bench_img = Image.new("RGB", (96, 16), (0, 0, 0))
    d = ImageDraw.Draw(bench_img)
    d.text((2, 1), "BENCHMARK 96x16", fill=(255, 0, 128))
    for x in range(0, 96, 4):
        d.point((x, 14), fill=(0, 255, 200))

    modes_to_test = ["rgb_max", "rgb_raw", "palette"]
    results = []

    for mode in modes_to_test:
        t_enc_start = time.perf_counter()
        png_bytes = encode_matrix_png(bench_img, png_mode=mode)
        enc_ms = round((time.perf_counter() - t_enc_start) * 1000, 2)
        byte_len = len(png_bytes)

        t_send_start = time.perf_counter()
        ok = await ble_worker.send_image_bytes(png_bytes, file_ext=".png")
        total_transfer_ms = round((time.perf_counter() - t_send_start) * 1000, 1)

        metrics = ble_worker.last_transfer_metrics
        tx_ms = metrics.get("tx_ms", 0)
        ack_ms = metrics.get("ack_ms", 0)
        chunks = metrics.get("chunks_count", 0)

        results.append({
            "mode": mode,
            "success": ok,
            "bytes": byte_len,
            "encode_ms": enc_ms,
            "chunks": chunks,
            "tx_ms": tx_ms,
            "ack_ms": ack_ms,
            "total_ms": total_transfer_ms,
            "min_scroll_speed_ms": max(60, int(total_transfer_ms * 1.15))
        })
        await asyncio.sleep(0.3)

    # Restore current active display frame if active_matrix_frame.png exists
    try:
        active_frame = image_manager.get_in_memory_image("active_matrix_frame.png")
        if active_frame:
            await ble_worker.send_image_bytes(active_frame, file_ext=".png")
    except Exception:
        pass

    return {"results": results, "active_mode": config_manager.get().get("ble", {}).get("png_mode", "rgb_max")}

# Text Display Endpoints
@app.post("/api/text")
async def send_text(payload: TextPayload):
    config_manager.update({
        "mode": "text",
        "text": payload.dict()
    })
    ok = await ble_worker.send_text(
        text=payload.content,
        color=payload.color,
        bg_color=payload.bg_color,
        rainbow_mode=payload.rainbow_mode,
        animation=payload.animation,
        speed=payload.speed,
        font=payload.font
    )
    return {"success": ok}

# Script Studio Endpoints
@app.get("/api/scripts")
async def list_scripts():
    return script_manager.list_scripts()

@app.get("/api/scripts/{script_id}")
async def get_script(script_id: str):
    script = script_manager.get_script(script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script

@app.post("/api/scripts/test")
async def test_script(payload: ScriptTestPayload):
    ok, output = script_manager.execute_script(payload.code)
    return {"success": ok, "output": output if ok else None, "error": None if ok else output}

@app.post("/api/scripts/check-syntax")
async def check_script_syntax(payload: ScriptTestPayload):
    ok, msg = script_manager.check_syntax(payload.code)
    return {"success": ok, "message": msg}

@app.post("/api/scripts/fix-indent")
async def fix_script_indent(payload: ScriptTestPayload):
    ok, fixed_code, report = script_manager.fix_indentation(payload.code)
    return {"success": ok, "code": fixed_code, "report": report}

@app.post("/api/scripts/save")
async def save_script(payload: ScriptSavePayload):
    ok, err = script_manager.save_script(payload.id, payload.name, payload.description, payload.code)
    # Save script artifact only without forcing background mode override
    return {"success": ok, "error": err}

@app.delete("/api/scripts/{script_id}")
async def delete_script(script_id: str):
    ok = script_manager.delete_script(script_id)
    return {"success": ok}

# Image Endpoints
@app.get("/api/images")
async def list_images():
    return image_manager.list_images()

@app.get("/api/images/{filename}")
async def get_image_file(filename: str):
    # Check in-memory store first (for temporary layers/previews)
    mem_bytes = image_manager.get_in_memory_image(filename)
    if mem_bytes is not None:
        return Response(content=mem_bytes, media_type="image/png")

    p = image_manager.get_image_path(filename)
    if not p:
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(str(p))

@app.post("/api/images/upload")
async def upload_image(file: UploadFile = File(...)):
    filename = file.filename
    dest = UPLOAD_DIR / filename
    with open(dest, "wb") as f:
        f.write(await file.read())
    return {"filename": filename, "success": True}

@app.post("/api/images/process")
async def process_image_endpoint(payload: ImageProcessPayload):
    try:
        crop_tuple = tuple(payload.crop_box) if payload.crop_box and len(payload.crop_box) == 4 else None
        resize_tuple = tuple(payload.resize_dim) if payload.resize_dim and len(payload.resize_dim) == 2 else None

        result = image_manager.process_and_save(
            source_filename=payload.source_filename,
            output_filename=payload.output_filename,
            crop_box=crop_tuple,
            resize_dim=resize_tuple,
            remove_bg=payload.remove_bg,
            bg_key_hex=payload.bg_key_hex,
            bg_tolerance=payload.bg_tolerance,
            swap_color_enabled=payload.swap_color_enabled,
            swap_src_hex=payload.swap_src_hex,
            swap_dst_hex=payload.swap_dst_hex,
            swap_tolerance=payload.swap_tolerance,
            color_swaps=payload.color_swaps,
            antialias=payload.antialias,
            is_temporary=payload.is_temporary
        )
        return {"success": True, "image": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/images/delete")
async def delete_image(filename: str):
    ok = image_manager.delete_image(filename)
    return {"success": ok}

# Text Message with Emojis & Fonts Endpoints
@app.get("/api/text-message/fonts")
async def get_text_message_fonts():
    return AVAILABLE_FONTS

@app.get("/api/text-message/configs")
async def list_configs():
    return list_text_message_configs()

@app.get("/api/text-message/configs/{config_id}")
async def get_config_by_id(config_id: str):
    cfg = get_text_message_config(config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return cfg

@app.post("/api/text-message/preview")
async def preview_text_message(payload: TextMessageRenderPayload):
    # If scroll_enabled is True, render full-width canvas
    img, content_w = render_text_message(
        text=payload.text,
        width=96,
        height=16,
        font_id=payload.font_id,
        font_size=payload.font_size,
        text_color=payload.text_color,
        bg_color=payload.bg_color,
        alignment=payload.alignment,
        antialias=payload.antialias,
        v_alignment=payload.v_alignment,
        full_width=payload.scroll_enabled
    )
    rgb_img = img.convert("RGB")

    # Apply motion blur if enabled during frame skip for live simulator sync
    if payload.scroll_enabled and payload.frame_skip_enabled and payload.blur_enabled and payload.frame_skip_step > 1:
        rgb_img = apply_motion_blur(rgb_img, payload.scroll_direction, payload.frame_skip_step, payload.bg_color)

    buf = BytesIO()
    rgb_img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
    fits = content_w <= 96 or payload.scroll_enabled

    # Extract RGB raw pixel array for virtual simulator
    # If full_width, extract all columns so the frontend can animate smoothly
    pixels = []
    img_w, img_h = rgb_img.size
    for y in range(img_h):
        row = []
        for x in range(img_w):
            r, g, b = rgb_img.getpixel((x, y))
            row.append([r, g, b])
        pixels.append(row)

    return {
        "success": True,
        "preview_url": f"data:image/png;base64,{b64_data}",
        "pixels": pixels,
        "content_width": content_w,
        "canvas_width": img_w,
        "max_width": 96,
        "fits_hardware": fits,
        "scroll_enabled": payload.scroll_enabled,
        "scroll_direction": payload.scroll_direction,
        "scroll_speed": payload.scroll_speed,
        "frame_skip_enabled": payload.frame_skip_enabled,
        "frame_skip_step": payload.frame_skip_step,
        "blur_enabled": payload.blur_enabled
    }

@app.post("/api/text-message/save")
async def save_config(payload: TextMessageRenderPayload):
    data = payload.dict()
    ok = save_text_message_config(data)
    return {"success": ok}

@app.delete("/api/text-message/configs/{config_id}")
async def delete_config(config_id: str):
    ok = delete_text_message_config(config_id)
    return {"success": ok}

@app.post("/api/text-message/send")
async def send_text_message(payload: TextMessageRenderPayload):
    # Store text_message configuration for live background refreshing & scrolling
    config_manager.update({
        "mode": "text_message",
        "active_text_message": payload.dict()
    })

    # Render initial frame
    img, content_w = render_text_message(
        text=payload.text,
        width=96,
        height=16,
        font_id=payload.font_id,
        font_size=payload.font_size,
        text_color=payload.text_color,
        bg_color=payload.bg_color,
        alignment=payload.alignment,
        antialias=payload.antialias,
        v_alignment=payload.v_alignment,
        full_width=payload.scroll_enabled
    )

    rgb_img = img.convert("RGB")

    # Apply motion blur if enabled during frame skip for live simulator sync
    if payload.scroll_enabled and payload.frame_skip_enabled and payload.blur_enabled and payload.frame_skip_step > 1:
        rgb_img = apply_motion_blur(rgb_img, payload.scroll_direction, payload.frame_skip_step, payload.bg_color)

    img_w, img_h = rgb_img.size

    # If scrolling is enabled, take the first 96x16 window slice to display initially
    if payload.scroll_enabled:
        first_frame = rgb_img.crop((0, 0, 96, 16)) if payload.scroll_direction == "rtl" else rgb_img.crop((max(0, img_w - 96), 0, max(0, img_w - 96) + 96, 16))
    else:
        first_frame = rgb_img

    ble_cfg = config_manager.get().get("ble", {})
    png_mode = ble_cfg.get("png_mode", "rgb_raw")
    img_bytes = encode_matrix_png(first_frame, png_mode=png_mode)
    image_manager.set_in_memory_image("active_matrix_frame.png", img_bytes)

    # Extract pixels for simulator sync (full canvas so frontend simulator can also animate)
    pixels = []
    for y in range(img_h):
        row = []
        for x in range(img_w):
            r, g, b = rgb_img.getpixel((x, y))
            row.append([r, g, b])
        pixels.append(row)

    ok = await ble_worker.send_image_bytes(img_bytes, file_ext=".png")
    return {
        "success": ok,
        "content_width": content_w,
        "canvas_width": img_w,
        "pixels": pixels,
        "fits_hardware": content_w <= 96 or payload.scroll_enabled,
        "scroll_enabled": payload.scroll_enabled,
        "scroll_direction": payload.scroll_direction,
        "scroll_speed": payload.scroll_speed,
        "frame_skip_enabled": payload.frame_skip_enabled,
        "frame_skip_step": payload.frame_skip_step,
        "blur_enabled": payload.blur_enabled
    }

# Scheduling Endpoints
@app.post("/api/schedule/toggle")
async def toggle_schedule(enabled: bool):
    config_manager.update({"schedule": {"enabled": enabled}})
    return {"success": True, "enabled": enabled}

@app.post("/api/schedule/slot")
async def add_or_update_schedule_slot(slot: Dict[str, Any]):
    cfg = config_manager.get()
    slots = cfg.get("schedule", {}).get("slots", [])
    slot_id = slot.get("id")
    
    # If slot with same ID exists, update it in place
    updated = False
    if slot_id:
        for i, s in enumerate(slots):
            if s.get("id") == slot_id:
                slots[i] = slot
                updated = True
                break
    
    if not updated:
        slots.append(slot)

    config_manager.update({"schedule": {"slots": slots}})
    return {"success": True, "slots": slots, "updated": updated}

@app.delete("/api/schedule/slot/{slot_id}")
async def delete_schedule_slot(slot_id: str):
    cfg = config_manager.get()
    slots = cfg.get("schedule", {}).get("slots", [])
    initial_len = len(slots)
    
    # Match by slot id first
    new_slots = [s for s in slots if str(s.get("id")) != str(slot_id)]
    
    # Fallback to index if slot_id is purely numeric and no match by ID
    if len(new_slots) == initial_len and slot_id.isdigit():
        idx = int(slot_id)
        if 0 <= idx < len(slots):
            new_slots = [s for i, s in enumerate(slots) if i != idx]

    config_manager.update({"schedule": {"slots": new_slots}})
    return {"success": True, "slots": new_slots}

@app.post("/api/schedule/reorder")
async def reorder_schedule_slots(payload: Dict[str, Any]):
    """Reorder schedule slots by a provided list of slot IDs."""
    slot_ids = payload.get("slot_ids", [])
    cfg = config_manager.get()
    slots = cfg.get("schedule", {}).get("slots", [])
    
    slot_map = {s.get("id"): s for s in slots if s.get("id")}
    reordered = []
    
    # Append slots matching the ordered ID list
    for sid in slot_ids:
        if sid in slot_map:
            reordered.append(slot_map.pop(sid))
            
    # Append any remaining slots not explicitly mentioned
    for remaining in slot_map.values():
        reordered.append(remaining)
        
    config_manager.update({"schedule": {"slots": reordered}})
    return {"success": True, "slots": reordered}


