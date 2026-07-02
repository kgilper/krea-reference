"""Temporary hooks into the Krea (Qwen) CLIP model during encoding.

The stack encoder isolates ingredient contributions by re-encoding the same
tokens with one ingredient muted or rescaled. These context managers patch
the loaded CLIP model for the duration of a single encode and always restore
the original methods, so the model is untouched between calls.
"""

from contextlib import contextmanager


def get_qwen_clip_model(clip):
    """Return the inner Qwen CLIP model, or None when the shape is unknown."""
    cond_stage_model = getattr(clip, "cond_stage_model", None)
    clip_attr = getattr(cond_stage_model, "clip", None)
    return getattr(cond_stage_model, clip_attr, None) if clip_attr is not None else None


@contextmanager
def scaled_image_embeddings(clip, image_scales=None):
    """Scale image embeds during encode, per reference index when tagged.

    `image_scales` maps a card's kg_reference_index to a strength; untagged
    or unmapped images fall back to their kg_reference_strength (default 1.0).
    Yields without patching when the model does not expose preprocess_embed.
    """
    clip_model = get_qwen_clip_model(clip)
    transformer = getattr(clip_model, "transformer", None)
    original = getattr(transformer, "preprocess_embed", None)

    if original is None:
        yield
        return

    def patched_preprocess_embed(embed, device):
        emb, extra = original(embed, device)
        strength = 1.0
        if isinstance(embed, dict) and embed.get("type") == "image":
            image_index = embed.get("kg_reference_index", None)
            if image_scales is not None and image_index in image_scales:
                strength = float(image_scales[image_index])
            else:
                strength = float(embed.get("kg_reference_strength", 1.0))

        if strength != 1.0 and emb is not None:
            emb = emb * strength
            if isinstance(extra, dict) and "deepstack" in extra:
                extra = extra.copy()
                extra["deepstack"] = [d * strength for d in extra["deepstack"]]

        return emb, extra

    transformer.preprocess_embed = patched_preprocess_embed
    try:
        yield
    finally:
        transformer.preprocess_embed = original


@contextmanager
def muted_prompt_embeddings(clip, get_prompt_bounds):
    """Zero the written-prompt span (embeds and attention) during encode.

    `get_prompt_bounds(tokens, embeds_info)` returns the (start, end)
    embedding positions to mute. Yields without patching when the model does
    not expose process_tokens.
    """
    clip_model = get_qwen_clip_model(clip)
    original = getattr(clip_model, "process_tokens", None)

    if original is None:
        yield
        return

    def patched_process_tokens(tokens, device):
        embeds, attention_mask, num_tokens, embeds_info = original(tokens, device)
        start, end = get_prompt_bounds(tokens, embeds_info)
        start = min(max(0, start), embeds.shape[1])
        end = min(max(start, end), embeds.shape[1])

        if end > start:
            embeds = embeds.clone()
            attention_mask = attention_mask.clone()
            embeds[:, start:end] = 0.0
            attention_mask[:, start:end] = 0
            num_tokens = [int(mask.sum().item()) for mask in attention_mask]

        return embeds, attention_mask, num_tokens, embeds_info

    clip_model.process_tokens = patched_process_tokens
    try:
        yield
    finally:
        clip_model.process_tokens = original


def encode_with_controls(clip, tokens, image_scales=None, mute_prompt=False, get_prompt_bounds=None):
    """Encode tokens with the requested image scaling / prompt muting hooks."""
    with scaled_image_embeddings(clip, image_scales):
        if mute_prompt:
            with muted_prompt_embeddings(clip, get_prompt_bounds):
                return clip.encode_from_tokens_scheduled(tokens)
        return clip.encode_from_tokens_scheduled(tokens)
