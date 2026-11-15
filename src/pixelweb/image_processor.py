import io
import math
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ImageOps

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class ImageManager:
    def __init__(self):
        # In-memory store for temporary editing layers and previews
        self._mem_cache: Dict[str, bytes] = {}

    def get_in_memory_image(self, filename: str) -> Optional[bytes]:
        """Retrieve in-memory image bytes if present."""
        return self._mem_cache.get(filename)

    def set_in_memory_image(self, filename: str, data: bytes) -> None:
        """Store in-memory image bytes, keeping cache size bounded."""
        self._mem_cache[filename] = data
        if len(self._mem_cache) > 20:
            # Evict oldest entries
            oldest_keys = list(self._mem_cache.keys())[:5]
            for k in oldest_keys:
                self._mem_cache.pop(k, None)

    def list_images(self) -> List[Dict[str, Any]]:
        """
        Lists only genuine user artifacts (uploads and saved edited creations).
        Excludes transient temporary previews and rendered frames.
        """
        images = []
        for f in sorted(UPLOAD_DIR.glob("*.*")):
            if f.name.startswith("__") or f.name.startswith("rendered_msg_") or f.name.startswith("temp_"):
                continue
            if f.suffix.lower() in [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"]:
                try:
                    stat = f.stat()
                    with Image.open(f) as img:
                        w, h = img.size
                    images.append({
                        "filename": f.name,
                        "path": str(f),
                        "width": w,
                        "height": h,
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
                except Exception as e:
                    print(f"Error reading image {f}: {e}")
        return images

    def get_image_path(self, filename: str) -> Optional[Path]:
        p = UPLOAD_DIR / filename
        if p.exists():
            return p
        return None

    def delete_image(self, filename: str) -> bool:
        if filename in self._mem_cache:
            del self._mem_cache[filename]
        target = UPLOAD_DIR / filename
        if target.exists():
            target.unlink()
            return True
        return False

    def remove_background(
        self,
        img: Image.Image,
        key_color_hex: str = "#FFFFFF",
        tolerance: int = 30
    ) -> Image.Image:
        """
        Replaces pixels matching key_color within Euclidean tolerance with transparency.
        """
        img = img.convert("RGBA")
        key_color = key_color_hex.lstrip("#")
        if len(key_color) == 6:
            r_key = int(key_color[0:2], 16)
            g_key = int(key_color[2:4], 16)
            b_key = int(key_color[4:6], 16)
        else:
            r_key, g_key, b_key = 255, 255, 255

        # Maximum color distance threshold
        max_dist = (tolerance / 100.0) * math.sqrt(255**2 + 255**2 + 255**2)

        data = img.getdata()
        new_data = []
        for item in data:
            # item is (r, g, b, a)
            dist = math.sqrt((item[0] - r_key)**2 + (item[1] - g_key)**2 + (item[2] - b_key)**2)
            if dist <= max_dist:
                new_data.append((item[0], item[1], item[2], 0))  # Fully transparent
            else:
                new_data.append(item)

        img.putdata(new_data)
        return img

    def swap_color(
        self,
        img: Image.Image,
        src_color_hex: str,
        dst_color_hex: str,
        tolerance: int = 30
    ) -> Image.Image:
        """
        Replaces pixels matching src_color within Euclidean tolerance with dst_color.
        Preserves alpha channel.
        """
        img = img.convert("RGBA")
        src_clean = src_color_hex.lstrip("#")
        dst_clean = dst_color_hex.lstrip("#")

        r_src = int(src_clean[0:2], 16) if len(src_clean) == 6 else 255
        g_src = int(src_clean[2:4], 16) if len(src_clean) == 6 else 255
        b_src = int(src_clean[4:6], 16) if len(src_clean) == 6 else 255

        r_dst = int(dst_clean[0:2], 16) if len(dst_clean) == 6 else 0
        g_dst = int(dst_clean[2:4], 16) if len(dst_clean) == 6 else 0
        b_dst = int(dst_clean[4:6], 16) if len(dst_clean) == 6 else 0

        max_dist = (tolerance / 100.0) * math.sqrt(255**2 + 255**2 + 255**2)

        data = img.getdata()
        new_data = []
        for item in data:
            dist = math.sqrt((item[0] - r_src)**2 + (item[1] - g_src)**2 + (item[2] - b_src)**2)
            if dist <= max_dist and item[3] > 0:  # Only swap non-transparent pixels
                new_data.append((r_dst, g_dst, b_dst, item[3]))
            else:
                new_data.append(item)

        img.putdata(new_data)
        return img

    def swap_colors_multi(
        self,
        img: Image.Image,
        swaps: List[Dict[str, Any]]
    ) -> Image.Image:
        """
        Performs multiple sequential color swaps with individual tolerances.
        swaps: list of dicts with 'from_hex', 'to_hex', 'tolerance'
        """
        img = img.convert("RGBA")
        parsed_swaps = []
        for s in swaps:
            src_clean = s.get("from_hex", "#FFFFFF").lstrip("#")
            dst_clean = s.get("to_hex", "#000000").lstrip("#")
            r_src = int(src_clean[0:2], 16) if len(src_clean) == 6 else 255
            g_src = int(src_clean[2:4], 16) if len(src_clean) == 6 else 255
            b_src = int(src_clean[4:6], 16) if len(src_clean) == 6 else 255
            r_dst = int(dst_clean[0:2], 16) if len(dst_clean) == 6 else 0
            g_dst = int(dst_clean[2:4], 16) if len(dst_clean) == 6 else 0
            b_dst = int(dst_clean[4:6], 16) if len(dst_clean) == 6 else 0
            tol = int(s.get("tolerance", 25))
            max_dist = (tol / 100.0) * math.sqrt(255**2 + 255**2 + 255**2)
            parsed_swaps.append((r_src, g_src, b_src, r_dst, g_dst, b_dst, max_dist))

        data = img.getdata()
        new_data = []
        for item in data:
            if item[3] == 0:
                new_data.append(item)
                continue
            r, g, b, a = item
            # Evaluate against swaps in order
            for r_src, g_src, b_src, r_dst, g_dst, b_dst, max_dist in parsed_swaps:
                dist = math.sqrt((r - r_src)**2 + (g - g_src)**2 + (b - b_src)**2)
                if dist <= max_dist:
                    r, g, b = r_dst, g_dst, b_dst
                    break
            new_data.append((r, g, b, a))

        img.putdata(new_data)
        return img

    def process_and_save(
        self,
        source_filename: str,
        output_filename: str,
        crop_box: Optional[Tuple[int, int, int, int]] = None,
        resize_dim: Optional[Tuple[int, int]] = None,
        remove_bg: bool = False,
        bg_key_hex: str = "#FFFFFF",
        bg_tolerance: int = 30,
        swap_color_enabled: bool = False,
        swap_src_hex: str = "#FF0000",
        swap_dst_hex: str = "#00FF00",
        swap_tolerance: int = 30,
        color_swaps: Optional[List[Dict[str, Any]]] = None,
        antialias: bool = True,
        is_temporary: bool = False
    ) -> Dict[str, Any]:
        # Check in-memory cache first, then disk
        if source_filename in self._mem_cache:
            img = Image.open(io.BytesIO(self._mem_cache[source_filename]))
        else:
            src_path = self.get_image_path(source_filename)
            if not src_path or not src_path.exists():
                raise FileNotFoundError(f"File {source_filename} not found")
            img = Image.open(src_path)

        with img:
            img = img.convert("RGBA")

            # 1. Crop if specified
            if crop_box:
                x0, y0, x1, y1 = crop_box
                x0 = max(0, min(img.width - 1, x0))
                y0 = max(0, min(img.height - 1, y0))
                x1 = max(x0 + 1, min(img.width, x1))
                y1 = max(y0 + 1, min(img.height, y1))
                img = img.crop((x0, y0, x1, y1))

            # 2. Multi-color swaps if provided, or single legacy swap
            if color_swaps and len(color_swaps) > 0:
                img = self.swap_colors_multi(img, color_swaps)
            elif swap_color_enabled:
                img = self.swap_color(img, src_color_hex=swap_src_hex, dst_color_hex=swap_dst_hex, tolerance=swap_tolerance)

            # 3. Remove background if specified
            if remove_bg:
                img = self.remove_background(img, key_color_hex=bg_key_hex, tolerance=bg_tolerance)

            # 4. Resize if specified
            if resize_dim and resize_dim[0] > 0 and resize_dim[1] > 0:
                resample = Image.Resampling.LANCZOS if antialias else Image.Resampling.NEAREST
                img = img.resize(resize_dim, resample)

            clean_name = output_filename.strip()
            if not any(clean_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                clean_name += ".png"

            # Check if this is a temporary edit/layer or a permanent save
            is_temp = is_temporary or clean_name.startswith("__")

            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True, compress_level=9)
            img_bytes = buf.getvalue()

            if is_temp:
                # Keep completely in memory
                self.set_in_memory_image(clean_name, img_bytes)
                file_size = len(img_bytes)
            else:
                # Permanent save directly to UPLOAD_DIR
                dest_path = UPLOAD_DIR / clean_name
                with open(dest_path, "wb") as f:
                    f.write(img_bytes)
                file_size = dest_path.stat().st_size

            return {
                "filename": clean_name,
                "width": img.width,
                "height": img.height,
                "size": file_size
            }

image_manager = ImageManager()
