# Creative Automation Pipeline (Take-Home POC)

Proof-of-concept CLI that takes a campaign brief (JSON/YAML), reuses provided product assets when available, generates missing hero images (GenAI if configured; otherwise a local placeholder), then produces three aspect-ratio variants with campaign text overlaid and saves outputs organized by product and ratio.

## Requirements covered

- Accept a campaign brief with **at least two products**, **region**, **audience**, **campaign message**
- Accept/reuse **input assets** from a local folder
- If assets are missing, **generate** them (OpenAI if available; fallback if not)
- Produce creatives for **1:1**, **9:16**, **16:9**
- Display campaign message on final posts
- Run locally via CLI
- Save outputs organized by **campaign/product/aspect ratio**
- Includes basic logging + toy brand/legal checks

## Quickstart

Create a virtualenv and install dependencies:

```bash
cd /Users/mwilker/projects/fde-creative-pipeline-lite
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the web app (recommended)

```bash
cd /Users/mwilker/projects/fde-creative-pipeline-lite
source .venv/bin/activate
streamlit run app.py
```

In the sidebar you can upload:
- a `logo` overlay image
- an optional `seed image` (used for edits-style generation)
- optional per-`product` asset images (wired to `product.asset`)

There is also a toggle: **“Regenerate even if a product asset exists”** (forces hero generation even when local assets are present).

Run using the included example brief:

```bash
python3 main.py --brief examples/brief.json --assets-dir assets --outputs-dir outputs
```

If you want to force local placeholder generation (no API calls):

```bash
python3 main.py --brief examples/brief.json --no-genai
```

If you want message localization/translation (translates into languages inferred from the brief's `region` targets):

```bash
python3 main.py --brief examples/brief.json --localize
```

## OpenAI image generation (optional)

If you have an OpenAI API key, set it in your shell (the app reads `OPENAI_API_KEY`):

```bash
export OPENAI_API_KEY="YOUR_KEY"
python3 main.py --brief examples/brief.json
```

Or pass it directly (overrides the env var):

```bash
python3 main.py --brief examples/brief.json --openai-api-key "YOUR_KEY"
```

You can also tune the model/size:

```bash
python3 main.py --brief examples/brief.json --openai-image-model gpt-image-1 --openai-image-size 1024x1024
```

You can also provide extra prompt guidance from the CLI:

```bash
python3 main.py --brief examples/brief.json --image-prompt "Minimal studio shot, white seamless background, premium look."
```

If GenAI fails for any reason, the pipeline automatically falls back to a local placeholder hero image so the demo still runs.

## Campaign brief format

Example (`examples/brief.json`):

```json
{
  "campaign_name": "summer_refresh",
  "region": ["US", "DE", "FR"],
  "audience": "young professionals",
  "message": "Stay refreshed this summer!",
  "image_prompt": "Photoreal lifestyle. Bright natural light. Minimal premium background.",
  "products": [
    { "name": "SparkleWater", "asset": "sparklewater.png", "image_prompt": "Cool blue accents, citrus garnish." },
    { "name": "FreshJuice", "asset": null, "image_prompt": "Vibrant oranges/yellows, sliced fruit." }
  ]
}
```

Notes:
- Brief can be **JSON** (`.json`) or **YAML** (`.yml` / `.yaml`).
- `asset` can be:
  - a filename relative to `--assets-dir`
  - a relative/absolute path
  - `null` (missing → will generate)
- Optional `image_prompt` can be set:
  - at the **campaign** level (`image_prompt`) to guide all generated images
  - per **product** (`products[].image_prompt`) to guide each product’s hero image
  - via CLI `--image-prompt` to override both

## Input assets

Put product images in `assets/` (or pass `--assets-dir`).

The resolver checks:
- The explicit `product.asset` value (as-is)
- `assets/<asset>` if `asset` is relative
- `assets/<ProductName>.png` and `assets/<ProductName>.jpg`

## Outputs

Outputs are written to:

`outputs/<campaign_name>/<region>/<product_name>/<aspect_ratio_key>/ad.png`

Aspect ratio keys:
- `1:1` (1024×1024)
- `9:16` (1080×1920)
- `16:9` (1920×1080)

## Design decisions

- **Fast local fallback**: even without an API key, you can run the full pipeline end-to-end for demo/review.
- **Cover resize**: variants are created using a “cover” strategy (scale to fill then center-crop) which tends to look better for social formats.
- **Legible overlay**: message is placed on a semi-transparent bottom banner to improve readability across varied imagery.
- **Simple checks (bonus)**:
  - Legal check: flags a small list of prohibited phrases
  - Brand check: toy heuristic for “logo” in filename + brightness warning

## Assumptions & limitations

- GenAI prompt is intentionally simple; no brand kit ingestion, logos, or localization pipeline.
- “Localization” translates the campaign message into target languages inferred from the `region` values.
- Brand/legal checks are heuristics, not production-grade validation.

