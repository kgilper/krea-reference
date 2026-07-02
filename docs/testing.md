# Testing Guide

Use this guide to validate changes with portable paths and test images created for the package.

## Local Contract Tests

These tests stub the small parts of ComfyUI needed by the V9 math and label contracts:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

They verify:

- V9 widget labels remain stable for saved workflow compatibility.
- The text/logo guard supports both full prompt rewriting and gentle prompt preservation.
- Per-layer conditioning math handles scalar and layer-weight composition.
- Layer-target fallback warns when conditioning cannot split into the expected bands.
- Strength curves and timestep ranges behave predictably.

## Syntax Check

```bash
python -m compileall -q kg_krea_v9 __init__.py
```

## Real ComfyUI Smoke Test

Before a release, install the package into a real ComfyUI `custom_nodes` folder, restart ComfyUI, and confirm these node keys appear:

```text
KGKrea2ImageGuideCardV9
KGTextEncodeKreaImageReferencesV9
```

Then load the example workflows and replace placeholder Load Image filenames with test images created for that run.

## Test Images

- Use images generated specifically for the test, public-domain fixtures, or images explicitly provided for the test.
- Keep generated test inputs and outputs outside the git repo, or under ignored local folders such as `input/`, `output/`, or `temp/`.
- Do not commit generated images unless they are intentionally curated public documentation assets.
