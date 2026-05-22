from typing import Any, Dict, List, Sequence


def summarize_graph(graph: Any, max_nodes: int = 64, max_edges: int = 96) -> Dict[str, Any]:
    nodes = list(graph.getNodes())
    edges = list(graph.getEdges())

    node_items = [
        {
            'id': _fmt_node_id(nid),
            'cbva': _fmt_optional_va(nprops.get('cbva')),
            'size': nprops.get('size'),
            'out_degree': len(list(graph.getRefsFrom((nid, nprops)))),
            'in_degree': len(list(graph.getRefsTo((nid, nprops)))),
        }
        for nid, nprops in nodes
    ]
    edge_items = [
        {
            'id': str(eid),
            'from': _fmt_node_id(n1),
            'to': _fmt_node_id(n2),
            'props': dict(eprops),
        }
        for eid, n1, n2, eprops in edges
    ]

    loop_edges = [edge for edge in edges if edge[2] <= edge[1]]
    branch_nodes = [item for item in node_items if item['out_degree'] > 1]
    root_nodes = [item['id'] for item in node_items if item['in_degree'] == 0]
    leaf_nodes = [item['id'] for item in node_items if item['out_degree'] == 0]

    return {
        'node_count': len(nodes),
        'edge_count': len(edges),
        'loop_edge_count': len(loop_edges),
        'branch_node_count': len(branch_nodes),
        'roots': root_nodes[:8],
        'leaves': leaf_nodes[:8],
        'nodes': node_items[:max_nodes],
        'edges': edge_items[:max_edges],
        'truncated': {
            'nodes': max(0, len(node_items) - min(len(node_items), max_nodes)),
            'edges': max(0, len(edge_items) - min(len(edge_items), max_edges)),
        },
    }


def _fmt_node_id(value: Any) -> str:
    return _fmt_optional_va(value) or str(value)


def _fmt_optional_va(value: Any) -> str | None:
    if isinstance(value, int):
        return f'0x{value:08x}'
    return None
