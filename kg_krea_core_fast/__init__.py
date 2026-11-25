"""Isolated, upgrade-guarded ComfyUI Krea 2 core performance accelerator."""

from .core_fast import (
    KNOWN_UPSTREAM_KREA2_MODEL_SHA256,
    combine_norm_mod_scale,
    fused_qk_rms_rope_bnhd,
    fused_rms_adaln,
    fused_rms_norm,
    install_krea2_core_fast,
    krea2_block_attention_and_mlp,
    select_nhd_attention_backend,
    should_use_epilogue_residual,
)

__all__ = [
    "KNOWN_UPSTREAM_KREA2_MODEL_SHA256",
    "combine_norm_mod_scale",
    "fused_qk_rms_rope_bnhd",
    "fused_rms_adaln",
    "fused_rms_norm",
    "install_krea2_core_fast",
    "krea2_block_attention_and_mlp",
    "select_nhd_attention_backend",
    "should_use_epilogue_residual",
]
