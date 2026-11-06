"""Overview v2 - a richer, animated dashboard (pure HTML/CSS/SVG, no JavaScript, works offline).

Motion is CSS-only: count-up numbers (@property counters), rings and bars that fill on load, a donut that
draws itself, a sweeping sensitivity line, a gently floating 3D capital column and an activity timeline that
plays the run. Everything switches off under the OS "reduce motion" setting.
"""
from __future__ import annotations

import math
from html import escape

from .overview_html import CAT, CSS as BASE_CSS, _compact, _l, _short, capital_scene, donut, sensitivity_chart, waterfall

P, P_DEEP, P_VIOLET, P_SOFT = "#4F2D7F", "#2B1747", "#7B4FC4", "#B9A8D9"
INK, MUTED, FAINT, LINE = "#16131D", "#6B6878", "#9A97A6", "#ECEAF1"
GREEN, AMBER, RED = "#2E8B5E", "#C7861A", "#C23B57"
SEV = {"Critical": "#8E1B3A", "High": "#E0567A", "Medium": "#F0A93B", "Low": "#A9A6B3"}

ICONS = {
    "shield": '<path d="M12 3l7 3v5c0 4.4-3 8.3-7 9.5C8 19.3 5 15.4 5 11V6l7-3z" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 11.5l2.2 2.2L15.5 9.5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "layers": '<path d="M12 4l8 4-8 4-8-4 8-4z" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M4 12l8 4 8-4M4 16l8 4 8-4" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
    "scale": '<path d="M12 4v16M6 20h12M5 8h14" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/><path d="M5 8l-2.5 6h5L5 8zM19 8l-2.5 6h5L19 8z" fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/>',
    "flag": '<path d="M6 21V4M6 4h10l-1.5 3.5L16 11H6" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
}

