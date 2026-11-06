"""Overview dashboard as one self-contained HTML/CSS/SVG block (bento grid).

Rendered with st.html: no iframe, no JavaScript, no external fonts or scripts - so it works offline and
looks identical on every machine. Every chart is drawn here from the engine's numbers.
"""
from __future__ import annotations

import math
from html import escape

P = "#4F2D7F"          # Grant Thornton purple
P2 = "#7C5CB0"
P3 = "#B9A8D9"
P4 = "#E9E3F4"
INK = "#14121A"
MUTED = "#6B6878"
FAINT = "#9A97A6"
LINE = "#ECEAF1"
GREEN = "#2E7D57"
AMBER = "#B7791F"
RED = "#B4364E"
SEV = {"Critical": "#7A1F33", "High": RED, "Medium": AMBER, "Low": "#A9A6B3"}

CSS = f"""
<style>
.cx {{ --r: 18px; container-type: inline-size; background: #EEEFF3; border-radius: 26px; padding: 16px;
      font-family: "Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
      color: {INK}; -webkit-font-smoothing: antialiased; }}
.cx * {{ box-sizing: border-box; }}
.cx-grid {{ display: grid; gap: 14px; align-items: start;
           grid-template-columns: 292px minmax(0, 1fr) 300px; grid-template-areas: "l c r"; }}
@container (max-width: 1180px) {{ .cx-grid {{ grid-template-columns: minmax(0,1fr) minmax(0,1fr);
                                              grid-template-areas: "c c" "l r"; }} }}
@container (max-width: 760px)  {{ .cx-grid {{ grid-template-columns: minmax(0,1fr); grid-template-areas: "c" "l" "r"; }} }}
.cx-l {{ grid-area: l; }} .cx-c {{ grid-area: c; }} .cx-r {{ grid-area: r; }}
.cx-col {{ display: flex; flex-direction: column; gap: 14px; min-width: 0; }}
.cx-card {{ background: #fff; border-radius: var(--r); padding: 16px 18px;
           border: 1px solid rgba(20,18,26,.04);
           box-shadow: 0 1px 2px rgba(20,18,26,.04), 0 8px 24px rgba(20,18,26,.05); }}
.cx-h {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }}
.cx-t {{ font-size: 13.5px; font-weight: 600; color: {INK}; letter-spacing: -.005em; }}
.cx-chip {{ font-size: 11px; font-weight: 500; color: #3F3C4A; background: #F4F3F7; border: 1px solid #E7E5EE;
           padding: 3px 9px; border-radius: 999px; white-space: nowrap; }}
.cx-ok, .cx-warn {{ white-space: nowrap; }}
.cx-ok {{ font-size: 11px; font-weight: 600; color: {GREEN}; background: #E8F3EC; padding: 3px 9px; border-radius: 999px; }}
.cx-warn {{ font-size: 11px; font-weight: 600; color: {AMBER}; background: #FBF1DE; padding: 3px 9px; border-radius: 999px; }}
.cx-lbl {{ font-size: 11.5px; color: {MUTED}; }}
.cx-big {{ font-size: 34px; font-weight: 600; letter-spacing: -.02em; line-height: 1.05; font-variant-numeric: tabular-nums; }}
.cx-big small {{ font-size: 15px; font-weight: 500; color: {MUTED}; margin-left: 1px; }}
.cx-num {{ font-variant-numeric: tabular-nums; }}
.cx-row2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
.cx-mini {{ padding: 13px 15px; }}
.cx-mini .v {{ font-size: 19px; font-weight: 600; margin-top: 6px; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.cx-ic {{ display: inline-flex; width: 18px; height: 18px; border-radius: 50%; align-items: center; justify-content: center;
         background: {P4}; color: {P}; font-size: 10px; font-weight: 700; margin-right: 6px; vertical-align: -4px; }}
.cx-list .it {{ display: grid; grid-template-columns: 10px minmax(0,1fr) auto; gap: 10px; align-items: center;
               padding: 9px 0; border-top: 1px solid {LINE}; }}
.cx-list .it:first-child {{ border-top: none; padding-top: 2px; }}
.cx-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
.cx-list .nm {{ font-size: 12.5px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cx-list .sb {{ font-size: 11px; color: {FAINT}; margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cx-list .bp {{ font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }}
.cx-leg {{ display: grid; grid-template-columns: 10px 1fr auto; gap: 8px 8px; align-items: center; font-size: 12px; }}
.cx-leg .sw {{ width: 8px; height: 8px; border-radius: 50%; }}
.cx-leg .pc {{ color: {MUTED}; font-variant-numeric: tabular-nums; text-align: right; }}
.cx-stats {{ display: grid; grid-template-columns: 1.55fr 1fr 1fr; }}
.cx-stats > div {{ padding: 2px 10px; border-left: 1px solid {LINE}; min-width: 0; }}
.cx-stats > div:first-child {{ border-left: none; padding-left: 0; }}
.cx-stats .v {{ font-size: 15px; font-weight: 600; margin-top: 4px; white-space: nowrap; font-variant-numeric: tabular-nums; }}
.cx-hero {{ position: relative; padding: 0; overflow: hidden; height: 470px;
           background: radial-gradient(120% 90% at 60% 35%, #FFFFFF 0%, #F4F1F9 55%, #ECE7F5 100%); }}
.cx-hero .hd {{ position: absolute; left: 22px; top: 18px; z-index: 2; }}
.cx-hero .ttl {{ font-size: 25px; font-weight: 600; letter-spacing: -.02em; }}
.cx-hero .chips {{ display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }}
.cx-glass {{ position: absolute; z-index: 2; background: rgba(255,255,255,.72); border: 1px solid rgba(255,255,255,.9);
            backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-radius: 16px;
            box-shadow: 0 8px 28px rgba(40,24,80,.10); }}
.cx-comp {{ right: 16px; top: 16px; width: 228px; padding: 14px 16px; }}
.cx-comp .rw {{ display: flex; justify-content: space-between; align-items: baseline; padding: 7px 0; border-top: 1px solid {LINE}; }}
.cx-comp .rw:first-of-type {{ border-top: none; }}
.cx-comp .k {{ font-size: 12px; color: {MUTED}; }}
.cx-comp .v {{ font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }}
.cx-comp .m {{ font-size: 11px; color: {FAINT}; margin-left: 6px; font-weight: 500; }}
.cx-legend {{ left: 16px; bottom: 16px; padding: 10px 14px; display: flex; gap: 14px; flex-wrap: wrap; font-size: 11.5px; }}
.cx-legend span {{ display: inline-flex; align-items: center; gap: 6px; color: #3F3C4A; white-space: nowrap; }}
.cx-legend i {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
.cx-hero svg.scene {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
.cx-score .rw {{ display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 12px; align-items: baseline;
                padding: 9px 0; border-top: 1px solid {LINE}; }}
.cx-score .rw:first-of-type {{ border-top: none; padding-top: 0; }}
.cx-score .k {{ font-size: 12.5px; font-weight: 500; }}
.cx-score .v {{ font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }}
.cx-score .m {{ font-size: 11.5px; color: {FAINT}; font-variant-numeric: tabular-nums; min-width: 54px; text-align: right; }}
.cx-bars .b {{ padding: 8px 0 9px; border-top: 1px solid {LINE}; }}
.cx-bars .b:first-child {{ border-top: none; padding-top: 0; }}
.cx-bars .tp {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 6px; gap: 10px; }}
.cx-bars .tp span:first-child {{ color: {MUTED}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cx-bars .tp span:last-child {{ font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.cx-track {{ height: 5px; background: #F0EEF4; border-radius: 999px; overflow: hidden; }}
.cx-fill {{ height: 100%; border-radius: 999px; background: {P}; }}
.cx-imp .rw {{ display: grid; grid-template-columns: minmax(0,1fr) 70px 40px; gap: 10px; align-items: center; padding: 6px 0; }}
.cx-imp .nm {{ font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cx-imp .bp {{ font-size: 12px; font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }}
.cx-kb {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
.cx-kb .v {{ font-size: 18px; font-weight: 600; margin-top: 3px; font-variant-numeric: tabular-nums; }}
.cx svg text {{ font-family: inherit; }}
.cx-sens {{ padding-left: 30px; }}
.cx-sens .plot {{ position: relative; height: 112px; margin: 6px 0 0 0; }}
.cx-sens .curve {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }}
.cx-sens .gl {{ position: absolute; left: 0; right: 0; border-top: 1px dashed {LINE}; }}
.cx-sens .yl {{ position: absolute; left: -30px; transform: translateY(-50%); font-size: 10px; color: {FAINT}; }}
.cx-sens .minl {{ position: absolute; right: 0; transform: translateY(-120%); font-size: 10px; color: {RED}; }}
.cx-sens .dot {{ position: absolute; width: 10px; height: 10px; margin: -5px 0 0 -5px; border-radius: 50%;
                background: #fff; border: 2px solid {P}; box-sizing: border-box; }}
.cx-sens .tip {{ position: absolute; transform: translate(-50%, calc(-100% - 10px)); font-size: 10.5px; white-space: nowrap;
                background: #fff; border: 1px solid {LINE}; border-radius: 7px; padding: 3px 8px; color: {INK};
                box-shadow: 0 2px 8px rgba(20,18,26,.06); }}
.cx-sens .xaxis {{ position: relative; height: 18px; margin-top: 4px; }}
.cx-sens .xl {{ position: absolute; transform: translateX(-50%); font-size: 10px; color: {FAINT}; white-space: nowrap; }}
.cx-sens .xl:last-child {{ transform: translateX(-100%); }} .cx-sens .xl:first-child {{ transform: none; }}
.cx-wf {{ display: grid; grid-template-columns: 34px minmax(0,1fr); }}
.cx-wf .yax {{ position: relative; height: 196px; }}
.cx-wf .yl {{ position: absolute; right: 8px; transform: translateY(50%); font-size: 10px; color: {FAINT}; }}
.cx-wf .gl {{ display: none; }}
.cx-wf .cols {{ display: flex; position: relative; }}
.cx-wf .c {{ flex: 1 1 0; min-width: 0; }}
.cx-wf .area {{ position: relative; height: 196px; border-bottom: 1px solid #D9D6E2; }}
.cx-wf .bar {{ position: absolute; left: 22%; right: 22%; border-radius: 5px; }}
.cx-wf .bar.up {{ background: {P3}; }} .cx-wf .bar.down {{ background: #E5A9B5; }} .cx-wf .bar.total {{ background: {P}; }}
.cx-wf .val {{ position: absolute; left: 0; right: 0; text-align: center; font-size: 10.5px; color: {MUTED};
              font-variant-numeric: tabular-nums; }}
.cx-wf .val.tot {{ color: {INK}; font-weight: 600; }}
.cx-wf .cn {{ position: absolute; left: 78%; width: 44%; border-top: 1px dashed #CFCBDA; z-index: 1; }}
.cx-wf .cap {{ font-size: 10.5px; color: {MUTED}; text-align: center; line-height: 1.25; padding: 7px 2px 0;
              display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: 34px; }}
</style>
"""


