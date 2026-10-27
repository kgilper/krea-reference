"""CPU scalar/control-flow fixtures; no Torch, weights, GPU or neural claims.

The optional NumPy tensor boundary exercises the actual chunked reducer and
observer code. Native Comfy preparation, fusion and predictor are authored
fixtures, explicitly not a native-runtime acceptance test.
"""
from dataclasses import replace
import json
from types import SimpleNamespace as NS
import sys
import threading
import unittest
import uuid
from unittest.mock import patch

try:
    import numpy as np
except ImportError:
    np = None

import test_krea_v12 as fixture
NODES, card = fixture.NODES, fixture.card
from native_v12_tests import consumer, diagnostics as d, native, studies


class Array:
    """Small NumPy-backed boundary, NOT a Torch implementation."""
    device = 'cpu-fixture'

    def __init__(self, values, dtype=None):
        self.a = np.asarray(values, dtype=dtype or np.float32)

    @property
    def shape(self): return self.a.shape
    @property
    def dtype(self): return self.a.dtype
    def numel(self): return self.a.size
    def is_floating_point(self): return self.a.dtype.kind == 'f'
    def detach(self): return self
    def clone(self): return Array(self.a.copy(), self.dtype)
    def reshape(self, *shape): return Array(self.a.reshape(*shape), self.dtype)
    def flatten(self): return self.reshape(-1)
    def float(self): return Array(self.a.astype(np.float32))
    def abs(self): return Array(np.abs(self.a), self.dtype)
    def max(self): return Array(np.max(self.a), self.dtype)
    def sum(self): return Array(np.sum(self.a), self.dtype)
    def all(self): return Array(np.all(self.a), np.bool_)
    def item(self): return self.a.item()
    def to(self, device=None, dtype=None): return Array(self.a.astype(dtype or self.dtype), dtype or self.dtype)
    def __getitem__(self, index): return Array(self.a[index], self.dtype)
    def __add__(self, other): return Array(self.a + (other.a if isinstance(other, Array) else other), self.dtype)
    def __sub__(self, other): return Array(self.a - (other.a if isinstance(other, Array) else other), self.dtype)
    def __mul__(self, other): return Array(self.a * (other.a if isinstance(other, Array) else other), self.dtype)
    def __ne__(self, other): return Array(self.a != other.a, np.int64)


class RNG:
    state = 0
    @classmethod
    def get_rng_state(cls): return cls.state
    @classmethod
    def set_rng_state(cls, state): cls.state = state


class CUDA:
    state = [17, 23]
    @classmethod
    def is_initialized(cls): return True
    @classmethod
    def get_rng_state_all(cls): return cls.state.copy()
    @classmethod
    def set_rng_state_all(cls, states): cls.state = states.copy()


TORCH = NS(Tensor=Array, isfinite=lambda v: Array(np.isfinite(v.a), np.bool_),
           count_nonzero=lambda v: Array(np.count_nonzero(v.a), np.int64),
           equal=lambda a,b: np.array_equal(a.a,b.a), random=RNG, cuda=CUDA)


def context_fixture():
    n = Array(np.full((1, 2, 30720), 2.0))
    target = Array(np.zeros((1, 16, 1, 2, 2)))
    source = Array(np.ones((1, 16, 1, 2, 2)))
    dm = NS(_unpack_context=lambda x: x.reshape(1, 2, 12, 2560))
    opts = {'transformer_options': {'wrappers': {'diffusion_model': {
        'kg_native_enhancer_v12': [object()], 'krea2_edit': [object()]}},
        'kg_native_enhancer_v12': {'enabled': True, 'strength': 1}}}
    model = NS(model=NS(diffusion_model=dm), model_options=opts, patches_uuid='fixture',
               get_additional_models_with_key=lambda key: [])
    bundle = dict(model=model, positive=[[n, {}]], negative=[[n*0, {}]],
                  source_latent={'samples': source}, target_latent={'samples': target}, noise_mask=None)
    clip = NS(cond_stage_model=object())
    sources = (object(), None)
    context = native.NativeContext(clip, bundle, 'preserve', '', 'fixture-revision', None,
                                   model.patches_uuid, sources, native.context_signature(clip,bundle,sources))
    return context, dm


