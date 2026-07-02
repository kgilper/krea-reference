"""Tests for the Krea V9 package (kg_krea_v9/).

Covers three layers:

1. Label contracts - widget labels are the saved-workflow API surface.
2. Guard behavior - the V9 prompt-handling choice (full vs gentle guard).
3. Numerical math - conditioning deltas, per-layer composition, the
   divisibility fallback (with its one-time warning), and the per-layer
   soft cap, exercised with a pure-Python tensor stub.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _kg_stub_env import FakeTensor, load_module


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
            "_prepare_image_v9",
        )
    }

    def fake_compose(conditioning, weighted_deltas):
        captured.setdefault("compose_calls", []).append(weighted_deltas)
        return ["composed"]

    cls._tag_image_references = staticmethod(lambda tokens: None)
    cls._encode_with_controls = staticmethod(lambda clip, tokens, **kwargs: ["base"])
    cls._conditioning_delta = staticmethod(lambda conditioning, muted: "image-delta")
    cls._apply_prompt_delta = staticmethod(lambda conditioning, muted: "prompt-delta")
    cls._compose_conditioning = staticmethod(fake_compose)
    cls._prepare_image_v9 = staticmethod(lambda image, res, fit, treat, det, color: "prepared")
    return original


def restore_encoder_machinery(cls, original):
    for name, value in original.items():
        setattr(cls, name, value)


class KreaV9LabelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v9", "kg_krea_v9_under_test")

    def test_v9_is_fully_standalone(self):
        self.assertEqual(self.nodes.KGKrea2ImageGuideCardV9.__bases__, (object,))
        self.assertEqual(self.nodes.KGTextEncodeKreaImageReferencesV9.__bases__, (object,))
        for name in (
            "_tag_image_references",
            "_conditioning_delta",
            "_compose_conditioning",
            "_encode_with_controls",
            "_with_timestep_range",
            "_blur_samples",
            "_prepare_image_v9",
        ):
            self.assertIn(name, vars(self.nodes.KGTextEncodeKreaImageReferencesV9))

    def test_v9_card_labels_are_frozen(self):
        inputs = self.nodes.KGKrea2ImageGuideCardV9.INPUT_TYPES()["required"]
        self.assertEqual(
            list(inputs.keys()),
            [
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
            ],
        )

    def test_v9_stack_labels_are_frozen_and_add_guard_choice(self):
        inputs = self.nodes.KGTextEncodeKreaImageReferencesV9.INPUT_TYPES()
        self.assertEqual(
            list(inputs["required"].keys()),
            [
                "Krea CLIP",
                "Final image prompt",
                "Written prompt strength",
                "Image slider feel",
                "Image detail level",
                "Image framing",
                "When images guide",
                "Early-to-final handoff",
                "Text/logo guard prompt handling",
            ],
        )
        self.assertEqual(
            inputs["required"]["Text/logo guard prompt handling"][0],
            [
                "full guard - rewrite my prompt",
                "gentle guard - keep my prompt words",
            ],
        )
        self.assertEqual(
            list(inputs["optional"].keys()),
            [f"Reference {i} guide card" for i in range(1, 13)],
        )

    def test_v9_card_packet_is_versioned(self):
        card = self.nodes.KGKrea2ImageGuideCardV9().build(**{
            "Reference image": "img",
            "How strongly this image guides": 1.0,
            "Use image for": "avoid copying text/logos",
        })[0]
        self.assertEqual(card["source_version"], "v9")
        self.assertTrue(card["v9_blank_surface_guard"])
        self.assertEqual(card["v9_strength_cap"], 0.03)
        self.assertEqual(card["strength"], 0.03)

    def test_v9_max_layer_scale_constant(self):
        self.assertEqual(self.nodes.KGTextEncodeKreaImageReferencesV9.MAX_LAYER_SCALE, 6.0)


class KreaV9GuardBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v9", "kg_krea_v9_guard_tests")

    def _run_guarded(self, guard_mode, prompt="a shop sign with no text", prompt_strength=1.0):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV9
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            clip = FakeClip()
            card = self.nodes.KGKrea2ImageGuideCardV9().build(**{
                "Reference image": "img",
                "How strongly this image guides": 0.5,
                "Use image for": "avoid copying text/logos",
            })[0]
            cls().execute(**{
                "Krea CLIP": clip,
                "Final image prompt": prompt,
                "Written prompt strength": prompt_strength,
                "Image slider feel": "literal slider values",
                "When images guide": "guide the whole image",
                "Text/logo guard prompt handling": guard_mode,
                "Reference 1 guide card": card,
            })
            return clip.calls[0], captured
        finally:
            restore_encoder_machinery(cls, original)

    def test_full_guard_rewrites_prompt_and_floors_prompt_strength(self):
        call, captured = self._run_guarded("full guard - rewrite my prompt")
        text = call["text"]
        self.assertIn("plain blank board", text)
        self.assertIn("plain unmarked", text)
        self.assertNotIn("sign", text.replace("plain blank board", ""))
        prompt_entries = [e for e in captured["compose_calls"][0] if e[0] == "prompt-delta"]
        self.assertEqual(len(prompt_entries), 1)
        self.assertAlmostEqual(prompt_entries[0][1], 2.5)

    def test_gentle_guard_keeps_prompt_words_and_prompt_strength(self):
        call, captured = self._run_guarded("gentle guard - keep my prompt words")
        text = call["text"]
        # The artist's exact words survive; only the blank-surface suffix is added.
        self.assertIn("a shop sign with no text", text)
        self.assertIn("smooth empty blank panel", text)
        # Prompt strength stays at 1.0, so no prompt delta is composed.
        prompt_entries = [e for e in captured["compose_calls"][0] if e[0] == "prompt-delta"]
        self.assertEqual(prompt_entries, [])

    def test_gentle_guard_still_respects_explicit_prompt_strength(self):
        call, captured = self._run_guarded(
            "gentle guard - keep my prompt words", prompt_strength=2.0
        )
        prompt_entries = [e for e in captured["compose_calls"][0] if e[0] == "prompt-delta"]
        self.assertEqual(len(prompt_entries), 1)
        self.assertAlmostEqual(prompt_entries[0][1], 1.0)

    def test_layer_soft_cap_limits_token_layer_targets(self):
        cls = self.nodes.KGTextEncodeKreaImageReferencesV9
        captured = {}
        original = patch_encoder_machinery(cls, captured)
        try:
            clip = FakeClip()
            hot_card = {
                "image": "img",
                "strength": 2.0,
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
                "resolved_layer_pull": [5.0] * 12,
            }
            cls().execute(**{
                "Krea CLIP": clip,
                "Final image prompt": "a portrait",
                "Written prompt strength": 1.0,
                "Image slider feel": "literal slider values",
                "When images guide": "guide the whole image",
                "Text/logo guard prompt handling": "full guard - rewrite my prompt",
                "Reference 1 guide card": hot_card,
            })
            image_entries = [e for e in captured["compose_calls"][0] if e[0] == "image-delta"]
            self.assertEqual(len(image_entries), 1)
            _, token_weight, pooled_weight, token_layers = image_entries[0]
            self.assertAlmostEqual(token_weight, 1.0)  # strength 2.0 -> target - 1
            self.assertAlmostEqual(pooled_weight, 1.0)
            # Uncapped scale would be 2.0 * 5.0 = 10.0; V9 caps at 6.0 -> weight 5.0.
            self.assertEqual(token_layers, [5.0] * 12)
        finally:
            restore_encoder_machinery(cls, original)


class KreaV9NumericalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_v9", "kg_krea_v9_numeric_tests")
        cls.encoder = cls.nodes.KGTextEncodeKreaImageReferencesV9

    def setUp(self):
        self.nodes.conditioning._layer_fallback_warned = False

    @staticmethod
    def _conditioning(cond_values, pooled_values):
        return [[FakeTensor(cond_values), {"pooled_output": FakeTensor(pooled_values)}]]

    def test_conditioning_delta_subtracts_cond_and_pooled(self):
        full = self._conditioning([[[3.0, 5.0]]], [[2.0, 4.0]])
        muted = self._conditioning([[[1.0, 2.0]]], [[0.5, 1.0]])
        delta = self.encoder._conditioning_delta(full, muted)
        self.assertEqual(delta[0][0].tolist(), [[[2.0, 3.0]]])
        self.assertEqual(delta[0][1]["pooled_output"].tolist(), [[1.5, 3.0]])

    def test_conditioning_delta_rejects_shape_mismatch(self):
        full = self._conditioning([[[1.0, 2.0]]], [[1.0]])
        muted = self._conditioning([[[1.0, 2.0, 3.0]]], [[1.0]])
        with self.assertRaises(RuntimeError):
            self.encoder._conditioning_delta(full, muted)

    def test_compose_scalar_weights(self):
        base = self._conditioning([[[1.0, 1.0]]], [[2.0, 2.0]])
        delta = self._conditioning([[[4.0, 8.0]]], [[4.0, 8.0]])
        out = self.encoder._compose_conditioning(base, [(delta, 0.5, 0.25)])
        self.assertEqual(out[0][0].tolist(), [[[3.0, 5.0]]])
        self.assertEqual(out[0][1]["pooled_output"].tolist(), [[3.0, 4.0]])

    def test_compose_layer_weights_scale_each_chunk(self):
        layer_count = 12
        layer_dim = 2
        tokens = 2
        flat = layer_count * layer_dim
        base = self._conditioning([[[0.0] * flat for _ in range(tokens)]], [[0.0]])
        delta = self._conditioning([[[1.0] * flat for _ in range(tokens)]], [[0.0]])
        gains = [float(i) for i in range(layer_count)]  # 0.0 .. 11.0

        out = self.encoder._compose_conditioning(base, [(delta, 1.0, 0.0, gains)])
        row = out[0][0].tolist()[0][0]
        expected = []
        for gain in gains:
            expected.extend([gain] * layer_dim)
        self.assertEqual(row, expected)
        # Both token rows get the same per-layer scaling.
        self.assertEqual(out[0][0].tolist()[0][1], expected)

    def test_compose_layer_fallback_averages_and_warns_once(self):
        # 25 columns cannot split into 12 chunks -> flat average fallback.
        flat = 25
        base = self._conditioning([[[0.0] * flat]], [[0.0]])
        delta = self._conditioning([[[1.0] * flat]], [[0.0]])
        gains = [2.0] * 6 + [4.0] * 6  # average 3.0

        with self.assertLogs("kg_krea_v9_numeric_tests", level="WARNING") as logs:
            out = self.encoder._compose_conditioning(base, [(delta, 1.0, 0.0, gains)])
        self.assertTrue(any("does not split" in message for message in logs.output))
        self.assertEqual(out[0][0].tolist()[0][0], [3.0] * flat)

        # The warning fires once per process, not once per encode.
        self.assertTrue(self.nodes.conditioning._layer_fallback_warned)
        if hasattr(self, "assertNoLogs"):
            with self.assertNoLogs("kg_krea_v9_numeric_tests", level="WARNING"):
                self.encoder._compose_conditioning(base, [(delta, 1.0, 0.0, gains)])

    def test_strength_curves(self):
        curve = self.encoder._effective_image_strength_v9
        # Literal mode passes values through.
        self.assertEqual(curve(0.4, "linear"), 0.4)
        # Artist mode is soft at low values and has a hard zero below 0.01.
        self.assertEqual(curve(0.005, "artist"), 0.0)
        self.assertAlmostEqual(curve(0.5, "artist"), 0.5 ** 1.6)
        self.assertAlmostEqual(curve(2.0, "artist"), 1.0 + 1.0 * 1.15)
        # Extra gentle mode is softer still with a zero below 0.02.
        self.assertEqual(curve(0.02, "extra gentle"), 0.0)
        self.assertAlmostEqual(curve(0.5, "extra gentle"), 0.5 ** 2.7)
        # Negative inputs clamp to zero.
        self.assertEqual(curve(-1.0, "linear"), 0.0)

    def test_with_timestep_range_sets_percentages(self):
        base = self._conditioning([[[1.0]]], [[1.0]])
        ranged = self.encoder._with_timestep_range(base, 0.0, 0.4)
        self.assertEqual(ranged[0][1]["start_percent"], 0.0)
        self.assertEqual(ranged[0][1]["end_percent"], 0.4)
        # The original pooled dict is not mutated.
        self.assertNotIn("start_percent", base[0][1])


if __name__ == "__main__":
    unittest.main()
