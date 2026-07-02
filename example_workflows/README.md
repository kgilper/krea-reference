# Example Workflows

This folder contains V9 starter workflows. The Load Image nodes use the included synthetic example filenames; copy `../example_assets/krea-reference-examples/` into your ComfyUI input folder, or replace the Load Image nodes with your own test images before queueing.

The examples intentionally avoid LoRA and model-enhancer plumbing so the graph stays focused on Krea plus the V9 reference nodes.

![Synthetic reference images included with Krea Reference](../example_assets/krea-reference-examples/contact_sheet.png)

## V9 Full Showcase

File: [krea-v9-full-showcase-workflow.json](krea-v9-full-showcase-workflow.json)

This is the best workflow for seeing the V9 controls together. It uses five cards:

- Content anchor: `keep the same subject`, strength `0.80`.
- Visual style: `suggest the visual style`, strength `0.65`.
- Material/texture: `suggest material or texture`, strength `0.35`.
- Manual lighting/mood: `manual tuning` with `lighting and shadows`, strength `0.45`.
- Text/logo guard: `avoid copying text/logos`, strength `0.03`.

![Krea V9 recipe demo output gallery](../docs/assets/krea-v9/demos/recipe-gallery.png)

## V9 No-Prompt Style Transfer

File: [krea-v9-no-prompt-style-transfer-workflow.json](krea-v9-no-prompt-style-transfer-workflow.json)

Use this when you want image 2's visual style applied to image 1 without typing a prompt. It starts with:

- Reference 1: `keep the same subject`, strength `0.80`.
- Reference 2: `suggest the visual style`, strength `0.65`.
- `Final image prompt`: blank.
- `Written prompt strength`: `0.0`.
- `When images guide`: `smart per-card timing`.

For product/object content with a person-style reference, lower Reference 2 toward `0.45`.

## V9 Starter Reference Stack

File: [krea-v9-reference-stack-workflow.json](krea-v9-reference-stack-workflow.json)

This workflow demonstrates the V9 Krea reference route:

```text
Load Image -> KG Krea 2 Image Guide Card V9 -> KG Krea 2 Reference Stack Encoder V9 -> sampler positive input
```

## Workflow Dependencies

The workflows require Krea 2 compatible model, CLIP, and VAE files in your ComfyUI model folders.

If your model filenames differ, update the loader widgets in the workflow after loading it.

## Related Docs

- [Krea 2 V9 visual user guide](../docs/krea-v9-user-guide.html)
- [Krea 2 V9 documentation index](../docs/krea-v9-documentation-index.md)
- [KG Krea 2 Image Guide Card V9](../docs/nodes/kg-krea-2-image-guide-card-v9.md)
- [KG Krea 2 Reference Stack Encoder V9](../docs/nodes/kg-krea-2-reference-stack-encoder-v9.md)
