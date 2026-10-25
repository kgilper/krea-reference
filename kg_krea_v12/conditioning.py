"""Uniform native-tap arithmetic, with all native metadata retained.

No per-tap recipe table or calibrated semantic range is introduced by V12.
"""


def delta(plus, minus):
    if len(plus) != len(minus):
        raise RuntimeError('V12 conditioning schedules differ')
    result = []
    for (positive, _), (negative, _) in zip(plus, minus):
        if positive.shape != negative.shape:
            raise RuntimeError('V12 axis studies have different native extents')
        result.append(positive - negative)
    return result


def compose(base, weighted_axes):
    result = []
    for index, (cond, metadata) in enumerate(base):
        value = cond.clone()
        for axis, weight in weighted_axes:
            if weight:
                value = value + axis[index] * weight
        result.append([value, metadata.copy()])
    return result


def project_native(conditioning, retained_positions):
    """Index only positions of ONE native study; never combine finished encodes."""
    positions = list(retained_positions)
    result = []
    for value, metadata in conditioning:
        projected = value[:, positions]
        extra = metadata.copy()
        if extra.get('attention_mask') is not None:
            extra['attention_mask'] = extra['attention_mask'][:, positions]
        result.append([projected, extra])
    return result


def blend_native(native, steered, phase_load):
    """Taper extended-layout branch activation near zero; never pad two encodes.

    These are separate conditioning branches. Their downstream evaluation and
    attention compatibility remain part of the explicit sampler consumer gate.
    """
    activation = min(1.0, phase_load / 0.25)
    if activation >= 1:
        return steered
    return [[value, {**metadata, 'strength': metadata.get('strength', 1.0) * weight}]
            for conditioning, weight in ((native, 1 - activation), (steered, activation))
            for value, metadata in conditioning]
