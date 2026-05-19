import unittest


class FakeProvider:
    def __init__(self):
        self.calls = []

    def complete_structured(self, task_type, system_prompt, user_payload, schema, options=None):
        self.calls.append({
            'task_type': task_type,
            'system_prompt': system_prompt,
            'user_payload': user_payload,
            'schema': schema,
            'options': dict(options or {}),
        })
        return {
            'summary': f'{task_type} ok',
            'evidence': [user_payload.get('function', {}).get('va', 'none')],
            'confidence': 'medium',
        }


class ErrorProvider:
    def complete_structured(self, task_type, system_prompt, user_payload, schema, options=None):
        raise RuntimeError('provider exploded')


class FakeWorkspace:
    def __init__(self):
        self.locations = {
            0x5000: (0x5000, 4, 9, 'kernel32.CreateFileA'),
            0x7000: (0x7000, 12, 2, 'password=supersecret'),
            0x401000: (0x401000, 5, 99, None),
        }
        self.function_blocks = {0x401000: [(0x401000, 5, 0x401000)]}

    def getMeta(self, key, default=None):
        return {'Architecture': 'amd64', 'Platform': 'windows', 'Format': 'pe'}.get(key, default)

    def getEntryPoints(self):
        return [0x401000]

    def getImports(self):
        return [self.locations[0x5000]]

    def getExports(self):
        return []

    def getLocations(self, ltype=None):
        if ltype == 2:
            return [self.locations[0x7000]]
        return list(self.locations.values())

    def reprLocation(self, loc):
        return loc[3]

    def getFunctions(self):
        return [0x401000]

    def getFunctionBlocks(self, fva):
        return list(self.function_blocks[fva])

    def getName(self, va):
        return {0x401000: 'main'}.get(va)

    def getCallers(self, va):
        return [0x400100]

    def isFunction(self, va):
        return va in self.function_blocks

    def getXrefsFrom(self, va, rtype=None):
        refs = [
            (0x401000, 0x5000, 1, 1),
            (0x401000, 0x7000, 2, 0),
        ]
        if rtype is None:
            return refs
        return [ref for ref in refs if ref[2] == rtype]

    def getLocation(self, va):
        return self.locations.get(va)

    def reprVa(self, va):
        return f'op_{va:08x}'

    def getFunctionGraph(self, fva):
        class Graph:
            def getNodes(self_inner):
                return [(0x401000, {'cbva': 0x401000, 'size': 5})]

            def getEdges(self_inner):
                return []

            def getRefsFrom(self_inner, node):
                return []

            def getRefsTo(self_inner, node):
                return []

        return Graph()


class AnalysisServiceTests(unittest.TestCase):
    def _config(self):
        from viv_ai.config import AiConfig, ProviderConfig

        return AiConfig(
            default_provider='ollama',
            providers={
                'ollama': ProviderConfig(
                    provider_type='ollama',
                    model='cas/llama-3.2-3b-instruct:latest',
                    endpoint='http://MATRIX:11434',
                )
            },
        )

    def test_service_caches_repeated_function_analysis(self):
        from viv_ai.cache import AnalysisCache
        from viv_ai.service import AnalysisService

        provider = FakeProvider()
        service = AnalysisService(
            self._config(),
            cache=AnalysisCache(),
            provider_factory=lambda cfg: provider,
        )

        first = service.analyze_function(FakeWorkspace(), 0x401000)
        second = service.analyze_function(FakeWorkspace(), 0x401000)

        self.assertFalse(first['cache_hit'])
        self.assertTrue(second['cache_hit'])
        self.assertEqual(first['analysis']['summary'], 'function_summary ok')
        self.assertEqual(len(provider.calls), 1)

    def test_service_redacts_sensitive_string_content_before_provider_call(self):
        from viv_ai.service import AnalysisService

        provider = FakeProvider()
        service = AnalysisService(
            self._config(),
            provider_factory=lambda cfg: provider,
        )

        service.analyze_function(FakeWorkspace(), 0x401000)

        payload = provider.calls[0]['user_payload']
        self.assertEqual(payload['string_refs'][0]['value'], '<redacted:secret>')

    def test_service_wraps_provider_errors_with_task_context(self):
        from viv_ai.service import AnalysisError, AnalysisService

        service = AnalysisService(
            self._config(),
            provider_factory=lambda cfg: ErrorProvider(),
        )

        with self.assertRaises(AnalysisError) as ctx:
            service.analyze_binary(FakeWorkspace())

        self.assertIn('binary_summary', str(ctx.exception))

    def test_cache_key_changes_when_payload_changes(self):
        from viv_ai.cache import AnalysisCache

        cache = AnalysisCache()
        key1 = cache.make_key('function_summary', {'a': 1}, {'type': 'object'}, {'temperature': 0.1}, 'ollama', 'model-a')
        key2 = cache.make_key('function_summary', {'a': 2}, {'type': 'object'}, {'temperature': 0.1}, 'ollama', 'model-a')
        self.assertNotEqual(key1, key2)

    def test_cache_returns_deep_copy_so_mutations_do_not_poison_future_reads(self):
        from viv_ai.cache import AnalysisCache

        cache = AnalysisCache()
        cache.set('k', {'summary': 'ok', 'evidence': ['a']})
        first = cache.get('k')
        first['evidence'].append('b')
        second = cache.get('k')

        self.assertEqual(second['evidence'], ['a'])

    def test_redaction_scrubs_sensitive_keyed_values(self):
        from viv_ai.redaction import redact_value

        redacted = redact_value({'api_key': 'abc123', 'nested': {'password': 'hunter2'}})

        self.assertEqual(redacted['api_key'], '<redacted:secret>')
        self.assertEqual(redacted['nested']['password'], '<redacted:secret>')

    def test_service_wraps_provider_factory_failures(self):
        from viv_ai.service import AnalysisError, AnalysisService

        service = AnalysisService(
            self._config(),
            provider_factory=lambda cfg: (_ for _ in ()).throw(ValueError('bad provider config')),
        )

        with self.assertRaises(AnalysisError) as ctx:
            service.analyze_binary(FakeWorkspace())

        self.assertIn('binary_summary', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
