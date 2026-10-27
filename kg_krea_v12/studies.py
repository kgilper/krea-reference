"""Actual combined-native pole studies, with explicit downstream consumption gates.

No finished independently-tokenized conditioning is padded, concatenated or
added. All positive studies use one prepared image/template/token sequence.
Negative conditioning remains the original native paired encode.
"""
from dataclasses import dataclass
import math

from .hooks import controlled_encode, encoder_lease
from .ledger import TAP_WIDTH, TAPS, TokenLedger
from .native import NativeContext
from .diagnostics import current as current_diagnostic

TIMINGS = ('throughout', 'early-layout', 'final-details')


def number(value, name, low, high):
    if (isinstance(value, bool) or not isinstance(value, (float, int))
            or not math.isfinite(value) or not low <= value <= high):
        raise ValueError('V12 {} must be a finite number in [{}, {}]'.format(name, low, high))
    return float(value)


def resolve_axes(cards, split, budget):
    """Explicit canonical identities only; prose similarity never merges axes.

    Native coefficient units are intentionally separate from shared calibrated
    -100..100 user amounts. No calibrated conversion is implemented or claimed.
    """
    if not isinstance(cards, (list, tuple)) or len(cards) > 8:
        raise ValueError('V12 accepts at most eight native axis cards')
    groups = {}
    for card in cards:
        if not isinstance(card, dict) or set(card) != {'axis_id', 'revision', 'plus', 'minus', 'coefficient', 'timing'}:
            raise ValueError('V12 axis requires exact versioned native coefficient fields')
        weight = number(card['coefficient'], 'coefficient', -6, 6)
        timing = card['timing']
        if timing not in TIMINGS:
            raise ValueError('V12 unknown active-step timing')
        if any(not isinstance(card[key], str) or not card[key].strip()
               for key in ('axis_id', 'revision', 'plus', 'minus')) or card['plus'] == card['minus']:
            raise ValueError('V12 requires distinct literal poles and explicit axis/revision IDs')
        key = (card['axis_id'], card['revision'])
        if key in groups and (groups[key]['plus'], groups[key]['minus']) != (card['plus'], card['minus']):
            raise ValueError('V12 canonical axis poles changed without a new revision')
        group = groups.setdefault(key, {**card, 'weights': [0.0, 0.0]})
        if timing != 'final-details' and split > 0:
            group['weights'][0] += weight
        if timing != 'early-layout' and split < 1:
            group['weights'][1] += weight
    active = [group for group in groups.values() if any(group['weights'])]
    scales = []
    for phase in range(2):
        load = sum(abs(group['weights'][phase]) for group in active)
        scale = min(1.0, budget / load) if load else 1.0
        scales.append(scale)
        for group in active:
            group['weights'][phase] *= scale
    return [group for group in active if any(group['weights'])], tuple(scales)


def _validate_output(conditioning, expanded):
    if not isinstance(conditioning, (list, tuple)) or len(conditioning) != 1:
        raise RuntimeError('V12 requires one native conditioning schedule')
    cond, meta = conditioning[0]
    if tuple(cond.shape) != (1, expanded.output_length, len(TAPS) * TAP_WIDTH):
        raise RuntimeError('V12 actual output does not match the expanded/stripped tap ledger')
    if not isinstance(meta, dict) or meta.get('pooled_output') is not None:
        raise RuntimeError('V12 unexpected native pooled conditioning')
    mask = meta.get('attention_mask')
    if mask is not None and tuple(mask.shape) != (1, expanded.output_length):
        raise RuntimeError('V12 output attention mask does not match stripped native extent')


@dataclass(frozen=True)
class NativeStudies:
    context: NativeContext
    phases: tuple
    ledgers: tuple
    encode_passes: int
    budget_scales: tuple
    active: bool
    retained_output_positions: tuple = ()
    diagnostic: object = None

    def for_step(self, model, step_index, active_steps):
        """Research join seam: select exactly one phase at an actual active step.

        This is NOT an installed sampler hook. Callers must prove step mapping,
        wrapper compatibility and masked/grounded attention handling separately.
        """
        self.context.verify()
        if model is not self.context.native['model']:
            raise RuntimeError('V12 study belongs to a different native MODEL')
        if (isinstance(step_index, bool) or not isinstance(step_index, int)
                or isinstance(active_steps, bool) or not isinstance(active_steps, int)
                or active_steps <= 0 or not 0 <= step_index < active_steps):
            raise ValueError('V12 requires an actual active denoise step index/count')
        split, early, final = self.phases
        return early if step_index / active_steps < split else final

    def sampler_conditioning(self):
        self.context.verify()
        if self.active:
            raise RuntimeError('V12 active studies require a verified wrapper/attention/step consumer; sampler export is gated')
        return self.context.native


