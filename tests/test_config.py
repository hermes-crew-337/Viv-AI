import os
import tempfile
import unittest


class PhaseAConfigTests(unittest.TestCase):
    def test_default_config_uses_conservative_readonly_policy(self):
        from viv_ai.config import AiConfig, MutationPolicy

        cfg = AiConfig()

        self.assertEqual(cfg.mutation_policy, MutationPolicy.CONSERVATIVE_READONLY)
        self.assertTrue(cfg.local_only)
        self.assertFalse(cfg.remote_providers_enabled)

    def test_config_round_trip_preserves_provider_and_policy(self):
        from viv_ai.config import AiConfig, MutationPolicy, ProviderConfig

        cfg = AiConfig(
            default_provider='ollama',
            default_model='qwen2.5-coder:32b-instruct',
            mutation_policy=MutationPolicy.REVIEW_BEFORE_APPLY,
            providers={
                'ollama': ProviderConfig(
                    provider_type='ollama',
                    model='qwen2.5-coder:32b-instruct',
                    endpoint='http://MATRIX:11434',
                )
            },
        )

        clone = AiConfig.from_dict(cfg.to_dict())

        self.assertEqual(clone.default_provider, 'ollama')
        self.assertEqual(clone.default_model, 'qwen2.5-coder:32b-instruct')
        self.assertEqual(clone.mutation_policy, MutationPolicy.REVIEW_BEFORE_APPLY)
        self.assertIn('ollama', clone.providers)
        self.assertEqual(clone.providers['ollama'].endpoint, 'http://MATRIX:11434')

    def test_invalid_mutation_policy_is_rejected(self):
        from viv_ai.config import AiConfig

        with self.assertRaises(ValueError):
            AiConfig.from_dict({'mutation_policy': 'definitely-not-valid'})

    def test_config_round_trip_preserves_mcp_operational_limits(self):
        from viv_ai.config import AiConfig

        cfg = AiConfig.from_dict({
            'mcp_max_concurrent_tools': 3,
            'mcp_max_tool_seconds': 17,
            'mcp_http_bind_host': '127.0.0.1',
            'mcp_http_bind_port': 8765,
            'mcp_http_auth_token_env': 'VIV_AI_MCP_TOKEN',
        })

        clone = AiConfig.from_dict(cfg.to_dict())

        self.assertEqual(clone.mcp_max_concurrent_tools, 3)
        self.assertEqual(clone.mcp_max_tool_seconds, 17)
        self.assertEqual(clone.mcp_http_bind_host, '127.0.0.1')
        self.assertEqual(clone.mcp_http_bind_port, 8765)
        self.assertEqual(clone.mcp_http_auth_token_env, 'VIV_AI_MCP_TOKEN')

    def test_resolve_config_path_prefers_explicit_path_over_env(self):
        from viv_ai.config import resolve_config_path

        with tempfile.TemporaryDirectory() as tmpdir:
            explicit_path = os.path.join(tmpdir, 'explicit.json')
            env_path = os.path.join(tmpdir, 'env.json')
            os.environ['VIV_AI_CONFIG'] = env_path
            try:
                resolved = resolve_config_path(explicit_path)
            finally:
                os.environ.pop('VIV_AI_CONFIG', None)

        self.assertEqual(str(resolved), explicit_path)

    def test_resolve_config_path_uses_env_when_present(self):
        from viv_ai.config import resolve_config_path

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = os.path.join(tmpdir, 'env.json')
            os.environ['VIV_AI_CONFIG'] = env_path
            try:
                resolved = resolve_config_path()
            finally:
                os.environ.pop('VIV_AI_CONFIG', None)

        self.assertEqual(str(resolved), env_path)

    def test_load_runtime_config_returns_default_when_no_path_is_available(self):
        from viv_ai.config import AiConfig, load_runtime_config

        os.environ.pop('VIV_AI_CONFIG', None)
        cfg = load_runtime_config()

        self.assertIsInstance(cfg, AiConfig)
        self.assertEqual(cfg.default_provider, 'ollama')
        self.assertEqual(cfg.providers, {})

    def test_load_runtime_config_raises_for_missing_explicit_path(self):
        from viv_ai.config import load_runtime_config

        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = os.path.join(tmpdir, 'missing.json')
            with self.assertRaises(FileNotFoundError):
                load_runtime_config(missing_path)

    def test_load_runtime_config_reads_json_from_env_path(self):
        from viv_ai.config import load_runtime_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'config.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write('{"default_provider": "ollama", "providers": {"ollama": {"provider_type": "ollama", "endpoint": "http://127.0.0.1:11434", "model": "qwen2.5:72b-instruct"}}}')
            os.environ['VIV_AI_CONFIG'] = config_path
            try:
                cfg = load_runtime_config()
            finally:
                os.environ.pop('VIV_AI_CONFIG', None)

        self.assertEqual(cfg.providers['ollama'].endpoint, 'http://127.0.0.1:11434')
        self.assertEqual(cfg.providers['ollama'].model, 'qwen2.5:72b-instruct')


