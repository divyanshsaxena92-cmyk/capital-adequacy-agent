"""Building blocks for every Command-Centre-style page (same component, same look, same interactions).

Interactions available to any page (implemented once in ui/dashboard_component/index.html):
  data-drill="key" + <template data-drill-body="key">  -> detail panel opens OVER the page (nothing reflows)
  <table data-table="id"> + th[data-sort] + input[data-search-for=id] + [data-chips-for=id] button[data-key][data-val]
  data-set="group:option" / data-out="group:field" / data-bar="group:field" -> instant scenario toggles
  data-tabs / data-tab / data-pane (inside .panes -> fixed height), data-nav="module" -> go to another page
  data-search on any block -> page search highlights it; Enter in the search box asks the agent
"""
from __future__ import annotations

from html import escape

from .command_center import CSS as BASE_CSS, ic

EXTRA_CSS = """
<style>
[data-drill] { cursor: pointer; }
.drill-hint { font-size: 11px; color: var(--faint); display: inline-flex; align-items: center; gap: 4px; }
.ov-backdrop { position: absolute; inset: 0; z-index: 30; background: rgba(20,12,36,.30); backdrop-filter: blur(3px);
               -webkit-backdrop-filter: blur(3px); border-radius: 28px; animation: fade .2s ease both; }
.ov-panel { position: absolute; left: 22px; right: 22px; margin: 0 auto; max-width: 1000px; z-index: 31; background: var(--card);
            border: 1px solid var(--line); border-radius: 24px; padding: 26px 28px 24px; box-shadow: 0 30px 80px rgba(20,10,40,.38);
            animation: pop .25s ease both; color: var(--ink); }
.ov-x { position: absolute; right: 16px; top: 14px; width: 36px; height: 36px; border-radius: 11px; border: 1px solid var(--chipb);
        background: var(--chip); color: var(--ink); font-size: 20px; line-height: 1; cursor: pointer; }
.ov-x:hover { border-color: #7B4FC4; color: #7B4FC4; }
.ov-h { font-size: 19px; font-weight: 700; letter-spacing: -.015em; padding-right: 48px; }
.ov-s { font-size: 12.5px; color: var(--mut); margin-top: 4px; }
.ov-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-top: 18px; }
.ov-box { background: var(--card2); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; min-width: 0; }
.ov-box small { display: block; font-size: 11px; color: var(--mut); } .ov-box b { font-size: 15px; font-variant-numeric: tabular-nums; }
.ov-p { font-size: 13px; line-height: 1.6; margin-top: 14px; color: var(--ink); }
.ov-q { border-left: 3px solid #7B4FC4; background: var(--card2); border-radius: 0 12px 12px 0; padding: 10px 14px; margin-top: 12px;
        font-size: 12.5px; line-height: 1.55; color: var(--mut); }
/* tabs: one fixed-height panel; long content scrolls inside it (no blank gaps, no page jumps) */
.panes { position: relative; height: 300px; } .panes > .pane { position: absolute; inset: 0; overflow: auto; display: block;
  visibility: hidden; opacity: 0; transition: opacity .25s; padding-right: 4px; }
.panes > .pane.on { visibility: visible; opacity: 1; }
.ov-panel .panes { height: auto; } .ov-panel .panes > .pane { position: static; display: none; } .ov-panel .panes > .pane.on { display: block; }
/* card header tools: icon + expand */
.hdl { display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 10px; align-items: start; }
.hdl > .cico { grid-row: span 2; width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center; color: #7B4FC4;
  background: rgba(123,79,196,.12); margin-top: -2px; }
.dark .hdl > .cico { color: #D9C8FF; background: rgba(255,255,255,.10); }
.xbtn { margin-left: 6px; width: 30px; height: 30px; flex: none; border-radius: 9px; border: 1px solid var(--chipb); background: var(--chip);
  color: var(--mut); cursor: pointer; font-size: 15px; line-height: 1; opacity: .55; transition: all .2s; }
.card:hover .xbtn, .dark:hover .xbtn { opacity: 1; } .xbtn:hover { color: #7B4FC4; border-color: #7B4FC4; }
.dark .xbtn { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.14); color: #E8E0F7; }
.hd { align-items: flex-start; } .hd > :last-child:not(.hdl) { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.ov-panel.wide { max-width: 1240px; } .ov-panel .hd { padding-right: 46px; } .ov-panel .cico { display: none; }
/* command palette, toast */
.ov-panel.pal { max-width: 640px; padding: 14px; }
.pal-in { display: flex; align-items: center; gap: 10px; border: 1px solid var(--chipb); border-radius: 14px; padding: 0 14px; height: 50px; background: var(--input); }
.pal-in span { color: #7B4FC4; font-weight: 700; } .pal-in input { flex: 1; border: 0; outline: 0; background: transparent; font: inherit; font-size: 15px; color: var(--ink); }
.pal-list { max-height: 340px; overflow: auto; margin-top: 8px; }
.pal-it { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-radius: 10px; cursor: pointer; font-size: 13.5px; }
.pal-it.on, .pal-it:hover { background: rgba(123,79,196,.12); } .pal-it kbd { font: inherit; font-size: 11px; color: var(--mut); background: var(--chip);
  border: 1px solid var(--chipb); border-radius: 6px; padding: 2px 7px; }
.pal-ft { font-size: 11px; color: var(--faint); padding: 8px 4px 0; }
.toast { position: absolute; left: 50%; transform: translateX(-50%); z-index: 40; background: #17121F; color: #fff; padding: 9px 16px;
  border-radius: 999px; font-size: 12.5px; font-weight: 600; box-shadow: 0 10px 30px rgba(0,0,0,.3); animation: pop .2s ease both; }
/* mini charts in tiles */
.vrow { display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; } .vrow .spark { flex: none; opacity: .95; }
/* compact density (default): less scrolling on desktop */
#cc[data-density="compact"] { padding: 16px; }
#cc[data-density="compact"] .g { gap: 16px; }
#cc[data-density="compact"] .tb { margin-bottom: 16px; padding: 10px 14px; }
#cc[data-density="compact"] .card, #cc[data-density="compact"] .dark { padding: 18px 20px; }
#cc[data-density="compact"] .hd { margin-bottom: 12px; }
#cc[data-density="compact"] .hero { padding: 24px 28px; min-height: 0; }
#cc[data-density="compact"] .huge { font-size: 54px !important; }
#cc[data-density="compact"] .gauge { width: 176px; height: 176px; }
#cc[data-density="compact"] .scene-wrap { height: 380px; }
#cc[data-density="compact"] .tile .lbl { margin-top: 12px; }
#cc[data-density="compact"] .meter { margin-top: 10px; }
#cc[data-density="compact"] .rq td, #cc[data-density="compact"] .dt td { padding: 9px 12px; }
#cc[data-density="compact"] .tl .ev { padding-bottom: 10px; }
.dt { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12.5px; }
.dt th { font-size: 11.5px; font-weight: 600; color: var(--mut); text-align: left; padding: 10px 12px; background: var(--card2);
         border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); white-space: nowrap; user-select: none; }
.dt th:first-child { border-left: 1px solid var(--line); border-radius: 12px 0 0 12px; }
.dt th:last-child { border-right: 1px solid var(--line); border-radius: 0 12px 12px 0; }
.dt th.sorted { color: #7B4FC4; } .dt th[data-dir="asc"]::after { content: " ↑"; } .dt th[data-dir="desc"]::after { content: " ↓"; }
.dt td { padding: 11px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; max-width: 360px; overflow: hidden; text-overflow: ellipsis; }
.dt td.r, .dt th.r { text-align: right; font-variant-numeric: tabular-nums; }
.dt tbody tr { transition: background .15s; } .dt tbody tr:hover td { background: var(--card2); }
.tools { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin: 4px 0 14px; }
.mini-search { display: flex; align-items: center; gap: 8px; background: var(--input); border: 1px solid var(--chipb); border-radius: 11px;
               padding: 0 10px; height: 36px; min-width: 220px; flex: 1; max-width: 340px; }
.mini-search input { border: 0; outline: 0; background: transparent; font: inherit; font-size: 12.5px; color: var(--ink); flex: 1; min-width: 0; }
.mini-search svg { color: var(--faint); }
.cmeter { display: inline-flex; align-items: center; gap: 8px; } .cmeter span { width: 70px; height: 6px; border-radius: 999px;
          background: var(--track); overflow: hidden; display: inline-block; } .cmeter span i { display: block; height: 100%; border-radius: 999px; }
.bl .row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 12px; align-items: center; margin-top: 12px; }
.bl .nm { font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bl .v { font-size: 12.5px; font-weight: 650; font-variant-numeric: tabular-nums; }
.bl .trk { grid-column: 1 / -1; height: 8px; border-radius: 999px; background: var(--track); overflow: hidden; }
.bl .trk i { display: block; height: 100%; border-radius: 999px; transform-origin: left; animation: growx 1.2s cubic-bezier(.2,.75,.2,1) both;
             animation-delay: var(--d, 0s); }
.tor .row { display: grid; grid-template-columns: 190px minmax(0, 1fr) 70px; gap: 12px; align-items: center; margin-top: 10px; font-size: 12.5px; }
.tor .axis { position: relative; height: 18px; background: linear-gradient(var(--line), var(--line)) center / 1px 100% no-repeat; }
.tor .axis i { position: absolute; top: 3px; height: 12px; border-radius: 4px; animation: fade .6s ease both; animation-delay: var(--d, 0s); }
.tor .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } .tor .v { text-align: right; font-weight: 650; font-variant-numeric: tabular-nums; }
.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.step { position: relative; background: var(--card2); border: 1px solid var(--line); border-radius: 16px; padding: 14px 16px; }
.step .n { width: 24px; height: 24px; border-radius: 8px; display: grid; place-items: center; font-size: 12px; font-weight: 700; color: #fff;
           background: linear-gradient(135deg, #4F2D7F, #7B4FC4); }
.step small { display: block; font-size: 11.5px; color: var(--mut); margin-top: 10px; } .step b { font-size: 17px; font-variant-numeric: tabular-nums; }
.step .f { font-size: 11px; color: var(--faint); margin-top: 4px; }
.formula { display: flex; align-items: stretch; gap: 10px; flex-wrap: wrap; }
.formula .blk { flex: 1 1 140px; background: var(--card2); border: 1px solid var(--line); border-radius: 16px; padding: 14px 16px; }
.formula .blk.k { background: linear-gradient(135deg, #2B1747, #4F2D7F); color: #fff; border: 0; }
.formula .blk small { display: block; font-size: 11.5px; opacity: .75; } .formula .blk b { font-size: 20px; font-variant-numeric: tabular-nums; }
.formula .op { align-self: center; font-size: 22px; font-weight: 700; color: var(--faint); }
.seg2 { display: inline-flex; gap: 4px; background: var(--chip); border: 1px solid var(--chipb); border-radius: 12px; padding: 4px; }
.seg2 button { font: inherit; font-size: 12px; font-weight: 600; border: 0; background: transparent; color: var(--mut); padding: 6px 12px;
               border-radius: 9px; cursor: pointer; } .seg2 button.on { background: var(--card); color: var(--ink); box-shadow: 0 2px 8px rgba(60,30,110,.12); }
.cards3 { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.mcard { background: var(--card2); border: 1px solid var(--line); border-radius: 18px; padding: 16px 18px; transition: transform .2s, box-shadow .2s;
         min-width: 0; } .mcard:hover { transform: translateY(-2px); box-shadow: var(--hover); }
.mcard .id { font-size: 11px; font-weight: 700; color: #7B4FC4; font-family: "Cascadia Code", Consolas, monospace; }
.mcard .tt { font-size: 13.5px; font-weight: 650; margin-top: 6px; line-height: 1.35; }
.mcard .meta { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; }
.tlx { position: relative; margin-top: 8px; }
.tlx .lane { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 14px; align-items: center; padding: 8px 0; border-bottom: 1px dashed var(--line); }
.tlx .lane .nm { font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tlx .track { position: relative; height: 22px; }
.tlx .bar { position: absolute; top: 3px; height: 16px; border-radius: 6px; font-size: 10px; color: #fff; padding: 0 6px; display: flex;
            align-items: center; white-space: nowrap; overflow: hidden; }
.tlx .now { position: absolute; top: -6px; bottom: -6px; width: 2px; background: #D64560; }
.tlx .now span { position: absolute; top: -18px; left: 4px; font-size: 10.5px; font-weight: 700; color: #D64560; white-space: nowrap; }
.tlx .ax { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 14px; margin-top: 6px; }
.tlx .ax > div { position: relative; height: 16px; } .tlx .ax > div > span { position: absolute; transform: translateX(-50%); font-size: 10.5px; color: var(--faint); white-space: nowrap; }
.pipe { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.pipe .p { position: relative; background: var(--card2); border: 1px solid var(--line); border-radius: 16px; padding: 14px; }
.pipe .p .st { font-size: 11px; font-weight: 700; } .pipe .p b { display: block; font-size: 13.5px; margin-top: 6px; }
.pipe .p small { display: block; font-size: 11px; color: var(--mut); margin-top: 4px; line-height: 1.4; }
.howto { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
.howto .h { background: var(--card2); border: 1px solid var(--line); border-radius: 18px; padding: 16px 18px; }
.howto .h b { font-size: 14px; } .howto .h p { font-size: 12.5px; color: var(--mut); line-height: 1.55; margin: 8px 0 0; }
.howto .h .badge2 { font-size: 10.5px; font-weight: 700; letter-spacing: .08em; color: #7B4FC4; }
</style>
"""
CSS = BASE_CSS + EXTRA_CSS

