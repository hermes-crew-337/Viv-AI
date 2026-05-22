from typing import Any, Dict, Iterable, List


def summarize_symbolik_paths(paths: Iterable[Dict[str, Any]], max_paths: int = 8, max_constraints: int = 8, max_effects: int = 8) -> Dict[str, Any]:
    path_list = list(paths)
    summary_paths = []
    for path in path_list[:max_paths]:
        constraints = list(path.get('constraints', ()))
        effects = list(path.get('effects', ()))
        summary_paths.append({
            'path_id': path.get('path_id'),
            'constraints': constraints[:max_constraints],
            'effects': effects[:max_effects],
            'return_relation': path.get('return_relation'),
            'truncated': {
                'constraints': max(0, len(constraints) - min(len(constraints), max_constraints)),
                'effects': max(0, len(effects) - min(len(effects), max_effects)),
            },
        })
    return {
        'paths': summary_paths,
        'path_count': len(path_list),
        'truncated': {
            'paths': max(0, len(path_list) - min(len(path_list), max_paths)),
        },
    }
