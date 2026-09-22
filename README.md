# ComfyUI Krea Reference — V11

Guide Krea 2 with reference images and training-free concept sliders. **V11 is the current version to start with**, available in package 0.5.0 or newer. Existing V9/V10/Slider V1 workflows keep their original behavior.

![V11 reference-guided teapot example](docs/assets/krea-v11/reference-style.png)

V11 subject-plus-style guidance, using synthetic product and graphic references. See the [illustrated gallery](docs/krea-v11-gallery.md) for the inputs, settings and limitations.

## Start with V11

| What you want | Open |
|---|---|
| Guide an image with reference cards | [Native V11 Reference starter](example_workflows/krea-v11-reference-stack-workflow.json) |
| Adjust text-defined attributes | [Native V11 Concept Slider showcase](example_workflows/krea-slider-v11-showcase-workflow.json) |
| Install, connect nodes and understand controls | [V11 user guide](docs/krea-v11-user-guide.md) |
| Follow concrete prompts and recipes | [Nine worked examples](docs/krea-v11-worked-examples.md) |
| Inspect real V11 outputs | [V11 example gallery](docs/krea-v11-gallery.md) |

Download the raw workflow JSON and drag it into ComfyUI. Follow the [model/image setup instructions](example_workflows/README.md#open-directly-in-comfyui). These are native ComfyUI workflows; Photo Studio is not required. The reference example needs input images; the slider example does not.

The current slider showcase uses **automatic reach and budget**: card values determine the effective controls, up to the combined limit. This feature requires the latest GitHub source update after registry 0.5.0. See [automatic scaling](docs/krea-v11-user-guide.md#automatic-reach-and-budget) for migration and examples.

## Two V11 instruments

**Reference cards** assign jobs such as subject, visual style, lighting, layout or a counter-example to input images. Up to 12 cards feed the V11 reference stack. Sign-preserving balance limits signed layer targets; content/revision-aware caching speeds tuning. Recipes, including balanced, retain their established settings.

```text
Load Image → Image Guide Card V11 → Reference Stack Encoder V11 → sampler
```

**Concept Sliders** turn descriptions and paired endpoint text into attribute controls. Up to 8 cards feed the V11 slider stack. V11 adds automatic or manual combined budgeting, duplicate/opposite cancellation, per-card timing, height/crowd presets and a smoother transition near zero. No slider training or extra slider weights are needed.

```text
Concept Slider Card V11 → Concept Slider Stack V11 → sampler
```

| Plain prompt | V11 tiny adjustment | V11 working-range adjustment |
|---|---|---|
| ![Plain prompt baseline](docs/assets/krea-v11/slider-neutral.png) | ![Brightness plus0.05 in V11](docs/assets/krea-v11/slider-tiny-positive.png) | ![Brightness plus3 in V11](docs/assets/krea-v11/slider-brightness-positive.png) |

Same prompt and seed; brightness values 0, +0.05, +3. Tiny values stay closer to neutral, but stronger values can change shape and framing. Reference borders, fine-texture transfer and entangled attributes remain limitations. These are creative controls, not calibrated physical measurements. Reference and slider stacks are separate encoders; a combined image-anchor-plus-slider encoder is not included.

## Install

Install **Krea Reference** through ComfyUI Manager/Registry, or clone this repository into your ComfyUI custom_nodes folder:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/kgilper/krea-reference.git
```

Restart ComfyUI and refresh the browser. Select installed Krea 2 diffusion, Krea Qwen3-VL encoder and Qwen image VAE files. This repo does not ship model weights. See the [V11 guide](docs/krea-v11-user-guide.md) for exact node class names and host requirements.

## Recipes, implementation and prior versions

- [Custom recipe kit](custom_recipes/README.md) and Recipe Builder in `web/recipe-builder.html`.
- [V11 technical notes](docs/krea-v11-technical-notes.md), [node index](docs/nodes/README.md) and [testing](docs/testing.md).
- [Prior-version guides](docs/previous-versions/README.md): V10, V9 and Concept Slider V1, with their historical examples and technical papers.

Older nodes, assets and native workflows retain their original paths. Old guide URLs forward to their archive; no saved workflow is migrated automatically.

## Support and license

Krea Reference is free. Support development through [GitHub Sponsors](https://github.com/sponsors/kgilper?frequency=one-time), or contribute useful issues and examples. [MIT license](LICENSE).