class Sampler:
    extra_options = {}
    inpaint_options = {}
    def __init__(self, function): self.sampler_function = function


class Guider:
    def __init__(self, context):
        self.model_patcher = context.native['model']
        self.cfg = 1
        self.original_conds = {}
        self.calls = []
        self.returned = []
        self.fail = None
        self.foreign = None
        self.foreign_mode = 'neutral'
        self.mutate_x = False
        self.mutate_source = False
        self.context = context
        self.inner_set_conds({k:context.native[k] for k in ('positive','negative')})

    def inner_set_conds(self, entries):
        for k, value in entries.items():
            self.original_conds[k] = [dict(meta, cross_attn=tensor, model_conds={}, uuid=uuid.uuid4())
                                     for tensor, meta in value]

    def sample(self, noise, latent, sampler, sigmas, denoise_mask=None, callback=None, **kwargs):
        # This is the only preparation boundary in this fixture. The actual
        # NativePhaseGuider must submit baseline here, before predictions.
        self.conds = {k:[dict(v, model_conds={'c_crossattn':NS(cond=v['cross_attn'])}) for v in values]
                      for k,values in self.original_conds.items()}
        for i, sigma in enumerate(sigmas[:-1]):
            prediction = self.predict_noise(latent, Array([sigma]), model_options={}, seed=kwargs.get('seed'))
            self.returned.append(prediction)
            if callback is not None: callback(i, prediction, latent, len(sigmas)-1)
        return self.returned[-1]

    def predict_noise(self, x, timestep, model_options=None, seed=None):
        session = d.current()
        assert session is not None
        mode, index = session.mode, session.index
        if self.fail == (index, mode): raise KeyboardInterrupt('fixture cancelled')
        cond = self.conds['positive'][0]['model_conds']['c_crossattn'].cond
        dm = self.model_patcher.model.diffusion_model
        value = dm._unpack_context(cond)
        fused = Array(value.a.mean(axis=2))
        session.fusion(dm, value, fused)
        RNG.state += 1
        CUDA.state[0] += 1
        result = Array(x.a + float(cond.a.mean()))
        self.calls.append((index,mode,cond,result))
        if mode == self.foreign_mode and self.foreign is not None:
            self.conds['positive'] = self.foreign
        if mode == 'neutral' and self.mutate_x:
            x.a.flat[0] += 1
        if mode == 'neutral' and self.mutate_source:
            self.context.native['source_latent']['samples'].a.flat[0] += 1
        return result


