# Example Workflows

## Open directly in ComfyUI

The V11 files below are **native ComfyUI canvas workflows**, with nodes, links, widget values and canvas layout. They are not Photo Studio imports and do not need Photo Studio to run.

1. Install Krea Reference **0.5.0 or newer**, restart ComfyUI and refresh the page.
2. Download [V11 Reference starter — raw JSON](https://raw.githubusercontent.com/kgilper/krea-reference/main/example_workflows/krea-v11-reference-stack-workflow.json) or [V11 Concept Sliders — raw JSON](https://raw.githubusercontent.com/kgilper/krea-reference/main/example_workflows/krea-slider-v11-showcase-workflow.json). On a GitHub file page, use **Download raw file**; do not save the HTML page as JSON.
3. Drag the downloaded JSON onto the ComfyUI canvas, or use ComfyUI's workflow Open command.
4. Select installed Krea model files in the diffusion-model, text-encoder and VAE loaders. The saved examples use `krea2/krea2_turbo_nvfp4.safetensors`, `krea2/qwen3vl_4b_fp8_scaled.safetensors` and `krea2/qwen_image_vae.safetensors`. Folder separators vary by host. A compatible alternative model must be selected explicitly if those files are absent.
5. For the reference starter, copy the repo's `example_assets/krea-reference-examples` folder into `ComfyUI/input/krea-reference-examples`, or choose your own files in all three Load Image nodes. The assets are available in the GitHub repository; registry packages may not include them. Even the zero-strength card's connected Load Image needs a valid file. The slider showcase requires no input images.
6. Queue the workflow. Defaults are 1024×1536, eight Euler/simple steps and CFG1. The slider showcase also renders a plain comparison branch, so it runs two samplers. View the image previews and the stack reports.

Every Krea guide card, reference stack, concept card and concept stack in these V11 files is a V11 class, including negative/comparison branches. Their JSON `version: 0.4` denotes the ComfyUI canvas format, not the Krea node version. Standard Comfy nodes and shared socket types keep their usual names.

## V11 opt-in examples

- [Reference starter](krea-v11-reference-stack-workflow.json): the established reference topology with V11 classes; balance starts off. Replace the sample image filenames and select your installed models.
- [Concept Slider showcase](krea-slider-v11-showcase-workflow.json): six cards, combined budget 2, per-card presets/timing and a same-seed plain comparison. Start with one nonzero card. Near-zero values blend toward the plain prompt; larger changes can still reframe the subject.

See the [V11 guide](../docs/krea-v11-user-guide.md). Existing example files remain available unchanged.


## Prior-version examples

Older V9/V10/Slider V1 graphs retain their filenames for saved links. Their [workflow descriptions](../docs/previous-versions/native-workflows.md) and [versioned documentation](../docs/previous-versions/README.md) are archived separately.
