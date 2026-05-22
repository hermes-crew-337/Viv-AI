from typing import Any, Dict

ANALYSIS_SCHEMAS: Dict[str, Dict[str, Any]] = {
    'binary_summary': {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string'},
            'evidence': {'type': 'array', 'items': {'type': 'string'}},
            'confidence': {'type': 'string'},
            'interesting_functions': {'type': 'array', 'items': {'type': 'string'}},
            'hypotheses': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['summary', 'evidence', 'confidence'],
    },
    'function_summary': {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string'},
            'evidence': {'type': 'array', 'items': {'type': 'string'}},
            'confidence': {'type': 'string'},
            'purpose': {'type': 'string'},
            'risks': {'type': 'array', 'items': {'type': 'string'}},
            'hypotheses': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['summary', 'evidence', 'confidence'],
    },
    'graph_summary': {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string'},
            'evidence': {'type': 'array', 'items': {'type': 'string'}},
            'confidence': {'type': 'string'},
            'shape': {'type': 'string'},
            'hotspots': {'type': 'array', 'items': {'type': 'string'}},
            'hypotheses': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['summary', 'evidence', 'confidence'],
    },
    'symbolik_summary': {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string'},
            'evidence': {'type': 'array', 'items': {'type': 'string'}},
            'confidence': {'type': 'string'},
            'constraints': {'type': 'array', 'items': {'type': 'string'}},
            'effects': {'type': 'array', 'items': {'type': 'string'}},
            'hypotheses': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['summary', 'evidence', 'confidence'],
    },
}

_SYSTEM_PROMPTS = {
    'binary_summary': 'You are analyzing bounded reverse-engineering context for a binary. Separate facts separately from hypotheses. Return only schema-valid JSON.',
    'function_summary': 'You are analyzing bounded reverse-engineering context for one function. Present facts separately from hypotheses. Return only schema-valid JSON.',
    'graph_summary': 'You are analyzing bounded reverse-engineering context for a control-flow graph. Present facts separately from hypotheses. Return only schema-valid JSON.',
    'symbolik_summary': 'You are analyzing bounded reverse-engineering context for symbolik paths. Present facts separately from hypotheses. Return only schema-valid JSON.',
}


def build_task_prompt_bundle(task_type: str, user_payload: Dict[str, Any]) -> Dict[str, Any]:
    if task_type not in ANALYSIS_SCHEMAS:
        raise KeyError(f'unknown task type: {task_type}')
    return {
        'task_type': task_type,
        'system_prompt': _SYSTEM_PROMPTS[task_type],
        'schema': ANALYSIS_SCHEMAS[task_type],
        'user_payload': user_payload,
    }
