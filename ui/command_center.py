"""Capital Command Centre - the Overview, rendered as a local Streamlit custom component (its own iframe).

Running in its own frame means no HTML sanitiser touches it, so it renders exactly as designed, and it can
be interactive: live search, day/night theme, alerts menu, a what-if slider, tabs, filters and sorting.
Everything is local - no network, no external libraries. All numbers come from the deterministic engine.
"""
from __future__ import annotations

import datetime as dt
import math
from html import escape

from .overview_html import CAT, _l, _short, _smooth, capital_scene, donut, waterfall
from .overview_html import CSS as CHART_CSS

P, P_DEEP, P_VIOLET = "#4F2D7F", "#2B1747", "#7B4FC4"
SEV = {"Critical": "#8E1B3A", "High": "#E0567A", "Medium": "#F0A93B", "Low": "#A9A6B3"}
CATS = ["Interpretation", "Data", "Evidence", "Completeness", "Governance", "Classification"]

ICON = {
    "search": '<path d="M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9 16-4.3-4.3" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"/>',
    "bell": '<path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15L6 16zM10 20a2 2 0 0 0 4 0" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
    "sun": '<circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "moon": '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
    "shield": '<path d="M12 3l7 3v5c0 4.4-3 8.3-7 9.5C8 19.3 5 15.4 5 11V6l7-3z" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 11.5l2.2 2.2L15.5 9.5" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "layers": '<path d="M12 4l8 4-8 4-8-4 8-4z" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M4 12l8 4 8-4M4 16l8 4 8-4" fill="none" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
    "scale": '<path d="M12 4v16M6 20h12M5 8h14" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/><path d="M5 8l-2.5 6h5L5 8zM19 8l-2.5 6h5L19 8z" fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/>',
    "flag": '<path d="M6 21V4M6 4h10l-1.5 3.5L16 11H6" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 11V8a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="1.8"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
    "sort": '<path d="M7 4v16M7 20l-3-3M7 20l3-3M17 20V4M17 4l-3 3M17 4l3 3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
}


def ic(name: str, size: int = 18) -> str:
    return f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true">{ICON[name]}</svg>'


