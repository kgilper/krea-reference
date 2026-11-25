"""Isolated, upgrade-safe Krea 2 core accelerator using Comfy-Kitchen & CombinedLinear.

Never modifies any files inside core ComfyUI. Instead, on startup it verifies the
SHA-256 of upstream `comfy/ldm/krea2/model.py` against known tested hashes and, if
matched, installs clean in-memory optimizations matching modern ComfyUI kernels
(`CombinedLinear`, `comfy_kitchen.rms_adaln`, `comfy_kitchen.rms_rope`, fused
SwiGLU+residual INT8 epilogues, native-GQA NHD attention, `model_prefetch`, step
caching of `txtfusion` / `pe_embedder`, and final-block target-only pruning).
"""
from __future__ import annotations

import hashlib
import inspect
import os
from typing import Any

# Upstream ComfyUI v0.45.3 commit 8d534945e (`comfy/ldm/krea2/model.py`, 2026-09-27)
KNOWN_UPSTREAM_KREA2_MODEL_SHA256 = frozenset({
    "6EDB05ABDC9630837FE5CFA7C38C136F3296DC17570837AB40A0C527A323320B",
})

_INSTALLED = False
_NHD_BACKEND_CACHE: dict[tuple[Any, ...], str] = {}
_ANNOUNCED_NHD_BACKENDS: set[tuple[Any, ...]] = set()


def _in_training() -> bool:
    try:
        import comfy.model_management as mm
        return bool(mm.in_training)
    except Exception:
        return False


def _sage_attention_requested() -> bool:
    try:
        import comfy.model_management as mm
        return bool(mm.sage_attention_enabled())
    except Exception:
        return False


def combine_norm_mod_scale(norm_scale, mod_scale):
    """Exact algebraic merge of `(1 + norm_scale)` with `(1 + mod_scale)` as `(eff_scale = prod - 1)`."""
    return (1.0 + norm_scale) * (1.0 + mod_scale) - 1.0


def should_use_epilogue_residual(batch_size: int, residual, gate) -> bool:
    """CUTLASS / GEMV residual epilogue requires batch-1 vector `[N]` matching output width."""
    if residual is None or gate is None or batch_size != 1:
        return False
    return gate.numel() == residual.shape[-1]


def fused_rms_norm(norm_mod, x):
    """Dtype-native F.rms_norm avoiding full-activation FP32 copies when unpatched."""
    if not (hasattr(norm_mod, "scale") and hasattr(norm_mod, "eps") and "forward" not in vars(norm_mod)):
        return norm_mod(x)
    import torch
    import torch.nn.functional as F
    import comfy.model_management as mm

    if mm.in_training:
        return norm_mod(x)
    w = (mm.cast_to(norm_mod.scale, dtype=torch.float32, device=x.device) + 1.0).to(x.dtype)
    return F.rms_norm(x, (x.shape[-1],), weight=w, eps=norm_mod.eps)


def fused_rms_adaln(x, norm_mod, mod_scale, mod_shift):
    """Fused RMSNorm + AdaLN modulation via `comfy_kitchen.rms_adaln` when safe."""
    if (
        not (hasattr(norm_mod, "scale") and hasattr(norm_mod, "eps") and "forward" not in vars(norm_mod))
        or _in_training()
        or not getattr(x, "is_cuda", False)
    ):
        y = norm_mod(x)
        return y.mul(1.0 + mod_scale).add_(mod_shift) if y is x else y.mul_(1.0 + mod_scale).add_(mod_shift)

    import torch
    import comfy.model_management as mm

    w_f32 = mm.cast_to(norm_mod.scale, dtype=torch.float32, device=x.device) + 1.0
    eff_scale = (w_f32 * (1.0 + mod_scale.float()) - 1.0).to(x.dtype)
    try:
        import comfy.quant_ops
        return comfy.quant_ops.ck.rms_adaln(x, eff_scale, mod_shift, norm_mod.eps)
    except Exception:
        import torch.nn.functional as F
        y = F.rms_norm(x, (x.shape[-1],), weight=w_f32.to(x.dtype), eps=norm_mod.eps)
        return y.mul_(1.0 + mod_scale).add_(mod_shift)


