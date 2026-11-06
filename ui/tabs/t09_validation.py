"""Validation - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.validation(ctx.run)
    show(ctx, html, data, "t09_validation")


TAB = {"title": "Validation", "section": "Data & evidence", "icon": ":material/fact_check:", "order": 20,
       "subtitle": "Source tie-outs, controls and benchmark", "render": render, "bare": True}
