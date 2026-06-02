"""Tests for viv_ai.graphs — summarize_graph with mock graph objects."""

import unittest


class _MockNode:
    """Simulate vivisect graph node tuple (nid, nprops)."""
    def __init__(self, nid, nprops=None):
        self.nid = nid
        self.nprops = _NodeProps(nprops or {})

class _NodeProps(dict):
    """Hashable/comparable wrapper for node properties dict.
    In real Vivisect, nprops is a dict-like object; this wrapper
    makes dict ordering comparisons safe for loop-edge detection.
    Comparison is based on node id (the 'cbva' value if present)."""
    def __le__(self, other):
        if isinstance(other, dict):
            return self.get('cbva', id(self)) <= other.get('cbva', id(other))
        return NotImplemented


class _MockGraph:
    """Minimal mock of a vivisect CFG/function graph."""
    def __init__(self, nodes=None, edges=None):
        # Wrap bare nprops dicts in _NodeProps for safe comparison
        _wrap = lambda t: (t[0], _NodeProps(t[1]) if isinstance(t[1], dict) else t[1])
        self._nodes = [_wrap(n) for n in (nodes or [])]
        self._edges = []
        for eid, n1, n2, eprops in (edges or []):
            self._edges.append((eid, _wrap(n1), _wrap(n2), eprops))
        # Edge format: (eid, (n1id, n1props), (n2id, n2props), eprops)
        # Use nid as the key; ignore nprops dict hashing issues
        self._refs_from = {}
        self._refs_to = {}
        for eid, n1, n2, eprops in self._edges:
            n1id = n1[0]
            n2id = n2[0]
            self._refs_from.setdefault(n1id, []).append((eid, n2, eprops))
            self._refs_to.setdefault(n2id, []).append((eid, n1, eprops))

    def getNodes(self):
        return self._nodes

    def getEdges(self):
        return self._edges

    def getRefsFrom(self, nid_and_props):
        return iter(self._refs_from.get(nid_and_props[0], []))

    def getRefsTo(self, nid_and_props):
        return iter(self._refs_to.get(nid_and_props[0], []))


class SummarizeGraphTests(unittest.TestCase):
    def test_empty_graph(self):
        from viv_ai.graphs import summarize_graph
        graph = _MockGraph()
        result = summarize_graph(graph)
        self.assertEqual(result['node_count'], 0)
        self.assertEqual(result['edge_count'], 0)
        self.assertEqual(result['roots'], [])
        self.assertEqual(result['leaves'], [])
        self.assertEqual(result['truncated']['nodes'], 0)

    def test_single_node_graph(self):
        from viv_ai.graphs import summarize_graph
        graph = _MockGraph(nodes=[(0x401000, {'cbva': 0x401000, 'size': 16})])
        result = summarize_graph(graph)
        self.assertEqual(result['node_count'], 1)
        self.assertEqual(result['edge_count'], 0)
        self.assertEqual(result['roots'], ['0x00401000'])
        self.assertEqual(result['leaves'], ['0x00401000'])

    def test_linear_chain(self):
        from viv_ai.graphs import summarize_graph
        nodes = [(0x401000, {'cbva': 0x401000, 'size': 8}),
                 (0x401008, {'cbva': 0x401008, 'size': 12})]
        edges = [('e1', nodes[0], nodes[1], {'type': 1})]
        graph = _MockGraph(nodes=nodes, edges=edges)
        result = summarize_graph(graph)
        self.assertEqual(result['node_count'], 2)
        self.assertEqual(result['edge_count'], 1)
        self.assertEqual(result['loop_edge_count'], 0)
        self.assertEqual(result['branch_node_count'], 0)
        self.assertEqual(result['roots'], ['0x00401000'])
        self.assertEqual(result['leaves'], ['0x00401008'])

    def test_branching_detection(self):
        from viv_ai.graphs import summarize_graph
        n_a = (0x401000, {'cbva': 0x401000, 'size': 8})
        n_b = (0x401008, {'cbva': 0x401008, 'size': 4})
        n_c = (0x40100c, {'cbva': 0x40100c, 'size': 4})
        nodes = [n_a, n_b, n_c]
        edges = [('e1', n_a, n_b, {}), ('e2', n_a, n_c, {})]
        graph = _MockGraph(nodes=nodes, edges=edges)
        result = summarize_graph(graph)
        self.assertEqual(result['branch_node_count'], 1)
        self.assertEqual(result['node_count'], 3)
        self.assertEqual(result['edge_count'], 2)

    def test_truncation(self):
        from viv_ai.graphs import summarize_graph
        nodes = [(0x401000 + i * 4, {'cbva': 0x401000 + i * 4, 'size': 4}) for i in range(100)]
        edges = []
        for i in range(99):
            edges.append((f'e{i}', nodes[i], nodes[i + 1], {}))
        graph = _MockGraph(nodes=nodes, edges=edges)
        result = summarize_graph(graph, max_nodes=16, max_edges=24)
        self.assertEqual(result['node_count'], 100)
        self.assertEqual(result['edge_count'], 99)
        self.assertEqual(len(result['nodes']), 16)
        self.assertEqual(len(result['edges']), 24)
        self.assertEqual(result['truncated']['nodes'], 84)
        self.assertEqual(result['truncated']['edges'], 75)

    def test_loop_edge_detection(self):
        from viv_ai.graphs import summarize_graph
        n_entry = (0x400FFC, {'cbva': 0x400FFC, 'size': 4})
        n_a = (0x401000, {'cbva': 0x401000, 'size': 4})
        n_b = (0x401004, {'cbva': 0x401004, 'size': 4})
        n_c = (0x401008, {'cbva': 0x401008, 'size': 4})
        nodes = [n_entry, n_a, n_b, n_c]
        # Entry -> A -> B -> C -> A (loop)
        edges = [('e0', n_entry, n_a, {}),
                 ('e1', n_a, n_b, {}),
                 ('e2', n_b, n_c, {}),
                 ('e3', n_c, n_a, {})]
        graph = _MockGraph(nodes=nodes, edges=edges)
        result = summarize_graph(graph)
        self.assertEqual(result['loop_edge_count'], 1)
        self.assertIn('0x00400ffc', result['roots'])

    def test_fmt_optional_va(self):
        from viv_ai.graphs import _fmt_optional_va
        self.assertEqual(_fmt_optional_va(0x401000), '0x00401000')
        self.assertIsNone(_fmt_optional_va('not_an_int'))
        self.assertIsNone(_fmt_optional_va(None))

    def test_fmt_node_id_falls_back_to_string(self):
        from viv_ai.graphs import _fmt_node_id
        self.assertEqual(_fmt_node_id(0x401000), '0x00401000')
        self.assertEqual(_fmt_node_id('orphan'), 'orphan')
