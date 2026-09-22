# Krea V11 worked examples

[View the V11 example gallery](krea-v11-gallery.md): synthetic reference inputs, reference-guided outputs, a slider value comparison and the native showcase result.

![V11 example output](assets/krea-v11/reference-style.png)

These examples use the four V11 node classes listed in the [user guide](krea-v11-user-guide.md). They are starting points for controlled exploration, not guarantees of identity preservation or perfectly isolated edits. Keep the seed fixed while comparing settings. Change one control at a time, then try several seeds before choosing a setting.

The two downloadable ComfyUI graphs are [Reference starter](../example_workflows/krea-v11-reference-stack-workflow.json) and [Concept Slider showcase](../example_workflows/krea-slider-v11-showcase-workflow.json). Load them as workflows, select your installed model files, and replace reference-image placeholders. Both contain V11 cards and V11 stacks throughout. Examples below describe edits to those graphs; they are not additional downloaded workflows.

## 1. Preserve a product, then borrow a graphic style

Use a clean photograph of one product for reference A and artwork for reference B. A simple background in A makes unwanted background borrowing easier to diagnose.

**Final image prompt:**

> An amber ceramic teapot with a cobalt blue handle on a pale stone pedestal. Apply a coral and cyan botanical graphic finish while retaining the teapot's recognizable shape. One product, centered studio composition.

| V11 guide-card control | A: product | B: artwork |
|---|---|---|
| Use image for | keep the same subject | suggest the visual style |
| How strongly this image guides | 0.9 | 0.55 |
| Prepare image by | use image as-is | use image as-is |
| Guide direction | toward this image | toward this image |
| When this card guides | recipe decides | recipe decides |

On the V11 reference stack, start with written prompt strength 1, medium study detail (384), full-image framing and balance off. First set B's strength to zero and render the product anchor. Restore B to 0.55 and compare. Try gentle sign-preserving balance as a separate comparison; it can reduce the anchor as well as the style when the combined layer targets exceed its budget.

**Inspect:** shape, handle/spout placement, background ornaments, and whether the requested style reaches the product or only its surroundings. The controlled synthetic tests sometimes showed less graphic framing with V11 balance, but watercolor-like borders still appeared and fine textile detail transferred weakly. If you see a decorative frame, reduce B and simplify its input; increasing study detail or cropping is not a proven general cure.

These 0.9/0.55 values reproduce the main two-card strength setup used in the synthetic comparisons. They are strong inputs, not universal defaults.

## 2. Reproduce the downloadable reference starter

The starter's prompt is `two people standing in a field`. Its three V11 cards begin at:

| Card | Recipe | Strength |
|---|---|---:|
| Pose/layout reference | copy pose and layout | 0.14 |
| Style reference | suggest the visual style | 0.28 |
| Optional text/logo reference | avoid copying text/logos | 0 |

Replace all Load Image filenames, even the zero-strength card's image: a connected Load Image node still needs a valid file. Alternatively disconnect and remove that unused image/card pair. The stack starts with written prompt strength 1.15, medium detail, smart timing and balance off. Its negative conditioning also comes from a V11 reference stack.

Queue once with only the pose/layout card active, then restore the style card. Inspect the `prepared_references` preview before raising strength. This preview is the processed study input, not the generated output. A blurred or desaturated prepared reference can encourage softness or a color change; the preview helps reveal that cause.

## 3. Use a reference as a counter-example

Start from an accepted positive reference setup. Add a V11 card showing the unwanted layout. Choose `copy the camera framing`, strength 0.1, `Guide direction = away from this image`, and `When this card guides = early layout only`. Keep the other cards unchanged.

Compare the added card at zero and 0.1, with the same seed. Then compare balance off versus gentle sign-preserving balance. Under V11 balancing, negative layer targets remain negative and zero targets remain zero. This is the mathematical contract; it does not mean the model understands a precise prohibition. An away card can move the subject or change the camera instead of removing the unwanted property.

