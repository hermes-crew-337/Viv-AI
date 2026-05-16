import abc
import json
import os
import urllib.request
from typing import Any, Dict, Optional

from ..models import ProviderCapabilities, ProviderConfig


class BaseProvider(abc.ABC):
    capabilities = ProviderCapabilities()

    def __init__(self, config: ProviderConfig):
        self.config = config

    def list_models(self):
        if self.config.model:
            return [self.config.model]
        return []

    @abc.abstractmethod
    def build_request(self, task_type: str, system_prompt: str, user_payload: Dict[str, Any], schema: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def complete_structured(self, task_type: str, system_prompt: str, user_payload: Dict[str, Any], schema: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError('provider does not implement complete_structured yet')

    def _api_key(self) -> Optional[str]:
        if not self.config.api_key_env:
            return None
        return os.getenv(self.config.api_key_env)

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {'Content-Type': 'application/json'}
        if extra:
            headers.update(extra)
        return headers

    def _post_json_bytes(self, url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> bytes:
        body = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request(url, data=body, headers=self._headers(headers), method='POST')
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as resp:
            return resp.read()
