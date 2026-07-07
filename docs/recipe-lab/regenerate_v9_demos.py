"""Re-render the V9 guide demos through the current V9 nodes.

Each demo's shipped sidecar workflow (docs/assets/krea-v9/demos/<slug>.workflow.json)
is the source of truth: its widget values are converted to an API graph, rendered on
the configured ComfyUI server, and the very same sidecar is embedded in the fresh PNG so the
drag-in workflow always matches what rendered. Use this whenever node behavior
changes (recipe retunes, image-prep fixes) so the public demo set shows current
output quality. Sidecar files themselves are not rewritten.

Usage:
    python docs/recipe-lab/regenerate_v9_demos.py [--server http://127.0.0.1:8188]
                                                  [--only slug1,slug2] [--skip-render]
"""
import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

DEMO_DIR = Path(__file__).resolve().parents[1] / "assets" / "krea-v9" / "demos"
DEFAULT_SERVER = os.environ.get("KREA_COMFYUI_SERVER", "http://127.0.0.1:8188")

CARD_CLASS = "KGKrea2ImageGuideCardV9"
ENCODER_CLASS = "KGTextEncodeKreaImageReferencesV9"


def widget_inputs(node):
    """Map a sidecar node's declared widget inputs onto its widgets_values."""
    names = [i["name"] for i in node.get("inputs", []) if i.get("widget")]
    values = node.get("widgets_values", [])
    if len(names) != len(values):
        raise ValueError("widget mismatch on node type {}: {} names vs {} values".format(
            node["type"], len(names), len(values)))
    return dict(zip(names, values))


def find(ui, node_type, title_contains=None):
    for node in ui["nodes"]:
        if node["type"] != node_type:
            continue
        if title_contains and title_contains not in (node.get("title") or ""):
            continue
        return node
    raise KeyError("{} ({}) not found".format(node_type, title_contains or "any"))


def build_api_graph(ui, slug):
    unet = find(ui, "UNETLoader")["widgets_values"]
    clip = find(ui, "CLIPLoader")["widgets_values"]
    vae = find(ui, "VAELoader")["widgets_values"]
    latent = find(ui, "EmptyLatentImage")["widgets_values"]
    ks = find(ui, "KSampler")["widgets_values"]
    ref = find(ui, "LoadImage")["widgets_values"][0]

    card_in = widget_inputs(find(ui, CARD_CLASS))
    card_in["Reference image"] = ["load", 0]
    pos_in = widget_inputs(find(ui, ENCODER_CLASS, "positive"))
    pos_in["Krea CLIP"] = ["clip", 0]
    pos_in["Reference 1 guide card"] = ["card", 0]
    neg_in = widget_inputs(find(ui, ENCODER_CLASS, "negative"))
    neg_in["Krea CLIP"] = ["clip", 0]

    return {
        "unet": {"class_type": "UNETLoader",
                 "inputs": {"unet_name": unet[0], "weight_dtype": unet[1]}},
        "sampling": {"class_type": "ModelSamplingAuraFlow",
                     "inputs": {"shift": find(ui, "ModelSamplingAuraFlow")["widgets_values"][0],
                                "model": ["unet", 0]}},
        "clip": {"class_type": "CLIPLoader",
                 "inputs": {"clip_name": clip[0], "type": clip[1], "device": clip[2]}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": vae[0]}},
        "load": {"class_type": "LoadImage", "inputs": {"image": ref, "upload": "image"}},
        "card": {"class_type": CARD_CLASS, "inputs": card_in},
        "pos": {"class_type": ENCODER_CLASS, "inputs": pos_in},
        "neg": {"class_type": ENCODER_CLASS, "inputs": neg_in},
        "latent": {"class_type": "EmptyLatentImage",
                   "inputs": {"width": latent[0], "height": latent[1], "batch_size": latent[2]}},
        "sampler": {"class_type": "KSampler", "inputs": {
            "seed": ks[0], "steps": ks[2], "cfg": ks[3], "sampler_name": ks[4],
            "scheduler": ks[5], "denoise": ks[6], "model": ["sampling", 0],
            "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0]}},
        "decode": {"class_type": "VAEDecode",
                   "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {
            "images": ["decode", 0],
            "filename_prefix": "claude-generations/v9-guide-demos/" + slug}},
    }


def render(slug, server):
    ui = json.loads((DEMO_DIR / (slug + ".workflow.json")).read_text(encoding="utf-8"))
    graph = build_api_graph(ui, slug)
    body = {"prompt": graph, "extra_data": {"extra_pnginfo": {"workflow": ui}}}
    req = urllib.request.Request(server + "/prompt", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pid = json.load(r)["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < 600:
        with urllib.request.urlopen(server + "/history/" + pid, timeout=30) as r:
            e = json.load(r).get(pid)
        if e and e.get("outputs"):
            info = e["outputs"]["save"]["images"][0]
            break
        if e and e.get("status", {}).get("status_str") == "error":
            raise RuntimeError(slug + ": " + json.dumps(e.get("status"))[:300])
        time.sleep(2)
    else:
        raise TimeoutError(slug)
    q = urllib.parse.urlencode({"filename": info["filename"],
                                "subfolder": info.get("subfolder", ""), "type": "output"})
    with urllib.request.urlopen(server + "/view?" + q, timeout=60) as r:
        (DEMO_DIR / (slug + ".png")).write_bytes(r.read())
    print("rendered", slug)


def touch_manifest():
    path = DEMO_DIR / "guide-demo-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["generated_at"] = "2026-07-03"
    manifest["engine_note"] = ("Re-rendered with the current V9 nodes (retuned appearance "
                               "recipes, bilinear palette wash) on the configured ComfyUI server; "
                               "sidecar workflow values are exactly what rendered.")
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("manifest touched")


def write_gallery_sheet(slugs):
    cell_w, cell_h, bar = 256, 384, 26
    cols = 3
    rows = (len(slugs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + bar)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    manifest = json.loads((DEMO_DIR / "guide-demo-manifest.json").read_text(encoding="utf-8"))
    titles = {d["slug"]: d["recipe"] for d in manifest["demos"]}
    for i, slug in enumerate(slugs):
        img = Image.open(DEMO_DIR / (slug + ".png")).convert("RGB").resize((cell_w, cell_h))
        x, y = (i % cols) * cell_w, (i // cols) * (cell_h + bar)
        sheet.paste(img, (x, y))
        draw.text((x + 8, y + cell_h + 6), titles[slug], fill=(235, 235, 235))
    sheet.save(DEMO_DIR / "recipe-gallery.png")
    print("gallery sheet written")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--only", help="comma-separated slugs to render")
    ap.add_argument("--skip-render", action="store_true")
    args = ap.parse_args()
    manifest = json.loads((DEMO_DIR / "guide-demo-manifest.json").read_text(encoding="utf-8"))
    slugs = [d["slug"] for d in manifest["demos"]]
    only = set(args.only.split(",")) if args.only else None
    if not args.skip_render:
        for slug in slugs:
            if only and slug not in only:
                continue
            render(slug, args.server.rstrip("/"))
    touch_manifest()
    write_gallery_sheet(slugs)


if __name__ == "__main__":
    main()
