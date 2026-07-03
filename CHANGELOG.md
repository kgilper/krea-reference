# Changelog

## Unreleased - Krea 2 V10 Nodes

- Added `KG Krea 2 Image Guide Card V10` and `KG Krea 2 Reference Stack Encoder V10` (`kg_krea_v10/`). The V9 nodes are untouched and both versions cross-connect: packets stay V9-compatible in both directions.
- Card: four new quick recipes for the previously manual-only roles (`suggest the color palette`, `use the background/setting`, `copy the camera framing`, `mood board only`).
- Card: `Guide direction` - a card can steer the result *away* from its image (counter-example guidance via negative delta targets, with symmetric per-layer clamping).
- Card: `When this card guides` - per-card timing (`whole image`, `early layout only`, `final details only`) on top of the stack schedule.
- Card: manual-only `Structure layers pull` / `Finish layers pull` dials over the deepstack gain table.
- Card: user-defined custom recipes - schema-validated YAML/JSON files in `custom_recipes/` (or `<ComfyUI user dir>/krea_reference/recipes/`) become first-class `Use image for` choices, picked up on node-definition refresh. Only `label` and `role` are required; unknown keys are rejected (typo protection); invalid files are skipped with logged reasons and the node always loads; removed-recipe workflows fall back to `balanced` with a warning. Ships with `custom_recipes/README.md` and a disabled template.
- Recipe authoring docs: `custom_recipes/README.md` and both V10 guides now explain how the `layers` array values work - the 12 text-layer taps Krea 2 conditions on, the built-in family tables, the `clamp(strength x shape x gain, +/-6)` landing math, a step-by-step derivation procedure with a copy-paste helper (the same scaling as the card's Structure/Finish dials), and a worked example.
- `docs/deepstack-layers/`: an authoritative determination of what the `layers` values scale (verified from the Krea 2 model - 12 text-encoder layer taps, `hidden_states[2,5,8,...,35]`, flattened to a 30720-wide conditioning; the "deepstack" name is a documented misnomer for the separate 3 vision taps), where the specific numbers came from (adopted from the ComfyUI-ConditioningKrea2Rebalance node's defaults plus shallow=structure/deep=appearance design reasoning, with only the scalar shape/cap knobs empirically tuned - not a per-tap sweep), a reproducible table-shape analysis, and a turnkey single-tap measurement sweep (still to be run).
- `docs/deepstack-layers/` authoritative design basis (README section 3.5): the 12-layer text conditioning is UniFusion-style Layerwise Attention Pooling over every-third Qwen3-VL layer (per the Krea 2 Technical Report + the UniFusion paper), which favors early-to-middle layers with the penultimate contributing least - so the shipped tables' deep-tap spikes are shifted deeper than the design and the model's own learned weighting, with concrete source-backed improvement directions.
- `docs/deepstack-layers/` derivation harness (a reliable, targeted methodology for setting the layer values): Stage 0 extracts Krea 2's own learned per-tap weighting (`txtfusion.projector`) and scores the shipped tables against it (they only weakly track the model - motivation to re-derive); Stage 1 is a no-render selectivity harness (a `KG Conditioning Probe` node + variance-decomposition analysis, with a passing synthetic self-test) that measures what each tap encodes from controlled reference sets; Stages 2-3 (metric-scored render validation and black-box optimization of the 12-gain vector against a stated objective) are documented for a V10 render box.
- Appearance-recipe retune (render-validated on the real Krea 2 model): the `suggest the color palette` and `suggest the visual style` recipes now actually transfer the reference's palette at normal strengths - they were near-silent before. Root cause found by rendering: on Krea 2 the Qwen3-VL text encoder emits no pooled output, so the recipes' `global` (pooled) pull is inert and their whole effect was routed through a dead axis; the live lever is the token-path `shape` pull under structure-destroying image prep. Palette moves `shape` 0.05 -> 0.7; style moves `shape` 0.35 -> 0.8 with coarser prep (study 384 -> 256). Both stay subtle at low card strength and clearly borrow the reference palette by ~0.65 while keeping the subject; validated on a geometric and a natural reference. Code comments in `conditioning.py`/`recipes.py` record that appearance strength rides `shape`, not `global`, on this model. The same fix was applied and render-validated for the other appearance recipes (`copy lighting and mood`, `suggest material or texture`, `use the background/setting`, `mood board only`): each now uses palette-wash prep with a live `shape` so it transfers the reference palette at normal strength with the subject kept, instead of silently doing nothing (or, for the background/environment recipe, morphing the subject toward the reference's shape). On a subject unlike the reference these recipes all converge to structure-safe palette transfer; painting the reference's finish onto the subject's surface or compositing its scene behind the subject is a known limitation of the non-spatial conditioning, not a tuning gap. Structural recipes (subject/pose/layout/framing/shape) are unchanged.
- Stack: `Balance strong cards` - an optional per-phase budget on summed departure from neutral, so several hot cards degrade gracefully instead of fighting.
- Stack: `Reuse image studies` - a content-keyed cache of the base encode and ingredient deltas; re-runs that change only strengths, direction, timing, or balance skip every encoder pass.
- Stack: two new outputs - `stack_report` (plain-language account of caps, curves, guard actions, balance, timing, and encoder pass counts) and `prepared_references` (contact sheet of exactly what the vision encoder studied).
- Text/logo guard: the full guard's prompt rewriter now also understands common marking words in Spanish, French, German, Portuguese, and Italian.
- Web extension: the compact card sockets and manual-row greying now cover the V10 nodes (the V10 layer dials grey out outside manual tuning).
- Contract tests: `tests/test_krea_v10.py` pins the V10 label surface, packet compatibility, direction/timing/balance math, cache behavior, and the multilingual guard vocabulary.
- Example workflows: `krea-v10-full-showcase-workflow.json` (six cards, new recipes, per-card timing, gentle balance, both feedback outputs wired), `krea-v10-counter-example-workflow.json` (the away direction), and `krea-v10-reference-stack-workflow.json` (compact starter), all using the bundled example assets.
- Documentation: V10 user guides (`docs/krea-v10-user-guide.md` / `.html`), a V10 technical companion paper (`docs/krea-v10-technical-paper.md`), a V10 documentation index, per-node V10 pages, and updated landing pages, workflow README, and testing guide (including the V10 smoke checklist and demo-render release step).
- Demo journeys: ten ComfyUI-rendered V10 demos under `docs/assets/krea-v10/demos/` (the four new recipes with a palette before/after pair, the per-card timing pair, the direction journey, and the full showcase), each PNG with the matching V10 workflow embedded, plus a gallery contact sheet and a `guide-demo-manifest.json` recording model, prompt, seed, and strengths per demo. Both V10 guides now show every step of each journey - input images, recipe and settings, the exact prompt, and the result - and the V9 Markdown guide gained demo prompt/seed rows on its recipe cards.
- Guide demo refresh (post-retune): the full demo set was re-rendered through the real V10 nodes with the retuned recipes - twenty demos now cover **every built-in recipe** (a new twelve-recipe gallery with a labeled contact sheet; the four appearance demos share one prompt/seed so the family differences are directly comparable) plus the journeys, including the two that previously waited on a V10 render box: the away-direction step of the direction journey and a balance off/gentle showcase pair. Each PNG embeds the exact V10 workflow that rendered it (maintainer script: `docs/recipe-lab/generate_guide_demos.py`).
- Recipe-authoring docs rewritten around the render-verified control model, in `custom_recipes/README.md` and both V10 guides: `treatment` decides *what* can transfer (with a which-treatment-for-which-borrow table), `shape` is the volume knob (with calibrated anchor bands - below ~0.4 a card is effectively off on Krea 2), `layers` is second-order fine-tuning (with the exact landing math and a render-validated worked example), and `global` is documented as inert on Krea 2. Includes a two-minute render-validation protocol for new recipes; the shipped `_example-vintage-postcard.yaml` template was retuned to working values (shape 0.75, study 256). The V9/V10 technical papers' recipe and pull tables, the worked end-to-end example, the node pages, and the V9 guide's manual-dial descriptions and strength bands were updated to match the retuned code (including an honest note that `Overall style reach` does nothing on Krea 2).

## 0.1.6 - Runnable Example Workflows

- Pointed the starter reference-stack and no-prompt style-transfer workflows' Load Image nodes at the bundled example assets, so all three example workflows run out of the box after copying `example_assets/krea-reference-examples/` into the ComfyUI input folder.
- Added Comfy Registry packaging metadata: the `[tool.comfy]` publisher section in pyproject.toml and a `.comfyignore` that keeps registry packages lean (runtime code, web extension, and example workflows ship; heavy demo assets and dev files do not).

## 0.1.5 - Maintainability Refactor

- Split the single-file `kg_krea_v9.py` module into the `kg_krea_v9/` package: node classes (`guide_card.py`, `encoder.py`) now sit on focused, reusable modules for tuning tables (`recipes.py`), prompt text (`prompts.py`), image preparation (`images.py`), token analysis (`qwen_tokens.py`), CLIP patches (`clip_hooks.py`), and conditioning math (`conditioning.py`).
- Added `docs/krea-v9-technical-paper.md`: a comprehensive technical paper covering the architecture, the mute-and-diff conditioning math, per-layer weighting, the text/logo guard, verification, limitations, and extension/porting guides.
- No behavior change: node keys, widget labels, guide-packet keys, and all conditioning math are unchanged, verified by the contract tests plus an old-vs-new equivalence sweep. Saved workflows keep loading as-is.
- The syntax check in the docs is now `python -m compileall -q kg_krea_v9 __init__.py`; the contract tests load the package instead of the single file.

## 0.1.4 - Markdown Guide Layout

- Reworked `docs/krea-v9-user-guide.md` for GitHub readability with a table of contents, recipe chooser, compact visual recipe cards, and workflow-link tables.

## 0.1.3 - Documentation Refresh

- Reworked the README around visual examples, task-based setup, recipe examples, and workflow selection.
- Improved the docs landing page and V9 documentation index with clearer navigation and embedded images.
- Added example images to the workflow README to make the bundled demos easier to understand.

## 0.1.2 - Markdown User Guide

- Added `docs/krea-v9-user-guide.md`, a Markdown version of the V9 visual guide with embedded demo images.
- Linked the Markdown guide from the README and documentation index.

## 0.1.1 - Visual Guide And Recipe Demos

- Added `docs/krea-v9-user-guide.html`, an extensive visual guide for the V9 guide card and reference stack.
- Added ComfyUI-generated PNG examples for every `Use image for` recipe.
- Embedded each recipe demo workflow in its matching PNG so the image can be dragged into ComfyUI.
- Added extra synthetic reference fixtures for pose/layout, big-shape, and background/environment examples.

## 0.1.0 - Initial Public Package

- Extracted the standalone Krea 2 V9 guide-card and reference-stack encoder nodes.
- Added portable V9 starter workflows with synthetic example assets.
- Added local contract tests for V9 labels, guard behavior, and conditioning math.
