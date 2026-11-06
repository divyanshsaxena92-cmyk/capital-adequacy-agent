"""One-page management memo (self-contained HTML; open in a browser and Print -> Save as PDF)."""
from __future__ import annotations

import datetime as dt
from html import escape

from . import ledger, rbi_brain


def build(run, rag=None, prepared_by: str = "") -> bytes:
    r, m = run.final, run.minimums
    ok = r.crar >= m["crar"] and r.tier1_ratio >= m["tier1"]
    led = ledger.build(run)
    open_ex = [e for e in run.exceptions if e.status == "OPEN"]
    impact = sorted([e for e in open_ex if e.scenario_overrides], key=lambda e: -abs(e.impact_crar_bps))[:8]
    b3 = getattr(run, "basel3", None)
    as_of = str(run.ds.reporting_date)
    applied, newer = [], []
    if rag is not None:
        for c in rbi_brain.catalogue(rag):
            if c["kind"] in ("draft",):
                continue
            row = (c["official_title"] or ("Curated summary (not an RBI document)" if c["kind"] == "curated" else c["our_label"]),
                   c["ref_no"] or "—", c["rbi_type"], c["in_force_from"])
            if c["in_force_from"] <= as_of and (not c["in_force_to"] or c["in_force_to"] > as_of):
                applied.append(row)
            elif c["in_force_from"] > as_of:
                newer.append(row)
    tr = lambda cells: "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    kf = "".join(tr([escape(k), f"<b>{escape(v)}</b>", escape(n)]) for k, v, n in (
        ("CRAR", f"{r.crar:.2%}", f"minimum {m['crar']:.0%} · headroom {(r.crar - m['crar']) * 100:+.2f} pp"),
        ("Tier 1 ratio", f"{r.tier1_ratio:.2%}", f"minimum {m['tier1']:.0%}"),
        ("Tier 1 capital", f"₹{r.tier1:,.2f} lakhs", "after deductions"),
        ("Tier 2 capital", f"₹{r.tier2:,.2f} lakhs", f"provision ₹{r.gp_gross:,.0f} L capped at 1.25% of RWA"),
        ("Risk-weighted assets", f"₹{r.total_rwa:,.2f} lakhs", f"on-balance-sheet ₹{r.rwa_credit_on_bs:,.0f} L · derivatives ₹{r.rwa_ccr:,.0f} L")))
    b3rows = "".join(tr([escape({"cet1": "CET1", "tier1": "Tier 1", "total": "Total capital", "leverage": "Leverage"}[x["metric"]]), f"{x['value']:.2%}",
                         f"{x['required']:.2%}", f"{x['headroom'] * 100:+.2f} pp"]) for x in b3["rows"]) if b3 else ""
    items = "".join(tr([escape(e.exc_id), escape(e.title.split(":")[0]), escape(e.severity), f"{e.impact_crar_bps:+.0f}"]) for e in impact)
    rbi_a = "".join(tr([escape(t), f'<span style="white-space:nowrap">{escape(ref)}</span>', escape(k.split(" (")[0].split(" -")[0]), escape(f)])
                    for t, ref, k, f in applied)
    rbi_n = "".join(tr([escape(t), f'<span style="white-space:nowrap">{escape(ref)}</span>', escape(k.split(" (")[0].split(" -")[0]), escape(f)])
                    for t, ref, k, f in newer)
    passed = sum(c.status == "PASS" for c in run.checks)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Capital adequacy memo - {escape(as_of)}</title>
