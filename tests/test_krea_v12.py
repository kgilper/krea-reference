"""Synthetic-only native-boundary checks. No Torch, host, model or image files."""
import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('native_v12_tests', ROOT / 'kg_krea_v12/__init__.py',
                                             submodule_search_locations=[str(ROOT / 'kg_krea_v12')])
NODES = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = NODES
SPEC.loader.exec_module(NODES)
from native_v12_tests import hooks, ledger, native, studies


class Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class Row:
    def __init__(self, values):
        self.values = values

    def sum(self):
        return Scalar(sum(self.values))


class Buffer:
    """One scalar per sequence position, with an explicit logical host width.

    This deliberately does not emulate a real model/tensor implementation.
    It exercises input mutation, metadata, extents and scalar control flow.
    """
    def __init__(self, values, width=1, mask=False):
        self.values = list(values)
        self.width = width
        self.mask = mask
        self.shape = (1, len(values)) if mask else (1, len(values), width)

    def clone(self):
        return Buffer(self.values, self.width, self.mask)

    def __setitem__(self, index, value):
        _, span = index
        self.values[span] = [value] * (span.stop - span.start)

    def __getitem__(self, index):
        _, positions = index
        return Buffer([self.values[i] for i in positions], self.width, self.mask)

    def __iter__(self):
        yield Row(self.values)

    def __mul__(self, value):
        return Buffer([v * value for v in self.values], self.width, self.mask)

    def __add__(self, other):
        return Buffer([a + b for a, b in zip(self.values, other.values)], self.width, self.mask)

    def __sub__(self, other):
        return Buffer([a - b for a, b in zip(self.values, other.values)], self.width, self.mask)


class Features:
    def __init__(self, value):
        self.value = value

    def __mul__(self, gain):
        return Features(self.value * gain)


class Image:
    shape = (1, 2, 2, 3)

    def __init__(self, value, size):
        self.value, self.size = value, size


class Transformer:
    def preprocess_embed(self, embed, device):
        image = embed['data']
        return Features(image.value), {'grid': (1, 2, 2),
                                       'deepstack': [Features(image.value * i) for i in (2, 3, 4)]}


class Encoder:
    layer = list(ledger.TAPS)

    def __init__(self):
        self.transformer = Transformer()
        self.captures = []

    def process_tokens(self, tokens, device):
        values, info = [], []
        for token in tokens[0]:
            if isinstance(token, dict):
                emb, extra = self.transformer.preprocess_embed(token, device=device)
                size = token['data'].size
                info.append(dict(type='image', index=len(values), size=size, extra=extra))
                values.extend([emb.value] * size)
            else:
                values.append(float(token))
        return Buffer(values), Buffer([1] * len(values), mask=True), [len(values)], info


class Clip:
    def __init__(self):
        self.encoder = Encoder()
        self.cond_stage_model = SimpleNamespace(clip='qwen3vl_4b', qwen3vl_4b=self.encoder)
        self.encodes, self.tokenizations = 0, 0
        self.raise_encode = False
        self.change_expansion = False

    def tokenize(self, text, images=(), llama_template=None):
        self.tokenizations += 1
        row = [151644, 200, 198, 201, 151645, 198, 151644, 872, 198]
        for image in images:
            row.extend([151652, dict(type='image', data=image), 151653])
        row += [ord(c) for c in text] + [151645, 198, 151644, 202, 198]
        return {ledger.TOKEN_KEY: [[(value, 1.0) for value in row]]}

    def encode_from_tokens_scheduled(self, tokens):
        self.encodes += 1
        raw = [[ledger.element(item) for item in tokens[ledger.TOKEN_KEY][0]]]
        embeds, mask, counts, info = self.encoder.process_tokens(raw, 'synthetic')
        if self.raise_encode:
            raise RuntimeError('synthetic encode failure')
        self.encoder.captures.append((embeds.clone(), mask.clone(), counts, info))
        # A simple context-sensitive scalar field proves studies really see
        # images AND unmuted poles; it does not predict neural interpretation.
        context = sum(value * active for value, active in zip(embeds.values, mask.values))
        deepstack = sum(f.value for image in info for f in image['extra']['deepstack'])
        strip = ledger.native_output_start(tokens[ledger.TOKEN_KEY][0])
        values = [value + context + deepstack for value in embeds.values[strip:]]
        return [[Buffer(values, len(ledger.TAPS) * ledger.TAP_WIDTH),
                 {'attention_mask': Buffer(mask.values[strip:], mask=True), 'foreign': self}]]