CSS = CHART_CSS + """
<style>
:root, #cc[data-theme="light"] {
  --bg: #F2F0F7; --blob1: #DCCFF4; --blob2: #EDE3FA; --card: #FFFFFF; --card2: #FAF9FC; --ink: #16131D; --mut: #6B6878;
  --faint: #9A97A6; --line: #ECEAF1; --chip: #F3F1F8; --chipb: #E7E3F0; --floor: #F4F0FA; --grid: #DED7EC;
  --scene: radial-gradient(120% 90% at 55% 40%, #FFFFFF 0%, #F5F1FB 60%, #EEE8F7 100%);
  --shadow: 0 1px 2px rgba(32,20,60,.04), 0 12px 32px rgba(32,20,60,.07); --hover: 0 2px 4px rgba(32,20,60,.06), 0 20px 44px rgba(32,20,60,.13);
  --input: #FFFFFF; --track: #EFECF5;
}
#cc[data-theme="dark"] {
  --bg: #0D0A13; --blob1: #2A1A47; --blob2: #1C1430; --card: #16121E; --card2: #1C1726; --ink: #F1EDF8; --mut: #A9A2B8;
  --faint: #7D7690; --line: #2A2436; --chip: #211B2C; --chipb: #2E2740; --floor: #1B1626; --grid: #33294A;
  --scene: radial-gradient(120% 90% at 55% 40%, #241B35 0%, #1A1427 60%, #140F1E 100%);
  --shadow: 0 1px 2px rgba(0,0,0,.3), 0 12px 32px rgba(0,0,0,.35); --hover: 0 2px 4px rgba(0,0,0,.35), 0 20px 44px rgba(0,0,0,.5);
  --input: #1C1726; --track: #2A2338;
}
html, body { margin: 0; padding: 0; background: transparent; }
#cc { position: relative; isolation: isolate; overflow: hidden; border-radius: 28px; padding: 22px; background: var(--bg);
      font-family: "Inter", "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, Arial, sans-serif; color: var(--ink);
      -webkit-font-smoothing: antialiased; transition: background .35s ease, color .35s ease; }
#cc * { box-sizing: border-box; }
#cc::before, #cc::after { content: ""; position: absolute; z-index: -1; border-radius: 50%; filter: blur(80px); opacity: .7; pointer-events: none; }
#cc::before { width: 560px; height: 560px; left: -180px; top: 320px; background: var(--blob1); }
#cc::after { width: 620px; height: 620px; right: -220px; bottom: -160px; background: var(--blob2); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 22px; padding: 22px 24px; min-width: 0;
        box-shadow: var(--shadow); transition: transform .25s ease, box-shadow .25s ease, background .35s ease, border-color .35s ease;
        animation: up .6s cubic-bezier(.2,.75,.2,1) both; animation-delay: var(--d, 0s); }
.card:hover { transform: translateY(-3px); box-shadow: var(--hover); }
.hd { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.t { font-size: 15px; font-weight: 650; letter-spacing: -.01em; }
.s { font-size: 12px; color: var(--mut); margin-top: 3px; }
.chip { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; font-weight: 550; color: var(--ink); background: var(--chip);
        border: 1px solid var(--chipb); padding: 4px 11px; border-radius: 999px; white-space: nowrap; }
.btn { display: inline-flex; align-items: center; gap: 6px; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; color: var(--ink);
       background: var(--chip); border: 1px solid var(--chipb); padding: 6px 12px; border-radius: 10px; transition: all .2s; white-space: nowrap; }
.btn:hover { border-color: #7B4FC4; color: #7B4FC4; }
.btn.on { background: #4F2D7F; border-color: #4F2D7F; color: #fff; }
.mut { color: var(--mut); } .faint { color: var(--faint); }
.num { font-variant-numeric: tabular-nums; }

/* command bar */
.tb { display: grid; grid-template-columns: auto minmax(220px, 1fr) auto; gap: 20px; align-items: center; margin-bottom: 22px;
      background: var(--card); border: 1px solid var(--line); border-radius: 20px; padding: 14px 16px 14px 18px; box-shadow: var(--shadow);
      position: relative; z-index: 5; animation: up .5s ease both; }
.brand { display: flex; align-items: center; gap: 12px; }
.mark { width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 13px;
        background: linear-gradient(135deg, #2B1747, #4F2D7F 55%, #7B4FC4); box-shadow: 0 8px 18px rgba(79,45,127,.35); letter-spacing: .02em; }
.brand .f { font-size: 10.5px; font-weight: 750; letter-spacing: .16em; color: #7B4FC4; }
.brand .n { font-size: 17px; font-weight: 700; letter-spacing: -.015em; margin-top: 1px; white-space: nowrap; }
.search { position: relative; display: flex; align-items: center; gap: 10px; background: var(--input); border: 1px solid var(--chipb);
          border-radius: 14px; padding: 0 12px; height: 44px; transition: border-color .2s, box-shadow .2s; }
.search:focus-within { border-color: #7B4FC4; box-shadow: 0 0 0 4px rgba(123,79,196,.15); }
.search svg { color: var(--faint); flex: none; }
.search input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; font: inherit; font-size: 13.5px; color: var(--ink); }
.search input::placeholder { color: var(--faint); }
.search kbd { font: inherit; font-size: 10.5px; font-weight: 600; color: var(--mut); background: var(--chip); border: 1px solid var(--chipb);
              border-radius: 6px; padding: 2px 6px; white-space: nowrap; }
#qcount { font-size: 11.5px; color: #7B4FC4; font-weight: 600; white-space: nowrap; }
.tr { display: flex; align-items: center; gap: 10px; }
.clock { text-align: right; line-height: 1.2; white-space: nowrap; }
.clock b { font-size: 14px; font-variant-numeric: tabular-nums; } .clock span { display: block; font-size: 10.5px; color: var(--faint); }
.iconbtn { position: relative; width: 42px; height: 42px; display: grid; place-items: center; border-radius: 12px; cursor: pointer;
           color: var(--ink); background: var(--chip); border: 1px solid var(--chipb); transition: all .2s; }
.iconbtn:hover { color: #7B4FC4; border-color: #7B4FC4; }
.badge { position: absolute; top: -5px; right: -5px; min-width: 19px; height: 19px; padding: 0 5px; border-radius: 999px; background: #E0567A;
         color: #fff; font-size: 10.5px; font-weight: 700; display: grid; place-items: center; border: 2px solid var(--card); }
.avatar { width: 42px; height: 42px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 750; font-size: 12.5px;
          background: linear-gradient(135deg, #4F2D7F, #7B4FC4); box-shadow: 0 6px 14px rgba(79,45,127,.35); }
.menu { position: absolute; right: 0; top: 52px; width: 340px; background: var(--card); border: 1px solid var(--line); border-radius: 16px;
        box-shadow: 0 24px 60px rgba(20,10,40,.25); padding: 8px; display: none; z-index: 20; }
.menu.open { display: block; animation: pop .2s ease both; }
.menu .mh { font-size: 11px; font-weight: 700; letter-spacing: .1em; color: var(--faint); padding: 8px 10px 6px; }
.menu .mi { display: grid; grid-template-columns: 8px minmax(0,1fr) auto; gap: 10px; align-items: center; padding: 9px 10px; border-radius: 10px; cursor: pointer; }
.menu .mi:hover { background: var(--chip); }
.menu .mi b { font-size: 12.5px; font-weight: 600; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.menu .mi small { font-size: 11px; color: var(--faint); }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }

/* grid */
.g { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 22px; }
.c12 { grid-column: span 12; } .c8 { grid-column: span 8; } .c7 { grid-column: span 7; } .c6 { grid-column: span 6; } .c5 { grid-column: span 5; }
.c4 { grid-column: span 4; } .c3 { grid-column: span 3; }
@media (max-width: 1000px) { .c8, .c7, .c6, .c5 { grid-column: span 12; } .c4 { grid-column: span 6; } .c3 { grid-column: span 6; }
                              .c4.last { grid-column: span 12; } }
@media (max-width: 760px)  { .g > * { grid-column: span 12 !important; } .tb { grid-template-columns: 1fr; } .tr { justify-content: space-between; } }
@media (max-width: 760px)  { .hero { grid-template-columns: 1fr; min-height: 0; padding: 24px; } .hero-aside { justify-content: flex-start; }
                              .hero .gauge { width: min(214px, 100%); height: auto; aspect-ratio: 1; } }

/* hero */
.hero { position: relative; overflow: hidden; border-radius: 26px; padding: 30px 32px; color: #fff; min-height: 270px;
        background: linear-gradient(125deg, #2B1747 0%, #4F2D7F 48%, #7B4FC4 100%); box-shadow: 0 22px 54px rgba(60,30,110,.30);
        display: grid; grid-template-columns: minmax(0, 1fr) minmax(210px, 30%); gap: 26px; align-items: center; animation: up .6s ease both; }
.hero .orb { position: absolute; border-radius: 50%; filter: blur(40px); pointer-events: none; }
.hero .o1 { width: 340px; height: 340px; right: 20%; top: -160px; background: rgba(176,140,255,.45); animation: drift 9s ease-in-out infinite alternate; }
.hero .o2 { width: 260px; height: 260px; left: -60px; bottom: -150px; background: rgba(255,255,255,.18); animation: drift 11s ease-in-out infinite alternate-reverse; }
.hero .mesh { position: absolute; inset: 0; opacity: .13; pointer-events: none;
              background-image: linear-gradient(rgba(255,255,255,.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.5) 1px, transparent 1px);
              background-size: 34px 34px; -webkit-mask-image: radial-gradient(70% 90% at 75% 40%, #000 0%, transparent 70%);
              mask-image: radial-gradient(70% 90% at 75% 40%, #000 0%, transparent 70%); }
.hero > div { position: relative; z-index: 1; min-width: 0; }
.hero-copy { min-width: 0; }
.hero-aside { min-width: 0; width: 100%; display: flex; justify-content: flex-end; align-items: center; }
.eyebrow { display: inline-flex; align-items: center; gap: 8px; font-size: 11.5px; font-weight: 600; background: rgba(255,255,255,.12);
           border: 1px solid rgba(255,255,255,.22); padding: 5px 11px; border-radius: 999px; }
.pulse { width: 8px; height: 8px; border-radius: 50%; background: #7CF0B5; animation: pulse 2s infinite; }
.hero .h1 { font-size: 14.5px; font-weight: 600; margin-top: 18px; color: #E8DFFA; }
.huge { font-size: clamp(42px, 6vw, 66px); font-weight: 700; letter-spacing: -.04em; line-height: 1.05; margin-top: 6px; white-space: nowrap; max-width: 100%; overflow-wrap: anywhere; font-variant-numeric: tabular-nums;
        text-shadow: 0 8px 30px rgba(0,0,0,.18); }
.huge .pct { font-size: 30px; font-weight: 500; margin-left: 4px; color: #E0D3F7; }
.gb { font-size: 11.5px; font-weight: 600; padding: 5px 11px; border-radius: 999px; white-space: nowrap; background: rgba(255,255,255,.14);
      border: 1px solid rgba(255,255,255,.25); }
.gb.ok { background: rgba(124,240,181,.18); border-color: rgba(124,240,181,.45); color: #C9FFE3; }
.gbs { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 18px; }
.gauge { width: 214px; height: 214px; position: relative; }
.gauge svg { width: 100%; height: 100%; transform: rotate(-90deg); overflow: visible; }
.gauge .ring { animation: ringin 1.9s cubic-bezier(.2,.75,.2,1) both; } .gauge .ring.r2 { animation-delay: .25s; }
.gauge .ctr { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; }
.gauge .ky { display: inline-flex; align-items: center; gap: 7px; font-size: 11px; font-weight: 600; color: #EDE6FA; width: 78px; }
.gauge .ky i { width: 9px; height: 9px; border-radius: 3px; display: inline-block; flex: none; }

/* run status */
.ring2 { width: 96px; height: 96px; position: relative; flex: none; }
.ring2 svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.ring2 .ring { animation: ringin 1.6s cubic-bezier(.2,.75,.2,1) .3s both; }
.ring2 .c { position: absolute; inset: 0; display: grid; place-items: center; text-align: center; }
.ring2 .c b { font-size: 20px; font-weight: 700; display: block; line-height: 1; } .ring2 .c small { font-size: 10px; color: var(--faint); }
.kv { display: grid; grid-template-columns: 1fr auto; gap: 10px 14px; font-size: 12.5px; margin-top: 16px; }
.kv .k { color: var(--mut); } .kv .v { font-weight: 650; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.mono { font-family: "Cascadia Code", "Consolas", "SFMono-Regular", Menlo, monospace; font-size: 11.5px; }

/* KPI tiles */
.tile { position: relative; overflow: hidden; }
.tile::after { content: ""; position: absolute; right: -40px; top: -40px; width: 150px; height: 150px; border-radius: 50%; background: var(--glow);
               opacity: .14; filter: blur(4px); }
.tile .top { display: flex; align-items: center; justify-content: space-between; }
.ico { width: 44px; height: 44px; border-radius: 14px; display: grid; place-items: center; box-shadow: 0 8px 18px var(--sh); }
.trend { font-size: 11px; font-weight: 650; padding: 3px 9px; border-radius: 999px; white-space: nowrap; }
.tile .lbl { font-size: 12.5px; color: var(--mut); margin-top: 18px; }
.tile .val { font-size: 28px; font-weight: 700; letter-spacing: -.03em; margin-top: 4px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.tile .val small { font-size: 14px; font-weight: 500; color: var(--mut); margin-left: 3px; }
.meter { height: 6px; border-radius: 999px; background: var(--track); margin-top: 16px; overflow: hidden; }
.meter i { display: block; height: 100%; width: var(--w); border-radius: 999px; background: var(--grad); transform-origin: left;
           animation: growx 1.4s cubic-bezier(.2,.75,.2,1) both; animation-delay: var(--d, 0s); }
.tile .foot { font-size: 11.5px; color: var(--faint); margin-top: 9px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* scene */
.scene-card { padding: 0; overflow: hidden; position: relative; }
.scene-card .hd { position: absolute; left: 24px; right: 24px; top: 20px; z-index: 2; margin: 0; }
.scene-wrap { height: 470px; position: relative; background: var(--scene); transition: background .35s; }
.scene-wrap svg.scene { position: absolute; inset: 0; width: 100%; height: 100%; }
.sc-floor { fill: var(--floor); } .sc-grid { stroke: var(--grid); } .sc-lt { fill: var(--ink); } .sc-ls { fill: var(--mut); }
.sc-ll { stroke: var(--faint); } .sc-dot { stroke: var(--ink); fill: var(--card); }
#cc[data-theme="dark"] .scene-wrap polygon[stroke-dasharray] { fill: rgba(160,130,220,.10) !important; stroke: #8E7BC0; }
.cv-float { animation: float 5.5s ease-in-out infinite; }
.cv-shadow { animation: shadowpulse 5.5s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }

/* dark feature tile */
.dark { position: relative; overflow: hidden; color: #fff; border-radius: 22px; padding: 24px 26px; border: 1px solid rgba(255,255,255,.06);
        background: radial-gradient(120% 100% at 100% 0%, #3A2363 0%, #1B1428 55%, #140F1E 100%); box-shadow: 0 18px 44px rgba(20,10,40,.30);
        animation: up .6s ease both; animation-delay: var(--d, 0s); transition: transform .25s; }
.dark:hover { transform: translateY(-3px); }
.dark .s { color: #B9AED0; } .dark .chip { background: rgba(255,255,255,.08); border-color: rgba(255,255,255,.14); color: #E8E0F7; }
.dark .big { font-size: 44px; font-weight: 700; letter-spacing: -.035em; margin: 6px 0 0; font-variant-numeric: tabular-nums; }
.dark .big small { font-size: 15px; color: #B9AED0; font-weight: 500; margin-left: 5px; }
.dark .rw { display: grid; grid-template-columns: minmax(0,1fr) 50px; gap: 7px 12px; align-items: center; margin-top: 14px; }
.dark .nm { font-size: 12.5px; color: #DCD3EC; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dark .bp { font-size: 12.5px; font-weight: 700; text-align: right; font-variant-numeric: tabular-nums; }
.dark .trk { grid-column: 1 / -1; height: 6px; border-radius: 999px; background: rgba(255,255,255,.08); overflow: hidden; }
.dark .trk i { display: block; height: 100%; width: var(--w); border-radius: 999px; background: var(--c); box-shadow: 0 0 12px var(--c);
               transform-origin: left; animation: growx 1.3s cubic-bezier(.2,.75,.2,1) both; animation-delay: var(--d, 0s); }

/* tabs */
.tabs { display: inline-flex; gap: 4px; background: var(--chip); border: 1px solid var(--chipb); border-radius: 12px; padding: 4px; }
.tabs button { font: inherit; font-size: 12px; font-weight: 600; border: 0; background: transparent; color: var(--mut); padding: 6px 12px;
               border-radius: 9px; cursor: pointer; transition: all .2s; white-space: nowrap; }
.tabs button.on { background: var(--card); color: var(--ink); box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 4px 10px rgba(60,30,110,.10); }
.pane { display: none; } .pane.on { display: block; animation: fade .35s ease both; }
.cmp { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.cmp th { text-align: left; font-size: 11.5px; font-weight: 600; color: var(--mut); padding: 9px 10px; border-bottom: 1px solid var(--line); }
.cmp td { padding: 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
.cmp td.r, .cmp th.r { text-align: right; font-variant-numeric: tabular-nums; }
.tag { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; font-weight: 650; padding: 3px 8px; border-radius: 999px; white-space: nowrap; }

/* what-if */
.wi-big { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.wi-big b { font-size: 40px; font-weight: 700; letter-spacing: -.035em; font-variant-numeric: tabular-nums; }
.wi-plot { position: relative; height: 150px; margin: 18px 0 0 32px; }
.wi-plot svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
.wi-plot .yl { position: absolute; left: -32px; transform: translateY(-50%); font-size: 10px; color: var(--faint); }
.wi-plot .gl { position: absolute; left: 0; right: 0; border-top: 1px dashed var(--line); }
.wi-dot { position: absolute; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 50%; background: var(--card); border: 3px solid #4F2D7F;
          box-shadow: 0 0 0 6px rgba(79,45,127,.15); transition: left .15s, top .15s; }
.wi-vl { position: absolute; top: 0; bottom: 0; border-left: 1.5px dashed #7B4FC4; opacity: .6; transition: left .15s; }
.wi-x { display: flex; justify-content: space-between; margin: 6px 0 0 32px; font-size: 10.5px; color: var(--faint); }
input[type=range] { -webkit-appearance: none; appearance: none; width: 100%; height: 6px; border-radius: 999px; margin: 18px 0 6px;
  background: linear-gradient(90deg, #4F2D7F var(--p), var(--track) var(--p)); outline: none; cursor: pointer; }
input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 22px; height: 22px; border-radius: 50%; background: #fff;
  border: 4px solid #4F2D7F; box-shadow: 0 4px 12px rgba(79,45,127,.4); }
input[type=range]::-moz-range-thumb { width: 16px; height: 16px; border-radius: 50%; background: #fff; border: 4px solid #4F2D7F; }
.wi-stats { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; margin-top: 14px; }
.wi-stats div { background: var(--card2); border: 1px solid var(--line); border-radius: 14px; padding: 11px 12px; }
.wi-stats small { font-size: 11px; color: var(--mut); display: block; } .wi-stats b { font-size: 16px; font-variant-numeric: tabular-nums; }

/* review table */
.flt { display: flex; gap: 6px; flex-wrap: wrap; }
.rq { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 16px; font-size: 12.5px; }
.rq th { font-size: 11.5px; font-weight: 600; color: var(--mut); text-align: left; padding: 10px 12px; background: var(--card2);
         border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); white-space: nowrap; }
.rq th:first-child { border-left: 1px solid var(--line); border-radius: 12px 0 0 12px; }
.rq th:last-child { border-right: 1px solid var(--line); border-radius: 0 12px 12px 0; }
.rq td { padding: 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }
.rq tbody tr { cursor: pointer; transition: background .15s; animation: up .5s ease both; animation-delay: var(--d, 0s); }
.rq tbody tr:hover td { background: var(--card2); }
.rq .itm { display: flex; align-items: center; gap: 11px; font-weight: 650; max-width: 300px; }
.rq .itm span:last-child { overflow: hidden; text-overflow: ellipsis; }
.logo { width: 32px; height: 32px; border-radius: 10px; display: grid; place-items: center; color: #fff; font-size: 10.5px; font-weight: 750;
        flex: none; box-shadow: 0 4px 10px rgba(40,20,80,.18); }
.st { display: inline-flex; align-items: center; gap: 6px; }
.tblw { overflow-x: auto; }

/* heat map */
.hm { display: grid; grid-template-columns: 70px repeat(6, minmax(0,1fr)); gap: 5px; font-size: 11px; }
.hm .h { color: var(--mut); text-align: center; font-weight: 600; padding-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hm .r { color: var(--mut); font-weight: 600; display: flex; align-items: center; }
.hm .cell { height: 40px; border-radius: 9px; display: grid; place-items: center; font-weight: 700; font-size: 13px;
            transition: transform .2s; animation: fade .5s ease both; animation-delay: var(--d, 0s); }
.hm .cell:hover { transform: scale(1.08); }

/* timeline */
.tl { position: relative; padding-left: 24px; }
.tl::before { content: ""; position: absolute; left: 7px; top: 6px; bottom: 8px; width: 2px; background: var(--line); border-radius: 2px; }
.tl .ev { position: relative; padding: 0 0 14px; animation: up .6s ease both; animation-delay: var(--d); }
.tl .ev::before { content: ""; position: absolute; left: -22px; top: 4px; width: 12px; height: 12px; border-radius: 50%; background: var(--card);
                  border: 2.5px solid #4F2D7F; }
.tl .ev.now::before { background: #D48B12; border-color: #D48B12; animation: pulsea 2s infinite; }
.tl .a { font-size: 13px; font-weight: 650; } .tl .b { font-size: 11.5px; color: var(--mut); margin-top: 2px; }

/* data quality */
.seg { display: flex; gap: 3px; margin: 12px 0 6px; }
.seg i { flex: 1 1 0; height: 26px; border-radius: 3px; animation: segin .35s ease both; animation-delay: var(--d); transform-origin: bottom; }
.chk { display: grid; grid-template-columns: auto minmax(0,1fr) auto; gap: 10px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--line); }
.chk:last-child { border-bottom: none; }
.chk .id { font-size: 12px; font-weight: 700; } .chk .ds { font-size: 12px; color: var(--mut); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* rbi */
.cite { padding: 11px 0; border-bottom: 1px solid var(--line); } .cite:last-child { border-bottom: 0; }
.cite b { font-size: 12.5px; } .cite .p { font-size: 11px; font-weight: 700; color: #7B4FC4; background: rgba(123,79,196,.10);
          padding: 2px 7px; border-radius: 6px; margin-right: 8px; }
.cite div { font-size: 11.5px; color: var(--mut); margin-top: 4px; line-height: 1.4; }

/* status bar */
.sbar { display: flex; flex-wrap: wrap; gap: 8px 22px; align-items: center; margin-top: 22px; padding: 14px 18px; border-radius: 16px;
        background: var(--card); border: 1px solid var(--line); font-size: 11.5px; color: var(--mut); }
.sbar b { color: var(--ink); font-weight: 650; } .sbar .lock { display: inline-flex; align-items: center; gap: 6px; color: #2E8B5E; font-weight: 650; }
.sbar .grow { flex: 1; }

/* search highlighting */
.dim { opacity: .28; filter: grayscale(.6); transition: opacity .2s; }
.hit { outline: 2px solid rgba(123,79,196,.55); outline-offset: 2px; border-radius: 10px; }

/* motion */
.cx-wf .bar { transform-origin: bottom; animation: growy 1s cubic-bezier(.2,.75,.2,1) both; }
svg .seg { animation: draw 1.2s cubic-bezier(.2,.75,.2,1) both; }
@keyframes up { from { opacity: 0; transform: translateY(12px); } }
@keyframes fade { from { opacity: 0; } }
@keyframes pop { from { opacity: 0; transform: translateY(-6px) scale(.98); } }
@keyframes ringin { from { stroke-dashoffset: var(--c); } }
@keyframes growx { from { transform: scaleX(0); } }
@keyframes growy { from { transform: scaleY(0); } }
@keyframes segin { from { opacity: 0; transform: scaleY(.2); } }
@keyframes draw { from { stroke-dasharray: 0 999; } }
@keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
@keyframes shadowpulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(.92); opacity: .75; } }
@keyframes drift { from { transform: translate(0, 0); } to { transform: translate(40px, 30px); } }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(124,240,181,.7); } 70% { box-shadow: 0 0 0 9px rgba(124,240,181,0); } 100% { box-shadow: 0 0 0 0 rgba(124,240,181,0); } }
@keyframes pulsea { 0% { box-shadow: 0 0 0 0 rgba(212,139,18,.6); } 70% { box-shadow: 0 0 0 8px rgba(212,139,18,0); } 100% { box-shadow: 0 0 0 0 rgba(212,139,18,0); } }
@media (prefers-reduced-motion: reduce) { #cc *, #cc *::before, #cc *::after { animation: none !important; transition: none !important; } }
</style>
"""


