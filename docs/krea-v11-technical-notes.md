# Krea V11 technical notes

V11 subclasses the existing reference/slider stack contracts and registers separate node classes. V9, V10, Slider V1 and the recipe tables remain unchanged.

## Reference coefficients

For each card, measure the maximum absolute target across its active layers. Sum those peaks across cards. If that sum exceeds the selected gentle/strict budget, multiply every layer target by the same nonnegative scale, budget / sum. This preserves zeros and signs. The inactive pooled channel does not consume budget. This bounds coefficients, not embedding norms or perceptual influence. Balance remains off by default.

## Slider composition

Identical pole pairs share a study; reversed pairs are oriented consistently and their signed weights combined. Exact cancellation is removed before encoding. In manual mode, each early/final phase separately caps the sum of absolute axis coefficients, default 2. A zero manual budget or reach bypasses pole encoding. Timing ends or starts at the handoff, default 0.4, using plain prompt conditioning in an inactive phase.

For total applied absolute weight w below 0.25, plain and steered conditioning branches carry Comfy conditioning strengths 1-alpha and alpha, with alpha=w/0.25. At zero only plain conditioning is emitted; at or above 0.25 only the existing steered branch is emitted. This avoids a sudden token-layout change at the first nonzero value. It does not enforce monotonicity or perceptual independence. Near-neutral branches may cost extra denoiser work.

## Studies

Prepared image keys use SHA256 of all tensor bytes, shape and dtype. Cache entries bind to the CLIP object through a weak reference and include its model patch revision and encoder identity. Unknown revisions bypass caching. The bounded cache retains at most two studies. Arbitrary in-place model changes that do not update Comfy's patch revision require always re-study.

## Host requirements

The active slider route requires the Krea encoder token-muting hook and fails explicitly when unsupported. Zero-value bypass is still usable. V11 uses the same Krea model assets as V10; no new model download or trained slider weights are included. The reference and slider stacks remain separate encoders.

## Automatic reach and budget

Select **Slider scaling mode: automatic** on the V11 slider stack to derive both controls from the active cards. The updated native showcase selects this mode. Existing workflows without the new field retain manual behavior; select automatic explicitly when upgrading an existing canvas.

Automatic mode ignores the manual reach and budget widgets, including zero values. Set all cards to zero (or switch to manual and set reach to zero) for a plain-prompt comparison. The slider report shows effective controls for active configurations; inactive configurations report plain bypass.

At unit reach, each card requests value / 3. Duplicate/opposite poles are combined and timing applied before measuring the maximum absolute coefficient sum across the two phases. Automatic budget equals that load up to 6. Reach stays 1 while load is at most 6; beyond that, reach becomes 6 / load and budget stays 6. Small values are never amplified to fill a budget. This limit bounds coefficients, not visual quality or concept independence.

Examples: brightness +3, fog +2, height -4 produce load 3, reach 1 and budget 3. Two distinct +3 cards produce budget 2. Eight distinct +6 cards produce load 16, reach 0.375 and budget 6; the report explicitly reports the reduction. Early-only and final-only cards consume their respective phase capacity rather than being counted as simultaneous. No semantic calibration or identity preservation is implied.

Earlier reach/budget tuning examples describe **manual** mode. Manual remains available with its original zero-bypass and per-phase budgeting behavior.
