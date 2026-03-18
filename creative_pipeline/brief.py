import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ProductBrief:
    name: str
    asset: str | None
    image_prompt: str | None


@dataclass(frozen=True)
class CampaignBrief:
    campaign_name: str
    regions: list[str]
    audience: str
    message: str
    overlay_text: str | None  # Optional text shown on the image; if None/empty, message is used
    image_prompt: str | None
    products: list[ProductBrief]


def _load_structured(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(raw)
    elif suffix == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(f"Unsupported brief type: {suffix} (use .json/.yaml/.yml)")
    if not isinstance(data, dict):
        raise ValueError("Brief root must be an object/dict")
    return data


def _parse_regions_field(value: Any) -> list[str]:
    if value is None:
        raise ValueError("Brief missing required field: region")
    if isinstance(value, list):
        items = [str(v).strip() for v in value]
    else:
        # Allow common separators: comma, semicolon, newlines.
        items = [p.strip() for p in re.split(r"[,\n;]+", str(value)) if p.strip()]
    regions = [it for it in items if it]
    if not regions:
        raise ValueError("Brief field 'region' must contain at least one non-empty target.")
    return regions


def load_brief(path: Path) -> CampaignBrief:
    data = _load_structured(path)

    required = ["campaign_name", "region", "audience", "message", "products"]
    missing = [k for k in required if k not in data or data[k] in (None, "")]
    if missing:
        raise ValueError(f"Brief missing required fields: {missing}")

    products_raw = data["products"]
    if not isinstance(products_raw, list) or len(products_raw) < 2:
        raise ValueError("Brief must contain 'products' as a list with at least 2 items")

    products: list[ProductBrief] = []
    for i, p in enumerate(products_raw):
        if not isinstance(p, dict):
            raise ValueError(f"Product at index {i} must be an object/dict")
        if not p.get("name"):
            raise ValueError(f"Product at index {i} is missing 'name'")
        asset = p.get("asset", None)
        if asset is not None and not isinstance(asset, str):
            raise ValueError(f"Product '{p['name']}' has non-string 'asset'")
        image_prompt = p.get("image_prompt", None)
        if image_prompt is not None and not isinstance(image_prompt, str):
            raise ValueError(f"Product '{p['name']}' has non-string 'image_prompt'")
        products.append(
            ProductBrief(name=str(p["name"]), asset=asset, image_prompt=image_prompt)
        )

    overlay_text = data.get("overlay_text")
    if overlay_text is not None and not isinstance(overlay_text, str):
        overlay_text = None

    return CampaignBrief(
        campaign_name=str(data["campaign_name"]),
        regions=_parse_regions_field(data["region"]),
        audience=str(data["audience"]),
        message=str(data["message"]),
        overlay_text=overlay_text.strip() if (overlay_text and str(overlay_text).strip()) else None,
        image_prompt=str(data["image_prompt"]) if data.get("image_prompt") else None,
        products=products,
    )