# ------------------------------------------------------------------ helpers
def _l(v: float) -> str:
    return f"₹{v:,.0f}"


def _smooth(pts: list[tuple[float, float]]) -> str:
    """Catmull-Rom spline through points, as an SVG cubic path."""
    if len(pts) < 2:
        return ""
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i > 0 else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d


FRIENDLY = [("45-ic", "Statutory reserve (45-IC)"), ("esop", "ESOP & other reserves"),
            ("corporate guarantee", "Parent guarantee reserve"), ("cost of hedging", "Cost of hedging reserve"),
            ("cash flow hedge", "Cash flow hedge reserve"), ("remeasurement", "Actuarial remeasurement"),
            ("derivative cem", "Derivative counterparty data"), ("loan book does not reconcile", "Loan book reconciliation"),
            ("prepaid", "Prepaid expenses"), ("other advances", "Other advances (TDS)"),
            ("framework", "Applicable RBI framework"), ("layer not stated", "NBFC layer"),
            ("co-lending", "Co-lending profit"), ("default loss guarantee", "Default loss guarantee"),
            ("off-balance-sheet", "Off-balance-sheet exposures"), ("dta composition", "Deferred tax composition"),
            ("rwa010", "RWA schedule column"), ("non-numeric", "Input column format"),
            ("loan tape", "Loan tape evidence"), ("loans", "Loan book risk weight")]


