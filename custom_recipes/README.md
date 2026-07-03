# Custom Recipes

Drop `.yaml`, `.yml`, or `.json` files into this folder and they become
first-class choices in the V10 guide card's `Use image for` dropdown -
indistinguishable from the built-in recipes. No code required.

Files can also live in `<ComfyUI user dir>/krea_reference/recipes/`, which
survives reinstalling or updating this node pack. Files whose names start
with `_` or `.` are ignored (that is why the bundled template loads nothing
until you copy and rename it).

## Quick Start

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
| `study` | no | `stack`, `256`, `384`, `512`, `768` | `stack` |
| `framing` | no | `stack`, `preserve aspect`, `center crop square`, `stretch square` | `stack` |
| `subject` | no | `recipe`, `avoid`, `allow`, `preserve` | `recipe` |
| `early` / `late` | no | `0.0` to `5.0` - phase multipliers | `1.0` |
| `guard` | no | `true` enables the text/logo blank-surface guard (clamps the card like the built-in guard recipe) | `false` |
| `cap` | no | `0.0` to `3.0`, or omit for no cap - hard ceiling on effective strength | none |
| `shape` | no | `0.0` to `3.0` - spatial/structure pull | role default |
| `global` | no | `0.0` to `4.0` - overall look/style pull | role default |
| `layers` | no | list of exactly 12 numbers (`0.0` to `8.0`) - per-layer conditioning gains | role table |

## Deriving The `layers` Array

`layers` is the only field with no obvious hand-set value, so here is exactly
how the numbers work and how to derive your own.

### What the 12 positions mean

Each position scales one of the **12 text-encoder layer taps** Krea 2
conditions on (`hidden_states[2,5,8,...,35]`, flattened to a 30720-wide
conditioning that the node splits into 12 x 2560). Position is depth: `0` is
the shallowest tap, `11` the deepest. The table below is the *design intent*
behind the built-in tables (shallow layers carry structure, deep layers carry
appearance) - a principled, borrowed pattern, **not** a per-tap measurement on
Krea 2. Full provenance and the (still-unrun) measurement sweep:
[docs/deepstack-layers/](../docs/deepstack-layers/README.md).

| Positions | Design intent | Family tables put here |
| --- | --- | --- |
| `0`-`4` | Layout, subject structure (shallow layers) | Ramp `0.15` to `0.85` (suppressed) for look-borrowing; `1.0` for structure jobs |
| `5`-`6` | Transition | `1.0` |
| `7` | First appearance band | `2.0`-`2.8` |
| `8` | **Strongest** appearance band (deep) | `4.0`-`5.5` |
| `9` | Mild | `1.1`-`1.4` |
| `10` | Second appearance band | `3.0`-`4.5` |
| `11` | Mild | `1.1`-`1.2` |

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
recipes.

### How a gain actually lands (the math)

Each position's effective scale is
`clamp(strength_after_feel_curve x shape x gain, -6, +6)` - the gains
multiply the card's **token-channel** target per band, and the encoder
soft-caps the product at 6. Two consequences:

1. **Gains and `shape` trade off.** Look-borrowing recipes run low `shape`
   (`0.05`-`0.35`) so structure stays suppressed everywhere, and the spikes
   at 7/8/10 restore just the finish bands. A spike of `5.0` on a
   `shape 0.3` card at effective strength `0.5` lands at
   `0.5 x 0.3 x 5.0 = 0.75` - still below native, just *least* suppressed.
2. **`layers` never touches the overall look channel.** The `global` field
   (pooled channel) carries palette/atmosphere independently; if your recipe
   is "pure look, zero structure", low `shape` + high `global` matters more
   than fine layer tuning.

### Derivation procedure

1. Start from the family table that matches the recipe's *intent* (not
   necessarily its role).
2. Scale positions `0`-`5` by how much layout/structure should arrive
   (`x0.3` to suppress harder, `x1.2`-`x1.5` for structure jobs).
3. Scale positions `6`-`11` by how strongly the finish should arrive; keep
   the spike ordering (`8` > `10` > `7` >> `9`,`11`).
4. Stay within `0.0`-`8.0` per entry (schema limit) and remember effective
   scale caps at 6 regardless.

Copy-paste helper (same math as the card's manual Structure/Finish dials):

```python
STYLE = [0.25, 0.35, 0.45, 0.6, 0.8, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.2]
structure, finish = 0.6, 1.2   # your emphasis choices
layers = [round(min(g * (structure if i < 6 else finish), 8.0), 3)
          for i, g in enumerate(STYLE)]
print(layers)
```

Worked example - "watercolor paper texture, absolutely no layout influence":
start from `material`, halve structure, keep finish:
`[0.1, 0.15, 0.225, 0.325, 0.425, 0.5, 1.0, 2.0, 4.0, 1.2, 3.0, 1.1]`
with `shape: 0.15`, `global: 1.4`, `treatment: strong blur`, `detail: 0.05`.

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
