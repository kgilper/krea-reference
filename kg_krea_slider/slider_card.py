"""The Concept Slider card: describes one user-defined slider.

A card is pure description - it costs nothing to evaluate and emits a
small packet the slider stack reads. The artist names an attribute
("height", "brightness", "age"), sets a value on the -6..+6 dial (0 = no
change, negative = less / the opposite, positive = more), and can
optionally spell out what each end of the dial looks like when the
auto-derived pole phrases are not right for the attribute.
"""

from .constants import KG_KREA_SLIDER_TYPE, SLIDER_RANGE


class KGKrea2ConceptSliderCardV1:
    """
    KG Prefix: Krea 2 Concept Slider Card V1

    Describes one training-free attribute slider and emits a slider packet
    for the Concept Slider stack. No model work happens on the card.
    """

    @classmethod
    def INPUT_TYPES(cls):
        # Widget labels are the saved-workflow API: append new labels only;
        # never rename or reorder (same freeze rule as the V9/V10 cards).
        return {
            "required": {
                "What this slider changes": ("STRING", {"default": "brightness", "multiline": False}),
                "Slider value": ("FLOAT", {
                    "default": 0.0,
                    "min": -SLIDER_RANGE,
                    "max": SLIDER_RANGE,
                    "step": 0.05,
                    "display": "slider",
                }),
                "What +6 looks like (optional)": ("STRING", {"default": "", "multiline": False}),
                "What -6 looks like (optional)": ("STRING", {"default": "", "multiline": False}),
            }
        }

    RETURN_TYPES = (KG_KREA_SLIDER_TYPE,)
    RETURN_NAMES = ("slider",)
    FUNCTION = "build"
    CATEGORY = "advanced/conditioning"

    def build(self, **kwargs):
        value = float(kwargs.get("Slider value", 0.0))
        value = min(max(value, -SLIDER_RANGE), SLIDER_RANGE)
        # Packet keys are frozen once shipped (append-only), like the V9
        # guide-card packet keys.
        packet = {
            "kg_slider_version": 1,
            "description": str(kwargs.get("What this slider changes", "") or "").strip(),
            "value": value,
            "increase_text": str(kwargs.get("What +6 looks like (optional)", "") or "").strip(),
            "decrease_text": str(kwargs.get("What -6 looks like (optional)", "") or "").strip(),
        }
        return (packet,)
