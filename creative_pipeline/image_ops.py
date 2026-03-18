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


@dataclass(frozen=True)
class OverlaySpec:
    message: str
    product_name: str
    company_name: str | None = None
    brand_hex: str | None = None


def add_text_overlay(img: Image.Image, spec: OverlaySpec) -> Image.Image:
    base = img.convert("RGBA")
    w, h = base.size

    # Semi-transparent gradient-ish banner at bottom for legibility.
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

    try:
        font_big = ImageFont.truetype("Arial.ttf", size=max(28, int(h * 0.045)))
        font_small = ImageFont.truetype("Arial.ttf", size=max(18, int(h * 0.028)))
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    pad = int(min(w, h) * 0.045)
    x = pad
    y = h - banner_h + pad

    # Product line
    prefix = f"{spec.company_name}  •  " if spec.company_name else ""
    product_line = f"{prefix}{spec.product_name}"
    draw.text((x, y), product_line, font=font_small, fill=(255, 255, 255, 235))
    y += int(font_small.size * 1.6) if hasattr(font_small, "size") else 26

    # Message (single or wrapped-ish with naive splitting)
    msg = spec.message.strip()
    lines: list[str] = []
    max_chars = 42 if w <= 1080 else 60
    while msg:
        if len(msg) <= max_chars:
            lines.append(msg)
            break
        cut = msg.rfind(" ", 0, max_chars)
        if cut == -1:
            cut = max_chars
        lines.append(msg[:cut].strip())
        msg = msg[cut:].strip()

    for line in lines[:3]:
        draw.text((x, y), line, font=font_big, fill=(255, 255, 255, 245))
        y += int(font_big.size * 1.25) if hasattr(font_big, "size") else 34

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

