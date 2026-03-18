from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ASPECT_RATIOS: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


def cover_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src = img.convert("RGB")
    sw, sh = src.size
    scale = max(target_w / sw, target_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = src.resize((nw, nh), resample=Image.Resampling.LANCZOS)

    left = (nw - target_w) // 2
    top = (nh - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def contain_resize(
    img: Image.Image,
    target_w: int,
    target_h: int,
    *,
    background_hex: str | None = None,
) -> Image.Image:
    """Scale the image to fit entirely within the frame; letterbox/pillarbox with background fill so the product is always in frame."""
    src = img.convert("RGB")
    sw, sh = src.size
    scale = min(target_w / sw, target_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    nw, nh = max(1, nw), max(1, nh)
    resized = src.resize((nw, nh), resample=Image.Resampling.LANCZOS)
    # Center on canvas
    x = (target_w - nw) // 2
    y = (target_h - nh) // 2
    if background_hex:
        try:
            rgb = hex_to_rgb(background_hex)
            canvas = Image.new("RGB", (target_w, target_h), rgb)
        except Exception:
            canvas = Image.new("RGB", (target_w, target_h), (40, 40, 45))
    else:
        canvas = Image.new("RGB", (target_w, target_h), (40, 40, 45))
    canvas.paste(resized, (x, y))
    return canvas


@dataclass(frozen=True)
class OverlaySpec:
    message: str  # Campaign message shown in the bottom banner
    product_name: str
    company_name: str | None = None
    brand_hex: str | None = None
    overlay_text: str | None = None  # Optional text drawn on the image (above the banner)


def _wrap_text_to_width(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, max_px_width: int) -> list[str]:
    """Split text into lines that do not exceed max_px_width when drawn with the given font."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = (current + [word]) if current else [word]
        line_str = " ".join(candidate)
        bbox = draw.textbbox((0, 0), line_str, font=font)
        line_w = bbox[2] - bbox[0]
        if line_w <= max_px_width:
            current = candidate
        else:
            if current:
                lines.append(" ".join(current))
            current = [word] if (draw.textbbox((0, 0), word, font=font)[2] - draw.textbbox((0, 0), word, font=font)[0] <= max_px_width) else []
            if current:
                continue
            # Single word longer than width: break by character not supported here; keep as one line
            lines.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _text_block_height(draw: ImageDraw.Draw, lines: list[str], font: ImageFont.FreeTypeFont | ImageFont.ImageFont, line_spacing: float = 1.25) -> int:
    """Total pixel height of a block of text with the given line spacing."""
    if not lines:
        return 0
    line_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = max(line_height, bbox[3] - bbox[1])
    return int(line_height * (1 + (len(lines) - 1) * line_spacing)) if line_height else 0


def add_text_overlay(img: Image.Image, spec: OverlaySpec) -> Image.Image:
    base = img.convert("RGBA")
    w, h = base.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    banner_h = int(h * 0.28)
    banner_color = (0, 0, 0, 140)
    if spec.brand_hex:
        try:
            rgb = hex_to_rgb(spec.brand_hex)
            banner_color = (rgb[0], rgb[1], rgb[2], 160)
        except Exception:
            banner_color = (0, 0, 0, 140)
    draw.rectangle([(0, h - banner_h), (w, h)], fill=banner_color)

    pad = int(min(w, h) * 0.045)
    content_left = pad
    content_width = max(1, w - 2 * pad)
    banner_top = h - banner_h
    content_top = banner_top + pad
    content_bottom = h - pad
    available_height = content_bottom - content_top

    min_font_big = 14
    min_font_small = 12
    max_lines = 5

    # ---- Overlay text on the image (above the banner) ----
    overlay_str = (spec.overlay_text or "").strip()
    if overlay_str:
        overlay_zone_top = pad
        overlay_zone_bottom = banner_top - pad
        overlay_zone_height = max(1, overlay_zone_bottom - overlay_zone_top)
        overlay_width = content_width
        font_overlay_size = max(min_font_big, int(h * 0.055))
        overlay_lines: list[str] = []
        font_overlay = None
        for try_size in range(font_overlay_size, min_font_big - 1, -2):
            try:
                font_overlay = ImageFont.truetype("Arial.ttf", size=try_size)
            except Exception:
                font_overlay = ImageFont.load_default()
            raw = _wrap_text_to_width(draw, overlay_str, font_overlay, overlay_width)
            overlay_lines = raw[:max_lines]
            block_h = _text_block_height(draw, overlay_lines, font_overlay, line_spacing=1.25)
            if block_h <= overlay_zone_height:
                break
        if font_overlay is None:
            try:
                font_overlay = ImageFont.truetype("Arial.ttf", size=min_font_big)
            except Exception:
                font_overlay = ImageFont.load_default()
            overlay_lines = _wrap_text_to_width(draw, overlay_str, font_overlay, overlay_width)[:max_lines]
        # Center overlay text vertically in the image zone; draw shadow then text for legibility
        total_overlay_h = _text_block_height(draw, overlay_lines, font_overlay, line_spacing=1.25)
        y_overlay = overlay_zone_top + (overlay_zone_height - total_overlay_h) // 2
        shadow_offset = max(1, int(h * 0.004))
        for line in overlay_lines:
            bbox = draw.textbbox((0, 0), line, font=font_overlay)
            line_h = bbox[3] - bbox[1]
            if y_overlay + line_h > overlay_zone_bottom:
                break
            line_w = bbox[2] - bbox[0]
            x_center = content_left + (content_width - line_w) // 2
            draw.text((x_center + shadow_offset, y_overlay + shadow_offset), line, font=font_overlay, fill=(0, 0, 0, 180))
            draw.text((x_center, y_overlay), line, font=font_overlay, fill=(255, 255, 255, 250))
            y_overlay += int(line_h * 1.25)

    # ---- Banner: product line + campaign message ----
    try:
        font_small = ImageFont.truetype("Arial.ttf", size=max(min_font_small, int(h * 0.028)))
    except Exception:
        font_small = ImageFont.load_default()

    prefix = f"{spec.company_name}  •  " if spec.company_name else ""
    product_line = f"{prefix}{spec.product_name}"
    product_bbox = draw.textbbox((0, 0), product_line, font=font_small)
    product_line_h = product_bbox[3] - product_bbox[1]
    if product_bbox[2] - product_bbox[0] > content_width:
        for size in range(max(min_font_small, int(h * 0.028)), min_font_small - 1, -2):
            try:
                font_small = ImageFont.truetype("Arial.ttf", size=size)
            except Exception:
                continue
            bbox = draw.textbbox((0, 0), product_line, font=font_small)
            if bbox[2] - bbox[0] <= content_width:
                product_line_h = bbox[3] - bbox[1]
                break
    available_msg_height = available_height - product_line_h - int(product_line_h * 0.3)

    msg = spec.message.strip()
    font_size_big = max(min_font_big, int(h * 0.045))
    message_lines: list[str] = []
    font_big = None
    for try_size in range(font_size_big, min_font_big - 1, -2):
        try:
            font_big = ImageFont.truetype("Arial.ttf", size=try_size)
        except Exception:
            font_big = ImageFont.load_default()
        raw_lines = _wrap_text_to_width(draw, msg, font_big, content_width)
        message_lines = raw_lines[:max_lines]
        block_h = _text_block_height(draw, message_lines, font_big, line_spacing=1.25)
        if block_h <= available_msg_height:
            break
    if font_big is None:
        try:
            font_big = ImageFont.truetype("Arial.ttf", size=min_font_big)
        except Exception:
            font_big = ImageFont.load_default()
        message_lines = _wrap_text_to_width(draw, msg, font_big, content_width)[:max_lines]

    y = content_top
    draw.text((content_left, y), product_line, font=font_small, fill=(255, 255, 255, 235))
    y += product_line_h + int(product_line_h * 0.3)

    for line in message_lines:
        bbox = draw.textbbox((0, 0), line, font=font_big)
        line_height_px = bbox[3] - bbox[1]
        if y + line_height_px > content_bottom:
            break
        draw.text((content_left, y), line, font=font_big, fill=(255, 255, 255, 245))
        y += int(line_height_px * 1.25)

    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join([c * 2 for c in v])
    if len(v) != 6:
        raise ValueError("hex color must be 3 or 6 digits")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def overlay_logo(img: Image.Image, logo: Image.Image, *, max_width_frac: float = 0.18) -> Image.Image:
    base = img.convert("RGBA")
    w, h = base.size
    l = logo.convert("RGBA")

    target_w = max(48, int(w * max_width_frac))
    scale = min(1.0, target_w / max(l.size[0], 1))
    nw, nh = int(l.size[0] * scale), int(l.size[1] * scale)
    l = l.resize((max(1, nw), max(1, nh)), resample=Image.Resampling.LANCZOS)

    pad = int(min(w, h) * 0.03)
    x = w - l.size[0] - pad
    y = pad

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    overlay.paste(l, (x, y), l)
    return Image.alpha_composite(base, overlay).convert("RGB")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

