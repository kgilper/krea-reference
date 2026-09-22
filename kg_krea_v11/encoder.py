"""V11 sign-preserving reference budgets with unchanged V10 recipes."""
import copy
import math
from ._deps import v10
from . import cache


def balance_targets(targets, budget):
    if budget is None or not targets:
        return 1.0
    # Budget actual active layer coefficients, not offsets from native 1.
    # Pooled pull is excluded: Krea's Qwen encoder has no pooled output.
    load = sum(max((abs(1.0 + w) for w in target['token_layers']), default=abs(target['token']))
               for target in targets)
    if not math.isfinite(load):
        raise ValueError('V11 reference targets must be finite')
    scale = min(1.0, float(budget) / load) if load else 1.0
    if scale < 1.0:
        for target in targets:
            target['token'] *= scale
            target['pooled'] *= scale
            target['token_layers'] = [(1.0 + weight) * scale - 1.0 for weight in target['token_layers']]
    return scale


class KGKrea2ImageGuideCardV11(v10.KGKrea2ImageGuideCardV10):
    """V10 recipe semantics, explicitly versioned for V11 graphs."""
    def build(self, **kwargs):
        card = super().build(**kwargs)[0]
        card['source_version'] = 'v11'
        return (card,)


class KGTextEncodeKreaImageReferencesV11(v10.KGTextEncodeKreaImageReferencesV10):
    BALANCE_LABELS = {
        'off - use my values': 'off',
        'gentle sign-preserving balance': 'gentle',
        'strict sign-preserving balance': 'strict',
    }
    _balance_targets = staticmethod(balance_targets)

    @staticmethod
    def _cache_key(clip, prompt_text, template_text, prepared_images):
        return cache.make_key(clip, 'reference-v11', prompt_text, template_text, images=prepared_images)

    _cache_lookup = staticmethod(cache.lookup)
    _cache_store = staticmethod(cache.store)

    @staticmethod
    def _build_report(info):
        report_info = copy.deepcopy(info)
        report_info['balance_budget'] = None
        result = v10.encoder.stack_report.build_report(report_info)
        result = result.replace('Encoder V10', 'Encoder V11')
        lines = [line for line in result.splitlines() if not line.startswith('Balance:')]
        # Older report's "look" target is inert on Krea. Do not imply otherwise.
        lines.append('Krea has no pooled look channel; recipe appearance uses token layers.')
        budget = info.get('balance_budget')
        lines.append('V11 balance: off.' if budget is None else
                     'V11 balance: signed layer targets scaled toward zero; budget {:.2f}; phase scales {}.'.format(
                         budget, ', '.join('{:.4f}'.format(s) for s in info.get('balance_scales', []))))
        lines.append('Cache: SHA-256 image content plus model patch revision; unknown revisions bypass reuse.')
        return '\n'.join(lines)
