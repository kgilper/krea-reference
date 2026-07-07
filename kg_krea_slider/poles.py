"""Pole phrases and their token spans for the Concept Slider stack.

A slider is a semantic axis between two opposite pole phrases (increase /
decrease). Both poles are appended to the artist's prompt in ONE token
sequence, so each pole's contribution can be isolated by muting its token
span - the same-sequence trick that makes V9's ingredient deltas
per-token comparable. This module builds the pole sentences and finds each
pole's token span by tokenizing successive prefixes and taking the first
divergence between consecutive rows (robust against BPE merges at the
segment boundaries: a merge shifts the divergence by at most one separator
token, which is harmless to mute with either neighbor).
"""

from ._v9 import v9


def normalize_text(text):
    """Collapse whitespace; empty-ish input becomes the empty string."""
    return " ".join(str(text or "").split()).strip()


def pole_sentence(text):
    """Normalize an artist-supplied pole phrase into one sentence."""
    text = normalize_text(text)
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def auto_pole_texts(description):
    """Default pole sentences derived from the slider description.

    The two sentences are token-parallel (they differ only in the
    high/maximum vs low/minimum words), so their difference isolates the
    more-vs-less axis of the described attribute rather than a phrasing
    difference. Noun-style descriptions ("brightness", "height", "age")
    read best; adjective styles should use the explicit pole overrides.
    """
    description = normalize_text(description).rstrip(".!?")
    if not description:
        return "", ""
    return (
        "Extremely high {}, maximum {}.".format(description, description),
        "Extremely low {}, minimum {}.".format(description, description),
    )


def prefix_texts(prompt, sliders):
    """The tokenization ladder: prompt, then one more pole sentence per rung.

    Returns len == 1 + 2 * len(sliders); the final entry is the full text
    that gets encoded. Pole order per slider is increase then decrease.
    """
    prompt = str(prompt or "").strip()
    texts = [prompt]
    current = prompt
    first = True
    for slider in sliders:
        for sentence in (slider["plus_text"], slider["minus_text"]):
            separator = "\n\n" if first else "\n"
            current = (current + separator + sentence) if current else sentence
            texts.append(current)
            first = False
    return texts


def _row_ids(row):
    """Token ids for divergence comparison; slider sequences are text-only."""
    ids = []
    for item in row:
        elem = v9.qwen_tokens.token_elem(item)
        if isinstance(elem, dict):
            raise RuntimeError(
                "KG Concept Slider: the slider stack is text-only but the token "
                "row contains an embedded image; connect images through the "
                "V9/V10 reference stack instead."
            )
        ids.append(int(elem))
    return ids


def _first_divergence(previous_ids, current_ids):
    limit = min(len(previous_ids), len(current_ids))
    for i in range(limit):
        if previous_ids[i] != current_ids[i]:
            return i
    return limit


def pole_spans(token_rows):
    """Per-pole (start, end) token spans inside the FINAL row.

    `token_rows` is the ladder of first token rows, one per prefix text.
    Span k starts where row k first diverges from row k-1 and ends where
    row k+1 first diverges from row k (the next pole's start); the last
    span ends at the written content's end in the final row. In a
    text-only sequence token indices equal embedding positions.
    """
    if len(token_rows) < 2:
        return []
    id_rows = [_row_ids(row) for row in token_rows]
    divergences = [
        _first_divergence(id_rows[k - 1], id_rows[k]) for k in range(1, len(id_rows))
    ]
    _, _, content_end = v9.qwen_tokens.find_prompt_bounds(token_rows[-1], 0)

    spans = []
    for k, start in enumerate(divergences):
        stop = divergences[k + 1] if k + 1 < len(divergences) else content_end
        stop = max(start, min(stop, content_end))
        spans.append((start, stop))
    return spans
