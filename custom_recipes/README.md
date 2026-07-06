# Custom Recipes - the Recipe Kit

Drop `.yaml`, `.yml`, or `.json` files into this folder and they become
first-class choices in the V10 guide card's `Use image for` dropdown -
indistinguishable from the built-in recipes. No code required.

This folder is the complete kit for creating recipes:

| Piece | What it gives you |
| --- | --- |
| [Recipe Builder](../web/recipe-builder.html) (`web/recipe-builder.html`) | Three plain-language questions -> a validated, downloadable recipe file. Also served by a running ComfyUI at `/extensions/<pack folder>/recipe-builder.html`. |
| [starter-pack.yaml](starter-pack.yaml) | Ready-made recipes, **loaded automatically**: `borrow the weather`, `borrow the clothing style`, `borrow drawing medium`, `borrow photo finish`, `cinematic color grade`. Working examples to copy from; delete or underscore the file to opt out. |
| [_example-vintage-postcard.yaml](_example-vintage-postcard.yaml) | A fully-commented single-recipe template (disabled until you rename it). |
| This README | The schema, what every field really does on Krea 2, the `focus` field, the layer math, and the render-validation ritual. |
| [Technical reference](../docs/krea-v10-technical-paper.md) | The standalone V10 paper: every widget, every table, all the math. |

Files can also live in `<ComfyUI user dir>/krea_reference/recipes/`, which
survives reinstalling or updating this node pack. Files whose names start
with `_` or `.` are ignored (that is why the bundled template loads nothing
until you copy and rename it).

## Quick Start

**The easy way - no schema knowledge needed:** open the
[Recipe Builder](../web/recipe-builder.html) (`web/recipe-builder.html`).
Answer three plain-language questions (name, what the reference should give,
how strongly) and download a ready-to-drop-in file with every number filled
from the render-validated tuning tables. On a running ComfyUI with this pack
installed it is also served at
`http://<your-comfy>/extensions/<this pack's folder name>/recipe-builder.html`
(e.g. `http://127.0.0.1:8188/extensions/krea-reference/recipe-builder.html`
for a git-clone install).

**The manual way:**

1. Copy [_example-vintage-postcard.yaml](_example-vintage-postcard.yaml) to a
   new name without the leading underscore, e.g. `my-style.yaml`.
2. Edit the `label` (the dropdown text) and the fields you care about.
3. In ComfyUI, refresh node definitions (or restart). Your label now appears
   in `Use image for` on the V10 guide card.

A minimal recipe is two lines - everything else defaults from the role's
tuning tables:

```yaml
label: soft palette hint
role: palette
```

## How A Recipe Actually Works On Krea 2

Before the schema, the mental model. These four facts were established by
rendering controlled sweeps on the real model (not by theory), and they are
the difference between a recipe that works and one that silently does
nothing:

1. **`treatment` decides WHAT can transfer.** The reference is re-drawn by
   the treatment *before* the encoder ever sees it, so the treatment is a
   hard filter on what the card can possibly deliver:

   | You want to borrow | Use treatment | Why it is safe |
   | --- | --- | --- |
   | colors / palette / mood | `palette wash` | the source's shapes are destroyed first, so its subject **cannot** leak into your image |
   | layout / arrangement | `grayscale blur` | color is stripped, so placement arrives without recoloring |
   | silhouette only | `shape wash` | everything but the big masses is removed |
   | the actual subject | `normal` | nothing is removed - the subject can and will copy in |
   | subject + softness | `soft blur` / `strong blur` | **caution:** these keep the source's forms; at working strengths the source object itself tends to appear or reshape your subject |

2. **`shape` is the volume knob.** It scales the one conditioning channel
   that actually moves pixels on Krea 2. Render-calibrated anchors:

   | `shape` | What happens (at normal card strengths, ~0.6-0.9) |
   | --- | --- |
   | `0.0` - `0.4` | effectively **off** - nothing visible arrives |
   | `0.5` - `0.65` | onset - the borrow appears near the top of the strength range |
   | `0.7` - `1.0` | working range for appearance recipes - clear borrow by strength ~0.65, subject preserved (with a structure-destroying treatment) |
   | `1.0` - `1.3` | structural jobs - layout/subject transfer (the built-in structure recipes live here) |

