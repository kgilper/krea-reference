"""The V9 guide-card node: describes one reference image for the stack.

The card resolves its artist-facing widgets into a guide packet: either a
quick recipe supplies every setting, or manual mode reads the tuning rows.
The text/logo blank-surface guard then clamps whatever the artist chose.
"""

from . import recipes
from .constants import KG_KREA_REFERENCE_TYPE


class KGKrea2ImageGuideCardV9:
    """
    KG Prefix: Krea 2 Image Guide Card V9

    Describes one reference image and emits a guide packet for the stack
    encoder.
    """

    PURPOSE_LABELS = {
        "manual tuning": None,
        "balanced": "balanced",
        "keep the same subject": "identity",
        "copy pose and layout": "composition",
        "copy lighting and mood": "lighting",
        "suggest the visual style": "style gentle",
        "suggest material or texture": "texture gentle",
        "copy big shapes only": "shape only",
        "avoid copying text/logos": "text/logo safe",
    }

    MANUAL_TARGET_LABELS = {
        "overall image": "balanced",
        "colors and art style": "style",
        "color palette only": "palette",
        "pose, camera, and layout": "composition",
        "camera/framing only": "framing",
        "same person/product/object": "identity",
        "background/environment": "environment",
        "lighting and shadows": "lighting",
        "mood-board only": "loose",
        "surface/material only": "material",
        "big shapes only": "shape only",
        "avoid words/logos": "text/logo safe",
    }

    PREP_LABELS = {
        "use image as-is": "normal",
        "remove color": "grayscale",
        "soften tiny details": "soft blur",
        "blur words and texture": "strong blur",
        "palette wash": "palette wash",
        "color wash": "color wash",
        "shape-only cleanup": "grayscale blur",
        "strong shape cleanup": "shape wash",
    }

    STUDY_LABELS = {
        "use stack setting": "stack",
        "low - loose idea (256)": "256",
        "medium - balanced default (384)": "384",
        "high - more exact (512)": "512",
        "very high - most exact (768)": "768",
    }

    FRAMING_LABELS = {
        "use stack setting": "stack",
        "keep full image shape": "preserve aspect",
        "center crop square": "center crop square",
        "stretch to square": "stretch square",
    }

    SUBJECT_LABELS = {
        "recipe decides": "recipe",
        "avoid copying subject": "avoid",
        "allow subject if useful": "allow",
        "preserve same subject": "preserve",
    }

    # Tuning tables live in recipes.py; the class aliases preserve the
    # original single-module surface for external callers.
    ROLE_PULL_DEFAULTS = recipes.ROLE_PULL_DEFAULTS
    EVEN_LAYER_PULL = recipes.EVEN_LAYER_PULL
    STYLE_LAYER_PULL = recipes.STYLE_LAYER_PULL
    PALETTE_LAYER_PULL = recipes.PALETTE_LAYER_PULL
    MATERIAL_LAYER_PULL = recipes.MATERIAL_LAYER_PULL
    LIGHTING_LAYER_PULL = recipes.LIGHTING_LAYER_PULL
    ROLE_LAYER_PULL_DEFAULTS = recipes.ROLE_LAYER_PULL_DEFAULTS
    QUICK_RECIPES = recipes.QUICK_RECIPES

    @classmethod
    def INPUT_TYPES(cls):
        # Widget labels are the saved-workflow API: renaming any label breaks
        # existing workflows and API-format calls. Treat them as frozen.
        # Rows from "Manual mode borrows" down only count when "Use image for"
        # is "manual tuning"; the V9 web extension greys them out otherwise.
        return {
            "required": {
                "Reference image": ("IMAGE",),
                "How strongly this image guides": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 3.0, "step": 0.05}),
                "Use image for": (list(cls.PURPOSE_LABELS.keys()),),
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
    def _role_pull_defaults(role):
        return recipes.role_pull_defaults(role)

    @staticmethod
    def _role_layer_pull_defaults(role):
        return recipes.role_layer_pull_defaults(role)

    @classmethod
    def _recipe_settings(cls, recipe_key):
        """Resolve one quick recipe into the card's settings."""
        recipe = cls.QUICK_RECIPES[recipe_key]
        role = recipe["role"]
        return {
            "quick_recipe": recipe_key,
            "manual_active": False,
            "role": role,
            "treatment": recipe["treatment"],
            "color_keep": recipe["color"],
            "detail": recipe["detail"],
            "study_at": recipe["study"],
            "framing": recipe["framing"],
            "subject_policy": recipe["subject"],
            "early_multiplier": recipe["early"],
            "late_multiplier": recipe["late"],
            "blank_surface_guard": recipe["guard"],
            "strength_cap": recipe["cap"],
            "shape_pull": recipe.get("shape", cls._role_pull_defaults(role)[0]),
            "global_pull": recipe.get("global", cls._role_pull_defaults(role)[1]),
            "layer_pull": list(recipe.get("layers", cls._role_layer_pull_defaults(role))),
        }

    @classmethod
    def _manual_settings(cls, kwargs, manual_target, prep):
        """Resolve the manual tuning rows into the card's settings."""
        role = cls._map_label(cls.MANUAL_TARGET_LABELS, manual_target)
        blank_surface_guard = role == "text/logo safe"
        manual_cap = cls._clamp(kwargs.get("Maximum image pull", 3.0), 0.0, 3.0)
        base_shape_pull, base_global_pull = cls._role_pull_defaults(role)
        return {
            "quick_recipe": "manual",
            "manual_active": True,
            "role": role,
            "treatment": cls._map_label(cls.PREP_LABELS, prep),
            "color_keep": cls._clamp(kwargs.get("Color kept", 1.0), 0.0, 1.0),
            "detail": cls._clamp(kwargs.get("Small details kept", 1.0), 0.0, 1.0),
            "study_at": cls._map_label(cls.STUDY_LABELS, kwargs.get("Study this image at", "use stack setting")),
            "framing": cls._map_label(cls.FRAMING_LABELS, kwargs.get("Frame this reference by", "use stack setting")),
            "subject_policy": cls._map_label(cls.SUBJECT_LABELS, kwargs.get("Subject copying", "recipe decides")),
            "early_multiplier": cls._clamp(kwargs.get("Early layout guidance", 1.0), 0.0, 5.0),
            "late_multiplier": cls._clamp(kwargs.get("Final detail copying", 1.0), 0.0, 5.0),
            "blank_surface_guard": blank_surface_guard,
            "strength_cap": 0.03 if blank_surface_guard else manual_cap,
            "shape_pull": base_shape_pull * cls._clamp(kwargs.get("Shape copied", 1.0), 0.0, 2.0),
            "global_pull": base_global_pull * cls._clamp(kwargs.get("Overall style reach", 1.0), 0.0, 3.0),
            "layer_pull": cls._role_layer_pull_defaults(role),
        }

    @staticmethod
    def _apply_blank_surface_guard(settings):
        """Clamp settings so a guarded card cannot carry text or logo detail."""
        settings["treatment"] = "shape wash"
        settings["color_keep"] = 0.0
        settings["detail"] = 0.0
        settings["study_at"] = "256"
        settings["early_multiplier"] = min(float(settings["early_multiplier"]), 0.75)
        settings["late_multiplier"] = 0.0
        settings["subject_policy"] = "avoid"
        settings["strength_cap"] = 0.03
        settings["shape_pull"] = min(float(settings["shape_pull"]), 0.08)
        settings["global_pull"] = 0.0
        settings["layer_pull"] = [min(float(value), 0.15) for value in settings["layer_pull"]]

    def build(self, **kwargs):
        purpose = kwargs.get("Use image for", "manual tuning")
        manual_target = kwargs.get("Manual mode borrows", "overall image")
        prep = kwargs.get("Prepare image by", "use image as-is")
        recipe_key = self._map_label(self.PURPOSE_LABELS, purpose)

        if recipe_key in self.QUICK_RECIPES:
            settings = self._recipe_settings(recipe_key)
        else:
            settings = self._manual_settings(kwargs, manual_target, prep)

        if settings["blank_surface_guard"]:
            self._apply_blank_surface_guard(settings)

        raw_strength = max(0.0, float(kwargs.get("How strongly this image guides", 0.2)))
        strength_cap = settings["strength_cap"]
        strength = min(raw_strength, strength_cap) if strength_cap is not None else raw_strength
        shape_pull = self._clamp(settings["shape_pull"], 0.0, 3.0)
        global_pull = self._clamp(settings["global_pull"], 0.0, 4.0)
        card = {
            "source_version": "v9",
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
        }
        return (card,)
