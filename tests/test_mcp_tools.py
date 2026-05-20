import unittest


class FakeGraph:
    def getNodes(self):
        return [(0x401000, {'cbva': 0x401000, 'size': 5}), (0x401005, {'cbva': 0x401005, 'size': 5})]

    def getEdges(self):
        return [('e1', 0x401000, 0x401005, {'codeflow': True})]

    def getRefsFrom(self, node):
        return [edge for edge in self.getEdges() if edge[1] == node[0]]

    def getRefsTo(self, node):
        return [edge for edge in self.getEdges() if edge[2] == node[0]]


class FakeVW:
    def __init__(self):
        self.meta = {'Architecture': 'amd64', 'Platform': 'linux', 'Format': 'elf'}
        self.locations = {
            0x5000: (0x5000, 8, 9, 'puts'),
            0x5008: (0x5008, 8, 9, 'strcpy'),
            0x6000: (0x6000, 5, 2, '"alpha"'),
            0x6010: (0x6010, 5, 2, '"beta"'),
            0x6020: (0x6020, 5, 2, '"gamma"'),
            0x401000: (0x401000, 5, 99, None),
            0x401005: (0x401005, 5, 99, None),
            0x402000: (0x402000, 5, 99, None),
        }
        self.names = {0x401000: 'main', 0x402000: 'helper', 0x5000: 'puts'}
        self.function_blocks = {
            0x401000: [(0x401000, 5, 0x401000), (0x401005, 5, 0x401000)],
            0x402000: [(0x402000, 5, 0x402000)],
        }
        self.xrefs_from = {
            0x401000: [(0x401000, 0x5000, 1, 0), (0x401000, 0x6000, 2, 0), (0x401000, 0x402000, 1, 0)],
            0x401005: [(0x401005, 0x5008, 1, 0), (0x401005, 0x6010, 2, 0)],
            0x402000: [(0x402000, 0x6020, 2, 0)],
        }
        self.xrefs_to = {
            0x401000: [(0x400100, 0x401000, 1, 0), (0x400200, 0x401000, 1, 0)],
            0x5000: [(0x401000, 0x5000, 1, 0)],
            0x5008: [(0x401005, 0x5008, 1, 0)],
            0x6000: [(0x401000, 0x6000, 2, 0)],
            0x6010: [(0x401005, 0x6010, 2, 0)],
            0x6020: [(0x402000, 0x6020, 2, 0)],
            0x402000: [(0x401000, 0x402000, 1, 0)],
        }
        self.exports = [(0x402000, 'FUNC', 'helper', 'sample.bin')]
        self.imports = [self.locations[0x5000], self.locations[0x5008]]
        self.symbolik_paths = {
            0x401000: [
                {
                    'path_id': 'p0',
                    'constraints': ['eax == 1', 'ebx != 0'],
                    'effects': ['calls helper', 'writes flag'],
                    'return_relation': 'returns eax',
                },
                {
                    'path_id': 'p1',
                    'constraints': ['eax == 2'],
                    'effects': ['returns early'],
                    'return_relation': 'returns 0',
                },
            ]
        }

    def getMeta(self, name):
        return self.meta.get(name)

    def getEntryPoints(self):
        return [0x401000]

    def getImports(self):
        return list(self.imports)

    def getExports(self):
        return list(self.exports)

    def getLocations(self, ltype=None):
        if ltype is None:
            return list(self.locations.values())
        return [loc for loc in self.locations.values() if loc[2] == ltype]

    def reprLocation(self, loc):
        return loc[3]

    def getFunctions(self):
        return [0x401000, 0x402000]

    def getFunctionBlocks(self, fva):
        return list(self.function_blocks[fva])

    def getCallers(self, va):
        return [xref[0] for xref in self.xrefs_to.get(va, []) if xref[2] == 1]

    def isFunction(self, va):
        return va in self.function_blocks

    def getXrefsFrom(self, va, rtype=None):
        refs = list(self.xrefs_from.get(va, []))
        if rtype is None:
            return refs
        return [ref for ref in refs if ref[2] == rtype]

    def getXrefsTo(self, va, rtype=None):
        refs = list(self.xrefs_to.get(va, []))
        if rtype is None:
            return refs
        return [ref for ref in refs if ref[2] == rtype]

    def getLocation(self, va):
        return self.locations.get(va)

    def reprVa(self, va):
        return f'op_{va:08x}'

    def getFunctionGraph(self, fva):
        return FakeGraph()

    def getName(self, va):
        return self.names.get(va)

    def getNames(self):
        return list(self.names.items())

    def getFunctionApi(self, fva):
        return None

    def getSymbolikPaths(self, fva):
        return list(self.symbolik_paths.get(fva, []))