def _short(label: str, n: int = 34) -> str:
    low = label.lower()
    for key, name in FRIENDLY:
        if key in low:
            return name if len(name) <= n else name[: n - 1] + "…"
    s = label.split(" (")[0].replace("OCI – ", "").replace("OCI - ", "").replace("Equity others - ", "")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


COMPACT = {"Statutory reserve (45-IC)": "Statutory reserve", "Parent guarantee reserve": "Parent guarantee",
           "ESOP & other reserves": "ESOP reserves", "Derivative counterparty data": "Derivative data",
           "Loan book risk weight": "Loan risk weight", "Cost of hedging reserve": "Hedging reserve",
           "Actuarial remeasurement": "Actuarial gain", "Off-balance-sheet exposures": "Off-balance sheet"}
WF = [("equity share capital", "Share capital"), ("securities premium", "Share premium"),
      ("retained earnings", "Retained earnings"), ("cost of hedging", "Hedging reserve"),
      ("deferred tax", "Deferred tax"), ("prepaid", "Prepaid"), ("statutory", "Statutory reserve")]


def _compact(label: str) -> str:
    s = _short(label, 40)
    return COMPACT.get(s, s)


def _wf_name(label: str) -> str:
    low = label.lower()
    return next((n for k, n in WF if k in low), _short(label, 22))


CAT = {"Regulatory interpretation": "Interpretation", "Data completeness": "Data", "Data quality": "Data",
       "Classification": "Classification", "Governance": "Governance", "Evidence": "Evidence",
       "Completeness": "Completeness"}


