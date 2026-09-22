# Krea V11 technical notes

V11 subclasses the existing reference/slider stack contracts and registers separate node classes. V9, V10, Slider V1 and the recipe tables remain unchanged.

## Reference coefficients

For each card, measure the maximum absolute target across its active layers. Sum those peaks across cards. If that sum exceeds the selected gentle/strict budget, multiply every layer target by the same nonnegative scale, budget / sum. This preserves zeros and signs. The inactive pooled channel does not consume budget. This bounds coefficients, not embedding norms or perceptual influence. Balance remains off by default.

## Slider composition

Identical pole pairs share a study; reversed pairs are oriented consistently and their signed weights combined. Exact cancellation is removed before encoding. Each early/final phase separately caps the sum of absolute axis coefficients, default 2. A zero budget or reach bypasses pole encoding. Timing ends or starts at the handoff, default 0.4, using plain prompt conditioning in an inactive phase.

For total applied absolute weight w below 0.25, plain and steered conditioning branches carry Comfy conditioning strengths 1-alpha and alpha, with alpha=w/0.25. At zero only plain conditioning is emitted; at or above 0.25 only the existing steered branch is emitted. This avoids a sudden token-layout change at the first nonzero value. It does not enforce monotonicity or perceptual independence. Near-neutral branches may cost extra denoiser work.

## Studies

Prepared image keys use SHA256 of all tensor bytes, shape and dtype. Cache entries bind to the CLIP object through a weak reference and include its model patch revision and encoder identity. Unknown revisions bypass caching. The bounded cache retains at most two studies. Arbitrary in-place model changes that do not update Comfy's patch revision require always re-study.

## Host requirements

The active slider route requires the Krea encoder token-muting hook and fails explicitly when unsupported. Zero-value bypass is still usable. V11 uses the same Krea model assets as V10; no new model download or trained slider weights are included. The reference and slider stacks remain separate encoders.
