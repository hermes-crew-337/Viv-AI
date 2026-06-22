"""Tests for viv_ai/providers/ollama.py — with HTTP mocking."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest


class TestOllamaProviderInit(unittest.TestCase):
    def test_init_with_config(self):
        from viv_ai.providers.ollama import OllamaProvider
        from viv_ai.models import ProviderConfig
        config = ProviderConfig(model="llama3:8b")
        provider = OllamaProvider(config)
        self.assertEqual(provider.config.model, "llama3:8b")


@patch('viv_ai.providers.ollama.urllib.request')
class TestOllamaProviderListModels(unittest.TestCase):
    def test_list_models_with_model(self, mock_request):
        """list_models should return [model] since model is configured."""
        from viv_ai.providers.ollama import OllamaProvider
        from viv_ai.models import ProviderConfig
        config = ProviderConfig(model="llama3:70b")
        provider = OllamaProvider(config)
        # list_models tries HTTP call; mock it
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"models": [{"name": "llama3:70b"}]}'
        mock_request.urlopen.return_value.__enter__.return_value = mock_response
        models = provider.list_models()
        self.assertIn("llama3:70b", models)


class TestOllamaProviderBuildRequest(unittest.TestCase):
    def setUp(self):
        from viv_ai.providers.ollama import OllamaProvider
        from viv_ai.models import ProviderConfig
        self.provider = OllamaProvider(ProviderConfig(model="llama3:8b"))

    def test_build_request_includes_model(self):
        request = self.provider.build_request("chat", "sys", {"input": "hello"}, {"type": "object"})
        self.assertEqual(request.get("model"), "llama3:8b")

    def test_build_request_has_messages(self):
        request = self.provider.build_request("chat", "sys", {"input": "hello"}, {"type": "object"})
        self.assertIn("messages", request)

    def test_build_request_system_message(self):
        request = self.provider.build_request("chat", "You are a bot.", {"input": "hello"}, {"type": "object"})
        messages = request.get("messages", [])
        system_msgs = [m for m in messages if m.get("role") == "system"]
        self.assertGreater(len(system_msgs), 0)

    def test_build_request_user_message(self):
        request = self.provider.build_request("chat", "sys", {"input": "hello"}, {"type": "object"})
        messages = request.get("messages", [])
        user_msgs = [m for m in messages if m.get("role") == "user"]
        self.assertGreater(len(user_msgs), 0)

    def test_build_request_stream_false(self):
        request = self.provider.build_request("chat", "sys", {"input": "hello"}, {"type": "object"})
        self.assertFalse(request.get("stream", True))


@patch('viv_ai.providers.ollama.urllib.request')
class TestOllamaProviderCompleteStructured(unittest.TestCase):
    def setUp(self):
        from viv_ai.providers.ollama import OllamaProvider
        from viv_ai.models import ProviderConfig
        self.provider = OllamaProvider(ProviderConfig(model="llama3:8b"))

    def test_complete_structured_nested_json_response(self, mock_request):
        """complete_structured expects message.content to be a JSON string."""
        import json
        mock_response = MagicMock()
        inner_content = json.dumps({"result": "ok"})
        outer = json.dumps({"message": {"content": inner_content}})
        mock_response.read.return_value = outer.encode('utf-8')
        mock_request.urlopen.return_value.__enter__.return_value = mock_response
        result = self.provider.complete_structured(
            "analyze", "You are an analyst.", {"target": "0x401000"}, {"type": "object"}
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("result"), "ok")

    def test_complete_structured_makes_http_post(self, mock_request):
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"response": "ok"}'
        mock_request.urlopen.return_value.__enter__.return_value = mock_response
        self.provider.complete_structured(
            "chat", "sys", {"input": "hi"}, {"type": "object"}
        )
        mock_request.Request.assert_called_once()
        # Check URL contains /api/chat
        args, _ = mock_request.Request.call_args
        self.assertIn("/api/chat", args[0])


if __name__ == "__main__":
    unittest.main()
