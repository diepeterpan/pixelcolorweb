import asyncio
import io
import hashlib
import logging
from datetime import datetime, time
from typing import Any, Callable, Dict, List, Optional, Set
from PIL import Image
from .config_manager import config_manager
from .script_runner import script_manager
from .ble_worker import ble_worker
from .image_processor import encode_matrix_png
from .text_message_renderer import render_text_message, get_text_message_config

logger = logging.getLogger("Scheduler")

def apply_motion_blur(canvas: Image.Image, direction: str, skip_step: int, bg_color: str) -> Image.Image:
    """
    Apply directional motion blur / phosphor decay trailing to rendered scrolling canvas.
    - RTL: motion is leftwards, trailing is to the right (+x)
    - LTR: motion is rightwards, trailing is to the left (-x)
    - Decay: 45%, 30%, 15% scaled to skip_step. Subtle decay (max 15%) in 1px letter gaps.
    """
    if skip_step <= 1:
        return canvas

    blurred = canvas.copy()
    w, h = canvas.size
    bg_hex = (bg_color or "#000000").lstrip("#")
    if len(bg_hex) == 6:
        bg_rgb = tuple(int(bg_hex[i:i+2], 16) for i in (0, 2, 4))
    else:
        bg_rgb = (0, 0, 0)

    if skip_step == 2:
        decay_percentages = [0.35, 0.18]
    elif skip_step == 3:
        decay_percentages = [0.55, 0.35, 0.18]
    elif skip_step == 4:
        decay_percentages = [0.70, 0.50, 0.32, 0.18]
    else:
        decay_percentages = [0.80, 0.60, 0.42, 0.28, 0.16]

    step_dx = 1 if direction == "rtl" else -1
    pixels_orig = canvas.load()
    pixels_out = blurred.load()

    def is_bg(rgb):
        return abs(rgb[0] - bg_rgb[0]) < 10 and abs(rgb[1] - bg_rgb[1]) < 10 and abs(rgb[2] - bg_rgb[2]) < 10

    for y in range(h):
        for x in range(w):
            c_orig = pixels_orig[x, y]
            if is_bg(c_orig):
                continue

            for t_idx, pct in enumerate(decay_percentages):
                tx = x + step_dx * (t_idx + 1)
                if tx < 0 or tx >= w:
                    break
                if not is_bg(pixels_orig[tx, y]):
                    break

                # Subtle decay in 1px gaps between letters (capped at 25% for distinction)
                next_x = tx + step_dx
                if 0 <= next_x < w and not is_bg(pixels_orig[next_x, y]):
                    pct = min(pct, 0.25)

                trail_rgb = (
                    int(round((1.0 - pct) * bg_rgb[0] + pct * c_orig[0])),
                    int(round((1.0 - pct) * bg_rgb[1] + pct * c_orig[1])),
                    int(round((1.0 - pct) * bg_rgb[2] + pct * c_orig[2])),
                )
                cur_out = pixels_out[tx, y]
                pixels_out[tx, y] = (
                    max(cur_out[0], trail_rgb[0]),
                    max(cur_out[1], trail_rgb[1]),
                    max(cur_out[2], trail_rgb[2])
                )

    return blurred


