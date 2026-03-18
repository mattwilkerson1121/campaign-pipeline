from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class CheckResult:
    warnings: list[str]


def legal_word_check(message: str) -> CheckResult:
    banned = ["guaranteed cure", "miracle"]
    m = message.lower()
    warnings: list[str] = []
    for phrase in banned:
        if phrase in m:
            warnings.append(f"Legal check: message contains prohibited phrase '{phrase}'")
    return CheckResult(warnings=warnings)


def brand_compliance_check(
    *,
    asset_path: Path | None,
    image: Image.Image,
) -> CheckResult:
    # Intentionally simple "bonus" checks for the take-home:
    # - if a provided asset filename doesn't mention 'logo', warn
    # - check overall brightness isn't too dark (brand-safe readability)
    warnings: list[str] = []
    if asset_path is not None and "logo" not in asset_path.name.lower():
        warnings.append(
            "Brand check: provided asset filename doesn't mention 'logo' (toy heuristic)"
        )

    try:
        gray = image.convert("L")
        hist = gray.histogram()
        total = sum(hist) or 1
        avg = sum(i * c for i, c in enumerate(hist)) / total
        if avg < 55:
            warnings.append(
                "Brand check: image is very dark on average; text legibility may suffer"
            )
    except Exception:
        pass

    return CheckResult(warnings=warnings)

