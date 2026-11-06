"""Turn an agent Run into pandas DataFrames. Every tab uses these, so a new tab
only needs to pick a frame (or add one here) - no calculation logic in the UI."""
from __future__ import annotations

import pandas as pd


def metrics(run) -> pd.DataFrame:
    r, av = run.final, run.agent_view
    bench = {b["metric"]: b for b in run.benchmark}
    mins = {"CRAR": run.minimums["crar"], "Tier 1 Ratio": run.minimums["tier1"]}
    rows = []
    for k, v in r.as_dict().items():
        b = bench.get(k)
        rows.append({"Metric": k, "Engine": v, "Minimum": mins.get(k), "Benchmark": b["expected"] if b else None,
                     "Tie-out": b["status"] if b else "n/a", "Agent view (not approved)": av.as_dict()[k]})
    return pd.DataFrame(rows)


def tier1(run) -> pd.DataFrame:
    from capital_agent.engine import CapitalLine
    rows = []
    for a in run.cap_applied:
        if a.applied == "T2_GENERAL_PROVISION":
            continue
        c = a.cls
        rows.append({"Item": c.item_id, "Line item": c.label, "Source": c.source_ref, "Source amount": c.amount,
                     "Applied": a.applied,
                     "Regulatory amount": CapitalLine(c.item_id, c.label, c.amount, a.applied).tier1_effect,
                     "Agent proposal": c.treatment, "Confidence": c.confidence, "Route": c.route, "Rule": c.rule_id,
                     "Citation": c.citation_text, "Basis": a.basis})
    return pd.DataFrame(rows)


def tier2(run) -> pd.DataFrame:
    r = run.final
    return pd.DataFrame([
        {"Component": "Stage 1 ECL (general provision)", "INR lakhs": r.gp_gross, "Reference": "para 13(iii), 16(6)"},
        {"Component": "Cap: 1.25% x Total RWA", "INR lakhs": r.gp_cap, "Reference": "para 13(iii)"},
        {"Component": "Eligible = MIN(provision, cap)", "INR lakhs": r.tier2_gp_eligible, "Reference": ""},
        {"Component": "Tier 1 (Tier 2 limit)", "INR lakhs": r.tier1, "Reference": "para 6(3)"},
        {"Component": "Tier 2 Capital", "INR lakhs": r.tier2, "Reference": ""},
        {"Component": "Provision not recognised", "INR lakhs": r.gp_gross - r.tier2_gp_eligible, "Reference": ""},
    ])


def rwa(run) -> pd.DataFrame:
    rows = []
    for a in run.rwa_applied:
        c = a.cls
        rw = a.applied
        rows.append({"Item": c.item_id, "Exposure": c.label, "Source": c.source_ref, "Value": a.exposure,
                     "Applied RW": rw, "RWA": a.exposure * rw, "Agent RW": c.risk_weight,
                     "Confidence": c.confidence, "Route": c.route, "Rule": c.rule_id, "Citation": c.citation_text,
                     "Basis": a.basis})
    rows.append({"Item": "CCR", "Exposure": "Counterparty credit risk (CEM)", "Source": "Derivative inputs",
                 "Value": run.cem.credit_equivalent, "Applied RW": run.cem.counterparty_rw, "RWA": run.cem.rwa,
                 "Route": "", "Rule": "R-CCR-001/002", "Citation": "para 18(3), 18(8)", "Basis": ""})
    return pd.DataFrame(rows)


def cem(run) -> pd.DataFrame:
    return pd.DataFrame([{"Item": d.item_id, "Deal": d.deal_id, "Contract type": d.contract_type,
                          "Notional (INR)": d.notional_inr, "Notional (lakhs)": d.notional_lakhs,
                          "Residual (yrs)": d.residual_years, "Add-on": d.add_on, "PFE (lakhs)": d.pfe_lakhs,
                          "Source": d.source_ref} for d in run.cem.deals])


def exceptions(run) -> pd.DataFrame:
    return pd.DataFrame([{
        "Exception ID": e.exc_id, "Severity": e.severity, "Category": e.category, "Title": e.title,
        "CRAR impact (bps)": round(e.impact_crar_bps, 1) if e.scenario_overrides else None,
        "Status": e.status, "Decision": e.decision or "", "Reviewer": e.reviewer, "Comment": e.comment,
        "Agent's reading": e.ai_best_guess, "Competing interpretations": e.competing, "Citation": e.citations,
        "Evidence required": e.evidence_required, "Calculated on": e.baseline_basis, "Scenario": e.scenario_desc,
        "Issue": e.issue, "Sample ref": e.maker_ref} for e in run.exceptions])


