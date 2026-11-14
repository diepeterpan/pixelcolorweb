import json
import logging
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from pypixelcolor.lib.emoji_manager import get_emoji_image

logger = logging.getLogger("TextMessageRenderer")

FONTS_DIR = Path("data/fonts")
TEXT_MESSAGES_DIR = Path("data/text_messages")
UPLOAD_DIR = Path("data/uploads")
TEMP_DIR = Path("data/temp")

FONTS_DIR.mkdir(parents=True, exist_ok=True)
TEXT_MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

AVAILABLE_FONTS = [
    {"id": "PressStart2P", "name": "Press Start 2P (Pixel Proportional)", "file": "PressStart2P.ttf", "default_size": 8},
    {"id": "Silkscreen", "name": "Silkscreen (Compact Pixel)", "file": "Silkscreen.ttf", "default_size": 10},
    {"id": "DejaVuSans", "name": "DejaVu Sans (Clean Proportional)", "file": "DejaVuSans.ttf", "default_size": 11},
    {"id": "VT323", "name": "VT323 (Terminal Proportional)", "file": "VT323.ttf", "default_size": 14},
    {"id": "Unifont", "name": "Unifont (Built-in Matrix)", "file": "unifont.otf", "default_size": 14}
]

TAG_REGEX = re.compile(r"<([a-zA-Z0-9_\-\.]+\.(?:png|jpg|jpeg|gif|webp|bmp|py))>")
from .script_runner import script_manager

def is_emoji_char(char: str) -> bool:
    cp = ord(char)
    if (0x1F300 <= cp <= 0x1FAFF) or \
       (0x2600 <= cp <= 0x27BF) or \
       (0x2300 <= cp <= 0x23FF) or \
       (0x2B50 <= cp <= 0x2B55) or \
       (0x200D == cp) or \
       (0xFE0F == cp):
        return True
    return unicodedata.category(char) in ("So", "Sk") and cp > 0x7F

def split_into_runs(text: str) -> List[Tuple[str, str]]:
    """
    Splits text into tokens of:
    - ('text', string)
    - ('emoji', emoji_char)
    - ('image', filename)
    - ('script', script_id_or_name)
    """
    runs: List[Tuple[str, str]] = []
    
    parts = []
    last_end = 0
    for match in TAG_REGEX.finditer(text):
        if match.start() > last_end:
            parts.append(("text", text[last_end:match.start()]))
        tag_val = match.group(1)
        if tag_val.lower().endswith(".py"):
            parts.append(("script", tag_val))
        else:
            parts.append(("image", tag_val))
        last_end = match.end()
    if last_end < len(text):
        parts.append(("text", text[last_end:]))

    for p_type, val in parts:
        if p_type in ("image", "script"):
            runs.append((p_type, val))
        else:
            curr = []
            for ch in val:
                if is_emoji_char(ch):
                    if curr:
                        runs.append(("text", "".join(curr)))
                        curr = []
                    runs.append(("emoji", ch))
                else:
                    curr.append(ch)
            if curr:
                runs.append(("text", "".join(curr)))

    return runs

def get_font_instance(font_id: str, font_size: int) -> ImageFont.FreeTypeFont:
    for f in AVAILABLE_FONTS:
        if f["id"] == font_id or f["file"] == font_id:
            font_path = FONTS_DIR / f["file"]
            if font_path.exists():
                try:
                    return ImageFont.truetype(str(font_path), font_size)
                except Exception as e:
                    logger.warning(f"Failed to load font {font_path}: {e}")
    # Fallback
    for f_path in FONTS_DIR.glob("*.*"):
        if f_path.suffix.lower() in [".ttf", ".otf"]:
            try:
                return ImageFont.truetype(str(f_path), font_size)
            except Exception:
                pass
    return ImageFont.load_default()

