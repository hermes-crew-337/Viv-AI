import json
from typing import Any, Dict, Optional

from ..models import ProviderCapabilities
from .base import BaseProvider


class AnthropicProvider(BaseProvider):
    capabilities = ProviderCapabilities(supports_json_mode=True, supports_tools=True, local_only=False)

    def build_request(self, task_type: str, system_prompt: str, user_payload: Dict[str, Any], schema: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        options = dict(options or {})
        user_text = json.dumps({'task_type': task_type, 'payload': user_payload}, indent=2, sort_keys=True)
        return {
            'model': self.config.model,
            'max_tokens': options.get('max_tokens', 1024),
            'system': f'{system_prompt}\n\nReturn JSON matching this schema:\n{json.dumps(schema, indent=2, sort_keys=True)}',
            'messages': [
                {'role': 'user', 'content': [{'type': 'text', 'text': user_text}]},
            ],
        }
