"""Explicit V11 slider presets and timing; V1 remains unchanged."""
from ._deps import sliders

# Concrete poles carry prior render evidence; presets never override explicit text.
PRESETS = {
    'custom or automatic': None,
    'person height': ('height', 'a very tall man with long legs, towering height',
                      'a very short man with a small compact stature, much shorter than average'),
    'plaza crowd': ('crowd size', 'a plaza packed with a dense crowd of people',
                    'an empty deserted plaza with bare pavement and no people'),
}
TIMINGS = ['whole image', 'early layout only', 'final details only']


class KGKrea2ConceptSliderCardV11(sliders.KGKrea2ConceptSliderCardV1):
    @classmethod
    def INPUT_TYPES(cls):
        inputs = super().INPUT_TYPES()
        inputs['required'].update({
            'Slider preset': (list(PRESETS),),
            'When this slider guides': (TIMINGS,),
        })
        return inputs

    def build(self, **kwargs):
        packet = super().build(**kwargs)[0]
        preset = kwargs.get('Slider preset', 'custom or automatic')
        if preset not in PRESETS:
            raise ValueError('Unknown V11 slider preset: ' + str(preset))
        settings = PRESETS[preset]
        if settings:
            packet['description'] = settings[0]
            packet['increase_text'] = packet['increase_text'] or settings[1]
            packet['decrease_text'] = packet['decrease_text'] or settings[2]
        timing = kwargs.get('When this slider guides', 'whole image')
        if timing not in TIMINGS:
            raise ValueError('Unknown V11 slider timing: ' + str(timing))
        packet.update(kg_slider_version=11, preset=preset, timing=timing)
        return (packet,)