# ------------------------------------------------------------------ charts
def sensitivity_chart(run) -> str:
    """CRAR as the loan risk weight moves from 50% to 150%. The curve stretches to any width; all text is HTML
    so it stays the same size at every width."""
    loans = next(a for a in run.rwa_applied if a.cls.label == "Loans")
    xs = list(range(50, 155, 5))
    ys = [run._compute({"rwa": {loans.cls.item_id: x / 100}}).crar * 100 for x in xs]
    m = run.minimums["crar"] * 100
    lo, hi = min(min(ys), m) - 3, max(ys) + 3
    px = lambda x: (x - 50) / 100 * 100                    # % of plot width
    py = lambda y: (hi - y) / (hi - lo) * 100              # % of plot height
    pts = [(px(x), py(y)) for x, y in zip(xs, ys)]
    path = _smooth(pts)
    area = path + f" L100,100 L0,100 Z"
    cur = loans.applied * 100
    cx_, cy = px(cur), py(run.final.crar * 100)
    ylab = "".join(f'<span class="yl" style="top:{py(v):.1f}%">{v:.0f}%</span>'
                   f'<span class="gl" style="top:{py(v):.1f}%"></span>' for v in _ticks(lo, hi, 4))
    xlab = "".join(f'<span class="xl" style="left:{px(x):.1f}%">{x}%</span>' for x in (50, 75, 100, 125, 150))
    tip_left = min(max(cx_, 22), 78)
    return f"""<div class="cx-sens"><div class="plot">{ylab}
<svg viewBox="0 0 100 100" preserveAspectRatio="none" class="curve"><defs><linearGradient id="cxg" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{P}" stop-opacity=".26"/><stop offset="1" stop-color="{P}" stop-opacity="0"/></linearGradient></defs>
<path d="{area}" fill="url(#cxg)"/><path d="{path}" fill="none" stroke="{P}" stroke-width="2" vector-effect="non-scaling-stroke"/>
<line x1="0" x2="100" y1="{py(m):.2f}" y2="{py(m):.2f}" stroke="{RED}" stroke-width="1" stroke-dasharray="4 3" vector-effect="non-scaling-stroke"/>
<line x1="{cx_:.2f}" x2="{cx_:.2f}" y1="0" y2="100" stroke="{P}" stroke-opacity=".3" stroke-dasharray="2 2" vector-effect="non-scaling-stroke"/></svg>
<span class="minl" style="top:{py(m):.1f}%">RBI minimum {m:.0f}%</span>
<span class="dot" style="left:{cx_:.1f}%;top:{cy:.1f}%" title="Loans at {cur:.0f}% → CRAR {run.final.crar:.2%}"></span>
<span class="tip" style="left:{tip_left:.1f}%;top:{cy:.1f}%">Current {cur:.0f}% · {run.final.crar:.2%}</span>
</div><div class="xaxis">{xlab}</div></div>"""


def _wrap2(text: str, width: int) -> tuple[str, str]:
    """Two lines of at most `width` characters, breaking on spaces; ellipsis if it still doesn't fit."""
    words, l1, l2 = text.split(" "), "", ""
    for w in words:
        if not l2 and len((l1 + " " + w).strip()) <= width:
            l1 = (l1 + " " + w).strip()
        else:
            l2 = (l2 + " " + w).strip()
    if len(l2) > width:
        l2 = l2[: width - 1].rstrip() + "…"
    if len(l1) > width:
        l1 = l1[: width - 1] + "…"
    return l1, l2


def _ticks(lo, hi, n):
    step = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(step)) if step > 0 else 1
    step = max(mag, round(step / mag) * mag)
    v = math.ceil(lo / step) * step
    out = []
    while v <= hi:
        out.append(v)
        v += step
    return out


def donut(parts: list[tuple[str, float, str]], size: int = 118) -> str:
    total = sum(v for _, v, _ in parts) or 1
    r, c = 44, 2 * math.pi * 44
    off, segs = 0.0, []
    for name, v, col in parts:
        frac = v / total
        segs.append(f'<circle class="seg" style="animation-delay:{len(segs) * 160}ms" r="{r}" cx="60" cy="60" '
                    f'fill="none" stroke="{col}" stroke-width="14" '
                    f'stroke-dasharray="{max(frac * c - 2, 0):.2f} {c:.2f}" stroke-dashoffset="{-off * c:.2f}" '
                    f'transform="rotate(-90 60 60)"><title>{escape(name)}: {frac:.1%}</title></circle>')
        off += frac
    return (f'<svg viewBox="0 0 120 120" width="{size}" height="{size}" role="img" aria-label="RWA mix">'
            f'<circle r="{r}" cx="60" cy="60" fill="none" stroke="#F2F0F6" stroke-width="14"/>{"".join(segs)}'
            f'<text x="60" y="57" text-anchor="middle" font-size="9" fill="{MUTED}">RWA</text>'
            f'<text x="60" y="71" text-anchor="middle" font-size="12" font-weight="600" fill="{INK}">100%</text></svg>')


