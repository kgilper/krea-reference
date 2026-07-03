"""Tuning tables and strength curves shared by the V9 guide card and encoder.

Everything artist-facing that is "just numbers" lives here: per-role pull
defaults, per-layer gain tables, the quick recipes behind the card's
"Use image for" choices, and the slider-feel strength curves. Keeping the
tables in one module lets the card and the stack encoder agree on defaults
without importing each other.
"""

# Baseline shape/global pull per resolved role. "shape" scales the token-level
# delta (layout/structure); "global" scales the pooled delta (overall style).
#
# IMPORTANT (render-verified 2026-07-03): on Krea 2 the text encoder emits no
# usable pooled_output, so the "global" axis is a silent no-op (compose only
# adds the pooled delta when it is a tensor). ALL appearance transfer therefore
# flows through the token path (strength x shape x layers). Appearance recipes
# must carry their effect on "shape" with structure-destroying image prep
# (palette wash / strong blur); a near-zero shape leaning on "global" transfers
# nothing regardless of card strength. Do not "fix" a weak appearance recipe by
# raising global - raise shape. See docs/deepstack-layers + the recipe-retune
# record for the sweep.
ROLE_PULL_DEFAULTS = {
    "balanced": {"shape": 1.0, "global": 1.0},
    "style": {"shape": 0.8, "global": 1.35},
    "palette": {"shape": 0.7, "global": 1.75},
    "composition": {"shape": 1.25, "global": 0.35},
    "framing": {"shape": 0.9, "global": 0.25},
    "identity": {"shape": 1.0, "global": 1.0},
    "environment": {"shape": 0.65, "global": 0.8},
    "lighting": {"shape": 0.25, "global": 1.25},
    "material": {"shape": 0.18, "global": 1.2},
    "loose": {"shape": 0.12, "global": 0.65},
    "shape only": {"shape": 1.2, "global": 0.05},
    "text/logo safe": {"shape": 0.08, "global": 0.0},
}

# Per-layer gains over the 12 deepstack conditioning chunks. The
# spiked entries (layers 8 and 10, counting from 0) carried the strongest
# palette/finish response in internal empirical sweeps; early layers stay
# low so style cards do not drag subject structure along. The stack
# encoder soft-caps the effective per-layer scale (MAX_LAYER_SCALE).
# Note: render-validation showed the layer *shape* is second-order at whisper
# strengths - the first-order appearance lever is the recipe's "shape" pull
# (token-path scale) under structure-destroying prep, not this table.
EVEN_LAYER_PULL = [1.0] * 12
STYLE_LAYER_PULL = [0.25, 0.35, 0.45, 0.6, 0.8, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.2]
PALETTE_LAYER_PULL = [0.15, 0.2, 0.3, 0.45, 0.7, 1.0, 1.0, 2.8, 5.5, 1.3, 4.5, 1.2]
MATERIAL_LAYER_PULL = [0.2, 0.3, 0.45, 0.65, 0.85, 1.0, 1.0, 2.0, 4.0, 1.2, 3.0, 1.1]
LIGHTING_LAYER_PULL = [0.2, 0.25, 0.35, 0.5, 0.8, 1.0, 1.0, 2.2, 4.5, 1.4, 4.0, 1.2]

ROLE_LAYER_PULL_DEFAULTS = {
    "balanced": EVEN_LAYER_PULL,
    "style": STYLE_LAYER_PULL,
    "palette": PALETTE_LAYER_PULL,
    "composition": EVEN_LAYER_PULL,
    "framing": EVEN_LAYER_PULL,
    "identity": EVEN_LAYER_PULL,
    "environment": STYLE_LAYER_PULL,
    "lighting": LIGHTING_LAYER_PULL,
    "material": MATERIAL_LAYER_PULL,
    "loose": STYLE_LAYER_PULL,
    "shape only": EVEN_LAYER_PULL,
    "text/logo safe": [0.15] * 12,
}

