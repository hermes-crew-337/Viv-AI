import unittest


class FakeVW:
    def __init__(self):
        self.events = []
        self.ctx_hooks = {}
        self.current_function = 0x401000
        self.names = {0x401000: 'main'}
        self.comments = {}
        self.function_lookup = {0x401000: 0x401000, 0x401004: 0x401000, 0x500000: None}
        self.graph_requests = []
        self.symbolik_requests = []

    def vprint(self, message):
        self.events.append(message)

    def addCtxMenuHook(self, name, hook):
        self.ctx_hooks[name] = hook

    def getFunction(self, va):
        return self.function_lookup.get(va)

    def getFunctionGraph(self, va):
        self.graph_requests.append(va)
        return {'graph_for': va}

    def getSymbolikPaths(self, va):
        self.symbolik_requests.append(va)
        return [{'path_id': 'path-1', 'constraints': ['eax == 0'], 'effects': ['retval = 1']}]

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

    def provider_status(self, provider_name=None):
        self.calls.append(('provider_status', provider_name))
        return {
            'provider_name': provider_name or 'ollama',
            'provider_type': 'ollama',
            'endpoint': 'http://MATRIX:11434',
            'configured_model': 'qwen2.5:72b-instruct',
            'available_models': ['qwen2.5:72b-instruct', 'gemma4:31b'],
            'issues': [],
        }

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
            'provider': {'type': 'ollama', 'model': 'qwen2.5:72b-instruct'},
        }

    def analyze_graph(self, graph, options=None):
        self.calls.append(('graph', graph, dict(options or {})))
        return {
            'task_type': 'graph_summary',
            'cache_hit': False,
            'analysis': {
                'summary': 'dispatcher graph with one loop hub',
                'evidence': ['back edge at 0x401020'],
                'confidence': 'medium',
            },
            'provider': {'type': 'ollama', 'model': 'qwen2.5:72b-instruct'},
        }

    def analyze_symbolik(self, paths, options=None):
        self.calls.append(('symbolik', paths, dict(options or {})))
        return {
            'task_type': 'symbolik_summary',
            'cache_hit': False,
            'analysis': {
                'summary': 'one satisfiable success path',
                'evidence': ['constraint eax == 0'],
                'confidence': 'low',
            },
            'provider': {'type': 'ollama', 'model': 'qwen2.5:72b-instruct'},
        }

    def analyze_binary(self, vw, options=None):
        self.calls.append(('binary', dict(options or {})))
        return {
            'task_type': 'binary_summary',
            'cache_hit': True,
            'analysis': {
                'summary': 'binary overview',
                'evidence': ['entry point 0x401000'],
                'confidence': 'high',
            },
            'provider': {'type': 'ollama', 'model': 'qwen2.5:72b-instruct'},
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
        self.assertTrue(hasattr(vwgui.docks[0].widget, 'settings_controller'))
        menu_paths = {path for path, _, _ in vwgui.menu_fields}
        self.assertIn('&Tools.&AI Helper.&Show Panel', menu_paths)
        self.assertIn('&Tools.&AI Helper.&Explain Current Function', menu_paths)
        self.assertIn('&Tools.&AI Helper.&Analyze Current Function Graph', menu_paths)
        self.assertIn('&Tools.&AI Helper.&Summarize Current Binary', menu_paths)
        self.assertIn('&Tools.&AI Helper.&Summarize Current Function Symboliks', menu_paths)
        self.assertIn('&Tools.&AI Helper.&Queue Current Function Analysis', menu_paths)
        self.assertIn('&Tools.&AI Helper.&Show Provider Status', menu_paths)
        self.assertIn('viv_ai', vw.ctx_hooks)
        self.assertTrue(any('Phase P GUI loaded' in event for event in vw.events))

    def test_context_hook_exposes_function_actions(self):
        from viv_ai.ui import build_context_menu_entries

        entries = build_context_menu_entries(FakeVW(), FakeVWGui(), va=0x401004)

        labels = {entry['label'] for entry in entries}
        self.assertIn('Explain Function with AI', labels)
        self.assertIn('Analyze Function Graph with AI', labels)
        self.assertIn('Summarize Symbolik Paths with AI', labels)
        self.assertIn('Queue Function Analysis', labels)
        self.assertTrue(all(entry['va'] == 0x401000 for entry in entries))

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

    def test_tools_menu_actions_reuse_visible_panel_service(self):
        from viv_ai.ui.widgets import install_gui

        vw = FakeVW()
        vwgui = FakeVWGui()
        service = FakeService()

        panel, _dock = install_gui(vw, vwgui, service=service)
        menu_callbacks = {path: callback for path, callback, _args in vwgui.menu_fields}

        menu_callbacks['&Tools.&AI Helper.&Explain Current Function']()
        menu_callbacks['&Tools.&AI Helper.&Analyze Current Function Graph']()
        menu_callbacks['&Tools.&AI Helper.&Summarize Current Binary']()
        menu_callbacks['&Tools.&AI Helper.&Summarize Current Function Symboliks']()
        menu_callbacks['&Tools.&AI Helper.&Show Provider Status']()

        self.assertEqual(service.calls[0], ('function', 0x401000, {}))
        self.assertEqual(service.calls[1], ('graph', {'graph_for': 0x401000}, {}))
        self.assertEqual(service.calls[2], ('binary', {}))
        self.assertEqual(service.calls[3][0], 'symbolik')
        self.assertEqual(service.calls[4], ('provider_status', None))
        self.assertEqual(panel.last_result['task_type'], 'provider_status')
        self.assertIn('Configured model: qwen2.5:72b-instruct', panel.render_last_result())

    def test_installed_context_hook_reuses_visible_panel_service(self):
        from viv_ai.ui.widgets import install_gui

        vw = FakeVW()
        vwgui = FakeVWGui()
        service = FakeService()

        panel, _dock = install_gui(vw, vwgui, service=service)
        menu = FakeMenu()
        vw.ctx_hooks['viv_ai'](vw, va=0x401004, menu=menu)
        actions = {label: callback for label, callback in menu.actions}
        actions['Explain Function with AI']()
        actions['Analyze Function Graph with AI']()
        actions['Summarize Symbolik Paths with AI']()
        actions['Queue Function Analysis']()

        self.assertEqual(len(menu.actions), 4)
        self.assertIsNotNone(panel.last_result)
        self.assertEqual(service.calls[0], ('function', 0x401000, {}))
        self.assertEqual(service.calls[1], ('graph', {'graph_for': 0x401000}, {}))
        self.assertEqual(service.calls[2][0], 'symbolik')
        self.assertEqual(service.calls[3], ('function', 0x401000, {'background': True}))
        self.assertEqual(panel.review_panel.pending_name, 'parse_input')
        self.assertEqual(vw.graph_requests, [0x401000])
        self.assertEqual(vw.symbolik_requests, [0x401000])

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
