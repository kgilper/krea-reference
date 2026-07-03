# Krea Reference V10 — Technical Reference

*The complete, self-contained technical account of the V10 nodes: every
widget, every recipe value, the conditioning math, the prompt machinery, the
caches, the outputs, and the verified behavior on Krea 2. Nothing here
requires reading the V9 paper; where V10 inherits V9 machinery, the
machinery is documented in full.*

**Package:** `comfyui-krea-reference` — nodes `KG Krea 2 Image Guide Card V10`
(`KGKrea2ImageGuideCardV10`) and `KG Krea 2 Reference Stack Encoder V10`
(`KGTextEncodeKreaImageReferencesV10`), in `kg_krea_v10/` (which composes the
`kg_krea_v9/` modules; both node families ship together and cross-connect).

---

## 1. System overview

Krea Reference gives every reference image a plain-language **job**. Each
image flows through a **guide card** that resolves the job into a settings
packet, and up to twelve packets plus the written prompt flow into the
**stack encoder**, which builds the final conditioning:

```
Load Image ─> Guide Card V10 ─┐
Load Image ─> Guide Card V10 ─┤─> Reference Stack Encoder V10 ─> KSampler (positive)
   written prompt ────────────┘        ├─> stack_report (STRING)
                                       └─> prepared_references (IMAGE)
```

Design goals, in priority order:

1. **Jobs, not knobs.** An artist states what an image is *for*; every
   number follows from tested tables.
2. **Guarantees over suggestions.** What a card must not contribute is
   removed from the image *before* the encoder studies it (§4) — prompt
   wording alone is never the safety mechanism.
3. **Controllable strength.** Low slider values whisper, the working range
   is calibrated, caps stop "too much".
4. **Inspectable.** The stack report says what every card requested, got,
   and why; the prepared-references sheet shows exactly what was studied.

## 2. The conditioning mechanism

### 2.1 What Krea 2 conditions on

Krea 2's text encoder is Qwen3-VL (4B). The model conditions on **twelve
text-encoder layer taps** — `hidden_states[2, 5, 8, ..., 35]`, one every
third layer — each 2560 wide, flattened to a single 30720-wide token
conditioning. The stack encoder addresses these taps individually: any
30720-wide conditioning splits into 12 × 2560 "bands" (position 0 =
shallowest tap, 11 = deepest). Widths that do not divide by 12 fall back to
a flat average of the band gains, with a once-per-process log warning.

Two facts about this model, established by rendering controlled sweeps
(2026-07) and load-bearing for everything below:

- **The pooled channel is inert.** Qwen3-VL emits no `pooled_output`, so
  the delta math carries no pooled component and every `global` pull in the
  recipe tables multiplies nothing. The fields remain for pooled-emitting
  encoders; on Krea 2 all transfer rides the token bands.
- **The band table is second-order.** Shallow bands lean structure and deep
  bands lean appearance, but per-band magnitudes differ so much that
  reshaping the gain table changes flavor, not outcome. Outcomes are decided
  by the treatment (§4) and the `shape` pull (§3).

### 2.2 Mute-and-diff deltas

The encoder isolates each ingredient's contribution empirically:

1. **Base encode** — one forward pass with the full prompt, the system
   prompt (§5), and every prepared reference attached: `C_full`.
2. **Ingredient deltas** — for each reference *i* whose targets are
   non-neutral, re-encode with that image's embedding scaled to zero and
   subtract: `Δ_i = C_full − C_muted(i)`. If the written prompt strength is
   not 1.0, a prompt delta is isolated the same way (prompt tokens muted).
3. **Compose** — re-add the deltas at per-card weights:

   `C_out = C_full + (s_p − 1)·Δ_prompt + Σ_i W_i ⊙ Δ_i`

   where `W_i` is per-band: for band ℓ with gain `γ_ℓ`,
   `w_{i,ℓ} = clamp(t_i · γ_ℓ, −6, +6) − 1` (`MAX_LAYER_SCALE = 6.0`), and
   `t_i` is the card's token target (§3). A target of exactly 1.0 on every
   channel means the delta is not needed at all — that card costs no
   encoder pass.

