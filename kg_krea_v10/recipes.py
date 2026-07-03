"""V10 tuning tables: the V9 tables plus the V10 additions.

V10 adds quick recipes for the four roles that V9 left manual-only
(palette, environment, framing, loose), the per-card timing table, the
stack's balance budgets, and the manual structure/finish layer-dial split.
Everything else re-exports V9 so the two versions cannot drift apart.
"""

from ._v9 import v9

_v9_recipes = v9.recipes

# Re-exported V9 tables and curves (single source of truth stays in V9).
ROLE_PULL_DEFAULTS = _v9_recipes.ROLE_PULL_DEFAULTS
ROLE_LAYER_PULL_DEFAULTS = _v9_recipes.ROLE_LAYER_PULL_DEFAULTS
EVEN_LAYER_PULL = _v9_recipes.EVEN_LAYER_PULL
STYLE_LAYER_PULL = _v9_recipes.STYLE_LAYER_PULL
PALETTE_LAYER_PULL = _v9_recipes.PALETTE_LAYER_PULL
MATERIAL_LAYER_PULL = _v9_recipes.MATERIAL_LAYER_PULL
LIGHTING_LAYER_PULL = _v9_recipes.LIGHTING_LAYER_PULL

role_pull_defaults = _v9_recipes.role_pull_defaults
role_layer_pull_defaults = _v9_recipes.role_layer_pull_defaults
effective_image_strength = _v9_recipes.effective_image_strength

# V10 quick recipes: the V9 bundles plus one bundle per previously
# manual-only role. Starting values follow the role's pull baselines and the
# whisper-defaults philosophy (soft caps, avoid-subject policies).
QUICK_RECIPES = dict(_v9_recipes.QUICK_RECIPES)
QUICK_RECIPES.update({
    "palette only": {
        "role": "palette",
        "treatment": "palette wash",
        "color": 1.0,
        "detail": 0.0,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.9,
        "late": 0.9,
        "guard": False,
        "cap": 0.9,
        "shape": 0.05,
        "global": 1.8,
        "layers": PALETTE_LAYER_PULL,
    },
    "environment": {
        "role": "environment",
        "treatment": "soft blur",
        "color": 1.0,
        "detail": 0.6,
        "study": "stack",
        "framing": "stack",
        "subject": "avoid",
        "early": 1.1,
        "late": 0.6,
        "guard": False,
        "cap": 1.2,
        "shape": 0.7,
        "global": 0.85,
        "layers": STYLE_LAYER_PULL,
    },
    "framing": {
        "role": "framing",
        "treatment": "grayscale blur",
        "color": 0.0,
        "detail": 0.15,
        "study": "256",
        "framing": "preserve aspect",
        "subject": "avoid",
        "early": 1.2,
        "late": 0.15,
        "guard": False,
        "cap": 1.2,
        "shape": 0.95,
        "global": 0.25,
        "layers": EVEN_LAYER_PULL,
    },
    "mood board": {
        "role": "loose",
        "treatment": "soft blur",
        "color": 1.0,
        "detail": 0.35,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.8,
        "late": 0.8,
        "guard": False,
        "cap": 0.6,
        "shape": 0.15,
        "global": 0.7,
        "layers": STYLE_LAYER_PULL,
    },
})

# Per-card timing: how "When this card guides" rewrites the resolved
# early/late phase multipliers. "recipe" keeps the recipe/manual values.
CARD_TIMING_BEHAVIOR = {
    "recipe": None,
    "constant": (1.0, 1.0),
    "early": ("keep", 0.0),
    "late": (0.0, "keep"),
}

# Stack balance budgets: the allowed sum of per-card departures from neutral
# (|target - 1|) per sampling phase before the stack scales strong cards
# back toward neutral. None disables balancing.
BALANCE_BUDGETS = {
    "off": None,
    "gentle": 2.5,
    "strict": 1.5,
}

# Manual layer dials: which deepstack chunks each dial scales. Chunks 7-10
# carried the strongest palette/finish response in the V9 sweeps, so the
# finish dial owns the back half and the structure dial the front half.
STRUCTURE_LAYER_RANGE = range(0, 6)
FINISH_LAYER_RANGE = range(6, 12)


def apply_layer_dials(layer_pull, structure_dial, finish_dial):
    """Scale a per-layer gain table by the manual structure/finish dials."""
    structure_dial = max(0.0, float(structure_dial))
    finish_dial = max(0.0, float(finish_dial))
    scaled = list(layer_pull)
    for i in STRUCTURE_LAYER_RANGE:
        if i < len(scaled):
            scaled[i] = float(scaled[i]) * structure_dial
    for i in FINISH_LAYER_RANGE:
        if i < len(scaled):
            scaled[i] = float(scaled[i]) * finish_dial
    return scaled


def apply_card_timing(timing, early_multiplier, late_multiplier):
    """Rewrite (early, late) phase multipliers for a card timing choice."""
    behavior = CARD_TIMING_BEHAVIOR.get(timing)
    if behavior is None:
        return float(early_multiplier), float(late_multiplier)
    early_rule, late_rule = behavior
    early = float(early_multiplier) if early_rule == "keep" else float(early_rule)
    late = float(late_multiplier) if late_rule == "keep" else float(late_rule)
    return early, late
