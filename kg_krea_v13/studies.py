"""Owned shared-row studies retaining selected literal semantic carriers.

Original native positions use the unchanged V12 N+sum(w*(P-M)) arithmetic.
Additional rows are actual selected-pole native encoder states, not padding.
"""
from dataclasses import dataclass

from ..kg_krea_v12.hooks import controlled_encode, encoder_lease
from ..kg_krea_v12.ledger import TAP_WIDTH, TAPS, TokenLedger
from ..kg_krea_v12.native import NativeContext
from ..kg_krea_v12.studies import NativeStudies, _validate_output, number, resolve_axes
from ..kg_krea_v12 import conditioning as projected_math
from ..kg_krea_v12.consumer import NativePhaseGuider
from .conditioning import construct


@dataclass(frozen=True)
class CarrierStudies(NativeStudies):
    carrier_output_positions: tuple = ()


def build_carrier_studies(
    context,
    cards,
    split=0.4,
    budget=2.0,
    max_passes=20,
    max_tokens=8192,
    max_image_pixels=1179648,
):
    if not isinstance(context, NativeContext):
        raise ValueError("V13 requires an owned native context")
    context.verify()
    split = number(split, "handoff", 0, 1)
    budget = number(budget, "coefficient budget", 0, 6)
    for value in (max_passes, max_tokens, max_image_pixels):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("V13 admission budgets must be positive integers")
    groups, scales = resolve_axes(cards, split, budget)
    if not groups:
        return CarrierStudies(
            context, (split, context.native, context.native), (), 0, scales, False
        )
    passes = 1 + 2 * len(groups)
    if passes > max_passes:
        raise RuntimeError("V13 native study pass budget exceeded")
    if (
        len(context.prompt) + sum(len(g["plus"]) + len(g["minus"]) + 4 for g in groups)
        > max_tokens * 32
    ):
        raise RuntimeError("V13 pole text admission budget exceeded")
    with encoder_lease(context.clip) as (model, transformer):
        prepared = context.prepare_inputs()
        if len(prepared.images) > 2:
            raise RuntimeError("V13 supports native source and optional donor only")
        pixels = 0
        for image in prepared.images:
            shape = getattr(image, "shape", ())
            if len(shape) != 4 or shape[0] != 1 or shape[3] != 3:
                raise RuntimeError("V13 requires single clean RGB native images")
            pixels += shape[1] * shape[2]
        if pixels > max_image_pixels:
            raise RuntimeError("V13 prepared-image pixel budget exceeded")
        original = prepared.tokenize(context.clip, context.prompt)
        payloads = [
            context.clip.tokenize(pole)
            for g in groups
            for pole in (g["plus"], g["minus"])
        ]
        ledger = TokenLedger.assemble(original, prepared.owners, payloads)
        if (
            len(ledger.row) > max_tokens
            or sum(end - start for start, end in ledger.poles) > 512
        ):
            raise RuntimeError(
                "V13 token/carrier budget exceeded before study encoding"
            )
        tokens = ledger.tagged_tokens()
        observed = []
        retained = []

        def encode(muted):
            with controlled_encode(
                model, transformer, ledger, muted, max_tokens=max_tokens
            ) as observation:
                result = context.clip.encode_from_tokens_scheduled(tokens)
            expanded = observation["ledger"]
            _validate_output(result, expanded)
            if (
                expanded.input_length > max_tokens
                or observed
                and expanded != observed[0]
            ):
                raise RuntimeError(
                    "V13 native expanded ledger changed or exceeds budget"
                )
            positions = ledger.native_output_positions(original, expanded)
            n = context.native["positive"]
            if (
                len(n) != 1
                or n[0][0].shape != (1, len(positions), len(TAPS) * TAP_WIDTH)
                or retained
                and positions != retained[0]
            ):
                raise RuntimeError("V13 original native extent/projection changed")
            observed.append(expanded)
            retained.append(positions)
            return result

        all_poles = tuple(range(len(ledger.poles)))
        base = encode(all_poles)
        axes = []
        carriers = []
        for i, group in enumerate(groups):
            positive = encode(tuple(p for p in all_poles if p != 2 * i))
            negative = encode(tuple(p for p in all_poles if p != 2 * i + 1))
            axes.append(
                projected_math.delta(
                    projected_math.project_native(positive, retained[0]),
                    projected_math.project_native(negative, retained[0]),
                )
            )
            plus_span = observed[0].output_span(observed[0].poles[2 * i])
            minus_span = observed[0].output_span(observed[0].poles[2 * i + 1])
            plus = projected_math.project_native(positive, range(*plus_span))[0][0]
            minus = projected_math.project_native(negative, range(*minus_span))[0][0]
            carriers.append((plus_span, minus_span, plus, minus))
            del positive, negative
        phases = []
        phase_positions = []
        for phase in range(2):
            weights = [g["weights"][phase] for g in groups]
            if not any(weights):
                phases.append(context.native)
                phase_positions.append(())
                continue
            projected = projected_math.compose(
                context.native["positive"], list(zip(axes, weights))
            )
            full, positions = construct(
                context.native["positive"],
                projected,
                base,
                retained[0],
                carriers,
                weights,
            )
            positive = projected_math.blend_native(
                context.native["positive"], full, sum(abs(w) for w in weights)
            )
            phases.append({**context.native, "positive": positive})
            phase_positions.append(positions)
    context.verify()
    return CarrierStudies(
        context,
        (split, *phases),
        tuple(observed),
        passes,
        scales,
        True,
        retained[0],
        None,
        tuple(phase_positions),
    )


class CarrierPhaseGuider(NativePhaseGuider):
    def sample(self, *args, **kwargs):
        if self.native_guider.cfg != 1:
            raise RuntimeError("V13 carrier guider requires CFG1 throughout sampling")
        return super().sample(*args, **kwargs)


def bind_carrier_guider(studies, guider):
    if not isinstance(studies, CarrierStudies):
        raise ValueError("V13 guider requires V13 carrier studies")
    if studies.active and getattr(guider, "cfg", None) != 1:
        raise RuntimeError(
            "V13 carrier guider requires CFG1 for its two-branch evaluation bound"
        )
    from ..kg_krea_v12.consumer import bind_native_guider

    bound = bind_native_guider(studies, guider)
    if not studies.active:
        return bound
    return CarrierPhaseGuider(bound.native_guider, bound.studies, bound.host)
