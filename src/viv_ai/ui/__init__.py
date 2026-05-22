from .widgets import AIHelperPanel, install_gui, _build_context_action


def build_context_menu_entries(vw, vwgui, va=None, service=None, config=None):
    target_va = None
    if va is not None:
        target_va = getattr(vw, 'getFunction', lambda _va: None)(va)
    panel = AIHelperPanel(vw, vwgui, service=service, config=config)
    action = _build_context_action(panel, target_va)
    return [] if action is None else [action]


__all__ = ['AIHelperPanel', 'install_gui', 'build_context_menu_entries']
