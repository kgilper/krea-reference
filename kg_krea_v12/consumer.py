"""Thin, versioned consumer over the original Comfy guider and Euler sampler.

No solver, CFG implementation, model forward or inpaint path is copied here.
Source compatibility is checked before active native evaluation is permitted.
"""
from contextlib import contextmanager
import hashlib
import inspect
import math
from numbers import Real
from pathlib import Path
import threading
import uuid

from .native import GROUNDING_BLOB, _signature
from .studies import NativeStudies

SAMPLERS_BLOB = 'a7cc3419e325e7d55aac8c7d5ce6d65f620fc511'
EULER_SHA256 = 'cfc4221ed0bc1f84a6f5689d3ec440cad3008c2541ab8f5e2599d1a73fac74ce'
HELPERS_SHA256 = '53c82235bfea0c4edf3cd5219f080c44c45ac1c9a6c3171f2aae151e18b56b91'
MODEL_BASE_SHA256 = 'e7d08a4450287c76994b109437fbd03d721cf373fc8214bb9c30c478db060ffe'
_lock = threading.Lock()
_busy = set()
_MISSING = object()
_PHASE_KEYS = ('kg_native_v12_early', 'kg_native_v12_final')
_UNSUPPORTED_COND = frozenset(('hooks', 'control', 'gligen', 'model_conds', 'mask', 'area',
                             'default', 'start_percent', 'end_percent', 'clip_start_percent',
                             'clip_end_percent', 'timestep_start', 'timestep_end'))


def _source_bytes(obj):
    return Path(inspect.getfile(obj)).read_bytes().replace(b'\r\n', b'\n')


def load_consumer_host():
    import comfy.samplers as samplers
    import comfy.sampler_helpers as helpers
    import comfy.model_base as model_base
    import comfy.k_diffusion.sampling as euler
    data = _source_bytes(samplers)
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != SAMPLERS_BLOB:
        raise RuntimeError('V12 native guider/sampler source revision is unverified')
    for module, expected in ((euler, EULER_SHA256), (helpers, HELPERS_SHA256), (model_base, MODEL_BASE_SHA256)):
        if hashlib.sha256(_source_bytes(module)).hexdigest() != expected:
            raise RuntimeError('V12 native evaluation dependency source revision is unverified')
    return samplers, euler, model_base


def _scalar(value):
    if not isinstance(value, Real):
        if not callable(getattr(value, 'numel', None)) or value.numel() != 1:
            raise RuntimeError('V12 requires one actual sigma value per native evaluation')
        value = value.item()
    if isinstance(value, bool) or not math.isfinite(value):
        raise RuntimeError('V12 native sigma must be finite')
    return float(value)


def _schedule(sigmas):
    values = sigmas.tolist() if callable(getattr(sigmas, 'tolist', None)) else sigmas
    if not isinstance(values, (tuple, list)) or not 2 <= len(values) <= 10001:
        raise RuntimeError('V12 needs a bounded actual accepted sigma schedule')
    values = tuple(_scalar(value) for value in values)
    if values[-1] < 0 or any(a <= b for a, b in zip(values, values[1:])):
        raise RuntimeError('V12 native schedule must be strictly decreasing and nonnegative')
    return values


def _validate_native_pair(guider, studies):
    if guider.model_patcher is not studies.context.native['model']:
        raise RuntimeError('V12 native guider belongs to a different MODEL')
    if set(guider.original_conds) != {'positive', 'negative'}:
        raise RuntimeError('V12 native guider already owns extra conditioning branches')
    for name in ('positive', 'negative'):
        actual, original = guider.original_conds[name], studies.context.native[name]
        if len(actual) != len(original):
            raise RuntimeError('V12 native guider conditioning pair differs from its context')
        for converted, (value, metadata) in zip(actual, original):
            expected_keys = set(metadata) | {'cross_attn', 'model_conds', 'uuid'}
            if (not isinstance(converted, dict) or set(converted) != expected_keys
                    or type(converted.get('model_conds')) is not dict or converted['model_conds']
                    or not isinstance(converted.get('uuid'), uuid.UUID)):
                raise RuntimeError('V12 actual native guider has unsupported converted conditioning additions')
            if converted.get('cross_attn') is not value:
                raise RuntimeError('V12 native guider cross attention differs from its context')
            if any(key in metadata for key in _UNSUPPORTED_COND):
                raise RuntimeError('V12 initial consumer does not support conditioned hooks/areas/masks/control')
            if any(_signature(converted.get(key)) != _signature(item) for key, item in metadata.items()):
                raise RuntimeError('V12 native guider metadata differs from its context')
    for phase in studies.phases[1:]:
        for _, metadata in phase['positive']:
            if any(key in metadata for key in _UNSUPPORTED_COND):
                raise RuntimeError('V12 initial consumer does not support conditioned hooks/areas/masks/control')


