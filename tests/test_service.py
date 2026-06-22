"""Comprehensive tests for viv_ai.service — targets >95% line coverage."""

import unittest
from unittest import mock

from viv_ai.service import AnalysisService, AnalysisError
from viv_ai.models import ProviderConfig
from viv_ai.config import AiConfig


class TestAnalysisError(unittest.TestCase):
    """AnalysisError is a simple RuntimeError subclass."""

    def test_is_runtime_error(self):
        self.assertTrue(issubclass(AnalysisError, RuntimeError))

    def test_can_be_raised_and_caught(self):
        with self.assertRaises(AnalysisError):
            raise AnalysisError("test error")

    def test_message_preserved(self):
        try:
            raise AnalysisError("something went wrong")
        except AnalysisError as e:
            self.assertEqual(str(e), "something went wrong")


class TestConstructor(unittest.TestCase):
    """AnalysisService.__init__"""

    def test_default_cache_and_factory(self):
        """When cache and provider_factory are None, defaults are used."""
        config = AiConfig()
        svc = AnalysisService(config)
        # Should have a real AnalysisCache and create_provider
        self.assertIs(svc.config, config)
        from viv_ai.cache import AnalysisCache
        self.assertIsInstance(svc.cache, AnalysisCache)
        from viv_ai.providers import create_provider
        self.assertIs(svc.provider_factory, create_provider)

    def test_explicit_cache_and_factory(self):
        """Custom cache and factory are stored."""
        config = AiConfig()
        fake_cache = mock.Mock()
        fake_factory = mock.Mock()
        svc = AnalysisService(config, cache=fake_cache, provider_factory=fake_factory)
        self.assertIs(svc.cache, fake_cache)
        self.assertIs(svc.provider_factory, fake_factory)


class TestProviderConfig(unittest.TestCase):
    """_provider_config helper"""

    def test_returns_config_when_provider_exists(self):
        provider_cfg = ProviderConfig(provider_type="ollama", model="test-model")
        config = AiConfig(default_provider="myprov", providers={"myprov": provider_cfg})
        svc = AnalysisService(config)
        result = svc._provider_config()
        self.assertIs(result, provider_cfg)

    def test_raises_when_provider_missing(self):
        """Line 128: unknown provider in _provider_config."""
        config = AiConfig(default_provider="nonexistent", providers={})
        svc = AnalysisService(config)
        with self.assertRaises(AnalysisError) as ctx:
            svc._provider_config()
        self.assertIn("unknown provider: nonexistent", str(ctx.exception))


