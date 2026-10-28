"""Host-free integration checks; numeric upstream math and model effects are not mocked proof."""
import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('enhancer_v12_tests', ROOT / 'kg_krea_v12/__init__.py',
                                             submodule_search_locations=[str(ROOT / 'kg_krea_v12')])
NODES = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = NODES
SPEC.loader.exec_module(NODES)
from enhancer_v12_tests import enhancer
from enhancer_v12_tests.native import _signature


class Fusion:
    layerwise_blocks = ()
    refiner_blocks = ()
    projector = object()

    def forward(self, x, mask=None, transformer_options=None):
        return NS(shape=(1, 2, 2560), value='original')


class Model:
    def __init__(self, dm=None, options=None, wrappers=None):
        self.model = NS(diffusion_model=dm or NS(txtfusion=Fusion(), txtlayers=12, txtdim=2560))
        self.model_options = {} if options is None else options
        self.wrappers = {} if wrappers is None else wrappers
        self.callbacks = {}

    def clone(self):
        cloned = Model(self.model.diffusion_model, copy.deepcopy(self.model_options), copy.deepcopy(self.wrappers))
        cloned.callbacks = copy.deepcopy(self.callbacks)
        return cloned

    def add_wrapper_with_key(self, kind, key, wrapper):
        # Native ModelPatcher API stores these separately until sampling prep.
        self.wrappers.setdefault(kind, {}).setdefault(key, []).append(wrapper)


class Executor:
    def __init__(self, dm, invoke=None):
        self.class_obj, self.invoke = dm, invoke

    def __call__(self, *args, **kwargs):
        if self.invoke is not None:
            return self.invoke(*args, **kwargs)
        return self.class_obj.txtfusion.forward(NS(shape=(1, 2, 12, 2560)),
                                               transformer_options=kwargs.get('transformer_options'))