3. **`layers` fine-tunes WHICH bands are emphasized - it is second-order.**
   The 12 gains reshape the signal that `shape` lets through; they cannot
   rescue a `shape` that is too low, and swapping between sensible tables
   changes far less than one step of `shape` or a treatment change. Omit
   `layers` (use the role's table) unless you are deliberately fine-tuning.

4. **`global` has no effect on Krea 2.** It scales a pooled conditioning
   channel that Krea 2's text encoder does not produce. The field stays in
   the schema for other/future models, but do not reach for it on Krea 2 -
   a weak recipe is fixed by raising `shape` (and hardening `treatment`),
   never by raising `global`.

One honest limit to design around: with a structure-destroying treatment the
borrowed look arrives as palette/mood (a color field over the scene), not as
brushwork painted onto your subject's surface, and not as the source's scene
composited behind your subject. Recipes that promise those need conditioning
this model does not have - tune expectations, not numbers.

## Schema

One file holds either a single recipe or a pack: `{"recipes": [...]}`.
Required: `label`, `role`. Unknown keys are rejected (typo protection).

| Field | Required | Type / choices | Default |
| --- | --- | --- | --- |
| `label` | yes | dropdown text; must not collide with a built-in or another custom label | - |
| `role` | yes | `balanced`, `style`, `palette`, `composition`, `framing`, `identity`, `environment`, `lighting`, `material`, `loose`, `shape only`, `text/logo safe` | - |
| `description` | no | free text, shown in docs/tools | `""` |
| `treatment` | no | `normal`, `grayscale`, `soft blur`, `strong blur`, `palette wash`, `color wash`, `grayscale blur`, `shape wash` | `normal` |
| `color` | no | `0.0` to `1.0` - how much color survives preparation | `1.0` |
| `detail` | no | `0.0` to `1.0` - how much fine detail survives | `1.0` |
| `study` | no | `stack`, `256`, `384`, `512`, `768` - study resolution; coarser = looser, and appearance recipes land best at `256` | `stack` |
| `framing` | no | `stack`, `preserve aspect`, `center crop square`, `stretch square` | `stack` |
| `subject` | no | `recipe`, `avoid`, `allow`, `preserve` | `recipe` |
| `early` / `late` | no | `0.0` to `5.0` - phase multipliers | `1.0` |
| `guard` | no | `true` enables the text/logo blank-surface guard (clamps the card like the built-in guard recipe) | `false` |
| `cap` | no | `0.0` to `3.0`, or omit for no cap - hard ceiling on effective strength | none |
| `shape` | no | `0.0` to `3.0` - **the main transfer volume** (see the anchors above) | role default |
| `global` | no | `0.0` to `4.0` - pooled overall-look pull; **inert on Krea 2**, kept for other models | role default |
| `layers` | no | list of exactly 12 numbers (`0.0` to `8.0`) - per-band fine-tuning gains | role table |
| `focus` | no | string, up to 300 chars - **which aspect** of the image the encoder should study (see below) | none |

## The `focus` Field - Aspect-Only Recipes

The numeric fields select *visual channels* (color vs structure); they
cannot separate semantic categories - a dress and the person wearing it
share both. `focus` is the semantic scalpel: free text that the encoder is
told to study, written into its instructions as
`study only <your text> from this image; ignore everything else about it.`

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

Render-verified behavior (same reference, same seed, only the focus text
changed):

- **Selecting works:** clothing-focus kept the reference's red raincoat and
  added garment detail the unfocused run lacked.
- **De-selecting is powerful:** focusing the same photo on "the background
  environment only, *not the person or their clothing*" removed the red
  coat entirely - name what to skip and it stays behind.
- **Boundary:** scene-wide moods (weather, seasons) mostly ride the image
  itself at working strengths - use the treatment + strength for those
  (see `borrow the weather` in the starter pack) and save `focus` for
  object-bound aspects: clothing, props, hairstyles, furniture, vehicles.

`focus` biases what the encoder studies; it does not replace the treatment
guarantees. Keep `subject: avoid` and the treatment appropriate to the job,
and render-validate like everything else.

## The `layers` Array, Exactly

### What the 12 positions are

Each position scales one of the **12 text-encoder layer taps** Krea 2
conditions on (`hidden_states[2,5,8,...,35]`, flattened to a 30720-wide
conditioning that the node splits into 12 x 2560). Position is depth: `0` is
the shallowest tap, `11` the deepest. The built-in tables follow a design
intent - shallow taps lean structure, deep taps lean appearance:

| Positions | Design intent | Family tables put here |
| --- | --- | --- |
| `0`-`4` | Layout, subject structure (shallow taps) | Ramp `0.15` to `0.85` (suppressed) for look-borrowing; `1.0` for structure jobs |
| `5`-`6` | Transition | `1.0` |
| `7` | First appearance band | `2.0`-`2.8` |
| `8` | **Strongest** appearance band (deep) | `4.0`-`5.5` |
| `9` | Mild | `1.1`-`1.4` |
| `10` | Second appearance band | `3.0`-`4.5` |
| `11` | Mild | `1.1`-`1.2` |

The card's manual `Structure layers pull` / `Finish layers pull` dials scale
positions `0`-`5` and `6`-`11` of this same table - a custom `layers` array
is those two dials with per-position control.

### The built-in family tables (your starting points)

```yaml
even:      [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]      # balanced, identity, composition, framing, shape only
style:     [0.25, 0.35, 0.45, 0.6, 0.8, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.2]   # style, environment, loose
palette:   [0.15, 0.2, 0.3, 0.45, 0.7, 1.0, 1.0, 2.8, 5.5, 1.3, 4.5, 1.2]    # palette
material:  [0.2, 0.3, 0.45, 0.65, 0.85, 1.0, 1.0, 2.0, 4.0, 1.2, 3.0, 1.1]   # material
lighting:  [0.2, 0.25, 0.35, 0.5, 0.8, 1.0, 1.0, 2.2, 4.5, 1.4, 4.0, 1.2]    # lighting
guard:     [0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15]  # text/logo safe
```

Omitting `layers` uses your `role`'s table - the right default for most
recipes. One practical note from the table above: `material` has the mildest
appearance spikes, which is why the built-in material recipe runs the highest
`shape` (1.0) of the appearance family - milder gains need more volume.

### How a gain actually lands (the math)

Each position's effective scale is
`clamp(strength_after_feel_curve x shape x gain, -6, +6)` - the gains
multiply the card's per-band pull, and the encoder soft-caps the product at
6. Two render-verified consequences:

1. **Gains and `shape` multiply, so they trade off - but `shape` sets the
   floor.** A spike of `5.0` on a `shape 0.7` card at effective strength
   `0.5` lands at `0.5 x 0.7 x 5.0 = 1.75` on that band; the suppressed
   front bands land near `0.1` - structure stays quiet while the appearance
   bands speak. With `shape 0.1`, even the `5.0` spike lands at `0.25` -
   which is why low-`shape` recipes are invisible no matter the layer table.
2. **`layers` cannot route around `shape` or `treatment`.** The gains only
   reshape what those two let through. Change the outcome with treatment and
   shape; polish the flavor with layers.

### Derivation procedure

0. **Pick `treatment` first** from the "what can transfer" table - it
   decides the outcome class (colors vs layout vs silhouette vs subject).
1. **Pick `shape` from the anchors** (appearance ~`0.7`-`1.0` under
   `palette wash`; structure ~`1.0`-`1.3`; whisper jobs lower + a `cap`).
2. **Start `layers` from the family table** that matches the recipe's
   *intent* (not necessarily its role) - or omit it entirely.
3. Optionally scale positions `0`-`5` by how much layout should arrive
   (`x0.3` to suppress harder, `x1.2`-`x1.5` for structure jobs) and
   positions `6`-`11` by finish emphasis; keep the spike ordering
   (`8` > `10` > `7` >> `9`, `11`) and stay within `0.0`-`8.0`.
4. **Render-validate** (below). Numbers that are not render-validated are
   guesses - that is how the original appearance recipes shipped silent.

Copy-paste helper (same math as the card's manual Structure/Finish dials):

```python
STYLE = [0.25, 0.35, 0.45, 0.6, 0.8, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.2]
structure, finish = 0.6, 1.2   # your emphasis choices
layers = [round(min(g * (structure if i < 6 else finish), 8.0), 3)
          for i, g in enumerate(STYLE)]
print(layers)
```

### Worked example (render-validated)

"Borrow a material reference's surface finish and pattern energy while keeping
source shape quiet" - this mirrors the shipped `suggest material or texture`
recipe, and the reasoning generalizes:

```yaml
label: surface finish borrow
role: material
treatment: strong blur    # keep softened material cues, not sharp source detail
color: 1.0                # keep the material's color/finish signal
detail: 0.35              # enough detail for glaze, fabric, stone, or finish
study: "384"              # moderate study for surface character
subject: avoid
early: 0.35               # keep source structure quiet
late: 0.9                 # let finish arrive late
cap: 0.65
shape: 0.8
global: 1.55              # no effect on Krea 2; harmless to keep for other models
layers: [0.05, 0.075, 0.113, 0.163, 0.213, 0.25, 1.25, 2.75, 5.5, 1.5, 4.125, 1.375]
```

### Validate by rendering (two minutes)

1. Drop the file in, refresh node definitions, pick your label on a card.
2. Fix the seed. Render the same prompt at strengths `0.4`, `0.65`, `0.9`.
3. Read the results against three checks:
   - **Silent?** (0.9 looks like no card at all) -> raise `shape` a step, or
     coarsen `study` to `256`.
   - **Source leaking?** (the reference's subject appears or reshapes yours)
     -> harden `treatment` (`palette wash`), lower `detail`, keep
     `subject: avoid`.
   - **Controllable?** 0.4 should whisper, 0.65 should clearly show the
     borrow, 0.9 should be strong but not destructive. Set `cap` where "too
     much" begins.
4. Wire the encoder's `prepared_references` output to a Preview Image node:
   it shows exactly what the encoder studied. If the treated frame still
   shows what you meant to strip, the treatment is not hard enough.

## Validation

Every file is validated on load. Invalid recipes are skipped with a warning
in the ComfyUI log naming the file and the reason; the node always loads.
Across files (scanned in sorted name order) the first definition of a label
wins.

## Sharing And Saved Workflows

Saved workflows reference custom recipes **by label**. Anyone loading your
workflow needs the same recipe file installed, and renaming or deleting a
file orphans workflows that use it (the card falls back to `balanced` with a
logged warning). Ship the recipe file alongside shared workflows.

## Learn More

- [Creating recipes - full guide section](../docs/krea-v10-user-guide.md#create-your-own-recipes)
- [Guide Card V10 node docs](../docs/nodes/kg-krea-2-image-guide-card-v10.md)
- [Technical companion - loader and validation](../docs/krea-v10-technical-paper.md)
- [How the 12 taps were determined](../docs/deepstack-layers/README.md) - the
  model-verified account of what the layers scale and how the tables were
  derived and re-derived by render measurement.