@unittest.skipIf(np is None, 'optional NumPy numeric boundary unavailable')
class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.torch = patch.dict(sys.modules, {'torch':TORCH})
        self.torch.start()
        self.addCleanup(self.torch.stop)
        self.addCleanup(self.assertIsNone, d.current())
        self.addCleanup(self.assertFalse, d._active)
        self.addCleanup(self.assertFalse, consumer._busy)
        RNG.state, CUDA.state = 0, [17,23]

    def prepared(self):
        context, dm = context_fixture()
        session = d.BoundedDiagnostic(context, context.revision)
        session.state = 'ready'
        changed = [[context.native['positive'][0][0] + 0.25, {}]]
        phase = {**context.native, 'positive':changed}
        study = studies.NativeStudies(context, (0.4,phase,phase), (),3,(1.0,1.0),True,(),session)
        guider = Guider(context)
        euler = NS(sample_euler=lambda: None, sample_euler_ancestral=lambda: None)
        host = (NS(CFGGuider=Guider, KSAMPLER=Sampler),euler,NS(Krea2=type(context.native['model'].model)))
        return session, study, guider, host, Sampler(euler.sample_euler)

    def run_sample(self, bundle, callback=None):
        session, study, guider, host, sampler = bundle
        bound = consumer.NativePhaseGuider(guider,study,host)
        target = study.context.native['target_latent']['samples']
        with patch.object(consumer,'_validate_grounded_wrapper'):
            return bound.sample(target.clone(),target,sampler,[8,7,6,5,4,3,2,1,0],callback=callback,seed=581102)

    def test_chunked_reducer_matches_explicit_math(self):
        a = Array(np.arange(101) / 7)
        b = Array(np.arange(101) / 11)
        with patch.object(d, 'CHUNK', 13): r = d.summarize(a,b)
        self.assertAlmostEqual(r['rms'],float(np.sqrt(np.mean(a.a.astype('float64')**2))),places=6)
        self.assertAlmostEqual(r['differenceRms'],float(np.sqrt(np.mean((a.a.astype('float64')-b.a)**2))),places=6)
        self.assertEqual(r['changed'],100)
        self.assertEqual(d.summarize(a,a)['differenceRms'],0)
        self.assertIsNone(d.summarize(a,Array(np.zeros(101)))['relativeRms'])

    def test_zero_nonfinite_extent_and_payload_reject(self):
        self.assertEqual(d.summarize(Array([0,0]))['rms'],0)
        for values in ([float('nan')],[float('inf')],[]):
            with self.assertRaises(RuntimeError): d.summarize(Array(values))
        with self.assertRaises(RuntimeError): d.summarize(Array([1]),Array([1,2]))
        context,_ = context_fixture()
        s = d.BoundedDiagnostic(context, context.revision)
        with self.assertRaisesRegex(RuntimeError,'payload'):s.add('bad',value='x'*65536)
        with self.assertRaises(ValueError):s.add('bad',value=float('nan'))
        self.assertEqual(s.rows,[])

    def test_float16_cast_loss_and_composition_residual_are_distinct(self):
        n = Array(np.ones((1,1,30720)), np.float16)
        delta = Array(np.full((1,1,30720),0.0001),np.float16)
        r = n + delta
        self.assertGreater(d.summarize(delta)['rms'],0)
        self.assertEqual(d.summarize(r,n)['changed'],0)
        context,_ = context_fixture()
        s = d.BoundedDiagnostic(context,context.revision)
        with s.scope('studies'):
            s.composition(n,delta,r,0)
            s.projected=[None,None,None]
        residual=[row for row in s.rows if row['kind']=='compositionRounding'][0]
        self.assertGreater(residual['residualMax'],0)
        self.assertEqual(residual['roundedExpected']['changed'],0)

    def test_full_consumer_ten_calls_eight_callbacks_preserves_return_and_rng(self):
        bundle=self.prepared(); s,study,g,_,_=bundle
        original=g.original_conds
        callbacks=[]
        output=self.run_sample(bundle,lambda i,*args:callbacks.append(i))
        self.assertEqual(len(g.calls),10)
        self.assertEqual([i for i,mode,*_ in g.calls if mode=='neutral'],[0,4])
        self.assertEqual(callbacks,list(range(8)))
        self.assertEqual(RNG.state,8)
        self.assertEqual(CUDA.state,[25,23])
        self.assertIs(g.original_conds,original)
        self.assertNotIn('predict_noise',vars(g))
        self.assertFalse(set(g.conds)&{*consumer._PHASE_KEYS,d.BASELINE_KEY})
        for returned,call in zip(g.returned,[c for c in g.calls if c[1]=='selected']):
            self.assertIs(returned,call[3])
        self.assertIs(output,g.returned[-1])
        receipt=json.loads(s.receipt())
        self.assertEqual(receipt['nativePredictions'],10)
        self.assertEqual(len([r for r in receipt['rows'] if r['kind']=='fusionPair']),2)
        self.assertLess(len(s.receipt().encode()),65536)
        self.assertEqual(s.pairs,{})
        with self.assertRaisesRegex(RuntimeError,'single-use'):self.run_sample(bundle)

    def test_cancel_each_probe_restores_rng_conditioning_and_owned_state(self):
        for index in (0,4):
            with self.subTest(index=index):
                RNG.state,CUDA.state=0,[17,23]
                bundle=self.prepared();s,_,g,_,_=bundle;g.fail=(index,'neutral')
                original=g.original_conds
                with self.assertRaises(KeyboardInterrupt):self.run_sample(bundle)
                self.assertEqual(s.state,'failed')
                self.assertEqual(RNG.state,index+1)
                self.assertEqual(CUDA.state,[18+index,23])
                self.assertIs(g.original_conds,original)
                self.assertNotIn('predict_noise',vars(g))
                self.assertEqual(s.pairs,{})
                self.assertIsNone(d.current())
                with self.assertRaisesRegex(RuntimeError,'completed'):s.receipt()

    def test_ordinary_cancellation_and_callback_failure_cleanup(self):
        bundle=self.prepared();s,_,g,_,_=bundle;g.fail=(3,'selected')
        with self.assertRaises(KeyboardInterrupt):self.run_sample(bundle)
        self.assertEqual(s.state,'failed');self.assertNotIn('predict_noise',vars(g))
        bundle=self.prepared();s,_,g,_,_=bundle
        def fail(*args):raise ValueError('callback failed')
        with self.assertRaisesRegex(ValueError,'callback failed'):self.run_sample(bundle,fail)
        self.assertEqual(s.state,'failed');self.assertNotIn('predict_noise',vars(g))
        self.assertEqual(s.pairs,{})

    def test_foreign_positive_preserved_and_input_mutation_rejected(self):
        for mode in ('selected','neutral'):
            bundle=self.prepared();s,_,g,_,_=bundle;g.foreign=[{'foreign':True}];g.foreign_mode=mode
            with self.assertRaisesRegex(RuntimeError,'foreign'):self.run_sample(bundle)
            self.assertIs(g.conds['positive'],g.foreign)
            self.assertEqual(s.state,'failed')
        bundle=self.prepared();s,_,g,_,_=bundle;g.mutate_x=True
        with self.assertRaisesRegex(RuntimeError,'mutated'):self.run_sample(bundle)
        self.assertEqual(s.state,'failed')
        bundle=self.prepared();s,_,g,_,_=bundle;g.mutate_source=True
        with self.assertRaisesRegex(RuntimeError,'mutated'):self.run_sample(bundle)
        self.assertEqual(s.state,'failed')

    def test_wrong_step_count_sampler_cfg_callbacks_and_extra_wrappers_reject(self):
        for change in ('steps','sampler','cfg','callback','wrapper','transformer','target'):
            bundle=self.prepared();s,study,g,host,sampler=bundle
            schedule=[8,7,6,5,4,3,2,1,0]
            if change=='steps':schedule=[2,1,0]
            elif change=='sampler':sampler.sampler_function=host[1].sample_euler_ancestral
            elif change=='cfg':g.cfg=2
            elif change=='callback':g.model_patcher.model_options['sampler_post_cfg_function']=[lambda:None]
            elif change=='wrapper':g.model_patcher.model_options['transformer_options']['wrappers']['predict_noise']={}
            elif change=='transformer':g.model_patcher.model_options['transformer_options']['patches']={}
            else:study.context.native['target_latent']['samples']=Array(np.zeros((1,16,1,129,1)))
            with self.subTest(change=change),self.assertRaises(RuntimeError):
                s.validate(study,g,sampler,schedule,host[1])
            self.assertFalse(g.calls)

    def test_scope_reentry_other_thread_and_failure_clear_tensors(self):
        context,_=context_fixture();s=d.BoundedDiagnostic(context,context.revision)
        errors=[]
        with self.assertRaises(KeyboardInterrupt):
            with s.scope('studies'):
                s.vision['temporary']=Array([1]);s.pairs['temporary']=Array([2])
                with self.assertRaises(RuntimeError):
                    with s.scope('studies'):pass
                def other():
                    try:s.check()
                    except RuntimeError:errors.append(True)
                t=threading.Thread(target=other);t.start();t.join()
                raise KeyboardInterrupt()
        self.assertEqual(errors,[True]);self.assertFalse(s.vision);self.assertFalse(s.pairs)
        self.assertEqual(s.state,'failed')

    def test_actual_observer_localizes_taps_and_regions(self):
        context,_=context_fixture();s=d.BoundedDiagnostic(context,context.revision)
        n=context.native['positive'][0][0]
        expanded=NS(poles=((3,4),(4,5)),prompt=(1,2),images=(('native:source',0,1),),strip=0)
        plus=n.clone();plus.a[:,1,2560:5120]+=0.5
        with s.scope('studies'):
            for value in (n,plus,n):s.encoded(value,expanded,(0,1))
        row=[r for r in s.rows if r['kind']=='direction'][0]
        self.assertGreater(row['taps'][1]['rms'],0)
        self.assertEqual(row['taps'][0]['rms'],0)
        self.assertEqual(row['regions']['native:source']['rms'],0)
        self.assertGreater(row['regions']['prompt']['rms'],0)

    def test_vision_and_three_deepstack_pairs_clear_after_studies(self):
        context,_=context_fixture();s=d.BoundedDiagnostic(context,context.revision)
        with s.scope('studies'):
            for i in range(3):
                s.image('native:source',Array([1,2]),{'deepstack':[Array([3]),Array([4]),Array([5+i])]})
                s.projected.append(None)
        self.assertFalse(s.vision)
        rows=[r for r in s.rows if r['kind']=='vision']
        self.assertEqual(len(rows),12)
        self.assertEqual(rows[-2]['summary']['changed'],0)
        self.assertEqual(rows[-1]['summary']['changed'],1)
        context,_=context_fixture();s=d.BoundedDiagnostic(context,context.revision)
        with self.assertRaisesRegex(RuntimeError,'tensor bound'):
            with s.scope('studies'),patch.object(d,'MAX_ELEMENTS',1):
                s.image('native:source',Array([1,2]),{'deepstack':[Array([1])]*3})
        self.assertFalse(s.vision)

    def test_explicit_builder_runs_actual_study_assembly_three_times_and_cleans_on_cancel(self):
        f=fixture.NativeV12Tests();f.setUp()
        class Feature(Array):
            def __init__(self,value):
                self.value=value
                super().__init__([value])
            def __mul__(self,gain):return Feature(self.value*gain)
        original=f.clip.encode_from_tokens_scheduled
        def encode(tokens):
            result=original(tokens)
            return [[Array(np.repeat(np.asarray(v.values,dtype=np.float32)[None,:,None],30720,axis=-1)),meta]
                    for v,meta in result]
        try:
            with patch.object(fixture,'Features',Feature),patch.object(f.clip,'encode_from_tokens_scheduled',side_effect=encode):
                model=NS(model=object(),patches_uuid='fixture',model_options={})
                context=native.prepare_context(f.clip,model,'plain',source=f.source,revision='exact-diagnostic',
                            source_latent={'samples':Array([1])},target_latent={'samples':Array([0])})
                context=replace(context,owned_recipe=NS(verify=lambda:None))
                axis=dict(axis_id='illumination',revision='krea-illumination-v1:1',
                          plus='Bright clear lighting with strong illumination.',
                          minus='Dim lighting with low illumination and deep shadows.',coefficient=1,timing='throughout')
                before=f.clip.encodes
                result=d.build_diagnostic(context,axis,context.revision)
                self.assertEqual(f.clip.encodes-before,3)
                self.assertEqual(result.diagnostic.state,'ready')
                self.assertEqual(len([r for r in result.diagnostic.rows if r['kind']=='projected']),3)
                self.assertFalse(result.diagnostic.vision)
                self.assertFalse(result.diagnostic.projected)
                with self.assertRaisesRegex(ValueError,'revision'):d.build_diagnostic(context,axis,'wrong')
                with patch.object(d.BoundedDiagnostic,'encoded',side_effect=KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):d.build_diagnostic(context,axis,context.revision)
                f.assert_clean()
        finally:f.doCleanups()