def fused_qk_rms_rope_bnhd(qknorm_mod, q_bnhd, k_bnhd, freqs_q_nhd, freqs_k_nhd=None):
    """Apply fused per-head QK RMSNorm + interleaved RoPE directly in BNHD layout."""
    if freqs_k_nhd is None:
        freqs_k_nhd = freqs_q_nhd
    if (
        hasattr(qknorm_mod, "qnorm")
        and hasattr(qknorm_mod, "knorm")
        and hasattr(qknorm_mod.qnorm, "scale")
        and hasattr(qknorm_mod.knorm, "scale")
        and "forward" not in vars(qknorm_mod)
        and "forward" not in vars(qknorm_mod.qnorm)
        and "forward" not in vars(qknorm_mod.knorm)
        and not _in_training()
        and getattr(q_bnhd, "is_cuda", False)
        and freqs_q_nhd is not None
    ):
        import torch
        import comfy.model_management as mm
        import comfy.quant_ops

        q_c = q_bnhd if q_bnhd.is_contiguous() else q_bnhd.contiguous()
        k_c = k_bnhd if k_bnhd.is_contiguous() else k_bnhd.contiguous()
        fq_c = freqs_q_nhd if freqs_q_nhd.is_contiguous() else freqs_q_nhd.contiguous()
        fk_c = fq_c if freqs_k_nhd is freqs_q_nhd else (freqs_k_nhd if freqs_k_nhd.is_contiguous() else freqs_k_nhd.contiguous())
        q_w = (mm.cast_to(qknorm_mod.qnorm.scale, dtype=torch.float32, device=q_c.device) + 1.0).to(q_c.dtype)
        k_w = (mm.cast_to(qknorm_mod.knorm.scale, dtype=torch.float32, device=k_c.device) + 1.0).to(k_c.dtype)
        try:
            if fk_c is fq_c and q_c.shape == k_c.shape:
                return comfy.quant_ops.ck.rms_rope(q_c, k_c, fk_c, q_w, k_w, qknorm_mod.qnorm.eps)
            q_out = comfy.quant_ops.ck.rms_rope1(q_c, fq_c, q_w, qknorm_mod.qnorm.eps)
            k_out = comfy.quant_ops.ck.rms_rope1(k_c, fk_c, k_w, qknorm_mod.knorm.eps)
            return q_out, k_out
        except Exception:
            pass

    # Clean BHND fallback if custom hooks or unsupported device/dtype
    q_hnd = fused_rms_norm(qknorm_mod.qnorm, q_bnhd.transpose(1, 2)) if "forward" not in vars(qknorm_mod) else qknorm_mod(q_bnhd.transpose(1, 2), k_bnhd.transpose(1, 2))[0]
    if "forward" not in vars(qknorm_mod):
        k_hnd = fused_rms_norm(qknorm_mod.knorm, k_bnhd.transpose(1, 2))
    else:
        _, k_hnd = qknorm_mod(q_bnhd.transpose(1, 2), k_bnhd.transpose(1, 2))
    if freqs_q_nhd is not None:
        from comfy.ldm.flux.math import apply_rope1
        fq = freqs_q_nhd.transpose(1, 2)
        fk = freqs_k_nhd.transpose(1, 2)
        q_hnd = apply_rope1(q_hnd, fq)
        k_hnd = apply_rope1(k_hnd, fk)
    return q_hnd.transpose(1, 2), k_hnd.transpose(1, 2)


