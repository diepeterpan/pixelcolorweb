import asyncio
import io
import hashlib
import logging
from datetime import datetime, time
from typing import Any, Dict, List, Optional
from PIL import Image
from .config_manager import config_manager
from .script_runner import script_manager
from .ble_worker import ble_worker
from .text_message_renderer import render_text_message, get_text_message_config

logger = logging.getLogger("Scheduler")

class SchedulerService:
    def __init__(self):
        self.running: bool = False
        self.task: Optional[asyncio.Task] = None

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._schedule_loop())
        logger.info("Schedule background service running.")

    async def _schedule_loop(self):
        last_slot_id = None
        last_refresh_tick = 0
        last_rendered_hash = None
        while self.running:
            try:
                cfg = config_manager.get()
                sched_cfg = cfg.get("schedule", {})
                mode = cfg.get("mode")

                # Dynamic text_message refresh loop (when refresh_interval > 0)
                if mode == "text_message" and ble_worker.connected:
                    msg_cfg = cfg.get("active_text_message")
                    if msg_cfg:
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
                            # Convert to adaptive palette PNG for minimum payload size
                            pal_img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
                            buf = io.BytesIO()
                            pal_img.save(buf, format="PNG", optimize=True)
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
                pal_img = img.convert('P', palette=Image.Palette.ADAPTIVE, colors=256)
                buf = io.BytesIO()
                pal_img.save(buf, format="PNG", optimize=True)
                await ble_worker.send_image_bytes(buf.getvalue(), file_ext=".png")

                # Set active_text_message so any dynamic interval continues during this slot
                config_manager.update({
                    "mode": "text_message",
                    "active_text_message": saved_cfg
                })
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

