"""
Qt dock widget and GUI integration for Viv-AI analysis.

Phase R: builds out AIHelperDockWidget with proper Qt layout, HTML result viewer,
scope selector, history browser, queue tab, and provenance visualization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..config import AiConfig
from ..service import AnalysisService
from .jobs import BackgroundJobRunner
from .render import render_analysis_result, render_plain_text_fallback
from .review import ReviewApplyPanel
from .settings import SettingsController

try:
    from PyQt6 import QtCore, QtWidgets
except Exception:  # pragma: no cover — optional during headless tests
    try:
        from PyQt5 import QtCore, QtWidgets  # type: ignore
    except Exception:  # pragma: no cover — optional during headless tests
        QtCore = None
        QtWidgets = None


_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<style>
body {{
    font-family: -apple-system, 'Segoe UI', sans-serif;
    font-size: 13px;
    line-height: 1.4;
    padding: 0;
    margin: 0;
    background: #fff;
    color: #212121;
}}
</style>
</head>
<body>
{body}
</body>
</html>"""


class HistoryDiffDialog(QtWidgets.QDialog if QtWidgets else object):
    """Side-by-side diff view for two analysis results."""

    def __init__(self, entry_a: Dict, entry_b: Dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Compare Analysis Results')
        self.resize(800, 500)
        layout = QtWidgets.QHBoxLayout(self)

        left = QtWidgets.QTextEdit()
        left.setReadOnly(True)
        left.setHtml(_HTML_TEMPLATE.format(body=render_analysis_result(entry_a.get('raw_result', {}))))

        right = QtWidgets.QTextEdit()
        right.setReadOnly(True)
        right.setHtml(_HTML_TEMPLATE.format(body=render_analysis_result(entry_b.get('raw_result', {}))))

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        layout.addWidget(splitter)


class AIHelperPanel:
    """Controller for Viv-AI analysis panel. Owns service, history, queue, and job runner."""

    def __init__(
        self,
        vw: Any,
        vwgui: Any,
        service: Optional[Any] = None,
        config: Optional[AiConfig] = None,
        job_runner: Optional[BackgroundJobRunner] = None,
    ):
        self.vw = vw
        self.vwgui = vwgui
        self.config = config or AiConfig()
        self._uses_default_service = service is None
        self.service = service or AnalysisService(self.config)
        self.scope = 'function'
        self.history: List[Dict[str, Any]] = []
        self.job_history: List[Dict[str, Any]] = []
        self.last_result: Optional[Dict[str, Any]] = None
        self.last_rendered_result_html: str = ''
        self.last_rendered_result_plain: str = ''
        self.review_panel = ReviewApplyPanel(vw, mutation_policy=self.config.mutation_policy)
        self.job_runner = job_runner or BackgroundJobRunner()

    def apply_config(self, config: AiConfig) -> None:
        self.config = config
        self.review_panel.mutation_policy = config.mutation_policy
        if self._uses_default_service:
            self.service = AnalysisService(self.config)

    def set_scope(self, scope: str) -> None:
        self.scope = scope

    def _record_history(self, result: Dict[str, Any]) -> None:
        """Store an analysis result in history with metadata for provenance."""
        analysis = result.get('analysis') or {}
        entry = {
            'scope': self.scope,
            'task_type': result.get('task_type'),
            'cache_hit': bool(result.get('cache_hit')),
            'status': 'cache hit' if result.get('cache_hit') else 'fresh',
            'summary': analysis.get('summary', '(no summary)'),
            'confidence': analysis.get('confidence', ''),
            'provider': dict(result.get('provider') or {}),
            'raw_result': dict(result),
            'timestamp': None,  # filled by caller or display layer
        }
        self.history.append(entry)
        self.job_history.append(entry)

    def _handle_success_result(self, result, target_va: Optional[int] = None):
        self.last_result = result
        self.last_rendered_result_html = render_analysis_result(result)
        self.last_rendered_result_plain = render_plain_text_fallback(result)
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
        self.last_rendered_result_html = render_analysis_result(result)
        self.last_rendered_result_plain = render_plain_text_fallback(result)
        return result

    def _handle_error_result(self, task_type: str, error: str, va: Optional[int] = None):
        result = {'error': error, 'task_type': task_type}
        if va is not None:
            result['va'] = f'0x{va:08x}'
        self.last_result = result
        self.last_rendered_result_html = render_analysis_result(result)
        self.last_rendered_result_plain = render_plain_text_fallback(result)
        return result

    def render_last_result(self) -> str:
        return self.last_rendered_result_plain

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
                target_va = (
                    (snapshot.get('metadata') or {}).get('target_va')
                    if snapshot.get('task_type') == 'function_summary'
                    else None
                )
                self._handle_success_result(snapshot['result'], target_va=target_va)
            elif snapshot['status'] == 'failed':
                self._handle_error_result(
                    snapshot.get('task_type', 'unknown'), snapshot.get('error', 'unknown error')
                )
        return snapshots


# ---- Qt dock widget ----

if QtWidgets is not None:

    class AIHelperDockWidget(QtWidgets.QWidget):
        """Viv-AI analysis dock widget with HTML result viewer, history, and queue tabs."""

        def __init__(self, controller: AIHelperPanel, settings_controller: Optional[SettingsController] = None):
            super().__init__()
            self.controller = controller
            self.settings_controller = settings_controller
            self.setWindowTitle('Viv-AI Helper')

            self._build_ui()

            # Connect panel state changes to UI updates
            self._refresh_timer = QtCore.QTimer(self)
            self._refresh_timer.setInterval(500)
            self._refresh_timer.timeout.connect(self._poll_jobs)
            self._refresh_timer.start()

        def _build_ui(self):
            """Construct the full dock widget layout."""
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(4)

            # ---- Toolbar row ----
            toolbar = QtWidgets.QHBoxLayout()
            toolbar.setSpacing(4)

            self.scope_combo = QtWidgets.QComboBox()
            self.scope_combo.addItems(['Function', 'Binary', 'Graph'])
            self.scope_combo.currentTextChanged.connect(self._on_scope_changed)
            toolbar.addWidget(self.scope_combo)

            self.explain_btn = QtWidgets.QPushButton('Explain')
            self.explain_btn.clicked.connect(self._on_explain)
            toolbar.addWidget(self.explain_btn)

            self.queue_btn = QtWidgets.QPushButton('Queue')
            self.queue_btn.clicked.connect(self._on_queue)
            toolbar.addWidget(self.queue_btn)

            self.provider_btn = QtWidgets.QPushButton('Provider')
            self.provider_btn.clicked.connect(self._on_provider_status)
            toolbar.addWidget(self.provider_btn)

            toolbar.addStretch()
            layout.addLayout(toolbar)

            # ---- Tab widget: Result | History | Queue ----
            self.tabs = QtWidgets.QTabWidget()

            # Tab 1: Result viewer
            result_tab = QtWidgets.QWidget()
            result_layout = QtWidgets.QVBoxLayout(result_tab)
            result_layout.setContentsMargins(0, 0, 0, 0)

            self.result_view = QtWidgets.QTextEdit()
            self.result_view.setReadOnly(True)
            self.result_view.setHtml('<p style="color:#9e9e9e;font-style:italic;">Run an analysis to see results here.</p>')
            result_layout.addWidget(self.result_view)

            # Status bar below result
            status_bar = QtWidgets.QHBoxLayout()
            self.provenance_label = QtWidgets.QLabel('')
            self.provenance_label.setStyleSheet('color:#757575;font-size:11px;font-family:monospace;')
            status_bar.addWidget(self.provenance_label)
            status_bar.addStretch()
            self.job_status_label = QtWidgets.QLabel('')
            self.job_status_label.setStyleSheet('color:#1565c0;font-size:11px;font-family:monospace;')
            status_bar.addWidget(self.job_status_label)
            result_layout.addLayout(status_bar)

            self.tabs.addTab(result_tab, 'Result')

            # Tab 2: History
            history_tab = QtWidgets.QWidget()
            history_layout = QtWidgets.QVBoxLayout(history_tab)
            history_layout.setContentsMargins(0, 0, 0, 0)

            history_top = QtWidgets.QHBoxLayout()
            self.history_list = QtWidgets.QListWidget()
            self.history_list.currentRowChanged.connect(self._on_history_selected)
            history_top.addWidget(self.history_list)

            history_actions = QtWidgets.QVBoxLayout()
            self.compare_btn = QtWidgets.QPushButton('Compare')
            self.compare_btn.clicked.connect(self._on_compare)
            self.compare_btn.setEnabled(False)
            history_actions.addWidget(self.compare_btn)

            self.clear_btn = QtWidgets.QPushButton('Clear')
            self.clear_btn.clicked.connect(self._on_clear_history)
            history_actions.addWidget(self.clear_btn)

            history_actions.addStretch()
            history_top.addLayout(history_actions)
            history_layout.addLayout(history_top)

            self.history_detail = QtWidgets.QTextEdit()
            self.history_detail.setReadOnly(True)
            self.history_detail.setMaximumHeight(120)
            self.history_detail.setPlaceholderText('Selected entry detail')
            history_layout.addWidget(self.history_detail)

            self.tabs.addTab(history_tab, 'History')

            # Tab 3: Queue
            queue_tab = QtWidgets.QWidget()
            queue_layout = QtWidgets.QVBoxLayout(queue_tab)
            queue_layout.setContentsMargins(0, 0, 0, 0)

            self.queue_list = QtWidgets.QListWidget()
            queue_layout.addWidget(self.queue_list)

            queue_actions = QtWidgets.QHBoxLayout()
            self.queue_apply_btn = QtWidgets.QPushButton('Apply Selected')
            self.queue_apply_btn.clicked.connect(self._on_queue_apply)
            queue_actions.addWidget(self.queue_apply_btn)

            self.queue_skip_btn = QtWidgets.QPushButton('Skip Selected')
            self.queue_skip_btn.clicked.connect(self._on_queue_skip)
            queue_actions.addWidget(self.queue_skip_btn)

            self.queue_apply_all_btn = QtWidgets.QPushButton('Apply All')
            self.queue_apply_all_btn.clicked.connect(self._on_queue_apply_all)
            queue_actions.addWidget(self.queue_apply_all_btn)
            queue_actions.addStretch()

            queue_layout.addLayout(queue_actions)
            self.tabs.addTab(queue_tab, 'Queue (0)')

            layout.addWidget(self.tabs)

            # ---- Progress bar ----
            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setVisible(False)
            self.progress_bar.setMaximumHeight(12)
            layout.addWidget(self.progress_bar)

            # Connect panel tab changes
            self.tabs.currentChanged.connect(self._on_tab_changed)

        def _on_scope_changed(self, scope_text: str):
            self.controller.set_scope(scope_text.lower())

        def _on_explain(self):
            try:
                result = self.controller.explain_current_function()
                self._display_result(result)
            except ValueError as e:
                self.result_view.setHtml(
                    f'<p style="color:#c62828;">Error: {e}</p>'
                )

        def _on_queue(self):
            try:
                job = self.controller.schedule_current_analysis()
                self._update_queue_tab()
                self.job_status_label.setText(f'Queued: {job.task_type}')
            except ValueError as e:
                self.job_status_label.setText(f'Error: {e}')

        def _on_provider_status(self):
            result = self.controller.show_provider_status()
            self._display_result(result)
            self.tabs.setCurrentIndex(0)

        def _display_result(self, result: Dict):
            """Update the result view and provenance label with a new result."""
            html = render_analysis_result(result)
            self.result_view.setHtml(_HTML_TEMPLATE.format(body=html))

            # Provenance info
            cache_hit = result.get('cache_hit', False)
            provider = result.get('provider') or {}
            ptype = provider.get('type', '?')
            model = provider.get('model', '?')
            tag = 'CACHED' if cache_hit else 'FRESH'
            self.provenance_label.setText(f'{tag} — {ptype}/{model}')

            # Switch to result tab
            self.tabs.setCurrentIndex(0)

            # Update history list
            self._populate_history_list()

        def _populate_history_list(self):
            """Refresh the history list widget from panel history."""
            self.history_list.blockSignals(True)
            self.history_list.clear()
            for i, entry in enumerate(self.controller.history):
                cache_tag = '■' if entry.get('cache_hit') else '○'
                label = f'{cache_tag} {entry.get("task_type", "?")}'
                if entry.get('summary'):
                    # Truncate summary for display
                    s = entry['summary'][:60]
                    label += f': {s}'
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, i)
                self.history_list.addItem(item)
            self.history_list.blockSignals(False)

        def _on_history_selected(self, row: int):
            if row < 0 or row >= len(self.controller.history):
                self.history_detail.clear()
                self.compare_btn.setEnabled(False)
                return
            entry = self.controller.history[row]
            raw = entry.get('raw_result', {})
            html = render_analysis_result(raw)
            self.history_detail.setHtml(_HTML_TEMPLATE.format(body=html))

            # Enable compare if >= 2 items selected
            selected = self.history_list.selectedItems()
            self.compare_btn.setEnabled(len(selected) >= 2)

        def _on_compare(self):
            selected = self.history_list.selectedItems()
            if len(selected) < 2:
                return
            indices = [item.data(QtCore.Qt.UserRole) for item in selected[:2]]
            entries = [self.controller.history[i] for i in indices]
            dialog = HistoryDiffDialog(entries[0], entries[1], parent=self)
            dialog.exec()

        def _on_clear_history(self):
            self.controller.history.clear()
            self._populate_history_list()
            self.history_detail.clear()
            self.compare_btn.setEnabled(False)

        def _update_queue_tab(self):
            """Refresh the queue list widget from ReviewApplyPanel."""
            self.queue_list.clear()
            items = self.controller.review_panel.preview_queue()
            for item in items:
                parts = [f"0x{item['va']}"]
                if item.get('has_name'):
                    parts.append('[rename]')
                if item.get('has_comment'):
                    parts.append('[comment]')
                self.queue_list.addItem(' '.join(parts))

            # Update tab label with count
            count = len(items)
            self.tabs.setTabText(2, f'Queue ({count})')

        def _on_queue_apply(self):
            result = self.controller.review_panel.apply_current(approved=True)
            self._update_queue_tab()

        def _on_queue_skip(self):
            self.controller.review_panel.skip_current()
            self._update_queue_tab()

        def _on_queue_apply_all(self):
            result = self.controller.review_panel.apply_all(approved=True)
            self._update_queue_tab()

        def _on_tab_changed(self, index: int):
            if index == 2:  # Queue tab
                self._update_queue_tab()

        def _poll_jobs(self):
            """Periodic poll for background job progress (R5)."""
            pending = self.controller.job_runner.pending_count()
            running = self.controller.job_runner.running_count()
            if pending > 0 or running > 0:
                # Read actual progress from running jobs
                best_progress = 0
                messages: list[str] = []
                for job in self.controller.job_runner.jobs:
                    if job.status in ('running',):
                        best_progress = max(best_progress, job.progress)
                        messages.append(job.message)
                if messages:
                    self.job_status_label.setText(f'Running: {messages[0]} ({best_progress}%)')
                else:
                    self.job_status_label.setText(f'Pending: {pending} | Running: {running}')
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(max(best_progress, 1))
            else:
                self.job_status_label.setText('')
                self.progress_bar.setVisible(False)

else:
    # Headless fallback (no Qt available)
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


def build_context_menu_entries(vw, vwgui, va=None, service=None, config=None):
    target_va = None
    if va is not None:
        target_va = getattr(vw, 'getFunction', lambda _va: None)(va)
    panel = AIHelperPanel(vw, vwgui, service=service, config=config)
    return _build_context_actions(panel, target_va)


def install_gui(vw: Any, vwgui: Any, service: Optional[Any] = None, config: Optional[AiConfig] = None):
    panel = AIHelperPanel(vw, vwgui, service=service, config=config)
    settings_controller = SettingsController(panel.config)
    settings_controller.bind_panel(panel)
    widget = AIHelperDockWidget(panel, settings_controller=settings_controller)
    dock = vwgui.vqDockWidget(widget, floating=False)
    if hasattr(dock, 'resize'):
        dock.resize(560, 420)
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


__all__ = [
    'AIHelperPanel',
    'AIHelperDockWidget',
    'HistoryDiffDialog',
    'install_gui',
    'build_context_menu_entries',
]