def select_nhd_attention_backend(device, dtype, headdim: int, kv_rep: int) -> str:
    """Self-verify native-GQA NHD SageAttention vs PyTorch SDPA once per device/dtype/dim."""
    import torch
    import torch.nn.functional as F

    sage_enabled = _sage_attention_requested()
    cache_key = (device.type, getattr(device, "index", None), str(dtype), int(headdim), int(kv_rep), sage_enabled)
    if cache_key in _NHD_BACKEND_CACHE:
        return _NHD_BACKEND_CACHE[cache_key]

    chosen = "sdpa_gqa"
    note = ""
    if sage_enabled and device.type == "cuda" and dtype in (torch.bfloat16, torch.float16):
        try:
            from sageattention import sageattn

            gen = torch.Generator(device=device).manual_seed(23)
            h_kv = 2
            l_q, l_k = 64, 128
            q_nhd = torch.randn((2, l_q, h_kv * kv_rep, headdim), device=device, dtype=dtype, generator=gen)
            k_nhd = torch.randn((2, l_k, h_kv, headdim), device=device, dtype=dtype, generator=gen)
            v_nhd = torch.randn((2, l_k, h_kv, headdim), device=device, dtype=dtype, generator=gen)
            out_nhd = sageattn(q_nhd, k_nhd, v_nhd, tensor_layout="NHD", is_causal=False, return_lse=False, smooth_k=False)
            ref_hnd = F.scaled_dot_product_attention(
                q_nhd.transpose(1, 2),
                k_nhd.transpose(1, 2).repeat_interleave(kv_rep, dim=1) if kv_rep > 1 else k_nhd.transpose(1, 2),
                v_nhd.transpose(1, 2).repeat_interleave(kv_rep, dim=1) if kv_rep > 1 else v_nhd.transpose(1, 2),
                dropout_p=0.0,
                is_causal=False,
            )
            diff = (out_nhd.transpose(1, 2).float() - ref_hnd.float()).abs()
            mean_d, max_d = diff.mean().item(), diff.max().item()
            extra_diag = ""
            try:
                import comfy.quant_ops
                from comfy.ldm.flux.math import apply_rope1

                k_rep_hnd = k_nhd.transpose(1, 2).repeat_interleave(kv_rep, dim=1).contiguous() if kv_rep > 1 else k_nhd.transpose(1, 2).contiguous()
                v_rep_hnd = v_nhd.transpose(1, 2).repeat_interleave(kv_rep, dim=1).contiguous() if kv_rep > 1 else v_nhd.transpose(1, 2).contiguous()
                out_hnd = sageattn(
                    q_nhd.transpose(1, 2).contiguous(),
                    k_rep_hnd,
                    v_rep_hnd,
                    tensor_layout="HND",
                    is_causal=False,
                    return_lse=False,
                    smooth_k=False,
                )
                nhd_vs_hnd_max = (out_nhd.transpose(1, 2).float() - out_hnd.float()).abs().max().item()

                x_ad = torch.randn((2, 64, 256), device=device, dtype=dtype, generator=gen)
                n_sc = torch.randn((256,), device=device, dtype=dtype, generator=gen) * 0.1
                m_sc = torch.randn((2, 1, 256), device=device, dtype=dtype, generator=gen) * 0.1
                m_sh = torch.randn((2, 1, 256), device=device, dtype=dtype, generator=gen) * 0.1
                eff_sc = ((1.0 + n_sc.float()) * (1.0 + m_sc.float()) - 1.0).to(dtype)
                adaln_out = comfy.quant_ops.ck.rms_adaln(x_ad, eff_sc, m_sh, 1e-5)
                adaln_ref = (1.0 + m_sc.float()) * F.rms_norm(x_ad.float(), (256,), weight=n_sc.float() + 1.0, eps=1e-5) + m_sh.float()
                adaln_b2_max = (adaln_out.float() - adaln_ref).abs().max().item()

                theta = torch.randn((2, 64, 1, headdim // 2), device=device, dtype=torch.float32, generator=gen)
                c_r, s_r = torch.cos(theta), torch.sin(theta)
                freqs_r = torch.stack((c_r, -s_r, s_r, c_r), dim=-1).reshape(2, 64, 1, headdim // 2, 2, 2).contiguous()
                xr = torch.randn((2, 64, 4, headdim), device=device, dtype=dtype, generator=gen)
                rscale = (1.0 + torch.randn((headdim,), device=device, dtype=torch.float32, generator=gen) * 0.1).to(dtype)
                rope_out = comfy.quant_ops.ck.rms_rope1(xr, freqs_r, rscale, 1e-5)
                rope_ref = apply_rope1(
                    F.rms_norm(xr.float(), (headdim,), weight=rscale.float(), eps=1e-5).to(dtype).transpose(1, 2),
                    freqs_r.transpose(1, 2),
                ).transpose(1, 2)
                rope_b2_max = (rope_out.float() - rope_ref.float()).abs().max().item()
                extra_diag = f" nhd_vs_hnd_max={nhd_vs_hnd_max:.4f} adaln_b2_max={adaln_b2_max:.4f} rope_b2_max={rope_b2_max:.4f}"
            except Exception as dex:
                extra_diag = f" diag_err={type(dex).__name__}"

            if out_nhd.shape == q_nhd.shape and torch.isfinite(out_nhd).all() and mean_d < 0.03 and max_d < 0.25:
                chosen = "sage_nhd_gqa"
                note = f" mean_diff={mean_d:.4f} max_diff={max_d:.4f}{extra_diag}"
            else:
                note = f" sage_rejected(mean={mean_d:.4f}/max={max_d:.4f}){extra_diag}"
        except Exception as exc:
            note = f" sage_err={type(exc).__name__}"

    _NHD_BACKEND_CACHE[cache_key] = chosen
    if cache_key not in _ANNOUNCED_NHD_BACKENDS:
        _ANNOUNCED_NHD_BACKENDS.add(cache_key)
        print(
            f"[kg_krea_core_fast] NHD attention backend={chosen} (dtype={dtype}, D={headdim}, gqa={kv_rep}x, sage={sage_enabled}{note})",
            flush=True,
        )
    return chosen


def _proj_qkvg(attn, pre, target_only: bool, tgt_start: int):
    """Project (q, k, v, gate) via resident CombinedLinear when available, else individual linears."""
    combined_lin = getattr(attn, "combined_qkvg", None)
    dim = attn.heads * attn.headdim
    kv_dim = attn.kvheads * attn.headdim
    if combined_lin is not None:
        packed = combined_lin.forward(pre)
        if packed is not NotImplemented:
            q_f, k_f, v_f, g_f = packed.split((dim, kv_dim, kv_dim, dim), dim=-1)
            if target_only:
                q_f = q_f[:, tgt_start:]
                g_f = g_f[:, tgt_start:]
            return q_f, k_f, v_f, g_f
    if target_only:
        pre_q = pre[:, tgt_start:]
        return attn.wq(pre_q), attn.wk(pre), attn.wv(pre), attn.gate(pre_q)
    return attn.wq(pre), attn.wk(pre), attn.wv(pre), attn.gate(pre)


def _mlp_step(mlp, post, residual=None, residual_scale=None):
    """Run MLP (and fused SwiGLU + CUTLASS/GEMV residual epilogue when CombinedLinear is resident)."""
    import torch.nn.functional as F
    import comfy.ops

    combined_gu = getattr(mlp, "combined_gate_up", None)
    if combined_gu is not None and "forward" not in vars(mlp):
        packed = combined_gu.forward(post)
        if packed is not NotImplemented:
            return comfy.ops.linear_input_act(
                mlp.down,
                packed,
                "swiglu",
                residual=residual,
                residual_scale=residual_scale,
            )

    if "forward" not in vars(mlp):
        mlp_out = mlp.down(F.silu(mlp.gate(post)).mul_(mlp.up(post)))
    else:
        mlp_out = mlp(post)
    if residual is None:
        return mlp_out
    if residual_scale is None:
        return residual + mlp_out
    return residual.addcmul_(mlp_out, residual_scale)


def _wo_residual_step(wo_mod, attn_gated, residual=None, residual_scale=None):
    import comfy.ops

    if residual is not None and residual_scale is not None:
        try:
            return comfy.ops.linear_input_act(
                wo_mod,
                attn_gated,
                None,
                residual=residual,
                residual_scale=residual_scale,
            )
        except Exception:
            pass
        return residual.addcmul_(wo_mod(attn_gated), residual_scale)
    return wo_mod(attn_gated)


def _attend_bnhd(q_bnhd, k_bnhd, v_bnhd, attn, nhd_backend: str):
    import comfy.ops

    kv_rep = attn.heads // attn.kvheads
    if nhd_backend == "sage_nhd_gqa":
        try:
            from sageattention import sageattn
            v_c = v_bnhd if v_bnhd.is_contiguous() else v_bnhd.contiguous()
            out_nhd = sageattn(q_bnhd, k_bnhd, v_c, tensor_layout="NHD", is_causal=False, return_lse=False, smooth_k=False)
            return out_nhd.flatten(2)
        except Exception:
            pass

    out_hnd = comfy.ops.scaled_dot_product_attention(
        q_bnhd.transpose(1, 2),
        k_bnhd.transpose(1, 2),
        v_bnhd.transpose(1, 2),
        attn_mask=None,
        dropout_p=0.0,
        is_causal=False,
        enable_gqa=(kv_rep > 1),
    )
    return out_hnd.transpose(1, 2).flatten(2)


def krea2_block_attention_and_mlp(
    block,
    x,
    prescale,
    preshift,
    pregate,
    postscale,
    postshift,
    postgate,
    *,
    freqs_q_nhd,
    freqs_k_nhd,
    target_only: bool,
    tgt_start: int,
    transformer_options: dict[str, Any],
):
    """Execute one SingleStreamBlock with Comfy-Kitchen AdaLN/RMS-RoPE + CombinedLinear + epilogues."""
    import torch.nn.functional as F

    bs, seq_len, _ = x.shape
    attn = block.attn
    heads = attn.heads
    kvheads = attn.kvheads
    headdim = attn.headdim
    kv_rep = heads // kvheads
    dim = heads * headdim

    pre = fused_rms_adaln(x, block.prenorm, prescale, preshift)
    q_f, k_f, v_f, g_f = _proj_qkvg(attn, pre, target_only=target_only, tgt_start=tgt_start)
    del pre

    tgt_len = seq_len - tgt_start if target_only else seq_len
    q_bnhd = q_f.view(bs, tgt_len, heads, headdim)
    k_bnhd = k_f.view(bs, seq_len, kvheads, headdim)
    v_bnhd = v_f.view(bs, seq_len, kvheads, headdim)

    q_bnhd, k_bnhd = fused_qk_rms_rope_bnhd(attn.qknorm, q_bnhd, k_bnhd, freqs_q_nhd, freqs_k_nhd)
    nhd_backend = select_nhd_attention_backend(q_bnhd.device, q_bnhd.dtype, headdim, kv_rep)
    attn_flat = _attend_bnhd(q_bnhd, k_bnhd, v_bnhd, attn, nhd_backend)
    del q_bnhd, k_bnhd, v_bnhd

    attn_gated = attn_flat * F.sigmoid(g_f.reshape(bs, tgt_len, dim))
    del attn_flat, g_f

    x_work = x[:, tgt_start:].contiguous() if target_only else x
    use_wo_epi = should_use_epilogue_residual(bs, x_work, pregate)
    x_work = _wo_residual_step(
        attn.wo,
        attn_gated,
        residual=x_work if use_wo_epi else None,
        residual_scale=pregate.reshape(-1) if use_wo_epi else None,
    ) if use_wo_epi else x_work.addcmul_(attn.wo(attn_gated), pregate)
    del attn_gated

    post = fused_rms_adaln(x_work, block.postnorm, postscale, postshift)
    use_mlp_epi = should_use_epilogue_residual(bs, x_work, postgate)
    if use_mlp_epi:
        out = _mlp_step(block.mlp, post, residual=x_work, residual_scale=postgate.reshape(-1))
    else:
        mlp_out = _mlp_step(block.mlp, post)
        out = x_work.addcmul_(mlp_out, postgate)
    del post
    return out


def compute_file_sha256(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def check_krea2_core_compatibility(krea2_model_module) -> tuple[bool, str]:
    """Verify upstream `comfy/ldm/krea2/model.py` matches tested SHA-256 before patching."""
    if os.environ.get("KG_KREA2_CORE_FAST", "1").strip().lower() in ("0", "false", "no", "off"):
        return False, "disabled via KG_KREA2_CORE_FAST=0"
    src = inspect.getsourcefile(krea2_model_module)
    if not src or not os.path.exists(src):
        return False, "source path unavailable"
    digest = compute_file_sha256(src)
    if digest not in KNOWN_UPSTREAM_KREA2_MODEL_SHA256:
        return (
            False,
            f"upstream comfy/ldm/krea2/model.py SHA-256 changed ({digest}); skipping core accelerator until reviewed",
        )
    return True, digest


def _can_use_fast_core_block(block, transformer_options: dict[str, Any], mask, timestep_zero_index) -> bool:
    if mask is not None or timestep_zero_index is not None or _in_training():
        return False
    patches = transformer_options.get("patches", {})
    if "attn1_patch" in patches or "attn1_output_patch" in patches:
        return False
    if "optimized_attention_override" in transformer_options:
        return False
    attn = getattr(block, "attn", None)
    if attn is None or getattr(getattr(attn, "comfy_attention", None), "function", None) is not None:
        return False
    if not hasattr(block, "mod") or not hasattr(block, "prenorm") or not hasattr(block, "postnorm") or not hasattr(block, "mlp"):
        return False
    return "forward" not in vars(block.mod) and "forward" not in vars(attn)


def install_krea2_core_fast() -> bool:
    """Safely install in-memory Krea 2 core optimizations if upstream files match known hashes."""
    global _INSTALLED
    if _INSTALLED:
        return True

    import torch
    import comfy.ldm.common_dit
    import comfy.ldm.krea2.model as km
    import comfy.model_base as mb
    import comfy.model_management as mm
    import comfy.model_prefetch
    import comfy.ops
    import comfy.utils
    from comfy.ldm.flux.layers import timestep_embedding
    from comfy.ldm.flux.math import apply_rope
    from comfy.ldm.modules.attention import AttentionTensorContainer, optimized_attention_masked
    from einops import rearrange

    ok, detail = check_krea2_core_compatibility(km)
    if not ok:
        print(f"[kg_krea_core_fast] INACTIVE: {detail}", flush=True)
        return False

    # 1. Dynamic VRAM unit ordering for CombinedLinear & prefetching
    if not hasattr(mb.Krea2, "get_dynamic_vram__units"):
        def _krea2_dynamic_units(self):
            return list(self.diffusion_model.blocks), []
        mb.Krea2.get_dynamic_vram__units = _krea2_dynamic_units

    # 2. CombinedLinear groups attached cleanly inside SingleStreamBlock.__init__ (when bias is None)
    orig_block_init = km.SingleStreamBlock.__init__

    def _fast_block_init(self, *args, **kwargs):
        orig_block_init(self, *args, **kwargs)
        if hasattr(comfy.ops, "CombinedLinear"):
            attn = self.attn
            if all(getattr(m, "bias", None) is None for m in (attn.wq, attn.wk, attn.wv, attn.gate)):
                attn.combined_qkvg = comfy.ops.CombinedLinear((attn.wq, attn.wk, attn.wv, attn.gate))
            mlp = self.mlp
            if all(getattr(m, "bias", None) is None for m in (mlp.gate, mlp.up)):
                mlp.combined_gate_up = comfy.ops.CombinedLinear((mlp.gate, mlp.up))

    km.SingleStreamBlock.__init__ = _fast_block_init

    # 3. RMSNorm dtype-native fast path
    orig_rmsnorm_forward = km.RMSNorm.forward

    def _fast_rmsnorm_forward(self, x: torch.Tensor) -> torch.Tensor:
        if mm.in_training:
            return orig_rmsnorm_forward(self, x)
        import torch.nn.functional as F
        w = (mm.cast_to(self.scale, dtype=torch.float32, device=x.device) + 1.0).to(x.dtype)
        return F.rms_norm(x, (x.shape[-1],), weight=w, eps=self.eps)

    km.RMSNorm.forward = _fast_rmsnorm_forward

    # 4. Attention fallback optimization: avoid 4x repeat_interleave when possible + support CombinedLinear
    def _fast_attention_forward(self, x, freqs=None, mask=None, transformer_options={}):
        transformer_patches = transformer_options.get("patches", {})
        extra_options = transformer_options.copy()
        q_f, k_f, v_f, gate = _proj_qkvg(self, x, target_only=False, tgt_start=0)
        q = q_f.view(x.shape[0], x.shape[1], self.heads, self.headdim)
        k = k_f.view(x.shape[0], x.shape[1], self.kvheads, self.headdim)
        v = v_f.view(x.shape[0], x.shape[1], self.kvheads, self.headdim)

        has_attn_patch = "block_index" in transformer_options and "attn1_patch" in transformer_patches
        has_out_patch = "block_index" in transformer_options and "attn1_output_patch" in transformer_patches
        comfy_fn = getattr(getattr(self, "comfy_attention", None), "function", None)
        can_bnhd_direct = (
            freqs is not None
            and mask is None
            and not has_attn_patch
            and not has_out_patch
            and comfy_fn is None
            and "optimized_attention_override" not in transformer_options
            and not mm.in_training
        )
        if can_bnhd_direct:
            freqs_nhd = freqs.transpose(1, 2).contiguous() if (freqs.ndim == 6 and freqs.shape[2] == x.shape[1]) else freqs
            q, k = fused_qk_rms_rope_bnhd(self.qknorm, q, k, freqs_nhd)
            nhd_backend = select_nhd_attention_backend(q.device, q.dtype, self.headdim, self.heads // self.kvheads)
            out = _attend_bnhd(q, k, v, self, nhd_backend)
            return self.wo(out * torch.nn.functional.sigmoid(gate))

        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)
        q, k = self.qknorm(q, k)

        if has_attn_patch:
            for p in transformer_patches["attn1_patch"]:
                p_out = p(q, k, v, pe=freqs, attn_mask=mask, extra_options=extra_options)
                q, k, v = p_out.get("q", q), p_out.get("k", k), p_out.get("v", v)
                freqs, mask = p_out.get("pe", freqs), p_out.get("attn_mask", mask)

        if freqs is not None:
            q, k = apply_rope(q, k, freqs)

        # Keep native GQA on maskless optimized_attention / SDPA, only repeating for external patched masks/fn
        can_native_gqa = (mask is None and not has_attn_patch and comfy_fn is None and "optimized_attention_override" not in transformer_options)
        if self.kvheads != self.heads and not can_native_gqa:
            rep = self.heads // self.kvheads
            k = k.repeat_interleave(rep, dim=1)
            v = v.repeat_interleave(rep, dim=1)
        elif self.kvheads != self.heads and _sage_attention_requested():
            # Ensure contiguous for SageAttention native GQA
            k = k.contiguous()
            v = v.contiguous()

        q_c, k_c, v_c = AttentionTensorContainer(q), AttentionTensorContainer(k), AttentionTensorContainer(v)
        gqa_kw = {"enable_gqa": True} if (self.kvheads != self.heads and can_native_gqa) else {}
        out = optimized_attention_masked(
            q_c, k_c, v_c, self.heads, mask=mask, skip_reshape=True,
            preferred_attention=self.comfy_attention, transformer_options=transformer_options, **gqa_kw
        )

        if has_out_patch:
            for p in transformer_patches["attn1_output_patch"]:
                out = p(out, extra_options)

        return self.wo(out * torch.nn.functional.sigmoid(gate))

    km.Attention.forward = _fast_attention_forward

    # 5. SingleStreamBlock fused path (used directly when external callers invoke block(...) without _forward)
    def _fast_single_block_forward(self, x, vec, freqs, mask=None, timestep_zero_index=None, transformer_options={}):
        prescale, preshift, pregate, postscale, postshift, postgate = self.mod(vec)
        if timestep_zero_index is not None:
            bs = x.shape[0]
            ref_prescale, ref_preshift, ref_pregate = prescale[bs:], preshift[bs:], pregate[bs:]
            ref_postscale, ref_postshift, ref_postgate = postscale[bs:], postshift[bs:], postgate[bs:]
            prescale, preshift, pregate = prescale[:bs], preshift[:bs], pregate[:bs]
            postscale, postshift, postgate = postscale[:bs], postshift[:bs], postgate[:bs]

            pre = torch.cat((
                fused_rms_adaln(x[:, :timestep_zero_index], self.prenorm, prescale, preshift),
                fused_rms_adaln(x[:, timestep_zero_index:], self.prenorm, ref_prescale, ref_preshift),
            ), dim=1)
            attn = self.attn(pre, freqs, mask, transformer_options=transformer_options)
            del pre
            attn[:, :timestep_zero_index].mul_(pregate)
            attn[:, timestep_zero_index:].mul_(ref_pregate)
            x = x + attn
            del attn

            post = torch.cat((
                fused_rms_adaln(x[:, :timestep_zero_index], self.postnorm, postscale, postshift),
                fused_rms_adaln(x[:, timestep_zero_index:], self.postnorm, ref_postscale, ref_postshift),
            ), dim=1)
            mlp = _mlp_step(self.mlp, post)
            del post
            mlp[:, :timestep_zero_index].mul_(postgate)
            mlp[:, timestep_zero_index:].mul_(ref_postgate)
            x = x + mlp
            del mlp
            return x

        if _can_use_fast_core_block(self, transformer_options, mask, None):
            freqs_nhd = transformer_options.get("_kg_freqs_nhd")
            if freqs_nhd is None and freqs is not None:
                freqs_nhd = freqs.transpose(1, 2).contiguous()
            return krea2_block_attention_and_mlp(
                self, x, prescale, preshift, pregate, postscale, postshift, postgate,
                freqs_q_nhd=freqs_nhd, freqs_k_nhd=freqs_nhd,
                target_only=False, tgt_start=0, transformer_options=transformer_options,
            )

        pre = fused_rms_adaln(x, self.prenorm, prescale, preshift)
        attn_out = self.attn(pre, freqs, mask, transformer_options=transformer_options)
        del pre
        x = x + pregate * attn_out
        del attn_out
        post = fused_rms_adaln(x, self.postnorm, postscale, postshift)
        mlp_out = _mlp_step(self.mlp, post)
        del post
        return x + postgate * mlp_out

    km.SingleStreamBlock.forward = _fast_single_block_forward

    # 6. LastLayer fused AdaLN
    def _fast_last_layer_forward(self, x, tvec):
        scale, shift = self.modulation(tvec)
        return self.linear(fused_rms_adaln(x, self.norm, scale, shift))

    km.LastLayer.forward = _fast_last_layer_forward

    # 7. SingleStreamDiT._forward with txtfusion cache, freqs cache, prefetch, and last-block pruning
    def _fast_dit_forward(self, x, timesteps, context, attention_mask=None, ref_latents=None, transformer_options={}, **kwargs):
        transformer_options = transformer_options.copy()
        temporal = x.ndim == 5
        if temporal:
            b5, c5, t5, h5, w5 = x.shape
            x = x.reshape(b5 * t5, c5, h5, w5)
        bs, _, h_orig, w_orig = x.shape
        patch = self.patch

        img, imgpos, h_, w_ = self.process_img(x)
        img_tokens = img.shape[1]
        timestep_zero_index = None
        ref_method = kwargs.get("ref_latents_method", self.default_ref_method)
        if ref_method is not None and ref_latents is not None and len(ref_latents) > 0:
            ref_tokens = []
            ref_pos = []
            ref_num_tokens = []
            for index, ref in enumerate(ref_latents, 1):
                if ref.ndim == 5:
                    rb, rc, rt, rh5, rw5 = ref.shape
                    ref = ref.reshape(rb * rt, rc, rh5, rw5)
                ref = comfy.utils.repeat_to_batch_size(ref, bs)
                kontext, kontext_ids, _, _ = self.process_img(ref, index=index)
                ref_tokens.append(kontext)
                ref_pos.append(kontext_ids)
                ref_num_tokens.append(kontext.shape[1])
            img = torch.cat([img] + ref_tokens, dim=1)
            imgpos = torch.cat([imgpos] + ref_pos, dim=1)
            del ref_tokens, ref_pos
            if ref_method == "index_timestep_zero":
                timestep_zero_index = img_tokens
            transformer_options["reference_image_num_tokens"] = ref_num_tokens

        img = self.first(img)

        t = self.tmlp(timestep_embedding(timesteps, self.tdim).unsqueeze(1).to(img.dtype))
        tvec = self.tproj(t)
        if timestep_zero_index is not None:
            t0 = self.tmlp(timestep_embedding(torch.zeros_like(timesteps), self.tdim).unsqueeze(1).to(img.dtype))
            tvec = torch.cat((tvec, self.tproj(t0)), dim=0)

        patches = transformer_options.get("patches", {})
        has_post_input = "post_input" in patches
        enhancer_hooked = "forward" in vars(self.txtfusion)
        cache_dict = getattr(self, "_kg_core_cache", None)
        if cache_dict is None:
            cache_dict = {"txt": {}, "freqs": {}}
            self._kg_core_cache = cache_dict

        # Cache step-invariant txtfusion + txtmlp output unless training/hooked/masked
        ctx_out = None
        if not mm.in_training and not enhancer_hooked and attention_mask is None and not has_post_input:
            tkey = (id(context), context.data_ptr(), tuple(context.shape), str(context.dtype), str(context.device))
            cached = cache_dict["txt"].get(tkey)
            if cached is not None and cached[0] is context:
                ctx_out = cached[1]
        if ctx_out is None:
            unpacked = self._unpack_context(context)
            ctx_out = self.txtmlp(self.txtfusion(unpacked, mask=None, transformer_options=transformer_options))
            if not mm.in_training and not enhancer_hooked and attention_mask is None and not has_post_input:
                if len(cache_dict["txt"]) >= 2:
                    cache_dict["txt"].clear()
                tkey = (id(context), context.data_ptr(), tuple(context.shape), str(context.dtype), str(context.device))
                cache_dict["txt"][tkey] = (context, ctx_out)

        txtlen = ctx_out.shape[1]
        device = ctx_out.device
        if has_post_input:
            txtpos = torch.zeros(bs, txtlen, 3, device=device, dtype=torch.float32)
            for p in patches["post_input"]:
                out = p({"img": img, "txt": ctx_out, "img_ids": imgpos, "txt_ids": txtpos, "transformer_options": transformer_options})
                img, ctx_out = out["img"], out["txt"]
                imgpos, txtpos = out["img_ids"], out["txt_ids"]
            pos = torch.cat((txtpos, imgpos), dim=1)
            del txtpos, imgpos
            freqs = self.pe_embedder(pos)
            del pos
            freqs_nhd = freqs.transpose(1, 2).contiguous()
        else:
            ref_shapes = tuple(r.shape[-2:] for r in ref_latents) if ref_latents else ()
            fkey = (bs, txtlen, h_, w_, ref_shapes, str(ref_method), str(device))
            cached_f = cache_dict["freqs"].get(fkey)
            if cached_f is not None:
                freqs, freqs_nhd = cached_f
            else:
                txtpos = torch.zeros(bs, txtlen, 3, device=device, dtype=torch.float32)
                pos = torch.cat((txtpos, imgpos), dim=1)
                del txtpos, imgpos
                freqs = self.pe_embedder(pos)
                del pos
                freqs_nhd = freqs.transpose(1, 2).contiguous()
                if len(cache_dict["freqs"]) >= 4:
                    cache_dict["freqs"].clear()
                cache_dict["freqs"][fkey] = (freqs, freqs_nhd)

        combined = torch.cat((ctx_out, img), dim=1)
        del ctx_out, img
        if timestep_zero_index is not None:
            timestep_zero_index += txtlen

        n_blocks = len(self.blocks)
        transformer_options["total_blocks"] = n_blocks
        transformer_options["block_type"] = "single"
        transformer_options["img_slice"] = [txtlen, combined.shape[1]]
        transformer_options["_kg_freqs_nhd"] = freqs_nhd

        can_prune_last = (
            n_blocks > 0
            and not mm.in_training
            and timestep_zero_index is None
            and not has_post_input
            and not ref_latents
            and _can_use_fast_core_block(self.blocks[-1], transformer_options, None, None)
        )
        freqs_tgt_nhd = freqs_nhd[:, txtlen : txtlen + img_tokens].contiguous() if can_prune_last else None

        b0_attn = self.blocks[0].attn
        select_nhd_attention_backend(combined.device, combined.dtype, b0_attn.headdim, b0_attn.heads // b0_attn.kvheads)

        prefetch_queue = comfy.model_prefetch.make_prefetch_queue(list(self.blocks), device, transformer_options)
        for i, block in enumerate(self.blocks):
            comfy.model_prefetch.prefetch_queue_pop(prefetch_queue, device, block, combined.dtype)
            transformer_options["block_index"] = i
            if can_prune_last and i == n_blocks - 1:
                prescale, preshift, pregate, postscale, postshift, postgate = block.mod(tvec)
                target_out = krea2_block_attention_and_mlp(
                    block,
                    combined,
                    prescale,
                    preshift,
                    pregate,
                    postscale,
                    postshift,
                    postgate,
                    freqs_q_nhd=freqs_tgt_nhd,
                    freqs_k_nhd=freqs_nhd,
                    target_only=True,
                    tgt_start=txtlen,
                    transformer_options=transformer_options,
                )
                del combined
                combined = target_out
            else:
                combined = block(combined, tvec, freqs, None, timestep_zero_index=timestep_zero_index, transformer_options=transformer_options)
        comfy.model_prefetch.prefetch_queue_pop(prefetch_queue, device, None)

        final = self.last(combined if can_prune_last else combined[:, txtlen : txtlen + img_tokens], t)
        del combined
        out = rearrange(final, "b (h w) (c ph pw) -> b c (h ph) (w pw)", h=h_, w=w_, ph=patch, pw=patch, c=self.channels)
        out = out[:, :, :h_orig, :w_orig]
        if temporal:
            out = out.reshape(b5, t5, self.channels, h_orig, w_orig).movedim(1, 2)
        return out

    km.SingleStreamDiT._forward = _fast_dit_forward

    _INSTALLED = True
    print(f"[kg_krea_core_fast] ACTIVE (sha256={detail[:12]}.., CombinedLinear + comfy_kitchen + prefetch + cache + last-block prune)", flush=True)
    return True
