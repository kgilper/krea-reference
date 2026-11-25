"""ComfyUI-free contract and mathematical identity tests for kg_krea_core_fast."""
from __future__ import annotations

import importlib.util
import io
import os
import random
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
CORE_SPEC = importlib.util.spec_from_file_location(
    "kg_krea_core_fast",
    ROOT / "kg_krea_core_fast/__init__.py",
    submodule_search_locations=[str(ROOT / "kg_krea_core_fast")],
)
CORE_PKG = importlib.util.module_from_spec(CORE_SPEC)
sys.modules[CORE_SPEC.name] = CORE_PKG
CORE_SPEC.loader.exec_module(CORE_PKG)

from kg_krea_core_fast import (  # noqa: E402
    KNOWN_UPSTREAM_KREA2_MODEL_SHA256,
    combine_norm_mod_scale,
    should_use_epilogue_residual,
)


class KreaCoreFastUnitTests(unittest.TestCase):
    def test_upstream_sha256_guard_skips_when_krea2_model_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_model = Path(tmp) / "model.py"
            fake_model.write_text("# modified upstream comfyui krea2 model\n", encoding="utf-8")
            fake_mod = types.ModuleType("comfy.ldm.krea2.model")
            fake_mod.__file__ = str(fake_model)

            ok, msg = CORE_PKG.core_fast.check_krea2_core_compatibility(fake_mod)
            self.assertFalse(ok)
            self.assertIn("SHA-256 changed", msg)
            digest = CORE_PKG.core_fast.compute_file_sha256(fake_model)
            self.assertNotIn(digest, KNOWN_UPSTREAM_KREA2_MODEL_SHA256)

    def test_env_disable_turns_off_core_accelerator(self):
        fake_mod = types.ModuleType("comfy.ldm.krea2.model")
        orig = os.environ.get("KG_KREA2_CORE_FAST")
        os.environ["KG_KREA2_CORE_FAST"] = "0"
        try:
            ok, msg = CORE_PKG.core_fast.check_krea2_core_compatibility(fake_mod)
            self.assertFalse(ok)
            self.assertIn("KG_KREA2_CORE_FAST=0", msg)
        finally:
            if orig is None:
                os.environ.pop("KG_KREA2_CORE_FAST", None)
            else:
                os.environ["KG_KREA2_CORE_FAST"] = orig

    def test_combined_norm_mod_scale_matches_unfused_algebra_exactly(self):
        rng = random.Random(20261124)
        for _ in range(50):
            r_x = rng.uniform(-3.0, 3.0)
            norm_scale = rng.uniform(-0.5, 1.5)
            mod_scale = rng.uniform(-0.8, 0.8)
            mod_shift = rng.uniform(-2.0, 2.0)

            unfused = (1.0 + mod_scale) * (r_x * (1.0 + norm_scale)) + mod_shift
            eff = combine_norm_mod_scale(norm_scale, mod_scale)
            fused = r_x * (1.0 + eff) + mod_shift
            self.assertAlmostEqual(fused, unfused, places=12)

    def test_epilogue_residual_guard_rejects_batch_gt_1_or_mismatched_gate(self):
        res_b1 = SimpleNamespace(shape=(1, 100, 6144))
        res_b2 = SimpleNamespace(shape=(2, 100, 6144))
        gate_vec = SimpleNamespace(numel=lambda: 6144)
        gate_batched = SimpleNamespace(numel=lambda: 2 * 6144)

        self.assertTrue(should_use_epilogue_residual(1, res_b1, gate_vec))
        self.assertFalse(should_use_epilogue_residual(2, res_b2, gate_vec))
        self.assertFalse(should_use_epilogue_residual(2, res_b2, gate_batched))
        self.assertFalse(should_use_epilogue_residual(1, None, gate_vec))
        self.assertFalse(should_use_epilogue_residual(1, res_b1, None))

    def test_root_init_registers_core_fast_non_fatally(self):
        text = (ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("install_krea2_core_fast", text)


if __name__ == "__main__":
    unittest.main()
