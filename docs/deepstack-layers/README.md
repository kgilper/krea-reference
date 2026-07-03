# Deepstack Layers: How The `layers` Values Are Determined

This folder is the authoritative, reproducible account of **what the 12
`layers` values are, where they come from, and how they were determined** for
the Krea reference nodes. It exists because the `layers` array is the one
recipe field with no obvious hand-set value, and "trust me, I swept it" is not
good enough for a public repo.

The determination has three levels of confidence, kept deliberately separate:

1. **Structure - verified from code** (certain).
2. **Semantics - determined by convergent evidence** (strong; reproducible now).
3. **Precise response curve - fresh measurement** (the §16.4 sweep; turnkey
   kit here, awaiting a render box with the V10 nodes).

---

## 1. What the 12 values physically are (verified from code)

Krea 2's text encoder is a Qwen3-VL-family multimodal model. Its token-level
conditioning width is **not flat**: it is a concatenation of **12 equal
"deepstack" chunks**, each carrying vision-language features injected from a
different (successively deeper) encoder layer.

This is not a metaphor - it is visible in the code:

- The model exposes the per-layer features as a **list** named `deepstack` in
  the embedding extras. During a muted encode, each is scaled in lockstep:
  [`kg_krea_v9/clip_hooks.py`](../../kg_krea_v9/clip_hooks.py) - `extra["deepstack"] = [d * strength for d in extra["deepstack"]]`.
- The reweighting splits the conditioning-delta's feature width into
  `layer_count` (= table length = 12) equal chunks and scales chunk `i` by
  `layers[i]`:
  [`kg_krea_v9/conditioning.py`](../../kg_krea_v9/conditioning.py) -
  `shaped_delta = delta.view(..., layer_count, layer_dim); shaped_delta *= gains`.
  The split is guarded by `flat % layer_count == 0`; on a model whose width
  does not divide by 12 it falls back to a flat average and warns once.

So `layers[i]` is the gain on the delta contributed by the **i-th deepstack
encoder-depth band**. Position is depth: `layers[0]` is the shallowest band,
`layers[11]` the deepest.

