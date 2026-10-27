# Krea V12 native preparation and studies

V12 adds an experimental developer interface for studying semantic poles in the
same source/donor context as a native Krea encode. A thin developer consumer
delegates to pinned native Comfy Euler, Euler ancestral or ER-SDE sampling; **this is not a model-validated
or supported combined generation/edit workflow.** V11
remains the supported starting point. Existing nodes and recipe tables retain
their behavior.

The implementation is original integration code that calls host interfaces. It
does not bundle model weights or upstream encoder/edit runtime implementations.
Use the repository's normal custom-node installation. Grounded preparation also
requires the original `Krea2EditGroundedEncode` node. There is no new pip package
or model asset to install for this interface.

## Nodes and ports

| Class | Inputs | Output |
|---|---|---|
| `KGKrea2PrepareNativeContextV12` | Native CLIP/MODEL, positive/negative prompt, explicit context revision; optional clean source/donor, original source/target latent and noise mask | `KG_KREA_NATIVE_CONTEXT_V12` |
| `KGKrea2NativeAxisV12` | Explicit canonical axis ID/revision, literal positive/negative poles, native coefficient, timing | `KG_KREA_NATIVE_AXIS_V12` |
| `KGKrea2CombinedNativeStudiesV12` | Native context, up to eight native axes, coefficient budget, handoff | `KG_KREA_NATIVE_STUDIES_V12`, report |
| `KGKrea2NativePhaseGuiderV12` | Actual studies and their original native `CFGGuider` | Native `GUIDER` protocol proxy; neutral returns original guider |
| `KGKrea2PrepareOwnedGroundedContextV12` | Original MODEL before edit patch, clean source/donor, source/target latents, VAE and exact native patch/preparation arguments | Context plus native MODEL, positive, negative, target latent |
| `KGKrea2RemoveOwnedReferenceV12` | Owned grounded context, `native:donor` OFF | Rebuilt context plus its native MODEL, positive, negative, target latent |
| `KGKrea2NativeEnhancerV12` | Native MODEL before edit patch, enabled (default OFF), strength0..2 | MODEL plus attachment report; OFF/strength0 returns original MODEL |
| `KGKrea2PrepareNativeTargetV12` | Final native context and enabled (default OFF) | Prepared context plus its exact shared native target LATENT |

Optional native positive and negative conditioning inputs must be connected
together. They adopt the existing paired encodes without re-encoding. Otherwise,
the preparation node calls the original native encoder for both prompts. The
grounded path delegates sizing and template construction to the installed edit
node. Native image order is source first, donor second. A donor without a source
is rejected. Drawing interpretation belongs before this interface; provide clean
renderer images.

The three custom context/axis/study port types hold in-process objects. Do not
persist native handles in JSON or send them over an application API. Study
output goes through the explicit native guider consumer, never directly to a
conditioning input. The guider protocol uses the original native sampler route.

Native coefficients are finite numbers from -6 through +6. Zero is neutral.
They are **not** a calibrated conversion of a shared user-facing percentage or
semantic range. Canonical identity/revision must be explicit; similar text does
not imply interchangeable axes. Equal and opposite coefficients cancel only
within the same declared axis/revision and overlapping phase. Conflicting poles
under one identity/revision reject the whole study request.

## Preparation and ownership

Positive studies preserve one exact native image/template/prompt token row.
Each literal pole is tokenized as text only; its nonempty payload and two owned
trailing Qwen newline tokens are inserted after complete source/donor vision
blocks and before original prompt content tokens, including separate leading whitespace.
This makes the poles causally visible to the original prompt positions. The
original prompt is never retokenized with added text: byte BPE can otherwise
merge punctuation or whitespace and change native tokens. Verified user-opening
newline carriers198/271/1406 stay whole before the poles, including any leading
newlines carried by that token. No later whitespace is skipped. Native output
stripping is tracked separately: Krea retains the user-opening tokens for merged
carriers271/1406. Unknown carriers reject; original tokens are never split.
Leading newlines after a complete image block remain prompt tokens. Incomplete image
blocks, images outside the native prefix and unowned control/media tokens reject.
All pole spans, including their delimiters, are owned before a combined encode.
Deleting every owned span must recover the original token objects, weights,
image handles/order and suffix exactly. Pole payloads containing special/control
or media tokens reject. This is token-level assembly before encoding, not a join
of finished encodes. The implementation resolves token coordinates,
expanded input coordinates and coordinates after native template stripping.
Image indices and extents must match the host's reported preparation. Every
encode verifies output shape and attention-mask extent. Image gains, when used
through the internal hook interface, scale both initial image features and all
three visual deepstack contributions.