<style>
@page {{ size: A4; margin: 14mm; }}
body {{ font-family: "Segoe UI", Arial, sans-serif; color: #1E1B24; font-size: 11.5px; line-height: 1.45; max-width: 820px; margin: 24px auto; }}
.top {{ display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 3px solid #4F2D7F; padding-bottom: 10px; }}
.firm {{ color: #4F2D7F; font-weight: 700; letter-spacing: .14em; font-size: 10.5px; }} h1 {{ font-size: 20px; margin: 4px 0 0; }}
.meta {{ text-align: right; color: #5F5C66; font-size: 10.5px; }}
.verdict {{ margin: 14px 0; padding: 12px 14px; border-radius: 8px; background: {"#E9F5EE" if ok else "#FBE9ED"};
           border-left: 4px solid {"#2E8B5E" if ok else "#C23B57"}; font-size: 13px; }}
h2 {{ font-size: 12.5px; color: #4F2D7F; text-transform: uppercase; letter-spacing: .08em; margin: 18px 0 6px; }}
table {{ width: 100%; border-collapse: collapse; }} td, th {{ padding: 5px 6px; border-bottom: 1px solid #E6E2EC; text-align: left; vertical-align: top; }}
th {{ font-size: 10px; color: #6B6878; text-transform: uppercase; letter-spacing: .05em; }}
.two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }} .muted {{ color: #6B6878; }}
.sign {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 26px; }}
.sign div {{ border-top: 1px solid #1E1B24; padding-top: 6px; font-size: 10.5px; }}
.draft {{ color: #B4364E; font-weight: 700; }}
</style></head><body>
<div class="top"><div><div class="firm">GRANT THORNTON</div><h1>Capital adequacy — management summary</h1>
<div class="muted">{escape(run.entity_type)} · {escape("Middle" if run.layer == "ML" else "Upper")} Layer · reporting date {run.ds.reporting_date:%d %B %Y}</div></div>
<div class="meta">Run {escape(run.run_id)}<br>Prepared {dt.datetime.now():%d %b %Y %H:%M}{(" by " + escape(prepared_by)) if prepared_by else ""}<br>
<span class="draft">{escape(run.status)}</span></div></div>
<div class="verdict"><b>{"Compliant" if ok else "Not compliant"} with RBI minimum capital requirements.</b> CRAR {r.crar:.2%} against {m['crar']:.0%};
Tier 1 ratio {r.tier1_ratio:.2%} against {m['tier1']:.0%}. {len(open_ex)} items await SME review; reported figures change only on signed decisions.</div>
<h2>Key figures</h2><table>{kf}</table>
<div class="two"><div><h2>Largest open judgement calls</h2><table><tr><th>ID</th><th>Item</th><th>Priority</th><th>bps</th></tr>{items or tr(["—", "None", "", ""])}</table></div>
<div><h2>Basel III lens ({escape(b3["framework"]) if b3 else "n/a"})</h2><table><tr><th>Ratio</th><th>Actual</th><th>Required incl. buffers</th><th>Headroom</th></tr>{b3rows}</table>
<p class="muted">For an NBFC this is a benchmark; compliance is assessed under the NBFC Directions.</p></div></div>
<h2>RBI texts applied to this run (in force on {run.ds.reporting_date:%d %b %Y})</h2>
<table><tr><th>Official RBI name</th><th>RBI reference</th><th>Type</th><th>In force from</th></tr>{rbi_a or tr(["Not recorded", "", "", ""])}</table>
{f'<h2>Newer RBI texts — not applied to this reporting date</h2><table><tr><th>Official RBI name</th><th>RBI reference</th><th>Type</th><th>In force from</th></tr>{rbi_n}</table>' if rbi_n else ''}
<h2>Controls</h2><table>
{tr(["Calculation ledger", f"{len(led['rows'])} steps; independently reproduces the engine: <b>{'yes' if led['reproduced'] else 'NO'}</b>", "CSV available"])}
{tr(["Source validation", f"{passed} of {len(run.checks)} tie-outs pass", "failures listed in the review queue"])}
{tr(["Benchmark", f"{sum(b['status'] == 'PASS' for b in run.benchmark)} of {len(run.benchmark)} metrics tie to the maker's schedule", ""])}
{tr(["Method", "Deterministic rules engine and offline RBI knowledge base; no AI model, no API, no data leaves the machine", f"rules {escape(run.rules.version)} · KB {escape(run.kb.version)}"])}
</table>
<div class="sign"><div>Prepared by (maker)</div><div>Reviewed by (checker / SME)</div><div>Approved by</div></div>
<p class="muted" style="margin-top:18px">Decision-support output. Figures are draft until the open items are decided and the checker signs off.</p>
</body></html>"""
    return html.encode("utf-8")
