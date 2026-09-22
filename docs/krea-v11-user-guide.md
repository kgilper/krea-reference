# Krea Reference V11

V11 is an explicit alternative to the V9/V10 reference nodes and Concept Slider V1. Existing graphs keep their original node classes and behavior. The `balanced` recipe and all V10 recipe tables are reused without retuning.

## Select V11

In ComfyUI, add **KG Krea 2 Image Guide Card V11** and **KG Krea 2 Reference Stack Encoder V11** from `advanced/conditioning`. Existing V9/V10 image cards can feed the V11 stack through the same reference-card link type. Select a V11 sign-preserving balance mode explicitly; balance remains off by default.

For attributes, use **KG Krea 2 Concept Slider Card V11** with **KG Krea 2 Concept Slider Stack V11**. V1 cards also work with the V11 slider stack, using whole-image timing. The V11 card adds concrete person-height and plaza-crowd presets; explicit pole text overrides a preset. Height wording describes a man: use custom poles for another subject. Crowd reduction needs a scene containing people to have room to decrease.

## Changes

- Reference balance limits the sum of maximum absolute layer targets. It scales signed targets toward zero, preserving suppression and away direction. It ignores the inactive pooled channel. This is a coefficient budget, not a measured perceptual guarantee.
- Image-study keys hash the full prepared image content and include the CLIP patch revision. Unknown patch revisions bypass the cache. In-place model modifications outside Comfy's revision protocol require `always re-study`.
- Slider stacks group duplicate/opposite pole pairs before encoding and budget their total absolute coefficients separately for early/final phases. Default total budget is 2, equal to a single full-range slider at reach 1; up to 6 can be selected deliberately.
- Per-card timing can affect the whole image, early layout, or final details. The stack handoff defaults to 0.4. Timing is a creative control, not a promise that late influence preserves every structure.
- Zero overall reach, zero budget, or fully cancelled axes bypass pole encoding entirely. Unsupported active token-muting hosts raise a clear error instead of producing a silent slider.

## Compatibility and limitations

V11 uses the Krea Qwen3-VL encoder and existing Krea model/VAE assets. The reference and slider stacks remain separate; connecting their finished conditioning together is not a supported combined encoder.

There is no automatic migration. Copy an accepted workflow before selecting V11 classes. V10 balance labels must be replaced with the explicitly named V11 balance option. V11 timing/preset packet additions have no effect in older slider stacks. Do not feed a V11 card into V1 when expecting those additions to work.

Reference image preparation stays at the accepted V10 behavior until controlled comparisons support a change. No automatic model replacement, alternative style backend, asymmetrical gain calibration, or new trained weights are included. Strong controls can still change identity, framing, or style. Begin around +/-2 to 4 and inspect both directions.

## Validation and rollback

The initial implementation passes the existing contract suite plus V11 regression tests. Image-quality acceptance and portable example graphs are being evaluated separately; a passing code test is not a visual-quality claim.

Rollback is workflow selection: choose the unchanged V10 reference stack or Slider V1 stack and the original workflow copy. Keeping V11 installed does not change existing node behavior. Do not delete older nodes or overwrite saved workflow files during migration.
