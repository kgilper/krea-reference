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

## 4. How to derive the values reliably (the methodology + harness)

Deriving these reliably - and re-deriving them for any future checkpoint - is a
four-stage pipeline, from cheapest/most-targeted to definitive. Stages 0-1 are
built and have been run (Stage 1 once, see its result below); Stages 2-3 add
render-based validation and optimization on a V10 box. This replaces the way
the shipped values were actually set (borrow a template + eyeball), which
Stages 0-1 show does not match how the model behaves.

### Stage 0 - the model's own prior (free, no rendering) - DONE

Krea 2's diffusion model already learned a per-tap weighting
(`txtfusion.projector [1,12]`). Extract it and compare the shipped tables to
it:

```bash
python docs/deepstack-layers/extract_model_prior.py --model <krea2-*.safetensors>  # re-extract
python docs/deepstack-layers/compare_to_model_prior.py                             # tables vs. prior
```

**Result (2026-07-03):** the model leans hardest on taps **7 > 9 > 4 > 10 > 8**;
the shipped tables spike **8 > 10 > 7**. Rank-correlation of each table with the
model's emphasis is only +0.58 to +0.64, with consistent gaps at taps 4 (model
#3, tables suppress it), 8 (tables' #1 spike, model #5), and 11. So the
borrowed template does not track how Krea 2 actually uses the taps - concrete
motivation to re-derive. (Caveat: the projector weights *processed* taps while
the node's gains hit the *raw* delta, so this is a prior/smell-test, not ground
truth.) Prior values: [model_prior.json](model_prior.json).

### Stage 1 - representational selectivity (cheap, no rendering) - RUN ONCE

Measure, at the conditioning level, what each tap encodes. Build a *controlled*
reference set (vary one attribute at a time), encode each through a neutral V10
card, capture the per-tap signature with the probe node, and decompose the
variance per tap per attribute.

```bash
python docs/deepstack-layers/probe_selectivity.py --selftest              # validate the math (passes)
python docs/deepstack-layers/generate_probe_graphs.py --dry-run           # build encode graphs
# then on a V10+probe box: --server URL, copy signatures back, then:
python docs/deepstack-layers/probe_selectivity.py --probes <dir> --manifest probe_out/probe-manifest.json
```

**Measured (2026-07-03, on the Krea 2 turbo model), in three passes:**

1. **Mechanism confirmed live.** The probe reported feature width **30720**,
   divisible by 12, `tap_dim` 2560 - exactly the 12-tap stack; the split
   engages. Tap magnitude rises steeply with depth (tap 0 ~29 -> tap 11 ~293).
2. **Conditioning-level selectivity does exist** (once the stimuli are clean:
   one colorful base, each attribute changed by a single pure transform). In
   *proportion*, shallow taps 0-4 lean palette and middle taps 5-10 lean
   texture (cross-tap std-dev ~0.10-0.12, well above the flat first attempt).
3. **But render validation flipped the practical conclusion** - and this is the
   important part. Isolating taps in an actual render (`shape=1, global=0`,
   spike the taps, render, measure) showed the **deep taps do essentially all
   the visible work**: spiking taps 7/8/10 turned a plain bowl into the colorful
   reference vase entirely, while spiking the shallow taps 0-4 did *nothing*.
   The deep taps' huge magnitude dominates the pixel effect regardless of their
   proportional attribute mix, so the shallow "palette" taps are practically
   irrelevant, and the effective (deep) taps move palette + texture + subject
   *together* - they do not cleanly separate.

**Net:** the shipped tables spiking taps 7/8/10 is directionally reasonable
(those are the high-leverage taps, which the model's own projector also
emphasizes). What is *not* supported is the idea that the per-tap values cleanly
route distinct attributes - and whether the specific per-role numbers are
optimal cannot be answered at the conditioning level at all.

**The load-bearing lesson:** conditioning-level selectivity misleads on its own,
because tap magnitude and the nonlinear diffusion path dominate the actual
effect. **The layers can only be derived reliably from renders.** Full arc, raw
signatures, and the validation images:
`local_records/2026-07-03-deepstack-layer-determination/stage1-measurement/`.

