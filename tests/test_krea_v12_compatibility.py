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
    def test_exact_core_pairs_admit_but_cross_pairs_and_unknown_reject(self):
        pairs = list(consumer.CONSUMER_SOURCE_PROFILES)
        self.assertEqual(len(pairs), 2)
        for pair in pairs:
            self.assertTrue(consumer._consumer_source_profile(*pair))
        for pair in ((pairs[0][0], pairs[1][1]), (pairs[1][0], pairs[0][1]), ('unknown', pairs[0][1])):
            with self.assertRaisesRegex(RuntimeError, 'source pair is unverified'):
                consumer._consumer_source_profile(*pair)

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