def waterfall(steps: list[tuple[str, float, str]]) -> str:
    """Bridge chart in HTML: bars stretch with the card, labels stay a constant size."""
    rows, run_ = [], 0.0
    for lbl, amt, kind in steps:
        if kind == "total":
            rows.append((lbl, 0.0, amt, "total", amt))
            run_ = amt
        else:
            rows.append((lbl, run_, run_ + amt, "up" if amt >= 0 else "down", amt))
            run_ += amt
    top = max(max(a, b) for _, a, b, _, _ in rows) * 1.14
    pc = lambda v: v / top * 100
    grid = "".join(f'<span class="gl" style="bottom:{pc(v):.2f}%"></span><span class="yl" style="bottom:{pc(v):.2f}%">'
                   f'{v / 1000:.0f}k</span>' for v in _ticks(0, top, 4))
    cols = []
    for i, (lbl, a, b, kind, amt) in enumerate(rows):
        lo_, hi_ = min(a, b), max(a, b)
        val = f"{amt / 1000:.1f}k" if kind == "total" else f"{amt / 1000:+.1f}k"
        # (bars animate upward in sequence; see .cv .cx-wf .bar in overview_v2)
        conn = (f'<span class="cn" style="bottom:{pc(b):.2f}%"></span>' if i < len(rows) - 1 else "")
        cols.append(f'<div class="c"><div class="area">'
                    f'<span class="bar {kind}" style="bottom:{pc(lo_):.2f}%;height:max({pc(hi_ - lo_):.2f}%,2px);'
                    f'animation-delay:{i * 80}ms" '
                    f'title="{escape(lbl)}: {amt:+,.2f} lakhs"></span>'
                    f'<span class="val {"tot" if kind == "total" else ""}" style="bottom:calc({pc(hi_):.2f}% + 4px)">{val}</span>{conn}</div>'
                    f'<div class="cap">{escape(_wf_name(lbl))}</div></div>')
    return f'<div class="cx-wf"><div class="yax">{grid}</div><div class="cols">{"".join(cols)}</div></div>'


