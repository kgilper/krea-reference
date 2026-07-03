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