def _gauge(crar, t1r, mc, mt) -> str:
    top = max(40.0, math.ceil(max(crar, t1r) * 100 / 10) * 10 + 10)
    out = []
    for i, (val, mn, r, w, g) in enumerate(((crar, mc, 88, 14, "g1"), (t1r, mt, 64, 10, "g2"))):
        c = 2 * math.pi * r
        off = c * (1 - min(val * 100 / top, 1))
        a = mn * 100 / top * 2 * math.pi
        out.append(f'<circle cx="105" cy="105" r="{r}" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="{w}"/>'
                   f'<circle class="ring{" r2" if i else ""}" cx="105" cy="105" r="{r}" fill="none" stroke="url(#{g})" stroke-width="{w}" '
                   f'stroke-linecap="round" stroke-dasharray="{c:.2f}" style="--c:{c:.2f};stroke-dashoffset:{off:.2f}"/>'
                   f'<circle cx="{105 + r * math.cos(a):.1f}" cy="{105 + r * math.sin(a):.1f}" r="{w / 2 + 2.5:.1f}" fill="#FFD27A" '
                   f'stroke="#2B1747" stroke-width="2"><title>RBI minimum {mn:.0%}</title></circle>')
    return (f'<div class="gauge"><svg viewBox="0 0 210 210"><defs><linearGradient id="g1" x1="0" x2="1" y1="0" y2="1">'
            f'<stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#C8B2FF"/></linearGradient>'
            f'<linearGradient id="g2" x1="0" x2="1" y1="1" y2="0"><stop offset="0" stop-color="#9EF2C8"/><stop offset="1" stop-color="#5FD6A0"/>'
            f'</linearGradient></defs>{"".join(out)}</svg><div class="ctr"><span class="ky"><i style="background:#E7DCFF"></i>CRAR</span>'
            f'<span class="ky"><i style="background:#7FE3B4"></i>Tier 1</span><span class="ky"><i style="background:#FFD27A;border-radius:50%"></i>Minimum</span></div></div>')


