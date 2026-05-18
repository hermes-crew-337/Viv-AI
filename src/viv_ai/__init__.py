"""Viv-AI standalone plugin package for Vivisect.

This package is designed to live outside the built-in vivisect namespace and be
loaded through VIV_EXT_PATH. The public boundaries are kept narrow so the code
can migrate in-tree later if that becomes desirable.
"""


def vivExtension(vw, vwgui):
    vw.vprint('viv_ai Phase B core loaded (standalone package)')
    return {'name': 'viv_ai', 'vwgui_present': vwgui is not None}


__all__ = ['vivExtension']
