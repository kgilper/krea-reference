# Experimental native carrier studies V13

The opt-in V13 study builder retains selected literal pole-token output states.
V12 projects all pole rows away and keeps only their contextual effect on the
original native prompt positions. This can produce a measurable prediction
change with little visible response. V13 tests whether keeping those semantic
carriers gives the denoiser a useful signed instruction.

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
The V13 guider requires CFG1 both when bound and when sampling starts. This
limits a step to at most two native positive conditioning branches; an eight-step
run is conservatively budgeted at sixteen branch evaluations. There are no
diagnostic counterfactual predictions.

Admission retains the existing maximum eight axes, 8192 expanded tokens, and
1179648 prepared image pixels, and additionally limits all literal pole spans
together to 512 tokens before study encoding. The original native source checks,
negative conditioning, target latent, noise mask, source/donor handles, encoder
cleanup, and native sampler delegation remain in force. No model weights,
training, persistent hook, solver replacement, or application-default migration
is introduced. Reverting a workflow to its V12 builder/guider disables this
experimental construction.
