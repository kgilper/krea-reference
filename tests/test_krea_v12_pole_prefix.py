"""Captured BPE plus declared causal scalar studies; no neural or visual proof."""
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import test_krea_v12 as fixture
import test_krea_v12_token_assembly as bpe
from native_v12_tests import hooks, ledger, native, studies

EDGES = json.loads((Path(__file__).parent / 'fixtures/krea_v12_pole_prefix_edges.json').read_text())


class CausalBPEClip(bpe.BPEClip):
    """Prefix-sum attention surrogate obeying causal visibility and key masking.

    Actual BPE/assembly/hooks/projection/composition run normally. These scalar
    hidden states deliberately do not claim a Qwen or diffusion model result.
    """
    def __init__(self, record):
        super().__init__(record)
        self.study_outputs = []
        self.mutate_row = False
        self.fail_study = 0
        self.foreign_hook = None

    def encode_from_tokens_scheduled(self, tokens):
        self.encodes += 1
        controlled = 'process_tokens' in vars(self.encoder)
        if controlled and self.mutate_row:
            tokens[ledger.TOKEN_KEY][0][0] = (999, 1.0)
        raw = [[ledger.element(item) for item in tokens[ledger.TOKEN_KEY][0]]]
        embeds, mask, counts, info = self.encoder.process_tokens(raw, 'causal-scalar')
        injection = [0.] * len(embeds.values)
        for image in info:
            extra = sum(value.value for value in image['extra']['deepstack'])
            for index in range(image['index'], image['index'] + image['size']):
                injection[index] = extra
        hidden, prefix = [], 0.
        for value, attended, extra in zip(embeds.values, mask.values, injection):
            value += extra
            prefix += value * attended
            hidden.append(value + prefix)
        strip = ledger.native_output_start(tokens[ledger.TOKEN_KEY][0])
        if controlled:
            self.study_outputs.append(dict(hidden=hidden, mask=list(mask.values), counts=counts,
                row=tuple(value if not isinstance(value, dict) else ('image', id(value['data']), value[ledger.OWNER_KEY]) for value in raw[0]),
                info=info))
            if self.foreign_hook is not None:
                self.encoder.process_tokens = self.foreign_hook
            if len(self.study_outputs) == self.fail_study:
                raise RuntimeError('owned causal fixture encode failure')
        return [[fixture.Buffer(hidden[strip:], len(ledger.TAPS) * ledger.TAP_WIDTH),
                 {'attention_mask': fixture.Buffer(mask.values[strip:], mask=True), 'foreign': self}]]


def make_context(record, count):
    clip, grounder = CausalBPEClip(record), bpe.BPEGrounder()
    source, donor = (fixture.Image(7, 3) if count else None), (fixture.Image(11, 5) if count == 2 else None)
    model = NS(patches_uuid='causal-prefix-fixture', model_options={})
    target = {'samples': object(), 'noise_mask': object()}
    with patch.object(native, 'load_grounder', return_value=grounder):
        context = native.prepare_context(clip, model, record['prompt'], source=source, donor=donor,
            revision='causal-prefix-context', source_latent=object(), target_latent=target)
    return context, grounder


def legacy_append(original_tokens, owners, pole_tokens):
    """Negative control: previous full row, leading separators, poles at user end."""
    original = ledger.TokenLedger.build(original_tokens, owners)
    _, end = ledger.content_bounds(original.row)
    additions, spans = [], []
    for tokens in pole_tokens:
        row = ledger.single_row(tokens)
        start, stop = ledger.content_bounds(row)
        begin = end + len(additions)
        additions.extend(((198, 1.), (198, 1.)))
        additions.extend(row[start:stop])
        spans.append((begin, end + len(additions)))
    return ledger.TokenLedger(original.row[:end] + tuple(additions) + original.row[end:],
                              tuple(owners), original.prompt, tuple(spans), original.strip)