# Full settings bundle behind each non-manual "Use image for" choice.
QUICK_RECIPES = {
    "balanced": {
        "role": "balanced",
        "treatment": "normal",
        "color": 1.0,
        "detail": 1.0,
        "study": "stack",
        "framing": "stack",
        "subject": "recipe",
        "early": 1.0,
        "late": 1.0,
        "guard": False,
        "cap": None,
        "shape": 1.0,
        "global": 1.0,
        "layers": EVEN_LAYER_PULL,
    },
    "identity": {
        "role": "identity",
        "treatment": "normal",
        "color": 1.0,
        "detail": 1.0,
        "study": "stack",
        "framing": "stack",
        "subject": "preserve",
        "early": 1.0,
        "late": 1.0,
        "guard": False,
        "cap": None,
        "shape": 1.0,
        "global": 1.0,
        "layers": EVEN_LAYER_PULL,
    },
    "composition": {
        "role": "composition",
        "treatment": "grayscale blur",
        "color": 0.0,
        "detail": 0.25,
        "study": "stack",
        "framing": "stack",
        "subject": "avoid",
        "early": 1.2,
        "late": 0.2,
        "guard": False,
        "cap": 1.25,
        "shape": 1.3,
        "global": 0.3,
        "layers": EVEN_LAYER_PULL,
    },
    "lighting": {
        "role": "lighting",
        "treatment": "soft blur",
        "color": 0.85,
        "detail": 0.55,
        "study": "stack",
        "framing": "stack",
        "subject": "avoid",
        "early": 1.0,
        "late": 0.55,
        "guard": False,
        "cap": 1.25,
        "shape": 0.25,
        "global": 1.3,
        "layers": LIGHTING_LAYER_PULL,
    },
    "style gentle": {
        "role": "style",
        "treatment": "palette wash",
        "color": 0.85,
        # Render-tuned 2026-07-03: coarse prep (study 256, detail 0) + a live
        # "shape" so the borrowed look actually lands at demo strength. The old
        # shape 0.35 / study 384 leaned on the (inert) global axis and showed
        # nothing. Structure-safe: palette wash destroys the reference's shape
        # before encoding, so raising shape borrows the palette, not the subject.
        "detail": 0.0,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.85,
        "late": 0.85,
        "guard": False,
        "cap": 0.9,
        "shape": 0.8,
        "global": 1.85,
        "layers": STYLE_LAYER_PULL,
    },
    "texture gentle": {
        "role": "material",
        "treatment": "strong blur",
        "color": 0.65,
        "detail": 0.05,
        "study": "stack",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.5,
        "late": 0.75,
        "guard": False,
        "cap": 0.95,
        "shape": 0.35,
        "global": 1.55,
        "layers": MATERIAL_LAYER_PULL,
    },
    "shape only": {
        "role": "shape only",
        "treatment": "shape wash",
        "color": 0.0,
        "detail": 0.0,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 1.1,
        "late": 0.0,
        "guard": False,
        "cap": 1.0,
        "shape": 1.2,
        "global": 0.05,
        "layers": EVEN_LAYER_PULL,
    },
    "text/logo safe": {
        "role": "text/logo safe",
        "treatment": "shape wash",
        "color": 0.0,
        "detail": 0.0,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.75,
        "late": 0.0,
        "guard": True,
        "cap": 0.03,
        "shape": 0.08,
        "global": 0.0,
        "layers": [0.15] * 12,
    },
}


def role_pull_defaults(role):
    """Return the (shape, global) pull baseline for a resolved role."""
    defaults = ROLE_PULL_DEFAULTS.get(role, ROLE_PULL_DEFAULTS["balanced"])
    return float(defaults["shape"]), float(defaults["global"])


def role_layer_pull_defaults(role):
    """Return a fresh copy of the per-layer gain table for a resolved role."""
    return list(ROLE_LAYER_PULL_DEFAULTS.get(role, EVEN_LAYER_PULL))


def effective_image_strength(raw_strength, curve):
    """Map the card's strength slider through the stack's slider-feel curve.

    "linear" passes values through; "extra gentle" and the default artist
    curve are soft at low values with a hard zero near the bottom so idle
    sliders cost nothing, and stay slightly super-linear above 1.0.
    """
    raw_strength = max(0.0, float(raw_strength))
    if curve == "linear":
        return raw_strength
    if curve == "extra gentle":
        if raw_strength <= 0.02:
            return 0.0
        if raw_strength <= 1.0:
            return raw_strength ** 2.7
        return 1.0 + (raw_strength - 1.0) * 1.1

    if raw_strength <= 0.01:
        return 0.0
    if raw_strength <= 1.0:
        return raw_strength ** 1.6
    return 1.0 + (raw_strength - 1.0) * 1.15
