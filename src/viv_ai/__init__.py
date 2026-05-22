"""Viv-AI standalone plugin package for Vivisect.

This package is designed to live outside the built-in vivisect namespace and be
loaded through VIV_EXT_PATH. The public boundaries are kept narrow so the code
can migrate in-tree later if that becomes desirable.
"""

from .ui.widgets import install_gui


def vivExtension(vw, vwgui):
    result = {'name': 'viv_ai', 'vwgui_present': vwgui is not None}
    if vwgui is None:
        vw.vprint('viv_ai Phase D core loaded without GUI')
        return result

    panel, dock = install_gui(vw, vwgui)
    result['panel'] = panel
    result['dock'] = dock
    vw.vprint('viv_ai Phase D GUI loaded (panel, menu, context hook)')
    return result


__all__ = ['vivExtension']