Encoder passes per run: 1 base + 1 per non-neutral card + 1 iff
`prompt strength ≠ 1.0`. The study cache (§7.3) can reduce all of them to 0.

### 2.3 Scheduling

The stack can compose two variants of the conditioning — an **early** set
(per-card `early` multipliers) and a **late** set (`late` multipliers) — and
emit them with timestep ranges `[0, split]` and `[split, 1]`, where `split`
is the `Early-to-final handoff` widget (default `0.40`). Single-phase modes
emit one composition over `[0, 1]`.

## 3. The strength model

Per card, in application order:

1. **Cap.** `strength = min(slider, cap)` — recipe caps (§8) or the manual
   `Maximum image pull`. The text/logo guard forces `cap = 0.03`.
2. **Feel curve** (stack-wide `Image slider feel`):
   - `artist friendly - soft at low values` (default): 0 below 0.01, then
     `s^1.6` up to 1.0, then `1 + (s − 1) · 1.15`.
   - `extra gentle for stubborn references`: 0 below 0.02, `s^2.7`,
     `1 + (s − 1) · 1.1` above 1.0.
   - `literal slider values`: pass-through.
   The result is the effective strength `σ`.
3. **Phase multiplier** `m` — the recipe/manual `early`/`late` values,
   possibly rewritten by per-card timing (§6.3).
4. **Direction sign** — `+1` toward, `−1` away (§6.4).
5. **Targets** — `token t = sign · σ · m · shape_pull` and
   `pooled g = sign · σ · m · global_pull` (pooled: inert on Krea 2).
   Target 1.0 = the image's native in-context influence; between 0 and 1
   interpolates toward muted; above 1 amplifies; negative repels.
6. **Per-band weights** — `w_ℓ = clamp(t · γ_ℓ, ±6) − 1` over the card's
   12-gain table.
7. **Balance** (optional, §7.2) — scales every card's departure from
   neutral down to a per-phase budget.

Render-calibrated behavior on Krea 2: with a structure-destroying treatment,
appearance recipes run `shape` 0.65–1.0 and land clearly from slider ≈ 0.6;
below `shape` ≈ 0.4 a card is effectively silent; structure jobs run
1.0–1.3; `keep the same subject` reproduces its reference by ≈ 1.2.

## 4. Image preparation

`prepare_image` turns each reference into exactly what the vision encoder
studies — this is the pack's hard guarantee layer. Pipeline order:

1. **Framing** (`framing`): `preserve aspect` scales to equal area
   (`side²` pixels, minimum 16 px per edge); `center crop square` crops the
   centered square then scales to `side × side`; `stretch square` scales
   without cropping. Area interpolation.
2. **Color keep** (`color`, 0–1): blends toward the grayscale copy.
   Grayscale-family treatments force it to 0.
3. **Treatment** (`treatment`):

   | Treatment | Operation | Removes |
   | --- | --- | --- |
   | `normal` | none | nothing |
   | `grayscale` | color drop | palette |
   | `soft blur` | box blur k=5 | micro-texture |
   | `strong blur` | box blur k=13 | words, texture patterns |
   | `palette wash` | adaptive color grid (2–10 cells/side, `side//48`), blended 85/15 with the mean color, then blur k=9 | **everything except color relationships** |
   | `color wash` | box blur k=31 | structure, keeps soft color fields |
   | `grayscale blur` | gray + blur k=13 | palette + detail (keeps shapes) |
   | `shape wash` | gray + blur k=25 | everything except broad silhouette |

4. **Detail keep** (`detail`, 0–1): blends with a blur-17 copy (0 = fully
   softened).
5. Output is RGB, handed to the tokenizer as that card's image.

