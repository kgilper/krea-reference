# Testing Guide

Use this guide to validate changes with portable paths and test images created for the package.

## Local Contract Tests

Run the complete source suite from the repository root:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The suite covers the preserved V9/V10 contracts, Slider V1/V11 behavior and
the additive V12/V13 native interfaces. Lightweight host doubles keep most
checks independent of a running ComfyUI server; tensor checks use the available
PyTorch runtime. Read the test output for any skipped checks. Key coverage:

- V9 widget labels remain stable for saved workflow compatibility, and V10 labels are the V9 labels plus appended rows only.
- Guide packets stay compatible in both directions: V9 cards work in the V10 stack and V10 cards work in the V9 stack.
- The text/logo guard supports both full prompt rewriting and gentle prompt preservation, and the V10 multilingual vocabulary rewrites Spanish/French/German/Portuguese/Italian marking words without touching English collision words.
- Per-layer conditioning math handles scalar and layer-weight composition, and the V10 direction feature negates targets with a symmetric layer clamp.
- Per-card timing rewrites phase multipliers and the blank-surface guard clamp always wins.
- The V10 balance budget scales hot stacks while preserving card ratios.
- The V10 study cache skips encoder passes on re-runs and re-studies when reuse is off.
- Custom recipe files validate against the schema: valid YAML/JSON recipes appear after the built-in dropdown choices and resolve on the card (including guard clamping and direction/timing composition), invalid files are skipped with named reasons, labels cannot shadow built-ins in either direction, and removed-recipe workflows fall back to `balanced`.
- Layer-target fallback warns when conditioning cannot split into the expected bands.
- Strength curves and timestep ranges behave predictably.
- V11 automatic/manual slider budgets, cancellation, timing and saved-widget compatibility.
- V12 native ownership, target preparation, source compatibility, optional enhancer ordering/cleanup and bounded diagnostics.
- V13 literal carrier selection, exact unit-weight copies, cancellation/zero identity, CFG1 admission and native guider delegation.

Passing these checks establishes source contracts. It does not establish useful
semantic effects on an installed model. The [V13 illumination comparison](krea-v13-native-carriers.md#verified-signed-illumination-comparison)
is separate live evidence with a specific recipe and scope.

## Syntax Check

```bash
python -m compileall -q kg_krea_v9 kg_krea_v10 kg_krea_slider kg_krea_v11 kg_krea_v12 kg_krea_v13 __init__.py
```

## Real ComfyUI Smoke Test

Before a release, install the package into a real ComfyUI `custom_nodes` folder, restart ComfyUI, and confirm these node keys appear:

```text
KGKrea2ImageGuideCardV9
KGTextEncodeKreaImageReferencesV9
KGKrea2ImageGuideCardV10
KGTextEncodeKreaImageReferencesV10
KGKrea2ConceptSliderCardV1
KGKrea2ConceptSliderStackV1
KGKrea2ImageGuideCardV11
KGTextEncodeKreaImageReferencesV11
KGKrea2ConceptSliderCardV11
KGKrea2ConceptSliderStackV11
```

Current GitHub source also registers ten V12 and two V13 native classes; see
the [complete node index](nodes/README.md). Confirm both V13 nodes have the
expected typed ports and inspect startup errors. Node presence alone does not
verify native dependency compatibility or loaded model behavior.

For a native V13 smoke, first check the documented host/source profiles and
follow [setup and wiring](krea-v13-native-carriers.md#setup-and-first-comparison).
Keep synthetic source, prompt, seed and recipe fixed for the zero/minus/plus
comparison. Confirm completion, actual outputs and absence of errors, then
inspect scene preservation and the intended visible change. Retain actual
parameters and original outputs privately. Use ordinary studies; diagnostic
nodes add predictions and require a separate bounded test plan.

On a shared server, coordinate an idle installation/restart window. If installed
runtime bytes already match the reviewed source, verify identity and usability
without restarting solely for documentation changes.

Then load the example workflows and replace placeholder Load Image filenames with test images created for that run. For the V10 workflows, additionally confirm:

- The stack report (Preview Any) prints per-card lines and the `Studies:` pass count.
- The prepared-references contact sheet (Preview Image) shows one treated frame per active card.
- A second queue with only a strength change reports zero new encoder passes when `Reuse image studies` is on.
- The counter-example workflow's away card is marked in the report with negative targets.
- The twenty bundled recipes appear in `Use image for` out of the box: the five starter recipes (`borrow the weather`, `borrow the clothing style`, `borrow drawing medium`, `borrow photo finish`, `cinematic color grade`), the ten designer-artwork-pack recipes (`borrow the poster style`, `borrow the soft media look`, `borrow the pattern energy`, `borrow the era print look`, `borrow the paper and canvas`, `borrow the metallic accents`, `borrow the ornament borders`, `borrow the stained glass look`, `style the finish only`, `style the layout first`), and the five edit-composite-pack recipes (`match the scene light`, `match the monochrome look`, `match the atmosphere`, `use the background only`, `carry the subject over`). The starter-recipe workflow queues cleanly.
- A recipe with a `focus` prints `Focus: ...` on its report card line - including the built-in `suggest the visual style` and `copy lighting and mood` cards, which ship focuses of their own.
- The V10 recipe overrides resolve on the V10 card: `copy lighting and mood` resolves to `strong blur` (not the V9 palette wash) and `copy big shapes only` resolves the structure-only layer table.
- The Recipe Builder is served at `/extensions/<pack folder>/recipe-builder.html` and its downloaded files validate (drop one in `custom_recipes/`, refresh node definitions, confirm it appears).

## V10 Demo Renders (release checklist)

The V10 demo set (twenty journeys: one demo per built-in recipe - the twelve-recipe gallery with its labeled contact sheet - plus the palette before/after pair, the timing pair, the three-step direction journey including the away render, and the balance off/gentle showcase pair) lives under `docs/assets/krea-v10/demos/` with per-demo settings in its `guide-demo-manifest.json`. Every demo was rendered through the real V10 nodes with the current recipe tuning; each PNG embeds the exact V10 workflow that rendered it.

To regenerate after a recipe change: `python docs/recipe-lab/generate_guide_demos.py` (renders on the configured ComfyUI box, re-embeds workflows, and rebuilds the manifest and the recipe-gallery contact sheet; `--only <slugs>` re-renders a subset).

## Test Images

- Use images generated specifically for the test, public-domain fixtures, or images explicitly provided for the test.
- Keep generated test inputs and outputs outside the git repo, or under ignored local folders such as `input/`, `output/`, or `temp/`.
- Do not commit generated images unless they are intentionally curated public documentation assets.
