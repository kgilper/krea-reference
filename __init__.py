"""ComfyUI Krea Reference custom nodes.

This package registers the Krea 2 V9 reference-stack nodes.
"""

from .kg_krea_v9 import KGKrea2ImageGuideCardV9, KGTextEncodeKreaImageReferencesV9

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "KGKrea2ImageGuideCardV9": KGKrea2ImageGuideCardV9,
    "KGTextEncodeKreaImageReferencesV9": KGTextEncodeKreaImageReferencesV9,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KGKrea2ImageGuideCardV9": "KG Krea 2 Image Guide Card V9",
    "KGTextEncodeKreaImageReferencesV9": "KG Krea 2 Reference Stack Encoder V9",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
