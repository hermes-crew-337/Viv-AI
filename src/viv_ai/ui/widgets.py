from __future__ import annotations

from typing import Any, Optional

from ..config import AiConfig
from ..service import AnalysisService
from .review import ReviewApplyPanel
from .settings import SettingsController

try:
    from PyQt6 import QtWidgets
except Exception:  # pragma: no cover - optional during headless tests
    try:
        from PyQt5 import QtWidgets  # type: ignore
    except Exception:  # pragma: no cover - optional during headless tests
        QtWidgets = None


class AIHelperPanel:
    def __init__(self, vw: Any, vwgui: Any, service: Optional[Any] = None, config: Optional[AiConfig] = None):
        self.vw = vw
        self.vwgui = vwgui
        self.config = config or AiConfig()
        self._uses_default_service = service is None
        self.service = service or AnalysisService(self.config)
        self.scope = 'function'
        self.history = []
        self.last_result = None
        self.review_panel = ReviewApplyPanel(vw, mutation_policy=self.config.mutation_policy)

    def apply_config(self, config: AiConfig) -> None:
        self.config = config
        self.review_panel.mutation_policy = config.mutation_policy
        if self._uses_default_service:
            self.service = AnalysisService(self.config)

    def set_scope(self, scope: str) -> None:
        self.scope = scope

    def _record_history(self, result):
        status = 'cache hit' if result.get('cache_hit') else 'fresh'
        entry = {
            'scope': self.scope,
            'task_type': result.get('task_type'),
            'cache_hit': bool(result.get('cache_hit')),
            'status': status,
            'summary': result.get('analysis', {}).get('summary', ''),
            'provider': dict(result.get('provider') or {}),
        }
        self.history.append(entry)

    def explain_current_function(self):
        current = getattr(self.vw, 'current_function', None)
        if current is None:
            raise ValueError('no current function available')
        return self.explain_function(current)

    def explain_function(self, fva: int, options: Optional[dict] = None):
        if self._uses_default_service and self.config.providers.get(self.config.default_provider) is None:
            self.last_result = {'error': f'unknown provider: {self.config.default_provider}', 'task_type': 'function_summary', 'va': f'0x{fva:08x}'}
            return self.last_result
        try:
            result = self.service.analyze_function(self.vw, fva, options=options)
        except Exception as exc:
            self.last_result = {'error': str(exc), 'task_type': 'function_summary', 'va': f'0x{fva:08x}'}
            return self.last_result
        self.last_result = result
        self._record_history(result)
        analysis = result.get('analysis', {})
        self.review_panel.stage_suggestions(
            fva,
            proposed_name=analysis.get('proposed_name'),
            proposed_comment=analysis.get('proposed_comment'),
        )
        return result

    def run_current_analysis(self, options: Optional[dict] = None):
        options = dict(options or {})
        try:
            if self.scope == 'binary':
                result = self.service.analyze_binary(self.vw, options=options)
            elif self.scope == 'graph':
                current = getattr(self.vw, 'current_function', None)
                if current is None:
                    raise ValueError('no current function available')
                graph = self.vw.getFunctionGraph(current)
                result = self.service.analyze_graph(graph, options=options)
            else:
                current = getattr(self.vw, 'current_function', None)
                if current is None:
                    raise ValueError('no current function available')
                return self.explain_function(current, options=options)
        except Exception as exc:
            self.last_result = {'error': str(exc), 'task_type': f'{self.scope}_summary'}
            return self.last_result
        self.last_result = result
        self._record_history(result)
        return result


if QtWidgets is not None:
    class AIHelperDockWidget(QtWidgets.QWidget):
        def __init__(self, controller: AIHelperPanel, settings_controller: Optional[SettingsController] = None):
            super().__init__()
            self.controller = controller
            self.settings_controller = settings_controller
            self.setWindowTitle('Viv-AI Helper')
else:
    class AIHelperDockWidget:  # pragma: no cover - only used in headless tests
        def __init__(self, controller: AIHelperPanel, settings_controller: Optional[SettingsController] = None):
            self.controller = controller
            self.settings_controller = settings_controller
            self._window_title = 'Viv-AI Helper'

        def windowTitle(self):
            return self._window_title


def _build_context_action(panel: AIHelperPanel, target_va: Optional[int]):
    if target_va is None:
        return None
    return {
        'label': 'Explain Function with AI',
        'va': target_va,
        'callback': lambda: panel.explain_function(target_va),
    }


def _ctx_menu_hook(vw, va=None, expr=None, menu=None, parent=None, nav=None, tag=None, panel: Optional[AIHelperPanel] = None):
    if panel is None:
        return menu
    target_va = None
    if va is not None:
        target_va = getattr(vw, 'getFunction', lambda _va: None)(va)
    action = _build_context_action(panel, target_va)
    if menu is None:
        return [] if action is None else [action]
    if action is None:
        return menu
    menu.addAction(action['label'], action['callback'])
    return menu


def install_gui(vw: Any, vwgui: Any, service: Optional[Any] = None, config: Optional[AiConfig] = None):
    panel = AIHelperPanel(vw, vwgui, service=service, config=config)
    settings_controller = SettingsController(panel.config)
    settings_controller.bind_panel(panel)
    widget = AIHelperDockWidget(panel, settings_controller=settings_controller)
    dock = vwgui.vqDockWidget(widget, floating=False)
    if hasattr(dock, 'resize'):
        dock.resize(480, 360)
    if hasattr(vwgui, 'vqAddMenuField'):
        vwgui.vqAddMenuField('&Tools.&AI Helper.&Show Panel', lambda: widget, ())
    if hasattr(vw, 'addCtxMenuHook'):
        vw.addCtxMenuHook('viv_ai', lambda *args, **kwargs: _ctx_menu_hook(*args, **kwargs, panel=panel))
    if hasattr(vwgui, 'addHotKey'):
        vwgui.addHotKey('ctrl+shift+a', 'vivai:explain-current-function')
    if hasattr(vwgui, 'addHotKeyTarget'):
        vwgui.addHotKeyTarget('vivai:explain-current-function', panel.explain_current_function)
    return panel, dock
