# Krea Reference V10 User Guide

Krea Reference lets every source image have a clear job before it reaches Krea.
V10 keeps everything from V9 and adds four more jobs, a direction (a card can
now be a counter-example), per-card timing, an auto-balance for hot stacks, a
study cache for fast tuning, and two feedback outputs that show you what the
stack actually did.

If you are new to Krea Reference, read the [V9 guide](krea-v9-user-guide.md)
first for the core mental model; this guide focuses on what V10 adds - and it
now demonstrates **every built-in recipe**, not just the new ones. Every demo
below is a complete journey - input images, recipe and settings, the exact
prompt, and the result - and every result PNG has the matching V10 workflow
embedded, so you can drag it into ComfyUI and inspect the setup.

All twelve recipes, one job each (details in
[The Recipe Gallery](#the-recipe-gallery)):

![Krea V10 demo output gallery](assets/krea-v10/demos/recipe-gallery.png)

The synthetic source images used throughout ship with the repo:

![Synthetic reference images included with Krea Reference](../example_assets/krea-reference-examples/contact_sheet.png)

## Contents

- [Fast Start](#fast-start)
- [What V10 Adds](#what-v10-adds)
- [How The Demos Were Made](#how-the-demos-were-made)
- [The Recipe Gallery](#the-recipe-gallery)
- [New Quick Recipes](#new-quick-recipes)
- [Create Your Own Recipes](#create-your-own-recipes)
- [Guide Direction: Counter-Examples](#guide-direction-counter-examples)
- [Per-Card Timing](#per-card-timing)
- [Manual Layer Dials](#manual-layer-dials)
- [Balance Strong Cards](#balance-strong-cards)
- [Reuse Image Studies](#reuse-image-studies)
- [Reading The Stack Report](#reading-the-stack-report)
- [The Prepared-References Preview](#the-prepared-references-preview)
- [Multi-Reference Recipes](#multi-reference-recipes)
- [Embedded Demo Workflows](#embedded-demo-workflows)
- [Troubleshooting](#troubleshooting)

## Fast Start

Use one guide card per image, exactly as in V9:

```text
Load Image -> KG Krea 2 Image Guide Card V10 -> KG Krea 2 Reference Stack Encoder V10 -> KSampler positive input
```

Then wire the two new stack outputs:

```text
Reference Stack Encoder V10 (stack_report) -> Preview Any
Reference Stack Encoder V10 (prepared_references) -> Preview Image
```

Try the bundled examples first:

| File | Purpose |
| --- | --- |
| [krea-v10-full-showcase-workflow.json](../example_workflows/krea-v10-full-showcase-workflow.json) | Best first run. Six cards including the new palette, environment, and framing recipes, per-card timing, gentle balance, and both feedback outputs. |
| [krea-v10-counter-example-workflow.json](../example_workflows/krea-v10-counter-example-workflow.json) | The new `away from this image` direction: keep the subject, push a style out. |
| [krea-v10-reference-stack-workflow.json](../example_workflows/krea-v10-reference-stack-workflow.json) | Compact starter graph for building your own V10 stack. |

Copy [example_assets/krea-reference-examples](../example_assets/krea-reference-examples/)
into your ComfyUI `input/` folder so the bundled workflows can find their
example images.

V9 and V10 cross-connect: a V9 card plugs into the V10 stack (the V10 controls
use their defaults) and a V10 card plugs into a V9 stack (which ignores the
V10 controls). Saved V9 workflows keep working unchanged.

## What V10 Adds

| Control | Where | What it does |
| --- | --- | --- |
| `suggest the color palette` | card | Palette-only quick recipe (was manual-only in V9). |
| `use the background/setting` | card | Environment quick recipe (was manual-only in V9). |
| `copy the camera framing` | card | Framing-only quick recipe (was manual-only in V9). |
| `mood board only` | card | Loose-inspiration quick recipe (was manual-only in V9). |
| Custom recipes | card | Your own YAML/JSON recipe files appear in `Use image for` as first-class choices. |
| `focus` recipe field | recipe file | A recipe can study **one named aspect** of its image - clothing, props, a setting - and skip the rest. The built-in style and lighting recipes ship focuses of their own. |
| Bundled recipes | shipped | Twenty ready-made recipes load out of the box: the [starter pack](../custom_recipes/starter-pack.yaml) (weather, clothing, drawing medium, photo finish, cinematic color grade), the [designer artwork pack](../custom_recipes/designer-artwork-pack.yaml) (poster style, soft media, pattern energy, era print look, paper and canvas, metallic accents, ornament borders, stained glass, and the style-timing pair), and the [edit-and-composite pack](../custom_recipes/edit-composite-pack.yaml) (scene light, monochrome look, atmosphere, background only, carry the subject over). |
| Recipe Builder | `web/` | A single HTML page that turns three plain-language questions into a validated recipe file. |
| `Guide direction` | card | `toward this image` (V9 behavior) or `away from this image` (counter-example). |
| `When this card guides` | card | Per-card timing: recipe decides, whole image, early layout only, or final details only. |
| `Structure layers pull` / `Finish layers pull` | card | Manual-mode dials over the structure-vs-finish conditioning layers. |
| `Balance strong cards` | stack | Budgets the total pull of hot stacks so cards degrade gracefully instead of fighting. |
| `Reuse image studies` | stack | Content-keyed cache; strength/timing tweaks re-run with zero encoder passes. |
| `stack_report` | stack output | Plain-language account of what every card requested, got, and why. |
| `prepared_references` | stack output | Contact sheet of exactly what the vision encoder studied. |

The text/logo guard's full-guard prompt rewriter also understands common
marking words in Spanish, French, German, Portuguese, and Italian.

## How The Demos Were Made

Every journey in this guide shares the same house setup, so the settings
tables list only what changes per demo:

| House setting | Value |
| --- | --- |
| Model / CLIP / VAE | `krea2_turbo_nvfp4` / `qwen3vl_4b_fp8_scaled` / `qwen_image_vae` |
| Sampler | 8 steps, cfg `1.0`, `euler` / `simple`, AuraFlow shift `3.14`, 512x768, fixed seed per demo |
| Stack | `artist friendly` feel, `medium (384)` detail, `keep full image shape`, `smart per-card timing`, handoff `0.40`, written prompt strength `1.25` |
| Negative prompt | `boring, dull, blurry, low-quality, fake letters, readable text, logo, watermark, oversaturated colours` |

Drag any result PNG into ComfyUI to load its embedded V10 workflow, or open
the `.workflow.json` beside it in [assets/krea-v10/demos](assets/krea-v10/demos/).
Every demo was rendered by ComfyUI through the real V10 nodes with the current
recipe tuning - the embedded workflow values are exactly what rendered - using
the maintainer script
[docs/recipe-lab/generate_guide_demos.py](recipe-lab/generate_guide_demos.py).

## The Recipe Gallery

One demo per built-in recipe, all on the bundled example assets so you can
reproduce any row. The four appearance journeys marked with the same prompt
and seed are directly comparable - the only change between them is the card.

| Recipe | Reference | Strength | Seed | Result | What arrives |
| --- | --- | --- | --- | --- | --- |
| `balanced` | slot1 content anchor | `0.60` | `972110` | [PNG](assets/krea-v10/demos/recipe-balanced.png) | A little of everything; the prompt still leads. |
| `keep the same subject` | slot1 content anchor | `1.00` | `972111` | [PNG](assets/krea-v10/demos/recipe-keep-same-subject.png) | The reference's subject travels into the prompt's new scene - markings included (pair with the guard if you don't want them). Fires from ~`0.9` up. |
| `copy pose and layout` | slot6 pose/layout | `0.90` | `972112` | [PNG](assets/krea-v10/demos/recipe-copy-pose-layout.png) | The arrangement, studied as a grayscale blur - placement arrives, color stays the prompt's. |
| `copy big shapes only` | slot7 shape only | `0.90` | `972115` | [PNG](assets/krea-v10/demos/recipe-copy-big-shapes.png) | Silhouette guidance only - the big masses steer the composition. |
| `copy the camera framing` | slot6 pose/layout | `0.30` | `972103` | [PNG](assets/krea-v10/demos/copy-camera-framing.png) | Camera distance, crop, and viewpoint - subject and palette stay the prompt's. |
| `avoid copying text/logos` | slot5 text/logo guard | `0.50` (clamps to `0.03`) | `972116` | [PNG](assets/krea-v10/demos/recipe-avoid-text-logos.png) | Nothing readable: the guard clamps the card and rewrites the prompt toward blank surfaces. |
| `suggest the color palette` | slot2 style reference | `0.65` | `972101` | [PNG](assets/krea-v10/demos/suggest-color-palette.png) | The reference's color relationships, as soft color fields - composition identical to the no-card baseline. |
| `suggest the visual style` | slot2 style reference | `0.65` | `972101` | [PNG](assets/krea-v10/demos/recipe-suggest-visual-style.png) | Same inputs and seed as the palette row: true style transfer - the medium, palette, and finish energy arrive with the subject kept crisp (an anti-blur focus keeps the recipe's own softening out of the result). |
| `copy lighting and mood` | slot4 lighting/mood | `0.65` | `972113` | [PNG](assets/krea-v10/demos/recipe-copy-lighting-mood.png) | The reference's light color and tonal mood as a scene-wide cast. |
| `suggest material or texture` | slot3 material/texture | `0.55` | `972114` | [PNG](assets/krea-v10/demos/recipe-suggest-material-texture.png) | The material's surface finish and pattern energy, with source structure kept quiet. |
| `use the background/setting` | slot8 background/environment | `0.65` | `972102` | [PNG](assets/krea-v10/demos/use-background-setting.png) | The setting's palette and room mood; the model builds a coherent place around the prompt's subject. |
| `mood board only` | slot2 style reference | `0.50` | `972104` | [PNG](assets/krea-v10/demos/mood-board-only.png) | A gentle borrowed palette and feeling under a hard cap - never a dictated composition. |

Two honest notes on the appearance family (palette, style, lighting,
material, environment, mood board), tuned and render-verified on Krea 2:

- **They respond to the strength slider in a controllable band.** Low
  strengths whisper, the borrow lands clearly from about `0.6`, and each
  recipe caps itself before "too much". If an appearance card seems silent,
  raise its strength toward `0.65` first.
- **They borrow palette and mood, not paint.** With their structure-safe
  preparation the reference's colors arrive as color fields over the scene
  and subject; they do not repaint the reference's brushwork onto your
  subject's surface or composite its scene behind it. Where the color lands
  follows the prompt: sparse neutral scenes let it settle on the subject
  itself (as in the sphere demos).

## New Quick Recipes

The four V10 recipes cover the jobs that previously required `manual tuning`.
Each journey below shows the input, the card settings, the exact prompt, and
the result.

### Suggest The Color Palette

| Input | Result |
| --- | --- |
| <img src="../example_assets/krea-reference-examples/slot2_style_reference.png" alt="Palette source image" width="260"> | <img src="assets/krea-v10/demos/suggest-color-palette.png" alt="Suggest the color palette result" width="420"> |

| Setting | Value |
| --- | --- |
| Recipe | `suggest the color palette` |
| Strength | `0.65` (whispers below ~`0.5`, clear from ~`0.6`, capped at `0.9`) |
| Seed | `972101` |
| Prompt | `a matte ceramic sphere on a small plinth, neutral gray studio backdrop, soft even light, clean unmarked design, no readable text` |
| Demo files | [result PNG](assets/krea-v10/demos/suggest-color-palette.png), [workflow JSON](assets/krea-v10/demos/suggest-color-palette.workflow.json) |

Compare the pair below - same prompt, same seed, the only change is the
card: the neutral sphere takes on the source's pastel coral-teal-lavender
relationships as soft color fields while the abstract source shapes stay out
entirely. The image is reduced to a palette wash at low study resolution
before the encoder sees it, so color relationships are all that *can*
arrive - which is also why the composition is pixel-comparable to the
baseline.

| Prompt only (no cards) | With the palette card |
| --- | --- |
| <img src="assets/krea-v10/demos/suggest-color-palette-off.png" alt="Palette journey prompt-only baseline" width="300"> | <img src="assets/krea-v10/demos/suggest-color-palette.png" alt="Palette journey with palette card" width="300"> |

### Use The Background/Setting

| Input | Result |
| --- | --- |
| <img src="../example_assets/krea-reference-examples/slot8_background_environment.png" alt="Environment source image" width="260"> | <img src="assets/krea-v10/demos/use-background-setting.png" alt="Use the background/setting result" width="420"> |

| Setting | Value |
| --- | --- |
| Recipe | `use the background/setting` |
| Strength | `0.65` |
| Seed | `972102` |
| Prompt | `a sculptural table lamp on a small side table, editorial product photo, cohesive interior scene, no readable text` |
| Demo files | [result PNG](assets/krea-v10/demos/use-background-setting.png), [workflow JSON](assets/krea-v10/demos/use-background-setting.workflow.json) |

The environment recipe borrows the *feeling of the place*: the reference's
warm plaster palette and room mood arrive, and the model builds a coherent
interior around the prompt's lamp. It deliberately does not lift the
reference's literal room - the reference is studied structure-free, so it can
set the atmosphere without ever reshaping your subject into its own forms.

### Copy The Camera Framing

| Input | Result |
| --- | --- |
| <img src="../example_assets/krea-reference-examples/slot6_pose_layout.png" alt="Framing source image" width="260"> | <img src="assets/krea-v10/demos/copy-camera-framing.png" alt="Copy the camera framing result" width="420"> |

| Setting | Value |
| --- | --- |
| Recipe | `copy the camera framing` |
| Strength | `0.30` |
| Seed | `972103` |
| Prompt | `three ceramic vases in a row on a low wooden table, plain unmarked surfaces, soft daylight, refined product photography, no readable text` |
| Demo files | [result PNG](assets/krea-v10/demos/copy-camera-framing.png), [workflow JSON](assets/krea-v10/demos/copy-camera-framing.workflow.json) |

Framing borrows camera distance, crop, and viewpoint only - the diagonal
row arrangement echoes the reference while subject, palette, and surface
come from the prompt. The recipe studies the reference in grayscale at its
own aspect ratio, because the frame *is* the information. It pairs well with
`When this card guides` set to `early layout only`.

### Mood Board Only

| Input | Result |
| --- | --- |
| <img src="../example_assets/krea-reference-examples/slot2_style_reference.png" alt="Mood board source image" width="260"> | <img src="assets/krea-v10/demos/mood-board-only.png" alt="Mood board only result" width="420"> |

| Setting | Value |
| --- | --- |
| Recipe | `mood board only` |
| Strength | `0.50` (hard cap `0.9`) |
| Seed | `972104` |
| Prompt | `a calm desk scene with a small ceramic lamp and a closed notebook, editorial photo, no readable text` |
| Demo files | [result PNG](assets/krea-v10/demos/mood-board-only.png), [workflow JSON](assets/krea-v10/demos/mood-board-only.workflow.json) |

Mood board stays the quietest appearance recipe: a gentle borrowed palette
and feeling - the sage-and-cream calm of the source settles over the desk -
without ever dictating content or composition.

## Create Your Own Recipes

The built-in recipes are settings bundles - and in V10 you can write your
own. A custom recipe is a small YAML or JSON file; every file that passes
validation appears in `Use image for` as a first-class choice,
indistinguishable from a built-in. This section defines **every field, every
allowed value, and what changing it does** - all of it verified against the
node's own code and render-tested on the real model, so nothing here needs
guessing.

> **No schema required:** the pack ships a
> [Recipe Builder](../web/recipe-builder.html) (`web/recipe-builder.html`) -
> a single HTML page you can open in any browser (or from a running ComfyUI
> at `/extensions/<pack folder>/recipe-builder.html`). Pick what the
> reference should give, pick a loudness, download the file. Every number is
> filled from the render-validated tables below, and the page tells you
> honestly what each job can and cannot do. The rest of this section is for
> when you want to understand or hand-tune what the builder produces.

### Where recipe files go

| Location | Notes |
| --- | --- |
| `custom_recipes/` inside this node pack | Ships with a README and a template. Easiest to find. |
| `<ComfyUI user dir>/krea_reference/recipes/` | Survives reinstalling or updating the node pack. Create the folder if it does not exist. |

The loading rules, exactly:

- Accepted extensions: `.yaml`, `.yml`, `.json`. YAML needs PyYAML (ComfyUI
  ships it); JSON always works.
- A file holds either **one recipe** (a plain mapping) or **a pack** - a
  mapping whose *only* key is `recipes`, holding a list of recipe mappings.
  Any other top-level key alongside `recipes` rejects the file.
- Files named with a leading `_` or `.` are ignored - that is how the
  bundled template
  ([_example-vintage-postcard.yaml](../custom_recipes/_example-vintage-postcard.yaml))
  ships without adding itself to your dropdown, and how you disable a recipe
  without deleting it.
- Files load in **sorted name order**, pack folder first, then the user
  directory. The first definition of a label wins; a duplicate label in a
  later file is skipped with a collision warning.
- The dropdown re-scans on every node-definition refresh, so dropping in or
  editing a file needs a refresh (or restart), not a reinstall.

### Your first recipe, in three steps

1. Create `custom_recipes/soft-palette-hint.yaml` containing:

   ```yaml
   label: soft palette hint
   role: palette
   cap: 0.5
   ```

2. In ComfyUI, refresh node definitions (or restart).
3. Open a V10 guide card: `soft palette hint` is now in `Use image for`.

Only `label` (the dropdown text) and `role` (which built-in behavior family
to start from) are required. Every omitted field defaults from the role's
tuning tables, so a two-line recipe is already well-behaved.

### How a recipe becomes a picture

Every field acts at exactly one of three stages. Knowing a field's stage
tells you what it can and cannot do before you touch it:

| Stage | What happens | Fields that act here |
| --- | --- | --- |
| **1. What the encoder sees** | The reference is physically re-drawn before study, in this order: framed (`framing`), scaled to the study size (`study`), color-reduced (`color`), treated (`treatment`), detail-softened (`detail`). The stack's `prepared_references` output shows exactly this frame. | `framing`, `study`, `color`, `treatment`, `detail` |
| **2. What the encoder is told** | The stack writes instruction lines for the card: the `role`'s borrow sentence, your `focus` ("study only ... ignore everything else about it"), and the `subject` rule. | `role`, `subject`, `focus` |
| **3. How hard it lands** | The card's slider is ceilinged (`cap`), shaped by the stack's slider-feel curve, split into sampling phases (`early`, `late`), then scaled onto the conditioning: `shape` times the per-band `layers` gains. `global` would also act here - on models with a pooled channel, which Krea 2 is not. `guard: true` clamps this whole stage. | `cap`, `early`, `late`, `shape`, `global`, `layers`, `guard` |

Stage 1 is the only stage with a **guarantee**: whatever the treatment
destroys cannot arrive, no matter what stages 2 and 3 ask for. Stage 2
*biases* the study; stage 3 sets the *volume*. When a render misbehaves,
identify which stage owns the problem - leak means stage 1, wrong aspect
means stage 2, too quiet or too loud means stage 3.

### The four facts (read this before tuning numbers)

Established by rendering controlled sweeps on the real model. They are the
difference between a recipe that works and one that silently does nothing:

1. **`treatment` decides WHAT can transfer.** The reference is re-drawn by
   the treatment *before* the encoder studies it, so it is a hard filter on
   what the card can possibly deliver:

   | You want to borrow | Use treatment | Why it is safe |
   | --- | --- | --- |
   | colors / palette / mood | `palette wash` | the source's shapes are destroyed first, so its subject **cannot** leak in |
   | style / medium / light mood | `strong blur` + a de-selecting `focus` + a `cap` | how the shipped style and lighting recipes work: the blur mutes detail, the focus skips the source's subject, layout, *and the blur itself* |
   | layout / arrangement | `grayscale blur` | color is stripped, so placement arrives without recoloring |
   | silhouette only | `shape wash` | everything but the big masses is removed (pair with a structure-heavy `layers` table like the shipped shape recipe, or the flat-gray study can mute your colors) |
   | the actual subject | `normal` | nothing is removed - the subject can and will copy in |
   | subject + softness | `soft blur` / `strong blur` alone | **caution:** without a focus and cap the source's forms survive; at working strengths the source object tends to appear or reshape your subject |

2. **`shape` is the volume knob.** It scales the one conditioning channel
   that actually moves pixels on Krea 2:

   | `shape` | What happens at normal card strengths (~`0.6`-`0.9`) |
   | --- | --- |
   | `0.0`-`0.4` | effectively **off** - nothing visible arrives, at any slider value |
   | `0.5`-`0.65` | onset - the borrow appears only near the top of the strength range |
   | `0.7`-`1.0` | the appearance recipes' working range - clear borrow by strength ~`0.65`, subject preserved (with a structure-destroying treatment) |
   | `1.0`-`1.3` | structural jobs - layout and subject transfer |

3. **`layers` fine-tunes WHICH bands are emphasized - it is second-order.**
   The 12 gains reshape the signal `shape` lets through; they cannot rescue
   a `shape` that is too low. Omit `layers` unless you are deliberately
   fine-tuning.

4. **`global` has no effect on Krea 2.** It scales a pooled conditioning
   channel this model's text encoder does not produce. The field stays for
   other/future models - but a weak recipe on Krea 2 is fixed by raising
   `shape` (and hardening `treatment`), never by raising `global`.

And one limit to design around: with a structure-destroying treatment the
borrowed look arrives as palette and mood over the scene - not as brushwork
painted onto your subject's surface, and not as the source's scene composited
behind it. Recipes promising those need conditioning this model does not
have; write honest descriptions instead.

### The full schema at a glance

A file holds one recipe, or a pack: `{"recipes": [recipe, recipe, ...]}`.
Every field is defined in depth in the next section.

| Field | Required | Values | Default |
| --- | --- | --- | --- |
| `label` | yes | Dropdown text. Must not collide with any reserved label (list below). | - |
| `role` | yes | `balanced`, `style`, `palette`, `composition`, `framing`, `identity`, `environment`, `lighting`, `material`, `loose`, `shape only`, `text/logo safe` | - |
| `description` | no | Free text for humans; never sent to the model. | `""` |
| `treatment` | no | `normal`, `grayscale`, `soft blur`, `strong blur`, `palette wash`, `color wash`, `grayscale blur`, `shape wash` | `normal` |
| `color` | no | `0.0`-`1.0`: how much color survives preparation. | `1.0` |
| `detail` | no | `0.0`-`1.0`: how much fine detail survives preparation. | `1.0` |
| `study` | no | `stack`, `"256"`, `"384"`, `"512"`, `"768"` | `stack` |
| `framing` | no | `stack`, `preserve aspect`, `center crop square`, `stretch square` | `stack` |
| `subject` | no | `recipe`, `avoid`, `allow`, `preserve` | `recipe` |
| `early`, `late` | no | `0.0`-`5.0`: per-phase landing multipliers. | `1.0` |
| `guard` | no | `true` applies the full text/logo blank-surface clamp to this card. | `false` |
| `cap` | no | `0.0`-`3.0`: hard ceiling on the strength slider. Omit for no cap. | none |
| `shape` | no | `0.0`-`3.0`: **the main transfer volume**. | role baseline |
| `global` | no | `0.0`-`4.0`: pooled overall-look pull - **inert on Krea 2**. | role baseline |
| `layers` | no | Exactly 12 numbers (`0.0`-`8.0`): per-band gains. | role table |
| `focus` | no | Up to 300 chars: **which aspect** the encoder studies. | none |

### Every field, fully defined

#### `label` - the recipe's identity (required)

The text that appears in `Use image for`, and the recipe's identity
everywhere: saved workflows store the label, the stack report prints it, and
sharing a workflow means sharing a recipe file whose label matches.

- Any non-empty text (surrounding whitespace is trimmed).
- It must not collide with a **reserved label**. Reserved means all of:
  - the built-in dropdown choices: `manual tuning`, `balanced`,
    `keep the same subject`, `copy pose and layout`,
    `copy lighting and mood`, `suggest the visual style`,
    `suggest material or texture`, `copy big shapes only`,
    `avoid copying text/logos`, `suggest the color palette`,
    `use the background/setting`, `copy the camera framing`,
    `mood board only`;
  - the built-ins' internal recipe keys (they resolve behind the dropdown,
    so they are reserved too): `identity`, `composition`, `lighting`,
    `style gentle`, `texture gentle`, `shape only`, `text/logo safe`,
    `palette only`, `environment`, `framing`, `mood board`;
  - any label already defined by an earlier-sorted recipe file - including
    the twenty shipped pack labels (the starter pack's `borrow the weather`,
    `borrow the clothing style`, `borrow drawing medium`,
    `borrow photo finish`, and `cinematic color grade`; the designer
    artwork pack's ten `borrow the .../style the ...` labels; and the
    edit-composite pack's five `match the .../use the .../carry the ...`
    labels).
- **Renaming a label orphans every workflow that used it** - the card falls
  back to `balanced` with a logged warning. Prefer adding a new recipe over
  renaming an old one.
- Naming hint: name the *job*, not the source image ("borrow the weather",
  not "storm photo") - the dropdown reads as a list of jobs.

#### `description` - notes for humans (default `""`)

Free text shown to people reading the file and by tooling; it is **never
sent to the model**, so it changes nothing about the render. Use it to state
the working strength range, the cap, and - honestly - what the recipe cannot
do (the shipped `borrow drawing medium` description is the model: it says
plainly that louder settings import the drawing's subject).

#### `role` - the highest-leverage word in the file (required)

`role` sets three things at once, which is why it is the first thing to
choose and the most impactful:

1. **The instruction sentence** the encoder receives for this card - the
   exact per-role text is in the table below. This is stage 2's main lever:
   it tells the encoder what the image is *for*.
2. **The `shape` / `global` baselines** used when you omit those fields.
3. **The default `layers` table** used when you omit `layers`.

It also selects the counter-example sentence used when the card is set to
`away from this image`, so a recipe designed for one job repels that same
job when flipped.

| `role` | The encoder is told to... | `shape` / `global` baseline | Default `layers` table |
| --- | --- | --- | --- |
| `balanced` | "use as general visual guidance" | 1.0 / 1.0 | even |
| `identity` | "preserve the main source subject, recognizable visual cues, product shape, object design, and proportions when relevant" | 1.0 / 1.0 | even |
| `style` | "borrow palette, tonal feel, medium, art direction, rendering finish, and atmosphere without copying the style reference subject" | 0.8 / 1.35 | style |
| `palette` | "borrow broad color palette, contrast, and tonal relationship only; avoid subject, layout, and texture copying" | 0.7 / 1.75 | palette |
| `composition` | "borrow pose, subject placement, spacing, camera angle, crop, and scene structure more than identity or surface style" | 1.25 / 0.35 | even |
| `framing` | "borrow camera distance, crop, lens feel, viewpoint, and framing only" | 0.9 / 0.25 | even |
| `environment` | "borrow background, location type, scene context, spatial atmosphere, and environmental cues without replacing the main subject" | 0.7 / 0.8 | style |
| `lighting` | "borrow lighting direction, contrast, mood, color cast, glow, and shadow behavior" | 0.8 / 1.25 | lighting |
| `material` | "borrow material feel, surface quality, finish, and tactile impression without copying exact grain, text, or tiny marks" | 1.0 / 1.2 | material |
| `loose` | "treat as loose mood-board inspiration only; avoid copying specific details unless the user asks" | 0.65 / 0.65 | style |
| `shape only` | "borrow broad silhouette, spacing, and geometric structure only; ignore color, texture, text, logos, and small details" | 1.2 / 0.05 | even |
| `text/logo safe` | "borrow only broad blank shape and layout; treat writing, logos, symbols, UI, and letter-like detail as empty surfaces that should not be reproduced" | 0.08 / 0.0 | flat 0.15 |

How to choose: match the **intent**, not the source image. Borrowing a
photo's color grade is a `palette` job even if the photo is a portrait.
When two roles could fit, pick the one whose instruction sentence names what
you want and *disclaims* what you fear (`style` explicitly disclaims the
subject; `environment` explicitly keeps yours).

Two things `role` does **not** do: it does not touch the image preparation
(a `palette` role with `treatment: normal` still shows the encoder the full,
un-washed image - the role only *asks* politely), and its baselines fill in
only the fields you omit - anything you set wins.

#### `treatment` - what the encoder can possibly see (default `normal`)

The physical re-draw of the reference before study. Preparation runs in a
fixed order - framing, then `color`, then `treatment`, then `detail` - and
this is the only **guaranteed** control in the whole schema: information the
treatment destroys is gone before the encoder looks.

| Value | Exact pixel effect | What survives | Use it to borrow |
| --- | --- | --- | --- |
| `normal` | unchanged | everything | the actual subject (identity/content jobs) |
| `grayscale` | color fully removed (forces `color` to `0.0`) | structure, detail, tone | layout or tone where the source's palette must stay out |
| `soft blur` | gentle blur (kernel 5) | forms, most detail, color | softening tiny marks and micro-texture only |
| `strong blur` | heavy blur (kernel 13) | broad forms, color masses, light | style/medium/light mood - **with** a de-selecting `focus` and a `cap` (the shipped style and lighting recipes' pattern) |
| `palette wash` | the image becomes a smooth coarse color-field grid (2-10 cells per side, ~1 cell per 48 px), blended 85/15 with the image's average color, then blurred (kernel 9) | color relationships only - **no shapes at all** | palette, grade, color mood; the structure-safe choice |
| `color wash` | very heavy blur (kernel 31) | soft color fields, faint massing | broad color atmosphere when palette wash feels too abstract |
| `grayscale blur` | grayscale + heavy blur (kernel 13; forces `color` to `0.0`) | arrangement and massing, no color | layout / pose / camera placement without recoloring |
| `shape wash` | grayscale + very heavy blur (kernel 25; forces `color` to `0.0`) | only the biggest masses | silhouette; also the guard's clamped treatment |

How the choice plays out:

- **`palette wash` is the only treatment that guarantees zero subject
  leak** - the shapes are gone before encoding. All four shipped
  palette-family recipes (palette, environment, mood board, cinematic
  grade) use it for exactly that reason.
- **`soft blur` and `strong blur` preserve structure, and that is a cliff,
  not a dial.** At working strengths the source's forms can appear in your
  render or reshape your subject (pre-retune, an environment reference
  literally morphed a bowl into a jar). The shipped style/lighting recipes
  make strong blur safe with the full pattern: blur + a `focus` that
  de-selects the subject, layout, *and the blur itself* + a `cap`. Copy the
  whole pattern, not just the blur.
- **The treatment's own look can transfer.** The encoder studies whatever
  it is shown - including preparation artifacts. A blur can be studied as
  "soft focus style" (fixed in the shipped style recipe by the anti-blur
  focus); a flat-gray shape wash can drain your render toward monochrome
  (fixed in the shipped shape recipe by a structure-heavy `layers` table).
  If a render shows a quality the *reference does not have*, suspect the
  prep first, and check the `prepared_references` preview.
- The three grayscale-family treatments (`grayscale`, `grayscale blur`,
  `shape wash`) force `color` to `0.0` regardless of what you set.

#### `color` - how much color survives (0.0-1.0, default 1.0)

A blend toward grayscale applied **before** the treatment: `1.0` keeps the
original colors, `0.0` is fully gray, values between are a partial
desaturation.

| Value | Effect |
| --- | --- |
| `1.0` | full color - palette-borrowing recipes want this |
| `0.8`-`0.9` | slightly muted; a small safety margin against oversaturated sources (the shipped template uses `0.9`) |
| `0.3`-`0.7` | strongly muted palette - the borrow arrives as tinted tone rather than full color |
| `0.0` | no color at all - the card can only carry structure and tone |

Interactions: `grayscale`, `grayscale blur`, and `shape wash` force it to
`0.0` (setting it there changes nothing); `palette wash` and `color wash`
respect it, so `palette wash` + `color: 0.5` borrows a *muted version* of
the reference palette. If your borrowed colors land too loud, lowering
`color` is a gentler first move than lowering `shape`.

#### `detail` - how much fine structure survives (0.0-1.0, default 1.0)

A blend with a heavily blurred copy applied **after** the treatment: `1.0`
keeps the treated image untouched, `0.0` replaces it with the fully
softened copy, values between interpolate. Think of it as the fine-trim on
top of the treatment's coarse guarantee.

| Value | Effect | Shipped anchors |
| --- | --- | --- |
| `0.0` | nothing fine survives | palette (`0.0`), shape only (`0.0`), the guard (`0.0`) |
| `0.1`-`0.35` | broad masses and light only - the appearance band | weather (`0.15`), lighting (`0.15`), photo finish (`0.2`), style (`0.3`), material (`0.35`) |
| `0.4`-`0.7` | recognizable objects survive softened | drawing medium (`0.45`), clothing style (`0.7`) |
| `1.0` | everything survives | balanced, keep the same subject |

This is the first dial to lower when the `prepared_references` preview
still shows something you meant to strip - and one render-tested warning in
the other direction: raising `detail` (with a finer `study`) on a
structure-preserving treatment re-opens subject takeover. During the 2026-07
retune, a strong-blur recipe pushed to `study: "512"` + `detail: 0.6`
stopped borrowing and replaced the prompt's subject outright.

#### `study` - how closely the encoder looks (default `stack`)

The resolution the prepared reference is scaled to before study (the side
length; with the default framing the image keeps its proportions at the
equivalent pixel area). Write it quoted in YAML (`study: "384"`) - a bare
number is also accepted and converted, but quoting matches every shipped
file.

| Value | Meaning | Effect on the recipe |
| --- | --- | --- |
| `stack` | defer to the stack's `Image detail level` widget (default `medium - balanced default (384)`) | the user controls it per graph; right for general-purpose recipes like `balanced` |
| `"256"` | loose idea | the appearance sweet spot: **coarser studies land at lower strengths**, and detail that could leak never reaches the encoder. Nearly every shipped appearance recipe studies at 256 |
| `"384"` | balanced default | enough detail for semantic `focus` work (the clothing and style recipes use it - a garment must still be recognizable to be studied) |
| `"512"` | more exact | more faithful borrowing, **needs higher strength before anything shows**, and more copy risk on structure-preserving treatments |
| `"768"` | most exact | identity-grade exactness; reserve for subject-preserving jobs |

Rule of thumb: pick the *coarsest* study that still contains your signal. A
palette does not need 512 pixels; a specific garment does need ~384. If a
recipe seems silent, coarsening the study one step is as effective as
raising `shape` half a step - and safer.

#### `framing` - what happens to the aspect ratio (default `stack`)

How the reference is fitted to the study size, before everything else:

| Value | Exact behavior | Use when |
| --- | --- | --- |
| `stack` | defer to the stack's `Image framing` widget (default `keep full image shape`) | almost always - the default for every shipped recipe except one |
| `preserve aspect` | scale to the study area keeping the original proportions | **the frame itself is the signal.** The built-in `copy the camera framing` recipe pins this so a stack-level square override can never destroy the crop information it exists to borrow |
| `center crop square` | largest centered square, edges discarded, then scaled | the borrowable content is central and the edges are noise - but check the preview: the crop happily discards the very thing you meant to study |
| `stretch square` | force to a square, distorting proportions | rarely right; harmless only when geometry is destroyed anyway (a palette wash does not care about proportions) |

#### `subject` - the subject rule (default `recipe`)

Adds one sentence to the card's instructions telling the encoder what to do
with the reference's subject. The exact sentences:

| Value | The encoder is told... | Use for |
| --- | --- | --- |
| `recipe` | *(no extra sentence - the role's own language governs)* | when the role already says it (`identity` preserves, `style` disclaims) |
| `avoid` | "Do not copy this reference image's subject identity, face, product identity, outfit, or object design." | **every look-borrowing recipe.** All ten shipped non-identity recipes set it |
| `allow` | "This reference may influence subject details only when that helps the user's requested result." | deliberately permissive mood-board-style cards |
| `preserve` | "Preserve this reference image's main subject or product identity as an important content source." | identity/content jobs only |

Two rules to remember:

- This is stage 2 - an *instruction*, not a guarantee. `subject: avoid`
  with `treatment: normal` at high strength can still copy the subject;
  the guarantee lives in the treatment. Set both.
- It is overridden in two cases: a card set to `away from this image`
  always behaves as `avoid` (a counter-example never imports its subject),
  and `guard: true` forces `avoid`.

#### `focus` - study one named aspect (up to 300 chars, default none)

The numeric fields select *visual channels* (color vs structure); they
cannot separate a dress from the person wearing it. `focus` is the semantic
scalpel: free text inserted verbatim into the encoder's instructions as

> "study only **your text** from this image; ignore everything else about
> it."

so write the text to fit that sentence - an aspect description, not a
command ("the clothing and garment style worn by the person, not the
person's identity, face, or the background").

```yaml
label: borrow the clothing style
role: balanced
treatment: normal
detail: 0.7
study: "384"
subject: avoid
cap: 1.1
shape: 0.8
focus: the clothing and garment style worn by the person, not the person's identity, face, or the background
```

What the render tests showed (same reference, same seed, only the focus
text changed):

- **Selecting works** - the clothing-focused recipe kept the reference's
  red raincoat and picked up garment details the unfocused run missed.
- **De-selecting is the power move** - focusing the same photo on "the
  background environment only, *not the person or their clothing*" removed
  the red coat entirely. Name what to skip and it stays behind.
- **De-selection also fixes prep artifacts.** Two built-ins ship focuses
  for exactly this, and their focus lines appearing on the stack report is
  expected: `suggest the visual style` de-selects "the image's blurriness
  or soft focus" so its own deliberate reference-softening is not studied
  as the style, and `copy lighting and mood` de-selects "the place,
  objects, or scene layout" so a dramatic sky's mood arrives without the
  reference's location taking over. Copy the pattern if your
  heavy-treatment recipe starts echoing its treatment in renders.
- **Know its limits** - scene-wide moods (weather, seasons, time of day)
  mostly ride the image itself at working strengths; use treatment +
  strength for those (that is exactly what `borrow the weather` does) and
  save `focus` for object-bound aspects: clothing, props, hairstyles,
  furniture, vehicles.
- **The wording is load-bearing - render-test any change.** During the
  2026-07 retune, dropping one de-selection clause from the style focus
  fixed one problem and silently broke a different use of the same recipe.
  Treat focus text like code.

Mechanics and interplay, exactly:

- Whitespace is collapsed, so YAML folded blocks (`focus: >-`) are fine;
  more than 300 characters rejects the recipe. Keep it one aspect - a
  paragraph of wishes dilutes the study.
- `focus` biases what the encoder studies; it does **not** replace the
  treatment guarantees. Keep `subject: avoid` and a job-appropriate
  treatment.
- On an `away from this image` card the focus *scopes the repulsion*: the
  instruction becomes "only **your text** from this image; its other
  aspects do not apply" - so a focused away card repels one aspect instead
  of the whole look.
- On a text/logo-safe (guarded) card the guard's blank-panel instruction
  replaces the role and focus lines entirely.
- The stack report prints each card's focus, so you can always confirm it
  reached the encoder.

#### `early` and `late` - when the card guides (0.0-5.0 each, default 1.0)

Per-phase multipliers on the card's landing. With the stack's timing on
`smart per-card timing` (the default) or `layout early, details later`, the
run is split at the stack's `Early-to-final handoff` (default `0.40`): the
**early** phase covers the first 40% of sampling steps - where composition
and placement commit - and the **late** phase the rest, where surface and
finish land. Each phase multiplies the card's strength by its value.

| Value | Effect on that phase |
| --- | --- |
| `0.0` | the card is completely silent in that phase |
| `0.5`-`0.9` | present but soft |
| `1.0` | neutral - full card strength |
| above `1.0` | amplified (the shipped structure recipes use up to `1.2`; the range allows `5.0` but there is rarely a reason to go past ~`1.3`) |

The shipped patterns, and why:

- **Structure jobs: early high, late low.** Composition `1.2 / 0.2`,
  framing `1.2 / 0.15`, shape only `1.1 / 0.0` - they compose the image,
  then get out of the way so they cannot stiffen the finish.
- **Finish jobs: late-leaning.** Material `0.35 / 0.9`, photo finish
  `0.85 / 0.7` - the source arrives in the detail passes on the prompt's
  own layout.
- **Appearance all-rounders: balanced and slightly soft.** Style
  `0.85 / 0.85`, palette `0.9 / 0.9`.

Two facts that stop guesswork:

- **These fields are inert when the stack timing is `guide the whole
  image`** (single-phase). An early/late experiment under that setting
  silently tests nothing.
- The card's `When this card guides` widget **overrides** them: `whole
  image` forces `1.0 / 1.0`, `early layout only` keeps your early value
  and zeroes late, `final details only` zeroes early and keeps your late
  value, and `recipe decides` uses your values as written.
- One render-verified subtlety: color commits in the first steps, so even
  an early-only card leaves its palette behind. What early/late really
  choose is whether the source also guides *composition* (early) or lands
  as *finish detail* on the prompt's layout (late).

#### `guard` - the text/logo clamp (default `false`)

`guard: true` turns the card into a text/logo-safety card, identical to the
built-in `avoid copying text/logos`. The clamp is applied **last**, after
every other field, the timing widget, and the manual dials - so nothing can
re-open what it closes:

| Setting | Clamped to |
| --- | --- |
| `treatment` | `shape wash` |
| `color` | `0.0` |
| `detail` | `0.0` |
| `study` | `"256"` |
| `early` | `min(early, 0.75)` |
| `late` | `0.0` |
| `subject` | `avoid` |
| `cap` | `0.03` |
| `shape` | `min(shape, 0.08)` |
| `global` | `0.0` |
| every `layers` gain | `min(gain, 0.15)` |

A guarded card also enrolls the whole stack in the blank-surface prompt
handling (the same machinery as the built-in guard, including the
marking-word prompt rewriter when the stack's guard mode is full). Use it
**only** for text/logo-safety recipes - pair it with `role: text/logo safe`
- and leave it `false` everywhere else: it is a safety clamp, not a
"be gentle" switch (that is what `cap` is for).

#### `cap` - the intent ceiling (0.0-3.0, or omit; default none)

A hard ceiling on the strength slider, applied at the card **before** the
slider-feel curve: the card's strength becomes `min(slider, cap)`. Sliding
past the cap does nothing, and the stack report says so on the card's line
(`requested 0.90 -> capped at 0.65`).

Why it exists: a recipe encodes an intent, and the cap is where "too much"
begins for that intent. A whisper recipe without a cap is one slider bump
away from not being a whisper.

| Cap | Shipped anchors |
| --- | --- |
| `0.03` | the guard (a nudge is all it needs) |
| `0.55`-`0.65` | quiet-by-design recipes: drawing medium (`0.55`), style / material / photo finish (`0.65`) |
| `0.9`-`1.2` | the appearance family's "strong but not destructive" band: palette / mood board (`0.9`), weather / clothing (`1.1`), environment / framing / cinematic grade (`1.2`) |
| `1.25` | structure recipes (composition, lighting) |
| *omit* | anchor jobs that should follow the slider all the way (`balanced`, `keep the same subject`) |

How to set it: render at `0.4` / `0.65` / `0.9` on a fixed seed and place
the cap where the result stops improving and starts distorting. Edge case
worth knowing: `cap: 0.0` silences the card permanently (it is skipped as
"strength 0 - costs nothing") - omit the field instead if you want no
ceiling.

#### `shape` - the volume knob (0.0-3.0, default: role baseline)

The single most important number in the file. It scales the token-path
conditioning - on Krea 2, the **only** live channel - so together with the
slider it decides how much of whatever the treatment let through actually
arrives. Fact 2's bands are the map; anchors from the shipped set:

| Job | `shape` | Why |
| --- | --- | --- |
| loose vibes | `0.65` (mood board) | deliberately under the working band - a whisper even at high slider |
| appearance borrow | `0.7`-`0.85` (palette `0.7`, weather `0.75`, style `0.85`) | clear borrow by strength ~`0.65` with a structure-destroying treatment |
| material role, default table | `1.0` (the role baseline) | the classic material family table has the mildest deep-band spikes, so it needs more volume; the shipped material recipe instead pairs a hotter finish table with `shape 0.8` |
| camera/framing | `0.95` | structure-adjacent but deliberately under the structure band |
| identity/content | `1.0` | native-strength anchor |
| layout/silhouette | `1.2`-`1.3` (shape only `1.2`, composition `1.3`) | structure transfer needs to push past native |

Interactions to keep straight: `shape` multiplies against the slider, the
phase multipliers, and each `layers` gain (the arithmetic, with a worked
example, is under [Deriving the `layers` array](#deriving-the-layers-array))
- so it sets the floor for everything. Below `~0.5` no layer table, focus,
or slider setting will make the card visible; that is the single most
common cause of "my recipe does nothing". And raising `shape` raises
*everything* the treatment let through - if raising it starts leaking
structure, the fix is a harder `treatment` (or lower `detail`), not more
`shape`.

#### `global` - inert on Krea 2 (0.0-4.0, default: role baseline)

On models whose text encoder emits a pooled summary vector, `global` would
scale a whole-image "overall look" pull alongside the per-token channel.
**Krea 2's text encoder produces no pooled output, so this field does
nothing on Krea 2** - the stack only applies the pooled delta when the
encoder emits one. It is not deprecated; it is kept so recipe files stay
portable to models that do have the channel.

Practical rules: set it from the role baseline (or copy a shipped recipe)
and forget it; never diagnose or fix a weak recipe with it - on this model
that knob is not connected to anything. Any value costs nothing either way.

#### `layers` - the 12 band gains (exactly 12 numbers, 0.0-8.0; default: role table)

Per-band fine-tuning gains over the 12 conditioning bands (position `0`
shallowest to `11` deepest; shallow bands lean structure, deep bands lean
appearance). This is the *polish* knob - second-order by design - and the
only field whose values should be derived rather than hand-picked, so it
has its own section:
[Deriving the `layers` array](#deriving-the-layers-array) below, including
what each position does, the family tables, the exact landing math, and a
worked example. Omit the field to use your role's table - the right default
unless you are deliberately fine-tuning.

### The starter pack: five worked examples

Five ready-made recipes ship **enabled** in
[custom_recipes/starter-pack.yaml](../custom_recipes/starter-pack.yaml) -
each one a render-validated example of a pattern from this section, and the
best starting point for a recipe of the same shape. Delete or underscore the
file to remove them from your dropdown;
[krea-v10-starter-recipe-workflow.json](../example_workflows/krea-v10-starter-recipe-workflow.json)
runs one of them out of the box.

| Recipe | The pattern it demonstrates | Start at |
| --- | --- | --- |
| `borrow the weather` | scene-wide mood via treatment + strength (strong blur, `detail: 0.15`), not via focus | `0.7`, full drama `0.85`, cap `1.1` |
| `borrow the clothing style` | semantic separation via `focus` (normal treatment, `detail: 0.7` so the garment stays studyable) | `0.75`, cap `1.1` |
| `borrow drawing medium` | the honest whisper: a quiet cap (`0.55`) plus a description that states the ceiling - louder settings import the drawing's subject | `0.5`, cap `0.55` |
| `borrow photo finish` | the full strong-blur pattern: blur + de-selecting focus + finish-heavy custom `layers` + cap | `0.55`-`0.6`, cap `0.65` |
| `cinematic color grade` | a bolder sibling of a built-in: same palette-wash safety, higher cap so it can push harder when asked | `0.6`, cap `1.2` |

### The designer and edit packs: fifteen more, same rules

Two more packs ship enabled alongside the starter pack, built the same way
(every recipe render-validated on Krea 2, every description stating its
working strength and its honest limits):

- [designer-artwork-pack.yaml](../custom_recipes/designer-artwork-pack.yaml) -
  ten recipes for working from artwork references: `borrow the poster style`,
  `borrow the soft media look`, `borrow the pattern energy`, `borrow the era
  print look`, `borrow the paper and canvas`, `borrow the metallic accents`,
  `borrow the ornament borders`, `borrow the stained glass look`, and the
  style-timing pair `style the finish only` / `style the layout first`.
- [edit-composite-pack.yaml](../custom_recipes/edit-composite-pack.yaml) -
  five recipes for editing and compositing: `match the scene light`,
  `match the monochrome look`, `match the atmosphere`, `use the background
  only`, and `carry the subject over`.

Each recipe's dropdown description is its usage guide: the strength to start
at, which references work best (full-bleed artwork for the style family,
scene plates for the light matchers, clean product shots for subject
carrying), and what to expect when a reference fights the recipe. Delete or
underscore either file to remove its labels from the dropdown.

To see every one of these recipes in action - reference, prompt-only
baseline, and result side by side - open the
[recipe visual guide](recipe-visual-guide.md), which shows all twelve
built-ins and all twenty bundled recipes at their documented starting
strengths.

### A complete example, annotated

The shipped template
([_example-vintage-postcard.yaml](../custom_recipes/_example-vintage-postcard.yaml)),
with the reason for every line:

```yaml
label: vintage postcard style          # the dropdown text (no collisions)
description: Warm faded palette and a soft print finish, without copying the source subject.
role: style                            # style instruction language + style-family defaults
treatment: palette wash                # guarantee: source shapes destroyed before study
color: 0.9                             # keep the palette, shave oversaturation slightly
detail: 0.0                            # nothing fine survives (palette wash leaves little anyway)
study: "256"                           # coarse study - appearance lands at lower strengths
framing: stack                         # aspect handling is not this recipe's signal
subject: avoid                         # instruction-channel backup to the treatment guarantee
early: 0.85                            # slightly soft in the layout phase...
late: 0.9                              # ...and in the finish phase - a gentle recipe throughout
guard: false                           # not a text/logo-safety card
cap: 0.85                              # "too much" begins here - the slider stops mattering
shape: 0.75                            # appearance working band (0.7-1.0)
global: 1.7                            # inert on Krea 2; kept for portability
layers: [0.25, 0.35, 0.45, 0.6, 0.8, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.2]   # the style family table, written out
```

The same recipe as JSON is the same mapping with JSON syntax - both formats
are equivalent.

### Deriving the `layers` array

`layers` is the only field without an obvious hand-set value. The 12
positions are Krea 2's 12 text-encoder layer taps (position 0 shallowest,
11 deepest). The built-in tables follow a *design intent* - shallow bands
(`0`-`4`) carry structure and are turned down for look-borrowing; `5`-`6`
transition; deep bands carry appearance, spiked at `8` (strongest), `10`,
then `7`, with `9` and `11` mild. The card's manual
`Structure layers pull` / `Finish layers pull` dials scale positions `0`-`5`
and `6`-`11` of this same table - a custom array is those two dials with
per-position control.

**The landing math, exactly.** Per band, the applied scale is:

```text
scale = clamp( slider-after-cap-and-feel-curve x phase (early/late) x shape x layers[band],  -6 .. +6 )
```

where `1.0` means "the image's native influence", below `1.0` mutes toward
prompt-only, above amplifies, and negative (an `away` card) repels. Worked
example - the vintage postcard recipe above at slider `0.65`, on the
default `artist friendly` slider feel and `smart per-card timing`:

1. cap `0.85`: `0.65` passes unchanged;
2. feel curve: `0.65^1.6 = 0.50`;
3. early phase: `0.50 x 0.85 = 0.43`; times `shape 0.75` = **`0.32`**;
4. band `8` (gain `5.0`): `0.32 x 5.0 = 1.60` - the appearance band speaks
   at 60% past native;
5. band `0` (gain `0.25`): `0.32 x 0.25 = 0.08` - structure is nearly
   muted to prompt-only.

That is the whole trick of a look-borrowing table: one number (`0.32`) is
split into loud appearance and near-silent structure. And it shows why
`shape` sets the floor: the same table on a `shape 0.1` card lands band `8`
at `0.21` - invisible - no matter the gains. Layer tuning is the *polish*
step; outcome-level changes come from `treatment` and `shape`. (For
completeness, the slider-feel curves: `artist friendly` is `s^1.6` (zero
below `0.01`, `1 + (s-1) x 1.15` above `1.0`); `extra gentle` is `s^2.7`
(zero below `0.02`, `1 + (s-1) x 1.1` above `1.0`); `literal slider values`
passes through.)

To derive your own array: start from the closest family table, scale the
front half (`0`-`5`) by how much structure should arrive (`x0.3` to
suppress hard, `x1.2`-`x1.5` for structure jobs), scale the back half
(`6`-`11`) by finish emphasis, keep the spike ordering (`8` > `10` > `7`),
and stay within `0.0`-`8.0`.

Know the three V10-only tables before copying from a built-in: the shipped
style, material, and shape recipes override their roles' classic tables
(with a hotter *style-transfer* table, a *material-finish* table, and a
*structure-only* table `[1.3 x 6, 0.25 x 6]` respectively). The last one is
a worked lesson in when layers are the right fix: the shape recipe's
flat-gray study was draining renders to monochrome through the deep
appearance bands, a `focus` could not override an image-channel signal that
dominant, and re-weighting *where the pull lands* (structure bands `x1.3`,
appearance bands `x0.25`) delivered silhouette influence with
prompt-natural color. When the leak is the encoder's *description* of the
study, fix it with `focus`; when the leak *is* the dominant image signal,
fix it with `layers` or the treatment.

The family tables, the full band map, a copy-paste derivation snippet, a
render-validated worked example, and a two-minute render-testing protocol
live in
[custom_recipes/README.md](../custom_recipes/README.md#the-layers-array-exactly);
the shipped values for every built-in are in the
[V10 technical paper, section 8](krea-v10-technical-paper.md#8-recipes).
The full determination - what the 12 taps are (verified from the model),
where the specific numbers came from, and how the retuned values were
measured - is documented in [docs/deepstack-layers/](deepstack-layers/README.md).

### How validation behaves

Every file is validated on load, strictly about keys and values, forgivingly
about omissions:

- **Unknown keys reject the recipe** with a named error (say, `colour`), so
  typos cannot silently become no-ops.
- **Missing `label` or `role` rejects it**; everything else has a
  role-derived default.
- **Out-of-range or mistyped values reject it, by name**: a number outside
  its documented range, a `true`/`false` where a number belongs (and vice
  versa for `guard`), a `treatment`/`study`/`framing`/`subject` value not
  in its list, a `layers` list that is not exactly 12 numbers in
  `0.0`-`8.0`, a `focus` over 300 characters, or a label collision.
- **The node always loads.** Invalid recipes are skipped with a warning in
  the ComfyUI log naming the file and the reason; your other recipes and
  the built-ins are unaffected. A file that cannot be parsed at all is
  skipped the same way.
- **First definition wins.** Files scan in sorted name order; a duplicate
  label in a later file is skipped with a collision warning.

Custom recipes compose with every other V10 control: `Guide direction`,
`When this card guides`, and the strength slider all apply on top, the stack
report names your recipe on its card line, and a `guard: true` recipe is
clamped exactly like the built-in text/logo guard.

### Recipe design tips

- Start from the closest shipped recipe: the starter pack above, or a
  built-in's values from the
  [V10 technical paper's recipe tables](krea-v10-technical-paper.md#8-recipes)
  - then move **one field at a time**, and re-render after each move.
- Set the guarantee first (`treatment`), the volume second (`shape`), the
  ceiling third (`cap`). Everything else is refinement.
- Keep `subject: avoid` on every look-borrowing recipe, even when the
  treatment already guarantees safety - instructions and guarantees back
  each other up.
- Give whisper-jobs a `cap` so a slider bump cannot blow past their intent,
  and state the working range in the `description`.
- Appearance recipes land best with a coarse study (`study: "256"`) - finer
  studies raise the strength needed before anything shows.
- Test with the `prepared_references` preview: if the treated frame still
  shows what you meant to strip, strengthen `treatment` or lower `detail`.
- When torn between two values, pick the quieter one and say so in the
  description - users can raise a slider; they cannot un-leak a render.
- **Validate by rendering, always.** Fix a seed, render your recipe at
  strengths `0.4` / `0.65` / `0.9`, and check three things: not silent at
  `0.9`? (raise `shape` or coarsen `study`); source not leaking in?
  (harden `treatment`, lower `detail`); the three strengths read quiet /
  clear / strong? (set `cap` where "too much" begins). Numbers that were
  never rendered are guesses.

### Sharing recipes and saved workflows

Saved workflows reference custom recipes **by label**. If you share a
workflow that uses one, ship the recipe file with it; without the file the
card falls back to `balanced` with a logged warning. Renaming a label
orphans existing workflows the same way - prefer adding a new recipe over
renaming an old one.

## Guide Direction: Counter-Examples

`Guide direction` is the biggest new idea in V10. Every card still gets a job;
now it also gets a direction:

- `toward this image` - exact V9 behavior: the reference pulls the result
  toward its look.
- `away from this image` - the card becomes a **counter-example**: the stack
  isolates what this image contributes and re-adds it negatively, steering the
  result away from whatever aspect the card's job selects.

The job picks *what* to repel:

| Combination | Meaning |
| --- | --- |
| `away` + `suggest the visual style` | Not this style. |
| `away` + `suggest the color palette` | Not this palette. |
| `away` + `copy pose and layout` | Not this composition. |
| `away` + `keep the same subject` | Keep this subject out entirely. |

### The direction journey

The three steps below show exactly what an away card negates. Same prompt,
same seed (`972106`); the only change is the style card and its direction:

| Step 1: prompt only | Step 2: style toward `0.65` | Step 3: style away `0.40` |
| --- | --- | --- |
| <img src="assets/krea-v10/demos/counter-example-baseline.png" alt="Direction journey prompt-only baseline" width="240"> | <img src="assets/krea-v10/demos/counter-example-toward.png" alt="Direction journey with style pulled toward" width="240"> | <img src="assets/krea-v10/demos/counter-example-away.png" alt="Direction journey with style pushed away" width="240"> |

| Setting | Value |
| --- | --- |
| Style source | <img src="../example_assets/krea-reference-examples/slot2_style_reference.png" alt="Style source image" width="180"> |
| Prompt (all steps) | `a sculptural table lamp in a clean studio product photo, no readable text` |
| Step 2 card | `suggest the visual style`, `toward this image`, strength `0.65` |
| Step 3 card | `suggest the visual style`, `away from this image`, strength `0.40` |
| Demo files | [step 1](assets/krea-v10/demos/counter-example-baseline.png), [step 2](assets/krea-v10/demos/counter-example-toward.png), [step 3](assets/krea-v10/demos/counter-example-away.png) + `.workflow.json` beside each |

Pulled toward, the source's pastel palette takes over the lamp - a rose
shade, a sage base, a rounder and softer art direction.
Pushed away, the same card scrubs the result in the opposite direction - the
lamp comes out plainer and warmer-neutral than even the prompt-only baseline,
because the stack is actively steering out of the source's palette and
manner. Away pushes harder per slider unit than toward (it extrapolates past
removal), which is why step 3 runs at `0.40` and the rules below say start
low.

Rules of thumb:

- Start low: `0.10` to `0.30`. Repulsion gets strange faster than attraction.
- Always pair an away card with a written prompt or a toward card that says
  what you *do* want; pure repulsion with no positive signal wanders.
- A counter-example card always avoids subject copying, whatever
  `Subject copying` says.
- The stack report marks away cards and prints their negative targets.

## Per-Card Timing

V9 timing was a stack-level choice plus recipe-baked early/late behavior. V10
adds `When this card guides` on every card:

| Choice | Behavior |
| --- | --- |
| `recipe decides` | Keep the recipe or manual early/late behavior (V9 default). |
| `whole image` | Guide both phases at full card strength. |
| `early layout only` | Keep the card's early behavior; remove its influence in the final phase. |
| `final details only` | Remove the card's influence early; keep its late behavior. |

Typical uses: a framing or layout card set to `early layout only` composes the
image and then gets out of the way; a material card set to
`final details only` touches only the finish. The text/logo guard still clamps
last - a guarded card never regains late-phase influence.

### The timing journey

Same style card, same seed (`972105`), same prompt - the only change is
`When this card guides`:

| `early layout only` | `final details only` |
| --- | --- |
| <img src="assets/krea-v10/demos/timing-style-early-only.png" alt="Timing journey early layout only" width="300"> | <img src="assets/krea-v10/demos/timing-style-final-only.png" alt="Timing journey final details only" width="300"> |

| Setting | Value |
| --- | --- |
| Style source | <img src="../example_assets/krea-reference-examples/slot2_style_reference.png" alt="Style source image" width="180"> |
| Card | `suggest the visual style`, strength `0.75` |
| Prompt (both) | `a modern table lamp in a clean studio product photo, no readable text` |
| Demo files | [early-only PNG](assets/krea-v10/demos/timing-style-early-only.png), [final-only PNG](assets/krea-v10/demos/timing-style-final-only.png) + `.workflow.json` beside each |

Both timings deliver the borrowed palette - color commits in the first
sampling steps, so even an early-only card leaves color behind. What the
widget really moves is *how* the look lands: early-only lets the source
guide the composition and broad color fields, then the prompt's own finish
passes smooth the surfaces - the shade comes out a classic soft-graded cone.
Final-only is the mirror image: the prompt owns the early composition and
the source arrives in the detail passes, landing its rose-and-sage palette
as a crisp two-tone finish on the prompt's lamp. One widget, two clearly
different pictures.

## Manual Layer Dials

In `manual tuning` mode only, two new dials scale the per-layer conditioning
gains in plain language:

- `Structure layers pull` - the early conditioning bands that carry layout and
  subject structure.
- `Finish layers pull` - the late bands that carry palette, texture, and
  rendering finish.

Lower structure and raise finish for a style card that keeps dragging the
subject along; do the opposite for a layout card that keeps recoloring things.
Quick recipes ignore both dials (their tables are already tuned), and the web
extension greys them out outside manual mode.

## Balance Strong Cards

Several simultaneously strong cards blend less faithfully than the same cards
used separately - they fight. `Balance strong cards` puts a budget on the
stack's total pull per timing phase and softly scales every card down when the
stack exceeds it:

| Choice | Budget | Use when |
| --- | --- | --- |
| `off - use my values` | none | Exact V9 behavior. The default. |
| `gentle balance` | `2.5` | Four or more active cards, or two or three aggressive ones. Rarely intervenes otherwise. |
| `strict balance` | `1.5` | Conservative blends where fidelity beats punch. |

The written prompt is never balanced - only image cards are scaled - and the
stack report states the applied scale whenever balancing intervenes.

The six-card showcase, rendered both ways on the same seed:

| Balance `off - use my values` | `gentle balance` |
| --- | --- |
| <img src="assets/krea-v10/demos/full-showcase.png" alt="Showcase with balance off" width="300"> | <img src="assets/krea-v10/demos/full-showcase-balanced.png" alt="Showcase with gentle balance" width="300"> |

With six active cards the gentle budget trims the loudest pulls: the balanced
render keeps the same mug-on-desk composition while the ensemble blends a
touch more evenly (the balanced mug comes out slightly lighter, with a
simpler lid and softer shadows). With
stacks this size the difference is deliberately subtle - balance is a
graceful-degradation guard, not a look control.

## Reuse Image Studies

The expensive part of every run is the encoder passes that study each image in
context. Those studies depend only on the prompt and the prepared images -
never on strengths, direction, timing, or balance. `Reuse image studies`
caches them:

- `reuse between runs - faster tuning` (default): re-runs that change only
  strengths, direction, timing, handoff, or balance reuse every study and skip
  all encoder passes. The report's `Studies:` line shows exactly what was
  reused.
- `always re-study`: exact V9 behavior; every run pays full encode cost.

The cache keys on image and prompt *content*, so editing an image or the
prompt re-studies automatically - stale reuse cannot happen. The one caveat:
reuse assumes the connected CLIP is unchanged between runs. Pick
`always re-study` while hot-swapping CLIP patches or LoRA hooks.

The tuning ritual this enables: queue once, read the report, then tweak one
strength at a time and re-queue - each re-run is nearly free.

## Reading The Stack Report

Wire `stack_report` into a `Preview Any` node. A typical report:

```text
KG Krea 2 Reference Stack Encoder V10 - stack report
Prompt: "a ceramic travel mug on a wooden desk in a bright studio" at strength 1.15.
Timing: smart per-card timing. with early-to-final handoff at 0.40.
Balance: gentle balance - cards were within budget, nothing scaled.
Studies: 7 encoder passes this run; studies cached for faster strength tuning.

Card 1 (keep the same subject): requested 0.80 -> guiding at 0.70 after the slider feel curve. Targets: early shape 0.70x / look 0.70x, final shape 0.70x / look 0.70x.
Card 6 (avoid copying text/logos): requested 0.03 -> capped at 0.03 by the text/logo guard. ...
```

What to look for:

| Line | Tells you |
| --- | --- |
| `requested X -> guiding at Y` | The slider feel curve's effect. If a card feels dead at `0.05`, this line shows why. |
| `capped at X by ...` | A recipe cap or the text/logo guard clamped the card. Raising the slider further does nothing. |
| `Balance: ... scaled strong cards to X` | The stack intervened; your relative card ratios were kept, total pull was reduced. |
| `Studies: N encoder passes ... reused M` | The run's real cost and what the cache saved. |
| `Skipped without cost: ...` | Cards that contributed nothing (no image, or strength 0) and why. |

## The Prepared-References Preview

Wire `prepared_references` into a `Preview Image` node. It shows one frame per
active card: exactly what the vision encoder studied after framing, washes,
color reduction, and detail reduction.

This makes the invisible visible. If a style card's frame still shows a
recognizable subject, the subject can leak - lower `Small details kept`, pick
a stronger `Prepare image by` treatment, or reduce the study resolution. If a
palette card's frame is nothing but soft color blocks, it is doing its job.

## Multi-Reference Recipes

| Scenario | Setup |
| --- | --- |
| Product in a place | `keep the same subject` for the product, `use the background/setting` for the location, `suggest the color palette` for grade. Turn on `gentle balance`. |
| Composed shot, free contents | `copy the camera framing` at `early layout only`, then style/material cards for the finish. |
| "Anything but that" | Normal toward cards for what you want, plus one `away` card holding the look to avoid at `0.15` to `0.25`. |
| Fast strength search | Any stack with `reuse between runs`; queue, read the report, tweak one card, repeat. |

### The full showcase journey

Six cards, one job each - rendered as a single journey:

| Setting | Value |
| --- | --- |
| Cards | `keep the same subject` `0.80` (slot1) - `suggest the visual style` `0.55` (slot2) - `use the background/setting` `0.35` (slot8) - `suggest the color palette` `0.40` (slot4) - `copy the camera framing` `0.30`, `early layout only` (slot6) - `avoid copying text/logos` `0.03` (slot5) |
| Prompt | `a ceramic travel mug on a wooden desk in a bright studio, no readable text` (strength `1.15`) |
| Seed | `972107` |
| Demo files | [result PNG](assets/krea-v10/demos/full-showcase.png), [workflow JSON](assets/krea-v10/demos/full-showcase.workflow.json) |

<img src="assets/krea-v10/demos/full-showcase.png" alt="Full showcase result - six jobs" width="420">

The mug is the prompt's, anchored by the content card; the desk, books, and
window light read bright-studio; the style and palette cards keep the grade
quiet and warm; and no readable markings survive the guard. This render used
`off - use my values` balance (the
[gentle-balance render](assets/krea-v10/demos/full-showcase-balanced.png) of
the same seed sits in the Balance section); the shipped
[showcase workflow](../example_workflows/krea-v10-full-showcase-workflow.json)
turns `gentle balance` on as its starting point:

```text
Reference 1: keep the same subject, 0.80
Reference 2: suggest the visual style, 0.55
Reference 3: use the background/setting, 0.35
Reference 4: suggest the color palette, 0.40
Reference 5: copy the camera framing, 0.30, early layout only
Reference 6: avoid copying text/logos, 0.03
Stack: gentle balance, reuse between runs
```

## Embedded Demo Workflows

Drag any demo PNG into ComfyUI to load its V10 workflow, or open the JSON
beside it. Full per-demo settings live in
[guide-demo-manifest.json](assets/krea-v10/demos/guide-demo-manifest.json).

| Journey | PNG | JSON |
| --- | --- | --- |
| Balanced | [recipe-balanced.png](assets/krea-v10/demos/recipe-balanced.png) | [workflow](assets/krea-v10/demos/recipe-balanced.workflow.json) |
| Keep the same subject | [recipe-keep-same-subject.png](assets/krea-v10/demos/recipe-keep-same-subject.png) | [workflow](assets/krea-v10/demos/recipe-keep-same-subject.workflow.json) |
| Copy pose and layout | [recipe-copy-pose-layout.png](assets/krea-v10/demos/recipe-copy-pose-layout.png) | [workflow](assets/krea-v10/demos/recipe-copy-pose-layout.workflow.json) |
| Copy big shapes only | [recipe-copy-big-shapes.png](assets/krea-v10/demos/recipe-copy-big-shapes.png) | [workflow](assets/krea-v10/demos/recipe-copy-big-shapes.workflow.json) |
| Copy the camera framing | [copy-camera-framing.png](assets/krea-v10/demos/copy-camera-framing.png) | [workflow](assets/krea-v10/demos/copy-camera-framing.workflow.json) |
| Avoid copying text/logos | [recipe-avoid-text-logos.png](assets/krea-v10/demos/recipe-avoid-text-logos.png) | [workflow](assets/krea-v10/demos/recipe-avoid-text-logos.workflow.json) |
| Suggest the color palette | [suggest-color-palette.png](assets/krea-v10/demos/suggest-color-palette.png) | [workflow](assets/krea-v10/demos/suggest-color-palette.workflow.json) |
| Palette journey, prompt only | [suggest-color-palette-off.png](assets/krea-v10/demos/suggest-color-palette-off.png) | [workflow](assets/krea-v10/demos/suggest-color-palette-off.workflow.json) |
| Suggest the visual style | [recipe-suggest-visual-style.png](assets/krea-v10/demos/recipe-suggest-visual-style.png) | [workflow](assets/krea-v10/demos/recipe-suggest-visual-style.workflow.json) |
| Copy lighting and mood | [recipe-copy-lighting-mood.png](assets/krea-v10/demos/recipe-copy-lighting-mood.png) | [workflow](assets/krea-v10/demos/recipe-copy-lighting-mood.workflow.json) |
| Suggest material or texture | [recipe-suggest-material-texture.png](assets/krea-v10/demos/recipe-suggest-material-texture.png) | [workflow](assets/krea-v10/demos/recipe-suggest-material-texture.workflow.json) |
| Use the background/setting | [use-background-setting.png](assets/krea-v10/demos/use-background-setting.png) | [workflow](assets/krea-v10/demos/use-background-setting.workflow.json) |
| Mood board only | [mood-board-only.png](assets/krea-v10/demos/mood-board-only.png) | [workflow](assets/krea-v10/demos/mood-board-only.workflow.json) |
| Timing: early layout only | [timing-style-early-only.png](assets/krea-v10/demos/timing-style-early-only.png) | [workflow](assets/krea-v10/demos/timing-style-early-only.workflow.json) |
| Timing: final details only | [timing-style-final-only.png](assets/krea-v10/demos/timing-style-final-only.png) | [workflow](assets/krea-v10/demos/timing-style-final-only.workflow.json) |
| Direction journey: prompt only | [counter-example-baseline.png](assets/krea-v10/demos/counter-example-baseline.png) | [workflow](assets/krea-v10/demos/counter-example-baseline.workflow.json) |
| Direction journey: style toward | [counter-example-toward.png](assets/krea-v10/demos/counter-example-toward.png) | [workflow](assets/krea-v10/demos/counter-example-toward.workflow.json) |
| Direction journey: style away | [counter-example-away.png](assets/krea-v10/demos/counter-example-away.png) | [workflow](assets/krea-v10/demos/counter-example-away.workflow.json) |
| Full showcase (balance off) | [full-showcase.png](assets/krea-v10/demos/full-showcase.png) | [workflow](assets/krea-v10/demos/full-showcase.workflow.json) |
| Full showcase (gentle balance) | [full-showcase-balanced.png](assets/krea-v10/demos/full-showcase-balanced.png) | [workflow](assets/krea-v10/demos/full-showcase-balanced.workflow.json) |

If a loaded demo reports missing images, copy
`example_assets/krea-reference-examples/` into your ComfyUI `input/` folder.

## Troubleshooting

| Problem | What to try |
| --- | --- |
| A card seems to do nothing. | Read the stack report: the feel curve, a recipe cap, or the guard is usually named on that card's line. Appearance recipes (palette/style/lighting/material/environment/mood) are tuned to land from about strength `0.6` - below that they whisper by design. |
| A custom recipe seems to do nothing at any strength. | Its `shape` is too low (below ~`0.5` the card is effectively off on Krea 2) or its `study` too fine. Raise `shape` toward the built-ins' `0.7`-`1.0`; raising `global` will not help on this model. |
| A `focus` seems ignored. | Check the stack report - the card's line prints its focus. Focus is strongest on object-bound aspects (clothing, props); scene-wide moods ride the image itself. Rephrase to name what to *skip* ("..., not the person or the background") - de-selection is the reliable move. |
| Away card makes the image muddy or empty. | Lower its strength below `0.30`, and make sure something positive (prompt or toward card) says what you *do* want. |
| Many cards fight each other. | Turn on `gentle balance`, or lower the two strongest cards. The report shows the applied scale. |
| Style card drags its subject in. | Check the prepared-references preview; if the subject is visible there, lower detail or strengthen the treatment. In manual mode, lower `Structure layers pull`. |
| Style results look soft or out of focus. | Make sure you are on the current tuning: `suggest the visual style` ships an anti-blur focus (printed on its stack-report line) that stops the recipe's deliberate reference-softening from being copied as the style. If soft-medium references (watercolor, hazy photos) still read soft, that is the medium arriving - lower the card below `0.6` or add crispness words to the prompt. |
| Re-runs are slow while tuning. | Set `Reuse image studies` to `reuse between runs` and keep the prompt fixed while you tune strengths. |
| Behaves oddly after swapping CLIP patches. | Use `always re-study` while experimenting with CLIP-side changes. |

## Companion Files

- [V10 documentation index](krea-v10-documentation-index.md)
- [V10 visual HTML guide](krea-v10-user-guide.html)
- [V10 technical companion paper](krea-v10-technical-paper.md)
- [Guide Card V10 node docs](nodes/kg-krea-2-image-guide-card-v10.md)
- [Reference Stack V10 node docs](nodes/kg-krea-2-reference-stack-encoder-v10.md)
- [V9 user guide](krea-v9-user-guide.md)
- [Example workflows](../example_workflows/README.md)
