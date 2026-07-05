"""Render engine for the rapid recipe tweak-and-test loop.

One self-contained command that a cheap agent can drive: given a recipe (a
built-in label OR a full recipe bundle to try as a tweak) plus a reference
image, prompt, strength, and seed, it renders on the ComfyUI box and returns
the local image path plus quick objective metrics as JSON. No agent judgment
here - this is the mechanical "manual work" half of the loop; a judge model
reads the returned image to decide success.

Usage:
  python tweak_test.py --builtin "suggest the visual style" --ref layerprobe2/base.png \
      --prompt "a plain white bowl on a wooden table" --strength 0.6 --seed 424242 --name style-current
  python tweak_test.py --recipe-json cand.json --ref ... --name style-cand1   # cand.json = full recipe bundle

Prints one JSON line: {"name","image","metrics":{...}} (image = local PNG path).
"""
import argparse, io, json, sys, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageFilter

DEFAULT_SERVER = "http://10.0.0.35:8188"
OLGA_RECIPES = Path("//Olga/d/ComfyUI/custom_nodes/comfyui-krea-reference/custom_recipes")
OUTDIR = Path(__file__).resolve().parent / "runs"
MODEL = "krea2\\krea2_turbo_nvfp4.safetensors"
CLIP = "krea2\\qwen3vl_4b_fp8_scaled.safetensors"
VAE = "krea2\\qwen_image_vae.safetensors"
NEG = "boring, dull, blurry, low-quality, text, watermark"

CARD_DEFAULTS = {
    "Manual mode borrows": "overall image", "Prepare image by": "use image as-is", "Color kept": 1.0,
    "Small details kept": 1.0, "Study this image at": "use stack setting", "Frame this reference by": "use stack setting",
    "Subject copying": "recipe decides", "Early layout guidance": 1.0, "Final detail copying": 1.0,
    "Maximum image pull": 3.0, "Shape copied": 1.0, "Overall style reach": 1.0, "Guide direction": "toward this image",
    "When this card guides": "recipe decides", "Structure layers pull": 1.0, "Finish layers pull": 1.0}


def stack(prompt, card=False):
    inp = {"Krea CLIP": ["clip", 0], "Final image prompt": prompt, "Written prompt strength": 1.0,
           "Image slider feel": "artist friendly - soft at low values", "Image detail level": "medium - balanced default (384)",
           "Image framing": "keep full image shape", "When images guide": "guide the whole image",
           "Early-to-final handoff": 0.4, "Text/logo guard prompt handling": "gentle guard - keep my prompt words",
           "Balance strong cards": "off - use my values", "Reuse image studies": "always re-study"}
    if card:
        inp["Reference 1 guide card"] = ["card", 0]
    return {"class_type": "KGTextEncodeKreaImageReferencesV10", "inputs": inp}


def build_graph(label, ref, prompt, strength, seed, name):
    g = {"unet": {"class_type": "UNETLoader", "inputs": {"unet_name": MODEL, "weight_dtype": "default"}},
         "sampling": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3.14, "model": ["unet", 0]}},
         "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "krea2", "device": "default"}},
         "vae": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}}, "neg": stack(NEG),
         "load": {"class_type": "LoadImage", "inputs": {"image": ref, "upload": "image"}},
         "latent": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
         "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}},
         "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0], "filename_prefix": "claude-generations/recipe-lab/" + name}}}
    card_in = dict(CARD_DEFAULTS)
    card_in.update({"Reference image": ["load", 0], "How strongly this image guides": strength, "Use image for": label})
    g["card"] = {"class_type": "KGKrea2ImageGuideCardV10", "inputs": card_in}
    g["pos"] = stack(prompt, card=True)
    g["sampler"] = {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 8, "cfg": 1.0, "sampler_name": "euler",
                    "scheduler": "simple", "denoise": 1.0, "model": ["sampling", 0], "positive": ["pos", 0],
                    "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    return g


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


def refresh_card_info(server):
    """Force ComfyUI to rescan V10 card inputs after dropping a lab recipe."""
    with urllib.request.urlopen(server + "/object_info/KGKrea2ImageGuideCardV10", timeout=30) as r:
        r.read()


def hist(img, bins=8):
    img = img.resize((128, 128))
    h = [0.0] * (bins * 3)
    for r, g, b in img.getdata():
        h[r*bins//256] += 1
        h[bins+g*bins//256] += 1
        h[2*bins+b*bins//256] += 1
    return [x / (128*128) for x in h]


def gray(img):
    return list(img.convert("L").resize((32, 32)).getdata())


def struct_sim(a, b):
    n = len(a)
    ma = sum(a)/n
    mb = sum(b)/n
    num = sum((a[i]-ma)*(b[i]-mb) for i in range(n))
    da = sum((a[i]-ma)**2 for i in range(n))**0.5
    db = sum((b[i]-mb)**2 for i in range(n))**0.5
    return num/(da*db) if da and db else 0.0


def lapvar(img):
    px = list(img.convert("L").resize((256, 256)).filter(ImageFilter.FIND_EDGES).getdata())
    m = sum(px)/len(px)
    return sum((p-m)**2 for p in px)/len(px)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--builtin")
    ap.add_argument("--recipe-json")
    ap.add_argument("--ref", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--strength", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=424242)
    ap.add_argument("--name", required=True)
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--ref-is-input", action="store_true", help="reference lives in ComfyUI input/ (default true)")
    args = ap.parse_args()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    if args.recipe_json:
        bundle = json.loads(Path(args.recipe_json).read_text(encoding="utf-8"))
        label = bundle["label"]
        OLGA_RECIPES.mkdir(parents=True, exist_ok=True)
        (OLGA_RECIPES / ("lab-" + label.replace(" ", "-") + ".json")).write_text(json.dumps(bundle), encoding="utf-8")
    elif args.builtin:
        label = args.builtin
    else:
        print(json.dumps({"error": "need --builtin or --recipe-json"}))
        return 2

    server = args.server.rstrip("/")
    if args.recipe_json:
        refresh_card_info(server)
    info = submit(server, build_graph(label, args.ref, args.prompt, args.strength, args.seed, args.name))
    out = fetch(server, info)
    local = OUTDIR / (args.name + ".png")
    out.save(local)
    ref_img = fetch(server, {"filename": Path(args.ref).name, "subfolder": str(Path(args.ref).parent).replace("\\", "/"), "type": "input"})
    metrics = {
        "palette_dist_to_ref": round(sum(abs(a-b) for a, b in zip(hist(out), hist(ref_img))), 3),
        "struct_sim_to_ref": round(struct_sim(gray(out), gray(ref_img)), 3),
        "texture_energy": round(lapvar(out), 0),
    }
    print(json.dumps({"name": args.name, "label": label, "image": str(local), "metrics": metrics}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