class TestProviderStatus(unittest.TestCase):
    """provider_status method — lines 28-56."""

    def test_happy_path_default_provider(self):
        """provider_name=None uses default_provider, returns success."""
        provider_cfg = ProviderConfig(
            provider_type="ollama",
            model="llama3",
            endpoint="http://localhost:11434",
        )
        config = AiConfig(default_provider="ollama", providers={"ollama": provider_cfg})
        svc = AnalysisService(config)

        result = svc.provider_status()

        self.assertEqual(result["provider_name"], "ollama")
        self.assertEqual(result["provider_type"], "ollama")
        self.assertEqual(result["endpoint"], "http://localhost:11434")
        self.assertEqual(result["configured_model"], "llama3")
        self.assertIsInstance(result["available_models"], list)
        self.assertIsInstance(result["issues"], list)

    def test_provider_with_name_arg(self):
        """Explicit provider_name overrides default."""
        provider_cfg = ProviderConfig(provider_type="openai_compat", model="gpt-4")
        config = AiConfig(default_provider="ollama", providers={"custom": provider_cfg})
        svc = AnalysisService(config)

        result = svc.provider_status(provider_name="custom")

        self.assertEqual(result["provider_name"], "custom")
        self.assertEqual(result["provider_type"], "openai_compat")

    def test_unknown_provider_raises(self):
        """Line 32: cfg is None → raise AnalysisError."""
        config = AiConfig(default_provider="ollama", providers={})
        svc = AnalysisService(config)

        with self.assertRaises(AnalysisError) as ctx:
            svc.provider_status(provider_name="ghost")
        self.assertIn("unknown provider: ghost", str(ctx.exception))

    def test_model_listing_exception_handled(self):
        """Lines 41-44: exception from provider factory / list_models stores error."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="llama3")
        config = AiConfig(default_provider="ollama", providers={"ollama": provider_cfg})
        factory = mock.Mock(side_effect=ValueError("connection refused"))
        svc = AnalysisService(config, provider_factory=factory)

        result = svc.provider_status("ollama")

        # model_error should be truthy → issues list gets appended
        self.assertEqual(result["available_models"], [])
        issues = result["issues"]
        self.assertTrue(any(
            "failed to discover available models" in i["message"]
            for i in issues
        ))

    def test_model_listing_provider_factory_ok_but_list_models_raises(self):
        """Lines 41-44: provider created OK, but list_errors raises."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="llama3")
        config = AiConfig(default_provider="ollama", providers={"ollama": provider_cfg})

        fake_provider = mock.Mock()
        fake_provider.list_models.side_effect = RuntimeError("API timeout")

        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(config, provider_factory=factory)

        result = svc.provider_status("ollama")

        self.assertEqual(result["available_models"], [])
        issues = result["issues"]
        self.assertTrue(any(
            "failed to discover available models" in i["message"]
            for i in issues
        ))

    def test_model_listing_no_attribute(self):
        """Provider has no list_models attribute → no error, empty models."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="llama3")
        config = AiConfig(default_provider="ollama", providers={"ollama": provider_cfg})

        fake_provider = mock.Mock(spec=[])  # no list_models
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(config, provider_factory=factory)

        result = svc.provider_status("ollama")

        self.assertEqual(result["available_models"], [])
        self.assertFalse(any(
            "failed to discover available models" in i["message"]
            for i in result["issues"]
        ))

    def test_model_listing_not_callable(self):
        """list_models attr exists but is not callable."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="llama3")
        config = AiConfig(default_provider="ollama", providers={"ollama": provider_cfg})

        fake_provider = mock.Mock()
        fake_provider.list_models = "not_callable"
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(config, provider_factory=factory)

        result = svc.provider_status("ollama")

        self.assertEqual(result["available_models"], [])
        self.assertFalse(any(
            "failed to discover available models" in i["message"]
            for i in result["issues"]
        ))

    def test_issues_from_config_validation_included(self):
        """Lines 33, 44-48: config.validate() issues filtered by field prefix."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="", endpoint="")
        config = AiConfig(default_provider="ollama", providers={"ollama": provider_cfg})
        svc = AnalysisService(config)

        result = svc.provider_status("ollama")

        # model is empty → validate() returns an issue for providers.ollama.model
        # endpoint is empty → validate() returns an issue for providers.ollama.endpoint
        issues = result["issues"]
        field_names = {i["field"] for i in issues}
        self.assertIn("providers.ollama.model", field_names)
        self.assertIn("providers.ollama.endpoint", field_names)


class TestAnalyzeBinary(unittest.TestCase):
    """analyze_binary dispatches to _run_task with 'binary_summary'."""

    def test_calls_run_task(self):
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={"done": True}) as rt:
            # We also mock analysis_limits_from_config and extract_binary_overview
            # since they're called inside analyze_binary.
            with mock.patch("viv_ai.service.analysis_limits_from_config", return_value={"max_nodes": 32}):
                with mock.patch("viv_ai.service.extract_binary_overview", return_value={"binary": "data"}):
                    result = svc.analyze_binary(fake_vw, options={"opt": 1})

        rt.assert_called_once_with("binary_summary", {"binary": "data"}, {"opt": 1})
        self.assertEqual(result, {"done": True})

    def test_default_options_none(self):
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={"done": True}) as rt:
            with mock.patch("viv_ai.service.analysis_limits_from_config", return_value={}):
                with mock.patch("viv_ai.service.extract_binary_overview", return_value={}):
                    result = svc.analyze_binary(fake_vw)

        rt.assert_called_once_with("binary_summary", {}, None)
        self.assertEqual(result, {"done": True})


class TestAnalyzeFunction(unittest.TestCase):
    """analyze_function dispatches to _run_task with 'function_summary'."""

    def test_calls_run_task(self):
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={"done": True}) as rt:
            with mock.patch("viv_ai.service.analysis_limits_from_config", return_value={}):
                with mock.patch("viv_ai.service.extract_function_overview", return_value={"fn": "data"}):
                    result = svc.analyze_function(fake_vw, 0x401000, options={"opt": 2})

        rt.assert_called_once_with("function_summary", {"fn": "data"}, {"opt": 2})
        self.assertEqual(result, {"done": True})

    def test_default_options(self):
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={}) as rt:
            with mock.patch("viv_ai.service.analysis_limits_from_config", return_value={}):
                with mock.patch("viv_ai.service.extract_function_overview", return_value={}):
                    svc.analyze_function(fake_vw, 0x401000)

        rt.assert_called_once_with("function_summary", {}, None)


class TestAnalyzeFunctions(unittest.TestCase):
    """analyze_functions — lines 68-81."""

    def test_all_succeed(self):
        """Lines 69-74: all functions succeed, fva is added to each result."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        svc.analyze_function = mock.Mock(side_effect=[
            {"summary": "fn1"},
            {"summary": "fn2"},
        ])

        results = svc.analyze_functions(fake_vw, [0x401000, 0x401200])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], {"summary": "fn1", "fva": "0x00401000"})
        self.assertEqual(results[1], {"summary": "fn2", "fva": "0x00401200"})

    def test_some_fail_with_analysis_error(self):
        """Lines 75-80: AnalysisError caught and error dict appended."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        svc.analyze_function = mock.Mock(side_effect=[
            {"summary": "ok"},
            AnalysisError("provider timeout"),
            {"summary": "ok2"},
        ])

        results = svc.analyze_functions(fake_vw, [0x401000, 0x401200, 0x401400])

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], {"summary": "ok", "fva": "0x00401000"})
        self.assertEqual(results[1], {
            "fva": "0x00401200",
            "error": "provider timeout",
            "task_type": "function_summary",
        })
        self.assertEqual(results[2], {"summary": "ok2", "fva": "0x00401400"})

    def test_all_fail(self):
        """All functions raise AnalysisError."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        svc.analyze_function = mock.Mock(side_effect=AnalysisError("boom"))

        results = svc.analyze_functions(fake_vw, [0x401000, 0x401200])

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn("error", r)
            self.assertEqual(r["error"], "boom")
            self.assertEqual(r["task_type"], "function_summary")

    def test_empty_list(self):
        """Line 128 (per task description): empty fvas list returns empty list."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_vw = mock.Mock()
        results = svc.analyze_functions(fake_vw, [])
        self.assertEqual(results, [])


class TestAnalyzeGraph(unittest.TestCase):
    """analyze_graph dispatches to _run_task with 'graph_summary'."""

    def test_calls_run_task(self):
        """Line 85: _run_task('graph_summary', ...)."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_graph = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={"done": True}) as rt:
            with mock.patch("viv_ai.service.summarize_graph", return_value={"g": "data"}):
                result = svc.analyze_graph(fake_graph, options={"opt": 3})

        rt.assert_called_once_with("graph_summary", {"g": "data"}, {"opt": 3})
        self.assertEqual(result, {"done": True})

    def test_default_options_none(self):
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_graph = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={}) as rt:
            with mock.patch("viv_ai.service.summarize_graph", return_value={}):
                svc.analyze_graph(fake_graph)

        rt.assert_called_once_with("graph_summary", {}, None)


