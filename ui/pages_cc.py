"""Command-Centre-style pages. Each builder returns (html, data) for the local component.
All figures come from the deterministic engine; every row or tile opens a detail panel over the page."""
from __future__ import annotations

import math
from html import escape

from .command_center import CAT, SEV, ic
from .overview_html import _short, donut, waterfall
from .page_kit import (SEVC, bars, boxes, card, conf_meter, count, drill, hero, page, table, tag, tile, tornado,
                       treat_tag)

P, PV = "#4F2D7F", "#7B4FC4"


def _date(run):
    return f"As at {run.ds.reporting_date:%d %b %Y} · {run.run_id}"


def _cls_detail(a, run):
    c = a.cls
    cites = "".join(f'<div class="ov-q"><b>para {escape(x["para"])}</b> · {escape(x.get("title", ""))}'
                    + (f'<br>{escape(run.kb.get(x["id"]).text)}' if run.kb.get(x["id"]) else "") + "</div>" for x in c.citations)
    alts = "".join(f'<li>{escape(str(x.get("treatment") or ""))} {("RW " + format(x["risk_weight"], ".0%")) if x.get("risk_weight") is not None else ""}'
                   f' — {escape(x.get("basis", ""))}</li>' for x in c.alternatives)
    return (boxes([("Source amount (₹ L)", f"{c.amount:,.2f}"), ("Source cell", c.source_ref[:40]), ("Rule", c.rule_id or "—"),
                   ("Confidence", f"{c.confidence:.2f}"), ("Route", "Auto-accepted" if c.route == "AUTO_ACCEPT" else "Human review"),
                   ("Applied", str(a.applied) if not isinstance(a.applied, float) else f"RW {a.applied:.0%}")])
            + f'<div class="ov-p"><b>Why:</b> {escape(c.rationale)}</div>'
            + (f'<div class="ov-p"><b>Guardrails:</b> {escape("; ".join(c.guardrail_notes))}</div>' if c.guardrail_notes else "")
            + (f'<div class="ov-p"><b>Other readings</b><ul style="margin:6px 0 0 18px;line-height:1.6">{alts}</ul></div>' if alts else "")
            + (f'<div class="ov-p"><b>Evidence needed:</b> {escape(c.evidence_required)}</div>' if c.evidence_required else "")
            + f'<div class="ov-p"><b>Basis:</b> {escape(a.basis)}</div>' + cites)


# ------------------------------------------------------------------ Tier 1
def tier1(run):
    r, m = run.final, run.minimums
    inc = [a for a in run.cap_applied if a.applied == "T1_INCLUDE"]
    ded = [a for a in run.cap_applied if a.applied == "T1_DEDUCT"]
    exc = [a for a in run.cap_applied if a.applied == "T1_EXCLUDE"]
    rev = [a for a in run.cap_applied if a.cls.route != "AUTO_ACCEPT" and a.applied != "T2_GENERAL_PROVISION"]
    s_inc = sum(a.cls.amount for a in inc)
    s_ded = sum(abs(a.cls.amount) for a in ded)
    s_exc = sum(a.cls.amount for a in exc)
    gross = s_inc or 1
    right = (f'<div style="min-width:240px"><div class="eyebrow" style="margin-bottom:12px">Composition</div>'
             f'<div style="height:16px;border-radius:999px;overflow:hidden;display:flex;background:rgba(255,255,255,.15)">'
             f'<i style="width:{(s_inc - s_ded) / gross * 100:.1f}%;background:#fff"></i><i style="width:{s_ded / gross * 100:.1f}%;background:#F28CA0"></i></div>'
             f'<div style="display:flex;justify-content:space-between;font-size:11.5px;margin-top:8px;color:#E8DFFA">'
             f'<span>Net Tier 1</span><span>Deductions {s_ded / gross:.0%}</span></div>'
             f'<div class="gb" style="margin-top:16px;display:inline-block">Tier 1 ratio {r.tier1_ratio:.2%} · min {m["tier1"]:.0%}</div></div>')
    body = hero("Owned fund / CET1 build", "Tier 1 capital (₹ lakhs)", count(r.tier1, 2, "₹"), " L",
                [(f"{r.tier1 / (r.tier1 + r.tier2):.0%} of total capital", ""), (f"{len(inc)} included · {len(ded)} deducted", ""),
                 (f"{len(rev)} items for SME review", "")], right)
    body += card("At a glance", "Click any figure for its components", f"""<div class="kv">
 <span class="k">Included items</span><span class="v">₹{s_inc:,.2f} L</span><span class="k">Deductions</span><span class="v" style="color:#D64560">−₹{s_ded:,.2f} L</span>
 <span class="k">Excluded (not counted)</span><span class="v">₹{s_exc:,.2f} L</span><span class="k">Tier 1 minimum (10% of RWA)</span><span class="v">₹{m['tier1'] * r.total_rwa:,.0f} L</span>
 <span class="k">Surplus over Tier 1 minimum</span><span class="v" style="color:#2E8B5E">₹{r.tier1 - m['tier1'] * r.total_rwa:,.0f} L</span></div>""", "c4", d=.06)
    body += tile("shield", "#2E8B5E", "#5FC48D", "Gross inclusions", count(s_inc, 0, "₹"), " L", 1, f"{len(inc)} items", "Counted",
                 "rgba(46,139,94,.12)", "#2E8B5E", .1, "inc")
    body += tile("flag", "#C2405E", "#F08AA0", "Deductions", count(s_ded, 0, "₹"), " L", s_ded / gross, f"{s_ded / gross:.1%} of inclusions",
                 "Deducted", "rgba(214,69,96,.12)", "#D64560", .15, "ded")
    body += tile("layers", "#8C8996", "#B9B6C2", "Excluded reserves", count(s_exc, 0, "₹"), " L", min(abs(s_exc) / gross, 1),
                 f"{len(exc)} items not counted", "Not counted", "var(--chip)", "var(--mut)", .2, "exc")
    body += tile("scale", "#E28A1C", "#F5BE5C", "Under SME review", count(len(rev)), "", len(rev) / max(len(run.cap_applied), 1),
                 "interpretive / low confidence", "Review", "rgba(226,138,28,.14)", "#C7781A", .25, "rev")
    steps = [(a.cls.label, a.cls.amount if a.applied == "T1_INCLUDE" else -abs(a.cls.amount), "x")
             for a in run.cap_applied if a.applied in ("T1_INCLUDE", "T1_DEDUCT") and abs(a.cls.amount) > .005]
    steps.append(("Tier 1 capital", r.tier1, "total"))
    body += card("Tier 1 bridge", "From equity to Tier 1 capital · ₹ lakhs", waterfall(steps), "c7", d=.3)
    moves = []
    for e in run.exceptions:
        ov = e.scenario_overrides.get("capital") if e.scenario_overrides and e.status == "OPEN" else None
        if ov:
            dt1 = run._compute({"capital": ov}).tier1 - r.tier1
            moves.append((_short(e.title, 30), dt1, f"{dt1:+,.0f} L", "#2E8B5E" if dt1 > 0 else "#D64560"))
    moves.sort(key=lambda x: -abs(x[1]))
    body += card("What could move Tier 1", "If each open judgement call went the other way", bars(moves) if moves else
                 '<div class="s">Nothing open.</div>', "c5", d=.36)
    rows, tpls = [], []
    for a in run.cap_applied:
        if a.applied == "T2_GENERAL_PROVISION":
            continue
        c = a.cls
        key = f"t1-{c.item_id}"
        para = ", ".join(x["para"] for x in c.citations[:2])
        rows.append(f'<tr data-drill="{key}" data-treat="{a.applied}" data-route="{c.route}"><td><b>{escape(_short(c.label, 40))}</b></td>'
                    f'<td class="mono">{escape(c.source_ref[:26])}</td><td class="r" data-v="{c.amount}">{c.amount:,.2f}</td>'
                    f'<td>{treat_tag(a.applied)}</td><td class="mono">{escape(c.rule_id or "")}</td><td>{escape(para)}</td>'
                    f'<td data-v="{c.confidence}">{conf_meter(c.confidence)}</td><td>{"Auto" if c.route == "AUTO_ACCEPT" else tag("Review", "rgba(226,138,28,.14)", "#C7781A")}</td></tr>')
        tpls.append(drill(key, c.label, f"{c.item_id} · Tier 1 component", _cls_detail(a, run)))
    body += card("Components", "Every Tier 1 line, the rule applied and its RBI paragraph · click a row for full reasoning",
                 table("t1", [("Item", "txt", ""), ("Source", "txt", ""), ("₹ lakhs", "num", "r"), ("Treatment", "txt", ""),
                              ("Rule", "txt", ""), ("RBI para", "txt", ""), ("Confidence", "num", ""), ("Route", "txt", "")], rows,
                       [("treat", [("All", "all"), ("Included", "T1_INCLUDE"), ("Deducted", "T1_DEDUCT"), ("Excluded", "T1_EXCLUDE")]),
                        ("route", [("Any route", "all"), ("Review", "HUMAN_REVIEW"), ("Auto", "AUTO_ACCEPT")])]), "c12", d=.42)

    def lst(items):
        return "".join(f'<div class="ov-q"><b>{escape(a.cls.label)}</b> · {"−" if a.cls.amount < 0 else ""}₹{abs(a.cls.amount):,.2f} L · {escape(a.cls.rule_id or "")}</div>' for a in items) or '<div class="ov-p">None.</div>'
    tpls += [drill("inc", "Gross inclusions", f"₹{s_inc:,.2f} lakhs across {len(inc)} items", lst(inc)),
             drill("ded", "Deductions", f"₹{s_ded:,.2f} lakhs — assets that cannot absorb losses", lst(ded)),
             drill("exc", "Excluded reserves", "Reserves the rule library does not count (or counts only after SME decision)", lst(exc)),
             drill("rev", "Under SME review", "Interpretive provisions or low confidence — maker treatment applied until decided", lst(rev))]
    return page("Tier 1 capital", _date(run), body, "".join(tpls)), {}


