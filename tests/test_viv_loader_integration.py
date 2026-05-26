import os
import pathlib
import unittest


class VivisectLoaderIntegrationTests(unittest.TestCase):
    def test_vivisect_extension_loader_discovers_package_from_viv_ext_path(self):
        import vivisect.extensions as vext

        plugin_parent = pathlib.Path(__file__).resolve().parents[1] / 'src'
        old = os.environ.get('VIV_EXT_PATH')
        os.environ['VIV_EXT_PATH'] = str(plugin_parent)
        self.addCleanup(lambda: os.environ.__setitem__('VIV_EXT_PATH', old) if old is not None else os.environ.pop('VIV_EXT_PATH', None))

        events = []
        exts = {}

        class FakeVW:
            vivhome = '/tmp/does-not-matter'

            def vprint(self, msg):
                events.append(msg)

            def addExtension(self, name, module):
                exts[name] = module

        vext.loadExtensions(FakeVW(), None)

        self.assertIn('viv_ai', exts)
        self.assertTrue(any('viv_ai Phase P core loaded without GUI' in e for e in events))
