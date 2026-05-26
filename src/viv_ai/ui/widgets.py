from __future__ import annotations

from typing import Any, Optional

from ..config import AiConfig
from ..service import AnalysisService
from .jobs import BackgroundJobRunner
from .render import render_analysis_result
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
    def __init__(self, vw: Any, vwgui: Any, service: Optional[Any] = None, config: Optional[AiConfig] = None, job_runner: Optional[BackgroundJobRunner] = None):
        self.vw = vw
        self.vwgui = vwgui
        self.config = config or AiConfig()
        self._uses_default_service = service is None
        self.service = service or AnalysisService(self.config)
        self.scope = 'function'
        self.history = []
        self.job_history = []
        self.last_result = None
        self.last_rendered_result = ''
        self.review_panel = ReviewApplyPanel(vw, mutation_policy=self.config.mutation_policy)
        self.job_runner = job_runner or BackgroundJobRunner()

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
        self.job_history.append(entry)

    def _handle_success_result(self, result, target_va: Optional[int] = None):
        self.last_result = result
        self.last_rendered_result = render_analysis_result(result)
        self._record_history(result)
        analysis = result.get('analysis', {})
        if target_va is not None:
            self.review_panel.stage_suggestions(
                target_va,
                proposed_name=analysis.get('proposed_name'),
                proposed_comment=analysis.get('proposed_comment'),
            )
        return result

    def _handle_status_result(self, task_type: str, status: dict):
        result = {'task_type': task_type, 'status': dict(status or {})}
        self.last_result = result
        self.last_rendered_result = render_analysis_result(result)
        return result

    def _handle_error_result(self, task_type: str, error: str, va: Optional[int] = None):
        result = {'error': error, 'task_type': task_type}
        if va is not None:
            result['va'] = f'0x{va:08x}'
        self.last_result = result
        self.last_rendered_result = render_analysis_result(result)
        return result

    def render_last_result(self) -> str:
        return self.last_rendered_result

    def explain_current_function(self):
        current = getattr(self.vw, 'current_function', None)
        if current is None:
            raise ValueError('no current function available')
        return self.explain_function(current)

    def explain_function(self, fva: int, options: Optional[dict] = None):
        if self._uses_default_service and self.config.providers.get(self.config.default_provider) is None:
            return self._handle_error_result('function_summary', f'unknown provider: {self.config.default_provider}', va=fva)
        try:
            result = self.service.analyze_function(self.vw, fva, options=options)
        except Exception as exc:
            return self._handle_error_result('function_summary', str(exc), va=fva)
        return self._handle_success_result(result, target_va=fva)

    def summarize_current_binary(self, options: Optional[dict] = None):
        self.set_scope('binary')
        return self.run_current_analysis(options=options)

    def analyze_current_graph(self, options: Optional[dict] = None):
        self.set_scope('graph')
        return self.run_current_analysis(options=options)

    def analyze_graph_for_function(self, fva: int, options: Optional[dict] = None):
        try:
            graph = self.vw.getFunctionGraph(fva)
            result = self.service.analyze_graph(graph, options=options)
        except Exception as exc:
            return self._handle_error_result('graph_summary', str(exc), va=fva)
        return self._handle_success_result(result, target_va=fva)

    def summarize_current_symboliks(self, options: Optional[dict] = None):
        current = getattr(self.vw, 'current_function', None)
        if current is None:
            return self._handle_error_result('symbolik_summary', 'no current function available')
        return self.summarize_symboliks_for_function(current, options=options)

    def summarize_symboliks_for_function(self, fva: int, options: Optional[dict] = None):
        getter = getattr(self.vw, 'getSymbolikPaths', None)
        if getter is None:
            return self._handle_error_result('symbolik_summary', 'symbolik path provider is unavailable', va=fva)
        try:
            paths = getter(fva)
            result = self.service.analyze_symbolik(paths, options=options)
        except Exception as exc:
            return self._handle_error_result('symbolik_summary', str(exc), va=fva)
        return self._handle_success_result(result, target_va=fva)

    def queue_function_analysis(self, fva: int, options: Optional[dict] = None):
        queued_options = dict(options or {})
        queued_options.setdefault('background', True)
        return self.explain_function(fva, options=queued_options)

    def show_provider_status(self, provider_name: Optional[str] = None):
        try:
            status = self.service.provider_status(provider_name=provider_name)
        except Exception as exc:
            return self._handle_error_result('provider_status', str(exc))
        return self._handle_status_result('provider_status', status)

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
            return self._handle_error_result(f'{self.scope}_summary', str(exc))
        return self._handle_success_result(result)

    def schedule_current_analysis(self, options: Optional[dict] = None):
        options = dict(options or {})
        current = getattr(self.vw, 'current_function', None)
        scope = self.scope

        def job_fn(update):
            update(10, 'extracting context')
            if scope == 'binary':
                update(70, 'waiting on provider')
                return self.service.analyze_binary(self.vw, options=options)
            if scope == 'graph':
                if current is None:
                    raise ValueError('no current function available')
                graph = self.vw.getFunctionGraph(current)
                update(70, 'waiting on provider')
                return self.service.analyze_graph(graph, options=options)
            if current is None:
                raise ValueError('no current function available')
            update(70, 'waiting on provider')
            return self.service.analyze_function(self.vw, current, options=options)

        task_type = f'{scope}_summary'
        metadata = {'target_va': current} if scope == 'function' else {}
        return self.job_runner.submit(task_type, job_fn, metadata=metadata)

    def run_pending_jobs(self):
        snapshots = self.job_runner.run_pending()
        for snapshot in snapshots:
            if snapshot['status'] == 'completed':
                target_va = (snapshot.get('metadata') or {}).get('target_va') if snapshot.get('task_type') == 'function_summary' else None
                self._handle_success_result(snapshot['result'], target_va=target_va)
            elif snapshot['status'] == 'failed':
                self._handle_error_result(snapshot.get('task_type', 'unknown'), snapshot.get('error', 'unknown error'))
        return snapshots


