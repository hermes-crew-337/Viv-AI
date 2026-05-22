from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .cache import AnalysisCache
from .extractors import extract_binary_overview, extract_function_overview
from .graphs import summarize_graph
from .config import AiConfig
from .models import ProviderConfig
from .prompts import build_task_prompt_bundle
from .redaction import redact_value
from .mcp.security import assert_provider_allowed
from .symbolik import summarize_symbolik_paths
from .providers import create_provider


class AnalysisError(RuntimeError):
    pass


class AnalysisService:
    def __init__(self, config: AiConfig, cache: Optional[AnalysisCache] = None, provider_factory: Optional[Callable[[ProviderConfig], Any]] = None):
        self.config = config
        self.cache = cache or AnalysisCache()
        self.provider_factory = provider_factory or create_provider

    def provider_status(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        name = provider_name or self.config.default_provider
        cfg = self.config.providers.get(name)
        if cfg is None:
            raise AnalysisError(f'unknown provider: {name}')
        issues = [issue for issue in self.config.validate() if issue.get('field', '').startswith(f'providers.{name}.') or issue.get('field') == 'default_provider']
        available_models = []
        model_error = None
        try:
            provider = self.provider_factory(cfg)
            lister = getattr(provider, 'list_models', None)
            if callable(lister):
                available_models = list(lister() or [])
        except Exception as exc:
            model_error = str(exc)
        if model_error:
            issues = list(issues) + [{
                'field': f'providers.{name}.model',
                'message': f'failed to discover available models for provider {name!r}',
                'hint': model_error,
            }]
        return {
            'provider_name': name,
            'provider_type': cfg.provider_type,
            'endpoint': cfg.endpoint,
            'configured_model': cfg.model,
            'available_models': available_models,
            'issues': issues,
        }

    def analyze_binary(self, vw: Any, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = extract_binary_overview(vw)
        return self._run_task('binary_summary', payload, options)

    def analyze_function(self, vw: Any, fva: int, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = extract_function_overview(vw, fva)
        return self._run_task('function_summary', payload, options)

    def analyze_graph(self, graph: Any, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = summarize_graph(graph)
        return self._run_task('graph_summary', payload, options)

    def analyze_symbolik(self, paths: Any, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = summarize_symbolik_paths(paths)
        return self._run_task('symbolik_summary', payload, options)

    def _run_task(self, task_type: str, payload: Dict[str, Any], options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        provider_cfg = self._provider_config()
        prompt = build_task_prompt_bundle(task_type, redact_value(payload))
        request_options = dict(options or {})
        cache_key = self.cache.make_key(task_type, prompt['user_payload'], prompt['schema'], request_options, provider_cfg.provider_type, provider_cfg.model)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return {
                'task_type': task_type,
                'cache_hit': True,
                'analysis': cached,
                'provider': {'type': provider_cfg.provider_type, 'model': provider_cfg.model},
            }
        try:
            provider = self.provider_factory(provider_cfg)
            assert_provider_allowed(self.config, provider)
            analysis = provider.complete_structured(
                task_type=task_type,
                system_prompt=prompt['system_prompt'],
                user_payload=prompt['user_payload'],
                schema=prompt['schema'],
                options=request_options,
            )
        except Exception as exc:
            raise AnalysisError(f'{task_type} failed: {exc}') from exc
        self.cache.set(cache_key, analysis)
        return {
            'task_type': task_type,
            'cache_hit': False,
            'analysis': dict(analysis),
            'provider': {'type': provider_cfg.provider_type, 'model': provider_cfg.model},
        }

    def _provider_config(self) -> ProviderConfig:
        name = self.config.default_provider
        cfg = self.config.providers.get(name)
        if cfg is None:
            raise AnalysisError(f'unknown provider: {name}')
        return cfg
