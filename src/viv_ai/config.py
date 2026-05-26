import dataclasses
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .models import MutationPolicy, ProviderConfig


_DEFAULT_CONFIG_ENV = 'VIV_AI_CONFIG'
_DEFAULT_CONFIG_PATH = Path('~/.config/viv-ai/config.json').expanduser()


@dataclasses.dataclass
class AiConfig:
    default_provider: str = 'ollama'
    default_model: str = ''
    local_only: bool = True
    remote_providers_enabled: bool = False
    mutation_policy: MutationPolicy = MutationPolicy.CONSERVATIVE_READONLY
    mcp_max_concurrent_tools: int = 4
    mcp_max_tool_seconds: int = 30
    mcp_http_bind_host: str = '127.0.0.1'
    mcp_http_bind_port: int = 0
    mcp_http_auth_token_env: Optional[str] = None
    providers: Dict[str, ProviderConfig] = dataclasses.field(default_factory=dict)

    def validate(self) -> list[Dict[str, str]]:
        issues: list[Dict[str, str]] = []
        if self.default_provider not in self.providers:
            issues.append({
                'field': 'default_provider',
                'message': f'default provider {self.default_provider!r} is not configured',
                'hint': f'Add providers.{self.default_provider} to the config before using analysis features.',
            })

        for name, provider in self.providers.items():
            if not provider.endpoint:
                issues.append({
                    'field': f'providers.{name}.endpoint',
                    'message': f'provider {name!r} has no endpoint configured',
                    'hint': 'Set the provider endpoint URL before using this provider.',
                })
            if not provider.model:
                hint = 'Set an exact model name for this provider.'
                if provider.provider_type == 'ollama':
                    hint = (
                        f'Set providers.{name}.model to an exact installed model name. '
                        'Discover names with ollama list or GET /api/tags on the Ollama server.'
                    )
                issues.append({
                    'field': f'providers.{name}.model',
                    'message': f'provider {name!r} has no model configured',
                    'hint': hint,
                })
        return issues

    def to_dict(self) -> Dict[str, Any]:
        return {
            'default_provider': self.default_provider,
            'default_model': self.default_model,
            'local_only': self.local_only,
            'remote_providers_enabled': self.remote_providers_enabled,
            'mutation_policy': self.mutation_policy.value,
            'mcp_max_concurrent_tools': self.mcp_max_concurrent_tools,
            'mcp_max_tool_seconds': self.mcp_max_tool_seconds,
            'mcp_http_bind_host': self.mcp_http_bind_host,
            'mcp_http_bind_port': self.mcp_http_bind_port,
            'mcp_http_auth_token_env': self.mcp_http_auth_token_env,
            'providers': {name: cfg.to_dict() for name, cfg in self.providers.items()},
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> 'AiConfig':
        data = dict(data or {})
        raw_policy = data.get('mutation_policy', MutationPolicy.CONSERVATIVE_READONLY.value)
        try:
            policy = MutationPolicy(raw_policy)
        except ValueError as exc:
            raise ValueError(f'invalid mutation policy: {raw_policy}') from exc

        providers = {
            name: ProviderConfig.from_dict(cfg)
            for name, cfg in dict(data.get('providers') or {}).items()
        }
        return cls(
            default_provider=data.get('default_provider', 'ollama'),
            default_model=data.get('default_model', ''),
            local_only=bool(data.get('local_only', True)),
            remote_providers_enabled=bool(data.get('remote_providers_enabled', False)),
            mutation_policy=policy,
            mcp_max_concurrent_tools=int(data.get('mcp_max_concurrent_tools', 4)),
            mcp_max_tool_seconds=int(data.get('mcp_max_tool_seconds', 30)),
            mcp_http_bind_host=str(data.get('mcp_http_bind_host', '127.0.0.1')),
            mcp_http_bind_port=int(data.get('mcp_http_bind_port', 0)),
            mcp_http_auth_token_env=data.get('mcp_http_auth_token_env'),
            providers=providers,
        )

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> 'AiConfig':
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))

    def save(self, path: os.PathLike[str] | str) -> None:
        outpath = Path(path)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        with open(outpath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)


MutationPolicy = MutationPolicy
ProviderConfig = ProviderConfig


def default_config_path() -> Path:
    return _DEFAULT_CONFIG_PATH


def resolve_config_path(path: os.PathLike[str] | str | None = None) -> Optional[Path]:
    if path:
        return Path(path).expanduser()
    env_path = os.getenv(_DEFAULT_CONFIG_ENV)
    if env_path:
        return Path(env_path).expanduser()
    if _DEFAULT_CONFIG_PATH.exists():
        return _DEFAULT_CONFIG_PATH
    return None


def load_runtime_config(path: os.PathLike[str] | str | None = None) -> AiConfig:
    resolved = resolve_config_path(path)
    if resolved is None:
        return AiConfig()
    if not resolved.exists():
        raise FileNotFoundError(f'Viv-AI config file not found: {resolved}')
    return AiConfig.load(resolved)
