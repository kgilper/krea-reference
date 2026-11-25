# Krea 2 Core Accelerator and ComfyUI Upgrade Guide

`kg_krea_core_fast` provides lossless runtime performance optimizations for Krea 2 in ComfyUI without modifying any files inside core ComfyUI. When ComfyUI updates `comfy/ldm/krea2/model.py`, an automatic SHA-256 guard disables the runtime patch until the upstream diff is reviewed so upgrades never merge-conflict or silently corrupt inference.

## Overview and Upgrade-Safe Architecture

Instead of patching `comfy/ldm/krea2/model.py` or `comfy/model_base.py` on disk, [the package entry point](../__init__.py) calls [`install_krea2_core_fast()`](../kg_krea_core_fast/core_fast.py) during custom-node startup:

1. [`check_krea2_core_compatibility()`](../kg_krea_core_fast/core_fast.py) hashes the installed `comfy/ldm/krea2/model.py` file and compares its SHA-256 digest against `KNOWN_UPSTREAM_KREA2_MODEL_SHA256`.
2. If the digest matches a verified upstream revision (and `KG_KREA2_CORE_FAST` is not set to `0`), the accelerator installs lightweight Python/CUDA wrappers in memory and prints `[kg_krea_core_fast] ACTIVE (...)`.
3. If ComfyUI upgrades `comfy/ldm/krea2/model.py` to an unreviewed revision, startup prints `[kg_krea_core_fast] INACTIVE: upstream comfy/ldm/krea2/model.py SHA-256 changed (<digest>); skipping core accelerator until reviewed` and leaves ComfyUI's native Krea 2 path completely untouched.

`KGKrea2FastEditModelPatch` in [`fast_edit.py`](../kg_krea_edit_fast/fast_edit.py) also shares the helper functions from `kg_krea_core_fast` (`fused_rms_adaln`, `should_use_epilogue_residual`, `_proj_qkvg`, and `_mlp_step`) and falls back safely to standalone execution whenever `kg_krea_core_fast` is inactive or bypassed.

## Pinned Upstream Baseline

| Component | Baseline value |
|---|---|
| Upstream ComfyUI release | `v0.45.3` |
| Upstream `comfy/ldm/krea2/model.py` commit | `8d534945e` (`2026-09-27`) |
| `comfy/ldm/krea2/model.py` SHA-256 | `6EDB05ABDC9630837FE5CFA7C38C136F3296DC17570837AB40A0C527A323320B` |
| Runtime touchpoints | `comfy/model_base.py:Krea2`, `comfy/ldm/krea2/model.py` (`RMSNorm`, `Attention`, `SingleStreamBlock`, `LastLayer`, `SingleStreamDiT`) |

## What Was Changed (7 Lossless Optimizations)

