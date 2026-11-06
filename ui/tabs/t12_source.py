"""Raw view of the uploaded workbook - every sheet, including ones the agent doesn't use yet."""
import pandas as pd

from ui.widgets import table
from ui import theme


def render(ctx):
    st = ctx.st
    if not ctx.input_path:
        st.info("Upload a workbook in the sidebar.")
        return
    xl = pd.ExcelFile(ctx.input_path)
    pf = ctx.extra.get("preflight")
    if pf:
        theme.section(st, "How the agent read this workbook")
        table(st, pd.DataFrame(pf["roles"]))
        if pf["items"]:
            table(st, pd.DataFrame(pf["items"]), **{"Value": st.column_config.NumberColumn("Value", format="%.2f")})
        for line in pf["log"]:
            st.caption("• " + line)
    theme.section(st, "Sheets")
    sheet = st.selectbox("Sheet", xl.sheet_names, key="src-sheet")
    df = xl.parse(sheet, header=None)
    st.caption(f"{df.shape[0]} rows × {df.shape[1]} columns · read-only (the agent never modifies source data)")
    st.dataframe(df.astype(str).replace("nan", ""), height=500)


TAB = {"title": "Source workbook", "section": "Data & evidence", "icon": ":material/table_view:", "order": 40,
       "subtitle": "How the agent read the uploaded file, sheet by sheet", "render": render, "needs_run": False}
