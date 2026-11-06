"""Tier 1 capital - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.tier1(ctx.run)
    show(ctx, html, data, "t02_tier1")


TAB = {"title": "Tier 1 capital", "section": "Capital", "icon": ":material/account_balance:", "order": 10,
       "subtitle": "Every component, the rule applied and its RBI paragraph", "render": render, "bare": True}