def _count(value: float, dp: int = 0, prefix: str = "", suffix: str = "") -> str:
    """Final value as text (works without JS); the component animates it up from zero."""
    txt = f"{prefix}{value:,.{dp}f}{suffix}"
    return f'<span data-count="{value}" data-dp="{dp}" data-prefix="{escape(prefix)}" data-suffix="{escape(suffix)}">{escape(txt)}</span>'


def spark_bars(values, colors, w=118, h=40, title=""):
    """Tiny bar chart for a KPI tile (values >= 0)."""
    vals = [abs(v) for v in values] or [0]
    mx = max(vals) or 1
    n = len(vals)
    bw = (w - (n - 1) * 3) / n
    bars = "".join(f'<rect x="{i * (bw + 3):.1f}" y="{h - max(v / mx * h, 2):.1f}" width="{bw:.1f}" height="{max(v / mx * h, 2):.1f}" rx="2.5" '
                   f'fill="{colors[i % len(colors)]}" style="animation:growy .9s cubic-bezier(.2,.75,.2,1) {.2 + i * .05:.2f}s both;'
                   f'transform-box:fill-box;transform-origin:bottom"/>' for i, v in enumerate(vals))
    return f'<svg class="spark" width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-label="{escape(title)}">{bars}</svg>'


def _tile(icon, g1, g2, label, val_html, unit, meter, foot, trend, tbg, tfg, d, search, drill=None, spark=""):
    dd = f' data-drill="{drill}"' if drill else ""
    return (f'<div class="card tile c3" style="--d:{d}s;--glow:{g1}"{dd} data-search="{escape(search)}">'
            f'<div class="top"><span class="ico" style="background:linear-gradient(135deg,{g1},{g2});--sh:{g1}55">{ic(icon, 22)}</span>'
            f'<span class="trend" style="background:{tbg};color:{tfg}">{escape(trend)}</span></div>'
            f'<div class="lbl">{escape(label)}</div><div class="vrow"><div class="val">{val_html}<small>{escape(unit)}</small></div>{spark}</div>'
            f'<div class="meter"><i style="--w:{max(min(meter, 1), .02) * 100:.1f}%;--grad:linear-gradient(90deg,{g1},{g2});--d:{d + .2:.2f}s"></i></div>'
            f'<div class="foot">{escape(foot)}</div></div>')


def _initials(name: str) -> str:
    w = [x for x in name.replace("(", " ").replace("-", " ").split() if x[:1].isalpha()]
    return (w[0][0] + (w[1][0] if len(w) > 1 else w[0][1:2])).upper() if w else "•"