class ObserverRoutingTests(unittest.TestCase):
    def test_enhancer_observer_returns_exact_helper_result_and_cleans_on_cancel(self):
        import test_krea_v12_enhancer as ef
        f=ef.EnhancerV12Tests();f.setUp()
        captures=[]
        try:
            enhanced,options,wrapper=f.attached()
            observer=NS(fusion=lambda *args:captures.append(args))
            with patch.object(ef.enhancer,'current_diagnostic',return_value=observer):
                result=wrapper(ef.Executor(f.model.model.diffusion_model),transformer_options=options)
            self.assertIs(captures[0][2],result)
            self.assertEqual(len(f.calls),1)
            def cancel(*args):raise KeyboardInterrupt()
            observer.fusion=cancel
            with patch.object(ef.enhancer,'current_diagnostic',return_value=observer):
                with self.assertRaises(KeyboardInterrupt):
                    wrapper(ef.Executor(f.model.model.diffusion_model),transformer_options=options)
            self.assertEqual(len(f.calls),2)
        finally:f.doCleanups()

    def test_ordinary_studies_and_off_paths_have_no_diagnostic(self):
        f=fixture.NativeV12Tests();f.setUp()
        try:
            with patch.object(d,'summarize',side_effect=AssertionError('off reduction')):
                result=studies.build_studies(f.prepare(),[card()])
                zero=studies.build_studies(f.prepare(),[card(0)])
            self.assertIsNone(result.diagnostic);self.assertIsNone(zero.diagnostic)
            self.assertIsNone(d.current())
        finally:f.doCleanups()

    def test_existing_study_and_image_routes_call_observer_without_changing_results(self):
        f=fixture.NativeV12Tests();f.setUp()
        recorder=NS(encoded=lambda *args:events.append(('encoded',args)),
                    composition=lambda *args:events.append(('composition',args)),
                    image=lambda *args:events.append(('image',args)))
        events=[]
        try:
            context=f.prepare();before=studies.build_studies(context,[card()])
            with patch.object(studies,'current_diagnostic',return_value=recorder),\
                    patch.object(NODES.hooks,'current_diagnostic',return_value=recorder):
                after=studies.build_studies(context,[card()])
            self.assertEqual(before.phases[1]['positive'][0][0].values,after.phases[1]['positive'][0][0].values)
            self.assertEqual([name for name,_ in events].count('encoded'),3)
            self.assertEqual([name for name,_ in events].count('composition'),2)
            self.assertEqual([name for name,_ in events].count('image'),6)
            self.assertFalse(NODES.hooks._busy)
        finally:f.doCleanups()

    def test_explicit_node_contract_and_receipt_gate(self):
        self.assertEqual(NODES.KGKrea2BoundedNativeDiagnosticV12.RETURN_TYPES,(NODES.nodes.STUDIES_TYPE,))
        self.assertTrue(NODES.KGKrea2NativeDiagnosticReceiptV12.OUTPUT_NODE)
        with self.assertRaises(RuntimeError):
            NODES.KGKrea2NativeDiagnosticReceiptV12().execute(**{'Native studies':NS(diagnostic=None),'Completed samples':{}})
        f=fixture.NativeV12Tests();f.setUp()
        try:
            for axis in (card(0),card(-1),card(1,'final-details')):
                with self.assertRaises(ValueError):d.build_diagnostic(f.prepare(),axis,'wrong')
        finally:f.doCleanups()


if __name__=='__main__':unittest.main()