# ------------------------------------------------------------------ Tier 2
def tier2(run):
    r, m = run.final, run.minimums
    gp, cap, elig = r.gp_gross, r.gp_cap, r.tier2_gp_eligible
    rate = 0.0125
    need_rwa = gp / rate
    right = _ring_html(elig / gp if gp else 0, "of provision counted")
    body = hero("Tier 2 · general provisions", "Tier 2 capital (₹ lakhs)", count(r.tier2, 2, "₹"), " L",
                [("Cap binding" if gp > cap else "Below cap", ""), (f"Tier 2 = {r.tier2 / r.tier1:.1%} of Tier 1 (max 100%)", "")], right)
    body += card("Cap headroom", "How the 1.25% cap behaves", f"""<div class="kv">
 <span class="k">Stage 1 ECL (provision)</span><span class="v">₹{gp:,.2f} L</span><span class="k">Cap at 1.25% of RWA</span><span class="v">₹{cap:,.2f} L</span>
 <span class="k">Not recognised</span><span class="v" style="color:#D64560">₹{gp - elig:,.2f} L</span>
 <span class="k">RWA needed to count it all</span><span class="v">₹{need_rwa:,.0f} L (×{need_rwa / r.total_rwa:.1f})</span>
 <span class="k">Tier 2 limit (100% of Tier 1)</span><span class="v">₹{r.tier1:,.0f} L</span></div>""", "c4", d=.06)
    steps = f"""<div class="steps">
 <div class="step" data-drill="s1"><span class="n">1</span><small>Stage 1 ECL</small><b>₹{gp:,.0f} L</b><div class="f">12-month expected credit loss</div></div>
 <div class="step" data-drill="s2"><span class="n">2</span><small>Cap = 1.25% × RWA</small><b>₹{cap:,.0f} L</b><div class="f">1.25% × ₹{r.total_rwa:,.0f} L</div></div>
 <div class="step"><span class="n">3</span><small>Eligible = min(1, 2)</small><b>₹{elig:,.0f} L</b><div class="f">{elig / gp:.0%} of the provision</div></div>
 <div class="step"><span class="n">4</span><small>Tier 2 ≤ Tier 1?</small><b style="color:#2E8B5E">Yes ✓</b><div class="f">{r.tier2 / r.tier1:.1%} of Tier 1</div></div>
 <div class="step"><span class="n">5</span><small>Tier 2 capital</small><b>₹{r.tier2:,.0f} L</b><div class="f">counts towards CRAR</div></div></div>"""
    body += card("How Tier 2 is computed", "Para 13(iii) and 16(6) — click a step for the rule", steps, "c12", d=.2)
    vis = f"""<div style="position:relative;margin:26px 0 8px;height:44px;border-radius:14px;background:var(--track);overflow:hidden">
 <i style="position:absolute;left:0;top:0;bottom:0;width:{min(elig / gp, 1) * 100:.1f}%;background:linear-gradient(90deg,#4F2D7F,#7B4FC4);border-radius:14px;animation:growx 1.4s both;transform-origin:left"></i>
 <span style="position:absolute;left:12px;top:12px;color:#fff;font-size:12.5px;font-weight:650">Counted ₹{elig:,.0f} L</span>
 <span style="position:absolute;right:12px;top:12px;font-size:12.5px;font-weight:650;color:var(--mut)">Not counted ₹{gp - elig:,.0f} L</span></div>
 <div class="s">Full bar = Stage 1 ECL of ₹{gp:,.0f} L. The cap moves with RWA: every ₹1 of extra RWA lets ₹0.0125 more count.</div>"""
    body += card("Provision vs cap", "The share of the provision that becomes capital", vis, "c7", d=.3)
    others = [("Non-convertible preference shares", "13(i)"), ("Revaluation reserves (55% discount)", "13(ii)"),
              ("Hybrid debt instruments", "13(iv)"), ("Subordinated debt (maturity discount, ≤50% of Tier 1)", "13(v)"),
              ("Perpetual debt above the Tier 1 limit", "13(vi)")]
    rows = [f'<tr><td>{escape(n)}</td><td class="r">0.00</td><td>{p}</td><td>{tag("None in source", "var(--chip)", "var(--mut)")}</td></tr>' for n, p in others]
    body += card("Other Tier 2 instruments", "Supported by the rule library; none in this workbook",
                 table("t2o", [("Instrument", "txt", ""), ("₹ lakhs", "num", "r"), ("Para", "txt", ""), ("Status", None, "")], rows), "c5", d=.36)
    tpls = drill("s1", "Stage 1 ECL", "General provision eligible for Tier 2", '<div class="ov-p">12-month ECL on Stage 1 assets is a '
                 'general provision not attributable to identified losses, so it can count as Tier 2 — but only up to 1.25% of RWA '
                 '(para 13(iii), 16(6)). Lifetime ECL (Stage 2/3) does not count and is reduced from RWA instead.</div>') + \
        drill("s2", "The 1.25% cap", "Para 13(iii)", f'<div class="ov-p">Cap = 1.25% × total RWA = 1.25% × ₹{r.total_rwa:,.2f} L = ₹{cap:,.2f} L. '
              f'Because the provision (₹{gp:,.2f} L) exceeds the cap, ₹{gp - elig:,.2f} L stays a provision and is not counted.</div>')
    return page("Tier 2 capital", _date(run), body, tpls), {}


def _ring_html(frac, label):
    c = 2 * math.pi * 52
    return (f'<div style="width:150px;height:150px;position:relative"><svg viewBox="0 0 120 120" style="width:100%;height:100%;transform:rotate(-90deg)">'
            f'<circle cx="60" cy="60" r="52" fill="none" stroke="rgba(255,255,255,.15)" stroke-width="12"/>'
            f'<circle class="ring" cx="60" cy="60" r="52" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" '
            f'stroke-dasharray="{c:.1f}" style="--c:{c:.1f};stroke-dashoffset:{c * (1 - frac):.1f};animation:ringin 1.6s both"/></svg>'
            f'<div style="position:absolute;inset:0;display:grid;place-items:center;text-align:center"><div><b style="font-size:26px">{frac:.0%}</b>'
            f'<div style="font-size:11px;color:#E0D3F7">{escape(label)}</div></div></div></div>')


