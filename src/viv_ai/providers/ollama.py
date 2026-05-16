import json
from typing import Any, Dict, Optional

from ..models import ProviderCapabilities
from .base import BaseProvider


class OllamaProvider(BaseProvider):
    capabilities = ProviderCapabilities(supports_json_mode=True, supports_tools=False, local_only=True)

    def build_request(self, task_type: str, system_prompt: str, user_payload: Dict[str, Any], schema: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = dict(options or {})
        prompt_body = json.dumps({'task_type': task_type, 'payload': user_payload}, indent=2, sort_keys=True)
        return {
            'model': self.config.model,
            'stream': False,
            'format': {
                'type': 'json_schema',
                'json_schema': {
                    'name': f'{task_type}_response',
                    'schema': schema,
                },
            },
            'options': options,
            'messages': [
                {'role': 'system', 'content': f'{system_prompt}\n\nReturn JSON matching this schema:\n{json.dumps(schema, indent=2, sort_keys=True)}'},
                {'role': 'user', 'content': prompt_body},
            ],
        }

    def complete_structured(self, task_type: str, system_prompt: str, user_payload: Dict[str, Any], schema: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = self.build_request(task_type, system_prompt, user_payload, schema, options)
        raw = json.loads(self._post_json_bytes(f"{self.config.endpoint.rstrip('/')}/api/chat", payload).decode('utf-8'))
        content = raw.get('message', {}).get('content', '{}')
        return json.loads(content)
