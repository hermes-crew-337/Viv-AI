import unittest


class FakeVW:
    def __init__(self):
        self.events = []
        self.ctx_hooks = {}
        self.current_function = 0x401000
        self.names = {0x401000: 'main'}
        self.comments = {}
        self.function_lookup = {0x401000: 0x401000, 0x401004: 0x401000, 0x500000: None}

    def vprint(self, message):
        self.events.append(message)

    def addCtxMenuHook(self, name, hook):
        self.ctx_hooks[name] = hook

    def getFunction(self, va):
        return self.function_lookup.get(va)

    def getName(self, va):
        return self.names.get(va)

    def makeName(self, va, name):
        self.names[va] = name
        return name

    def setComment(self, va, comment):
        self.comments[va] = comment


class FakeDock:
    def __init__(self, widget, floating=False):
        self.widget = widget
        self.floating = floating
        self.sizes = []

    def resize(self, width, height):
        self.sizes.append((width, height))


class FakeMenu:
    def __init__(self):
        self.actions = []

    def addAction(self, label, callback):
        self.actions.append((label, callback))
        return callback


class FakeVWGui:
    def __init__(self):
        self.menu_fields = []
        self.docks = []
        self.hotkeys = []
        self.hotkey_targets = []

    def vqDockWidget(self, widget, floating=False):
        dock = FakeDock(widget, floating=floating)
        self.docks.append(dock)
        return dock

    def vqAddMenuField(self, path, callback, args):
        self.menu_fields.append((path, callback, args))

    def addHotKey(self, key, target):
        self.hotkeys.append((key, target))

    def addHotKeyTarget(self, target, callback):
        self.hotkey_targets.append((target, callback))


class FakeService:
    def __init__(self):
        self.calls = []

    def analyze_function(self, vw, fva, options=None):
        self.calls.append(('function', fva, dict(options or {})))
        return {
            'task_type': 'function_summary',
            'cache_hit': False,
            'analysis': {
                'summary': 'main parses an input buffer',
                'evidence': ['calls CreateFileA'],
                'confidence': 'medium',
                'proposed_name': 'parse_input',
                'proposed_comment': 'possible parser entrypoint',
            },
        }


class GuiPluginTests(unittest.TestCase):
    def test_viv_extension_registers_dock_menu_and_context_hook(self):
        from viv_ai import vivExtension

        vw = FakeVW()
        vwgui = FakeVWGui()
        result = vivExtension(vw, vwgui)

        self.assertEqual(result['name'], 'viv_ai')
        self.assertTrue(result['vwgui_present'])
        self.assertEqual(len(vwgui.docks), 1)
        self.assertTrue(hasattr(vwgui.docks[0].widget, 'controller'))
        self.assertTrue(any(path == '&Tools.&AI Helper.&Show Panel' for path, _, _ in vwgui.menu_fields))
        self.assertIn('viv_ai', vw.ctx_hooks)
        self.assertTrue(any('Phase D GUI loaded' in event for event in vw.events))

    def test_context_hook_exposes_function_action(self):
        from viv_ai.ui import build_context_menu_entries

        entries = build_context_menu_entries(FakeVW(), FakeVWGui(), va=0x401004)

        self.assertTrue(any(entry['label'] == 'Explain Function with AI' for entry in entries))
        self.assertEqual(entries[0]['va'], 0x401000)

    def test_context_hook_skips_non_function_targets(self):
        from viv_ai.ui import build_context_menu_entries

        entries = build_context_menu_entries(FakeVW(), FakeVWGui(), va=0x500000)

        self.assertEqual(entries, [])

    def test_panel_runs_analysis_and_stages_reviewable_suggestions(self):
        from viv_ai.ui.widgets import AIHelperPanel

        vw = FakeVW()
        service = FakeService()
        panel = AIHelperPanel(vw, FakeVWGui(), service=service)

        result = panel.explain_current_function()

        self.assertEqual(service.calls, [('function', 0x401000, {})])
        self.assertEqual(result['analysis']['summary'], 'main parses an input buffer')
        self.assertEqual(panel.review_panel.pending_name, 'parse_input')
        self.assertEqual(panel.review_panel.pending_comment, 'possible parser entrypoint')

    def test_panel_returns_structured_error_when_no_provider_is_configured(self):
        from viv_ai.ui.widgets import AIHelperPanel

        vw = FakeVW()
        panel = AIHelperPanel(vw, FakeVWGui())

        result = panel.explain_current_function()

        self.assertIn('error', result)
        self.assertIn('unknown provider', result['error'])

    def test_installed_context_hook_reuses_visible_panel_service(self):
        from viv_ai.ui.widgets import install_gui

        vw = FakeVW()
        vwgui = FakeVWGui()
        service = FakeService()

        panel, _dock = install_gui(vw, vwgui, service=service)
        menu = FakeMenu()
        vw.ctx_hooks['viv_ai'](vw, va=0x401004, menu=menu)
        menu.actions[0][1]()

        self.assertEqual(len(menu.actions), 1)
        self.assertIsNotNone(panel.last_result)
        self.assertEqual(service.calls, [('function', 0x401000, {})])
        self.assertEqual(panel.review_panel.pending_name, 'parse_input')

    def test_installed_context_hook_skips_non_function_targets(self):
        from viv_ai.ui.widgets import install_gui

        vw = FakeVW()
        vwgui = FakeVWGui()
        service = FakeService()

        install_gui(vw, vwgui, service=service)
        menu = FakeMenu()
        vw.ctx_hooks['viv_ai'](vw, va=0x500000, menu=menu)

        self.assertEqual(menu.actions, [])
        self.assertEqual(service.calls, [])


if __name__ == '__main__':
    unittest.main()
