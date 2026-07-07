"""ComfyUI Krea Reference custom nodes.

This package registers the Krea 2 V9 and V10 reference-stack nodes and
the Concept Slider V1 nodes.
"""

from .kg_krea_v9 import KGKrea2ImageGuideCardV9, KGTextEncodeKreaImageReferencesV9
from .kg_krea_v10 import KGKrea2ImageGuideCardV10, KGTextEncodeKreaImageReferencesV10
from .kg_krea_slider import KGKrea2ConceptSliderCardV1, KGKrea2ConceptSliderStackV1

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "KGKrea2ImageGuideCardV9": KGKrea2ImageGuideCardV9,
    "KGTextEncodeKreaImageReferencesV9": KGTextEncodeKreaImageReferencesV9,
    "KGKrea2ImageGuideCardV10": KGKrea2ImageGuideCardV10,
    "KGTextEncodeKreaImageReferencesV10": KGTextEncodeKreaImageReferencesV10,
    "KGKrea2ConceptSliderCardV1": KGKrea2ConceptSliderCardV1,
    "KGKrea2ConceptSliderStackV1": KGKrea2ConceptSliderStackV1,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KGKrea2ImageGuideCardV9": "KG Krea 2 Image Guide Card V9",
    "KGTextEncodeKreaImageReferencesV9": "KG Krea 2 Reference Stack Encoder V9",
    "KGKrea2ImageGuideCardV10": "KG Krea 2 Image Guide Card V10",
    "KGTextEncodeKreaImageReferencesV10": "KG Krea 2 Reference Stack Encoder V10",
    "KGKrea2ConceptSliderCardV1": "KG Krea 2 Concept Slider Card V1",
    "KGKrea2ConceptSliderStackV1": "KG Krea 2 Concept Slider Stack V1",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
