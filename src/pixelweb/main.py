import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, HTTPException, UploadFile, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .logger_config import setup_logging
from .config_manager import config_manager
from .script_runner import script_manager
from .image_processor import image_manager, UPLOAD_DIR
from .ble_worker import ble_worker
from .scheduler import scheduler_service
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
    return ble_worker.last_status

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
        v_alignment=payload.v_alignment
    )
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
    fits = content_w <= 96

    # Extract RGB raw pixel array (96x16) for virtual simulator
    pixels = []
    rgb_img = img.convert("RGB")
    for y in range(16):
        row = []
        for x in range(96):
            r, g, b = rgb_img.getpixel((x, y))
            row.append([r, g, b])
        pixels.append(row)

    return {
        "success": True,
        "preview_url": f"data:image/png;base64,{b64_data}",
        "pixels": pixels,
        "content_width": content_w,
        "max_width": 96,
        "fits_hardware": fits
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
        v_alignment=payload.v_alignment
    )
    # Store in-memory frame bytes directly
    buf = BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    image_manager.set_in_memory_image("active_matrix_frame.png", img_bytes)

    # Extract pixels for simulator sync
    pixels = []
    rgb_img = img.convert("RGB")
    for y in range(16):
        row = []
        for x in range(96):
            r, g, b = rgb_img.getpixel((x, y))
            row.append([r, g, b])
        pixels.append(row)

    # Store text_message configuration for live background refreshing
    config_manager.update({
        "mode": "text_message",
        "active_text_message": payload.dict()
    })

    ok = await ble_worker.send_image_bytes(img_bytes, file_ext=".png")
    return {
        "success": ok,
        "content_width": content_w,
        "pixels": pixels,
        "fits_hardware": content_w <= 96
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