TREAT = {"T1_INCLUDE": ("Included", "rgba(46,139,94,.13)", "#2E8B5E"), "T1_DEDUCT": ("Deducted", "rgba(214,69,96,.13)", "#D64560"),
         "T1_EXCLUDE": ("Excluded", "var(--chip)", "var(--mut)"), "T2_GENERAL_PROVISION": ("Tier 2", "rgba(123,79,196,.13)", "#7B4FC4"),
         "RISK_WEIGHT": ("Risk weight", "rgba(61,43,140,.12)", "#5B4FC8"), "INFO": ("Info", "var(--chip)", "var(--mut)")}
SEVC = {"Critical": "#8E1B3A", "High": "#E0567A", "Medium": "#F0A93B", "Low": "#A9A6B3"}


def tag(text, bg="var(--chip)", fg="var(--mut)"):
    return f'<span class="tag" style="background:{bg};color:{fg}">{escape(str(text))}</span>'


def treat_tag(t):
    label, bg, fg = TREAT.get(t, (t, "var(--chip)", "var(--mut)"))
    return tag(label, bg, fg)


def conf_meter(c: float):
    col = "#2E8B5E" if c >= .85 else ("#D48B12" if c >= .7 else "#D64560")
    return f'<span class="cmeter"><span><i style="width:{c * 100:.0f}%;background:{col}"></i></span><b class="num">{c:.2f}</b></span>'


