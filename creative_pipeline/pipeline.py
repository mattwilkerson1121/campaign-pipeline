from __future__ import annotations

import re
from pathlib import Path

from loguru import logger
from PIL import Image

from creative_pipeline.brief import CampaignBrief, load_brief
from creative_pipeline.checks import brand_compliance_check, legal_word_check
from creative_pipeline.genai import GenAIResult, generate_hero_image, load_image
from creative_pipeline.image_ops import ASPECT_RATIOS, OverlaySpec, add_text_overlay, contain_resize, ensure_dir, overlay_logo


def _resolve_asset_path(product_name: str, asset_field: str | None, assets_dir: Path) -> Path | None:
    candidates: list[Path] = []
    if asset_field:
        p = Path(asset_field)
        candidates.append(p)
        if not p.is_absolute():
            candidates.append(assets_dir / asset_field)
    # common convention: assets/<product>.png
    candidates.append(assets_dir / f"{product_name}.png")
    candidates.append(assets_dir / f"{product_name}.jpg")

    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _safe_region_dir_name(region: str) -> str:
    cleaned = region.strip().replace(" ", "_")
    cleaned = re.sub(r'[\/\\:*?"<>|]+', "_", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)
    return cleaned or "unknown"


def _infer_target_language(region: str) -> str:
    token = (region or "").strip()
    if not token:
        return "English"

    lower = token.lower()

    # Treat common country/market codes as languages.
    region_to_language: dict[str, str] = {
        "us": "English",
        "usa": "English",
        "united states": "English",
        "uk": "English",
        "gb": "English",
        "united kingdom": "English",
        "ca": "English",
        "canada": "English",
        "au": "English",
        "au.": "English",
        "australia": "English",
        "nz": "English",
        "new zealand": "English",
        "de": "German",
        "germany": "German",
        "at": "German",
        "austria": "German",
        "ch": "German",
        "switzerland (de)": "German",
        "fr": "French",
        "france": "French",
        "es": "Spanish",
        "spain": "Spanish",
        "it": "Italian",
        "italy": "Italian",
        "pt": "Portuguese",
        "portugal": "Portuguese",
        "br": "Portuguese",
        "brazil": "Portuguese",
        "nl": "Dutch",
        "netherlands": "Dutch",
        "se": "Swedish",
        "sweden": "Swedish",
        "no": "Norwegian",
        "norway": "Norwegian",
        "pl": "Polish",
        "poland": "Polish",
        "ru": "Russian",
        "russia": "Russian",
        "ja": "Japanese",
        "japan": "Japanese",
        "ko": "Korean",
        "korea": "Korean",
        "cn": "Chinese",
        "china": "Chinese",
        "zh": "Chinese",
        "ar": "Arabic",
        "sa": "Arabic",
        "arabic": "Arabic",
        "he": "Hebrew",
        "iw": "Hebrew",
        "hebrew": "Hebrew",
    }

    lang_codes: dict[str, str] = {
        "en": "English",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "nl": "Dutch",
        "sv": "Swedish",
        "no": "Norwegian",
        "pl": "Polish",
        "ru": "Russian",
        "uk": "Ukrainian",
        "tr": "Turkish",
        "cs": "Czech",
        "ro": "Romanian",
        "hu": "Hungarian",
        "ar": "Arabic",
        "he": "Hebrew",
        "ja": "Japanese",
        "ko": "Korean",
        "zh": "Chinese",
        "id": "Indonesian",
        "th": "Thai",
        "vi": "Vietnamese",
        "ms": "Malay",
    }

    if lower in region_to_language:
        return region_to_language[lower]

    # Handle explicit language codes like "es", "pt-BR", "fr-FR".
    m = re.match(r"^([a-z]{2})(-[a-z]{2})?$", lower)
    if m:
        base = m.group(1)
        return lang_codes.get(base, base)

    # Treat the provided token as a language name if we can't infer it.
    return token


def _is_english_language(language: str) -> bool:
    l = (language or "").strip().lower()
    return l == "english" or l.startswith("en")


def _translate_message(*, text: str, target_language: str, openai_api_key: str | None) -> str:
    if _is_english_language(target_language):
        return text

    if not openai_api_key:
        # Fallback when no API key is available: keep English copy (no region/language text).
        return text

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "You translate marketing copy. Output ONLY the translated text (no quotes, no explanations).",
                },
                {
                    "role": "user",
                    "content": f"Translate into {target_language}:\n\n{text}",
                },
            ],
        )
        translated = resp.choices[0].message.content or ""
        translated = translated.strip()
        return translated or text
    except Exception as e:
        logger.warning("Translation failed (falling back): {}", e)
        return text


def _write_image(img: Image.Image, path: Path) -> None:
    ensure_dir(path.parent)
    img.save(path, format="PNG", optimize=True)


