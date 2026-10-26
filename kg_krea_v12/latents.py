"""Own the native target preparation boundary without replacing native math."""
from dataclasses import dataclass, replace
import inspect
from pathlib import Path

from .compatibility import _ast_fingerprint, _lookup, _source_maps, verify_loaded_functions
from .native import NativeContext, _signature, context_signature

PROVENANCE_KEY = 'kg_native_v12_target_preparation'
_SAMPLE_PINS = {'fix_empty_latent_channels': '2ea7af39c924e442d1d5204ae82c9ee9eed2c684dc72a486e95df55ecc05332b'}
_UTILS_PINS = {
    'repeat_to_batch_size': 'b4537d24a8494c5259eac72f2398550bfa396a2b48a9e1dac5f7207d5497ffaf',
    'common_upscale': '32dc30d1611b33ea16c21f6b56c184895dcf4996503b7b7918560031f1a8360b',
}
_FORMAT_PINS = {'LatentFormat.fix_empty_latent': '048115b7383529fd85a0c72cff703b826a12ceb11cc05040285730ba778713d8'}
_FORMAT_VALUES = dict(latent_channels=16, latent_dimensions=3,
                      spacial_downscale_ratio=8, temporal_downscale_ratio=4)


def _verified_functions(module, pins):
    source = Path(inspect.getfile(module)).read_bytes()
    _, definitions = _source_maps(source)
    if any(name not in definitions or _ast_fingerprint(definitions[name]) != expected for name, expected in pins.items()):
        raise RuntimeError('V12 native target preparation source is unverified')
    verify_loaded_functions(module, source, tuple(pins))
    bindings = []
    for name in pins:
        function = _lookup(module, name)
        if function.__globals__ is not vars(module):
            raise RuntimeError('V12 native target preparation globals differ')
        bindings.append((module, name, function, function.__code__))
    return tuple(bindings)


@dataclass(frozen=True)
class NativeLatentHost:
    sample_module: object
    utils_module: object
    formats_module: object
    comfy_module: object
    format: object
    format_class: object
    base_format_class: object
    tensor_type: object
    bindings: tuple

    def verify(self, model):
        fmt = self.format
        if (model.get_model_object('latent_format') is not fmt
                or type(fmt) is not self.format_class
                or self.formats_module.Wan21 is not self.format_class
                or self.formats_module.LatentFormat is not self.base_format_class
                or self.format_class.__bases__ != (self.base_format_class,)
                or self.sample_module.__dict__.get('comfy') is not self.comfy_module
                or self.comfy_module.utils is not self.utils_module
                or any(name in vars(fmt) for name in (*_FORMAT_VALUES, 'fix_empty_latent'))
                or any(type(getattr(fmt, name, None)) is not int or getattr(fmt, name) != value
                       for name, value in _FORMAT_VALUES.items())
                or getattr(fmt.fix_empty_latent, '__func__', None) is not self.base_format_class.fix_empty_latent):
            raise RuntimeError('V12 native Krea target latent format changed or is unsupported')
        for module, name, function, code in self.bindings:
            if _lookup(module, name) is not function or function.__code__ is not code:
                raise RuntimeError('V12 native target preparation function changed')


def load_latent_host(model):
    import torch
    import comfy
    import comfy.sample as sample
    import comfy.utils as utils
    import comfy.latent_formats as formats
    from .consumer import load_consumer_host
    _, _, model_base = load_consumer_host()
    if type(model.model) is not model_base.Krea2:
        raise RuntimeError('V12 target preparation requires the pinned native Krea2 MODEL')
    bindings = (_verified_functions(sample, _SAMPLE_PINS)
                + _verified_functions(utils, _UTILS_PINS)
                + _verified_functions(formats, _FORMAT_PINS))
    host = NativeLatentHost(sample, utils, formats, comfy, model.get_model_object('latent_format'),
                            formats.Wan21, formats.LatentFormat, torch.Tensor, bindings)
    host.verify(model)
    return host


def _model_signature(model):
    return _signature((model, getattr(model, 'patches_uuid', None), getattr(model, 'model_options', None)))


