"""Tests for the Concept Slider V1 package (kg_krea_slider/).

Covers five layers:

1. Label contracts - the card/stack widget surfaces, packet keys, link
   type, and root registration are the saved-workflow API (append-only).
2. Card behavior - packet contents, value clamping, text normalization.
3. Pole and span math - auto pole templates, the tokenization ladder, and
   divergence-based span discovery (including the BPE boundary-merge case
   and the text-only guard).
4. Encoder behavior - collect/skip rules, weight math, muted-span
   complements per encode, compose weights, study-cache reuse, and the
   slider report.
5. Hook behavior - multi-span muting zeroes embeds and attention and
   always restores the model.
"""

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _kg_stub_env import load_module

CARD_LABELS = [
    "What this slider changes",
    "Slider value",
    "What +6 looks like (optional)",
    "What -6 looks like (optional)",
]

STACK_REQUIRED_LABELS = [
    "Krea CLIP",
    "Final image prompt",
    "Overall slider reach",
    "Reuse slider studies",
]

STACK_SLIDER_LABELS = [f"Slider {i}" for i in range(1, 9)]

PACKET_KEYS = {"kg_slider_version", "description", "value", "increase_text", "decrease_text"}


class FakeSliderClip:
    """Word-level fake of the Qwen tokenizer: prefix-stable, template-shaped.

    Rows look like [im_start, 9, nl, im_start, user, nl, <word ids>, im_end]
    so the real krea_user_content_start / find_prompt_bounds analysis runs.
    """

    IM_START, IM_END, USER, NL = 151644, 151645, 872, 198

    def __init__(self):
        self.vocab = {}
        self.tokenize_calls = []

    def word_ids(self, text):
        ids = []
        for word in str(text).split():
            if word not in self.vocab:
                self.vocab[word] = 5000 + len(self.vocab)
            ids.append(self.vocab[word])
        return ids

    def tokenize(self, text):
        self.tokenize_calls.append(text)
        row = [self.IM_START, 9, self.NL, self.IM_START, self.USER, self.NL]
        row += self.word_ids(text)
        row += [self.IM_END]
        return {"qwen": [row]}


def patch_slider_machinery(cls, captured):
    original = {
        name: vars(cls)[name]
        for name in ("_encode_with_spans", "_conditioning_delta", "_compose_conditioning")
    }

    def fake_encode(clip, tokens, muted_spans):
        calls = captured.setdefault("encode_calls", [])
        calls.append(list(muted_spans))
        return ["enc:{}".format(len(calls))]

    def fake_delta(plus_conditioning, minus_conditioning):
        captured.setdefault("delta_calls", []).append((plus_conditioning, minus_conditioning))
        return ("axis", plus_conditioning[0], minus_conditioning[0])

    def fake_compose(base_conditioning, weighted_axes):
        captured.setdefault("compose_calls", []).append((base_conditioning, list(weighted_axes)))
        return ["composed"]

    cls._encode_with_spans = staticmethod(fake_encode)
    cls._conditioning_delta = staticmethod(fake_delta)
    cls._compose_conditioning = staticmethod(fake_compose)
    return original


def restore_slider_machinery(cls, original):
    for name, value in original.items():
        setattr(cls, name, value)


def card_packet(nodes, description="brightness", value=0.0, increase="", decrease=""):
    card = nodes.KGKrea2ConceptSliderCardV1()
    (packet,) = card.build(**{
        "What this slider changes": description,
        "Slider value": value,
        "What +6 looks like (optional)": increase,
        "What -6 looks like (optional)": decrease,
    })
    return packet


def run_stack(nodes, clip, prompt, packets, reach=1.0, reuse="reuse between runs - faster tuning"):
    stack = nodes.KGKrea2ConceptSliderStackV1()
    kwargs = {
        "Krea CLIP": clip,
        "Final image prompt": prompt,
        "Overall slider reach": reach,
        "Reuse slider studies": reuse,
    }
    for i, packet in enumerate(packets, start=1):
        kwargs[f"Slider {i}"] = packet
    return stack.execute(**kwargs)


class SliderLabelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_slider", "kg_krea_slider_under_test")

    def test_card_labels_are_frozen(self):
        inputs = self.nodes.KGKrea2ConceptSliderCardV1.INPUT_TYPES()
        self.assertEqual(list(inputs["required"].keys()), CARD_LABELS)
        self.assertNotIn("optional", inputs)

    def test_card_value_widget_is_a_bipolar_slider(self):
        inputs = self.nodes.KGKrea2ConceptSliderCardV1.INPUT_TYPES()
        kind, config = inputs["required"]["Slider value"]
        self.assertEqual(kind, "FLOAT")
        self.assertEqual(config["default"], 0.0)
        self.assertEqual(config["min"], -6.0)
        self.assertEqual(config["max"], 6.0)
        self.assertEqual(config["display"], "slider")

    def test_stack_labels_are_frozen(self):
        inputs = self.nodes.KGKrea2ConceptSliderStackV1.INPUT_TYPES()
        self.assertEqual(list(inputs["required"].keys()), STACK_REQUIRED_LABELS)
        self.assertEqual(list(inputs["optional"].keys()), STACK_SLIDER_LABELS)
        for label in STACK_SLIDER_LABELS:
            self.assertEqual(inputs["optional"][label], ("KG_KREA_SLIDER",))

    def test_node_outputs_and_category(self):
        card = self.nodes.KGKrea2ConceptSliderCardV1
        stack = self.nodes.KGKrea2ConceptSliderStackV1
        self.assertEqual(card.RETURN_TYPES, ("KG_KREA_SLIDER",))
        self.assertEqual(card.RETURN_NAMES, ("slider",))
        self.assertEqual(stack.RETURN_TYPES, ("CONDITIONING", "STRING"))
        self.assertEqual(stack.RETURN_NAMES, ("conditioning", "slider_report"))
        self.assertEqual(card.CATEGORY, "advanced/conditioning")
        self.assertEqual(stack.CATEGORY, "advanced/conditioning")

    def test_packet_keys_are_frozen_and_versioned(self):
        packet = card_packet(self.nodes, "height", 2.5, "a very tall person", "a very short person")
        self.assertEqual(set(packet.keys()), PACKET_KEYS)
        self.assertEqual(packet["kg_slider_version"], 1)

    def test_slider_range_is_six(self):
        self.assertEqual(self.nodes.encoder.SLIDER_RANGE, 6.0)

    def test_root_package_registers_both_nodes(self):
        root_init = (Path(__file__).resolve().parents[1] / "__init__.py").read_text(encoding="utf-8")
        for key in ("KGKrea2ConceptSliderCardV1", "KGKrea2ConceptSliderStackV1"):
            self.assertGreaterEqual(root_init.count(key), 3, key)
        self.assertIn("KG Krea 2 Concept Slider Card V1", root_init)
        self.assertIn("KG Krea 2 Concept Slider Stack V1", root_init)


class SliderCardBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_slider", "kg_krea_slider_card_tests")

    def test_packet_carries_normalized_fields(self):
        packet = card_packet(self.nodes, "  brightness  ", 3.0, " sunlit ", "")
        self.assertEqual(packet["description"], "brightness")
        self.assertEqual(packet["value"], 3.0)
        self.assertEqual(packet["increase_text"], "sunlit")
        self.assertEqual(packet["decrease_text"], "")

    def test_value_is_clamped_to_the_dial(self):
        self.assertEqual(card_packet(self.nodes, value=9.5)["value"], 6.0)
        self.assertEqual(card_packet(self.nodes, value=-11.0)["value"], -6.0)


class SliderPoleAndSpanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_slider", "kg_krea_slider_pole_tests")
        cls.poles = cls.nodes.poles

    def test_auto_pole_texts_are_parallel(self):
        plus, minus = self.poles.auto_pole_texts("brightness")
        self.assertEqual(plus, "Extremely high brightness, maximum brightness.")
        self.assertEqual(minus, "Extremely low brightness, minimum brightness.")

    def test_auto_pole_texts_normalize_the_description(self):
        plus, minus = self.poles.auto_pole_texts("  Height. ")
        self.assertEqual(plus, "Extremely high Height, maximum Height.")
        self.assertEqual(minus, "Extremely low Height, minimum Height.")
        self.assertEqual(self.poles.auto_pole_texts(""), ("", ""))

    def test_pole_sentence_normalizes_and_terminates(self):
        self.assertEqual(self.poles.pole_sentence(" a  very tall person "), "a very tall person.")
        self.assertEqual(self.poles.pole_sentence("dark!"), "dark!")
        self.assertEqual(self.poles.pole_sentence("   "), "")

    def test_prefix_texts_ladder(self):
        sliders = [{"plus_text": "P1.", "minus_text": "M1."}]
        self.assertEqual(
            self.poles.prefix_texts("a cat", sliders),
            ["a cat", "a cat\n\nP1.", "a cat\n\nP1.\nM1."],
        )
        self.assertEqual(self.poles.prefix_texts("", sliders), ["", "P1.", "P1.\nM1."])

    def test_pole_spans_cover_each_sentence_exactly(self):
        clip = FakeSliderClip()
        sliders = [
            {"plus_text": "Extremely high brightness.", "minus_text": "Extremely low brightness."},
            {"plus_text": "a very tall person.", "minus_text": "a very short person."},
        ]
        texts = self.poles.prefix_texts("a man in a park", sliders)
        rows = [clip.tokenize(text)["qwen"][0] for text in texts]
        spans = self.poles.pole_spans(rows)
        self.assertEqual(len(spans), 4)

        final_row = rows[-1]
        expected_sentences = [
            sliders[0]["plus_text"], sliders[0]["minus_text"],
            sliders[1]["plus_text"], sliders[1]["minus_text"],
        ]
        for span, sentence in zip(spans, expected_sentences):
            start, end = span
            self.assertEqual(final_row[start:end], clip.word_ids(sentence), sentence)

        # Spans are disjoint, ascending, and stop at the written content end.
        for (start_a, end_a), (start_b, end_b) in zip(spans, spans[1:]):
            self.assertLessEqual(end_a, start_b)
        self.assertEqual(spans[-1][1], len(final_row) - 1)

    def test_pole_spans_tolerate_a_boundary_merge(self):
        # Simulate a BPE merge: appending the second sentence retro-changes
        # the last token of the first (Y -> Z). The divergence point moves
        # one token early; spans stay disjoint and inside the content.
        prefix = [151644, 9, 198, 151644, 872, 198]
        row_0 = prefix + [5000, 151645]
        row_1 = prefix + [5000, 5001, 5002, 151645]
        row_2 = prefix + [5000, 5001, 5003, 5004, 5005, 151645]
        spans = self.poles.pole_spans([row_0, row_1, row_2])
        self.assertEqual(spans, [(7, 8), (8, 11)])

    def test_image_rows_are_rejected(self):
        row_with_image = [151644, 9, 198, {"type": "image"}, 151645]
        with self.assertRaises(RuntimeError):
            self.poles.pole_spans([[151644, 9, 198, 151645], row_with_image])


class SliderEncoderBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_slider", "kg_krea_slider_encoder_tests")

    def setUp(self):
        self.captured = {}
        self.original = patch_slider_machinery(self.nodes.KGKrea2ConceptSliderStackV1, self.captured)
        self.nodes.cache.reset()

    def tearDown(self):
        restore_slider_machinery(self.nodes.KGKrea2ConceptSliderStackV1, self.original)
        self.nodes.cache.reset()

    def test_collect_skips_idle_and_empty_sliders(self):
        stack = self.nodes.KGKrea2ConceptSliderStackV1()
        kwargs = {
            "Slider 1": card_packet(self.nodes, "brightness", 0.0),
            "Slider 2": card_packet(self.nodes, "", 2.0),
            "Slider 3": "not a packet",
            "Slider 4": card_packet(self.nodes, "height", -3.0),
        }
        active, skipped = stack._collect_sliders(kwargs, reach=1.0)
        self.assertEqual([slider["index"] for slider in active], [4])
        reasons = {skip["index"]: skip["reason"] for skip in skipped}
        self.assertEqual(reasons[1], "at 0 - costs nothing")
        self.assertEqual(reasons[2], "no description or pole text")
        self.assertEqual(reasons[3], "not a slider packet")

    def test_weight_math_is_linear_and_bipolar(self):
        stack = self.nodes.KGKrea2ConceptSliderStackV1()
        active, _ = stack._collect_sliders({
            "Slider 1": card_packet(self.nodes, "brightness", 3.0),
            "Slider 2": card_packet(self.nodes, "height", -6.0),
        }, reach=1.0)
        self.assertAlmostEqual(active[0]["weight"], 1.0)
        self.assertAlmostEqual(active[1]["weight"], -2.0)

        boosted, _ = stack._collect_sliders(
            {"Slider 1": card_packet(self.nodes, "brightness", 6.0)}, reach=3.0
        )
        self.assertAlmostEqual(boosted[0]["weight"], 6.0)

    def test_execute_mutes_the_right_span_complements(self):
        clip = FakeSliderClip()
        packets = [
            card_packet(self.nodes, "brightness", 3.0),
            card_packet(self.nodes, "height", -2.0, "a very tall person", "a very short person"),
        ]
        conditioning, report = run_stack(self.nodes, clip, "a man in a park", packets)

        encode_calls = self.captured["encode_calls"]
        self.assertEqual(len(encode_calls), 5)
        all_spans = encode_calls[0]
        self.assertEqual(len(all_spans), 4)
        for pole_position in range(4):
            expected = [span for i, span in enumerate(all_spans) if i != pole_position]
            self.assertEqual(encode_calls[1 + pole_position], expected)

        base, weighted = self.captured["compose_calls"][0]
        self.assertEqual(base, ["enc:1"])
        self.assertEqual(len(weighted), 2)
        self.assertAlmostEqual(weighted[0][1], 1.0)
        self.assertAlmostEqual(weighted[1][1], -2.0 / 3.0)
        self.assertEqual(conditioning, ["composed"])
        self.assertIn('Slider 1 "brightness" at +3.00 -> push +1.00', report)
        self.assertIn('increase (auto): "Extremely high brightness, maximum brightness."', report)
        self.assertIn('increase: "a very tall person."', report)

    def test_execute_without_sliders_is_a_plain_encode(self):
        clip = FakeSliderClip()
        conditioning, report = run_stack(self.nodes, clip, "a cat", [])
        self.assertEqual(self.captured["encode_calls"], [[]])
        self.assertNotIn("compose_calls", self.captured)
        self.assertEqual(conditioning, ["enc:1"])
        self.assertIn("no sliders connected", report)

    def test_zero_value_slider_costs_nothing_and_reports_it(self):
        clip = FakeSliderClip()
        conditioning, report = run_stack(
            self.nodes, clip, "a cat", [card_packet(self.nodes, "brightness", 0.0)]
        )
        self.assertEqual(self.captured["encode_calls"], [[]])
        self.assertEqual(conditioning, ["enc:1"])
        self.assertIn("Slider 1 skipped - at 0 - costs nothing", report)

    def test_value_only_reruns_are_compose_only(self):
        clip = FakeSliderClip()
        first_packets = [card_packet(self.nodes, "brightness", 3.0)]
        run_stack(self.nodes, clip, "a cat", first_packets)
        self.assertEqual(len(self.captured["encode_calls"]), 3)

        _, report = run_stack(self.nodes, clip, "a cat", [card_packet(self.nodes, "brightness", -1.5)])
        self.assertEqual(len(self.captured["encode_calls"]), 3)
        self.assertIn("encoder passes: 0 new, 3 reused", report)
        _, weighted = self.captured["compose_calls"][-1]
        self.assertAlmostEqual(weighted[0][1], -0.5)

    def test_always_re_study_bypasses_the_cache(self):
        clip = FakeSliderClip()
        packets = [card_packet(self.nodes, "brightness", 3.0)]
        run_stack(self.nodes, clip, "a cat", packets, reuse="always re-study")
        run_stack(self.nodes, clip, "a cat", packets, reuse="always re-study")
        self.assertEqual(len(self.captured["encode_calls"]), 6)

    def test_twin_sliders_share_one_study(self):
        clip = FakeSliderClip()
        packets = [
            card_packet(self.nodes, "brightness", 2.0),
            card_packet(self.nodes, "brightness", 5.0),
        ]
        _, report = run_stack(self.nodes, clip, "a cat", packets)
        self.assertEqual(len(self.captured["encode_calls"]), 3)
        _, weighted = self.captured["compose_calls"][0]
        self.assertEqual(len(weighted), 2)
        self.assertIn("2 reused", report)


class SliderHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module("kg_krea_slider", "kg_krea_slider_hook_tests")

    class MiniEmbeds:
        def __init__(self, length, fill=1.0):
            self.values = [fill] * length
            self.shape = (1, length)

        def clone(self):
            copy = type(self)(len(self.values))
            copy.values = list(self.values)
            return copy

        def __setitem__(self, key, value):
            _, span = key
            for i in range(span.start, span.stop):
                self.values[i] = float(value)

    class MiniMask(MiniEmbeds):
        def __iter__(self):
            row_sum = sum(self.values)
            yield types.SimpleNamespace(sum=lambda: types.SimpleNamespace(item=lambda: row_sum))

    def make_clip(self, length):
        test_case = self

        class MiniModel:
            def __init__(self):
                self.original_process_tokens = None

            def process_tokens(self, tokens, device):
                return (
                    test_case.MiniEmbeds(length),
                    test_case.MiniMask(length, fill=1),
                    [length],
                    [],
                )

        model = MiniModel()

        class MiniClip:
            def __init__(self):
                self.cond_stage_model = types.SimpleNamespace(clip="qwen", qwen=model)

            def encode_from_tokens_scheduled(self, tokens):
                embeds, mask, num_tokens, _info = model.process_tokens(tokens, "cpu")
                return [[embeds, {"num_tokens": num_tokens}]]

        return MiniClip(), model

    def test_muted_spans_zero_embeds_and_attention(self):
        clip, model = self.make_clip(10)
        result = self.nodes.hooks.encode_with_muted_spans(clip, {"qwen": [[1]]}, [(2, 4), (6, 8)])
        embeds, extras = result[0]
        self.assertEqual(embeds.values, [1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0])
        self.assertEqual(extras["num_tokens"], [6])
        # The model is restored: encoding again outside the hook is unmuted.
        embeds_after, extras_after = clip.encode_from_tokens_scheduled({"qwen": [[1]]})[0]
        self.assertEqual(embeds_after.values, [1.0] * 10)
        self.assertEqual(extras_after["num_tokens"], [10])

    def test_empty_spans_encode_untouched(self):
        clip, model = self.make_clip(4)
        result = self.nodes.hooks.encode_with_muted_spans(clip, {"qwen": [[1]]}, [])
        embeds, extras = result[0]
        self.assertEqual(embeds.values, [1.0, 1.0, 1.0, 1.0])
        self.assertEqual(extras["num_tokens"], [4])

    def test_unknown_model_shapes_encode_without_patching(self):
        class BareClip:
            def encode_from_tokens_scheduled(self, tokens):
                return [["bare", {}]]

        result = self.nodes.hooks.encode_with_muted_spans(BareClip(), {"qwen": [[1]]}, [(0, 2)])
        self.assertEqual(result, [["bare", {}]])


if __name__ == "__main__":
    unittest.main()
