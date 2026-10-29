# Node index

The serialized class is the identifier stored in a workflow. Versioned classes
remain available so old workflows keep their original behavior. V11 is the
recommended starting point; V12/V13 are experimental native interfaces available
from current GitHub source, beyond registry package 0.5.0.

## V11 reference cards and sliders

| Display name | Serialized class | Usage |
|---|---|---|
| KG Krea 2 Image Guide Card V11 | `KGKrea2ImageGuideCardV11` | [Reference controls](../krea-v11-user-guide.md#reference-controls) |
| KG Krea 2 Reference Stack Encoder V11 | `KGTextEncodeKreaImageReferencesV11` | [Reference wiring](../krea-v11-user-guide.md#reference-wiring) |
| KG Krea 2 Concept Slider Card V11 | `KGKrea2ConceptSliderCardV11` | [Slider controls](../krea-v11-user-guide.md#slider-controls) |
| KG Krea 2 Concept Slider Stack V11 | `KGKrea2ConceptSliderStackV11` | [Slider wiring](../krea-v11-user-guide.md#slider-wiring) |

[Illustrated examples](../krea-v11-gallery.md) · [Cookbook](../krea-v11-worked-examples.md)

## V13 native carrier sliders

Start with [setup and the first comparison](../krea-v13-native-carriers.md#setup-and-first-comparison).
The display names end in **(Experimental)**. Both nodes are under
`advanced/conditioning/native carriers`.

| Serialized class | Purpose and output |
|---|---|
| `KGKrea2NativeCarrierStudiesV13` | Combine a V12 native context and up to eight V12 axis cards into `KG_KREA_NATIVE_CARRIER_STUDIES_V13`, plus a study report |
| `KGKrea2NativeCarrierPhaseGuiderV13` | Bind those carrier studies to their original native CFG1 guider; output `GUIDER` for native sampling |

V13 studies cannot connect to the V12 phase guider. Use the matched V13 pair.
One full-frame synthetic illumination comparison is visibly verified; broader
semantic calibration and donor/mask quality remain unestablished.

## V12 native preparation and diagnostics

These nodes are under `advanced/conditioning/native studies`, except the last
two, which use `advanced/conditioning/native diagnostics`. Their display names
spell out the class words after **KG Krea 2**.
See [exact ports, source pins and limits](../krea-v12-native-studies.md).

| Serialized class | Purpose |
|---|---|
| `KGKrea2PrepareNativeContextV12` | Adopt or prepare explicit native CLIP/MODEL, prompt and image/latent handles |
| `KGKrea2PrepareOwnedGroundedContextV12` | Prepare the owned grounded edit context; also return its MODEL, positive/negative conditioning and target LATENT |
| `KGKrea2NativeAxisV12` | Declare canonical axis ID/revision, literal positive/negative poles, signed native coefficient and timing |
| `KGKrea2CombinedNativeStudiesV12` | Original projection-only native studies and report; use V13 studies for the demonstrated illumination construction |
| `KGKrea2NativePhaseGuiderV12` | Bind V12 studies to the matching original native guider |
| `KGKrea2RemoveOwnedReferenceV12` | Remove `native:donor` from an owned context and rebuild its native outputs |
| `KGKrea2NativeEnhancerV12` | Optional pinned Krea2T enhancer, default OFF; attach before the edit patch |
| `KGKrea2PrepareNativeTargetV12` | Optional native target-latent preparation, default OFF; return the updated context and shared target LATENT |
| `KGKrea2BoundedNativeDiagnosticV12` | Explicit extra-prediction diagnostic study builder; not needed for ordinary image generation |
| `KGKrea2NativeDiagnosticReceiptV12` | Emit the bounded diagnostic's scalar receipt after samples complete |

## Preserved earlier classes

| Version | Serialized classes | Guide |
|---|---|---|
| V9 | `KGKrea2ImageGuideCardV9`, `KGTextEncodeKreaImageReferencesV9` | [Prior-version documentation](../previous-versions/README.md) |
| V10 | `KGKrea2ImageGuideCardV10`, `KGTextEncodeKreaImageReferencesV10` | [Prior-version documentation](../previous-versions/README.md) |
| Slider V1 | `KGKrea2ConceptSliderCardV1`, `KGKrea2ConceptSliderStackV1` | [Prior-version documentation](../previous-versions/README.md) |

Updating the package does not automatically convert a workflow to a newer class.
