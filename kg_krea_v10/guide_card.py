"""The V10 guide-card node: describes one reference image for the stack.

Everything the V9 card does, plus quick recipes for the four roles V9 left
manual-only, a guide direction (a card can now be a counter-example), a
per-card timing choice, manual-mode structure/finish layer dials, and
user-defined custom recipes loaded from YAML/JSON files (custom_recipes.py)
that appear in "Use image for" as first-class choices.

Packets stay V9-compatible: every V9 key is emitted with the same meaning,
so a V10 card plugs into a V9 stack (which simply ignores the V10 keys) and
a V9 card plugs into the V10 stack (V10 keys fall back to their defaults).
"""

from . import custom_recipes, recipes
from ._v9 import v9

KG_KREA_REFERENCE_TYPE = v9.KG_KREA_REFERENCE_TYPE

_V9Card = v9.KGKrea2ImageGuideCardV9


class _V9Resolution(_V9Card):
    """Internal only: V9's resolution logic pointed at the V10 recipe table."""

    QUICK_RECIPES = recipes.QUICK_RECIPES


class KGKrea2ImageGuideCardV10:
    """
    KG Prefix: Krea 2 Image Guide Card V10

    Describes one reference image and emits a guide packet for the stack
    encoder. Extends the V9 card with direction, timing, four more quick
    recipes, and manual layer dials.
    """

    PURPOSE_LABELS = {
        **_V9Card.PURPOSE_LABELS,
        "suggest the color palette": "palette only",
        "use the background/setting": "environment",
        "copy the camera framing": "framing",
        "mood board only": "mood board",
    }

    MANUAL_TARGET_LABELS = dict(_V9Card.MANUAL_TARGET_LABELS)
    PREP_LABELS = dict(_V9Card.PREP_LABELS)
    STUDY_LABELS = dict(_V9Card.STUDY_LABELS)
    FRAMING_LABELS = dict(_V9Card.FRAMING_LABELS)
    SUBJECT_LABELS = dict(_V9Card.SUBJECT_LABELS)

    DIRECTION_LABELS = {
        "toward this image": "toward",
        "away from this image": "away",
    }

    TIMING_LABELS = {
        "recipe decides": "recipe",
        "whole image": "constant",
        "early layout only": "early",
        "final details only": "late",
    }

    QUICK_RECIPES = recipes.QUICK_RECIPES

    @classmethod
    def _custom_recipes(cls):
        """Currently loaded user recipes (label -> validated bundle).

        Reserved labels cover both the artist-facing purpose labels and the
        internal recipe keys, so a custom label can never shadow (or be
        shadowed by) a built-in on either level.
        """
        reserved = set(cls.PURPOSE_LABELS) | set(cls.QUICK_RECIPES)
        loaded, _errors = custom_recipes.refresh(reserved)
        return loaded

    @classmethod
    def _purpose_choices(cls):
        """Built-in purposes first (frozen order), then custom labels sorted."""
        return list(cls.PURPOSE_LABELS.keys()) + sorted(cls._custom_recipes())

    @classmethod
    def INPUT_TYPES(cls):
        # Widget labels are the saved-workflow API: the first 15 rows repeat
        # the V9 card's frozen surface, and the V10 rows are appended after.
        # Append new labels only; never rename or reorder. "Use image for"
        # additionally lists validated custom recipes after the built-ins;
        # ComfyUI re-calls this on node-definition refresh, so new recipe
        # files appear without a restart.
        return {
            "required": {
                "Reference image": ("IMAGE",),
                "How strongly this image guides": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 3.0, "step": 0.05}),
                "Use image for": (cls._purpose_choices(),),
                "Manual mode borrows": (list(cls.MANUAL_TARGET_LABELS.keys()),),
                "Prepare image by": (list(cls.PREP_LABELS.keys()),),
                "Color kept": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "Small details kept": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "Study this image at": (list(cls.STUDY_LABELS.keys()),),
                "Frame this reference by": (list(cls.FRAMING_LABELS.keys()),),
                "Subject copying": (list(cls.SUBJECT_LABELS.keys()),),
                "Early layout guidance": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
                "Final detail copying": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
                "Maximum image pull": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 3.0, "step": 0.05}),
                "Shape copied": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "Overall style reach": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05}),
                "Guide direction": (list(cls.DIRECTION_LABELS.keys()),),
                "When this card guides": (list(cls.TIMING_LABELS.keys()),),
                "Structure layers pull": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "Finish layers pull": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = (KG_KREA_REFERENCE_TYPE,)
    RETURN_NAMES = ("guide_card",)
    FUNCTION = "build"
    CATEGORY = "advanced/conditioning"

    @staticmethod
    def _map_label(mapping, value):
        return mapping.get(value, value)

    @staticmethod
    def _clamp(value, minimum, maximum):
        return min(max(float(value), minimum), maximum)

    @staticmethod
    def _custom_recipe_settings(label, bundle):
        """Resolve one validated custom-recipe bundle into card settings."""
        return {
            "quick_recipe": label,
            "manual_active": False,
            "role": bundle["role"],
            "treatment": bundle["treatment"],
            "color_keep": bundle["color"],
            "detail": bundle["detail"],
            "study_at": bundle["study"],
            "framing": bundle["framing"],
            "subject_policy": bundle["subject"],
            "early_multiplier": bundle["early"],
            "late_multiplier": bundle["late"],
            "blank_surface_guard": bool(bundle["guard"]),
            "strength_cap": bundle["cap"],
            "shape_pull": bundle["shape"],
            "global_pull": bundle["global"],
            "layer_pull": list(bundle["layers"]),
            # Optional semantic focus: what the encoder should study from
            # this image ("the clothing and garment style only", ...).
            "focus": bundle.get("focus", ""),
        }

    def build(self, **kwargs):
        purpose = kwargs.get("Use image for", "manual tuning")
        manual_target = kwargs.get("Manual mode borrows", "overall image")
        prep = kwargs.get("Prepare image by", "use image as-is")
        recipe_key = self._map_label(self.PURPOSE_LABELS, purpose)
        custom_recipe = None

        if recipe_key in self.QUICK_RECIPES:
            settings = _V9Resolution._recipe_settings(recipe_key)
        elif purpose not in self.PURPOSE_LABELS and (custom_recipe := self._custom_recipes().get(purpose)) is not None:
            settings = self._custom_recipe_settings(purpose, custom_recipe)
        elif purpose not in self.PURPOSE_LABELS:
            # A saved workflow references a custom recipe whose file was
            # removed or renamed: fall back to balanced rather than silently
            # reading the manual rows.
            custom_recipes.warn_missing(purpose)
            settings = _V9Resolution._recipe_settings("balanced")
        else:
            settings = _V9Resolution._manual_settings(kwargs, manual_target, prep)
            # Manual-only layer dials scale the role's per-layer gain table.
            settings["layer_pull"] = recipes.apply_layer_dials(
                settings["layer_pull"],
                self._clamp(kwargs.get("Structure layers pull", 1.0), 0.0, 2.0),
                self._clamp(kwargs.get("Finish layers pull", 1.0), 0.0, 2.0),
            )

        timing_label = kwargs.get("When this card guides", "recipe decides")
        timing = self._map_label(self.TIMING_LABELS, timing_label)
        settings["early_multiplier"], settings["late_multiplier"] = recipes.apply_card_timing(
            timing, settings["early_multiplier"], settings["late_multiplier"]
        )

        direction_label = kwargs.get("Guide direction", "toward this image")
        direction = self._map_label(self.DIRECTION_LABELS, direction_label)
        if direction == "away" and settings["subject_policy"] != "avoid":
            # A counter-example never carries its subject into the result.
            settings["subject_policy"] = "avoid"

        # The blank-surface guard clamps last, so it wins over timing and
        # dial choices exactly as it wins over manual rows in V9.
        if settings["blank_surface_guard"]:
            _V9Resolution._apply_blank_surface_guard(settings)

        raw_strength = max(0.0, float(kwargs.get("How strongly this image guides", 0.2)))
        strength_cap = settings["strength_cap"]
        strength = min(raw_strength, strength_cap) if strength_cap is not None else raw_strength
        shape_pull = self._clamp(settings["shape_pull"], 0.0, 3.0)
        global_pull = self._clamp(settings["global_pull"], 0.0, 4.0)
        card = {
            "source_version": "v10",
            "image": kwargs.get("Reference image"),
            "strength": strength,
            "requested_strength": raw_strength,
            "purpose": purpose,
            "manual_mode_borrows": manual_target,
            "prepare_image_by": prep,
            "color_kept": kwargs.get("Color kept", 1.0),
            "study_this_image_at": kwargs.get("Study this image at", "use stack setting"),
            "frame_this_reference_by": kwargs.get("Frame this reference by", "use stack setting"),
            "subject_copying": kwargs.get("Subject copying", "recipe decides"),
            "shape_copied": kwargs.get("Shape copied", 1.0),
            "overall_style_reach": kwargs.get("Overall style reach", 1.0),
            "manual_controls_active": settings["manual_active"],
            "quick_recipe": settings["quick_recipe"],
            "resolved_role": settings["role"],
            "resolved_treatment": settings["treatment"],
            "resolved_color_keep": settings["color_keep"],
            "resolved_detail": settings["detail"],
            "resolved_reference_resolution": settings["study_at"],
            "resolved_reference_fit": settings["framing"],
            "resolved_subject_policy": settings["subject_policy"],
            "resolved_early_multiplier": settings["early_multiplier"],
            "resolved_late_multiplier": settings["late_multiplier"],
            "resolved_shape_pull": shape_pull,
            "resolved_global_pull": global_pull,
            "resolved_layer_pull": settings["layer_pull"],
            "v9_blank_surface_guard": bool(settings["blank_surface_guard"]),
            "v9_strength_cap": strength_cap,
            # V10 additions (V9 stacks ignore these keys).
            "guide_direction": direction_label,
            "resolved_direction": direction,
            "when_this_card_guides": timing_label,
            "resolved_timing": timing,
            "structure_layers_pull": kwargs.get("Structure layers pull", 1.0),
            "finish_layers_pull": kwargs.get("Finish layers pull", 1.0),
            "custom_recipe": custom_recipe is not None,
            "custom_recipe_source": custom_recipe.get("source") if custom_recipe else None,
            "resolved_focus": str(settings.get("focus", "") or ""),
            # Shared packet keys keep the guide card easy to inspect in tests
            # and future stack nodes.
            "preset": "manual",
            "role": settings["role"],
            "treatment": settings["treatment"],
            "detail": settings["detail"],
            "early_multiplier": settings["early_multiplier"],
            "late_multiplier": settings["late_multiplier"],
            "shape_pull": shape_pull,
            "global_pull": global_pull,
            "layer_pull": settings["layer_pull"],
            "direction": direction,
            "timing": timing,
            "focus": str(settings.get("focus", "") or ""),
        }
        return (card,)
