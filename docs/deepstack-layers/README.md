# The `layers` Values: What They Scale, and Where They Came From

This folder is the authoritative, reproducible account of the 12 `layers`
values in the Krea reference recipes - **what they physically scale (verified
from the model), where the specific numbers came from (traced through the
development history), and what is still unmeasured.** It is deliberately
honest about the difference between those three things, because "trust me, I
swept it" would be wrong: the numbers were *not* swept.

## 1. What the 12 values scale (verified from ComfyUI source + the model weights)

Krea 2 is unusual in how it conditions on text. Its ComfyUI text encoder
(`comfy/text_encoders/krea2.py`) states it directly:

> Krea 2 (K2) text encoder: Qwen3-VL-4B, 12-layer tap. K2 conditions on a
> stack of hidden states from **12 layers** of Qwen3-VL-4B (reference taps
> `hidden_states[2,5,8,...,35]`), kept as a `(B, 12, seq, 2560)` tensor ...
> flattened to `(B, seq, 12*2560)`.

So the conditioning Krea 2 consumes is **12 text-encoder layer taps** (layers
2, 5, 8, ... 35 - every third layer), each 2560 wide, flattened to width
**12 x 2560 = 30720**. The Krea 2 diffusion model then fuses them with a
*learned* weighting - its weights include `txtfusion.projector [1, 12]` and
per-tap `layerwise_blocks` at width 2560 (visible in the checkpoint header).

The node ([`kg_krea_v9/conditioning.py`](../../kg_krea_v9/conditioning.py))
splits the conditioning-delta's width into `layer_count` (= table length =
12) equal chunks. On Krea 2: `flat = 30720`, `30720 % 12 == 0`,
`layer_dim = 2560` - **the split lands exactly on the 12 layer taps, the
divisibility check passes, and the per-layer gains genuinely apply (no
flat-average fallback).** `layers[i]` scales tap `i` (`hidden_states[2+3i]`),
on top of the model's own learned fusion. Position is depth: `layers[0]` is
the shallowest tap (layer 2), `layers[11]` the deepest (layer 35).

**Terminology warning - "deepstack" is a misnomer here.** The node and the
V9 paper call these "deepstack chunks." That name is inherited but wrong:
Qwen3-VL's actual *deepstack* is **3 vision taps** (`qwen3vl.py`:
`deepstack_visual_indexes=[5, 11, 17]`) used to inject *image*-embed features,
not text. The node's 12 chunks are the 12 K2 *text*-layer taps above. Read
"deepstack chunk N" as "text-layer tap N" throughout.

The landing math per tap: effective scale =
`clamp(strength x phase x shape x layers[i], -6, +6)`, compose weight =
`scale - 1`. Gains act on the **token channel only**; the pooled/global
channel (`global`) is independent. Derivation for authoring:
[`custom_recipes/README.md`](../../custom_recipes/README.md#deriving-the-layers-array).

## 2. Where the specific numbers came from (traced, not guessed)

The provenance was reconstructed from the node's development history (Kevin's
OpenAI Codex sessions, 2026-06-30 to 07-01; internal record in
`local_records/2026-07-03-deepstack-layer-determination/`). The honest story:

1. **Early versions (v1-v5)** applied a single uniform scalar across the whole
   tap stack - no per-tap tables. "Roles" were prose appended to the prompt.
2. **The per-tap tables were adopted, not swept.** The 12-value shape came
   from a third-party node,
   `ComfyUI-ConditioningKrea2Rebalance` (GitHub `nova452`), whose
   `DEFAULT_WEIGHTS = "1,1,1,1,1,1,1,2.5,5.0,1.1,4.0,1.0"` spike the deep taps
   (strongest at tap 8, then 10, then 7). The shipped `STYLE_LAYER_PULL` tail
   is that template almost verbatim (`... 2.5, 5.0, 1.1, 4.0, 1.2`); PALETTE,
   MATERIAL, and LIGHTING are per-role scalings of the same template; the
   suppressed early ramp (taps 0-4) was added on the principle that shallow
   layers carry structure a look-borrowing card should drop.
