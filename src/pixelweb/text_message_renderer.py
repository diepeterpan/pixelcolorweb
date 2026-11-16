import json
import logging
import re
import unicodedata
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

import pypixelcolor.lib.emoji_manager as em
from pypixelcolor.lib.emoji_manager import get_emoji_image, CACHE_DIR, TWEMOJI_BASE_URL, get_emoji_codepoint

# Patch / enhance download_emoji in emoji_manager to support multi-codepoint flag and ZWJ sequences
_orig_download_emoji = em.download_emoji

def _enhanced_download_emoji(char: str) -> Optional[Image.Image]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []

    # 1. Exact raw codepoints (retains variation selectors if needed)
    cps_full = [f"{ord(c):x}" for c in char]
    candidates.append("-".join(cps_full))

    # 2. Standard get_emoji_codepoint (which strips variation selectors)
    raw_code = get_emoji_codepoint(char)
    candidates.append(raw_code)

    # 3. Specific twemoji conventions (e.g. rainbow flag, transgender, pirate flag)
    if raw_code == "1f3f4-200d-2620":
        candidates.append("1f3f4-200d-2620-fe0f")
    elif raw_code == "1f3f3-200d-1f308":
        candidates.append("1f3f3-fe0f-200d-1f308")
    elif raw_code == "1f3f3-200d-26a7":
        candidates.append("1f3f3-fe0f-200d-26a7-fe0f")

    seen = set()
    unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    for codepoint in unique_candidates:
        cache_path = CACHE_DIR / f"{codepoint}.png"
        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except Exception:
                cache_path.unlink(missing_ok=True)

        url = f"{TWEMOJI_BASE_URL}{codepoint}.png"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                image_data = response.read()
            img = Image.open(BytesIO(image_data))
            img.save(cache_path, "PNG")
            return img
        except Exception:
            continue

    return None

em.download_emoji = _enhanced_download_emoji

logger = logging.getLogger("TextMessageRenderer")

FONTS_DIR = Path("data/fonts")
TEXT_MESSAGES_DIR = Path("data/text_messages")
UPLOAD_DIR = Path("data/uploads")

FONTS_DIR.mkdir(parents=True, exist_ok=True)
TEXT_MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

AVAILABLE_FONTS = [
    {"id": "PressStart2P", "name": "Press Start 2P (Pixel Proportional)", "file": "PressStart2P.ttf", "default_size": 8},
    {"id": "Silkscreen", "name": "Silkscreen (Compact Pixel)", "file": "Silkscreen.ttf", "default_size": 10},
    {"id": "DejaVuSans", "name": "DejaVu Sans (Clean Proportional)", "file": "DejaVuSans.ttf", "default_size": 11},
    {"id": "VT323", "name": "VT323 (Terminal Proportional)", "file": "VT323.ttf", "default_size": 14},
    {"id": "Unifont", "name": "Unifont (Built-in Matrix)", "file": "unifont.otf", "default_size": 14}
]

TAG_REGEX = re.compile(r"<([a-zA-Z0-9_\-\.]+\.(?:png|jpg|jpeg|gif|webp|bmp|py))>")
from .script_runner import script_manager

LINEBREAK_PATTERN = re.compile(r"\r\n|\n\r|[\r\n]")

def clean_scrolling_text(text: str) -> str:
    """
    Replaces CR / LF / CRLF / LFCR sequences with a single space for continuous scrolling.
    Consecutive line breaks collapse into a single space.
    """
    if not text:
        return ""
    return LINEBREAK_PATTERN.sub(" ", text)

def expand_script_tags_in_text(text: str) -> str:
    """
    Evaluates any inline <script.py> tags within text and substitutes their output string.
    """
    if not text:
        return ""
    
    def _replace_tag(match):
        tag_val = match.group(1)
        if tag_val.lower().endswith(".py"):
            script_id = tag_val[:-3]
            script = script_manager.get_script(script_id)
            if script:
                ok, res_text = script_manager.execute_script(script.get("code", ""))
                return res_text if ok else f"[{script_id}:ERR]"
            return f"[{script_id}]"
        return match.group(0)

    return TAG_REGEX.sub(_replace_tag, text)

