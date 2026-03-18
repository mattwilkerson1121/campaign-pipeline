import json
import tempfile
import re
import hashlib
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image
from loguru import logger as loguru_logger

from creative_pipeline.pipeline import run_pipeline


def _parse_products(text: str) -> list[dict]:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    names = [ln for ln in lines if ln]
    if len(names) < 2:
        raise ValueError("Please enter at least two product names (one per line).")
    return [{"name": n, "asset": None} for n in names]


def _parse_product_names(text: str) -> list[str]:
    items = _parse_products(text)
    return [p["name"] for p in items]


def _parse_regions(text: str) -> list[str]:
    items = [p.strip() for p in re.split(r"[,\n;]+", text or "") if p.strip()]
    if not items:
        raise ValueError("Please enter at least one target region/market.")
    return items


def _safe_region_dir_name(region: str) -> str:
    cleaned = (region or "").strip().replace(" ", "_")
    cleaned = re.sub(r'[\/\\:*?"<>|]+', "_", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)
    return cleaned or "unknown"


def _save_upload_as_png(upload, out_path: Path) -> str:
    img = Image.open(upload).convert("RGB")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG", optimize=True)
    return out_path.name


def _load_uploaded_image(upload) -> Image.Image | None:
    if upload is None:
        return None
    return Image.open(upload).convert("RGBA")


st.set_page_config(page_title="Creative Pipeline Lite", layout="wide")

st.title("Creative Automation Pipeline")
st.caption("Fill out the brief in the sidebar, then generate creatives.")

