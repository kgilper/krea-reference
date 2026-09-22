"""V11 regressions: signs, zero, cache identity, combined axes and timing."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kg_stub_env import load_module


class V11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nodes, cls.torch = load_module('kg_krea_v11', 'kg_krea_v11_test')

    def target(self, values, pooled=0):
        return {'token': values[0], 'pooled': pooled, 'token_layers': [v - 1 for v in values]}

    def test_balance_never_reverses_away_or_restores_zero(self):
        targets = [self.target([-0.1, 0, -6]) for _ in range(4)]
        scale = self.nodes.encoder.balance_targets(targets, 1.5)
        self.assertLess(scale, 1)
        for target in targets:
            values = [v + 1 for v in target['token_layers']]
            self.assertLess(values[0], 0)
            self.assertEqual(values[1], 0)
            self.assertLess(values[2], 0)

    def test_balance_budgets_layer_peaks_not_inert_pooled(self):
        targets = [self.target([0.1, 6], pooled=1000) for _ in range(2)]
        scale = self.nodes.encoder.balance_targets(targets, 2.5)
        self.assertAlmostEqual(scale, 2.5 / 12)
        self.assertAlmostEqual(sum(max(abs(w + 1) for w in t['token_layers']) for t in targets), 2.5)

    def test_balance_within_budget_and_off_are_exact(self):
        for budget in (None, 2.5):
            target = self.target([0, 0.25, -0.3])
            original = repr(target)
            self.assertEqual(self.nodes.encoder.balance_targets([target], budget), 1)
            self.assertEqual(repr(target), original)

    def test_old_moment_collision_gets_different_hashes(self):
        digest = self.nodes.cache.digest_bytes
        self.assertNotEqual(digest((4,), 'uint8', bytes([0, 1, 1, 0])), digest((4,), 'uint8', bytes([1, 0, 0, 1])))
        self.assertNotEqual(digest((4,), 'uint8', b'abcd'), digest((2, 2), 'uint8', b'abcd'))
        self.assertNotEqual(digest((4,), 'uint8', b'abcd'), digest((4,), 'int8', b'abcd'))

    def test_cache_revision_and_unknown_host(self):
        class Clip: pass
        clip = Clip()
        self.assertIsNone(self.nodes.cache.make_key(clip, 'prompt'))
        clip.patcher = SimpleNamespace(patches_uuid='first')
        key = self.nodes.cache.make_key(clip, 'prompt')
        self.nodes.cache.store(key, clip, 'base', {'axis': 1})
        self.assertEqual(self.nodes.cache.lookup(key, clip)['full'], 'base')
        clip.patcher.patches_uuid = 'second'
        self.assertNotEqual(key, self.nodes.cache.make_key(clip, 'prompt'))
        self.assertIsNone(self.nodes.cache.lookup(self.nodes.cache.make_key(clip, 'prompt'), clip))

    def slider(self, weight=6, timing='whole image', reverse=False, index=1):
        return {'plus_text': 'low' if reverse else 'high', 'minus_text': 'high' if reverse else 'low',
                'weight': weight, 'timing': timing, 'index': index}

    def test_duplicates_cannot_multiply_past_stack_budget(self):
        groups = self.nodes.slider_encoder.grouped_sliders([self.slider(index=i) for i in range(8)])
        self.assertEqual(len(groups), 1)
        weights, scales = self.nodes.slider_encoder.budget_weights(groups, 2)
        self.assertEqual(weights, [[2], [2]])
        self.assertAlmostEqual(scales[0], 2 / 48)

    def test_opposites_cancel_before_encoding(self):
        self.assertEqual(self.nodes.slider_encoder.grouped_sliders([self.slider(), self.slider(reverse=True)]), [])
        self.assertEqual(self.nodes.slider_encoder.grouped_sliders([self.slider(), self.slider(weight=-6)]), [])

    def test_timing_groups_same_axis_once_and_budgets_per_phase(self):
        groups = self.nodes.slider_encoder.grouped_sliders([self.slider(1, 'early layout only'), self.slider(-3, 'final details only')])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['weights'], [1, -3])
        self.assertEqual(self.nodes.slider_encoder.budget_weights(groups, 2)[0], [[1], [-2]])

    def test_distinct_axes_share_one_budget(self):
        a, b = self.slider(2), self.slider(2)
        b['plus_text'] = 'other'
        weights, _ = self.nodes.slider_encoder.budget_weights(self.nodes.slider_encoder.grouped_sliders([a, b]), 2)
        self.assertEqual(weights, [[1, 1], [1, 1]])

    def test_neutral_blend_preserves_endpoints_and_metadata(self):
        plain = [['plain', {'attention_mask': 'a'}]]
        steered = [['steered', {'attention_mask': 'b'}]]
        blend = self.nodes.slider_encoder.blend_neutral
        self.assertIs(blend(plain, steered, 0), plain)
        self.assertIs(blend(plain, steered, 1), steered)
        mixed = blend(plain, steered, 0.1)
        self.assertEqual([v[1]['strength'] for v in mixed], [0.9, 0.1])
        self.assertEqual([v[1]['attention_mask'] for v in mixed], ['a', 'b'])
        self.assertNotIn('strength', plain[0][1])

    def test_presets_allow_explicit_pole_override(self):
        card = self.nodes.KGKrea2ConceptSliderCardV11().build(**{'Slider preset': 'person height', 'What +6 looks like (optional)': 'custom plus'})[0]
        self.assertEqual(card['increase_text'], 'custom plus')
        self.assertIn('compact stature', card['decrease_text'])
        self.assertEqual(card['timing'], 'whole image')

    def test_legacy_card_values_and_recipe_tables_are_unchanged(self):
        old = self.nodes.encoder.v10.KGKrea2ImageGuideCardV10().build(**{'Use image for': 'balanced'})[0]
        new = self.nodes.KGKrea2ImageGuideCardV11().build(**{'Use image for': 'balanced'})[0]
        new['source_version'] = old['source_version']
        self.assertEqual(new, old)

    def test_zero_reach_and_budget_plain_prompt_bypass(self):
        stack = self.nodes.KGKrea2ConceptSliderStackV11()
        class Clip:
            def tokenize(self, text): return text
            def encode_from_tokens_scheduled(self, tokens): return ['plain', tokens]
        for field in ('Overall slider reach', 'Combined slider budget'):
            with patch.object(stack, '_collect_sliders', side_effect=AssertionError('must not study')):
                result = stack.execute(**{'Krea CLIP': Clip(), 'Final image prompt': 'hello', field: 0})
                self.assertEqual(result[0], ['plain', 'hello'])

    def test_unknown_muting_fails_only_for_active_spans(self):
        with self.assertRaisesRegex(RuntimeError, 'token-span muting'):
            self.nodes.KGKrea2ConceptSliderStackV11._encode_with_spans(object(), {}, [(0, 1)])

    def test_legacy_widget_prefix_preserved(self):
        legacy = self.nodes.slider_card.sliders.KGKrea2ConceptSliderCardV1.INPUT_TYPES()['required']
        new = self.nodes.KGKrea2ConceptSliderCardV11.INPUT_TYPES()['required']
        self.assertEqual(list(new)[:len(legacy)], list(legacy))


if __name__ == '__main__':
    unittest.main()
