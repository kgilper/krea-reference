"""Render the V10 user-guide demo set on the ComfyUI box.

One entry per guide journey: every built-in recipe gets a single-card demo,
plus the prompt-only baselines, the timing pair, the direction journey
(including `away`), and the six-card showcase pair (balance off / gentle).
Each render embeds the equivalent V10 *UI* workflow in the PNG (drag it into
ComfyUI to load) and writes the same JSON as a `.workflow.json` sidecar, then
the script rebuilds `guide-demo-manifest.json` and the recipe-gallery contact
sheet. Renders go to the dedicated `claude-generations/` output folder and are
downloaded into `docs/assets/krea-v10/demos/`.

Usage:
  python docs/recipe-lab/generate_guide_demos.py            # render everything
  python docs/recipe-lab/generate_guide_demos.py --only suggest-color-palette,recipe-balanced
  python docs/recipe-lab/generate_guide_demos.py --skip-render   # manifest + sheet only
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tweak_test as tt  # submit/fetch helpers + model constants

DEMO_DIR = Path(__file__).resolve().parents[1] / "assets" / "krea-v10" / "demos"
TEMPLATE_CARD = DEMO_DIR / "suggest-color-palette.workflow.json"
TEMPLATE_OFF = DEMO_DIR / "suggest-color-palette-off.workflow.json"
TEMPLATE_SHOWCASE = DEMO_DIR / "full-showcase.workflow.json"

NEG_PROMPT = ("boring, dull, blurry, low-quality, fake letters, readable text, "
              "logo, watermark, oversaturated colours")
SPHERE = ("a matte ceramic sphere on a small plinth, neutral gray studio backdrop, "
          "soft even light, clean unmarked design, no readable text")

# slug, title, recipe label ("(no cards)" / "showcase"), refs, prompt,
# prompt_strength, seed, strengths, lesson (+ optional direction/timing/balance).
DEMOS = [
    # --- recipe gallery: one card, one job, every built-in recipe -----------
    dict(slug="recipe-balanced", title="Balanced", recipe="balanced",
         refs=["krea-reference-examples/slot1_content_anchor.png"],
         prompt="a ceramic travel mug on a wooden desk in a bright studio, no readable text",
         seed=972110, strengths=[0.6],
         lesson="The all-rounder: subject, palette, and layout each arrive a little; the prompt still leads."),
    dict(slug="recipe-keep-same-subject", title="Keep the same subject", recipe="keep the same subject",
         refs=["krea-reference-examples/slot1_content_anchor.png"],
         prompt="a product photo on a marble countertop in warm morning light, no readable text",
         seed=972111, strengths=[1.0],
         lesson="The reference's subject travels into the prompt's new scene. Strength-hungry by design: expect it to fire from ~0.9 up."),
    dict(slug="recipe-copy-pose-layout", title="Copy pose and layout", recipe="copy pose and layout",
         refs=["krea-reference-examples/slot6_pose_layout.png"],
         prompt="ceramic bottles and bowls arranged on a studio table, soft daylight, no readable text",
         seed=972112, strengths=[0.9],
         lesson="Arrangement without appearance: the reference is studied as a grayscale blur, so placement arrives and color stays the prompt's."),
    dict(slug="recipe-copy-lighting-mood", title="Copy lighting and mood", recipe="copy lighting and mood",
         refs=["krea-reference-examples/slot4_lighting_mood.png"],
         prompt=SPHERE, seed=972113, strengths=[0.65],
         lesson="Borrows the reference's light color and tonal mood as a scene-wide cast; the sphere and plinth stay the prompt's."),
    dict(slug="recipe-suggest-visual-style", title="Suggest the visual style", recipe="suggest the visual style",
         refs=["krea-reference-examples/slot2_style_reference.png"],
         prompt=SPHERE, seed=972101, strengths=[0.65],
         lesson="The bolder sibling of the palette recipe (same inputs, same seed): the source's palette and energy arrive, the subject stays untouched."),
    dict(slug="recipe-suggest-material-texture", title="Suggest material or texture", recipe="suggest material or texture",
         refs=["krea-reference-examples/slot3_material_texture.png"],
         prompt=SPHERE, seed=972114, strengths=[0.75],
         lesson="Borrows the material reference's surface palette and finish energy - the slate-and-sand weave arrives as a stony recolor. Runs the hottest shape of the appearance family because its gain table is the mildest."),
    dict(slug="recipe-copy-big-shapes", title="Copy big shapes only", recipe="copy big shapes only",
         refs=["krea-reference-examples/slot7_shape_only.png"],
         prompt="a minimalist ceramic sculpture on a white plinth, gallery lighting, no readable text",
         seed=972115, strengths=[0.9],
         lesson="Silhouette guidance: the reference is reduced to a shape wash, so only the big masses steer the composition."),
    dict(slug="recipe-avoid-text-logos", title="Avoid copying text/logos", recipe="avoid copying text/logos",
         refs=["krea-reference-examples/slot5_text_logo_guard.png"],
         prompt="a plain cardboard shipping box on a white table, soft studio light, no readable text",
         seed=972116, strengths=[0.5],
         lesson="The guard recipe clamps itself to 0.03 no matter the slider and rewrites the prompt toward blank surfaces: the label-covered reference cannot deposit markings."),
    dict(slug="suggest-color-palette", title="Suggest the color palette", recipe="suggest the color palette",
         refs=["krea-reference-examples/slot2_style_reference.png"],
         prompt=SPHERE, seed=972101, strengths=[0.65],
         lesson="Palette-only borrows color relationships and nothing else: the palette arrives, the abstract source shapes do not."),
    dict(slug="use-background-setting", title="Use the background/setting", recipe="use the background/setting",
         refs=["krea-reference-examples/slot8_background_environment.png"],
         prompt="a sculptural table lamp on a small side table, editorial product photo, cohesive interior scene, no readable text",
         seed=972102, strengths=[0.65],
         lesson="Borrows the setting's palette and room mood while the prompt keeps the lamp. It suggests the atmosphere of the place, not a pasted backdrop."),
    dict(slug="copy-camera-framing", title="Copy the camera framing", recipe="copy the camera framing",
         refs=["krea-reference-examples/slot6_pose_layout.png"],
         prompt="three ceramic vases in a row on a low wooden table, plain unmarked surfaces, soft daylight, refined product photography, no readable text",
         seed=972103, strengths=[0.3],
         lesson="Framing borrows camera distance, crop, and viewpoint only - grayscale study, structure-heavy early, quiet late."),
    dict(slug="mood-board-only", title="Mood board only", recipe="mood board only",
         refs=["krea-reference-examples/slot2_style_reference.png"],
         prompt="a calm desk scene with a small ceramic lamp and a closed notebook, editorial photo, no readable text",
         seed=972104, strengths=[0.5],
         lesson="Loose inspiration under a hard 0.9 cap: a gentle borrowed palette and feeling, never a dictated composition."),
    # --- journeys -----------------------------------------------------------
    dict(slug="suggest-color-palette-off", title="Palette journey: prompt only", recipe="(no cards)",
         refs=[], prompt=SPHERE, seed=972101, strengths=[],
         lesson="Baseline for the palette pair: the prompt alone asks for a neutral gray scene."),
    dict(slug="timing-style-early-only", title="Timing: style, early layout only", recipe="suggest the visual style",
         refs=["krea-reference-examples/slot2_style_reference.png"],
         prompt="a modern table lamp in a clean studio product photo, no readable text",
         seed=972105, strengths=[0.75], timing="early layout only",
         lesson="The style card guides only the first 40% of steps: broad color fields and composition arrive early, then the prompt's own finish passes smooth the surfaces."),
    dict(slug="timing-style-final-only", title="Timing: style, final details only", recipe="suggest the visual style",
         refs=["krea-reference-examples/slot2_style_reference.png"],
         prompt="a modern table lamp in a clean studio product photo, no readable text",
         seed=972105, strengths=[0.75], timing="final details only",
         lesson="Same seed, same card, opposite timing: the prompt owns the early composition and the source arrives in the detail passes - its mosaic finish lands crisply on the prompt's lamp."),
    dict(slug="counter-example-baseline", title="Counter-example journey: prompt only", recipe="(no cards)",
         refs=[], prompt="a sculptural table lamp in a clean studio product photo, no readable text",
         seed=972106, strengths=[],
         lesson="Step one of the direction journey: the prompt alone, no reference cards."),
    dict(slug="counter-example-toward", title="Counter-example journey: style pulled toward", recipe="suggest the visual style",
         refs=["krea-reference-examples/slot2_style_reference.png"],
         prompt="a sculptural table lamp in a clean studio product photo, no readable text",
         seed=972106, strengths=[0.65],
         lesson="Step two: the style source pulled toward at 0.65 - palette, finish, art direction arrive."),
    dict(slug="counter-example-away", title="Counter-example journey: style pushed away", recipe="suggest the visual style",
         refs=["krea-reference-examples/slot2_style_reference.png"],
         prompt="a sculptural table lamp in a clean studio product photo, no readable text",
         seed=972106, strengths=[0.4], direction="away from this image",
         lesson="Step three: the same card set to away steers the result out of the source's palette and manner. Away pushes harder per slider unit, so start lower."),
    dict(slug="full-showcase", title="Full showcase - six jobs", recipe="showcase",
         refs=["krea-reference-examples/slot1_content_anchor.png",
               "krea-reference-examples/slot2_style_reference.png",
               "krea-reference-examples/slot8_background_environment.png",
               "krea-reference-examples/slot4_lighting_mood.png",
               "krea-reference-examples/slot6_pose_layout.png",
               "krea-reference-examples/slot5_text_logo_guard.png"],
         prompt="a ceramic travel mug on a wooden desk in a bright studio, no readable text",
         prompt_strength=1.15, seed=972107, strengths=[0.8, 0.55, 0.35, 0.4, 0.3, 0.03],
         lesson="Six cards, one job each, balance off."),
    dict(slug="full-showcase-balanced", title="Full showcase - gentle balance", recipe="showcase",
         refs=["krea-reference-examples/slot1_content_anchor.png",
               "krea-reference-examples/slot2_style_reference.png",
               "krea-reference-examples/slot8_background_environment.png",
               "krea-reference-examples/slot4_lighting_mood.png",
               "krea-reference-examples/slot6_pose_layout.png",
               "krea-reference-examples/slot5_text_logo_guard.png"],
         prompt="a ceramic travel mug on a wooden desk in a bright studio, no readable text",
         prompt_strength=1.15, seed=972107, strengths=[0.8, 0.55, 0.35, 0.4, 0.3, 0.03],
         balance=True,
         lesson="The same six cards under gentle balance: the stack budgets the total pull so strong cards degrade gracefully instead of fighting."),
]

# The 12 gallery slugs, in the order they appear on the contact sheet.
GALLERY = ["recipe-balanced", "recipe-keep-same-subject", "recipe-copy-pose-layout",
           "recipe-copy-big-shapes", "copy-camera-framing", "recipe-avoid-text-logos",
           "suggest-color-palette", "recipe-suggest-visual-style", "recipe-copy-lighting-mood",
           "recipe-suggest-material-texture", "use-background-setting", "mood-board-only"]

# Showcase card labels/timing, matching the shipped showcase workflow order.
SHOWCASE_CARDS = [("keep the same subject", "recipe decides"),
                  ("suggest the visual style", "recipe decides"),
                  ("use the background/setting", "recipe decides"),
                  ("suggest the color palette", "recipe decides"),
                  ("copy the camera framing", "early layout only"),
                  ("avoid copying text/logos", "recipe decides")]


def _stack_inputs(prompt, strength, balance):
    return {"Krea CLIP": ["clip", 0], "Final image prompt": prompt,
            "Written prompt strength": strength,
            "Image slider feel": "artist friendly - soft at low values",
            "Image detail level": "medium - balanced default (384)",
            "Image framing": "keep full image shape",
            "When images guide": "smart per-card timing",
            "Early-to-final handoff": 0.4,
            "Text/logo guard prompt handling": "full guard - rewrite my prompt",
            "Balance strong cards": "gentle balance" if balance else "off - use my values",
            "Reuse image studies": "always re-study"}


def _neg_inputs():
    return {"Krea CLIP": ["clip", 0], "Final image prompt": NEG_PROMPT,
            "Written prompt strength": 1.0,
            "Image slider feel": "literal slider values",
            "Image detail level": "low - loose idea (256)",
            "Image framing": "keep full image shape",
            "When images guide": "guide the whole image",
            "Early-to-final handoff": 0.4,
            "Text/logo guard prompt handling": "gentle guard - keep my prompt words",
            "Balance strong cards": "off - use my values",
            "Reuse image studies": "always re-study"}


def build_api_graph(demo):
    """API-format graph for one demo: the values the UI workflow shows."""
    g = {"unet": {"class_type": "UNETLoader", "inputs": {"unet_name": tt.MODEL, "weight_dtype": "default"}},
         "sampling": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3.14, "model": ["unet", 0]}},
         "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": tt.CLIP, "type": "krea2", "device": "default"}},
         "vae": {"class_type": "VAELoader", "inputs": {"vae_name": tt.VAE}},
         "neg": {"class_type": "KGTextEncodeKreaImageReferencesV10", "inputs": _neg_inputs()},
         "latent": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 768, "batch_size": 1}},
         "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0], "vae": ["vae", 0]}},
         "save": {"class_type": "SaveImage", "inputs": {
             "images": ["decode", 0],
             "filename_prefix": "claude-generations/guide-demos/" + demo["slug"]}}}
    pos = _stack_inputs(demo["prompt"], demo.get("prompt_strength", 1.25), demo.get("balance", False))
    cards = SHOWCASE_CARDS if demo["recipe"] == "showcase" else [
        (demo["recipe"], demo.get("timing", "recipe decides"))] if demo["refs"] else []
    for i, (ref, strength) in enumerate(zip(demo["refs"], demo["strengths"]), start=1):
        label, timing = cards[i - 1]
        g["load%d" % i] = {"class_type": "LoadImage", "inputs": {"image": ref, "upload": "image"}}
        card_in = dict(tt.CARD_DEFAULTS)
        card_in.update({"Reference image": ["load%d" % i, 0],
                        "How strongly this image guides": strength,
                        "Use image for": label,
                        "Guide direction": demo.get("direction", "toward this image"),
                        "When this card guides": timing})
        g["card%d" % i] = {"class_type": "KGKrea2ImageGuideCardV10", "inputs": card_in}
        pos["Reference %d guide card" % i] = ["card%d" % i, 0]
    g["pos"] = {"class_type": "KGTextEncodeKreaImageReferencesV10", "inputs": pos}
    g["sampler"] = {"class_type": "KSampler", "inputs": {
        "seed": demo["seed"], "steps": 8, "cfg": 1.0, "sampler_name": "euler",
        "scheduler": "simple", "denoise": 1.0, "model": ["sampling", 0],
        "positive": ["pos", 0], "negative": ["neg", 0], "latent_image": ["latent", 0]}}
    return g


def build_ui_workflow(demo):
    """Patch the right shipped template into this demo's drag-in UI workflow."""
    if demo["recipe"] == "showcase":
        ui = json.loads(TEMPLATE_SHOWCASE.read_text(encoding="utf-8"))
    elif demo["refs"]:
        ui = json.loads(TEMPLATE_CARD.read_text(encoding="utf-8"))
    else:
        ui = json.loads(TEMPLATE_OFF.read_text(encoding="utf-8"))
    ui["id"] = "kg-krea-v10-demo-" + demo["slug"]
    ui.setdefault("extra", {})["workflow_name"] = "Krea V10 demo - " + demo["title"]
    card_index = 0
    for node in ui["nodes"]:
        t = node["type"]
        if t == "KSampler":
            node["widgets_values"][0] = demo["seed"]
        elif t == "SaveImage":
            node["widgets_values"][0] = "krea_reference_v10_guide/" + demo["slug"]
        elif t == "LoadImage" and demo["refs"]:
            # showcase load nodes appear in reference order; single template has one
            idx = min(card_index, len(demo["refs"]) - 1)
            if demo["recipe"] == "showcase":
                continue  # showcase template already points at the right assets
            node["widgets_values"][0] = demo["refs"][idx]
        elif t == "KGKrea2ImageGuideCardV10":
            wv = node["widgets_values"]
            wv[0] = demo["strengths"][card_index]
            if demo["recipe"] != "showcase":
                wv[1] = demo["recipe"]
                wv[14] = demo.get("direction", "toward this image")
                wv[15] = demo.get("timing", "recipe decides")
                node["title"] = "Guide Card V10 - " + demo["recipe"]
            card_index += 1
        elif t == "KGTextEncodeKreaImageReferencesV10" and "negative" not in (node.get("title") or ""):
            wv = node["widgets_values"]
            wv[0] = demo["prompt"]
            wv[1] = demo.get("prompt_strength", 1.25)
            wv[8] = "gentle balance" if demo.get("balance") else "off - use my values"
    return ui


