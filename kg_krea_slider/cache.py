"""Content-keyed study cache for the Concept Slider stack.

The base conditioning and every slider axis depend only on the encoded
text (prompt plus pole sentences) - never on slider values or reach,
which are applied at compose time. Caching them makes slider drags
compose-only: re-runs that change only values skip every encoder forward
pass, the same study-reuse behavior the V10 stack ships. Slider values do
not appear in the encoded text, so the common tuning loop (drag one
slider, re-render) is always a cache hit.

Keys are (CLIP identity, full text); the CLIP object is validated by weak
reference like the V10 cache, so a reloaded model can never serve stale
studies.
"""

import weakref
from collections import OrderedDict

# Two entries cover the common tuning loop (current setup plus the one the
# artist just stepped away from) without holding many conditioning-sized
# tensors alive.
MAX_ENTRIES = 2

_CACHE = OrderedDict()


def reset():
    """Drop every cached study (used by tests and low-memory situations)."""
    _CACHE.clear()


def make_key(clip, full_text):
    return (id(clip), str(full_text))


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


def store(key, clip, base_conditioning, axes):
    """Insert or refresh a cache entry; silently skips uncacheable CLIPs."""
    if key is None:
        return
    try:
        clip_ref = weakref.ref(clip)
    except TypeError:
        return
    _CACHE[key] = {
        "clip_ref": clip_ref,
        "base": base_conditioning,
        "axes": dict(axes),
    }
    _CACHE.move_to_end(key)
    while len(_CACHE) > MAX_ENTRIES:
        _CACHE.popitem(last=False)
