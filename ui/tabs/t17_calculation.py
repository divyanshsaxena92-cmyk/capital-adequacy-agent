"""Calculation (step by step) - the full working from source cell to CRAR, independently re-derived and checked
against the engine, with downloads for validation outside the tool."""
import os
import tempfile

from capital_agent import ledger, memo
from capital_agent.report import build_pack
from ui import pages_cc, theme
from ui.component import show


def render(ctx):
    st, run = ctx.st, ctx.run
    html, data = pages_cc.calculation(run, st.session_state.get("history", []))
    show(ctx, html, data, "t17_calculation")
    theme.section(st, "Download the working")
    a, b, c = st.columns(3, gap="medium")
    with a:
        st.markdown("**Calculation ledger (CSV)**  \nEvery step with inputs, formula, result, rule and RBI paragraph. Opens in Excel.")
        st.download_button("Download CSV ledger", ledger.to_csv(run), file_name=f"Calculation_ledger_{run.ds.reporting_date}.csv",
                           mime="text/csv", type="primary", width="stretch", key="calc-csv")
    with b:
        st.markdown("**Excel pack with live formulas**  \nRecalculates in Excel, so a reviewer can change an input and see the effect.")
        out = os.path.join(tempfile.gettempdir(), f"pack_{run.run_id}.xlsx")
        if not os.path.exists(out):
            build_pack(run, out)
        with open(out, "rb") as f:
            st.download_button("Download Excel pack", f.read(), file_name=f"Capital_Agent_Output_{run.ds.reporting_date}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch", key="calc-xlsx")
    with c:
        st.markdown("**Management memo**  \nOne page: figures, compliance, RBI texts applied (official names), open items, sign-off.")
        who = st.text_input("Prepared by", key="calc-memo-who", placeholder="Your name")
        st.download_button("Download memo (open → Print → PDF)", memo.build(run, ctx.extra["rag"], who),
                           file_name=f"Capital_adequacy_memo_{run.ds.reporting_date}.html", mime="text/html", width="stretch", key="calc-memo")


TAB = {"title": "Calculation (step by step)", "section": "Capital", "icon": ":material/calculate:", "order": 5,
       "subtitle": "The full working, re-derived and checked against the engine", "render": render, "bare": True}
