import copy
import hashlib
import json
from typing import Any, Dict, Optional


class AnalysisCache:
    def __init__(self):
        self._entries: dict[str, dict[str, Any]] = {}

    def make_key(self, task_type: str, payload: Dict[str, Any], schema: Dict[str, Any], options: Dict[str, Any], provider_type: str, model: str) -> str:
        blob = {
            'task_type': task_type,
            'payload': payload,
            'schema': schema,
            'options': options,
            'provider_type': provider_type,
            'model': model,
        }
        encoded = json.dumps(blob, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        value = self._entries.get(key)
        if value is None:
            return None
        return copy.deepcopy(value)

    def set(self, key: str, value: Dict[str, Any]) -> Dict[str, Any]:
        stored = copy.deepcopy(value)
        self._entries[key] = stored
        return copy.deepcopy(stored)
