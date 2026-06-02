"""Tests for viv_ai.cache — AnalysisCache with key generation and deepcopy isolation."""

import unittest


class AnalysisCacheTests(unittest.TestCase):
    def setUp(self):
        from viv_ai.cache import AnalysisCache
        self.cache = AnalysisCache()

    def test_make_key_is_deterministic(self):
        key1 = self.cache.make_key('fn_summary', {'va': 0x401000}, {'type': 'object'}, {'temperature': 0}, 'ollama', 'qwen2.5')
        key2 = self.cache.make_key('fn_summary', {'va': 0x401000}, {'type': 'object'}, {'temperature': 0}, 'ollama', 'qwen2.5')
        self.assertEqual(key1, key2)

    def test_make_key_differs_on_different_input(self):
        key1 = self.cache.make_key('fn_summary', {'va': 0x401000}, {'type': 'object'}, {'temperature': 0}, 'ollama', 'qwen2.5')
        key2 = self.cache.make_key('fn_summary', {'va': 0x401100}, {'type': 'object'}, {'temperature': 0}, 'ollama', 'qwen2.5')
        self.assertNotEqual(key1, key2)

    def test_make_key_is_sha256_hex(self):
        key = self.cache.make_key('test', {'a': 1}, {'type': 'object'}, {}, 'ollama', 'test-model')
        self.assertEqual(len(key), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in key))

    def test_set_and_get_roundtrip(self):
        expected = {'status': 'ok', 'summary': 'test result'}
        key = self.cache.make_key('test', {}, {}, {}, 'ollama', 'm')
        self.cache.set(key, expected)
        actual = self.cache.get(key)
        self.assertEqual(actual, expected)

    def test_get_missing_returns_none(self):
        result = self.cache.get('nonexistent-key')
        self.assertIsNone(result)

    def test_get_returns_deep_copy(self):
        from viv_ai.cache import AnalysisCache
        cache = AnalysisCache()
        original = {'items': [1, 2, 3], 'nested': {'a': 1}}
        key = cache.make_key('t', {}, {}, {}, 'ollama', 'm')
        cache.set(key, original)
        retrieved = cache.get(key)
        # Mutating retrieved should not affect stored copy
        retrieved['items'].append(4)
        retrieved['nested']['a'] = 999
        self.assertEqual(len(cache._entries[key]['items']), 3)
        self.assertEqual(cache._entries[key]['nested']['a'], 1)

    def test_set_returns_deep_copy(self):
        stored = self.cache.set('k', {'a': [1]})
        stored['a'].append(2)
        self.assertEqual(len(self.cache._entries['k']['a']), 1)

    def test_concurrent_entries_dont_interfere(self):
        key_a = self.cache.make_key('a', {'va': 1}, {}, {}, 'ollama', 'm1')
        key_b = self.cache.make_key('b', {'va': 2}, {}, {}, 'ollama', 'm2')
        self.cache.set(key_a, {'value': 'first'})
        self.cache.set(key_b, {'value': 'second'})
        self.assertEqual(self.cache.get(key_a)['value'], 'first')
        self.assertEqual(self.cache.get(key_b)['value'], 'second')

    def test_make_key_sorts_keys_for_consistency(self):
        key_ab = self.cache.make_key('t', {'b': 2, 'a': 1}, {}, {}, 'ollama', 'm')
        key_ba = self.cache.make_key('t', {'a': 1, 'b': 2}, {}, {}, 'ollama', 'm')
        self.assertEqual(key_ab, key_ba)