LOGO = {"Interpretation": ("#4F2D7F", "#7B4FC4"), "Data": ("#B5651D", "#E09A3E"), "Evidence": ("#127F73", "#3CB5A6"),
        "Completeness": ("#1D6FA5", "#4FA3D9"), "Governance": ("#2B2F3A", "#596173"), "Classification": ("#6B3FB8", "#A276E8")}


def build(run, rag_stats: dict | None = None, kb_hits: list | None = None) -> tuple[str, dict]:
    r, m = run.final, run.minimums
    total = r.tier1 + r.tier2
    req, req_t1 = m["crar"] * r.total_rwa, m["tier1"] * r.total_rwa
    ok = r.crar >= m["crar"] and r.tier1_ratio >= m["tier1"]
    open_ex = [e for e in run.exceptions if e.status == "OPEN"]
    hi = [e for e in open_ex if e.severity in ("Critical", "High")]
    passed = sum(c.status == "PASS" for c in run.checks + run.control_checks)
    nchk = len(run.checks + run.control_checks)
    status_label = ("Management-ready — human approval recorded" if run.status.startswith("MANAGEMENT-READY")
                    else "Blocked — evidence/control gate failed" if run.status.startswith("BLOCKED")
                    else "Calculated draft — human approval pending")
    bench = run.benchmark
    tie = sum(b["status"] == "PASS" for b in bench)
    date = f"{run.ds.reporting_date:%d %b %Y}"
    layer = "Middle Layer" if run.layer == "ML" else "Upper Layer"
    kb = rag_stats or {}
    started = run.started.replace("T", " ")[:16]

    # ------------------------------------------------ command bar
    alerts = "".join(
        f'<div class="mi" data-nav="t06_exceptions"><span class="dot" style="background:{SEV.get(e.severity)}"></span>'
        f'<span style="min-width:0"><b>{escape(_short(e.title, 40))}</b><small>{escape(e.severity)} · '
        f'{escape(CAT.get(e.category, e.category))}</small></span>'
        f'<small class="num">{(f"{e.impact_crar_bps:+.0f} bps") if e.scenario_overrides else ""}</small></div>' for e in hi[:8])
    topbar = f"""
<header class="tb"><div class="brand"><span class="mark">GT</span><div><div class="f">GRANT THORNTON</div>
 <div class="n">Capital Command Centre</div></div></div>
 <label class="search">{ic("search")}<input id="q" type="text" autocomplete="off"
  placeholder="Search everything · Enter asks the agent"><span id="qcount"></span><kbd>Ctrl K</kbd></label>
 <div class="tr"><div class="clock"><b id="clock">--:--</b><span>Run {escape(started)}</span></div>
  <div style="position:relative"><button class="iconbtn" id="bell" title="Alerts">{ic("bell")}<span class="badge">{len(hi)}</span></button>
   <div class="menu" id="bellmenu"><div class="mh">HIGH-PRIORITY ITEMS · {len(hi)}</div>{alerts or '<div class="mi">Nothing high priority.</div>'}</div></div>
  <button class="iconbtn" id="theme" title="Day / night"><span class="i-sun">{ic("sun")}</span><span class="i-moon" style="display:none">{ic("moon")}</span></button>
  <span class="avatar" title="Grant Thornton">GT</span></div></header>"""

    # ------------------------------------------------ hero + run status
    whole = f"{r.crar * 100:.2f}"
    hero = f"""
<section class="hero c8"><div class="orb o1"></div><div class="orb o2"></div><div class="mesh"></div>
 <div><span class="eyebrow"><span class="pulse"></span>Engine verified · {tie}/{len(bench)} benchmark metrics tie out</span>
  <div class="h1">Capital to risk-weighted assets (CRAR) · as at {escape(date)}</div>
  <div class="huge">{_count(r.crar * 100, 2)}<span class="pct">%</span></div>
  <div class="gbs"><span class="gb {'ok' if ok else ''}">{'✓ Compliant with RBI minimums' if ok else '⚠ Below an RBI minimum'}</span>
   <span class="gb">+{(r.crar - m['crar']) * 100:.2f} pp above the {m['crar']:.0%} floor</span>
   <span class="gb">Tier 1 {r.tier1_ratio:.2%} vs {m['tier1']:.0%}</span>
   <span class="gb">{escape(run.entity_type)} · {escape(layer)}</span></div></div>
 {_gauge(r.crar, r.tier1_ratio, m['crar'], m['tier1'])}</section>"""
    circ = 2 * math.pi * 40
    status = f"""
<section class="card c4" style="--d:.08s"><div class="hd"><div><div class="t">Run status</div><div class="s">This calculation, end to end</div></div>
 <span class="chip" style="color:#2E8B5E">{ic("lock", 13)} Offline</span></div>
 <div style="display:flex;gap:18px;align-items:center">
  <div class="ring2"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="none" stroke="var(--track)" stroke-width="10"/>
   <circle class="ring" cx="50" cy="50" r="40" fill="none" stroke="#2E8B5E" stroke-width="10" stroke-linecap="round"
    stroke-dasharray="{circ:.2f}" style="--c:{circ:.2f};stroke-dashoffset:{circ * (1 - passed / max(nchk, 1)):.2f}"/></svg>
   <div class="c"><div><b>{passed}/{nchk}</b><small>checks pass</small></div></div></div>
  <div style="min-width:0"><div class="t" style="font-size:13.5px">{status_label}</div>
   <div class="s">{len(open_ex)} open items · {len(hi)} high priority</div>
   <div class="s mono" style="margin-top:8px">{escape(run.run_id)}</div></div></div>
 <div class="kv"><span class="k">Benchmark tie-out</span><span class="v" style="color:#2E8B5E">{tie}/{len(bench)} ✓</span>
  <span class="k">Rule library</span><span class="v">{escape(run.rules.version)} · {len(run.rules.rules)} rules</span>
  <span class="k">RBI knowledge base</span><span class="v">{kb.get('documents', 0)} docs · {kb.get('chunks_current', 0):,} paras</span>
  <span class="k">Basel III lens · CET1</span><span class="v" style="color:#2E8B5E">{run.basel3["ratios"]["cet1"]:.2%} vs {run.basel3["required"]["cet1"]:.1%}</span>
  <span class="k">Reasoning mode</span><span class="v">Deterministic · no LLM</span></div></section>"""

    # ------------------------------------------------ KPI tiles
    cap_rwa = total / m["crar"]
    t2s = r.tier2_gp_eligible / r.gp_gross if r.gp_gross else 0
    cap_lines = [a for a in run.cap_applied if a.applied in ("T1_INCLUDE", "T1_DEDUCT") and abs(a.cls.amount) > 1]
    sp_t1 = spark_bars([a.cls.amount for a in cap_lines], ["#7B4FC4" if a.applied == "T1_INCLUDE" else "#E0567A" for a in cap_lines], title="Tier 1 components")
    sp_t2 = spark_bars([r.gp_gross, r.gp_cap, r.tier2], ["#C9B8E0", "#8E5FD8", "#4F2D7F"], w=70, title="Provision, cap, counted")
    top_rw = sorted(run.rwa_applied, key=lambda a: -a.exposure * a.applied)[:6]
    sp_rwa = spark_bars([a.exposure * a.applied for a in top_rw], ["#3D2B8C", "#5B4FC8", "#7B70DC", "#9A92E4", "#B9B3EC", "#D3CFF3"], title="Largest exposures")
    sevs_ = ["Critical", "High", "Medium", "Low"]
    sp_rev = spark_bars([sum(e.severity == s_ for e in open_ex) for s_ in sevs_], [SEV[s_] for s_ in sevs_], w=70, title="By priority")
    tiles = "".join([
        _tile("shield", "#6B3FB8", "#9B6BEB", "Tier 1 capital", _count(r.tier1, 0, "₹"), " L", r.tier1 / total,
              f"{r.tier1 / total:.0%} of total capital", "Core", "rgba(123,79,196,.12)", "#7B4FC4", .12, "tier 1 capital equity reserves", "cc-t1", sp_t1),
        _tile("layers", "#A276E8", "#D1B7FA", "Tier 2 capital", _count(r.tier2, 0, "₹"), " L", t2s,
              f"{t2s:.0%} of provision counted", "Capped", "rgba(162,118,232,.14)", "#8E5FD8", .18, "tier 2 capital provisions ecl cap", "cc-t2", sp_t2),
        _tile("scale", "#3D2B8C", "#6E64D8", "Risk-weighted assets", _count(r.total_rwa, 0, "₹"), " L", r.total_rwa / cap_rwa,
              f"capacity at the {m['crar']:.0%} floor", f"{r.total_rwa / cap_rwa:.0%} used", "rgba(110,100,216,.14)", "#5B4FC8", .24,
              "rwa risk weighted assets", "cc-rwa", sp_rwa),
        _tile("flag", "#E28A1C", "#F5BE5C", "Items for review", _count(len(open_ex)), "", len(hi) / max(len(open_ex), 1),
              f"{len(hi)} high priority", f"{len(hi)} high", "rgba(226,138,28,.14)", "#C7781A", .3, "review exceptions open items", "cc-rev", sp_rev),
    ])

    # ------------------------------------------------ scene + judgement calls
    scene = f"""
<section class="card scene-card c7" style="--d:.34s" data-search="capital held required tier 1 tier 2 isometric">
 <div class="hd"><div><div class="t">Capital held vs RBI requirement</div><div class="s">Isometric view · ₹ lakhs</div></div>
  <span style="display:flex;gap:6px;flex-wrap:wrap"><span class="chip">■ Tier 1</span><span class="chip" style="color:#8E5FD8">■ Tier 2</span>
  <span class="chip">⬚ Required</span></span></div>
 <div class="scene-wrap">{capital_scene(r.tier1, r.tier2, req, req_t1)}</div></section>"""
    imp = sorted([e for e in open_ex if e.scenario_overrides], key=lambda e: -abs(e.impact_crar_bps))
    mx = max((abs(e.impact_crar_bps) for e in imp), default=1) or 1
    upside = (run.agent_view.crar - r.crar) * 1e4
    drows = "".join(
        f'<span class="nm" title="{escape(e.title)}">{escape(_short(e.title, 32))}</span>'
        f'<span class="bp" style="color:{SEV.get(e.severity)}">{e.impact_crar_bps:+.0f}</span>'
        f'<span class="trk"><i style="--w:{abs(e.impact_crar_bps) / mx * 100:.0f}%;--c:{SEV.get(e.severity)};--d:{.5 + i * .12:.2f}s"></i></span>'
        for i, e in enumerate(imp[:7]))
    dark = f"""
<section class="dark c5" style="--d:.4s" data-search="judgement calls at stake bps interpretation">
 <div class="hd" style="margin-bottom:6px"><div><div class="t">Judgement calls at stake</div>
  <div class="s">CRAR impact if each alternative reading is accepted</div></div><span class="chip">bps</span></div>
 <div class="big">{_count(upside, 0, "+" if upside >= 0 else "")}<small>bps</small></div>
 <div class="s" style="margin-top:2px">if every agent reading is accepted</div>
 <div class="rw">{drows or '<span class="nm">Nothing open.</span>'}</div>
 <div class="s" style="margin-top:16px">Reported figures change only after a signed SME decision.</div></section>"""

    # ------------------------------------------------ analytics tabs
    steps = []
    for a in run.cap_applied:
        if a.applied in ("T1_INCLUDE", "T1_DEDUCT") and abs(a.cls.amount) > 0.005:
            steps.append((a.cls.label, a.cls.amount if a.applied == "T1_INCLUDE" else -abs(a.cls.amount), "x"))
    steps += [("Tier 1 capital", r.tier1, "total"), ("Tier 2 (capped)", r.tier2, "x"), ("Total capital", total, "total")]
    grp = {"Loans": 0.0, "Receivables": 0.0, "Other": 0.0}
    for a in run.rwa_applied:
        v = a.exposure * a.applied
        lb = a.cls.label.lower()
        key = "Loans" if a.cls.label == "Loans" else ("Receivables" if any(t in lb for t in ("receivable", "deposit", "advance", "gateway")) else "Other")
        grp[key] += v
    grp["Derivatives"] = r.rwa_ccr
    parts = [(k, v, c) for (k, v), c in zip(grp.items(), [P, P_VIOLET, "#B9A8D9", "#E2D8F3"])]
    tot = sum(v for _, v, _ in parts) or 1
    leg = "".join(f'<span class="sw" style="background:{c}"></span><span>{escape(k)}</span><span class="pc">{v / tot:.1%}</span>' for k, v, c in parts)
    comp_rows = "".join(
        f'<tr data-search="{escape(a.cls.label.lower())}"><td>{escape(_short(a.cls.label, 34))}</td>'
        f'<td><span class="tag" style="background:{"rgba(46,139,94,.12);color:#2E8B5E" if a.applied == "T1_INCLUDE" else ("rgba(214,69,96,.12);color:#D64560" if a.applied == "T1_DEDUCT" else "var(--chip);color:var(--mut)")}">'
        f'{escape({"T1_INCLUDE": "Included", "T1_DEDUCT": "Deducted", "T2_GENERAL_PROVISION": "Tier 2", "T1_EXCLUDE": "Excluded"}.get(a.applied, a.applied))}</span></td>'
        f'<td class="r">{a.cls.amount:,.2f}</td><td class="mono">{escape(a.cls.rule_id or "")}</td>'
        f'<td>{"Auto" if a.cls.route == "AUTO_ACCEPT" else "Review"}</td></tr>' for a in run.cap_applied)
    analytics = f"""
<section class="card c7" style="--d:.46s" data-tabs>
 <div class="hd"><div><div class="t">Capital analytics</div><div class="s">From equity to regulatory capital and risk</div></div>
  <div class="tabs"><button class="on" data-tab="bridge">Bridge</button><button data-tab="mix">RWA mix</button><button data-tab="comp">Components</button></div></div>
 <div class="panes"><div class="pane on" data-pane="bridge">{waterfall(steps)}</div>
 <div class="pane" data-pane="mix"><div style="display:flex;align-items:center;gap:28px;padding:10px 0 4px">{donut(parts, 180)}
  <div class="cx-leg" style="flex:1;min-width:0;font-size:13px;row-gap:12px">{leg}</div></div>
  <div class="kv"><span class="k">Total RWA</span><span class="v">{_l(r.total_rwa)} L</span><span class="k">Counterparty (derivatives) RWA</span>
  <span class="v">{_l(r.rwa_ccr)} L</span></div></div>
 <div class="pane" data-pane="comp"><div class="tblw"><table class="cmp"><thead><tr><th>Component</th><th>Treatment</th><th class="r">₹ lakhs</th>
  <th>Rule</th><th>Route</th></tr></thead><tbody>{comp_rows}</tbody></table></div></div></div></section>"""

    # ------------------------------------------------ what-if slider
    loans = next(a for a in run.rwa_applied if a.cls.label == "Loans")
    xs = list(range(50, 155, 5))
    sims = [run._compute({"rwa": {loans.cls.item_id: x / 100}}) for x in xs]
    crars = [s.crar * 100 for s in sims]
    t1s = [s.tier1_ratio * 100 for s in sims]
    lo, hi_ = 0.0, (int(max(crars) // 10) + 1) * 10
    px = lambda x: (x - 50) / 100 * 100
    py = lambda y: (hi_ - y) / (hi_ - lo) * 100
    path = _smooth([(px(x), py(y)) for x, y in zip(xs, crars)])
    cur = round(loans.applied * 100 / 5) * 5
    grid = "".join(f'<span class="gl" style="top:{py(t):.1f}%"></span><span class="yl" style="top:{py(t):.1f}%">{t}%</span>'
                   for t in range(0, int(hi_) + 1, 10))
    whatif = f"""
<section class="card c5" style="--d:.52s" data-search="what if loan risk weight slider sensitivity crar">
 <div class="hd"><div><div class="t">Live what-if</div><div class="s">Drag the loan risk weight — the engine's curve updates instantly</div></div>
  <button class="btn" data-nav="t15_whatif">Full simulator {ic("arrow", 14)}</button></div>
 <div class="wi-big"><b id="wiCrar">{r.crar:.2%}</b><span class="chip" id="wiStatus" style="color:#2E8B5E">Compliant</span>
  <span class="mut num" id="wiDelta" style="font-size:12.5px">±0 bps vs reported</span></div>
 <div class="wi-plot">{grid}<svg viewBox="0 0 100 100" preserveAspectRatio="none">
  <line x1="0" x2="100" y1="{py(m['crar'] * 100):.2f}" y2="{py(m['crar'] * 100):.2f}" stroke="#D64560" stroke-width="1.2" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>
  <path d="{path}" fill="none" stroke="#4F2D7F" stroke-width="2.6" vector-effect="non-scaling-stroke"/></svg>
  <span class="wi-vl" id="wiVl" style="left:{px(cur):.1f}%"></span><span class="wi-dot" id="wiDot" style="left:{px(cur):.1f}%;top:{py(r.crar * 100):.1f}%"></span></div>
 <div class="wi-x"><span>50%</span><span>75%</span><span>100%</span><span>125%</span><span>150%</span></div>
 <input type="range" id="rw" min="50" max="150" step="5" value="{cur}" style="--p:{px(cur):.1f}%">
 <div class="wi-stats"><div><small>Loan risk weight</small><b id="wiRw">{cur}%</b></div><div><small>Tier 1 ratio</small><b id="wiT1">{r.tier1_ratio:.2%}</b></div>
  <div><small>Headroom</small><b id="wiHead">{(r.crar - m['crar']) * 100:+.2f} pp</b></div></div></section>"""

    # ------------------------------------------------ review queue
    rows = []
    for i, e in enumerate(open_ex):
        nm = _short(e.title, 36)
        cat = CAT.get(e.category, e.category)
        g1, g2 = LOGO.get(cat, (P, P_VIOLET))
        imp_v = e.impact_crar_bps if e.scenario_overrides else 0
        col = "#2E8B5E" if imp_v > 0 else ("#D64560" if imp_v < 0 else "var(--faint)")
        rows.append(f'<tr data-nav="t06_exceptions" data-sev="{escape(e.severity)}" data-cat="{escape(cat)}" data-impact="{abs(imp_v):.1f}" '
                    f'data-search="{escape((e.title + " " + e.category + " " + e.severity).lower())}" style="--d:{.55 + min(i, 10) * .05:.2f}s">'
                    f'<td><div class="itm"><span class="logo" style="background:linear-gradient(135deg,{g1},{g2})">{escape(_initials(nm))}</span>'
                    f'<span title="{escape(e.title)}">{escape(nm)}</span></div></td><td>{escape(cat)}</td>'
                    f'<td><span class="st"><i class="dot" style="background:{SEV.get(e.severity)}"></i>{escape(e.severity)}</span></td>'
                    f'<td class="num" style="font-weight:650;color:{col}">{(f"{imp_v:+.0f} bps") if e.scenario_overrides else "—"}</td>'
                    f'<td><span class="st"><i class="dot" style="background:#D48B12"></i>Open</span></td></tr>')
    queue = f"""
<section class="card c8" style="--d:.58s"><div class="hd"><div><div class="t">Review queue</div>
 <div class="s"><span id="rqn">{len(open_ex)}</span> open items · click a row to open the exception queue</div></div>
 <div class="flt"><button class="btn on" data-filter="all">All</button><button class="btn" data-filter="High">High</button>
  <button class="btn" data-filter="Data">Data</button><button class="btn" data-filter="Evidence">Evidence</button>
  <button class="btn" id="sortbtn" title="Sort by CRAR impact">{ic("sort", 14)} Impact</button></div></div>
 <div class="tblw"><table class="rq"><thead><tr><th>Item</th><th>Category</th><th>Priority</th><th>CRAR impact</th><th>Status</th></tr></thead>
 <tbody id="rqb">{''.join(rows) or '<tr><td colspan="5">Nothing open — ready for checker sign-off.</td></tr>'}</tbody></table></div>
 <div style="text-align:center;margin-top:14px"><button class="btn" id="rqmore">Show all items</button></div></section>"""

    # ------------------------------------------------ heat map
    sevs = ["Critical", "High", "Medium", "Low"]
    counts = {(s, c): 0 for s in sevs for c in CATS}
    for e in open_ex:
        cat = CAT.get(e.category, e.category)
        if (e.severity, cat) in counts:
            counts[(e.severity, cat)] += 1
    mxc = max(counts.values()) or 1
    base = {"Critical": (142, 27, 58), "High": (224, 86, 122), "Medium": (240, 169, 59), "Low": (169, 166, 179)}
    short = {"Interpretation": "Interp.", "Data": "Data", "Evidence": "Evid.", "Completeness": "Compl.", "Governance": "Gov.",
             "Classification": "Class."}
    cells = '<span></span>' + "".join(f'<span class="h" title="{c}">{short[c]}</span>' for c in CATS)
    k = 0
    for s in sevs:
        cells += f'<span class="r">{s}</span>'
        for c in CATS:
            n = counts[(s, c)]
            rr, gg, bb = base[s]
            alpha = 0.08 + 0.85 * (n / mxc) if n else 0.05
            fg = "#fff" if n and alpha > .45 else "var(--ink)"
            cells += (f'<span class="cell" title="{s} · {c}: {n}" style="--d:{.6 + k * .02:.2f}s;background:rgba({rr},{gg},{bb},{alpha:.2f});'
                      f'color:{fg}">{n or ""}</span>')
            k += 1
    cat_n = {}
    for e in open_ex:
        k_ = CAT.get(e.category, e.category)
        cat_n[k_] = cat_n.get(k_, 0) + 1
    mxn = max(cat_n.values(), default=1)
    cat_bars = "".join(
        f'<div style="display:grid;grid-template-columns:110px minmax(0,1fr) 26px;gap:10px;align-items:center;margin-top:9px;font-size:12px">'
        f'<span class="mut">{escape(k_)}</span><span class="meter" style="margin:0;height:7px"><i style="--w:{v / mxn * 100:.0f}%;'
        f'--grad:linear-gradient(90deg,{LOGO.get(k_, (P, P_VIOLET))[0]},{LOGO.get(k_, (P, P_VIOLET))[1]});--d:{.6 + i * .06:.2f}s"></i></span>'
        f'<b class="num" style="text-align:right">{v}</b></div>' for i, (k_, v) in enumerate(sorted(cat_n.items(), key=lambda x: -x[1])))
    heat = f"""
<section class="card c4 last" style="--d:.62s" data-search="risk heat map severity category"><div class="hd"><div><div class="t">Risk heat map</div>
 <div class="s">Open items by priority and category</div></div><span class="chip">{len(open_ex)} items</span></div>
 <div class="hm">{cells}</div>
 <div class="s" style="margin-top:12px">Darker = more items. Hover a cell for the count.</div>
 <div style="margin-top:18px;padding-top:14px;border-top:1px solid var(--line)"><div class="t" style="font-size:13px">Open items by category</div>
 {cat_bars}</div></section>"""

    # ------------------------------------------------ bottom row: activity, quality, RBI
    auto = sum(a.cls.route == "AUTO_ACCEPT" for a in run.cap_applied + run.rwa_applied)
    allc = len(run.cap_applied + run.rwa_applied)
    events = [("Workbook ingested", f"{len(run.ds.sheet_map)} sheets recognised by their headers"),
              ("Validated against source", f"{passed} of {nchk} tie-outs pass"),
              ("RBI text retrieved", f"{kb.get('chunks_current', 0):,} paragraphs in force on {date}"),
              ("Items classified", f"{auto} of {allc} auto-accepted with citations"),
              ("Capital computed", f"CRAR {r.crar:.2%} · benchmark {tie}/{len(bench)}"),
              ("Awaiting SME review", f"{len(open_ex)} items · {len(hi)} high priority")]
    tl = "".join(f'<div class="ev{" now" if i == len(events) - 1 else ""}" style="--d:{.65 + i * .15:.2f}s"><div class="a">{escape(a)}</div>'
                 f'<div class="b">{escape(b)}</div></div>' for i, (a, b) in enumerate(events))
    activity = f"""<section class="card c4" style="--d:.66s" data-search="agent activity timeline"><div class="hd"><div><div class="t">Agent activity</div>
 <div class="s">This run, step by step</div></div><span class="chip" style="color:#2E8B5E">● Live</span></div><div class="tl">{tl}</div></section>"""
    srt = sorted(run.checks, key=lambda c: c.status == "PASS")
    segs = "".join(f'<i title="{escape(c.check_id)}: {escape(c.status)}" style="background:{"#2E8B5E" if c.status == "PASS" else ("#D48B12" if c.status == "WARN" else "#D64560")};'
                   f'--d:{.7 + i * .02:.2f}s"></i>' for i, c in enumerate(srt))
    bad = [c for c in run.checks + run.control_checks if c.status != "PASS"][:4]
    chk = "".join(f'<div class="chk" data-search="{escape((c.check_id + " " + c.description).lower())}"><span class="id">{escape(c.check_id.split("-")[0])}</span>'
                  f'<span class="ds" title="{escape(c.description)}">{escape(c.description)}</span>'
                  f'<span class="tag" style="background:{"rgba(214,69,96,.12);color:#D64560" if c.status == "FAIL" else "rgba(212,139,18,.14);color:#C27C10"}">{escape(c.status.title())}</span></div>'
                  for c in bad)
    quality = f"""<section class="card c4" style="--d:.7s" data-search="data quality validation checks"><div class="hd"><div><div class="t">Data quality</div>
 <div class="s">Source tie-outs, failures first</div></div><span class="chip num">{passed}/{nchk}</span></div>
 <div class="seg">{segs}</div><div class="s" style="margin-bottom:6px">{passed} pass · {sum(c.status == 'FAIL' for c in run.checks + run.control_checks)} fail · {sum(c.status == 'WARN' for c in run.checks + run.control_checks)} warn</div>{chk}</section>"""
    cites = "".join(f'<div class="cite" data-search="{escape((h["para"] + " " + h["title"] + " " + h["text"]).lower()[:400])}">'
                    f'<b><span class="p">para {escape(h["para"])}</span>{escape(h.get("heading") or h["title"][:46])}</b><div>{escape(h["text"][:150])}…</div></div>'
                    for h in (kb_hits or [])[:3])
    rbi = f"""<section class="card c4 last" style="--d:.74s" data-search="rbi knowledge base paragraphs citations"><div class="hd"><div><div class="t">RBI knowledge base</div>
 <div class="s">Paragraphs behind today's judgement calls</div></div><button class="btn" data-nav="t13_rbi_knowledge">Library {ic("arrow", 14)}</button></div>
 {cites or '<div class="s">Load RBI text on the RBI library page.</div>'}</section>"""

    sbar = f"""<footer class="sbar"><span class="lock">{ic("lock", 14)} Offline · no LLM · no API</span>
 <span>Engine <b>deterministic</b></span><span>Rules <b>{escape(run.rules.version)}</b></span><span>KB <b>{escape(run.kb.version)}</b></span>
 <span>Framework <b>{escape(run.rules.framework)}</b></span><span class="grow"></span><span class="mono">{escape(run.run_id)}</span></footer>"""

    from .page_kit import EXTRA_CSS, boxes, drill
    inc = [a for a in run.cap_applied if a.applied == "T1_INCLUDE"]
    ded = [a for a in run.cap_applied if a.applied == "T1_DEDUCT"]
    li = lambda xs: "".join(f'<div class="ov-q"><b>{escape(_short(a.cls.label, 50))}</b> · {"−" if a.cls.amount < 0 else ""}₹{abs(a.cls.amount):,.2f} L</div>' for a in xs)
    top_rwa = sorted(run.rwa_applied, key=lambda a: -a.exposure * a.applied)[:6]
    sev_n = {s_: sum(e.severity == s_ for e in open_ex) for s_ in ("Critical", "High", "Medium", "Low")}
    tpls = (drill("cc-t1", "Tier 1 capital", f"₹{r.tier1:,.2f} lakhs · {r.tier1_ratio:.2%} of RWA (minimum {m['tier1']:.0%})",
                  boxes([("Included", f"₹{sum(a.cls.amount for a in inc):,.2f} L"), ("Deducted", f"−₹{sum(abs(a.cls.amount) for a in ded):,.2f} L"),
                         ("Share of total capital", f"{r.tier1 / total:.1%}"), ("Surplus over Tier 1 minimum", f"₹{r.tier1 - req_t1:,.0f} L")])
                  + '<div class="ov-p"><b>Included</b></div>' + li(inc) + '<div class="ov-p"><b>Deducted</b></div>' + li(ded)
                  + '<div class="ov-p"><button class="btn" data-nav="t02_tier1">Open the Tier 1 page →</button></div>')
            + drill("cc-t2", "Tier 2 capital", "General provisions, capped at 1.25% of RWA",
                    boxes([("Stage 1 ECL", f"₹{r.gp_gross:,.2f} L"), ("Cap (1.25% × RWA)", f"₹{r.gp_cap:,.2f} L"),
                           ("Counted", f"₹{r.tier2:,.2f} L"), ("Not counted", f"₹{r.gp_gross - r.tier2_gp_eligible:,.2f} L")])
                    + '<div class="ov-p">The provision exceeds the cap, so only part of it counts. The cap grows with RWA.</div>'
                    + '<div class="ov-p"><button class="btn" data-nav="t03_tier2">Open the Tier 2 page →</button></div>')
            + drill("cc-rwa", "Risk-weighted assets", f"₹{r.total_rwa:,.2f} lakhs · {r.total_rwa / cap_rwa:.0%} of capacity at the {m['crar']:.0%} floor",
                    boxes([("On-balance-sheet", f"₹{r.rwa_credit_on_bs:,.2f} L"), ("Derivatives (CEM)", f"₹{r.rwa_ccr:,.2f} L"),
                           ("Capacity at minimum CRAR", f"₹{cap_rwa:,.0f} L"), ("Room to grow", f"+{cap_rwa / r.total_rwa - 1:.0%}")])
                    + '<div class="ov-p"><b>Largest exposures</b></div>'
                    + "".join(f'<div class="ov-q"><b>{escape(_short(a.cls.label, 40))}</b> · ₹{a.exposure:,.0f} L × {a.applied:.0%} = ₹{a.exposure * a.applied:,.0f} L</div>' for a in top_rwa)
                    + '<div class="ov-p"><button class="btn" data-nav="t04_rwa">Open the RWA page →</button></div>')
            + drill("cc-rev", "Items for review", f"{len(open_ex)} open · decide the largest CRAR impacts first",
                    boxes([(k, str(v)) for k, v in sev_n.items()])
                    + "".join(f'<div class="ov-q"><b>{escape(_short(e.title, 50))}</b> · {e.severity}'
                              + (f' · {e.impact_crar_bps:+.0f} bps' if e.scenario_overrides else '') + '</div>' for e in open_ex[:8])
                    + '<div class="ov-p"><button class="btn" data-nav="t06_exceptions">Open the exception queue →</button></div>'))
    html = (CSS + EXTRA_CSS + f'<div id="cc" data-theme="light">{topbar}<main class="g">{hero}{status}{tiles}{scene}{dark}{analytics}{whatif}'
            f'{queue}{heat}{activity}{quality}{rbi}</main>{sbar}{tpls}</div>')
    data = {"xs": xs, "crar": crars, "t1": t1s, "lo": lo, "hi": hi_, "min": m["crar"] * 100, "min_t1": m["tier1"] * 100,
            "reported": r.crar * 100}
    return html, data


def kb_hits(rag, run, open_ex):
    """RBI paragraphs behind the top judgement calls."""
    hits, seen = [], set()
    queries = [e.title.split(":")[0] for e in open_ex[:5]] + ["statutory reserve common equity", "consumer credit risk weight"]
    for q in queries:
        for h in rag.search(q, k=1, as_of=run.ds.reporting_date, frameworks=["NBFC"]):
            if h.chunk_id not in seen:
                seen.add(h.chunk_id)
                hits.append({"para": h.para, "title": h.title, "heading": h.heading, "text": h.text})
        if len(hits) >= 3:
            break
    return hits
