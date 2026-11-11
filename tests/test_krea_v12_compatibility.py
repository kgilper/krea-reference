"""Source-admission and observed loaded-code regressions; no host or model import."""
import functools
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('compatibility_v12_tests', ROOT / 'kg_krea_v12/__init__.py',
                                             submodule_search_locations=[str(ROOT / 'kg_krea_v12')])
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)
from compatibility_v12_tests import compatibility, consumer, enhancer


class CompatibilityTests(unittest.TestCase):
    def test_complete_reviewed_torch_profiles_are_admitted(self):
        self.assertEqual(set(compatibility._TORCH_SOURCE_PROFILES), {'pytorch-v2.9.0', 'pytorch-v2.11.0'})
        for context, grad in compatibility._TORCH_SOURCE_PROFILES.values():
            self.assertEqual(len(context) + len(grad), 7)
            self.assertEqual(compatibility._torch_source_profile(dict(context), dict(grad)), (context, grad))

    def test_mixed_torch_context_definitions_reject(self):
        old_context, grad = compatibility._TORCH_SOURCE_PROFILES['pytorch-v2.9.0']
        new_context, _ = compatibility._TORCH_SOURCE_PROFILES['pytorch-v2.11.0']
        changed = [name for name in old_context if old_context[name] != new_context[name]]
        self.assertEqual(set(changed), {'context_decorator', '_NoParamDecoratorContextManager.__new__'})
        for name in changed:
            mixed = {**old_context, name: new_context[name]}
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'source tuple is unverified'):
                compatibility._torch_source_profile(mixed, grad)

    def test_unknown_or_missing_torch_definition_rejects_for_both_profiles(self):
        for context, grad in compatibility._TORCH_SOURCE_PROFILES.values():
            for name in context:
                for value in (None, 'unknown'):
                    with self.subTest(name=name, value=value), self.assertRaisesRegex(RuntimeError, 'source tuple is unverified'):
                        compatibility._torch_source_profile({**context, name: value}, grad)
            for name in grad:
                with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'source tuple is unverified'):
                    compatibility._torch_source_profile(context, {**grad, name: 'unknown'})

    def test_exact_core_pairs_admit_but_cross_pairs_and_unknown_reject(self):
        expected = {
            (consumer.SAMPLERS_BLOB, consumer.MODEL_BASE_SHA256): 'native-krea-writable-scope-v1',
            (consumer.SAMPLERS_BLOB, consumer.MODEL_BASE_V2_SHA256): 'native-krea-writable-scope-v2',
            ('17f7bb8babdeec605586cc08df2ab1c4f1c92fd4',
             '5722b46418c6b7475041733d659bbd71f11f1dacb4d0aaff2b21aeb2c82d5542'): 'native-krea-pre-writable-scope-v1',
        }
        self.assertEqual(consumer.CONSUMER_SOURCE_PROFILES, expected)
        self.assertEqual(consumer._WRITABLE_SCOPE_PROFILES,
                         frozenset(('native-krea-writable-scope-v1', 'native-krea-writable-scope-v2')))
        for pair, profile in expected.items():
            self.assertEqual(consumer._consumer_source_profile(*pair), profile)
        samplers_blobs = {pair[0] for pair in expected} | {'unknown'}
        model_hashes = {pair[1] for pair in expected} | {'unknown'}
        for s_blob in samplers_blobs:
            for m_hash in model_hashes:
                if (s_blob, m_hash) in expected:
                    continue
                with self.subTest(samplers_blob=s_blob, model_base_sha256=m_hash):
                    with self.assertRaisesRegex(RuntimeError, 'source pair is unverified'):
                        consumer._consumer_source_profile(s_blob, m_hash)

    def test_load_consumer_host_enforces_writable_hook_for_both_writable_profiles(self):
        from unittest.mock import patch
        samplers_src = (
            'class CFGGuider:\n'
            '    def sample(self): return 1\n'
            '    def outer_sample(self): return 1\n'
            '    def inner_sample(self): return 1\n'
            '    def predict_noise(self): return 1\n'
            '    def inner_set_conds(self): return 1\n'
            '    def set_conds(self): return 1\n'
            'class KSAMPLER:\n'
            '    def sample(self): return 1\n'
            'class KSamplerX0Inpaint:\n'
            '    def __call__(self): return 1\n'
            'def process_conds(): return 1\n'
            'def calc_cond_batch(): return 1\n'
            'def _calc_cond_batch(): return 1\n'
            'def sampling_function(): return 1\n'
            'def cfg_function(): return 1\n'
        ).encode()
        writable_model_src = (
            'class BaseModel:\n'
            '    def apply_model(self): return 1\n'
            '    def _apply_model(self): return 1\n'
            '    def extra_conds(self): return 1\n'
            '    def process_latent_in(self): return 1\n'
            '    def process_latent_out(self): return 1\n'
            '    def get_writable_model(self): return None\n'
            'class Krea2(BaseModel):\n'
            '    def __init__(self): pass\n'
            '    def extra_conds(self): return 1\n'
        ).encode()
        pre_writable_model_src = writable_model_src.replace(b'    def get_writable_model(self): return None\n', b'')
        helpers_src = b'def convert_cond(): return 1\n'
        euler_src = (
            'def sample_euler(): return 1\n'
            'def sample_euler_ancestral(): return 1\n'
            'def sample_euler_ancestral_RF(): return 1\n'
            'def sample_er_sde(): return 1\n'
            'def offset_first_sigma_for_snr(): return 1\n'
            'def sigma_to_half_log_snr(): return 1\n'
        ).encode()

        def build_modules(model_src):
            comfy = ModuleType('comfy')
            k_diff = ModuleType('comfy.k_diffusion')
            mods = {}
            for name, src in (('comfy.samplers', samplers_src), ('comfy.model_base', model_src),
                              ('comfy.sampler_helpers', helpers_src), ('comfy.k_diffusion.sampling', euler_src)):
                mod = ModuleType(name)
                exec(compile(src, f'<{name}>', 'exec', dont_inherit=True), mod.__dict__)
                mods[name] = (mod, src)
            comfy.samplers = mods['comfy.samplers'][0]
            comfy.model_base = mods['comfy.model_base'][0]
            comfy.sampler_helpers = mods['comfy.sampler_helpers'][0]
            k_diff.sampling = mods['comfy.k_diffusion.sampling'][0]
            comfy.k_diffusion = k_diff
            sys_map = {'comfy': comfy, 'comfy.k_diffusion': k_diff, **{k: v[0] for k, v in mods.items()}}
            byte_map = {id(v[0]): v[1] for v in mods.values()}
            return sys_map, byte_map

        for profile in ('native-krea-writable-scope-v1', 'native-krea-writable-scope-v2'):
            with self.subTest(profile=profile):
                sys_map, byte_map = build_modules(writable_model_src)
                with patch.dict(sys.modules, sys_map), \
                     patch.object(consumer, '_source_bytes', side_effect=lambda m: byte_map[id(m)]), \
                     patch.object(consumer, '_consumer_source_profile', return_value=profile), \
                     patch.object(consumer, 'EULER_SHA256', consumer.hashlib.sha256(euler_src).hexdigest()), \
                     patch.object(consumer, 'HELPERS_SHA256', consumer.hashlib.sha256(helpers_src).hexdigest()):
                    s, e, mb = consumer.load_consumer_host()
                    self.assertIs(mb, sys_map['comfy.model_base'])
                    mb.BaseModel.get_writable_model = lambda self: object()
                    with self.assertRaisesRegex(RuntimeError, 'loaded function differs'):
                        consumer.load_consumer_host()

        sys_map, byte_map = build_modules(pre_writable_model_src)
        with patch.dict(sys.modules, sys_map), \
             patch.object(consumer, '_source_bytes', side_effect=lambda m: byte_map[id(m)]), \
             patch.object(consumer, '_consumer_source_profile', return_value='native-krea-pre-writable-scope-v1'), \
             patch.object(consumer, 'EULER_SHA256', consumer.hashlib.sha256(euler_src).hexdigest()), \
             patch.object(consumer, 'HELPERS_SHA256', consumer.hashlib.sha256(helpers_src).hexdigest()):
            consumer.load_consumer_host()
            sys_map['comfy.model_base'].BaseModel.get_writable_model = lambda self: None
            with self.assertRaisesRegex(RuntimeError, 'unverified writable-model hook'):
                consumer.load_consumer_host()

    def test_loaded_body_changed_after_disk_read_rejects(self):
        source = 'def predict(x):\n    return x + 1\n'
        module = ModuleType('observed_source_fixture')
        exec(compile(source, '<original-loaded-file>', 'exec', dont_inherit=True), module.__dict__)
        compatibility.verify_loaded_functions(module, source.encode(), ('predict',))
        changed = ModuleType('changed')
        exec('def predict(x):\n    return x - 1\n', changed.__dict__)
        module.predict = changed.predict
        with self.assertRaisesRegex(RuntimeError, 'loaded function differs'):
            compatibility.verify_loaded_functions(module, source.encode(), ('predict',))

    def test_loaded_nested_code_and_exception_cleanup_must_match(self):
        source = ('class Guider:\n'
                  '    def sample(self, x):\n'
                  '        def evaluate():\n'
                  '            return x + 1\n'
                  '        try:\n'
                  '            return evaluate()\n'
                  '        finally:\n'
                  '            self.clean = True\n')
        module = ModuleType('nested_source_fixture')
        exec(compile(source, '<original>', 'exec', dont_inherit=True), module.__dict__)
        compatibility.verify_loaded_functions(module, source.encode(), ('Guider.sample',))
        other = ModuleType('changed_nested')
        exec(compile(source.replace('x + 1', 'x + 2'), '<other>', 'exec', dont_inherit=True), other.__dict__)
        module.Guider.sample = other.Guider.sample
        with self.assertRaisesRegex(RuntimeError, 'loaded function differs'):
            compatibility.verify_loaded_functions(module, source.encode(), ('Guider.sample',))

    def test_wraps_numeric_change_on_undecorated_source_is_rejected(self):
        source = 'def step(x):\n    return x * 2\n'
        module = ModuleType('decorated_source_fixture')
        exec(compile(source, '<loaded>', 'exec', dont_inherit=True), module.__dict__)
        original = module.step
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            return original(*args, **kwargs) + 1
        module.step = wrapper
        self.assertEqual(module.step(3), 7)
        with self.assertRaisesRegex(RuntimeError, 'loaded function differs'):
            compatibility.verify_loaded_functions(module, source.encode(), ('step',))

    def test_even_transparent_unknown_wrapper_is_not_admitted(self):
        source = 'def step(x):\n    return x * 2\n'
        module = ModuleType('transparent_fixture')
        exec(compile(source, '<loaded>', 'exec', dont_inherit=True), module.__dict__)
        original = module.step
        @functools.wraps(original)
        def wrapper(*args, **kwargs):
            return original(*args, **kwargs)
        module.step = wrapper
        with self.assertRaisesRegex(RuntimeError, 'loaded function differs'):
            compatibility.verify_loaded_functions(module, source.encode(), ('step',))

    def test_source_declared_unknown_decorator_rejects_without_unwrapping(self):
        source = '@unknown_decorator\ndef step(x):\n    return x\n'
        module = ModuleType('unknown_decorator_fixture')
        exec(compile('def step(x):\n    return x\n', '<loaded>', 'exec', dont_inherit=True), module.__dict__)
        with self.assertRaisesRegex(RuntimeError, 'source decorator chain is unsupported'):
            compatibility.verify_loaded_functions(module, source.encode(), ('step',))

    def test_source_compilation_never_executes_module_body(self):
        source = 'must_never_execute()\ndef step(x):\n    return x\n'
        module = ModuleType('compile_only_fixture')
        exec(compile('def step(x):\n    return x\n', '<loaded>', 'exec', dont_inherit=True), module.__dict__)
        compatibility.verify_loaded_functions(module, source.encode(), ('step',))

    def test_extra_writable_or_multigpu_models_reject(self):
        patcher = NS(model=NS(), get_additional_models_with_key=lambda name: [])
        consumer._validate_writable_scope(patcher)
        patcher.model.get_writable_model = lambda *args: object()
        with self.assertRaisesRegex(RuntimeError, 'extra writable/multigpu'):
            consumer._validate_writable_scope(patcher)
        del patcher.model.get_writable_model
        patcher.get_additional_models_with_key = lambda name: [object()]
        with self.assertRaisesRegex(RuntimeError, 'extra writable/multigpu'):
            consumer._validate_writable_scope(patcher)

    def test_enhancer_profiles_bind_only_two_reviewed_whole_sources(self):
        self.assertEqual(set(enhancer.ENHANCER_SOURCE_PROFILES),
                         {'c46e1c3ed244caaef231c580bb601ea935b3d1c7',
                          '31e24388a8d495a524f46371659d3087e2302664'})


if __name__ == '__main__':
    unittest.main()
