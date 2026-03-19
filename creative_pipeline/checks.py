from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class CheckResult:
    warnings: list[str]


def legal_word_check(message: str) -> CheckResult:
    banned = ["guaranteed cure", "miracle","shit","fuck","bitch","asshole","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","damn","fuck you","shit","ass","bitch","retard"]
    m = message.lower()
    warnings: list[str] = []
    for phrase in banned:
        if phrase in m:
            warnings.append(f"Legal check: message contains prohibited phrase '{phrase}'")
    return CheckResult(warnings=warnings)


def brand_compliance_check(
    *,
    image: Image.Image,
    logo_image_provided: bool,
    generated_image: bool,
) -> CheckResult:
    # Intentionally simple "bonus" checks for the take-home:
    # - warn if generated creatives have no logo input provided
    # - check overall brightness isn't too dark (brand-safe readability)
    warnings: list[str] = []
    if generated_image and not logo_image_provided:
        warnings.append(
            "Brand check: no logo image provided for generated creatives"
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

