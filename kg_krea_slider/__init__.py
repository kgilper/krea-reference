"""KG Krea 2 Concept Slider V1: user-defined attribute sliders for Krea 2.

A new node line beside V9/V10 (frozen and evolving reference stacks): the
slider card describes one attribute axis ("height", "brightness") with a
-6..+6 value, and the slider stack turns each axis into conditioning
using the delta architecture the reference stacks proved on Krea 2 - no
LoRA training or download required.
"""

from .encoder import KGKrea2ConceptSliderStackV1
from .slider_card import KGKrea2ConceptSliderCardV1

__all__ = [
    "KGKrea2ConceptSliderCardV1",
    "KGKrea2ConceptSliderStackV1",
]