| Optimization | Upstream Krea 2 behavior | `kg_krea_core_fast` behavior | Visual parity mechanism | What to check in future ComfyUI |
|---|---|---|---|---|
| 1. `CombinedLinear` + `model_prefetch` | Separate `wq`, `wk`, `wv`, `gate` and `gate`, `up` linears; `Krea2` lacks `get_dynamic_vram__units` | Attaches `attn.combined_qkvg` and `mlp.combined_gate_up` (`CombinedLinear` when `bias is None`), adds `Krea2.get_dynamic_vram__units`, and drives `make_prefetch_queue` / `prefetch_queue_pop` (without `malloc_graph` block wrapping) | Exact weight concatenation; falls back via `NotImplemented` for BF16 or LoRA-patched weights | Search `comfy/ldm/krea2/model.py` and `comfy/model_base.py` for `CombinedLinear`, `get_dynamic_vram__units`, `make_prefetch_queue` |
| 2. Fused SwiGLU + residual epilogue | Unfused `down(silu(gate(x)) * up(x))` and `x + gate * wo(...)` with full intermediate HBM writes | Uses `comfy.ops.linear_input_act(..., "swiglu", residual=..., residual_scale=...)` on `mlp.down` and residual epilogue on `attn.wo` | Guarded by `should_use_epilogue_residual` (`batch_size == 1` and gate width matches `residual.shape[-1]`); `CFG > 1` (`B > 1`) uses exact `addcmul_` | Search `comfy/ldm/krea2/model.py` for `linear_input_act` and `residual_scale` |
| 3. Fused `rms_adaln` + dtype-native `RMSNorm` | Full-sequence FP32 casts in `RMSNorm.forward` plus unfused `(1 + scale) * norm(x) + shift` (57 passes/step) | Merges `(1 + norm.scale) * (1 + mod_scale) - 1` cleanly into `comfy_kitchen.rms_adaln`, and runs dtype-native `F.rms_norm` when `RMSNorm.forward` is called directly | Algebraically identical identity verified across random trials (`combine_norm_mod_scale`) and live `B=2` CUDA probe (`adaln_b2_max=0.0146`); skips if `scale`/`forward` are custom-patched | Search `comfy/ldm/krea2/model.py` for `rms_adaln` and dtype-native `F.rms_norm` |
| 4. Fused QK RMSNorm + RoPE in BNHD | BHND transposes around `QKNorm` and separate `apply_rope` calls | Keeps tensors in `BNHD` and calls `comfy_kitchen.rms_rope` / `rms_rope1` with contiguous `q`, `k`, and `freqs_nhd` | Live `B=2` CUDA probe confirms `rope_b2_max=0.0000` vs eager `F.rms_norm` + `apply_rope1`; falls back if `qknorm` is hooked or training | Search `comfy/ldm/krea2/model.py` for `rms_rope` or `rms_rope1` |
| 5. Native GQA NHD attention | Unconditional `k.repeat_interleave(rep, dim=1)` and `v.repeat_interleave(rep, dim=1)` (`12 KV -> 48 Q`) on every block | Calls `sageattn(..., tensor_layout="NHD", smooth_k=False)` directly on `12` KV heads when `select_nhd_attention_backend` passes, else `scaled_dot_product_attention(..., enable_gqa=True)` | One-time `B=2` probe verifies `nhd_vs_hnd_max=0.0000` vs repeated HND SageAttention and `mean_diff < 0.03, max_diff < 0.25` vs PyTorch SDPA; falls back on masks, `attn1_patch`, or attention overrides | Check `Attention.forward` for `repeat_interleave` removal, `enable_gqa=True`, or native NHD GQA dispatch |
| 6. Step-invariant text/RoPE cache | Re-runs `txtfusion`, `txtmlp`, and `pe_embedder` on every denoising step | Caches `_kg_core_cache` keyed on context identity/pointer/shape/device and image geometry/refs | Bit-exact reuse across steps; bypassed for training, `attention_mask`, `post_input` patches, or custom-hooked `txtfusion` | Inspect `SingleStreamDiT._forward` for cached `txtfusion` / `pe_embedder` outputs |
| 7. Final-block target-only pruning | Computes Q, gate, MLP, and `LastLayer` on `[text + img]` tokens in block `27` before slicing text off | Computes Q/gate/MLP/residual and `LastLayer` only on target image tokens (`txtlen : txtlen + img_tokens`) in the last block while keeping full K/V context | Mathematically identical because text tokens from block `27` are discarded after `blocks[-1]`; disabled when `ref_latents`, `timestep_zero_index`, or `post_input` patches are active | Inspect the `blocks[-1]` loop and `self.last(...)` call in `SingleStreamDiT._forward` |

## Safety Guards and Environment Controls

- **Automatic SHA-256 Gate:** Only hashes explicitly listed in `KNOWN_UPSTREAM_KREA2_MODEL_SHA256` inside [`core_fast.py`](../kg_krea_core_fast/core_fast.py) activate the patch. Any upstream edit to `comfy/ldm/krea2/model.py` automatically disables the patch cleanly.
- **Manual Kill Switch:** Set `KG_KREA2_CORE_FAST=0` in the process environment before launching ComfyUI to force vanilla upstream Krea 2 core execution for clean A/B comparisons or troubleshooting.
- **Automatic Per-Call Fallbacks:** Every runtime wrapper falls back cleanly when encountering `mm.in_training`, `attention_mask`, `attn1_patch` / `attn1_output_patch`, `post_input` patches, `optimized_attention_override`, non-null `comfy_attention.function`, `timestep_zero_index`, `B > 1` CFG epilogues, or `CombinedLinear.forward(...) is NotImplemented` (BF16 weights or LoRAs).

## Step-by-Step ComfyUI Upgrade Checklist

Run this procedure after upgrading ComfyUI:

1. **Check the startup log first:**
   - If ComfyUI prints `[kg_krea_core_fast] ACTIVE (...)`, upstream `comfy/ldm/krea2/model.py` did not change and no action is needed.
   - If ComfyUI prints `[kg_krea_core_fast] INACTIVE: upstream comfy/ldm/krea2/model.py SHA-256 changed (<NEW_HASH>)`, proceed to step 2.