def count(value: float, dp: int = 0, prefix: str = "", suffix: str = "") -> str:
    txt = f"{prefix}{value:,.{dp}f}{suffix}"
    return (f'<span data-count="{value}" data-dp="{dp}" data-prefix="{escape(prefix)}" '
            f'data-suffix="{escape(suffix)}">{escape(txt)}</span>')


def topbar(title: str, subtitle: str) -> str:
    return f"""<header class="tb"><div class="brand"><span class="mark">GT</span><div><div class="f">GRANT THORNTON · CAPITAL ADEQUACY</div>
 <div class="n">{escape(title)}</div></div></div>
 <label class="search">{ic("search")}<input id="q" type="text" autocomplete="off" placeholder="Search · Enter asks the agent">
  <span id="qcount"></span><kbd>Ctrl K</kbd></label>
 <div class="tr"><div class="clock"><b id="clock">--:--</b><span>{escape(subtitle)}</span></div>
  <button class="iconbtn" data-nav="t01_overview" title="Back to Command Centre">{ic("arrow", 18)}</button>
  <button class="iconbtn" id="theme" title="Day / night"><span class="i-sun">{ic("sun")}</span><span class="i-moon" style="display:none">{ic("moon")}</span></button>
  <span class="avatar" title="Grant Thornton">GT</span></div></header>"""


