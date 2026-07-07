# KG Krea 2 Concept Slider Card V1

Class: `KGKrea2ConceptSliderCardV1`  
Node key: `KGKrea2ConceptSliderCardV1`  
Category: `advanced/conditioning`  
Source: `kg_krea_slider/slider_card.py`  
Deep dive: [Concept Slider V1 guide](../concept-slider-v1.md) (the dial, the ten-slider render audit, and the slider-writing cookbook)

## What It Does

This node describes one training-free attribute slider for `KG Krea 2 Concept Slider Stack V1`. Name an attribute (`brightness`, `age`, `fog density`), set a value on the `-6..+6` dial, and the stack derives the more-vs-less axis from Krea 2's own text encoder - no LoRA training, no downloads, no extra weights. The card is pure description: no model work happens on it, so a card at `0` costs nothing. For visual examples of ten sliders swept across the dial, see the [Concept Slider guide](../concept-slider-v1.md#the-ten-slider-audit).

## Controls

### `What this slider changes`

The attribute the slider dials. A noun works best (`brightness`, not `bright`; `age`, not `old`). Anything you can describe works - `height`, `clutter`, `color saturation`, `crowd size`, `fine detail`, or a fully custom axis like photoreal-vs-cartoon (set with the pole fields below).

### `Slider value`

The dial, from `-6` to `+6`.

- `0`: exactly your prompt. A zero slider is excluded from the encode entirely (render-proven pixel-identical to a plain prompt encode) and costs nothing.
- `+/-1` to `+/-2`: subtle, composition-preserving nudges.
- `+/-3` to `+/-4`: the reliable working band - clearly visible, scene mostly held.
- `+/-5` to `+/-6`: maximum push. Always audible, never degraded, but expect side effects: composition can reframe, people can change identity, and the axis can saturate.

Negative values push toward less / the opposite; positive toward more.

### `What +6 looks like (optional)`

A sentence describing the high end of the dial. Leave blank to let the stack auto-derive the pole from the attribute name. Fill it in when the auto pole is weak or when you want a specific axis - e.g. `a photorealistic photograph with natural skin texture` for a realism slider.

### `What -6 looks like (optional)`

The low end, same idea. Presence-worded phrases carry the most weight: `an empty deserted plaza with bare pavement and no people` moves a crowd slider's `-6` far more than the bare label does. The guide's [cookbook](../concept-slider-v1.md#fixing-a-weak-slider) has render-proven examples of fixing a weak direction with wording.

## Output

- `slider`: a slider packet for `KG Krea 2 Concept Slider Stack V1`. Connect it to any of the stack's `Slider 1`..`Slider 8` inputs.
