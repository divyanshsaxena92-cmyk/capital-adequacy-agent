"""Risk-weighted assets - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.rwa(ctx.run)
    show(ctx, html, data, "t04_rwa")


TAB = {"title": "Risk-weighted assets", "section": "Capital", "icon": ":material/scale:", "order": 30,
       "subtitle": "Each exposure, its risk weight and the resulting RWA", "render": render, "bare": True}
