"""Tests for viv_ai.symbolik — summarize_symbolik_paths and get_symbolik_path_dicts."""

import sys
import time
import unittest
from unittest.mock import MagicMock, patch


class SummarizeSymbolikPathsTests(unittest.TestCase):
    def test_empty_paths(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        result = summarize_symbolik_paths([])
        self.assertEqual(result['paths'], [])
        self.assertEqual(result['path_count'], 0)
        self.assertEqual(result['truncated']['paths'], 0)

    def test_single_path(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        paths = [{
            'path_id': 'P1',
            'constraints': [('eax', '>', '0')],
            'effects': [('ebx', '=', 'eax')],
            'return_relation': 'eax',
        }]
        result = summarize_symbolik_paths(paths)
        self.assertEqual(result['path_count'], 1)
        self.assertEqual(result['paths'][0]['path_id'], 'P1')
        self.assertEqual(len(result['paths'][0]['constraints']), 1)
        self.assertEqual(len(result['paths'][0]['effects']), 1)

    def test_truncation_of_paths(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        paths = [{'path_id': f'P{i}'} for i in range(20)]
        result = summarize_symbolik_paths(paths, max_paths=5)
        self.assertEqual(result['path_count'], 20)
        self.assertEqual(len(result['paths']), 5)
        self.assertEqual(result['truncated']['paths'], 15)

    def test_truncation_of_constraints(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        path = {'path_id': 'P1', 'constraints': list(range(20)), 'effects': []}
        result = summarize_symbolik_paths([path], max_paths=8, max_constraints=3)
        self.assertEqual(len(result['paths'][0]['constraints']), 3)
        self.assertEqual(result['paths'][0]['truncated']['constraints'], 17)

    def test_truncation_of_effects(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        path = {'path_id': 'P1', 'constraints': [], 'effects': list(range(20))}
        result = summarize_symbolik_paths([path], max_paths=8, max_constraints=3, max_effects=4)
        self.assertEqual(len(result['paths'][0]['effects']), 4)
        self.assertEqual(result['paths'][0]['truncated']['effects'], 16)

    def test_multiple_paths(self):
        from viv_ai.symbolik import summarize_symbolik_paths
        paths = [
            {'path_id': 'P1', 'constraints': [('a', '==', '1')], 'effects': []},
            {'path_id': 'P2', 'constraints': [], 'effects': [('b', '=', 'a')]},
        ]
        result = summarize_symbolik_paths(paths)
        self.assertEqual(result['path_count'], 2)
        self.assertEqual(result['paths'][0]['path_id'], 'P1')
        self.assertEqual(result['paths'][1]['path_id'], 'P2')


class GetSymbolikPathDictsTests(unittest.TestCase):
    """Tests for get_symbolik_path_dicts, mocking the Vivisect symbolik chain."""

    def setUp(self):
        # The real vivisect is always importable (it's installed).  We use
        # patch.object on the real modules' attributes so the function's
        # dynamic imports inside the try/except block find our mocks.
        import vivisect.symboliks.analysis as va_mod
        import vivisect.tools.graphutil as vg_mod

        self._patchers = []

        p1 = patch.object(va_mod, 'getSymbolikAnalysisContext')
        p2 = patch.object(va_mod, 'EFFTYPE_CONSTRAIN', 1)
        p3 = patch.object(vg_mod, 'getLongPath')

        self._mock_gasc = p1.start()
        p2.start()
        self._mock_glp = p3.start()

        self._patchers.extend([p1, p2, p3])

        self._va_mod = va_mod
        self._vg_mod = vg_mod

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def _mock_path_result(self, emu, effects):
        """Return a tuple matching what getSymbolikPaths yields per path."""
        return (emu, effects)

    def _make_emu(self, return_val='<return eax>'):
        emu = MagicMock()
        emu.getFunctionReturn.return_value.reduce.return_value = return_val
        return emu

    def _make_effect(self, efftype, text='<effect>', reduce_ok=True):
        eff = MagicMock()
        eff.efftype = efftype
        eff.__str__.return_value = text
        if not reduce_ok:
            eff.reduce.side_effect = ValueError('reduce failed')
        return eff

    def test_normal_paths(self):
        """Happy path: multiple paths with constraints and effects."""
        emu1 = self._make_emu('<ret eax>')
        eff1 = self._make_effect(1, 'eax > 0')  # efftype 1 = EFFTYPE_CONSTRAIN
        eff2 = self._make_effect(2, 'call helper')

        emu2 = self._make_emu('<ret 0>')
        eff3 = self._make_effect(1, 'eax == 0')

        mock_gen = iter([
            self._mock_path_result(emu1, [eff1, eff2]),
            self._mock_path_result(emu2, [eff3]),
        ])

        symctx = self._mock_gasc.return_value
        symctx.getSymbolikGraph.return_value = MagicMock()
        symctx.getSymbolikPaths.return_value = mock_gen

        from viv_ai.symbolik import get_symbolik_path_dicts

        result = get_symbolik_path_dicts(
            MagicMock(), 0x401000,
            max_paths=10,
            per_path_timeout=5.0,
            total_timeout=30.0,
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['path_id'], 'p0')
        self.assertIn('eax > 0', result[0]['constraints'])
        self.assertIn('call helper', result[0]['effects'])
        self.assertEqual(result[0]['return_relation'], '<ret eax>')

        self.assertEqual(result[1]['path_id'], 'p1')
        self.assertIn('eax == 0', result[1]['constraints'])
        self.assertEqual(result[1]['return_relation'], '<ret 0>')

    def test_max_paths_respected(self):
        """Only up to max_paths are consumed from the generator."""
        emu = self._make_emu()
        eff = self._make_effect(1, 'x')
        many_paths = [self._mock_path_result(emu, [eff]) for _ in range(500)]

        mock_gen = iter(many_paths)
        symctx = self._mock_gasc.return_value
        symctx.getSymbolikGraph.return_value = MagicMock()
        symctx.getSymbolikPaths.return_value = mock_gen

        from viv_ai.symbolik import get_symbolik_path_dicts

        result = get_symbolik_path_dicts(
            MagicMock(), 0x401000,
            max_paths=100,
            per_path_timeout=5.0,
            total_timeout=30.0,
        )

        self.assertEqual(len(result), 100)

    def test_per_path_timeout_returns_partial(self):
        """If consuming a path times out, we return what we have so far."""
        emu = self._make_emu()
        eff = self._make_effect(1, 'x')

        def _slow_gen():
            yield self._mock_path_result(emu, [eff])  # first path fast
            time.sleep(10)  # second path hangs

        symctx = self._mock_gasc.return_value
        symctx.getSymbolikGraph.return_value = MagicMock()
        symctx.getSymbolikPaths.return_value = _slow_gen()

        from viv_ai.symbolik import get_symbolik_path_dicts

        result = get_symbolik_path_dicts(
            MagicMock(), 0x401000,
            max_paths=10,
            per_path_timeout=0.5,  # very short per-path timeout
            total_timeout=30.0,    # generous total
        )

        # We should get the first path but time out on the second.
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['path_id'], 'p0')

    def test_total_timeout_returns_partial(self):
        """Total deadline cuts off even if individual paths are fast."""
        emu = self._make_emu()
        eff = self._make_effect(1, 'x')

        def _fast_gen():
            for i in range(100_000):  # huge so even fast iteration can't finish
                yield self._mock_path_result(emu, [eff])

        symctx = self._mock_gasc.return_value
        symctx.getSymbolikGraph.return_value = MagicMock()
        symctx.getSymbolikPaths.return_value = _fast_gen()

        from viv_ai.symbolik import get_symbolik_path_dicts

        result = get_symbolik_path_dicts(
            MagicMock(), 0x401000,
            max_paths=100_000,
            per_path_timeout=5.0,
            total_timeout=0.05,  # tight deadline — 50ms
        )

        # Should have a partial result, but not all 100k.
        self.assertGreater(len(result), 0)
        self.assertLess(len(result), 100_000)

    def test_get_long_path_ordering_used(self):
        """Verify that getLongPath and the graph are wired into getSymbolikPaths."""
        symctx = self._mock_gasc.return_value
        symctx.getSymbolikGraph.return_value = '<mock-sg>'
        symctx.getSymbolikPaths.return_value = iter([])

        from viv_ai.symbolik import get_symbolik_path_dicts
        get_symbolik_path_dicts(MagicMock(), 0x401000, max_paths=5)

        # getSymbolikGraph should have been called
        symctx.getSymbolikGraph.assert_called_once()
        # getLongPath should have been called with the graph
        self._mock_glp.assert_called_once_with('<mock-sg>')
        # getSymbolikPaths should have been called with paths=getLongPath result + graph
        symctx.getSymbolikPaths.assert_called_once_with(
            0x401000,
            paths=self._mock_glp.return_value,
            graph='<mock-sg>',
        )

    def test_module_unavailable_raises_runtime_error(self):
        """When vivisect.symboliks is not importable, raises RuntimeError."""
        for p in self._patchers:
            p.stop()

        # Patch the real modules so the import inside the function fails.
        # We create a mock module that raises ImportError when trying to
        # import from vivisect.symboliks.analysis and vivisect.tools.graphutil.
        import vivisect.symboliks.analysis as va_mod
        import vivisect.tools.graphutil as vg_mod

        # Remove the names from the real modules so the import raises
        original_gasc = va_mod.getSymbolikAnalysisContext
        original_eff = getattr(va_mod, 'EFFTYPE_CONSTRAIN', None)
        original_glp = vg_mod.getLongPath

        delattr(va_mod, 'getSymbolikAnalysisContext')
        # EFFTYPE_CONSTRAIN doesn't exist in the real module, so
        # from...import will raise on getSymbolikAnalysisContext

        try:
            from viv_ai.symbolik import get_symbolik_path_dicts
            with self.assertRaises(RuntimeError) as ctx:
                get_symbolik_path_dicts(MagicMock(), 0x401000)
            self.assertIn('symbolik path provider is unavailable', str(ctx.exception))
        finally:
            va_mod.getSymbolikAnalysisContext = original_gasc
            if original_eff is not None:
                va_mod.EFFTYPE_CONSTRAIN = original_eff
            vg_mod.getLongPath = original_glp
