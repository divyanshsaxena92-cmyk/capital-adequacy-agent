"""Overview v3 - clean fintech layout (top bar, hero balance, gradient 'cards', dual-line chart with a dark
tooltip, review table, segmented score), in Grant Thornton purple. Pure HTML/CSS/SVG: no JavaScript, no
external assets. Motion is CSS-only and switches off under the OS reduce-motion setting.
"""
from __future__ import annotations

from html import escape

from .overview_html import CAT, _short, _smooth

P, P2, P3, P4 = "#4F2D7F", "#7B4FC4", "#B9A8D9", "#F1ECF8"
INK, MUTED, FAINT, LINE = "#121016", "#6B6878", "#9D9AA8", "#EEECF2"
GREEN, AMBER, RED, TEAL = "#1F9D62", "#D48B12", "#D64560", "#169C8F"

CSS = f"""
<style>
@property --v {{ syntax: '<integer>'; initial-value: 0; inherits: false; }}
@counter-style pad3 {{ system: extends decimal; pad: 3 "0"; }}
@counter-style pad2 {{ system: extends decimal; pad: 2 "0"; }}
.fx {{ position: relative; container-type: inline-size; isolation: isolate; overflow: hidden; border-radius: 26px; padding: 14px;
      font-family: "Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
      color: {INK}; -webkit-font-smoothing: antialiased;
      background: linear-gradient(135deg, #F3EEFB 0%, #FBF8FE 38%, #FDF6F1 72%, #F7F1FB 100%); }}
.fx * {{ box-sizing: border-box; }}
.fx-card {{ background: #fff; border-radius: 20px; padding: 18px 20px; border: 1px solid rgba(18,16,22,.04);
           box-shadow: 0 1px 2px rgba(18,16,22,.03), 0 6px 22px rgba(60,30,110,.05); min-width: 0;
           transition: box-shadow .25s ease, transform .25s ease; animation: fxup .6s cubic-bezier(.2,.75,.2,1) both;
           animation-delay: var(--d, 0s); }}
.fx-card:hover {{ transform: translateY(-2px); box-shadow: 0 2px 4px rgba(18,16,22,.04), 0 16px 36px rgba(60,30,110,.10); }}
.fx-h {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; }}
.fx-t {{ font-size: 15px; font-weight: 600; letter-spacing: -.01em; }}
.fx-mut {{ font-size: 12.5px; color: {MUTED}; }}
.fx-pill {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; color: #34313D;
           background: #fff; border: 1px solid #E8E5EE; padding: 6px 12px; border-radius: 999px; white-space: nowrap; }}
.fx-dots {{ color: {FAINT}; font-size: 18px; letter-spacing: 1px; line-height: 1; }}

/* top bar */
.fx-top {{ display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap;
          background: rgba(255,255,255,.75); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
          border: 1px solid rgba(255,255,255,.9); border-radius: 18px; padding: 12px 16px 12px 20px; margin-bottom: 14px;
          animation: fxup .5s ease both; }}
.fx-top .eb {{ font-size: 10.5px; font-weight: 700; letter-spacing: .14em; color: {P}; }}
.fx-top .ti {{ font-size: 21px; font-weight: 600; letter-spacing: -.015em; margin-top: 1px; }}
.fx-top .rt {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
.fx-live {{ color: {GREEN}; background: #EAF7F0; border-color: #D4EFE1; font-weight: 600; }}
.fx-live i {{ width: 7px; height: 7px; border-radius: 50%; background: {GREEN}; display: inline-block; animation: fxpulse 2s infinite; }}
.fx-av {{ width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-size: 12px; font-weight: 700;
         background: linear-gradient(135deg, {P}, {P2}); box-shadow: 0 4px 12px rgba(79,45,127,.35); }}

/* grid */
.fx-row1 {{ display: grid; grid-template-columns: 330px minmax(0, 1fr); gap: 14px; }}
.fx-row2 {{ display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 14px; margin-top: 14px; }}
.fx-col {{ display: flex; flex-direction: column; gap: 14px; min-width: 0; }}
@container (max-width: 1000px) {{ .fx-row1, .fx-row2 {{ grid-template-columns: minmax(0, 1fr); }}
                                  .fx-col.l {{ display: grid; grid-template-columns: 1fr 1fr; }} }}
@container (max-width: 640px)  {{ .fx-col.l {{ grid-template-columns: minmax(0, 1fr); }} }}

/* hero balance */
.fx-bal {{ font-size: 36px; font-weight: 650; letter-spacing: -.03em; margin: 12px 0 8px; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.fx-bal .u {{ font-size: 15px; color: {MUTED}; font-weight: 500; margin-left: 4px; letter-spacing: 0; }}
.fx-up {{ display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; font-weight: 600; color: {GREEN};
         background: #EAF7F0; padding: 3px 8px; border-radius: 999px; }}
.fx-split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 16px; }}
.fx-blk {{ border-radius: 14px; padding: 11px 14px; min-width: 0; }}
.fx-blk .k {{ font-size: 11.5px; opacity: .8; }} .fx-blk .v {{ font-size: 15.5px; font-weight: 650; margin-top: 2px; white-space: nowrap; font-variant-numeric: tabular-nums; }}
.fx-blk.dark {{ background: linear-gradient(135deg, #2A1747, {P}); color: #fff; box-shadow: 0 8px 18px rgba(79,45,127,.30); }}
.fx-blk.light {{ background: #F5F2FA; border: 1px solid #ECE6F5; }}
.c-int {{ --v: var(--to); counter-reset: v var(--v); animation: fxcount 1.7s cubic-bezier(.2,.75,.2,1) both; }}
.c-int::after {{ content: counter(v); }} .c-p3::after {{ content: counter(v, pad3); }} .c-p2::after {{ content: counter(v, pad2); }}

/* capital 'cards' */
.fx-cards .it {{ display: grid; grid-template-columns: 50px minmax(0, 1fr) auto; gap: 12px; align-items: center;
                background: #FAF9FC; border: 1px solid #F0EDF5; border-radius: 14px; padding: 10px 12px; margin-top: 10px; }}
.fx-cc {{ width: 50px; height: 34px; border-radius: 7px; position: relative; overflow: hidden; box-shadow: 0 4px 10px rgba(40,20,80,.18); }}
.fx-cc::before {{ content: ""; position: absolute; left: 7px; top: 9px; width: 11px; height: 8px; border-radius: 2px; background: rgba(255,225,160,.9); }}
.fx-cc::after {{ content: ""; position: absolute; right: -10px; top: -14px; width: 40px; height: 40px; border-radius: 50%; background: rgba(255,255,255,.22); }}
.fx-cards .nm {{ font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.fx-cards .sb {{ font-size: 11.5px; color: {FAINT}; margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.fx-cards .am {{ font-size: 14px; font-weight: 650; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.fx-cards .am small {{ font-size: 11px; color: {FAINT}; font-weight: 500; }}
.fx-total {{ display: flex; justify-content: space-between; align-items: center; margin-top: 10px; padding: 11px 14px;
            border: 1.5px dashed #DDD5EA; border-radius: 14px; font-size: 13px; font-weight: 600; }}

/* main chart */
.fx-big {{ font-size: 32px; font-weight: 650; letter-spacing: -.03em; margin-top: 4px; font-variant-numeric: tabular-nums; }}
.fx-chart {{ position: relative; margin-top: 18px; padding-left: 34px; }}
.fx-plot {{ position: relative; height: 250px; }}
.fx-plot svg {{ position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }}
.fx-plot .yl {{ position: absolute; left: -34px; transform: translateY(-50%); font-size: 10.5px; color: {FAINT}; }}
.fx-plot .gl {{ position: absolute; left: 0; right: 0; border-top: 1px dashed {LINE}; }}
.fx-plot .lines {{ animation: fxreveal 1.8s cubic-bezier(.2,.75,.2,1) .25s both; }}
.fx-plot .bars rect {{ transform-box: fill-box; transform-origin: bottom; animation: fxgrowy .9s cubic-bezier(.2,.75,.2,1) both; }}
.fx-tip {{ position: absolute; transform: translate(14px, -50%); background: #17121F; color: #fff; border-radius: 14px; padding: 10px 12px;
          box-shadow: 0 14px 30px rgba(20,10,40,.35); min-width: 168px; animation: fxpop .5s cubic-bezier(.2,.75,.2,1) 1.6s both; z-index: 2; }}
.fx-tip .r {{ display: grid; grid-template-columns: 26px 1fr; gap: 8px; align-items: center; padding: 3px 0; }}
.fx-tip .ic {{ width: 26px; height: 26px; border-radius: 8px; background: rgba(255,255,255,.09); display: grid; place-items: center; font-size: 12px; }}
.fx-tip .k {{ font-size: 10.5px; color: #B7AECB; }} .fx-tip .v {{ font-size: 13px; font-weight: 650; font-variant-numeric: tabular-nums; }}
.fx-vline {{ position: absolute; top: 0; bottom: 0; border-left: 1.5px solid #17121F; opacity: .8; }}
.fx-dot {{ position: absolute; width: 11px; height: 11px; margin: -5.5px 0 0 -5.5px; border-radius: 50%; background: #fff; border: 2.5px solid; }}
.fx-xax {{ position: relative; height: 20px; margin-top: 8px; }}
.fx-xax span {{ position: absolute; transform: translateX(-50%); font-size: 11px; color: {FAINT}; white-space: nowrap; }}
.fx-xax span:first-child {{ transform: none; }} .fx-xax span:last-child {{ transform: translateX(-100%); }}
.fx-xcap {{ text-align: center; font-size: 11px; color: {FAINT}; margin-top: 2px; }}
.fx-leg {{ display: flex; justify-content: center; gap: 22px; flex-wrap: wrap; margin-top: 10px; font-size: 12.5px; }}
.fx-leg span {{ display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }}
.fx-leg i {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}

/* table */
.fx-tbl {{ width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 14px; }}
.fx-tbl th {{ font-size: 12px; font-weight: 500; color: {MUTED}; text-align: left; padding: 10px 12px; background: #F6F4F9; white-space: nowrap; }}
.fx-tbl th:first-child {{ border-radius: 12px 0 0 12px; }} .fx-tbl th:last-child {{ border-radius: 0 12px 12px 0; }}
.fx-tbl td {{ font-size: 12.5px; padding: 11px 12px; border-bottom: 1px solid {LINE}; white-space: nowrap; }}
.fx-tbl tr:last-child td {{ border-bottom: none; }}
.fx-tbl tbody tr {{ animation: fxup .5s ease both; animation-delay: var(--d); transition: background .2s; }}
.fx-tbl tbody tr:hover td {{ background: #FBFAFD; }}
.fx-tbl .itm {{ display: flex; align-items: center; gap: 10px; font-weight: 600; max-width: 260px; }}
.fx-tbl .itm span {{ overflow: hidden; text-overflow: ellipsis; }}
.fx-logo {{ width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center; font-size: 10.5px; font-weight: 700;
           color: #fff; flex: none; box-shadow: 0 3px 8px rgba(40,20,80,.15); }}
.fx-st {{ display: inline-flex; align-items: center; gap: 6px; }} .fx-st i {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block; }}
.fx-num {{ font-variant-numeric: tabular-nums; font-weight: 600; }}
.fx-tw {{ overflow-x: auto; }}

/* score */
.fx-score {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; background: #F6F9F7; border: 1px solid #E5F1EA;
            border-radius: 14px; padding: 12px 14px; margin-top: 14px; }}
.fx-score .lb {{ font-size: 13px; font-weight: 600; white-space: nowrap; }}
.fx-seg {{ display: flex; gap: 2px; flex: 1; min-width: 0; }}
.fx-seg i {{ flex: 1 1 0; min-width: 2px; max-width: 6px; height: 20px; border-radius: 2px; animation: fxseg .35s ease both;
            animation-delay: var(--d); transform-origin: bottom; }}
.fx-score .n {{ font-size: 18px; font-weight: 650; white-space: nowrap; font-variant-numeric: tabular-nums; }}
.fx-score .n small {{ font-size: 12px; color: {FAINT}; font-weight: 500; }}
.fx-inv .r {{ display: grid; grid-template-columns: auto auto minmax(0, 1fr) auto; gap: 4px 10px; align-items: center;
             padding: 10px 0; border-bottom: 1px solid {LINE}; animation: fxup .5s ease both; animation-delay: var(--d); }}
.fx-inv .r .ds {{ grid-column: 1 / -1; white-space: normal; line-height: 1.35; color: {MUTED}; }}
.fx-inv .r:last-child {{ border-bottom: none; }}
.fx-inv .id {{ font-size: 12.5px; font-weight: 600; }} .fx-inv .ar {{ font-size: 11px; color: {FAINT}; }}
.fx-tag {{ display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 999px; border: 1px solid; white-space: nowrap; }}
.fx-tag i {{ width: 6px; height: 6px; border-radius: 50%; }}
.fx-inv .ds {{ font-size: 12px; color: #3B3845; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.fx-inv .vl {{ font-size: 12.5px; font-weight: 600; text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}

@keyframes fxup {{ from {{ opacity: 0; transform: translateY(12px); }} }}
@keyframes fxcount {{ from {{ --v: 0; }} }}
@keyframes fxreveal {{ from {{ clip-path: inset(0 100% 0 0); }} to {{ clip-path: inset(0 0 0 0); }} }}
@keyframes fxgrowy {{ from {{ transform: scaleY(0); }} }}
@keyframes fxpop {{ from {{ opacity: 0; transform: translate(4px, -50%) scale(.92); }} }}
@keyframes fxseg {{ from {{ opacity: 0; transform: scaleY(.2); }} }}
@keyframes fxpulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(31,157,98,.6); }} 70% {{ box-shadow: 0 0 0 7px rgba(31,157,98,0); }} 100% {{ box-shadow: 0 0 0 0 rgba(31,157,98,0); }} }}
@media (prefers-reduced-motion: reduce) {{ .fx *, .fx *::before, .fx *::after {{ animation: none !important; transition: none !important; }} }}
</style>
"""