class TestAnalyzeSymbolik(unittest.TestCase):
    """analyze_symbolik dispatches to _run_task with 'symbolik_summary'."""

    def test_calls_run_task(self):
        """Lines 88-89: _run_task('symbolik_summary', ...)."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_paths = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={"done": True}) as rt:
            with mock.patch("viv_ai.service.summarize_symbolik_paths", return_value={"s": "data"}):
                result = svc.analyze_symbolik(fake_paths, options={"opt": 4})

        rt.assert_called_once_with("symbolik_summary", {"s": "data"}, {"opt": 4})
        self.assertEqual(result, {"done": True})

    def test_default_options_none(self):
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        svc = AnalysisService(config)

        fake_paths = mock.Mock()
        with mock.patch.object(svc, "_run_task", return_value={}) as rt:
            with mock.patch("viv_ai.service.summarize_symbolik_paths", return_value={}):
                svc.analyze_symbolik(fake_paths)

        rt.assert_called_once_with("symbolik_summary", {}, None)


class TestRunTask(unittest.TestCase):
    """_run_task — lines 91-122."""

    def setUp(self):
        self.provider_cfg = ProviderConfig(
            provider_type="ollama",
            model="llama3",
        )
        self.config = AiConfig(
            default_provider="ollama",
            providers={"ollama": self.provider_cfg},
        )

    def test_cache_hit(self):
        """Lines 96-103: cached result returned with cache_hit=True."""
        svc = AnalysisService(self.config)
        svc.cache.get = mock.Mock(return_value={"cached": "data"})
        svc.cache.make_key = mock.Mock(return_value="some_key")

        # We must ensure _provider_config returns the provider config,
        # build_task_prompt_bundle returns a dict, redact_value returns the payload.
        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                btp.return_value = {
                    "system_prompt": "sys",
                    "user_payload": {"p": 1},
                    "schema": {"type": "object"},
                }
                result = svc._run_task("binary_summary", {"data": 1}, {"opt": 1})

        self.assertTrue(result["cache_hit"])
        self.assertEqual(result["task_type"], "binary_summary")
        self.assertEqual(result["analysis"], {"cached": "data"})
        self.assertEqual(
            result["provider"],
            {"type": "ollama", "model": "llama3"},
        )

    def test_cache_miss_success(self):
        """Lines 104-122: cache miss, provider succeeds, result cached."""
        fake_provider = mock.Mock()
        fake_provider.complete_structured.return_value = {"summary": "analysis result"}

        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(self.config, provider_factory=factory)

        svc.cache.get = mock.Mock(return_value=None)
        svc.cache.set = mock.Mock()
        svc.cache.make_key = mock.Mock(return_value="key123")

        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                with mock.patch("viv_ai.service.assert_provider_allowed") as apa:
                    btp.return_value = {
                        "system_prompt": "sys",
                        "user_payload": {"p": 1},
                        "schema": {"type": "object"},
                    }
                    result = svc._run_task("binary_summary", {"data": 1}, {"opt": 1})

        self.assertFalse(result["cache_hit"])
        self.assertEqual(result["task_type"], "binary_summary")
        self.assertEqual(result["analysis"], {"summary": "analysis result"})
        self.assertEqual(
            result["provider"],
            {"type": "ollama", "model": "llama3"},
        )
        fake_provider.complete_structured.assert_called_once_with(
            task_type="binary_summary",
            system_prompt="sys",
            user_payload={"p": 1},
            schema={"type": "object"},
            options={"opt": 1},
        )
        svc.cache.set.assert_called_once_with("key123", {"summary": "analysis result"})
        apa.assert_called_once_with(self.config, fake_provider)

    def test_provider_raises_exception(self):
        """Lines 114-115: provider exception wrapped in AnalysisError."""
        fake_provider = mock.Mock()
        fake_provider.complete_structured.side_effect = RuntimeError("API error")

        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(self.config, provider_factory=factory)

        svc.cache.get = mock.Mock(return_value=None)
        svc.cache.make_key = mock.Mock(return_value="key456")

        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                with mock.patch("viv_ai.service.assert_provider_allowed"):
                    btp.return_value = {
                        "system_prompt": "sys",
                        "user_payload": {},
                        "schema": {},
                    }
                    with self.assertRaises(AnalysisError) as ctx:
                        svc._run_task("function_summary", {}, {})

        self.assertIn("function_summary failed: API error", str(ctx.exception))

    def test_provider_assertion_fails(self):
        """assert_provider_allowed raises → wrapped in AnalysisError."""
        fake_provider = mock.Mock()
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(self.config, provider_factory=factory)

        svc.cache.get = mock.Mock(return_value=None)
        svc.cache.make_key = mock.Mock(return_value="key789")

        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                with mock.patch(
                    "viv_ai.service.assert_provider_allowed",
                    side_effect=RuntimeError("local-only policy blocks provider: ollama"),
                ):
                    btp.return_value = {
                        "system_prompt": "sys",
                        "user_payload": {},
                        "schema": {},
                    }
                    with self.assertRaises(AnalysisError) as ctx:
                        svc._run_task("graph_summary", {}, None)

        self.assertIn(
            "graph_summary failed: local-only policy blocks provider: ollama",
            str(ctx.exception),
        )

    def test_options_none_becomes_empty_dict(self):
        """Line 94: options=None becomes {}."""
        fake_provider = mock.Mock()
        fake_provider.complete_structured.return_value = {"ok": True}
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(self.config, provider_factory=factory)

        svc.cache.get = mock.Mock(return_value=None)
        svc.cache.make_key = mock.Mock(return_value="key")

        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                with mock.patch("viv_ai.service.assert_provider_allowed"):
                    btp.return_value = {
                        "system_prompt": "sys",
                        "user_payload": {},
                        "schema": {},
                    }
                    svc._run_task("symbolik_summary", {}, None)

        # options should be {} when None was passed
        call_kwargs = fake_provider.complete_structured.call_args.kwargs
        self.assertEqual(call_kwargs["options"], {})

    def test_analysis_is_dict_copy(self):
        """Line 120: analysis returned as dict(analysis)."""
        fake_provider = mock.Mock()
        fake_provider.complete_structured.return_value = {"summary": "result"}
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(self.config, provider_factory=factory)

        svc.cache.get = mock.Mock(return_value=None)
        svc.cache.make_key = mock.Mock(return_value="key")

        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                with mock.patch("viv_ai.service.assert_provider_allowed"):
                    btp.return_value = {
                        "system_prompt": "sys",
                        "user_payload": {},
                        "schema": {},
                    }
                    result = svc._run_task("binary_summary", {}, {})

        self.assertEqual(result["analysis"], {"summary": "result"})

    def test_provider_cfg_not_found_in_run_task(self):
        """_run_task calls _provider_config which raises if provider missing."""
        config = AiConfig(default_provider="missing", providers={})
        svc = AnalysisService(config)

        with self.assertRaises(AnalysisError) as ctx:
            svc._run_task("binary_summary", {}, None)
        self.assertIn("unknown provider: missing", str(ctx.exception))


class TestIntegrationThroughPublicAPI(unittest.TestCase):
    """End-to-end flows through the public methods."""

    def test_analyze_function_full_flow(self):
        """analyze_function → _run_task → provider → cached result."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        fake_provider = mock.Mock()
        fake_provider.complete_structured.return_value = {"summary": "cool"}
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(config, provider_factory=factory)

        fake_vw = mock.Mock()
        with mock.patch("viv_ai.service.analysis_limits_from_config", return_value={}):
            with mock.patch("viv_ai.service.extract_function_overview", return_value={"va": 123}):
                with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
                    with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                        with mock.patch("viv_ai.service.assert_provider_allowed"):
                            btp.return_value = {
                                "system_prompt": "sys",
                                "user_payload": {"va": 123},
                                "schema": {"type": "object"},
                            }
                            result = svc.analyze_function(fake_vw, 0x401000)

        self.assertFalse(result["cache_hit"])
        self.assertEqual(result["analysis"], {"summary": "cool"})
        self.assertEqual(result["task_type"], "function_summary")

    def test_analyze_binary_full_flow_cache_hit(self):
        """Second call hits cache."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        fake_provider = mock.Mock()
        fake_provider.complete_structured.return_value = {"summary": "binary"}
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(config, provider_factory=factory)

        # First call — cache miss
        fake_vw = mock.Mock()
        with mock.patch("viv_ai.service.analysis_limits_from_config", return_value={}):
            with mock.patch("viv_ai.service.extract_binary_overview", return_value={"arch": "x86"}):
                with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
                    with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                        with mock.patch("viv_ai.service.assert_provider_allowed"):
                            btp.return_value = {
                                "system_prompt": "sys",
                                "user_payload": {"arch": "x86"},
                                "schema": {"type": "object"},
                            }
                            result1 = svc.analyze_binary(fake_vw)

        self.assertFalse(result1["cache_hit"])

        # Second call — cache hit (the cache now has the key)
        with mock.patch("viv_ai.service.analysis_limits_from_config", return_value={}):
            with mock.patch("viv_ai.service.extract_binary_overview", return_value={"arch": "x86"}):
                with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
                    with mock.patch("viv_ai.service.redact_value", side_effect=lambda x: x):
                        btp.return_value = {
                            "system_prompt": "sys",
                            "user_payload": {"arch": "x86"},
                            "schema": {"type": "object"},
                        }
                        result2 = svc.analyze_binary(fake_vw)

        self.assertTrue(result2["cache_hit"])


class TestEdgeCases(unittest.TestCase):
    """Corner cases not covered by nominal flows."""

    def test_provider_status_with_issues_filter(self):
        """validate() returns issues including non-prefixed ones that should still appear."""
        provider_cfg = ProviderConfig(
            provider_type="ollama",
            model="m",
            endpoint="http://ok",
        )
        config = AiConfig(
            default_provider="p",
            providers={"p": provider_cfg},
            mcp_http_bind_host="",
        )
        svc = AnalysisService(config)

        result = svc.provider_status("p")

        # config.validate() includes mcp_http_bind_host issue — it doesn't match the
        # field prefix filter so it should NOT appear in result["issues"]
        issues = result["issues"]
        for issue in issues:
            self.assertNotEqual(issue["field"], "mcp_http_bind_host")

    def test_provider_status_no_list_models(self):
        """Provider with no list_models attr — controlled path through lines 38-40."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        fake_provider = mock.Mock(spec=["complete_structured"])  # no list_models
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(config, provider_factory=factory)

        result = svc.provider_status("p")
        self.assertEqual(result["available_models"], [])

    def test_provider_status_list_models_returns_none(self):
        """list_models returns None → available_models stays [] (line 40)."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        fake_provider = mock.Mock()
        fake_provider.list_models.return_value = None
        factory = mock.Mock(return_value=fake_provider)
        svc = AnalysisService(config, provider_factory=factory)

        result = svc.provider_status("p")
        self.assertEqual(result["available_models"], [])

    def test_run_task_redact_value_called(self):
        """redact_value is called on payload."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        factory = mock.Mock()
        svc = AnalysisService(config, provider_factory=factory)

        svc.cache.get = mock.Mock(return_value=None)
        svc.cache.make_key = mock.Mock(return_value="k")

        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value") as rv:
                with mock.patch("viv_ai.service.assert_provider_allowed"):
                    rv.return_value = {"redacted": True}
                    btp.return_value = {
                        "system_prompt": "sys",
                        "user_payload": {"redacted": True},
                        "schema": {},
                    }
                    # Make provider factory raise so we don't need full mock
                    factory.side_effect = RuntimeError("stop")
                    with self.assertRaises(AnalysisError):
                        svc._run_task("binary_summary", {"password": "secret"}, {})

        rv.assert_called_once_with({"password": "secret"})

    def test_run_task_cache_make_key_uses_redacted_payload(self):
        """make_key gets the *redacted* payload, not the original."""
        provider_cfg = ProviderConfig(provider_type="ollama", model="m")
        config = AiConfig(default_provider="p", providers={"p": provider_cfg})
        factory = mock.Mock()
        svc = AnalysisService(config, provider_factory=factory)

        svc.cache.get = mock.Mock(return_value=None)
        svc.cache.make_key = mock.Mock(return_value="k")

        with mock.patch("viv_ai.service.build_task_prompt_bundle") as btp:
            with mock.patch("viv_ai.service.redact_value") as rv:
                with mock.patch("viv_ai.service.assert_provider_allowed"):
                    rv.return_value = {"redacted_payload": True}
                    btp.return_value = {
                        "system_prompt": "sys",
                        "user_payload": {"redacted_payload": True},
                        "schema": {"type": "object"},
                    }
                    factory.side_effect = RuntimeError("stop")
                    with self.assertRaises(AnalysisError):
                        svc._run_task("binary_summary", {"password": "hunter2"}, {"opt": 1})

        svc.cache.make_key.assert_called_once_with(
            "binary_summary",
            {"redacted_payload": True},  # redacted user_payload
            {"type": "object"},          # schema
            {"opt": 1},                  # request_options
            "ollama",                    # provider_type
            "m",                         # model
        )


if __name__ == "__main__":
    unittest.main()