def capital_scene(t1: float, t2: float, req: float, req_t1: float) -> str:
    """Isometric columns: capital held (Tier 1 + Tier 2) beside what RBI requires.
    Composed around the overlays: title top-left, compliance card top-right, legend bottom-left."""
    W, H = 760, 470
    c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
    ox, oy = 372, 318

    def iso(x, y, z):
        return ox + (x - y) * c30, oy + (x + y) * s30 - z

    def pts(*p):
        return " ".join(f"{a:.1f},{b:.1f}" for a, b in (iso(*q) for q in p))

    def box(x, y, w, d, z0, h, top, left, right, stroke="none", dash=""):
        z1 = z0 + h
        sd = f' stroke="{stroke}" stroke-width="1.2" stroke-linejoin="round"' + (f' stroke-dasharray="{dash}"' if dash else "")
        return (f'<polygon points="{pts((x, y + d, z0), (x + w, y + d, z0), (x + w, y + d, z1), (x, y + d, z1))}" fill="{left}"{sd}/>'
                f'<polygon points="{pts((x + w, y, z0), (x + w, y + d, z0), (x + w, y + d, z1), (x + w, y, z1))}" fill="{right}"{sd}/>'
                f'<polygon points="{pts((x, y, z1), (x + w, y, z1), (x + w, y + d, z1), (x, y + d, z1))}" fill="{top}"{sd}/>')

    k = 205 / (max(t1 + t2, req) or 1)
    grid = []
    for i in range(-5, 6):
        for a_, b_ in (((i * 44, -220, 0), (i * 44, 220, 0)), ((-220, i * 44, 0), (220, i * 44, 0))):
            p1, p2 = iso(*a_), iso(*b_)
            grid.append(f'<line class="sc-grid" x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="#DED7EC" stroke-width=".8"/>')
    floor = (f'<polygon class="sc-floor" points="{pts((-220, -220, 0), (220, -220, 0), (220, 220, 0), (-220, 220, 0))}" fill="#F4F0FA"/>'
             + "".join(grid))
    ghost = ("rgba(255,255,255,.6)", "rgba(255,255,255,.4)", "rgba(233,227,244,.55)")
    # back-left: requirement ghost; centre: capital held; front-right: Tier 1 requirement ghost
    reqc = box(-196, -64, 84, 84, 0, req * k, *ghost, stroke="#9C8BC0", dash="4 3")
    held = (box(-40, -40, 92, 92, 0, t1 * k, "#6E50A0", "#4F2D7F", "#3B2160")
            + box(-40, -40, 92, 92, t1 * k, t2 * k, "#DCD2EE", "#BFAFDD", "#A994CF"))
    zr = req_t1 * k                                           # Tier 1 minimum drawn as a ring on the column
    ring = (f'<polyline points="{pts((-40, 52, zr), (52, 52, zr), (52, -40, zr))}" fill="none" stroke="#FFFFFF" '
            f'stroke-width="1.6" stroke-dasharray="5 4" opacity=".95"/>')
    sh = iso(6, 6, 0)
    shadow = f'<ellipse cx="{sh[0]:.1f}" cy="{sh[1] + 10:.1f}" rx="118" ry="30" fill="#4F2D7F" opacity=".07"/>'

    def label(anchor, tx, ty, txt, sub, align="start"):
        x0, y0 = anchor
        ex = tx - 6 if align == "start" else tx + 6
        return (f'<polyline class="sc-ll" points="{x0:.1f},{y0:.1f} {ex:.1f},{ty:.1f}" fill="none" stroke="#A9A3B8" stroke-width=".9"/>'
                f'<circle class="sc-dot" cx="{x0:.1f}" cy="{y0:.1f}" r="3" fill="#fff" stroke="{INK}" stroke-width="1.4"/>'
                f'<text class="sc-lt" x="{tx:.1f}" y="{ty - 2:.1f}" font-size="12.5" font-weight="600" fill="{INK}" text-anchor="{align}">{escape(txt)}</text>'
                f'<text class="sc-ls" x="{tx:.1f}" y="{ty + 13:.1f}" font-size="11" fill="{MUTED}" text-anchor="{align}">{escape(sub)}</text>')

    t1_anchor = iso(52, 10, (zr + t1 * k) / 2)                 # right face, Tier 1 section above the ring
    t2_anchor = iso(52, 10, t1 * k + t2 * k / 2)               # right face, Tier 2 band
    rq_anchor = iso(-196, -10, req * k * 0.7)                  # left face of requirement ghost
    r1_anchor = iso(52, 6, zr)                                 # the ring on the right face
    labels = (label(t1_anchor, 520, 300, "Tier 1 capital", f"{_l(t1)} lakhs")
              + label(t2_anchor, 520, 238, "Tier 2 capital", f"{_l(t2)} lakhs")
              + label(rq_anchor, 176, 232, "Required at 15% of RWA", f"{_l(req)} lakhs", "end")
              + label(r1_anchor, 520, 362, "Tier 1 minimum (10%)", f"{_l(req_t1)} lakhs"))
    return (f'<svg class="scene" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet" role="img" '
            f'aria-label="Capital held versus required">{floor}<g class="cv-shadow">{shadow}</g>{reqc}<g class="cv-float">{held}{ring}{labels}</g></svg>')


