"""Stage 2 & 8 - Data validation, reconciliation and control checks (deterministic)."""
from __future__ import annotations

from dataclasses import dataclass

from .ingest import Dataset, norm

TOL = 0.01  # INR lakhs


@dataclass
class Check:
    check_id: str
    area: str
    description: str
    status: str            # PASS | FAIL | WARN
    expected: float | str | None = None
    actual: float | str | None = None
    detail: str = ""

    @property
    def difference(self):
        if isinstance(self.expected, (int, float)) and isinstance(self.actual, (int, float)):
            return round(self.actual - self.expected, 4)
        return None


def _tie(cid, area, desc, expected, actual, detail="", warn=False) -> Check:
    ok = abs(expected - actual) <= TOL
    return Check(cid, area, desc, "PASS" if ok else ("WARN" if warn else "FAIL"), round(expected, 4), round(actual, 4), detail)


def _num(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    try:
        return float(str(v).replace(",", "").replace("=", ""))
    except (TypeError, ValueError):
        return None


def source_checks(ds: Dataset) -> list[Check]:
    c: list[Check] = []
    f = ds.find
    v = lambda pat, sec="FACE": (f(pat, sec).amount if f(pat, sec) else 0.0)

    # ---- structure & metadata
    c.append(Check("V01", "Ingestion", "Reporting date identified", "PASS" if ds.reporting_date else "FAIL",
                   actual=str(ds.reporting_date)))
    c.append(Check("V02", "Ingestion", "Units / currency identified", "PASS" if ds.units else "FAIL", actual=ds.units))
    dates = {str(r.get("reporting_date"))[:10] for tbl in (ds.capital_inputs, ds.rwa_inputs, ds.bs_inputs)
             for r in tbl if r.get("reporting_date")}
    c.append(Check("V03", "Ingestion", "Reporting date consistent across input sheets",
                   "PASS" if len(dates) <= 1 else "FAIL", actual=", ".join(sorted(dates))))

    # ---- balance sheet arithmetic
    fa = ["cash and cash equivalents", "bank balances other", "derivative financial", "trade receivables",
          "^loans$", "^investments$", "other financial assets"]
    c.append(_tie("V04", "Balance sheet", "Financial assets sum to subtotal", v("total financial assets"),
                  sum(v(p) for p in fa)))
    nfa = ["current tax assets", "deferred tax assets", "property, plant", "right of use", "other non-financial assets"]
    c.append(_tie("V05", "Balance sheet", "Non-financial assets sum to subtotal", v("total non-financial assets"),
                  sum(v(p) for p in nfa)))
    c.append(_tie("V06", "Balance sheet", "Total assets = Total liabilities and equity", v("^total assets"),
                  v("total liabilities and equity")))
    fl = ["^derivative financial", "dues of micro", "dues of creditors", "debt securities", "borrowings",
          "other financial liabilities"]
    liab_items = [sv for sv in ds.section_items("FACE")]
    # liabilities appear after 'liabilities and equity' heading; take matches after total assets
    after = False
    fl_sum = 0.0
    for sv in liab_items:
        if "total assets" in norm(sv.label):
            after = True
            continue
        if after and any(__import__("re").search(p, norm(sv.label)) for p in fl):
            fl_sum += sv.amount
        if after and "total financial liabilities" in norm(sv.label):
            break
    c.append(_tie("V07", "Balance sheet", "Financial liabilities sum to subtotal", v("total financial liabilities"), fl_sum))
    c.append(_tie("V08", "Balance sheet", "Equity share capital + Other equity = Total equity", v("^total equity"),
                  v("equity share capital") + v("^other equity")))

    # ---- notes tie to face
    n23 = [sv for sv in ds.section_items("Note 23") if "total" not in norm(sv.label) and "of which" not in norm(sv.label)]
    c.append(_tie("V09", "Notes", "Note 23 Other equity breakup ties to face", v("^other equity"), sum(s.amount for s in n23)))
    sub = [sv.amount for sv in ds.section_items("Note 23") if "of which" in norm(sv.label)]
    par = f("equity others", "Note 23")
    if par:
        c.append(_tie("V10", "Notes", "Equity others = sum of 'of which' components", par.amount, sum(sub)))
    n10 = [sv for sv in ds.section_items("Note 10") if "total" not in norm(sv.label)]
    c.append(_tie("V11", "Notes", "Note 10 Other financial assets breakup ties to face", v("other financial assets"),
                  sum(s.amount for s in n10)))
    n18 = [sv for sv in ds.section_items("Note 18") if "total" not in norm(sv.label)]
    c.append(_tie("V12", "Notes", "Note 18 Other financial liabilities breakup ties to face",
                  v("other financial liabilities"), sum(s.amount for s in n18)))
    n7 = [sv for sv in ds.section_items("Note 7") if "total" not in norm(sv.label)]
    c.append(_tie("V13", "Notes", "Note 7 Trade receivables breakup ties to face", v("trade receivables"),
                  sum(s.amount for s in n7)))
    pre = f("prepaid", "Note 14")
    c.append(Check("V14", "Notes", "Note 14 prepaid component <= Other non-financial assets",
                   "PASS" if pre and pre.amount <= v("other non-financial assets") + TOL else "FAIL",
                   v("other non-financial assets"), pre.amount if pre else None))

    # ---- loan staging reconciliation
    g1, e1 = f("stage 1 - gross", "Note 8"), f("stage 1 - impairment", "Note 8")
    if g1 and e1:
        net1 = g1.amount + e1.amount
        c.append(Check("V15", "Loans", "Net loans on face reconcile to stage-wise gross less ECL",
                       "PASS" if abs(net1 - v("^loans$")) <= TOL else "FAIL", round(v("^loans$"), 2), round(net1, 2),
                       "Only Stage 1 data provided. Stage 1 gross less ECL exceeds net loans on the face by "
                       f"{net1 - v('^loans$'):,.2f} lakhs; Stage 2/3 balances, EIR and other adjustments are missing."))

    # ---- maker input sheets tie to balance sheet
    bs_lookup = {
        "paid-up": v("equity share capital"), "securities premium": v("securities premium", "Note 23"),
        "statutory reserve": v("statutory reserve", "Note 23"), "retained earnings": v("retained earnings", "Note 23"),
        "deferred tax": v("deferred tax assets"), "prepaid": v("prepaid", "Note 14"),
        "general provisions": abs(v("stage 1 - impairment", "Note 8")),
    }
    for rec in ds.capital_inputs:
        lbl = norm(rec.get("line_item", ""))
        for k, bsv in bs_lookup.items():
            if k in lbl:
                raw = _num(rec.get("raw_amount_inr_lakhs")) or 0.0
                c.append(_tie(f"V16-{rec['item_id']}", "Maker inputs",
                              f"Capital input '{rec['line_item']}' raw amount ties to balance sheet", bsv, raw,
                              f"{rec['_sheet']}!{rec['_cells'].get('raw_amount_inr_lakhs')}"))
    bad = [r["item_id"] for r in ds.capital_inputs
           if r.get("agent_adjusted_amount") is not None and _num(r["agent_adjusted_amount"]) is None]
    malformed = [r["item_id"] for r in ds.capital_inputs if str(r.get("agent_adjusted_amount", "")).startswith("-=")]
    c.append(Check("V17", "Maker inputs", "Adjusted-amount column holds numeric values only",
                   "WARN" if bad or malformed else "PASS", actual=", ".join(bad + malformed),
                   detail="Text instructions ('same', 'cap at 1.25% RWA') and malformed entries ('-=8385.36') "
                          "in a numeric column; the agent interprets them but they should be cleaned at source."))
    for rec in ds.rwa_inputs:
        val, rw, rwa = _num(rec.get("asset_value_inr_lakhs")), _num(rec.get("risk_weight")), _num(rec.get("rwa_inr_lakhs"))
        if None not in (val, rw, rwa):
            c.append(_tie(f"V18-{rec['item_id']}", "Maker inputs", f"RWA = value x RW for '{rec['asset_class']}'",
                          val * rw, rwa, f"{rec['_sheet']}!{rec['_cells'].get('rwa_inr_lakhs')}"))

    # ---- duplicates / completeness
    ids = [r["item_id"] for tbl in (ds.capital_inputs, ds.rwa_inputs, ds.derivative_inputs) for r in tbl]
    c.append(Check("V19", "Data quality", "No duplicate item IDs", "PASS" if len(ids) == len(set(ids)) else "FAIL"))
    for d in ds.derivative_inputs:
        ok = d["maturity_date"] and d["trade_date"] and d["maturity_date"] > ds.reporting_date >= d["trade_date"]
        c.append(Check(f"V20-{d['item_id']}", "Derivatives", f"{d['deal_id_masked']}: trade <= reporting < maturity",
                       "PASS" if ok else "FAIL"))
    return c
