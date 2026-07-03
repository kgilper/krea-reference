"""Single-chunk deepstack sweep - the fresh empirical determination (section 16.4).

Renders the experiment that measures what each of the 12 deepstack chunks
carries: hold one reference at fixed strength, and for each chunk L render a
gain table that is 1.0 everywhere except a spike at L. Any visual difference
between spike-L and the all-ones control is attributable to chunk L, because
the pooled channel and every other chunk are held identical.

Each spike is expressed as a V10 custom recipe (role balanced -> even base,
neutral shape/global, so only the layers array differs). Rendering therefore
REQUIRES the kg_krea_v10 nodes installed on the target ComfyUI - the single-
chunk tables are not expressible through the V9 widgets. Run
`--dry-run` anywhere to generate the recipe files and API graphs without a
server (validates construction against the real node code via the stubs).

Usage:
  python generate_sweep.py --dry-run                 # build + validate, no render
  python generate_sweep.py --server http://HOST:PORT # render on a V10 box
  python generate_sweep.py --gains 2 4 6             # multi-level (default: 4)

Outputs (locally, under docs/deepstack-layers/sweep_out/):
  recipes/chunk-NN-gainG.yaml   one custom recipe per spike
  grids/<ref>__chunk-NN-gainG.png   rendered result (when a server is given)
  grids/<ref>__control.png          the all-ones baseline
  sweep-manifest.json               every cell: ref, chunk, gain, seed, file

On the render box, SaveImage writes under the dedicated Claude output
folder (output/claude-generations/krea-deepstack-sweep/); this tool only
downloads back the images it just generated and never opens any other.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
OUT_DIR = HERE / "sweep_out"
sys.path.insert(0, str(REPO_ROOT / "tests"))

CHUNKS = 12
MODEL = "krea2\\krea2_turbo_nvfp4.safetensors"
CLIP = "krea2\\qwen3vl_4b_fp8_scaled.safetensors"
VAE = "krea2\\qwen_image_vae.safetensors"
WIDTH, HEIGHT, STEPS, CFG, SEED = 512, 768, 8, 1.0, 424242

# References chosen so every aspect CAN respond: a clear-subject product shot
# (structure + material) and an abstract palette study (palette + finish).
REFERENCES = {
    "subject": "krea-reference-examples/slot1_content_anchor.png",
    "palette": "krea-reference-examples/slot2_style_reference.png",
}
# Neutral prompt: let the reference speak so the chunk's contribution shows.
PROMPT = "a product photograph on a plain seamless background, soft even light"
NEGATIVE = "boring, dull, blurry, low-quality, oversaturated colours"
CARD_STRENGTH = 0.7  # fixed across the whole sweep; literal feel curve for exactness


def spike_table(chunk, gain):
    table = [1.0] * CHUNKS
    table[chunk] = float(gain)
    return table


def spike_recipe(chunk, gain):
    """A V10 custom recipe isolating one chunk. Role balanced keeps shape and
    global at 1.0, so between cells only the `layers` array differs."""
    label = "sweep chunk {:02d} gain {:g}".format(chunk, gain)
    return label, {
        "label": label,
        "description": "Deepstack sweep: chunk {} spiked to {}x, all others 1.0.".format(chunk, gain),
        "role": "balanced",
        "treatment": "normal",
        "color": 1.0,
        "detail": 1.0,
        "study": "384",
        "framing": "stack",
        "subject": "allow",
        "early": 1.0,
        "late": 1.0,
        "guard": False,
        "cap": 3.0,
        "shape": 1.0,
        "global": 1.0,
        "layers": spike_table(chunk, gain),
    }


def control_recipe():
    return "sweep control", {
        "label": "sweep control",
        "description": "Deepstack sweep control: all chunks 1.0 (native).",
        "role": "balanced", "treatment": "normal", "color": 1.0, "detail": 1.0,
        "study": "384", "framing": "stack", "subject": "allow", "early": 1.0,
        "late": 1.0, "guard": False, "cap": 3.0, "shape": 1.0, "global": 1.0,
        "layers": [1.0] * CHUNKS,
    }


def validate_recipes(recipes):
    """Run every generated recipe through the REAL V10 validation + resolution."""
    from _kg_stub_env import load_module
    nodes, _ = load_module("kg_krea_v10", "kg_deepstack_sweep_validate")
    card_cls = nodes.KGKrea2ImageGuideCardV10
    reserved = set(card_cls.PURPOSE_LABELS) | set(card_cls.QUICK_RECIPES)
    problems = []
    for label, bundle in recipes.items():
        try:
            _resolved_label, resolved = nodes.custom_recipes.validate_recipe(bundle, reserved)
            if resolved["layers"] != bundle["layers"]:
                problems.append("{}: layers not preserved".format(label))
        except Exception as exc:  # noqa: BLE001
            problems.append("{}: {}".format(label, exc))
    return problems


def build_api_graph(recipe_label, recipe_bundle, reference_image):
    """API graph: a V10 guide card carrying the spike recipe -> V10 stack."""
    card_inputs = {
        "Reference image": ["load", 0],
        "How strongly this image guides": CARD_STRENGTH,
        "Use image for": recipe_label,
    }
    stack_inputs = {
        "Krea CLIP": ["clip", 0],
        "Final image prompt": PROMPT,
        "Written prompt strength": 1.0,
        "Image slider feel": "literal slider values",
        "Image detail level": "medium - balanced default (384)",
        "Image framing": "keep full image shape",
        "When images guide": "guide the whole image",
        "Early-to-final handoff": 0.4,
        "Text/logo guard prompt handling": "gentle guard - keep my prompt words",
        "Balance strong cards": "off - use my values",
        "Reuse image studies": "always re-study",
        "Reference 1 guide card": ["card", 0],
    }
    neg_inputs = dict(stack_inputs)
    neg_inputs.pop("Reference 1 guide card")
    neg_inputs["Final image prompt"] = NEGATIVE
    return {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": MODEL, "weight_dtype": "default"}},
        "sampling": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3.14, "model": ["unet", 0]}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "krea2", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "load": {"class_type": "LoadImage", "inputs": {"image": reference_image, "upload": "image"}},
        "card": {"class_type": "KGKrea2ImageGuideCardV10", "inputs": card_inputs},
        "pos": {"class_type": "KGTextEncodeKreaImageReferencesV10", "inputs": stack_inputs},
        "neg": {"class_type": "KGTextEncodeKreaImageReferencesV10", "inputs": neg_inputs},
        "latent": {"class_type": "EmptyLatentImage", "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1}},
        "sampler": {"class_type": "KSampler", "inputs": {
            "seed": SEED, "steps": STEPS, "cfg": CFG, "sampler_name": "euler",
            "scheduler": "simple", "denoise": 1.0, "model": ["sampling", 0],
            "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0]}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0],
                 "filename_prefix": "claude-generations/krea-deepstack-sweep/spike"}},
    }


def post_and_wait(server, graph, timeout=420):
    payload = json.dumps({"prompt": graph}).encode("utf-8")
    req = urllib.request.Request(server + "/prompt", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        prompt_id = json.load(r)["prompt_id"]
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(server + "/history/" + prompt_id, timeout=30) as r:
            entry = json.load(r).get(prompt_id)
        if entry and entry.get("outputs"):
            return entry["outputs"]["save"]["images"][0]
        if entry and entry.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(entry["status"])[:800])
        time.sleep(2)
    raise TimeoutError(prompt_id)


def download(server, info, dest):
    q = urllib.parse.urlencode({"filename": info["filename"],
                                "subfolder": info.get("subfolder", ""), "type": info.get("type", "output")})
    with urllib.request.urlopen(server + "/view?" + q, timeout=60) as r:
        dest.write_bytes(r.read())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", help="ComfyUI base URL with V10 nodes installed")
    ap.add_argument("--dry-run", action="store_true", help="build + validate only")
    ap.add_argument("--gains", type=float, nargs="+", default=[4.0])
    args = ap.parse_args()

    (OUT_DIR / "recipes").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "grids").mkdir(parents=True, exist_ok=True)

    recipes = dict([control_recipe()])
    for gain in args.gains:
        for chunk in range(CHUNKS):
            label, bundle = spike_recipe(chunk, gain)
            recipes[label] = bundle
    for label, bundle in recipes.items():
        slug = label.replace(" ", "-")
        (OUT_DIR / "recipes" / (slug + ".yaml")).write_text(
            "\n".join("{}: {}".format(k, json.dumps(v)) for k, v in bundle.items()) + "\n", encoding="utf-8")

    problems = validate_recipes(recipes)
    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("validated {} recipes (1 control + {} spikes) against the real V10 node code".format(
        len(recipes), len(recipes) - 1))

    cells = []
    for ref_name, ref_image in REFERENCES.items():
        for label, bundle in recipes.items():
            cells.append({"reference": ref_name, "reference_image": ref_image,
                          "recipe_label": label, "layers": bundle["layers"], "seed": SEED})

    if args.dry_run or not args.server:
        (OUT_DIR / "sweep-manifest.json").write_text(json.dumps(
            {"rendered": False, "prompt": PROMPT, "card_strength": CARD_STRENGTH,
             "seed": SEED, "gains": args.gains, "cells": cells}, indent=2) + "\n", encoding="utf-8")
        print("dry run: {} recipe files + {} planned cells written to {}".format(
            len(recipes), len(cells), OUT_DIR))
        print("to render: install kg_krea_v10 on a ComfyUI box, then rerun with --server URL")
        return 0

    server = args.server.rstrip("/")
    for cell in cells:
        img = build_api_graph(cell["recipe_label"], recipes[cell["recipe_label"]], cell["reference_image"])
        slug = cell["recipe_label"].replace(" ", "-")
        dest = OUT_DIR / "grids" / "{}__{}.png".format(cell["reference"], slug)
        print("rendering", dest.name, flush=True)
        info = post_and_wait(server, img)
        download(server, info, dest)
        cell["output"] = "grids/{}__{}.png".format(cell["reference"], slug)
    (OUT_DIR / "sweep-manifest.json").write_text(json.dumps(
        {"rendered": True, "server": server, "prompt": PROMPT, "card_strength": CARD_STRENGTH,
         "seed": SEED, "gains": args.gains, "cells": cells}, indent=2) + "\n", encoding="utf-8")
    print("rendered {} cells -> {}".format(len(cells), OUT_DIR / "grids"))
    print("next: score with SCORING.md and record verdicts in README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
