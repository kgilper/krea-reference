# KG Krea 2 Concept Slider Stack V1

Class: `KGKrea2ConceptSliderStackV1`  
Node key: `KGKrea2ConceptSliderStackV1`  
Category: `advanced/conditioning`  
Source: `kg_krea_slider/encoder.py`  
Deep dive: [Concept Slider V1 guide](../concept-slider-v1.md) (architecture, the render audit, and the slider report)

## What It Does

Reads up to eight [slider cards](kg-krea-2-concept-slider-card-v1.md), combines them with your written prompt, and builds Krea conditioning with each slider's semantic axis pushed by its value. It replaces your CLIP Text Encode node on the positive prompt. A stack with no cards behaves exactly like CLIP Text Encode, so a second copy can carry the negative prompt.

What a slider LoRA learns offline - a direction between "more of this attribute" and "less of it" - this stack derives at encode time from the text encoder itself: each slider's two pole sentences are appended to the prompt in one token sequence, the base is encoded with every pole muted, each pole is encoded solo, and the axis is the difference. Everything rides the token path (Krea 2's encoder has no pooled output). See the [guide](../concept-slider-v1.md) for the full account.

## Controls

### `Krea CLIP`

The Krea 2 CLIP. The same model you would feed a CLIP Text Encode node.

### `Final image prompt`

Your written prompt. With no sliders connected, this encodes exactly as a plain prompt.

### `Overall slider reach`

One multiplier over every slider's push (`0.0`-`3.0`, default `1.0`). Raise it for a stubborn prompt before maxing individual sliders; drop it to tame a whole stack at once. Note that amplifying a vaguely worded axis amplifies nothing - fix a weak direction with pole wording (on the card), not with reach.

### `Reuse slider studies`

Each slider's axis depends only on text, never on its value, so value drags can be compose-only:

- `reuse between runs - faster tuning`: re-runs that change only slider values or reach reuse every study and skip all encoder passes. Keys are content fingerprints, so editing the prompt or a pole re-studies automatically.
- `always re-study`: every run pays full encode cost. Pick this while hot-swapping CLIP patches or LoRA hooks.

### `Slider 1` .. `Slider 8` (optional)

Up to eight slider-card inputs. Order does not matter; a disconnected or `0`-valued slider costs nothing. Two sliders over the same poles share one study.

## Outputs

- `conditioning`: Krea conditioning for the KSampler positive input.
- `slider_report`: a plain-language account of the run - each active slider's exact pole sentences, computed push, and whether each pole was auto-derived or custom; every skipped slider and why (`at 0 - costs nothing`, `no description or pole text`); and the encoder-pass vs. cache-hit counts. Wire it into any text-display node when a slider seems to be doing nothing.

## Performance

`1 + 2 x (active sliders)` encoder passes on the first run for a given prompt and pole set, then zero on value-only re-runs with study reuse on. The report prints the exact pass count each run.