def _validate_grounded_wrapper(studies):
    if studies.context.sources[0] is None:
        return
    options = getattr(studies.context.native['model'], 'model_options', {})
    wrappers = options.get('transformer_options', {}).get('wrappers', {}).get('diffusion_model', {})
    owned = wrappers.get('krea2_edit', [])
    if len(owned) != 1 or getattr(owned[0], '__qualname__', '') != 'Krea2EditModelPatch.patch.<locals>.wrapper':
        raise RuntimeError('V12 grounded consumer requires the original single krea2_edit wrapper')
    data = _source_bytes(owned[0])
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != GROUNDING_BLOB:
        raise RuntimeError('V12 grounded MODEL wrapper source revision is unverified')


@contextmanager
def native_model_preparation_lease(model):
    """Exclude owned native reconstruction/VAE priming from active consumption."""
    key = id(getattr(model, 'model', model))
    with _lock:
        if key in _busy:
            raise RuntimeError('V12 native MODEL is busy; owned reconstruction cannot overlap sampling')
        _busy.add(key)
    try:
        yield
    finally:
        with _lock:
            _busy.discard(key)


@contextmanager
def _guider_lease(guider):
    keys = (id(guider), id(guider.model_patcher.model))
    with _lock:
        if any(key in _busy for key in keys):
            raise RuntimeError('V12 native guider/model already has an active consumer')
        _busy.update(keys)
    try:
        yield
    finally:
        with _lock:
            _busy.difference_update(keys)


