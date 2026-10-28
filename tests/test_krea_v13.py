"""Scalar/control-flow carrier fixtures; no Torch, weights or neural proof."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as NS, ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import test_krea_v12 as fixture
from native_v12_tests import studies as legacy, ledger

parent = ModuleType("carrier_experiment")
parent.__path__ = [str(ROOT)]
sys.modules[parent.__name__] = parent
for key, module in list(sys.modules.items()):
    if key == "native_v12_tests" or key.startswith("native_v12_tests."):
        sys.modules[
            "carrier_experiment.kg_krea_v12" + key[len("native_v12_tests") :]
        ] = module
spec = importlib.util.spec_from_file_location(
    "carrier_experiment.kg_krea_v13",
    ROOT / "kg_krea_v13/__init__.py",
    submodule_search_locations=[str(ROOT / "kg_krea_v13")],
)
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from carrier_experiment.kg_krea_v13 import studies, nodes
from carrier_experiment.kg_krea_v13.conditioning import construct


class IndexedBuffer(fixture.Buffer):
    def __setitem__(self, index, value):
        _, positions = index
        indices = (
            list(range(len(self.values)))[positions]
            if isinstance(positions, slice)
            else list(positions)
        )
        values = (
            value.values
            if isinstance(value, fixture.Buffer)
            else [value] * len(indices)
        )
        if len(values) != len(indices):
            raise ValueError("Fixture assignment shape differs")
        for i, v in zip(indices, values):
            self.values[i] = v


class CarrierTests(unittest.TestCase):
    def setUp(self):
        self.buffer = patch.object(fixture, "Buffer", IndexedBuffer)
        self.buffer.start()
        self.addCleanup(self.buffer.stop)
        self.f = fixture.NativeV12Tests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.traces = []

        def causal_encode(tokens):
            self.f.clip.encodes += 1
            raw = [[ledger.element(item) for item in tokens[ledger.TOKEN_KEY][0]]]
            embeds, mask, _, _ = self.f.clip.encoder.process_tokens(raw, "synthetic")
            values = []
            context = 0
            for value, enabled in zip(embeds.values, mask.values):
                context += value * enabled
                values.append(value + context)
            strip = ledger.native_output_start(tokens[ledger.TOKEN_KEY][0])
            result = [
                [
                    IndexedBuffer(values[strip:], 30720),
                    {
                        "attention_mask": IndexedBuffer(mask.values[strip:], mask=True),
                        "foreign": self.f.clip,
                    },
                ]
            ]
            self.traces.append(result)
            return result

        self.f.clip.encode_from_tokens_scheduled = causal_encode
        self.context = self.f.prepare()
        self.traces.clear()
        self.addCleanup(self.f.assert_clean)

    def test_zero_empty_and_cancellation_native_identity_no_encoding(self):
        for cards in ([], [fixture.card(0)], [fixture.card(1), fixture.card(-1)]):
            before = self.f.clip.encodes
            result = studies.build_carrier_studies(self.context, cards)
            self.assertFalse(result.active)
            self.assertEqual(result.encode_passes, 0)
            self.assertIs(result.phases[1], self.context.native)
            self.assertEqual(self.f.clip.encodes, before)

    def test_signed_carriers_real_states_and_original_arithmetic_preserved(self):
        for weight in (1, -1):
            with self.subTest(weight=weight):
                old = legacy.build_studies(self.context, [fixture.card(weight)])
                self.traces.clear()
                new = studies.build_carrier_studies(
                    self.context, [fixture.card(weight)]
                )
                self.assertEqual(len(self.traces), 3)
                self.assertEqual(new.encode_passes, 3)
                native_positions = new.retained_output_positions
                keep = new.carrier_output_positions[0]
                mapping = {old: new for new, old in enumerate(keep)}
                actual = new.phases[1]["positive"][0][0].values
                self.assertEqual(
                    [actual[mapping[i]] for i in native_positions],
                    old.phases[1]["positive"][0][0].values,
                )
                expanded = new.ledgers[0]
                which = 0 if weight > 0 else 1
                span = expanded.output_span(expanded.poles[which])
                native_pass = self.traces[1 if weight > 0 else 2][0][0].values
                self.assertEqual(
                    [actual[mapping[i]] for i in range(*span)],
                    native_pass[span[0] : span[1]],
                )
                other = expanded.output_span(expanded.poles[1 - which])
                self.assertFalse(set(range(*other)).intersection(keep))
                self.assertIs(
                    new.phases[1]["negative"], self.context.native["negative"]
                )
                for key in ("model", "source_latent", "target_latent", "noise_mask"):
                    self.assertIs(new.phases[1][key], self.context.native[key])
                self.assertEqual(
                    new.phases[1]["positive"][0][1]["attention_mask"].values,
                    [1] * len(keep),
                )
                self.assertIs(new.phases[1]["positive"][0][1]["foreign"], self.f.clip)

    def test_causal_source_image_states_unchanged_and_timing_native_off_phase(self):
        result = studies.build_carrier_studies(
            self.context, [fixture.card(1, "final-details")]
        )
        self.assertIs(result.phases[1], self.context.native)
        self.assertEqual(result.carrier_output_positions[0], ())
        keep = result.carrier_output_positions[1]
        mapping = {old: new for new, old in enumerate(keep)}
        image_positions = []
        for _, start, end in result.ledgers[0].images:
            image_positions.extend(
                range(start - result.ledgers[0].strip, end - result.ledgers[0].strip)
            )
        nmap = {full: i for i, full in enumerate(result.retained_output_positions)}
        actual = result.phases[2]["positive"][0][0].values
        self.assertEqual(
            [actual[mapping[i]] for i in image_positions],
            [
                self.context.native["positive"][0][0].values[nmap[i]]
                for i in image_positions
            ],
        )

    def test_small_load_has_two_bounded_native_branches(self):
        result = studies.build_carrier_studies(self.context, [fixture.card(0.01)])
        positive = result.phases[1]["positive"]
        self.assertEqual(len(positive), 2)
        self.assertIs(positive[0][0], self.context.native["positive"][0][0])
        self.assertAlmostEqual(positive[0][1]["strength"], 0.96)
        self.assertAlmostEqual(positive[1][1]["strength"], 0.04)

    def test_joint_axes_shared_encodes_and_budget_never_amplifies(self):
        result = studies.build_carrier_studies(
            self.context,
            [fixture.card(3, axis="first"), fixture.card(-3, axis="second")],
            budget=2,
        )
        self.assertEqual(result.encode_passes, 5)
        self.assertEqual(result.budget_scales, (1 / 3, 1 / 3))
        keep = result.carrier_output_positions[0]
        e = result.ledgers[0]
        for index in (0, 3):
            self.assertTrue(set(range(*e.output_span(e.poles[index]))).issubset(keep))
        for index in (1, 2):
            self.assertFalse(
                set(range(*e.output_span(e.poles[index]))).intersection(keep)
            )

    def test_carrier_budget_rejects_before_study_encoder(self):
        before = self.f.clip.encodes
        with self.assertRaisesRegex(RuntimeError, "carrier budget"):
            studies.build_carrier_studies(
                self.context, [fixture.card(1, plus="b" * 300, minus="d" * 300)]
            )
        self.assertEqual(self.f.clip.encodes, before)

    def test_encoder_failure_cleanup_and_input_metadata_unchanged(self):
        mask = self.context.native["positive"][0][1]["attention_mask"]
        before = mask.values.copy()
        with patch.object(
            self.f.clip,
            "encode_from_tokens_scheduled",
            side_effect=ValueError("encode failed"),
        ):
            with self.assertRaisesRegex(ValueError, "encode failed"):
                studies.build_carrier_studies(self.context, [fixture.card()])
        self.assertEqual(mask.values, before)

    def test_type_and_cfg_bound_before_host_loading_and_zero_guider_identity(self):
        from native_v12_tests import consumer

        active = studies.build_carrier_studies(self.context, [fixture.card()])
        with patch.object(
            consumer, "load_consumer_host", side_effect=AssertionError("host read")
        ):
            with self.assertRaisesRegex(RuntimeError, "CFG1"):
                studies.bind_carrier_guider(active, NS(cfg=2))
            neutral = studies.build_carrier_studies(self.context, [])
            guider = NS(model_patcher=self.context.native["model"])
            self.assertIs(studies.bind_carrier_guider(neutral, guider), guider)
        old = legacy.build_studies(self.context, [])
        with self.assertRaisesRegex(ValueError, "V13"):
            studies.bind_carrier_guider(old, NS(cfg=1))

    def test_new_type_prevents_legacy_study_connection(self):
        self.assertNotEqual(
            nodes.CARRIER_STUDIES_TYPE, fixture.NODES.nodes.STUDIES_TYPE
        )
        self.assertEqual(
            nodes.KGKrea2NativeCarrierPhaseGuiderV13.INPUT_TYPES()["required"][
                "Carrier studies"
            ],
            (nodes.CARRIER_STUDIES_TYPE,),
        )

    def test_cfg_bound_is_rechecked_at_sample(self):
        native_guider = NS(cfg=2, model_patcher=object())
        proxy = studies.CarrierPhaseGuider(native_guider, object(), object())
        with self.assertRaisesRegex(RuntimeError, "throughout sampling"):
            proxy.sample()

    def test_real_cpu_tensor_carrier_assignment_and_mask_preservation(self):
        try:
            import torch
        except ImportError:
            self.skipTest("Optional Torch CPU boundary unavailable")
        # Actual tensor indexing/dtypes only. No model or native encoder is run.
        for dtype in (torch.float32, torch.bfloat16):
            with self.subTest(dtype=dtype):
                full = (
                    torch.arange(12 * 24, dtype=torch.float32)
                    .reshape(1, 12, 24)
                    .to(dtype)
                )
                retained = (0, 1, 2, 9, 10, 11)
                mask = torch.tensor([[1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1]])
                original = full[:, list(retained)].clone()
                native_mask = mask[:, list(retained)].clone()
                native_mask[:, 1] = 0
                foreign = object()
                native = [
                    [original, {"attention_mask": native_mask, "foreign": foreign}]
                ]
                projected = [[original + 2, native[0][1].copy()]]
                base = [[full, {"attention_mask": mask}]]
                plus, minus = full[:, 3:6] + 8, full[:, 6:9] - 4
                # Unit selection must copy actual states rather than incur
                # cancellation in B+(P-B) when native encodes differ greatly.
                full[:, 3:6] = 100000000
                plus[:] = 1.125
                poles = [((3, 6), (6, 9), plus, minus)]
                for weight in (1, -1, 0.5):
                    actual, keep = construct(
                        native, projected, base, retained, poles, [weight]
                    )
                    positions = {old: new for new, old in enumerate(keep)}
                    value, metadata = actual[0]
                    torch.testing.assert_close(
                        value[:, [positions[i] for i in retained]],
                        projected[0][0],
                        rtol=0,
                        atol=0,
                    )
                    span, selected = ((3, 6), plus) if weight > 0 else ((6, 9), minus)
                    indexes = list(range(*span))
                    expected = (
                        selected
                        if abs(weight) == 1
                        else full[:, indexes]
                        + (selected - full[:, indexes]) * abs(weight)
                    )
                    torch.testing.assert_close(
                        value[:, [positions[i] for i in indexes]],
                        expected,
                        rtol=0,
                        atol=0,
                    )
                    self.assertEqual(value.dtype, dtype)
                    self.assertIs(metadata["foreign"], foreign)
                    self.assertEqual(
                        metadata["attention_mask"][
                            :, [positions[i] for i in retained]
                        ].tolist(),
                        native_mask.tolist(),
                    )
                    self.assertEqual(
                        metadata["attention_mask"][
                            :, [positions[i] for i in indexes]
                        ].tolist(),
                        [[1, 1, 1]],
                    )
                self.assertEqual(mask.tolist(), [[1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1]])
                torch.testing.assert_close(native[0][0], original, rtol=0, atol=0)
                actual, keep = construct(native, projected, base, retained, poles, [0])
                self.assertIs(actual, native)
                self.assertEqual(keep, retained)


if __name__ == "__main__":
    unittest.main()
