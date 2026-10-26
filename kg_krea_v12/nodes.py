"""Versioned in-process preparation/study nodes; active sampler export is gated."""
from .native import prepare_context
from .studies import TIMINGS, build_studies, number

CONTEXT_TYPE = 'KG_KREA_NATIVE_CONTEXT_V12'
AXIS_TYPE = 'KG_KREA_NATIVE_AXIS_V12'
STUDIES_TYPE = 'KG_KREA_NATIVE_STUDIES_V12'


class KGKrea2PrepareNativeContextV12:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'Krea CLIP': ('CLIP',),
                'Native MODEL': ('MODEL',),
                'Final image prompt': ('STRING', {'multiline': True}),
                'Negative prompt': ('STRING', {'multiline': True, 'default': ''}),
                'Native context revision': ('STRING', {'default': ''}),
                'Grounding pixels': ('INT', {'default': 768, 'min': 0, 'max': 4096}),
                'Grounding system prompt': ('STRING', {'multiline': True, 'default': ''}),
            },
            'optional': {
                'Clean source image': ('IMAGE',),
                'Clean donor image': ('IMAGE',),
                'Native source latent': ('LATENT',),
                'Native target latent': ('LATENT',),
                'Native noise mask': ('MASK',),
                'Native positive conditioning': ('CONDITIONING',),
                'Native negative conditioning': ('CONDITIONING',),
            },
        }

    RETURN_TYPES = (CONTEXT_TYPE,)
    RETURN_NAMES = ('native_context',)
    FUNCTION = 'execute'
    CATEGORY = 'advanced/conditioning/native studies'

    def execute(self, **kwargs):
        positive = kwargs.get('Native positive conditioning')
        negative = kwargs.get('Native negative conditioning')
        if (positive is None) != (negative is None):
            raise ValueError('V12 must adopt native positive and negative together')
        bundle = None
        if positive is not None:
            target = kwargs.get('Native target latent')
            mask = kwargs.get('Native noise mask')
            if mask is None and isinstance(target, dict):
                mask = target.get('noise_mask')
            bundle = dict(model=kwargs['Native MODEL'], positive=positive, negative=negative,
                          source_latent=kwargs.get('Native source latent'),
                          target_latent=target, noise_mask=mask)
        return (prepare_context(
            kwargs['Krea CLIP'], kwargs['Native MODEL'], kwargs['Final image prompt'],
            negative_prompt=kwargs['Negative prompt'],
            source=kwargs.get('Clean source image'), donor=kwargs.get('Clean donor image'),
            grounding_px=kwargs['Grounding pixels'], system_prompt=kwargs['Grounding system prompt'],
            revision=kwargs['Native context revision'],
            source_latent=kwargs.get('Native source latent'), target_latent=kwargs.get('Native target latent'),
            noise_mask=kwargs.get('Native noise mask'), native_bundle=bundle),)


class KGKrea2NativeAxisV12:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'Canonical axis ID': ('STRING', {'default': ''}),
            'Axis revision': ('STRING', {'default': ''}),
            'Positive pole': ('STRING', {'multiline': True}),
            'Negative pole': ('STRING', {'multiline': True}),
            'Native coefficient': ('FLOAT', {'default': 0.0, 'min': -6.0, 'max': 6.0, 'step': 0.01}),
            'Sampling timing': (list(TIMINGS),),
        }}

    RETURN_TYPES = (AXIS_TYPE,)
    RETURN_NAMES = ('native_axis',)
    FUNCTION = 'execute'
    CATEGORY = 'advanced/conditioning/native studies'

    def execute(self, **kwargs):
        from .studies import resolve_axes
        card = dict(axis_id=kwargs['Canonical axis ID'], revision=kwargs['Axis revision'],
                    plus=kwargs['Positive pole'], minus=kwargs['Negative pole'],
                    coefficient=number(kwargs['Native coefficient'], 'coefficient', -6, 6),
                    timing=kwargs['Sampling timing'])
        resolve_axes([card], 0.4, 6.0)
        return (card,)


class KGKrea2CombinedNativeStudiesV12:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'Native context': (CONTEXT_TYPE,),
            'Early-to-final handoff': ('FLOAT', {'default': 0.4, 'min': 0.0, 'max': 1.0}),
            'Native coefficient budget': ('FLOAT', {'default': 2.0, 'min': 0.0, 'max': 6.0}),
        }, 'optional': {f'Native axis {i}': (AXIS_TYPE,) for i in range(1, 9)}}

    RETURN_TYPES = (STUDIES_TYPE, 'STRING')
    RETURN_NAMES = ('native_studies', 'study_report')
    FUNCTION = 'execute'
    CATEGORY = 'advanced/conditioning/native studies'

    def execute(self, **kwargs):
        cards = [kwargs[f'Native axis {i}'] for i in range(1, 9) if kwargs.get(f'Native axis {i}') is not None]
        result = build_studies(kwargs['Native context'], cards,
                               split=kwargs['Early-to-final handoff'], budget=kwargs['Native coefficient budget'])
        report = ('Krea native studies V12: {} study passes. Active sampler export gated; '
                  'no calibrated semantic range. Phase scales {}. Native MODEL, negative, '
                  'latent and mask handles retained.').format(result.encode_passes, result.budget_scales)
        return result, report


