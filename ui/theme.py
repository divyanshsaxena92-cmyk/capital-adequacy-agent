"""Design system - Grant Thornton style: core purple #4F2D7F on white, neutral greys, editorial typography.

Principles: restrained colour (purple carries the brand, greys carry the structure, status colours only for
status), hairline rules instead of boxes, small-caps labels, tabular figures, generous whitespace.
All layout is CSS grid/flex in our own HTML, so it renders identically at every width. System fonts only
(nothing loaded from the internet).
"""
from __future__ import annotations

from html import escape

PURPLE = "#4F2D7F"          # Grant Thornton core purple (brand guidance: fixed value)
PURPLE_DARK = "#3B2160"
PURPLE_MID = "#8A73AE"
PURPLE_SOFT = "#F6F3FA"
INK = "#1E1E24"
GREY = "#5F5C66"
GREY_LIGHT = "#8C8994"
LINE = "#E2DFE7"
GREEN = "#2F7A55"
AMBER = "#A86F00"
RED = "#A8344B"
CORAL = RED                 # kept for older imports
PALETTE = [PURPLE, PURPLE_MID, "#B9AACF", "#6E6A75", "#A5A2AB"]
SEV_COLOR = {"Critical": "#7A1F33", "High": RED, "Medium": "#C08A1A", "Low": "#A5A2AB"}
TONE = {"ok": GREEN, "warn": AMBER, "bad": RED}

FONT = '"Segoe UI", "Helvetica Neue", Arial, sans-serif'

