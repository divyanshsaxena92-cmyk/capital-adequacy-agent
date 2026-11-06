"""Basel III assessment (RBI implementation for commercial banks).

For a bank this is the binding framework; for an NBFC it is a benchmark lens - NBFC compliance is governed by the
NBFC Capital Adequacy Directions, and that verdict is unchanged.

RBI Basel III (Commercial Banks - Prudential Norms on Capital Adequacy Directions, 2025):
  minimum CET1 5.5% · Tier 1 7% · total capital (CRAR) 9% of RWA, plus
  capital conservation buffer (CCB) 2.5% CET1 · countercyclical buffer (CCyB) 0-2.5% CET1 (when activated)
  D-SIB surcharge 0.20-0.80% CET1 · leverage ratio >= 4% (D-SIBs) / 3.5% (other banks).
Global BCBS floors for comparison: CET1 4.5% · Tier 1 6% · total 8% · leverage 3%.
"""
from __future__ import annotations

RBI_BANK = {"cet1": 0.055, "tier1": 0.07, "total": 0.09, "ccb": 0.025, "lev_dsib": 0.04, "lev_other": 0.035}
BCBS = {"cet1": 0.045, "tier1": 0.06, "total": 0.08, "ccb": 0.025, "lev": 0.03}
DSIB_BUCKETS = [("None", 0.0), ("Bucket 1 · 0.20%", 0.002), ("Bucket 2 · 0.40%", 0.004), ("Bucket 3 · 0.60%", 0.006),
                ("Bucket 4 · 0.80%", 0.008)]
CCYB_LEVELS = [0.0, 0.005, 0.01, 0.015, 0.02, 0.025]
AT1_WORDS = ("perpetual", "pdi", "additional tier 1", "at1", "compulsorily convertible preference")


def capital_stack(run) -> dict:
    """CET1 / AT1 / Tier 2 from the engine's applied treatments."""
    r = run.final
    at1 = sum(a.cls.amount for a in run.cap_applied
              if a.applied == "T1_INCLUDE" and any(w in a.cls.label.lower() for w in AT1_WORDS))
    cet1 = r.tier1 - at1
    return {"cet1": cet1, "at1": at1, "tier1": r.tier1, "tier2": r.tier2, "gp_gross": r.gp_gross,
            "credit_rwa": r.total_rwa}


def leverage_exposure(run) -> dict:
    """Tier 1 / exposure: balance-sheet assets less assets already deducted from Tier 1, with the on-balance-sheet
    derivative asset replaced by its counterparty exposure (replacement cost + PFE). No off-balance-sheet data."""
    ta = run.ds.find("^total assets")
    total_assets = ta.amount if ta else 0.0
    deducted = sum(abs(a.cls.amount) for a in run.cap_applied if a.applied == "T1_DEDUCT")
    deriv = run.ds.find("derivative financial")
    deriv_asset = deriv.amount if deriv else 0.0
    on_bs = total_assets - deducted - deriv_asset
    exposure = on_bs + run.cem.credit_equivalent
    return {"total_assets": total_assets, "less_deductions": deducted, "less_derivative_asset": deriv_asset,
            "on_balance_sheet": on_bs, "derivatives_cem": run.cem.credit_equivalent, "off_balance_sheet": 0.0,
            "exposure": exposure}


def conservation(cet1_ratio: float, buffer: float) -> float:
    """Share of earnings to be conserved when CET1 sits inside the combined buffer (Basel III quartile table)."""
    if buffer <= 0:
        return 0.0
    pos = (cet1_ratio - RBI_BANK["cet1"]) / buffer
    if pos >= 1:
        return 0.0
    if pos < 0.25:
        return 1.0
    if pos < 0.5:
        return 0.8
    if pos < 0.75:
        return 0.6
    return 0.4


def assess(run, dsib: float = 0.0, ccyb: float = 0.0, op_addon: float = 0.0) -> dict:
    """op_addon: illustrative market + operational risk RWA as a share of credit RWA (not in the source data)."""
    st = capital_stack(run)
    lev = leverage_exposure(run)
    credit_rwa = st["credit_rwa"]
    rwa = credit_rwa * (1 + op_addon)
    t2 = min(st["gp_gross"], 0.0125 * credit_rwa)                 # GP cap on credit RWA
    total = st["tier1"] + t2
    buf = RBI_BANK["ccb"] + ccyb + dsib
    ratios = {"cet1": st["cet1"] / rwa, "tier1": st["tier1"] / rwa, "total": total / rwa,
              "leverage": st["tier1"] / lev["exposure"] if lev["exposure"] else 0.0}
    req = {"cet1": RBI_BANK["cet1"] + buf, "tier1": RBI_BANK["tier1"] + buf, "total": RBI_BANK["total"] + buf,
           "leverage": RBI_BANK["lev_dsib"] if dsib > 0 else RBI_BANK["lev_other"]}
    head = {k: ratios[k] - req[k] for k in ratios}
    binding = min(head, key=lambda k: head[k])
    rows = [{"metric": k, "value": ratios[k], "minimum": (RBI_BANK[k] if k != "leverage" else req["leverage"]),
             "required": req[k], "headroom": head[k], "bcbs": BCBS["lev" if k == "leverage" else k], "ok": head[k] >= 0}
            for k in ("cet1", "tier1", "total", "leverage")]
    return {"framework": "binding" if getattr(run, "entity_type", "") == "BANK" else "benchmark",
            "stack": st, "tier2_basel": t2, "leverage": lev, "rwa": rwa, "op_addon": op_addon, "dsib": dsib, "ccyb": ccyb,
            "buffer": buf, "ratios": ratios, "required": req, "headroom": head, "binding": binding, "rows": rows,
            "conservation": conservation(ratios["cet1"], buf), "compliant": all(v >= 0 for v in head.values()),
            "gaps": ["Market-risk RWA not in source data", "Operational-risk RWA not in source data",
                     "Off-balance-sheet exposures not supplied (leverage exposure may be understated)",
                     "AT1 / Tier 2 instruments: none in source - Basel III eligibility criteria not tested"]}
