"""Calculation ledger - every step from source cell to CRAR, with the formula used, so the result can be validated
outside the tool (CSV opens in Excel). The ledger re-derives every total independently from the line items and
then checks each one against the engine; any difference is reported in the CHECK rows.
"""
from __future__ import annotations

import csv
import io

COLUMNS = ["Step", "Section", "Line item", "Source (sheet!cell)", "Input (₹ lakhs)", "Treatment / weight", "Formula",
           "Result (₹ lakhs or %)", "Running total", "Rule", "RBI paragraph", "Basis / note"]


def _paras(c) -> str:
    return "; ".join(x.get("para", "") for x in c.citations) if c.citations else ""


def build(run) -> dict:
    """Returns {"rows": [...], "checks": [...], "reproduced": bool}."""
    r, cem, m = run.final, run.cem, run.minimums
    rows, n = [], [0]

    def add(section, item, src="", inp=None, treat="", formula="", result=None, running=None, rule="", para="", note=""):
        n[0] += 1
        rows.append({"Step": n[0], "Section": section, "Line item": item, "Source (sheet!cell)": src,
                     "Input (₹ lakhs)": inp, "Treatment / weight": treat, "Formula": formula,
                     "Result (₹ lakhs or %)": result, "Running total": running, "Rule": rule, "RBI paragraph": para,
                     "Basis / note": note})

    # A. Tier 1
    t1 = 0.0
    for a in run.cap_applied:
        if a.applied == "T2_GENERAL_PROVISION":
            continue
        c = a.cls
        eff = c.amount if a.applied == "T1_INCLUDE" else (-abs(c.amount) if a.applied == "T1_DEDUCT" else 0.0)
        t1 += eff
        f = {"T1_INCLUDE": "+ amount", "T1_DEDUCT": "− |amount| (deduction)", "T1_EXCLUDE": "0 (not counted)"}.get(a.applied, a.applied)
        add("A. Tier 1 capital", c.label, c.source_ref, round(c.amount, 4), a.applied, f, round(eff, 4), round(t1, 4),
            c.rule_id or "", _paras(c), a.basis)
    add("A. Tier 1 capital", "Tier 1 capital (total)", "", None, "", "Σ of results above", round(t1, 4), round(t1, 4),
        "", "6, 7, 9", "")

    # B. Tier 2
    gp = sum(abs(a.cls.amount) for a in run.cap_applied if a.applied == "T2_GENERAL_PROVISION")
    for a in run.cap_applied:
        if a.applied == "T2_GENERAL_PROVISION":
            add("B. Tier 2 capital", a.cls.label, a.cls.source_ref, round(a.cls.amount, 4), "T2_GENERAL_PROVISION",
                "|amount| into the provision pool", round(abs(a.cls.amount), 4), None, a.cls.rule_id or "", _paras(a.cls), a.basis)

    # C. RWA on balance sheet
    rwa_bs = 0.0
    for a in run.rwa_applied:
        v = a.exposure * a.applied
        rwa_bs += v
        add("C. Risk-weighted assets", a.cls.label, a.cls.source_ref, round(a.exposure, 4), f"{a.applied:.0%}",
            f"{a.exposure:,.2f} × {a.applied:.0%}", round(v, 4), round(rwa_bs, 4), a.cls.rule_id or "", _paras(a.cls), a.basis)
    add("C. Risk-weighted assets", "On-balance-sheet RWA (total)", "", None, "", "Σ exposure × risk weight", round(rwa_bs, 4),
        round(rwa_bs, 4), "", "18(1)", "")

    # D. Derivatives (CEM)
    pfe = 0.0
    for d in cem.deals:
        pfe += d.pfe_lakhs
        add("D. Derivatives (CEM)", f"{d.deal_id} PFE", d.source_ref, round(d.notional_lakhs, 4), f"add-on {d.add_on:.1%}",
            f"notional {d.notional_lakhs:,.2f} × {d.add_on:.1%} (residual {d.residual_years:.2f} yrs)", round(d.pfe_lakhs, 4),
            round(pfe, 4), "R-RWA-CEM", "18(8)", "")
    add("D. Derivatives (CEM)", "Replacement cost (positive MTM)", cem.rc_source_ref, round(cem.replacement_cost, 4), "",
        "aggregate derivative asset (no netting)", round(cem.replacement_cost, 4), None, "R-RWA-CEM", "18(8), 18(9)", "")
    ce = cem.replacement_cost + pfe
    add("D. Derivatives (CEM)", "Credit equivalent", "", None, "", f"RC {cem.replacement_cost:,.2f} + PFE {pfe:,.2f}", round(ce, 4),
        None, "", "18(8)", "")
    rwa_ccr = ce * cem.counterparty_rw
    add("D. Derivatives (CEM)", "Counterparty RWA", "", round(ce, 4), f"{cem.counterparty_rw:.0%}",
        f"{ce:,.2f} × {cem.counterparty_rw:.0%}", round(rwa_ccr, 4), None, "", "18(3)", "counterparty weight per maker")

    # E. Totals and ratios
    total_rwa = rwa_bs + rwa_ccr
    add("E. Totals and ratios", "Total RWA", "", None, "", f"{rwa_bs:,.2f} + {rwa_ccr:,.2f}", round(total_rwa, 4), None, "", "", "")
    cap = 0.0125 * total_rwa
    add("B. Tier 2 capital", "Stage 1 ECL provision pool", "", None, "", "Σ provisions above", round(gp, 4), None, "", "13(iii)", "")
    add("B. Tier 2 capital", "Cap: 1.25% of total RWA", "", round(total_rwa, 4), "1.25%", f"{total_rwa:,.2f} × 1.25%", round(cap, 4),
        None, "", "13(iii)", "")
    elig = min(gp, cap)
    t2 = min(elig, max(t1, 0.0))
    add("B. Tier 2 capital", "Tier 2 capital", "", None, "", "min(provision pool, cap, Tier 1)", round(t2, 4), None, "", "13(iii), 6(3)",
        f"not recognised: {gp - elig:,.2f}")
    crar = (t1 + t2) / total_rwa if total_rwa else 0.0
    t1r = t1 / total_rwa if total_rwa else 0.0
    add("E. Totals and ratios", "Total capital", "", None, "", f"Tier 1 {t1:,.2f} + Tier 2 {t2:,.2f}", round(t1 + t2, 4), None, "", "", "")
    add("E. Totals and ratios", "CRAR", "", None, "", f"{t1 + t2:,.2f} ÷ {total_rwa:,.2f}", round(crar * 100, 6), None, "", "6",
        f"minimum {m['crar']:.0%} · headroom {(crar - m['crar']) * 100:+.2f} pp")
    add("E. Totals and ratios", "Tier 1 ratio", "", None, "", f"{t1:,.2f} ÷ {total_rwa:,.2f}", round(t1r * 100, 6), None, "", "6",
        f"minimum {m['tier1']:.0%} · headroom {(t1r - m['tier1']) * 100:+.2f} pp")
    b3 = getattr(run, "basel3", None)
    if b3:
        for k, lbl in (("cet1", "CET1 ratio (Basel III lens)"), ("leverage", "Leverage ratio (Basel III lens)")):
            add("F. Basel III lens", lbl, "", None, "", "Tier 1 ÷ " + ("RWA" if k == "cet1" else f"exposure {b3['leverage']['exposure']:,.2f}"),
                round(b3["ratios"][k] * 100, 6), None, "R-B3-001" if k == "cet1" else "R-B3-005", "Commercial Banks Directions",
                f"requirement incl. buffers {b3['required'][k]:.2%} · {b3['framework']}")

    # G. Independent check against the engine
    checks = []
    for name, mine, eng, tol in (("Tier 1", t1, r.tier1, .005), ("Tier 2", t2, r.tier2, .005), ("On-balance-sheet RWA", rwa_bs, r.rwa_credit_on_bs, .005),
                                 ("Derivatives RWA", rwa_ccr, r.rwa_ccr, .005), ("Total RWA", total_rwa, r.total_rwa, .005),
                                 ("CRAR (%)", crar * 100, r.crar * 100, 1e-6), ("Tier 1 ratio (%)", t1r * 100, r.tier1_ratio * 100, 1e-6)):
        ok = abs(mine - eng) <= tol
        checks.append({"metric": name, "ledger": mine, "engine": eng, "difference": mine - eng, "ok": ok})
        add("G. Check vs engine", name, "", None, "", "ledger − engine", round(mine - eng, 8), None, "", "",
            "MATCH" if ok else "DIFFERENCE - investigate")
    order = {s: i for i, s in enumerate(["A. Tier 1 capital", "B. Tier 2 capital", "C. Risk-weighted assets", "D. Derivatives (CEM)",
                                         "E. Totals and ratios", "F. Basel III lens", "G. Check vs engine"])}
    rows.sort(key=lambda x: (order.get(x["Section"], 99), x["Step"]))
    for i, row in enumerate(rows, 1):
        row["Step"] = i
    return {"rows": rows, "checks": checks, "reproduced": all(c["ok"] for c in checks)}


def to_csv(run) -> bytes:
    """UTF-8 with BOM so Excel shows ₹ correctly. A header block records what was calculated and when."""
    led = build(run)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Capital adequacy calculation ledger"])
    w.writerow(["Entity", run.ds.entity_name if hasattr(run.ds, "entity_name") else "", "Reporting date", str(run.ds.reporting_date),
                "Run", run.run_id, "Status", run.status])
    w.writerow(["Framework", run.rules.framework, "Rule library", run.rules.version, "Knowledge base", run.kb.version,
                "Ledger reproduces engine", "YES" if led["reproduced"] else "NO"])
    w.writerow([])
    w.writerow(COLUMNS)
    for row in led["rows"]:
        w.writerow(["" if row[c] is None else row[c] for c in COLUMNS])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")
