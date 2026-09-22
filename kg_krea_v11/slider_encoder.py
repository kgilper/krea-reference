"""V11 slider grouping, per-phase budgets and explicit zero bypass."""
import math
from ._deps import sliders, v9
from . import cache


def grouped_sliders(active):
    groups = {}
    for slider in active:
        pair = (slider['plus_text'], slider['minus_text'])
        if pair[0] == pair[1]:
            continue
        reverse = (pair[1], pair[0])
        sign = 1.0
        if reverse in groups:
            pair, sign = reverse, -1.0
        if pair not in groups:
            groups[pair] = {**slider, 'weights': [0.0, 0.0], 'indices': []}
        group = groups[pair]
        group['indices'].append(slider['index'])
        timing = slider['timing']
        for phase in range(2):
            if (phase == 0 and timing == 'final details only') or (phase == 1 and timing == 'early layout only'):
                continue
            group['weights'][phase] += sign * slider['weight']
    return [s for s in groups.values() if any(w != 0 for w in s['weights'])]


def budget_weights(groups, budget):
    weights = [[s['weights'][phase] for s in groups] for phase in range(2)]
    scales = []
    for phase in weights:
        load = sum(abs(w) for w in phase)
        scale = min(1.0, budget / load) if load else 1.0
        phase[:] = [w * scale for w in phase]
        scales.append(scale)
    return weights, scales


def automatic_controls(groups):
    """Use unit reach until the maximum grouped phase load reaches six.

    Never amplify tiny values to fill a budget. Group cancellation and timing
    are resolved first, so inactive cards consume no capacity.
    """
    load = max((sum(abs(g['weights'][phase]) for g in groups) for phase in range(2)), default=0.0)
    reach = min(1.0, 6.0 / load) if load else 1.0
    return reach, min(6.0, load)


def blend_neutral(plain, steered, amount):
    """Blend denoiser predictions through Comfy's conditioning strengths.

    Below a quarter unit of aggregate axis weight, taper the activation of
    the extended pole sequence as well as its delta. This avoids a finite
    token-layout jump at zero. Full working-band values use one branch.
    """
    if amount <= 0:
        return plain
    if amount >= 1:
        return steered
    return [[cond, {**meta, 'strength': float(meta.get('strength', 1)) * weight}]
            for conditioning, weight in ((plain, 1 - amount), (steered, amount))
            for cond, meta in conditioning]


