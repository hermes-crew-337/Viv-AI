"""Comprehensive tests for viv_ai/vulntriage.py — >95% coverage target."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import unittest


class TestVulnerabilityDataclass(unittest.TestCase):
    def test_defaults_applied(self):
        from viv_ai.vulntriage import Vulnerability
        v = Vulnerability(va=0x401000, fva=0x401000, description="test", severity="High", confidence=0.9, details=None, status=None, review_notes=None)
        self.assertEqual(v.details, {})
        self.assertEqual(v.status, "pending")
        self.assertEqual(v.review_notes, "")

    def test_custom_values(self):
        from viv_ai.vulntriage import Vulnerability
        v = Vulnerability(va=0x401000, fva=0x401000, description="test", severity="High", confidence=0.9, details={"key": "val"}, status="confirmed", review_notes="analyzed")
        self.assertEqual(v.details, {"key": "val"})
        self.assertEqual(v.status, "confirmed")


class TestBaseWidgetFallback(unittest.TestCase):
    def test_base_widget_set_window_title(self):
        from viv_ai.vulntriage import BaseWidget
        w = BaseWidget()
        w.setWindowTitle("test")
        self.assertEqual(w._window_title, "test")

    def test_base_widget_set_object_name(self):
        from viv_ai.vulntriage import BaseWidget
        w = BaseWidget()
        w.setObjectName("test_obj")
        self.assertEqual(w._object_name, "test_obj")

    def test_base_dock_widget_set_window_title(self):
        from viv_ai.vulntriage import BaseDockWidget
        w = BaseDockWidget()
        w.setWindowTitle("dock test")
        self.assertEqual(w._window_title, "dock test")


class TestVulnerabilityTriageWidget(unittest.TestCase):
    def test_init_without_qt(self):
        """When Qt is None, widget skips setupUI and setupSignals."""
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        vw = MagicMock()
        vwgui = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui)
        self.assertIs(widget.vw, vw)
        self.assertEqual(widget.vulns, [])
        self.assertEqual(widget.current_vuln_idx, -1)

    def test_init_with_service(self):
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        from viv_ai.config import AiConfig
        vw = MagicMock()
        vwgui = MagicMock()
        service = MagicMock()
        config = AiConfig()
        widget = VulnerabilityTriageWidget(vw, vwgui, service=service, config=config)
        self.assertIs(widget.service, service)
        self.assertFalse(widget._uses_default_service)

    def test_init_with_default_service(self):
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        vw = MagicMock()
        vwgui = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui)
        self.assertTrue(widget._uses_default_service)

    def test_apply_config_updates_config(self):
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        from viv_ai.config import AiConfig
        vw = MagicMock()
        vwgui = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui)
        new_config = AiConfig()
        widget.apply_config(new_config)
        self.assertIs(widget.config, new_config)

    def test_apply_config_replaces_service_when_default(self):
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        from viv_ai.config import AiConfig
        vw = MagicMock()
        vwgui = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui)
        original = widget.service
        widget.apply_config(AiConfig())
        self.assertIsNot(widget.service, original)

    def test_apply_config_preserves_own_service(self):
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        from viv_ai.config import AiConfig
        vw = MagicMock()
        vwgui = MagicMock()
        service = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui, service=service)
        original = widget.service
        widget.apply_config(AiConfig())
        self.assertIs(widget.service, original)

    def test_setupUI_does_not_raise(self):
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        vw = MagicMock()
        vwgui = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui)
        # setupUI is a pass
        self.assertIsNone(widget.setupUI())

    def test_setupSignals_does_not_raise(self):
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        vw = MagicMock()
        vwgui = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui)
        self.assertIsNone(widget.setupSignals())


class TestBuildVulnContextActions(unittest.TestCase):
    def test_returns_empty_when_no_target(self):
        from viv_ai.vulntriage import _build_vuln_context_actions
        result = _build_vuln_context_actions(None, None)
        self.assertEqual(result, [])

    def test_returns_action_when_target(self):
        from viv_ai.vulntriage import _build_vuln_context_actions
        panel = MagicMock()
        result = _build_vuln_context_actions(panel, 0x401000)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "Analyze Function for Vulnerabilities")


class TestCtxMenuHook(unittest.TestCase):
    def test_returns_menu_when_no_panel(self):
        from viv_ai.vulntriage import _ctx_menu_hook
        vw = MagicMock()
        menu = MagicMock()
        result = _ctx_menu_hook(vw, menu=menu, panel=None)
        self.assertIs(result, menu)

    def test_builds_actions_when_panel(self):
        from viv_ai.vulntriage import _ctx_menu_hook
        vw = MagicMock()
        vw.getFunction.return_value = 0x401000
        panel = MagicMock()
        result = _ctx_menu_hook(vw, va=0x401000, panel=panel)
        # No menu passed, returns actions list
        self.assertGreater(len(result), 0)

    def test_adds_to_menu_when_menu_provided(self):
        from viv_ai.vulntriage import _ctx_menu_hook
        vw = MagicMock()
        vw.getFunction.return_value = 0x401000
        panel = MagicMock()
        menu = MagicMock()
        result = _ctx_menu_hook(vw, va=0x401000, menu=menu, panel=panel)
        self.assertIs(result, menu)


class TestInstallVulnGUI(unittest.TestCase):
    def test_install_basic(self):
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock()
        panel, dock = install_vuln_gui(vw, vwgui)
        self.assertIsNotNone(panel)
        self.assertIsNone(dock)

    def test_install_with_config(self):
        from viv_ai.vulntriage import install_vuln_gui
        from viv_ai.config import AiConfig
        vw = MagicMock()
        vwgui = MagicMock()
        config = AiConfig()
        service = MagicMock()
        panel, dock = install_vuln_gui(vw, vwgui, service=service, config=config)
        self.assertIs(panel.service, service)
        self.assertIs(panel.config, config)

    @patch('viv_ai.vulntriage.QtWidgets', MagicMock())
    def test_init_with_qt_enabled(self):
        """When QtWidgets is available, setupUI and setupSignals are called."""
        from viv_ai.vulntriage import VulnerabilityTriageWidget
        vw = MagicMock()
        vwgui = MagicMock()
        widget = VulnerabilityTriageWidget(vw, vwgui)
        # setupUI/setupSignals are no-ops, but they should be called
        self.assertIsNotNone(widget)

    @patch('viv_ai.vulntriage.QtWidgets', MagicMock())
    def test_install_with_dock_support(self):
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock()
        mock_dock = MagicMock()
        vwgui.vqDockWidget.return_value = mock_dock
        panel, dock = install_vuln_gui(vw, vwgui)
        self.assertIs(dock, mock_dock)
        mock_dock.setWindowTitle.assert_called_once_with("Vulnerability Triage")

    @patch('viv_ai.vulntriage.QtWidgets', MagicMock())
    def test_install_without_setWindowTitle(self):
        """When dock has no setWindowTitle, it's skipped."""
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock()
        dock = MagicMock(spec=[])  # no setWindowTitle
        vwgui.vqDockWidget.return_value = dock
        install_vuln_gui(vw, vwgui)
        # No exception

    @patch('viv_ai.vulntriage.QtWidgets', MagicMock())
    def test_install_when_vwgui_lacks_vqDockWidget(self):
        """When vwgui lacks vqDockWidget, dock creation is skipped."""
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock(spec=['addHotKey', 'addHotKeyTarget'])
        # will get panel, no dock
        panel, dock = install_vuln_gui(vw, vwgui)
        self.assertIsNone(dock)

    def test_install_adds_menu_fields(self):
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock()
        install_vuln_gui(vw, vwgui)
        self.assertEqual(vwgui.vqAddMenuField.call_count, 2)

    def test_install_adds_ctx_hook(self):
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock()
        install_vuln_gui(vw, vwgui)
        vw.addCtxMenuHook.assert_called_once()

    def test_install_adds_hotkeys(self):
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock()
        vwgui.addHotKey.return_value = True
        vwgui.addHotKeyTarget.return_value = True
        install_vuln_gui(vw, vwgui)
        vwgui.addHotKey.assert_called_once_with("ctrl+shift+v", "vuln:analyze")
        vwgui.addHotKeyTarget.assert_called_once()

    def test_install_handles_hotkey_exception(self):
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock()
        vwgui = MagicMock()
        vwgui.addHotKey.side_effect = Exception("hotkey not supported")
        # Should not raise
        install_vuln_gui(vw, vwgui)

    @patch('viv_ai.vulntriage.QtWidgets', None)
    def test_install_no_addCtxMenuHook(self):
        """When vw lacks addCtxMenuHook, context hook is skipped."""
        from viv_ai.vulntriage import install_vuln_gui
        vw = MagicMock(spec=[])  # no addCtxMenuHook
        vwgui = MagicMock()
        install_vuln_gui(vw, vwgui)
        # No exception should be raised

if __name__ == "__main__":
    unittest.main()
