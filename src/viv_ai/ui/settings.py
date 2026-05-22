from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..config import AiConfig


class SettingsController:
    def __init__(self, config: AiConfig):
        self.config = config
        self._bound_panels = []

    def to_dict(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def bind_panel(self, panel) -> None:
        self._bound_panels.append(panel)

    def apply_updates(self, updates: Dict[str, Any]) -> AiConfig:
        merged = self.config.to_dict()
        merged.update(dict(updates or {}))
        self.config = AiConfig.from_dict(merged)
        for panel in self._bound_panels:
            if hasattr(panel, 'apply_config'):
                panel.apply_config(self.config)
        return self.config

    def save(self, path) -> Path:
        outpath = Path(path)
        self.config.save(outpath)
        return outpath