class PolePrefixTests(unittest.TestCase):
    def build(self, context, grounder):
        record = context.clip.record
        with patch.object(native, 'load_grounder', return_value=grounder):
            return studies.build_studies(context, [fixture.card(1, plus=record['plus'], minus=record['minus'])])

    def assert_clean(self, context):
        context.verify()
        self.assertFalse(hooks._busy)
        self.assertNotIn('process_tokens', vars(context.clip.encoder))
        self.assertNotIn('preprocess_embed', vars(context.clip.encoder.transformer))

    def test_captured_bpe_assembly_recovers_every_original_object_and_prompt_token(self):
        for record in [*bpe.DATA['cases'], *EDGES['cases']]:
            for count in (0, 1, 2):
                with self.subTest(prompt=record['prompt'], images=count):
                    context, grounder = make_context(record, count)
                    with patch.object(native, 'load_grounder', return_value=grounder):
                        prepared = context.prepare_inputs()
                        tokens = prepared.tokenize(context.clip, context.prompt)
                    original = ledger.single_row(tokens)
                    original_ledger = ledger.TokenLedger.build(tokens, prepared.owners)
                    result = ledger.TokenLedger.assemble(tokens, prepared.owners,
                        [context.clip.tokenize(record['plus']), context.clip.tokenize(record['minus'])])
                    self.assertEqual(result.poles[0][0], original_ledger.prompt[0])
                    self.assertEqual(result.poles[-1][1], result.prompt[0])
                    self.assertEqual(result.strip, original_ledger.strip)
                    self.assertEqual(result.owners, original_ledger.owners)
                    kept = [item for i, item in enumerate(result.row) if not any(a <= i < b for a, b in result.poles)]
                    self.assertEqual(len(kept), len(original))
                    for actual, expected in zip(kept, original):
                        self.assertIs(actual, expected)
                    a, z = original_ledger.prompt
                    for actual, expected in zip(result.row[result.prompt[0]:result.prompt[1]], original[a:z]):
                        self.assertIs(actual, expected)
                    for a, z in result.poles:
                        self.assertEqual([ledger.element(item) for item in result.row[z - 2:z]], [198, 198])
                    self.assert_clean(context)

    def test_old_append_is_causal_negative_control_with_suffix_only_contrast(self):
        for count in (0, 1, 2):
            context, grounder = make_context(bpe.DATA['cases'][0], count)
            with patch.object(ledger.TokenLedger, 'assemble', side_effect=legacy_append):
                result = self.build(context, grounder)
            expanded = result.ledgers[0]
            plus, minus = context.clip.study_outputs[1:]
            start, stop = expanded.prompt
            self.assertEqual(plus['hidden'][start:stop], minus['hidden'][start:stop])
            suffix_start = expanded.poles[-1][1]
            self.assertTrue(any(a != b for a, b in zip(plus['hidden'][suffix_start:], minus['hidden'][suffix_start:])))
            self.assert_clean(context)

    def test_prefix_causally_reaches_prompt_but_not_preceding_images_with_common_layout(self):
        for count in (0, 1, 2):
            context, grounder = make_context(bpe.DATA['cases'][0], count)
            before = context.clip.encodes
            result = self.build(context, grounder)
            self.assertEqual(context.clip.encodes - before, 3)
            expanded = result.ledgers[0]
            base, plus, minus = context.clip.study_outputs
            self.assertEqual(base['row'], plus['row'])
            self.assertEqual(base['row'], minus['row'])
            self.assertTrue(all(value == expanded for value in result.ledgers))
            start, stop = expanded.prompt
            self.assertTrue(all(a != b for a, b in zip(plus['hidden'][start:stop], minus['hidden'][start:stop])))
            self.assertEqual(plus['hidden'][:expanded.poles[0][0]], minus['hidden'][:expanded.poles[0][0]])
            for observation in (base, plus, minus):
                for image in observation['info']:
                    self.assertEqual([f.value for f in image['extra']['deepstack']],
                                     [image['extra']['deepstack'][0].value * factor for factor in (1., 1.5, 2.)])
            for key in ('model', 'negative', 'source_latent', 'target_latent', 'noise_mask'):
                self.assertIs(result.phases[1][key], context.native[key])
            self.assertIs(result.phases[1]['positive'][0][1]['attention_mask'], context.native['positive'][0][1]['attention_mask'])
            self.assert_clean(context)

    def test_grounded_leading_newlines_and_empty_prompts_are_preserved(self):
        for record in EDGES['cases']:
            for count in (1, 2):
                context, grounder = make_context(record, count)
                result = self.build(context, grounder)
                expanded = result.ledgers[0]
                native_ids = record['grounded'][str(count)]
                first_prompt = max(i for i, token in enumerate(native_ids) if token == 151653) + 1
                end = native_ids.index(151645, first_prompt)
                self.assertEqual(expanded.prompt[1] - expanded.prompt[0], end - first_prompt)
                if record['prompt'].startswith('\n'):
                    self.assertIn(native_ids[first_prompt], (198, 271))
                if not record['prompt']:
                    self.assertEqual(expanded.prompt[0], expanded.prompt[1])
                self.assertEqual(len(result.retained_output_positions), context.native['positive'][0][0].shape[1])
                self.assert_clean(context)

    def test_two_image_expansion_drives_pole_projection_offsets(self):
        context, grounder = make_context(bpe.DATA['cases'][0], 2)
        result = self.build(context, grounder)
        expanded = result.ledgers[0]
        raw_sizes = [end - start for _, start, end in expanded.images]
        self.assertEqual(raw_sizes, [context.sources[0].size, context.sources[1].size])
        original_raw = bpe.DATA['cases'][0]['grounded']['2']
        raw_insertion = max(i for i, value in enumerate(original_raw) if value == 151653) + 1
        self.assertEqual(expanded.poles[0][0] - raw_insertion, sum(size - 1 for size in raw_sizes))
        for span in expanded.poles:
            a, z = expanded.output_span(span)
            self.assertFalse(set(range(a, z)).intersection(result.retained_output_positions))
        for _, a, z in expanded.images:
            self.assertTrue(set(range(a - expanded.strip, z - expanded.strip)).issubset(result.retained_output_positions))
        self.assert_clean(context)

    def test_verified_carriers_match_actual_native_strip_and_retain_role_header(self):
        seen = set()
        for record in EDGES['cases']:
            seen.add(record['native_user_opening_carrier'])
            for count in (0, 1, 2):
                context, grounder = make_context(record, count)
                result = self.build(context, grounder)
                expanded = result.ledgers[0]
                ids = record['native'] if not count else record['grounded'][str(count)]
                expected_strip = record['native_output_strip'] if not count else record['grounded_output_strip'][str(count)]
                self.assertEqual(expanded.strip, expected_strip)
                expansion = sum(image.size - 1 for image in context.sources if image is not None)
                self.assertEqual(len(result.retained_output_positions), len(ids) + expansion - expected_strip)
                if not count and record['native_user_opening_carrier'] != 198:
                    self.assertEqual(ids[expected_strip:expected_strip + 3], [151644, 872, record['native_user_opening_carrier']])
                    self.assertTrue(set(range(3)).issubset(result.retained_output_positions))
                    plus, minus = context.clip.study_outputs[1:]
                    self.assertEqual(plus['hidden'][expected_strip:expected_strip + 3], minus['hidden'][expected_strip:expected_strip + 3])
                self.assert_clean(context)
        self.assertEqual(seen, {198, 271, 1406})

    def test_unknown_opening_carriers_and_malformed_roles_reject(self):
        row = bpe.DATA['cases'][0]['native']
        start = [i for i, value in enumerate(row) if value == 151644][1]
        poles = [bpe.weighted(bpe.DATA['cases'][0][name]) for name in ('plus_native', 'minus_native')]
        for carrier in (999, 1022, 151653, dict(type='image', data=object())):
            tokens = bpe.weighted(row)
            tokens[ledger.TOKEN_KEY][0][start + 2] = (carrier, 1.)
            with self.subTest(carrier=carrier), self.assertRaisesRegex(RuntimeError, 'native user opening'):
                ledger.TokenLedger.assemble(tokens, (), poles)
        tokens = bpe.weighted(row)
        tokens[ledger.TOKEN_KEY][0][start + 1] = (8948, 1.)
        with self.assertRaisesRegex(RuntimeError, 'native user opening'):
            ledger.TokenLedger.assemble(tokens, (), poles)

    def test_merged_pole_opening_is_not_silently_normalized(self):
        original = bpe.weighted(bpe.DATA['cases'][0]['native'])
        with self.assertRaisesRegex(RuntimeError, 'plain text'):
            ledger.TokenLedger.assemble(original, (), [bpe.weighted(EDGES['cases'][0]['native'])])

    def test_malformed_prefix_and_unowned_markers_fail_before_study_encoding(self):
        context, grounder = make_context(bpe.DATA['cases'][0], 2)
        original_tokenize = context.clip.tokenize
        def changed(kind):
            def tokenize(text, **kwargs):
                result = original_tokenize(text, **kwargs)
                if text == context.prompt:
                    row = result[ledger.TOKEN_KEY][0]
                    first_image = next(i for i, item in enumerate(row) if isinstance(ledger.element(item), dict))
                    if kind == 'missing-close': row[first_image + 1] = (999, 1.)
                    elif kind == 'text-before-images': row.insert(first_image - 1, (123, 1.))
                    else:
                        _, end = ledger.content_bounds(row)
                        row.insert(end, (151653, 1.))
                return result
            return tokenize
        for kind in ('missing-close', 'text-before-images', 'unowned-marker'):
            before = context.clip.encodes
            with patch.object(context.clip, 'tokenize', side_effect=changed(kind)), self.assertRaises(RuntimeError):
                self.build(context, grounder)
            self.assertEqual(context.clip.encodes, before)
            self.assert_clean(context)

    def test_token_mutation_during_preparation_rejects_and_cleans_hooks(self):
        context, grounder = make_context(bpe.DATA['cases'][0], 2)
        context.clip.mutate_row = True
        with self.assertRaisesRegex(RuntimeError, 'changed token content'):
            self.build(context, grounder)
        self.assert_clean(context)

    def test_second_study_failure_cleans_hooks_and_preserves_native_bundle(self):
        context, grounder = make_context(bpe.DATA['cases'][0], 2)
        context.clip.fail_study = 2
        original = context.native.copy()
        with self.assertRaisesRegex(RuntimeError, 'causal fixture encode failure'):
            self.build(context, grounder)
        for key, value in original.items():
            self.assertIs(context.native[key], value)
        self.assert_clean(context)

    def test_foreign_hook_replacement_is_preserved_and_owned_lease_released(self):
        context, grounder = make_context(bpe.DATA['cases'][0], 1)
        foreign = lambda *args: None
        context.clip.foreign_hook = foreign
        try:
            with self.assertRaisesRegex(RuntimeError, 'foreign hook mutation'):
                self.build(context, grounder)
            self.assertIs(vars(context.clip.encoder)['process_tokens'], foreign)
            self.assertNotIn('preprocess_embed', vars(context.clip.encoder.transformer))
            self.assertFalse(hooks._busy)
        finally:
            del context.clip.encoder.process_tokens
        self.assert_clean(context)

    def test_neutral_cancel_and_budget_zero_skip_prefix_preparation_entirely(self):
        for cards, options in (([fixture.card(0)], {}), ([fixture.card(1), fixture.card(-1)], {}),
                               ([fixture.card(1)], {'budget': 0})):
            context, grounder = make_context(EDGES['cases'][0], 2)
            before = context.clip.encodes, context.clip.tokenizations, len(grounder.preps)
            with patch.object(ledger.TokenLedger, 'assemble', side_effect=AssertionError('neutral assembly')):
                result = studies.build_studies(context, cards, **options)
            self.assertIs(result.sampler_conditioning(), context.native)
            self.assertEqual(before, (context.clip.encodes, context.clip.tokenizations, len(grounder.preps)))
            self.assert_clean(context)


if __name__ == '__main__':
    unittest.main()