class KGKrea2ConceptSliderStackV11(sliders.KGKrea2ConceptSliderStackV1):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        inputs['required'].update({
            'Combined slider budget': ('FLOAT', {'default': 2.0, 'min': 0.0, 'max': 6.0, 'step': 0.1}),
            'Early-to-final handoff': ('FLOAT', {'default': 0.4, 'min': 0.0, 'max': 1.0, 'step': 0.01}),
        })
        inputs['optional']['Slider scaling mode'] = (['manual', 'automatic'], {
            'default': 'manual',
            'tooltip': 'Automatic computes reach and budget from active cards; the two manual values are ignored. Manual preserves saved workflows.',
        })
        return inputs

    @staticmethod
    def _encode_with_spans(clip, tokens, muted_spans):
        if muted_spans and not callable(getattr(v9.clip_hooks.get_qwen_clip_model(clip), 'process_tokens', None)):
            raise RuntimeError('V11 sliders require a Krea Qwen encoder with token-span muting support')
        return sliders.encoder.hooks.encode_with_muted_spans(clip, tokens, muted_spans)

    def execute(self, **kwargs):
        clip = kwargs.get('Krea CLIP')
        prompt = str(kwargs.get('Final image prompt', '') or '')
        mode = kwargs.get('Slider scaling mode', 'manual')
        if mode not in ('manual', 'automatic'):
            raise ValueError('Unknown V11 slider scaling mode')
        automatic = mode == 'automatic'
        reach = 1.0 if automatic else float(kwargs.get('Overall slider reach', 1.0))
        budget = 6.0 if automatic else float(kwargs.get('Combined slider budget', 2.0))
        split = float(kwargs.get('Early-to-final handoff', 0.4))
        if not all(math.isfinite(v) for v in (reach, budget, split)):
            raise ValueError('V11 slider controls must be finite')
        reach, budget, split = max(0.0, min(3.0, reach)), max(0.0, min(6.0, budget)), max(0.0, min(1.0, split))
        if reach == 0 or budget == 0:
            return (clip.encode_from_tokens_scheduled(self._tokenize(clip, prompt)),
                    'V11: reach or budget is zero; exact plain-prompt bypass, no slider studies.')
        active, skipped = self._collect_sliders(kwargs, reach)
        packets = dict(self._connected_sliders(kwargs))
        for slider in active:
            if not math.isfinite(slider['weight']):
                raise ValueError('V11 slider value must be finite')
            slider['timing'] = packets[slider['index']].get('timing', 'whole image')
            if slider['timing'] not in ('whole image', 'early layout only', 'final details only'):
                raise ValueError('Unknown V11 slider timing')
            if (split == 0 and slider['timing'] == 'early layout only') or (split == 1 and slider['timing'] == 'final details only'):
                slider['weight'] = 0.0
        groups = grouped_sliders(active)
        if not groups:
            return (clip.encode_from_tokens_scheduled(self._tokenize(clip, prompt)),
                    'V11: no active axes after cancellation/timing; exact plain-prompt bypass.')
        if automatic:
            reach, budget = automatic_controls(groups)
            for group in groups:
                group['weights'] = [w * reach for w in group['weights']]
        weights, scales = budget_weights(groups, budget)
        texts = sliders.encoder.poles.prefix_texts(prompt, groups)
        tokens = self._tokenize(clip, texts[-1])
        key_name = next(iter(tokens))
        rows = [self._tokenize(clip, text)[key_name][0] for text in texts[:-1]] + [tokens[key_name][0]]
        spans = self._pole_spans(rows)
        if len(spans) != 2 * len(groups) or any(end <= start for start, end in spans):
            raise RuntimeError('V11 could not resolve all slider pole spans; shorten the prompt/poles')
        reuse = kwargs.get('Reuse slider studies', 'reuse between runs - faster tuning') == 'reuse between runs - faster tuning'
        key = cache.make_key(clip, 'slider-v11-smooth1', texts[-1]) if reuse else None
        cached = cache.lookup(key, clip)
        encodes = 0
        if cached is None:
            base = self._encode_with_spans(clip, tokens, spans)
            axes = {}
            encodes += 1
        else:
            base, axes = cached['full'], dict(cached['deltas'])
        for position, group in enumerate(groups):
            pair = (group['plus_text'], group['minus_text'])
            if pair not in axes:
                plus = self._encode_with_spans(clip, tokens, [s for i, s in enumerate(spans) if i != position * 2])
                minus = self._encode_with_spans(clip, tokens, [s for i, s in enumerate(spans) if i != position * 2 + 1])
                axes[pair] = self._conditioning_delta(plus, minus)
                encodes += 2
        phase_loads = [sum(abs(w) for w in phase) for phase in weights]
        if min(phase_loads) < 0.25 and 'plain' not in axes:
            axes['plain'] = clip.encode_from_tokens_scheduled(self._tokenize(clip, prompt))
            encodes += 1
        cache.store(key, clip, base, axes)
        def compose(phase):
            if phase_loads[phase] == 0:
                return axes['plain']
            steered = self._compose_conditioning(base, [(axes[(s['plus_text'], s['minus_text'])], w)
                                                        for s, w in zip(groups, weights[phase]) if w])
            amount = min(1.0, phase_loads[phase] / 0.25)
            return blend_neutral(axes.get('plain'), steered, amount)
        if weights[0] == weights[1]:
            result = compose(0)
        elif split == 0:
            result = compose(1)
        elif split == 1:
            result = compose(0)
        else:
            result = v9.conditioning.with_timestep_range(compose(0), 0.0, split)
            result += v9.conditioning.with_timestep_range(compose(1), split, 1.0)
        lines = ['KG Krea 2 Concept Slider Stack V11',
                 'Studies: {} encoder passes; {} distinct axes from {} active cards.'.format(encodes, len(groups), len(active)),
                 'Aggregate coefficient budget {:.2f}; phase scales {:.4f}, {:.4f}; handoff {:.2f}.'.format(budget, *scales, split),
                 'The budget bounds coefficients, not perceptual change. Start in the +/-2 to 4 working band.']
        lines.insert(1, 'Scaling mode: {}; effective reach {:.4f}; effective budget {:.4f}.'.format(mode, reach, budget))
        if automatic:
            lines.append('Automatic uses active grouped phase loads; manual reach/budget widgets are ignored.')
            if reach < 1.0:
                lines.append('Automatic reach reduced to keep the combined coefficient magnitude within 6; relative card strengths are preserved.')
        if min(phase_loads) < 0.25:
            lines.append('Neutral transition active below 0.25 total axis weight; inactive phases use the plain prompt. Small values may require a second denoiser branch.')
        for i, group in enumerate(groups):
            lines.append('Cards {}: early {:.4f}, final {:.4f}; + {} / - {}'.format(
                group['indices'], weights[0][i], weights[1][i], group['plus_text'], group['minus_text']))
        for skip in skipped:
            lines.append('Skipped card {}: {}'.format(skip['index'], skip['reason']))
        return result, '\n'.join(lines)
