"""Render V10 multi-card style-transfer stack experiments.

This complements tweak_test.py, which is intentionally one-card. The goal here
is to test a *method*: keep a content reference stable while applying a style
reference through V10 guide cards.

Examples:
  python docs/recipe-lab/style_transfer_stack_test.py --method two-card \
    --content-ref codex-style-variety-20260705/durer_hare.jpg \
    --style-ref codex-style-variety-20260705/starry_night.jpg \
    --style-recipe-json docs/recipe-lab/runs/codex-style-transfer-final.json \
    --prompt "the same hare sitting on a stone plinth, no readable text" \
    --seed 771201 --name hare-starry-two-card

Prints one JSON line with local output path and metrics against both refs.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tweak_test as tt


def stack_inputs(prompt, prompt_strength, balance):
    return {
        "Krea CLIP": ["clip", 0],
        "Final image prompt": prompt,
        "Written prompt strength": prompt_strength,
        "Image slider feel": "artist friendly - soft at low values",
        "Image detail level": "medium - balanced default (384)",
        "Image framing": "keep full image shape",
        "When images guide": "smart per-card timing",
        "Early-to-final handoff": 0.4,
        "Text/logo guard prompt handling": "gentle guard - keep my prompt words",
        "Balance strong cards": "gentle balance" if balance else "off - use my values",
        "Reuse image studies": "always re-study",
    }


def method_cards(method, style_label):
    """Return card specs for one V10 style-transfer method."""
    if method == "content-only":
        return [
            {"ref": "content", "recipe": "keep the same subject", "strength": 0.9},
        ]
    if method == "style-only":
        return [
            {"ref": "style", "recipe": style_label, "strength": 0.65},
        ]
    if method == "two-card":
        return [
            {"ref": "content", "recipe": "keep the same subject", "strength": 0.9},
            {"ref": "style", "recipe": style_label, "strength": 0.55},
        ]
    if method == "final-style":
        return [
            {"ref": "content", "recipe": "keep the same subject", "strength": 0.9},
            {
                "ref": "style",
                "recipe": style_label,
                "strength": 0.65,
                "timing": "final details only",
            },
        ]
    if method == "final-style-guarded":
        return [
            {"ref": "content", "recipe": "keep the same subject", "strength": 0.9},
            {
                "ref": "style",
                "recipe": style_label,
                "strength": 0.65,
                "timing": "final details only",
            },
            {
                "ref": "style",
                "recipe": "copy pose and layout",
                "strength": 0.1,
                "direction": "away from this image",
                "timing": "early layout only",
            },
        ]
    if method == "stable-style":
        return [
            {"ref": "content", "recipe": "keep the same subject", "strength": 0.9},
            {
                "ref": "style",
                "recipe": style_label,
                "strength": 0.6,
                "timing": "final details only",
            },
            {
                "ref": "style",
                "recipe": "copy pose and layout",
                "strength": 0.2,
                "direction": "away from this image",
                "timing": "early layout only",
            },
        ]
    raise ValueError(f"unknown method: {method}")


def build_graph(method, content_ref, style_ref, style_label, prompt, prompt_strength, seed, name, balance):
    graph = {
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": tt.MODEL, "weight_dtype": "default"}},
        "sampling": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3.14, "model": ["unet", 0]}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": tt.CLIP, "type": "krea2", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": tt.VAE}},
        "neg": tt.stack(tt.NEG),
        "latent": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}},
        "save": {
            "class_type": "SaveImage",
            "inputs": {"images": ["decode", 0], "filename_prefix": "claude-generations/recipe-lab/" + name},
        },
    }
    ref_paths = {"content": content_ref, "style": style_ref}
    pos = stack_inputs(prompt, prompt_strength, balance)

    for i, spec in enumerate(method_cards(method, style_label), start=1):
        load_key = f"load{i}"
        card_key = f"card{i}"
        graph[load_key] = {
            "class_type": "LoadImage",
            "inputs": {"image": ref_paths[spec["ref"]], "upload": "image"},
        }
        card_inputs = dict(tt.CARD_DEFAULTS)
        card_inputs.update(
            {
                "Reference image": [load_key, 0],
                "How strongly this image guides": spec["strength"],
                "Use image for": spec["recipe"],
                "Guide direction": spec.get("direction", "toward this image"),
                "When this card guides": spec.get("timing", "recipe decides"),
            }
        )
        graph[card_key] = {"class_type": "KGKrea2ImageGuideCardV10", "inputs": card_inputs}
        pos[f"Reference {i} guide card"] = [card_key, 0]

    graph["pos"] = {"class_type": "KGTextEncodeKreaImageReferencesV10", "inputs": pos}
    graph["sampler"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": 8,
            "cfg": 1.0,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1.0,
            "model": ["sampling", 0],
            "positive": ["pos", 0],
            "negative": ["neg", 0],
            "latent_image": ["latent", 0],
        },
    }
    return graph


def input_ref(server, path):
    return tt.fetch(
        server,
        {
            "filename": Path(path).name,
            "subfolder": str(Path(path).parent).replace("\\", "/"),
            "type": "input",
        },
    )


def metrics(out, content_img, style_img):
    return {
        "content_palette_dist": round(sum(abs(a - b) for a, b in zip(tt.hist(out), tt.hist(content_img))), 3),
        "content_struct_sim": round(tt.struct_sim(tt.gray(out), tt.gray(content_img)), 3),
        "style_palette_dist": round(sum(abs(a - b) for a, b in zip(tt.hist(out), tt.hist(style_img))), 3),
        "style_struct_sim": round(tt.struct_sim(tt.gray(out), tt.gray(style_img)), 3),
        "texture_energy": round(tt.lapvar(out), 0),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--method",
        choices=[
            "content-only",
            "style-only",
            "two-card",
            "final-style",
            "final-style-guarded",
            "stable-style",
        ],
        required=True,
    )
    ap.add_argument("--content-ref", required=True)
    ap.add_argument("--style-ref", required=True)
    ap.add_argument("--style-recipe-json")
    ap.add_argument("--style-label", default="suggest the visual style")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--prompt-strength", type=float, default=1.1)
    ap.add_argument("--seed", type=int, default=771201)
    ap.add_argument("--name", required=True)
    ap.add_argument("--server", default=tt.DEFAULT_SERVER)
    ap.add_argument("--balance", action="store_true")
    args = ap.parse_args()

    server = args.server.rstrip("/")
    style_label = args.style_label
    if args.style_recipe_json:
        bundle = json.loads(Path(args.style_recipe_json).read_text(encoding="utf-8"))
        style_label = bundle["label"]
        tt.OLGA_RECIPES.mkdir(parents=True, exist_ok=True)
        (tt.OLGA_RECIPES / ("lab-" + style_label.replace(" ", "-") + ".json")).write_text(
            json.dumps(bundle),
            encoding="utf-8",
        )
        tt.refresh_card_info(server)

    info = tt.submit(
        server,
        build_graph(
            args.method,
            args.content_ref,
            args.style_ref,
            style_label,
            args.prompt,
            args.prompt_strength,
            args.seed,
            args.name,
            args.balance,
        ),
    )
    out = tt.fetch(server, info)
    tt.OUTDIR.mkdir(parents=True, exist_ok=True)
    local = tt.OUTDIR / (args.name + ".png")
    out.save(local)
    content_img = input_ref(server, args.content_ref)
    style_img = input_ref(server, args.style_ref)
    print(
        json.dumps(
            {
                "name": args.name,
                "method": args.method,
                "image": str(local),
                "style_label": style_label,
                "metrics": metrics(out, content_img, style_img),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