class Grounder:
    def __init__(self):
        self.preps, self.calls = [], []

    def _prep(self, image, size):
        self.preps.append((image, size))
        return image

    def _template(self, count, system):
        return ('native-template', count, system)

    def encode(self, clip, prompt, image, image_b=None, grounding_px=768, system_prompt=''):
        self.calls.append((prompt, image, image_b, grounding_px, system_prompt))
        images = [self._prep(image, grounding_px)]
        if image_b is not None:
            images.append(self._prep(image_b, grounding_px))
        return (clip.encode_from_tokens_scheduled(clip.tokenize(prompt, images=images,
                    llama_template=self._template(len(images), system_prompt))),)


class NativePatch:
    def __init__(self):
        self.calls = []
        self.change_foreign = False

    def patch(self, model, **kwargs):
        import copy
        self.calls.append((model, kwargs))
        options = copy.deepcopy(getattr(model, 'model_options', {}))
        wrappers = options.setdefault('transformer_options', {}).setdefault('wrappers', {}).setdefault('diffusion_model', {})
        wrappers.setdefault('krea2_edit', []).append(lambda *args: None)
        if self.change_foreign:
            options['unowned'] = 'changed'
        return (SimpleNamespace(patches_uuid='synthetic-owned-clone-v1', model_options=options),)


def card(value=1, timing='throughout', axis='light', plus='bright', minus='dim'):
    return dict(axis_id=axis, revision='synthetic-v1', plus=plus, minus=minus,
                coefficient=value, timing=timing)