### Stage 2 - metric-scored render validation (moderate) - PROVEN OUT, formalize next

The decisive test above (isolate taps -> render -> measure palette/texture) is
Stage 2 in miniature and is why the conclusion is trustworthy. Formalizing it
means a fixed seed/prompt grid scored with objective, attribute-specific metrics
(color-distribution distance for palette, LPIPS/SSIM for structure, high-frequency
energy for texture, style/identity distances),
not by eye. [SCORING.md](SCORING.md) is the interim manual rubric.

### Stage 3 - derive the table from renders (definitive) - RUN ONCE for the style role

Turn a role's intent into a measurable objective and pick/optimize the 12-gain
vector by *rendering* candidates and scoring them. Done here for the **style**
role: hold the real style-recipe settings fixed and vary only `layers`; render
(colorful reference -> plain-bowl prompt) and score look-transfer minus
subject-leak.

**Result (2026-07-03):** among seven candidate tables, the **shipped STYLE
table scored best** (objective 0.106), with the shallow-tap table clearly worst
- the render evidence supports spiking the deep taps. But the differences are
small and every candidate's output was nearly the same bowl, so **for the style
role the layer table is a second-order knob**: the shipped values hold up, and
the primary look-vs-subject control is strength and the shape/global
(token/pooled) split, not the per-tap vector. The layers visibly bite only in
the aggressive isolation test (Stage 1 result above), where the deep taps
dominate - which the shipped tables already emphasize.

To go further (more roles, references, a real CMA-ES/Bayesian optimizer with
CLIP style/identity metrics), the harness and objective are in place; this run
is the demonstration. Full result + images:
`local_records/.../stage1-measurement/stage3-derivation/`.

### Bottom line

The reliable, measured way to set the layers is **render-based** (Stages 2-3);
conditioning analysis alone misleads (Stage 1). Applying it shows the shipped
tables are directionally right (they spike the effective, high-magnitude deep
taps, which the model's own projector also leans on) and, for the style role,
near-optimal and second-order. The durable deliverable is the harness itself,
which can re-derive or verify the layers for any future checkpoint.

### Building the controlled reference sets

Stage 1's reliability depends on the sets being controlled. Make them by
generating variants that hold everything fixed but one attribute (e.g. the same
scene re-rendered in N palettes; the same palette over N subjects). These can be
produced with Krea/Ideogram to a dedicated folder. The
[probe manifest](generate_probe_graphs.py) records each reference's attribute
levels for the variance decomposition.

## Files

| File | What | Runs |
| --- | --- | --- |
| [analyze_tables.py](analyze_tables.py) | Prints the five tables' designed shape from live code. | now, local |
| [extract_model_prior.py](extract_model_prior.py) | Extracts the model's learned per-tap weighting from a checkpoint. | now (reads model file) |
| [compare_to_model_prior.py](compare_to_model_prior.py) | Stage 0: tables vs. the model prior. | now, local |
| [probe_node/](probe_node/) | ComfyUI node that saves per-tap conditioning signatures. | install on box |
| [probe_selectivity.py](probe_selectivity.py) | Stage 1: tap x attribute selectivity + self-test. | now (selftest), needs data (real) |
| [generate_probe_graphs.py](generate_probe_graphs.py) | Builds the encode-only probe graphs. | now (dry-run), needs box (encode) |
| [generate_sweep.py](generate_sweep.py) | Stage 2: single-tap render sweep. | needs V10 box |
| [SCORING.md](SCORING.md) | Manual scoring rubric for the render sweep. | reference |

## Cross-references

- [V9 technical paper 5.2](../krea-v9-technical-paper.md#52-per-layer-gains-steering-inside-the-token-channel) - the channel math (inherits the "deepstack" naming corrected here).
- [V9 technical paper 16.4](../krea-v9-technical-paper.md#164-re-tune-layer-gains-for-a-new-checkpoint) - the render-sweep methodology.
- [custom_recipes/README.md](../../custom_recipes/README.md#deriving-the-layers-array) - authoring a `layers` array from this structure.
