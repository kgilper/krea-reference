# Testing Guide

Use this guide to validate changes with portable paths and test images created for the package.

## Local Contract Tests

These tests stub the small parts of ComfyUI needed by the V9 and V10 math and label contracts:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

They verify:

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

## Syntax Check

```bash
python -m compileall -q kg_krea_v9 kg_krea_v10 __init__.py
```

## Real ComfyUI Smoke Test

Before a release, install the package into a real ComfyUI `custom_nodes` folder, restart ComfyUI, and confirm these node keys appear:

```text
KGKrea2ImageGuideCardV9
KGTextEncodeKreaImageReferencesV9
KGKrea2ImageGuideCardV10
KGTextEncodeKreaImageReferencesV10
```

Then load the example workflows and replace placeholder Load Image filenames with test images created for that run. For the V10 workflows, additionally confirm:

- The stack report (Preview Any) prints per-card lines and the `Studies:` pass count.
- The prepared-references contact sheet (Preview Image) shows one treated frame per active card.
- A second queue with only a strength change reports zero new encoder passes when `Reuse image studies` is on.
- The counter-example workflow's away card is marked in the report with negative targets.

## V10 Demo Renders (release checklist)

The V10 release mirrors the V9 demo gallery: on a live Krea 2 ComfyUI, render one demo per new control (the four new recipes, an away-card pair, and a per-card timing example), save the PNGs with embedded workflow metadata under `docs/assets/krea-v10/demos/`, and link them from the V10 guides - the same format as `docs/assets/krea-v9/demos/`.

## Test Images

- Use images generated specifically for the test, public-domain fixtures, or images explicitly provided for the test.
- Keep generated test inputs and outputs outside the git repo, or under ignored local folders such as `input/`, `output/`, or `temp/`.
- Do not commit generated images unless they are intentionally curated public documentation assets.