def _generate_or_load_hero(
    *,
    brief: CampaignBrief,
    product_name: str,
    asset_path: Path | None,
    enable_genai: bool,
    openai_api_key: str | None,
    openai_image_model: str,
    openai_image_size: str,
    image_prompt: str | None,
    seed_image: Image.Image | None,
    regenerate_assets: bool,
) -> GenAIResult:
    if asset_path is not None and not regenerate_assets:
        logger.info("Using existing asset for {}: {}", product_name, asset_path)
        return GenAIResult(image=load_image(asset_path).convert("RGB"), used_provider="input-asset")

    logger.info("Missing asset for {}. Generating new hero image.", product_name)
    return generate_hero_image(
        product_name=product_name,
        audience=brief.audience,
        campaign_message=brief.message,
        enable_genai=enable_genai,
        openai_api_key=openai_api_key,
        openai_image_model=openai_image_model,
        openai_image_size=openai_image_size,
        image_prompt=image_prompt,
        seed_image=seed_image,
    )


def run_pipeline(
    *,
    brief_path: Path,
    assets_dir: Path,
    outputs_dir: Path,
    localize: bool,
    enable_genai: bool,
    openai_api_key: str | None,
    openai_image_model: str,
    image_prompt_override: str | None,
    company_name: str | None = None,
    brand_primary_hex: str | None = None,
    logo_image: Image.Image | None = None,
    seed_image: Image.Image | None = None,
    regenerate_assets: bool = False,
) -> dict:
    # OpenAI supports only a limited set of pixel sizes. We generate one hero image
    # per target aspect ratio so composition stays consistent when we place it
    # into the final creative formats.
    ratio_to_openai_image_size: dict[str, str] = {
        "1:1": "1024x1024",
        "9:16": "1024x1536",
        "16:9": "1536x1024",
    }

    brief = load_brief(brief_path)
    warnings: list[str] = []

    warnings.extend(legal_word_check(brief.message).warnings)

    # Precompute region-specific translated messages so hero images are generated once (English).
    region_messages: dict[str, str] = {}
    language_cache: dict[str, str] = {}
    for region in brief.regions:
        target_language = _infer_target_language(region)
        if not localize or _is_english_language(target_language):
            region_messages[region] = brief.message
            continue
        if target_language not in language_cache:
            language_cache[target_language] = _translate_message(
                text=brief.message,
                target_language=target_language,
                openai_api_key=openai_api_key,
            )
        region_messages[region] = language_cache[target_language]

    for product in brief.products:
        asset_path = _resolve_asset_path(product.name, product.asset, assets_dir)
        image_prompt = image_prompt_override or product.image_prompt or brief.image_prompt
        heroes_by_ratio: dict[str, GenAIResult] = {}
        for ratio_key in ASPECT_RATIOS.keys():
            heroes_by_ratio[ratio_key] = _generate_or_load_hero(
                brief=brief,
                product_name=product.name,
                asset_path=asset_path,
                enable_genai=enable_genai,
                openai_api_key=openai_api_key,
                openai_image_model=openai_image_model,
                openai_image_size=ratio_to_openai_image_size[ratio_key],
                image_prompt=image_prompt,
                seed_image=seed_image,
                regenerate_assets=regenerate_assets,
            )
            logger.info(
                "Hero image provider for {} ({}) : {}",
                product.name,
                ratio_key,
                heroes_by_ratio[ratio_key].used_provider,
            )

        generated_image = any(h.used_provider != "input-asset" for h in heroes_by_ratio.values())
        warnings.extend(
            brand_compliance_check(
                image=heroes_by_ratio.get("1:1", next(iter(heroes_by_ratio.values()))).image,
                logo_image_provided=logo_image is not None,
                generated_image=generated_image,
            ).warnings
        )
        for region in brief.regions:
            region_dir = _safe_region_dir_name(region)
            final_message = region_messages[region]

            product_out_root = outputs_dir / brief.campaign_name / region_dir / product.name

            for ratio_key, (tw, th) in ASPECT_RATIOS.items():
                logger.info("Creating {} variant for {} ({})", ratio_key, product.name, region)
                hero = heroes_by_ratio[ratio_key]
                variant = contain_resize(
                    hero.image,
                    tw,
                    th,
                    background_hex=brand_primary_hex,
                )
                variant = add_text_overlay(
                    variant,
                    OverlaySpec(
                        message=final_message,
                        product_name=product.name,
                        company_name=company_name,
                        brand_hex=brand_primary_hex,
                    ),
                )
                if logo_image is not None:
                    variant = overlay_logo(variant, logo_image)
                out_path = product_out_root / ratio_key / "ad.png"
                _write_image(variant, out_path)
                logger.info("Saved {}", out_path)

    return {
        "products_processed": len(brief.products),
        "regions_processed": len(brief.regions),
        "warnings": warnings,
    }

