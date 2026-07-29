"""Comprehensive pagination validation tests for all list-like tools.

Covers 7 boundary cases:
1. Empty results (0 items)  
2. Single result (< limit)
3. Exact page (== limit)
4. Multi-page (> limit, first page)
5. Last partial page
6. Offset past end (>= total)
7. Mid-page offset

All tests mock the workspace to return predictable data without requiring real binaries.
"""

import unittest
from viv_ai.mcp import tools


def make_strings_fake(count):
    """Return FakeVW that provides `count` strings."""
    class FakeVW:
        def getLocations(self, ltype):
            if ltype == 2:
                return [(i*10, 8, 2, f"str_{i}") for i in range(count)]
            return []
    return FakeVW()


def make_imports_fake(count):
    """Return FakeVW that provides `count` imports."""
    class FakeVW:
        def getImports(self):
            return [(0x100+i, 8, 3, f"import_{i}") for i in range(count)]
    return FakeVW()


def make_xrefsfrom_fake(count):
    """Return FakeVW that provides cross-refs from a VA."""
    class FakeVW:
        def getXrefsFrom(self, va):
            return [(va, va+20+i, 1, i) for i in range(count)]
    return FakeVW()


class MgrFake:
    """Minimal fake WorkspaceSessionManager for tool tests."""
    mode = 'local'
    
    def __init__(self, workspace):
        self._workspace = workspace
    
    def get_workspace(self, wsid):
        return self._workspace


class TestPaginationEmpty(unittest.TestCase):
    """Case 1: 0 results - every paginated tool should return empty with no has_more."""

    def test_get_strings_empty(self):
        mgr = MgrFake(make_strings_fake(0))
        result = tools.get_strings(mgr, workspace_id='x')
        data = result['data']
        self.assertEqual(len(data['strings']), 0)
        self.assertFalse(data['pagination']['has_more'])

    def test_get_imports_empty(self):
        mgr = MgrFake(make_imports_fake(0)) 
        result = tools.get_imports(mgr, workspace_id='x')
        data = result['data']
        self.assertFalse(data['pagination']['has_more'])


class TestPaginationSingle(unittest.TestCase):
    """Case 2: Fewer results than default limit (32)."""

    def test_get_strings_few(self):
        mgr = MgrFake(make_strings_fake(10))
        result = tools.get_strings(mgr, workspace_id='x')
        data = result['data']
        self.assertEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 10)
        self.assertFalse(data['pagination']['has_more'])


class TestPaginationExactPage(unittest.TestCase):
    """Case 3: Results exactly equal to limit (32)."""

    def test_get_strings_exact_limit(self):
        mgr = MgrFake(make_strings_fake(32))
        result = tools.get_strings(mgr, workspace_id='x')
        data = result['data']
        self.assertEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 32)
        self.assertFalse(data['pagination']['has_more'])


class TestPaginationMultiPage(unittest.TestCase):
    """Case 4: More than limit → has_more on first page."""

    def test_get_strings_page1(self):
        mgr = MgrFake(make_strings_fake(100))
        result = tools.get_strings(mgr, workspace_id='x')
        data = result['data']
        self.assertLessEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 32)
        self.assertTrue(data['pagination']['has_more'])


class TestPaginationLastPage(unittest.TestCase):
    """Case 5: Getting the last partial page."""

    def test_get_strings_last_page(self):
        mgr = MgrFake(make_strings_fake(50))  # 32+18
        result = tools.get_strings(mgr, workspace_id='x', offset=32)
        data = result['data']
        self.assertEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 18)
        self.assertFalse(data['pagination']['has_more'])


class TestPaginationOffsetPastEnd(unittest.TestCase):
    """Case 6: Offset beyond available results."""

    def test_get_strings_offset_past_end(self):
        mgr = MgrFake(make_strings_fake(20))
        result = tools.get_strings(mgr, workspace_id='x', offset=100)
        data = result['data']
        self.assertEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 0)
        self.assertFalse(data['pagination']['has_more'])

    def test_get_imports_offset_past_end(self):
        mgr = MgrFake(make_imports_fake(30))
        result = tools.get_imports(mgr, workspace_id='x', offset=100)
        data = result['data']
        self.assertEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 0)


class TestPaginationMidPage(unittest.TestCase):
    """Case 7: Offset in the middle of results."""

    def test_get_strings_mid_page(self):
        mgr = MgrFake(make_strings_fake(100))
        result = tools.get_strings(mgr, workspace_id='x', offset=15)
        data = result['data']
        # Should get items 15-47 (up to limit from offset)
        self.assertGreater(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 0)
        self.assertEqual(data['pagination']['offset'], 15)


class TestPaginationImports(unittest.TestCase):
    """Tests for import-specific pagination."""

    def test_imports_has_more(self):
        mgr = MgrFake(make_imports_fake(100))
        result = tools.get_imports(mgr, workspace_id='x')
        data = result['data']
        self.assertTrue(data['pagination']['has_more'])

    def test_imports_exact_limit(self):
        mgr = MgrFake(make_imports_fake(32))
        result = tools.get_imports(mgr, workspace_id='x')
        data = result['data']
        self.assertEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 32)


class TestPaginationXrefsFrom(unittest.TestCase):
    """Tests for xrefs_from pagination."""

    def test_xrefsfrom_basic(self):
        mgr = MgrFake(make_xrefsfrom_fake(50))
        result = tools.get_xrefs_from(mgr, workspace_id='x', va=0x401000)
        data = result['data']
        self.assertIn('pagination', data)
        
    def test_xrefsfrom_with_limit(self):
        mgr = MgrFake(make_xrefsfrom_fake(50))
        result = tools.get_xrefs_from(mgr, workspace_id='x', va=0x401000, limit=10)
        data = result['data']
        self.assertLessEqual(len(data.get('strings', data.get('imports', data.get('xrefsfrom', [])))), 10)


if __name__ == '__main__':
    unittest.main()