Before axis arithmetic, each study projects onto the original native output
positions. All owned pole positions are removed through indexed selection
within that one study. The retained source/image/prompt and assistant-suffix
tokens must exactly match the original native sequence. The projected extent
must also match the actual native positive conditioning. Thus extra masked pole
positions are not passed to a consumer that ignores its conditioning mask.
This projection still requires real-tokenizer/model validation.

Each active phase composes the projected signed contrasts onto the adopted
original native positive: `N + sum(weight * (plus - minus))`. The all-muted
combined-row study still runs and is counted and validated, but does not replace
the native anchor or its metadata. This avoids adding an all-muted-base offset
shared by both signs. The existing low-load native/steered branch taper remains
unchanged. This arithmetic correction does not establish visual calibration.

One exclusive lease covers a study sequence, including CLIP clones sharing an
inner encoder or transformer. Missing hooks, existing instance hook overrides,
changed layout or intervening foreign mutations fail. Cleanup removes only owned
hooks and preserves foreign replacements. Other extensions must cooperate with
resource ownership; this plugin cannot lock uncooperative external code.

The source compatibility boundary is Krea's twelve Qwen3-VL-4B output taps
`[2,5,8,11,14,17,20,23,26,29,32,35]`, each width2560. The vision tower's three
deepstack injections are a separate mechanism. Grounded delegation checks the
edit node source at commit `13ef60f20828949becada815d3cbc371eb5ccaab`, Git blob
`e924efbd930e03e3b00cb040d177992a08b462b4`, allowing CRLF normalization. A matching
source file is a compatibility check; model/task support still requires tests.

Initial scope is one unweighted `qwen3vl_4b` token row and image batch1, with at
most source plus donor. Reject token truncation, boundary merges into original
content, unsupported embedding types and unexpected pooled output. Other image
recipe cards are not supported by this study interface. No persistent study
cache is used. Defaults bound study passes20, token/expanded extent8192 and total
prepared RGB image pixels1,179,648. These are admission limits, not measured peak
memory guarantees. Image expansion is checked before text-transformer evaluation;
vision preparation must first run to report its actual expanded extent.

## Neutral, timing and native state

The Python `prepare_context(..., native_bundle=bundle)` interface adopts a complete
existing bundle by identity, including arbitrary external fields. The caller
supplies the actual original preparation inputs and a new context revision when
they change. Existing MODEL, positive/negative, source/target latent, mask and
foreign metadata handles are retained. Mutation checks cover patch revisions,
wrapper metadata, callback identity and available handle version counters. They
are not image-content checksums; in-place changes without version counters
require a new caller revision.
Inference-mode tensors explicitly carry an unversioned-inference marker: their
throwing version property is not read. Identity and the caller's revision remain
binding, but in-place writes to these tensors cannot be detected. A changed input
requires new preparation and a new revision. Unknown version-getter failures
still reject; they are never treated as evidence of immutability.

Zero, exact cancellation, budget0 and empty timing windows do not tokenize poles,
prepare images or run extra encodes. The entire adopted native bundle is returned
unchanged. Native image references stay active. Reference OFF is a different
operation. An adopted context rejects removal because it lacks complete native
MODEL/source-latent rebuilding ownership. An owned grounded context can remove
its optional `native:donor`: it rebuilds from the original MODEL before the edit
patch, delegates the original model patch and VAE priming with donor image/latent
arguments absent, and re-encodes both native conditionings with source only.
The source, target latent/noise mask, foreign model options and external bundle
fields stay owned by their original paths. No already-patched MODEL is patched
again. Because the native wrapper uses separate earlier/last reference controls,
the remaining source keeps its previous earlier-reference gain and placement
when it becomes the only reference. The departed donor's reference-space boost
mask is removed; the target latent noise mask is retained. Core source OFF and
arbitrary reference recipe cards remain unsupported.
An owned donor requires its native VAE pixel path or a valid donor latent packet.
The vision-only crop combination with neither is rejected before patching or
encoding, because it does not establish a second MODEL reference to remove.
Owned reconstruction and VAE priming take the same shared-model resource lease
as native consumption, rejecting overlap before native patching or encoding.

Timing values are `throughout`, `early-layout`, `final-details`. Studies hold two
phase bundles. The Python research join `for_step(model, i, N)` selects early when
`i/N < handoff` and final otherwise, over actual active steps `i=0..N-1`. Exactly
one phase owns the boundary. An inactive phase returns the native bundle. This
method is called by the thin native consumer below; installed model behavior
still requires separate validation.
Timing never substitutes for a spatial mask.

