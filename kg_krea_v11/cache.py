"""Bounded, revision-aware V11 studies; no changes to older caches."""
import hashlib
import json
import weakref
from collections import OrderedDict

_CACHE = OrderedDict()
MAX_ENTRIES = 2


def digest_bytes(shape, dtype, data):
    digest = hashlib.sha256()
    digest.update(json.dumps([list(shape), str(dtype)], separators=(',', ':')).encode())
    digest.update(b'\0')
    digest.update(data)
    return digest.hexdigest()


def image_digest(image):
    # Byte view also supports bfloat16, which NumPy cannot represent directly.
    import torch
    value = image.detach().cpu().contiguous()
    return digest_bytes(value.shape, value.dtype, value.view(torch.uint8).numpy().tobytes())


def make_key(clip, *content, images=()):
    patcher = getattr(clip, 'patcher', None)
    revision = getattr(patcher, 'patches_uuid', None)
    # Unknown hosts are uncacheable: identity alone cannot prove model state.
    if revision is None:
        return None
    try:
        weakref.ref(clip)
        return (id(clip), id(getattr(clip, 'cond_stage_model', None)), str(revision),
                str(getattr(clip, 'layer_idx', None)), *content,
                tuple(image_digest(image) for image in images))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return None


def lookup(key, clip):
    entry = _CACHE.get(key) if key is not None else None
    if entry is None:
        return None
    if entry['clip_ref']() is not clip:
        _CACHE.pop(key, None)
        return None
    _CACHE.move_to_end(key)
    return entry


def store(key, clip, full, deltas):
    if key is None:
        return
    _CACHE[key] = {'clip_ref': weakref.ref(clip), 'full': full, 'deltas': dict(deltas)}
    _CACHE.move_to_end(key)
    while len(_CACHE) > MAX_ENTRIES:
        _CACHE.popitem(last=False)


def reset():
    _CACHE.clear()