# ------------------------------------------------------------------ RWA
def rwa(run):
    r = run.final
    lines = [(a.cls.label, a.exposure, a.applied, a.exposure * a.applied, a) for a in run.rwa_applied]
    tot_exp = sum(x[1] for x in lines) + run.cem.credit_equivalent
    dens = r.total_rwa / tot_exp if tot_exp else 0
    big = max(lines, key=lambda x: x[3])
    right = _ring_html(dens, "average risk weight")
    body = hero("Credit + counterparty risk", "Total risk-weighted assets (₹ lakhs)", count(r.total_rwa, 0, "₹"), " L",
                [(f"On-balance-sheet ₹{r.rwa_credit_on_bs:,.0f} L", ""), (f"Derivatives ₹{r.rwa_ccr:,.0f} L", ""),
                 (f"Largest: {_short(big[0], 20)} {big[3] / r.total_rwa:.0%}", "")], right)
    buckets = {}
    for _, e, w, rv, _a in lines:
        k = f"{w:.0%}"
        b = buckets.setdefault(k, [0, 0])
        b[0] += e
        b[1] += rv
    bl = sorted(buckets.items(), key=lambda kv: float(kv[0].rstrip("%")))
    body += card("Risk-weight buckets", "Exposure and RWA by weight", bars([(f"{k} weight · exposure ₹{v[0]:,.0f} L", v[1], f"₹{v[1]:,.0f} L", "")
                                                                         for k, v in bl]), "c4", d=.06)
    rev = [x for x in lines if x[4].cls.route != "AUTO_ACCEPT"]
    body += tile("scale", "#3D2B8C", "#6E64D8", "Exposures", count(len(lines)), "", 1, f"₹{tot_exp:,.0f} L incl. derivatives", "Lines",
                 "rgba(110,100,216,.14)", "#5B4FC8", .1)
    body += tile("layers", "#6B3FB8", "#9B6BEB", "Average risk weight", count(dens * 100, 1, "", "%"), "", dens / 1.5, "RWA ÷ exposure",
                 "Density", "rgba(123,79,196,.12)", "#7B4FC4", .15)
    body += tile("shield", "#C2405E", "#F08AA0", "Loan book share", count(big[3] / r.total_rwa * 100, 1, "", "%"), "", big[3] / r.total_rwa,
                 "concentration of RWA", "Concentrated", "rgba(214,69,96,.12)", "#D64560", .2, "loans")
    body += tile("flag", "#E28A1C", "#F5BE5C", "Weights under review", count(len(rev)), "", len(rev) / max(len(lines), 1),
                 "interpretive or ambiguous", "Review", "rgba(226,138,28,.14)", "#C7781A", .25, "rwrev")
    body += card("Where the risk sits", "RWA by exposure · ₹ lakhs", bars(sorted([(_short(n, 36), rv, f"₹{rv:,.0f} L", "") for n, _, _, rv, _ in lines]
                                                                              + [("Derivatives (CEM)", r.rwa_ccr, f"₹{r.rwa_ccr:,.0f} L", PV)],
                                                                              key=lambda x: -x[1])), "c7", d=.3)
    grp = {"Loans": 0.0, "Receivables": 0.0, "Other": 0.0}
    for n, _, _, rv, _a in lines:
        lb = n.lower()
        grp["Loans" if n == "Loans" else ("Receivables" if any(t in lb for t in ("receivable", "deposit", "advance", "gateway")) else "Other")] += rv
    grp["Derivatives"] = r.rwa_ccr
    parts = [(k, v, c) for (k, v), c in zip(grp.items(), [P, PV, "#B9A8D9", "#E2D8F3"])]
    tot = sum(v for _, v, _ in parts) or 1
    leg = "".join(f'<span class="sw" style="background:{c}"></span><span>{escape(k)}</span><span class="pc">{v / tot:.1%}</span>' for k, v, c in parts)
    body += card("Mix", "Share of total RWA", f'<div style="display:flex;align-items:center;gap:22px">{donut(parts, 170)}'
                 f'<div class="cx-leg" style="flex:1;min-width:0;font-size:13px;row-gap:12px">{leg}</div></div>'
                 f'<div style="margin-top:16px"><button class="btn" data-nav="t15_whatif">Change the loan risk weight {ic("arrow", 14)}</button></div>', "c5", d=.36)
    rows, tpls = [], []
    for n, e, w, rv, a in lines:
        key = f"rw-{a.cls.item_id}"
        rows.append(f'<tr data-drill="{key}" data-rw="{w:.0%}" data-route="{a.cls.route}"><td><b>{escape(_short(n, 40))}</b></td>'
                    f'<td class="r" data-v="{e}">{e:,.2f}</td><td>{tag(f"{w:.0%}", "rgba(61,43,140,.12)", "#5B4FC8")}</td>'
                    f'<td class="r" data-v="{rv}">{rv:,.2f}</td><td class="r" data-v="{rv / r.total_rwa}">{rv / r.total_rwa:.1%}</td>'
                    f'<td class="mono">{escape(a.cls.rule_id or "")}</td><td data-v="{a.cls.confidence}">{conf_meter(a.cls.confidence)}</td></tr>')
        tpls.append(drill(key, n, f"{a.cls.item_id} · exposure", _cls_detail(a, run)))
    wopts = [("All", "all")] + [(k, k) for k, _ in bl]
    body += card("Exposures", "Click a row for the rule, citation and reasoning",
                 table("rw", [("Exposure", "txt", ""), ("Exposure ₹ L", "num", "r"), ("Weight", "txt", ""), ("RWA ₹ L", "num", "r"),
                              ("Share", "num", "r"), ("Rule", "txt", ""), ("Confidence", "num", "")], rows, [("rw", wopts)]), "c12", d=.42)
    tpls += drill("loans", "Loan book", "The dominant risk driver", _cls_detail(next(x[4] for x in lines if x[0] == "Loans"), run))
    tpls += drill("rwrev", "Weights under review", "Applied on the maker's basis until an SME decides",
                  "".join(f'<div class="ov-q"><b>{escape(x[0])}</b> · weight {x[2]:.0%} · {escape(x[4].cls.rule_id or "")}</div>' for x in rev) or
                  '<div class="ov-p">None.</div>')
    return page("Risk-weighted assets", _date(run), body, tpls), {}


