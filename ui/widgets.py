"""Small display helpers shared by tabs."""
from __future__ import annotations

SEV_ICON = {"Critical": "🟥", "High": "🔴", "Medium": "🟠", "Low": "🟢"}
ROUTE_ICON = {"AUTO_ACCEPT": "Auto-accepted", "HUMAN_REVIEW": "Human review"}


def money(st, label="INR lakhs"):
    return st.column_config.NumberColumn(label, format="%.2f")


def pct(st, label):
    return st.column_config.NumberColumn(label, format="%.2f%%")


def as_pct(df, *cols):
    """Ratios stored as fractions -> percentage numbers for display."""
    out = df.copy()
    for c in cols:
        out[c] = out[c].map(lambda v: None if v is None else v * 100)
    return out


def table(st, df, height=None, **colcfg):
    kw = {"hide_index": True, "column_config": colcfg or None}
    if height:
        kw["height"] = height
    st.dataframe(df, **kw)


def csv_button(st, df, name, label="Download CSV"):
    st.download_button(label, df.to_csv(index=False).encode(), file_name=name, mime="text/csv", key=f"dl-{name}")
