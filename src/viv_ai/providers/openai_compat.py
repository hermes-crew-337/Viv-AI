import json
from typing import Any, Dict, Optional

from ..models import ProviderCapabilities
from .base import BaseProvider


class OpenAICompatProvider(BaseProvider):
    capabilities = ProviderCapabilities(supports_json_mode=True, supports_tools=True, local_only=False)

    def build_request(self, task_type: str, system_prompt: str, user_payload: Dict[str, Any], schema: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = dict(options or {})
        payload_text = json.dumps({'task_type': task_type, 'payload': user_payload}, indent=2, sort_keys=True)
        return {
            'model': self.config.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': payload_text},
            ],
            'response_format': {
                'type': 'json_schema',
                'json_schema': {
                    'name': f'{task_type}_response',
                    'schema': schema,
                },
            },
            'temperature': options.get('temperature', 0),
        }