The landing math (per band): effective scale =
`clamp(strength x phase x shape x layers[i], -6, +6)`, compose weight =
`scale - 1`. Gains act on the **token channel only**; the pooled/global channel
(the `global` field) is independent. Full derivation:
[`custom_recipes/README.md`](../../custom_recipes/README.md#deriving-the-layers-array).

## 2. What each band carries (determined by convergent evidence)

We do not have to take the tuned tables on faith - we can interrogate them.
The repo ships **five** layer tables. Four of them (`style`, `palette`,
`material`, `lighting`) were tuned independently, for four **different** jobs,
by a human running renders. If those four agree about how to treat a given
chunk, that agreement is evidence about what the chunk carries - four
independent tuning targets converging on the same answer.

Run it yourself (reads the live tables from the code, no rendering):

```bash
python docs/deepstack-layers/analyze_tables.py
```

The four appearance tables agree, chunk for chunk:

| Chunk | Consensus across style/palette/material/lighting | Carries |
| --- | --- | --- |
| 0 | all suppress (0.15-0.25) | **structure** |
| 1 | all suppress (0.20-0.35) | **structure** |
| 2 | all suppress (0.30-0.45) | **structure** |
| 3 | all suppress (0.45-0.65) | **structure** |
| 4 | all suppress (0.70-0.85) | **structure** (fading) |
| 5 | all neutral (1.00) | transition |
| 6 | all neutral (1.00) | transition |
| 7 | all spike (mean 2.38x) | **appearance / finish** |
| 8 | all spike (mean 4.75x) | **appearance / finish - strongest** |
| 9 | all mild (1.10-1.40) | appearance (gentle) |
| 10 | all spike (mean 3.88x) | **appearance / finish - second** |
| 11 | all mild (1.10-1.20) | appearance (gentle) |

Two facts make this more than a coincidence:

- **The front ramp is monotonic in all four tables.** Chunks 0->5 rise
  smoothly (e.g. style `0.25, 0.35, 0.45, 0.6, 0.8, 1.0`). Structure influence
  fades out smoothly with encoder depth - exactly the gradient you would
  predict, not an arbitrary set of knobs.
- **The spike ranking is identical in all four:** chunk 8 > chunk 10 > chunk 7,
  every time. Four independent tunings do not agree on a three-way ranking by
  chance.

This is consistent with the well-established behavior of vision transformers:
shallow layers encode local geometry and structure; deep layers encode
semantic appearance (palette, material, finish). The deepstack bands inherit
that gradient, and the tables measured it.

**Determination (level 2):** chunks **0-4 carry subject/layout structure**
(monotonically fading with depth), **5-6 are a neutral transition**, and
**7, 8, 10 carry appearance/finish** (palette, material, rendering look), with
**chunk 8 the dominant appearance band**, 10 second, 7 third; 9 and 11 add a
gentle appearance lift. This is why every look-borrowing recipe suppresses the
front and spikes 7/8/10: it imports finish while leaving the reference's
subject structure behind.

## 3. The precise response curve (fresh measurement - turnkey, pending a render box)

Level 2 determines the qualitative map with confidence. To pin the **exact**
per-chunk response (which chunk moves palette vs. texture vs. lighting
specifically, and how much per unit of gain), the direct experiment is the
§16.4 single-chunk sweep, and it is built and ready here:

```bash
# build + validate the experiment against the real node code (no server):
python docs/deepstack-layers/generate_sweep.py --dry-run

# render it (requires kg_krea_v10 installed on the target ComfyUI):
python docs/deepstack-layers/generate_sweep.py --server http://HOST:8188
```

Method: hold one reference at fixed strength; for each chunk `L`, render a
gain table that is 1.0 everywhere except a spike at `L`; compare each render to
the all-ones control. Everything except chunk `L` is held identical (prompt,
seed, reference, strength, pooled channel, all other chunks), so any visible
difference isolates chunk `L`. Two references (clear-subject and
palette-abstract) let every aspect respond. Scoring rubric: [SCORING.md](SCORING.md).

**Why this is not yet run:** single-chunk spike tables cannot be expressed
through the V9 widgets - only the V10 custom-recipe mechanism can carry an
arbitrary `layers` array - and the available LAN render box currently has only
the V9 nodes installed. The generator therefore emits each spike as a V10
custom recipe and validates them against the real node code today; rendering
needs the V10 pack on a reachable ComfyUI. Once that exists, the command above
produces the grid, and the verdicts get recorded in the table below.

### Measured verdicts (to be filled by the sweep)

| Chunk | subject ref | palette ref | consensus | matches level-2 prediction? |
| --- | --- | --- | --- | --- |
| 0 | _pending_ | _pending_ | | structure |
| 1 | _pending_ | _pending_ | | structure |
| 2 | _pending_ | _pending_ | | structure |
| 3 | _pending_ | _pending_ | | structure |
| 4 | _pending_ | _pending_ | | structure (fading) |
| 5 | _pending_ | _pending_ | | transition |
| 6 | _pending_ | _pending_ | | transition |
| 7 | _pending_ | _pending_ | | appearance |
| 8 | _pending_ | _pending_ | | appearance (strongest) |
| 9 | _pending_ | _pending_ | | appearance (gentle) |
| 10 | _pending_ | _pending_ | | appearance (second) |
| 11 | _pending_ | _pending_ | | appearance (gentle) |

---

## Files

| File | What |
| --- | --- |
| [analyze_tables.py](analyze_tables.py) | Reproducible convergent-evidence analysis (level 2). No rendering. |
| [generate_sweep.py](generate_sweep.py) | The §16.4 single-chunk sweep generator (level 3). Dry-run anywhere; render on a V10 box. |
| [SCORING.md](SCORING.md) | How to score the rendered grid into per-chunk verdicts. |

## Cross-references

- [V9 technical paper §5.2](../krea-v9-technical-paper.md#52-per-layer-gains-steering-inside-the-token-channel) - the channel math and the original statement of provenance.
- [V9 technical paper §16.4](../krea-v9-technical-paper.md#164-re-tune-layer-gains-for-a-new-checkpoint) - the sweep methodology this kit implements, reusable for re-tuning on a new checkpoint.
- [custom_recipes/README.md](../../custom_recipes/README.md#deriving-the-layers-array) - how to derive a `layers` array for a new recipe from these findings.
