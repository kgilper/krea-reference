"""Additive opt-in carrier API; existing V12 nodes/behavior are untouched."""
from ..kg_krea_v12.nodes import CONTEXT_TYPE, AXIS_TYPE
from .studies import build_carrier_studies, bind_carrier_guider

CARRIER_STUDIES_TYPE = "KG_KREA_NATIVE_CARRIER_STUDIES_V13"


class KGKrea2NativeCarrierStudiesV13:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Native context": (CONTEXT_TYPE,),
                "Early-to-final handoff": (
                    "FLOAT",
                    {"default": 0.4, "min": 0.0, "max": 1.0},
                ),
                "Native coefficient budget": (
                    "FLOAT",
                    {"default": 2.0, "min": 0.0, "max": 6.0},
                ),
            },
            "optional": {f"Native axis {i}": (AXIS_TYPE,) for i in range(1, 9)},
        }

    RETURN_TYPES = (CARRIER_STUDIES_TYPE, "STRING")
    RETURN_NAMES = ("carrier_studies", "study_report")
    FUNCTION = "execute"
    CATEGORY = "advanced/conditioning/native carriers"

    def execute(self, **kwargs):
        cards = [
            kwargs[f"Native axis {i}"]
            for i in range(1, 9)
            if kwargs.get(f"Native axis {i}") is not None
        ]
        result = build_carrier_studies(
            kwargs["Native context"],
            cards,
            split=kwargs["Early-to-final handoff"],
            budget=kwargs["Native coefficient budget"],
        )
        return result, (
            "Native carrier studies V13: {} encoder passes; selected literal carriers retained; "
            "CFG1 and at most two native positive branches per step. No semantic calibration claimed."
        ).format(result.encode_passes)


class KGKrea2NativeCarrierPhaseGuiderV13:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "Carrier studies": (CARRIER_STUDIES_TYPE,),
                "Native guider": ("GUIDER",),
            }
        }

    RETURN_TYPES = ("GUIDER",)
    RETURN_NAMES = ("native_carrier_guider",)
    FUNCTION = "execute"
    CATEGORY = "advanced/conditioning/native carriers"

    def execute(self, **kwargs):
        return (
            bind_carrier_guider(kwargs["Carrier studies"], kwargs["Native guider"]),
        )
