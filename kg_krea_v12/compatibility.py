"""Compare loaded Python function bodies with admitted source without executing it.

This observes the imported callable's code, rather than assuming a file hash
proves which code was loaded. Dependency/device/model state needs separate host
verification. No upstream implementation is copied or executed by compilation.
"""
import inspect
import types


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


def verify_loaded_functions(module, source, names):
    compiled = compile(source, '<v12-admitted-source>', 'exec', dont_inherit=True)
    codes = {}
    def collect(code, prefix=()):
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                path = (*prefix, value.co_name)
                codes['.'.join(path)] = value
                collect(value, path)
    collect(compiled)
    for name in names:
        value = module
        for part in name.split('.'):
            value = getattr(value, part, None)
        if isinstance(value, (classmethod, staticmethod)):
            value = value.__func__
        value = inspect.unwrap(value)
        actual = getattr(value, '__code__', None)
        expected = codes.get(name)
        if (not isinstance(actual, types.CodeType) or expected is None
                or _code_key(actual) != _code_key(expected)):
            raise RuntimeError('V12 loaded function differs from admitted source: ' + name)