class EnhancerV12Tests(unittest.TestCase):
    def setUp(self):
        self.model = Model()
        self.calls = []
        self.original_host_loader = enhancer.load_enhancer_host

        def helper(fusion, x, **kwargs):
            self.calls.append((fusion, x, kwargs))
            return NS(shape=(1, 2, 2560), value='delegated-helper'), None

        host_patch = patch.object(enhancer, 'load_enhancer_host', return_value=(helper, lambda dm: True, enhancer.ENHANCER_BLOB))
        host_patch.start()
        self.addCleanup(host_patch.stop)
        self.addCleanup(self.assertFalse, enhancer._busy)
        self.addCleanup(self.assertNotIn, 'forward', vars(self.model.model.diffusion_model.txtfusion))

    def attached(self):
        enhanced, _ = enhancer.apply_enhancer(self.model, True, 0.5)
        options = enhanced.model_options['transformer_options']
        wrapper = options['wrappers']['diffusion_model'][enhancer.WRAPPER_KEY][0]
        return enhanced, options, wrapper

    def test_off_and_zero_preserve_model_identity_without_host_reads(self):
        with patch.object(enhancer, 'load_enhancer_host', side_effect=AssertionError('OFF must not read host')):
            for enabled, strength in ((False, 1), (True, 0)):
                result, _ = enhancer.apply_enhancer(self.model, enabled, strength)
                self.assertIs(result, self.model)
        self.assertEqual(self.model.model_options, {})

    def test_options_registration_precedes_native_edit_after_pending_merge(self):
        foreign = lambda executor, *args, **kwargs: executor(*args, **kwargs)
        self.model.add_wrapper_with_key('diffusion_model', 'foreign', foreign)
        self.model.callbacks={'on_load_after':{'foreign':[foreign]}}
        enhanced, options, wrapper = self.attached()
        self.assertEqual(list(enhanced.wrappers['diffusion_model']), ['foreign'])
        self.assertEqual(list(options['wrappers']['diffusion_model']), [enhancer.WRAPPER_KEY])
        self.assertEqual(self.model.model_options, {})
        self.assertEqual(enhanced.callbacks,self.model.callbacks)
        self.assertIsNot(enhanced.callbacks,self.model.callbacks)
        observed=[]
        dm=self.model.model.diffusion_model
        def native_edit(executor, **kwargs):
            observed.append('native-edit-bypasses-inner')
            return dm.txtfusion.forward(NS(shape=(1,2,12,2560)),
                                        transformer_options=kwargs['transformer_options'])
        options['wrappers']['diffusion_model']['krea2_edit']=[native_edit]
        # Ordinary native preparation preserves options keys, then appends the
        # separately registered ModelPatcher wrappers. No source/body emulation.
        for kind, entries in enhanced.wrappers.items():
            for key, functions in entries.items():
                options['wrappers'].setdefault(kind,{}).setdefault(key,[]).extend(functions)
        chain=[fn for group in options['wrappers']['diffusion_model'].values() for fn in group]
        class Chain:
            class_obj=dm
            def __init__(self,index=0):self.index=index
            def __call__(self,*args,**kwargs):
                return chain[self.index](Chain(self.index+1),*args,**kwargs)
        result=Chain()(transformer_options=options)
        self.assertEqual(result.value,'delegated-helper')
        self.assertEqual(observed,['native-edit-bypasses-inner'])
        self.assertEqual(len(self.calls),1)
        self.assertEqual(list(options['wrappers']['diffusion_model']),
                         [enhancer.WRAPPER_KEY,'krea2_edit','foreign'])
        self.assertEqual(list(self.model.wrappers['diffusion_model']),['foreign'])

    def test_pending_duplicate_enhancer_and_edit_rejected_before_clone(self):
        for key in (enhancer.WRAPPER_KEY,*enhancer._OTHER_KEYS,'krea2_edit'):
            with self.subTest(key=key):
                model=Model()
                model.add_wrapper_with_key('diffusion_model',key,lambda *a:None)
                with patch.object(model,'clone',side_effect=AssertionError('must reject first')):
                    with self.assertRaises(RuntimeError):enhancer.apply_enhancer(model,True,1)

    def test_options_duplicate_enhancer_and_edit_rejected_before_clone(self):
        for key in (enhancer.WRAPPER_KEY,*enhancer._OTHER_KEYS,'krea2_edit'):
            with self.subTest(key=key):
                model=Model(options={'transformer_options':{'wrappers':{'diffusion_model':{key:[lambda *a:None]}}}})
                with patch.object(model,'clone',side_effect=AssertionError('must reject first')):
                    with self.assertRaises(RuntimeError):enhancer.apply_enhancer(model,True,1)

    def test_active_invokes_pinned_helper_and_preserves_model_options_and_forward(self):
        foreign = lambda *args: None
        self.model.add_wrapper_with_key('diffusion_model', 'foreign', foreign)
        original = _signature(self.model.model_options)
        enhanced, options, wrapper = self.attached()
        before = _signature(enhanced.model_options)
        for _ in range(2):
            result = wrapper(Executor(self.model.model.diffusion_model), transformer_options=options)
            self.assertEqual(result.value, 'delegated-helper')
            self.assertNotIn('forward', vars(self.model.model.diffusion_model.txtfusion))
            self.assertEqual(_signature(enhanced.model_options), before)
        self.assertEqual(_signature(self.model.model_options), original)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.calls[0][2]['strength'], 0.5)
        self.assertFalse(self.calls[0][2]['collect_debug'])

    def test_exception_and_bypass_release_hook_and_lease(self):
        _, options, wrapper = self.attached()
        dm = self.model.model.diffusion_model
        def fail(**kwargs):
            dm.txtfusion.forward(NS(shape=(1, 2, 12, 2560)))
            raise ValueError('sample failed')
        with self.assertRaisesRegex(ValueError, 'sample failed'):
            wrapper(Executor(dm, fail), transformer_options=options)
        with self.assertRaisesRegex(RuntimeError, 'was bypassed'):
            wrapper(Executor(dm, lambda **kwargs: None), transformer_options=options)
        self.assertEqual(wrapper(Executor(dm), transformer_options=options).value, 'delegated-helper')

    def test_foreign_hook_is_preserved_on_conflict(self):
        _, options, wrapper = self.attached()
        dm = self.model.model.diffusion_model
        foreign = lambda *args: None
        def mutate(**kwargs):
            dm.txtfusion.forward = foreign
        try:
            with self.assertRaisesRegex(RuntimeError, 'foreign hook mutation'):
                wrapper(Executor(dm, mutate), transformer_options=options)
            self.assertIs(dm.txtfusion.forward, foreign)
            self.assertFalse(enhancer._busy)
        finally:
            del dm.txtfusion.forward

    def test_existing_hook_or_throwing_setup_releases_lease(self):
        _, options, wrapper = self.attached()
        dm = self.model.model.diffusion_model
        dm.txtfusion.forward = lambda *args: None
        try:
            with self.assertRaisesRegex(RuntimeError, 'existing temporary'):
                wrapper(Executor(dm), transformer_options=options)
        finally:
            del dm.txtfusion.forward
        with patch.object(enhancer, '_check_architecture', side_effect=ValueError('setup failed')):
            with self.assertRaisesRegex(ValueError, 'setup failed'):
                wrapper(Executor(dm), transformer_options=options)
        self.assertFalse(enhancer._busy)
        wrapper(Executor(dm), transformer_options=options)

    def test_overlap_shared_fusion_rejected_and_outer_owner_recovers(self):
        _, options, wrapper = self.attached()
        dm = self.model.model.diffusion_model
        def overlap(**kwargs):
            with self.assertRaisesRegex(RuntimeError, 'already active'):
                wrapper(Executor(dm), transformer_options=options)
            return dm.txtfusion.forward(NS(shape=(1, 2, 12, 2560)))
        wrapper(Executor(dm, overlap), transformer_options=options)

    def test_duplicate_enhancer_wrong_edit_order_or_configuration_rejected(self):
        enhanced, options, wrapper = self.attached()
        with self.assertRaisesRegex(RuntimeError, 'already enhanced'):
            enhancer.apply_enhancer(enhanced, True, 0.5)
        self.model.add_wrapper_with_key('diffusion_model', 'krea2_edit', lambda: None)
        with self.assertRaisesRegex(RuntimeError, 'must precede'):
            enhancer.apply_enhancer(self.model, True, 0.5)
        dm = self.model.model.diffusion_model
        options[enhancer.WRAPPER_KEY]['strength'] = 1.5
        with self.assertRaisesRegex(RuntimeError, 'configuration changed'):
            wrapper(Executor(dm), transformer_options=options)

    def test_edit_reorder_after_attachment_is_rejected(self):
        _, options, wrapper = self.attached()
        own = options['wrappers']['diffusion_model'].pop(enhancer.WRAPPER_KEY)
        options['wrappers']['diffusion_model']['krea2_edit'] = [lambda: None]
        options['wrappers']['diffusion_model'][enhancer.WRAPPER_KEY] = own
        with self.assertRaisesRegex(RuntimeError, 'ownership/order changed'):
            wrapper(Executor(self.model.model.diffusion_model), transformer_options=options)

    def test_invalid_input_and_helper_output_shapes_fail_with_cleanup(self):
        _, options, wrapper = self.attached()
        dm = self.model.model.diffusion_model
        def bad_shape(**kwargs):
            return dm.txtfusion.forward(NS(shape=(1, 2, 4, 2560)))
        with self.assertRaisesRegex(RuntimeError, 'unexpected native text-fusion tensor'):
            wrapper(Executor(dm, bad_shape), transformer_options=options)
        self.assertEqual(self.calls, [])
        def helper(*args, **kwargs):
            return NS(shape=(1, 3, 2560)), None
        with patch.object(enhancer, 'load_enhancer_host', return_value=(helper, lambda dm: True, enhancer.ENHANCER_BLOB)):
            _, malformed_options, malformed_wrapper = self.attached()
            with self.assertRaisesRegex(RuntimeError, 'helper returned'):
                malformed_wrapper(Executor(dm), transformer_options=malformed_options)

    def test_node_ports_append_and_off_is_identity(self):
        node = NODES.KGKrea2NativeEnhancerV12()
        self.assertEqual(list(node.INPUT_TYPES()['required']),
                         ['Native MODEL before edit patch', 'Enhancer enabled', 'Enhancer strength'])
        self.assertEqual(node.RETURN_TYPES, ('MODEL', 'STRING'))
        self.assertIs(node.execute(**{'Native MODEL before edit patch': self.model,
                                     'Enhancer enabled': False, 'Enhancer strength': 1})[0], self.model)

    def test_missing_or_changed_upstream_source_rejects_instead_of_bypassing(self):
        module = types.ModuleType('nodes')
        module.NODE_CLASS_MAPPINGS = {}
        with patch.dict(sys.modules, {'nodes': module}):
            with self.assertRaisesRegex(RuntimeError, 'requires the pinned original'):
                self.original_host_loader()
            module.NODE_CLASS_MAPPINGS['ComfyUI-Krea2T-Enhancer'] = Fusion
            with self.assertRaisesRegex(RuntimeError, 'source revision is unverified'):
                self.original_host_loader()

    def test_foreign_architecture_rejected_before_clone_or_wrapper_installation(self):
        original = _signature(self.model.model_options)
        self.model.model.diffusion_model.txtdim = 1024
        with self.assertRaisesRegex(RuntimeError, 'verified Krea2 text-fusion architecture'):
            enhancer.apply_enhancer(self.model, True, 0.5)
        self.assertEqual(_signature(self.model.model_options), original)

    def test_actual_block_instance_override_rejected_before_owned_hook(self):
        class Block:
            def forward(self, x): return x
        class NativeFusion:
            def __init__(self):
                self.layerwise_blocks, self.refiner_blocks = [Block(), Block()], [Block(), Block()]
            def forward(self, x): return x
        dm = NS(txtfusion=NativeFusion())
        verify = lambda: enhancer._verify_fusion_instances(dm, NativeFusion, Block, NativeFusion.forward, Block.forward)
        verify()
        block = dm.txtfusion.layerwise_blocks[0]
        block.forward = lambda x: x + 1
        with self.assertRaisesRegex(RuntimeError, 'actual fusion/block forward path'):
            verify()
        self.assertNotIn('forward', vars(dm.txtfusion))
        del block.forward
        verify()

    def test_stale_block_class_and_compiled_call_rejected(self):
        class Block:
            def forward(self, x): return x
        class NativeFusion:
            def __init__(self):
                self.layerwise_blocks, self.refiner_blocks = [Block(), Block()], [Block(), Block()]
            def forward(self, x): return x
        dm = NS(txtfusion=NativeFusion())
        verify = lambda: enhancer._verify_fusion_instances(dm, NativeFusion, Block, NativeFusion.forward, Block.forward)
        class Foreign(Block): pass
        dm.txtfusion.refiner_blocks[0] = Foreign()
        with self.assertRaisesRegex(RuntimeError, 'actual fusion/block forward path'):
            verify()
        dm.txtfusion.refiner_blocks[0] = Block()
        dm.txtfusion.refiner_blocks[0]._compiled_call_impl = lambda x: x + 1
        with self.assertRaisesRegex(RuntimeError, 'actual fusion/block forward path'):
            verify()

    def test_changed_class_forward_after_admission_rejects(self):
        class Block:
            def forward(self, x): return x
        class NativeFusion:
            def __init__(self):
                self.layerwise_blocks, self.refiner_blocks = [Block(), Block()], [Block(), Block()]
            def forward(self, x): return x
        dm = NS(txtfusion=NativeFusion())
        admitted = Block.forward
        Block.forward = lambda self, x: x + 1
        with self.assertRaisesRegex(RuntimeError, 'actual fusion/block forward path'):
            enhancer._verify_fusion_instances(dm, NativeFusion, Block, NativeFusion.forward, admitted)


if __name__ == '__main__':
    unittest.main()
