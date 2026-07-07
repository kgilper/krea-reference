"""Run the V10 style-transfer method reliability suite.

The suite renders a fixed matrix of content/style stress cases and method
variants, writes JSONL metrics, and builds a contact sheet. It intentionally
uses the real V10 ComfyUI nodes through style_transfer_stack_test.py.

Examples:
  python docs/recipe-lab/style_transfer_reliability_suite.py --render --skip-existing
  python docs/recipe-lab/style_transfer_reliability_suite.py --sheet-only
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / "docs" / "recipe-lab" / "runs"
LOCAL_REFS = Path(os.environ.get("KREA_REFERENCE_STYLE_REFS", REPO / "docs" / "recipe-lab" / "refs"))
STACK_TEST = REPO / "docs" / "recipe-lab" / "style_transfer_stack_test.py"
STYLE_RECIPE = REPO / "docs" / "recipe-lab" / "runs" / "codex-style-transfer-final.json"

SUITE_ID = "20260705"
METHODS = ["content-only", "two-card", "final-style", "final-style-guarded"]
REQUIRED_REF_FILENAMES = [
    "durer_hare.jpg",
    "starry_night.jpg",
    "apollo_bootprint.jpg",
    "hokusai_great_wave.jpg",
    "vitruvian.jpg",
    "mondrian_color_fields.jpg",
    "migrant_mother.jpg",
    "pillars_creation.jpg",
]

CASES = [
    {
        "key": "hare-starry",
        "label": "Hare -> Starry",
        "content_ref": "codex-style-variety-20260705/durer_hare.jpg",
        "content_local": LOCAL_REFS / "durer_hare.jpg",
        "style_ref": "codex-style-variety-20260705/starry_night.jpg",
        "style_local": LOCAL_REFS / "starry_night.jpg",
        "prompt": "the same hare from the content reference sitting on a simple stone plinth in a clean studio scene, no readable text",
        "seed": 771201,
    },
    {
        "key": "bootprint-hokusai",
        "label": "Bootprint -> Hokusai",
        "content_ref": "codex-style-variety-20260705/apollo_bootprint.jpg",
        "content_local": LOCAL_REFS / "apollo_bootprint.jpg",
        "style_ref": "codex-style-variety-20260705/hokusai_great_wave.jpg",
        "style_local": LOCAL_REFS / "hokusai_great_wave.jpg",
        "prompt": "the same lunar bootprint impression from the content reference in a clean square composition, no readable text",
        "seed": 771202,
    },
    {
        "key": "figure-mondrian",
        "label": "Figure -> Mondrian",
        "content_ref": "codex-style-variety-20260705/vitruvian.jpg",
        "content_local": LOCAL_REFS / "vitruvian.jpg",
        "style_ref": "codex-style-variety-20260705/mondrian_color_fields.jpg",
        "style_local": LOCAL_REFS / "mondrian_color_fields.jpg",
        "prompt": "the same standing human figure study from the content reference, centered in a clean studio composition, no readable text",
        "seed": 771203,
    },
    {
        "key": "portrait-starry",
        "label": "Portrait -> Starry",
        "content_ref": "codex-style-variety-20260705/migrant_mother.jpg",
        "content_local": LOCAL_REFS / "migrant_mother.jpg",
        "style_ref": "codex-style-variety-20260705/starry_night.jpg",
        "style_local": LOCAL_REFS / "starry_night.jpg",
        "prompt": "the same adult woman from the content reference in a simple seated studio portrait, no readable text",
        "seed": 771204,
    },
    {
        "key": "nebula-mondrian",
        "label": "Nebula -> Mondrian",
        "content_ref": "codex-style-variety-20260705/pillars_creation.jpg",
        "content_local": LOCAL_REFS / "pillars_creation.jpg",
        "style_ref": "codex-style-variety-20260705/mondrian_color_fields.jpg",
        "style_local": LOCAL_REFS / "mondrian_color_fields.jpg",
        "prompt": "the same pillar-shaped nebula forms from the content reference in a clean square space image, no readable text",
        "seed": 771205,
    },
    {
        "key": "hare-hokusai",
        "label": "Hare -> Hokusai",
        "content_ref": "codex-style-variety-20260705/durer_hare.jpg",
        "content_local": LOCAL_REFS / "durer_hare.jpg",
        "style_ref": "codex-style-variety-20260705/hokusai_great_wave.jpg",
        "style_local": LOCAL_REFS / "hokusai_great_wave.jpg",
        "prompt": "the same hare from the content reference sitting on a simple stone plinth in a clean studio scene, no readable text",
        "seed": 771206,
    },
]


def output_name(case_key, method):
    return f"codex-suite-{case_key}-{method}-{SUITE_ID}"


def output_path(case_key, method):
    return RUNS / f"{output_name(case_key, method)}.png"


def validate_local_refs():
    missing = [name for name in REQUIRED_REF_FILENAMES if not (LOCAL_REFS / name).exists()]
    if not missing:
        return
    missing_list = ", ".join(missing)
    raise FileNotFoundError(
        "Missing style-transfer reference images in "
        f"{LOCAL_REFS}. Add the files there or set KREA_REFERENCE_STYLE_REFS "
        f"to the folder that contains them. Missing: {missing_list}"
    )


def run_render(case, method, skip_existing):
    image = output_path(case["key"], method)
    if skip_existing and image.exists():
        return None
    cmd = [
        sys.executable,
        str(STACK_TEST),
        "--method",
        method,
        "--content-ref",
        case["content_ref"],
        "--style-ref",
        case["style_ref"],
        "--style-recipe-json",
        str(STYLE_RECIPE),
        "--prompt",
        case["prompt"],
        "--seed",
        str(case["seed"]),
        "--name",
        output_name(case["key"], method),
        "--balance",
    ]
    proc = subprocess.run(cmd, cwd=REPO, check=True, capture_output=True, text=True)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    result = json.loads(lines[-1])
    result["case"] = case["key"]
    return result


def write_metrics(records):
    out = RUNS / f"codex-style-transfer-reliability-suite-{SUITE_ID}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    return out


def load_font(names, size):
    candidates = []
    for name in names:
        candidates.extend([
            name,
            f"C:/Windows/Fonts/{name}",
            f"/System/Library/Fonts/{name}",
            f"/Library/Fonts/{name}",
            f"/usr/share/fonts/truetype/dejavu/{name}",
            f"/usr/share/fonts/truetype/liberation2/{name}",
        ])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def build_sheet():
    out = RUNS / f"codex-style-transfer-reliability-suite-{SUITE_ID}.png"
    cols = [("Content ref", "content"), ("Style ref", "style")] + [(m, m) for m in METHODS]

    title_font = load_font(["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"], 21)
    header_font = load_font(["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"], 13)
    label_font = load_font(["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"], 12)

    thumb = 146
    label_h = 38
    header_h = 104
    margin = 14
    gap = 9
    sheet_w = margin * 2 + len(cols) * thumb + (len(cols) - 1) * gap
    sheet_h = header_h + margin + len(CASES) * (thumb + label_h) + (len(CASES) - 1) * gap + margin
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f4f1ea")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 12), "V10 style-transfer reliability suite", fill="#171411", font=title_font)
    draw.text(
        (margin, 42),
        "Fixed public-domain content/style stress cases. Compare default transfer against safer final-detail variants.",
        fill="#4a443d",
        font=label_font,
    )
    draw.text(
        (margin, 62),
        "Methods: content-only baseline, two-card default, final-style leak control, final-style-guarded composition guard.",
        fill="#4a443d",
        font=label_font,
    )

    for col_index, (heading, _kind) in enumerate(cols):
        x = margin + col_index * (thumb + gap)
        draw.text((x, header_h - 26), heading, fill="#171411", font=header_font)

    for row_index, case in enumerate(CASES):
        y = header_h + margin + row_index * (thumb + label_h + gap)
        for col_index, (_heading, kind) in enumerate(cols):
            x = margin + col_index * (thumb + gap)
            if kind == "content":
                path = case["content_local"]
                caption = case["label"]
            elif kind == "style":
                path = case["style_local"]
                caption = "style source"
            else:
                path = output_path(case["key"], kind)
                caption = kind
            img = Image.open(path).convert("RGB")
            img = ImageOps.contain(img, (thumb, thumb), Image.Resampling.LANCZOS)
            frame = Image.new("RGB", (thumb, thumb), "#ded7cb")
            frame.paste(img, ((thumb - img.width) // 2, (thumb - img.height) // 2))
            sheet.paste(frame, (x, y))
            draw.rectangle((x, y, x + thumb - 1, y + thumb - 1), outline="#b7aea1", width=1)
            draw.text((x, y + thumb + 7), caption, fill="#28231e", font=label_font)
    sheet.save(out, quality=94)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--render", action="store_true", help="render every case/method image")
    ap.add_argument("--skip-existing", action="store_true", help="do not rerender existing PNGs")
    ap.add_argument("--sheet-only", action="store_true", help="only rebuild the contact sheet")
    args = ap.parse_args()

    RUNS.mkdir(parents=True, exist_ok=True)
    validate_local_refs()
    records = []
    if args.render and not args.sheet_only:
        for case in CASES:
            for method in METHODS:
                print(f"Rendering {case['key']} / {method}", flush=True)
                record = run_render(case, method, args.skip_existing)
                if record is not None:
                    records.append(record)
        if records:
            metrics_path = write_metrics(records)
            print(metrics_path)
    sheet_path = build_sheet()
    print(sheet_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
