"""Actual build_studies anchoring with deliberately different study/native bases."""
from types import SimpleNamespace as NS
import unittest

import test_krea_v12 as fixture
from native_v12_tests import hooks, ledger, native, studies


class OffsetStudyClip(fixture.Clip):
    """Declared scalar encoder boundary; controlled studies share a nonnative bias."""
    def __init__(self):
        super().__init__()
        self.study_outputs = []

    def encode_from_tokens_scheduled(self, tokens):
        result = super().encode_from_tokens_scheduled(tokens)
        if 'process_tokens' in vars(self.encoder):
            value, metadata = result[0]
            result = [[fixture.Buffer([item + 37 for item in value.values], value.width), metadata]]
            self.study_outputs.append(result)
        return result


class NativeAnchorTests(unittest.TestCase):
    def setUp(self):
        self.clip = OffsetStudyClip()
        self.model = NS(patches_uuid='native-anchor-model-v1', model_options={})
        fresh = self.clip.encode_from_tokens_scheduled(self.clip.tokenize('plain'))
        value, metadata = fresh[0]
        self.original_values = [item + 101 for item in value.values]
        self.marker = object()
        self.positive = [[fixture.Buffer(self.original_values, value.width),
                          {**metadata, 'original_native_marker': self.marker}]]
        self.negative = self.clip.encode_from_tokens_scheduled(self.clip.tokenize(''))
        self.mask = object()
        bundle = dict(model=self.model, positive=self.positive, negative=self.negative,
                      source_latent=object(), target_latent={'samples': object(), 'noise_mask': self.mask},
                      noise_mask=self.mask)
        self.context = native.prepare_context(self.clip, self.model, 'plain', revision='adopted-original-anchor', native_bundle=bundle)
        self.addCleanup(self.assert_clean)

    def assert_clean(self):
        self.context.verify()
        self.assertEqual(self.positive[0][0].values, self.original_values)
        self.assertNotIn('process_tokens', vars(self.clip.encoder))
        self.assertNotIn('preprocess_embed', vars(self.clip.encoder.transformer))
        self.assertFalse(hooks._busy)

    def build(self, cards):
        self.clip.study_outputs.clear()
        before = self.clip.encodes
        result = studies.build_studies(self.context, cards)
        self.assertEqual(self.clip.encodes - before, result.encode_passes)
        self.assertEqual(len(self.clip.study_outputs), result.encode_passes)
        projected = [[out[0][0].values[index] for index in result.retained_output_positions]
                     for out in self.clip.study_outputs]
        if result.active:
            self.assertNotEqual(projected[0], self.original_values, 'fixture must expose B!=N')
        return result, projected

    def phase(self, result):
        bundle = result.for_step(self.model, 0, 8)
        for key in ('model', 'negative', 'source_latent', 'target_latent', 'noise_mask'):
            self.assertIs(bundle[key], self.context.native[key])
        return bundle['positive']

    def assert_native_metadata(self, conditioning):
        for _, metadata in conditioning:
            self.assertIs(metadata['original_native_marker'], self.marker)
            self.assertIs(metadata['attention_mask'], self.positive[0][1]['attention_mask'])
            self.assertIs(metadata['foreign'], self.positive[0][1]['foreign'])

    def test_signed_build_deltas_are_opposite_about_adopted_native_not_muted_base(self):
        positive, rows = self.build([fixture.card(1)])
        plus = self.phase(positive)
        expected_delta = [p - m for p, m in zip(rows[1], rows[2])]
        self.assertTrue(any(expected_delta))
        self.assertEqual(plus[0][0].values, [n + d for n, d in zip(self.original_values, expected_delta)])
        negative, _ = self.build([fixture.card(-1)])
        minus = self.phase(negative)
        self.assertEqual(minus[0][0].values, [n - d for n, d in zip(self.original_values, expected_delta)])
        self.assertEqual([(p + m) / 2 for p, m in zip(plus[0][0].values, minus[0][0].values)], self.original_values)
        self.assertEqual(positive.encode_passes, 3)
        self.assert_native_metadata(plus)
        self.assert_native_metadata(minus)

    def test_zero_delta_has_no_muted_base_displacement_despite_active_studies(self):
        # Same scalar payload sum, distinct literal poles. Owned pole outputs
        # are projected away, yielding a genuinely zero retained P-M contrast.
        result, rows = self.build([fixture.card(1, plus='ab', minus='ba')])
        self.assertEqual(rows[1], rows[2])
        self.assertNotEqual(rows[0], self.original_values)
        self.assertTrue(result.active)
        self.assertEqual(result.encode_passes, 3)
        conditioning = self.phase(result)
        self.assertEqual(conditioning[0][0].values, self.original_values)
        self.assert_native_metadata(conditioning)

    def test_multiple_axis_build_sums_signed_contrasts_on_native_anchor(self):
        cards = [fixture.card(.5), fixture.card(-.75, axis='temperature', plus='warm', minus='cool')]
        result, rows = self.build(cards)
        expected = [n + .5 * (p0 - m0) - .75 * (p1 - m1)
                    for n, p0, m0, p1, m1 in zip(self.original_values, *rows[1:])]
        self.assertEqual(result.encode_passes, 5)
        self.assertEqual(result.budget_scales, (1., 1.))
        self.assertEqual(self.phase(result)[0][0].values, expected)
        self.assertEqual(result.for_step(self.model, 7, 8)['positive'][0][0].values, expected)
        self.assert_native_metadata(self.phase(result))

    def test_low_load_keeps_existing_strengths_with_native_anchored_steered_branch(self):
        result, rows = self.build([fixture.card(.01)])
        conditioning = self.phase(result)
        self.assertEqual(len(conditioning), 2)
        self.assertIs(conditioning[0][0], self.positive[0][0])
        self.assertAlmostEqual(conditioning[0][1]['strength'], .96)
        self.assertAlmostEqual(conditioning[1][1]['strength'], .04)
        expected = [n + .01 * (p - m) for n, p, m in zip(self.original_values, rows[1], rows[2])]
        self.assertEqual(conditioning[1][0].values, expected)
        self.assertEqual(result.encode_passes, 3)
        self.assert_native_metadata(conditioning)

    def test_neutral_cancelled_and_inactive_phases_keep_exact_adopted_bundle(self):
        for cards in ([fixture.card(0)], [fixture.card(1), fixture.card(-1)]):
            result, _ = self.build(cards)
            self.assertEqual(result.encode_passes, 0)
            self.assertIs(result.for_step(self.model, 0, 8), self.context.native)
        result, _ = self.build([fixture.card(1, 'early-layout')])
        self.assertEqual(result.encode_passes, 3)
        self.assertIs(result.for_step(self.model, 7, 8), self.context.native)


if __name__ == '__main__':
    unittest.main()
