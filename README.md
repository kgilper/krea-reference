# ComfyUI Krea Reference

Give each reference image a job before it reaches Krea.

Krea Reference is a small ComfyUI custom-node package for directing Krea 2 with
multiple image references. Instead of one source image vaguely influencing the
whole result, each image gets a clear role: preserve the subject, borrow a
visual style, copy lighting, suggest a material, follow a layout, or avoid
copying text and logos.

![Krea V9 recipe demo output gallery](docs/assets/krea-v9/demos/recipe-gallery.png)

The demo images above were generated with the included workflows. Each
individual PNG in [docs/assets/krea-v9/demos](docs/assets/krea-v9/demos/) has
ComfyUI workflow metadata embedded, so you can drag a demo PNG into ComfyUI to
inspect the exact setup.

## What It Helps You Do

| Goal | How to set it up |
| --- | --- |
| Put image 2's style onto image 1 | Image 1: `keep the same subject` at `0.80`. Image 2: `suggest the visual style` at `0.45` to `0.65`. |
| Keep a product or character recognizable | Use `keep the same subject` for the identity image, then add lower-strength style, lighting, or material cards. |
| Borrow lighting without copying the subject | Use `copy lighting and mood` around `0.30` to `0.45`. |
| Borrow a surface or finish | Use `suggest material or texture` around `0.25` to `0.40`. |
| Follow a pose, crop, or composition | Use `copy pose and layout` or `copy big shapes only` at gentle to medium strength. |
| Use a reference that contains text or logos | Add `avoid copying text/logos` at very low strength, usually around `0.03`. |

## How The Workflow Thinks

![Synthetic reference images included with Krea Reference](example_assets/krea-reference-examples/contact_sheet.png)

Each guide card answers two questions:

1. What should Krea borrow from this image?
2. How strongly should this image guide the result?

The stack encoder combines the written prompt and all connected guide cards:

```text
Load Image -> KG Krea 2 Image Guide Card V9 -> KG Krea 2 Reference Stack Encoder V9 -> KSampler positive input
```

That makes multi-reference workflows easier to reason about. A product image can
be responsible for the subject, an abstract image can be responsible for style,
a third image can be responsible for lighting, and a fourth can protect against
text/logo copying.

## Included Nodes

| Node | Purpose |
| --- | --- |
| `KG Krea 2 Image Guide Card V9` | Describes one reference image. Choose a recipe or use manual tuning. |
| `KG Krea 2 Reference Stack Encoder V9` | Combines the final prompt and up to 12 guide cards into Krea conditioning. |

The nodes expose plain-language controls for prompt strength, image strength
feel, image detail level, framing, timing, and text/logo guard behavior.

## Install

