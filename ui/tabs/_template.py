"""TEMPLATE for a new tab - copy to ui/tabs/t13_my_tab.py (no leading underscore) and edit.

The registry picks up any module that defines TAB. You get:
  ctx.st          the streamlit module
  ctx.run         the agent Run (results, exceptions, audit, cem, kb, rules, ds = parsed workbook)
  ctx.input_path  path of the uploaded workbook (e.g. to read an extra sheet with pandas)
  ctx.rerun(rows) re-run the agent with SME decisions
Table builders in ui/frames.py are reusable; add new ones there.
"""
from ui import frames
from ui.widgets import table


def render(ctx):
    st, run = ctx.st, ctx.run
    st.subheader("My new tab")
    # Example: read an extra sheet the agent doesn't use yet
    # import pandas as pd; df = pd.read_excel(ctx.input_path, sheet_name="Leverage_Input")
    table(st, frames.metrics(run))


TAB = {"title": "My page", "section": "Review", "icon": ":material/star:", "order": 130,
       "subtitle": "One line under the title", "render": render, "needs_run": True, "enabled": True}
