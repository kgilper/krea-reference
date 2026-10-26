"""Owned target provenance and caller boundary; native source integration is separate."""
import importlib.util
from dataclasses import replace
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('target_preparation_v12_tests', ROOT / 'kg_krea_v12/__init__.py',
                                             submodule_search_locations=[str(ROOT / 'kg_krea_v12')])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
from target_preparation_v12_tests import latents, native, nodes, consumer


class Tensor:
    is_nested = False
    def __init__(self, shape, value=0):
        self.shape, self.value, self._version = tuple(shape), value, 0
        self.ndim = len(shape)


class LatentFormat:
    latent_channels, latent_dimensions = 16, 3
    spacial_downscale_ratio, temporal_downscale_ratio = 8, 4
    def fix_empty_latent(self, value):
        return value


class Wan21(LatentFormat):
    pass


class TargetPreparationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        fmt = Wan21()
        utils, formats, comfy, sample = (ModuleType(name) for name in ('fixture_utils', 'fixture_formats', 'fixture_comfy', 'fixture_sample'))
        comfy.utils = utils
        formats.Wan21, formats.LatentFormat = Wan21, LatentFormat
        sample.comfy = comfy
        def helper(model, value, spatial=None, temporal=None):
            self.calls.append((model, value, spatial, temporal))
            shape = list(value.shape)
            if value.value == 0:
                shape[1] = 16
                if spatial is not None and spatial != 8:
                    shape[-2:] = [round(length * spatial / 8) for length in shape[-2:]]
            if len(shape) == 4:
                shape.insert(2, 1)
            if tuple(shape) != value.shape:
                value = Tensor(shape, value.value)
            return fmt.fix_empty_latent(value)
        sample.fix_empty_latent_channels = helper
        self.host = latents.NativeLatentHost(sample, utils, formats, comfy, fmt, Wan21, LatentFormat, Tensor,
            ((sample, 'fix_empty_latent_channels', helper, helper.__code__),))
        self.model = NS(model=object(), model_options={}, patches_uuid='owned-model', get_model_object=lambda name: fmt)
        self.raw = Tensor((1, 4, 3, 5))
        self.mask, self.foreign, self.source = object(), object(), object()
        self.target = dict(samples=self.raw, noise_mask=self.mask, foreign=self.foreign, downscale_ratio_spacial=16)
        self.bundle = dict(model=self.model, positive=[], negative=[], source_latent=self.source,
                           target_latent=self.target, noise_mask=self.mask)
        self.context = native.prepare_context(NS(), self.model, 'owned prompt', revision='owned-target-v1', native_bundle=self.bundle)
        host_patch = patch.object(latents, 'load_latent_host', return_value=self.host)
        host_patch.start()
        self.addCleanup(host_patch.stop)
        self.addCleanup(lambda: self.assertFalse(consumer._busy))

    def prepare(self):
        return latents.prepare_context_target(self.context, enabled=True)

    def test_disabled_is_exact_original_context_and_target_without_host_reads(self):
        with patch.object(latents, 'load_latent_host', side_effect=AssertionError('OFF host read')):
            context, target = latents.prepare_context_target(self.context)
        self.assertIs(context, self.context)
        self.assertIs(target, self.target)
        self.assertFalse(self.calls)

    def test_shared_output_consumes_scale_and_second_native_call_is_identity(self):
        context, target = self.prepare()
        self.assertIs(context.native['target_latent'], target)
        self.assertEqual(target['samples'].shape, (1, 16, 1, 6, 10))
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn('downscale_ratio_spacial', target)
        self.assertNotIn('downscale_ratio_temporal', target)
        again = self.host.sample_module.fix_empty_latent_channels(self.model, target['samples'], target.get('downscale_ratio_spacial'), target.get('downscale_ratio_temporal'))
        self.assertIs(again, target['samples'])
        self.assertEqual(self.target['samples'].shape, (1, 4, 3, 5))
        self.assertEqual(self.target['downscale_ratio_spacial'], 16)
        context.verify()

    def test_foreign_packet_values_mask_source_and_conditioning_retain_identity(self):
        context, target = self.prepare()
        self.assertIs(target['noise_mask'], self.mask)
        self.assertIs(target['foreign'], self.foreign)
        for key in ('model', 'positive', 'negative', 'source_latent', 'noise_mask'):
            self.assertIs(context.native[key], self.bundle[key])
        self.context.verify()

    def test_nonempty_native_values_keep_channels_resolution_and_mask(self):
        self.raw.shape, self.raw.ndim, self.raw.value = (1, 16, 3, 5), 4, 7
        self.context = native.prepare_context(NS(), self.model, 'owned prompt', revision='nonempty', native_bundle=self.bundle)
        context, target = self.prepare()
        self.assertEqual(target['samples'].shape, (1, 16, 1, 3, 5))
        self.assertEqual(target['samples'].value, 7)
        self.assertIs(target['noise_mask'], self.mask)
        context.verify()

    def test_different_model_packet_or_same_value_tensor_cannot_use_receipt(self):
        _, target = self.prepare()
        receipt = target[latents.PROVENANCE_KEY]
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            receipt.verify(NS(**vars(self.model)), target)
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            receipt.verify(self.model, target.copy())
        target['samples'] = Tensor(target['samples'].shape)
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            receipt.verify(self.model, target)

    def test_original_and_canonical_mask_mutations_reject(self):
        context, target = self.prepare()
        self.target['noise_mask'] = object()
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            context.verify()
        self.target['noise_mask'] = self.mask
        target['noise_mask'] = object()
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            context.verify()

    def test_raw_tensor_version_and_model_revision_mutations_reject(self):
        context, _ = self.prepare()
        self.raw._version += 1
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            context.verify()
        self.raw._version -= 1
        self.model.patches_uuid = 'foreign-revision'
        with self.assertRaisesRegex(RuntimeError, 'provenance changed'):
            context.verify()

    def test_format_or_helper_replacement_after_preparation_rejects(self):
        context, _ = self.prepare()
        self.host.format.latent_channels = 4
        with self.assertRaisesRegex(RuntimeError, 'format changed'):
            context.verify()
        del self.host.format.latent_channels
        self.host.sample_module.fix_empty_latent_channels = lambda *args: self.raw
        with self.assertRaisesRegex(RuntimeError, 'function changed'):
            context.verify()

    def test_unsupported_batch_nested_duplicate_or_ratio_rejects(self):
        for change in ({'samples': Tensor((2, 4, 3, 5))}, {'downscale_ratio_spacial': float('nan')},
                       {latents.PROVENANCE_KEY: object()}):
            with self.subTest(change=change), self.assertRaises((RuntimeError, ValueError)):
                latents.prepare_native_target(self.model, {**self.target, **change}, True)
        self.raw.is_nested = True
        with self.assertRaisesRegex(RuntimeError, 'ordinary image latent'):
            self.prepare()

    def test_additive_node_exports_both_shared_ports(self):
        cls = nodes.KGKrea2PrepareNativeTargetV12
        self.assertEqual(cls.RETURN_TYPES, ('KG_KREA_NATIVE_CONTEXT_V12', 'LATENT'))
        context, target = cls().execute(**{'Native context': self.context, 'Native target preparation enabled': True})
        self.assertIs(context.native['target_latent'], target)
        self.assertEqual(cls.INPUT_TYPES()['required']['Native target preparation enabled'][1]['default'], False)

    def test_preparation_cannot_overlap_an_owned_model_operation(self):
        with consumer.native_model_preparation_lease(self.model):
            with self.assertRaisesRegex(RuntimeError, 'busy'):
                self.prepare()
        self.assertFalse(self.calls)

    def test_grounded_spatial_change_rejects_without_changing_original_handles(self):
        context = replace(self.context, owned_recipe=NS(verify=lambda: None))
        with self.assertRaisesRegex(RuntimeError, 'grounded target preparation cannot change spatial'):
            latents.prepare_context_target(context, enabled=True)
        self.assertIs(context.native['target_latent'], self.target)
        self.assertIs(self.target['samples'], self.raw)
        self.assertIs(self.target['noise_mask'], self.mask)
        self.assertIs(context.native['source_latent'], self.source)
        self.assertEqual(self.raw.shape, (1, 4, 3, 5))
        context.verify()

    def test_grounded_channel_dimension_preparation_with_same_spatial_shape_is_allowed(self):
        self.target['downscale_ratio_spacial'] = 8
        context = native.prepare_context(NS(), self.model, 'owned prompt', revision='grounded-no-resize', native_bundle=self.bundle)
        context = replace(context, owned_recipe=NS(verify=lambda: None))
        prepared, target = latents.prepare_context_target(context, enabled=True)
        self.assertEqual(target['samples'].shape, (1, 16, 1, 3, 5))
        self.assertIs(prepared.owned_recipe, context.owned_recipe)
        self.assertIs(target['noise_mask'], self.mask)
        prepared.verify()


if __name__ == '__main__':
    unittest.main()