# ------------------------------------------------------------------ Derivatives
def derivatives(run):
    cem, r = run.cem, run.final
    sets = {}
    for lbl, w in (("bank", 0.20), ("corporate", 1.0), ("sovereign", 0.0)):
        res = run._compute({"ccr_rw": w})
        sets[lbl] = {"rw": f"{w:.0%}", "rwa": f"₹{cem.credit_equivalent * w:,.2f} L", "crar": f"{res.crar:.2%}",
                     "delta": f"{(res.crar - r.crar) * 1e4:+.0f} bps vs reported"}
    body = hero("Counterparty credit risk · Current Exposure Method", "Derivatives RWA (₹ lakhs)", count(cem.rwa, 2, "₹"), " L",
                [(f"{len(cem.deals)} cross-currency swaps", ""), (f"Credit equivalent ₹{cem.credit_equivalent:,.0f} L", ""),
                 (f"{cem.rwa / r.total_rwa:.2%} of total RWA", "")], _ring_html(cem.pfe_total / cem.credit_equivalent if cem.credit_equivalent else 0, "of exposure is PFE"))
    body += card("Counterparty type", "Switch to see the capital effect instantly", f"""
 <div class="seg2"><button class="on" data-set="cp:bank">Bank 20%</button><button data-set="cp:corporate">Corporate 100%</button>
 <button data-set="cp:sovereign">Sovereign 0%</button></div>
 <div class="kv" style="margin-top:18px"><span class="k">Risk weight</span><span class="v" data-out="cp:rw">20%</span>
 <span class="k">Derivatives RWA</span><span class="v" data-out="cp:rwa">₹{cem.rwa:,.2f} L</span>
 <span class="k">CRAR</span><span class="v" data-out="cp:crar">{r.crar:.2%}</span>
 <span class="k">Change</span><span class="v" data-out="cp:delta">+0 bps vs reported</span></div>
 <div class="s" style="margin-top:12px">Para 18(3): 0% sovereign · 20% banks · 100% others. Counterparty type is an open evidence item.</div>""", "c4", d=.06)
    formula = f"""<div class="formula">
 <div class="blk"><small>Replacement cost (MTM)</small><b>₹{cem.replacement_cost:,.2f}</b></div><span class="op">+</span>
 <div class="blk"><small>Potential future exposure</small><b>₹{cem.pfe_total:,.2f}</b></div><span class="op">=</span>
 <div class="blk"><small>Credit equivalent</small><b>₹{cem.credit_equivalent:,.2f}</b></div><span class="op">×</span>
 <div class="blk"><small>Counterparty weight</small><b data-out="cp:rw">20%</b></div><span class="op">=</span>
 <div class="blk k"><small>Derivatives RWA</small><b data-out="cp:rwa">₹{cem.rwa:,.2f} L</b></div></div>"""
    body += card("The CEM formula, live", "Para 18(8): current exposure + add-on × notional", formula, "c12", d=.2)
    cards = []
    tpls = []
    for i, d in enumerate(cem.deals):
        key = f"deal-{d.item_id}"
        yrs = d.residual_years
        bucket = "≤1y" if yrs <= 1 else ("1–5y" if yrs <= 5 else ">5y")
        cards.append(f'<div class="mcard" data-drill="{key}" data-search="{escape(d.deal_id.lower())} swap deal"><div class="id">{escape(d.deal_id)}</div>'
                     f'<div class="tt">Cross-currency swap · {"exchange-rate contract" if d.contract_type == "fx_gold" else "interest-rate contract"}</div>'
                     f'<div class="kv" style="margin-top:12px"><span class="k">Notional</span><span class="v">₹{d.notional_lakhs:,.2f} L</span>'
                     f'<span class="k">Residual maturity</span><span class="v">{yrs:.2f} yrs</span><span class="k">Add-on</span><span class="v">{d.add_on:.0%} ({bucket})</span>'
                     f'<span class="k">PFE</span><span class="v">₹{d.pfe_lakhs:,.2f} L</span></div>'
                     f'<div class="meter" style="margin-top:14px"><i style="--w:{min(yrs / 5, 1) * 100:.0f}%;--grad:linear-gradient(90deg,#4F2D7F,#7B4FC4);--d:{.3 + i * .1}s"></i></div>'
                     f'<div class="foot" style="font-size:11px;color:var(--faint);margin-top:6px">Maturity bar: 0 → 5 years</div></div>')
        tpls.append(drill(key, d.deal_id, "Cross-currency swap — CEM detail",
                          boxes([("Notional (INR)", f"{d.notional_inr:,.0f}"), ("Notional (₹ L)", f"{d.notional_lakhs:,.2f}"),
                                 ("Residual maturity", f"{yrs:.2f} years"), ("Add-on bucket", f"{bucket} → {d.add_on:.0%}"),
                                 ("PFE", f"₹{d.pfe_lakhs:,.2f} L"), ("Source cell", d.source_ref[:36])])
                          + '<div class="ov-p">Exchange-rate contracts (incl. cross-currency swaps, para 18(7)(iii)(b)) carry add-ons of '
                            '2% / 10% / 15% for ≤1 / 1–5 / >5 years. Replacement cost uses the aggregate derivative asset because deal-level '
                            'MTM was not supplied; no netting is recognised without a legal opinion (para 18(9)).</div>'))
    body += card("Deals", "Each swap's contribution · click a deal for detail", f'<div class="cards3">{"".join(cards)}</div>', "c12", d=.3)
    return page("Derivatives (CEM)", _date(run), body, "".join(tpls)), {"sets": {"cp": sets}}


# ------------------------------------------------------------------ Sensitivity
def sensitivity(run):
    r = run.final
    open_ex = [e for e in run.exceptions if e.status == "OPEN" and e.scenario_overrides]
    items = sorted([(_short(e.title, 30), e.impact_crar_bps, SEV.get(e.severity, "#999")) for e in open_ex], key=lambda x: -abs(x[1]))
    av = run.agent_view
    up = sum(v for _, v, _ in items if v > 0)
    dn = sum(v for _, v, _ in items if v < 0)
    body = hero("One judgement call at a time", "CRAR if every agent reading is accepted", count(av.crar * 100, 2), "%",
                [(f"Reported {r.crar:.2%}", ""), (f"Upside {up:+.0f} bps", "ok"), (f"Downside {dn:+.0f} bps", "")],
                _ring_html(min(av.crar / 0.4, 1), "of a 40% scale"))
    body += card("Range", "Best and worst single moves", f"""<div class="kv">
 <span class="k">Largest upside</span><span class="v" style="color:#2E8B5E">{max((v for _, v, _ in items), default=0):+.0f} bps</span>
 <span class="k">Largest downside</span><span class="v" style="color:#D64560">{min((v for _, v, _ in items), default=0):+.0f} bps</span>
 <span class="k">Open items with an impact</span><span class="v">{len(items)}</span>
 <span class="k">Minimum CRAR</span><span class="v">{run.minimums['crar']:.0%}</span></div>""", "c4", d=.06)
    body += card("Tornado — CRAR impact by item", "Bars to the right raise CRAR, to the left lower it · coloured by priority",
                 tornado(items) if items else '<div class="s">Nothing open.</div>', "c12", d=.2)
    rows, tpls = [], []
    for e in open_ex:
        res = run._compute(e.scenario_overrides)
        key = f"sn-{e.exc_id}"
        rows.append(f'<tr data-drill="{key}" data-sev="{e.severity}"><td><b>{escape(_short(e.title, 40))}</b></td><td>{escape(e.severity)}</td>'
                    f'<td class="r" data-v="{res.tier1}">{res.tier1:,.0f}</td><td class="r" data-v="{res.total_rwa}">{res.total_rwa:,.0f}</td>'
                    f'<td class="r" data-v="{res.crar}">{res.crar:.2%}</td><td class="r" data-v="{e.impact_crar_bps}">{e.impact_crar_bps:+.1f}</td>'
                    f'<td>{"Breach" if res.breaches else "OK"}</td></tr>')
        tpls.append(drill(key, e.title, e.exc_id, boxes([("Tier 1", f"₹{res.tier1:,.2f} L"), ("RWA", f"₹{res.total_rwa:,.2f} L"),
                                                       ("CRAR", f"{res.crar:.2%}"), ("vs reported", f"{e.impact_crar_bps:+.1f} bps")])
                          + f'<div class="ov-p">{escape(e.scenario_desc)}</div><div class="ov-p"><b>Agent\'s reading:</b> {escape(e.ai_best_guess)}</div>'))
    body += card("Scenarios", "Full engine re-run per item", table("sn", [("Item", "txt", ""), ("Priority", "txt", ""), ("Tier 1", "num", "r"),
                                                                         ("RWA", "num", "r"), ("CRAR", "num", "r"), ("bps", "num", "r"),
                                                                         ("Status", "txt", "")], rows,
                                                               [("sev", [("All", "all"), ("High", "High"), ("Medium", "Medium"), ("Low", "Low")])]),
                 "c12", d=.3)
    return page("Sensitivity", _date(run), body, "".join(tpls)), {}