Use a precise prompt to describe the desired alternative. Avoid using a reference full of unrelated unwanted objects: moving away from its whole learned contribution is broader than removing one object.

## 4. Make a brightness slider and compare it with plain generation

Open the slider showcase. Set every card to zero, then activate only the brightness card. The showcase has a same-seed comparison branch without cards.

**Final image prompt:**

> An amber ceramic teapot with a cobalt blue handle on a pale stone pedestal, clean studio photograph.

| Control | Setting |
|---|---|
| What this slider changes | brightness |
| Slider preset | custom or automatic |
| Positive/negative pole fields | leave both empty |
| When this slider guides | whole image |
| Overall slider reach | 1 |
| Combined slider budget | 2 |
| Early-to-final handoff | 0.4 |

Render values `0`, `-0.05`, `+0.05`, `-3`, `+3` using a fixed seed. Zero is the plain-prompt baseline. Tiny values test continuity; +/-3 tests the working range. V11 transitions toward plain conditioning below total applied axis weight 0.25, so near-zero changes should be gentler. The threshold is an internal coefficient, not a slider value of 0.25; for one whole-image slider at reach 1, it corresponds to an absolute slider value of 0.75.

In the ten-seed synthetic brightness benchmark, V11 stayed closer to the zero image in all 20 tiny-value comparisons. Mean absolute RGB difference fell from 37.52 to 5.02 on a 0–255 scale. This measures continuity for one model/prompt, not general photographic quality. Larger values can still redesign the teapot or reframe it.

## 5. Write concrete custom poles

Choose `custom or automatic` and name a single attribute. Describe both ends with parallel wording. For example, this uncalibrated warm/cool experiment keeps the subject description matched:

| Field | Text |
|---|---|
| What this slider changes | illumination warmth |
| What +6 looks like (optional) | the same product photograph illuminated by warm amber light |
| What -6 looks like (optional) | the same product photograph illuminated by cool blue light |

Start at +/-2, whole-image timing, reach 1 and budget 2. Compare both directions. If the product changes material or the background changes, reduce the amount and simplify the poles. Wording that says “the same” is an intention, not an identity lock.

Do not put extra properties such as “luxurious glossy studio shot” into only one pole; that asks the axis to change several things. Filling both fields makes the two endpoints explicit. With a preset selected, your nonempty text overrides that corresponding preset pole; the other endpoint still comes from the preset. With automatic mode, a blank endpoint uses generic maximum/minimum wording derived from the attribute.

## 6. Try the built-in height and crowd presets

| Preset | Suitable prompt | First comparison |
|---|---|---|
| person height | Full body photo of a man standing in a city park, natural light, both shoes visible. | 0, -3, +3 |
| plaza crowd | A wide photograph of a public plaza with pedestrians, late afternoon daylight. | 0, -3, +3 |

Leave explicit pole fields empty to use the preset. The height preset describes a man with long legs at the positive end and a short compact stature at the negative end. Use custom wording when that subject description does not fit. The crowd preset contrasts a densely packed plaza with a deserted plaza and bare pavement.

The synthetic comparisons showed a clear dense-crowd direction in some outputs, but the decrease direction did not reliably empty the scene. Height could change clothing, anatomy and framing; some negative examples cropped the head. Neither preset is a measured height/count control. Preserve your neutral image and judge the entire frame, not just the requested attribute.

## 7. Separate early layout and final detail influence

With only brightness at +3, render three variants: `whole image`, `early layout only`, and `final details only`. Keep the handoff at 0.4. Early influence applies before the handoff; final influence applies afterwards. The handoff is a sampling-progress boundary, not a spatial mask and not a guarantee of an exact integer number of steps.

In an inactive slider phase, V11 uses plain prompt conditioning. Late brightness can preserve more of the early composition in some images, but its effect can be weaker or different. Choose by comparison rather than assuming “final details” means structure cannot change.

