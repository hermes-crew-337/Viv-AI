import dataclasses
import enum
from typing import Any, Dict, Optional


class MutationPolicy(str, enum.Enum):
    CONSERVATIVE_READONLY = 'conservative_readonly'
    REVIEW_BEFORE_APPLY = 'review_before_apply'
    DIRECT_APPLY_ENABLED = 'direct_apply_enabled'


@dataclasses.dataclass(frozen=True)
class ProviderCapabilities:
    supports_json_mode: bool = True
    supports_tools: bool = False
    local_only: bool = False
    max_context: Optional[int] = None


@dataclasses.dataclass
class ProviderConfig:
    provider_type: str = 'ollama'
    model: str = ''
    endpoint: str = ''
    api_key_env: Optional[str] = None
    timeout_seconds: int = 60
    extra: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider_type': self.provider_type,
            'model': self.model,
            'endpoint': self.endpoint,
            'api_key_env': self.api_key_env,
            'timeout_seconds': self.timeout_seconds,
            'extra': dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> 'ProviderConfig':
        data = dict(data or {})
        return cls(
            provider_type=data.get('provider_type', 'ollama'),
            model=data.get('model', ''),
            endpoint=data.get('endpoint', ''),
            api_key_env=data.get('api_key_env'),
            timeout_seconds=int(data.get('timeout_seconds', 60)),
            extra=dict(data.get('extra') or {}),
        )


@dataclasses.dataclass
class StructuredCompletionRequest:
    task_type: str
    system_prompt: str
    user_payload: Dict[str, Any]
    schema: Dict[str, Any]
    options: Dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class StructuredCompletionResult:
    content: Dict[str, Any]
    raw_response: Dict[str, Any]
