"""Selected native pole carriers with the original projected states preserved."""
import math


def construct(native, projected, full_base, retained_positions, poles, weights):
    """Each pole: (plus_span, minus_span, plus_cells, minus_cells).

    Span coordinates refer to the actual shared-row, native-stripped output.
    Each cells item is that same span sliced from the corresponding real pass.
    """
    if len(poles) != len(weights) or any(
        isinstance(w, bool)
        or not isinstance(w, (float, int))
        or not math.isfinite(w)
        or abs(w) > 6
        for w in weights
    ):
        raise ValueError("Invalid carrier weights")
    if not any(weights):
        return native, tuple(retained_positions)
    if (
        len(native) != len(projected)
        or len(native) != len(full_base)
        or len(native) != 1
    ):
        raise ValueError("One native schedule is required")
    retained = tuple(retained_positions)
    n, nmeta = native[0]
    p, _ = projected[0]
    b, bmeta = full_base[0]
    if (
        n.shape != p.shape
        or len(retained) != n.shape[1]
        or len(set(retained)) != len(retained)
        or n.shape[0] != 1
        or b.shape[0] != 1
        or b.shape[-1] != n.shape[-1]
        or any(type(i) is not int or not 0 <= i < b.shape[1] for i in retained)
    ):
        raise ValueError("Native carrier extent differs")
    selected = []
    occupied = set(retained)
    for entry, w in zip(poles, weights):
        plus_span, minus_span, plus, minus = entry
        for start, end in (plus_span, minus_span):
            if not 0 <= start < end <= b.shape[1] or occupied.intersection(
                range(start, end)
            ):
                raise ValueError("Unowned/overlapping carrier span")
            occupied.update(range(start, end))
        if not w:
            continue
        span, cells = (plus_span, plus) if w > 0 else (minus_span, minus)
        if cells.shape != (1, span[1] - span[0], b.shape[-1]):
            raise ValueError("Carrier cells must come from the exact selected span")
        selected.append((span, cells, abs(w)))
    if sum(end - start for (start, end), _, _ in selected) > 512:
        raise ValueError("Carrier token budget exceeded")
    keep = sorted(set(retained).union(*(set(range(*span)) for span, _, _ in selected)))
    mapping = {old: new for new, old in enumerate(keep)}
    value = b[:, keep].clone()
    value[:, [mapping[i] for i in retained]] = p
    for (start, end), cells, w in selected:
        positions = list(range(start, end))
        value[:, [mapping[i] for i in positions]] = (
            cells if w == 1 else b[:, positions] + (cells - b[:, positions]) * w
        )
    metadata = nmeta.copy()
    if bmeta.get("attention_mask") is not None:
        mask = bmeta["attention_mask"][:, keep].clone()
        for span, _, _ in selected:
            mask[:, [mapping[i] for i in range(*span)]] = 1
        if nmeta.get("attention_mask") is not None:
            mask[:, [mapping[i] for i in retained]] = nmeta["attention_mask"]
        metadata["attention_mask"] = mask
    elif nmeta.get("attention_mask") is not None:
        raise ValueError("Expanded native key mask missing")
    return [[value, metadata]], tuple(keep)