CSS = BASE_CSS + f"""
<style>
@property --v {{ syntax: '<integer>'; initial-value: 0; inherits: false; }}
.cv {{ position: relative; container-type: inline-size; overflow: hidden; border-radius: 28px; padding: 18px;
      background: #F2F1F6; font-family: "Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
      color: {INK}; -webkit-font-smoothing: antialiased; isolation: isolate; }}
.cv * {{ box-sizing: border-box; }}
.cv::before, .cv::after {{ content: ""; position: absolute; z-index: -1; border-radius: 50%; filter: blur(70px); opacity: .55; }}
.cv::before {{ width: 520px; height: 520px; left: -160px; top: 240px; background: #D9CCF2; }}
.cv::after {{ width: 560px; height: 560px; right: -200px; bottom: -120px; background: #E7DDF7; }}
.cv-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
.cv-span2 {{ grid-column: span 2; }} .cv-full {{ grid-column: 1 / -1; }}
@container (max-width: 1050px) {{ .cv-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
                                   .cv-span2 {{ grid-column: 1 / -1; }} }}
@container (max-width: 680px)  {{ .cv-grid {{ grid-template-columns: minmax(0, 1fr); }} }}

/* cards */
.cv-card {{ background: rgba(255,255,255,.86); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
           border: 1px solid rgba(255,255,255,.9); border-radius: 22px; padding: 18px 20px;
           box-shadow: 0 1px 2px rgba(32,20,60,.04), 0 10px 30px rgba(32,20,60,.07);
           transition: transform .25s ease, box-shadow .25s ease; min-width: 0; }}
.cv-card:hover, .cv-tile:hover {{ transform: translateY(-3px); box-shadow: 0 2px 4px rgba(32,20,60,.05), 0 18px 40px rgba(32,20,60,.12); }}
.cv-h {{ display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px; }}
.cv-t {{ font-size: 14px; font-weight: 600; letter-spacing: -.005em; }}
.cv-sub {{ font-size: 11.5px; color: {MUTED}; margin-top: 2px; }}
.cv-chip {{ font-size: 11px; font-weight: 500; color: #3F3C4A; background: #F3F1F8; border: 1px solid #E9E5F2;
           padding: 3px 10px; border-radius: 999px; white-space: nowrap; }}

/* hero */
.cv-hero {{ position: relative; overflow: hidden; border-radius: 26px; padding: 28px 30px; color: #fff; min-height: 262px;
           background: linear-gradient(125deg, {P_DEEP} 0%, {P} 48%, {P_VIOLET} 100%);
           box-shadow: 0 20px 50px rgba(60,30,110,.28); display: grid; gap: 28px; align-items: center;
           grid-template-columns: minmax(0, 1.25fr) auto minmax(0, 1fr); }}
@container (max-width: 1050px) {{ .cv-hero {{ grid-template-columns: minmax(0, 1fr) auto; }} .cv-hero-r {{ grid-column: 1 / -1; }} }}
@container (max-width: 680px)  {{ .cv-hero {{ grid-template-columns: minmax(0, 1fr); }} }}
.cv-hero .orb {{ position: absolute; border-radius: 50%; filter: blur(40px); pointer-events: none; }}
.cv-hero .o1 {{ width: 340px; height: 340px; right: 18%; top: -150px; background: rgba(176,140,255,.45); animation: drift 9s ease-in-out infinite alternate; }}
.cv-hero .o2 {{ width: 260px; height: 260px; left: -60px; bottom: -140px; background: rgba(255,255,255,.18); animation: drift 11s ease-in-out infinite alternate-reverse; }}
.cv-hero .mesh {{ position: absolute; inset: 0; opacity: .14; pointer-events: none;
                 background-image: linear-gradient(rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.5) 1px, transparent 1px);
                 background-size: 34px 34px; mask-image: radial-gradient(70% 90% at 75% 40%, #000 0%, transparent 70%);
                 -webkit-mask-image: radial-gradient(70% 90% at 75% 40%, #000 0%, transparent 70%); }}
.cv-hero > div {{ position: relative; z-index: 1; min-width: 0; }}
.cv-eyebrow {{ display: inline-flex; align-items: center; gap: 8px; font-size: 11.5px; font-weight: 600; letter-spacing: .02em;
              background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.22); padding: 5px 11px; border-radius: 999px; }}
.cv-pulse {{ width: 8px; height: 8px; border-radius: 50%; background: #7CF0B5; box-shadow: 0 0 0 0 rgba(124,240,181,.7);
            animation: pulse 2s infinite; }}
.cv-hero .h1 {{ font-size: 15px; font-weight: 600; margin-top: 16px; color: #E8DFFA; }}
.cv-huge {{ font-size: 64px; font-weight: 650; letter-spacing: -.035em; line-height: 1; margin-top: 6px;
           font-variant-numeric: tabular-nums; text-shadow: 0 8px 30px rgba(0,0,0,.18); white-space: nowrap; }}
.cv-huge .pct {{ font-size: 30px; font-weight: 500; margin-left: 4px; color: #E0D3F7; }}
.cnt, .cnt2 {{ --v: var(--to); counter-reset: v var(--v); animation: count 1.8s cubic-bezier(.2,.75,.2,1) both; }}
.cnt::after {{ content: counter(v); }} .cnt2::after {{ content: counter(v, decimal-leading-zero); }}
.cv-hero .desc {{ font-size: 13px; color: #DCD0F2; margin-top: 10px; }}
.cv-badges {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }}
.cv-gb {{ font-size: 11.5px; font-weight: 600; padding: 5px 11px; border-radius: 999px; white-space: nowrap;
         background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.25); }}
.cv-gb.ok {{ background: rgba(124,240,181,.18); border-color: rgba(124,240,181,.45); color: #C9FFE3; }}
.cv-gauge {{ width: 210px; height: 210px; position: relative; }}
.cv-gauge svg {{ width: 100%; height: 100%; transform: rotate(-90deg); overflow: visible; }}
.cv-gauge .ring {{ animation: ringin 1.9s cubic-bezier(.2,.75,.2,1) both; }}
.cv-gauge .ring.r2 {{ animation-delay: .25s; }}
.cv-gauge .ctr {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
.cv-gauge .ctr {{ gap: 5px; }}
.cv-gauge .ky {{ display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600; color: #EDE6FA; width: 74px; }}
.cv-gauge .ky i {{ width: 9px; height: 9px; border-radius: 3px; display: inline-block; flex: none; }}
.cv-hero-r {{ display: grid; gap: 10px; }}
.cv-glass {{ background: rgba(255,255,255,.11); border: 1px solid rgba(255,255,255,.22); border-radius: 16px; padding: 12px 14px;
            backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
.cv-glass .k {{ font-size: 11.5px; color: #DCD0F2; }} .cv-glass .v {{ font-size: 18px; font-weight: 650; font-variant-numeric: tabular-nums; white-space: nowrap; }}
.cv-glass .m {{ font-size: 11px; color: #CBBDE8; text-align: right; white-space: nowrap; }}

/* KPI tiles */
.cv-tiles {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }}
@container (max-width: 1050px) {{ .cv-tiles {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@container (max-width: 520px)  {{ .cv-tiles {{ grid-template-columns: minmax(0, 1fr); }} }}
.cv-tile {{ position: relative; overflow: hidden; background: #fff; border-radius: 22px; padding: 18px 20px 16px; min-width: 0;
           border: 1px solid rgba(255,255,255,.9); box-shadow: 0 1px 2px rgba(32,20,60,.04), 0 10px 30px rgba(32,20,60,.07);
           transition: transform .25s ease, box-shadow .25s ease; }}
.cv-tile::after {{ content: ""; position: absolute; right: -40px; top: -40px; width: 140px; height: 140px; border-radius: 50%;
                  background: var(--glow); opacity: .14; filter: blur(4px); }}
.cv-tile .top {{ display: flex; align-items: center; justify-content: space-between; }}
.cv-ico {{ width: 40px; height: 40px; border-radius: 13px; display: grid; place-items: center; box-shadow: 0 8px 18px var(--shadow); }}
.cv-ico svg {{ width: 22px; height: 22px; }}
.cv-trend {{ font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; white-space: nowrap; }}
.cv-tile .lbl {{ font-size: 12.5px; color: {MUTED}; margin-top: 16px; }}
.cv-tile .val {{ font-size: 27px; font-weight: 650; letter-spacing: -.025em; margin-top: 4px; font-variant-numeric: tabular-nums;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cv-tile .val small {{ font-size: 14px; font-weight: 500; color: {MUTED}; margin-left: 2px; }}
.cv-meter {{ height: 6px; border-radius: 999px; background: #F0EDF6; margin-top: 14px; overflow: hidden; }}
.cv-meter i {{ display: block; height: 100%; width: var(--w); border-radius: 999px; background: var(--grad);
              transform-origin: left; animation: growx 1.4s cubic-bezier(.2,.75,.2,1) both; animation-delay: var(--d, 0s); }}
.cv-tile .foot {{ font-size: 11.5px; color: {FAINT}; margin-top: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

/* dark feature tile */
.cv-dark {{ position: relative; overflow: hidden; background: radial-gradient(120% 100% at 100% 0%, #3A2363 0%, #1B1428 55%, #140F1E 100%);
           color: #fff; border-radius: 22px; padding: 20px 22px; box-shadow: 0 16px 40px rgba(20,10,40,.28);
           transition: transform .25s ease; }}
.cv-dark:hover {{ transform: translateY(-3px); }}
.cv-dark .cv-t {{ color: #fff; }} .cv-dark .cv-sub {{ color: #B9AED0; }}
.cv-dark .big {{ font-size: 40px; font-weight: 650; letter-spacing: -.03em; margin: 10px 0 2px; font-variant-numeric: tabular-nums; }}
.cv-dark .big small {{ font-size: 15px; color: #B9AED0; font-weight: 500; margin-left: 4px; }}
.cv-dark .rw {{ display: grid; grid-template-columns: minmax(0, 1fr) 46px; gap: 6px 12px; align-items: center; margin-top: 12px; }}
.cv-dark .nm {{ font-size: 12px; color: #DCD3EC; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cv-dark .bp {{ font-size: 12px; font-weight: 650; text-align: right; font-variant-numeric: tabular-nums; }}
.cv-dark .tr {{ grid-column: 1 / -1; height: 6px; border-radius: 999px; background: rgba(255,255,255,.08); overflow: hidden; }}
.cv-dark .tr i {{ display: block; height: 100%; width: var(--w); border-radius: 999px; background: var(--c);
                 box-shadow: 0 0 12px var(--c); transform-origin: left; animation: growx 1.3s cubic-bezier(.2,.75,.2,1) both;
                 animation-delay: var(--d, 0s); }}

/* timeline */
.cv-tl {{ position: relative; padding-left: 22px; }}
.cv-tl::before {{ content: ""; position: absolute; left: 7px; top: 6px; bottom: 6px; width: 2px; background: #ECE7F5; border-radius: 2px; }}
.cv-tl .ev {{ position: relative; padding: 0 0 13px; animation: fadeup .6s ease both; animation-delay: var(--d); }}
.cv-tl .ev::before {{ content: ""; position: absolute; left: -20px; top: 4px; width: 10px; height: 10px; border-radius: 50%;
                     background: #fff; border: 2px solid {P}; box-sizing: border-box; }}
.cv-tl .ev.now::before {{ background: {AMBER}; border-color: {AMBER}; animation: pulse-amber 2s infinite; }}
.cv-tl .a {{ font-size: 12.5px; font-weight: 600; }}
.cv-tl .b {{ font-size: 11.5px; color: {MUTED}; margin-top: 1px; }}

/* motion */
.cv-in {{ animation: fadeup .7s cubic-bezier(.2,.75,.2,1) both; animation-delay: var(--d, 0s); }}
.cv .cx-wf .bar {{ transform-origin: bottom; animation: growy 1s cubic-bezier(.2,.75,.2,1) both; }}
.cv .cx-sens .curve {{ animation: reveal 1.6s cubic-bezier(.2,.75,.2,1) .3s both; }}
.cv svg .seg {{ animation: draw 1.2s cubic-bezier(.2,.75,.2,1) both; }}
.cv .cv-float {{ animation: float 5.5s ease-in-out infinite; }}
.cv .cv-shadow {{ animation: shadowpulse 5.5s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }}
@keyframes count {{ from {{ --v: 0; }} }}
@keyframes ringin {{ from {{ stroke-dashoffset: var(--c); }} }}
@keyframes growx {{ from {{ transform: scaleX(0); }} }}
@keyframes growy {{ from {{ transform: scaleY(0); }} }}
@keyframes fadeup {{ from {{ opacity: 0; transform: translateY(10px); }} }}
@keyframes reveal {{ from {{ clip-path: inset(0 100% 0 0); }} to {{ clip-path: inset(0 0 0 0); }} }}
@keyframes draw {{ from {{ stroke-dasharray: 0 999; }} }}
@keyframes float {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-7px); }} }}
@keyframes shadowpulse {{ 0%, 100% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(.92); opacity: .75; }} }}
@keyframes drift {{ from {{ transform: translate(0, 0); }} to {{ transform: translate(40px, 30px); }} }}
@keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(124,240,181,.7); }} 70% {{ box-shadow: 0 0 0 9px rgba(124,240,181,0); }}
                   100% {{ box-shadow: 0 0 0 0 rgba(124,240,181,0); }} }}
@keyframes pulse-amber {{ 0% {{ box-shadow: 0 0 0 0 rgba(199,134,26,.6); }} 70% {{ box-shadow: 0 0 0 8px rgba(199,134,26,0); }}
                         100% {{ box-shadow: 0 0 0 0 rgba(199,134,26,0); }} }}
@media (prefers-reduced-motion: reduce) {{ .cv *, .cv *::before, .cv *::after {{ animation: none !important; transition: none !important; }} }}
</style>
"""


