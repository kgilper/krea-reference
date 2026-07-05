# V10 Style Transfer Method

Goal: make style transfer reliable inside the V10 Krea guide-card stack while
preserving the requested content subject. This is a stack method, not only a
single recipe.

## Default Method

Use two guide cards:

| Slot | Reference | Use image for | Direction | Card timing | Strength |
| --- | --- | --- | --- | --- | --- |
| 1 | content image | `keep the same subject` | toward | recipe decides | `0.9` |
| 2 | style image | `suggest the visual style` | toward | recipe decides | `0.55` |

Stack settings:

| Setting | Value |
| --- | --- |
| `When images guide` | `smart per-card timing` |
| `Balance strong cards` | `gentle balance` |
| `Image slider feel` | `artist friendly - soft at low values` |
| `Written prompt strength` | start around `1.1` |

This is the best first pass when the user wants obvious style transfer. The
content card anchors the subject; the style card brings palette, medium, and
finish. It is stronger than the single-card style recipe and much more stable
than trying to style-transfer from a prompt alone.

## Input Hygiene

The content reference must be clean. `keep the same subject` preserves the
visible content subject, and if the image contains several people or objects it
may preserve several of them. For reliable style transfer, crop or choose a
content reference where the intended subject is isolated, centered, and free of
extra people, text, logos, or distracting props.

The style reference can be messier, but source-heavy style images need the
leak-control method below. Strong subjects, famous scenes, portraits, big
foreground objects, and hard composition lines are the risky cases.

## Leak-Control Method

If the style source starts bringing its scene/layout along with the look,
change only the style card timing:

| Slot | Reference | Use image for | Direction | Card timing | Strength |
| --- | --- | --- | --- | --- | --- |
| 1 | content image | `keep the same subject` | toward | recipe decides | `0.9` |
| 2 | style image | `suggest the visual style` | toward | `final details only` | `0.65` |

This gives the content image and prompt first claim on layout, then applies the
style in the late/detail phase. It is safer for source-heavy artwork, photos,
and drawings, but the style can be quieter.

Use this as the first choice when content fidelity matters more than obvious
style intensity, or when the style reference has a strong subject/scene.

## Optional Layout Guard

Use this only when the style image still imposes its composition:

| Slot | Reference | Use image for | Direction | Card timing | Strength |
| --- | --- | --- | --- | --- | --- |
| 3 | style image | `copy pose and layout` | away | `early layout only` | `0.1` |

The `0.1` guard is intentionally small. A heavier `0.2` away-layout card was
render-tested and proved too conservative: it protected content but often
muted the useful style signal.

## Decision Tree

1. Use the default two-card method when the style source is abstract,
   texture-like, graphic, or when the user wants obvious visual transformation.
2. Use leak-control (`final details only`) when the style source has a strong
   scene/subject or the first render starts importing the source layout.
3. Add the optional `0.1` layout guard only after leak-control still shows
   source composition leakage.
4. Do not start with the guard. It is a correction, not the default.
5. If all safe variants look too quiet, return to the default two-card method
   and accept some background/style-source presence as the tradeoff for a
   visible transfer.

## Evidence

Rendered on the real V10 ComfyUI server using public-domain references:

- `codex-style-transfer-variety-proof-20260705.png`: one-card style recipe
  across paintings, drawings, photos, and different prompts.
- `codex-style-transfer-method-stack-expanded-proof-20260705.png`: content
  anchor + style-stack comparisons across animal, object/terrain, and figure
  cases.
- `codex-style-transfer-reliability-suite-20260705.png`: 24-render regression
  matrix across six content/style stress cases and four methods.
- `codex-style-transfer-reliability-suite-20260705.jsonl`: matching metrics
  against content and style references.
- `codex-style-transfer-seed-sweep-20260705.png`: 18-render seed-stability
  check across the two recommended methods.
- `codex-style-transfer-seed-sweep-20260705.jsonl`: matching seed-sweep
  metrics.

Key observations from the expanded method proof:

- `style-only` transfers style but does not reliably preserve the intended
  content subject.
- `content + style` gives the strongest visible style transfer while keeping
  the content subject recognizable.
- `final-style` reduces source-scene takeover and is the safer fallback.
- The seed sweep confirms this tradeoff is stable: `two-card` is consistently
  visible across seeds, while `final-style` consistently preserves layout
  better but can be too quiet on some style sources.
- `final-style-guarded` is useful when composition leakage remains, but should
  not be the default.
- Heavy layout-away guarding (`stable-style`, away layout `0.2`) is too muted
  for a general style-transfer method.
- Multi-subject content references are a known failure mode: the content card
  correctly anchors what it sees, so the suite portrait case preserves multiple
  figures. Crop/clean the content reference before treating this as a style
  failure.
- Highly self-styled content references, especially space/nebula imagery, can
  resist unrelated graphic styles. In those cases the method stays stable, but
  the transfer may be subtle unless the default two-card method is used.

## Lab Command

Use `style_transfer_stack_test.py` for repeatable checks:

```bash
python docs/recipe-lab/style_transfer_stack_test.py \
  --method two-card \
  --content-ref codex-style-variety-20260705/durer_hare.jpg \
  --style-ref codex-style-variety-20260705/starry_night.jpg \
  --style-recipe-json docs/recipe-lab/runs/codex-style-transfer-final.json \
  --prompt "the same hare from the content reference sitting on a simple stone plinth in a clean studio scene, no readable text" \
  --seed 771201 \
  --name hare-starry-two-card \
  --balance
```

The `--style-recipe-json` argument exists because the render server may not
have reloaded local Python changes. It injects a lab recipe with the same
settings as the V10 `suggest the visual style` override.

Run the full regression suite:

```bash
python docs/recipe-lab/style_transfer_reliability_suite.py --render --skip-existing
```

Run the seed-stability check:

```bash
python docs/recipe-lab/style_transfer_seed_sweep.py --render --skip-existing
```