**The safety consequence (render-verified):** the treatment decides *what
can transfer*. `palette wash` destroys the reference's shapes before
encoding, so its subject **cannot** arrive regardless of strength — that is
what makes a live `shape` pull safe on appearance recipes. Structure-keeping
blurs (`soft`/`strong blur`) leave forms the model can reconstruct: at
working strengths the reference's subject tends to appear or reshape yours.

## 5. Prompt machinery

The encode uses a chat template with a generated system prompt and the
user's prompt (plus one `<|vision_start|><|image_pad|><|vision_end|>` line
per reference) in the user turn.

### 5.1 Role and focus instructions

For each card, the system prompt gets:

- `Input N role: <instruction>.` — per-role language, e.g. lighting =
  *"borrow lighting direction, contrast, mood, color cast, glow, and shadow
  behavior"*; away cards get counter-example phrasing instead (*"treat as a
  style counter-example; steer palette ... away from this image"*).
- `Input N focus: study only <focus> from this image; ignore everything
  else about it.` — when the card carries a `focus` (§9). Away cards get
  scoping phrasing (*"only <focus> from this image; its other aspects do
  not apply"*).
- `Input N subject rule: <policy>.` — for non-default subject policies:
  `avoid` (*"Do not copy this reference image's subject identity, face,
  product identity, outfit, or object design."*), `allow`, `preserve`.

### 5.2 The empty-prompt fallback

An empty written prompt is replaced by role-derived language ("Create a
cohesive final image from the connected visual sources." plus one clause per
active role family), and its strength floors to 1.0. Away cards append
"Steer the overall result away from each counter-example source's look."

### 5.3 The text/logo guard

A guarded card (`avoid copying text/logos`, `guard: true` recipes, or the
manual text/logo-safe target) clamps itself hard — treatment `shape wash`,
color 0, detail 0, study 256, `early ≤ 0.75`, `late = 0`, subject `avoid`,
`cap 0.03`, `shape ≤ 0.08`, `global 0`, every band gain ≤ 0.15 — and
switches the whole stack into guard mode:

- system prompt: marked areas become "smooth empty blank surfaces";
- `full guard - rewrite my prompt`: marking words in the written prompt are
  rewritten to blank-surface language (English plus a starter vocabulary
  for Spanish, French, German, Portuguese, and Italian; negations like "no
  text"/"sin texto" too, since the encoder renders words it reads), and the
  prompt strength floors to **3.5** so the rewritten prompt stays in charge;
- `gentle guard - keep my prompt words`: the prompt is left alone and only
  the blank-surface suffix is appended.

## 6. The Guide Card V10

### 6.1 Widgets (the saved-workflow API — append-only)

| # | Widget | Type / range | Default |
| --- | --- | --- | --- |
| 1 | `Reference image` | IMAGE | — |
| 2 | `How strongly this image guides` | 0.0–3.0 | 0.2 |
| 3 | `Use image for` | 13 built-ins + `manual tuning` + custom recipes | — |
| 4 | `Manual mode borrows` | 12 ingredient choices | `overall image` |
| 5 | `Prepare image by` | 8 treatments (artist labels, §4 table) | `use image as-is` |
| 6 | `Color kept` | 0.0–1.0 | 1.0 |
| 7 | `Small details kept` | 0.0–1.0 | 1.0 |
| 8 | `Study this image at` | stack / 256 / 384 / 512 / 768 | stack |
| 9 | `Frame this reference by` | stack / full shape / center crop / stretch | stack |
| 10 | `Subject copying` | recipe / avoid / allow / preserve | recipe |
| 11 | `Early layout guidance` | 0.0–5.0 | 1.0 |
| 12 | `Final detail copying` | 0.0–5.0 | 1.0 |
| 13 | `Maximum image pull` | 0.0–3.0 | 3.0 |
| 14 | `Shape copied` | 0.0–2.0 | 1.0 |
| 15 | `Overall style reach` | 0.0–3.0 | 1.0 |
| 16 | `Guide direction` | toward / away from this image | toward |
| 17 | `When this card guides` | recipe decides / whole image / early layout only / final details only | recipe decides |
| 18 | `Structure layers pull` | 0.0–2.0 | 1.0 |
| 19 | `Finish layers pull` | 0.0–2.0 | 1.0 |

Rows 4–15 are the manual-mode levers; every quick recipe ignores them (the
bundled web extension greys them out). Rows 16–17 apply to *every* mode.
Rows 18–19 apply in manual mode only.

### 6.2 Resolution order

`Use image for` resolves in this order:

1. A **built-in recipe** label → its `QUICK_RECIPES` bundle (§8.1).
2. A **custom recipe** label → its validated bundle (§8.3).
3. An **unknown label** (a saved workflow whose recipe file was removed) →
   the `balanced` bundle, with a once-per-label log warning — the manual
   rows are *not* silently read.
4. `manual tuning` → the manual levers: role from `Manual mode borrows`,
   treatment from `Prepare image by`,
   `shape_pull = role_base_shape × Shape copied`,
   `global_pull = role_base_global × Overall style reach`,
   `cap = Maximum image pull`, and the role's band table scaled by the two
   layer dials (`Structure layers pull` × bands 0–5, `Finish layers pull` ×
   bands 6–11).

Then, in order: per-card timing rewrites the early/late multipliers
(§6.3); an away direction forces `subject_policy = avoid`; and a guard
clamps everything (§5.3) — the guard always wins.

### 6.3 Per-card timing

| Choice | Effect on (early, late) |
| --- | --- |
| `recipe decides` | keep the recipe/manual values |
| `whole image` | (1.0, 1.0) |
| `early layout only` | (keep, 0.0) |
| `final details only` | (0.0, keep) |

Render note: color commits in the first sampling steps, so an early-only
appearance card still delivers its palette; what the widget really moves is
whether the source guides composition (early) or lays its finish onto the
prompt's layout (late).

### 6.4 Direction

`away from this image` negates the card's targets (token, bands, pooled):
the isolated delta is re-added negatively, steering the result out of
whatever the card's job selects. Away extrapolates past removal, so it is
stronger per slider unit — recommended range 0.1–0.4. Away cards never copy
their subject and use counter-example prompt language (§5.1).

### 6.5 The packet

The card emits a plain dict (type `KG_KREA_REFERENCE`). Load-bearing keys:
`image`, `strength` (post-cap), `requested_strength`, resolved settings
(`resolved_role`, `resolved_treatment`, `resolved_color_keep`,
`resolved_detail`, `resolved_reference_resolution`,
`resolved_reference_fit`, `resolved_subject_policy`,
`resolved_early_multiplier`, `resolved_late_multiplier`,
`resolved_shape_pull`, `resolved_global_pull`, `resolved_layer_pull`,
`resolved_focus`), guard state (`v9_blank_surface_guard`,
`v9_strength_cap`), V10 state (`guide_direction`, `resolved_direction`,
`when_this_card_guides`, `resolved_timing`, `custom_recipe`,
`custom_recipe_source`), and unprefixed compatibility duplicates (`role`,
`treatment`, `shape_pull`, `global_pull`, `layer_pull`, `direction`,
`timing`, `focus`, ...). Packet keys are a frozen surface: append-only.

## 7. The Reference Stack Encoder V10

### 7.1 Widgets

| # | Widget | Choices / range | Default |
| --- | --- | --- | --- |
| 1 | `Krea CLIP` | CLIP | — |
| 2 | `Final image prompt` | multiline string | — |
| 3 | `Written prompt strength` | 0.0–10.0 | 1.0 |
| 4 | `Image slider feel` | artist friendly / literal / extra gentle | artist friendly |
| 5 | `Image detail level` | low (256) / medium (384) / high (512) / very high (768) | medium |
| 6 | `Image framing` | keep full image shape / center crop square / stretch to square | keep full |
| 7 | `When images guide` | smart per-card timing / guide the whole image / layout early, details later | smart |
| 8 | `Early-to-final handoff` | 0.0–1.0 | 0.40 |
| 9 | `Text/logo guard prompt handling` | full guard / gentle guard | full |
| 10 | `Balance strong cards` | off / gentle balance / strict balance | off |
| 11 | `Reuse image studies` | reuse between runs / always re-study | reuse |
| 12+ | `Reference 1..12 guide card` | optional card inputs | — |

`smart per-card timing` and `layout early, details later` both compose two
phases (§2.3); `guide the whole image` composes one. Per-card `study`/
`framing` set to `stack` inherit widgets 5–6.

Skipped cards (no image, or effective strength 0) are listed in the report
and cost nothing.

### 7.2 Balance

Per phase, the departure is `Σ_i max(|t_i − 1|, |g_i − 1|)` over active
cards. When it exceeds the budget (`gentle` 2.5, `strict` 1.5), every
card's token/pooled targets are scaled toward neutral by
`budget / departure` and the band weights scale by the same factor —
relative ratios between cards are preserved, and the written prompt is
never balanced. The applied scale is printed in the report.

### 7.3 The study cache

Deltas depend only on *content* — prompt text, system prompt, and the
prepared images — never on strengths, direction, timing, or balance, which
are compose-time. With `reuse between runs`, the encoder caches
`{full conditioning, ingredient deltas}` under a content key:
`(id(clip), full prompt, chat template, per-image fingerprint)`, where an
image fingerprint is `(shape, dtype, Σx, Σx², Σ x·position)` — edited
images cannot collide with stale entries. The CLIP object is held by weak
reference and validated on lookup; 2 entries are kept (the current setup
plus the one just stepped away from). Re-runs that change only strengths,
direction, timing, handoff, or balance perform **zero** encoder passes.
Caveat: reuse assumes the connected CLIP's behavior is unchanged — pick
`always re-study` while hot-swapping CLIP patches or LoRA hooks.

### 7.4 Outputs

- **`conditioning`** — the composed (possibly two-phase, range-tagged)
  positive conditioning.
- **`stack_report`** (STRING) — plain language: the prompt line and notes
  (auto-prompt, guard rewrite, strength floor), the timing mode, balance
  budget and applied per-phase scales, study reuse counts ("N encoder
  passes this run"), one line per card — purpose, direction, requested →
  effective strength and what intervened (feel curve, recipe cap, guard),
  per-phase shape/look targets, timing, and the card's `focus` when set —
  plus skipped cards and a band-fallback warning when the model's width
  does not split into 12.
- **`prepared_references`** (IMAGE) — a contact sheet, one frame per active
  card, of exactly what the vision encoder studied after §4. If a frame
  still shows what the card was supposed to strip, the treatment is not
  hard enough.

## 8. Recipes

### 8.1 Built-in quick recipes (the shipped values)

All fourteen keys per bundle; `layers` refers to the family tables in §8.2.
Values are the 2026-07 render-retuned set.

| Recipe (dropdown label) | role | treatment | color | detail | study | framing | subject | early | late | cap | shape | global* | layers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `balanced` | balanced | normal | 1.0 | 1.0 | stack | stack | recipe | 1.0 | 1.0 | — | 1.0 | 1.0 | even |
| `keep the same subject` | identity | normal | 1.0 | 1.0 | stack | stack | preserve | 1.0 | 1.0 | — | 1.0 | 1.0 | even |
| `copy pose and layout` | composition | grayscale blur | 0.0 | 0.25 | stack | stack | avoid | 1.2 | 0.2 | 1.25 | 1.3 | 0.3 | even |
| `copy lighting and mood` | lighting | palette wash | 0.85 | 0.15 | 256 | stack | avoid | 1.0 | 0.55 | 1.25 | 0.8 | 1.3 | lighting |
| `suggest the visual style` | style | palette wash | 0.85 | 0.0 | 256 | stack | avoid | 0.85 | 0.85 | 0.9 | 0.8 | 1.85 | style |
| `suggest material or texture` | material | palette wash | 0.8 | 0.1 | 256 | stack | avoid | 0.5 | 0.75 | 0.95 | 1.0 | 1.55 | material |
| `copy big shapes only` | shape only | shape wash | 0.0 | 0.0 | 256 | stack | avoid | 1.1 | 0.0 | 1.0 | 1.2 | 0.05 | even |
| `avoid copying text/logos` | text/logo safe | shape wash | 0.0 | 0.0 | 256 | stack | avoid | 0.75 | 0.0 | **0.03** | 0.08 | 0.0 | flat 0.15 |
| `suggest the color palette` | palette | palette wash | 1.0 | 0.0 | 256 | stack | avoid | 0.9 | 0.9 | 0.9 | 0.7 | 1.8 | palette |
| `use the background/setting` | environment | palette wash | 1.0 | 0.3 | 256 | stack | avoid | 1.1 | 0.6 | 1.2 | 0.7 | 0.85 | style |
| `copy the camera framing` | framing | grayscale blur | 0.0 | 0.15 | 256 | preserve aspect | avoid | 1.2 | 0.15 | 1.2 | 0.95 | 0.25 | even |
| `mood board only` | loose | palette wash | 1.0 | 0.2 | 256 | stack | avoid | 0.8 | 0.8 | 0.9 | 0.65 | 0.7 | style |

\* `global` is inert on Krea 2 (§2.1); values are kept for pooled-emitting
encoders.

Role pull baselines (used by manual mode and as defaults for minimal custom
recipes): balanced 1.0/1.0, identity 1.0/1.0, style 0.8/1.35, palette
0.7/1.75, composition 1.25/0.35, framing 0.9/0.25, environment 0.7/0.8,
lighting 0.8/1.25, material 1.0/1.2, loose 0.65/0.65, shape only 1.2/0.05,
text/logo safe 0.08/0.0.

### 8.2 Band gain tables

```
even:     [1.0] × 12                                    # balanced, identity, composition, framing, shape only
style:    [0.25, 0.35, 0.45, 0.6,  0.8,  1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.2]   # style, environment, loose
palette:  [0.15, 0.2,  0.3,  0.45, 0.7,  1.0, 1.0, 2.8, 5.5, 1.3, 4.5, 1.2]
material: [0.2,  0.3,  0.45, 0.65, 0.85, 1.0, 1.0, 2.0, 4.0, 1.2, 3.0, 1.1]
lighting: [0.2,  0.25, 0.35, 0.5,  0.8,  1.0, 1.0, 2.2, 4.5, 1.4, 4.0, 1.2]
flat:     [0.15] × 12                                   # text/logo safe
```

The design intent: bands 0–4 shallow/structure (suppressed in
look-borrowing tables), 5–6 transition, spikes at 8 (strongest), 10, then
7, with 9/11 mild. Material's spikes are the mildest, which is why its
recipe runs the highest `shape` of the appearance family. The manual
Structure/Finish dials scale bands 0–5 and 6–11 of the same tables.

### 8.3 Custom recipes

Schema-validated `.yaml`/`.yml`/`.json` files become first-class
`Use image for` choices. Search paths, in priority order: the pack's
`custom_recipes/` folder, `<ComfyUI user dir>/krea_reference/recipes/`
(survives pack updates), plus test/power-user extra paths. Files starting
with `_` or `.` are ignored; a file holds one recipe or a pack
(`recipes: [...]`); across files (sorted name order) the first definition
of a label wins; the card's `INPUT_TYPES` re-scans on node-definition
refresh, so new files appear without a restart.

| Field | Required | Values | Default |
| --- | --- | --- | --- |
| `label` | yes | dropdown text; must not collide with built-in labels or internal recipe keys | — |
| `role` | yes | one of the twelve roles | — |
| `description` | no | free text | `""` |
| `treatment` | no | the eight §4 treatments | `normal` |
| `color`, `detail` | no | 0.0–1.0 | 1.0 |
| `study` | no | `stack`/`256`/`384`/`512`/`768` | `stack` |
| `framing` | no | `stack`/`preserve aspect`/`center crop square`/`stretch square` | `stack` |
| `subject` | no | `recipe`/`avoid`/`allow`/`preserve` | `recipe` |
| `early`, `late` | no | 0.0–5.0 | 1.0 |
| `guard` | no | `true` applies the full §5.3 clamp | `false` |
| `cap` | no | 0.0–3.0, omit for none | none |
| `shape` | no | 0.0–3.0 — the main transfer volume | role baseline |
| `global` | no | 0.0–4.0 — inert on Krea 2 | role baseline |
| `layers` | no | exactly 12 numbers, 0.0–8.0 | role table |
| `focus` | no | string ≤ 300 chars — what the encoder should study (§9) | none |

Validation is strict about keys (unknown keys are named errors — typos
cannot become no-ops) and forgiving about omissions. Invalid recipes are
skipped with a logged reason; the node always loads. Saved workflows
reference custom recipes **by label**; a missing label falls back to
`balanced` with a warning (§6.2).

**Starter pack.** `custom_recipes/starter-pack.yaml` auto-loads three
render-validated recipes — `borrow the weather` (strong blur + detail 0.15
keeps the reference's objects out while the sky mood arrives),
`borrow the clothing style` (focus-driven, §9), and
`cinematic color grade` (a bolder palette sibling, cap 1.2). Delete or
underscore the file to opt out.

**Recipe Builder.** `web/recipe-builder.html` (also served by ComfyUI at
`/extensions/<pack folder>/recipe-builder.html`) generates validated recipe
files from plain-language questions; its embedded tables mirror §8.1–8.2
and its outputs are machine-verified against the real loader.

## 9. The focus channel

`focus` names *which aspect* of the reference the encoder should study —
the semantic scalpel the numeric fields cannot provide (a dress and its
wearer share structure and palette; no treatment separates them).

**Mechanism.** The card packet carries `resolved_focus`; the stack writes
`Input N focus: study only <text> from this image; ignore everything else
about it.` directly after the role line (§5.1). The vision encoder is a
VLM: the instruction changes how the image is encoded, so the isolated
delta itself shifts toward the named aspect. Whitespace is normalized, 300
chars max, empty focus is omitted. Away cards get scoping language;
guarded cards skip focus (the guard's blank-panel line wins).

**Validated behavior (A/B, same reference, same seed, 2026-07-03):**

- *Selection:* clothing-focus on a person-in-red-raincoat reference kept
  the garment and added garment detail the unfocused run lacked.
- *De-selection (the strong result):* focusing the same reference on "the
  park setting and background environment only, **not the person or their
  clothing**" removed the signature red coat entirely — text alone chose
  which aspect transferred.
- *Boundary:* for scene-wide moods (weather) at working strengths the
  image channel dominates and focus adds little — broad moods ride
  strength and treatment; focus shines on object-bound aspects (clothing,
  props, marked regions of content).

Focus **biases the study; it does not replace the §4 guarantees.** Keep
`subject: avoid` and the treatment appropriate to the job; use focus to
name the aspect, and name what to skip ("... not the person, face, or the
background") — negative scoping is demonstrably powerful.

## 10. V9 interoperability

Both node generations ship together and cross-connect: a V9 card into the
V10 stack behaves exactly as in V9 (the V10-only packet keys default:
direction toward, timing recipe, focus empty); a V10 card into the V9 stack
works with the V10 controls ignored. V9 nodes are untouched by V10
releases, and saved V9 workflows keep loading unchanged. The retuned recipe
values (§8.1) are shared tables, so both generations render identically for
the shared recipes.

## 11. Verification

- **Contract tests** (`tests/test_krea_v10.py`, with `test_krea_v9.py`;
  run `python -m unittest discover -s tests -p "test_*.py"`): pin the
  widget-label surfaces, packet keys and compatibility, recipe resolution
  (built-in/custom/fallback/manual), direction/timing/balance math, guard
  clamps and multilingual sanitizer, custom-recipe validation (including
  `focus` and the shipped starter pack), cache behavior, and report
  content. The encoder math is exercised through stub seams
  (`_encode_with_controls` etc.) without a GPU.
- **Render validation** — the behavioral claims in this paper (retuned
  strengths, pooled inertness, treatment safety, focus selectivity) were
  established by same-seed A/B renders on the real model via the
  maintainer harness in `docs/recipe-lab/` (a render engine plus an
  agent-orchestrated tweak-and-judge workflow). Every recipe value shipped
  in §8 was render-validated before adoption; numbers that were never
  rendered are guesses.

## 12. Frozen surfaces and extension rules

Three surfaces are load-bearing and append-only, pinned by the tests:

1. **Widget labels** (both nodes) — saved workflows store values by label.
2. **Guide-packet keys** — V9/V10 stacks read them; new keys must default
   sanely when absent.
3. **Recipe labels and internal keys** — saved workflows reference recipes
   by label; custom labels must never collide (the validator enforces it).

Extending safely: append new widget rows, packet keys, recipe labels, or
schema fields with backward-compatible defaults; never rename, reorder, or
repurpose existing ones. Registry releases are immutable once accepted.

## 13. A worked example

*One card, real numbers: a painting connected through
`suggest the visual style`, slider 1.4, stack defaults, prompt "a portrait
of a fox" at strength 1.0.*

1. **Resolution** (§6.2): style-gentle bundle — palette wash, color 0.85,
   detail 0.0, study 256, subject avoid, early/late 0.85/0.85, cap 0.9,
   pulls 0.8/1.85, style band table. Slider 1.4 caps to 0.9.
2. **Feel curve** (§3): σ = 0.9^1.6 = 0.8449.
3. **Preparation** (§4): ≈256² px, 85% color, palette-washed to a ≤10×10
   color grid, fully softened. The encoder sees a soft blocky color map —
   no subject from the painting *can* arrive.
4. **Prompt** (§5): system prompt gains the style role line and the avoid
   subject rule; user turn is one image-pad line plus the prompt.
5. **Targets** (§3), both phases (m = 0.85): base = 0.8449 × 0.85 =
   0.7181; token t = 0.7181 × 0.8 = **0.5745**; pooled g = 0.7181 × 1.85 =
   1.3286 (inert on Krea 2).
6. **Band weights** `w_ℓ = clamp(0.5745 γ_ℓ, ±6) − 1`:

   | ℓ | 0 | 1 | 2 | 3 | 4 | 5 | 6 | **7** | **8** | 9 | **10** | 11 |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | w | −0.856 | −0.799 | −0.741 | −0.655 | −0.540 | −0.426 | −0.426 | **+0.436** | **+1.873** | −0.368 | **+1.298** | −0.311 |

   Structure bands suppressed to 14–57% of native; the three finish bands
   amplified to 1.4–2.9×. The card imports look by making the finish bands
   speak — and because the reference was palette-washed first, those bands
   can only carry color and finish.
7. **Passes** (§2.2): prompt strength 1.0 → no prompt delta; one image
   delta; **2 encoder passes** (0 on a cache hit). Both phases equal here,
   so the two range-tagged compositions are numerically identical.

---

*Companion documents: [V10 user guide](krea-v10-user-guide.md) (journeys
and demos for every feature above), [custom_recipes/README.md](../custom_recipes/README.md)
(the recipe kit), [docs/deepstack-layers/](deepstack-layers/README.md) (the
model-verified determination behind §2.1 and the retune), and the
[V9 technical paper](krea-v9-technical-paper.md) (the V9-era account; not
required reading for this document).*
