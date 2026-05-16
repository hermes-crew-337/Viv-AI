import importlib
import importlib.util
import pathlib
import sys
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
        self.assertIn('Phase A loaded', events[-1])

    def test_top_level_runtime_import_and_plugin_wrapper_share_entrypoint(self):
        plugin_root = pathlib.Path(__file__).resolve().parents[1] / 'src'
        sys.path.insert(0, str(plugin_root))
        self.addCleanup(lambda: sys.path.remove(str(plugin_root)))

        package = importlib.import_module('viv_ai')
        plugin = importlib.import_module('viv_ai.plugin')

        self.assertIs(plugin.vivExtension, package.vivExtension)