class NativePhaseGuider:
    """GUIDER protocol proxy: delegate sample to the unchanged native guider.

    Phase conditionings enter the native conversion/preparation/load path as
    additional simple full-frame positive contexts. Only the positive selection
    at predict_noise changes; native negative, CFG and model callbacks run once.
    """
    def __init__(self, guider, studies, host):
        self.native_guider, self.studies, self.host = guider, studies, host
        self.model_patcher = guider.model_patcher

    def sample(self, noise, latent_image, sampler, sigmas, denoise_mask=None, callback=None,
               disable_pbar=False, seed=None):
        studies, guider = self.studies, self.native_guider
        studies.context.verify()
        _validate_native_pair(guider, studies)
        _validate_grounded_wrapper(studies)
        samplers, euler, model_base = self.host
        if type(guider) is not samplers.CFGGuider or type(guider.model_patcher.model) is not model_base.Krea2:
            raise RuntimeError('V12 consumer requires the pinned native Krea2 CFGGuider')
        if (type(sampler) is not samplers.KSAMPLER
                or sampler.sampler_function not in (euler.sample_euler, euler.sample_euler_ancestral)
                or sampler.extra_options or any(k != 'random' or v is not False for k, v in sampler.inpaint_options.items())):
            raise RuntimeError('V12 consumer supports only unchanged native Euler/ancestral defaults')
        schedule = _schedule(sigmas)
        native_target = studies.context.native['target_latent']
        if not isinstance(native_target, dict) or latent_image is not native_target.get('samples'):
            raise RuntimeError('V12 consumer requires the original native target latent samples')
        native_mask = studies.context.native['noise_mask']
        if denoise_mask is not native_mask or native_target.get('noise_mask') is not native_mask:
            raise RuntimeError('V12 consumer requires the original native latent noise mask')
        if not getattr(latent_image, 'shape', ()) or latent_image.shape[0] != 1 or noise.shape != latent_image.shape:
            raise RuntimeError('V12 initial native consumer requires one matching latent/noise batch')
        if 'predict_noise' in vars(guider):
            raise RuntimeError('V12 native guider already has an instance prediction hook')
        with _guider_lease(guider):
            original_conds = guider.original_conds
            original_predict = guider.predict_noise
            state = {'next': 0, 'callbacks': 0, 'predicting': False, 'processed': {}}
            phase_signature = None
            owner_thread = threading.get_ident()
            owned_original = None
            owned_phase_entries = {}

            def predict(x, timestep, model_options=None, seed=None):
                studies.context.verify()
                index = state['next']
                if (threading.get_ident() != owner_thread or state['predicting']
                        or index >= len(schedule) - 1 or _scalar(timestep) != schedule[index]):
                    raise RuntimeError('V12 native evaluation does not match the accepted active step')
                if phase_signature != _signature(guider.original_conds):
                    raise RuntimeError('V12 detected foreign native conditioning mutation')
                bundle = studies.for_step(self.model_patcher, index, len(schedule) - 1)
                if not state['processed']:
                    state['processed'] = {key: guider.conds[key] for key in _PHASE_KEYS if key in guider.conds}
                previous = guider.conds['positive']
                selected = previous
                state['predicting'] = True
                try:
                    if bundle is not studies.context.native:
                        phase = 0 if index / (len(schedule) - 1) < studies.phases[0] else 1
                        selected = guider.conds[_PHASE_KEYS[phase]]
                        guider.conds['positive'] = selected
                    result = original_predict(x, timestep, model_options=model_options, seed=seed)
                    state['next'] += 1
                    return result
                finally:
                    state['predicting'] = False
                    if guider.conds.get('positive') is not selected:
                        raise RuntimeError('V12 foreign processed-positive mutation detected; foreign state preserved')
                    guider.conds['positive'] = previous

            def accepted_step(index, denoised, x, total_steps):
                if (index != state['callbacks'] or state['next'] != index + 1
                        or total_steps != len(schedule) - 1):
                    raise RuntimeError('V12 native sampler callback does not identify the accepted step')
                state['callbacks'] += 1
                if callback is not None:
                    return callback(index, denoised, x, total_steps)

            try:
                guider.original_conds = original_conds.copy()
                owned_original = guider.original_conds
                for key, phase in zip(_PHASE_KEYS, studies.phases[1:]):
                    if phase is not studies.context.native:
                        guider.inner_set_conds({key: phase['positive']})
                        owned_phase_entries[key] = guider.original_conds[key]
                phase_signature = _signature(guider.original_conds)
                guider.predict_noise = predict
                output = guider.sample(noise, latent_image, sampler, sigmas, denoise_mask=denoise_mask,
                                       callback=accepted_step, disable_pbar=disable_pbar, seed=seed)
                if state['next'] != len(schedule) - 1 or state['callbacks'] != len(schedule) - 1:
                    raise RuntimeError('V12 native sampler did not complete the accepted active schedule')
                studies.context.verify()
                return output
            finally:
                conflict = vars(guider).get('predict_noise', _MISSING) not in (_MISSING, predict)
                if vars(guider).get('predict_noise', _MISSING) is predict:
                    del guider.predict_noise
                if phase_signature is not None and _signature(guider.original_conds) != phase_signature:
                    conflict = True
                processed = getattr(guider, 'conds', None)
                if isinstance(processed, dict):
                    for key, original_entries in owned_phase_entries.items():
                        current = processed.get(key)
                        owned = state['processed'].get(key, _MISSING)
                        # Native preparation copies entry dictionaries while
                        # retaining their conversion UUIDs and cross attention.
                        # This also identifies owned entries if failure happens
                        # before the first accepted native prediction.
                        derived = (isinstance(current, list) and len(current) == len(original_entries)
                                   and all(c.get('uuid') is o.get('uuid') and c.get('cross_attn') is o.get('cross_attn')
                                           for c, o in zip(current, original_entries)))
                        if current is owned or derived:
                            processed.pop(key)
                        elif key in processed:
                            conflict = True
                if not conflict:
                    guider.original_conds = original_conds
                elif guider.original_conds is owned_original:
                    for key, owned in owned_phase_entries.items():
                        if guider.original_conds.get(key) is owned:
                            guider.original_conds.pop(key)
                if conflict:
                    raise RuntimeError('V12 foreign guider mutation detected; foreign state preserved')


def bind_native_guider(studies, guider):
    if not isinstance(studies, NativeStudies):
        raise ValueError('V12 native consumer requires actual owned studies')
    studies.context.verify()
    if getattr(guider, 'model_patcher', None) is not studies.context.native['model']:
        raise RuntimeError('V12 native guider belongs to a different MODEL')
    if not studies.active:
        return guider
    host = load_consumer_host()
    _validate_native_pair(guider, studies)
    _validate_grounded_wrapper(studies)
    return NativePhaseGuider(guider, studies, host)
