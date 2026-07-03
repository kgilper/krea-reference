"""Tests for the Krea V10 package (kg_krea_v10/).

Covers four layers:

1. Label contracts - the V10 widget surface is the V9 surface plus appended
   rows, and packets stay V9-compatible.
2. Card behavior - the new recipes, direction, timing, and layer dials.
3. Encoder behavior - away-card target math, balance budgets, the study
   cache, the stack report, and V9-packet cross-compatibility.
4. Prompt behavior - direction-aware system prompts and the multilingual
   text/logo guard vocabulary.
"""

import sys
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
        purposes = list(self.nodes.KGKrea2ImageGuideCardV10.INPUT_TYPES()["required"]["Use image for"][0])
        self.assertEqual(
            purposes,
            [
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
            ],
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
