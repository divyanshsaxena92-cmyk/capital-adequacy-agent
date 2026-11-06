"""Charts in the house palette (Altair ships with Streamlit). Falls back to st.bar_chart if Altair is absent."""
from __future__ import annotations

import pandas as pd

from .theme import FONT as _F, GREY, GREY_LIGHT, INK, LINE, PURPLE, PURPLE_MID, RED, SEV_COLOR

FONT = "Segoe UI, Helvetica Neue, Arial, sans-serif"   # same stack as the theme


def _alt():
    try:
        import altair as alt
        return alt
    except ImportError:
        return None


def _style(chart, height):
    return (chart.properties(height=height)
            .configure_view(strokeWidth=0)
            .configure_axis(labelFont=FONT, titleFont=FONT, labelColor=GREY, titleColor=GREY_LIGHT, labelFontSize=11,
                            titleFontSize=10.5, titleFontWeight="normal", gridColor="#EFEDF2", gridDash=[2, 3],
                            domainColor=LINE, tickColor=LINE, labelPadding=6)
            .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=INK, orient="top")
            .configure_text(font=FONT))


def _show(st, chart):
    st.altair_chart(chart)


def ratio_bullet(st, df: pd.DataFrame, height: int = 190):
    """df: label, actual (%), minimum (%). Bar = actual, red tick = RBI minimum."""
    alt = _alt()
    if alt is None:
        st.bar_chart(df.set_index("label")[["actual", "minimum"]], stack=False)
        return
    top = max(df["actual"].max(), df["minimum"].max()) * 1.18
    base = alt.Chart(df).encode(y=alt.Y("label:N", title=None, sort=None, axis=alt.Axis(labelFontSize=12)))
    bar = base.mark_bar(color=PURPLE, size=22).encode(
        x=alt.X("actual:Q", title="% of risk-weighted assets", scale=alt.Scale(domain=[0, top])),
        tooltip=[alt.Tooltip("label:N", title="Ratio"), alt.Tooltip("actual:Q", title="Actual %", format=".2f"),
                 alt.Tooltip("minimum:Q", title="RBI minimum %", format=".2f")])
    tick = base.mark_tick(color=INK, thickness=2, size=34).encode(x="minimum:Q")
    lbl = base.mark_text(align="left", dx=8, color=INK, fontSize=12).encode(
        x="actual:Q", text=alt.Text("actual:Q", format=".2f"))
    _show(st, _style(alt.layer(bar, tick, lbl), height))
    st.caption("Bar: actual ratio. Dark marker: RBI minimum.")


def hbars(st, df: pd.DataFrame, label: str, value: str, height: int = 280, fmt: str = ",.0f",
          title: str = "", color: str = PURPLE):
    alt = _alt()
    if alt is None:
        st.bar_chart(df.set_index(label)[[value]], horizontal=True)
        return
    base = alt.Chart(df).encode(y=alt.Y(f"{label}:N", title=None, sort="-x", axis=alt.Axis(labelLimit=230)))
    bar = base.mark_bar(color=color, size=16).encode(
        x=alt.X(f"{value}:Q", title=title), tooltip=[alt.Tooltip(f"{label}:N"), alt.Tooltip(f"{value}:Q", format=fmt)])
    txt = base.mark_text(align="left", dx=5, color=GREY, fontSize=10.5).encode(
        x=f"{value}:Q", text=alt.Text(f"{value}:Q", format=fmt))
    _show(st, _style(alt.layer(bar, txt), height))


def impact_bars(st, df: pd.DataFrame, height: int = 280):
    """df: label, bps, severity. Positive = CRAR would rise if the alternative is accepted."""
    alt = _alt()
    if alt is None:
        st.bar_chart(df.set_index("label")[["bps"]], horizontal=True)
        return
    sev = [s for s in ["Critical", "High", "Medium", "Low"] if s in set(df["severity"])]
    base = alt.Chart(df).encode(y=alt.Y("label:N", title=None, sort="-x", axis=alt.Axis(labelLimit=230)))
    bar = base.mark_bar(size=16).encode(
        x=alt.X("bps:Q", title="CRAR impact if the alternative is accepted (bps)"),
        color=alt.Color("severity:N", title=None, scale=alt.Scale(domain=sev, range=[SEV_COLOR[s] for s in sev])),
        tooltip=[alt.Tooltip("label:N", title="Item"), alt.Tooltip("bps:Q", title="bps", format="+.1f"),
                 alt.Tooltip("severity:N")])
    rule = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=GREY).encode(x="x:Q")
    _show(st, _style(alt.layer(bar, rule), height))


def waterfall(st, steps: list[tuple[str, float, str]], height: int = 330):
    """steps: (label, amount, kind) with kind in {'add','sub','total'}; totals are drawn from zero."""
    rows, run = [], 0.0
    for label, amt, kind in steps:
        if kind == "total":
            rows.append({"label": label, "start": 0.0, "end": amt, "kind": "Total", "amount": amt})
            run = amt
        else:
            start, run = run, run + amt
            rows.append({"label": label, "start": start, "end": run, "kind": "Increase" if amt >= 0 else "Decrease",
                         "amount": amt})
    df = pd.DataFrame(rows)
    df["order"] = range(len(df))
    alt = _alt()
    if alt is None:
        st.bar_chart(df.set_index("label")[["amount"]])
        return
    kinds = [k for k in ["Increase", "Decrease", "Total"] if k in set(df["kind"])]
    cmap = {"Increase": PURPLE_MID, "Decrease": RED, "Total": PURPLE}
    base = alt.Chart(df).encode(x=alt.X("label:N", title=None, sort=alt.SortField("order"),
                                        axis=alt.Axis(labelAngle=-28, labelLimit=170, labelFontSize=11)))
    bar = base.mark_bar(size=30).encode(
        y=alt.Y("start:Q", title="₹ lakhs"), y2="end:Q",
        color=alt.Color("kind:N", title=None, scale=alt.Scale(domain=kinds, range=[cmap[k] for k in kinds])),
        tooltip=[alt.Tooltip("label:N", title="Step"), alt.Tooltip("amount:Q", title="₹ lakhs", format=",.2f")])
    df["top"] = df[["start", "end"]].max(axis=1)
    txt = alt.Chart(df).mark_text(dy=-7, color=GREY, fontSize=10).encode(
        x=alt.X("label:N", sort=alt.SortField("order")), y="top:Q", text=alt.Text("amount:Q", format=",.0f"))
    _show(st, _style(alt.layer(bar, txt), height))
