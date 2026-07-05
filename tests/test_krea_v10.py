"""Tests for the Krea V10 package (kg_krea_v10/).

Covers five layers:

1. Label contracts - the V10 widget surface is the V9 surface plus appended
   rows, and packets stay V9-compatible.
2. Card behavior - the new recipes, direction, timing, and layer dials.
3. Encoder behavior - away-card target math, balance budgets, the study
   cache, the stack report, and V9-packet cross-compatibility.
4. Prompt behavior - direction-aware system prompts and the multilingual
   text/logo guard vocabulary.
5. Custom recipes - schema validation, dynamic dropdown inclusion, card
   resolution, guard clamping, and safe failure modes.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _kg_stub_env import load_module

V9_CARD_LABELS = [
    "Reference image",
    "How strongly this image guides",
    "Use image for",
    "Manual mode borrows",
    "Prepare image by",
    "Color kept",
    "Small details kept",
    "Study this image at",
    "Frame this reference by",
    "Subject copying",
    "Early layout guidance",
    "Final detail copying",
    "Maximum image pull",
    "Shape copied",
    "Overall style reach",
]

V9_STACK_LABELS = [
    "Krea CLIP",
    "Final image prompt",
    "Written prompt strength",
    "Image slider feel",
    "Image detail level",
    "Image framing",
    "When images guide",
    "Early-to-final handoff",
    "Text/logo guard prompt handling",
]

RECIPE_KEYS = {
    "role", "treatment", "color", "detail", "study", "framing", "subject",
    "early", "late", "guard", "cap", "shape", "global", "layers",
}


class FakeClip:
    def __init__(self):
        self.calls = []

    def tokenize(self, text, images=None, llama_template=None):
        self.calls.append({"text": text, "images": images, "llama_template": llama_template})
        return {"qwen": [[151644, 872, 198]]}


def patch_encoder_machinery(cls, captured):
    original = {
        name: vars(cls)[name]
        for name in (
            "_tag_image_references",
            "_encode_with_controls",
            "_conditioning_delta",
            "_apply_prompt_delta",
            "_compose_conditioning",
            "_with_timestep_range",
            "_prepare_image_v10",
            "_build_contact_sheet",
        )
    }

    def fake_encode(clip, tokens, **kwargs):
        captured.setdefault("encode_calls", []).append(kwargs)
        return ["base"]

    def fake_compose(conditioning, weighted_deltas):
        captured.setdefault("compose_calls", []).append(weighted_deltas)
        return ["composed"]

    cls._tag_image_references = staticmethod(lambda tokens: None)
    cls._encode_with_controls = staticmethod(fake_encode)
    cls._conditioning_delta = staticmethod(lambda conditioning, muted: "image-delta")
    cls._apply_prompt_delta = staticmethod(lambda conditioning, muted: "prompt-delta")
    cls._compose_conditioning = staticmethod(fake_compose)
    cls._with_timestep_range = staticmethod(lambda conditioning, start, end: conditioning)
    cls._prepare_image_v10 = staticmethod(lambda image, res, fit, treat, det, color: "prepared:" + str(image))
    cls._build_contact_sheet = staticmethod(lambda prepared_images: "sheet")
    return original


def restore_encoder_machinery(cls, original):
    for name, value in original.items():
        setattr(cls, name, value)


def balanced_card(image="img", strength=0.5, **overrides):
    """A hand-built neutral-role packet (V9-key subset unless overridden)."""
    card = {
        "image": image,
        "strength": strength,
        "resolved_role": "balanced",
        "resolved_treatment": "normal",
        "resolved_color_keep": 1.0,
        "resolved_detail": 1.0,
        "resolved_reference_resolution": "384",
        "resolved_reference_fit": "preserve aspect",
        "resolved_subject_policy": "recipe",
        "resolved_early_multiplier": 1.0,
        "resolved_late_multiplier": 1.0,
        "resolved_shape_pull": 1.0,
        "resolved_global_pull": 1.0,
        "resolved_layer_pull": [1.0] * 12,
    }
    card.update(overrides)
    return card


class KreaV10LabelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v10", "kg_krea_v10_under_test")

    def test_v10_is_fully_standalone(self):
        self.assertEqual(self.nodes.KGKrea2ImageGuideCardV10.__bases__, (object,))
        self.assertEqual(self.nodes.KGTextEncodeKreaImageReferencesV10.__bases__, (object,))
        for name in (
            "_tag_image_references",
            "_conditioning_delta",
            "_compose_conditioning",
            "_encode_with_controls",
            "_with_timestep_range",
            "_blur_samples",
            "_prepare_image_v10",
            "_cache_key",
            "_cache_lookup",
            "_cache_store",
            "_build_report",
            "_build_contact_sheet",
        ):
            self.assertIn(name, vars(self.nodes.KGTextEncodeKreaImageReferencesV10))

    def test_v10_card_labels_are_v9_plus_appended_rows(self):
        inputs = self.nodes.KGKrea2ImageGuideCardV10.INPUT_TYPES()["required"]
        self.assertEqual(
            list(inputs.keys()),
            V9_CARD_LABELS + [
                "Guide direction",
                "When this card guides",
                "Structure layers pull",
                "Finish layers pull",
            ],
        )
        self.assertEqual(
            inputs["Guide direction"][0],
            ["toward this image", "away from this image"],
        )
        self.assertEqual(
            inputs["When this card guides"][0],
            ["recipe decides", "whole image", "early layout only", "final details only"],
        )

    def test_v10_purpose_choices_are_v9_plus_new_recipes(self):
        builtin = [
            "manual tuning",
            "balanced",
            "keep the same subject",
            "copy pose and layout",
            "copy lighting and mood",
            "suggest the visual style",
            "suggest material or texture",
            "copy big shapes only",
            "avoid copying text/logos",
            "suggest the color palette",
            "use the background/setting",
            "copy the camera framing",
            "mood board only",
        ]
        purposes = list(self.nodes.KGKrea2ImageGuideCardV10.INPUT_TYPES()["required"]["Use image for"][0])
        # Built-ins are a frozen prefix; validated custom recipes follow, sorted.
        self.assertEqual(purposes[:len(builtin)], builtin)
        self.assertEqual(
            purposes[len(builtin):],
            sorted(self.nodes.KGKrea2ImageGuideCardV10._custom_recipes()),
        )

    def test_v10_stack_labels_are_v9_plus_appended_rows(self):
        inputs = self.nodes.KGTextEncodeKreaImageReferencesV10.INPUT_TYPES()
        self.assertEqual(
            list(inputs["required"].keys()),
            V9_STACK_LABELS + ["Balance strong cards", "Reuse image studies"],
        )
        self.assertEqual(
            inputs["required"]["Balance strong cards"][0],
            ["off - use my values", "gentle balance", "strict balance"],
        )
        self.assertEqual(
            inputs["required"]["Reuse image studies"][0],
            ["reuse between runs - faster tuning", "always re-study"],
        )
        self.assertEqual(
            list(inputs["optional"].keys()),
            [f"Reference {i} guide card" for i in range(1, 13)],
        )

    def test_v10_stack_outputs(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        self.assertEqual(cls.RETURN_TYPES, ("CONDITIONING", "STRING", "IMAGE"))
        self.assertEqual(cls.RETURN_NAMES, ("conditioning", "stack_report", "prepared_references"))

    def test_v10_card_packet_is_versioned_and_v9_compatible(self):
        card = self.nodes.KGKrea2ImageGuideCardV10().build(**{
            "Reference image": "img",
            "How strongly this image guides": 1.0,
            "Use image for": "avoid copying text/logos",
        })[0]
        self.assertEqual(card["source_version"], "v10")
        self.assertTrue(card["v9_blank_surface_guard"])
        self.assertEqual(card["v9_strength_cap"], 0.03)
        self.assertEqual(card["strength"], 0.03)
        self.assertEqual(card["resolved_direction"], "toward")
        self.assertEqual(card["resolved_timing"], "recipe")
        # Every V9 packet key is still present with V9 semantics.
        for key in (
            "resolved_role", "resolved_treatment", "resolved_layer_pull",
            "resolved_shape_pull", "resolved_global_pull", "requested_strength",
            "role", "treatment", "shape_pull", "global_pull", "layer_pull",
        ):
            self.assertIn(key, card)

    def test_v10_quick_recipes_cover_the_manual_only_roles(self):
        recipes = self.nodes.recipes.QUICK_RECIPES
        for key, role in (
            ("palette only", "palette"),
            ("environment", "environment"),
            ("framing", "framing"),
            ("mood board", "loose"),
        ):
            self.assertIn(key, recipes)
            self.assertEqual(recipes[key]["role"], role)
        # Every recipe (V9 and V10) carries the full settings bundle.
        for key, recipe in recipes.items():
            self.assertEqual(set(recipe.keys()), RECIPE_KEYS, "recipe {} is incomplete".format(key))

    def test_v10_max_layer_scale_constant(self):
        self.assertEqual(self.nodes.KGTextEncodeKreaImageReferencesV10.MAX_LAYER_SCALE, 6.0)


class KreaV10CardBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v10", "kg_krea_v10_card_tests")

    def _build(self, **kwargs):
        base = {"Reference image": "img", "How strongly this image guides": 0.5}
        base.update(kwargs)
        return self.nodes.KGKrea2ImageGuideCardV10().build(**base)[0]

    def test_new_palette_recipe_resolves(self):
        card = self._build(**{"Use image for": "suggest the color palette"})
        self.assertEqual(card["resolved_role"], "palette")
        self.assertEqual(card["resolved_treatment"], "palette wash")
        self.assertEqual(card["v9_strength_cap"], 0.9)
        self.assertEqual(card["resolved_subject_policy"], "avoid")

    def test_visual_style_recipe_uses_v10_style_transfer_override(self):
        card = self._build(**{
            "Use image for": "suggest the visual style",
            "How strongly this image guides": 1.6,
        })

        self.assertEqual(card["source_version"], "v10")
        self.assertEqual(card["quick_recipe"], "style gentle")
        self.assertFalse(card["manual_controls_active"])
        self.assertFalse(card["custom_recipe"])
        self.assertEqual(card["resolved_role"], "style")
        self.assertEqual(card["resolved_treatment"], "strong blur")
        self.assertAlmostEqual(card["resolved_color_keep"], 1.0)
        self.assertAlmostEqual(card["resolved_detail"], 0.3)
        self.assertEqual(card["resolved_reference_resolution"], "384")
        self.assertEqual(card["resolved_reference_fit"], "stack")
        self.assertEqual(card["resolved_subject_policy"], "avoid")
        self.assertAlmostEqual(card["resolved_early_multiplier"], 0.85)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 0.85)
        self.assertEqual(card["v9_strength_cap"], 0.65)
        self.assertAlmostEqual(card["requested_strength"], 1.6)
        self.assertAlmostEqual(card["strength"], 0.65)
        self.assertAlmostEqual(card["resolved_shape_pull"], 0.85)
        self.assertGreater(card["resolved_shape_pull"], 0.4)
        self.assertAlmostEqual(card["resolved_global_pull"], 1.85)
        self.assertEqual(card["resolved_layer_pull"], self.nodes.recipes.STYLE_TRANSFER_LAYER_PULL)
        self.assertEqual(card["resolved_focus"], "")
        self.assertEqual(card["resolved_direction"], "toward")
        self.assertEqual(card["resolved_timing"], "recipe")

    def test_visual_style_recipe_keeps_contract_under_v10_direction_and_timing(self):
        card = self._build(**{
            "Use image for": "suggest the visual style",
            "Guide direction": "away from this image",
            "When this card guides": "final details only",
            "Structure layers pull": 0.25,
            "Finish layers pull": 2.0,
        })

        self.assertEqual(card["resolved_direction"], "away")
        self.assertEqual(card["direction"], "away")
        self.assertEqual(card["resolved_timing"], "late")
        self.assertEqual(card["resolved_subject_policy"], "avoid")
        self.assertEqual(card["resolved_role"], "style")
        self.assertEqual(card["resolved_treatment"], "strong blur")
        self.assertAlmostEqual(card["resolved_early_multiplier"], 0.0)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 0.85)
        # V10 layer dials are manual-mode only; built-in recipe layers stay stable.
        self.assertEqual(card["resolved_layer_pull"], self.nodes.recipes.STYLE_TRANSFER_LAYER_PULL)
        self.assertAlmostEqual(card["resolved_shape_pull"], 0.85)
        self.assertAlmostEqual(card["resolved_global_pull"], 1.85)

    def test_away_direction_forces_subject_avoid(self):
        card = self._build(**{
            "Use image for": "keep the same subject",
            "Guide direction": "away from this image",
        })
        self.assertEqual(card["resolved_direction"], "away")
        self.assertEqual(card["direction"], "away")
        self.assertEqual(card["resolved_subject_policy"], "avoid")

    def test_card_timing_overrides_phase_multipliers(self):
        # The composition recipe ships early 1.2 / late 0.2.
        recipe = {"Use image for": "copy pose and layout"}
        card = self._build(**recipe)
        self.assertAlmostEqual(card["resolved_early_multiplier"], 1.2)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 0.2)

        card = self._build(**recipe, **{"When this card guides": "whole image"})
        self.assertAlmostEqual(card["resolved_early_multiplier"], 1.0)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 1.0)

        card = self._build(**recipe, **{"When this card guides": "early layout only"})
        self.assertAlmostEqual(card["resolved_early_multiplier"], 1.2)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 0.0)

        card = self._build(**recipe, **{"When this card guides": "final details only"})
        self.assertAlmostEqual(card["resolved_early_multiplier"], 0.0)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 0.2)

    def test_guard_clamp_beats_timing(self):
        card = self._build(**{
            "Use image for": "avoid copying text/logos",
            "When this card guides": "whole image",
        })
        self.assertLessEqual(card["resolved_early_multiplier"], 0.75)
        self.assertEqual(card["resolved_late_multiplier"], 0.0)
        self.assertEqual(card["v9_strength_cap"], 0.03)

    def test_layer_dials_scale_manual_mode_only(self):
        manual = {
            "Use image for": "manual tuning",
            "Manual mode borrows": "overall image",
            "Structure layers pull": 0.5,
            "Finish layers pull": 2.0,
        }
        card = self._build(**manual)
        self.assertEqual(card["resolved_layer_pull"], [0.5] * 6 + [2.0] * 6)

        recipe_card = self._build(**{
            "Use image for": "balanced",
            "Structure layers pull": 0.5,
            "Finish layers pull": 2.0,
        })
        self.assertEqual(recipe_card["resolved_layer_pull"], [1.0] * 12)


class KreaV10EncoderBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v10", "kg_krea_v10_encoder_tests")

    def setUp(self):
        self.nodes.cache.reset()

    def _stack_kwargs(self, clip, **overrides):
        kwargs = {
            "Krea CLIP": clip,
            "Final image prompt": "a portrait",
            "Written prompt strength": 1.0,
            "Image slider feel": "literal slider values",
            "When images guide": "guide the whole image",
            "Text/logo guard prompt handling": "full guard - rewrite my prompt",
            "Balance strong cards": "off - use my values",
            "Reuse image studies": "always re-study",
        }
        kwargs.update(overrides)
        return kwargs

    def _run(self, captured, **overrides):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        clip = overrides.pop("clip", None) or FakeClip()
        result = cls().execute(**self._stack_kwargs(clip, **overrides))
        return result, clip

    def test_execute_returns_conditioning_report_and_sheet(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            result, _ = self._run(captured, **{"Reference 1 guide card": balanced_card()})
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0], ["composed"])
            self.assertIn("stack report", result[1])
            self.assertEqual(result[2], "sheet")
        finally:
            restore_encoder_machinery(cls, original)

    def test_away_card_negates_targets(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            card = balanced_card(strength=0.5, resolved_direction="away")
            self._run(captured, **{"Reference 1 guide card": card})
            image_entries = [e for e in captured["compose_calls"][0] if e[0] == "image-delta"]
            self.assertEqual(len(image_entries), 1)
            _, token_weight, pooled_weight, token_layers = image_entries[0]
            # target = -0.5 -> weight -1.5 (past removal into repulsion).
            self.assertAlmostEqual(token_weight, -1.5)
            self.assertAlmostEqual(pooled_weight, -1.5)
            self.assertEqual(token_layers, [-1.5] * 12)
        finally:
            restore_encoder_machinery(cls, original)

    def test_away_layer_targets_clamp_symmetrically(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            card = balanced_card(
                strength=2.0,
                resolved_direction="away",
                resolved_layer_pull=[5.0] * 12,
            )
            self._run(captured, **{"Reference 1 guide card": card})
            image_entries = [e for e in captured["compose_calls"][0] if e[0] == "image-delta"]
            _, token_weight, pooled_weight, token_layers = image_entries[0]
            self.assertAlmostEqual(token_weight, -3.0)
            # Uncapped scale would be -2.0 * 5.0 = -10.0; V10 clamps at -6.0.
            self.assertEqual(token_layers, [-7.0] * 12)
        finally:
            restore_encoder_machinery(cls, original)

    def test_strict_balance_scales_hot_stacks(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            cards = {
                "Reference 1 guide card": balanced_card(strength=2.0),
                "Reference 2 guide card": balanced_card(strength=2.0),
            }
            # Two cards at target 2.0 -> departure 1.0 each, total 2.0.
            self._run(captured, **cards, **{"Balance strong cards": "strict balance"})
            image_entries = [e for e in captured["compose_calls"][0] if e[0] == "image-delta"]
            # Budget 1.5 / departure 2.0 -> scale 0.75 -> weights 0.75.
            for _, token_weight, pooled_weight, _layers in image_entries:
                self.assertAlmostEqual(token_weight, 0.75)
                self.assertAlmostEqual(pooled_weight, 0.75)

            captured["compose_calls"] = []
            self._run(captured, **cards, **{"Balance strong cards": "gentle balance"})
            image_entries = [e for e in captured["compose_calls"][0] if e[0] == "image-delta"]
            # Budget 2.5 >= departure 2.0 -> untouched.
            for _, token_weight, pooled_weight, _layers in image_entries:
                self.assertAlmostEqual(token_weight, 1.0)
                self.assertAlmostEqual(pooled_weight, 1.0)
        finally:
            restore_encoder_machinery(cls, original)

    def test_study_reuse_skips_encoder_passes_on_reruns(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            clip = FakeClip()
            card = {"Reference 1 guide card": balanced_card()}
            reuse = {"Reuse image studies": "reuse between runs - faster tuning", "clip": clip}

            result, _ = self._run(captured, **card, **reuse)
            first_run_encodes = len(captured["encode_calls"])
            self.assertEqual(first_run_encodes, 2)  # base + one image delta

            result, _ = self._run(captured, **card, **reuse)
            self.assertEqual(len(captured["encode_calls"]), first_run_encodes)  # no new passes
            self.assertIn("reused 2 cached studies", result[1])

            # A strength tweak still reuses every study (compose-only rerun).
            tweaked = {"Reference 1 guide card": balanced_card(strength=1.5)}
            result, _ = self._run(captured, **tweaked, **reuse)
            self.assertEqual(len(captured["encode_calls"]), first_run_encodes)

            # Reuse off re-studies everything.
            result, _ = self._run(captured, **card, **{"Reuse image studies": "always re-study", "clip": clip})
            self.assertEqual(len(captured["encode_calls"]), first_run_encodes + 2)
        finally:
            restore_encoder_machinery(cls, original)

    def test_report_names_the_guard_cap(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            guard_card = self.nodes.KGKrea2ImageGuideCardV10().build(**{
                "Reference image": "img",
                "How strongly this image guides": 0.5,
                "Use image for": "avoid copying text/logos",
            })[0]
            result, _ = self._run(captured, **{"Reference 1 guide card": guard_card})
            report = result[1]
            self.assertIn("capped at 0.03", report)
            self.assertIn("text/logo guard", report)
        finally:
            restore_encoder_machinery(cls, original)

    def test_v9_style_packet_works_and_defaults_toward(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            self._run(captured, **{"Reference 1 guide card": balanced_card(strength=0.5)})
            image_entries = [e for e in captured["compose_calls"][0] if e[0] == "image-delta"]
            _, token_weight, pooled_weight, _layers = image_entries[0]
            self.assertAlmostEqual(token_weight, -0.5)  # target 0.5 -> weight -0.5
            self.assertAlmostEqual(pooled_weight, -0.5)
        finally:
            restore_encoder_machinery(cls, original)

    def test_visual_style_recipe_targets_finish_layers_and_balances_predictably(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV10
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            style_card = self.nodes.KGKrea2ImageGuideCardV10().build(**{
                "Reference image": "style-ref",
                "How strongly this image guides": 0.9,
                "Use image for": "suggest the visual style",
            })[0]
            self._run(
                captured,
                **{
                    "Image slider feel": "artist friendly - soft at low values",
                    "When images guide": "guide the whole image",
                    "Balance strong cards": "off - use my values",
                    "Reference 1 guide card": style_card,
                },
            )
            image_entries = [e for e in captured["compose_calls"][0] if e[0] == "image-delta"]
            self.assertEqual(len(image_entries), 1)
            _, token_weight, pooled_weight, token_layers = image_entries[0]
            effective = 0.65 ** 1.6
            token_target = effective * 0.85

            self.assertAlmostEqual(token_weight, token_target - 1.0)
            self.assertAlmostEqual(pooled_weight, effective * 1.85 - 1.0)
            self.assertLess(token_layers[0], 0.0)
            self.assertLess(token_layers[3], 0.0)
            self.assertGreater(token_layers[8], 1.5)
            self.assertGreater(token_layers[10], 1.0)

            captured["compose_calls"] = []
            self._run(
                captured,
                **{
                    "Image slider feel": "literal slider values",
                    "When images guide": "guide the whole image",
                    "Balance strong cards": "strict balance",
                    "Reference 1 guide card": style_card,
                    "Reference 2 guide card": style_card,
                },
            )
            balanced_entries = [
                e for e in captured["compose_calls"][0] if e[0] == "image-delta"
            ]
            self.assertEqual(len(balanced_entries), 2)
            # The recipe caps the literal 0.9 slider to 0.65. Target departures:
            # token: 0.65 * 0.85 - 1 = -0.4475,
            # pooled: 0.65 * 1.85 - 1 = 0.2025.
            # The balancer budgets by the larger axis per card, so this stack
            # stays below the strict 1.5 budget and should be unchanged.
            scale = 1.0
            for _, token_weight, pooled_weight, token_layers in balanced_entries:
                self.assertAlmostEqual(token_weight, (0.65 * 0.85 - 1.0) * scale)
                self.assertAlmostEqual(pooled_weight, (0.65 * 1.85 - 1.0) * scale)
                self.assertGreater(token_layers[8], token_layers[3])
        finally:
            restore_encoder_machinery(cls, original)


class KreaV10CustomRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v10", "kg_krea_v10_custom_recipe_tests")
        cls.custom = cls.nodes.custom_recipes
        cls.card_cls = cls.nodes.KGKrea2ImageGuideCardV10

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kg_v10_recipes_"))
        self._original_pack_dir = self.custom._PACK_RECIPE_DIR
        # Isolate from the repo's shipped custom_recipes/ folder.
        self.custom._PACK_RECIPE_DIR = self.tmp / "no-such-dir"
        self.custom.EXTRA_SEARCH_PATHS.clear()
        self.custom.EXTRA_SEARCH_PATHS.append(self.tmp)
        self.custom._last_errors = None
        self.custom._warned_missing.clear()

    def tearDown(self):
        self.custom._PACK_RECIPE_DIR = self._original_pack_dir
        self.custom.EXTRA_SEARCH_PATHS.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, content):
        (self.tmp / name).write_text(content, encoding="utf-8")

    def _refresh(self):
        reserved = set(self.card_cls.PURPOSE_LABELS) | set(self.card_cls.QUICK_RECIPES)
        return self.custom.refresh(reserved)

    def _build(self, purpose, strength=0.5, **kwargs):
        base = {"Reference image": "img", "How strongly this image guides": strength, "Use image for": purpose}
        base.update(kwargs)
        return self.card_cls().build(**base)[0]

    FULL_RECIPE = {
        "label": "neon glow style",
        "description": "Saturated neon palette and glow.",
        "role": "style",
        "treatment": "palette wash",
        "color": 0.8,
        "detail": 0.1,
        "study": "256",
        "framing": "stack",
        "subject": "avoid",
        "early": 0.9,
        "late": 0.8,
        "guard": False,
        "cap": 0.7,
        "shape": 0.3,
        "global": 1.9,
        "layers": [1.0] * 12,
    }

    def test_json_recipe_appears_in_dropdown_and_resolves_on_card(self):
        self._write("neon.json", json.dumps(self.FULL_RECIPE))
        purposes = self.card_cls.INPUT_TYPES()["required"]["Use image for"][0]
        self.assertIn("neon glow style", purposes)
        self.assertEqual(purposes.index("neon glow style"), len(self.card_cls.PURPOSE_LABELS))

        card = self._build("neon glow style", strength=0.9)
        self.assertTrue(card["custom_recipe"])
        self.assertEqual(card["custom_recipe_source"], "neon.json")
        self.assertEqual(card["quick_recipe"], "neon glow style")
        self.assertEqual(card["resolved_role"], "style")
        self.assertEqual(card["resolved_treatment"], "palette wash")
        self.assertAlmostEqual(card["resolved_color_keep"], 0.8)
        self.assertAlmostEqual(card["resolved_detail"], 0.1)
        self.assertEqual(card["resolved_reference_resolution"], "256")
        self.assertEqual(card["resolved_subject_policy"], "avoid")
        self.assertAlmostEqual(card["resolved_early_multiplier"], 0.9)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 0.8)
        self.assertAlmostEqual(card["resolved_shape_pull"], 0.3)
        self.assertAlmostEqual(card["resolved_global_pull"], 1.9)
        self.assertEqual(card["resolved_layer_pull"], [1.0] * 12)
        # Strength 0.9 exceeds the recipe's cap of 0.7.
        self.assertEqual(card["v9_strength_cap"], 0.7)
        self.assertAlmostEqual(card["strength"], 0.7)
        self.assertAlmostEqual(card["requested_strength"], 0.9)

    @unittest.skipUnless(__import__("importlib.util", fromlist=["util"]).find_spec("yaml"), "PyYAML not installed")
    def test_minimal_yaml_recipe_fills_role_defaults(self):
        self._write("hint.yaml", "label: soft palette hint\nrole: palette\n")
        recipes_map, errors = self._refresh()
        self.assertEqual(errors, [])
        bundle = recipes_map["soft palette hint"]
        self.assertEqual(bundle["treatment"], "normal")
        self.assertIsNone(bundle["cap"])
        self.assertEqual(bundle["subject"], "recipe")
        default_shape, default_global = self.nodes.recipes.role_pull_defaults("palette")
        self.assertAlmostEqual(bundle["shape"], default_shape)
        self.assertAlmostEqual(bundle["global"], default_global)
        self.assertEqual(bundle["layers"], self.nodes.recipes.role_layer_pull_defaults("palette"))

    def test_recipe_pack_loads_multiple(self):
        pack = {"recipes": [
            {"label": "pack style", "role": "style"},
            {"label": "pack lighting", "role": "lighting"},
        ]}
        self._write("pack.json", json.dumps(pack))
        recipes_map, errors = self._refresh()
        self.assertEqual(errors, [])
        self.assertEqual(sorted(recipes_map), ["pack lighting", "pack style"])

    def test_custom_guard_recipe_is_clamped_like_the_builtin_guard(self):
        recipe = {"label": "my logo guard", "role": "text/logo safe", "guard": True}
        self._write("guard.json", json.dumps(recipe))
        card = self._build("my logo guard", strength=0.5)
        self.assertTrue(card["v9_blank_surface_guard"])
        self.assertEqual(card["v9_strength_cap"], 0.03)
        self.assertAlmostEqual(card["strength"], 0.03)
        self.assertEqual(card["resolved_late_multiplier"], 0.0)
        self.assertEqual(card["resolved_treatment"], "shape wash")

    def test_direction_and_timing_apply_to_custom_recipes(self):
        self._write("neon.json", json.dumps(self.FULL_RECIPE))
        card = self._build(
            "neon glow style",
            **{"Guide direction": "away from this image", "When this card guides": "whole image"},
        )
        self.assertEqual(card["resolved_direction"], "away")
        self.assertEqual(card["resolved_subject_policy"], "avoid")
        self.assertAlmostEqual(card["resolved_early_multiplier"], 1.0)
        self.assertAlmostEqual(card["resolved_late_multiplier"], 1.0)

    def test_focus_field_validates_and_reaches_the_card_packet(self):
        recipe = dict(self.FULL_RECIPE)
        recipe["label"] = "clothing borrower"
        recipe["focus"] = "  the clothing and garment style,\n   not the person  "
        self._write("clothing.json", json.dumps(recipe))
        recipes_map, errors = self._refresh()
        self.assertEqual(errors, [])
        # Whitespace is normalized; the bundle carries the focus text.
        self.assertEqual(
            recipes_map["clothing borrower"]["focus"],
            "the clothing and garment style, not the person",
        )
        card = self._build("clothing borrower")
        self.assertEqual(card["resolved_focus"], "the clothing and garment style, not the person")
        self.assertEqual(card["focus"], "the clothing and garment style, not the person")
        # Built-in recipes carry an empty focus (key present, no text).
        builtin = self._build("suggest the visual style")
        self.assertEqual(builtin["resolved_focus"], "")

    def test_focus_without_text_is_omitted_from_the_bundle(self):
        self._write("nofocus.json", json.dumps({"label": "plain style", "role": "style", "focus": "   "}))
        recipes_map, errors = self._refresh()
        self.assertEqual(errors, [])
        self.assertNotIn("focus", recipes_map["plain style"])

    def test_focus_rejects_non_string_and_overlong_values(self):
        self._write("bad-focus-type.json", json.dumps({"label": "bad focus", "role": "style", "focus": 5}))
        self._write("bad-focus-long.json", json.dumps({
            "label": "long focus", "role": "style", "focus": "x" * 301}))
        recipes_map, errors = self._refresh()
        self.assertEqual(recipes_map, {})
        joined = "\n".join(errors)
        self.assertIn("focus must be a string", joined)
        self.assertIn("focus must be at most 300 characters", joined)

    def test_invalid_recipes_are_skipped_with_reasons(self):
        self._write("a-valid.json", json.dumps({"label": "still fine", "role": "style"}))
        self._write("bad-key.json", json.dumps({"label": "typo", "role": "style", "colour": 0.5}))
        self._write("bad-role.json", json.dumps({"label": "bad role", "role": "vibes"}))
        self._write("bad-range.json", json.dumps({"label": "hot color", "role": "style", "color": 1.5}))
        self._write("bad-layers.json", json.dumps({"label": "short layers", "role": "style", "layers": [1.0] * 11}))
        self._write("collide-label.json", json.dumps({"label": "balanced", "role": "style"}))
        self._write("collide-key.json", json.dumps({"label": "identity", "role": "style"}))
        self._write("not-a-mapping.json", json.dumps([1, 2, 3]))
        self._write("broken.yaml", "label: [unclosed\n")

        recipes_map, errors = self._refresh()
        self.assertEqual(sorted(recipes_map), ["still fine"])
        joined = "\n".join(errors)
        self.assertIn("unknown recipe keys: colour", joined)
        self.assertIn("role must be one of", joined)
        self.assertIn("color must be between 0.0 and 1.0", joined)
        self.assertIn("exactly 12 numbers", joined)
        self.assertIn('"balanced" collides', joined)
        self.assertIn('"identity" collides', joined)
        self.assertIn("expected a recipe mapping", joined)
        self.assertEqual(len(errors), 7 if self.custom.yaml is None else 8)

    def test_duplicate_label_across_files_first_wins(self):
        self._write("a.json", json.dumps({"label": "twice", "role": "style", "color": 0.2}))
        self._write("b.json", json.dumps({"label": "twice", "role": "style", "color": 0.9}))
        recipes_map, errors = self._refresh()
        self.assertAlmostEqual(recipes_map["twice"]["color"], 0.2)
        self.assertTrue(any('"twice" collides' in e for e in errors))

    def test_underscore_and_unknown_extensions_are_ignored(self):
        self._write("_disabled.json", json.dumps({"label": "hidden", "role": "style"}))
        self._write("notes.txt", "not a recipe")
        recipes_map, errors = self._refresh()
        self.assertEqual(recipes_map, {})
        self.assertEqual(errors, [])

    @unittest.skipUnless(__import__("importlib.util", fromlist=["util"]).find_spec("yaml"), "PyYAML not installed")
    def test_shipped_starter_pack_loads_cleanly(self):
        shipped = Path(__file__).resolve().parents[1] / "custom_recipes" / "starter-pack.yaml"
        self.assertTrue(shipped.is_file(), "starter-pack.yaml must ship with the pack")
        reserved = frozenset(set(self.card_cls.PURPOSE_LABELS) | set(self.card_cls.QUICK_RECIPES))
        loaded, errors = self.custom.load_recipe_file(shipped, reserved)
        self.assertEqual(errors, [])
        self.assertEqual(
            sorted(loaded),
            ["borrow the clothing style", "borrow the weather", "cinematic color grade"],
        )
        # Every starter recipe demonstrates the focus field.
        for label, bundle in loaded.items():
            self.assertTrue(bundle.get("focus"), "{} should carry a focus".format(label))

    def test_missing_custom_label_falls_back_to_balanced(self):
        card = self._build("ghost recipe that no longer exists")
        self.assertFalse(card["custom_recipe"])
        self.assertEqual(card["quick_recipe"], "balanced")
        self.assertEqual(card["resolved_role"], "balanced")
        # Manual rows were not silently read.
        self.assertFalse(card["manual_controls_active"])


class KreaV10PromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v10", "kg_krea_v10_prompt_tests")
        cls.prompts = cls.nodes.prompts

    def test_away_cards_get_counter_example_instructions(self):
        refs = [
            {"role": "style", "subject_policy": "avoid", "direction": "away"},
            {"role": "identity", "subject_policy": "preserve", "direction": "toward"},
        ]
        text = self.prompts.role_system_prompt(refs, False)
        self.assertIn("Input 1 role: treat as a style counter-example", text)
        self.assertIn("Input 2 role: preserve the main source subject", text)
        self.assertIn("Input 2 subject rule:", text)

    def test_focus_line_appears_in_the_system_prompt(self):
        refs = [
            {"role": "style", "subject_policy": "avoid", "direction": "toward",
             "focus": "the clothing and garment style"},
            {"role": "lighting", "subject_policy": "avoid", "direction": "toward"},
        ]
        text = self.prompts.role_system_prompt(refs, False)
        self.assertIn(
            "Input 1 focus: study only the clothing and garment style from this image; "
            "ignore everything else about it.",
            text,
        )
        # The focus line sits between the role line and the subject rule.
        self.assertLess(text.index("Input 1 role:"), text.index("Input 1 focus:"))
        self.assertLess(text.index("Input 1 focus:"), text.index("Input 1 subject rule:"))
        # A ref without focus gains no focus line.
        self.assertNotIn("Input 2 focus:", text)

    def test_focus_scopes_away_cards_too(self):
        refs = [{"role": "style", "subject_policy": "avoid", "direction": "away",
                 "focus": "the color palette"}]
        text = self.prompts.role_system_prompt(refs, False)
        self.assertIn("Input 1 role: treat as a style counter-example", text)
        self.assertIn(
            "Input 1 focus: only the color palette from this image; its other aspects do not apply.",
            text,
        )

    def test_blank_prompt_mentions_counter_examples(self):
        refs = [
            {"role": "identity", "subject_policy": "preserve", "direction": "toward"},
            {"role": "style", "subject_policy": "avoid", "direction": "away"},
        ]
        text = self.prompts.blank_prompt(refs, False)
        self.assertIn("Steer the overall result away from each counter-example source's look.", text)

    def test_blank_prompt_with_only_away_cards_still_says_something(self):
        refs = [{"role": "style", "subject_policy": "avoid", "direction": "away"}]
        text = self.prompts.blank_prompt(refs, False)
        self.assertIn("Create a new clean cohesive image.", text)
        self.assertIn("counter-example", text)

    def test_sanitizer_rewrites_spanish_and_german_marking_words(self):
        text = self.prompts.sanitize_text_logo_prompt("un letrero sin texto")
        self.assertIn("plain blank board", text)
        self.assertIn("plain unmarked", text)
        self.assertNotIn("letrero", text)

        text = self.prompts.sanitize_text_logo_prompt("ein Schild ohne Text, ein Plakat")
        self.assertIn("plain blank board", text)
        self.assertIn("plain unmarked", text)
        self.assertIn("plain blank panel", text)
        self.assertNotIn("Schild", text)
        self.assertNotIn("Plakat", text)

    def test_sanitizer_leaves_english_collision_words_alone(self):
        text = self.prompts.sanitize_text_logo_prompt(
            "a drug cartel film scene, proper etiquette, a parole meeting"
        )
        self.assertIn("cartel", text)
        self.assertIn("etiquette", text)
        self.assertIn("parole", text)

    def test_v9_english_sanitizer_still_runs(self):
        text = self.prompts.sanitize_text_logo_prompt("a shop sign with no text")
        self.assertIn("plain blank board", text)
        self.assertIn("plain unmarked", text)


if __name__ == "__main__":
    unittest.main()