def render_text_message(
    text: str,
    width: int = 96,
    height: int = 16,
    font_id: str = "PressStart2P",
    font_size: int = 8,
    text_color: str = "#FFFFFF",
    bg_color: str = "#000000",
    alignment: str = "center",  # "left", "center", "right"
    antialias: bool = False,
    v_alignment: str = "middle"  # "top", "middle", "bottom"
) -> Tuple[Image.Image, int]:
    """
    Renders text, emojis, and inline <image.png> tags into a pixel-perfect image sized (width, height).
    """
    font = get_font_instance(font_id, font_size)
    runs = split_into_runs(text)

    # First pass: Measure total width of all runs
    dummy_img = Image.new("RGBA", (width * 4, height), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)
    dummy_draw.fontmode = "L" if antialias else "1"

    measured_runs = []
    total_content_width = 0

    emoji_size = min(height, max(10, font_size + 4))

    for run_type, run_val in runs:
        if run_type == "emoji":
            measured_runs.append(("emoji", run_val, emoji_size, None))
            total_content_width += emoji_size
        elif run_type == "script":
            script_id = run_val[:-3] if run_val.lower().endswith(".py") else run_val
            script = script_manager.get_script(script_id)
            eval_text = f"[{script_id}]"
            if script:
                ok, res_text = script_manager.execute_script(script.get("code", ""))
                eval_text = res_text if ok else f"[{script_id}:ERR]"
            bbox = dummy_draw.textbbox((0, 0), eval_text, font=font)
            run_w = bbox[2] - bbox[0]
            measured_runs.append(("text", eval_text, run_w, None))
            total_content_width += run_w
        elif run_type == "image":
            # Load image from UPLOAD_DIR
            img_path = UPLOAD_DIR / run_val
            if img_path.exists():
                try:
                    with Image.open(img_path) as user_img:
                        w, h = user_img.size
                        aspect = w / max(1, h)
                        target_w = max(1, int(round(height * aspect)))
                        measured_runs.append(("image", run_val, target_w, (img_path, min(height, h))))
                        total_content_width += target_w
                except Exception as e:
                    logger.error(f"Failed to measure user image {run_val}: {e}")
            else:
                fallback_w = 12
                measured_runs.append(("missing_image", run_val, fallback_w, None))
                total_content_width += fallback_w
        else: # text
            bbox = dummy_draw.textbbox((0, 0), run_val, font=font)
            run_w = bbox[2] - bbox[0]
            if not run_w and run_val.strip() == "":
                space_box = dummy_draw.textbbox((0, 0), "A", font=font)
                run_w = (space_box[2] // 2) * len(run_val)
            measured_runs.append(("text", run_val, run_w, None))
            total_content_width += run_w

    # Second pass: Starting X position
    if alignment == "left":
        start_x = 0
    elif alignment == "right":
        start_x = max(0, width - total_content_width)
    else:  # "center"
        start_x = max(0, (width - total_content_width) // 2)

    # Canvas creation
    canvas = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(canvas)
    draw.fontmode = "L" if antialias else "1"

    curr_x = start_x
    resample_filter = Image.Resampling.LANCZOS if antialias else Image.Resampling.NEAREST

    v_align = v_alignment.lower() if v_alignment else "middle"

    for run_type, run_val, run_w, extra_data in measured_runs:
        if run_type == "emoji":
            try:
                emoji_img = get_emoji_image(run_val, size=emoji_size)
                if emoji_img:
                    emoji_img = emoji_img.convert("RGBA")
                    emoji_img = emoji_img.resize((emoji_size, emoji_size), resample_filter)
                    if v_align == "top":
                        y_pos = 0
                    elif v_align == "bottom":
                        y_pos = max(0, height - emoji_size)
                    else:  # middle
                        y_pos = (height - emoji_size) // 2
                    canvas.paste(emoji_img, (int(curr_x), int(y_pos)), emoji_img)
            except Exception as e:
                logger.error(f"Error drawing emoji {run_val}: {e}")

        elif run_type == "image" and extra_data:
            try:
                img_path, original_h = extra_data
                with Image.open(img_path) as u_img:
                    u_img = u_img.convert("RGBA")
                    target_h = height
                    if v_align == "top":
                        y_pos = 0
                    elif v_align == "bottom":
                        y_pos = max(0, height - target_h)
                    else:
                        y_pos = (height - target_h) // 2
                    u_img = u_img.resize((run_w, target_h), resample_filter)
                    canvas.paste(u_img, (int(curr_x), int(y_pos)), u_img)
            except Exception as e:
                logger.error(f"Error drawing custom image {run_val}: {e}")

        elif run_type == "text":
            bbox = draw.textbbox((0, 0), run_val, font=font)
            text_h = bbox[3] - bbox[1]
            ascender_offset = bbox[1]
            if v_align == "top":
                y_pos = -ascender_offset
            elif v_align == "bottom":
                y_pos = max(0, height - text_h - 1)
            else:  # middle
                y_pos = max(0, (height - text_h) // 2 - 1)
            draw.text((int(curr_x), int(y_pos)), run_val, font=font, fill=text_color)

        curr_x += run_w

    final_img = canvas.convert("RGB")
    return final_img, total_content_width

# Preset Management
def list_text_message_configs() -> List[Dict[str, Any]]:
    configs = []
    for f in sorted(TEXT_MESSAGES_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                configs.append(json.load(fp))
        except Exception as e:
            logger.error(f"Error loading {f}: {e}")
    return configs

def get_text_message_config(name_id: str) -> Optional[Dict[str, Any]]:
    path = TEXT_MESSAGES_DIR / f"{name_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    return None

def save_text_message_config(data: Dict[str, Any]) -> bool:
    name_id = data.get("id") or data.get("name", "message").strip().replace(" ", "_").lower()
    data["id"] = name_id
    path = TEXT_MESSAGES_DIR / f"{name_id}.json"
    try:
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save text message config: {e}")
        return False

def delete_text_message_config(name_id: str) -> bool:
    path = TEXT_MESSAGES_DIR / f"{name_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
