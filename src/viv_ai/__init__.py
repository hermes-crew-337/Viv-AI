"""Viv-AI standalone plugin package for Vivisect.

This package is designed to live outside the built-in vivisect namespace and be
loaded through VIV_EXT_PATH. The public boundaries are kept narrow so the code
can migrate in-tree later if that becomes desirable.
"""

from .config import load_runtime_config, resolve_config_path
from .ui.widgets import install_gui


def vivExtension(vw, vwgui):
    config_path = resolve_config_path()
    config = load_runtime_config(config_path)
    result = {'name': 'viv_ai', 'vwgui_present': vwgui is not None, 'config_path': str(config_path) if config_path else None}
    if vwgui is None:
        detail = f' using config {config_path}' if config_path else ' with default in-memory config'
        vw.vprint(f'viv_ai Phase P core loaded without GUI{detail}')
        return result

    panel, dock = install_gui(vw, vwgui, config=config)
    result['panel'] = panel
    result['dock'] = dock
    detail = f' using config {config_path}' if config_path else ' with default in-memory config'
    vw.vprint(f'viv_ai Phase P GUI loaded (panel, menu, context hook){detail}')
    return result


__all__ = ['vivExtension']
