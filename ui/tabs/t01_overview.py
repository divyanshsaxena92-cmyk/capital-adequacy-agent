"""Overview: the Capital Command Centre (local custom component) - search, alerts, day/night, live what-if."""
from ui import command_center
from ui.command_center import kb_hits
from ui.component import show


def render(ctx):
    run, rag = ctx.run, ctx.extra["rag"]
    open_ex = [e for e in run.exceptions if e.status == "OPEN"]
    html, data = command_center.build(run, rag.stats(), kb_hits(rag, run, open_ex))
    show(ctx, html, data, "cc")


TAB = {"title": "Overview", "section": "Dashboard", "icon": ":material/dashboard:", "order": 10,
       "subtitle": "Capital Command Centre", "render": render, "bare": True}
