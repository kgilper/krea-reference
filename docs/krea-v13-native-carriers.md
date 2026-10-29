# Experimental native carrier studies V13

The opt-in V13 study builder retains selected literal pole-token output states.
V12 projects all pole rows away and keeps only their contextual effect on the
original native prompt positions. This can produce a measurable prediction
change with little visible response. Keeping those semantic carriers produced
useful signed illumination in the native comparison below.

## Setup and first comparison

Use V13 when you want to investigate native image editing with explicit text
endpoints. For the simpler reference-card and conditioning-slider workflows,
start with the [V11 guide](krea-v11-user-guide.md).

### Requirements

- Install or update this package from current GitHub source, then restart
  ComfyUI and refresh the browser. Registry package 0.5.0 predates V12/V13.
- Use a ComfyUI host with native Krea 2 support, its Qwen3-VL 4B encoder and
  Qwen image VAE. Select your installed model files; this package ships none.
  The demonstrated recipe also uses the General Edit V2 task LoRA.
- Grounded editing requires the original `Krea2EditGroundedEncode` implementation.
  Active consumption verifies [specific edit and Comfy sampler source revisions](krea-v12-native-studies.md),
  including the paired guider/model profile. A newer host is not automatically
  compatible; unsupported revisions fail before active sampling.
