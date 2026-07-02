"""Conditioning delta and composition math for the V9 stack encoder.

The encoder isolates each ingredient's contribution by re-encoding with that
ingredient muted and subtracting (a delta), then re-adds the deltas with
per-card weights. Layer-targeted weights split the conditioning width into
the 12 deepstack chunks; when a model's width does not divide evenly the
composition falls back to a flat average and warns once per process.
"""

import logging

import torch

_logger = logging.getLogger(__name__)

# Set once when the layered conditioning path falls back to a flat average,
# so the warning appears a single time per process instead of every encode.
# Tests reset this flag directly to re-exercise the warning.
_layer_fallback_warned = False


def _warn_layer_fallback(flat, layer_count):
    global _layer_fallback_warned
    if _layer_fallback_warned:
        return
    _layer_fallback_warned = True
    _logger.warning(
        "KG Krea V9: conditioning width %s does not split into %s layer chunks; "
        "per-layer gains fall back to a flat average. Layer-targeted recipes "
        "(style, palette, material, lighting) will use broad conditioning on this model.",
        flat,
        layer_count,
    )


def conditioning_delta(conditioning, muted_conditioning):
    """Return per-schedule (cond, pooled) differences: full minus muted."""
    if len(conditioning) != len(muted_conditioning):
        raise RuntimeError("Krea delta expected matching conditioning schedules but got {} and {}".format(len(conditioning), len(muted_conditioning)))

    deltas = []
    for full, muted in zip(conditioning, muted_conditioning):
        cond, pooled = full
        muted_cond, muted_pooled = muted
        if cond.shape != muted_cond.shape:
            raise RuntimeError("Krea delta expected matching conditioning shapes but got {} and {}".format(cond.shape, muted_cond.shape))

        pooled_delta = {}
        full_pooled = pooled.get("pooled_output", None)
        muted_pooled_output = muted_pooled.get("pooled_output", None)
        if torch.is_tensor(full_pooled) and torch.is_tensor(muted_pooled_output) and full_pooled.shape == muted_pooled_output.shape:
            pooled_delta["pooled_output"] = full_pooled - muted_pooled_output

        deltas.append([cond - muted_cond, pooled_delta])
    return deltas


def apply_prompt_delta(conditioning, muted_conditioning):
    """conditioning_delta with a prompt-specific schedule-mismatch message."""
    if len(conditioning) != len(muted_conditioning):
        raise RuntimeError("Krea prompt strength delta expected matching conditioning schedules but got {} and {}".format(len(conditioning), len(muted_conditioning)))

    return conditioning_delta(conditioning, muted_conditioning)


def compose_conditioning(full_conditioning, weighted_deltas):
    """Add weighted deltas onto the full conditioning.

    Each weighted delta is (delta, token_weight), (delta, token_weight,
    pooled_weight), or (delta, token_weight, pooled_weight, layer_weights).
    A layer_weights list replaces the token weight with per-chunk gains over
    the deepstack layers; widths that do not split fall back to the flat
    average of the gains (with a once-per-process warning).
    """
    out = []
    for i, (cond, pooled) in enumerate(full_conditioning):
        cond_out = cond.clone()
        pooled_out = pooled.copy()
        pooled_output = pooled_out.get("pooled_output", None)
        pooled_out_value = pooled_output.clone() if torch.is_tensor(pooled_output) else pooled_output

        for entry in weighted_deltas:
            if len(entry) == 2:
                delta, token_weight = entry
                pooled_weight = token_weight
            elif len(entry) == 3:
                delta, token_weight, pooled_weight = entry
            elif len(entry) == 4:
                delta, token_weight, pooled_weight, layer_weights = entry
                if layer_weights is not None:
                    token_weight = layer_weights
            else:
                raise RuntimeError("Krea delta weights expected 2, 3, or 4 values but got {}".format(len(entry)))

            token_weight_is_list = isinstance(token_weight, (list, tuple))
            if (not token_weight_is_list and token_weight == 0.0) and pooled_weight == 0.0:
                continue
            delta_cond, delta_pooled = delta[i]
            if token_weight_is_list:
                layer_count = len(token_weight)
                flat = delta_cond.shape[-1]
                if layer_count > 1 and flat % layer_count == 0:
                    layer_dim = flat // layer_count
                    orig_dtype = delta_cond.dtype
                    shaped_delta = delta_cond.float().view(*delta_cond.shape[:-1], layer_count, layer_dim)
                    gains = torch.tensor(token_weight, dtype=shaped_delta.dtype, device=shaped_delta.device)
                    shaped_delta = shaped_delta * gains.view(*([1] * (shaped_delta.dim() - 2)), layer_count, 1)
                    cond_out = cond_out + shaped_delta.view_as(delta_cond).to(orig_dtype)
                else:
                    _warn_layer_fallback(flat, layer_count)
                    fallback_weight = sum(float(v) for v in token_weight) / max(1, layer_count)
                    if fallback_weight != 0.0:
                        cond_out = cond_out + delta_cond * fallback_weight
            elif token_weight != 0.0:
                cond_out = cond_out + delta_cond * token_weight
            delta_pooled_output = delta_pooled.get("pooled_output", None)
            if pooled_weight != 0.0 and torch.is_tensor(pooled_out_value) and torch.is_tensor(delta_pooled_output):
                pooled_out_value = pooled_out_value + delta_pooled_output * pooled_weight

        if torch.is_tensor(pooled_out_value):
            pooled_out["pooled_output"] = pooled_out_value

        out.append([cond_out, pooled_out])
    return out


def with_timestep_range(conditioning, start, end):
    """Return conditioning limited to a sampling window, without mutating."""
    ranged = []
    for cond, pooled in conditioning:
        pooled_out = pooled.copy()
        pooled_out["start_percent"] = float(start)
        pooled_out["end_percent"] = float(end)
        ranged.append([cond, pooled_out])
    return ranged