class KGKrea2NativePhaseGuiderV12:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'Native studies': (STUDIES_TYPE,), 'Native guider': ('GUIDER',)}}

    RETURN_TYPES = ('GUIDER',)
    RETURN_NAMES = ('native_phase_guider',)
    FUNCTION = 'execute'
    CATEGORY = 'advanced/conditioning/native studies'

    def execute(self, **kwargs):
        from .consumer import bind_native_guider
        return (bind_native_guider(kwargs['Native studies'], kwargs['Native guider']),)


class KGKrea2PrepareOwnedGroundedContextV12:
    @classmethod
    def INPUT_TYPES(cls):
        from .owned import REF_POSITIONS
        return {'required': {
            'Krea CLIP': ('CLIP',), 'Original MODEL before edit patch': ('MODEL',),
            'Clean source image': ('IMAGE',), 'Native source latent': ('LATENT',),
            'Native target latent': ('LATENT',),
            'Final image prompt': ('STRING', {'multiline': True}),
            'Negative prompt': ('STRING', {'default': '', 'multiline': True}),
            'Native context revision': ('STRING', {'default': ''}),
            'Grounding pixels': ('INT', {'default': 768, 'min': 0, 'max': 4096}),
            'Grounding system prompt': ('STRING', {'default': '', 'multiline': True}),
            'Native reference boost': ('FLOAT', {'default': 1.0}),
            'Native first reference boost': ('FLOAT', {'default': 1.0}),
            'Native fit mode': (['fit', 'crop'],),
            'Native last reference position': (list(REF_POSITIONS),),
            'Native first reference position': (list(REF_POSITIONS),),
        }, 'optional': {'Clean donor image': ('IMAGE',), 'Native donor latent': ('LATENT',),
                        'Native VAE': ('VAE',), 'Native reference boost mask': ('MASK',)}}

    RETURN_TYPES = (CONTEXT_TYPE, 'MODEL', 'CONDITIONING', 'CONDITIONING', 'LATENT')
    RETURN_NAMES = ('native_context', 'native_model', 'native_positive', 'native_negative', 'native_target_latent')
    FUNCTION = 'execute'
    CATEGORY = 'advanced/conditioning/native studies'

    @staticmethod
    def _outputs(context):
        return (context, context.native['model'], context.native['positive'], context.native['negative'],
                context.native['target_latent'])

    def execute(self, **kwargs):
        from .owned import prepare_owned_grounded
        context = prepare_owned_grounded(kwargs['Krea CLIP'], kwargs['Original MODEL before edit patch'],
            kwargs['Final image prompt'], kwargs['Clean source image'], kwargs['Native source latent'],
            kwargs['Native target latent'], donor=kwargs.get('Clean donor image'),
            source_latent_b=kwargs.get('Native donor latent'), vae=kwargs.get('Native VAE'),
            negative_prompt=kwargs['Negative prompt'], revision=kwargs['Native context revision'],
            grounding_px=kwargs['Grounding pixels'], system_prompt=kwargs['Grounding system prompt'],
            ref_boost=kwargs['Native reference boost'], ref_boost_a=kwargs['Native first reference boost'],
            ref_boost_mask=kwargs.get('Native reference boost mask'), fit_mode=kwargs['Native fit mode'],
            ref_position=kwargs['Native last reference position'], ref_position_a=kwargs['Native first reference position'])
        return self._outputs(context)


class KGKrea2RemoveOwnedReferenceV12:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'Native context': (CONTEXT_TYPE,), 'Owned reference OFF': (['native:donor'],)}}

    RETURN_TYPES = KGKrea2PrepareOwnedGroundedContextV12.RETURN_TYPES
    RETURN_NAMES = KGKrea2PrepareOwnedGroundedContextV12.RETURN_NAMES
    FUNCTION = 'execute'
    CATEGORY = 'advanced/conditioning/native studies'

    def execute(self, **kwargs):
        context = kwargs['Native context'].remove_reference(kwargs['Owned reference OFF'])
        return KGKrea2PrepareOwnedGroundedContextV12._outputs(context)


class KGKrea2NativeEnhancerV12:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'Native MODEL before edit patch': ('MODEL',),
            'Enhancer enabled': ('BOOLEAN', {'default': False}),
            'Enhancer strength': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 2.0, 'step': 0.05}),
        }}

    RETURN_TYPES = ('MODEL', 'STRING')
    RETURN_NAMES = ('native_model', 'enhancer_report')
    FUNCTION = 'execute'
    CATEGORY = 'advanced/conditioning/native studies'

    def execute(self, **kwargs):
        from .enhancer import apply_enhancer
        return apply_enhancer(kwargs['Native MODEL before edit patch'],
                              enabled=kwargs['Enhancer enabled'], strength=kwargs['Enhancer strength'])
