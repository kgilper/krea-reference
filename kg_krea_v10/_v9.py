"""Locate the sibling kg_krea_v9 package under any host import layout.

The V10 nodes reuse V9's portable math and host adapters (conditioning,
images, clip_hooks, qwen_tokens) plus its tables. Under ComfyUI the repo
root is a package and kg_krea_v9 is an importable sibling; under the
contract tests kg_krea_v10 is loaded as a top-level package, so this module
falls back to loading kg_krea_v9 by path. Either way `v9` is the loaded
kg_krea_v9 package.
"""

import importlib
import importlib.util
import sys
from pathlib import Path


def _load_v9():
    parent_name = __package__.rsplit(".", 1)[0] if "." in (__package__ or "") else None
    if parent_name:
        try:
            return importlib.import_module(parent_name + ".kg_krea_v9")
        except ImportError:
            pass

    module_name = (__package__ or "kg_krea_v10") + "._kg_krea_v9_dep"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing

    v9_dir = Path(__file__).resolve().parents[1] / "kg_krea_v9"
    spec = importlib.util.spec_from_file_location(
        module_name,
        v9_dir / "__init__.py",
        submodule_search_locations=[str(v9_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


v9 = _load_v9()
