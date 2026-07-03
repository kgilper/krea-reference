"""KG Conditioning Probe - a tiny ComfyUI node for the layer-derivation harness.

Captures the conditioning tensor flowing through it and saves a compact
per-tap signature to disk, so the layer-selectivity analysis (Stage 1 of the
methodology) can measure what each of Krea 2's 12 text-layer taps encodes -
WITHOUT running diffusion (no sampler, no VAE, no image generated).

It saves the sequence-mean of the conditioning, reshaped to (12, tap_dim):
one mean vector per tap. That is enough to compute, offline, how each tap's
contribution varies across a controlled set of reference images.

Install: copy this folder into ComfyUI/custom_nodes/ on the render box and
restart. Output goes under the dedicated Claude folder
(output/claude-generations/kg-selectivity-probe/<label>.json).

This is a maintainer/analysis tool - it is NOT part of the shipped node pack
(kept under docs/, excluded from registry packs).
"""

import json
import os

import torch

try:
    import folder_paths
    _OUT_ROOT = folder_paths.get_output_directory()
except Exception:
    _OUT_ROOT = os.path.join(os.getcwd(), "output")

_PROBE_DIR = os.path.join(_OUT_ROOT, "claude-generations", "kg-selectivity-probe")
LAYER_COUNT = 12


class KGConditioningProbe:
    """Save a per-tap signature of the conditioning; pass it through unchanged."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "label": ("STRING", {"default": "probe"}),
            }
        }

    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "saved_path")
    FUNCTION = "probe"
    CATEGORY = "advanced/conditioning"
    OUTPUT_NODE = True

    def probe(self, conditioning, label):
        os.makedirs(_PROBE_DIR, exist_ok=True)
        cond_tensor, _extras = conditioning[0]  # first schedule entry: (cond, dict)
        # Mean over batch + sequence -> (feature_width,), then split into 12 taps.
        flat = cond_tensor.float().reshape(-1, cond_tensor.shape[-1]).mean(dim=0)
        width = int(flat.shape[0])
        record = {
            "label": str(label),
            "feature_width": width,
            "divides_by_12": (width % LAYER_COUNT == 0),
            "tap_dim": width // LAYER_COUNT if width % LAYER_COUNT == 0 else None,
        }
        if record["divides_by_12"]:
            taps = flat.reshape(LAYER_COUNT, width // LAYER_COUNT)
            # Compact signature per tap: full mean vector (rounded) + norm.
            record["tap_mean_vectors"] = [[round(float(v), 5) for v in row] for row in taps]
            record["tap_norms"] = [round(float(row.norm()), 5) for row in taps]
        else:
            record["seq_mean_vector"] = [round(float(v), 5) for v in flat]
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(label))
        path = os.path.join(_PROBE_DIR, safe + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f)
        return (conditioning, path)


NODE_CLASS_MAPPINGS = {"KGConditioningProbe": KGConditioningProbe}
NODE_DISPLAY_NAME_MAPPINGS = {"KGConditioningProbe": "KG Conditioning Probe (analysis)"}