def _count(value: float, dp: int = 2) -> str:
    """Animated number with thousands separators: each group counts up on its own (CSS counters)."""
    neg = value < 0
    whole = int(abs(round(value, dp)))
    frac = round((abs(value) - whole) * 10 ** dp) if dp else 0
    if frac >= 10 ** dp:
        whole, frac = whole + 1, 0
    groups = f"{whole:,}".split(",")
    out = "-" if neg else ""
    for i, g in enumerate(groups):
        cls = "c-int" if i == 0 else "c-int c-p3"
        out += ("," if i else "") + f'<span class="{cls}" style="--to:{int(g)}"></span>'
    if dp:
        out += f'.<span class="c-int c-p2" style="--to:{frac}"></span>'
    return out


def _lk(v: float, dp: int = 2) -> str:
    return f"₹{v:,.{dp}f}"


def ratio_chart(run) -> str:
    """CRAR and Tier 1 ratio as the loan risk weight moves 0%-150%; faint bars = RWA; dark tooltip at today."""
    loans = next(a for a in run.rwa_applied if a.cls.label == "Loans")
    xs = list(range(50, 155, 5))
    res = [run._compute({"rwa": {loans.cls.item_id: x / 100}}) for x in xs]
    crar = [r.crar * 100 for r in res]
    t1 = [r.tier1_ratio * 100 for r in res]
    rwa = [r.total_rwa for r in res]
    m = run.minimums["crar"] * 100
    step = 10
    top = (int(max(crar) // step) + 1) * step
    lo = 0.0
    px = lambda x: (x - 50) / 100 * 100
    py = lambda y: (top - min(y, top)) / (top - lo) * 100
    c_path = _smooth([(px(x), py(y)) for x, y in zip(xs, crar)])
    t_path = _smooth([(px(x), py(y)) for x, y in zip(xs, t1)])
    rmax = max(rwa)
    bars = "".join(f'<rect x="{px(x) - .5:.2f}" y="{100 - v / rmax * 62:.2f}" width="1" height="{v / rmax * 62:.2f}" '
                   f'fill="{P}" opacity=".07" style="animation-delay:{i * 25}ms"/>' for i, (x, v) in enumerate(zip(xs, rwa)))
    ticks = list(range(0, int(top) + 1, step))
    grid = "".join(f'<span class="gl" style="top:{py(t):.2f}%"></span><span class="yl" style="top:{py(t):.2f}%">{t}%</span>'
                   for t in ticks)
    cur = loans.applied * 100
    cx = px(cur)
    cy_c, cy_t = py(run.final.crar * 100), py(run.final.tier1_ratio * 100)
    flip = cx > 70                                   # keep the tooltip inside the card
    tip_style = (f"left:{cx:.2f}%;top:{min(cy_c, cy_t) - 2:.2f}%" + (";transform:translate(calc(-100% - 14px),-50%)" if flip else ""))
    xl = "".join(f'<span style="left:{px(x):.2f}%">{x}%</span>' for x in (50, 75, 100, 125, 150))
    return f"""<div class="fx-chart"><div class="fx-plot">{grid}
<svg viewBox="0 0 100 100" preserveAspectRatio="none"><g class="bars">{bars}</g><g class="lines">
<line x1="0" x2="100" y1="{py(m):.2f}" y2="{py(m):.2f}" stroke="{RED}" stroke-width="1.2" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>
<path d="{t_path}" fill="none" stroke="{TEAL}" stroke-width="2.2" vector-effect="non-scaling-stroke"/>
<path d="{c_path}" fill="none" stroke="{P}" stroke-width="2.6" vector-effect="non-scaling-stroke"/></g></svg>
<span class="fx-vline" style="left:{cx:.2f}%"></span>
<span class="fx-dot" style="left:{cx:.2f}%;top:{cy_c:.2f}%;border-color:{P}"></span>
<span class="fx-dot" style="left:{cx:.2f}%;top:{cy_t:.2f}%;border-color:{TEAL}"></span>
<div class="fx-tip" style="{tip_style}">
 <div class="r"><span class="ic" style="color:#CDB8FF">◆</span><div><div class="k">CRAR at {cur:.0f}% loan weight</div><div class="v">{run.final.crar:.2%}</div></div></div>
 <div class="r"><span class="ic" style="color:#7FE3C6">●</span><div><div class="k">Tier 1 ratio</div><div class="v">{run.final.tier1_ratio:.2%}</div></div></div>
</div></div><div class="fx-xax">{xl}</div><div class="fx-xcap">Risk weight applied to the loan book</div>
<div class="fx-leg"><span><i style="background:{P}"></i>CRAR <b>{run.final.crar:.2%}</b></span>
<span><i style="background:{TEAL}"></i>Tier 1 ratio <b>{run.final.tier1_ratio:.2%}</b></span>
<span><i style="background:{RED}"></i>RBI minimum {m:.0f}%</span>
<span><i style="background:{P};opacity:.25;border-radius:2px"></i>RWA (bars)</span></div></div>"""


LOGO = {"Regulatory interpretation": ("#4F2D7F", "#7B4FC4"), "Data completeness": ("#B5651D", "#E09A3E"),
        "Data quality": ("#B5651D", "#E09A3E"), "Completeness": ("#1D6FA5", "#4FA3D9"),
        "Classification": ("#6B3FB8", "#A276E8"), "Governance": ("#2B2F3A", "#596173"), "Evidence": ("#127F73", "#3CB5A6")}
STATUS = {"OPEN": ("Open", AMBER), "RESOLVED - ALTERNATIVE APPLIED": ("Resolved", GREEN),
          "RESOLVED - BASELINE RETAINED": ("Resolved", GREEN), "RESOLVED - NOTED": ("Noted", GREEN)}
SEVC = {"Critical": "#8E1B3A", "High": RED, "Medium": AMBER, "Low": FAINT}


def _initials(name: str) -> str:
    w = [x for x in name.replace("(", " ").replace("-", " ").split() if x[:1].isalpha()]
    return (w[0][0] + (w[1][0] if len(w) > 1 else w[0][1:2])).upper() if w else "•"


def build(run, rag_stats: dict | None = None) -> str:
    r, m = run.final, run.minimums
    total = r.tier1 + r.tier2
    req = m["crar"] * r.total_rwa
    ok = r.crar >= m["crar"] and r.tier1_ratio >= m["tier1"]
    date = f"{run.ds.reporting_date:%d %b %Y}"
    layer = "Middle Layer" if run.layer == "ML" else "Upper Layer"
    open_ex = [e for e in run.exceptions if e.status == "OPEN"]
    ded = sum(abs(a.cls.amount) for a in run.cap_applied if a.applied == "T1_DEDUCT")

    top = f"""<div class="fx-top"><div><div class="eb">GRANT THORNTON · CAPITAL ADEQUACY AGENT</div><div class="ti">Overview</div></div>
<div class="rt"><span class="fx-pill">📅 As at {escape(date)}</span><span class="fx-pill">{escape(run.entity_type)} · {escape(layer)}</span>
<span class="fx-pill fx-live"><i></i>Offline · verified</span><span class="fx-av" title="Grant Thornton">GT</span></div></div>"""

    balance = f"""<div class="fx-card" style="--d:.05s"><div class="fx-h"><span class="fx-mut">Total regulatory capital</span>
<span class="fx-pill" style="padding:4px 10px">₹ Lakhs</span></div>
<div class="fx-bal">₹{_count(total)}<span class="u">L</span></div>
<span class="fx-up" style="{'' if ok else f'color:{RED};background:#FDECEF'}">{'✓ Compliant' if ok else '⚠ Breach'} · {(r.crar - m['crar']) * 100:+.2f} pp</span> <span class="fx-mut" style="font-size:12px;white-space:nowrap">vs {m['crar']:.0%} floor</span>
<div class="fx-split"><div class="fx-blk dark"><div class="k">Tier 1</div><div class="v">{_lk(r.tier1, 0)} L</div></div>
<div class="fx-blk light"><div class="k">Tier 2</div><div class="v">{_lk(r.tier2, 0)} L</div></div></div></div>"""

    cards = f"""<div class="fx-card fx-cards" style="--d:.12s"><div class="fx-h"><span class="fx-t">Capital components</span><span class="fx-pill" style="padding:3px 9px;font-size:11px">₹ L</span></div>
<div class="it"><span class="fx-cc" style="background:linear-gradient(135deg,#2A1747,#4F2D7F 55%,#7B4FC4)"></span>
 <div style="min-width:0"><div class="nm">Tier 1 capital</div><div class="sb">Equity & reserves</div></div><div class="am">{_lk(r.tier1, 0)}<small> L</small></div></div>
<div class="it"><span class="fx-cc" style="background:linear-gradient(135deg,#8E6CD0,#C9B6EC)"></span>
 <div style="min-width:0"><div class="nm">Tier 2 capital</div><div class="sb">Provisions, capped</div></div><div class="am">{_lk(r.tier2, 0)}<small> L</small></div></div>
<div class="it"><span class="fx-cc" style="background:linear-gradient(135deg,#C2405E,#F08AA0)"></span>
 <div style="min-width:0"><div class="nm">Deductions</div><div class="sb">DTA & prepaid</div></div><div class="am" style="color:{RED}">−{_lk(ded, 0)}<small> L</small></div></div>
<div class="fx-total"><span>Capital surplus</span><span style="color:{GREEN};white-space:nowrap">{_lk(total - req, 0)} L</span></div></div>"""

    chart = f"""<div class="fx-card" style="--d:.18s"><div class="fx-h"><span class="fx-t">Capital Ratio Overview <span style="color:{FAINT};font-weight:500">ⓘ</span></span>
<span class="fx-pill">Loan risk weight 50–150%</span></div>
<div class="fx-mut" style="margin-top:14px">CRAR at today's risk weights</div>
<div class="fx-big"><span class="c-int" style="--to:{int(r.crar * 100)}"></span>.<span class="c-int c-p2" style="--to:{round(r.crar * 10000) % 100}"></span>%</div>
<div class="fx-mut">vs <span style="color:{RED};font-weight:600">{m['crar']:.2%}</span> RBI minimum · Tier 1 ratio <b style="color:{INK}">{r.tier1_ratio:.2%}</b> vs {m['tier1']:.0%}</div>
{ratio_chart(run)}</div>"""

    rows = []
    for i, e in enumerate(open_ex[:6]):
        nm = _short(e.title, 34)
        g1, g2 = LOGO.get(e.category, (P, P2))
        st_txt, st_col = STATUS.get(e.status, ("Open", AMBER))
        imp = f"{e.impact_crar_bps:+.0f} bps" if e.scenario_overrides else "—"
        imp_col = GREEN if e.scenario_overrides and e.impact_crar_bps > 0 else (RED if e.scenario_overrides and e.impact_crar_bps < 0 else FAINT)
        rows.append(f'<tr style="--d:{.35 + i * .07:.2f}s"><td><div class="itm"><span class="fx-logo" style="background:linear-gradient(135deg,{g1},{g2})">'
                    f'{escape(_initials(nm))}</span><span title="{escape(e.title)}">{escape(nm)}</span></div></td>'
                    f'<td>{escape(CAT.get(e.category, e.category))}</td>'
                    f'<td><span class="fx-st"><i style="background:{SEVC.get(e.severity, FAINT)}"></i>{escape(e.severity)}</span></td>'
                    f'<td class="fx-num" style="color:{imp_col}">{imp}</td>'
                    f'<td><span class="fx-st"><i style="background:{st_col}"></i>{st_txt}</span></td></tr>')
    table = f"""<div class="fx-card" style="--d:.26s"><div class="fx-h"><span class="fx-t">Review Queue</span>
<span class="fx-mut" style="font-weight:500">{len(open_ex)} open · highest priority first</span></div>
<div class="fx-tw"><table class="fx-tbl"><thead><tr><th>Item</th><th>Category</th><th>Priority</th><th>CRAR impact</th><th>Status</th></tr></thead>
<tbody>{''.join(rows) or '<tr><td colspan="5">Nothing open — ready for checker sign-off.</td></tr>'}</tbody></table></div></div>"""

    checks = run.checks + run.control_checks
    n = len(run.checks)
    passed = sum(c.status == "PASS" for c in run.checks)
    segs = "".join(f'<i style="background:{GREEN if c.status == "PASS" else (AMBER if c.status == "WARN" else RED)};'
                   f'--d:{.4 + i * .025:.3f}s" title="{escape(c.check_id)}: {escape(c.status)}"></i>'
                   for i, c in enumerate(sorted(run.checks, key=lambda c: c.status != "PASS")))
    ordered = [c for c in checks if c.status != "PASS"] + [c for c in checks if c.status == "PASS"]
    tag = {"PASS": ("Pass", GREEN, "#EAF7F0", "#D4EFE1"), "FAIL": ("Fail", RED, "#FDECEF", "#F8D3DB"),
           "WARN": ("Warn", AMBER, "#FDF3E2", "#F7E1BA")}
    inv = []
    for i, c in enumerate(ordered[:5]):
        t, col, bg, bd = tag.get(c.status, tag["WARN"])
        val = (f"{c.actual - c.expected:+,.2f}" if isinstance(c.expected, (int, float)) and isinstance(c.actual, (int, float))
               and c.status != "PASS" else ("✓" if c.status == "PASS" else "—"))
        inv.append(f'<div class="r" style="--d:{.5 + i * .07:.2f}s"><span class="id">{escape(c.check_id.split("-")[0])}</span>'
                   f'<span class="fx-tag" style="color:{col};background:{bg};border-color:{bd}"><i style="background:{col}"></i>{t}</span>'
                   f'<span class="ar">{escape(c.area)}</span><span class="vl">{escape(val)}</span>'
                   f'<span class="ds">{escape(c.description)}</span></div>')
    quality = f"""<div class="fx-card" style="--d:.32s"><div class="fx-h"><span class="fx-t">Data Quality</span><span class="fx-mut" style="font-weight:500">failures first</span></div>
<div class="fx-score"><span class="lb">Validation</span><div class="fx-seg">{segs}</div><span class="n">{passed}<small>/{n}</small></span></div>
<div class="fx-inv" style="margin-top:6px">{''.join(inv)}</div></div>"""

    return (CSS + f'<div class="fx">{top}<div class="fx-row1"><div class="fx-col l">{balance}{cards}</div>{chart}</div>'
            f'<div class="fx-row2">{table}{quality}</div></div>')