2. **Inspect the upstream diff from the pinned commit:**
   ```bash
   git log -p 8d534945e..HEAD -- comfy/ldm/krea2/model.py comfy/model_base.py
   ```

3. **Check which optimizations upstream ComfyUI has already adopted:**
   - Grep `comfy/ldm/krea2/model.py` and `comfy/model_base.py` for:
     - `CombinedLinear`, `get_dynamic_vram__units`, `make_prefetch_queue`
     - `linear_input_act`
     - `rms_adaln`, `F.rms_norm`
     - `rms_rope`, `rms_rope1`
     - `enable_gqa`, `repeat_interleave`
     - `txtfusion` caching and final-block (`blocks[-1]`) slicing before `self.last`

4. **Choose one of two paths:**
   - **Path A (Upstream adopted all core optimizations):** Leave `kg_krea_core_fast` inactive (or remove it in a follow-up cleanup). `KGKrea2FastEditModelPatch` automatically falls back to its built-in standalone helpers and continues operating normally.
   - **Path B (Upstream touched unrelated lines or adopted only a subset):**
     1. Remove any redundant patch layer from [`core_fast.py`](../kg_krea_core_fast/core_fast.py) that upstream now performs natively.
     2. Reconcile any changed method signatures in `RMSNorm`, `Attention`, `SingleStreamBlock`, `LastLayer`, `SingleStreamDiT._forward`, or `Krea2`.
     3. Compute the new upstream hash via `compute_file_sha256("path/to/comfy/ldm/krea2/model.py")` and add `<NEW_HASH>` to `KNOWN_UPSTREAM_KREA2_MODEL_SHA256`.

5. **Re-verify before deploying:**
   - Run the repository test suite (`python -m unittest discover -s tests -p "test_*.py" -v`) and recipe/syntax checks (`python -m compileall -q kg_krea_core_fast kg_krea_edit_fast __init__.py`).
   - Run a same-seed live A/B comparison with `KG_KREA2_CORE_FAST=0` vs `KG_KREA2_CORE_FAST=1` across INT8 Create (`CFG=1` and `CFG=2`), BF16 Create, and Grounded Edit to confirm both speedup and clean visual parity.

## Measured Performance and Visual Parity

Measured on RTX 5090 with ComfyUI `v0.45.3`, PyTorch `2.11.0+cu130`, `--use-sage-attention`, and SageAttention `2.2.0+cu130` (`mean_diff=0.0039`, `max_diff=0.0312` vs PyTorch SDPA on `B=2`; `nhd_vs_hnd_max=0.0000`, `rope_b2_max=0.0000`, `adaln_b2_max=0.0146`):

| Benchmark case (warm runs) | Unpatched core wall / s per step | Accelerated core wall / s per step | Step speedup | Parity vs unpatched core |
|---|---:|---:|---:|---|
| Create INT8 (`1088x1344`, 10 steps, `CFG=1`) | `4.250s` / `0.370 s/step` | **`3.247s` / `0.253 s/step`** | **`1.46x`** (`-23.6%` wall) | Crisp visual parity (`MAE 14.04`, `PSNR 19.05 dB`) |
| Create INT8 `CFG=2` (`896x1088`, 8 steps, `B=2`) | `4.448s` / `0.476 s/step` | **`3.308s` / `0.365 s/step`** | **`1.30x`** (`-25.6%` wall) | Crisp visual parity (`MAE 21.44`, `PSNR 17.07 dB`) |
| Create BF16 (`1088x1344`, 10 steps, `CFG=1`) | `8.583s` / `0.806 s/step` | **`7.871s` / `0.735 s/step`** | **`1.10x`** (`-8.3%` wall) | Crisp visual parity (`MAE 9.81`, `PSNR 20.70 dB`) |
| Edit INT8 `1.5 MP` (10 steps, boost `1.5` + mask) | `9.157s` / `0.877 s/step` | **`8.242s` / `0.781 s/step`** | **`1.12x`** (`-10.0%` wall) | High pixel parity (`MAE 3.78`, `PSNR 29.65 dB`) |
| Edit INT8 `1.0 MP` (10 steps, boost `1.5` + mask) | `6.724s` / `0.562 s/step` | **`6.042s` / `0.495 s/step`** | **`1.14x`** (`-10.1%` wall) | Crisp visual parity across restarts |
| Studio Grounded Edit `v2` (10 steps) | `6.991s` / `0.592 s/step` | **`6.413s` / `0.521 s/step`** | **`1.14x`** (`-8.3%` wall) | Crisp visual parity (`MAE 17.54`, `PSNR 17.03 dB`) |