CSS = f"""
<style>
html, body, .stApp, [data-testid="stSidebar"], .stMarkdown, button, input, textarea, select {{ font-family: {FONT}; }}
/* Streamlit's fixed toolbar is ~3.75rem tall: start content below it so the masthead is never hidden */
.block-container {{ padding: 3.6rem 1.25rem 2rem !important; max-width: 100% !important; }}   /* full desktop width */
[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stDecoration"], [data-testid="stAppDeployButton"] {{ display: none !important; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #FBFAFE 0%, #F6F2FB 100%); border-right: 1px solid {LINE}; }}
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {{ border-radius: 10px !important; padding: 6px 10px !important; }}
[data-testid="stSidebarNav"] a[aria-current="page"], [data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: #FFFFFF !important; box-shadow: 0 1px 2px rgba(20,18,26,.05), 0 4px 12px rgba(60,30,110,.08); }}
[data-testid="stSidebarNavSeparator"] {{ border-color: {LINE}; }}
[data-testid="stSidebar"] .block-container {{ padding-top: 1.5rem !important; }}
.stButton > button, .stDownloadButton > button {{ border-radius: 10px; font-weight: 600; }}
[data-testid="stExpander"] details {{ border-radius: 12px; }}
[data-testid="stPageLink-NavLink"] {{ background: #fff; border: 1px solid #E7E5EE; border-radius: 12px; padding: 8px 12px;
                                      box-shadow: 0 1px 2px rgba(20,18,26,.04); }}

/* masthead */
.gt-mast {{ display: flex; align-items: flex-end; justify-content: space-between; gap: 16px 24px; flex-wrap: wrap;
           margin: 0 0 18px 0; }}
.gt-firm {{ color: {PURPLE}; font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
.gt-prod {{ color: {INK}; font-size: 1.62rem; font-weight: 600; line-height: 1.15; margin-top: 3px; letter-spacing: -.015em; }}
.gt-tag {{ color: {GREY}; font-size: .86rem; margin-top: 4px; }}
.gt-meta {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.gt-meta span {{ font-size: .74rem; font-weight: 500; color: #3F3C4A; background: #F4F3F7; border: 1px solid #E7E5EE;
                 padding: 4px 10px; border-radius: 999px; white-space: nowrap; }}
.gt-meta span.ok {{ color: {GREEN}; background: #E8F3EC; border-color: #E8F3EC; font-weight: 600; }}
.gt-meta span.warn {{ color: {AMBER}; background: #FBF1DE; border-color: #FBF1DE; font-weight: 600; }}
.gt-meta span.bad {{ color: {RED}; background: #FBE9ED; border-color: #FBE9ED; font-weight: 600; }}

/* page title */
.gt-page {{ margin: 0 0 18px 0; }}
.gt-page .t {{ color: {INK}; font-size: 1.3rem; font-weight: 600; margin: 0; letter-spacing: -.01em; }}
.gt-page .s {{ color: {GREY}; font-size: .88rem; margin-top: 3px; }}

/* section heading */
.gt-section {{ color: {INK}; font-size: .95rem; font-weight: 600; margin: 26px 0 12px 0; letter-spacing: -.005em; }}

/* key figures: rounded cards with soft shadow (same language as the Overview) */
.gt-kpiwrap {{ container-type: inline-size; width: 100%; margin: 0 0 6px 0; }}
.gt-kpis {{ display: grid; gap: 12px; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); }}
@container (max-width: 1050px) {{ .gt-kpis {{ grid-template-columns: repeat(var(--n-md), minmax(0, 1fr)); }} }}
@container (max-width: 600px)  {{ .gt-kpis {{ grid-template-columns: repeat(var(--n-sm), minmax(0, 1fr)); }} }}
@container (max-width: 330px)  {{ .gt-kpis {{ grid-template-columns: minmax(0, 1fr); }} }}
.gt-kpi {{ background: #fff; border: 1px solid rgba(20,18,26,.06); border-radius: 16px; padding: 15px 18px 14px;
          min-width: 0; height: 106px; box-sizing: border-box; display: flex; flex-direction: column;
          box-shadow: 0 1px 2px rgba(20,18,26,.04), 0 8px 24px rgba(20,18,26,.05); }}
.gt-kpi .l {{ color: {GREY}; font-size: .76rem; font-weight: 500; }}
.gt-kpi .v {{ color: {INK}; font-size: 1.55rem; font-weight: 600; margin-top: 6px; line-height: 1.15;
             font-variant-numeric: tabular-nums; letter-spacing: -.015em; }}
.gt-kpi .d {{ color: {GREY_LIGHT}; font-size: .76rem; margin-top: auto; }}
.gt-kpi .l, .gt-kpi .v, .gt-kpi .d {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.gt-kpi .d.ok {{ color: {GREEN}; font-weight: 600; }} .gt-kpi .d.bad {{ color: {RED}; font-weight: 600; }}
.gt-kpi .d.warn {{ color: {AMBER}; font-weight: 600; }}
.gt-kpi.lead .v {{ color: {PURPLE}; }}

/* key-value table in a card */
.gt-kv {{ background: #fff; border: 1px solid rgba(20,18,26,.06); border-radius: 16px; padding: 4px 18px;
         box-shadow: 0 1px 2px rgba(20,18,26,.04), 0 8px 24px rgba(20,18,26,.05); }}
.gt-kv .r {{ display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-top: 1px solid {LINE};
            font-size: .87rem; }}
.gt-kv .r:first-child {{ border-top: none; }}
.gt-kv .k {{ color: {GREY}; }}
.gt-kv .v {{ color: {INK}; font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }}

.gt-note {{ background: {PURPLE_SOFT}; border: 1px solid #EAE3F4; border-radius: 12px; padding: 11px 15px; color: {INK};
           font-size: .86rem; margin: 0 0 16px 0; line-height: 1.5; }}
.gt-badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: .72rem; font-weight: 600; color: #fff; }}

/* sidebar brand + footer */
.gt-side-firm {{ color: {PURPLE}; font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
.gt-side-prod {{ color: {INK}; font-size: 1.02rem; font-weight: 600; margin-top: 2px; }}
.gt-side-sub {{ color: {GREY}; font-size: .76rem; margin: 2px 0 14px 0; padding-bottom: 12px; border-bottom: 1px solid {LINE}; }}
.gt-offline {{ color: {GREEN}; font-size: .76rem; font-weight: 600; padding: 8px 0 0 0; border-top: 1px solid {LINE};
              margin-top: 10px; }}
.gt-foot {{ color: {GREY_LIGHT}; font-size: .7rem; line-height: 1.5; margin-top: 18px; }}
</style>
"""