# Keep sidebar inputs in session_state so we can populate them from an uploaded brief.
_DEFAULTS: dict[str, str] = {
    "company_name": "Acme Co.",
    "campaign_name": "web_campaign",
    "regions_text": "US",
    "audience": "young professionals",
    "message": "Stay refreshed this summer!",
    "overlay_text": "",
    "products_text": "SparkleWater\nFreshJuice",
    "art_direction": "Photoreal lifestyle, bright natural light, minimal premium background.",
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

with st.sidebar:
    st.header("Upload Existing Brief")

    brief_upload = st.file_uploader(
        "Upload existing brief (JSON)",
        type=["json"],
        accept_multiple_files=False,
        help="Auto-populates campaign_name/region/audience/message/products/image_prompt into the form.",
    )
    if brief_upload is not None:
        raw = brief_upload.getvalue()
        sig = hashlib.md5(raw).hexdigest()
        if st.session_state.get("_brief_import_sig") != sig:
            try:
                data = json.loads(raw.decode("utf-8"))
                st.session_state["_brief_import_sig"] = sig

                if isinstance(data, dict):
                    if isinstance(data.get("campaign_name"), str):
                        st.session_state["campaign_name"] = data["campaign_name"]

                    if "region" in data and data["region"] is not None:
                        if isinstance(data["region"], list):
                            regions_val = ",".join(str(x).strip() for x in data["region"] if str(x).strip())
                        else:
                            regions_val = str(data["region"])
                        if regions_val.strip():
                            st.session_state["regions_text"] = regions_val

                    if isinstance(data.get("audience"), str):
                        st.session_state["audience"] = data["audience"]

                    if isinstance(data.get("message"), str):
                        st.session_state["message"] = data["message"]

                    if "overlay_text" in data and isinstance(data.get("overlay_text"), str):
                        st.session_state["overlay_text"] = data["overlay_text"]

                    # App field name is `image_prompt`, but sidebar label is "Image art direction prompt".
                    if isinstance(data.get("image_prompt"), str):
                        st.session_state["art_direction"] = data["image_prompt"]

                    products_raw = data.get("products")
                    if isinstance(products_raw, list):
                        names: list[str] = []
                        for p in products_raw:
                            if isinstance(p, dict) and isinstance(p.get("name"), str) and p["name"].strip():
                                names.append(p["name"].strip())
                        if names:
                            st.session_state["products_text"] = "\n".join(names)

                st.success("Brief loaded into the form.")
            except Exception as e:
                st.error(f"Failed to load brief JSON: {e}")

    st.divider()

    st.header("Create New Brief")          

    company_name = st.text_input("Company name", key="company_name")
    campaign_name = st.text_input("Campaign name", key="campaign_name")
    regions_text = st.text_area(
        "Target regions / markets (comma or newline separated)",
        height=90,
        key="regions_text",
    )
    audience = st.text_input("Target audience", key="audience")
    message = st.text_area("Campaign message", key="message")
    overlay_text = st.text_area(
        "Text overlay (on image)",
        height=70,
        key="overlay_text",
        help="Optional. Text shown on the creative image. If empty, the campaign message is used.",
    )

    regions: list[str] = []
    try:
        regions = _parse_regions(regions_text)
    except Exception:
        regions = []

    st.subheader("Products (2+)")
    products_text = st.text_area(
        "Enter product names (one per line)",
        height=90,
        key="products_text",
    )
    product_names: list[str] = []
    try:
        product_names = _parse_product_names(products_text)
    except Exception:
        product_names = []

    regenerate_assets = st.checkbox(
        "Regenerate even if a product asset exists",
        value=False,
        help="If enabled, missing assets are generated even when local product assets are present.",
    )

    st.subheader("Brand")
    brand_primary = st.color_picker("Primary brand color", value="#0B5FFF")
    brand_secondary = st.color_picker("Secondary brand color", value="#FFB000")

    logo_upload = st.file_uploader("Upload logo (PNG preferred)", type=["png", "jpg", "jpeg", "webp"])
    seed_upload = st.file_uploader("Upload seed image (optional)", type=["png", "jpg", "jpeg", "webp"])

    st.subheader("Product assets (optional)")
    product_asset_uploads: dict[str, object] = {}
    for i, pn in enumerate(product_names):
        product_asset_uploads[pn] = st.file_uploader(
            f"Upload asset for {pn}",
            type=["png", "jpg", "jpeg", "webp"],
            key=f"asset_{i}",
        )

    st.subheader("GenAI art direction")
    art_direction = st.text_area(
        "Image art direction prompt",
        height=110,
        key="art_direction",
    )

    st.subheader("OpenAI")
    openai_api_key = st.text_input("OpenAI API key", value="", type="password")
    openai_model = st.text_input("Image model", value="gpt-image-1")
    openai_size = st.selectbox("Image size", options=["1024x1024", "1536x1024", "1024x1536"], index=0)

    col_a, col_b = st.columns(2)
    with col_a:
        generate_clicked = st.button("Generate creative", type="primary", use_container_width=True)
    with col_b:
        regenerate_clicked = st.button("Regenerate", use_container_width=True)

    st.divider()
    st.write("Outputs are written to `outputs/<campaign>/<region>/<product>/<ratio>/ad.png`.")


left, right = st.columns([0.35, 0.65], gap="large")

with left:
    st.subheader("Inputs preview")
    try:
        products = _parse_products(products_text)
        st.write(f"**Products:** {', '.join([p['name'] for p in products])}")
    except Exception as e:
        st.error(str(e))
        products = []

    st.write(f"**Company:** {company_name}")
    st.write(f"**Audience:** {audience}")
    st.write(f"**Regions:** {', '.join(regions) if regions else '(none)'}")
    st.write(f"**Brand colors:** {brand_primary}, {brand_secondary}")

    logo_img = _load_uploaded_image(logo_upload)
    seed_img = _load_uploaded_image(seed_upload)

    if products and product_names:
        for pn in product_names:
            up = product_asset_uploads.get(pn)
            if up is None:
                continue
            pn_img = _load_uploaded_image(up)
            if pn_img is not None:
                st.write(f"**Asset for {pn}:**")
                st.image(pn_img, use_container_width=True)

    if logo_img is not None:
        st.write("**Logo:**")
        st.image(logo_img, use_container_width=True)
    if seed_img is not None:
        st.write("**Seed image:**")
        st.image(seed_img, use_container_width=True)


def _run_generation() -> dict:
    # Create timestamped logs for this generation run.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_dir = Path("logs") / ts
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "generation.log"

    # Write both app-side steps and pipeline loguru output into the file.
    sink_id = loguru_logger.add(
        str(log_path),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
    )

    # We reuse the existing pipeline by writing a temp brief JSON file.
    try:
        loguru_logger.info("Starting campaign generation")
        loguru_logger.info(
            "campaign_name={} regions={} products={} regenerate_assets={}",
            campaign_name,
            regions,
            [pn for pn in product_names],
            regenerate_assets,
        )
        loguru_logger.info(
            "localize={} enable_genai={} openai_image_model={}",
            True,
            True,
            openai_model.strip() or "gpt-image-1",
        )

        products_with_assets: list[dict] = []
        assets_dir = Path("assets")
        assets_dir.mkdir(parents=True, exist_ok=True)
        loguru_logger.info("Preparing product assets")
        for pn in product_names:
            upload = product_asset_uploads.get(pn)
            asset_filename = None
            if upload is not None:
                loguru_logger.info("Saving uploaded asset for product={}", pn)
                asset_filename = _save_upload_as_png(
                    upload=upload,
                    out_path=assets_dir / f"{pn}.png",
                )
            products_with_assets.append({"name": pn, "asset": asset_filename})

        brief = {
            "campaign_name": campaign_name,
            "region": regions,
            "audience": audience,
            "message": message,
            "overlay_text": (overlay_text or "").strip() or None,
            "image_prompt": art_direction,
            "products": products_with_assets,
        }

        outputs_dir = Path("outputs")
        loguru_logger.info("Writing temp brief JSON and invoking pipeline")

        with tempfile.TemporaryDirectory() as td:
            brief_path = Path(td) / "brief.json"
            brief_path.write_text(json.dumps(brief, indent=2), encoding="utf-8")

            report = run_pipeline(
                brief_path=brief_path,
                assets_dir=assets_dir,
                outputs_dir=outputs_dir,
                localize=True,
                enable_genai=True,
                openai_api_key=openai_api_key.strip() or None,
                openai_image_model=openai_model.strip() or "gpt-image-1",
                openai_image_size=openai_size,
                image_prompt_override=None,
                company_name=company_name.strip() or None,
                brand_primary_hex=brand_primary,
                logo_image=logo_img,
                seed_image=seed_img,
                regenerate_assets=regenerate_assets,
            )

            loguru_logger.info("Pipeline finished. products_processed={}", report.get("products_processed"))
            # Expose log location to the UI after Streamlit re-renders.
            report["log_path"] = str(log_path)
            return report
    finally:
        # Avoid stacking multiple file sinks across Streamlit reruns.
        loguru_logger.remove(sink_id)


should_generate = generate_clicked or regenerate_clicked

with right:
    st.subheader("Generated creatives")

    if should_generate:
        if not products:
            st.error("Please enter at least two products.")
        elif not regions:
            st.error("Please enter at least one target region/market.")
        else:
            with st.spinner("Generating creatives..."):
                report = _run_generation()
            st.success(f"Done. Products processed: {report['products_processed']}")
            st.session_state["last_generation_log_path"] = report.get("log_path")
            if report.get("warnings"):
                st.warning("Warnings:\n" + "\n".join(f"- {w}" for w in report["warnings"]))

    if products:
        # Render whatever is currently on disk for this campaign.
        for r in regions or ["US"]:
            st.markdown(f"## Region: {r}")
            for p in [pr["name"] for pr in products]:
                st.markdown(f"### {p}")
                ratio_cols = st.columns(3)
                # The pipeline writes aspect ratio directories using the keys from
                # `creative_pipeline.image_ops.ASPECT_RATIOS` (e.g. "1:1", "9:16", "16:9").
                ratio_keys = ["1:1", "9:16", "16:9"]
                caption_keys = {"1:1": "1_1", "9:16": "9_16", "16:9": "16_9"}
                for idx, rk in enumerate(ratio_keys):
                    img_path = Path("outputs") / campaign_name / _safe_region_dir_name(r) / p / rk / "ad.png"
                    with ratio_cols[idx]:
                        st.caption(caption_keys.get(rk, rk))
                        if img_path.exists():
                            st.image(str(img_path), use_container_width=True)
                            st.code(str(img_path), language=None)
                        else:
                            st.info("Not generated yet.")

    # Bottom-of-panel: show the most recent generation log location.
    last_log_path = st.session_state.get("last_generation_log_path")
    if last_log_path:
        st.divider()
        st.caption("Generation log")
        st.code(str(last_log_path), language=None)

