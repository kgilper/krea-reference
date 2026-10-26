"""Cross-version AST representation and semantic-change guard regressions."""
import ast
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ast_fingerprint_v12_tests', ROOT / 'kg_krea_v12/__init__.py',
                                             submodule_search_locations=[str(ROOT / 'kg_krea_v12')])
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)
from ast_fingerprint_v12_tests import compatibility


class AstFingerprintTests(unittest.TestCase):
    def test_absent_old_python_type_params_equals_explicit_empty_new_field(self):
        node = ast.parse('def step(x):\n    return x + 1\n').body[0]
        old, new = copy.deepcopy(node), copy.deepcopy(node)
        if hasattr(old, 'type_params'):
            del old.type_params
        new.type_params = []
        self.assertEqual(compatibility._ast_fingerprint(old), compatibility._ast_fingerprint(new))
        new.type_params = [ast.Name(id='T', ctx=ast.Load())]
        self.assertNotEqual(compatibility._ast_fingerprint(old), compatibility._ast_fingerprint(new))

    def test_body_defaults_annotations_and_decorators_remain_binding(self):
        reference = ast.parse('def step(x: int, *, enabled=True):\n    return x + 1\n').body[0]
        original = compatibility._ast_fingerprint(reference)
        variants = [
            'def step(x: int, *, enabled=True):\n    return x + 2\n',
            'def step(x: int, *, enabled=False):\n    return x + 1\n',
            'def step(x: str, *, enabled=True):\n    return x + 1\n',
            '@other\ndef step(x: int, *, enabled=True):\n    return x + 1\n']
        for source in variants:
            with self.subTest(source=source):
                self.assertNotEqual(original, compatibility._ast_fingerprint(ast.parse(source).body[0]))

    def test_empty_fields_are_retained_and_debug_locations_do_not_change_structure(self):
        reference = ast.parse('def step(x):\n    return x\n').body[0]
        structure = dict(compatibility._ast_structure(reference)[1])
        self.assertEqual(structure['decorator_list'], [])
        self.assertEqual(structure['type_params'], [])
        self.assertIsNone(structure['returns'])
        changed = copy.deepcopy(reference)
        ast.increment_lineno(changed, 100)
        self.assertEqual(compatibility._ast_fingerprint(reference), compatibility._ast_fingerprint(changed))

    def test_unknown_semantic_dependency_change_still_rejects(self):
        reference = ast.parse('def step(x):\n    return x + 1\n').body[0]
        source = 'def step(x):\n    return x + 2\n'
        with tempfile.TemporaryDirectory(prefix='krea-native-ast-') as folder:
            path = Path(folder) / 'dependency.py'
            path.write_text(source, encoding='utf-8')
            module = ModuleType('owned_ast_dependency_fixture')
            module.__file__ = str(path)
            exec(compile(source, str(path), 'exec', dont_inherit=True), module.__dict__)
            with self.assertRaisesRegex(RuntimeError, 'dependency source is unverified'):
                compatibility._torch_source(module, {'step': compatibility._ast_fingerprint(reference)})


if __name__ == '__main__':
    unittest.main()
