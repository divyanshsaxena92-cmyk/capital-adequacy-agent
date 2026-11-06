"""Rules in force - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.rules(ctx.run)
    show(ctx, html, data, "t11_regulatory")


TAB = {"title": "Rules in force", "section": "Regulation", "icon": ":material/gavel:", "order": 20,
       "subtitle": "The controlled rule library at the reporting date", "render": render, "bare": True}