def sensitivity(run) -> pd.DataFrame:
    base = run.final
    rows = [{"Scenario": "Current basis", "Exception": "-", "Tier 1": base.tier1, "Tier 2": base.tier2,
             "Total RWA": base.total_rwa, "CRAR": base.crar, "Tier 1 ratio": base.tier1_ratio, "vs baseline (bps)": 0.0,
             "Breach": "No"}]
    for e in run.exceptions:
        if e.scenario_overrides and e.status == "OPEN":
            r = run._compute(e.scenario_overrides)
            rows.append({"Scenario": e.title, "Exception": e.exc_id, "Tier 1": r.tier1, "Tier 2": r.tier2,
                         "Total RWA": r.total_rwa, "CRAR": r.crar, "Tier 1 ratio": r.tier1_ratio,
                         "vs baseline (bps)": (r.crar - base.crar) * 1e4, "Breach": "; ".join(r.breaches) or "No"})
    av = run.agent_view
    rows.append({"Scenario": "All agent proposals accepted", "Exception": "combined", "Tier 1": av.tier1,
                 "Tier 2": av.tier2, "Total RWA": av.total_rwa, "CRAR": av.crar, "Tier 1 ratio": av.tier1_ratio,
                 "vs baseline (bps)": (av.crar - base.crar) * 1e4, "Breach": "; ".join(av.breaches) or "No"})
    return pd.DataFrame(rows)


def classifications(run) -> pd.DataFrame:
    rows = []
    for a in run.cap_applied + run.rwa_applied:
        c = a.cls
        rows.append({"Item": c.item_id, "Kind": c.kind, "Line item": c.label, "Amount": c.amount,
                     "Agent treatment": c.treatment, "Agent RW": c.risk_weight, "Rule": c.rule_id,
                     "Rule title": c.rule_title, "Citation": c.citation_text,
                     "Link": c.citations[0]["url"] if c.citations else None, "Confidence": c.confidence,
                     "Route": c.route, "Mode": c.mode, "Rationale": c.rationale,
                     "Guardrail notes": "; ".join(c.guardrail_notes), "Evidence required": c.evidence_required,
                     "Maker ref": a.maker_ref, "Maker treatment": a.maker_treatment, "Applied": str(a.applied),
                     "Basis": a.basis})
    return pd.DataFrame(rows)


def checks(run) -> pd.DataFrame:
    rows = [{"Check": c.check_id, "Area": c.area, "Description": c.description, "Status": c.status,
             "Expected": c.expected, "Actual": c.actual, "Difference": c.difference, "Detail": c.detail}
            for c in run.checks + run.control_checks]
    rows += [{"Check": "BENCH", "Area": "Benchmark", "Description": f"{b['metric']} vs Expected_Output",
              "Status": b["status"], "Expected": b["expected"], "Actual": b["actual"], "Difference": b["diff"],
              "Detail": ""} for b in run.benchmark]
    df = pd.DataFrame(rows)
    for col in ("Expected", "Actual", "Difference"):   # mixed numbers/text -> text for display
        df[col] = df[col].map(lambda v: "" if v is None else (f"{v:,.4f}" if isinstance(v, (int, float)) else str(v)))
    return df


def audit(run) -> pd.DataFrame:
    df = pd.DataFrame([{"#": e.seq, "Stage": e.stage, "Item": e.item_id, "Description": e.description,
                        "Source": e.source_ref, "Input": e.input_value, "Rule": e.rule_id, "Citation": e.citation,
                        "Treatment": e.treatment, "Output": e.output_value, "Actor": e.actor} for e in run.audit])
    for col in ("Input", "Output"):
        df[col] = df[col].map(lambda v: "" if v is None else str(v))
    return df


def rules(run) -> pd.DataFrame:
    return pd.DataFrame([{"Rule": r["id"], "Area": r["area"], "Title": r["title"], "Treatment": r["treatment"],
                          "Risk weight": r.get("risk_weight"), "Interpretive": bool(r.get("interpretive")),
                          "Confidence": r["default_confidence"],
                          "Paragraphs": ", ".join(run.kb.get(p).para for p in r.get("citations", [])),
                          "Effective from": str(r["effective_from"]), "Status": r["status"]}
                         for r in run.rules.rules.values()])


def kb(run) -> pd.DataFrame:
    return pd.DataFrame([{"Passage": p.id, "Para": p.para, "Title": p.title, "Summary": p.text,
                          "Effective from": str(p.effective_from), "Link": p.url} for p in run.kb.passages.values()])
