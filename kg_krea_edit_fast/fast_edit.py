"""Performance-optimized, mathematically equivalent forward & attention path for Krea 2 Edit.

Public pure-Python planning and reference fusion helpers are kept free of Torch/ComfyUI
top-level dependencies so contract and numerical unit tests run anywhere. Runtime CUDA
attention backends self-verify against standard PyTorch SDPA before activation.
"""
from __future__ import annotations

import math
from typing import Any

REF_POSITIONS = ["aligned (trained)", "beside (right of target)", "bag of features"]
FIT_MODES = ["fit", "crop (legacy)"]

_BACKEND_CACHE: dict[tuple[Any, ...], str] = {}
_ANNOUNCED_BACKENDS: set[tuple[Any, ...]] = set()


def plan_boost_partitions(
    txtlen: int,
    slens: list[int] | tuple[int, ...],
    tgtlen: int,
    boosts: list[float] | tuple[float, ...],
    mask_active_indices: list[int] | tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Partition `[0, rows0 + tgtlen)` into disjoint key segments sharing identical attention bias.

    Matches `comfyui-krea2edit._ref_attn_bias` semantics identically:
    - `[0, txtlen)` and `[rows0, L)` have zero logit bias (`beta = 0.0`).
    - For reference `i` covering `[off, off + sl)`:
      - if `boosts[i] == 1.0`: `beta = 0.0`.
      - else if `i == len(slens) - 1` and `mask_active_indices is not None`:
        active indices within `[0, sl)` receive `beta = math.log(max(boosts[i], 1e-4))`,
        inactive indices receive `beta = 0.0`.
      - else: the whole block `[off, off + sl)` receives `beta = math.log(max(boosts[i], 1e-4))`.
    Adjacent zero-bias contiguous slices are coalesced, and indices with identical non-zero
    `beta` are grouped so multi-partition Flash/cuDNN attention executes minimal passes.
    """
    nsrc = len(slens)
    if len(boosts) != nsrc:
        raise ValueError(f"boosts length ({len(boosts)}) must match slens length ({nsrc})")

    offs = [int(txtlen)]
    for sl in slens:
        offs.append(offs[-1] + int(sl))
    rows0 = offs[-1]
    total_len = rows0 + int(tgtlen)

    # Track spans in sequential key order; group identical non-zero betas if needed.
    zero_spans: list[tuple[int, int]] = [(0, int(txtlen))]
    biased_groups: dict[float, list[Any]] = {}

    for i, b_raw in enumerate(boosts):
        b = float(b_raw)
        off = offs[i]
        sl = int(slens[i])
        if b == 1.0 or sl == 0:
            zero_spans.append((off, off + sl))
            continue

        beta = math.log(max(b, 1e-4))
        if mask_active_indices is not None and i == nsrc - 1:
            active_set = sorted({int(idx) for idx in mask_active_indices if 0 <= int(idx) < sl})
            if not active_set:
                zero_spans.append((off, off + sl))
                continue
            if len(active_set) == sl:
                biased_groups.setdefault(beta, []).append(("slice", off, off + sl))
                continue

            # Partition [0, sl) into active (biased) indices and inactive (zero-bias) runs.
            biased_groups.setdefault(beta, []).append(("indices", [off + j for j in active_set]))
            active_lookup = set(active_set)
            run_start: int | None = None
            for j in range(sl):
                if j not in active_lookup:
                    if run_start is None:
                        run_start = j
                else:
                    if run_start is not None:
                        zero_spans.append((off + run_start, off + j))
                        run_start = None
            if run_start is not None:
                zero_spans.append((off + run_start, off + sl))
        else:
            biased_groups.setdefault(beta, []).append(("slice", off, off + sl))

    # Drop empty groups or tiny betas equal to 0.0 (e.g., if somehow added).
    if not biased_groups:
        return {
            "active": False,
            "rows0": rows0,
            "total_len": total_len,
            "partitions": [("slice", (0, total_len), 0.0)],
            "bias_segments": [],
        }

    # Target tokens always sit at [rows0, total_len) with zero bias.
    zero_spans.append((rows0, total_len))

    # Coalesce adjacent zero-bias spans into maximal contiguous slices.
    merged_zero_spans: list[tuple[int, int]] = []
    for s, e in sorted(zero_spans):
        if s >= e:
            continue
        if merged_zero_spans and merged_zero_spans[-1][1] == s:
            merged_zero_spans[-1] = (merged_zero_spans[-1][0], e)
        else:
            merged_zero_spans.append((s, e))

    partitions: list[tuple[str, Any, float]] = []
    if len(merged_zero_spans) == 1:
        partitions.append(("slice", merged_zero_spans[0], 0.0))
    else:
        zero_indices: list[int] = []
        for s, e in merged_zero_spans:
            zero_indices.extend(range(s, e))
        partitions.append(("indices", zero_indices, 0.0))

    bias_segments: list[tuple[str, Any, float]] = []
    for beta, specs in biased_groups.items():
        if len(specs) == 1 and specs[0][0] == "slice":
            span = (specs[0][1], specs[0][2])
            if span[0] < span[1]:
                partitions.append(("slice", span, beta))
                bias_segments.append(("slice", span, beta))
        else:
            combined_indices: list[int] = []
            for spec in specs:
                if spec[0] == "slice":
                    combined_indices.extend(range(spec[1], spec[2]))
                else:
                    combined_indices.extend(spec[1])
            combined_indices = sorted(set(combined_indices))
            if combined_indices:
                # Collapse back to slice if strictly contiguous.
                if combined_indices[-1] - combined_indices[0] + 1 == len(combined_indices):
                    span = (combined_indices[0], combined_indices[-1] + 1)
                    partitions.append(("slice", span, beta))
                    bias_segments.append(("slice", span, beta))
                else:
                    partitions.append(("indices", combined_indices, beta))
                    bias_segments.append(("indices", combined_indices, beta))

    return {
        "active": True,
        "rows0": rows0,
        "total_len": total_len,
        "partitions": partitions,
        "bias_segments": bias_segments,
    }


def _logsumexp_pair(a: float, b: float) -> float:
    m = a if a > b else b
    if math.isinf(m) and m < 0:
        return m
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def combine_partition_outputs_pure(
    outs: list[list[float]],
    lses: list[float],
    betas: list[float],
) -> list[float]:
    """Pure-Python exact online-softmax partition merge matching float32/64 biased attention."""
    if len(outs) != len(lses) or len(outs) != len(betas) or not outs:
        raise ValueError("outs, lses, and betas must be non-empty and match in length")
    if len(outs) == 1:
        return list(outs[0])
    scores = [l + b for l, b in zip(lses, betas)]
    max_s = max(scores)
    exps = [math.exp(s - max_s) for s in scores]
    denom = sum(exps)
    weights = [e / denom for e in exps]
    dim = len(outs[0])
    merged = [0.0] * dim
    for w, o in zip(weights, outs):
        for d in range(dim):
            merged[d] += w * o[d]
    return merged


def place_refs_pure(ref_ids_list: list[Any], modes: str | list[str], w_: int) -> list[Any]:
    """Mirror `_place_refs` mode resolution without importing torch during planning checks."""
    if isinstance(modes, str):
        modes = [modes] * len(ref_ids_list)
    if len(modes) != len(ref_ids_list):
        raise ValueError("modes count must match references count")
    return modes


def _normalize_lse_shape(lse, target_len: int):
    if lse.ndim == 4:
        lse = lse.squeeze(-1)
    if lse.shape[-1] > target_len:
        lse = lse[..., :target_len]
    return lse


def _sage_attention_requested() -> bool:
    try:
        import comfy.model_management as mm
        return bool(mm.sage_attention_enabled())
    except Exception:
        return False


try:
    from ..kg_krea_core_fast.core_fast import (  # noqa: E402
        _mlp_step as _core_mlp_step,
        fused_rms_adaln as _core_fused_rms_adaln,
        fused_rms_norm as _fast_rms_norm,
        should_use_epilogue_residual as _core_should_epi,
    )
except ImportError:
    from kg_krea_core_fast.core_fast import (  # noqa: E402
        _mlp_step as _core_mlp_step,
        fused_rms_adaln as _core_fused_rms_adaln,
        fused_rms_norm as _fast_rms_norm,
        should_use_epilogue_residual as _core_should_epi,
    )


def _apply_qknorm(qknorm_mod, q, k):
    if (
        hasattr(qknorm_mod, "qnorm")
        and hasattr(qknorm_mod, "knorm")
        and "forward" not in vars(qknorm_mod)
    ):
        return _fast_rms_norm(qknorm_mod.qnorm, q), _fast_rms_norm(qknorm_mod.knorm, k)
    return qknorm_mod(q, k)


def _fast_proj_qkvg(attn, pre, target_only: bool, rows0: int):
    combined_lin = getattr(attn, "combined_qkvg", None)
    dim = attn.heads * attn.headdim
    kv_dim = attn.kvheads * attn.headdim
    if combined_lin is not None:
        packed = combined_lin.forward(pre)
        if packed is not NotImplemented:
            q_f, k_f, v_f, g_f = packed.split((dim, kv_dim, kv_dim, dim), dim=-1)
            if target_only:
                q_f = q_f[:, rows0:]
                g_f = g_f[:, rows0:]
            return q_f, k_f, v_f, g_f
    if target_only:
        pre_tgt = pre[:, rows0:]
        return attn.wq(pre_tgt), attn.wk(pre), attn.wv(pre), attn.gate(pre_tgt)
    return attn.wq(pre), attn.wk(pre), attn.wv(pre), attn.gate(pre)


def _run_lse_candidate(backend: str, q, k, v, kv_rep: int):
    import torch

    b, h_q, l_q, d = q.shape
    l_k = k.shape[2]
    h_kv = k.shape[1]
    is_sage = backend.startswith("sage_")
    if is_sage:
        from sageattention import sageattn
        use_sage_gqa = backend.endswith("_gqa") or kv_rep == 1
        q_in = q.contiguous()
        if use_sage_gqa:
            k_in = k.contiguous()
            v_in = v.contiguous()
        else:
            k_in = k.repeat_interleave(kv_rep, dim=1).contiguous()
            v_in = v.repeat_interleave(kv_rep, dim=1).contiguous()
        out, lse = sageattn(q_in, k_in, v_in, tensor_layout="HND", is_causal=False, return_lse=True)
        lse = _normalize_lse_shape(lse, l_q)
        if "log2" in backend:
            lse = lse * math.log(2.0)
        return out, lse

    use_gqa_view = backend.endswith("_gqa") and kv_rep > 1
    if use_gqa_view:
        q_in = q.reshape(b * h_kv, kv_rep, l_q, d)
        k_in = k.reshape(b * h_kv, 1, l_k, d).expand(b * h_kv, kv_rep, l_k, d)
        v_in = v.reshape(b * h_kv, 1, l_k, d).expand(b * h_kv, kv_rep, l_k, d)
    else:
        q_in = q
        k_in = k.repeat_interleave(kv_rep, dim=1) if kv_rep > 1 else k
        v_in = v.repeat_interleave(kv_rep, dim=1) if kv_rep > 1 else v

    if backend.startswith("flash_"):
        out, lse, *_ = torch.ops.aten._scaled_dot_product_flash_attention.default(
            q_in, k_in, v_in, 0.0, False, return_debug_mask=False, scale=None
        )
    elif backend.startswith("cudnn_"):
        out, lse, *_ = torch.ops.aten._scaled_dot_product_cudnn_attention.default(
            q_in, k_in, v_in, None, True, 0.0, False, False, scale=None
        )
    else:
        raise ValueError(f"Unknown LSE backend: {backend}")

    if use_gqa_view:
        out = out.reshape(b, h_q, l_q, d)
        lse = _normalize_lse_shape(lse, l_q).reshape(b, h_q, l_q)
    else:
        lse = _normalize_lse_shape(lse, l_q)
    return out, lse


def _combine_partition_outputs_torch(outs: list[Any], lses: list[Any], betas: list[float], out_dtype):
    import torch

    if len(outs) == 1:
        return outs[0]
    if len(outs) == 2:
        w0 = torch.sigmoid((lses[0].float() + betas[0]) - (lses[1].float() + betas[1])).unsqueeze(-1)
        merged = w0 * outs[0].float() + (1.0 - w0) * outs[1].float()
        return merged.to(out_dtype)
    logits = torch.stack([lse.float() + float(beta) for lse, beta in zip(lses, betas)], dim=0)
    weights = torch.softmax(logits, dim=0).unsqueeze(-1)
    stacked = torch.stack([o.float() for o in outs], dim=0)
    return (weights * stacked).sum(dim=0).to(out_dtype)


def _select_lse_backend(device, dtype, headdim: int, kv_rep: int) -> str:
    """Self-verify CUDA Flash/cuDNN/Sage LSE kernels against SDPA; cache result per device/dtype/dim."""
    import torch
    import torch.nn.functional as F

    sage_enabled = _sage_attention_requested()
    cache_key = (
        device.type,
        getattr(device, "index", None),
        str(dtype),
        int(headdim),
        int(kv_rep),
        sage_enabled,
    )
    if cache_key in _BACKEND_CACHE:
        return _BACKEND_CACHE[cache_key]

    chosen = "split_q_aligned_1d"
    probe_note = ""
    sage_notes: list[str] = []
    if device.type == "cuda" and dtype in (torch.bfloat16, torch.float16):
        candidates: list[str] = []
        if sage_enabled:
            candidates.extend(
                ["sage_lse_gqa", "sage_lse", "sage_lse_log2_gqa", "sage_lse_log2"]
                if kv_rep > 1
                else ["sage_lse", "sage_lse_log2"]
            )
        candidates.extend(
            ["flash_gqa", "cudnn_gqa", "flash_repeat", "cudnn_repeat"]
            if kv_rep > 1
            else ["flash_repeat", "cudnn_repeat"]
        )
        try:
            gen = torch.Generator(device=device).manual_seed(17)
            h_kv = 2
            l_q, l_k = 64, 128
            split = 48
            beta = math.log(2.5)
            q = torch.randn((1, h_kv * kv_rep, l_q, headdim), device=device, dtype=dtype, generator=gen)
            k = torch.randn((1, h_kv, l_k, headdim), device=device, dtype=dtype, generator=gen)
            v = torch.randn((1, h_kv, l_k, headdim), device=device, dtype=dtype, generator=gen)

            bias = torch.zeros((1, 1, 1, l_k), device=device, dtype=dtype)
            bias[..., split:] = beta
            ref = F.scaled_dot_product_attention(
                q,
                k.repeat_interleave(kv_rep, dim=1) if kv_rep > 1 else k,
                v.repeat_interleave(kv_rep, dim=1) if kv_rep > 1 else v,
                attn_mask=bias,
                dropout_p=0.0,
                is_causal=False,
            )

            for cand in candidates:
                is_sage = cand.startswith("sage_")
                try:
                    o0, lse0 = _run_lse_candidate(cand, q, k[:, :, :split, :], v[:, :, :split, :], kv_rep)
                    o1, lse1 = _run_lse_candidate(cand, q, k[:, :, split:, :], v[:, :, split:, :], kv_rep)
                    merged = _combine_partition_outputs_torch([o0, o1], [lse0, lse1], [0.0, beta], dtype)
                    if merged.shape != ref.shape or not torch.isfinite(merged).all():
                        if is_sage:
                            sage_notes.append(f"{cand}:invalid_shape_or_nan")
                        continue
                    diff_abs = (merged.float() - ref.float()).abs()
                    mean_diff = diff_abs.mean().item()
                    max_diff = diff_abs.max().item()
                    if is_sage:
                        # SageAttention2++ uses INT8 QK / FP8 PV quantization, so random-normal
                        # max error is larger than exact BF16 while mean error stays tight (~0.01).
                        if not (mean_diff < 0.03 and max_diff < 0.25):
                            sage_notes.append(f"{cand}:mean={mean_diff:.4f}/max={max_diff:.4f}")
                            continue
                        # Verify tiny/unaligned mask partition slices (e.g., face mask) also work cleanly.
                        o_t, lse_t = _run_lse_candidate(cand, q[:, :, :19, :], k[:, :, :15, :], v[:, :, :15, :], kv_rep)
                        if (
                            o_t.shape != (1, h_kv * kv_rep, 19, headdim)
                            or lse_t.shape != (1, h_kv * kv_rep, 19)
                            or not (torch.isfinite(o_t).all() and torch.isfinite(lse_t).all())
                        ):
                            sage_notes.append(f"{cand}:tiny_partition_failed")
                            continue
                        chosen = cand
                        probe_note = f" mean_diff={mean_diff:.4f} max_diff={max_diff:.4f}"
                        break
                    else:
                        if max_diff < 5e-2:
                            chosen = cand
                            probe_note = f" max_diff={max_diff:.4f}"
                            break
                except Exception as exc:
                    if is_sage:
                        sage_notes.append(f"{cand}:{type(exc).__name__}")
                    continue
        except Exception:
            chosen = "split_q_aligned_1d"

    if sage_enabled and not chosen.startswith("sage_") and sage_notes:
        probe_note = f"{probe_note} sage_rejected=[{', '.join(sage_notes)}]"

    _BACKEND_CACHE[cache_key] = chosen
    if cache_key not in _ANNOUNCED_BACKENDS:
        _ANNOUNCED_BACKENDS.add(cache_key)
        print(
            f"[kg_krea_edit_fast] attention backend={chosen} (dtype={dtype}, D={headdim}, gqa={kv_rep}x, sage={sage_enabled}{probe_note})",
            flush=True,
        )
    return chosen


def _build_runtime_boost_resources(plan: dict[str, Any], device, dtype) -> dict[str, Any]:
    """Upload mask gather indices & 8-aligned 1D bias tensor once per geometry/device/dtype."""
    import torch

    if not plan["active"]:
        return {"active": False, "rows0": plan["rows0"], "total_len": plan["total_len"], "bias_1d": None, "partitions": []}

    runtime_parts = []
    for kind, spec, beta in plan["partitions"]:
        if kind == "slice":
            runtime_parts.append(("slice", slice(spec[0], spec[1]), float(beta)))
        else:
            idx_t = torch.tensor(spec, device=device, dtype=torch.long)
            runtime_parts.append(("indices", idx_t, float(beta)))

    total_len = plan["total_len"]
    l_pad = ((total_len + 7) // 8) * 8
    bias_buf = torch.zeros((1, 1, 1, l_pad), device=device, dtype=dtype)
    for kind, spec, beta in plan["bias_segments"]:
        if kind == "slice":
            bias_buf[..., spec[0]:spec[1]] = beta
        else:
            idx_t = torch.tensor(spec, device=device, dtype=torch.long)
            bias_buf[..., idx_t] = beta
    bias_1d = bias_buf[..., :total_len]
    return {
        "active": True,
        "rows0": plan["rows0"],
        "total_len": total_len,
        "partitions": runtime_parts,
        "bias_1d": bias_1d,
    }


def _build_legacy_full_bias(runtime_boost: dict[str, Any], device, dtype):
    """Build explicit (1, 1, L, L) bias only on rare external attn1_patch/comfy_attention fallback blocks."""
    import torch

    if not runtime_boost["active"] or runtime_boost["bias_1d"] is None:
        return None
    L = runtime_boost["total_len"]
    rows0 = runtime_boost["rows0"]
    bias = torch.zeros((1, 1, L, L), device=device, dtype=dtype)
    bias[:, :, rows0:, :] = runtime_boost["bias_1d"]
    return bias


def _attend_target_partitioned(q_tgt, k, v, kv_rep: int, runtime_boost: dict[str, Any], backend: str):
    import comfy.ops

    if backend == "split_q_aligned_1d":
        return comfy.ops.scaled_dot_product_attention(
            q_tgt, k, v, attn_mask=runtime_boost["bias_1d"], dropout_p=0.0, is_causal=False, enable_gqa=(kv_rep > 1)
        )

    outs, lses, betas = [], [], []
    for kind, spec, beta in runtime_boost["partitions"]:
        if kind == "slice":
            k_p = k[:, :, spec, :]
            v_p = v[:, :, spec, :]
        else:
            k_p = k.index_select(2, spec)
            v_p = v.index_select(2, spec)
        out_p, lse_p = _run_lse_candidate(backend, q_tgt, k_p, v_p, kv_rep)
        outs.append(out_p)
        lses.append(lse_p)
        betas.append(beta)
    return _combine_partition_outputs_torch(outs, lses, betas, q_tgt.dtype)


def _attend_maskless(q, k, v, kv_rep: int, backend: str):
    import comfy.ops

    if backend.startswith("sage_"):
        try:
            from sageattention import sageattn
            if backend.endswith("_gqa") or kv_rep == 1:
                k_in, v_in = k.contiguous(), v.contiguous()
            else:
                k_in = k.repeat_interleave(kv_rep, dim=1).contiguous()
                v_in = v.repeat_interleave(kv_rep, dim=1).contiguous()
            return sageattn(q.contiguous(), k_in, v_in, tensor_layout="HND", is_causal=False, return_lse=False)
        except Exception:
            pass
    return comfy.ops.scaled_dot_product_attention(
        q, k, v, attn_mask=None, dropout_p=0.0, is_causal=False, enable_gqa=(kv_rep > 1)
    )


def _fast_attention(
    attn_mod,
    q,
    k,
    v,
    freqs_q,
    freqs_k,
    runtime_boost: dict[str, Any],
    backend: str,
    target_only: bool,
    transformer_options: dict[str, Any],
):
    import torch
    from comfy.ldm.flux.math import apply_rope, apply_rope1

    bs = q.shape[0]
    heads = attn_mod.heads
    kvheads = attn_mod.kvheads
    kv_rep = heads // kvheads
    dim = heads * attn_mod.headdim

    if freqs_q is freqs_k:
        q, k = apply_rope(q, k, freqs_k)
    else:
        q = apply_rope1(q, freqs_q)
        k = apply_rope1(k, freqs_k)

    rows0 = runtime_boost["rows0"]
    if target_only:
        if runtime_boost["active"]:
            out = _attend_target_partitioned(q, k, v, kv_rep, runtime_boost, backend)
        else:
            out = _attend_maskless(q, k, v, kv_rep, backend)
    elif runtime_boost["active"]:
        total_len = q.shape[2]
        tgtlen = total_len - rows0
        q_pre = q[:, :, :rows0, :]
        q_tgt = q[:, :, rows0:, :]
        out_pre = _attend_maskless(q_pre, k, v, kv_rep, backend)
        out_tgt = _attend_target_partitioned(q_tgt, k, v, kv_rep, runtime_boost, backend)
        out = torch.empty((bs, total_len, dim), device=q.device, dtype=q.dtype)
        out[:, :rows0, :] = out_pre.transpose(1, 2).reshape(bs, rows0, dim)
        out[:, rows0:, :] = out_tgt.transpose(1, 2).reshape(bs, tgtlen, dim)
        del out_pre, out_tgt
        return _maybe_output_patch(out, transformer_options)
    else:
        out = _attend_maskless(q, k, v, kv_rep, backend)

    out = out.transpose(1, 2).reshape(bs, q.shape[2], dim)
    return _maybe_output_patch(out, transformer_options)


def _maybe_output_patch(out, transformer_options: dict[str, Any]):
    patches = transformer_options.get("patches", {})
    if "block_index" in transformer_options and "attn1_output_patch" in patches:
        for p in patches["attn1_output_patch"]:
            out = p(out, transformer_options)
    return out


def _fast_block(block, x, tvec, freqs, freqs_tgt, runtime_boost, backend, target_only: bool, transformer_options):
    import torch
    import torch.nn.functional as F
    import comfy.ops

    patches = transformer_options.get("patches", {})
    has_block_attrs = all(hasattr(block, k) for k in ("mod", "prenorm", "postnorm", "attn", "mlp"))
    has_attn_attrs = has_block_attrs and all(
        hasattr(block.attn, k) for k in ("wq", "wk", "wv", "gate", "qknorm", "wo", "heads", "kvheads", "headdim")
    )
    comfy_fn = getattr(getattr(getattr(block, "attn", None), "comfy_attention", None), "function", None)
    if (
        not has_attn_attrs
        or "attn1_patch" in patches
        or comfy_fn is not None
        or "optimized_attention_override" in transformer_options
    ):
        legacy_bias = _build_legacy_full_bias(runtime_boost, x.device, x.dtype)
        out = block(x, tvec, freqs, legacy_bias, transformer_options=transformer_options)
        if target_only:
            return out[:, runtime_boost["rows0"]:, :]
        return out

    bs = x.shape[0]
    prescale, preshift, pregate, postscale, postshift, postgate = block.mod(tvec)
    pre = _core_fused_rms_adaln(x, block.prenorm, prescale, preshift)

    attn = block.attn
    heads = attn.heads
    kvheads = attn.kvheads
    headdim = attn.headdim
    seq_len = pre.shape[1]
    rows0 = runtime_boost["rows0"]
    tgt_len = seq_len - rows0 if target_only else seq_len

    q_f, k_f, v_f, g_f = _fast_proj_qkvg(attn, pre, target_only=target_only, rows0=rows0)
    del pre

    q = q_f.view(bs, tgt_len, heads, headdim).transpose(1, 2)
    k = k_f.view(bs, seq_len, kvheads, headdim).transpose(1, 2)
    v = v_f.view(bs, seq_len, kvheads, headdim).transpose(1, 2)
    q, k = _apply_qknorm(attn.qknorm, q, k)
    attn_out = _fast_attention(
        attn,
        q,
        k,
        v,
        freqs_tgt if target_only else freqs,
        freqs,
        runtime_boost,
        backend,
        target_only,
        transformer_options,
    )
    del q, k, v

    attn_gated = attn_out * F.sigmoid(g_f)
    del attn_out, g_f

    x_work = x[:, rows0:, :].contiguous() if target_only else x
    if _core_should_epi(bs, x_work, pregate):
        try:
            x_work = comfy.ops.linear_input_act(
                attn.wo, attn_gated, None, residual=x_work, residual_scale=pregate.reshape(-1)
            )
        except Exception:
            x_work = x_work.addcmul_(attn.wo(attn_gated), pregate)
    else:
        x_work = x_work.addcmul_(attn.wo(attn_gated), pregate)
    del attn_gated

    post = _core_fused_rms_adaln(x_work, block.postnorm, postscale, postshift)
    if _core_should_epi(bs, x_work, postgate):
        res = _core_mlp_step(block.mlp, post, residual=x_work, residual_scale=postgate.reshape(-1))
    else:
        mlp_out = _core_mlp_step(block.mlp, post)
        res = x_work.addcmul_(mlp_out, postgate)
    del post
    return res


def _to_4d(v):
    if v.ndim == 5:
        b, c, t, h, w = v.shape
        return v.reshape(b * t, c, h, w)
    return v


def _fit_src(src, H: int, W: int):
    import torch.nn.functional as F

    sh, sw = src.shape[-2:]
    if (sh, sw) == (H, W):
        return src
    s = max(H / sh, W / sw)
    ch, cw = min(sh, int(round(H / s))), min(sw, int(round(W / s)))
    y0, x0 = (sh - ch) // 2, (sw - cw) // 2
    src = src[..., y0:y0 + ch, x0:x0 + cw]
    return F.interpolate(src.float(), size=(H, W), mode="bilinear")


def _fit_encode_image(image, vae, H: int, W: int, cache: dict, key: tuple, fit_mode: str = "fit"):
    import torch.nn.functional as F

    full_key = key + (fit_mode,)
    if full_key in cache:
        return cache[full_key]
    px_h, px_w = H * 8, W * 8
    img = image.movedim(-1, 1)
    ih, iw = img.shape[-2:]
    if fit_mode == "fit":
        sc = min(px_h / ih, px_w / iw)
        crop_tol = 0.08
        if ih * sc >= px_h * (1 - crop_tol) and iw * sc >= px_w * (1 - crop_tol):
            s = max(px_h / ih, px_w / iw)
            ch, cw = min(ih, int(round(px_h / s))), min(iw, int(round(px_w / s)))
            y0, x0 = (ih - ch) // 2, (iw - cw) // 2
            img = img[..., y0:y0 + ch, x0:x0 + cw]
            nh, nw = px_h, px_w
        else:
            nh = min(max(16, int(ih * sc) // 16 * 16), max(16, px_h // 16 * 16))
            nw = min(max(16, int(iw * sc) // 16 * 16), max(16, px_w // 16 * 16))
            ch2, cw2 = min(ih, max(1, int(round(nh / sc)))), min(iw, max(1, int(round(nw / sc))))
            y0, x0 = (ih - ch2) // 2, (iw - cw2) // 2
            img = img[..., y0:y0 + ch2, x0:x0 + cw2]
        img = F.interpolate(img.float(), size=(nh, nw), mode="bicubic", antialias=True)
        lat = vae.encode(img.movedim(1, -1)[..., :3].clamp(0, 1))
        cache[full_key] = lat
        return lat
    s = max(px_h / ih, px_w / iw)
    ch, cw = min(ih, int(round(px_h / s))), min(iw, int(round(px_w / s)))
    y0, x0 = (ih - ch) // 2, (iw - cw) // 2
    img = img[..., y0:y0 + ch, x0:x0 + cw]
    img = F.interpolate(img.float(), size=(px_h, px_w), mode="bicubic", antialias=True)
    lat = vae.encode(img.movedim(1, -1)[..., :3].clamp(0, 1))
    cache[full_key] = lat
    return lat


def _imgids(bs: int, frame: int, h_: int, w_: int, device):
    import torch

    ids = torch.zeros(h_, w_, 3, device=device, dtype=torch.float32)
    ids[..., 0] = frame
    ids[..., 1] = torch.arange(h_, device=device, dtype=torch.float32)[:, None]
    ids[..., 2] = torch.arange(w_, device=device, dtype=torch.float32)[None, :]
    return ids.reshape(1, h_ * w_, 3).repeat(bs, 1, 1)


def _imgids_offset(bs: int, frame: int, gh: int, gw: int, th: int, tw: int, device):
    import torch

    off_h, off_w = max(0.0, (th - gh) / 2), max(0.0, (tw - gw) / 2)
    ids = torch.zeros(gh, gw, 3, device=device, dtype=torch.float32)
    ids[..., 0] = frame
    ids[..., 1] = (torch.arange(gh, device=device, dtype=torch.float32) + off_h)[:, None]
    ids[..., 2] = (torch.arange(gw, device=device, dtype=torch.float32) + off_w)[None, :]
    return ids.reshape(1, gh * gw, 3).repeat(bs, 1, 1)


def _place_refs(ref_ids, modes, h_: int, w_: int):
    modes = place_refs_pure(ref_ids, modes, w_)
    out, x0 = [], float(w_)
    for ids, mode in zip(ref_ids, modes):
        if mode.startswith("aligned"):
            out.append(ids)
            continue
        ids = ids.clone()
        if mode.startswith("beside"):
            ids[..., 2] = ids[..., 2] - ids[..., 2].min() + x0
            x0 = float(ids[..., 2].max()) + 1.0
        elif mode.startswith("bag"):
            ids[..., 1] = (h_ - 1) / 2.0
            ids[..., 2] = (w_ - 1) / 2.0
        else:
            raise ValueError(f"unknown ref_position {mode!r}")
        out.append(ids)
    return out


def _context_cache_key(context) -> tuple[Any, ...]:
    ptr = context.data_ptr() if hasattr(context, "data_ptr") else None
    return (id(context), ptr, tuple(context.shape), str(context.dtype), str(context.device))


def krea2_fast_edit_forward(
    m,
    x,
    timesteps,
    context,
    src_latent,
    transformer_options: dict[str, Any],
    *,
    ref_boost: float = 1.0,
    ref_boost_a: float = 1.0,
    ref_boost_mask=None,
    ref_native: bool = False,
    pos_mode: str = "stride1",
    ref_position: str = "aligned (trained)",
    ref_position_a: str = "aligned (trained)",
    step_cache: dict[str, Any] | None = None,
):
    """Optimized drop-in replacement for `krea2_edit_forward`."""
    import torch
    import torch.nn.functional as F
    from einops import rearrange
    import comfy.ldm.common_dit
    from comfy.ldm.flux.layers import timestep_embedding

    transformer_options = transformer_options.copy()
    patch = m.patch

    temporal = x.ndim == 5
    if temporal:
        b5, c5, t5, h5, w5 = x.shape
    x = _to_4d(x)
    bs, _, H_orig, W_orig = x.shape

    x = comfy.ldm.common_dit.pad_to_patch_size(x, (patch, patch), padding_mode="replicate")
    H, W = x.shape[-2], x.shape[-1]
    h_, w_ = H // patch, W // patch

    tgt_img = m.first(rearrange(x, "b c (h ph) (w pw) -> b (h w) (c ph pw)", ph=patch, pw=patch))
    t = m.tmlp(timestep_embedding(timesteps, m.tdim).unsqueeze(1).to(tgt_img.dtype))
    tvec = m.tproj(t)

    # CRITICAL: Never bypass m.txtfusion cache if V12/native enhancer hooked fusion.forward!
    txt_fused = None
    enhancer_hooked = "forward" in vars(m.txtfusion)
    txt_cache = step_cache.setdefault("txt", {}) if step_cache is not None else None
    if txt_cache is not None and not enhancer_hooked:
        tkey = _context_cache_key(context)
        cached_txt = txt_cache.get(tkey)
        if cached_txt is not None and cached_txt[0] is context:
            txt_fused = cached_txt[1]

    if txt_fused is None:
        unpacked = m._unpack_context(context)
        txt_fused = m.txtmlp(m.txtfusion(unpacked, mask=None, transformer_options=transformer_options))
        if txt_cache is not None and not enhancer_hooked:
            if len(txt_cache) >= 2:
                txt_cache.clear()
            txt_cache[_context_cache_key(context)] = (context, txt_fused)

    txtlen, tgtlen = txt_fused.shape[1], tgt_img.shape[1]

    # Step-invariant source patch tokens (`bs=1` expandable or batch-matched)
    src_list = src_latent if isinstance(src_latent, (list, tuple)) else [src_latent]
    src_cache = step_cache.setdefault("src_imgs", {}) if step_cache is not None else None
    src_key = (
        tuple((id(s), tuple(s.shape), str(s.dtype)) for s in src_list),
        H,
        W,
        bool(ref_native),
        str(tgt_img.device),
        str(tgt_img.dtype),
    )
    cached_src = src_cache.get(src_key) if src_cache is not None else None
    if cached_src is not None:
        src_imgs_base, src_grids = cached_src
    else:
        src_imgs_base = []
        src_grids = []
        for sl in src_list:
            src = _to_4d(sl).to(tgt_img.device, tgt_img.dtype)
            if not ref_native and src.shape[-2:] != (H, W):
                src = _fit_src(src, H, W).to(tgt_img.dtype)
            src = comfy.ldm.common_dit.pad_to_patch_size(src, (patch, patch), padding_mode="replicate")
            src_grids.append((src.shape[-2] // patch, src.shape[-1] // patch))
            src_imgs_base.append(
                m.first(rearrange(src, "b c (h ph) (w pw) -> b (h w) (c ph pw)", ph=patch, pw=patch))
            )
        if src_cache is not None:
            if len(src_cache) >= 2:
                src_cache.clear()
            src_cache[src_key] = (src_imgs_base, src_grids)

    src_imgs = [
        si if si.shape[0] == bs else si[:1].expand(bs, *si.shape[1:])
        for si in src_imgs_base
    ]
    srclen = sum(si.shape[1] for si in src_imgs)

    ctx_out = txt_fused if txt_fused.shape[0] == bs else txt_fused[:1].expand(bs, *txt_fused.shape[1:])
    combined = torch.cat([ctx_out] + src_imgs + [tgt_img], dim=1)
    del tgt_img, ctx_out

    # Step-invariant RoPE frequencies
    pos_cache = step_cache.setdefault("freqs", {}) if step_cache is not None else None
    pos_key = (
        bs,
        txtlen,
        tuple(src_grids),
        h_,
        w_,
        pos_mode,
        bool(ref_native),
        ref_position,
        ref_position_a,
        str(combined.device),
    )
    cached_pos = pos_cache.get(pos_key) if pos_cache is not None else None
    if cached_pos is not None:
        freqs, freqs_tgt = cached_pos
    else:
        device = combined.device
        if pos_mode == "stride1" and ref_native:
            ref_ids = [_imgids_offset(bs, i + 1, gh, gw, h_, w_, device) for i, (gh, gw) in enumerate(src_grids)]
        else:
            ref_ids = [_imgids(bs, i + 1, gh, gw, device) for i, (gh, gw) in enumerate(src_grids)]
        ref_ids = _place_refs(ref_ids, [ref_position_a] * (len(ref_ids) - 1) + [ref_position], h_, w_)
        pos = torch.cat(
            [torch.zeros(bs, txtlen, 3, device=device, dtype=torch.float32)]
            + ref_ids
            + [_imgids(bs, 0, h_, w_, device)],
            dim=1,
        )
        freqs = m.pe_embedder(pos)
        del pos, ref_ids
        rows0 = txtlen + srclen
        freqs_tgt = freqs[:, :, rows0:] if freqs.ndim >= 3 and freqs.shape[2] == combined.shape[1] else freqs
        if pos_cache is not None:
            if len(pos_cache) >= 2:
                pos_cache.clear()
            pos_cache[pos_key] = (freqs, freqs_tgt)

    # Step-invariant partition plan & GPU mask indices (eliminates per-step F.interpolate + CPU sync)
    boost_cache = step_cache.setdefault("boost", {}) if step_cache is not None else None
    boost_key = (
        txtlen,
        tuple(si.shape[1] for si in src_imgs),
        tgtlen,
        float(ref_boost),
        float(ref_boost_a),
        tuple(src_grids),
        str(combined.device),
        str(combined.dtype),
    )
    runtime_boost = boost_cache.get(boost_key) if boost_cache is not None else None
    if runtime_boost is None:
        slens = [si.shape[1] for si in src_imgs]
        boosts = [float(ref_boost_a)] * (len(slens) - 1) + [float(ref_boost)]
        mask_active_indices = None
        if ref_boost_mask is not None and boosts and boosts[-1] != 1.0:
            mask = ref_boost_mask[:1]
            if mask.ndim == 2:
                mask = mask[None]
            interp = F.interpolate(mask[None].float(), size=src_grids[-1], mode="area")[0, 0]
            mask_active_indices = torch.nonzero(interp.reshape(-1) > 0.5, as_tuple=True)[0].tolist()
        plan = plan_boost_partitions(txtlen, slens, tgtlen, boosts, mask_active_indices)
        runtime_boost = _build_runtime_boost_resources(plan, combined.device, combined.dtype)
        if boost_cache is not None:
            if len(boost_cache) >= 2:
                boost_cache.clear()
            boost_cache[boost_key] = runtime_boost

    # Select & self-verify LSE backend once per device/dtype/dim
    block0_attn = m.blocks[0].attn
    kv_rep = block0_attn.heads // block0_attn.kvheads
    backend = (
        _select_lse_backend(combined.device, combined.dtype, block0_attn.headdim, kv_rep)
        if (runtime_boost["active"] or _sage_attention_requested())
        else "split_q_aligned_1d"
    )

    total_len = combined.shape[1]
    n_blocks = len(m.blocks)
    transformer_options["total_blocks"] = n_blocks
    transformer_options["block_type"] = "single"
    transformer_options["img_slice"] = [txtlen, total_len]

    import comfy.model_prefetch

    prefetch_queue = comfy.model_prefetch.make_prefetch_queue(list(m.blocks), combined.device, transformer_options)
    comfy.model_prefetch.malloc_graph_begin(combined.device)
    try:
        for i, block in enumerate(m.blocks):
            comfy.model_prefetch.prefetch_queue_pop(prefetch_queue, combined.device, block, combined.dtype, malloc_scope="block")
            transformer_options["block_index"] = i
            is_last = i == n_blocks - 1
            combined = _fast_block(
                block,
                combined,
                tvec,
                freqs,
                freqs_tgt,
                runtime_boost,
                backend,
                target_only=is_last,
                transformer_options=transformer_options,
            )
        comfy.model_prefetch.prefetch_queue_pop(prefetch_queue, combined.device, None, malloc_scope="block")
        comfy.model_prefetch.malloc_graph_end()
    except Exception:
        comfy.model_prefetch.cleanup_malloc_graph()
        raise

    final = m.last(combined, t)
    del combined
    out = final
    del final
    out = rearrange(
        out,
        "b (h w) (c ph pw) -> b c (h ph) (w pw)",
        h=h_,
        w=w_,
        ph=patch,
        pw=patch,
        c=m.channels,
    )
    out = out[:, :, :H_orig, :W_orig]
    if temporal:
        out = out.reshape(b5, t5, m.channels, H_orig, W_orig).movedim(1, 2)
    return out


class KGKrea2FastEditModelPatch:
    """Drop-in fast replacement for `Krea2EditModelPatch` using partitioned Flash/cuDNN attention."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
            },
            "optional": {
                "source_latent": ("LATENT", {"tooltip": "Optional when 'vae' + 'source_image' are connected (avoids redundant VAEEncode)."}),
                "source_latent_b": ("LATENT", {"tooltip": "2nd reference (subject photo) for multi-ref LoRAs -> RoPE frame=2, training-matched order: scene first, subject second"}),
                "ref_boost": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1000.0, "step": 0.01, "round": 0.001,
                                         "tooltip": "reference-fidelity dial: multiplies target->reference attention. Applies to the LAST ref (= the subject in two-ref workflows, the only ref in single-ref). 1.0 = off, >1 pulls harder toward the reference's appearance, <1 loosens."}),
                "ref_boost_a": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1000.0, "step": 0.01, "round": 0.001,
                                           "tooltip": "same dial for the FIRST ref (= the scene in two-ref workflows). No effect in single-ref workflows. 1.0 = off"}),
                "fit_mode": (FIT_MODES, {"default": "fit",
                                         "tooltip": "how an image source fits a mismatched output aspect ratio (needs vae + source_image connected): fit = resample the source to the target grid at a centered offset (default); crop (legacy) = center-crop to target AR then resize"}),
                "ref_boost_mask": ("MASK", {"tooltip": "optional region on the (last) reference to boost, e.g. the face; empty = whole reference"}),
                "vae": ("VAE", {"tooltip": "RECOMMENDED with source_image: enables the blur-proof pixel-space path (crop+resize in pixels, encode internally)"}),
                "source_image": ("IMAGE", {"tooltip": "source as IMAGE (with vae connected): overrides source_latent with exact pixel-space fitting"}),
                "source_image_b": ("IMAGE", {"tooltip": "2nd reference as IMAGE (with vae)"}),
                "target_latent": ("LATENT", {"tooltip": "RECOMMENDED with vae + source_image: wire the SAME latent you feed KSampler.latent_image to pre-encode before sampling starts"}),
                "ref_position": (REF_POSITIONS, {"default": REF_POSITIONS[0],
                                                  "tooltip": "where the LAST reference sits in position space: aligned (trained), beside, or bag of features"}),
                "ref_position_a": (REF_POSITIONS, {"default": REF_POSITIONS[0],
                                                    "tooltip": "the same choice for the FIRST reference in two-image workflows"}),
            },
        }

    RETURN_TYPES = ("MODEL",)
    FUNCTION = "patch"
    CATEGORY = "krea2edit"
    DESCRIPTION = (
        "Drop-in speed-optimized replacement for Krea2EditModelPatch: replaces the dense LxL attention bias "
        "with exact online-softmax partitioned Flash/cuDNN attention, keeps KV un-duplicated with GQA, "
        "caches step-invariant tensors, and prunes unused tokens in the final transformer block."
    )

    def patch(
        self,
        model,
        source_latent=None,
        source_latent_b=None,
        ref_boost: float = 1.0,
        ref_boost_a: float = 1.0,
        ref_boost_mask=None,
        vae=None,
        source_image=None,
        source_image_b=None,
        fit_mode: str = "fit",
        target_latent=None,
        ref_position: str = "aligned (trained)",
        ref_position_a: str = "aligned (trained)",
        **_future,
    ):
        has_pixel_path = vae is not None and source_image is not None
        if source_latent is None and not has_pixel_path:
            raise ValueError(
                "KGKrea2FastEditModelPatch requires either 'source_latent' or both 'vae' and 'source_image'."
            )

        import comfy.patcher_extension

        if _future:
            print(
                f"[kg_krea_edit_fast] WARNING: ignoring unknown newer inputs: {', '.join(sorted(_future))}",
                flush=True,
            )
        if fit_mode == "fit" and not has_pixel_path:
            print(
                "[kg_krea_edit_fast] WARNING: fit_mode='fit' has NO EFFECT without both 'vae' and 'source_image'; "
                "falling back to latent crop path.",
                flush=True,
            )

        m = model.clone()
        mm = model.model

        src_samples = None
        if not has_pixel_path and source_latent is not None:
            src_samples = mm.process_latent_in(source_latent["samples"])
            if source_latent_b is not None:
                src_samples = [src_samples, mm.process_latent_in(source_latent_b["samples"])]

        px_cache: dict[tuple, Any] = {}
        scaled_cache: dict[tuple[int, int], Any] = {}
        step_cache: dict[str, Any] = {}
        state = {"announced": False, "warned_mismatch": False}

        primed = None
        if has_pixel_path and target_latent is not None:
            hh, ww = target_latent["samples"].shape[-2], target_latent["samples"].shape[-1]
            lat_a = mm.process_latent_in(_fit_encode_image(source_image, vae, hh, ww, px_cache, ("a", hh, ww), fit_mode))
            if source_image_b is not None:
                lat_b = mm.process_latent_in(_fit_encode_image(source_image_b, vae, hh, ww, px_cache, ("b", hh, ww), fit_mode))
                scaled_cache[(hh, ww)] = [lat_a, lat_b]
            else:
                scaled_cache[(hh, ww)] = lat_a
            primed = (hh, ww)

        def wrapper(executor, x, timesteps, context, *wargs, **kwargs):
            transformer_options = kwargs.pop("transformer_options", None)
            if transformer_options is None:
                transformer_options = next((a for a in reversed(wargs) if isinstance(a, dict)), {})
            dm = executor.class_obj
            src = src_samples
            if has_pixel_path:
                xx = _to_4d(x)
                hh, ww = xx.shape[-2], xx.shape[-1]
                if not state["announced"]:
                    state["announced"] = True
                    print(
                        f"[kg_krea_edit_fast] pixel path ACTIVE (fit_mode={fit_mode}, pos={ref_position!r}/{ref_position_a!r})",
                        flush=True,
                    )
                if (hh, ww) not in scaled_cache:
                    if primed is not None and not state["warned_mismatch"]:
                        state["warned_mismatch"] = True
                        print(
                            f"[kg_krea_edit_fast] WARNING: 'target_latent' is {primed[0] * 8}x{primed[1] * 8}px "
                            f"but sampling is at {hh * 8}x{ww * 8}px; encoding on first step.",
                            flush=True,
                        )
                    lat_a = mm.process_latent_in(_fit_encode_image(source_image, vae, hh, ww, px_cache, ("a", hh, ww), fit_mode))
                    if source_image_b is not None:
                        lat_b = mm.process_latent_in(_fit_encode_image(source_image_b, vae, hh, ww, px_cache, ("b", hh, ww), fit_mode))
                        scaled_cache[(hh, ww)] = [lat_a, lat_b]
                    else:
                        scaled_cache[(hh, ww)] = lat_a
                src = scaled_cache[(hh, ww)]

            return krea2_fast_edit_forward(
                dm,
                x,
                timesteps,
                context,
                src,
                transformer_options,
                ref_boost=ref_boost,
                ref_boost_a=ref_boost_a,
                ref_boost_mask=ref_boost_mask,
                ref_native=has_pixel_path and fit_mode == "fit",
                pos_mode=("stride1" if fit_mode == "fit" else "anchor"),
                ref_position=ref_position,
                ref_position_a=ref_position_a,
                step_cache=step_cache,
            )

        to = m.model_options.setdefault("transformer_options", {})
        comfy.patcher_extension.add_wrapper_with_key(
            comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL,
            "kg_krea2_edit_fast",
            wrapper,
            to,
        )
        return (m,)
