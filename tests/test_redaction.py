"""Tests for viv_ai.redaction — secret redaction in config/log output."""

import unittest


class RedactValueTests(unittest.TestCase):
    def test_plain_value_passthrough(self):
        from viv_ai.redaction import redact_value
        self.assertEqual(redact_value(42), 42)
        self.assertEqual(redact_value(True), True)
        self.assertEqual(redact_value(None), None)

    def test_redacts_string_containing_secret(self):
        from viv_ai.redaction import redact_value
        self.assertEqual(redact_value('my-secret-token'), '<redacted:secret>')

    def test_redacts_string_containing_password(self):
        from viv_ai.redaction import redact_value
        self.assertEqual(redact_value('password = hunter2'), '<redacted:secret>')

    def test_passes_through_safe_string(self):
        from viv_ai.redaction import redact_value
        self.assertEqual(redact_value('hello world'), 'hello world')

    def test_redacts_dict_key_with_secret_name(self):
        from viv_ai.redaction import redact_value
        d = {'api_key': 'sk-abc123', 'model': 'gpt-4o'}
        result = redact_value(d)
        self.assertEqual(result['api_key'], '<redacted:secret>')
        self.assertEqual(result['model'], 'gpt-4o')

    def test_redacts_dict_key_with_password_name(self):
        from viv_ai.redaction import redact_value
        d = {'password': 'hunter2'}
        result = redact_value(d)
        self.assertEqual(result['password'], '<redacted:secret>')

    def test_redacts_dict_key_with_token_name(self):
        from viv_ai.redaction import redact_value
        d = {'auth_token': 'Bearer xyz'}
        result = redact_value(d)
        self.assertEqual(result['auth_token'], '<redacted:secret>')

    def test_nested_dict_redaction(self):
        from viv_ai.redaction import redact_value
        d = {'provider': {'api_key': 'sk-abc', 'endpoint': 'http://localhost'}}
        result = redact_value(d)
        self.assertEqual(result['provider']['api_key'], '<redacted:secret>')
        self.assertEqual(result['provider']['endpoint'], 'http://localhost')

    def test_list_redaction(self):
        from viv_ai.redaction import redact_value
        items = ['safe', 'secret-token-here', 'also-safe']
        result = redact_value(items)
        self.assertEqual(result[0], 'safe')
        self.assertEqual(result[1], '<redacted:secret>')
        self.assertEqual(result[2], 'also-safe')

    def test_tuple_redaction(self):
        from viv_ai.redaction import redact_value
        items = ('safe', 'my-api-key')
        result = redact_value(items)
        self.assertEqual(result[0], 'safe')
        self.assertEqual(result[1], '<redacted:secret>')

    def test_redacts_authorization_header(self):
        from viv_ai.redaction import redact_value
        self.assertEqual(redact_value('Bearer sk-1234'), '<redacted:secret>')

    def test_case_insensitive_redaction(self):
        from viv_ai.redaction import redact_value
        self.assertEqual(redact_value('API_KEY'), '<redacted:secret>')
        self.assertEqual(redact_value('TOKEN'), '<redacted:secret>')
