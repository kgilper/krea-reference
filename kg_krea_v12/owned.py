"""Complete owned optional-donor removal by original native reconstruction.

The edit MODEL is rebuilt from its original pre-edit MODEL and native patch
arguments. The original node owns VAE priming/source placement; no edit forward
or preparation implementation is copied, and no patched MODEL is patched again.
"""
from dataclasses import dataclass, replace
import math

from .native import _signature, context_signature, load_edit_node, prepare_context

REF_POSITIONS = ('aligned (trained)', 'beside (right of target)', 'bag of features')


def _edit_wrappers(model):
    return getattr(model, 'model_options', {}).get('transformer_options', {}).get('wrappers', {}).get('diffusion_model', {})


def _dict_copy(value):
    return {key: _dict_copy(item) if isinstance(item, dict) else item for key, item in value.items()}


def _verify_foreign_options(original, patched):
    """Remove exactly the newly owned wrapper from a copy and compare foreign state."""
    before = getattr(original, 'model_options', {})
    after = _dict_copy(getattr(patched, 'model_options', {}))
    wrappers = after.get('transformer_options', {}).get('wrappers', {}).get('diffusion_model', {})
    owned = wrappers.get('krea2_edit', [])
    if len(owned) != 1:
        raise RuntimeError('V12 native rebuild did not produce exactly one owned edit wrapper')
    del wrappers['krea2_edit']
    previous_transformer = before.get('transformer_options', {})
    previous_wrappers = previous_transformer.get('wrappers', {})
    if not wrappers and 'diffusion_model' not in previous_wrappers:
        after['transformer_options']['wrappers'].pop('diffusion_model')
    if not after.get('transformer_options', {}).get('wrappers') and 'wrappers' not in previous_transformer:
        after['transformer_options'].pop('wrappers', None)
    if not after.get('transformer_options') and 'transformer_options' not in before:
        after.pop('transformer_options', None)
    if _signature(after) != _signature(before):
        raise RuntimeError('V12 native rebuild changed unowned model options')


@dataclass(frozen=True)
class OwnedGroundedRecipe:
    clip: object
    original_model: object
    patch_node: object
    patch_args: dict
    source: object
    donor: object
    prompt: str
    negative_prompt: str
    grounding_px: int
    system_prompt: str
    revision: str
    metadata: object
    original_signature: tuple

    def current_signature(self):
        return _signature((self.original_model, getattr(self.original_model, 'patches_uuid', None),
                           getattr(self.original_model, 'model_options', {}), self.patch_args,
                           self.source, self.donor))

    def verify(self):
        if self.current_signature() != self.original_signature:
            raise RuntimeError('V12 original owned native preparation changed; rebuild rejected')

    def build(self, previous=None):
        from .consumer import native_model_preparation_lease
        with native_model_preparation_lease(self.original_model):
            return self._build_leased(previous)

    def _build_leased(self, previous=None):
        self.verify()
        if 'krea2_edit' in _edit_wrappers(self.original_model):
            raise RuntimeError('V12 owned rebuild requires the original MODEL before its edit wrapper')
        patched = self.patch_node.patch(model=self.original_model, **self.patch_args)[0]
        if patched is self.original_model:
            raise RuntimeError('V12 native edit patch must return its own MODEL clone')
        self.verify()
        _verify_foreign_options(self.original_model, patched)
        context = prepare_context(self.clip, patched, self.prompt, self.negative_prompt,
            source=self.source, donor=self.donor, grounding_px=self.grounding_px,
            system_prompt=self.system_prompt, revision=self.revision, native_metadata=self.metadata,
            source_latent=self.patch_args['source_latent'], target_latent=self.patch_args['target_latent'])
        native = context.native
        if previous is not None:
            # Replace only fields owned by this native reconstruction. Arbitrary
            # external bundle fields keep their original identities.
            native = {**previous.native, **native}
        return replace(context, native=native, owned_recipe=self,
                       signature=context_signature(context.clip, native, context.sources))

    def remove(self, context, owner):
        context.verify()
        if owner != 'native:donor' or self.donor is None:
            raise RuntimeError('V12 only owns optional donor removal; source/generation rebuilding is unbound')
        if context.sources[0] is not self.source or context.sources[1] is not self.donor:
            raise RuntimeError('V12 reference removal ownership differs from the native context')
        args = self.patch_args.copy()
        args.pop('source_image_b', None)
        args.pop('source_latent_b', None)
        # Native edit routing assigns *_a to earlier scene references and the
        # un-suffixed controls to the last reference. After donor removal the
        # source becomes last; retain its former gain/placement, and remove
        # only the departed donor's reference-space boost mask.
        args['ref_boost'] = args['ref_boost_a']
        args['ref_position'] = args['ref_position_a']
        args['ref_boost_mask'] = None
        rebuilt = replace(self, donor=None, patch_args=args, revision=self.revision + ':without-native-donor')
        rebuilt = replace(rebuilt, original_signature=rebuilt.current_signature())
        result = rebuilt.build(previous=context)
        if result.sources[1] is not None or 'source_image_b' in result.owned_recipe.patch_args:
            raise RuntimeError('V12 donor removal did not rebuild all owned donor channels')
        return result


