"""The Concept Slider stack: user-defined attribute sliders, training-free.

What a slider LoRA learns offline (a low-rank direction between "more of
this attribute" and "less of it"), this stack derives at encode time from
the text encoder itself, using the render-proven V9/V10 delta
architecture:

- Each slider contributes two opposite pole sentences appended to the
  prompt in ONE token sequence, so every contribution is measured in the
  same per-token frame.
- The base encode mutes every pole span (zeroed embeddings + attention,
  V9's mute mechanism), leaving exactly the artist's prompt.
- Each pole is then encoded solo (all other pole spans muted) and the
  slider's axis is the conditioning difference increase-minus-decrease -
  the base cancels out of the subtraction.
- The output re-adds each axis at a weight proportional to the slider
  value: out = base + sum((value / 6) * FULL_SCALE_PUSH * reach * axis).
  Negative values push along the decrease direction (negative re-adds are
  render-proven by V10's "away" cards); everything rides the token path,
  because Krea 2's Qwen3-VL encoder has no pooled output.

Cost: 1 + 2 x (active sliders) encoder passes, once per content change.
Axes depend only on text, never on values, so the content-keyed study
cache makes slider drags compose-only (no encoder passes at all).

The private methods that wrap sibling modules (_encode_with_spans,
_compose_conditioning, ...) are a stable seam the contract tests patch;
keep them defined on this class.
"""

from . import cache as study_cache
from . import hooks, poles
from . import report as slider_report
from ._v9 import v9
from .constants import FULL_SCALE_PUSH, KG_KREA_SLIDER_TYPE, MAX_AXIS_WEIGHT, SLIDER_RANGE