DARK_CSS = """
<style>
/* Night theme for the whole app (the dashboard component switches itself; this covers Streamlit's shell). */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"], [data-testid="stBottom"] > div
  { background: #0D0A13 !important; color: #EDE8F6 !important; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #120E19 0%, #0F0B16 100%) !important; border-right: 1px solid #2A2436 !important; }
[data-testid="stSidebar"] *, .stMarkdown, .stMarkdown p, .stMarkdown li, label, .stCaption, [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"] p, h1, h2, h3, h4 { color: #E6E1F0 !important; }
[data-testid="stSidebarNav"] a[aria-current="page"], [data-testid="stSidebarNavLink"][aria-current="page"]
  { background: #1F1930 !important; box-shadow: 0 0 0 1px #33294A !important; }
[data-testid="stSidebarNav"] a:hover, [data-testid="stSidebarNavLink"]:hover { background: #1A1526 !important; }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], textarea, input
  { background: #1C1726 !important; color: #F1EDF8 !important; border-color: #2E2740 !important; }
[data-baseweb="popover"] *, [data-baseweb="menu"] { background: #1C1726 !important; color: #F1EDF8 !important; }
.stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-secondary"]
  { background: #1C1726 !important; color: #F1EDF8 !important; border: 1px solid #2E2740 !important; }
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] { background: #4F2D7F !important; border-color: #4F2D7F !important; color: #fff !important; }
[data-testid="stExpander"] details, [data-testid="stExpander"] summary { background: #16121E !important; border-color: #2A2436 !important; }
[data-testid="stFileUploaderDropzone"] { background: #16121E !important; border-color: #2E2740 !important; }
[data-testid="stCode"], pre, code { background: #16121E !important; color: #E6E1F0 !important; }
[data-testid="stAlert"] { background: #1C1726 !important; }
.gt-kpi, .gt-kv { background: #16121E !important; border-color: #2A2436 !important; }
.gt-kpi .v, .gt-kv .v, .gt-prod, .gt-page .t, .gt-section { color: #F1EDF8 !important; }
.gt-note { background: #1C1530 !important; border-color: #33294A !important; color: #E6E1F0 !important; }
.gt-meta span { background: #1C1726 !important; border-color: #2E2740 !important; color: #E6E1F0 !important; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { filter: invert(.92) hue-rotate(180deg); }  /* canvas grids */
</style>
"""


def inject(st):
    st.markdown(CSS, unsafe_allow_html=True)
    if st.session_state.get("theme") == "dark":
        st.markdown(DARK_CSS, unsafe_allow_html=True)


def band(st, title: str, subtitle: str, chips: list[tuple[str, str]]):
    """Masthead: firm name, product, tagline; run facts on the right separated by hairlines."""
    meta = "".join(f'<span class="{escape(c)}">{escape(t)}</span>' for t, c in chips)
    st.markdown(f'<div class="gt-mast"><div><div class="gt-firm">Grant Thornton</div>'
                f'<div class="gt-prod">{escape(title)}</div><div class="gt-tag">{escape(subtitle)}</div></div>'
                f'<div class="gt-meta">{meta}</div></div>', unsafe_allow_html=True)


def page(st, title: str, subtitle: str = ""):
    st.markdown(f'<div class="gt-page"><div class="t">{escape(title)}</div>'
                + (f'<div class="s">{escape(subtitle)}</div>' if subtitle else "") + "</div>", unsafe_allow_html=True)


def section(st, text: str):
    st.markdown(f'<div class="gt-section">{escape(text)}</div>', unsafe_allow_html=True)


def note(st, text: str):
    """text may contain <b> and <br> only - everything else is escaped."""
    safe = escape(text).replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;br&gt;", "<br>")
    st.markdown(f'<div class="gt-note">{safe}</div>', unsafe_allow_html=True)


def kpis(st, items: list[dict]):
    """items: {label, value, delta?, delta_tone? ('ok'|'warn'|'bad'), lead? bool}.
    One row when wide; balanced rows when narrow (6 -> 3+3, 4 -> 2+2)."""
    n = len(items)
    md = n if n <= 4 else 3
    sm = 1 if n == 1 else 2
    cells = []
    for it in items:
        d = it.get("delta")
        dt = it.get("delta_tone", "")
        lab, val = escape(it["label"]), escape(str(it["value"]))
        dd = escape(d) if d else "&nbsp;"
        cells.append(f'<div class="gt-kpi{" lead" if it.get("lead") else ""}"><div class="l" title="{lab}">{lab}</div>'
                     f'<div class="v" title="{val}">{val}</div><div class="d {escape(dt)}" title="{escape(d or "")}">{dd}</div></div>')
    st.markdown(f'<div class="gt-kpiwrap"><div class="gt-kpis" style="--n:{n};--n-md:{md};--n-sm:{sm}">'
                f'{"".join(cells)}</div></div>', unsafe_allow_html=True)


def kv(st, rows: list[tuple[str, str]]):
    body = "".join(f'<div class="r"><span class="k">{escape(k)}</span><span class="v">{escape(v)}</span></div>'
                   for k, v in rows)
    st.markdown(f'<div class="gt-kv">{body}</div>', unsafe_allow_html=True)


def badge(sev: str) -> str:
    return f'<span class="gt-badge" style="background:{SEV_COLOR.get(sev, GREY)}">{escape(sev)}</span>'


def lakhs(v: float, dp: int = 0) -> str:
    return f"₹{v:,.{dp}f} L"
