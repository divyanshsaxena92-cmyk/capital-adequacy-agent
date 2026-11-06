"""Sensitivity - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.sensitivity(ctx.run)
    show(ctx, html, data, "t07_sensitivity")


TAB = {"title": "Sensitivity", "section": "Review", "icon": ":material/insights:", "order": 70,
       "subtitle": "CRAR impact of each open judgement call", "render": render, "bare": True}
