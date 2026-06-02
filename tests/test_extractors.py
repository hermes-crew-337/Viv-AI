import unittest

from viv_ai.extractors import extract_binary_overview, extract_function_overview
from viv_ai.graphs import summarize_graph
from viv_ai.symbolik import summarize_symbolik_paths


class FakeGraph:
    def __init__(self):
        self._nodes = [
            (0x401000, {'cbva': 0x401000, 'size': 5}),
            (0x401005, {'cbva': 0x401005, 'size': 6}),
            (0x401010, {'cbva': 0x401010, 'size': 4}),
        ]
        self._edges = [
            ('e1', 0x401000, 0x401005, {'codeflow': True}),
            ('e2', 0x401005, 0x401010, {'codeflow': True}),
            ('e3', 0x401010, 0x401005, {'codeflow': True}),
        ]

    def getNodes(self):
        return list(self._nodes)

    def getEdges(self):
        return list(self._edges)

    def getRefsFrom(self, node):
        nid = node[0]
        return [edge for edge in self._edges if edge[1] == nid]

    def getRefsTo(self, node):
        nid = node[0]
        return [edge for edge in self._edges if edge[2] == nid]


class FakeWorkspace:
    def __init__(self):
        self.locations = {
            0x5000: (0x5000, 4, 9, 'kernel32.CreateFileA'),
            0x6000: (0x6000, 6, 11, 'EXPORT_DoThing'),
            0x7000: (0x7000, 12, 2, '"alpha"'),
            0x7010: (0x7010, 16, 2, '"beta"'),
            0x401000: (0x401000, 5, 99, None),
            0x401005: (0x401005, 5, 99, None),
            0x401010: (0x401010, 4, 99, None),
            0x402000: (0x402000, 5, 99, None),
        }
        self.function_blocks = {
            0x401000: [(0x401000, 5, 0x401000), (0x401005, 5, 0x401000), (0x401010, 4, 0x401000)],
            0x402000: [(0x402000, 5, 0x402000)],
            0x403000: [(0x403000, 7, 0x403000)],
        }
        self.xrefs_from = {
            0x401000: [(0x401000, 0x5000, 1, 1), (0x401000, 0x7000, 2, 0)],
            0x401005: [(0x401005, 0x402000, 1, 1), (0x401005, 0x7010, 2, 0)],
            0x401010: [(0x401010, 0x403000, 1, 1)],
            0x402000: [],
            0x403000: [],
        }
        self.callers = {
            0x401000: [0x400100, 0x400200],
            0x402000: [0x401005],
            0x403000: [0x401010],
        }

    def getMeta(self, key, default=None):
        return {
            'Architecture': 'amd64',
            'Platform': 'windows',
            'Format': 'pe',
        }.get(key, default)

    def getEntryPoints(self):
        return [0x401000, 0x402000]

    def getImports(self):
        return [self.locations[0x5000], (0x5004, 4, 2, 'ws2_32.send')]

    def getExports(self):
        return [(0x6000, 'FUNC', 'DoThing', 'sample.exe')]

    def getLocations(self, ltype=None):
        if ltype == 2:
            return [self.locations[0x7000], self.locations[0x7010]]
        return list(self.locations.values())

    def reprLocation(self, loc):
        return loc[3]

    def getFunctions(self):
        return [0x401000, 0x402000, 0x403000]

    def getFunctionBlocks(self, fva):
        return list(self.function_blocks[fva])

    def getName(self, va):
        return {
            0x401000: 'main',
            0x402000: 'helper',
            0x403000: 'leaf',
        }.get(va)

    def getCallers(self, va):
        return list(self.callers.get(va, ()))

    def isFunction(self, va):
        return va in self.function_blocks

    def getXrefsFrom(self, va, rtype=None):
        refs = list(self.xrefs_from.get(va, ()))
        if rtype is None:
            return refs
        return [ref for ref in refs if ref[2] == rtype]

    def getLocation(self, va):
        return self.locations.get(va)

    def reprVa(self, va):
        return f'op_{va:08x}'

    def getFunctionGraph(self, fva):
        return FakeGraph()


