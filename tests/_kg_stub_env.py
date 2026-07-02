"""Shared stubs for testing the Krea reference-stack modules without ComfyUI.

Provides a pure-Python FakeTensor with just enough tensor semantics
(broadcasting multiply/add/subtract, view/reshape, clone) to exercise the
conditioning delta and layer-composition math numerically, plus a loader that
imports a node module or package against stubbed node_helpers / comfy / torch
modules.
"""

import importlib.util
import math
import sys
import types
from pathlib import Path


def _infer_shape(data):
    shape = []
    probe = data
    while isinstance(probe, (list, tuple)):
        shape.append(len(probe))
        probe = probe[0]
    return tuple(shape)


def _flatten(data, out):
    if isinstance(data, (list, tuple)):
        for item in data:
            _flatten(item, out)
    else:
        out.append(float(data))


def _strides(shape):
    strides = [0] * len(shape)
    acc = 1
    for i in range(len(shape) - 1, -1, -1):
        strides[i] = acc
        acc *= shape[i]
    return strides


class FakeTensor:
    def __init__(self, data=None, shape=None, flat=None, dtype="float32", device="cpu"):
        if flat is not None:
            self.shape = tuple(shape)
            self.flat = [float(v) for v in flat]
        else:
            self.shape = _infer_shape(data)
            self.flat = []
            _flatten(data, self.flat)
        self.dtype = dtype
        self.device = device
        expected = math.prod(self.shape) if self.shape else len(self.flat)
        if self.shape and expected != len(self.flat):
            raise ValueError("shape {} does not match {} values".format(self.shape, len(self.flat)))

    # -- metadata ----------------------------------------------------------
    def dim(self):
        return len(self.shape)

    def numel(self):
        return len(self.flat)

    # -- copies and reshapes ----------------------------------------------
    def clone(self):
        return FakeTensor(shape=self.shape, flat=self.flat, dtype=self.dtype, device=self.device)

    def float(self):
        return FakeTensor(shape=self.shape, flat=self.flat, dtype="float32", device=self.device)

    def to(self, dtype):
        return FakeTensor(shape=self.shape, flat=self.flat, dtype=dtype, device=self.device)

    def view(self, *shape):
        if math.prod(shape) != len(self.flat):
            raise ValueError("cannot view {} as {}".format(self.shape, shape))
        return FakeTensor(shape=shape, flat=self.flat, dtype=self.dtype, device=self.device)

    def view_as(self, other):
        return self.view(*other.shape)

    # -- elementwise / broadcast math ---------------------------------------
    def _binary(self, other, op):
        if isinstance(other, (int, float)):
            return FakeTensor(
                shape=self.shape,
                flat=[op(v, float(other)) for v in self.flat],
                dtype=self.dtype,
                device=self.device,
            )
        if not isinstance(other, FakeTensor):
            return NotImplemented

        rank = max(len(self.shape), len(other.shape))
        a_shape = (1,) * (rank - len(self.shape)) + self.shape
        b_shape = (1,) * (rank - len(other.shape)) + other.shape
        out_shape = []
        for a_dim, b_dim in zip(a_shape, b_shape):
            if a_dim != b_dim and 1 not in (a_dim, b_dim):
                raise ValueError("cannot broadcast {} with {}".format(self.shape, other.shape))
            out_shape.append(max(a_dim, b_dim))
        out_shape = tuple(out_shape)

        a_strides = _strides(a_shape)
        b_strides = _strides(b_shape)
        out_strides = _strides(out_shape)
        total = math.prod(out_shape) if out_shape else 1

        out_flat = [0.0] * total
        for flat_index in range(total):
            a_index = 0
            b_index = 0
            remainder = flat_index
            for d in range(rank):
                coord = remainder // out_strides[d]
                remainder = remainder % out_strides[d]
                a_index += (coord if a_shape[d] != 1 else 0) * a_strides[d]
                b_index += (coord if b_shape[d] != 1 else 0) * b_strides[d]
            out_flat[flat_index] = op(self.flat[a_index], other.flat[b_index])
        return FakeTensor(shape=out_shape, flat=out_flat, dtype=self.dtype, device=self.device)

    def __add__(self, other):
        return self._binary(other, lambda a, b: a + b)

    def __radd__(self, other):
        return self._binary(other, lambda a, b: b + a)

    def __sub__(self, other):
        return self._binary(other, lambda a, b: a - b)

    def __mul__(self, other):
        return self._binary(other, lambda a, b: a * b)

    def __rmul__(self, other):
        return self._binary(other, lambda a, b: b * a)

    # -- inspection ----------------------------------------------------------
    def tolist(self):
        def build(shape, flat, offset):
            if not shape:
                return flat[offset]
            step = math.prod(shape[1:]) if len(shape) > 1 else 1
            return [build(shape[1:], flat, offset + i * step) for i in range(shape[0])]

        return build(self.shape, self.flat, 0)

    def __eq__(self, other):
        return (
            isinstance(other, FakeTensor)
            and self.shape == other.shape
            and self.flat == other.flat
        )

    def __repr__(self):
        return "FakeTensor(shape={}, flat={})".format(self.shape, self.flat)


def make_torch_stub():
    torch_stub = types.ModuleType("torch")
    torch_stub.FakeTensor = FakeTensor
    torch_stub.is_tensor = lambda value: isinstance(value, FakeTensor)

    def _tensor(data, dtype=None, device=None):
        tensor = FakeTensor(data)
        if dtype is not None:
            tensor.dtype = dtype
        if device is not None:
            tensor.device = device
        return tensor

    torch_stub.tensor = _tensor
    torch_stub.nn = types.SimpleNamespace(functional=types.SimpleNamespace())
    return torch_stub


def load_module(target, module_name):
    """Import a node module or package from the repo root with ComfyUI stubs.

    `target` is a path relative to the repo root: either a single-file module
    ("foo.py") or a package directory ("foo"). Each call loads a fresh copy
    under `module_name`, so test classes stay isolated from each other.
    """
    root = Path(__file__).resolve().parents[1]

    node_helpers = types.ModuleType("node_helpers")
    node_helpers.conditioning_set_values = lambda conditioning, values, append=False: conditioning
    sys.modules.setdefault("node_helpers", node_helpers)

    comfy = types.ModuleType("comfy")
    comfy_utils = types.ModuleType("comfy.utils")
    comfy_utils.common_upscale = lambda samples, width, height, method, crop: samples
    comfy.utils = comfy_utils
    sys.modules.setdefault("comfy", comfy)
    sys.modules.setdefault("comfy.utils", comfy_utils)

    torch_stub = make_torch_stub()
    previous_torch = sys.modules.get("torch")
    sys.modules["torch"] = torch_stub
    try:
        target_path = root / target
        if target_path.is_dir():
            spec = importlib.util.spec_from_file_location(
                module_name,
                target_path / "__init__.py",
                submodule_search_locations=[str(target_path)],
            )
        else:
            spec = importlib.util.spec_from_file_location(module_name, target_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        if previous_torch is not None:
            sys.modules["torch"] = previous_torch
        else:
            sys.modules.pop("torch", None)
    return module, torch_stub