def split_text_pages(text: str) -> List[str]:
    """
    Splits text by CR / LF / CRLF / LFCR sequences into separate display segments.
    Consecutive line breaks do not create empty segments.
    Expands inline script tags first so scripts outputting line breaks will also split into segments.
    """
    if not text:
        return [""]
    # First expand script tags so script-generated CR/LF properly create segments
    expanded = expand_script_tags_in_text(text)
    # Split by line breaks and filter out empty lines
    parts = [p.strip() for p in LINEBREAK_PATTERN.split(expanded)]
    non_empty = [p for p in parts if p]
    return non_empty if non_empty else [" "]

EMOJI_PATTERN = re.compile(
    r"("
    r"[\U0001F1E6-\U0001F1FF]{2}"  # Regional indicator pair (national flags)
    r"|"
    r"\U0001F3F4[\U000E0020-\U000E007E]+\U000E007F"  # Subdivision flag (e.g. England, Scotland, Wales)
    r"|"
    r"(?:[\U0001F300-\U0001FAFF\u2600-\u27BF\u2300-\u23FF\u2B50-\u2B55\uD83C\uDDE6-\uDDFF]|[\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9-\u21AA\u25AA-\u25AB\u25B6\u25C0\u25FB-\u25FE\u3030\u303D\u3297\u3299])(?:\uFE0F)?"
    r"(?:\u200D(?:[\U0001F300-\U0001FAFF\u2600-\u27BF\u2300-\u23FF\u2B50-\u2B55]|[\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9-\u21AA\u25AA-\u25AB\u25B6\u25C0\u25FB-\u25FE\u3030\u303D\u3297\u3299])(?:\uFE0F)?)*"
    r")"
)

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
    - ('emoji', emoji_char_or_sequence)
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
            last = 0
            for m in EMOJI_PATTERN.finditer(val):
                if m.start() > last:
                    runs.append(("text", val[last:m.start()]))
                runs.append(("emoji", m.group(0)))
                last = m.end()
            if last < len(val):
                runs.append(("text", val[last:]))

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
    v_alignment: str = "middle",  # "top", "middle", "bottom"
    full_width: bool = False
) -> Tuple[Image.Image, int]:
    """
    Renders text, emojis, and inline <image.png> tags into an image.
    If full_width is True, the canvas width will accommodate the entire content (at least width).
    If full_width is True, any CR/LF sequences are cleaned to a single space.
    """
    if full_width:
        text = clean_scrolling_text(text)
    font = get_font_instance(font_id, font_size)
    runs = split_into_runs(text)

    # First pass: Measure total width of all runs
    dummy_img = Image.new("RGBA", (width * 8, height), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)
    dummy_draw.fontmode = "L" if antialias else "1"

    measured_runs = []
    total_content_width = 0

    emoji_size = min(height, max(10, font_size + 4))

    # Pre-process runs: expand script tags recursively so any emojis or sub-tags inside script output are preserved
    expanded_runs: List[Tuple[str, str]] = []
    for run_type, run_val in runs:
        if run_type == "script":
            script_id = run_val[:-3] if run_val.lower().endswith(".py") else run_val
            script = script_manager.get_script(script_id)
            eval_text = f"[{script_id}]"
            if script:
                ok, res_text = script_manager.execute_script(script.get("code", ""))
                eval_text = res_text if ok else f"[{script_id}:ERR]"
            # Parse the evaluated script text into individual text and emoji runs
            sub_runs = split_into_runs(eval_text)
            expanded_runs.extend(sub_runs)
        else:
            expanded_runs.append((run_type, run_val))

    for run_type, run_val in expanded_runs:
        if run_type == "emoji":
            measured_runs.append(("emoji", run_val, emoji_size, None))
            total_content_width += emoji_size
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

    actual_canvas_w = max(width, total_content_width) if full_width else width

    # Second pass: Starting X position
    if full_width or alignment == "left":
        start_x = 0
    elif alignment == "right":
        start_x = max(0, width - total_content_width)
    else:  # "center"
        start_x = max(0, (width - total_content_width) // 2)

    # Canvas creation
    canvas = Image.new("RGBA", (actual_canvas_w, height), bg_color)
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
