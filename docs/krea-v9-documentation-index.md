# Krea 2 V9 Documentation Index

This is the map for the V9 reference-stack nodes, demo images, and workflows.

![Synthetic reference images included with Krea Reference](../example_assets/krea-reference-examples/contact_sheet.png)

## Start Here

| Resource | Use it for |
| --- | --- |
| [Project README](../README.md) | Product overview, screenshots, installation, and first workflow. |
| [V9 visual HTML guide](krea-v9-user-guide.html) | Rich visual walkthrough with every recipe. |
| [V9 Markdown guide](krea-v9-user-guide.md) | GitHub-friendly version of the guide with embedded images. |
| [V9 technical paper](krea-v9-technical-paper.md) | Full architecture, math, and design reasoning; verification, extension, and porting guides. |
| [Example workflows README](../example_workflows/README.md) | Which workflow to load first and what each one demonstrates. |

## Workflows

| Workflow | Use it for |
| --- | --- |
| [V9 full showcase workflow](../example_workflows/krea-v9-full-showcase-workflow.json) | Best first run. Shows content, style, material, lighting, and text/logo guard roles together. |
| [V9 no-prompt style transfer workflow](../example_workflows/krea-v9-no-prompt-style-transfer-workflow.json) | Applying image 2's style to image 1 with no written prompt. |
| [V9 starter reference stack workflow](../example_workflows/krea-v9-reference-stack-workflow.json) | Compact graph for building your own reference stack. |

## Node Documentation

| Node | Details |
| --- | --- |
| [KG Krea 2 Image Guide Card V9](nodes/kg-krea-2-image-guide-card-v9.md) | Recipe choices, manual tuning controls, and guide-card packet shape. |
| [KG Krea 2 Reference Stack Encoder V9](nodes/kg-krea-2-reference-stack-encoder-v9.md) | Prompt strength, timing, detail level, framing, guard behavior, and conditioning output. |
| [Node documentation index](nodes/README.md) | Short index of all included node pages. |

## Recipe Demo Images

Every individual PNG below contains embedded ComfyUI workflow metadata:

- [manual-tuning.png](assets/krea-v9/demos/manual-tuning.png)
- [balanced.png](assets/krea-v9/demos/balanced.png)
- [keep-same-subject.png](assets/krea-v9/demos/keep-same-subject.png)
- [copy-pose-layout.png](assets/krea-v9/demos/copy-pose-layout.png)
- [copy-lighting-mood.png](assets/krea-v9/demos/copy-lighting-mood.png)
- [suggest-visual-style.png](assets/krea-v9/demos/suggest-visual-style.png)
- [suggest-material-texture.png](assets/krea-v9/demos/suggest-material-texture.png)
- [copy-big-shapes-only.png](assets/krea-v9/demos/copy-big-shapes-only.png)
- [avoid-copying-text-logos.png](assets/krea-v9/demos/avoid-copying-text-logos.png)

## Key Benefits

- Plain-language image roles make multi-reference workflows easier to tune.
- `balanced` provides a general-purpose reference behavior when one image should guide several aspects at once.
- `Text/logo guard prompt handling` makes blank-surface prompt rewriting an explicit stack-level choice.
- Per-layer conditioning gains are soft-capped (`MAX_LAYER_SCALE`) so recipe spikes cannot push a single conditioning band arbitrarily hard.
- When a loaded model's conditioning width does not split into the expected 12 layer chunks, V9 logs a one-time warning and falls back to flat averaging.
- The V9 web extension greys out manual-only guide-card rows whenever a quick recipe is selected and keeps stack encoder card sockets compact.

## Recommended No-Prompt Style Transfer Shape

```text
Reference image 1 -> KG Krea 2 Image Guide Card V9 -> Reference Stack Encoder V9
Reference image 2 -> KG Krea 2 Image Guide Card V9 -> Reference Stack Encoder V9
Reference Stack Encoder V9 -> sampler positive input
```

Use image 1 as the content or subject card, image 2 as the style card, leave
`Final image prompt` blank, and keep `Written prompt strength` at `0.0` for pure
image-reference style transfer.

## Maintainer Source Touchpoints

- [kg_krea_v9/](../kg_krea_v9) (node classes in `guide_card.py` and `encoder.py`; tuning tables, prompt text, image prep, token analysis, CLIP hooks, and conditioning math in sibling modules)
- [__init__.py](../__init__.py)
- [web/krea_reference_stack_v9_ui.js](../web/krea_reference_stack_v9_ui.js)
- [tests/test_krea_v9.py](../tests/test_krea_v9.py)