class KGKrea2ConceptSliderStackV1:
    """
    KG Prefix: Krea 2 Concept Slider Stack V1

    Reads slider packets and builds Krea conditioning with each slider's
    semantic axis pushed by its value, plus a plain-language slider report.
    """

    MAX_SLIDERS = 8

    REUSE_LABELS = {
        "reuse between runs - faster tuning": True,
        "always re-study": False,
    }

    @classmethod
    def _slider_inputs(cls):
        return {
            f"Slider {i}": (KG_KREA_SLIDER_TYPE,)
            for i in range(1, cls.MAX_SLIDERS + 1)
        }

    @classmethod
    def INPUT_TYPES(cls):
        # Widget labels are the saved-workflow API: append new labels only;
        # never rename or reorder (same freeze rule as the V9/V10 stacks).
        return {
            "required": {
                "Krea CLIP": ("CLIP",),
                "Final image prompt": ("STRING", {"multiline": True, "dynamic_prompts": True}),
                "Overall slider reach": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.05}),
                "Reuse slider studies": (list(cls.REUSE_LABELS.keys()),),
            },
            "optional": cls._slider_inputs(),
        }

    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "slider_report")
    FUNCTION = "execute"
    CATEGORY = "advanced/conditioning"

    # -- module seams (patched by the contract tests; keep on the class) ----

    @staticmethod
    def _tokenize(clip, text):
        return clip.tokenize(text)

    @staticmethod
    def _pole_spans(token_rows):
        return poles.pole_spans(token_rows)

    @staticmethod
    def _encode_with_spans(clip, tokens, muted_spans):
        return hooks.encode_with_muted_spans(clip, tokens, muted_spans)

    @staticmethod
    def _conditioning_delta(plus_conditioning, minus_conditioning):
        return v9.conditioning.conditioning_delta(plus_conditioning, minus_conditioning)

    @staticmethod
    def _compose_conditioning(base_conditioning, weighted_axes):
        return v9.conditioning.compose_conditioning(base_conditioning, weighted_axes)

    @staticmethod
    def _cache_key(clip, full_text):
        return study_cache.make_key(clip, full_text)

    @staticmethod
    def _cache_lookup(key, clip):
        return study_cache.lookup(key, clip)

    @staticmethod
    def _cache_store(key, clip, base_conditioning, axes):
        study_cache.store(key, clip, base_conditioning, axes)

    @staticmethod
    def _build_report(info):
        return slider_report.build_report(info)

    # -- slider packet reading ----------------------------------------------

    @staticmethod
    def _slider_index(name):
        parts = str(name).split()
        if len(parts) == 2 and parts[0] == "Slider" and parts[1].isdigit():
            return int(parts[1])
        return None

    def _connected_sliders(self, kwargs):
        sliders = []
        for key, value in kwargs.items():
            index = self._slider_index(key)
            if index is None or value is None:
                continue
            sliders.append((index, value))
        sliders.sort(key=lambda item: item[0])
        return sliders

    def _collect_sliders(self, kwargs, reach):
        """Resolve connected slider packets into active axis entries.

        Returns (active, skipped); packets at value 0 or without any pole
        text are skipped and cost nothing, with the reason surfaced in the
        report.
        """
        active = []
        skipped = []
        for index, packet in self._connected_sliders(kwargs):
            if not isinstance(packet, dict):
                skipped.append({"index": index, "reason": "not a slider packet"})
                continue

            description = poles.normalize_text(packet.get("description", ""))
            auto_plus, auto_minus = poles.auto_pole_texts(description)
            increase_override = poles.pole_sentence(packet.get("increase_text", ""))
            decrease_override = poles.pole_sentence(packet.get("decrease_text", ""))
            plus_text = increase_override or auto_plus
            minus_text = decrease_override or auto_minus
            if not plus_text or not minus_text:
                skipped.append({"index": index, "reason": "no description or pole text"})
                continue

            value = float(packet.get("value", 0.0))
            value = min(max(value, -SLIDER_RANGE), SLIDER_RANGE)
            if value == 0.0:
                skipped.append({"index": index, "reason": "at 0 - costs nothing"})
                continue

            weight = (value / SLIDER_RANGE) * FULL_SCALE_PUSH * reach
            weight = min(max(weight, -MAX_AXIS_WEIGHT), MAX_AXIS_WEIGHT)
            active.append({
                "index": index,
                "description": description,
                "value": value,
                "weight": weight,
                "plus_text": plus_text,
                "minus_text": minus_text,
                "plus_auto": not increase_override,
                "minus_auto": not decrease_override,
            })
        return active, skipped

    # -- node entry point ----------------------------------------------------

    def execute(self, **kwargs):
        clip = kwargs.get("Krea CLIP")
        prompt = str(kwargs.get("Final image prompt", "") or "")
        reach = max(0.0, float(kwargs.get("Overall slider reach", 1.0)))
        reuse_studies = bool(
            self.REUSE_LABELS.get(kwargs.get("Reuse slider studies", "reuse between runs - faster tuning"), True)
        )
        sliders, skipped = self._collect_sliders(kwargs, reach)

        texts = poles.prefix_texts(prompt, sliders)
        full_text = texts[-1]
        tokens = self._tokenize(clip, full_text)

        spans = []
        if sliders:
            key_name = next(iter(tokens))
            ladder_rows = [self._tokenize(clip, text)[key_name][0] for text in texts[:-1]]
            ladder_rows.append(tokens[key_name][0])
            spans = self._pole_spans(ladder_rows)

        cache_key = None
        cached = None
        if reuse_studies:
            cache_key = self._cache_key(clip, full_text)
            cached = self._cache_lookup(cache_key, clip)

        encodes_done = 0
        reused = 0
        if cached is None:
            base_conditioning = self._encode_with_spans(clip, tokens, spans)
            encodes_done += 1
            axes = {}
        else:
            base_conditioning = cached["base"]
            axes = dict(cached["axes"])
            reused += 1

        # One axis per distinct pole pair: two sliders over the same poles
        # share a study, and value-only re-runs are compose-only cache hits.
        # `reused` counts the encoder passes avoided this run.
        for position, slider in enumerate(sliders):
            pair = (slider["plus_text"], slider["minus_text"])
            if pair in axes:
                reused += 2
                continue
            pole_position = position * 2
            plus_spans = [span for i, span in enumerate(spans) if i != pole_position]
            minus_spans = [span for i, span in enumerate(spans) if i != pole_position + 1]
            plus_conditioning = self._encode_with_spans(clip, tokens, plus_spans)
            minus_conditioning = self._encode_with_spans(clip, tokens, minus_spans)
            encodes_done += 2
            axes[pair] = self._conditioning_delta(plus_conditioning, minus_conditioning)

        if cache_key is not None:
            self._cache_store(cache_key, clip, base_conditioning, axes)

        weighted_axes = [
            (axes[(slider["plus_text"], slider["minus_text"])], slider["weight"])
            for slider in sliders
        ]
        if weighted_axes:
            conditioning_out = self._compose_conditioning(base_conditioning, weighted_axes)
        else:
            conditioning_out = base_conditioning

        report_text = self._build_report({
            "prompt_text": prompt.strip(),
            "reach": reach,
            "encodes_done": encodes_done,
            "reused_studies": reused,
            "sliders": sliders,
            "skipped": skipped,
        })
        return (conditioning_out, report_text)