def _packet_signature(packet):
    return _signature({key: value for key, value in packet.items() if key != PROVENANCE_KEY})


@dataclass(frozen=True)
class NativeTargetPreparation:
    model: object
    original: dict
    canonical: dict
    host: object
    original_signature: tuple
    canonical_signature: tuple
    model_signature: tuple

    def verify(self, model, target):
        if (model is not self.model or target is not self.canonical
                or target.get(PROVENANCE_KEY) is not self
                or _signature(self.original) != self.original_signature
                or _packet_signature(target) != self.canonical_signature
                or _model_signature(model) != self.model_signature):
            raise RuntimeError('V12 owned native target preparation provenance changed')
        self.host.verify(model)


def verify_prepared_target(model, target):
    receipt = target.get(PROVENANCE_KEY)
    if type(receipt) is not NativeTargetPreparation:
        raise RuntimeError('V12 native target preparation receipt is invalid')
    receipt.verify(model, target)


def prepare_native_target(model, target, enabled=False):
    if type(enabled) is not bool:
        raise ValueError('V12 native target preparation enabled must be boolean')
    if not enabled:
        return target
    if type(target) is not dict or 'samples' not in target or PROVENANCE_KEY in target:
        raise ValueError('V12 native target preparation requires the original LATENT packet')
    for name in ('downscale_ratio_spacial', 'downscale_ratio_temporal'):
        ratio = target.get(name)
        if ratio is not None and (type(ratio) not in (int, float) or not 0 < ratio < float('inf')):
            raise ValueError('V12 native target downscale ratio must be finite and positive')
    from .consumer import native_model_preparation_lease
    with native_model_preparation_lease(model):
        host = load_latent_host(model)
        original = target['samples']
        if (type(original) is not host.tensor_type or original.is_nested
                or original.ndim not in (4, 5) or original.shape[0] != 1):
            raise RuntimeError('V12 native target preparation requires one ordinary image latent')
        before, model_before = _signature(target), _model_signature(model)
        samples = host.sample_module.fix_empty_latent_channels(model, original,
            target.get('downscale_ratio_spacial'), target.get('downscale_ratio_temporal'))
        host.verify(model)
        if before != _signature(target) or model_before != _model_signature(model):
            raise RuntimeError('V12 native target preparation changed its original packet or MODEL')
        if (type(samples) is not host.tensor_type or samples.is_nested
                or samples.ndim != 5 or samples.shape[:3] != (1, 16, 1)):
            raise RuntimeError('V12 native prepared target is outside the Krea image latent format')
        canonical = target.copy()
        canonical['samples'] = samples
        # These describe the raw packet and have already been consumed by the
        # native helper. Keeping them would apply the same resize again.
        canonical.pop('downscale_ratio_spacial', None)
        canonical.pop('downscale_ratio_temporal', None)
        receipt = NativeTargetPreparation(model, target, canonical, host, before,
                                           _packet_signature(canonical), model_before)
        canonical[PROVENANCE_KEY] = receipt
        receipt.verify(model, canonical)
        return canonical


def prepare_context_target(context, enabled=False):
    if not isinstance(context, NativeContext) or type(enabled) is not bool:
        raise ValueError('V12 target preparation requires a native context and boolean enabled')
    target = context.native.get('target_latent')
    if not enabled:
        return context, target
    context.verify()
    canonical = prepare_native_target(context.native['model'], target, enabled=True)
    if (context.owned_recipe is not None
            and target['samples'].shape[-2:] != canonical['samples'].shape[-2:]):
        # The original edit wrapper has already primed its VAE cache for these
        # target dimensions. Changing them here would trigger hidden re-encoding
        # during sampling; a broader owned rebuild is outside this preparation.
        raise RuntimeError('V12 owned grounded target preparation cannot change spatial dimensions')
    context.verify()
    bundle = {**context.native, 'target_latent': canonical}
    prepared = replace(context, native=bundle,
                       signature=context_signature(context.clip, bundle, context.sources))
    prepared.verify()
    return prepared, canonical