# ------------------------------------------------------------------ Rules in force
def rules(run):
    rl = list(run.rules.rules.values())
    drift_ids = {d["rule_id"] for d in (run.rbi_drift or [])}
    interp = sum(bool(x.get("interpretive")) for x in rl)
    areas = sorted({x["area"] for x in rl})
    body = hero("Controlled rule library", f"{run.rules.version} · {run.rules.framework}", count(len(rl)), " rules",
                [(f"{interp} interpretive → always human review", ""), (f"{len(drift_ids)} affected by RBI changes", "" if not drift_ids else ""),
                 (f"KB {run.kb.version}", "")], _ring_html(1 - interp / max(len(rl), 1), "deterministic rules"))
    body += card("Governance", "How rules are controlled", f"""<div class="kv">
 <span class="k">Approval status</span><span class="v">{escape(str(run.rules.approved_by)[:28])}</span>
 <span class="k">Rejected at load</span><span class="v">{len(run.rules.rejected)}</span>
 <span class="k">In force on</span><span class="v">{run.ds.reporting_date:%d %b %Y}</span>
 <span class="k">Passages excluded (future)</span><span class="v">{len(run.kb.excluded_future)}</span></div>""", "c4", d=.06)
    cards, tpls = [], []
    for x in rl:
        key = f"rule-{x['id']}"
        paras = ", ".join(run.kb.get(p).para for p in x.get("citations", []) if run.kb.get(p))
        rw = f" · RW {x['risk_weight']:.0%}" if x.get("risk_weight") is not None else ""
        badge = tag("Interpretive", "rgba(226,138,28,.14)", "#C7781A") if x.get("interpretive") else tag("Deterministic", "rgba(46,139,94,.12)", "#2E8B5E")
        dr = tag("RBI changed", "rgba(214,69,96,.13)", "#D64560") if x["id"] in drift_ids else ""
        cards.append(f'<div class="mcard" data-drill="{key}" data-area="{escape(x["area"])}" data-search="{escape((x["id"] + " " + x["title"] + " " + x["area"]).lower())}">'
                     f'<div class="id">{escape(x["id"])}</div><div class="tt">{escape(x["title"])}</div>'
                     f'<div class="meta">{treat_tag(x["treatment"])}{badge}{dr}{tag(x["area"])}</div>'
                     f'<div class="s" style="margin-top:10px">para {escape(paras)}{escape(rw)}</div>'
                     f'<div style="margin-top:10px">{conf_meter(x["default_confidence"])}</div></div>')
        passages = "".join(f'<div class="ov-q"><b>para {escape(run.kb.get(p).para)} · {escape(run.kb.get(p).title)}</b><br>{escape(run.kb.get(p).text)}</div>'
                           for p in x.get("citations", []) if run.kb.get(p))
        alts = "".join(f'<li>{escape(str(a.get("treatment") or ""))} {("RW " + format(a["risk_weight"], ".0%")) if a.get("risk_weight") is not None else ""} — {escape(a.get("basis", ""))}</li>'
                       for a in x.get("alternatives", []))
        drift = "".join(f'<div class="ov-q" style="border-color:#D64560"><b>RBI change:</b> para {escape(d["para"])} {escape(d["what"])} · {escape(d["source"])} · '
                        f'effective {escape(str(d["effective"]))} · {"applies to this run" if d["applies_to_run"] else "after this reporting date"}</div>'
                        for d in (run.rbi_drift or []) if d["rule_id"] == x["id"])
        tpls.append(drill(key, f'{x["id"]} · {x["title"]}', f'{x["area"]} · effective from {x["effective_from"]} · {x["status"]}',
                          boxes([("Treatment", x["treatment"]), ("Risk weight", f"{x['risk_weight']:.0%}" if x.get("risk_weight") is not None else "—"),
                                 ("Interpretive", "Yes" if x.get("interpretive") else "No"), ("Default confidence", f"{x['default_confidence']:.2f}")])
                          + drift + (f'<div class="ov-p"><b>Alternatives</b><ul style="margin:6px 0 0 18px;line-height:1.6">{alts}</ul></div>' if alts else "")
                          + (f'<div class="ov-p"><b>Evidence required:</b> {escape(x.get("evidence_required", ""))}</div>' if x.get("evidence_required") else "")
                          + passages))
    chips = "".join(f'<button class="btn" data-cf="rulecards|area|{escape(a)}">{escape(a)}</button>' for a in areas)
    body += card("Rules", "Click a rule for its RBI text, alternatives and any RBI change",
                 f'<div class="flt" style="margin-bottom:14px" id="areaf"><button class="btn on" data-cf="rulecards|area|all">All</button>{chips}</div>'
                 f'<div class="cards3" id="rulecards">{"".join(cards)}</div>', "c12", d=.2)
    return page("Rules in force", _date(run), body, "".join(tpls)), {}


# ------------------------------------------------------------------ Agent reasoning
def reasoning(run):
    allc = run.cap_applied + run.rwa_applied
    auto = [a for a in allc if a.cls.route == "AUTO_ACCEPT"]
    avg = sum(a.cls.confidence for a in allc) / max(len(allc), 1)
    hist = {}
    for a in allc:
        b = min(int(a.cls.confidence * 10), 9) / 10
        hist[b] = hist.get(b, 0) + 1
    body = hero("Deterministic reasoning · no LLM", "Classifications auto-accepted", count(len(auto)), f" of {len(allc)}",
                [(f"Average confidence {avg:.2f}", ""), (f"Threshold {run.agent.threshold:.2f}", ""),
                 (f"{len(allc) - len(auto)} routed to a human", "")], _ring_html(len(auto) / max(len(allc), 1), "auto-accepted"))
    body += card("Confidence distribution", "Number of classifications per confidence band",
                 bars([(f"{k:.1f} – {k + .1:.1f}", v, str(v), "#2E8B5E" if k >= .8 else ("#D48B12" if k >= .6 else "#D64560"))
                       for k, v in sorted(hist.items())]), "c4", d=.06)
    rows, tpls = [], []
    for a in allc:
        c = a.cls
        key = f"rs-{c.item_id}"
        rows.append(f'<tr data-drill="{key}" data-route="{c.route}" data-kind="{c.kind}"><td class="mono">{c.item_id}</td><td><b>{escape(_short(c.label, 38))}</b></td>'
                    f'<td>{escape(c.kind)}</td><td>{treat_tag(c.treatment)}</td><td class="mono">{escape(c.rule_id or "")}</td>'
                    f'<td data-v="{c.confidence}">{conf_meter(c.confidence)}</td>'
                    f'<td>{"Auto" if c.route == "AUTO_ACCEPT" else tag("Review", "rgba(226,138,28,.14)", "#C7781A")}</td></tr>')
        tpls.append(drill(key, c.label, f"{c.item_id} · {c.kind}", _cls_detail(a, run)))
    body += card("Every classification", "Click a row for the full chain: source → rule → RBI text → treatment",
                 table("rs", [("ID", "txt", ""), ("Line item", "txt", ""), ("Kind", "txt", ""), ("Treatment", "txt", ""), ("Rule", "txt", ""),
                              ("Confidence", "num", ""), ("Route", "txt", "")], rows,
                       [("route", [("All", "all"), ("Auto", "AUTO_ACCEPT"), ("Review", "HUMAN_REVIEW")]),
                        ("kind", [("Any kind", "all"), ("Capital", "capital"), ("Asset", "asset")])]), "c12", d=.2)
    return page("Agent reasoning", _date(run), body, "".join(tpls)), {}