def hero(eyebrow: str, label: str, value_html: str, unit: str, chips: list, right_html: str = "", span="c8") -> str:
    ch = "".join(f'<span class="gb {c[1] if isinstance(c, tuple) else ""}">{escape(c[0] if isinstance(c, tuple) else c)}</span>' for c in chips)
    return f"""<section class="hero {span}"><div class="orb o1"></div><div class="orb o2"></div><div class="mesh"></div>
 <div><span class="eyebrow"><span class="pulse"></span>{escape(eyebrow)}</span><div class="h1">{escape(label)}</div>
 <div class="huge" style="font-size:58px">{value_html}<span class="pct">{escape(unit)}</span></div><div class="gbs">{ch}</div></div>
 {right_html}</section>"""


def tile(icon, g1, g2, label, value_html, unit, meter, foot, trend, tbg, tfg, d, drill=None, search=""):
    dd = f' data-drill="{drill}"' if drill else ""
    hint = '<span class="drill-hint">Click for detail ↗</span>' if drill else ""
    return (f'<div class="card tile c3" style="--d:{d}s;--glow:{g1}"{dd} data-search="{escape(search or label.lower())}">'
            f'<div class="top"><span class="ico" style="background:linear-gradient(135deg,{g1},{g2});--sh:{g1}55">{ic(icon, 22)}</span>'
            f'<span class="trend" style="background:{tbg};color:{tfg}">{escape(trend)}</span></div>'
            f'<div class="lbl">{escape(label)}</div><div class="val">{value_html}<small>{escape(unit)}</small></div>'
            f'<div class="meter"><i style="--w:{max(min(meter, 1), .02) * 100:.1f}%;--grad:linear-gradient(90deg,{g1},{g2});--d:{d + .2:.2f}s"></i></div>'
            f'<div class="foot" style="display:flex;justify-content:space-between;gap:8px"><span>{escape(foot)}</span>{hint}</div></div>')


