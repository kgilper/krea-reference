"""KG Krea 2 V9 reference stack nodes.

Package for the V9 guide card and stack encoder.

Key behavior:

- The per-layer conditioning math warns once (instead of silently averaging)
  when the model's conditioning width does not split into the expected layer
  chunks, and per-layer gains are soft-capped so recipe spikes cannot push
  deltas arbitrarily far past encode-native scale.
- The text/logo blank-surface guard exposes a prompt-handling choice: the
  full guard rewrites marking words in the written prompt and boosts prompt
  strength, while the gentle guard keeps the artist's exact prompt words and
  prompt strength and only adds the blank-surface language.
- Widget labels are documented as a frozen API surface.

Performance note: each connected card whose targets differ from neutral costs
one extra text-encoder pass (the encode-with-this-image-muted delta), plus one
more pass when the written prompt strength is not 1.0. Encode time grows
roughly linearly with the number of active cards.

Module map:

- ``guide_card`` / ``encoder``: the two ComfyUI node classes.
- ``recipes``: tuning tables and strength curves shared by both nodes.
- ``prompts``: system/fallback prompt text and the text/logo guard rewriter.
- ``images``: reference-image preparation (framing, washes, detail control).
- ``qwen_tokens``: token-row analysis for the Krea chat template.
- ``clip_hooks``: temporary CLIP-model patches used to isolate ingredients.
- ``conditioning``: delta and per-layer composition math.
"""

from . import clip_hooks, conditioning, images, prompts, qwen_tokens, recipes
from .constants import KG_KREA_REFERENCE_TYPE
from .encoder import KGTextEncodeKreaImageReferencesV9
from .guide_card import KGKrea2ImageGuideCardV9

NODE_CLASS_MAPPINGS = {
    "KGKrea2ImageGuideCardV9": KGKrea2ImageGuideCardV9,
    "KGTextEncodeKreaImageReferencesV9": KGTextEncodeKreaImageReferencesV9,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KGKrea2ImageGuideCardV9": "KG Krea 2 Image Guide Card V9",
    "KGTextEncodeKreaImageReferencesV9": "KG Krea 2 Reference Stack Encoder V9",
}

__all__ = [
    "KG_KREA_REFERENCE_TYPE",
    "KGKrea2ImageGuideCardV9",
    "KGTextEncodeKreaImageReferencesV9",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "clip_hooks",
    "conditioning",
    "images",
    "prompts",
    "qwen_tokens",
    "recipes",
]