# ------------------------------------------------------------------ assemble
def build(run, rag_stats: dict | None = None) -> str:
    r, m = run.final, run.minimums
    req = m["crar"] * r.total_rwa
    req_t1 = m["tier1"] * r.total_rwa
    ok = r.crar >= m["crar"] and r.tier1_ratio >= m["tier1"]
    open_ex = [e for e in run.exceptions if e.status == "OPEN"]
    hi = sum(e.severity in ("Critical", "High") for e in open_ex)
    date = f"{run.ds.reporting_date:%d %b %Y}"
    entity = f"{run.entity_type} · {'Middle' if run.layer == 'ML' else 'Upper'} Layer"

    # ---- left column
    sens = sensitivity_chart(run)
    left = f"""
<div class="cx-card"><div class="cx-h"><span class="cx-t">Capital ratio</span><span class="cx-chip">CRAR</span></div>
 <div style="display:flex;justify-content:space-between;align-items:flex-end">
  <div><div class="cx-lbl">Capital to risk-weighted assets</div><div class="cx-big">{r.crar * 100:.2f}<small>%</small></div></div>
 </div>
 <div style="margin-top:8px"><span class="{'cx-ok' if r.crar >= m['crar'] else 'cx-warn'}">+{(r.crar - m['crar']) * 100:.2f} pp above the {m['crar']:.0%} minimum</span></div>
 <div style="margin-top:14px"><div class="cx-lbl" style="margin-bottom:22px">CRAR if the loan risk weight changes</div>{sens}</div>
</div>
<div class="cx-row2">
 <div class="cx-card cx-mini"><div class="cx-lbl"><span class="cx-ic">1</span>Tier 1 capital</div><div class="v">{_l(r.tier1)} L</div></div>
 <div class="cx-card cx-mini"><div class="cx-lbl"><span class="cx-ic">2</span>Tier 2 capital</div><div class="v">{_l(r.tier2)} L</div></div>
</div>"""
    items = "".join(
        f'<div class="it"><span class="cx-dot" style="background:{SEV.get(e.severity, FAINT)}"></span>'
        f'<div style="min-width:0"><div class="nm" title="{escape(e.title)}">{escape(_short(e.title, 34))}</div>'
        f'<div class="sb">{escape(e.severity)} · {escape(CAT.get(e.category, e.category))}</div></div>'
        f'<span class="bp" style="color:{GREEN if e.impact_crar_bps > 0 else (RED if e.impact_crar_bps < 0 else FAINT)}">'
        f'{(f"{e.impact_crar_bps:+.0f} bps") if e.scenario_overrides else "info"}</span></div>'
        for e in open_ex[:4])
    left += f"""
<div class="cx-card"><div class="cx-h"><span class="cx-t">Review queue</span><span class="{'cx-warn' if hi else 'cx-ok'}">{len(open_ex)} open</span></div>
 <div class="cx-list">{items or '<div class="cx-lbl">Nothing open.</div>'}</div></div>"""
    # RWA mix
    grp = {"Loans": 0.0, "Receivables": 0.0, "Other": 0.0}
    for a in run.rwa_applied:
        v = a.exposure * a.applied
        lb = a.cls.label.lower()
        if a.cls.label == "Loans":
            grp["Loans"] += v
        elif any(t in lb for t in ("receivable", "deposit", "advance", "gateway")):
            grp["Receivables"] += v
        else:
            grp["Other"] += v
    grp["Derivatives"] = r.rwa_ccr
    cols = [P, P2, P3, "#D9D2E9"]
    parts = [(k_, v, c_) for (k_, v), c_ in zip(grp.items(), cols)]
    tot = sum(v for _, v, _ in parts) or 1
    leg = "".join(f'<span class="sw" style="background:{c_}"></span><span>{escape(k_)}</span>'
                  f'<span class="pc">{v / tot:.1%}</span>' for k_, v, c_ in parts)
    passed = sum(c.status == "PASS" for c in run.checks)
    bench = run.benchmark
    tie = f"{sum(b['status'] == 'PASS' for b in bench)}/{len(bench)}" if bench else "–"
    left += f"""
<div class="cx-card"><div class="cx-h"><span class="cx-t">Risk-weighted assets</span><span class="cx-chip">Mix</span></div>
 <div style="display:flex;align-items:center;gap:16px">{donut(parts)}<div class="cx-leg" style="flex:1;min-width:0">{leg}</div></div>
 <div class="cx-stats" style="margin-top:14px;padding-top:12px;border-top:1px solid {LINE}">
  <div><div class="cx-lbl">Total RWA</div><div class="v">{_l(r.total_rwa)} L</div></div>
  <div><div class="cx-lbl">Checks</div><div class="v">{passed}/{len(run.checks)}</div></div>
  <div><div class="cx-lbl">Benchmark</div><div class="v">{tie}</div></div></div></div>"""

    # ---- centre: hero + capital build
    hero = f"""
<div class="cx-card cx-hero">
 <div class="hd"><div class="ttl">Capital adequacy</div>
  <div class="chips"><span class="cx-chip">Capital held vs RBI requirement · ₹ lakhs</span></div></div>
 {capital_scene(r.tier1, r.tier2, req, req_t1)}
 <div class="cx-glass cx-comp">
  <div class="cx-h" style="margin-bottom:6px"><span class="cx-t">Compliance</span><span class="{'cx-ok' if ok else 'cx-warn'}">{'Compliant' if ok else 'Breach'}</span></div>
  <div class="rw"><span class="k">CRAR</span><span><span class="v">{r.crar:.2%}</span><span class="m">min {m['crar']:.0%}</span></span></div>
  <div class="rw"><span class="k">Tier 1 ratio</span><span><span class="v">{r.tier1_ratio:.2%}</span><span class="m">min {m['tier1']:.0%}</span></span></div>
  <div class="rw"><span class="k">Capital surplus</span><span class="v">{_l(r.tier1 + r.tier2 - req)} L</span></div>
 </div>
 <div class="cx-glass cx-legend"><span><i style="background:{P}"></i>Tier 1</span><span><i style="background:{P3}"></i>Tier 2</span>
  <span><i style="background:#fff;border:1.2px dashed #9C8BC0"></i>RBI requirement</span></div>
</div>"""
    steps = []
    for a in run.cap_applied:
        if a.applied in ("T1_INCLUDE", "T1_DEDUCT") and abs(a.cls.amount) > 0.005:
            amt = a.cls.amount if a.applied == "T1_INCLUDE" else -abs(a.cls.amount)
            steps.append((a.cls.label, amt, "x"))
    steps += [("Tier 1 capital", r.tier1, "total"), ("Tier 2 (capped)", r.tier2, "x"),
              ("Total capital", r.tier1 + r.tier2, "total")]
    build_card = f"""
<div class="cx-card"><div class="cx-h"><span class="cx-t">How capital is built</span>
 <span style="display:flex;gap:6px"><span class="cx-chip">Tier 1 → Total capital</span><span class="cx-chip">₹ lakhs</span></span></div>
 {waterfall(steps)}</div>"""

    # ---- right column
    t2_share = r.tier2 / r.tier1 if r.tier1 else 0
    score = f"""
<div class="cx-card cx-score"><div class="cx-h"><span class="cx-t">Ratios vs minimum</span>
 <span class="{'cx-ok' if ok else 'cx-warn'}">{'Within limits' if ok else 'Breach'}</span></div>
 <div class="rw"><span class="k">CRAR</span><span class="v">{r.crar:.2%}</span><span class="m">≥ {m['crar']:.0%}</span></div>
 <div class="rw"><span class="k">Tier 1 ratio</span><span class="v">{r.tier1_ratio:.2%}</span><span class="m">≥ {m['tier1']:.0%}</span></div>
 <div class="rw"><span class="k">Tier 2 / Tier 1</span><span class="v">{t2_share:.1%}</span><span class="m">≤ 100%</span></div></div>"""
    auto = sum(a.cls.route == "AUTO_ACCEPT" for a in run.cap_applied + run.rwa_applied)
    allc = len(run.cap_applied + run.rwa_applied)
    cap_rwa = (r.tier1 + r.tier2) / m["crar"]
    bars_ = [("RWA used vs capacity at minimum", r.total_rwa / cap_rwa, f"{r.total_rwa / cap_rwa:.0%}"),
             ("Provision recognised in Tier 2", r.tier2_gp_eligible / r.gp_gross if r.gp_gross else 0,
              f"{(r.tier2_gp_eligible / r.gp_gross if r.gp_gross else 0):.0%}"),
             ("Classifications auto-accepted", auto / allc if allc else 0, f"{auto}/{allc}"),
             ("Validation checks passed", passed / len(run.checks) if run.checks else 0, f"{passed}/{len(run.checks)}")]
    state = "".join(f'<div class="b"><div class="tp"><span>{escape(k_)}</span><span>{escape(v_)}</span></div>'
                    f'<div class="cx-track"><div class="cx-fill" style="width:{max(min(f, 1), 0) * 100:.1f}%"></div></div></div>'
                    for k_, f, v_ in bars_)
    imp = [e for e in open_ex if e.scenario_overrides][:5]
    mx = max((abs(e.impact_crar_bps) for e in imp), default=1) or 1
    irows = "".join(
        f'<div class="rw"><span class="nm" title="{escape(e.title)}">{escape(_compact(e.title))}</span>'
        f'<div class="cx-track"><div class="cx-fill" style="width:{abs(e.impact_crar_bps) / mx * 100:.0f}%;'
        f'background:{SEV.get(e.severity, FAINT)}"></div></div>'
        f'<span class="bp">{e.impact_crar_bps:+.0f}</span></div>' for e in imp)
    kb = rag_stats or {}
    right = f"""{score}
<div class="cx-card cx-bars"><div class="cx-h"><span class="cx-t">Capital state</span><span class="cx-chip">This run</span></div>{state}</div>
<div class="cx-card cx-imp"><div class="cx-h"><span class="cx-t">Judgement calls</span><span class="cx-chip">CRAR bps</span></div>
 {irows or '<div class="cx-lbl">None open.</div>'}
 <div class="cx-lbl" style="margin-top:8px">Change in CRAR if the alternative reading is accepted.</div></div>
<div class="cx-card"><div class="cx-h"><span class="cx-t">RBI knowledge base</span><span class="cx-ok">Offline</span></div>
 <div class="cx-kb"><div><div class="cx-lbl">Documents</div><div class="v">{kb.get('documents', 0)}</div></div>
  <div><div class="cx-lbl">Paragraphs</div><div class="v">{kb.get('chunks_current', 0):,}</div></div></div></div>"""

    return (CSS + f'<div class="cx"><div class="cx-grid">'
            f'<div class="cx-col cx-l">{left}</div>'
            f'<div class="cx-col cx-c">{hero}{build_card}</div>'
            f'<div class="cx-col cx-r">{right}</div></div></div>')
