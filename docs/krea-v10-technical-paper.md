# Krea 2 V10 Reference Conditioning: Technical Companion

**Scope:** the V10 additions only. This paper is a companion to the
[V9 technical paper](krea-v9-technical-paper.md), which remains the canonical
description of the shared architecture: the mute-and-diff delta math (V9 §4),
channel-split weighting (§5), card resolution (§6), image treatments (§7), the
text/logo guard (§8), pass planning (§9), token analysis (§10), and CLIP hooks
(§11). V10 changes none of that. Everything below is layered on top, and the
V9 package is untouched: `kg_krea_v10/` imports V9's math and host-adapter
modules rather than forking them.

**Audience:** node maintainers, ComfyUI developers, and ML practitioners
extending or porting the techniques.

## Contents

1. [Design constraints](#1-design-constraints)
2. [New quick recipes](#2-new-quick-recipes)
3. [Direction: negative delta targets](#3-direction-negative-delta-targets)
4. [Per-card timing](#4-per-card-timing)
5. [Manual layer dials](#5-manual-layer-dials)
6. [Balance: a departure budget](#6-balance-a-departure-budget)
7. [The study cache](#7-the-study-cache)
8. [Feedback outputs](#8-feedback-outputs)
9. [Multilingual guard vocabulary](#9-multilingual-guard-vocabulary)
10. [Packet contract and cross-compatibility](#10-packet-contract-and-cross-compatibility)
11. [Verification](#11-verification)
12. [Limitations](#12-limitations)
13. [Extension points](#13-extension-points)

---

## 1. Design constraints

Three constraints shaped every V10 decision:

1. **V9 is frozen.** The V9 nodes, labels, packets, and math are a shipped
   API pinned by `tests/test_krea_v9.py`. V10 is a pair of *new* nodes; the
   V9 surface appears as an unchanged prefix inside the V10 surface, and new
   rows are appended only.
2. **One link type.** Both versions emit and accept `KG_KREA_REFERENCE`
   packets. A V9 card in a V10 stack and a V10 card in a V9 stack must both
   behave sensibly (§10).
3. **No second copy of the math.** `kg_krea_v10/_v9.py` locates the sibling
   `kg_krea_v9` package under both host layouts (ComfyUI package import and
   the tests' top-level load) so `conditioning`, `images`, `clip_hooks`, and
   `qwen_tokens` have exactly one implementation.

## 2. New quick recipes

V9 defined twelve roles but shipped quick recipes for only eight; `palette`,
`environment`, `framing`, and `loose` were reachable only through manual
tuning. V10 adds one settings bundle per orphaned role
(`kg_krea_v10/recipes.py`), following V9 §16.1: each bundle carries all
fourteen recipe keys, reuses the V9 role pull baselines and layer tables, and
keeps the whisper-defaults philosophy (avoid-subject policies, strength caps
of 0.6 to 1.2, destroy-before-encode treatments).

Two bundles are worth noting:

- **`palette only`** studies at 256 with a palette wash and `detail 0`, so the
  encoder can only ever see coarse color relationships. Shape pull is 0.05.
- **`framing`** sets per-card `framing: "preserve aspect"` rather than
  deferring to the stack, because the aspect ratio *is* the framing signal.

### 2.1 User-defined recipes

The recipe table itself is now user-extensible
(`kg_krea_v10/custom_recipes.py`). Files with `.yaml`/`.yml`/`.json`
extensions in the pack's `custom_recipes/` folder — plus
`<ComfyUI user dir>/krea_reference/recipes/` when `folder_paths` is
importable — are parsed, schema-validated, and merged into the card's
`Use image for` choices after the built-ins, sorted. The card's
`INPUT_TYPES` re-scans on every call, so ComfyUI's node-definition refresh
picks up new files without a restart.

**Schema.** A validated recipe resolves to the same fourteen-key settings
bundle as a built-in `QUICK_RECIPES` entry. `label` and `role` are required;
every other field defaults from the role's V9 tuning tables
(`role_pull_defaults` / `role_layer_pull_defaults`), so a two-line recipe is
well-formed. Validation is deliberately asymmetric: **strict about keys**
(an unknown key is an error — typos cannot become silent no-ops) and
**forgiving about omissions**. Numeric ranges mirror the card's own clamps;
`layers` must be exactly twelve numbers; `guard: true` marks the bundle for
the blank-surface clamp, which then applies in `build()` exactly as for the
built-in guard recipe.

**Identity and collisions.** The label is the identity. Reserved labels are
the union of the artist-facing purpose labels *and* the internal recipe keys
(`_custom_recipes` on the card), closing both shadowing directions — a
custom recipe named `identity` would otherwise resolve to the built-in
bundle through `_map_label`. Across files (scanned in sorted name order) the
first definition of a label wins; later duplicates are reported as
collisions. Files whose names start with `_` or `.` are skipped, which is
how the shipped template stays inert.

**Failure containment.** Node registration can never be broken by a recipe
file: parse and validation errors skip the recipe, are returned to callers,
and are logged once per *change* of the error list rather than once per
scan (`refresh` keeps the last error list; `INPUT_TYPES` runs often). At
build time, a purpose value that is neither built-in nor currently loaded —
a saved workflow whose recipe file was removed — falls back to the
`balanced` bundle with a once-per-label warning instead of silently reading
the manual rows.

**Resolution order** in `build()`: built-in recipe key → custom label →
`manual tuning` → balanced fallback. A resolved custom card carries
`custom_recipe: true` and `custom_recipe_source` (the file name) in its
packet; direction, timing, and the guard clamp compose on top unchanged.

## 3. Direction: negative delta targets

The V9 compose rule is $C_{out} = C_{full} + (t - 1)\,\Delta$ per ingredient
(V9 §4.1, §9.2): $t = 1$ is native, $t \in (0,1)$ interpolates toward the
muted encode, $t = 0$ removes the ingredient, $t > 1$ amplifies. The rule is
well-defined for $t < 0$ — extrapolation past removal into opposition — but V9
clamped all pulls at zero.

V10 exposes the negative range as **direction**. A card set to
`away from this image` negates its targets after the strength curve:

$$t_{token} = -\,s \cdot m_{phase} \cdot p_{shape}, \qquad
  t_{pooled} = -\,s \cdot m_{phase} \cdot p_{global}$$

where $s$ is the curved strength and $m_{phase}$ the phase multiplier. The
sign is applied in the encoder's `_reference_targets`, not in the packet:
packets still carry non-negative pulls, which is what keeps them V9-legal
(§10).

Two consequences follow:

**Symmetric layer clamp.** V9's per-layer soft cap was one-sided
(`min(t·γ, 6.0)`), sufficient when targets are non-negative. V10 clamps
symmetrically: layer scale is `min(max(t·γ, -6.0), 6.0)`, so a hot away card
with a spiked gain table cannot push a single band's weight below $-7$
(weight $= $ clamped scale $- 1$). For toward cards the two formulas are
identical, which the contract tests pin.

**Prompt-side agreement.** The delta captures the image's in-context
contribution regardless of the instruction text, but the role instruction
also influences the *prompt* tokens, which the image delta does not touch.
An away card therefore swaps its system-prompt line for counter-example
language (`REPEL_ROLE_INSTRUCTIONS`, one entry per role), so the prompt side
and the delta side point the same way. Away cards also force
`subject_policy = avoid` at the card, and the auto-prompt appends a
steer-away clause when any away card is present.

Muting is not absence (V9 §15.2), and the same caveat scales with $|t|$:
repulsion is repulsion *of the image's in-context contribution*, not a
guarantee the concept cannot re-enter through the prompt. Practically, away
cards behave at $|t_{token}| \lesssim 0.5$ and get surreal beyond that, which
is why the guides recommend 0.10–0.30.

## 4. Per-card timing

V9's two-phase schedule already computes per-card phase strengths from the
recipe's early/late multipliers (V9 §9.5); V10 adds an artist-facing rewrite
of those multipliers per card (`When this card guides`):

| Choice | Rewrite of (early, late) |
| --- | --- |
| `recipe decides` | unchanged |
| `whole image` | (1.0, 1.0) |
| `early layout only` | (early, 0.0) |
| `final details only` | (0.0, late) |

The rewrite happens at **card resolution time** (`apply_card_timing` in
`kg_krea_v10/recipes.py`), so the packet's `resolved_early_multiplier` /
`resolved_late_multiplier` carry the final values. That placement is what
makes the feature V9-compatible: a V9 stack honors a V10 card's timing choice
without knowing the feature exists. Note the semantics inherited from V9: a
phase multiplier of 0 gives that phase a target of $t = 0$, which *actively
removes* the image's native contribution during that window — the same
mechanism V9's guard recipes use for late suppression.

Ordering: timing rewrites first, then the blank-surface guard clamps
(`late = 0`, `early ≤ 0.75`), so a guarded card can never regain late-phase
influence through timing. This is pinned by
`test_guard_clamp_beats_timing`.

## 5. Manual layer dials

V9 §5.1 flagged per-layer editing as a deliberate simplification and an
extension point. V10 exposes it without exposing twelve raw numbers: two
manual-mode dials scale halves of the role's gain table —
`Structure layers pull` over chunks 0–5, `Finish layers pull` over chunks
6–11. The split follows the V9 empirical sweeps: the spiked
palette/finish-responsive chunks (7, 8, 10) all sit in the back half.

The dials multiply the role table rather than replacing it, compose with the
existing soft cap, and are ignored in recipe mode (recipes ship tuned
tables). The guard clamp runs after the dials, so `layer_pull ≤ 0.15`
survives any dial setting.

## 6. Balance: a departure budget

V9 §15.1 names the failure mode: first-order composition degrades with the
total departure from neutral, so several simultaneously aggressive cards
blend less faithfully than the same cards used separately. V10's
`Balance strong cards` bounds that total per phase.

For one phase's targets, define each card's departure
$d_i = \max(|t_{token,i} - 1|,\ |t_{pooled,i} - 1|)$ and the stack total
$D = \sum_i d_i$. Given budget $B$ (gentle 2.5, strict 1.5, off = none), if
$D > B$ every target is renormalized toward neutral by
$f = B / D$:

$$t' = 1 + (t - 1)\,f$$

applied to token and pooled targets, and per-layer *weights* (already
offsets from neutral) scale by $f$ directly. Properties worth stating:

- Relative card ratios are preserved; only the total is compressed.
- Away cards participate naturally — their departure $|t - 1|$ is large — so
  balance also tames hot repulsion.
- The written prompt is never balanced: text is the artist's voice.
- $f$ is computed per phase, so an early-heavy stack can be scaled while its
  quiet late phase is untouched.
- Balancing happens after target construction and before delta-need
  analysis; scaling never turns a non-neutral card neutral (for $f > 0$), so
  the pass plan is unchanged.

The budgets are heuristics chosen against the V9 strength guidance (a
content anchor at 0.8 plus two medium cards sits just under the gentle
budget); they are data, not architecture, and live in `BALANCE_BUDGETS`.

## 7. The study cache

The observation that makes the cache safe: in the pass plan (V9 §9.2), the
base conditioning and every ingredient delta depend only on the **token
layout** — the final prompt text, the system prompt baked into the chat
template, and the prepared reference tensors. Strengths, direction, timing,
handoff, and balance all apply at compose time. So the expensive artifacts
are pure functions of content, and re-runs that change only compose-time
inputs can skip every encoder forward.

`kg_krea_v10/cache.py` implements a two-entry LRU keyed on:

$$key = (\,id(clip),\ prompt,\ template,\ fingerprint(I_1),\ldots,fingerprint(I_n)\,)$$

with three defensive layers:

1. **Content fingerprints.** Each prepared image tensor is fingerprinted by
   shape, dtype, and three order-sensitive sums: $\sum x$, $\sum x^2$, and
   $\sum i\,x_i$ over the flattened tensor. The position-weighted sum is the
   important one — plain sum and sum-of-squares are invariant under pixel
   permutation (a flipped image would collide), the indexed sum is not.
   Anything that cannot be fingerprinted makes the whole key `None`, which
   bypasses the cache rather than risking a wrong hit.
2. **Weakref identity.** Entries hold `weakref.ref(clip)` and validate it on
   lookup, so a freed CLIP whose `id()` is recycled by the allocator cannot
   satisfy a stale key.
3. **Partial-hit repair.** An entry stores the base conditioning plus a dict
   of deltas keyed `"prompt"` / image index. `_encode_missing_deltas` only
   encodes deltas that are newly needed (e.g. a card whose strength moved
   off zero, or prompt strength leaving 1.0) and merges them back into the
   entry. Hits and misses are reported per run.

What the cache deliberately does **not** key on: mutations *inside* a live
CLIP object (hook keyframes, patches applied in place). Object identity is
the proxy, and the `always re-study` choice is the escape hatch (§12).

Memory: two entries × (1 base + up to 13 deltas) of conditioning-sized
tensors. The two-slot LRU covers the tuning loop (current setup plus the one
just abandoned) without holding a session's history alive.

## 8. Feedback outputs

Appending outputs is index-stable in ComfyUI (existing links bind to output
0), so the V10 stack returns `(CONDITIONING, STRING, IMAGE)`.

**The stack report** (`kg_krea_v10/report.py`) is a deliberate narration of
every decision the V9 architecture made silently: requested versus effective
strength (feel curve), cap engagement and which mechanism capped (recipe cap
versus guard), per-phase targets, direction, timing, balance scale, prompt
handling notes (auto-prompt, guard rewrite, strength floor), encoder pass
counts with cache reuse, skipped cards with reasons, and the once-per-process
layer-fallback state. It is text, not structure, on purpose: the audience is
the artist, and the frozen surface is the node's packet keys, not the
report's phrasing (the tests assert content, not exact formatting).

**The prepared-references contact sheet** (`kg_krea_v10/preview.py`) returns
what the vision encoder actually studied, one frame per active card, centered
on a shared padded canvas (`[N, H_{max}, W_{max}, 3]`, pad value 0.15 to
distinguish canvas from black content). Destroy-before-encode (V9 §7) is the
node's guaranteed information filter; the sheet makes it inspectable. An
empty stack returns a small blank frame so downstream previews never crash.

## 9. Multilingual guard vocabulary

The V9 sanitizer is English-only regex (V9 §15.6, §16.6). V10 adds a starter
vocabulary for five Latin-script languages (Spanish, French, German,
Portuguese, Italian) as a pre-pass in `kg_krea_v10/prompts.py`: a negation
pattern (`sin/sans/ohne/sem/senza` + marking noun → "plain unmarked") that
runs before noun replacement — same ordering rule and for the same reason as
V9 §8.3 — followed by a noun table mapping to the identical replacement
targets, then the unchanged V9 pass (which contributes the prefix and the
English vocabulary).

Selection rule for the table: any word that collides with a common English
word is excluded, because the guard must never rewrite English prompts that
merely mention *cartel*, *parole*, *etiquette*, *manifesto*, or *nombres*.
The tests pin both directions (rewrites happen; collisions survive). CJK
languages need non-regex segmentation and are explicitly out of scope.

## 10. Packet contract and cross-compatibility

A V10 packet is a strict superset of a V9 packet: every V9 key is present
with V9 semantics, `source_version` is `"v10"`, and the additions
(`resolved_direction`, `resolved_timing`, the dial echoes, plus bare
`direction`/`timing` fallbacks) follow the same resolved-plus-fallback
convention the V9 encoder established.

| Combination | Behavior |
| --- | --- |
| V10 card → V10 stack | Full V10 semantics. |
| V9 card → V10 stack | Direction defaults `toward`, timing `recipe`; byte-identical targets to V9 for the same settings. |
| V10 card → V9 stack | V9 reads only the keys it knows. Timing still works (it is baked into the resolved multipliers, §4); direction is carried as data but not acted on — the card behaves as its toward twin. |

The last row is the one deliberate asymmetry: direction requires encoder
cooperation, and a V9 stack predates the concept. Packets stay non-negative
precisely so this degradation is "ignores the feature" rather than "misreads
a number".

## 11. Verification

`tests/test_krea_v10.py` (27 tests) mirrors the V9 contract-test layers, via
the same stub environment and seam-patching pattern:

| Claim | Test |
| --- | --- |
| V10 surfaces are the V9 surfaces plus appended rows, in order | `test_v10_card_labels_are_v9_plus_appended_rows`, `test_v10_stack_labels_are_v9_plus_appended_rows`, `test_v10_purpose_choices_are_v9_plus_new_recipes` |
| Nodes are standalone; all seams exist on the class | `test_v10_is_fully_standalone` |
| Packets versioned, V9-key complete, guard still caps at 0.03 | `test_v10_card_packet_is_versioned_and_v9_compatible` |
| Every recipe (V9 and V10) carries the full 14-key bundle | `test_v10_quick_recipes_cover_the_manual_only_roles` |
| Away negates token/pooled/layer targets (§3) | `test_away_card_negates_targets` |
| Layer clamp is symmetric at ±6.0 (§3) | `test_away_layer_targets_clamp_symmetrically` |
| Timing rewrites; guard clamp wins (§4) | `test_card_timing_overrides_phase_multipliers`, `test_guard_clamp_beats_timing` |
| Dials scale manual mode only (§5) | `test_layer_dials_scale_manual_mode_only` |
| Balance scales only over budget, preserving ratios (§6) | `test_strict_balance_scales_hot_stacks` |
| Cache skips all passes on rerun; strength tweaks stay compose-only; reuse-off re-studies (§7) | `test_study_reuse_skips_encoder_passes_on_reruns` |
| Report names the guard cap (§8) | `test_report_names_the_guard_cap` |
| V9-style packets execute with toward defaults (§10) | `test_v9_style_packet_works_and_defaults_toward` |
| Multilingual rewrites fire; English collisions survive (§9) | `test_sanitizer_rewrites_spanish_and_german_marking_words`, `test_sanitizer_leaves_english_collision_words_alone` |
| Custom recipes load, appear after built-ins, and resolve on the card (§2.1) | `test_json_recipe_appears_in_dropdown_and_resolves_on_card`, `test_minimal_yaml_recipe_fills_role_defaults`, `test_recipe_pack_loads_multiple` |
| Custom guard recipes clamp; direction/timing compose on top (§2.1) | `test_custom_guard_recipe_is_clamped_like_the_builtin_guard`, `test_direction_and_timing_apply_to_custom_recipes` |
| Invalid recipes skip with named reasons; both shadowing directions reserved; first label wins; removed labels fall back to balanced (§2.1) | `test_invalid_recipes_are_skipped_with_reasons`, `test_duplicate_label_across_files_first_wins`, `test_underscore_and_unknown_extensions_are_ignored`, `test_missing_custom_label_falls_back_to_balanced` |

The V9 suite runs unchanged beside it — the strongest available statement
that V10 did not move V9.

## 12. Limitations

1. **Direction inherits every delta caveat.** First-order composition,
   muting-is-not-absence, and template coupling (V9 §15) apply to negative
   targets too, and repulsion amplifies them: away cards degrade noticeably
   past $|t| \approx 0.5$.
2. **Balance is a heuristic.** The budget bounds the *sum* of departures; it
   is a fidelity guardrail, not a proof, and the 2.5/1.5 budgets are tuned
   constants (data, not architecture).
3. **The cache trusts CLIP object identity.** In-place mutations of a live
   CLIP (hook keyframes, live patches) are invisible to the key. The
   documented escape is `always re-study`. Fingerprint collisions are
   cryptographically possible but require identical shape, dtype, and three
   simultaneous sum collisions on real image tensors.
4. **Cache memory is conditioning-sized.** Two entries of base-plus-deltas;
   twelve-card stacks at long prompts make that non-trivial. `MAX_ENTRIES`
   is one constant.
5. **The report is prose, not contract.** Downstream automation should read
   packets and outputs, never parse report text.
6. **The multilingual vocabulary is a starter set.** Five Latin-script
   languages, collision-filtered and therefore deliberately incomplete; CJK
   is out of scope for regex word boundaries.
7. **The V9 stack ignores direction** (§10). Cross-plugging an away card
   into V9 silently behaves as toward — carried as data, not acted on.
8. **Custom recipes make workflows label-portable, not file-portable.**
   Saved workflows reference custom recipes by label; sharing a workflow
   without its recipe file degrades that card to `balanced` (with a
   warning). The dropdown is also no longer a fully frozen list — the
   built-in prefix is frozen, the custom tail is the user's responsibility.
9. **YAML support depends on PyYAML.** ComfyUI ships it; in a stripped
   environment `.yaml` recipes report a clear error and `.json` recipes
   still work.

## 13. Extension points

The V9 paper's §16 recipes all still apply (they operate on the shared
tables). V10-specific seams, all data-first:

- **New recipe:** users need no code path at all — a schema-valid file in
  `custom_recipes/` is a first-class recipe (§2.1). Reserve the
  `QUICK_RECIPES`/`PURPOSE_LABELS` table edit (V9 §16.1) for recipes that
  should ship with the pack for everyone.
- **New role:** as V9 §16.2 (roles are still code: pull baselines, layer
  table, instruction language). Once a role exists, custom recipe files can
  target it immediately — `ROLES` derives from `ROLE_PULL_DEFAULTS`.
- **Recipe schema fields:** extend `ALLOWED_KEYS` plus a validation branch
  in `validate_recipe`, and default the new field in
  `_custom_recipe_settings`. Unknown-key strictness means old packs reject
  files that use fields they do not know — version recipe packs accordingly.
- **Repel language for a new role:** one entry in
  `REPEL_ROLE_INSTRUCTIONS`; unknown roles fall back to the balanced
  counter-example line.
- **Balance budgets:** edit `BALANCE_BUDGETS`; appending a new choice means
  appending a label to the stack's `BALANCE_LABELS`.
- **Guard languages:** extend `EXTRA_MARKING_REPLACEMENTS` /
  `EXTRA_NEGATION_PATTERN`, preserving negation-before-nouns order and the
  English-collision filter.
- **Cache size / policy:** `MAX_ENTRIES` in `cache.py`; the keying helpers
  (`fingerprint_value`, `make_key`) are the seam for smarter keys (e.g.
  hashing CLIP patch state to lift limitation 3).
- **Per-card handoff splits** (the remaining half of V9 §16.7): the V10
  timing rewrite covers phase membership; genuinely per-card *split points*
  would add range-tagged compositions per distinct boundary, still from one
  delta cache, still encode-free.
