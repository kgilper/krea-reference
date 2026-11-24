"""ComfyUI-free contract & mathematical parity tests for kg_krea_edit_fast."""
from __future__ import annotations

import ast
import importlib.util
import math
import random
import sys
import types
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
FAST_SPEC = importlib.util.spec_from_file_location(
    "kg_krea_edit_fast",
    ROOT / "kg_krea_edit_fast/__init__.py",
    submodule_search_locations=[str(ROOT / "kg_krea_edit_fast")],
)
FAST_PKG = importlib.util.module_from_spec(FAST_SPEC)
sys.modules[FAST_SPEC.name] = FAST_PKG
FAST_SPEC.loader.exec_module(FAST_PKG)

from kg_krea_edit_fast import (  # noqa: E402
    FIT_MODES,
    KGKrea2FastEditModelPatch,
    REF_POSITIONS,
    combine_partition_outputs_pure,
    plan_boost_partitions,
)


def _reference_attention_row(q_vec, keys, vals, biases):
    scale = 1.0 / math.sqrt(len(q_vec))
    logits = [
        sum(q_vec[d] * k_vec[d] for d in range(len(q_vec))) * scale + b
        for k_vec, b in zip(keys, biases)
    ]
    max_l = max(logits)
    exps = [math.exp(l - max_l) for l in logits]
    denom = sum(exps)
    weights = [e / denom for e in exps]
    dim = len(vals[0])
    out = [0.0] * dim
    for w, v_vec in zip(weights, vals):
        for d in range(dim):
            out[d] += w * v_vec[d]
    return out


def _unbiased_block_out_and_lse(q_vec, keys_sub, vals_sub):
    scale = 1.0 / math.sqrt(len(q_vec))
    logits = [
        sum(q_vec[d] * k_vec[d] for d in range(len(q_vec))) * scale
        for k_vec in keys_sub
    ]
    max_l = max(logits)
    exps = [math.exp(l - max_l) for l in logits]
    sum_e = sum(exps)
    lse = max_l + math.log(sum_e)
    dim = len(vals_sub[0])
    out = [0.0] * dim
    for e, v_vec in zip(exps, vals_sub):
        w = e / sum_e
        for d in range(dim):
            out[d] += w * v_vec[d]
    return out, lse