A handoff of 0 leaves no early-only interval; a handoff of 1 leaves no final-only interval. If you want both phase types, use an interior value such as 0.4. Reference-card timing is separate: choose smart per-card timing in the reference stack and set each reference card's timing there.

## 8. Understand duplicate, opposite and competing sliders

At reach 1, one full-range slider value +6 contributes coefficient 2. Two identical +6 cards request coefficient 4 together; the default budget 2 scales their combined contribution back to 2. Adding identical cards is therefore not a way around the budget. Different axes share the same per-phase budget and may both become weaker when you add another active card.

Try two cards with exactly the same description/poles and values +3 and -3. With matching timing they cancel and V11 uses the plain prompt. If one card is early-only and the other final-only, they act in different intervals and do not cancel across the whole run. Reversed identical pole pairs are oriented consistently before combining.

Semantically related but differently written poles are not automatically identified as duplicates. The budget bounds coefficients; it does not measure perceptual interference. Raise the budget only after you understand the individual axes. Setting budget or overall reach to zero is a quick exact plain-prompt comparison.

## 9. Tune efficiently and diagnose reports

1. Keep study reuse on while adjusting values, balance or timing.
2. Connect the reference `stack_report` or slider `slider_report` output to Preview Any.
3. Compare encoder-pass counts across runs. A cached tuning run can report zero new encoder passes; that does not mean the sampler is skipped.
4. Changing prompt/poles/reference content can require new studies. A different model patch revision also invalidates reuse.
5. Choose `always re-study` after an in-place model modification that does not update Comfy's patch revision, or when diagnosing suspected stale studies.

The cache is bounded, so switching among several setups can evict old studies. Near-neutral slider blending may require an additional denoiser branch; cheaper text-encoder reuse does not remove that sampling cost.

## Troubleshooting

| Symptom | What to inspect or try |
|---|---|
| V11 node is missing | Install package 0.5.0 or newer, restart ComfyUI, refresh the browser and search the full V11 node name. A displayed title alone does not identify the class. |
| Unsupported token-span muting error | Use a compatible Krea Qwen3-VL encoder/Comfy host. Do not substitute an unrelated CLIP model. Zero bypass does not prove active-slider support. |
| Slider has little effect | Verify nonzero value, reach and budget; check cancellation, timing endpoints and report poles. Improve wording before adding reach. |
| One slider weakens when another is added | Inspect combined per-phase budget scales. This can be intentional budget sharing. |
| A negative value changes the wrong thing | Inspect both poles; negative means toward the negative sentence, not a generic undo operation. |
| Style adds a frame or source objects | Inspect prepared references and reduce the style card. This remains a known limitation. |
| Texture does not appear | More strength/detail is not a guaranteed cure. Keep a successful anchor and compare clean, relevant reference inputs. |
| Old card plugged into a new stack works, but a preset does not | Compatibility packets are accepted, but old cards do not provide V11 preset/timing fields. Use V11 cards in V11 workflows. |
| Studio provider cannot be found | Import the portable Studio package and include disabled workflows in Admin Workflows. Source files alone do not create a database entry. |

## Safe migration and comparison

Save a separate workflow copy. Replace every reference card and reference encoder—including negative/comparison branches—with their V11 classes. For sliders, replace every card and stack. Reconnect links, copy controls by label, and set V11 balance labels explicitly. Never rename an old node's display title to make it appear upgraded. Load the provided V11 graph when unsure about widget ordering.

All public V11 examples and Studio V11 packages use V11 card/stack classes. Ordinary Comfy loaders, samplers, the existing LoRA loader and model enhancer keep their own class names; they do not have a Krea Reference V11 replacement. Shared link types `KG_KREA_REFERENCE` and `KG_KREA_SLIDER` are compatibility contracts, not old node versions.

Rollback by reopening the saved V10 or Slider V1 workflow. V11 installation does not migrate those graphs, and the `balanced` recipe remains unchanged.
