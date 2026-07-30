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
    mcp_http_api_key_env: Optional[str] = None
    mcp_http_max_request_size: int = 1024 * 1024  # 1MB default
    mcp_http_rate_limit: int = 60  # 60 requests per window
    mcp_http_rate_limit_window: int = 60  # 60 seconds
    analysis_max_nodes: int = 32
    analysis_max_edges: int = 64
    analysis_max_paths: int = 8
    analysis_max_constraints: int = 8
    analysis_max_effects: int = 8
    analysis_max_callers: int = 16
    analysis_max_callees: int = 16
    analysis_max_string_refs: int = 16
    analysis_max_import_refs: int = 16
    analysis_max_disassembly_items: int = 32
    analysis_max_functions: int = 64
    analysis_max_results: int = 32
    providers: Dict[str, ProviderConfig] = dataclasses.field(default_factory=dict)

    @property
    def read_only(self) -> bool:
        """Whether the server is in read-only mode (derived from mutation_policy)."""
        return self.mutation_policy == MutationPolicy.CONSERVATIVE_READONLY

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

        # --- HTTP transport configuration validation ---

        # Host validation
        host = self.mcp_http_bind_host
        if not host or not isinstance(host, str) or not host.strip():
            issues.append({
                'field': 'mcp_http_bind_host',
                'message': 'HTTP bind host must be a non-empty string',
                'hint': 'Set to a valid IP address (e.g. 127.0.0.1, 0.0.0.0) or hostname.',
            })

        # Port validation
        port = self.mcp_http_bind_port
        if not isinstance(port, int) or port < 0 or port > 65535:
            issues.append({
                'field': 'mcp_http_bind_port',
                'message': f'HTTP bind port must be an integer between 0 and 65535, got {port!r}',
                'hint': 'Use 0 for OS-assigned ephemeral port, or a specific port (1024-65535 for non-root).',
            })

        # Request size validation
        max_size = self.mcp_http_max_request_size
        if isinstance(max_size, int) and max_size <= 0:
            issues.append({
                'field': 'mcp_http_max_request_size',
                'message': f'HTTP max request size must be positive, got {max_size}',
                'hint': 'Set to a value in bytes (e.g. 1048576 for 1MB).',
            })

        # Rate limit validation
        rate_limit = self.mcp_http_rate_limit
        if isinstance(rate_limit, int) and rate_limit < 0:
            issues.append({
                'field': 'mcp_http_rate_limit',
                'message': f'HTTP rate limit must be non-negative, got {rate_limit}',
                'hint': 'Set to 0 to disable rate limiting, or a positive number of requests per window.',
            })

        rate_window = self.mcp_http_rate_limit_window
        if isinstance(rate_window, int) and rate_window <= 0:
            issues.append({
                'field': 'mcp_http_rate_limit_window',
                'message': f'HTTP rate limit window must be positive, got {rate_window}',
                'hint': 'Set the time window in seconds for the rate limit counter.',
            })

        # Auth config validation
        token_env = self.mcp_http_auth_token_env
        if token_env is not None and (not isinstance(token_env, str) or not token_env.strip()):
            issues.append({
                'field': 'mcp_http_auth_token_env',
                'message': 'HTTP auth token env var name must be a non-empty string when set',
                'hint': 'Set to the name of an environment variable containing the bearer token.',
            })

        key_env = self.mcp_http_api_key_env
        if key_env is not None and (not isinstance(key_env, str) or not key_env.strip()):
            issues.append({
                'field': 'mcp_http_api_key_env',
                'message': 'HTTP API key env var name must be a non-empty string when set',
                'hint': 'Set to the name of an environment variable containing the API key.',
            })

        return issues

    def to_dict(self) -> Dict[str, Any]:
        return {
            'default_provider': self.default_provider,
            'default_model': self.default_model,
            'local_only': self.local_only,
            'remote_providers_enabled': self.remote_providers_enabled,
            'read_only': self.read_only,
            'mutation_policy': self.mutation_policy.value,
            'mcp_max_concurrent_tools': self.mcp_max_concurrent_tools,
            'mcp_max_tool_seconds': self.mcp_max_tool_seconds,
            'mcp_http_bind_host': self.mcp_http_bind_host,
            'mcp_http_bind_port': self.mcp_http_bind_port,
            'mcp_http_auth_token_env': self.mcp_http_auth_token_env,
            'mcp_http_api_key_env': self.mcp_http_api_key_env,
            'mcp_http_max_request_size': self.mcp_http_max_request_size,
            'mcp_http_rate_limit': self.mcp_http_rate_limit,
            'mcp_http_rate_limit_window': self.mcp_http_rate_limit_window,
            'providers': {name: cfg.to_dict() for name, cfg in self.providers.items()},
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> 'AiConfig':
        data = dict(data or {})

        # Resolve mutation_policy.  If the high-level read_only bool is in the
        # config, it maps to the corresponding MutationPolicy value.  If both
        # are provided, mutation_policy takes precedence (read_only is ignored
        # as a derived convenience readable in server_info).
        if 'mutation_policy' in data:
            raw_policy = data['mutation_policy']
            try:
                policy = MutationPolicy(raw_policy)
            except ValueError as exc:
                raise ValueError(f'invalid mutation policy: {raw_policy}') from exc
        elif 'read_only' in data:
            policy = MutationPolicy.CONSERVATIVE_READONLY if bool(data['read_only']) else MutationPolicy.DIRECT_APPLY_ENABLED
        else:
            policy = MutationPolicy.CONSERVATIVE_READONLY

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
            mcp_http_api_key_env=data.get('mcp_http_api_key_env'),
            mcp_http_max_request_size=int(data.get('mcp_http_max_request_size', 1024 * 1024)),
            mcp_http_rate_limit=int(data.get('mcp_http_rate_limit', 60)),
            mcp_http_rate_limit_window=int(data.get('mcp_http_rate_limit_window', 60)),
            # Analysis limits — read from config JSON, fall back to dataclass defaults
            analysis_max_nodes=int(data.get('analysis_max_nodes', 32)),
            analysis_max_edges=int(data.get('analysis_max_edges', 64)),
            analysis_max_paths=int(data.get('analysis_max_paths', 8)),
            analysis_max_constraints=int(data.get('analysis_max_constraints', 8)),
            analysis_max_effects=int(data.get('analysis_max_effects', 8)),
            analysis_max_callers=int(data.get('analysis_max_callers', 16)),
            analysis_max_callees=int(data.get('analysis_max_callees', 16)),
            analysis_max_string_refs=int(data.get('analysis_max_string_refs', 16)),
            analysis_max_import_refs=int(data.get('analysis_max_import_refs', 16)),
            analysis_max_disassembly_items=int(data.get('analysis_max_disassembly_items', 32)),
            analysis_max_functions=int(data.get('analysis_max_functions', 64)),
            analysis_max_results=int(data.get('analysis_max_results', 32)),
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
