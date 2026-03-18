from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from loguru import logger
from PIL import Image


@dataclass(frozen=True)
class GenAIResult:
    image: Image.Image
    used_provider: str


def _placeholder_image(product_name: str, audience: str) -> Image.Image:
    # Fast local fallback: simple, deterministic-ish "hero" image.
    w, h = 1024, 1024
    img = Image.new("RGB", (w, h), color=(245, 247, 250))
    return img


def generate_hero_image(
    *,
    product_name: str,
    audience: str,
    campaign_message: str,
    enable_genai: bool,
    openai_api_key: str | None,
    openai_image_model: str,
    openai_image_size: str,
    image_prompt: str | None,
    seed_image: Image.Image | None,
) -> GenAIResult:
    if not enable_genai:
        return GenAIResult(
            image=_placeholder_image(product_name, audience),
            used_provider="placeholder",
        )

    try:
        from openai import OpenAI  # type: ignore
    except Exception as e:
        logger.warning("OpenAI SDK import failed (falling back): {}", e)
        return GenAIResult(
            image=_placeholder_image(product_name, audience),
            used_provider="placeholder",
        )

    extra = (image_prompt or "").strip()
    extra_block = f"\nAdditional guidance:\n{extra}\n" if extra else ""

    prompt = (
        "Create a clean commercial product advertising hero image.\n"
        f"Product: {product_name}\n"
        f"Target audience: {audience}\n"
        f"Campaign message (do not render as text): {campaign_message}\n"
        f"{extra_block}"
        "Style: modern, bright, lifestyle, social-ad ready, minimal background, high quality.\n"
        "No logos, no trademarks, no readable text."
    )

    try:
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY is not set (falling back to placeholder).")
            return GenAIResult(
                image=_placeholder_image(product_name, audience),
                used_provider="placeholder",
            )

        client = OpenAI(api_key=api_key)
        # If a seed image is provided, do an "edits-style" request (img2img-ish).
        # Otherwise, do normal text-to-image generation.
        if seed_image is not None:
            buf = BytesIO()
            seed_image.convert("RGBA").save(buf, format="PNG")
            buf.seek(0)
            # The OpenAI SDK accepts file-like objects; giving it a name improves multipart handling.
            buf.name = "seed.png"  # type: ignore[attr-defined]
            resp = client.images.edits(
                model=openai_image_model,
                image=buf,
                prompt=prompt,
                size=openai_image_size,
            )
            used = f"openai:{openai_image_model}:edits"
        else:
            resp = client.images.generate(
                model=openai_image_model,
                prompt=prompt,
                size=openai_image_size,
            )
            used = f"openai:{openai_image_model}:generate"

        b64 = resp.data[0].b64_json
        raw = base64.b64decode(b64)
        img = Image.open(BytesIO(raw)).convert("RGB")
        return GenAIResult(image=img, used_provider=used)
    except Exception as e:
        logger.warning("GenAI generation failed (falling back): {}", e)
        return GenAIResult(
            image=_placeholder_image(product_name, audience),
            used_provider="placeholder",
        )


def load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")

