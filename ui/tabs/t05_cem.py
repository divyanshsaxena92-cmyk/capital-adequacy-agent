"""Derivatives (CEM) - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.derivatives(ctx.run)
    show(ctx, html, data, "t05_cem")


TAB = {"title": "Derivatives (CEM)", "section": "Capital", "icon": ":material/swap_horiz:", "order": 40,
       "subtitle": "Counterparty credit risk on derivatives", "render": render, "bare": True}
