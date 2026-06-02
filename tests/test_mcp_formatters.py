"""Tests for viv_ai.mcp.formatters — VA formatting, bounded items, and collection helpers."""

import unittest
from unittest.mock import Mock


class HexVATests(unittest.TestCase):
    def test_hexva_from_int(self):
        from viv_ai.mcp.formatters import hexva
        self.assertEqual(hexva(0x401000), '0x00401000')

    def test_hexva_from_string(self):
        from viv_ai.mcp.formatters import hexva
        self.assertEqual(hexva('0x401000'), '0x00401000')

    def test_hexva_from_zero(self):
        from viv_ai.mcp.formatters import hexva
        self.assertEqual(hexva(0), '0x00000000')

    def test_hexva_pads_eight_digits(self):
        from viv_ai.mcp.formatters import hexva
        self.assertEqual(hexva(0x7fffffffffffffff), '0x7fffffffffffffff')


class ParseVATests(unittest.TestCase):
    def test_parse_va_from_int(self):
        from viv_ai.mcp.formatters import parse_va
        self.assertEqual(parse_va(0x401000), 0x401000)

    def test_parse_va_from_hex_string(self):
        from viv_ai.mcp.formatters import parse_va
        self.assertEqual(parse_va('0x401000'), 0x401000)

    def test_parse_va_from_decimal_string(self):
        from viv_ai.mcp.formatters import parse_va
        self.assertEqual(parse_va('4198400'), 4198400)


class BoundedTests(unittest.TestCase):
    def test_under_limit(self):
        from viv_ai.mcp.formatters import bounded
        items = [{'a': 1}, {'a': 2}]
        result, truncated = bounded(items, 10)
        self.assertEqual(len(result), 2)
        self.assertEqual(truncated, 0)

    def test_over_limit(self):
        from viv_ai.mcp.formatters import bounded
        items = [{'i': x} for x in range(100)]
        result, truncated = bounded(items, 5)
        self.assertEqual(len(result), 5)
        self.assertEqual(truncated, 95)

    def test_exactly_at_limit(self):
        from viv_ai.mcp.formatters import bounded
        items = [{'i': x} for x in range(10)]
        result, truncated = bounded(items, 10)
        self.assertEqual(len(result), 10)
        self.assertEqual(truncated, 0)

    def test_at_least_one(self):
        from viv_ai.mcp.formatters import bounded
        items = [{'a': 1}]
        result, truncated = bounded(items, 0)
        self.assertEqual(len(result), 1)
        self.assertEqual(truncated, 0)


class MockVivWorkspace:
    """Simulates a vivisect workspace with locations, imports, exports, and names."""
    def __init__(self):
        self._locations = []
        self._imports = []
        self._exports = []
        self._names = []
        self._xrefs_to = {}
        self._xrefs_from = {}

    LOC_STRING = 3
    LOC_UNI = 4

    def add_location(self, lva, lsize, ltype, info):
        self._locations.append((lva, lsize, ltype, info))

    def getLocations(self, ltype):
        return [loc for loc in self._locations if loc[2] == ltype]

    def add_import(self, lva, lsize, tinfo):
        self._imports.append((lva, lsize, 0, tinfo))

    def getImports(self):
        return iter(self._imports)

    def add_export(self, va, etype, name, filename):
        self._exports.append((va, etype, name, filename))

    def getExports(self):
        return iter(self._exports)

    def add_name(self, va, name):
        self._names.append((va, name))

    def getNames(self):
        return iter(self._names)

    def getXrefsTo(self, va):
        return iter(self._xrefs_to.get(va, []))

    def getXrefsFrom(self, va):
        return iter(self._xrefs_from.get(va, []))

    @staticmethod
    def reprLocation(loc):
        return str(loc[3])


class CollectStringsTests(unittest.TestCase):
    def test_empty(self):
        from viv_ai.mcp.formatters import collect_strings
        vw = MockVivWorkspace()
        result = collect_strings(vw)
        self.assertEqual(result, [])

    def test_collects_locations(self):
        from viv_ai.mcp.formatters import collect_strings
        vw = MockVivWorkspace()
        vw.add_location(0x402000, 8, MockVivWorkspace.LOC_STRING, 'hello')
        vw.add_location(0x401000, 4, MockVivWorkspace.LOC_STRING, 'world')
        result = collect_strings(vw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['va'], '0x00401000')  # sorted
        self.assertEqual(result[0]['value'], 'world')
        self.assertEqual(result[1]['va'], '0x00402000')
        self.assertEqual(result[1]['value'], 'hello')


class CollectImportsTests(unittest.TestCase):
    def test_empty(self):
        from viv_ai.mcp.formatters import collect_imports
        vw = MockVivWorkspace()
        self.assertEqual(collect_imports(vw), [])

    def test_collects_imports_sorted(self):
        from viv_ai.mcp.formatters import collect_imports
        vw = MockVivWorkspace()
        vw.add_import(0x403000, 4, 'kernel32.CreateFileA')
        vw.add_import(0x401000, 4, 'ntdll.NtCreateFile')
        result = collect_imports(vw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['va'], '0x00401000')
        self.assertIn('NtCreateFile', result[0]['symbol'])


class CollectExportsTests(unittest.TestCase):
    def test_empty(self):
        from viv_ai.mcp.formatters import collect_exports
        vw = MockVivWorkspace()
        self.assertEqual(collect_exports(vw), [])

    def test_collects_exports(self):
        from viv_ai.mcp.formatters import collect_exports
        vw = MockVivWorkspace()
        vw.add_export(0x401000, 1, 'DllMain', 'test.dll')
        vw.add_export(0x402000, 1, 'DllEntry', 'test.dll')
        result = collect_exports(vw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['va'], '0x00401000')


class CollectNamesTests(unittest.TestCase):
    def test_no_names_getter(self):
        from viv_ai.mcp.formatters import collect_names
        vw = object()  # no getNames method
        self.assertEqual(collect_names(vw), [])

    def test_collects_names(self):
        from viv_ai.mcp.formatters import collect_names
        vw = MockVivWorkspace()
        vw.add_name(0x401000, 'main')
        vw.add_name(0x402000, 'helper')
        result = collect_names(vw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'main')


class CollectXRefsTests(unittest.TestCase):
    def test_empty(self):
        from viv_ai.mcp.formatters import collect_xrefs
        vw = MockVivWorkspace()
        self.assertEqual(collect_xrefs(vw, 0x401000, 'to'), [])

    def test_xrefs_to(self):
        from viv_ai.mcp.formatters import collect_xrefs
        vw = MockVivWorkspace()
        vw._xrefs_to[0x401000] = [(0x402000, 0x401000, 1, 0)]
        result = collect_xrefs(vw, 0x401000, 'to')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['from_va'], '0x00402000')

    def test_xrefs_from(self):
        from viv_ai.mcp.formatters import collect_xrefs
        vw = MockVivWorkspace()
        vw._xrefs_from[0x401000] = [(0x401000, 0x402000, 1, 0)]
        result = collect_xrefs(vw, 0x401000, 'from')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['to_va'], '0x00402000')