# ------------------------------------------------------------------ Validation
def validation(run):
    allc = run.checks + run.control_checks
    ps = sum(c.status == "PASS" for c in allc)
    fl = [c for c in allc if c.status == "FAIL"]
    wn = [c for c in allc if c.status == "WARN"]
    areas = {}
    for c in allc:
        a = areas.setdefault(c.area, [0, 0])
        a[0 if c.status == "PASS" else 1] += 1
    body = hero("Source tie-outs and controls", "Checks passing", count(ps), f" of {len(allc)}",
                [(f"{len(fl)} fail", ""), (f"{len(wn)} warn", ""), (f"Benchmark {sum(b['status'] == 'PASS' for b in run.benchmark)}/{len(run.benchmark)}", "ok")],
                _ring_html(ps / max(len(allc), 1), "pass rate"))
    mat = "".join(f'<div class="ov-box" style="cursor:default"><small>{escape(a)}</small><b>{v[0]} ✓</b>'
                  f'{f" <span style=color:#D64560;font-weight:700>{v[1]} ✗</span>" if v[1] else ""}</div>' for a, v in sorted(areas.items()))
    body += card("By area", "Pass / issue counts", f'<div class="ov-grid" style="margin-top:0">{mat}</div>', "c4", d=.06)
    rows, tpls = [], []
    for c in allc:
        key = f"vc-{c.check_id}"
        col = {"PASS": ("rgba(46,139,94,.12)", "#2E8B5E"), "FAIL": ("rgba(214,69,96,.13)", "#D64560"), "WARN": ("rgba(212,139,18,.14)", "#C27C10")}[c.status]
        diff = c.difference
        rows.append(f'<tr data-drill="{key}" data-status="{c.status}"><td class="mono">{escape(c.check_id)}</td><td>{escape(c.area)}</td>'
                    f'<td>{escape(c.description[:70])}</td><td>{tag(c.status.title(), *col)}</td>'
                    f'<td class="r" data-v="{diff if diff is not None else 0}">{"" if diff is None else f"{diff:+,.2f}"}</td></tr>')
        tpls.append(drill(key, f"{c.check_id} · {c.description}", c.area,
                          boxes([("Status", c.status), ("Expected", f"{c.expected:,.4f}" if isinstance(c.expected, (int, float)) else str(c.expected or "—")),
                                 ("Actual", f"{c.actual:,.4f}" if isinstance(c.actual, (int, float)) else str(c.actual or "—")),
                                 ("Difference", "—" if diff is None else f"{diff:+,.4f}")])
                          + (f'<div class="ov-p">{escape(c.detail)}</div>' if c.detail else "")))
    body += card("All checks", "Click a check for expected vs actual", table("vc", [("ID", "txt", ""), ("Area", "txt", ""), ("Check", "txt", ""),
                                                                                  ("Status", "txt", ""), ("Difference", "num", "r")], rows,
                                                                            [("status", [("All", "all"), ("Fail", "FAIL"), ("Warn", "WARN"), ("Pass", "PASS")])]),
                 "c12", d=.2)
    return page("Validation", _date(run), body, "".join(tpls)), {}


# ------------------------------------------------------------------ Audit trail
def audit(run):
    stages = {}
    actors = {}
    for e in run.audit:
        stages[e.stage] = stages.get(e.stage, 0) + 1
        a = e.actor.split(" (")[0]
        actors[a] = actors.get(a, 0) + 1
    body = hero("Source → rule → treatment → output", "Audit entries this run", count(len(run.audit)), "",
                [(f"{len(stages)} stages", ""), (f"Agent {actors.get('Agent', 0)} · Engine {actors.get('Engine', 0)}", ""),
                 (f"Human {sum(v for k, v in actors.items() if k.startswith('Human'))}", "")], "")
    body += card("By stage", "Entries per pipeline stage", bars([(k, v, str(v), "") for k, v in sorted(stages.items())]), "c4", d=.06)
    rows = []
    for e in run.audit:
        a = e.actor.split(" (")[0]
        rows.append(f'<tr data-stage="{escape(e.stage)}" data-actor="{escape(a)}"><td class="r" data-v="{e.seq}">{e.seq}</td><td>{escape(e.stage)}</td>'
                    f'<td class="mono">{escape(str(e.item_id))}</td><td title="{escape(e.description)}">{escape(e.description[:90])}</td>'
                    f'<td class="mono">{escape(e.rule_id)}</td><td>{escape(str(e.output_value)[:18]) if e.output_value is not None else ""}</td>'
                    f'<td>{tag(a, "rgba(123,79,196,.12)" if a == "Agent" else ("rgba(46,139,94,.12)" if a.startswith("Human") else "var(--chip)"), "#7B4FC4" if a == "Agent" else ("#2E8B5E" if a.startswith("Human") else "var(--mut)"))}</td></tr>')
    sopts = [("All stages", "all")] + [(k, k) for k in sorted(stages)]
    aopts = [("Any actor", "all")] + [(k, k) for k in sorted(actors)]
    body += card("Trail", "Search and filter every step", table("au", [("#", "num", "r"), ("Stage", "txt", ""), ("Item", "txt", ""), ("Description", "txt", ""),
                                                                    ("Rule", "txt", ""), ("Output", "txt", ""), ("Actor", "txt", "")], rows,
                                                              [("stage", sopts), ("actor", aopts)]), "c12", d=.2)
    return page("Audit trail", _date(run), body), {}


# ------------------------------------------------------------------ Exception queue (summary above the native editor)
def exceptions(run):
    open_ex = [e for e in run.exceptions if e.status == "OPEN"]
    done = [e for e in run.exceptions if e.status != "OPEN"]
    sev = {s: sum(e.severity == s for e in open_ex) for s in ("Critical", "High", "Medium", "Low")}
    stake = sum(abs(e.impact_crar_bps) for e in open_ex if e.scenario_overrides)
    body = hero("Human-in-the-loop review", "Open items", count(len(open_ex)), "",
                [(f"{sev['High'] + sev['Critical']} high priority", ""), (f"{len(done)} resolved", "ok"), (f"{stake:,.0f} bps of CRAR at stake", "")],
                _ring_html(len(done) / max(len(run.exceptions), 1), "resolved"))
    body += card("By priority", "Open items", bars([(s, v, str(v), SEVC[s]) for s, v in sev.items()]), "c4", d=.06)
    items = sorted([(_short(e.title, 30), e.impact_crar_bps, SEV.get(e.severity)) for e in open_ex if e.scenario_overrides], key=lambda x: -abs(x[1]))
    body += card("CRAR at stake by item", "Decide the biggest bars first", tornado(items) if items else '<div class="s">Nothing open.</div>', "c7", d=.2)
    cats = {}
    for e in open_ex:
        k = CAT.get(e.category, e.category)
        cats[k] = cats.get(k, 0) + 1
    body += card("By category", "What kind of judgement is needed", bars([(k, v, str(v), "") for k, v in sorted(cats.items(), key=lambda x: -x[1])]), "c5", d=.26)
    rows, tpls = [], []
    for e in run.exceptions:
        key = f"ex-{e.exc_id}"
        rows.append(f'<tr data-drill="{key}" data-sev="{e.severity}" data-st="{"OPEN" if e.status == "OPEN" else "DONE"}"><td class="mono">{escape(e.exc_id)}</td>'
                    f'<td><b>{escape(_short(e.title, 40))}</b></td><td>{tag(e.severity, "var(--chip)", SEVC[e.severity])}</td>'
                    f'<td>{escape(CAT.get(e.category, e.category))}</td><td class="r" data-v="{e.impact_crar_bps if e.scenario_overrides else 0}">'
                    f'{f"{e.impact_crar_bps:+.0f}" if e.scenario_overrides else "—"}</td><td>{escape(e.status.title()[:24])}</td></tr>')
        tpls.append(drill(key, e.title, f"{e.exc_id} · {e.severity} · {e.category}",
                          boxes([("CRAR impact", f"{e.impact_crar_bps:+.1f} bps" if e.scenario_overrides else "—"), ("Status", e.status),
                                 ("Citation", e.citations[:40] or "—"), ("Decision", e.decision or "—")])
                          + f'<div class="ov-p">{escape(e.issue)}</div><div class="ov-p"><b>Agent\'s reading:</b> {escape(e.ai_best_guess)}</div>'
                          + f'<div class="ov-p"><b>Other readings:</b> {escape(e.competing)}</div><div class="ov-p"><b>Evidence needed:</b> {escape(e.evidence_required)}</div>'
                          + '<div class="ov-p" style="color:var(--mut)">Record the decision in the review table below this panel.</div>'))
    body += card("All items", "Click to read the full reasoning · record decisions in the table below",
                 table("ex", [("ID", "txt", ""), ("Item", "txt", ""), ("Priority", "txt", ""), ("Category", "txt", ""), ("bps", "num", "r"), ("Status", "txt", "")], rows,
                       [("sev", [("All", "all"), ("High", "High"), ("Medium", "Medium"), ("Low", "Low")]), ("st", [("Any status", "all"), ("Open", "OPEN"), ("Resolved", "DONE")])]),
                 "c12", d=.3)
    return page("Exception queue", _date(run), body, "".join(tpls)), {}


