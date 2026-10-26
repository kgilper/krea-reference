"""Compare loaded Python function bodies with admitted source without executing it.

This observes the imported callable's code, rather than assuming a file hash
proves which code was loaded. Dependency/device/model state needs separate host
verification. No upstream implementation is copied or executed by compilation.
"""
import ast
import hashlib
import inspect
from pathlib import Path
import types

_TORCH_CONTEXT_AST = {
    'context_decorator': '967c7c22412aef1d6b4b82c59bb2485ecff8bdafe845adf4edb294141b61f752',
    '_DecoratorContextManager.__call__': '3dced21e5ccb84912cca3b933c2144d2e0e2432f2c68d9e03a0ad28873de3719',
    '_DecoratorContextManager.clone': '1b8edbd9e45faf2702a9a40c4003b10dd58a1ea9992681cef9ef8282a7ca8323',
    '_NoParamDecoratorContextManager.__new__': 'c4a90e1fd69958e3e3d629a76bad5970a2411d90ac1d5528c3a395de27986a6b',
}
_TORCH_GRAD_AST = {
    'no_grad.__init__': 'c1ec080424ff4617104126eebbf0b1333cc16a59c4dafbc408135e634103617e',
    'no_grad.__enter__': '3b78db38d86b55bd581f39994a9ae49a5d617039e4c2b754860421a25837161f',
    'no_grad.__exit__': '2a3cf08e8b1266c73995b8ffa1469a43b3fb34c54e770165b64c73b7dfd70ceb',
}


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
        if node is None or hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest() != expected_hash:
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
