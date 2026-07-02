# KG Krea 2 Image Guide Card V9

Class: `KGKrea2ImageGuideCardV9`  
Node key: `KGKrea2ImageGuideCardV9`  
Category: `advanced/conditioning`  
Source: `kg_krea_v9/guide_card.py`  
Deep dive: [V9 technical paper](../krea-v9-technical-paper.md) (card resolution in section 6)

## What It Does

This node describes one reference image for `KG Krea 2 Reference Stack Encoder V9`. Pick a simple recipe when you know the job of the image, or use manual tuning when you want direct control over color, detail, framing, subject copying, timing, and style reach. For visual examples of every recipe, see the [V9 visual user guide](../krea-v9-user-guide.html).

## Main Controls

### `Reference image`

The image this card describes.

### `How strongly this image guides`

How loudly this image speaks.

- `0.00`: off.
- `0.03` to `0.08`: tiny nudge.
- `0.10` to `0.25`: gentle guidance.
- `0.25` to `0.45`: strong guidance.
- Above `0.50`: can overpower other instructions.

### `Use image for`

The main job of the image.

- `manual tuning`: use every manual lever below.
- `balanced`: general reference behavior with normal treatment, full detail, neutral timing, and even image pull.
- `keep the same subject`: preserve a person, product, object, outfit, or character.
- `copy pose and layout`: borrow pose, camera, crop, spacing, and structure while avoiding subject copying.
- `copy lighting and mood`: borrow light direction, glow, contrast, shadow, and atmosphere.
- `suggest the visual style`: borrow style, palette, finish, and atmosphere while avoiding the style image's subject. Uses a palette wash, very low detail, layer-aware spatial pull, stronger global style reach, and caps quick-style pull at `0.9`.
- `suggest material or texture`: borrow surface feel without copying exact grain or tiny marks.
- `copy big shapes only`: borrow broad shape and silhouette.
- `avoid copying text/logos`: use signs, logos, UI, or labels as blank broad shapes. Caps effective strength at `0.03`.

When a quick recipe is selected, every row below `Use image for` is ignored; the bundled V9 web extension greys those rows out so this is visible on the node.

## Manual Tuning Levers

These count only when `Use image for` is `manual tuning`.

- `Manual mode borrows`: choose the ingredient to borrow (`overall image`, `colors and art style`, `color palette only`, `pose, camera, and layout`, `camera/framing only`, `same person/product/object`, `background/environment`, `lighting and shadows`, `mood-board only`, `surface/material only`, `big shapes only`, or `avoid words/logos`).
- `Prepare image by`: simplify the image before Krea studies it (`use image as-is`, `remove color`, `soften tiny details`, `blur words and texture`, `palette wash`, `color wash`, `shape-only cleanup`, or `strong shape cleanup`).
- `Color kept`: keep or remove palette influence.
- `Small details kept`: reduce texture, tiny marks, fake letters, or exact grain.
- `Study this image at`: override the stack image detail level for this card (`use stack setting`, `low - loose idea (256)`, `medium - balanced default (384)`, `high - more exact (512)`, or `very high - most exact (768)`).
- `Frame this reference by`: override the stack framing mode for this card (`use stack setting`, `keep full image shape`, `center crop square`, or `stretch to square`).
- `Subject copying`: `recipe decides`, `avoid copying subject`, `allow subject if useful`, or `preserve same subject`.
- `Early layout guidance`: how strongly this image pushes early structure when timing is two-phase or smart.
- `Final detail copying`: how much late detail can come through.
- `Maximum image pull`: caps this card even if the main strength is higher.
- `Shape copied`: how much spatial/subject structure this card may push. Lower it for style, palette, lighting, or material cards that should not change the subject.
- `Overall style reach`: how much the card may influence global tone, palette, finish, and atmosphere. Raise it when a manual style card is too subtle.

## Output

- `guide_card`: a guide packet for the Krea reference stack encoder.