Clone this repo into your ComfyUI `custom_nodes` directory and restart ComfyUI:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/kgilper/krea-reference.git
```

This repo does not include model weights. Use your own Krea-compatible model,
CLIP, and VAE files in ComfyUI.

## Try It In Five Minutes

1. Copy [example_assets/krea-reference-examples](example_assets/krea-reference-examples/) into your ComfyUI `input/` folder.
2. Load [example_workflows/krea-v9-full-showcase-workflow.json](example_workflows/krea-v9-full-showcase-workflow.json).
3. Queue it once with the included synthetic reference images.
4. Replace the Load Image nodes with your own test images.
5. On each guide card, choose `Use image for` and adjust `How strongly this image guides`.

The full showcase demonstrates five roles:

| Slot | Recipe | Starting Strength |
| --- | --- | --- |
| Content anchor | `keep the same subject` | `0.80` |
| Visual style | `suggest the visual style` | `0.65` |
| Material/texture | `suggest material or texture` | `0.35` |
| Lighting/mood | `manual tuning` with lighting controls | `0.45` |
| Text/logo guard | `avoid copying text/logos` | `0.03` |

## Recipe Examples

These examples show the effect of common guide-card recipes. Open the linked PNG
or drag it into ComfyUI to load the embedded workflow.

| Recipe | Example | Use it when |
| --- | --- | --- |
| `balanced` | <img src="docs/assets/krea-v9/demos/balanced.png" alt="Balanced Krea V9 demo output" width="220"> | One image should be a broad, general reference. |
| `keep the same subject` | <img src="docs/assets/krea-v9/demos/keep-same-subject.png" alt="Keep the same subject Krea V9 demo output" width="220"> | The object, product, person, or character must stay recognizable. |
| `suggest the visual style` | <img src="docs/assets/krea-v9/demos/suggest-visual-style.png" alt="Suggest visual style Krea V9 demo output" width="220"> | You want palette, medium, finish, and art direction without copying the style image's subject. |
| `copy lighting and mood` | <img src="docs/assets/krea-v9/demos/copy-lighting-mood.png" alt="Copy lighting and mood Krea V9 demo output" width="220"> | You want light direction, contrast, haze, glow, or atmosphere. |
| `suggest material or texture` | <img src="docs/assets/krea-v9/demos/suggest-material-texture.png" alt="Suggest material or texture Krea V9 demo output" width="220"> | You want a surface quality such as fabric, stone, ceramic, paper, metal, or paint. |
| `avoid copying text/logos` | <img src="docs/assets/krea-v9/demos/avoid-copying-text-logos.png" alt="Avoid copying text/logos Krea V9 demo output" width="220"> | A reference contains words, labels, UI, signs, symbols, or brand marks. |

## Example Workflows

| Workflow | Best for |
| --- | --- |
| [krea-v9-full-showcase-workflow.json](example_workflows/krea-v9-full-showcase-workflow.json) | First run. Shows content, style, material, lighting, and text/logo guard cards together. |
| [krea-v9-no-prompt-style-transfer-workflow.json](example_workflows/krea-v9-no-prompt-style-transfer-workflow.json) | Applying image 2's style to image 1 with no written prompt. |
| [krea-v9-reference-stack-workflow.json](example_workflows/krea-v9-reference-stack-workflow.json) | Compact starter graph for building your own multi-reference workflow. |

The examples intentionally avoid LoRA, model-enhancer, and switch-node plumbing
so the Krea reference nodes are easy to inspect.

## Good Starting Values

| Strength | Meaning | Good uses |
| --- | --- | --- |
| `0.00` | Off | Keep a card connected but inactive. |
| `0.03` to `0.08` | Tiny nudge | Text/logo guard, shape hints, stubborn prompts. |
| `0.10` to `0.25` | Gentle guidance | Layout, material, mood-board influence. |
| `0.25` to `0.45` | Strong guidance | Lighting, texture, pose, broad style. |
| `0.50` to `0.90` | Very strong | Content anchor or deliberate style transfer. Watch for over-copying. |

Tips:

- Start strengths low and raise slowly.
- Use `0.80` only when the main subject must stay stable.
- Lower `Image detail level` if a style image starts copying the wrong subject.
- Raise `Written prompt strength` when the text prompt should win over references.
- Use text/logo guard whenever a reference includes readable marks.

## Documentation

| Start here | What it contains |
| --- | --- |
| [V9 visual HTML guide](docs/krea-v9-user-guide.html) | Full visual walkthrough with all recipes and embedded-workflow demo PNGs. |
| [V9 Markdown user guide](docs/krea-v9-user-guide.md) | Same guide in Markdown form for GitHub reading. |
| [Documentation landing page](docs/README.md) | Short navigation by task. |
| [Node documentation index](docs/nodes/README.md) | Per-node input and output details. |
| [Technical paper](docs/krea-v9-technical-paper.md) | How and why the nodes work: architecture, math, verification, extension and porting guides. |
| [Example workflows](example_workflows/README.md) | What each bundled workflow is for. |
| [Testing guide](docs/testing.md) | Maintainer checks for contract tests and workflow validation. |

## Development Checks

The contract tests run without launching ComfyUI:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python -m compileall -q kg_krea_v9 __init__.py
```

## License

MIT. See [LICENSE](LICENSE).
