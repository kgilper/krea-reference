"""Content-keyed study cache for the V10 stack encoder.

Deltas depend only on the token layout (prompt text, system prompt, and the
prepared reference images) — never on strengths, timing, or balance, which
are applied at compose time. Caching the base conditioning and each
ingredient's delta therefore makes slider tweaks compose-only: re-runs that
change only strengths skip every encoder forward pass.

Keys are content fingerprints (shape, dtype, and three order-sensitive sums
per image tensor), so edited images can never collide with stale entries.
The CLIP object is validated by weak reference; anything that cannot be
fingerprinted or weak-referenced simply bypasses the cache.
"""

import weakref
from collections import OrderedDict

import torch

# Two entries cover the common tuning loop (current setup plus the one the
# artist just stepped away from) without holding many conditioning-sized
# tensors alive.
MAX_ENTRIES = 2

_CACHE = OrderedDict()


def reset():
    """Drop every cached study (used by tests and low-memory situations)."""
    _CACHE.clear()


def _tensor_fingerprint(value):
    flat = value.float().reshape(-1)
    positions = torch.arange(flat.shape[0], dtype=flat.dtype, device=flat.device)
    return (
        "tensor",
        tuple(int(dim) for dim in value.shape),
        str(value.dtype),
        float(flat.sum().item()),
        float((flat * flat).sum().item()),
        float((flat * positions).sum().item()),
    )


def fingerprint_value(value):
    """Return a hashable content fingerprint, or None when uncacheable."""
    if value is None:
        return ("none",)
    if isinstance(value, (str, bytes, int, float, bool)):
        return ("plain", value)
    if torch.is_tensor(value):
        try:
            return _tensor_fingerprint(value)
        except Exception:
            return None
    return None


def make_key(clip, prompt_text, template_text, prepared_images):
    """Build the cache key for one encode context, or None when uncacheable."""
    image_prints = []
    for image in prepared_images:
        print_ = fingerprint_value(image)
        if print_ is None:
            return None
        image_prints.append(print_)
    return (id(clip), str(prompt_text), str(template_text), tuple(image_prints))


def lookup(key, clip):
    """Return the cached entry for key when its CLIP is still alive and same."""
    if key is None:
        return None
    entry = _CACHE.get(key)
    if entry is None:
        return None
    clip_ref = entry.get("clip_ref")
    if clip_ref is None or clip_ref() is not clip:
        _CACHE.pop(key, None)
        return None
    _CACHE.move_to_end(key)
    return entry


def store(key, clip, full_conditioning, deltas):
    """Insert or refresh a cache entry; silently skips uncacheable CLIPs."""
    if key is None:
        return
    try:
        clip_ref = weakref.ref(clip)
    except TypeError:
        return
    _CACHE[key] = {
        "clip_ref": clip_ref,
        "full": full_conditioning,
        "deltas": dict(deltas),
    }
    _CACHE.move_to_end(key)
    while len(_CACHE) > MAX_ENTRIES:
        _CACHE.popitem(last=False)