def build_studies(context, cards, split=0.4, budget=2.0, max_passes=20, max_tokens=8192,
                  max_image_pixels=1179648):
    if not isinstance(context, NativeContext):
        raise ValueError('V12 requires an owned native context')
    context.verify()
    split = number(split, 'handoff', 0, 1)
    budget = number(budget, 'coefficient budget', 0, 6)
    for value, name in ((max_passes, 'max passes'), (max_tokens, 'max tokens'),
                        (max_image_pixels, 'max image pixels')):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError('V12 {} must be a positive integer'.format(name))
    groups, scales = resolve_axes(cards, split, budget)
    if not groups:
        return NativeStudies(context, (split, context.native, context.native), (), 0, scales, False)
    passes = 1 + 2 * len(groups)
    if passes > max_passes:
        raise RuntimeError('V12 native study pass budget exceeded before preparation')
    text_size = len(context.prompt) + sum(len(group['plus']) + len(group['minus']) + 4 for group in groups)
    if text_size > max_tokens * 32:
        raise RuntimeError('V12 pole text admission budget exceeded before preparation')
    # Import only authored sibling conditioning helpers, never upstream runtime.
    from . import conditioning
    with encoder_lease(context.clip) as (model, transformer):
        prepared = context.prepare_inputs()
        pixels = 0
        if len(prepared.images) > 2:
            raise RuntimeError('V12 supports at most native source and donor')
        for image in prepared.images:
            shape = getattr(image, 'shape', ())
            if len(shape) != 4 or shape[0] != 1 or shape[3] != 3:
                raise RuntimeError('V12 requires single clean RGB native images')
            pixels += shape[1] * shape[2]
        if pixels > max_image_pixels:
            raise RuntimeError('V12 prepared-image pixel budget exceeded before vision encoding')
        original_tokens = prepared.tokenize(context.clip, context.prompt)
        # Keep the native image/template/prompt row authoritative. Tokenize only
        # each literal text payload with the native text tokenizer; do not
        # retokenize an ever-growing prompt or prepare its images repeatedly.
        pole_tokens = [context.clip.tokenize(pole) for group in groups
                       for pole in (group['plus'], group['minus'])]
        ledger = TokenLedger.assemble(original_tokens, prepared.owners, pole_tokens)
        if len(ledger.row) > max_tokens:
            raise RuntimeError('V12 token-row budget exceeded before encoding')
        tokens = ledger.tagged_tokens()
        observed = []
        retained_positions = []
        def encode(muted):
            with controlled_encode(model, transformer, ledger, muted, max_tokens=max_tokens) as observation:
                result = context.clip.encode_from_tokens_scheduled(tokens)
            expanded = observation['ledger']
            if expanded.input_length > max_tokens:
                raise RuntimeError('V12 expanded context budget exceeded')
            _validate_output(result, expanded)
            if observed and expanded != observed[0]:
                raise RuntimeError('V12 native preparation ledger changed between studies')
            positions = ledger.native_output_positions(original_tokens, expanded)
            if retained_positions and positions != retained_positions[0]:
                raise RuntimeError('V12 native output projection changed between studies')
            retained_positions.append(positions)
            projected = conditioning.project_native(result, positions)
            native_positive = context.native['positive']
            if (len(native_positive) != 1 or projected[0][0].shape != native_positive[0][0].shape):
                raise RuntimeError('V12 projected study extent differs from the actual native positive')
            observed.append(expanded)
            diagnostic = current_diagnostic()
            if diagnostic is not None:
                diagnostic.encoded(projected[0][0], expanded, positions)
            return projected
        all_poles = tuple(range(len(ledger.poles)))
        base = encode(all_poles)
        axes = []
        for index, group in enumerate(groups):
            plus = encode(tuple(i for i in all_poles if i != 2 * index))
            minus = encode(tuple(i for i in all_poles if i != 2 * index + 1))
            axes.append(conditioning.delta(plus, minus))
        phases = []
        for phase in range(2):
            weights = [group['weights'][phase] for group in groups]
            if not any(weights):
                phases.append(context.native)
                continue
            steered = conditioning.compose(context.native['positive'], list(zip(axes, weights)))
            diagnostic = current_diagnostic()
            if diagnostic is not None:
                diagnostic.composition(context.native['positive'][0][0], axes[0][0], steered[0][0], phase)
            blended = conditioning.blend_native(context.native['positive'], steered, sum(abs(w) for w in weights))
            phases.append({**context.native, 'positive': blended})
    context.verify()
    return NativeStudies(context, (split, *phases), tuple(observed), passes, scales, True,
                         retained_positions[0])