class PhaseQTransportConfigValidationTests(unittest.TestCase):
    """Transport configuration validation tests for Phase Q."""

    # --- Host validation ---
    def test_validate_accepts_default_host(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(providers={})
        issues = cfg.validate()
        host_issues = [i for i in issues if i['field'] == 'mcp_http_bind_host']
        self.assertEqual(host_issues, [])

    def test_validate_rejects_empty_host(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_bind_host='', providers={})
        issues = cfg.validate()
        host_issues = [i for i in issues if i['field'] == 'mcp_http_bind_host']
        self.assertEqual(len(host_issues), 1)

    def test_validate_rejects_whitespace_host(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_bind_host='   ', providers={})
        issues = cfg.validate()
        host_issues = [i for i in issues if i['field'] == 'mcp_http_bind_host']
        self.assertEqual(len(host_issues), 1)

    # --- Port validation ---
    def test_validate_accepts_valid_port(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_bind_port=8080, providers={})
        issues = cfg.validate()
        port_issues = [i for i in issues if i['field'] == 'mcp_http_bind_port']
        self.assertEqual(port_issues, [])

    def test_validate_accepts_ephemeral_port_zero(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_bind_port=0, providers={})
        issues = cfg.validate()
        port_issues = [i for i in issues if i['field'] == 'mcp_http_bind_port']
        self.assertEqual(port_issues, [])

    def test_validate_rejects_negative_port(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_bind_port=-1, providers={})
        issues = cfg.validate()
        port_issues = [i for i in issues if i['field'] == 'mcp_http_bind_port']
        self.assertEqual(len(port_issues), 1)

    def test_validate_rejects_port_out_of_range(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_bind_port=99999, providers={})
        issues = cfg.validate()
        port_issues = [i for i in issues if i['field'] == 'mcp_http_bind_port']
        self.assertEqual(len(port_issues), 1)

    # --- Request size validation ---
    def test_validate_accepts_default_request_size(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(providers={})
        issues = cfg.validate()
        size_issues = [i for i in issues if i['field'] == 'mcp_http_max_request_size']
        self.assertEqual(size_issues, [])

    def test_validate_rejects_non_positive_request_size(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_max_request_size=0, providers={})
        issues = cfg.validate()
        size_issues = [i for i in issues if i['field'] == 'mcp_http_max_request_size']
        self.assertEqual(len(size_issues), 1)

    def test_validate_rejects_negative_request_size(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_max_request_size=-100, providers={})
        issues = cfg.validate()
        size_issues = [i for i in issues if i['field'] == 'mcp_http_max_request_size']
        self.assertEqual(len(size_issues), 1)

    # --- Rate limit validation ---
    def test_validate_accepts_default_rate_limit(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(providers={})
        issues = cfg.validate()
        rl_issues = [i for i in issues if i['field'] == 'mcp_http_rate_limit']
        self.assertEqual(rl_issues, [])

    def test_validate_accepts_zero_rate_limit_disabled(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_rate_limit=0, providers={})
        issues = cfg.validate()
        rl_issues = [i for i in issues if i['field'] == 'mcp_http_rate_limit']
        self.assertEqual(rl_issues, [])

    def test_validate_rejects_negative_rate_limit(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_rate_limit=-5, providers={})
        issues = cfg.validate()
        rl_issues = [i for i in issues if i['field'] == 'mcp_http_rate_limit']
        self.assertEqual(len(rl_issues), 1)

    def test_validate_rejects_non_positive_rate_limit_window(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_rate_limit_window=0, providers={})
        issues = cfg.validate()
        rw_issues = [i for i in issues if i['field'] == 'mcp_http_rate_limit_window']
        self.assertEqual(len(rw_issues), 1)

    def test_validate_rejects_negative_rate_limit_window(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_rate_limit_window=-10, providers={})
        issues = cfg.validate()
        rw_issues = [i for i in issues if i['field'] == 'mcp_http_rate_limit_window']
        self.assertEqual(len(rw_issues), 1)

    # --- Auth env var name validation ---
    def test_validate_accepts_none_auth_token_env(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_auth_token_env=None, providers={})
        issues = cfg.validate()
        token_issues = [i for i in issues if i['field'] == 'mcp_http_auth_token_env']
        self.assertEqual(token_issues, [])

    def test_validate_accepts_valid_auth_token_env(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_auth_token_env='VIV_AI_TOKEN', providers={})
        issues = cfg.validate()
        token_issues = [i for i in issues if i['field'] == 'mcp_http_auth_token_env']
        self.assertEqual(token_issues, [])

    def test_validate_rejects_empty_auth_token_env(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_auth_token_env='', providers={})
        issues = cfg.validate()
        token_issues = [i for i in issues if i['field'] == 'mcp_http_auth_token_env']
        self.assertEqual(len(token_issues), 1)

    def test_validate_accepts_none_api_key_env(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_api_key_env=None, providers={})
        issues = cfg.validate()
        key_issues = [i for i in issues if i['field'] == 'mcp_http_api_key_env']
        self.assertEqual(key_issues, [])

    def test_validate_accepts_valid_api_key_env(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_api_key_env='VIV_AI_API_KEY', providers={})
        issues = cfg.validate()
        key_issues = [i for i in issues if i['field'] == 'mcp_http_api_key_env']
        self.assertEqual(key_issues, [])

    def test_validate_rejects_empty_api_key_env(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(mcp_http_api_key_env='', providers={})
        issues = cfg.validate()
        key_issues = [i for i in issues if i['field'] == 'mcp_http_api_key_env']
        self.assertEqual(len(key_issues), 1)

    # --- Default config produces no transport issues ---
    def test_validate_default_config_has_no_transport_issues(self):
        from viv_ai.config import AiConfig
        cfg = AiConfig(providers={})
        issues = cfg.validate()
        transport_fields = {
            'mcp_http_bind_host',
            'mcp_http_bind_port',
            'mcp_http_max_request_size',
            'mcp_http_rate_limit',
            'mcp_http_rate_limit_window',
            'mcp_http_auth_token_env',
            'mcp_http_api_key_env',
        }
        transport_issues = [i for i in issues if i['field'] in transport_fields]
        self.assertEqual(transport_issues, [])