class NativeV12Tests(unittest.TestCase):
    def setUp(self):
        self.clip, self.grounder = Clip(), Grounder()
        self.original_load_grounder = native.load_grounder
        grounder_patch = patch.object(native, 'load_grounder', return_value=self.grounder)
        grounder_patch.start()
        self.addCleanup(grounder_patch.stop)
        self.model = SimpleNamespace(patches_uuid='synthetic-model-v1')
        self.source, self.donor = Image(7, 3), Image(11, 5)
        self.foreign = {'composite': object(), 'restore': object()}
        self.latent, self.target, self.mask = object(), object(), object()

    def prepare(self, grounded=True):
        return native.prepare_context(self.clip, self.model, 'plain', negative_prompt='',
                source=self.source if grounded else None, donor=self.donor if grounded else None,
                revision='synthetic-context-v1', native_metadata=self.foreign,
                source_latent=self.latent, target_latent=self.target, noise_mask=self.mask)

    def assert_clean(self):
        self.assertNotIn('process_tokens', vars(self.clip.encoder))
        self.assertNotIn('preprocess_embed', vars(self.clip.encoder.transformer))
        self.assertFalse(hooks._busy)

    def test_zero_is_complete_native_identity_without_new_work(self):
        context = self.prepare()
        before = self.clip.encodes, self.clip.tokenizations, len(self.grounder.preps)
        result = studies.build_studies(context, [card(0)])
        self.assertIs(result.sampler_conditioning(), context.native)
        self.assertIs(result.for_step(self.model, 0, 8), context.native)
        self.assertIs(context.native['metadata'], self.foreign)
        self.assertIs(context.native['source_latent'], self.latent)
        self.assertIs(context.native['noise_mask'], self.mask)
        self.assertEqual(before, (self.clip.encodes, self.clip.tokenizations, len(self.grounder.preps)))
        self.assert_clean()

    def test_cancellation_budget_zero_and_empty_phases_do_not_prepare(self):
        for cards, options in (([card(1), card(-1)], {}), ([card(1)], {'budget': 0}),
                               ([card(1, 'early-layout')], {'split': 0}),
                               ([card(1, 'final-details')], {'split': 1})):
            context = self.prepare()
            before = self.clip.encodes
            result = studies.build_studies(context, cards, **options)
            self.assertIs(result.sampler_conditioning(), context.native)
            self.assertEqual(self.clip.encodes, before)

    def test_grounded_native_delegate_pairs_source_donor_and_negative(self):
        context = self.prepare()
        self.assertEqual([call[0] for call in self.grounder.calls], ['plain', ''])
        self.assertTrue(all(call[1] is self.source and call[2] is self.donor for call in self.grounder.calls))
        result = studies.build_studies(context, [card(0.5)])
        self.assertEqual(result.encode_passes, 3)
        bundle = result.for_step(self.model, 0, 8)
        for key in ('model', 'negative', 'source_latent', 'target_latent', 'noise_mask', 'metadata'):
            self.assertIs(bundle[key], context.native[key])
        self.assertIsNot(bundle['positive'], context.native['positive'])
        expanded = result.ledgers[0]
        self.assertEqual([owner for owner, _, _ in expanded.images], ['native:source', 'native:donor'])
        self.assertEqual([end - start for _, start, end in expanded.images], [3, 5])
        self.assertLessEqual(expanded.poles[-1][1], expanded.prompt[0])
        self.assertEqual(expanded.strip, 9)
        self.assertEqual(expanded.output_span(expanded.poles[0])[0], expanded.poles[0][0] - 9)
        self.assert_clean()

    def test_muted_spans_are_expanded_not_raw_indices(self):
        context = self.prepare()
        result = studies.build_studies(context, [card()])
        base_embeds, base_mask, counts, _ = self.clip.encoder.captures[-3]
        expanded = result.ledgers[0]
        for start, end in expanded.poles:
            self.assertEqual(base_embeds.values[start:end], [0] * (end - start))
            self.assertEqual(base_mask.values[start:end], [0] * (end - start))
        self.assertEqual(counts, [sum(base_mask.values)])
        for _, start, end in expanded.images:
            self.assertTrue(all(base_mask.values[start:end]))

    def test_native_and_deepstack_gains_are_scaled_together(self):
        tokens = self.clip.tokenize('plain', images=[self.source, self.donor])
        token_ledger = ledger.TokenLedger.build(tokens, ('source', 'donor'))
        tagged = token_ledger.tagged_tokens()
        with hooks.encoder_lease(self.clip) as (model, transformer):
            with hooks.controlled_encode(model, transformer, token_ledger,
                                          image_scales={'source': 0, 'donor': -0.5}):
                self.clip.encode_from_tokens_scheduled(tagged)
        embeds, _, _, info = self.clip.encoder.captures[-1]
        self.assertEqual(embeds.values[info[0]['index']:info[0]['index'] + 3], [0] * 3)
        self.assertEqual([f.value for f in info[0]['extra']['deepstack']], [0, 0, 0])
        self.assertEqual([f.value for f in info[1]['extra']['deepstack']], [-11, -16.5, -22])
        self.assert_clean()

    def test_signed_axes_reverse_and_budget_never_amplifies(self):
        context = self.prepare()
        positive = studies.build_studies(context, [card(0.5)])
        negative = studies.build_studies(context, [card(-0.5)])
        p = positive.for_step(self.model, 0, 8)['positive'][0][0].values
        n = negative.for_step(self.model, 0, 8)['positive'][0][0].values
        self.assertNotEqual(p, n)
        groups, scales = studies.resolve_axes([card(0.001)], 0.4, 2)
        self.assertEqual(scales, (1, 1))
        self.assertEqual(groups[0]['weights'], [0.001, 0.001])
        groups, scales = studies.resolve_axes([card(6), card(6, axis='other')], 0.4, 2)
        self.assertEqual(scales, (1/6, 1/6))
        self.assertEqual([g['weights'] for g in groups], [[1, 1], [1, 1]])

    def test_timing_has_one_phase_at_boundary_and_inactive_is_native(self):
        context = self.prepare()
        result = studies.build_studies(context, [card(1, 'early-layout')], split=0.5)
        self.assertIsNot(result.for_step(self.model, 1, 4), context.native)
        self.assertIs(result.for_step(self.model, 2, 4), context.native)
        self.assertIs(result.for_step(self.model, 3, 4), context.native)
        with self.assertRaisesRegex(RuntimeError, 'sampler export is gated'):
            result.sampler_conditioning()

    def test_text_path_and_different_model_rejection(self):
        context = self.prepare(False)
        result = studies.build_studies(context, [card()])
        self.assertEqual(result.ledgers[0].images, ())
        with self.assertRaisesRegex(RuntimeError, 'different native MODEL'):
            result.for_step(SimpleNamespace(patches_uuid=self.model.patches_uuid), 0, 8)
        self.model.patches_uuid = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'revision changed'):
            result.for_step(self.model, 0, 8)

    def test_failure_restores_exact_class_attribute_state(self):
        context = self.prepare()
        self.clip.raise_encode = True
        with self.assertRaisesRegex(RuntimeError, 'synthetic encode failure'):
            studies.build_studies(context, [card()])
        self.assert_clean()

    def test_shared_inner_encoder_lease_rejects_clone_and_releases_after_failure(self):
        clone = Clip()
        clone.cond_stage_model = self.clip.cond_stage_model
        with hooks.encoder_lease(self.clip):
            with self.assertRaisesRegex(RuntimeError, 'already leased'):
                with hooks.encoder_lease(clone):
                    self.fail('clone acquired same encoder')
        self.assert_clean()

    def test_real_thread_owner_rejects_overlap_and_unleased_hooks(self):
        import threading
        ready, release = threading.Event(), threading.Event()
        failures = []
        def owner():
            try:
                with hooks.encoder_lease(self.clip):
                    ready.set()
                    if not release.wait(3):
                        raise AssertionError('synthetic owner timeout')
            except Exception as error:
                failures.append(str(error))
        worker = threading.Thread(target=owner)
        worker.start()
        try:
            self.assertTrue(ready.wait(3))
            token_ledger = ledger.TokenLedger.build(self.clip.tokenize('plain'), ())
            with self.assertRaisesRegex(RuntimeError, 'current thread encoder lease'):
                with hooks.controlled_encode(self.clip.encoder, self.clip.encoder.transformer, token_ledger):
                    self.fail('foreign thread installed hooks')
            with self.assertRaisesRegex(RuntimeError, 'already leased'):
                with hooks.encoder_lease(self.clip):
                    self.fail('concurrent encoder owner')
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assert_clean()

    def test_foreign_hook_rejected_and_preserved(self):
        context = self.prepare()
        foreign = lambda *args, **kwargs: None
        self.clip.encoder.process_tokens = foreign
        with self.assertRaisesRegex(RuntimeError, 'existing instance hooks'):
            studies.build_studies(context, [card()])
        self.assertIs(self.clip.encoder.process_tokens, foreign)
        self.assertFalse(hooks._busy)
        del self.clip.encoder.process_tokens

    def test_foreign_mid_encode_mutation_is_preserved_while_other_hook_restores(self):
        token_ledger = ledger.TokenLedger.build(self.clip.tokenize('plain'), ())
        foreign = lambda *args: None
        with self.assertRaisesRegex(RuntimeError, 'foreign hook mutation'):
            with hooks.encoder_lease(self.clip) as (model, transformer):
                with hooks.controlled_encode(model, transformer, token_ledger):
                    self.clip.encoder.process_tokens = foreign
        self.assertIs(self.clip.encoder.process_tokens, foreign)
        self.assertNotIn('preprocess_embed', vars(self.clip.encoder.transformer))
        del self.clip.encoder.process_tokens
        self.assert_clean()

    def test_missing_hook_or_taps_fail_without_fallback(self):
        context = self.prepare()
        for target, name, value, message in ((Transformer, 'preprocess_embed', None, 'requires process_tokens'),
                                             (Encoder, 'layer', [2, 5], 'tap layout')):
            with patch.object(target, name, value):
                with self.assertRaisesRegex(RuntimeError, message):
                    studies.build_studies(context, [card()])
            self.assert_clean()

    def test_resource_limits_fail_before_transformer_and_cleanup(self):
        context = self.prepare()
        before = self.clip.encodes
        for options, message in (({'max_passes': 2}, 'pass budget'),
                                  ({'max_image_pixels': 1}, 'pixel budget'),
                                  ({'max_tokens': 1}, 'token-row budget')):
            with self.assertRaisesRegex(RuntimeError, message):
                studies.build_studies(context, [card()], **options)
            self.assertEqual(self.clip.encodes, before)
            self.assert_clean()
        token_ledger = ledger.TokenLedger.build(self.clip.tokenize('plain', images=[self.source]), ('source',))
        with self.assertRaisesRegex(RuntimeError, 'before transformer'):
            with hooks.encoder_lease(self.clip) as (model, transformer):
                with hooks.controlled_encode(model, transformer, token_ledger, max_tokens=2):
                    self.clip.encode_from_tokens_scheduled(token_ledger.tagged_tokens())
        self.assert_clean()

    def test_invalid_axis_and_unowned_off_are_rejected(self):
        context = self.prepare()
        for bad in (True, float('nan'), float('inf'), 7, -7, '1'):
            with self.assertRaises(ValueError):
                studies.build_studies(context, [card(bad)])
        with self.assertRaisesRegex(ValueError, 'canonical axis poles'):
            studies.build_studies(context, [card(), card(plus='changed')])
        with self.assertRaisesRegex(RuntimeError, 'complete owned native rebuild'):
            context.remove_reference('native:donor')

    def test_near_zero_activates_native_and_steered_as_separate_branches(self):
        context = self.prepare()
        result = studies.build_studies(context, [card(0.01)])
        conditioning = result.for_step(self.model, 0, 8)['positive']
        self.assertEqual(len(conditioning), 2)
        self.assertIs(conditioning[0][0], context.native['positive'][0][0])
        self.assertAlmostEqual(conditioning[0][1]['strength'], 0.96)
        self.assertAlmostEqual(conditioning[1][1]['strength'], 0.04)
        self.assertEqual(conditioning[0][0].shape, conditioning[1][0].shape)

    def test_projected_studies_drop_only_owned_poles_before_composition(self):
        context = self.prepare()
        result = studies.build_studies(context, [card()])
        expanded = result.ledgers[0]
        positions = result.retained_output_positions
        for span in expanded.poles:
            start, end = expanded.output_span(span)
            self.assertFalse(set(range(start, end)).intersection(positions))
        for _, start, end in expanded.images:
            self.assertTrue(set(range(start - expanded.strip, end - expanded.strip)).issubset(positions))
        self.assertEqual(len(positions), context.native['positive'][0][0].shape[1])
        value, metadata = result.for_step(self.model, 0, 8)['positive'][0]
        self.assertEqual(value.shape, context.native['positive'][0][0].shape)
        self.assertEqual(metadata['attention_mask'].values,
                         context.native['positive'][0][1]['attention_mask'].values)

    def test_projection_rejects_changed_original_suffix(self):
        full = self.clip.tokenize('plain\n\nbright')
        original = self.clip.tokenize('plain')
        token_ledger = ledger.TokenLedger.build(full, (), [original])
        raw = [[ledger.element(item) for item in full[ledger.TOKEN_KEY][0]]]
        embeds, _, _, info = self.clip.encoder.process_tokens(raw, 'synthetic')
        expanded = token_ledger.expand(raw, info, embeds.shape[1])
        original[ledger.TOKEN_KEY][0][-1] = (999, 1.0)
        with self.assertRaisesRegex(RuntimeError, 'original native token sequence'):
            token_ledger.native_output_positions(original, expanded)

    def test_wrapper_metadata_encoder_and_source_version_changes_reject(self):
        for change in ('wrapper', 'metadata', 'encoder', 'source'):
            with self.subTest(change=change):
                context = self.prepare()
                if change == 'wrapper':
                    self.model.model_options = {'wrappers': [lambda: None]}
                elif change == 'metadata':
                    self.foreign['changed'] = True
                elif change == 'encoder':
                    self.clip.cond_stage_model = SimpleNamespace(clip='qwen3vl_4b', qwen3vl_4b=self.clip.encoder)
                else:
                    self.source._version = 1
                with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                    studies.build_studies(context, [card()])

    def test_unknown_grounder_source_is_rejected_before_instantiation(self):
        import types
        fake_nodes = types.ModuleType('nodes')
        fake_nodes.NODE_CLASS_MAPPINGS = {'Krea2EditGroundedEncode': Grounder}
        with patch.dict(sys.modules, {'nodes': fake_nodes}):
            with self.assertRaisesRegex(RuntimeError, 'source revision is unverified'):
                self.original_load_grounder()

    def test_adopted_bundle_zero_preserves_foreign_fields_without_native_calls(self):
        context = self.prepare()
        bundle = {**context.native, 'foreign-wrapper-state': object(), 'sampler-grid': object()}
        before = self.clip.encodes, self.clip.tokenizations, len(self.grounder.preps)
        adopted = native.prepare_context(self.clip, self.model, 'plain', source=self.source,
                                         donor=self.donor, revision='adopted-v1', native_bundle=bundle)
        result = studies.build_studies(adopted, [card(0)])
        self.assertIs(result.sampler_conditioning(), bundle)
        self.assertEqual(before, (self.clip.encodes, self.clip.tokenizations, len(self.grounder.preps)))
        self.assertIs(result.for_step(self.model, 0, 8)['foreign-wrapper-state'], bundle['foreign-wrapper-state'])

    def test_prepare_node_adopts_paired_ports_and_rejects_partial_pair(self):
        context = self.prepare()
        kwargs = {'Krea CLIP': self.clip, 'Native MODEL': self.model,
                  'Final image prompt': 'plain', 'Negative prompt': '',
                  'Native context revision': 'ports-v1', 'Grounding pixels': 768,
                  'Grounding system prompt': '', 'Clean source image': self.source,
                  'Clean donor image': self.donor,
                  'Native positive conditioning': context.native['positive'],
                  'Native negative conditioning': context.native['negative']}
        before = self.clip.encodes, self.clip.tokenizations
        result = NODES.KGKrea2PrepareNativeContextV12().execute(**kwargs)[0]
        self.assertIs(result.native['positive'], context.native['positive'])
        self.assertIs(result.native['negative'], context.native['negative'])
        self.assertEqual(before, (self.clip.encodes, self.clip.tokenizations))
        del kwargs['Native negative conditioning']
        with self.assertRaisesRegex(ValueError, 'together'):
            NODES.KGKrea2PrepareNativeContextV12().execute(**kwargs)

    def test_source_pin_normalizes_crlf_without_executing_source(self):
        import hashlib
        import tempfile
        import types
        data = b'# synthetic fixture only\nclass Example: pass\n'
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        fake_nodes = types.ModuleType('nodes')
        fake_nodes.NODE_CLASS_MAPPINGS = {'Krea2EditGroundedEncode': Grounder}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'synthetic.py'
            path.write_bytes(data.replace(b'\n', b'\r\n'))
            with patch.dict(sys.modules, {'nodes': fake_nodes}), patch.object(native, 'GROUNDING_BLOB', blob), \
                    patch.object(native.inspect, 'getfile', return_value=str(path)):
                self.assertIsInstance(self.original_load_grounder(), Grounder)

    def test_ledger_rejects_truncation_merge_and_incomplete_expansion(self):
        tokens = self.clip.tokenize('plain\n\nbright', images=[self.source, self.donor])
        prefix = self.clip.tokenize('plain', images=[self.source, self.donor])
        token_ledger = ledger.TokenLedger.build(tokens, ('source', 'donor'), [prefix])
        raw = [[ledger.element(item) for item in tokens[ledger.TOKEN_KEY][0]]]
        embeds, _, _, info = self.clip.encoder.process_tokens(raw, 'synthetic')
        with self.assertRaisesRegex(RuntimeError, 'dropped or added'):
            token_ledger.expand(raw, info[:1], embeds.shape[1])
        info[1]['index'] -= 1
        with self.assertRaisesRegex(RuntimeError, 'index/size mismatch'):
            token_ledger.expand(raw, info, embeds.shape[1])
        prefix[ledger.TOKEN_KEY][0][-6] = (987, 1.0)
        with self.assertRaisesRegex(RuntimeError, 'merged'):
            ledger.TokenLedger.build(tokens, ('source', 'donor'), [prefix])
        with self.assertRaisesRegex(RuntimeError, 'truncated'):
            ledger.TokenLedger.build(tokens, ('source', 'donor'), [tokens])

    def test_versioned_node_ports_cannot_connect_active_studies_as_conditioning(self):
        self.assertEqual(NODES.KGKrea2CombinedNativeStudiesV12.RETURN_TYPES,
                         ('KG_KREA_NATIVE_STUDIES_V12', 'STRING'))
        result = NODES.KGKrea2CombinedNativeStudiesV12().execute(**{
            'Native context': self.prepare(), 'Early-to-final handoff': 0.4,
            'Native coefficient budget': 2, 'Native axis 1': card()})
        self.assertTrue(result[0].active)
        self.assertIn('sampler export gated', result[1])

    def test_neutral_consumer_returns_original_guider_without_host_reads(self):
        from native_v12_tests import consumer
        result = studies.build_studies(self.prepare(), [card(0)])
        guider = SimpleNamespace(model_patcher=self.model)
        with patch.object(consumer, 'load_consumer_host', side_effect=AssertionError('neutral host read')):
            self.assertIs(consumer.bind_native_guider(result, guider), guider)

    def test_consumer_rejects_invalid_native_schedule_before_evaluation(self):
        from native_v12_tests import consumer
        for values in ([1], [1, 1, 0], [0, 1], [1, -1], [float('nan'), 0], [True, 0]):
            with self.assertRaises(RuntimeError):
                consumer._schedule(values)
        self.assertEqual(consumer._schedule([2, 1, 0]), (2.0, 1.0, 0.0))

    def owned(self, patcher):
        from native_v12_tests import owned
        with patch.object(owned, 'load_edit_node', return_value=patcher):
            return owned.prepare_owned_grounded(self.clip, self.model, 'plain', self.source,
                {'samples': self.latent}, {'samples': self.target, 'noise_mask': self.mask},
                donor=self.donor, source_latent_b={'samples': object()}, vae=object(),
                revision='synthetic-owned-v1', native_metadata=self.foreign,
                ref_boost=3, ref_boost_a=0.75, ref_boost_mask=object(),
                ref_position='beside (right of target)', ref_position_a='aligned (trained)')

    def test_owned_donor_off_rebuilds_model_vision_vae_pair_and_preserves_foreign(self):
        callback = lambda *args: None
        self.model.model_options = {'transformer_options': {'wrappers': {'diffusion_model': {'foreign': [callback]}}}}
        patcher = NativePatch()
        context = self.owned(patcher)
        old_model = context.native['model']
        rebuilt = context.remove_reference('native:donor')
        self.assertEqual(len(patcher.calls), 2)
        self.assertTrue(all(model is self.model for model, _ in patcher.calls))
        self.assertIsNot(rebuilt.native['model'], old_model)
        self.assertIn('source_image_b', patcher.calls[0][1])
        self.assertIn('source_latent_b', patcher.calls[0][1])
        self.assertNotIn('source_image_b', patcher.calls[1][1])
        self.assertNotIn('source_latent_b', patcher.calls[1][1])
        self.assertEqual(patcher.calls[1][1]['ref_boost'], 0.75)
        self.assertEqual(patcher.calls[1][1]['ref_position'], 'aligned (trained)')
        self.assertIsNone(patcher.calls[1][1]['ref_boost_mask'])
        for key in ('source_latent', 'target_latent', 'noise_mask', 'metadata'):
            self.assertIs(rebuilt.native[key], context.native[key])
        self.assertIs(rebuilt.native['metadata'], self.foreign)
        wrappers = rebuilt.native['model'].model_options['transformer_options']['wrappers']['diffusion_model']
        self.assertEqual(len(wrappers['krea2_edit']), 1)
        self.assertIs(wrappers['foreign'][0], callback)
        self.assertNotIn('krea2_edit', self.model.model_options['transformer_options']['wrappers']['diffusion_model'])
        self.assertEqual([call[0] for call in self.grounder.calls], ['plain', '', 'plain', ''])
        self.assertTrue(all(call[2] is None for call in self.grounder.calls[-2:]))
        self.assertEqual(rebuilt.prepare_inputs().owners, ('native:source',))
        self.assertIs(rebuilt.sources[0], self.source)
        self.assertIsNone(rebuilt.sources[1])
        neutral = studies.build_studies(rebuilt, [card(0)])
        self.assertIs(neutral.sampler_conditioning(), rebuilt.native)

    def test_owned_off_rejects_changed_original_or_core_source_removal(self):
        context = self.owned(NativePatch())
        with self.assertRaisesRegex(RuntimeError, 'only owns optional donor'):
            context.remove_reference('native:source')
        self.model.patches_uuid = 'changed-original'
        with self.assertRaisesRegex(RuntimeError, 'original owned native preparation changed'):
            context.remove_reference('native:donor')

    def test_owned_rebuild_rejects_foreign_option_changes_and_existing_edit_patch(self):
        patcher = NativePatch()
        patcher.change_foreign = True
        with self.assertRaisesRegex(RuntimeError, 'changed unowned model options'):
            self.owned(patcher)
        patcher.change_foreign = False
        self.model.model_options = {'transformer_options': {'wrappers': {'diffusion_model': {'krea2_edit': [object()]}}}}
        before = len(patcher.calls)
        with self.assertRaisesRegex(RuntimeError, 'MODEL before its edit wrapper'):
            self.owned(patcher)
        self.assertEqual(len(patcher.calls), before)

    def test_owned_off_node_returns_rebuilt_native_bundle_fields(self):
        context = self.owned(NativePatch())
        result = NODES.KGKrea2RemoveOwnedReferenceV12().execute(**{
            'Native context': context, 'Owned reference OFF': 'native:donor'})
        self.assertEqual(len(result), 5)
        self.assertIs(result[1], result[0].native['model'])
        self.assertIs(result[2], result[0].native['positive'])
        self.assertIs(result[3], result[0].native['negative'])
        self.assertIs(result[4], context.native['target_latent'])

    def test_owned_vision_only_crop_donor_rejected_before_patch_or_encode(self):
        from native_v12_tests import owned
        before = self.clip.encodes, self.clip.tokenizations
        with patch.object(owned, 'load_edit_node', side_effect=AssertionError('patch node loading is too early')):
            with self.assertRaisesRegex(ValueError, 'VAE pixel path or donor latent packet'):
                owned.prepare_owned_grounded(self.clip, self.model, 'plain', self.source,
                    {'samples': self.latent}, {'samples': self.target, 'noise_mask': self.mask},
                    donor=self.donor, source_latent_b=None, vae=None, fit_mode='crop', revision='unbound-donor-v1')
        self.assertEqual(before, (self.clip.encodes, self.clip.tokenizations))

    def test_owned_reconstruction_cannot_overlap_native_shared_model_consumer(self):
        from native_v12_tests import consumer
        self.model.model = object()
        guider = SimpleNamespace(model_patcher=self.model)
        patcher = NativePatch()
        before = self.clip.encodes
        with consumer._guider_lease(guider):
            with self.assertRaisesRegex(RuntimeError, 'reconstruction cannot overlap sampling'):
                self.owned(patcher)
        self.assertEqual(patcher.calls, [])
        self.assertEqual(self.clip.encodes, before)
        self.assertFalse(consumer._busy)

    def test_inference_handle_avoids_throwing_version_and_marks_unversioned_identity(self):
        class InferenceImage(Image):
            def is_inference(self):
                return True

            @property
            def _version(self):
                raise RuntimeError('Inference tensors do not track version counter.')

        self.source = InferenceImage(7, 3)
        context = self.prepare()
        self.assertEqual(native._signature(self.source),
                         ('handle', id(self.source), ('unversioned-inference',)))
        context.verify()
        self.assertIs(studies.build_studies(context, [card(0)]).sampler_conditioning(), context.native)
        context.native['source_latent'] = InferenceImage(7, 3)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            context.verify()

    def test_throwing_unknown_version_fails_and_encoder_lease_is_released(self):
        class BrokenVersion:
            @property
            def _version(self):
                raise RuntimeError('unknown version getter failure')

        with self.assertRaisesRegex(RuntimeError, 'unknown version getter failure'):
            with hooks.encoder_lease(self.clip):
                native._signature({'foreign': BrokenVersion()})
        with hooks.encoder_lease(self.clip):
            pass
        self.assertFalse(hooks._busy)
        self.assertFalse(hooks._owner_threads)

    def test_throwing_owned_recipe_signature_releases_model_preparation_lease(self):
        from native_v12_tests import consumer
        context = self.owned(NativePatch())

        class BrokenVersion:
            @property
            def _version(self):
                raise RuntimeError('owned signature getter failure')

        context.owned_recipe.patch_args['foreign'] = BrokenVersion()
        with self.assertRaisesRegex(RuntimeError, 'owned signature getter failure'):
            context.owned_recipe.build()
        self.assertFalse(consumer._busy)
        with consumer.native_model_preparation_lease(context.owned_recipe.original_model):
            pass

    def test_regular_handle_version_change_still_rejects(self):
        value = SimpleNamespace(_version=1)
        before = native._signature(value)
        value._version = 2
        self.assertNotEqual(native._signature(value), before)

    def test_adopting_paired_ports_retains_target_noise_mask_without_duplicate_port(self):
        original = self.prepare()
        target = {'samples': self.target, 'noise_mask': self.mask}
        context, = NODES.KGKrea2PrepareNativeContextV12().execute(**{
            'Krea CLIP': self.clip, 'Native MODEL': self.model,
            'Final image prompt': 'plain', 'Negative prompt': '',
            'Native context revision': 'adopted-mask-v1', 'Grounding pixels': 768,
            'Grounding system prompt': '', 'Native target latent': target,
            'Native positive conditioning': original.native['positive'],
            'Native negative conditioning': original.native['negative'],
        })
        self.assertIs(context.native['target_latent'], target)
        self.assertIs(context.native['noise_mask'], self.mask)

    def test_er_sde_acceptance_delegates_native_sigma_offset_without_changing_input(self):
        from native_v12_tests import consumer
        raw = [1.0, 0.5, 0.0]
        model_sampling = object()
        calls = []
        def offset(sigmas, sampling):
            self.assertIs(sigmas, raw)
            self.assertIs(sampling, model_sampling)
            calls.append('native-offset')
            return [0.9999, *sigmas[1:]]
        er_sde = lambda: None
        host = SimpleNamespace(sample_er_sde=er_sde, offset_first_sigma_for_snr=offset)
        guider = SimpleNamespace(model_patcher=SimpleNamespace(get_model_object=lambda name: model_sampling))
        schedule = consumer._accepted_schedule(guider, SimpleNamespace(sampler_function=er_sde), raw, host)
        self.assertEqual(schedule, (0.9999, 0.5, 0.0))
        self.assertEqual(raw, [1.0, 0.5, 0.0])
        self.assertEqual(calls, ['native-offset'])
        calls.clear()
        self.assertEqual(consumer._accepted_schedule(guider, SimpleNamespace(sampler_function=lambda: None), raw, host), tuple(raw))
        self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
