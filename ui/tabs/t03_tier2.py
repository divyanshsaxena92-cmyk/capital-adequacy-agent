"""Tier 2 capital - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.tier2(ctx.run)
    show(ctx, html, data, "t03_tier2")


TAB = {"title": "Tier 2 capital", "section": "Capital", "icon": ":material/layers:", "order": 20,
       "subtitle": "Eligible provisions, the 1.25% of RWA cap and the Tier 1 limit", "render": render, "bare": True}
