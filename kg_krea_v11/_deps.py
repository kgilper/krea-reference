"""Reuse versioned implementations under ComfyUI and standalone tests."""
import importlib
import importlib.util
import sys
from pathlib import Path


def sibling(name):
    parent = __package__.rsplit('.', 1)[0] if '.' in __package__ else None
    if parent:
        return importlib.import_module(parent + '.' + name)
    key = __package__ + '._' + name
    if key not in sys.modules:
        path = Path(__file__).resolve().parents[1] / name
        spec = importlib.util.spec_from_file_location(key, path / '__init__.py', submodule_search_locations=[str(path)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


v10 = sibling('kg_krea_v10')
sliders = sibling('kg_krea_slider')
v9 = v10.encoder.v9
