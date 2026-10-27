"""Exclusive, fail-closed encoder studies; no persistent model patches."""
from contextlib import contextmanager
import math
import threading

from .ledger import OWNER_KEY, TAPS, VISION_DEPTH
from .diagnostics import current as current_diagnostic

_guard = threading.Lock()
_busy = set()
_owner_threads = {}
_MISSING = object()


def encoder_objects(clip):
    stage = getattr(clip, 'cond_stage_model', None)
    key = getattr(stage, 'clip', None)
    model = getattr(stage, key, None) if isinstance(key, str) else None
    transformer = getattr(model, 'transformer', None)
    if model is None or transformer is None:
        raise RuntimeError('V12 requires a native Krea Qwen encoder')
    return model, transformer


@contextmanager
def encoder_lease(clip):
    """Reject overlapping owners, including clones sharing either inner object.

    Uncooperative external code cannot be locked by this plugin. Instance hook
    overrides are rejected on entry; changes during a study are detected and
    preserved on exit instead of overwriting foreign state.
    """
    model, transformer = encoder_objects(clip)
    keys = (id(model), id(transformer))
    with _guard:
        if any(key in _busy for key in keys):
            raise RuntimeError('V12 encoder is already leased by another study')
        _busy.update(keys)
        for key in keys:
            _owner_threads[key] = threading.get_ident()
    try:
        yield model, transformer
    finally:
        with _guard:
            _busy.difference_update(keys)
            for key in keys:
                _owner_threads.pop(key, None)


@contextmanager
def controlled_encode(model, transformer, ledger, muted_poles=(), image_scales=None, max_tokens=8192):
    """One coherent hook pair for text muting and initial/deepstack image gains."""
    with _guard:
        if any(_owner_threads.get(id(obj)) != threading.get_ident() for obj in (model, transformer)):
            raise RuntimeError('V12 hook installation requires the current thread encoder lease')
    layers = getattr(model, 'layer', None)
    if not isinstance(layers, (tuple, list)) or tuple(layers) != TAPS:
        raise RuntimeError('V12 requires the verified Krea output tap layout')
    scales = dict(image_scales or {})
    if set(scales) - set(ledger.owners):
        raise ValueError('V12 image scale names an unowned reference')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in scales.values()):
        raise ValueError('V12 image scales must be finite numbers')
    if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(ledger.poles)
           for i in muted_poles):
        raise ValueError('V12 invalid pole span index')
    hooks = [(model, 'process_tokens'), (transformer, 'preprocess_embed')]
    originals = [getattr(obj, name, None) for obj, name in hooks]
    if any(not callable(method) for method in originals):
        raise RuntimeError('V12 requires process_tokens and preprocess_embed hooks')
    if any(vars(obj).get(name, _MISSING) is not _MISSING for obj, name in hooks):
        raise RuntimeError('V12 refuses an encoder with existing instance hooks')
    observation = {'ledger': None, 'images': [], 'process_calls': 0}

    def preprocess(embed, device):
        emb, extra = originals[1](embed, device)
        if not isinstance(embed, dict) or embed.get('type') != 'image':
            raise RuntimeError('V12 encountered an unowned embedded input')
        owner = embed.get(OWNER_KEY)
        if owner not in ledger.owners or owner in observation['images']:
            raise RuntimeError('V12 image preparation owner/order mismatch')
        if owner != ledger.owners[len(observation['images'])]:
            raise RuntimeError('V12 image order differs from its native preparation')
        observation['images'].append(owner)
        if (emb is None or not isinstance(extra, dict) or extra.get('grid') is None
                or not isinstance(extra.get('deepstack'), (tuple, list))
                or len(extra['deepstack']) != VISION_DEPTH):
            raise RuntimeError('V12 missing native image/deepstack preparation')
        gain = scales.get(owner, 1.0)
        diagnostic = current_diagnostic()
        if diagnostic is not None:
            diagnostic.image(owner, emb, extra)
        if gain != 1.0:
            emb = emb * gain
            extra = {**extra, 'deepstack': [feature * gain for feature in extra['deepstack']]}
        return emb, extra

    def process(tokens, device):
        observation['process_calls'] += 1
        if observation['process_calls'] != 1:
            raise RuntimeError('V12 does not support repeated/scheduled token preparations')
        embeds, mask, counts, info = originals[0](tokens, device)
        if len(embeds.shape) != 3 or embeds.shape[0] != 1 or tuple(mask.shape) != tuple(embeds.shape[:2]):
            raise RuntimeError('V12 requires a single native embedding batch and aligned mask')
        expanded = ledger.expand(tokens, info, embeds.shape[1])
        if expanded.input_length > max_tokens:
            raise RuntimeError('V12 expanded context budget exceeded before transformer evaluation')
        if observation['images'] != list(ledger.owners):
            raise RuntimeError('V12 host bypassed image preparation')
        observation['ledger'] = expanded
        if muted_poles:
            embeds, mask = embeds.clone(), mask.clone()
            for index in muted_poles:
                start, end = expanded.poles[index]
                embeds[:, start:end] = 0.0
                mask[:, start:end] = 0
            counts = [int(row.sum().item()) for row in mask]
        return embeds, mask, counts, info

    replacements = [process, preprocess]
    installed = []
    try:
        for (obj, name), replacement in zip(hooks, replacements):
            setattr(obj, name, replacement)
            installed.append((obj, name, replacement))
        yield observation
        if observation['ledger'] is None:
            raise RuntimeError('V12 host skipped process_tokens; no study is valid')
    finally:
        conflict = False
        for obj, name, replacement in reversed(installed):
            if vars(obj).get(name, _MISSING) is replacement:
                delattr(obj, name)
            else:
                conflict = True
        if conflict:
            raise RuntimeError('V12 detected a foreign hook mutation; foreign state preserved')