# ------------------------------------------------------------------ Basel III lens
def basel3(run):
    from capital_agent import basel3 as b3m
    b = run.basel3
    st, lev = b["stack"], b["leverage"]
    binding = b["framework"] == "binding"
    label = "Binding framework (bank)" if binding else "Benchmark lens — NBFC Directions govern compliance"
    body = hero("Basel III · RBI implementation for banks", "CET1 ratio", f'<span data-b3o="cet1_big">{b["ratios"]["cet1"] * 100:.2f}</span>', "%",
                [(label, "ok" if not binding else ""), ("CET1 floor 5.5% + CCB 2.5% = 8%", ""), ("Leverage floor 3.5% / 4% D-SIB", "")],
                '<div style="min-width:250px"><div class="eyebrow" style="margin-bottom:10px">Live result</div>'
                '<div style="font-size:13px;line-height:2;color:#EDE6FA">Binding constraint: <b data-b3o="binding">—</b><br>'
                'Distribution restriction: <b data-b3o="cons">—</b><br>Status: <b data-b3o="status">—</b></div></div>')
    dials = f"""<div class="s" style="margin-bottom:8px;font-weight:650;color:var(--ink)">D-SIB surcharge</div>
 <div class="seg2" style="flex-wrap:wrap">{''.join(f'<button class="{"on" if v == 0 else ""}" data-b3="dsib:{v}">{escape(n.split(" · ")[-1] if v else "None")}</button>' for n, v in b3m.DSIB_BUCKETS)}</div>
 <div class="s" style="margin:16px 0 8px;font-weight:650;color:var(--ink)">Countercyclical buffer (CCyB)</div>
 <div class="seg2" style="flex-wrap:wrap">{''.join(f'<button class="{"on" if v == 0 else ""}" data-b3="ccyb:{v}">{v:.1%}</button>' for v in b3m.CCYB_LEVELS)}</div>
 <div class="s" style="margin:16px 0 8px;font-weight:650;color:var(--ink)">Market + operational risk RWA (illustrative)</div>
 <div class="seg2" style="flex-wrap:wrap">{''.join(f'<button class="{"on" if v == 0 else ""}" data-b3="op:{v}">+{v:.0%}</button>' for v in (0, .1, .15, .2, .3))}</div>
 <div class="s" style="margin-top:12px">Not in the source data — the dial shows how much headroom remains if they were added.</div>"""
    body += card("Scenario dials", "Recalculated instantly", dials, "c4", d=.06)
    rows = "".join(f'<tr><td><b>{n}</b></td><td class="r" data-b3o="{k}">—</td><td class="r">{b3m.BCBS["lev" if k == "leverage" else k]:.1%}</td>'
                   f'<td class="r" data-b3o="{k}_min">—</td><td class="r" data-b3o="{k}_req">—</td><td class="r" data-b3o="{k}_h">—</td>'
                   f'<td data-b3s="{k}">—</td></tr>'
                   for k, n in (("cet1", "CET1 ratio"), ("tier1", "Tier 1 ratio"), ("total", "Total capital ratio"), ("leverage", "Leverage ratio")))
    tbl = (f'<div class="tblw"><table class="dt"><thead><tr><th>Ratio</th><th class="r">Actual</th><th class="r">BCBS floor</th>'
           f'<th class="r">RBI minimum</th><th class="r">RBI incl. buffers</th><th class="r">Headroom</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table></div>')
    body += card("Ratios against Basel III", "Global floor → RBI minimum → RBI with CCB, CCyB and D-SIB", tbl, "c12", d=.12)
    body += card("Requirement stack vs capital held", "Percentage points of RWA", '<div id="b3stack"></div>', "c6", d=.18)
    ladder = "".join(f'<div class="b3l" data-q="{q}"><span>{lbl}</span><b>{pct}</b></div>'
                     for q, lbl, pct in ((4, "Above the combined buffer", "0% conserved"), (3, "Top quartile of buffer", "40% conserved"),
                                         (2, "Second quartile", "60% conserved"), (1, "Third quartile", "80% conserved"),
                                         (0, "Bottom quartile", "100% conserved")))
    body += card("Capital conservation — distribution restriction", "Where CET1 sits inside the buffer decides how much of earnings must be retained",
                 f'<div class="b3lad">{ladder}</div><div class="s" style="margin-top:12px">Dividends and discretionary bonuses are restricted '
                 'when CET1 falls into the buffer (R-B3-002).</div>', "c6", d=.22)
    levb = boxes([("Total assets", f"₹{lev['total_assets']:,.0f} L"), ("Less: deducted from Tier 1", f"−₹{lev['less_deductions']:,.0f} L"),
                  ("Less: derivative asset", f"−₹{lev['less_derivative_asset']:,.0f} L"), ("Add: derivatives (RC + PFE)", f"₹{lev['derivatives_cem']:,.0f} L"),
                  ("Off-balance-sheet", "not supplied"), ("Exposure measure", f"₹{lev['exposure']:,.0f} L")])
    lr = b["ratios"]["leverage"]
    levtop = (f'<div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap"><b style="font-size:42px;letter-spacing:-.03em" '
              f'data-b3o="leverage">{lr:.2%}</b><span class="s">vs <b data-b3o="leverage_req">3.50%</b> minimum · '
              f'<b data-b3o="leverage_h">—</b> headroom</span></div>'
              f'<div style="position:relative;height:14px;border-radius:999px;background:var(--track);margin:14px 0 6px">'
              f'<i style="position:absolute;left:0;top:0;bottom:0;width:{min(lr / 0.3, 1) * 100:.1f}%;border-radius:999px;'
              f'background:linear-gradient(90deg,#4F2D7F,#7B4FC4);animation:growx 1.3s both;transform-origin:left"></i>'
              f'<span style="position:absolute;left:{0.035 / 0.3 * 100:.1f}%;top:-5px;bottom:-5px;width:2px;background:#D64560" title="3.5% floor"></span>'
              f'<span style="position:absolute;left:{0.04 / 0.3 * 100:.1f}%;top:-5px;bottom:-5px;width:2px;background:#8E1B3A" title="4% D-SIB floor"></span></div>'
              f'<div class="s" style="margin-bottom:14px">Scale 0–30% · red marks: 3.5% (banks) and 4% (D-SIBs)</div>')
    body += card("Leverage ratio", "Tier 1 ÷ exposure — a backstop that ignores risk weights",
                 levtop + levb.replace('class="ov-grid"', 'class="ov-grid" style="margin-top:0"'), "c7", d=.26)
    mapping = boxes([("CET1", f"₹{st['cet1']:,.0f} L · equity, reserves less deductions"), ("Additional Tier 1", f"₹{st['at1']:,.0f} L · none in source"),
                     ("Tier 2", f"₹{b['tier2_basel']:,.0f} L · provisions ≤1.25% credit RWA"), ("Credit RWA", f"₹{st['credit_rwa']:,.0f} L incl. derivatives")])
    gaps = "".join(f'<div class="ov-q" style="border-color:#D48B12">{escape(g)}</div>' for g in b["gaps"])
    body += card("Capital mapping and coverage gaps", "How the NBFC build maps to Basel III tiers", mapping.replace('class="ov-grid"', 'class="ov-grid" style="margin-top:0"') + gaps, "c5", d=.3)
    comp = "".join(f'<tr><td>{n}</td><td class="r">{a}</td><td class="r">{c}</td><td class="r">{d}</td></tr>' for n, a, c, d in (
        ("Minimum total capital", "8%", "9%", f"{run.minimums['crar']:.0%} (CRAR)"), ("Minimum Tier 1", "6%", "7%", f"{run.minimums['tier1']:.0%}"),
        ("Minimum CET1", "4.5%", "5.5%", "9% (Upper Layer only)"), ("Conservation buffer", "2.5%", "2.5%", "—"),
        ("Leverage ratio", "3%", "3.5% / 4% D-SIB", "—"), ("Tier 2 provisions cap", "1.25% credit RWA", "1.25% credit RWA", "1.25% RWA")))
    body += card("BCBS vs RBI banks vs RBI NBFCs", "Why the NBFC verdict and the Basel III lens can differ",
                 f'<div class="tblw"><table class="dt"><thead><tr><th>Requirement</th><th class="r">BCBS (global)</th><th class="r">RBI · banks</th>'
                 f'<th class="r">RBI · this NBFC</th></tr></thead><tbody>{comp}</tbody></table></div>', "c12", d=.34)
    data = {"b3": {"cet1": st["cet1"], "t1": st["tier1"], "gp": st["gp_gross"], "crwa": st["credit_rwa"], "exp": lev["exposure"],
                   "min": {"cet1": .055, "tier1": .07, "total": .09}, "ccb": .025, "lev_d": .04, "lev_o": .035}}
    css = """<style>.b3lad{display:grid;gap:8px}.b3l{display:flex;justify-content:space-between;padding:11px 14px;border-radius:12px;
 background:var(--card2);border:1px solid var(--line);font-size:12.5px;transition:all .25s}.b3l.on{background:linear-gradient(135deg,#2B1747,#4F2D7F);
 color:#fff;border-color:transparent;transform:scale(1.02)}#b3stack{display:flex;gap:28px;align-items:flex-end;height:300px;padding:6px 6px 0}
 .b3col{flex:1;display:flex;flex-direction:column-reverse;height:100%;border-radius:12px;overflow:hidden;background:var(--track)}
 .b3seg{display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:650;white-space:nowrap;overflow:hidden;
 transition:height .5s cubic-bezier(.2,.75,.2,1)}.b3cap{text-align:center;font-size:12px;font-weight:650;margin-top:8px}</style>"""
    return page("Basel III lens", _date(run), css + body), data


