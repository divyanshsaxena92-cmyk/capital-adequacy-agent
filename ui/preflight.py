"""Pre-flight: tell the user, before running, whether an uploaded workbook has what the agent needs.

Edit REQUIRED_BS_ITEMS / SHEET_ROLES to extend support for new templates.
"""
from __future__ import annotations

from openpyxl import load_workbook

from capital_agent.ingest import ingest
from capital_agent.framework import profile_for_dataset, preflight_diagnostics

# (pattern used by Dataset.find, section, human name, required?)
REQUIRED_BS_ITEMS = [
    ("^total assets", "FACE", "Total assets", True),
    ("^equity share capital", "FACE", "Equity share capital", True),
    ("cash and cash equivalents", "FACE", "Cash and cash equivalents", True),
    ("bank balances other", "FACE", "Bank balances other than cash", True),
    ("^trade receivables$", "FACE", "Trade receivables", True),
    ("^loans$", "FACE", "Loans", True),
    ("other non-financial assets", "FACE", "Other non-financial assets", True),
    ("derivative financial", "FACE", "Derivative financial instruments (asset)", True),
    ("^other equity", "FACE", "Other equity", True),
    ("securities premium", "Note 23", "Note 23 - Other equity breakup", False),
    ("stage 1 - impairment", "Note 8", "Note 8 - Stage 1 ECL", False),
    ("prepaid", "Note 14", "Note 14 - Prepaid expenses", False),
    ("security deposits", "Note 10", "Note 10 - Other financial assets breakup", False),
]

SHEET_ROLES = [
    ("balance_sheet", "Presentation balance sheet (A1 starts 'Balance Sheet as at ...')", True),
    ("derivative_inputs", "Deal-level derivatives (Deal_ID_Masked, Maturity_Date, Pay_Notional ...)", False),
    ("capital_inputs", "Maker capital schedule (Item_ID, Capital_Category, Raw_Amount_INR_Lakhs ...)", False),
    ("rwa_inputs", "Maker RWA schedule (Item_ID, Asset_Class, Risk_Weight ...)", False),
    ("expected_output", "Benchmark values (Metric, Expected_Value)", False),
    ("maker_exceptions", "Maker exception list (Exception_ID, Issue, Severity)", False),
    ("market_inputs", "Commercial-bank market-risk RWA schedule (Item_ID, Market_Risk_RWA)", False),
    ("operational_inputs", "Commercial-bank operational-risk schedule (Item_ID, Operational_Risk_RWA)", False),
]


def uncached_formulas(path: str, sheet: str) -> int:
    """Formulas with no stored result => file was not calculated/saved in Excel. Streams one sheet only."""
    fw = load_workbook(path, read_only=True)
    vw = load_workbook(path, read_only=True, data_only=True)
    n = 0
    for fr, vr in zip(fw[sheet].iter_rows(values_only=True), vw[sheet].iter_rows(values_only=True)):
        for f, v in zip(fr, vr):
            if isinstance(f, str) and f.startswith("=") and v is None:
                n += 1
    fw.close()
    vw.close()
    return n


def run(path: str) -> dict:
    ds = ingest(path)
    profile = profile_for_dataset(ds)
    roles = [{"Sheet role": r, "Expected": d, "Found as": ds.sheet_map.get(r, "-"),
              "Status": "OK" if r in ds.sheet_map else ("MISSING" if req else "optional - absent")}
             for r, d, req in SHEET_ROLES]
    items, blocking = [], []
    if "balance_sheet" in ds.sheet_map:
        for pat, sec, name, req in REQUIRED_BS_ITEMS:
            sv = ds.find(pat, sec)
            ok = sv is not None
            items.append({"Item": name, "Status": "OK" if ok else ("MISSING" if req else "optional - absent"),
                          "Value": sv.amount if ok else None, "Cell": sv.ref if ok else ""})
            if req and not ok:
                blocking.append(f"Balance sheet item not found: {name}")
        unc = uncached_formulas(path, ds.sheet_map["balance_sheet"])
        if unc:
            blocking.append(f"{unc} formula cell(s) on '{ds.sheet_map['balance_sheet']}' have no calculated value - "
                            "open the file in Excel, let it calculate, save, and re-upload.")
    else:
        blocking.append("No presentation balance sheet found (cell A1 should read 'Balance Sheet as at <date>').")
    if ds.reporting_date is None:
        blocking.append("Reporting date not found.")
    diagnostics = preflight_diagnostics(ds, profile)
    blocking.extend(diagnostics)
    return {"ds": ds, "roles": roles, "items": items, "blocking": blocking, "log": ds.ingestion_log,
            "large_sheets": ds.large_sheets, "profile": profile, "diagnostics": diagnostics}