def _num(v: float) -> str:
    return f"{v:,.0f}"


def _gauge(crar: float, t1r: float, min_crar: float, min_t1: float) -> str:
    top = max(40.0, math.ceil(max(crar, t1r) * 100 / 10) * 10 + 10)
    rings = []
    for i, (val, mn, r, w, grad) in enumerate(((crar, min_crar, 88, 14, "g1"), (t1r, min_t1, 64, 10, "g2"))):
        c = 2 * math.pi * r
        off = c * (1 - min(val * 100 / top, 1))
        mang = mn * 100 / top * 2 * math.pi
        mx, my = 105 + r * math.cos(mang), 105 + r * math.sin(mang)
        rings.append(f'<circle cx="105" cy="105" r="{r}" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="{w}"/>'
                     f'<circle class="ring{" r2" if i else ""}" cx="105" cy="105" r="{r}" fill="none" stroke="url(#{grad})" '
                     f'stroke-width="{w}" stroke-linecap="round" stroke-dasharray="{c:.2f}" '
                     f'style="--c:{c:.2f};stroke-dashoffset:{off:.2f}"/>'
                     f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{w / 2 + 2.5:.1f}" fill="#FFD27A" stroke="#2B1747" stroke-width="2">'
                     f'<title>RBI minimum {mn:.0%}</title></circle>')
    return (f'<div class="cv-gauge"><svg viewBox="0 0 210 210"><defs>'
            f'<linearGradient id="g1" x1="0" x2="1" y1="0" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#C8B2FF"/></linearGradient>'
            f'<linearGradient id="g2" x1="0" x2="1" y1="1" y2="0"><stop offset="0" stop-color="#9EF2C8"/><stop offset="1" stop-color="#5FD6A0"/></linearGradient>'
            f'</defs>{"".join(rings)}</svg><div class="ctr"><span class="ky"><i style="background:#E7DCFF"></i>CRAR</span>'
            f'<span class="ky"><i style="background:#7FE3B4"></i>Tier 1</span>'
            f'<span class="ky"><i style="background:#FFD27A;border-radius:50%"></i>Minimum</span></div></div>')