3. **What *was* tuned empirically** were the scalar knobs, not the vector: the
   `shape` pull (0.45 -> 0.35) and the strength `cap` (-> 0.9), judged against
   seeded before/after renders. The 12-value arrays themselves were held fixed
   and never validated tap-by-tap.

So the numbers rest on: a correct structural premise (12 real taps), a
borrowed spike template, and a sound general principle (shallow = structure,
deep = appearance) - but **not** a per-tap measurement on Krea 2.

## 3. What the tables' shape looks like (a designed pattern, not independent evidence)

`python docs/deepstack-layers/analyze_tables.py` prints the five tables from
the live code. Their shape is coherent and worth seeing:

| Taps | All appearance tables | Reading |
| --- | --- | --- |
| 0-4 | suppress, smooth ramp `0.15 -> 0.85` | shallow layers (structure) turned down |
| 5-6 | neutral `1.0` | transition |
| 7 / 8 / 10 | spike (mean 2.4x / 4.8x / 3.9x) | deep layers (appearance) turned up |
| 9, 11 | mild `1.1-1.4` | gentle |

Note: the four appearance tables agreeing does **not** independently confirm
the per-tap semantics - they agree because they are scalings of one borrowed
template (section 2), so their consensus reflects a single design, not four
independent measurements. It is a self-consistent, principled *design*; treat
it as such.

## 4. What is still unmeasured, and how to measure it (turnkey)

Nobody has yet measured, on Krea 2, what each individual tap actually does to
the image. The direct experiment is the single-chunk sweep, built and ready
here:

```bash
python docs/deepstack-layers/generate_sweep.py --dry-run                 # build + validate (no server)
python docs/deepstack-layers/generate_sweep.py --server http://HOST:8188 # render (needs the V10 nodes)
```

Method: hold one reference at fixed strength; for each tap `L`, render a gain
table that is 1.0 everywhere except a spike at `L`; compare to the all-ones
control. Everything else is held identical, so any visible difference isolates
tap `L`. Scoring: [SCORING.md](SCORING.md). It emits each spike as a V10
custom recipe (validated against the real node code) and writes renders to the
dedicated `output/claude-generations/` folder. Single-chunk tables are not
expressible through the V9 widgets, so rendering needs the V10 nodes on the
target ComfyUI.

### Measured verdicts (to be filled by the sweep)

| Tap | subject ref | palette ref | consensus | note |
| --- | --- | --- | --- | --- |
| 0-4 | _pending_ | _pending_ | | design predicts structure (shallow) |
| 5-6 | _pending_ | _pending_ | | design predicts transition |
| 7 / 8 / 10 | _pending_ | _pending_ | | design predicts appearance (deep); 8 strongest |
| 9, 11 | _pending_ | _pending_ | | design predicts gentle |

If the sweep contradicts the design prediction, that is a real finding - the
borrowed template may not match Krea 2's actual per-tap response, and the
tables would be worth re-deriving from the measurement.

## Files

| File | What |
| --- | --- |
| [analyze_tables.py](analyze_tables.py) | Prints the five tables and their designed shape from the live code. No rendering. |
| [generate_sweep.py](generate_sweep.py) | The single-tap sweep generator - the honest per-tap measurement, still to be run. |
| [SCORING.md](SCORING.md) | How to score the rendered grid into per-tap verdicts. |

## Cross-references

- [V9 technical paper 5.2](../krea-v9-technical-paper.md#52-per-layer-gains-steering-inside-the-token-channel) - the channel math (note: it inherits the "deepstack" naming corrected here).
- [V9 technical paper 16.4](../krea-v9-technical-paper.md#164-re-tune-layer-gains-for-a-new-checkpoint) - the sweep methodology this kit implements.
- [custom_recipes/README.md](../../custom_recipes/README.md#deriving-the-layers-array) - authoring a `layers` array from this structure.