# ------------------------------------------------------------------ Calculation (step by step)
def calculation(run, history=None):
    from capital_agent import ledger
    led = ledger.build(run)
    r, m = run.final, run.minimums
    ok = led["reproduced"]
    body = hero("Show the working", "Every number, from source cell to CRAR", count(len(led["rows"])), " steps",
                [("✓ Ledger reproduces the engine" if ok else "⚠ Ledger differs from engine", "ok" if ok else ""),
                 ("Download: CSV ledger · Excel with live formulas", ""), (f"CRAR {r.crar:.4%}", "")],
                _ring_html(1.0 if ok else 0.0, "metrics reproduced"), span="c12")
    flow = f"""<div class="formula">
 <div class="blk"><small>A · Tier 1</small><b>₹{r.tier1:,.2f}</b></div><span class="op">+</span>
 <div class="blk"><small>B · Tier 2 (capped)</small><b>₹{r.tier2:,.2f}</b></div><span class="op">÷</span>
 <div class="blk"><small>C + D · Total RWA</small><b>₹{r.total_rwa:,.2f}</b></div><span class="op">=</span>
 <div class="blk k"><small>E · CRAR</small><b>{r.crar:.4%}</b></div></div>
 <div class="s" style="margin-top:10px">Minimum {m['crar']:.0%} · headroom {(r.crar - m['crar']) * 100:+.2f} pp · Tier 1 ratio {r.tier1_ratio:.4%} (minimum {m['tier1']:.0%})</div>"""
    body += card("The formula, with this run's numbers", "Each block expands into its own section below", flow, "c12", d=.06)
    chk = "".join(f'<tr><td><b>{escape(c["metric"])}</b></td><td class="r">{c["ledger"]:,.6f}</td><td class="r">{c["engine"]:,.6f}</td>'
                  f'<td class="r">{c["difference"]:+.2e}</td><td>{tag("Match", "rgba(46,139,94,.12)", "#2E8B5E") if c["ok"] else tag("Differs", "rgba(214,69,96,.13)", "#D64560")}</td></tr>'
                  for c in led["checks"])
    body += card("Independent check", "The ledger re-adds every line itself and compares with the engine",
                 f'<div class="tblw"><table class="dt"><thead><tr><th>Metric</th><th class="r">Ledger</th><th class="r">Engine</th>'
                 f'<th class="r">Difference</th><th>Result</th></tr></thead><tbody>{chk}</tbody></table></div>', "c7", d=.1)
    hist = history or []
    if hist:
        hrows = []
        prev = None
        for h in hist[-8:]:
            dlt = "" if prev is None else f'{(h["crar"] - prev["crar"]) * 1e4:+.1f} bps'
            hrows.append(f'<tr><td>{escape(h["time"])}</td><td class="mono">{escape(h["run_id"][-11:])}</td><td class="r">{h["crar"]:.2%}</td>'
                         f'<td class="r">{dlt}</td><td class="r">{h["decisions"]}</td><td class="r">{h["open"]}</td></tr>')
            prev = h
        hist_html = (f'<div class="tblw"><table class="dt"><thead><tr><th>Time</th><th>Run</th><th class="r">CRAR</th><th class="r">Change</th>'
                     f'<th class="r">Decisions</th><th class="r">Open</th></tr></thead><tbody>{"".join(hrows)}</tbody></table></div>')
    else:
        hist_html = '<div class="s">Each re-run (for example after SME decisions) is listed here with its CRAR change.</div>'
    body += card("Run history", "How the result moved this session", hist_html, "c5", d=.14)
    secs = []
    for sec in dict.fromkeys(x["Section"] for x in led["rows"]):
        secs.append(sec)
    tabs = "".join(f'<button class="{"on" if i == 0 else ""}" data-tab="s{i}">{escape(sec.split(". ", 1)[-1])}</button>' for i, sec in enumerate(secs))
    panes = []
    for i, sec in enumerate(secs):
        rows = []
        for x in [y for y in led["rows"] if y["Section"] == sec]:
            res = x["Result (₹ lakhs or %)"]
            tot = x["Running total"]
            inp = x["Input (₹ lakhs)"]
            isum = x["Formula"].startswith("Σ") or x["Line item"].endswith("(total)") or sec.startswith("E")
            rows.append(f'<tr><td class="r">{x["Step"]}</td><td>{"<b>" if isum else ""}{escape(str(x["Line item"]))}{"</b>" if isum else ""}</td>'
                        f'<td class="mono" title="{escape(str(x["Source (sheet!cell)"]))}">{escape(str(x["Source (sheet!cell)"])[:30])}</td>'
                        f'<td class="r">{"" if inp is None else f"{inp:,.2f}"}</td>'
                        f'<td>{escape(str(x["Treatment / weight"]))}</td><td title="{escape(str(x["Formula"]))}">{escape(str(x["Formula"])[:60])}</td>'
                        f'<td class="r"><b>{"" if res is None else (f"{res:,.4f}" if isinstance(res, float) and abs(res) < 100 and ("ratio" in str(x["Line item"]).lower() or "CRAR" in str(x["Line item"])) else f"{res:,.2f}")}</b></td>'
                        f'<td class="r">{"" if tot is None else f"{tot:,.2f}"}</td><td class="mono">{escape(str(x["Rule"]))}</td><td>{escape(str(x["RBI paragraph"]))}</td>'
                        f'<td title="{escape(str(x["Basis / note"]))}">{escape(str(x["Basis / note"])[:40])}</td></tr>')
        panes.append(f'<div class="pane{" on" if i == 0 else ""}" data-pane="s{i}"><div class="tblw"><table class="dt"><thead><tr><th class="r">#</th><th>Line item</th>'
                     f'<th>Source</th><th class="r">Input ₹ L</th><th>Treatment</th><th>Formula</th><th class="r">Result</th><th class="r">Running</th>'
                     f'<th>Rule</th><th>Para</th><th>Note</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>')
    body += card("The ledger", "Same rows as the CSV download · switch sections with the tabs · ⤢ to expand",
                 f'<div class="tabs" style="margin-bottom:12px;flex-wrap:wrap">{tabs}</div><div class="panes" style="height:430px">{"".join(panes)}</div>',
                 "c12", d=.18, attrs="data-tabs")
    return page("Calculation (step by step)", _date(run), body), {}