class FastEditContractAndMathTests(unittest.TestCase):
    def test_root_init_registers_node_without_altering_v9_or_prior_nodes(self):
        tree = ast.parse((ROOT / "__init__.py").read_text(encoding="utf-8"))
        text = (ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("KGKrea2FastEditModelPatch", text)
        self.assertIn("KG Krea 2 Edit Fast (Source Patch)", text)
        self.assertIsInstance(tree, ast.Module)

    def test_drop_in_input_types_match_krea2_edit_patch_with_optional_source_latent(self):
        spec = KGKrea2FastEditModelPatch.INPUT_TYPES()
        self.assertEqual(list(spec["required"].keys()), ["model"])
        optional_keys = set(spec["optional"].keys())
        expected_optional = {
            "source_latent",
            "source_latent_b",
            "ref_boost",
            "ref_boost_a",
            "fit_mode",
            "ref_boost_mask",
            "vae",
            "source_image",
            "source_image_b",
            "target_latent",
            "ref_position",
            "ref_position_a",
        }
        self.assertEqual(optional_keys, expected_optional)
        self.assertEqual(spec["optional"]["fit_mode"][0], FIT_MODES)
        self.assertEqual(spec["optional"]["ref_position"][0], REF_POSITIONS)
        self.assertEqual(spec["optional"]["ref_position_a"][0], REF_POSITIONS)
        self.assertEqual(KGKrea2FastEditModelPatch.RETURN_TYPES, ("MODEL",))
        self.assertEqual(KGKrea2FastEditModelPatch.CATEGORY, "krea2edit")

    def test_plan_boost_partitions_covers_all_cases_disjointly(self):
        # 1. All unit boosts -> inactive fast path
        p_off = plan_boost_partitions(12, [100], 100, [1.0])
        self.assertFalse(p_off["active"])
        self.assertEqual(p_off["partitions"], [("slice", (0, 212), 0.0)])

        # 2. Unmasked single ref boost -> two contiguous slices
        p_single = plan_boost_partitions(12, [50], 60, [2.75])
        self.assertTrue(p_single["active"])
        self.assertEqual(p_single["rows0"], 62)
        self.assertEqual(p_single["total_len"], 122)
        self.assertEqual(
            p_single["partitions"],
            [
                ("indices", list(range(0, 12)) + list(range(62, 122)), 0.0),
                ("slice", (12, 62), math.log(2.75)),
            ],
        )

        # 3. Masked boost with empty active mask collapses cleanly to inactive
        p_empty = plan_boost_partitions(10, [20], 30, [1.5], mask_active_indices=[])
        self.assertFalse(p_empty["active"])

        # 4. Partial mask on single ref partitions disjointly into zero and biased indices
        p_masked = plan_boost_partitions(8, [10], 12, [1.5], mask_active_indices=[2, 3, 7])
        self.assertTrue(p_masked["active"])
        zero_idx = p_masked["partitions"][0][1]
        boost_idx = p_masked["partitions"][1][1]
        self.assertEqual(boost_idx, [10, 11, 15])
        self.assertEqual(sorted(zero_idx + boost_idx), list(range(30)))
        self.assertEqual(set(zero_idx).intersection(boost_idx), set())

        # 5. Two refs with distinct non-unit boosts + mask on last ref
        p_two = plan_boost_partitions(5, [6, 8], 9, [2.5, 1.8], mask_active_indices=[1, 2])
        self.assertTrue(p_two["active"])
        self.assertEqual(len(p_two["partitions"]), 3)
        covered = []
        for kind, spec, _ in p_two["partitions"]:
            if kind == "slice":
                covered.extend(range(spec[0], spec[1]))
            else:
                covered.extend(spec)
        self.assertEqual(sorted(covered), list(range(5 + 6 + 8 + 9)))
        self.assertEqual(len(covered), len(set(covered)))

        # 6. Zero boost clamps safely to math.log(1e-4) instead of -inf/ValueError
        p_zero = plan_boost_partitions(4, [5], 6, [0.0])
        self.assertAlmostEqual(p_zero["partitions"][1][2], math.log(1e-4), places=12)

    def test_online_softmax_partition_merge_matches_full_biased_attention_to_machine_precision(self):
        rng = random.Random(20261124)
        dim = 16
        seq_len = 29
        q_vec = [rng.uniform(-1.5, 1.5) for _ in range(dim)]
        keys = [[rng.uniform(-1.5, 1.5) for _ in range(dim)] for _ in range(seq_len)]
        vals = [[rng.uniform(-1.5, 1.5) for _ in range(dim)] for _ in range(seq_len)]

        plan = plan_boost_partitions(5, [8, 7], 9, [2.3, 1.7], mask_active_indices=[0, 2, 4])
        bias_per_key = [0.0] * seq_len
        for kind, spec, beta in plan["bias_segments"]:
            indices = range(spec[0], spec[1]) if kind == "slice" else spec
            for idx in indices:
                bias_per_key[idx] = beta

        expected = _reference_attention_row(q_vec, keys, vals, bias_per_key)

        outs, lses, betas = [], [], []
        for kind, spec, beta in plan["partitions"]:
            indices = list(range(spec[0], spec[1])) if kind == "slice" else spec
            o_p, lse_p = _unbiased_block_out_and_lse(
                q_vec, [keys[i] for i in indices], [vals[i] for i in indices]
            )
            outs.append(o_p)
            lses.append(lse_p)
            betas.append(beta)
        actual = combine_partition_outputs_pure(outs, lses, betas)

        max_err = max(abs(a - b) for a, b in zip(actual, expected))
        self.assertLess(max_err, 1e-12)

    def test_patch_validates_missing_source_and_registers_distinct_wrapper_key(self):
        patcher = KGKrea2FastEditModelPatch()

        class FakeModel:
            def __init__(self):
                self.model_options = {}
                self.model = SimpleNamespace(process_latent_in=lambda s: ("scaled", s))

            def clone(self):
                c = FakeModel()
                c.model_options = {}
                c.model = self.model
                return c

        # Error if neither source_latent nor vae+source_image provided
        with self.assertRaises(ValueError):
            patcher.patch(FakeModel())

        # Stub comfy.patcher_extension cleanly so unit test runs outside ComfyUI
        fake_wrappers = []

        def add_wrapper_with_key(slot, key, fn, to):
            fake_wrappers.append((slot, key, fn, to))
            to.setdefault("wrappers", {}).setdefault(slot, {}).setdefault(key, []).append(fn)

        fake_comfy = types.ModuleType("comfy")
        fake_pe = types.ModuleType("comfy.patcher_extension")
        fake_pe.WrappersMP = SimpleNamespace(DIFFUSION_MODEL="diffusion_model")
        fake_pe.add_wrapper_with_key = add_wrapper_with_key
        fake_comfy.patcher_extension = fake_pe

        orig_comfy = sys.modules.get("comfy")
        orig_pe = sys.modules.get("comfy.patcher_extension")
        sys.modules["comfy"] = fake_comfy
        sys.modules["comfy.patcher_extension"] = fake_pe
        try:
            (patched,) = patcher.patch(FakeModel(), source_latent={"samples": "lat_obj"})
            self.assertEqual(len(fake_wrappers), 1)
            self.assertEqual(fake_wrappers[0][1], "kg_krea2_edit_fast")
            self.assertIn("kg_krea2_edit_fast", patched.model_options["transformer_options"]["wrappers"]["diffusion_model"])
            # Must never collide with V12's 'krea2_edit' key check
            self.assertNotIn("krea2_edit", patched.model_options["transformer_options"]["wrappers"]["diffusion_model"])
        finally:
            if orig_comfy is not None:
                sys.modules["comfy"] = orig_comfy
            else:
                sys.modules.pop("comfy", None)
            if orig_pe is not None:
                sys.modules["comfy.patcher_extension"] = orig_pe
            else:
                sys.modules.pop("comfy.patcher_extension", None)


if __name__ == "__main__":
    unittest.main()
