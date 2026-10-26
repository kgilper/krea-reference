"""Compare loaded Python function bodies with admitted source without executing it.

This observes the imported callable's code, rather than assuming a file hash
proves which code was loaded. Dependency/device/model state needs separate host
verification. No upstream implementation is copied or executed by compilation.
"""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import types

_TORCH_CONTEXT_AST = {
    'context_decorator': 'ab88233fefe874378a063c5ba94e83e3c367c3d0f3a10b2285c36d20ee26b517',
    '_DecoratorContextManager.__call__': 'fd1b4f0e58ad7340d39e20dd2ffc37c887588baf07ae7b6f5ab4ac47b191d666',
    '_DecoratorContextManager.clone': 'df22dd330c061c2e3abb49ba6f554bc082f35cde53bc098d268d73f35a8c234a',
    '_NoParamDecoratorContextManager.__new__': '65c0570159bd596a54a15b9797c4465a2e093a3f0eb5f5bd80c3d9ba87f1023b',
}
_TORCH_GRAD_AST = {
    'no_grad.__init__': '895fe28d68080b651f4918f4540adf6c15a9a98c28f39724468cb57749333c0b',
    'no_grad.__enter__': '6da10b3038d3031ca8b09fa5b72844b9cd271b9174e13731b3fb8b65779e7122',
    'no_grad.__exit__': 'cdb682833c9504854cd368e7fc3a29d7c46164136d4af9c84492aed1bc87846d',
}


def _ast_structure(value):
    """Keep semantic fields explicit; avoid version-dependent ast.dump formatting."""
    if isinstance(value, ast.AST):
        fields = dict(ast.iter_fields(value))
        if isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Python3.11 lacks this field. It means no generic parameters, just
            # like an empty list in3.12+. Nonempty parameters remain binding.
            fields.setdefault('type_params', getattr(value, 'type_params', []))
        return [type(value).__name__, [[name, _ast_structure(fields[name])] for name in sorted(fields)]]
    if isinstance(value, list):
        return [_ast_structure(item) for item in value]
    if isinstance(value, bytes):
        return ['bytes', value.hex()]
    if isinstance(value, complex):
        return ['complex', value.real, value.imag]
    if value is Ellipsis:
        return ['ellipsis']
    return value


def _ast_fingerprint(node):
    data = json.dumps(_ast_structure(node), ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return hashlib.sha256(b'v12-ast-fields-v1\0' + data).hexdigest()


def _constant(value):
    if isinstance(value, types.CodeType):
        return ('code', _code_key(value))
    if isinstance(value, tuple):
        return tuple(_constant(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_constant(item) for item in value)
    return value


def _code_key(code):
    # Filename/line tables are debugging coordinates. Preserve executable byte
    # code, constants, closure layout and exception regions, including nesting.
    return (code.co_argcount, code.co_posonlyargcount, code.co_kwonlyargcount,
            code.co_nlocals, code.co_stacksize, code.co_flags, code.co_code,
            tuple(_constant(item) for item in code.co_consts), code.co_names,
            code.co_varnames, code.co_freevars, code.co_cellvars,
            getattr(code, 'co_exceptiontable', b''))


def _source_maps(source):
    compiled = compile(source, '<v12-admitted-source>', 'exec', dont_inherit=True)
    codes, definitions = {}, {}
    def collect(code, prefix=()):
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                path = (*prefix, value.co_name)
                codes['.'.join(path)] = value
                collect(value, path)
    collect(compiled)
    def collect_definitions(node, prefix=()):
        for item in node.body:
            if isinstance(item, (ast.ClassDef, ast.FunctionDef)):
                path = (*prefix, item.name)
                definitions['.'.join(path)] = item
                collect_definitions(item, path)
    collect_definitions(ast.parse(source))
    return codes, definitions


def _lookup(module, name):
    value = module
    for part in name.split('.'):
        value = getattr(value, part, None)
    return value.__func__ if isinstance(value, (classmethod, staticmethod)) else value


def _plain_code(value, expected, label):
    if (not isinstance(value, types.FunctionType) or hasattr(value, '__wrapped__')
            or expected is None or _code_key(value.__code__) != _code_key(expected)):
        raise RuntimeError('V12 loaded function differs from admitted source: ' + label)


def _torch_source(module, pins):
    source = Path(inspect.getfile(module)).read_bytes()
    codes, definitions = _source_maps(source)
    for name, expected_hash in pins.items():
        node = definitions.get(name)
        if node is None or _ast_fingerprint(node) != expected_hash:
            raise RuntimeError('V12 native no_grad dependency source is unverified: ' + name)
        function = _lookup(module, name)
        _plain_code(function, codes.get(name), name)
        if function.__globals__ is not vars(module):
            raise RuntimeError('V12 native no_grad dependency globals differ: ' + name)
    return codes


def _verified_no_grad_inner(value):
    """Admit one actual native no_grad layer, never arbitrary __wrapped__ links.

    Selected PyTorch function ASTs are pinned to the authoritative v2.9.0 code;
    identical definitions in other releases need no whole-module version guess.
    Both actual wrapper code and its bound context factory/target are verified.
    """
    import torch
    import torch.autograd.grad_mode as grad_mode
    import torch.utils._contextlib as contextlib
    codes = _torch_source(contextlib, _TORCH_CONTEXT_AST)
    _torch_source(grad_mode, _TORCH_GRAD_AST)
    if (torch.no_grad is not grad_mode.no_grad
            or grad_mode.no_grad.clone is not contextlib._DecoratorContextManager.clone
            or grad_mode.no_grad.__call__ is not contextlib._DecoratorContextManager.__call__
            or grad_mode.no_grad.__new__ is not contextlib._NoParamDecoratorContextManager.__new__
            or grad_mode.__dict__.get('torch') is not torch):
        raise RuntimeError('V12 native no_grad context class chain is unverified')
    if (not isinstance(value, types.FunctionType)
            or _code_key(value.__code__) != _code_key(codes['context_decorator.decorate_context'])
            or value.__globals__ is not vars(contextlib)):
        raise RuntimeError('V12 native no_grad wrapper code is unverified')
    closure = dict(zip(value.__code__.co_freevars, value.__closure__ or ()))
    if set(closure) != {'ctx_factory', 'func'}:
        raise RuntimeError('V12 native no_grad wrapper closure is unverified')
    factory, inner = closure['ctx_factory'].cell_contents, closure['func'].cell_contents
    if (not isinstance(factory, types.MethodType)
            or factory.__func__ is not contextlib._DecoratorContextManager.clone
            or type(factory.__self__) is not grad_mode.no_grad
            or set(vars(factory.__self__)) != {'prev'} or type(factory.__self__.prev) is not bool
            or getattr(value, '__wrapped__', None) is not inner
            or not isinstance(inner, types.FunctionType) or hasattr(inner, '__wrapped__')):
        raise RuntimeError('V12 native no_grad factory/target chain is unverified')
    return inner


def verify_loaded_functions(module, source, names, *, allow_no_grad=()):
    codes, definitions = _source_maps(source)
    for name in names:
        value = _lookup(module, name)
        node = definitions.get(name)
        decorators = [ast.unparse(item) for item in getattr(node, 'decorator_list', ())]
        if decorators:
            if name not in allow_no_grad or decorators != ['torch.no_grad()']:
                raise RuntimeError('V12 source decorator chain is unsupported: ' + name)
            value = _verified_no_grad_inner(value)
        _plain_code(value, codes.get(name), name)
