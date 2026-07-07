"""Run a seed-sweep check for the V10 style-transfer method.

The broad reliability suite varies content/style cases. This one varies seeds
for the recommended methods so we can see whether the method is stable across
sampling noise, not just lucky on one seed.

Examples:
  python docs/recipe-lab/style_transfer_seed_sweep.py --render --skip-existing
  python docs/recipe-lab/style_transfer_seed_sweep.py --sheet-only
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_transfer_reliability_suite as suite


RUNS = suite.RUNS
REPO = suite.REPO
STACK_TEST = suite.STACK_TEST
STYLE_RECIPE = suite.STYLE_RECIPE
SUITE_ID = suite.SUITE_ID

CASE_KEYS = ["hare-starry", "bootprint-hokusai", "figure-mondrian"]
METHODS = ["two-card", "final-style"]
SEEDS = [771301, 771302, 771303]
CASES = [case for case in suite.CASES if case["key"] in CASE_KEYS]


def output_name(case_key, method, seed):
    return f"codex-seedsweep-{case_key}-{method}-seed{seed}-{SUITE_ID}"


def output_path(case_key, method, seed):
    return RUNS / f"{output_name(case_key, method, seed)}.png"


def run_render(case, method, seed, skip_existing):
    image = output_path(case["key"], method, seed)
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
        str(seed),
        "--name",
        output_name(case["key"], method, seed),
        "--balance",
    ]
    proc = subprocess.run(cmd, cwd=REPO, check=True, capture_output=True, text=True)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    result = json.loads(lines[-1])
    result["case"] = case["key"]
    result["seed"] = seed
    return result


def write_metrics(records):
    out = RUNS / f"codex-style-transfer-seed-sweep-{SUITE_ID}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, sort_keys=True) + "\n")
    return out


def build_sheet():
    out = RUNS / f"codex-style-transfer-seed-sweep-{SUITE_ID}.png"
    columns = [("Content ref", "content", None), ("Style ref", "style", None)]
    for method in METHODS:
        for seed in SEEDS:
            columns.append((f"{method}\n{seed}", method, seed))

    title_font = suite.load_font(["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"], 21)
    header_font = suite.load_font(["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"], 12)
    label_font = suite.load_font(["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"], 12)

    thumb = 132
    label_h = 38
    header_h = 112
    margin = 14
    gap = 8
    sheet_w = margin * 2 + len(columns) * thumb + (len(columns) - 1) * gap
    sheet_h = header_h + margin + len(CASES) * (thumb + label_h) + (len(CASES) - 1) * gap + margin
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#f4f1ea")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 12), "V10 style-transfer seed sweep", fill="#171411", font=title_font)
    draw.text(
        (margin, 42),
        "Three seeds per recommended method. Failures here mean the method is seed-lucky rather than reliable.",
        fill="#4a443d",
        font=label_font,
    )
    draw.text(
        (margin, 62),
        "two-card = strongest visible transfer; final-style = leak-control fallback.",
        fill="#4a443d",
        font=label_font,
    )

    for col_index, (heading, _method, _seed) in enumerate(columns):
        x = margin + col_index * (thumb + gap)
        for line_index, line in enumerate(heading.splitlines()):
            draw.text((x, header_h - 40 + line_index * 16), line, fill="#171411", font=header_font)

    for row_index, case in enumerate(CASES):
        y = header_h + margin + row_index * (thumb + label_h + gap)
        for col_index, (_heading, method, seed) in enumerate(columns):
            x = margin + col_index * (thumb + gap)
            if method == "content":
                path = case["content_local"]
                caption = case["label"]
            elif method == "style":
                path = case["style_local"]
                caption = "style source"
            else:
                path = output_path(case["key"], method, seed)
                caption = f"{method} {seed}"
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
    ap.add_argument("--render", action="store_true", help="render every case/method/seed image")
    ap.add_argument("--skip-existing", action="store_true", help="do not rerender existing PNGs")
    ap.add_argument("--sheet-only", action="store_true", help="only rebuild the contact sheet")
    args = ap.parse_args()

    RUNS.mkdir(parents=True, exist_ok=True)
    suite.validate_local_refs()
    records = []
    if args.render and not args.sheet_only:
        for case in CASES:
            for method in METHODS:
                for seed in SEEDS:
                    print(f"Rendering {case['key']} / {method} / {seed}", flush=True)
                    record = run_render(case, method, seed, args.skip_existing)
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