def _tile(icon, g1, g2, label, value, unit, meter, foot, trend, trend_bg, trend_fg, delay, count=None):
    val = (f'<span class="cnt" style="--to:{count}"></span>' if count is not None else escape(value))
    return (f'<div class="cv-tile cv-in" style="--d:{delay}s;--glow:{g1}">'
            f'<div class="top"><span class="cv-ico" style="background:linear-gradient(135deg,{g1},{g2});--shadow:{g1}55">'
            f'<svg viewBox="0 0 24 24">{ICONS[icon]}</svg></span>'
            f'<span class="cv-trend" style="background:{trend_bg};color:{trend_fg}">{escape(trend)}</span></div>'
            f'<div class="lbl">{escape(label)}</div><div class="val">{val}<small>{escape(unit)}</small></div>'
            f'<div class="cv-meter"><i style="--w:{max(min(meter, 1), 0.02) * 100:.1f}%;--grad:linear-gradient(90deg,{g1},{g2});'
            f'--d:{delay + .2:.2f}s"></i></div><div class="foot">{escape(foot)}</div></div>')


def build(run, rag_stats: dict | None = None) -> str:
    r, m = run.final, run.minimums
    req = m["crar"] * r.total_rwa
    req_t1 = m["tier1"] * r.total_rwa
    ok = r.crar >= m["crar"] and r.tier1_ratio >= m["tier1"]
    open_ex = [e for e in run.exceptions if e.status == "OPEN"]
    hi = sum(e.severity in ("Critical", "High") for e in open_ex)
    data_gaps = sum(e.category in ("Data completeness", "Data quality", "Completeness") for e in open_ex)
    bench = run.benchmark
    tie_ok = sum(b["status"] == "PASS" for b in bench)
    passed = sum(c.status == "PASS" for c in run.checks)
    date = f"{run.ds.reporting_date:%d %b %Y}"
    whole, dec = divmod(round(r.crar * 10000), 100)

    # ---------------- hero
    hero = f"""
<div class="cv-hero cv-full cv-in" style="--d:0s"><div class="orb o1"></div><div class="orb o2"></div><div class="mesh"></div>
 <div>
  <span class="cv-eyebrow"><span class="cv-pulse"></span>Engine verified · {tie_ok}/{len(bench)} benchmark metrics tie out</span>
  <div class="h1">CRAR · as at {escape(date)}</div>
  <div class="cv-huge"><span class="cnt" style="--to:{whole}"></span>.<span class="cnt2" style="--to:{dec}"></span><span class="pct">%</span></div>
  <div class="cv-badges"><span class="cv-gb {'ok' if ok else ''}">{'✓ Compliant with RBI minimums' if ok else '⚠ Below an RBI minimum'}</span>
   <span class="cv-gb">+{(r.crar - m['crar']) * 100:.2f} pp above the {m['crar']:.0%} floor</span></div>
 </div>
 {_gauge(r.crar, r.tier1_ratio, m['crar'], m['tier1'])}
 <div class="cv-hero-r">
  <div class="cv-glass"><div><div class="k">Tier 1 ratio</div><div class="v">{r.tier1_ratio:.2%}</div></div><div class="m">minimum<br>{m['tier1']:.0%}</div></div>
  <div class="cv-glass"><div><div class="k">Capital surplus over requirement</div><div class="v">{_l(r.tier1 + r.tier2 - req)} L</div></div><div class="m">at 15%<br>of RWA</div></div>
  <div class="cv-glass"><div><div class="k">RWA growth capacity</div><div class="v">+{(r.tier1 + r.tier2) / m['crar'] / r.total_rwa - 1:.0%}</div></div><div class="m">before CRAR<br>hits {m['crar']:.0%}</div></div>
 </div>
</div>"""

    # ---------------- KPI tiles
    total_cap = r.tier1 + r.tier2
    cap_rwa = total_cap / m["crar"]
    t2_share = r.tier2_gp_eligible / r.gp_gross if r.gp_gross else 0
    tiles = "".join([
        _tile("shield", "#6B3FB8", "#9B6BEB", "Tier 1 capital", f"₹{_num(r.tier1)}", " L",
              r.tier1 / total_cap if total_cap else 0, f"{r.tier1 / total_cap:.0%} of total capital",
              "Core", "#F1EAFC", P, .08),
        _tile("layers", "#A276E8", "#D1B7FA", "Tier 2 capital", f"₹{_num(r.tier2)}", " L", t2_share,
              f"{t2_share:.0%} of provision counted", "Capped", "#F4EEFD", "#7B4FC4", .14),
        _tile("scale", "#3D2B8C", "#6E64D8", "Risk-weighted assets", f"₹{_num(r.total_rwa)}", " L",
              r.total_rwa / cap_rwa, f"capacity at the {m['crar']:.0%} floor",
              f"{r.total_rwa / cap_rwa:.0%} used", "#ECEBFB", "#3D2B8C", .2),
        _tile("flag", "#E28A1C", "#F5BE5C", "Items for review", "", "", hi / len(open_ex) if open_ex else 0,
              f"{hi} high priority · {data_gaps} data gaps", f"{hi} high", "#FDF1DE", "#B4700F", .26, count=len(open_ex)),
    ])
    tiles = f'<div class="cv-tiles cv-full">{tiles}</div>'

    # ---------------- scene + dark tile
    scene = f"""
<div class="cv-card cv-span2 cv-in" style="--d:.3s;padding:0;overflow:hidden;position:relative">
 <div class="cv-h" style="position:absolute;left:20px;right:20px;top:18px;z-index:2;margin:0">
  <div><div class="cv-t">Capital held vs RBI requirement</div><div class="cv-sub">Isometric view · ₹ lakhs</div></div>
  <span style="display:flex;gap:6px"><span class="cv-chip">■ Tier 1</span><span class="cv-chip" style="color:#7B4FC4">■ Tier 2</span>
  <span class="cv-chip">⬚ Required</span></span></div>
 <div class="cx-hero" style="height:430px;border:none;box-shadow:none;border-radius:0;background:radial-gradient(120% 90% at 55% 40%,#FFFFFF 0%,#F5F1FB 60%,#EEE8F7 100%)">
  {capital_scene(r.tier1, r.tier2, req, req_t1)}</div></div>"""
    imp = [e for e in open_ex if e.scenario_overrides]
    imp.sort(key=lambda e: -abs(e.impact_crar_bps))
    mx = max((abs(e.impact_crar_bps) for e in imp), default=1) or 1
    upside = (run.agent_view.crar - r.crar) * 1e4
    drows = "".join(
        f'<span class="nm" title="{escape(e.title)}">{escape(_compact(e.title))}</span>'
        f'<span class="bp" style="color:{SEV.get(e.severity, "#fff")}">{e.impact_crar_bps:+.0f}</span>'
        f'<span class="tr"><i style="--w:{abs(e.impact_crar_bps) / mx * 100:.0f}%;--c:{SEV.get(e.severity, "#fff")};--d:{.4 + i * .12:.2f}s"></i></span>'
        for i, e in enumerate(imp[:6]))
    dark = f"""
<div class="cv-dark cv-in" style="--d:.36s">
 <div class="cv-h" style="margin-bottom:0"><div><div class="cv-t">Judgement calls at stake</div>
  <div class="cv-sub">CRAR impact if each alternative reading is accepted</div></div>
  <span class="cv-chip" style="background:rgba(255,255,255,.08);border-color:rgba(255,255,255,.14);color:#E8E0F7">bps</span></div>
 <div class="big">{upside:+.0f}<small>bps</small></div>
 <div class="cv-sub" style="margin-top:0">if every agent reading is accepted</div>
 <div class="rw">{drows or '<span class="nm">Nothing open.</span>'}</div>
 <div class="cv-sub" style="margin-top:14px">Figures change only after a signed SME decision.</div></div>"""

    # ---------------- bridge + RWA mix
    steps = []
    for a in run.cap_applied:
        if a.applied in ("T1_INCLUDE", "T1_DEDUCT") and abs(a.cls.amount) > 0.005:
            steps.append((a.cls.label, a.cls.amount if a.applied == "T1_INCLUDE" else -abs(a.cls.amount), "x"))
    steps += [("Tier 1 capital", r.tier1, "total"), ("Tier 2 (capped)", r.tier2, "x"), ("Total capital", total_cap, "total")]
    bridge = f"""
<div class="cv-card cv-span2 cv-in" style="--d:.42s"><div class="cv-h"><div><div class="cv-t">How capital is built</div>
 <div class="cv-sub">From equity to total regulatory capital · ₹ lakhs</div></div><span class="cv-chip">Bridge</span></div>
 {waterfall(steps)}</div>"""
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
    parts = [(k, v, c) for (k, v), c in zip(grp.items(), [P, P_VIOLET, P_SOFT, "#E2D8F3"])]
    tot = sum(v for _, v, _ in parts) or 1
    leg = "".join(f'<span class="sw" style="background:{c}"></span><span>{escape(k)}</span><span class="pc">{v / tot:.1%}</span>'
                  for k, v, c in parts)
    mix = f"""
<div class="cv-card cv-in" style="--d:.48s"><div class="cv-h"><div><div class="cv-t">Risk-weighted assets</div>
 <div class="cv-sub">Where the risk sits</div></div><span class="cv-chip">Mix</span></div>
 <div style="display:flex;align-items:center;gap:18px">{donut(parts, 132)}<div class="cx-leg" style="flex:1;min-width:0">{leg}</div></div>
 <div class="cx-stats" style="margin-top:16px;padding-top:12px;border-top:1px solid {LINE}">
  <div><div class="cx-lbl">Total RWA</div><div class="v">{_l(r.total_rwa)} L</div></div>
  <div><div class="cx-lbl">Checks</div><div class="v">{passed}/{len(run.checks)}</div></div>
  <div><div class="cx-lbl">Benchmark</div><div class="v">{tie_ok}/{len(bench)}</div></div></div></div>"""

    # ---------------- sensitivity, queue, activity
    sens = f"""
<div class="cv-card cv-in" style="--d:.54s"><div class="cv-h"><div><div class="cv-t">CRAR sensitivity</div>
 <div class="cv-sub">If the loan risk weight changes</div></div><span class="cv-chip">What-if</span></div>
 <div style="margin-top:18px">{sensitivity_chart(run)}</div></div>"""
    qitems = "".join(
        f'<div class="it"><span class="cx-dot" style="background:{SEV.get(e.severity, FAINT)}"></span>'
        f'<div style="min-width:0"><div class="nm" title="{escape(e.title)}">{escape(_short(e.title, 34))}</div>'
        f'<div class="sb">{escape(e.severity)} · {escape(CAT.get(e.category, e.category))}</div></div>'
        f'<span class="bp" style="color:{GREEN if e.impact_crar_bps > 0 else (RED if e.impact_crar_bps < 0 else FAINT)}">'
        f'{(f"{e.impact_crar_bps:+.0f} bps") if e.scenario_overrides else "info"}</span></div>' for e in open_ex[:5])
    queue = f"""
<div class="cv-card cv-in" style="--d:.6s"><div class="cv-h"><div><div class="cv-t">Review queue</div>
 <div class="cv-sub">Highest priority first</div></div>
 <span class="cv-chip" style="background:#FDF1DE;border-color:#FBE3BC;color:#B4700F">{len(open_ex)} open</span></div>
 <div class="cx-list">{qitems or '<div class="cx-lbl">Nothing open.</div>'}</div></div>"""
    auto = sum(a.cls.route == "AUTO_ACCEPT" for a in run.cap_applied + run.rwa_applied)
    allc = len(run.cap_applied + run.rwa_applied)
    kb = rag_stats or {}
    events = [
        ("Workbook ingested", f"{len(run.ds.sheet_map)} sheets recognised by their headers"),
        ("Validated against source", f"{passed} of {len(run.checks)} tie-outs pass"),
        ("RBI text retrieved", f"{kb.get('chunks_current', 0):,} paragraphs in force on {date}"),
        ("Items classified", f"{auto} of {allc} auto-accepted with citations"),
        ("Capital computed", f"CRAR {r.crar:.2%} · benchmark {tie_ok}/{len(bench)}"),
        ("Awaiting SME review", f"{len(open_ex)} items · {hi} high priority"),
    ]
    tl = "".join(f'<div class="ev{" now" if i == len(events) - 1 else ""}" style="--d:{.6 + i * .18:.2f}s">'
                 f'<div class="a">{escape(a)}</div><div class="b">{escape(b)}</div></div>' for i, (a, b) in enumerate(events))
    activity = f"""
<div class="cv-card cv-in" style="--d:.66s"><div class="cv-h"><div><div class="cv-t">Agent activity</div>
 <div class="cv-sub">This run, step by step</div></div><span class="cv-chip" style="background:#E7F5EE;border-color:#CFEBDD;color:{GREEN}">Offline</span></div>
 <div class="cv-tl">{tl}</div></div>"""

    return (CSS + f'<div class="cv"><div class="cv-grid">{hero}{tiles}{scene}{dark}{bridge}{mix}{sens}{queue}{activity}'
            f'</div></div>')
