# Changelog

## Unreleased - Krea 2 V10 Nodes

- Added `KG Krea 2 Image Guide Card V10` and `KG Krea 2 Reference Stack Encoder V10` (`kg_krea_v10/`). The V9 nodes are untouched and both versions cross-connect: packets stay V9-compatible in both directions.
- Card: four new quick recipes for the previously manual-only roles (`suggest the color palette`, `use the background/setting`, `copy the camera framing`, `mood board only`).
- Card: `Guide direction` - a card can steer the result *away* from its image (counter-example guidance via negative delta targets, with symmetric per-layer clamping).
- Card: `When this card guides` - per-card timing (`whole image`, `early layout only`, `final details only`) on top of the stack schedule.
- Card: manual-only `Structure layers pull` / `Finish layers pull` dials over the deepstack gain table.
- Card: user-defined custom recipes - schema-validated YAML/JSON files in `custom_recipes/` (or `<ComfyUI user dir>/krea_reference/recipes/`) become first-class `Use image for` choices, picked up on node-definition refresh. Only `label` and `role` are required; unknown keys are rejected (typo protection); invalid files are skipped with logged reasons and the node always loads; removed-recipe workflows fall back to `balanced` with a warning. Ships with `custom_recipes/README.md` and a disabled template.
- Stack: `Balance strong cards` - an optional per-phase budget on summed departure from neutral, so several hot cards degrade gracefully instead of fighting.
- Stack: `Reuse image studies` - a content-keyed cache of the base encode and ingredient deltas; re-runs that change only strengths, direction, timing, or balance skip every encoder pass.
- Stack: two new outputs - `stack_report` (plain-language account of caps, curves, guard actions, balance, timing, and encoder pass counts) and `prepared_references` (contact sheet of exactly what the vision encoder studied).
- Text/logo guard: the full guard's prompt rewriter now also understands common marking words in Spanish, French, German, Portuguese, and Italian.
- Web extension: the compact card sockets and manual-row greying now cover the V10 nodes (the V10 layer dials grey out outside manual tuning).
- Contract tests: `tests/test_krea_v10.py` pins the V10 label surface, packet compatibility, direction/timing/balance math, cache behavior, and the multilingual guard vocabulary.
- Example workflows: `krea-v10-full-showcase-workflow.json` (six cards, new recipes, per-card timing, gentle balance, both feedback outputs wired), `krea-v10-counter-example-workflow.json` (the away direction), and `krea-v10-reference-stack-workflow.json` (compact starter), all using the bundled example assets.
- Documentation: V10 user guides (`docs/krea-v10-user-guide.md` / `.html`), a V10 technical companion paper (`docs/krea-v10-technical-paper.md`), a V10 documentation index, per-node V10 pages, and updated landing pages, workflow README, and testing guide (including the V10 smoke checklist and demo-render release step).
- Demo journeys: ten ComfyUI-rendered V10 demos under `docs/assets/krea-v10/demos/` (the four new recipes with a palette before/after pair, the per-card timing pair, the direction journey, and the full showcase), each PNG with the matching V10 workflow embedded, plus a gallery contact sheet and a `guide-demo-manifest.json` recording model, prompt, seed, and strengths per demo. Both V10 guides now show every step of each journey - input images, recipe and settings, the exact prompt, and the result - and the V9 Markdown guide gained demo prompt/seed rows on its recipe cards.

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