if QtWidgets is not None:
    class AIHelperDockWidget(QtWidgets.QWidget):
        def __init__(self, controller: AIHelperPanel, settings_controller: Optional[SettingsController] = None):
            super().__init__()
            self.controller = controller
            self.settings_controller = settings_controller
            self.setWindowTitle('Viv-AI Helper')
else:
    class AIHelperDockWidget:
        def __init__(self, controller: AIHelperPanel, settings_controller: Optional[SettingsController] = None):
            self.controller = controller
            self.settings_controller = settings_controller
            self._window_title = 'Viv-AI Helper'

        def windowTitle(self):
            return self._window_title


def _build_context_actions(panel: AIHelperPanel, target_va: Optional[int]):
    if target_va is None:
        return []
    actions = [
        {
            'label': 'Explain Function with AI',
            'va': target_va,
            'callback': lambda: panel.explain_function(target_va),
        },
        {
            'label': 'Analyze Function Graph with AI',
            'va': target_va,
            'callback': lambda: panel.analyze_graph_for_function(target_va),
        },
        {
            'label': 'Queue Function Analysis',
            'va': target_va,
            'callback': lambda: panel.queue_function_analysis(target_va),
        },
    ]
    if getattr(panel.vw, 'getSymbolikPaths', None) is not None:
        actions.append({
            'label': 'Summarize Symbolik Paths with AI',
            'va': target_va,
            'callback': lambda: panel.summarize_symboliks_for_function(target_va),
        })
    return actions


def _ctx_menu_hook(vw, va=None, expr=None, menu=None, parent=None, nav=None, tag=None, panel: Optional[AIHelperPanel] = None):
    if panel is None:
        return menu
    target_va = None
    if va is not None:
        target_va = getattr(vw, 'getFunction', lambda _va: None)(va)
    actions = _build_context_actions(panel, target_va)
    if menu is None:
        return actions
    for action in actions:
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
        vwgui.vqAddMenuField('&Tools.&AI Helper.&Explain Current Function', panel.explain_current_function, ())
        vwgui.vqAddMenuField('&Tools.&AI Helper.&Analyze Current Function Graph', panel.analyze_current_graph, ())
        vwgui.vqAddMenuField('&Tools.&AI Helper.&Summarize Current Binary', panel.summarize_current_binary, ())
        vwgui.vqAddMenuField('&Tools.&AI Helper.&Summarize Current Function Symboliks', panel.summarize_current_symboliks, ())
        vwgui.vqAddMenuField('&Tools.&AI Helper.&Queue Current Function Analysis', lambda: panel.queue_function_analysis(getattr(vw, 'current_function', None)), ())
        vwgui.vqAddMenuField('&Tools.&AI Helper.&Show Provider Status', panel.show_provider_status, ())
    if hasattr(vw, 'addCtxMenuHook'):
        vw.addCtxMenuHook('viv_ai', lambda *args, **kwargs: _ctx_menu_hook(*args, **kwargs, panel=panel))
    if hasattr(vwgui, 'addHotKey'):
        vwgui.addHotKey('ctrl+shift+a', 'vivai:explain-current-function')
    if hasattr(vwgui, 'addHotKeyTarget'):
        vwgui.addHotKeyTarget('vivai:explain-current-function', panel.explain_current_function)
    return panel, dock
