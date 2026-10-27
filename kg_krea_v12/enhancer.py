"""Owned integration over an installed, pinned Krea2T text-fusion helper.

The upstream numeric implementation stays in its separately installed package.
This module owns routing, admission, invocation and temporary hook cleanup.
No extra weights, sampler, phrase encoder or LoRA implementation is selected.
"""
from contextlib import contextmanager
import hashlib
import inspect
import math
from pathlib import Path
import sys
import threading
import types

from .ledger import TAP_WIDTH, TAPS
from .native import _signature
from .compatibility import verify_loaded_functions
from .diagnostics import current as current_diagnostic

ENHANCER_BLOB = 'c46e1c3ed244caaef231c580bb601ea935b3d1c7'
ENHANCER_SOURCE_PROFILES = {
    ENHANCER_BLOB: 'krea2t-basic-math-v1',
    '31e24388a8d495a524f46371659d3087e2302664': 'krea2t-basic-math-extra-registrations-v1',
}
CORE_FUSION_BLOB = 'a904e05e0053d38bda0fdbd70625cd8c5e9b70a2'
WRAPPER_KEY = 'kg_native_enhancer_v12'
_OTHER_KEYS = ('krea2t_prompt_adherence_enhancer', 'krea2t_prompt_adherence_enhancer_advanced')
_guard = threading.Lock()
_busy = set()
_MISSING = object()


def load_enhancer_host():
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get('ComfyUI-Krea2T-Enhancer')
    if cls is None:
        raise RuntimeError('V12 enhancer requires the pinned original Krea2T enhancer package')
    data = Path(inspect.getfile(cls)).read_bytes().replace(b'\r\n', b'\n')
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob not in ENHANCER_SOURCE_PROFILES:
        raise RuntimeError('V12 enhancer source revision is unverified')
    enhancer_blob = blob
    module = sys.modules[cls.__module__]
    helper = getattr(module, '_enhanced_txtfusion_forward', None)
    compatible = getattr(module, '_is_krea2_dm', None)
    if (not callable(helper) or not callable(compatible)
            or inspect.getfile(helper) != inspect.getfile(cls)
            or inspect.getfile(compatible) != inspect.getfile(cls)):
        raise RuntimeError('V12 enhancer helper does not belong to the pinned source')
    verify_loaded_functions(module, data, (
        '_is_krea2_dm', '_chunk_gains', '_run_refiners',
        '_run_txtfusion_parts', '_enhanced_txtfusion_forward'))
    profile = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.5, 5.0, 1.1, 4.0, 1.0)
    expected_constants = {'KREA2_TAP_LAYERS': TAPS, 'KREA2_TAP_DIM': TAP_WIDTH,
                          'KREA2_CHUNK_COUNT': 24, 'KREA2_CHUNK_DIM': 1280,
                          'ENHANCER_PROFILE_12': profile, 'ENHANCER_CHUNK_PROFILE': profile + profile,
                          'ENHANCER_GLOBAL_MULTIPLIER': 15.0, 'TXTFUSION_TOKEN_REL_CAP': 0.75}
    if any(getattr(module, name, None) != value for name, value in expected_constants.items()):
        raise RuntimeError('V12 loaded enhancer constants differ from admitted source')
    import comfy.ldm.krea2.model as core
    data = Path(inspect.getfile(core.TextFusionTransformer)).read_bytes().replace(b'\r\n', b'\n')
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != CORE_FUSION_BLOB:
        raise RuntimeError('V12 enhancer native text-fusion source revision is unverified')
    verify_loaded_functions(core, data, ('TextFusionTransformer.forward', 'TextFusionBlock.forward'))
    fusion_class, block_class = core.TextFusionTransformer, core.TextFusionBlock
    fusion_forward, block_forward = fusion_class.forward, block_class.forward

    def checked_compatible(dm):
        if not compatible(dm):
            return False
        _verify_fusion_instances(dm, fusion_class, block_class, fusion_forward, block_forward)
        return True

    return helper, checked_compatible, enhancer_blob


def _verify_fusion_instances(dm, fusion_class, block_class, fusion_forward, block_forward):
    """Bind the actual modules invoked by the helper, before installing our hook."""
    fusion = dm.txtfusion
    if type(fusion) is not fusion_class:
        raise RuntimeError('V12 enhancer actual fusion class is unverified')
    layers, refiners = fusion.layerwise_blocks, fusion.refiner_blocks
    if len(layers) != 2 or len(refiners) != 2:
        raise RuntimeError('V12 enhancer actual fusion block layout is unverified')
    for obj, cls, forward in [(fusion, fusion_class, fusion_forward),
                              *((block, block_class, block_forward) for block in (*layers, *refiners))]:
        bound = getattr(obj, 'forward', None)
        if (type(obj) is not cls or not isinstance(bound, types.MethodType)
                or bound.__self__ is not obj or bound.__func__ is not forward
                or any(name in vars(obj) for name in ('forward', '__call__', '_call_impl', '_wrapped_call_impl'))
                or getattr(obj, '_compiled_call_impl', None) is not None
                or getattr(obj, '_forward_hooks', None) or getattr(obj, '_forward_pre_hooks', None)):
            raise RuntimeError('V12 enhancer actual fusion/block forward path is unverified')


