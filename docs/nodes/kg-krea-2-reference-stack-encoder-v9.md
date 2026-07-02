# KG Krea 2 Reference Stack Encoder V9

Class: `KGTextEncodeKreaImageReferencesV9`  
Node key: `KGTextEncodeKreaImageReferencesV9`  
Category: `advanced/conditioning`  
Source: `kg_krea_v9/encoder.py`  
Deep dive: [V9 technical paper](../krea-v9-technical-paper.md) (core technique in section 4, pass plan in section 9)

## What It Does

This node combines a written prompt with one or more guide cards and sends the result to Krea 2 conditioning. For a visual walkthrough and embedded-workflow demo PNGs, see the [V9 visual user guide](../krea-v9-user-guide.html).

## Key Benefits

- **Guarded prompt handling is a visible choice.** When any card is text/logo safe, `Text/logo guard prompt handling` decides whether the stack rewrites marking words in your prompt and boosts prompt strength, or keeps your exact prompt words and only appends blank-surface language.
- **Per-layer gains are soft-capped** so a hot card strength times a spiked recipe layer cannot push a single conditioning band arbitrarily far past encode-native scale.
- **The layered path warns clearly.** If the loaded model's conditioning width does not split into the expected 12 layer chunks, the stack logs a warning once and falls back to broad conditioning.

## Performance

Each connected card whose resolved targets differ from neutral costs one extra text-encoder pass (encode with that image muted), plus one more pass when `Written prompt strength` is not `1.0`. Encode time grows roughly linearly with the number of active cards; a 12-card stack can run about 14 encoder passes. Use `literal slider values` when debugging strength behavior.

## Main Controls

### `Krea CLIP`

The Krea 2 text/image understanding model. Leave it connected.

### `Final image prompt`

Your written art direction. You may leave it blank when the guide cards fully describe the job. V9 then builds a hidden role instruction from connected cards.

### `Written prompt strength`

How strongly the written prompt wins over image references. This is conditioning math, not visible prompt text.

- `0.0`: okay for blank-prompt role mixing.
- `1.0`: normal.
- `1.2` to `2.5`: stronger prompt control.
- `3.5`: useful for text/logo safety or stubborn references.

### `Image slider feel`

- `artist friendly - soft at low values`: recommended.
- `literal slider values`: direct debugging behavior.
- `extra gentle for stubborn references`: lowers sticky references further.

### `Image detail level`

Global study size for cards that do not override `Study this image at`.

- `low - loose idea (256)`
- `medium - balanced default (384)`
- `high - more exact (512)`
- `very high - most exact (768)`

### `Image framing`

Global framing for cards that do not override `Frame this reference by`.

- `keep full image shape`
- `center crop square`
- `stretch to square`

### `When images guide`

- `smart per-card timing`: recommended default. Uses each guide card's early and late settings.
- `guide the whole image`: references guide from start to finish.
- `layout early, details later`: uses early/late card settings with the global handoff.

With `smart per-card timing`, content and layout cards can speak more strongly through spatial image tokens while style, palette, material, and lighting cards can speak more through pooled/global conditioning and style-sensitive Krea conditioning layers.

### `Early-to-final handoff`

Where smart or two-phase timing switches from early structure to later detail. Lower values fade references earlier.

### `Text/logo guard prompt handling`

Only matters when at least one connected card is text/logo safe.

- `full guard - rewrite my prompt`: V9 rewrites marking words in your prompt (for example `sign`, `label`, `screen`, `text`) into positive blank-surface language and raises effective prompt strength to at least `3.5`. Strongest protection, but it touches your whole prompt.
- `gentle guard - keep my prompt words`: V9 keeps your prompt and prompt strength exactly as written and only appends blank-surface language. Choose this when your prompt intentionally mentions signs or screens, or when the full rewrite changes your meaning.

Either way, the guarded card itself stays capped at `0.03` strength with shape-wash preprocessing and zero late copying.

## Practical Recipes

### Image 2 Style Onto Image 1 Without A Prompt

- Reference 1: `keep the same subject`, strength around `0.80`.
- Reference 2: `suggest the visual style`, strength around `0.45` to `0.70` for object/product content or `0.65` to `0.90` for portrait/content-image work.
- Stack: blank `Final image prompt`, `Written prompt strength: 0.0`, `smart per-card timing`, handoff around `0.40`.

If the style still changes the subject too much, lower Reference 2 toward `0.45` or switch it to manual `colors and art style`, `palette wash`, `Subject copying: avoid copying subject`, lower `Shape copied`, and raise `Overall style reach` only as needed.

### Style Or Material Is Too Literal

Use `suggest the visual style` or `suggest material or texture`, lower the card strength, and keep `smart per-card timing`.

### Text Or Logos Appear

Use `avoid copying text/logos` on the card. Keep `Text/logo guard prompt handling` on full guard unless the rewrite conflicts with your prompt.

### Prompt Is Being Ignored

Raise `Written prompt strength`, lower the strongest card, or set that card's `Maximum image pull` lower in manual tuning. If a text/logo-safe card is connected with full guard, remember it floors effective prompt strength at `3.5`.

### Layer Recipes Feel Weak On A New Model

Check the ComfyUI log for the one-time V9 warning about conditioning width. If it appears, the model does not expose the expected 12-chunk layout and style/palette/material/lighting recipes fall back to flat averaging.

## Output

- `CONDITIONING`: the combined Krea 2 conditioning.
