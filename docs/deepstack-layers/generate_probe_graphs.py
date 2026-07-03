"""Build the encode-only graphs that feed the layer-selectivity probe (Stage 1).

For each controlled reference image (plus a prompt-only baseline) this emits a
ComfyUI API graph that: loads the image, runs it through a V10 guide card at
NEUTRAL settings (balanced role, strength 1.0, literal feel - so the stack's
output is the plain encode of prompt+reference, not a recipe-shaped delta),
and routes the conditioning into the KG Conditioning Probe node, which saves
the per-tap signature. No UNET, no sampler, no VAE - nothing is rendered, so
this is cheap and touches only the text encoder.

Requires on the render box: the V10 nodes (kg_krea_v10) and the probe node
(probe_node/) installed, plus the controlled reference images in the ComfyUI
input folder.

Usage:
  python generate_probe_graphs.py --dry-run                       # build + validate, write a sample manifest
  python generate_probe_graphs.py --refs refs.json --server URL   # encode on the render box
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "probe_out"

CLIP = "krea2\\qwen3vl_4b_fp8_scaled.safetensors"
PROMPT = "a product photograph on a plain seamless background, soft even light"

# A controlled design: vary ONE attribute at a time across levels, others held
# fixed. Replace the image paths with real controlled sets (see README 5).
SAMPLE_REFS = {
    "attributes": ["palette", "structure", "texture", "lighting"],
    "baseline": "baseline",
    "references": {
        "palette_0": {"image": "layerprobe/palette_0.png", "palette": 0, "structure": 0, "texture": 0, "lighting": 0},
        "palette_1": {"image": "layerprobe/palette_1.png", "palette": 1, "structure": 0, "texture": 0, "lighting": 0},
        "palette_2": {"image": "layerprobe/palette_2.png", "palette": 2, "structure": 0, "texture": 0, "lighting": 0},
        "structure_1": {"image": "layerprobe/structure_1.png", "palette": 0, "structure": 1, "texture": 0, "lighting": 0},
        "structure_2": {"image": "layerprobe/structure_2.png", "palette": 0, "structure": 2, "texture": 0, "lighting": 0},
        "texture_1": {"image": "layerprobe/texture_1.png", "palette": 0, "structure": 0, "texture": 1, "lighting": 0},
        "texture_2": {"image": "layerprobe/texture_2.png", "palette": 0, "structure": 0, "texture": 2, "lighting": 0},
        "lighting_1": {"image": "layerprobe/lighting_1.png", "palette": 0, "structure": 0, "texture": 0, "lighting": 1},
        "lighting_2": {"image": "layerprobe/lighting_2.png", "palette": 0, "structure": 0, "texture": 0, "lighting": 2},
    },
}

STACK_NEUTRAL = {
    "Written prompt strength": 1.0,
    "Image slider feel": "literal slider values",
    "Image detail level": "medium - balanced default (384)",
    "Image framing": "keep full image shape",
    "When images guide": "guide the whole image",
    "Early-to-final handoff": 0.4,
    "Text/logo guard prompt handling": "gentle guard - keep my prompt words",
    "Balance strong cards": "off - use my values",
    "Reuse image studies": "always re-study",
}


def stack_inputs(with_card):
    inp = {"Krea CLIP": ["clip", 0], "Final image prompt": PROMPT}
    inp.update(STACK_NEUTRAL)
    if with_card:
        inp["Reference 1 guide card"] = ["card", 0]
    return inp


def build_graph(label, image):
    """Encode-only graph -> probe. image=None for the baseline."""
    g = {
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "krea2", "device": "default"}},
        "stack": {"class_type": "KGTextEncodeKreaImageReferencesV10", "inputs": stack_inputs(image is not None)},
        "probe": {"class_type": "KGConditioningProbe", "inputs": {"conditioning": ["stack", 0], "label": label}},
    }
    if image is not None:
        g["load"] = {"class_type": "LoadImage", "inputs": {"image": image, "upload": "image"}}
        # The API format requires every required widget; balanced ignores the
        # manual rows but ComfyUI still validates their presence. Neutral card:
        # strength 1.0 + literal feel -> stack output is the plain encode.
        g["card"] = {"class_type": "KGKrea2ImageGuideCardV10", "inputs": {
            "Reference image": ["load", 0],
            "How strongly this image guides": 1.0,
            "Use image for": "balanced",
            "Manual mode borrows": "overall image",
            "Prepare image by": "use image as-is",
            "Color kept": 1.0,
            "Small details kept": 1.0,
            "Study this image at": "use stack setting",
            "Frame this reference by": "use stack setting",
            "Subject copying": "recipe decides",
            "Early layout guidance": 1.0,
            "Final detail copying": 1.0,
            "Maximum image pull": 3.0,
            "Shape copied": 1.0,
            "Overall style reach": 1.0,
            "Guide direction": "toward this image",
            "When this card guides": "recipe decides",
            "Structure layers pull": 1.0,
            "Finish layers pull": 1.0,
        }}
    return g


def post_and_wait(server, graph, timeout=180):
    payload = json.dumps({"prompt": graph}).encode("utf-8")
    req = urllib.request.Request(server + "/prompt", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pid = json.load(r)["prompt_id"]
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(server + "/history/" + pid, timeout=30) as r:
            entry = json.load(r).get(pid)
        if entry and (entry.get("outputs") or entry.get("status", {}).get("completed")):
            return
        if entry and entry.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(entry["status"])[:800])
        time.sleep(1.5)
    raise TimeoutError(pid)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refs", help="controlled-reference manifest json (see SAMPLE_REFS)")
    ap.add_argument("--server", help="ComfyUI base URL (V10 + probe node installed)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    refs = json.loads(Path(args.refs).read_text(encoding="utf-8")) if args.refs else SAMPLE_REFS

    plan = [("baseline", None)] + [(lbl, r["image"]) for lbl, r in refs["references"].items()]
    graphs = {lbl: build_graph(lbl, img) for lbl, img in plan}
    # structural validation
    for lbl, g in graphs.items():
        assert g["probe"]["inputs"]["conditioning"] == ["stack", 0]
        assert g["probe"]["inputs"]["label"] == lbl

    if args.dry_run or not args.server:
        (OUT_DIR / "sample-refs.json").write_text(json.dumps(SAMPLE_REFS, indent=2) + "\n", encoding="utf-8")
        (OUT_DIR / "probe-manifest.json").write_text(json.dumps({
            "attributes": refs["attributes"], "baseline": "baseline",
            "references": {k: {a: v[a] for a in refs["attributes"]} for k, v in refs["references"].items()},
        }, indent=2) + "\n", encoding="utf-8")
        print("dry run OK: {} encode graphs (1 baseline + {} references) validated".format(
            len(graphs), len(graphs) - 1))
        print("wrote sample-refs.json + probe-manifest.json to", OUT_DIR)
        print("to run: install V10 + probe_node on the render box, put controlled images in")
        print("ComfyUI/input/layerprobe/, then rerun with --refs <yours> --server http://HOST:8188")
        return 0

    server = args.server.rstrip("/")
    for lbl, img in plan:
        print("encoding", lbl, flush=True)
        post_and_wait(server, graphs[lbl])
    print("done - probe signatures saved under output/claude-generations/kg-selectivity-probe/ on the box")
    print("copy them back, then: python probe_selectivity.py --probes <dir> --manifest probe_out/probe-manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
