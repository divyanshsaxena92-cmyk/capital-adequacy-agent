"""Basel III lens - RBI's Basel III bank framework applied to this run (binding for banks, benchmark for NBFCs)."""
from ui import pages_cc
from ui.component import show


def render(ctx):
    html, data = pages_cc.basel3(ctx.run)
    show(ctx, html, data, "t16_basel3")


TAB = {"title": "Basel III lens", "section": "Capital", "icon": ":material/account_tree:", "order": 45,
       "subtitle": "CET1, buffers, leverage and distribution limits under RBI Basel III", "render": render, "bare": True}
