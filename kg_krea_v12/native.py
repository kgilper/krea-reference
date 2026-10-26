"""Native preparation delegates and an in-process context, never serialized handles."""
from dataclasses import dataclass
import hashlib
import inspect
from pathlib import Path

from .hooks import encoder_lease

GROUNDING_BLOB = 'e924efbd930e03e3b00cb040d177992a08b462b4'


def _version_state(value):
    # Inference tensors have no version counter. Their identity and caller
    # revision remain binding; in-place writes require a new caller revision.
    # Unknown getter failures still propagate, rather than appearing immutable.
    is_inference = getattr(value, 'is_inference', None)
    if callable(is_inference) and is_inference():
        return ('unversioned-inference',)
    return getattr(value, '_version', None)


def _signature(value, seen=None):
    """Bind mutable native metadata, callbacks and versioned handles, no reuse cache.

    Pixel/latent in-place changes without a version counter still require the
    caller to issue a new context revision. This is not a content checksum.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    seen = set() if seen is None else seen
    if id(value) in seen:
        return ('cycle', id(value))
    seen.add(id(value))
    try:
        if isinstance(value, dict):
            return ('dict', tuple((key, _signature(item, seen)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return (type(value).__name__, tuple(_signature(item, seen) for item in value))
        return ('handle', id(value), _version_state(value))
    finally:
        seen.remove(id(value))


def context_signature(clip, native, sources):
    model = native['model']
    return (_signature(native), _signature(getattr(model, 'model_options', None)),
            _signature(getattr(model, 'patches_uuid', None)), id(getattr(clip, 'cond_stage_model', None)),
            _signature(getattr(getattr(clip, 'patcher', None), 'patches_uuid', None)),
            _signature(sources))


def load_edit_node(name):
    """Use the original installed node, with an explicit source compatibility pin.

    This is a source compatibility boundary, not a model/asset license or visual
    support assertion. No upstream runtime implementation is vendored here.
    """
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get(name)
    if cls is None:
        raise RuntimeError('V12 requires the original native edit node ' + name)
    data = Path(inspect.getfile(cls)).read_bytes().replace(b'\r\n', b'\n')
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()
    if blob != GROUNDING_BLOB:
        raise RuntimeError('V12 grounding source revision is unverified')
    return cls()


def load_grounder():
    return load_edit_node('Krea2EditGroundedEncode')


@dataclass(frozen=True)
class PreparedInputs:
    images: tuple
    owners: tuple
    template: object
    preparation_id: str

    def tokenize(self, clip, text):
        if self.template is None:
            return clip.tokenize(text)
        return clip.tokenize(text, images=list(self.images), llama_template=self.template)


@dataclass(frozen=True)
class NativeContext:
    clip: object
    native: dict
    prompt: str
    negative_prompt: str
    revision: str
    prepare_inputs: object
    model_revision: object
    sources: tuple
    signature: tuple
    owned_recipe: object = None

    def verify(self):
        if self.owned_recipe is not None:
            self.owned_recipe.verify()
        model = self.native['model']
        if getattr(model, 'patches_uuid', None) != self.model_revision:
            raise RuntimeError('V12 native model patch revision changed after preparation')
        if context_signature(self.clip, self.native, self.sources) != self.signature:
            raise RuntimeError('V12 native bundle, wrapper, encoder or source identity changed')
        if not self.revision:
            raise RuntimeError('V12 requires an explicit native context revision')

    def remove_reference(self, owner):
        """OFF must rebuild the complete native bundle, including MODEL latents.

        There is deliberately no scalar-zero or conditioning-key deletion fallback.
        The initial node has no complete MODEL/source-latent rebuilding authority.
        """
        if self.owned_recipe is None:
            raise RuntimeError('V12 reference OFF needs a complete owned native rebuild')
        return self.owned_recipe.remove(self, owner)


def prepare_context(clip, model, prompt, negative_prompt='', source=None, donor=None,
                    grounding_px=768, system_prompt='', revision='', native_metadata=None,
                    source_latent=None, target_latent=None, noise_mask=None,
                    native_bundle=None):
    """Encode original paired native conditioning and retain all external handles.

    Grounded preparation calls the installed native node's encode/_prep/_template
    methods. It does not restate their image sizing, trained text or ordering.
    Extra study preparation is lazy, so semantic zero adds no pole tokenization or
    image preparation. The caller retains wrapper/composite ownership.
    """
    if donor is not None and source is None:
        raise ValueError('V12 donor requires a native source image')
    if not isinstance(prompt, str) or not isinstance(negative_prompt, str):
        raise ValueError('V12 native prompts must be strings')
    if not isinstance(system_prompt, str):
        raise ValueError('V12 native system prompt must be a string')
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError('V12 requires an explicit native context revision')
    if isinstance(grounding_px, bool) or not isinstance(grounding_px, int) or not 0 <= grounding_px <= 4096:
        raise ValueError('V12 grounding size must be an integer from0 through4096')
    if noise_mask is None and isinstance(target_latent, dict):
        noise_mask = target_latent.get('noise_mask')
    if source is None:
        def prepare_inputs():
            return PreparedInputs((), (), None, 'native-text-v1')
    else:
        def prepare_inputs():
            grounder = load_grounder()
            images = [grounder._prep(source, grounding_px)]
            owners = ['native:source']
            if donor is not None:
                images.append(grounder._prep(donor, grounding_px))
                owners.append('native:donor')
            return PreparedInputs(tuple(images), tuple(owners),
                                  grounder._template(len(images), system_prompt),
                                  'krea2edit:' + GROUNDING_BLOB)
    if native_bundle is not None:
        if (not isinstance(native_bundle, dict) or native_bundle.get('model') is not model
                or any(key not in native_bundle for key in ('positive', 'negative', 'source_latent', 'target_latent', 'noise_mask'))):
            raise ValueError('V12 adopted native bundle needs paired conditioning, model, latent and mask fields')
        sources = (source, donor)
        return NativeContext(clip, native_bundle, prompt, negative_prompt, revision, prepare_inputs,
                             getattr(model, 'patches_uuid', None), sources,
                             context_signature(clip, native_bundle, sources))
    with encoder_lease(clip):
        if source is None:
            positive = clip.encode_from_tokens_scheduled(clip.tokenize(prompt))
            negative = clip.encode_from_tokens_scheduled(clip.tokenize(negative_prompt))
        else:
            grounder = load_grounder()
            kwargs = dict(clip=clip, image=source, image_b=donor, grounding_px=grounding_px,
                          system_prompt=system_prompt)
            positive = grounder.encode(prompt=prompt, **kwargs)[0]
            negative = grounder.encode(prompt=negative_prompt, **kwargs)[0]
    native = dict(model=model, positive=positive, negative=negative,
                  source_latent=source_latent, target_latent=target_latent,
                  noise_mask=noise_mask, metadata=native_metadata)
    sources = (source, donor)
    return NativeContext(clip, native, prompt, negative_prompt, revision, prepare_inputs,
                         getattr(model, 'patches_uuid', None), sources,
                         context_signature(clip, native, sources))
