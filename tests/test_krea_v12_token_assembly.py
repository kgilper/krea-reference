"""Actual Qwen byte-BPE rows; encoder/vision outputs remain authored scalar fixtures."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import test_krea_v12 as fixture
from native_v12_tests import hooks, ledger, native, studies

DATA = json.loads((Path(__file__).parent / 'fixtures/krea_v12_bpe_boundary.json').read_text(encoding='utf-8'))
weighted = lambda values: {ledger.TOKEN_KEY: [[(value, 1.0) for value in values]]}


class BPEClip(fixture.Clip):
    """Use captured exact byte-BPE rows, not a character/word tokenizer stub."""
    def __init__(self, record):
        super().__init__()
        self.record, self.raw_inputs = record, []

    def tokenize(self, text, images=(), llama_template=None):
        self.tokenizations += 1
        self.raw_inputs.append((text, tuple(images), llama_template))
        if text in (self.record['plus'], self.record['minus']):
            if images or llama_template is not None:
                raise AssertionError('pole tokenization must be text-only')
            key = 'plus_native' if text == self.record['plus'] else 'minus_native'
            ids = self.record[key]
        elif text == self.record['prompt'] or text == '':
            if images:
                if llama_template != DATA['ground_templates'][str(len(images))]:
                    raise AssertionError('actual native grounding template changed')
                ids = (self.record['grounded'] if text else DATA['negative_grounded'])[str(len(images))]
            else:
                ids = self.record['native'] if text else DATA['negative']
        else:
            raise AssertionError('native prompt/pole text was unexpectedly changed or concatenated')
        image_iter = iter(images)
        row = [(dict(type='image', data=next(image_iter), original_type='image') if value == 151655 else value, 1.0)
               for value in ids]
        return {ledger.TOKEN_KEY: [row]}


class BPEGrounder(fixture.Grounder):
    def _template(self, count, system):
        if system:
            raise AssertionError('this fixture binds the original native default')
        return DATA['ground_templates'][str(count)]


def make_context(record, image_count=0):
    clip, grounder = BPEClip(record), BPEGrounder()
    source = fixture.Image(7, 3) if image_count else None
    donor = fixture.Image(11, 5) if image_count == 2 else None
    model = NS(patches_uuid='native-bpe-fixture-v1')
    target = {'samples': object(), 'noise_mask': object()}
    with patch.object(native, 'load_grounder', return_value=grounder):
        context = native.prepare_context(clip, model, record['prompt'], source=source, donor=donor,
            source_latent=object(), target_latent=target, revision='bpe-row-fixture-v1')
    return context, grounder


class TokenAssemblyTests(unittest.TestCase):
    def test_actual_failing_qwen_period_boundary_is_reproduced_without_models(self):
        record = DATA['cases'][0]
        with self.assertRaisesRegex(RuntimeError, 'boundary merged'):
            ledger.TokenLedger.build(weighted(record['grown']), (), [weighted(record['native'])])
        point = DATA['mismatch']['index']
        self.assertEqual(record['native'][point], 13)
        self.assertEqual(record['grown'][point], 382)
        self.assertEqual(DATA['mismatch']['grown_piece'], '.\n\n')

    def test_multiple_owned_poles_recover_exact_bpe_native_row_and_weights(self):
        for record in DATA['cases']:
            with self.subTest(prompt=record['prompt']):
                original = weighted(record['native'])
                base = ledger.single_row(original)
                result = ledger.TokenLedger.assemble(original, (), [weighted(record['plus_native']), weighted(record['minus_native'])] * 2)
                self.assertEqual(len(result.poles), 4)
                kept = [item for index, item in enumerate(result.row)
                        if not any(a <= index < b for a, b in result.poles)]
                self.assertEqual(len(kept), len(base))
                for left, right in zip(kept, base):
                    self.assertIs(left, right)
                self.assertTrue(all(item[1] == 1.0 for item in result.row))

    def test_source_and_donor_identity_order_and_metadata_survive_assembly(self):
        for count in (1, 2):
            context, grounder = make_context(DATA['cases'][0], count)
            with patch.object(native, 'load_grounder', return_value=grounder):
                prepared = context.prepare_inputs()
                original = prepared.tokenize(context.clip, context.prompt)
                result = ledger.TokenLedger.assemble(original, prepared.owners,
                    [context.clip.tokenize(DATA['cases'][0]['plus']), context.clip.tokenize(DATA['cases'][0]['minus'])])
            images = [item for item in ledger.single_row(original) if isinstance(ledger.element(item), dict)]
            actual = [item for item in result.row if isinstance(ledger.element(item), dict)]
            self.assertEqual(len(actual), count)
            for left, right in zip(actual, images):
                self.assertIs(left, right)
                self.assertEqual(left[0]['original_type'], 'image')
            self.assertIs(actual[0][0]['data'], context.sources[0])
            if count == 2:
                self.assertIs(actual[1][0]['data'], context.sources[1])
            self.assertNotIn(ledger.OWNER_KEY, actual[0][0])

    def test_special_media_role_and_weighted_pole_payloads_reject(self):
        record = DATA['cases'][0]
        original = weighted(record['native'])
        for token in (151643, 151644, 151645, 151652, 151653, 151655, 151665, 200000):
            payload = weighted(record['plus_native'])
            start, _ = ledger.content_bounds(ledger.single_row(payload))
            payload[ledger.TOKEN_KEY][0].insert(start, (token, 1.0))
            with self.subTest(token=token), self.assertRaises(RuntimeError):
                ledger.TokenLedger.assemble(original, (), [payload])
        payload = weighted(record['plus_native'])
        start, _ = ledger.content_bounds(ledger.single_row(payload))
        payload[ledger.TOKEN_KEY][0][start] = (payload[ledger.TOKEN_KEY][0][start][0], 2.0)
        with self.assertRaisesRegex(RuntimeError, 'unweighted'):
            ledger.TokenLedger.assemble(original, (), [payload])
        payload = weighted(record['plus_native'])
        payload[ledger.TOKEN_KEY][0].insert(start, (dict(type='image', data=object()), 1.0))
        with self.assertRaisesRegex(RuntimeError, 'plain text'):
            ledger.TokenLedger.assemble(original, (), [payload])

    def test_complete_studies_use_single_native_bpe_image_row_and_project_only_owned_tokens(self):
        record = DATA['cases'][0]
        for count in (0, 1, 2):
            with self.subTest(image_count=count):
                context, grounder = make_context(record, count)
                before_image_calls = sum(bool(images) for _, images, _ in context.clip.raw_inputs)
                with patch.object(native, 'load_grounder', return_value=grounder):
                    result = studies.build_studies(context,
                        [fixture.card(1, plus=record['plus'], minus=record['minus']),
                         fixture.card(-0.5, axis='another', plus=record['plus'], minus=record['minus'])])
                self.assertEqual(result.encode_passes, 5)
                self.assertEqual(sum(bool(images) for _, images, _ in context.clip.raw_inputs) - before_image_calls, int(count > 0))
                self.assertIs(result.phases[1]['negative'], context.native['negative'])
                self.assertIs(result.phases[1]['target_latent'], context.native['target_latent'])
                self.assertIs(result.phases[1]['noise_mask'], context.native['noise_mask'])
                self.assertEqual(result.phases[1]['positive'][0][0].shape, context.native['positive'][0][0].shape)
                self.assertEqual(len(result.retained_output_positions), context.native['positive'][0][0].shape[1])
                self.assertFalse(hooks._busy)
                self.assertNotIn('process_tokens', vars(context.clip.encoder))

    def test_bpe_neutral_does_not_tokenize_prepare_or_encode_studies(self):
        context, grounder = make_context(DATA['cases'][0], 2)
        before = context.clip.tokenizations, context.clip.encodes, len(grounder.preps)
        result = studies.build_studies(context, [fixture.card(0)])
        self.assertIs(result.sampler_conditioning(), context.native)
        self.assertEqual(before, (context.clip.tokenizations, context.clip.encodes, len(grounder.preps)))


if __name__ == '__main__':
    unittest.main()
