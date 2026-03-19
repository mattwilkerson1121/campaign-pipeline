import argparse
from pathlib import Path

from loguru import logger

from creative_pipeline.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="creative-pipeline",
        description="Proof-of-concept creative automation pipeline for social ads.",
    )
    parser.add_argument(
        "--brief",
        required=True,
        help="Path to campaign brief (JSON or YAML).",
    )
    parser.add_argument(
        "--assets-dir",
        default="assets",
        help="Directory containing input assets (default: assets).",
    )
    parser.add_argument(
        "--outputs-dir",
        default="outputs",
        help="Directory to write outputs (default: outputs).",
    )
    parser.add_argument(
        "--localize",
        action="store_true",
        help="Translate the campaign message into target languages inferred from brief 'region' values.",
    )
    parser.add_argument(
        "--no-genai",
        action="store_true",
        help="Disable GenAI calls and always use local placeholder generation.",
    )
    parser.add_argument(
        "--openai-api-key",
        default=None,
        help="OpenAI API key (overrides OPENAI_API_KEY env var).",
    )
    parser.add_argument(
        "--openai-image-model",
        default="gpt-image-1",
        help="OpenAI image model to use (default: gpt-image-1).",
    )
    parser.add_argument(
        "--image-prompt",
        default=None,
        help="Optional: extra guidance appended to the image generation prompt.",
    )
    args = parser.parse_args(argv)

    brief_path = Path(args.brief)
    assets_dir = Path(args.assets_dir)
    outputs_dir = Path(args.outputs_dir)

    logger.info("Brief: {}", brief_path)
    logger.info("Assets dir: {}", assets_dir)
    logger.info("Outputs dir: {}", outputs_dir)

    report = run_pipeline(
        brief_path=brief_path,
        assets_dir=assets_dir,
        outputs_dir=outputs_dir,
        localize=args.localize,
        enable_genai=not args.no_genai,
        openai_api_key=args.openai_api_key,
        openai_image_model=args.openai_image_model,
        image_prompt_override=args.image_prompt,
    )

    logger.info("Done. Products processed: {}", report["products_processed"])
    if report["warnings"]:
        logger.warning("Warnings:")
        for w in report["warnings"]:
            logger.warning(" - {}", w)
    return 0
