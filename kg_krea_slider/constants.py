"""Shared node-graph contract values for the Concept Slider V1 nodes."""

# Custom link type carried from slider cards to the slider stack. Saved
# workflows serialize this name, so treat it as frozen.
KG_KREA_SLIDER_TYPE = "KG_KREA_SLIDER"

# The artist-facing slider spans -SLIDER_RANGE..+SLIDER_RANGE with 0 = no
# change, matching the convention of published slider LoRAs (Concept
# Sliders / Ostris sliders are driven at roughly -6..+6 weights).
SLIDER_RANGE = 6.0

# Conditioning push applied at full deflection (|value| = SLIDER_RANGE,
# reach 1.0): the increase pole rides at +FULL_SCALE_PUSH x native encode
# scale and the decrease pole at -FULL_SCALE_PUSH simultaneously. Chosen
# from the render-proven V9 anchor points (prompt-strength floor 3.5 is
# loud but safe on a full prompt span; MAX_LAYER_SCALE 6.0 is the ceiling).
# PROVISIONAL until the first render audit - see the 2026-07-06 record.
FULL_SCALE_PUSH = 2.0

# Hard cap on any single slider's axis weight after the reach multiplier,
# mirroring V9's MAX_LAYER_SCALE guard: a hot reach times full deflection
# can never push one axis arbitrarily far past encode-native scale.
MAX_AXIS_WEIGHT = 6.0
