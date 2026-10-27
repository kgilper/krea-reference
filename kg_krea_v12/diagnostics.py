"""Explicit one-shot scalar diagnostic; no endpoints, files, or permanent hooks.

Torch is imported only by an explicitly requested diagnostic. Ordinary workflows
have no diagnostic session. This measures transfer, not semantic calibration.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import math
import threading

from .ledger import TAP_WIDTH, TAPS

_current = ContextVar('krea_v12_bounded_diagnostic', default=None)
_lock = threading.Lock()
_active = set()
BASELINE_KEY = 'kg_native_v12_diagnostic_neutral'
MAX_ELEMENTS = 64 * 1024 * 1024
MAX_BYTES = 65536
CHUNK = 65536


def current():
    return _current.get()


def summarize(value, reference=None):
    """Bounded float32 reductions, scalar-only result; no full float32 copy."""
    import torch
    if (not isinstance(value, torch.Tensor) or value.numel() < 1
            or value.numel() > MAX_ELEMENTS or not value.is_floating_point()):
        raise RuntimeError('V12 diagnostic requires a bounded floating tensor')
    if reference is not None and (reference.shape != value.shape
                                  or reference.device != value.device):
        raise RuntimeError('V12 diagnostic paired tensor extent/device differs')
    flat = value.detach().reshape(-1)
    ref = reference.detach().reshape(-1) if reference is not None else None
    squares = diff_squares = ref_squares = maximum = diff_max = 0.0
    changed = nonzero = 0
    for start in range(0, value.numel(), CHUNK):
        a = flat[start:start + CHUNK].float()
        if not bool(torch.isfinite(a).all().item()):
            raise RuntimeError('V12 diagnostic encountered nonfinite values')
        squares += float((a * a).sum().item())
        maximum = max(maximum, float(a.abs().max().item()))
        nonzero += int(torch.count_nonzero(a).item())
        if ref is not None:
            b = ref[start:start + CHUNK].float()
            if not bool(torch.isfinite(b).all().item()):
                raise RuntimeError('V12 diagnostic encountered nonfinite reference')
            d = a - b
            diff_squares += float((d * d).sum().item())
            ref_squares += float((b * b).sum().item())
            diff_max = max(diff_max, float(d.abs().max().item()))
            changed += int((a != b).sum().item())
    count = value.numel()
    result = dict(shape=list(value.shape), dtype=str(value.dtype), numel=count,
                  rms=math.sqrt(squares / count), maxAbs=maximum, nonzero=nonzero)
    if ref is not None:
        result.update(differenceRms=math.sqrt(diff_squares / count), differenceMax=diff_max,
                      changed=changed, changedFraction=changed / count,
                      relativeRms=math.sqrt(diff_squares / ref_squares) if ref_squares else None)
    if any(isinstance(v, float) and not math.isfinite(v) for v in result.values()):
        raise RuntimeError('V12 diagnostic reduction overflow')
    return result


class BoundedDiagnostic:
    """One context, three study encodes, eight steps and two neutral probes."""
    def __init__(self, context, revision):
        if not isinstance(revision, str) or not 1 <= len(revision) <= 256 or revision != context.revision:
            raise ValueError('V12 diagnostic requires the exact explicit context revision')
        self.context = context
        self.revision = revision
        self.state = 'new'
        self.rows = []
        self.vision = {}
        self.projected = []
        self.regions = {}
        self.pairs = {}
        self.index = None
        self.mode = None
        self.fusion_calls = 0
        self.predictions = 0
        self.probes = []
        self.thread = None

    def add(self, kind, **values):
        row = dict(kind=kind, **values)
        # Fail before storing oversized/unserializable or nonfinite data.
        data = json.dumps(self.rows + [row], allow_nan=False, separators=(',', ':'))
        if len(data.encode('utf-8')) > MAX_BYTES - 2048:
            raise RuntimeError('V12 diagnostic scalar payload limit exceeded')
        self.rows.append(row)

    @contextmanager
    def scope(self, stage):
        expected = 'new' if stage == 'studies' else 'ready'
        if self.state != expected or current() is not None:
            raise RuntimeError('V12 diagnostic is single-use and cannot overlap')
        key = id(self.context.native['model'].model)
        with _lock:
            if key in _active:
                raise RuntimeError('V12 diagnostic MODEL already active')
            _active.add(key)
        self.thread = threading.get_ident()
        token = _current.set(self)
        self.state = stage
        try:
            yield self
            if stage == 'studies':
                if len(self.projected) != 3:
                    raise RuntimeError('V12 diagnostic requires exactly three study passes')
                self.state = 'ready'
            else:
                if self.predictions != 10 or self.probes != [0, 4]:
                    raise RuntimeError('V12 diagnostic prediction/probe count differs')
                self.state = 'complete'
        except BaseException:
            self.state = 'failed'
            raise
        finally:
            self.vision.clear()
            self.projected.clear()
            self.pairs.clear()
            self.mode = self.index = self.thread = None
            _current.reset(token)
            with _lock:
                _active.discard(key)

    def check(self):
        if current() is not self or threading.get_ident() != self.thread:
            raise RuntimeError('V12 diagnostic observer escaped its owned scope')

    def image(self, owner, value, extra):
        self.check()
        values = [value, *extra['deepstack']]
        if any(not 1 <= v.numel() <= MAX_ELEMENTS for v in values):
            raise RuntimeError('V12 diagnostic vision pair exceeds tensor bound')
        if owner not in self.vision:
            self.vision[owner] = [v.detach().clone() for v in values]
        for depth, (v, baseline) in enumerate(zip(values, self.vision[owner])):
            self.add('vision', study=len(self.projected), owner=owner, depth=depth,
                     summary=summarize(v, baseline))

    def encoded(self, value, expanded, positions):
        self.check()
        n = self.context.native['positive'][0][0]
        self.add('projected', study=len(self.projected), summary=summarize(value, n),
                 poleSpans=list(expanded.poles))
        if not self.regions:
            # Expanded output coordinates -> exact projected native positions.
            spans = {'prompt': expanded.prompt}
            spans.update({owner: (start, end) for owner, start, end in expanded.images})
            used = set()
            for name, (start, end) in spans.items():
                indices = [i for i, pos in enumerate(positions) if start <= pos + expanded.strip < end]
                self.regions[name] = indices
                used.update(indices)
            self.regions['headerSuffix'] = [i for i in range(len(positions)) if i not in used]
        # Retain only P until M; B needs a scalar receipt only.
        self.projected.append(value.detach().clone() if len(self.projected) == 1 else None)
        if len(self.projected) == 3:
            direction = self.projected[1] - value
            self.tap_regions('direction', direction, n)
            self.projected[1] = None

    def tap_regions(self, kind, value, reference):
        if value.shape[-1] != len(TAPS) * TAP_WIDTH:
            raise RuntimeError('V12 diagnostic tap layout differs')
        def summary(a, b):
            if kind != 'direction':
                return summarize(a, b)
            result, base = summarize(a), summarize(b)
            result.update(referenceRms=base['rms'],
                          directionToNativeRms=result['rms']/base['rms'] if base['rms'] else None)
            return result
        self.add(kind, summary=summary(value, reference),
                 taps=[summary(value[..., i*TAP_WIDTH:(i+1)*TAP_WIDTH],
                               reference[..., i*TAP_WIDTH:(i+1)*TAP_WIDTH]) for i in range(len(TAPS))],
                 regions={name: summary(value[:, indices], reference[:, indices])
                          for name, indices in self.regions.items() if indices})

    def composition(self, native, direction, result, phase):
        self.check()
        self.tap_regions('composed' + str(phase), result, native)
        # Chunked statistics of the float32 residual; avoid full float32 tensors.
        residual_max = 0.0
        for start in range(0, native.shape[-1], TAP_WIDTH):
            residual = (result[..., start:start+TAP_WIDTH].float()
                        - native[..., start:start+TAP_WIDTH].float()
                        - direction[..., start:start+TAP_WIDTH].float())
            residual_max = max(residual_max, summarize(residual)['maxAbs'])
        self.add('compositionRounding', phase=phase, residualMax=residual_max,
                 roundedExpected=summarize(result, native + direction))

    def validate(self, studies, guider, sampler, schedule, euler):
        if self.state != 'ready':
            raise RuntimeError('V12 diagnostic is single-use')
        if (studies.context is not self.context or self.state != 'ready'
                or len(schedule) != 9 or sampler.sampler_function is not euler.sample_euler
                or getattr(guider, 'cfg', None) != 1
                or self.context.native['noise_mask'] is not None
                or self.context.sources[0] is None or self.context.sources[1] is not None):
            raise RuntimeError('V12 diagnostic requires its single-source full-frame eight-step Euler CFG1 case')
        if studies.phases[0] != 0.4 or studies.budget_scales != (1.0, 1.0):
            raise RuntimeError('V12 diagnostic phase/budget differs')
        shape = tuple(self.context.native['target_latent']['samples'].shape)
        if len(shape) != 5 or shape[:3] != (1, 16, 1) or not all(1 <= size <= 128 for size in shape[-2:]):
            raise RuntimeError('V12 diagnostic target exceeds its single-image spatial bound')
        options = guider.model_patcher.model_options
        if set(options) - {'transformer_options'}:
            raise RuntimeError('V12 diagnostic refuses extra MODEL options/callbacks')
        wrappers = options.get('transformer_options', {}).get('wrappers', {})
        if set(options.get('transformer_options', {})) - {'wrappers', 'kg_native_enhancer_v12'}:
            raise RuntimeError('V12 diagnostic refuses extra transformer options/patches')
        if (set(wrappers) != {'diffusion_model'}
                or set(wrappers['diffusion_model']) != {'kg_native_enhancer_v12', 'krea2_edit'}):
            raise RuntimeError('V12 diagnostic requires only the owned enhancer and native edit wrappers')
        enhancer = options['transformer_options'].get('kg_native_enhancer_v12', {})
        if enhancer.get('enabled') is not True or enhancer.get('strength') != 1:
            raise RuntimeError('V12 diagnostic requires enhancer ON at one')

    def fusion(self, dm, value, result):
        self.check()
        if self.index is None or self.mode not in ('selected', 'neutral'):
            raise RuntimeError('V12 diagnostic unexpected fusion invocation')
        self.fusion_calls += 1
        if self.fusion_calls != 1:
            raise RuntimeError('V12 diagnostic requires one fusion per native prediction')
        if self.mode == 'selected':
            self.add('fusion', step=self.index, input=summarize(value), output=summarize(result))
            if self.index in (0, 4):
                self.pairs = dict(input=value.detach().clone(), output=result.detach().clone())
        else:
            import torch
            n = self.context.native['positive'][0][0]
            expected = dm._unpack_context(n.to(device=value.device, dtype=value.dtype))
            if not torch.equal(value, expected):
                raise RuntimeError('V12 diagnostic actual neutral fusion input differs from cast native conditioning')
            self.add('fusionPair', step=self.index, input=summarize(self.pairs['input'], value),
                     output=summarize(self.pairs['output'], result),
                     nativeCast=summarize(n.to(device=value.device),
                                          expected.reshape(n.shape).to(dtype=n.dtype)))

    def predict(self, predictor, guider, baseline, x, timestep, options, seed, index, phase):
        import torch
        from .native import _signature
        self.check()
        if index != self.predictions - len(self.probes) or not 0 <= index < 8:
            raise RuntimeError('V12 diagnostic ordinary prediction order differs')
        self.index, self.mode, self.fusion_calls = index, 'selected', 0
        selected = guider.conds['positive']
        if len(selected) != 1 or len(baseline) != 1:
            raise RuntimeError('V12 diagnostic requires one prepared positive branch')
        self.add('selected', step=index, phase=phase, sigma=float(timestep.flatten()[0].item()),
                 summary=summarize(selected[0]['cross_attn'], baseline[0]['cross_attn']))
        if self.predictions >= 10:
            raise RuntimeError('V12 diagnostic native prediction limit exceeded')
        self.predictions += 1
        result = predictor(x, timestep, model_options=options, seed=seed)
        if guider.conds.get('positive') is not selected:
            raise RuntimeError('V12 diagnostic foreign positive mutation; foreign state preserved')
        if self.fusion_calls != 1:
            raise RuntimeError('V12 diagnostic native fusion was bypassed')
        if index not in (0, 4):
            return result
        rng = torch.random.get_rng_state()
        cuda_rng = torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else None
        before_x, before_t = x.detach().clone(), timestep.detach().clone()
        before_result = result.detach().clone()
        before_source = self.context.native['source_latent']['samples'].detach().clone()
        signature = _signature((options, guider.model_patcher.model_options, self.context.native['source_latent']))
        self.mode, self.fusion_calls = 'neutral', 0
        try:
            guider.conds['positive'] = baseline
            if self.predictions >= 10:
                raise RuntimeError('V12 diagnostic native prediction limit exceeded')
            self.predictions += 1
            neutral = predictor(x, timestep, model_options=options, seed=seed)
            if self.fusion_calls != 1:
                raise RuntimeError('V12 diagnostic neutral fusion was bypassed')
            if (not torch.equal(x, before_x) or not torch.equal(timestep, before_t)
                    or not torch.equal(result, before_result)
                    or not torch.equal(self.context.native['source_latent']['samples'], before_source)
                    or signature != _signature((options, guider.model_patcher.model_options,
                                                self.context.native['source_latent']))):
                raise RuntimeError('V12 diagnostic counterfactual mutated native input/options')
            self.add('predictionPair', step=index, summary=summarize(result, neutral))
            self.probes.append(index)
        finally:
            torch.random.set_rng_state(rng)
            if cuda_rng is not None:
                torch.cuda.set_rng_state_all(cuda_rng)
            self.pairs.clear()
            if guider.conds.get('positive') is not baseline:
                raise RuntimeError('V12 diagnostic foreign positive mutation; foreign state preserved')
            guider.conds['positive'] = selected
            self.mode = 'selected'
        return result

    def receipt(self):
        if self.state != 'complete':
            raise RuntimeError('V12 diagnostic receipt requires a completed single job')
        return json.dumps(dict(schema='krea-v12-scalar-diagnostic-v1', state=self.state,
                               contextRevision=self.revision, studyPasses=3, samplerSteps=8,
                               nativePredictions=self.predictions, nominalUpperBound=20,
                               probes=self.probes, cleanup=True, rows=self.rows),
                          allow_nan=False, separators=(',', ':'))


def build_diagnostic(context, card, revision):
    from dataclasses import replace
    from .studies import build_studies
    expected = dict(axis_id='illumination', revision='krea-illumination-v1:1',
                    plus='Bright clear lighting with strong illumination.',
                    minus='Dim lighting with low illumination and deep shadows.',
                    coefficient=1.0, timing='throughout')
    if not isinstance(card, dict) or card != expected or isinstance(card['coefficient'], bool):
        raise ValueError('V12 diagnostic requires the explicit +1 Throughout illumination axis')
    context.verify()
    if (context.sources[0] is None or context.sources[1] is not None
            or context.native['noise_mask'] is not None or context.owned_recipe is None):
        raise RuntimeError('V12 diagnostic requires owned single-source full-frame context')
    session = BoundedDiagnostic(context, revision)
    with session.scope('studies'):
        result = build_studies(context, [card], split=0.4, budget=2.0)
    return replace(result, diagnostic=session)
