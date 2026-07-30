import importlib
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest


class PhaseAPluginLoadingTests(unittest.TestCase):
    def test_package_can_be_loaded_via_viv_extension_loader_style(self):
        init_path = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'viv_ai' / '__init__.py'
        spec = importlib.util.spec_from_file_location('viv_ai', init_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        events = []

        class FakeVW:
            def vprint(self, message):
                events.append(message)

        result = module.vivExtension(FakeVW(), None)

        self.assertTrue(callable(module.vivExtension))
        self.assertEqual(result['name'], 'viv_ai')
        self.assertIn('config_path', result)
        self.assertTrue(any('Phase P core loaded without GUI' in event for event in events))

    def test_top_level_runtime_import_and_plugin_wrapper_share_entrypoint(self):
        plugin_root = pathlib.Path(__file__).resolve().parents[1] / 'src'
        sys.path.insert(0, str(plugin_root))
        self.addCleanup(lambda: sys.path.remove(str(plugin_root)))

        package = importlib.import_module('viv_ai')
        plugin = importlib.import_module('viv_ai.plugin')

        self.assertIs(plugin.vivExtension, package.vivExtension)

    def test_plugin_bootstrap_with_no_config_file_uses_default_in_memory(self):
        """Verify plugin falls back to default in-memory config when no file exists."""
        init_path = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'viv_ai' / '__init__.py'
        spec = importlib.util.spec_from_file_location('viv_ai', init_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        # Ensure no config file will be found
        os.environ.pop('VIV_AI_CONFIG', None)
        events = []

        class FakeVW:
            def vprint(self, message):
                events.append(message)

        result = module.vivExtension(FakeVW(), None)

        self.assertIsNone(result['config_path'],
                          'expected no config path when no config file exists')
        self.assertTrue(any('with default in-memory config' in event for event in events),
                        'expected log message about default in-memory config')

    def test_plugin_bootstrap_with_explicit_env_config_resolves_to_existing_path(self):
        """Verify plugin uses env var config path when file exists."""
        init_path = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'viv_ai' / '__init__.py'
        spec = importlib.util.spec_from_file_location('viv_ai', init_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'viv-ai.json')
            config_data = {
                'default_provider': 'ollama',
                'default_model': 'test-model',
                'providers': {
                    'ollama': {
                        'provider_type': 'ollama',
                        'endpoint': 'http://127.0.0.1:11434',
                        'model': 'test-model',
                    }
                },
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f)

            os.environ['VIV_AI_CONFIG'] = config_path
            try:
                events = []

                class FakeVW:
                    def vprint(self, message):
                        events.append(message)

                result = module.vivExtension(FakeVW(), None)
                self.assertEqual(result['config_path'], config_path)
                self.assertTrue(any('using config' in event for event in events))
            finally:
                os.environ.pop('VIV_AI_CONFIG', None)

    def test_plugin_bootstrap_raises_for_missing_env_config_path(self):
        """Verify plugin raises FileNotFoundError when env var points to missing file."""
        init_path = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'viv_ai' / '__init__.py'
        spec = importlib.util.spec_from_file_location('viv_ai', init_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        # Set env to a path that doesn't exist
        os.environ['VIV_AI_CONFIG'] = '/tmp/nonexistent-viv-ai-config.json'
        try:

            class FakeVW:
                def vprint(self, message):
                    pass

            with self.assertRaises(FileNotFoundError):
                module.vivExtension(FakeVW(), None)
        finally:
            os.environ.pop('VIV_AI_CONFIG', None)
