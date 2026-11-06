"""Page plug-in registry.

Every module in ui/pages that defines TAB is picked up automatically and placed in the sidebar
navigation under its section, in `order`. Files starting with "_" are ignored (see _template.py).

    TAB = {"title": "My page", "section": "Review", "icon": ":material/star:", "order": 95,
           "subtitle": "One line shown under the page title", "render": render, "needs_run": True}
"""
from __future__ import annotations

import importlib
import pkgutil

from . import tabs as _tabs_pkg

SECTIONS = ["Dashboard", "Capital", "Review", "Regulation", "Data & evidence"]


def discover() -> list[dict]:
    found = []
    for mod in pkgutil.iter_modules(_tabs_pkg.__path__):
        if mod.name.startswith("_"):
            continue
        m = importlib.import_module(f"{_tabs_pkg.__name__}.{mod.name}")
        tab = getattr(m, "TAB", None)
        if tab and callable(tab.get("render")) and tab.get("enabled", True):
            found.append({"needs_run": True, "section": "Review", "icon": ":material/article:", "subtitle": "",
                          **tab, "module": mod.name})
    sec = {s: i for i, s in enumerate(SECTIONS)}
    return sorted(found, key=lambda t: (sec.get(t["section"], 99), t.get("order", 100), t["title"]))


def grouped(tabs: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for t in tabs:
        out.setdefault(t["section"], []).append(t)
    return out