def prepare_owned_grounded(clip, original_model, prompt, source, source_latent, target_latent,
                           donor=None, source_latent_b=None, vae=None, negative_prompt='', revision='',
                           grounding_px=768, system_prompt='', ref_boost=1.0, ref_boost_a=1.0,
                           ref_boost_mask=None, fit_mode='fit', ref_position='aligned (trained)',
                           ref_position_a='aligned (trained)', native_metadata=None):
    """Use exact native task-selected arguments; never infer/change task recipes."""
    if source is None or not isinstance(source_latent, dict) or not isinstance(target_latent, dict):
        raise ValueError('V12 owned preparation needs source and original source/target latent packets')
    if 'samples' not in source_latent or 'samples' not in target_latent:
        raise ValueError('V12 owned native latent packets must contain their original samples')
    if not all(isinstance(value, str) for value in (prompt, negative_prompt, system_prompt)):
        raise ValueError('V12 owned native prompts must be strings')
    if isinstance(grounding_px, bool) or not isinstance(grounding_px, int) or not 0 <= grounding_px <= 4096:
        raise ValueError('V12 owned grounding size is invalid')
    if fit_mode not in ('fit', 'crop'):
        raise ValueError('V12 owned native fit mode is unknown')
    if ref_position not in REF_POSITIONS or ref_position_a not in REF_POSITIONS:
        raise ValueError('V12 owned native reference position is unknown')
    for value in (ref_boost, ref_boost_a):
        if (isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value) or not 0 <= value <= 1000):
            raise ValueError('V12 owned reference boosts must be finite numbers in [0, 1000]')
    if donor is None and source_latent_b is not None:
        raise ValueError('V12 donor latent requires an owned donor image')
    if source_latent_b is not None and (not isinstance(source_latent_b, dict)
            or 'samples' not in source_latent_b or source_latent_b['samples'] is None):
        raise ValueError('V12 owned donor latent must be a native samples packet')
    if donor is not None and vae is None and source_latent_b is None:
        raise ValueError('V12 owned donor requires its native VAE pixel path or donor latent packet')
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError('V12 owned preparation requires an explicit context revision')
    if fit_mode == 'fit' and vae is None:
        raise ValueError('V12 owned fit preparation requires its original VAE')
    args = dict(source_latent=source_latent, target_latent=target_latent, source_image=source,
                vae=vae, ref_boost=ref_boost, ref_boost_a=ref_boost_a, ref_boost_mask=ref_boost_mask,
                fit_mode=fit_mode, ref_position=ref_position, ref_position_a=ref_position_a)
    if donor is not None:
        args['source_image_b'] = donor
    if source_latent_b is not None:
        args['source_latent_b'] = source_latent_b
    recipe = OwnedGroundedRecipe(clip, original_model, load_edit_node('Krea2EditModelPatch'), args,
        source, donor, prompt, negative_prompt, grounding_px, system_prompt, revision,
        native_metadata, ())
    recipe = replace(recipe, original_signature=recipe.current_signature())
    return recipe.build()
