# Changelog

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