The aggregate per-phase coefficient budget only attenuates coefficients; it does
not amplify small requests. Below total absolute coefficient0.25, native and
extended-layout conditioning are carried as separate weighted branches to taper
layout activation. No finished encodes are padded or concatenated. This is source
mechanics, not evidence of perceptual continuity or cross-model calibration.

## Optional pinned native enhancer

`KGKrea2NativeEnhancerV12` calls the original installed Krea2T numeric helper.
It adds no weights and changes neither the prompt, task LoRA nor sigma schedule.
The default is OFF. OFF or strength0 returns the exact input MODEL without
loading the optional package or reading its source. Active strength is0..2.

The supported source reference is the surviving
[Krea2T fork at e1f60f79](https://github.com/Ezgons123/ComfyUI-Krea2T-Enhancer/tree/e1f60f79e168c62b1cb1cf773dfb3ae4ee2292e2).
The original repository URL currently returns404. The integration verifies the
installed `ComfyUI-Krea2T-Enhancer` class source Git blob
`c46e1c3ed244caaef231c580bb601ea935b3d1c7` and the pinned native text-fusion source
before attachment. The separately reviewed source blob
`31e24388a8d495a524f46371659d3087e2302664` is also admitted: its basic enhancer
functions, class and numeric constants are identical, with only additional
imports/registrations for independent utilities. Loaded helper code and constants
must match the admitted source; a matching file alone is insufficient.
It delegates the original helper's two text-fusion paths and
bounded token delta; no upstream numeric implementation is bundled here. The
separate package retains its own MIT notice. Model and task-weight terms remain
separate from plugin code; this source compatibility check makes no commercial
model-use assertion.

Connect the task-selected MODEL after ordinary LoRA loading to this node, then
send its MODEL to owned grounded preparation. For text generation, send it to
the native context, guider and scheduler. The enhancer wrapper must precede
`krea2_edit`: that edit wrapper calls its own forward and bypasses inner wrappers.
Applying enhancement after an edit patch rejects. Optional donor OFF rebuilds
from the same enhanced original MODEL, preserving task routing.

Only the enhancer helper is used. The package's phrase encoder, Turbo sigma
scheduler, character loader and advanced text-scale utility are independent
features. Raw removal retains its Raw checkpoint, task LoRA, CFG and schedule;
it does not inherit the Turbo scheduler. Both Raw and Turbo use the native
12x2560 fusion interface, but each task still needs installed-model effect tests.

Active calls take an exclusive shared-fusion lease, install one temporary forward
hook and remove only that hook on success or error. Foreign hooks are rejected
or preserved on conflict. Duplicate enhancers, changed wrapper order, unexpected
tensor shapes or a sampling path that never invokes text fusion fail explicitly.
No step/debug counters are stored in model options. This verifies invocation and
cleanup; it does not promise improved prompt adherence or visual quality.
Admission also checks the actual fusion instance and its two layerwise/two
refiner block instances against the admitted native classes and captured bound
forward methods. Instance forward/call overrides, stale classes, compiled call
paths and local forward hooks reject before installing the owned fusion hook.
This is a check of those invoked modules, not a general audit of model internals.

## Verification and remaining integration

Run the focused synthetic checks with:

```bash
python -m unittest discover -s tests -p test_krea_v12.py -v
python -m compileall -q kg_krea_v12 __init__.py
```

The fixtures exercise original-delegate calls, source/donor order, paired
negative retention, expanded positions, deepstack gains, neutral identity,
budgets, exclusive phases, resource limits and failure cleanup. They use no
model or image files and establish no neural or visual result.

Raw active `sampler_conditioning()` export raises an error. The current grounded
edit consumer discards the conditioning attention mask. Owned output projection
addresses the extra pole positions in source; a complete consumer must verify
the projected native layout through the actual text-fusion path. Turbo/Raw task
coverage, installed enhancement compatibility, real-tokenizer/tensor checks,
near-zero behavior and visual strength calibration remain unverified. A source
study product must not advertise these capabilities as supported.

The V12 guider consumer delegates to the existing `CFGGuider.sample`, its native
conditioning conversion/preparation, native `KSAMPLER.sample`, Euler evaluation,
CFG and callbacks. It temporarily selects a preprocessed positive phase on that
same guider; paired negative, grounded MODEL wrapper and original CFG callbacks
are retained. It adds no solver or model forward. Native latent samples and the
latent noise mask must match the context by identity. That noise mask is separate
from a conditioning-area mask, which is unsupported by this initial consumer.

The native `SamplerCustomAdvanced` prepares latent channels, dimensions and empty
latent resolution before it calls the guider. For the active consumer, place
`KGKrea2PrepareNativeTargetV12` after the final native context (including any owned
grounded rebuild or reference removal). Enable preparation, connect its context
output0 to `KGKrea2CombinedNativeStudiesV12`, and connect its LATENT output1 to
`SamplerCustomAdvanced.latent_image`. Both branches then share the exact prepared
target; the original source latent, model, conditioning and mask remain bound.
The original seven node interfaces are unchanged.

This node delegates transformation to the installed
[`fix_empty_latent_channels`](https://github.com/Comfy-Org/ComfyUI/blob/v0.41.0/comfy/sample.py).
It consumes the raw spatial/temporal downscale markers so the sampler cannot
resize the already prepared empty latent again. The reviewed Krea2 configuration
uses [`Wan21`](https://github.com/Comfy-Org/ComfyUI/blob/v0.41.0/comfy/supported_models.py);
that format inherits the identity `LatentFormat.fix_empty_latent` method from
[`latent_formats.py`](https://github.com/Comfy-Org/ComfyUI/blob/v0.41.0/comfy/latent_formats.py).
Selected helper/utility/format source, actual loaded functions, format class and
normalization attributes must match before preparation. The prepared B1 image
latent has sixteen channels and one temporal position; the sampler's second
native preparation preserves its samples identity. Unsupported formats reject.
For an owned grounded context, preparation must retain target spatial dimensions:
its native edit wrapper has already primed the VAE cache for that size. A spatial
resize at this stage rejects rather than causing a hidden VAE re-encode during
sampling. Channel/dimension normalization at the same image size remains allowed.

The output carries an in-process provenance receipt binding the original packet,
prepared packet, exact model, format and helper functions. Context verification
checks the receipt before consumption; same-valued replacement tensors, changed
masks/packets/model revisions or replaced helpers reject. Ordinary tensor version
counters are retained; inference tensors still require a fresh caller revision
after in-place writes. No target values are compared as a substitute for identity.
Disabled preparation returns the original context and target by identity before
host reads or helper calls. Neutral routing can omit or disable this node.

Initial consumption requires the exact pinned Krea2/CFGGuider/KSAMPLER classes,
default Euler, Euler ancestral or ER-SDE options, B1 matching noise/latent shapes and a
strictly decreasing bounded accepted sigma schedule. Each evaluation must match
its next actual schedule sigma; each native callback must confirm the accepted
step. Duplicate, drifting or unknown evaluations fail. Shortened schedules use
their actual active count. No generic inclusive timestep window is installed.
For ER-SDE, the expected schedule uses the original host's
`offset_first_sigma_for_snr` with the actual model sampling object, matching its
first-sigma adjustment for CONST models. The input sigmas and original solver
remain unchanged. Source math probes confirm one evaluation/callback per step;
real-host/model acceptance remains separate.
Grounded consumption also requires the original single `krea2_edit` wrapper.
Actual converted guider entries must match native conversion, including empty
initial `model_conds` and generated UUIDs. Added controls, conditional hooks,
areas, masks or custom model conditions reject before native preparation.
Existing model wrappers and pre/post-CFG callbacks are preserved; this does not
establish arbitrary extension compatibility.

Source compatibility pins Comfy commit `7cebca52227c63b4180ceed448cbd7ad22903b6d`
for sampler, Euler, model-base and conditioning-helper source. Unknown revisions
reject active consumption. Scalar source probes exercise the actual pinned
guider, evaluation, batch and grounded-wrapper control flow with loading/device
boundaries and neural/VAE work explicitly substituted. Failure/short-schedule
cleanup evidence is source evidence, not installed-runtime or model acceptance.

Two exact native source pairs are admitted. The original pair binds sampler blob
`a7cc3419e325e7d55aac8c7d5ce6d65f620fc511` to model-base SHA256
`e7d08a4450287c76994b109437fbd03d721cf373fc8214bb9c30c478db060ffe`.
The reviewed earlier API pair binds sampler blob
`17f7bb8babdeec605586cc08df2ab1c4f1c92fd4` to model-base SHA256
`5722b46418c6b7475041733d659bbd71f11f1dacb4d0aaff2b21aeb2c82d5542`.
Mixed pairs reject. The earlier sampler omits the writable-model scope; Krea's
inherited writable-model request in the newer source returns None. The consumer
rejects instance writable-model overrides and additional multigpu models, keeping
this equivalence limited to the exact Krea path. Changes to other model families
do not establish their compatibility. Helper and numerical-sampling pins remain
unchanged.

At active binding, the consumer compiles the admitted source without executing
its module body and compares the observed loaded call-path code with
it, including nested code and exception regions. It also checks loaded enhancer
constants and native fusion methods. This detects stale or replaced function
bodies despite matching files; it is not a whole-runtime or model-state proof.
Device behavior, actual tokenizer/tensors, effect and task quality still require
installed-host validation. Node labels, caller revisions and inference-handle
limitations are unchanged.
Source-undecorated functions must be plain, matching functions with no wrapper
layer. The four admitted native sampling functions may have exactly the one
`torch.no_grad()` layer declared by their source. Its actual outer wrapper code,
closure target, bound clone factory and native context methods are checked
against selected definitions from
[PyTorch v2.9.0 contextlib](https://github.com/pytorch/pytorch/blob/v2.9.0/torch/utils/_contextlib.py)
and [grad mode](https://github.com/pytorch/pytorch/blob/v2.9.0/torch/autograd/grad_mode.py).
An additional complete tuple is reviewed from PyTorch v2.11.0
([context managers](https://github.com/pytorch/pytorch/blob/v2.11.0/torch/utils/_contextlib.py),
[grad mode](https://github.com/pytorch/pytorch/blob/v2.11.0/torch/autograd/grad_mode.py)).
It changes an assertion to an explicit error check and adds constructor type
annotations; the ordinary native decorator, clone and no-grad behavior remain
the same. All seven selected definitions must match one complete reviewed tuple;
mixed or unknown changes reject. Version strings alone never grant admission.
Identical complete tuples in another release satisfy the same source checks.
`__wrapped__` metadata alone never grants admission.
The source fingerprint uses a versioned explicit node/field/value representation,
not `ast.dump` display formatting, which differs between Python3.11 and3.13.
Empty semantic fields are retained. Nongeneric definitions on older Python get
the same empty `type_params` field as newer Python; nonempty generic parameters,
body, defaults, annotations and decorators all remain binding. This changes the
fingerprint representation of the same reviewed definitions, not the admitted
Torch semantics. Loaded-code, closure and context-factory checks still apply.
Extra transparent or numeric-changing wrappers, altered factories, multiple
layers and compiled wrappers remain unsupported. No PyTorch runtime code is
bundled by this integration.

To roll back this source addition, retain the previous checkout/package; no old
saved graph is rewritten and no model/recipe is migrated by these nodes.

## Explicit bounded scalar diagnostic

`KGKrea2BoundedNativeDiagnosticV12` is an alternative study builder for the
versioned illumination axis at +1 Throughout. Connect an owned, single-source,
full-frame context and its exact context revision. It executes the same three
study encodes and collects scalar measurements of the vision/deepstack inputs,
projected contrast, tap/region energy and composition rounding. Existing study
nodes and their ports are unchanged; ordinary workflows create no session.

The resulting studies use the existing native phase guider. Diagnostic sampling
accepts only eight native Euler steps, CFG1, handoff0.4, unattenuated phase
weights, enhancerON/strength1, no noise mask or donor, and a single native image
target no larger than1024x1024. Additional model callbacks, transformer patches
and wrappers reject. At steps0 and4 it makes one extra native-positive prediction
at the same latent and sigma, measuring actual text-fusion input/output and
prediction differences. Those neutral predictions never advance the sampler.
The ceiling is ten native predictions, conservatively twenty nominal CFG branch
evaluations, with no extra study/VAE pass introduced by the observer.

Connect `KGKrea2NativeDiagnosticReceiptV12` to these studies and the sampler's
completed samples to return a scalar JSON receipt in the output node's UI data.
The dependency must use the same sampler in the reviewed graph. A session is
single-use and a receipt requires successful completion. The receipt is bounded
to64KiB; no embeddings or tensor arrays are serialized. Source/context admission
remains unchanged. Temporary pairs, RNG state and owned conditioning branches
are restored or released on success, failure and cancellation, while detected
foreign state is preserved. There is no execution endpoint or persistent hook.

This diagnostic measures numerical transfer. Synthetic source tests do not
establish native neural behavior or useful lighting, and a nonzero measured
prediction difference does not by itself establish a calibrated semantic axis.
