"""V10 tuning tables: the V9 tables plus the V10 additions/overrides.

V10 adds quick recipes for the four roles that V9 left manual-only
(palette, environment, framing, loose), overrides the visual-style recipe,
the per-card timing table, the stack's balance budgets, and the manual
structure/finish layer-dial split. Shared tables still re-export V9; V10-only
behavior lives in this module so V9 remains frozen.
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
STYLE_TRANSFER_LAYER_PULL = [0.062, 0.087, 0.113, 0.15, 0.2, 0.25, 1.25, 3.438, 6.875, 1.375, 5.5, 1.5]
MATERIAL_FINISH_LAYER_PULL = [0.05, 0.075, 0.113, 0.163, 0.213, 0.25, 1.25, 2.75, 5.5, 1.5, 4.125, 1.375]

# Render-tuned 2026-07-06: the strong-blur prep is the style recipe's
# structure-safety guarantee, but the encoder was also *studying the blur* -
# on soft-medium references (watercolor, gouache, aged photos) renders came
# out pervasively soft, with the subject small and hazy. Crisper prep
# (higher detail, larger study) re-opened source-scene takeover instead, so
# the correction rides the instruction channel: de-selecting softness and
# scene layout keeps the prompt subject crisp and primary while palette,
# medium, and brushwork still arrive. A/B render-verified across five
# references, two strengths, and three seeds, single-card and in the
# two-card style-transfer method.
STYLE_TRANSFER_FOCUS = (
    "the artistic style: palette, medium, brushwork, art direction, and "
    "rendering finish - not the image's blurriness or soft focus, and not "
    "its subject or scene layout"
)

# Render-tuned 2026-07-06: the inherited palette-wash lighting recipe
# flattened dramatic skies into flat location tones (a brewing-storm
# reference delivered a dry sunny field at every strength). Palette wash
# destroys the very sky structure the mood lives in; strong blur keeps the
# broad light/cloud masses alive and the focus line keeps the place and its
# objects out. A/B render-verified: storm mood arrives at 0.65, full drama
# by 0.9, subject and prompt scene kept.
LIGHTING_MOOD_FOCUS = (
    "the lighting: light direction, contrast, mood, color cast, glow, and "
    "shadow behavior - not the place, objects, or scene layout"
)

# Render-tuned 2026-07-06: the even table at shape 1.2 drove the deep
# appearance taps too, so the shape-wash study's flat gray tone arrived as
# a monochrome result (prep-artifact leak; a focus de-selection could NOT
# override it). Shape lives in the shallow taps: structure x1.3, appearance
# x0.25 delivers silhouette influence with prompt-natural color.
STRUCTURE_ONLY_LAYER_PULL = [1.3, 1.3, 1.3, 1.3, 1.3, 1.3, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25]

role_pull_defaults = _v9_recipes.role_pull_defaults
role_layer_pull_defaults = _v9_recipes.role_layer_pull_defaults
effective_image_strength = _v9_recipes.effective_image_strength

# V10 quick recipes: the V9 bundles plus one bundle per previously
# manual-only role. Starting values follow the role's pull baselines and the
# whisper-defaults philosophy (soft caps, avoid-subject policies).
QUICK_RECIPES = dict(_v9_recipes.QUICK_RECIPES)
QUICK_RECIPES.update({
    "lighting": {
        "role": "lighting",
        # V10 override (2026-07-06): strong blur + de-place focus so dramatic
        # light/sky moods actually arrive; see LIGHTING_MOOD_FOCUS above.
        "treatment": "strong blur",
        "color": 1.0,
        "detail": 0.15,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 1.0,
        "late": 0.55,
        "guard": False,
        "cap": 1.25,
        "shape": 0.8,
        "global": 1.3,
        "layers": LIGHTING_LAYER_PULL,
        "focus": LIGHTING_MOOD_FOCUS,
    },
    "shape only": {
        "role": "shape only",
        # V10 override (2026-07-06): structure-heavy layer table so the gray
        # study cannot drain the result's color; see STRUCTURE_ONLY_LAYER_PULL.
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
        "layers": STRUCTURE_ONLY_LAYER_PULL,
    },
    "style gentle": {
        "role": "style",
        "treatment": "strong blur",
        "color": 1.0,
        # Render-tuned 2026-07-05 for V10 only: the inherited palette-wash
        # style recipe had collapsed into a color-grade twin of "suggest the
        # color palette". Strong blur keeps broad medium/finish cues alive
        # while muting small details, and the finish-heavy table suppresses the
        # source's structure layers. Palette-only safety stays with the
        # separate palette recipe.
        "detail": 0.3,
        "study": "384",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.85,
        "late": 0.85,
        "guard": False,
        "cap": 0.65,
        "shape": 0.85,
        "global": 1.85,
        "layers": STYLE_TRANSFER_LAYER_PULL,
        "focus": STYLE_TRANSFER_FOCUS,
    },
    "texture gentle": {
        "role": "material",
        "treatment": "strong blur",
        "color": 1.0,
        # V10 material override: preserve enough softened surface signal for
        # fabric, glaze, stone, and finish cues while keeping source-shape
        # influence low and late-weighted.
        "detail": 0.35,
        "study": "384",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.35,
        "late": 0.9,
        "guard": False,
        "cap": 0.65,
        "shape": 0.8,
        "global": 1.55,
        "layers": MATERIAL_FINISH_LAYER_PULL,
    },
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
        # Render-tuned 2026-07-03: shape 0.05 -> 0.7. On Krea 2 "global" is inert
        # (no pooled_output), so the old low-shape/high-global palette recipe
        # transferred nothing at any strength. With palette-wash prep, a live
        # shape borrows the reference palette as a color field (subtle at low
        # card strength, clear by ~0.65) while keeping the subject. Validated on
        # a geometric and a natural reference; see the recipe-retune record.
        "shape": 0.7,
        "global": 1.8,
        "layers": PALETTE_LAYER_PULL,
    },
    "environment": {
        "role": "environment",
        # Render-tuned 2026-07-03: soft blur pulled the reference's FORM onto the
        # subject (a bowl became a jar) - the conditioning is non-spatial, so it
        # cannot place a scene *behind* the subject. Palette wash keeps it
        # structure-safe: it borrows the setting's palette/mood, subject intact.
        "treatment": "palette wash",
        "color": 1.0,
        "detail": 0.3,
        "study": "256",
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
        # Render-tuned 2026-07-03: palette wash + a live shape so the loose vibe
        # actually reads a gentle borrowed palette (old shape 0.15 / cap 0.6 on
        # the inert global axis showed nothing). Kept soft via a lower shape than
        # palette and a modest cap.
        "treatment": "palette wash",
        "color": 1.0,
        "detail": 0.2,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.8,
        "late": 0.8,
        "guard": False,
        "cap": 0.9,
        "shape": 0.65,
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
