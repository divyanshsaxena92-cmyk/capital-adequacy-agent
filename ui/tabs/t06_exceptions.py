"""Exception queue: Command-Centre summary (priorities, CRAR at stake, full reasoning per item) above the native
signed-decision table. Decisions re-run the agent and are written to the audit trail."""
from ui import frames, pages_cc, theme
from ui.component import show
from ui.widgets import SEV_ICON, csv_button

DECISIONS = ["ACCEPT_ALTERNATIVE", "RETAIN_BASELINE", "NOTED"]


def render(ctx):
    st, run = ctx.st, ctx.run
    html, data = pages_cc.exceptions(run)
    show(ctx, html, data, "t06_exceptions")
    theme.section(st, "Record SME decisions")
    theme.note(st, "Choose a decision and enter your name, then apply - the agent re-runs and every decision goes to the "
                   "audit trail. Decisions without a reviewer are ignored.")
    ex = frames.exceptions(run)
    if not len(ex):
        st.success("No exceptions.")
        return
    f1, f2 = st.columns(2)
    sev = f1.multiselect("Priority", ["Critical", "High", "Medium", "Low"], default=["Critical", "High", "Medium", "Low"], key="ex-sev")
    status = f2.selectbox("Status", ["All", "OPEN", "RESOLVED"], key="ex-status")
    view = ex[ex["Severity"].isin(sev)]
    if status != "All":
        view = view[view["Status"].str.startswith(status)]
    edit = view[["Exception ID", "Severity", "Title", "CRAR impact (bps)", "Status", "Decision", "Reviewer", "Comment"]].copy()
    edit["Severity"] = edit["Severity"].map(lambda s: f"{SEV_ICON[s]} {s}")
    edit["Decision"] = edit["Decision"].replace("", None)
    edited = st.data_editor(
        edit, hide_index=True, key="ex-editor",
        disabled=["Exception ID", "Severity", "Title", "CRAR impact (bps)", "Status"],
        column_config={"Decision": st.column_config.SelectboxColumn("Decision", options=DECISIONS, required=False),
                       "Reviewer": st.column_config.TextColumn("Reviewer (required)"),
                       "Comment": st.column_config.TextColumn("Comment / basis", width="large"),
                       "CRAR impact (bps)": st.column_config.NumberColumn("CRAR impact (bps)", format="%+.1f"),
                       "Title": st.column_config.TextColumn("Title", width="large")})
    b1, b2, _ = st.columns([1, 1, 3])
    if b1.button("Apply decisions & re-run", type="primary", key="ex-apply"):
        rows = [{"exception_id": r["Exception ID"], "decision": r["Decision"] or "", "reviewer": r["Reviewer"] or "",
                 "comment": r["Comment"] or ""} for _, r in edited.iterrows() if r["Decision"]]
        unsigned = [r["exception_id"] for r in rows if not r["reviewer"].strip()]
        if unsigned:
            st.error(f"Reviewer name missing for: {', '.join(unsigned)}")
        elif not rows:
            st.info("No decisions entered.")
        else:
            ctx.rerun(rows)
    with b2:
        csv_button(st, frames.exceptions(run), "exception_queue.csv", "Download queue")


TAB = {"title": "Exception queue", "section": "Review", "icon": ":material/flag:", "order": 60,
       "subtitle": "Items the agent will not decide on its own", "render": render, "bare": True}
