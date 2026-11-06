"""Large data import: stream big Excel/CSV files into SQLite, profile, browse, and use loan tapes as evidence."""
import pandas as pd

from capital_agent.bigdata import UNIT, summarise_loan_tape
from ui.widgets import table
from ui import theme

KIND = {"loan_tape": "Loan tape", "derivative_deals": "Derivative deals", "generic": "Table"}


def _import(ctx, path, name, sheets=None):
    st, store = ctx.st, ctx.extra["data"]
    bar = st.progress(0.0, text="Reading…")
    seen = {"n": 0}

    def cb(sheet, n):
        seen["n"] = n
        bar.progress(min(0.99, (n % 100000) / 100000), text=f"{sheet}: {n:,} rows imported")

    res = store.import_file(path, sheets=sheets, progress=cb, display_name=name)
    bar.progress(1.0, text=f"Done - {sum(r['rows'] for r in res):,} rows")
    return res


def render(ctx):
    st, store = ctx.st, ctx.extra["data"]
    st.caption("Big files are read row by row and stored in a local SQLite database, so memory stays flat. "
               "Header rows are detected automatically, even below title rows.")

    pf = ctx.extra.get("preflight") or {}
    if pf.get("large_sheets") and ctx.input_path:
        st.info(f"The uploaded workbook has large sheet(s) the standard loader skipped: "
                f"**{', '.join(pf['large_sheets'])}**.")
        if admin and st.button("Import them into the data store", key="bd-import-large"):
            res = _import(ctx, ctx.input_path, pf["ds"].path.split("/")[-1], pf["large_sheets"])
            table(st, pd.DataFrame(res))

    from ui import access
    admin = access.is_admin(st)
    if not admin:
        access.read_only_note(st, theme, "Importing or deleting data")
    theme.section(st, "Import a large file")
    up = st.file_uploader("Excel or CSV (up to 1 GB)", type=["xlsx", "xlsm", "csv"], key="bd-upload") if admin else None
    if up is not None and st.button("Import", type="primary", key="bd-go"):
        suffix = "." + up.name.rsplit(".", 1)[-1].lower()
        path = ctx.extra["save_upload"](up, suffix)
        res = _import(ctx, path, up.name)
        table(st, pd.DataFrame(res))

    tabs = store.tables()
    if not tabs:
        st.info("No tables imported yet.")
        return
    theme.section(st, "Imported tables")
    table(st, pd.DataFrame([{"Table": t["table_name"], "Type": KIND.get(t["kind"], t["kind"]), "File": t["source_file"],
                             "Sheet": t["sheet"], "Rows": t["n_rows"], "Columns": t["n_cols"],
                             "Header row": t["header_row"], "Import secs": t["seconds"],
                             "Imported": t["imported_at"]} for t in tabs]),
          **{"Rows": ctx.st.column_config.NumberColumn("Rows", format="%d")})

    name = st.selectbox("Open table", [t["table_name"] for t in tabs], key="bd-table",
                        format_func=lambda n: f"{n}  ({next(t for t in tabs if t['table_name'] == n)['n_rows']:,} rows)")
    meta = next(t for t in tabs if t["table_name"] == name)
    views = ["Profile", "Browse"] + (["Loan tape summary"] if meta["kind"] == "loan_tape" else [])
    for view, box in zip(views, st.tabs(views)):
        with box:
            if view == "Profile":
                prof = pd.DataFrame(store.profile(name))
                for col in ("min", "max", "sum"):
                    if col in prof:
                        prof[col] = prof[col].map(lambda v: "" if pd.isna(v) else f"{v:,.2f}")
                table(st, prof)
                st.caption("Original headers: " + " | ".join(h for h in meta["original_headers"] if h))
                if admin and st.button("Delete this table", key="bd-drop"):
                    store.drop(name)
                    st.rerun()
            elif view == "Browse":
                a, b, c = st.columns([2, 2, 1])
                col = a.selectbox("Filter column", ["(none)"] + meta["columns"], key="bd-fcol")
                val = b.text_input("contains", key="bd-fval")
                page = c.number_input("Page", min_value=1, value=1, step=1, key="bd-page")
                where = {col: val} if col != "(none)" and val else None
                cols, rows, total = store.preview(name, where, limit=200, offset=(int(page) - 1) * 200)
                st.caption(f"{total:,} matching rows · showing {min(200, max(total - (int(page) - 1) * 200, 0)):,}")
                st.dataframe(pd.DataFrame(rows, columns=cols), hide_index=True, height=420)
            else:
                unit = st.selectbox("Amounts in the tape are in", list(UNIT), key="bd-unit")
                sm = summarise_loan_tape(store, name, unit)
                theme.kpis(st, [{"label": "Loans", "value": f"{sm['rows']:,}"},
                                {"label": "Gross book", "value": theme.lakhs(sm['gross_lakhs'])},
                                {"label": "Total ECL", "value": theme.lakhs(sm['ecl_lakhs'])},
                                {"label": "Blended risk weight", "tone": "ok",
                                 "value": "-" if sm["blended_risk_weight"] is None else f"{sm['blended_risk_weight']:.1%}"}])
                st.caption("Columns used: " + ", ".join(f"{k} → {v}" for k, v in sm["columns_used"].items() if v))
                st.markdown("**By RBI risk-weight bucket** (para 18(1) mapping by product name — check it)")
                bk = pd.DataFrame(sm["by_bucket"])
                bk["share"] = bk["gross"] / sm["gross_lakhs"] * 100
                table(st, bk, gross=st.column_config.NumberColumn("Gross (₹ L)", format="%.2f"),
                      share=st.column_config.NumberColumn("Share", format="%.1f%%"))
                if sm["unmapped_share"] > 0.001:
                    st.warning(f"{sm['unmapped_share']:.1%} of the book has a product name the mapping could not "
                               "place. Those loans are left out of the blended risk weight.")
                a, b = st.columns(2)
                with a:
                    st.markdown("**By product**")
                    table(st, pd.DataFrame(sm["by_product"]),
                          gross=st.column_config.NumberColumn("Gross (₹ L)", format="%.2f"),
                          ecl=st.column_config.NumberColumn("ECL (₹ L)", format="%.2f"))
                with b:
                    st.markdown("**By ECL stage**")
                    table(st, pd.DataFrame(sm["by_stage"]),
                          gross=st.column_config.NumberColumn("Gross (₹ L)", format="%.2f"),
                          ecl=st.column_config.NumberColumn("ECL (₹ L)", format="%.2f"))
                    st.caption(f"Lifetime (Stage 2/3) ECL ₹{sm['lifetime_ecl_lakhs']:,.2f} L is reduced from RWA "
                               "under para 16(6); Stage 1 ECL counts in Tier 2.")
                attached = (ctx.extra.get("loan_tape") or {}).get("table") == name
                if attached:
                    st.success("This tape is attached to the agent run (see exception EXC-DATA-LOANTAPE).")
                    if st.button("Detach from agent run", key="bd-detach"):
                        ctx.extra["set_loan_tape"](None)
                elif st.button("Use this tape as evidence in the agent run", type="primary", key="bd-attach"):
                    ctx.extra["set_loan_tape"](sm)


TAB = {"title": "Large data import", "section": "Data & evidence", "icon": ":material/database:", "order": 10,
       "subtitle": "Stream big Excel/CSV files into the local store; use loan tapes as evidence", "render": render, "needs_run": False}