class SchedulerService:
    def __init__(self):
        self.running: bool = False
        self.task: Optional[asyncio.Task] = None
        self._scroll_task: Optional[asyncio.Task] = None
        self._scroll_active_key: Optional[str] = None
        self._sync_listeners: Set[Callable[[Dict[str, Any]], Any]] = set()
        self.scroll_metrics: Dict[str, Any] = {
            "active": False,
            "target_speed_ms": 80,
            "actual_ble_ms": 0,
            "pixel_shift": 1,
            "direction": "rtl"
        }

    def register_sync_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        self._sync_listeners.add(callback)

    def unregister_sync_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        self._sync_listeners.discard(callback)

    def broadcast_sync(self, event_data: Dict[str, Any]):
        for cb in list(self._sync_listeners):
            try:
                cb(event_data)
            except Exception as e:
                logger.error(f"Error notifying sync listener: {e}")

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._schedule_loop())
        self._scroll_task = asyncio.create_task(self._text_scroll_loop())
        logger.info("Schedule background and text scroll services running.")

    async def _text_scroll_loop(self):
        """
        Dedicated software-based image scroller for active text_message with scroll_enabled.
        Streams cropped 96x16 frames to BLE at user-defined interval, adjusting / skipping
        vertical pixel columns to keep up if rendering or BLE transfer takes too long.
        """
        rendered_key = None
        pre_rendered_frames: List[bytes] = []
        canvas_w = 96
        offset_x = 0
        last_step_time = asyncio.get_event_loop().time()

        while self.running:
            try:
                cfg = config_manager.get()
                mode = cfg.get("mode")
                msg_cfg = cfg.get("active_text_message") if mode == "text_message" else None

                if not ble_worker.connected or not msg_cfg or not msg_cfg.get("scroll_enabled"):
                    self.scroll_metrics["active"] = False
                    rendered_key = None
                    pre_rendered_frames = []
                    await asyncio.sleep(0.2)
                    continue

                ble_cfg = cfg.get("ble", {})
                png_mode = ble_cfg.get("png_mode", "rgb_raw")
                frame_skip_on = bool(msg_cfg.get("frame_skip_enabled", False))
                skip_val = int(msg_cfg.get("frame_skip_step", 1))
                blur_on = bool(msg_cfg.get("blur_enabled", False))

                # Generate a unique hash key for current text config to know if content changed
                curr_key = f"{msg_cfg.get('text')}_{msg_cfg.get('font_id')}_{msg_cfg.get('font_size')}_{msg_cfg.get('text_color')}_{msg_cfg.get('bg_color')}_{msg_cfg.get('v_alignment')}_{msg_cfg.get('antialias')}_{msg_cfg.get('scroll_direction')}_{msg_cfg.get('scroll_speed')}_{frame_skip_on}_{skip_val}_{blur_on}_{png_mode}"
                if curr_key != rendered_key:
                    rendered_key = curr_key
                    # Render full width canvas with blank spacing between loops (Option A)
                    base_img, content_w = render_text_message(
                        text=msg_cfg.get("text", ""),
                        width=96,
                        height=16,
                        font_id=msg_cfg.get("font_id", "PressStart2P"),
                        font_size=msg_cfg.get("font_size", 8),
                        text_color=msg_cfg.get("text_color", "#FFFFFF"),
                        bg_color=msg_cfg.get("bg_color", "#000000"),
                        alignment="left",
                        antialias=msg_cfg.get("antialias", False),
                        v_alignment=msg_cfg.get("v_alignment", "middle"),
                        full_width=True
                    )
                    # For continuous loop wrap (Option A), add spacer of 24px and repeat
                    spacer_w = 24
                    loop_unit_w = max(96, content_w) + spacer_w
                    bg_col = msg_cfg.get("bg_color", "#000000")
                    full_w = loop_unit_w * 2 + 96
                    full_canvas = Image.new("RGB", (full_w, 16), bg_col)
                    full_canvas.paste(base_img.convert("RGB"), (0, 0))
                    full_canvas.paste(base_img.convert("RGB"), (loop_unit_w, 0))
                    full_canvas.paste(base_img.convert("RGB"), (loop_unit_w * 2, 0))
                    canvas_w = loop_unit_w

                    direction = msg_cfg.get("scroll_direction", "rtl")

                    # Apply motion blur if enabled during frame skip
                    if frame_skip_on and blur_on and skip_val > 1:
                        full_canvas = apply_motion_blur(full_canvas, direction, skip_val, bg_col)

                    # Pre-render each 96x16 window using configured PNG encoding mode
                    pre_rendered_frames = []
                    for x in range(canvas_w):
                        slice_img = full_canvas.crop((x, 0, x + 96, 16)).convert("RGB")
                        pre_rendered_frames.append(encode_matrix_png(slice_img, png_mode=png_mode))

                    offset_x = 0 if direction == "rtl" else (canvas_w - 1)
                    last_step_time = asyncio.get_event_loop().time()

                if not pre_rendered_frames:
                    await asyncio.sleep(0.05)
                    continue

                speed_ms = max(10, int(msg_cfg.get("scroll_speed", 80)))
                direction = msg_cfg.get("scroll_direction", "rtl")
                frame_skip = bool(msg_cfg.get("frame_skip_enabled", False))
                custom_skip_step = max(1, int(msg_cfg.get("frame_skip_step", 1)))

                step_start = asyncio.get_event_loop().time()

                # Instant slice lookup from ring buffer (0 ms latency)
                cur_x = int(round(offset_x)) % len(pre_rendered_frames)
                frame_bytes = pre_rendered_frames[cur_x]

                # Send frame over BLE via fast-path binary transport
                await ble_worker.send_image_bytes(frame_bytes, file_ext=".png")

                step_duration_ms = (asyncio.get_event_loop().time() - step_start) * 1000.0

                if frame_skip:
                    # User-configured fixed frame skip mode: advance by user-selected step
                    pixels_to_advance = custom_skip_step
                    remaining_sleep_ms = 5  # Run as fast as BLE allows
                else:
                    # Speed (ms) mode: dynamically calculate frame skip to preserve wall-clock speed
                    pixels_to_advance = max(1, int(round(max(speed_ms, step_duration_ms) / speed_ms)))
                    remaining_sleep_ms = max(5, speed_ms - step_duration_ms)

                # Update live scrolling telemetry
                sync_payload = {
                    "type": "frame_sync",
                    "offset": cur_x,
                    "target_speed_ms": speed_ms if not frame_skip else 0,
                    "actual_ble_ms": int(round(step_duration_ms)),
                    "pixel_shift": pixels_to_advance,
                    "direction": direction,
                    "total_frames": len(pre_rendered_frames),
                    "frame_skip": frame_skip
                }
                self.scroll_metrics.update({
                    "active": True,
                    "target_speed_ms": speed_ms if not frame_skip else 0,
                    "actual_ble_ms": int(round(step_duration_ms)),
                    "pixel_shift": pixels_to_advance,
                    "direction": direction,
                    "frame_skip": frame_skip
                })
                self.broadcast_sync(sync_payload)

                if direction == "rtl":
                    offset_x = (offset_x + pixels_to_advance) % len(pre_rendered_frames)
                else:
                    offset_x = (offset_x - pixels_to_advance) % len(pre_rendered_frames)

                await asyncio.sleep(remaining_sleep_ms / 1000.0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in text scroll loop: {e}")
                await asyncio.sleep(0.5)

    async def _schedule_loop(self):
        last_slot_id = None
        last_refresh_tick = 0
        last_rendered_hash = None
        while self.running:
            try:
                cfg = config_manager.get()
                sched_cfg = cfg.get("schedule", {})
                mode = cfg.get("mode")

                # Dynamic text_message refresh loop (when refresh_interval > 0 and not scrolling)
                if mode == "text_message" and ble_worker.connected:
                    msg_cfg = cfg.get("active_text_message")
                    if msg_cfg and not msg_cfg.get("scroll_enabled"):
                        interval = int(msg_cfg.get("refresh_interval", 0))
                        now_ts = asyncio.get_event_loop().time()
                        if interval > 0 and (now_ts - last_refresh_tick >= interval):
                            last_refresh_tick = now_ts
                            img, _ = render_text_message(
                                text=msg_cfg.get("text", ""),
                                width=96,
                                height=16,
                                font_id=msg_cfg.get("font_id", "PressStart2P"),
                                font_size=msg_cfg.get("font_size", 8),
                                text_color=msg_cfg.get("text_color", "#FFFFFF"),
                                bg_color=msg_cfg.get("bg_color", "#000000"),
                                alignment=msg_cfg.get("alignment", "center"),
                                antialias=msg_cfg.get("antialias", False),
                                v_alignment=msg_cfg.get("v_alignment", "middle")
                            )
                            # Convert to 24-bit RGB PNG with maximum compression
                            rgb_img = img.convert("RGB")
                            buf = io.BytesIO()
                            rgb_img.save(buf, format="PNG", optimize=True, compress_level=9)
                            frame_bytes = buf.getvalue()

                            # Compute hash to avoid re-transmitting identical frame
                            curr_hash = hashlib.md5(frame_bytes).hexdigest()
                            if curr_hash != last_rendered_hash:
                                last_rendered_hash = curr_hash
                                await ble_worker.send_image_bytes(frame_bytes, file_ext=".png")

                # Dynamic script update tick (every 10 seconds if mode is script)
                elif mode == "script" and ble_worker.connected:
                    script_id = cfg.get("active_script_id")
                    if script_id:
                        script = script_manager.get_script(script_id)
                        if script:
                            ok, text_val = script_manager.execute_script(script["code"])
                            if ok:
                                t_cfg = cfg.get("text", {})
                                await ble_worker.send_text(
                                    text=text_val,
                                    color=t_cfg.get("color", "#00FFAA"),
                                    rainbow_mode=t_cfg.get("rainbow_mode", 0),
                                    animation=t_cfg.get("animation", 0),
                                    speed=t_cfg.get("speed", 80)
                                )

                # Time-based rule scheduler evaluation
                if sched_cfg.get("enabled"):
                    slots = sched_cfg.get("slots", [])
                    now = datetime.now()
                    current_time_str = now.strftime("%H:%M")
                    current_date_str = now.strftime("%Y-%m-%d")

                    active_slot = None
                    for slot in slots:
                        # Check date bounds if provided
                        start_date = slot.get("start_date")
                        end_date = slot.get("end_date")
                        if start_date and current_date_str < start_date:
                            continue
                        if end_date and current_date_str > end_date:
                            continue

                        # Check hour/minute bounds
                        start_time = slot.get("start_time", "00:00")
                        end_time = slot.get("end_time", "23:59")
                        if start_time <= current_time_str <= end_time:
                            active_slot = slot
                            break

                    if active_slot and active_slot.get("id") != last_slot_id:
                        last_slot_id = active_slot.get("id")
                        logger.info(f"Triggering scheduled slot: {active_slot.get('name')}")
                        await self._execute_slot(active_slot)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")

            # Dynamic sleep interval: if fast text_message refresh is configured, wake up frequently
            sleep_duration = 5.0
            try:
                cfg_curr = config_manager.get()
                if cfg_curr.get("mode") == "text_message":
                    active_msg = cfg_curr.get("active_text_message", {})
                    inter = int(active_msg.get("refresh_interval", 0))
                    if inter > 0:
                        sleep_duration = min(0.5, inter / 2.0)
            except Exception:
                sleep_duration = 1.0

            await asyncio.sleep(sleep_duration)

    async def _execute_slot(self, slot: Dict[str, Any]):
        content_type = slot.get("type", "text_message")
        if content_type == "text_message" or content_type == "text":
            config_id = slot.get("config_id") or slot.get("content")
            saved_cfg = get_text_message_config(config_id) if config_id else None

            if saved_cfg:
                # Set active_text_message so any dynamic interval or scrolling activates immediately
                config_manager.update({
                    "mode": "text_message",
                    "active_text_message": saved_cfg
                })

                if not saved_cfg.get("scroll_enabled"):
                    img, _ = render_text_message(
                        text=saved_cfg.get("text", ""),
                        width=96,
                        height=16,
                        font_id=saved_cfg.get("font_id", "PressStart2P"),
                        font_size=saved_cfg.get("font_size", 8),
                        text_color=saved_cfg.get("text_color", "#FFFFFF"),
                        bg_color=saved_cfg.get("bg_color", "#000000"),
                        alignment=saved_cfg.get("alignment", "center"),
                        antialias=saved_cfg.get("antialias", False),
                        v_alignment=saved_cfg.get("v_alignment", "middle")
                    )
                    rgb_img = img.convert("RGB")
                    ble_cfg = config_manager.get().get("ble", {})
                    png_mode = ble_cfg.get("png_mode", "rgb_raw")
                    frame_bytes = encode_matrix_png(rgb_img, png_mode=png_mode)
                    await ble_worker.send_image_bytes(frame_bytes, file_ext=".png")
            else:
                raw_text = slot.get("content", "SCHEDULED TEXT")
                await ble_worker.send_text(
                    text=raw_text,
                    color=slot.get("color", "#FF007F"),
                    rainbow_mode=slot.get("rainbow_mode", 1),
                    animation=slot.get("animation", 1),
                    speed=slot.get("speed", 80)
                )
        elif content_type == "script":
            script_id = slot.get("script_id")
            if script_id:
                script = script_manager.get_script(script_id)
                if script:
                    ok, text_val = script_manager.execute_script(script["code"])
                    if ok:
                        await ble_worker.send_text(
                            text=text_val,
                            color=slot.get("color", "#00FFAA"),
                            rainbow_mode=slot.get("rainbow_mode", 0),
                            animation=slot.get("animation", 0)
                        )
        elif content_type == "image":
            img_path = slot.get("image_path")
            if img_path:
                await ble_worker.send_image(img_path)

scheduler_service = SchedulerService()