def render(demo, server):
    ui = build_ui_workflow(demo)
    graph = build_api_graph(demo)
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
            raise RuntimeError(demo["slug"] + ": " + json.dumps(e.get("status"))[:300])
        time.sleep(2)
    else:
        raise TimeoutError(demo["slug"])
    # download the PNG (with the embedded workflow) and write the sidecar
    q = urllib.parse.urlencode({"filename": info["filename"],
                                "subfolder": info.get("subfolder", ""), "type": "output"})
    with urllib.request.urlopen(server + "/view?" + q, timeout=60) as r:
        (DEMO_DIR / (demo["slug"] + ".png")).write_bytes(r.read())
    (DEMO_DIR / (demo["slug"] + ".workflow.json")).write_text(
        json.dumps(ui, indent=2), encoding="utf-8")
    print("rendered", demo["slug"])


def write_manifest():
    entries = []
    for d in DEMOS:
        entries.append({
            "slug": d["slug"], "title": d["title"], "recipe": d["recipe"],
            "references": d["refs"], "prompt": d["prompt"],
            "prompt_strength": d.get("prompt_strength", 1.25), "seed": d["seed"],
            "strengths": d["strengths"],
        })
        if d.get("direction"):
            entries[-1]["direction"] = d["direction"]
        if d.get("timing"):
            entries[-1]["timing"] = d["timing"]
        if d.get("balance"):
            entries[-1]["balance"] = "gentle balance"
        entries[-1]["output"] = "demos/" + d["slug"] + ".png"
        entries[-1]["workflow"] = "demos/" + d["slug"] + ".workflow.json"
        entries[-1]["lesson"] = d["lesson"]
    manifest = {
        "generated_at": "2026-07-03",
        "model": tt.MODEL, "clip": tt.CLIP, "vae": tt.VAE,
        "note": ("Demo images were generated by ComfyUI with the equivalent V10 workflow "
                 "embedded in PNG extra_pnginfo.workflow. Drag an individual demo PNG into "
                 "ComfyUI to load its V10 workflow."),
        "engine_note": ("Rendered with the real V10 nodes (retuned recipes) on the LAN "
                        "ComfyUI box; the embedded workflow values are exactly what rendered."),
        "gallery": GALLERY,
        "demos": entries,
        "workflow_embedded_in_png": True,
    }
    (DEMO_DIR / "guide-demo-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print("manifest written")


def write_gallery_sheet():
    """3x4 labeled contact sheet of the 12 recipe demos."""
    cell_w, cell_h, bar = 256, 384, 26
    cols, rows = 3, 4
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + bar)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    titles = {d["slug"]: (d["recipe"] if d["recipe"] not in ("(no cards)", "showcase") else d["title"])
              for d in DEMOS}
    for i, slug in enumerate(GALLERY):
        img = Image.open(DEMO_DIR / (slug + ".png")).convert("RGB").resize((cell_w, cell_h))
        x, y = (i % cols) * cell_w, (i // cols) * (cell_h + bar)
        sheet.paste(img, (x, y))
        draw.text((x + 8, y + cell_h + 6), titles[slug], fill=(235, 235, 235))
    sheet.save(DEMO_DIR / "recipe-gallery.png")
    print("gallery sheet written")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--server", default=tt.DEFAULT_SERVER)
    ap.add_argument("--only", help="comma-separated slugs to render")
    ap.add_argument("--skip-render", action="store_true")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None
    if not args.skip_render:
        for demo in DEMOS:
            if only and demo["slug"] not in only:
                continue
            render(demo, args.server.rstrip("/"))
    write_manifest()
    write_gallery_sheet()


if __name__ == "__main__":
    main()
