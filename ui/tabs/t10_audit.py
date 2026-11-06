"""Audit trail - Command-Centre page (local component)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.audit(ctx.run)
    show(ctx, html, data, "t10_audit")


TAB = {"title": "Audit trail", "section": "Data & evidence", "icon": ":material/receipt_long:", "order": 30,
       "subtitle": "Source cell to output, for every number", "render": render, "bare": True}