@contextmanager
def _fusion_lease(dm):
    keys = (id(dm), id(dm.txtfusion))
    with _guard:
        if any(key in _busy for key in keys):
            raise RuntimeError('V12 enhancer shared MODEL/text fusion is already active')
        _busy.update(keys)
    try:
        yield
    finally:
        with _guard:
            _busy.difference_update(keys)


def _wrappers(options):
    return options.get('transformer_options', {}).get('wrappers', {}).get('diffusion_model', {})


def _check_architecture(dm, compatible):
    if (not compatible(dm) or int(getattr(dm, 'txtlayers', 0)) != len(TAPS)
            or int(getattr(dm, 'txtdim', 0)) != TAP_WIDTH
            or any(not hasattr(dm.txtfusion, key) for key in ('layerwise_blocks', 'projector', 'refiner_blocks'))):
        raise RuntimeError('V12 enhancer requires the verified Krea2 text-fusion architecture')


def apply_enhancer(model, enabled=False, strength=1.0):
    if not isinstance(enabled, bool):
        raise ValueError('V12 enhancer enabled must be boolean')
    if (isinstance(strength, bool) or not isinstance(strength, (float, int))
            or not math.isfinite(strength) or not 0 <= strength <= 2):
        raise ValueError('V12 enhancer strength must be finite within [0, 2]')
    if not enabled or strength == 0:
        return model, 'Krea native enhancer V12: OFF; original MODEL retained.'
    helper, compatible, enhancer_blob = load_enhancer_host()
    dm = model.model.diffusion_model
    _check_architecture(dm, compatible)
    original_options_signature = _signature(model.model_options)
    original_wrappers = _wrappers(model.model_options)
    if any(key in original_wrappers for key in (WRAPPER_KEY, *_OTHER_KEYS)):
        raise RuntimeError('V12 enhancer refuses an already enhanced MODEL')
    if 'krea2_edit' in original_wrappers:
        raise RuntimeError('V12 enhancer must precede the native edit patch, which bypasses inner wrappers')
    config = {'enabled': True, 'strength': float(strength), 'source_blob': enhancer_blob}

    def wrapper(executor, *args, **kwargs):
        options = kwargs.get('transformer_options')
        if options is None:
            options = next((arg for arg in reversed(args) if isinstance(arg, dict)), {})
        if options.get(WRAPPER_KEY) != config:
            raise RuntimeError('V12 enhancer configuration changed after attachment')
        wrappers = options.get('wrappers', {}).get('diffusion_model', {})
        own = wrappers.get(WRAPPER_KEY, [])
        order = list(wrappers)
        if (len(own) != 1 or own[0] is not wrapper
                or any(key in wrappers for key in _OTHER_KEYS)
                or 'krea2_edit' in wrappers and order.index(WRAPPER_KEY) > order.index('krea2_edit')):
            raise RuntimeError('V12 enhancer wrapper ownership/order changed')
        if executor.class_obj is not dm:
            raise RuntimeError('V12 enhancer belongs to a different diffusion MODEL')
        with _fusion_lease(dm):
            _check_architecture(dm, compatible)
            fusion = dm.txtfusion
            if ('forward' in vars(fusion)
                    or hasattr(fusion, '_krea2t_enhancer_original_forward')
                    or hasattr(fusion, '_krea2t_enhancer_advanced_original_forward')):
                raise RuntimeError('V12 enhancer refuses existing temporary text-fusion hooks')
            calls = 0

            def enhanced(x, mask=None, transformer_options=None):
                nonlocal calls
                shape = tuple(getattr(x, 'shape', ()))
                if len(shape) != 4 or shape[0] < 1 or shape[1] < 1 or shape[2:] != (len(TAPS), TAP_WIDTH):
                    raise RuntimeError('V12 enhancer received an unexpected native text-fusion tensor')
                calls += 1
                result, _ = helper(fusion, x, mask=mask, transformer_options=transformer_options,
                                   strength=float(strength), collect_debug=False)
                if tuple(getattr(result, 'shape', ())) != (*shape[:2], TAP_WIDTH):
                    raise RuntimeError('V12 enhancer helper returned an unexpected native text-fusion tensor')
                diagnostic = current_diagnostic()
                if diagnostic is not None:
                    diagnostic.fusion(dm, x, result)
                return result

            try:
                fusion.forward = enhanced
                output = executor(*args, **kwargs)
                if calls == 0:
                    raise RuntimeError('V12 enhancer was bypassed; native text fusion did not execute')
                return output
            finally:
                if vars(fusion).get('forward', _MISSING) is enhanced:
                    del fusion.forward
                else:
                    raise RuntimeError('V12 enhancer detected a foreign hook mutation; foreign state preserved')

    patched = model.clone()
    if patched is model:
        raise RuntimeError('V12 enhancer requires an independent native MODEL clone')
    to = patched.model_options.setdefault('transformer_options', {})
    to[WRAPPER_KEY] = config.copy()
    patched.add_wrapper_with_key('diffusion_model', WRAPPER_KEY, wrapper)
    if _signature(model.model_options) != original_options_signature:
        raise RuntimeError('V12 enhancer clone changed original MODEL wrapper ownership')
    return patched, ('Krea native enhancer V12: pinned text-fusion helper attached; '
                     'strength {}. Runtime effect requires sampling verification.').format(float(strength))
