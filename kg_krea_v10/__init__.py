"""KG Krea 2 V10 reference stack nodes.

Package for the V10 guide card and stack encoder. V10 keeps the V9 delta
architecture and packet contract (the two versions cross-connect through
the same KG_KREA_REFERENCE link type) and adds:

- Quick recipes for the four roles V9 left manual-only: palette,
  environment, framing, and mood board.
- Guide direction: a card can steer the result *away* from its image
  (counter-example guidance via negative delta targets).
- Per-card timing: whole image, early layout only, or final details only,
  without touching the stack's handoff.
- Manual structure/finish layer dials over the deepstack gain table.
- Balance strong cards: an optional per-phase departure budget so several
  hot cards degrade gracefully instead of fighting.
- Study reuse: a content-keyed cache of the base encode and ingredient
  deltas, making strength/timing tweaks compose-only (no encoder passes).
- Two new outputs: a plain-language stack report and a contact sheet of
  the prepared (post-treatment) references.
- A multilingual starter vocabulary for the text/logo guard's prompt
  rewriter (Spanish, French, German, Portuguese, Italian).
- User-defined custom recipes: schema-validated YAML/JSON files in
  ``custom_recipes/`` become first-class "Use image for" choices.

Module map:

- ``guide_card`` / ``encoder``: the two ComfyUI node classes.
- ``recipes``: V9 tables plus the V10 recipes, timing, and balance tables.
- ``custom_recipes``: the user-recipe schema, validation, and file loader.
- ``prompts``: direction-aware prompt text and the wider guard vocabulary.
- ``cache``: the content-keyed study cache.
- ``report``: the plain-language stack report builder.
- ``preview``: the prepared-reference contact sheet.
- ``_v9``: locates the sibling kg_krea_v9 package (math and host adapters).
"""

from . import cache, custom_recipes, preview, prompts, recipes, report
from ._v9 import v9
from .encoder import KGTextEncodeKreaImageReferencesV10
from .guide_card import KGKrea2ImageGuideCardV10

KG_KREA_REFERENCE_TYPE = v9.KG_KREA_REFERENCE_TYPE

# Shared V9 modules, exposed for tests and external callers.
clip_hooks = v9.clip_hooks
conditioning = v9.conditioning
images = v9.images
qwen_tokens = v9.qwen_tokens

NODE_CLASS_MAPPINGS = {
    "KGKrea2ImageGuideCardV10": KGKrea2ImageGuideCardV10,
    "KGTextEncodeKreaImageReferencesV10": KGTextEncodeKreaImageReferencesV10,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KGKrea2ImageGuideCardV10": "KG Krea 2 Image Guide Card V10",
    "KGTextEncodeKreaImageReferencesV10": "KG Krea 2 Reference Stack Encoder V10",
}

__all__ = [
    "KG_KREA_REFERENCE_TYPE",
    "KGKrea2ImageGuideCardV10",
    "KGTextEncodeKreaImageReferencesV10",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "cache",
    "clip_hooks",
    "conditioning",
    "custom_recipes",
    "images",
    "preview",
    "prompts",
    "qwen_tokens",
    "recipes",
    "report",
    "v9",
]
