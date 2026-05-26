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

    def getFunctions(self):
        return [0x401000, 0x402000, 0x403000]


class FakeVWGui:
    def __init__(self):
        self.menu_fields = []
        self.hotkeys = []
        self.hotkey_targets = []

    def vqDockWidget(self, widget, floating=False):
        return FakeDock(widget, floating=floating)

    def vqAddMenuField(self, path, callback, args):
        self.menu_fields.append((path, callback, args))

    def addHotKey(self, key, target):
        self.hotkeys.append((key, target))

    def addHotKeyTarget(self, name, callback):
        self.hotkey_targets.append((name, callback))


class FakeDock:
    def __init__(self, widget, floating=False):
        self.widget = widget
        self.floating = floating


class VulnerabilityTriageTests(unittest.TestCase):
    def test_vulntriage_installation_registers_menu_and_context_hook(self):
        from viv_ai.vulntriage import install_vuln_gui, VulnerabilityTriageWidget

        vw = FakeVW()
        vwgui = FakeVWGui()
        panel, dock = install_vuln_gui(vw, vwgui)

        self.assertIsInstance(panel, VulnerabilityTriageWidget)
        # In headless tests, dock will be None as we don't have Qt
        # self.assertIsNotNone(dock)
        self.assertIn('viv_ai_vuln', vw.ctx_hooks)
        self.assertTrue(any('Tools' in field[0] and 'Vulnerability Analysis' in field[0] for field in vwgui.menu_fields))

    def test_vulntriage_context_menu_hook_adds_actions(self):
        from viv_ai.vulntriage import _ctx_menu_hook, VulnerabilityTriageWidget

        vw = FakeVW()
        panel = VulnerabilityTriageWidget(vw, None)

        # Test with no panel
        result = _ctx_menu_hook(vw, va=0x401000, menu=None, panel=None)
        self.assertEqual(result, None)

        # Test with panel but no menu
        result = _ctx_menu_hook(vw, va=0x401000, menu=None, panel=panel)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['label'], 'Analyze Function for Vulnerabilities')

        # Test with panel and menu
        class FakeMenu:
            def __init__(self):
                self.actions = []

            def addAction(self, label, callback):
                self.actions.append((label, callback))

        menu = FakeMenu()
        result = _ctx_menu_hook(vw, va=0x401000, menu=menu, panel=panel)
        self.assertEqual(result, menu)
        self.assertEqual(len(menu.actions), 1)
        self.assertEqual(menu.actions[0][0], 'Analyze Function for Vulnerabilities')

    def test_vulntriage_vulnerability_dataclass(self):
        from viv_ai.vulntriage import Vulnerability

        vuln = Vulnerability(
            va=0x401010,
            fva=0x401000,
            description="Buffer overflow",
            severity="High",
            confidence=0.95,
            details={"pattern": "strcpy"},
            status="pending",
            review_notes="Needs review"
        )

        self.assertEqual(vuln.va, 0x401010)
        self.assertEqual(vuln.fva, 0x401000)
        self.assertEqual(vuln.description, "Buffer overflow")
        self.assertEqual(vuln.severity, "High")
        self.assertEqual(vuln.confidence, 0.95)
        self.assertEqual(vuln.details, {"pattern": "strcpy"})
        self.assertEqual(vuln.status, "pending")
        self.assertEqual(vuln.review_notes, "Needs review")

    def test_vulntriage_vulnerability_defaults(self):
        from viv_ai.vulntriage import Vulnerability

        vuln = Vulnerability(
            va=0x401010,
            fva=0x401000,
            description="Buffer overflow",
            severity="High",
            confidence=0.95,
            details=None,
            status=None,
            review_notes=None
        )

        self.assertEqual(vuln.details, {})
        self.assertEqual(vuln.status, "pending")
        self.assertEqual(vuln.review_notes, "")