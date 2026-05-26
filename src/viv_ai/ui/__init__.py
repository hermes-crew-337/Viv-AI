from .widgets import AIHelperPanel, install_gui, _build_context_actions


def build_context_menu_entries(vw, vwgui, va=None, service=None, config=None):
    target_va = None
    if va is not None:
        target_va = getattr(vw, 'getFunction', lambda _va: None)(va)
    panel = AIHelperPanel(vw, vwgui, service=service, config=config)
    return _build_context_actions(panel, target_va)


__all__ = ['AIHelperPanel', 'install_gui', 'build_context_menu_entries']
