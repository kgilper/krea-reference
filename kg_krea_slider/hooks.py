"""Multi-span muting hook for the Concept Slider stack.

Same mechanism as V9's muted_prompt_embeddings (zero the span's input
embeddings AND its attention mask for the duration of one encode, then
restore the model), generalized to a list of spans so the stack can mute
every pole except the one being studied. kg_krea_v9 is reused read-only
for the model accessor; its single-span hook is left untouched.
"""

from contextlib import contextmanager

from ._v9 import v9


@contextmanager
def muted_span_embeddings(clip, get_spans):
    """Zero a list of (start, end) embedding spans during one encode.

    `get_spans(tokens, embeds_info)` returns the spans to mute. Yields
    without patching when the model does not expose process_tokens.
    """
    clip_model = v9.clip_hooks.get_qwen_clip_model(clip)
    original = getattr(clip_model, "process_tokens", None)

    if original is None:
        yield
        return

    def patched_process_tokens(tokens, device):
        embeds, attention_mask, num_tokens, embeds_info = original(tokens, device)
        cloned = False
        for span_start, span_end in get_spans(tokens, embeds_info):
            start = min(max(0, int(span_start)), embeds.shape[1])
            end = min(max(start, int(span_end)), embeds.shape[1])
            if end > start:
                if not cloned:
                    embeds = embeds.clone()
                    attention_mask = attention_mask.clone()
                    cloned = True
                embeds[:, start:end] = 0.0
                attention_mask[:, start:end] = 0
        if cloned:
            num_tokens = [int(mask.sum().item()) for mask in attention_mask]
        return embeds, attention_mask, num_tokens, embeds_info

    clip_model.process_tokens = patched_process_tokens
    try:
        yield
    finally:
        clip_model.process_tokens = original


def encode_with_muted_spans(clip, tokens, spans):
    """Encode tokens with the given spans muted (plain encode when empty)."""
    if not spans:
        return clip.encode_from_tokens_scheduled(tokens)
    with muted_span_embeddings(clip, lambda _tokens, _embeds_info: spans):
        return clip.encode_from_tokens_scheduled(tokens)