class ExtractorTests(unittest.TestCase):
    def test_extract_binary_overview_bounds_and_sorts(self):
        result = extract_binary_overview(
            FakeWorkspace(),
            max_entry_points=1,
            max_imports=1,
            max_exports=1,
            max_strings=1,
            max_top_functions=2,
        )

        self.assertEqual(result['metadata']['architecture'], 'amd64')
        self.assertEqual(result['entry_points'], ['0x00401000'])
        self.assertEqual(result['truncated']['entry_points'], 1)
        self.assertEqual(len(result['imports']), 1)
        self.assertEqual(result['imports'][0]['symbol'], 'kernel32.CreateFileA')
        self.assertEqual(len(result['strings']), 1)
        self.assertEqual(result['strings'][0]['value'], '"alpha"')
        self.assertEqual([item['name'] for item in result['top_functions']], ['main', 'helper'])

    def test_extract_function_overview_collects_graph_and_disassembly_slice(self):
        result = extract_function_overview(
            FakeWorkspace(),
            0x401000,
            max_callers=1,
            max_callees=2,
            max_string_refs=1,
            max_import_refs=1,
            max_disassembly_items=2,
        )

        self.assertEqual(result['function']['va'], '0x00401000')
        self.assertEqual(result['function']['name'], 'main')
        self.assertEqual(result['function']['block_count'], 3)
        self.assertEqual(result['callers'], ['0x00400100'])
        self.assertEqual(result['truncated']['callers'], 1)
        self.assertEqual(result['callees'], ['0x00402000', '0x00403000'])
        self.assertEqual(result['import_refs'][0]['symbol'], 'kernel32.CreateFileA')
        self.assertEqual(result['string_refs'][0]['value'], '"alpha"')
        self.assertEqual(len(result['disassembly_slice']), 2)
        self.assertEqual(result['graph_summary']['node_count'], 3)
        self.assertEqual(result['graph_summary']['loop_edge_count'], 1)

    def test_graph_and_symbolik_serializers_are_bounded(self):
        graph = summarize_graph(FakeGraph(), max_nodes=2, max_edges=2)
        self.assertEqual(len(graph['nodes']), 2)
        self.assertEqual(graph['truncated']['nodes'], 1)
        self.assertEqual(graph['edge_count'], 3)

        paths = [
            {
                'path_id': 'p0',
                'constraints': ['eax == 1', 'ebx != 0'],
                'effects': ['calls helper'],
                'return_relation': 'returns eax',
            },
            {
                'path_id': 'p1',
                'constraints': ['eax == 2'],
                'effects': ['calls leaf'],
                'return_relation': 'returns ebx',
            },
        ]
        summary = summarize_symbolik_paths(paths, max_paths=1, max_constraints=1, max_effects=1)
        self.assertEqual(len(summary['paths']), 1)
        self.assertEqual(summary['paths'][0]['constraints'], ['eax == 1'])
        self.assertEqual(summary['truncated']['paths'], 1)

    def test_find_functions_all(self):
        from viv_ai.extractors import find_functions

        result = find_functions(FakeWorkspace())

        names = [item['name'] for item in result]
        self.assertEqual(names, ['main', 'helper', 'leaf'])
        self.assertEqual(len(result), 3)

    def test_find_functions_name_glob(self):
        from viv_ai.extractors import find_functions

        result = find_functions(FakeWorkspace(), name_glob='*el*')

        names = [item['name'] for item in result]
        self.assertEqual(names, ['helper'])

    def test_find_functions_min_callers(self):
        from viv_ai.extractors import find_functions

        result = find_functions(FakeWorkspace(), min_callers=2)

        names = [item['name'] for item in result]
        self.assertEqual(names, ['main'])

    def test_find_functions_max_results(self):
        from viv_ai.extractors import find_functions

        result = find_functions(FakeWorkspace(), max_results=2)

        self.assertEqual(len(result), 2)


if __name__ == '__main__':
    unittest.main()