def card(title, sub, body, span="c6", right="", d=.3, attrs="", search=""):
    return (f'<section class="card {span}" style="--d:{d}s" {attrs} data-search="{escape(search or title.lower())}">'
            f'<div class="hd"><div><div class="t">{escape(title)}</div><div class="s">{escape(sub)}</div></div>{right}</div>{body}</section>')


def drill(key: str, title: str, sub: str, body: str) -> str:
    return f'<template data-drill-body="{escape(key)}"><div class="ov-h">{escape(title)}</div><div class="ov-s">{escape(sub)}</div>{body}</template>'


def boxes(items: list[tuple[str, str]]) -> str:
    return '<div class="ov-grid">' + "".join(f'<div class="ov-box"><small>{escape(k)}</small><b>{escape(v)}</b></div>' for k, v in items) + "</div>"


def table(tid: str, cols: list, rows: list[str], chips: list | None = None, search_ph: str = "Search table…") -> str:
    """cols: [(label, sort 'num'|'txt'|None, align 'r'|'' )]; rows: pre-rendered <tr> strings."""
    th = "".join(f'<th{" data-sort=" + chr(34) + s + chr(34) if s else ""}{" class=" + chr(34) + "r" + chr(34) if a == "r" else ""}>{escape(lbl)}</th>'
                 for lbl, s, a in cols)
    chip_html = ""
    for key, opts in (chips or []):
        btns = "".join(f'<button class="btn{" on" if i == 0 else ""}" data-key="{key}" data-val="{escape(v)}">{escape(lbl)}</button>'
                       for i, (lbl, v) in enumerate(opts))
        chip_html += f'<div class="flt" data-chips-for="{tid}">{btns}</div>'
    tools = (f'<div class="tools"><label class="mini-search">{ic("search", 15)}<input data-search-for="{tid}" placeholder="{escape(search_ph)}"></label>'
             f'{chip_html}<span class="mut" style="font-size:12px;margin-left:auto"><b data-count-for="{tid}">{len(rows)}</b> rows</span></div>')
    return f'{tools}<div class="tblw"><table class="dt" data-table="{tid}"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def bars(items: list[tuple[str, float, str, str]], color="#4F2D7F", fmt="{:,.0f}") -> str:
    """items: (name, value, display, colour or '')"""
    mx = max((abs(v) for _, v, _, _ in items), default=1) or 1
    return '<div class="bl">' + "".join(
        f'<div class="row"><span class="nm" title="{escape(n)}">{escape(n)}</span><span class="v">{escape(disp)}</span>'
        f'<span class="trk"><i style="width:{abs(v) / mx * 100:.1f}%;background:{c or color};--d:{.3 + i * .06:.2f}s"></i></span></div>'
        for i, (n, v, disp, c) in enumerate(items)) + "</div>"


def tornado(items: list[tuple[str, float, str]]) -> str:
    """items: (name, bps, colour). Centre line at zero."""
    mx = max((abs(v) for _, v, _ in items), default=1) or 1
    rows = []
    for i, (n, v, c) in enumerate(items):
        w = abs(v) / mx * 50
        left = 50 if v >= 0 else 50 - w
        rows.append(f'<div class="row"><span class="nm" title="{escape(n)}">{escape(n)}</span><span class="axis">'
                    f'<i style="left:{left:.1f}%;width:{max(w, .6):.1f}%;background:{c};--d:{.2 + i * .05:.2f}s"></i></span>'
                    f'<span class="v" style="color:{"#2E8B5E" if v > 0 else ("#D64560" if v < 0 else "var(--faint)")}">{v:+.0f} bps</span></div>')
    return '<div class="tor">' + "".join(rows) + "</div>"


def page(title: str, subtitle: str, body: str, templates="") -> str:
    if not isinstance(templates, str):                 # a list of detail panels -> join (never print a Python list)
        templates = "".join(templates)
    return CSS + f'<div id="cc" data-theme="light">{topbar(title, subtitle)}<main class="g">{body}</main>{templates}</div>'