class McpInspectionToolTests(unittest.TestCase):
    def _server(self):
        from viv_ai.mcp.server import VivAIMcpServer
        return VivAIMcpServer(workspace_loader=lambda path: FakeVW())

    def _open(self, server):
        return server.call_tool('workspace_open', path='/tmp/sample.bin')['data']['workspace_id']

    def test_registry_exposes_phase_h_read_only_tools(self):
        from viv_ai.mcp.tools import build_default_registry

        registry = build_default_registry()

        self.assertIn('get_strings', registry)
        self.assertIn('get_imports', registry)
        self.assertIn('get_exports', registry)
        self.assertIn('get_names', registry)
        self.assertIn('get_xrefs_to', registry)
        self.assertIn('get_xrefs_from', registry)
        self.assertIn('get_function_summary', registry)
        self.assertIn('get_function_graph', registry)
        self.assertIn('get_symbolik_summary', registry)

    def test_get_strings_is_bounded_and_reports_truncation(self):
        server = self._server()
        workspace_id = self._open(server)

        result = server.call_tool('get_strings', workspace_id=workspace_id, max_results=2)

        self.assertTrue(result['ok'])
        self.assertEqual(len(result['data']['strings']), 2)
        self.assertEqual(result['data']['truncated'], 1)
        self.assertIn('2 strings', result['summary'])

    def test_get_imports_and_exports_return_structured_results(self):
        server = self._server()
        workspace_id = self._open(server)

        imports_result = server.call_tool('get_imports', workspace_id=workspace_id, max_results=1)
        exports_result = server.call_tool('get_exports', workspace_id=workspace_id)

        self.assertEqual(imports_result['data']['imports'][0]['symbol'], 'puts')
        self.assertEqual(imports_result['data']['truncated'], 1)
        self.assertEqual(exports_result['data']['exports'][0]['name'], 'helper')

    def test_get_names_and_xrefs_are_bounded_and_hex_normalized(self):
        server = self._server()
        workspace_id = self._open(server)

        names_result = server.call_tool('get_names', workspace_id=workspace_id, max_results=2)
        xrefs_to_result = server.call_tool('get_xrefs_to', workspace_id=workspace_id, va='0x5000')
        xrefs_from_result = server.call_tool('get_xrefs_from', workspace_id=workspace_id, va='0x401000', max_results=2)

        self.assertEqual(len(names_result['data']['names']), 2)
        self.assertIn('0x00401000', [item['va'] for item in names_result['data']['names']])
        self.assertEqual(xrefs_to_result['data']['xrefs'][0]['from_va'], '0x00401000')
        self.assertEqual(xrefs_from_result['data']['truncated'], 1)

    def test_get_function_summary_reuses_bounded_extractor_payload(self):
        server = self._server()
        workspace_id = self._open(server)

        result = server.call_tool('get_function_summary', workspace_id=workspace_id, fva='0x401000', max_callers=1, max_import_refs=1)

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['function']['name'], 'main')
        self.assertEqual(result['data']['callers'], ['0x00400100'])
        self.assertEqual(result['data']['truncated']['import_refs'], 1)
        self.assertIn('main', result['summary'])

    def test_get_function_graph_returns_bounded_graph_summary(self):
        server = self._server()
        workspace_id = self._open(server)

        result = server.call_tool('get_function_graph', workspace_id=workspace_id, fva='0x401000', max_nodes=1, max_edges=1)

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['node_count'], 2)
        self.assertEqual(len(result['data']['nodes']), 1)
        self.assertEqual(result['data']['truncated']['nodes'], 1)
        self.assertIn('graph', result['summary'])

    def test_get_symbolik_summary_returns_bounded_path_summary(self):
        server = self._server()
        workspace_id = self._open(server)

        result = server.call_tool(
            'get_symbolik_summary',
            workspace_id=workspace_id,
            fva='0x401000',
            max_paths=1,
            max_constraints=1,
            max_effects=1,
        )

        self.assertTrue(result['ok'])
        self.assertEqual(result['data']['path_count'], 2)
        self.assertEqual(len(result['data']['paths']), 1)
        self.assertEqual(result['data']['paths'][0]['constraints'], ['eax == 1'])
        self.assertEqual(result['data']['paths'][0]['truncated']['effects'], 1)
        self.assertEqual(result['data']['truncated']['paths'], 1)
        self.assertIn('symbolik', result['summary'])


if __name__ == '__main__':
    unittest.main()
