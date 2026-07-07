"""Render smoke test for the Concept Slider V1 stack.

Renders one attribute slider at several values (default -6 / 0 / +6) with a
fixed seed and prints one JSON line per arm with the local image path plus
quick objective metrics (mean luma for brightness-style axes, edge energy as
a fry check). The 0 arm is the no-change baseline: it must match a plain
prompt encode. No judgment here - a judge (or Kevin's eyes) reads the images.

Requires the Concept Slider nodes REGISTERED on the box: deploy the package
and restart ComfyUI first; this script refuses to run against an old module.

Usage:
  python slider_smoke_test.py --attribute brightness --values "-6,0,6"
  python slider_smoke_test.py --attribute height --values "-6,6" \
      --increase "a very tall person" --decrease "a very short person"
"""
import argparse, io, json, sys, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageFilter

DEFAULT_SERVER = "http://10.0.0.35:8188"
OUTDIR = Path(__file__).resolve().parent / "runs"
MODEL = "krea2\\krea2_turbo_nvfp4.safetensors"
CLIP = "krea2\\qwen3vl_4b_fp8_scaled.safetensors"
VAE = "krea2\\qwen_image_vae.safetensors"
NEG = "boring, dull, blurry, low-quality, text, watermark"
STACK = "KGKrea2ConceptSliderStackV1"
CARD = "KGKrea2ConceptSliderCardV1"


def slider_stack(prompt, reuse, card_key=None):
    inputs = {"Krea CLIP": ["clip", 0], "Final image prompt": prompt,
              "Overall slider reach": 1.0,
              "Reuse slider studies": "reuse between runs - faster tuning" if reuse else "always re-study"}
    if card_key:
        inputs["Slider 1"] = [card_key, 0]
    return {"class_type": STACK, "inputs": inputs}


def build_graph(attribute, value, increase, decrease, prompt, seed, name, reuse):
    g = {"unet": {"class_type": "UNETLoader", "inputs": {"unet_name": MODEL, "weight_dtype": "default"}},
         "sampling": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3.14, "model": ["unet", 0]}},
         "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "krea2", "device": "default"}},
         "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
         "latent": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
         "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}},
         "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "claude-generations/concept-slider-v1/" + name}}}
    g["card1"] = {"class_type": CARD, "inputs": {
        "What this slider changes": attribute, "Slider value": value,
        "What +6 looks like (optional)": increase, "What -6 looks like (optional)": decrease}}
    g["pos"] = slider_stack(prompt, reuse, "card1")
    g["neg"] = slider_stack(NEG, reuse)
    g["sampler"] = {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler",
                    "scheduler": "simple", "denoise": 1.0, "model": ["sampling", 0], "positive": ["pos", 0],
                    "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    return g


def require_slider_nodes(server):
    try:
        with urllib.request.urlopen(server + "/object_info/" + STACK, timeout=30) as r:
            info = json.load(r)
    except Exception as e:
        sys.exit("cannot query the box at {}: {}".format(server, e))
    if STACK not in info:
        sys.exit("Concept Slider nodes are not registered on the box - "
                 "deploy kg_krea_slider/ + __init__.py and RESTART ComfyUI first "
                 "(file copies are not live until restart).")


def submit(server, g, timeout=300):
    req = urllib.request.Request(server + "/prompt", data=json.dumps({"prompt": g}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pid = json.load(r)["prompt_id"]
    t = time.time()
    while time.time() - t < timeout:
        with urllib.request.urlopen(server + "/history/" + pid, timeout=30) as r:
            e = json.load(r).get(pid)
        if e and e.get("outputs"):
            return e["outputs"]["save"]["images"][0]
        if e and e.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(e.get("status"))[:400])
        time.sleep(2)
    raise TimeoutError(pid)


def fetch(server, info):
    q = urllib.parse.urlencode({"filename": info["filename"], "subfolder": info.get("subfolder", ""), "type": info.get("type", "output")})
    with urllib.request.urlopen(server + "/view?" + q, timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def mean_luma(img):
    px = list(img.convert("L").resize((64, 64)).getdata())
    return sum(px) / len(px)


def lapvar(img):
    px = list(img.convert("L").resize((256, 256)).filter(ImageFilter.FIND_EDGES).getdata())
    m = sum(px) / len(px)
    return sum((p - m) ** 2 for p in px) / len(px)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attribute", default="brightness")
    ap.add_argument("--values", default="-6,0,6", help="comma-separated slider values")
    ap.add_argument("--increase", default="", help="optional +6 pole override")
    ap.add_argument("--decrease", default="", help="optional -6 pole override")
    ap.add_argument("--prompt", default="photo of a man standing in a city park, natural light")
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--prefix", default="slider-smoke")
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--reuse", action="store_true", help="exercise the study cache instead of clean re-studies")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    server = args.server.rstrip("/")
    require_slider_nodes(server)

    for raw in args.values.split(","):
        value = float(raw.strip())
        tag = ("{:+g}".format(value)).replace("+", "p").replace("-", "m")
        name = "{}-{}-{}".format(args.prefix, args.attribute.replace(" ", "-"), tag)
        graph = build_graph(args.attribute, value, args.increase, args.decrease,
                            args.prompt, args.seed, name, args.reuse)
        try:
            info = submit(server, graph)
        except Exception:
            # New-label race: the first /prompt after a node drop can 400.
            require_slider_nodes(server)
            info = submit(server, graph)
        img = fetch(server, info)
        local = OUTDIR / (name + ".png")
        img.save(local)
        print(json.dumps({"name": name, "attribute": args.attribute, "value": value,
                          "image": str(local), "mean_luma": round(mean_luma(img), 1),
                          "texture_energy": round(lapvar(img), 0)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
