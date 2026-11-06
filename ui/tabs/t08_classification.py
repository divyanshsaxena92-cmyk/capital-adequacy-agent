"""Agent reasoning - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.reasoning(ctx.run)
    show(ctx, html, data, "t08_classification")


TAB = {"title": "Agent reasoning", "section": "Regulation", "icon": ":material/psychology:", "order": 30,
       "subtitle": "Every classification with its rule and route", "render": render, "bare": True}