- To reproduce the enhancer-ON example, install a compatible
  [Krea2T enhancer](krea-v12-native-studies.md#optional-pinned-native-enhancer).
  It is optional when disabled. There is no additional pip dependency.

### Wiring the grounded image-edit path

Keep the native model, conditioning, source and target latents together. The
V13 nodes wrap the native guider rather than supplying a conditioning output
for a basic KSampler.

1. Load the Krea model, encoder, VAE and task LoRA. If using the enhancer, send
   the task-selected MODEL through `KGKrea2NativeEnhancerV12` **before** edit
   preparation. Use its `native_model` as `Original MODEL before edit patch`.
2. In `KGKrea2PrepareOwnedGroundedContextV12`, connect the clean source image,
   its native source latent, native target latent, Krea CLIP and VAE. Enter the
   final image prompt and an explicit context revision. Use a fresh revision
   when changing source images or preparation inputs.
3. Connect its `native_context` to `KGKrea2PrepareNativeTargetV12` and turn
   `Native target preparation enabled` ON. Send this node's context output to
   V13 studies and its `native_target_latent` output to
   `SamplerCustomAdvanced.latent_image`.
4. Build a `CFGGuider` from the owned preparation node's `native_model`,
   `native_positive` and `native_negative`; set **CFG to 1**. Use that same
   native model for the scheduler.
5. Make one `KGKrea2NativeAxisV12` card with the illumination ID, revision and
   literal poles [shown below](#verified-signed-illumination-comparison).
   Set `Sampling timing` to `throughout`. Connect `native_axis` to
   `Native axis 1` on `KGKrea2NativeCarrierStudiesV13`.
6. On V13 studies, keep `Native coefficient budget` at 2 and
   `Early-to-final handoff` at 0.4. Connect `carrier_studies` and the original
   `CFGGuider` to `KGKrea2NativeCarrierPhaseGuiderV13`. Send its output to
   `SamplerCustomAdvanced.guider`, alongside the existing native noise,
   sampler and sigmas. Decode the result with the same VAE.

| From | To |
|---|---|
| V12 owned preparation: `native_model`, `native_positive`, `native_negative` | Native `CFGGuider`: model, positive, negative |
| V12 target preparation: `native_context` | V13 studies: `Native context` |
| V12 axis card: `native_axis` | V13 studies: `Native axis 1` |
| V13 studies: `carrier_studies` and original CFGGuider output | V13 phase guider: `Carrier studies`, `Native guider` |
| V13 phase guider and V12 target preparation: `native_target_latent` | `SamplerCustomAdvanced`: guider, latent_image |

First compare coefficient **0**, **−1** and **+1**, keeping source, prompt,
seed, model, task LoRA and sampling settings fixed. Zero is the native baseline.
Use the exact recipe below for comparison with these published results.
In the demonstrated Studio adapter these endpoints appear as −100/0/+100;
the ComfyUI axis card takes native coefficients, not those display amounts.
No general calibration between the two scales is claimed.

### If something does not work

| Symptom | Check |
|---|---|
| Missing V12/V13 nodes | Update the Git installation, restart ComfyUI, refresh the browser and check startup errors; avoid duplicate package folders |
| Port will not connect | Use the V13 builder and V13 guider together; V12 studies have a different type |
| CFG or source-compatibility error | Use CFG 1 and the documented dependency profiles; keep native model/conditioning/latent handles from the same prepared context |
| Prepared-target mismatch | Enable V12 target preparation and feed its same context/LATENT pair to studies and sampler |
| Enhancer error | Check its pinned dependency and place it before edit preparation; OFF bypasses the optional package |
| Little visible change | Verify nonzero coefficient, active timing and literal poles; compare fixed-seed renders rather than treating a successful study report as visual proof |

The diagnostic nodes are separate instruments with extra predictions. They are
not part of this ordinary image comparison. Broader concepts, mixed axes,
intermediate amounts and donor/mask quality still need their own validation.

## Verified signed illumination comparison

These are actual native slider results from the same synthetic source scene and
preservation prompt. The signed images use source revision
[`97c5626`](https://github.com/kgilper/krea-reference/commit/97c5626eb1fd015df628b02f29320265818851ae).
The neutral is the unchanged native path. Both raw decodes and restored outputs
were inspected: dimming/brightening is visible and the teapot, cup and cubes keep
their broad geometry, materials, arrangement and viewpoint.

| Native coefficient −1 | Native neutral, 0 | Native coefficient +1 |
|---|---|---|
| ![V13 darker scene](assets/krea-v13/illumination-minus.png) | ![Native neutral scene](assets/krea-v13/illumination-neutral.png) | ![V13 brighter scene](assets/krea-v13/illumination-plus.png) |

The files preserve the exact rendered pixels and original compressed PNG image
data. Only the private embedded prompt/workflow metadata was removed. They are
not regenerated, retouched, brightness-adjusted or replacement illustrations.

| Setting | Value |
|---|---|
| Diffusion model | Krea2 Turbo INT8 ConvRot |
| Task LoRA | General Edit V2, strength1 |
| Text encoder / VAE | Qwen3-VL 4B FP8 scaled / Qwen image VAE |
| Seed | 581102 |
| Sampling | Euler, simple scheduler, eight steps, CFG1, denoise1 |
| Grounding / reference | 768 grounding pixels; reference boost4; fit, aligned |
| Enhancer | ON, strength1; registered before native edit |
| Native axis | `illumination`, revision `krea-illumination-instruction-v2:1` |
| Coefficients / budget / timing | −1, 0, +1; budget2; Throughout; handoff0.4 |
| Image size | Raw1024×1024; restored1000×1000 |
| Scope | One source, full frame, no donor or selection mask |

The image prompt stays identical in all three cases:

> Keep the same studio still life: gray teapot and gray cup in front of red and blue cubes. Preserve their shapes, arrangement, materials and viewpoint.

Literal positive pole:

> Relight the entire scene with much brighter, high-key studio illumination and noticeably lifted shadows. Bright clear lighting with strong illumination.

Literal negative pole:

> Relight the entire scene with much dimmer, low-key studio illumination and noticeably deeper shadows. Dim lighting with low illumination and deep shadows.

The poles enter through the axis card; the signed runs do not replace the image
prompt. Changing only the pole wording in the older projection-only construction
remained visually neutral. The carrier construction at the same coefficient and
budget produced the visible pair shown here.

Mean encoded-sRGB709 brightness is56.59 /153.59 /175.99 for dim/neutral/bright;
this is an image statistic on0..255, not photometric luminance. Raw outputs have
the same ordering, so aspect restoration retains the effect. This establishes
one visible synthetic illumination case. It does not establish a general
−100..100 calibration, monotonic intermediate amounts, other concepts, mixed
axes, or live donor/selection-mask quality for V13. Existing V12 widgets and
saved workflows remain unchanged.

## Connect the experimental nodes

Connect the existing owned native context and versioned V12 axis cards to
`KGKrea2NativeCarrierStudiesV13`, then connect its distinct carrier-studies output
and the original native CFG guider to `KGKrea2NativeCarrierPhaseGuiderV13`.
The output is a GUIDER for the existing supported native sampler path. Existing
nodes and saved workflows retain their current behavior. This is a research
interface; source tests alone do not establish useful effects or calibration.

All studies use one native token row, the original prepared source/donor images,
and the existing owned muting mechanism. For A active axes, the builder makes
1+2A text-encoder passes. At original native output positions it keeps exactly
the existing N+sum(w*(P-M)) arithmetic. For each active axis it additionally
retains only its selected plus or minus literal span from the corresponding
real native encoder pass, in original row order. At magnitude one these added
states are the exact selected encoder states; at other magnitudes they interpolate
or extrapolate from that span's muted-base states. The unselected pole is omitted.
No independently tokenized completed encodes are padded together, and no tap
gain or source-image conditioning gain is added.

Coefficients use the existing explicit native units, sign, per-phase timing,
canonical cancellation, and combined budget. They are not calibrated -100..100
amounts. Zero, empty, fully cancelled, and inactive phases retain original native
identity. Near zero, the existing V12 native/steered branch taper is preserved.
The V13 guider requires CFG1 both when bound and when sampling starts. It selects
at most two native positive conditioning branches. With the native CFG1 evaluation
used in the verified recipe, an eight-step run is conservatively budgeted at
sixteen branch evaluations. There are no diagnostic counterfactual predictions.

Admission retains the existing maximum eight axes, 8192 expanded tokens, and
1179648 prepared image pixels, and additionally limits all literal pole spans
together to 512 tokens before study encoding. The original native source checks,
negative conditioning, target latent, noise mask, source/donor handles, encoder
cleanup, and native sampler delegation remain in force. No model weights,
training, persistent hook, solver replacement, or application-default migration
is introduced. Reverting a workflow to its V12 builder/guider disables this
experimental construction.
