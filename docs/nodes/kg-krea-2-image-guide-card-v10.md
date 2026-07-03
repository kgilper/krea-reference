# KG Krea 2 Image Guide Card V10

Class: `KGKrea2ImageGuideCardV10`  
Node key: `KGKrea2ImageGuideCardV10`  
Category: `advanced/conditioning`  
Source: `kg_krea_v10/guide_card.py`  
Deep dive: [V9 technical paper](../krea-v9-technical-paper.md) (the V10 card shares the V9 resolution logic in section 6)

## What It Does

This node describes one reference image for `KG Krea 2 Reference Stack Encoder V10`. It is the V9 card plus four additions: quick recipes for the four jobs V9 left manual-only, a guide direction (a card can now be a counter-example), a per-card timing choice, and manual layer dials.

Guide packets stay V9-compatible: a V10 card plugs into a V9 stack (which ignores the V10 controls), and a V9 card plugs into the V10 stack (the V10 controls fall back to their defaults).

## Everything The V9 Card Has

The first fifteen rows repeat the [V9 card](kg-krea-2-image-guide-card-v9.md) exactly: strength, `Use image for`, and the manual tuning levers behave identically.

## New Quick Recipes

`Use image for` adds four choices:

- `suggest the color palette`: borrow broad color palette and tonal relationships only. Palette wash, zero detail, loose 256 study, quick-strength cap `0.9`.
- `use the background/setting`: borrow location, scene context, and spatial atmosphere without replacing the main subject.
- `copy the camera framing`: borrow camera distance, crop, lens feel, and viewpoint only. Grayscale, structure-heavy early, quiet late.
- `mood board only`: loose inspiration with a gentle `0.6` cap; avoids copying specific details.

## New Controls

### `Guide direction`

- `toward this image`: normal V9 behavior; the reference pulls the result toward its look.
- `away from this image`: the card becomes a counter-example. The stack re-adds this image's isolated contribution negatively, steering the result away from whatever aspect the card's job selects: away from a palette, away from a composition, away from a subject. Start low (`0.1` to `0.3`); repulsion gets strange faster than attraction. A counter-example card always avoids subject copying.

### `When this card guides`

Per-card timing on top of the stack's `When images guide` schedule:

- `recipe decides`: keep the recipe or manual early/late behavior (V9 behavior).
- `whole image`: guide both phases at full card strength.
- `early layout only`: keep the card's early behavior and remove its influence during the final phase.
- `final details only`: remove the card's influence early and keep its late behavior.

The text/logo guard still clamps last: a guarded card never regains late-phase influence.

### `Structure layers pull` and `Finish layers pull`

Manual-mode-only dials over the per-layer gain table (the technical paper's per-layer editing extension point, kept in plain language). `Structure layers pull` scales the first six deepstack chunks (layout and subject structure); `Finish layers pull` scales the last six (palette, texture, and rendering finish). Quick recipes ignore both dials; the bundled web extension greys them out outside manual tuning.

## Output

- `guide_card`: a guide packet for the Krea reference stack encoder (V10 or V9).
