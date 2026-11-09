"""Stage 1 - Data ingestion.

Reads the client workbook, works out what each sheet *is* from its headers (so
renamed or reordered sheets still load), parses the semi-structured balance
sheet including note breakups, and keeps a sheet!cell reference for every
number so the audit trail can point back to the exact source cell.
Source data is never modified.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import Any

from openpyxl import load_workbook

# Header signatures used to identify sheet roles regardless of sheet name.
SHEET_SIGNATURES = {
    "bs_inputs": {"reporting_date", "line_item", "amount_inr_lakhs"},
    "capital_inputs": {"item_id", "capital_category", "raw_amount_inr_lakhs"},
    "rwa_inputs": {"item_id", "asset_class", "risk_weight"},
    "derivative_inputs": {"deal_id_masked", "maturity_date", "pay_notional"},
    "maker_rules": {"rule_id", "capital_area", "calculation_logic"},
    "expected_output": {"metric", "expected_value"},
    "maker_exceptions": {"exception_id", "issue", "severity"},
}

MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def norm(text: str) -> str:
    """Lower-case, unify dashes/whitespace for matching."""
    t = str(text).lower().replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class SourceValue:
    key: str
    label: str
    amount: float
    sheet: str
    cell: str
    section: str
    note: Any = None

    @property
    def ref(self) -> str:
        return f"'{self.sheet}'!{self.cell}"


@dataclass
class Dataset:
    path: str
    sheet_map: dict = field(default_factory=dict)
    reporting_date: dt.date | None = None
    units: str | None = None
    currency: str | None = None
    bs: dict = field(default_factory=dict)          # key -> SourceValue
    bs_order: list = field(default_factory=list)
    capital_inputs: list = field(default_factory=list)
    rwa_inputs: list = field(default_factory=list)
    derivative_inputs: list = field(default_factory=list)
    maker_rules: list = field(default_factory=list)
    expected_output: list = field(default_factory=list)
    maker_exceptions: list = field(default_factory=list)
    bs_inputs: list = field(default_factory=list)
    raw_text: str = ""
    ingestion_log: list = field(default_factory=list)
    large_sheets: list = field(default_factory=list)   # big unrecognised sheets -> route to bigdata.DataStore
    formula_cells: list = field(default_factory=list)
    malformed_cells: list = field(default_factory=list)
    sheet_rows: dict = field(default_factory=dict)
    recognized_headers: dict = field(default_factory=dict)

    # -- lookups -----------------------------------------------------------
    def find(self, pattern: str, section: str | None = None) -> SourceValue | None:
        rx = re.compile(pattern, re.I)
        for key in self.bs_order:
            sv = self.bs[key]
            if section and not sv.section.startswith(section):
                continue
            if rx.search(norm(sv.label)):
                return sv
        return None

    def section_items(self, section_prefix: str) -> list[SourceValue]:
        return [self.bs[k] for k in self.bs_order if self.bs[k].section.startswith(section_prefix)]


def _to_date(v) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    if isinstance(v, (int, float)) and 30000 < v < 60000:  # Excel serial
        return (dt.datetime(1899, 12, 30) + dt.timedelta(days=float(v))).date()
    return None


def _detect_role(headers: set[str]) -> str | None:
    best, best_score = None, 0
    for role, sig in SHEET_SIGNATURES.items():
        score = len(sig & headers)
        if score == len(sig) and score > best_score:
            best, best_score = role, score
    return best


def _read_table(title: str, rows) -> list[dict]:
    """rows: iterable of cell tuples, first one is the header (works with read-only worksheets)."""
    rows = iter(rows)
    header_cells = next(rows, None)
    if header_cells is None:
        return []
    headers = [norm(c.value).replace(" ", "_") if c.value is not None else None for c in header_cells]
    out = []
    for i, r in enumerate(rows, start=2):
        if all(c.value is None for c in r):
            continue
        rec = {"_row": i, "_sheet": title, "_cells": {}}
        for h, c in zip(headers, r):
            if h:
                rec[h] = c.value
                rec["_cells"][h] = getattr(c, "coordinate", None)
        out.append(rec)
    return out


def _parse_balance_sheet(title: str, rows, ds: Dataset) -> None:
    """Parse a presentation-style balance sheet: label | note | amount, with note breakups below."""
    section = "FACE"
    text_lines = []
    for row in rows:
        if not row:
            continue
        label_cell = row[0]
        label = label_cell.value
        if label is None:
            continue
        label = str(label)
        text_lines.append(label)
        nl = norm(label)
        if ds.units is None and "lakh" in nl:
            ds.units = "INR Lakhs"
            ds.currency = "INR"
        if ds.reporting_date is None:
            m = re.search(rf"({MONTHS})\s+(\d{{1,2}}),\s*(\d{{4}})", nl)
            if m:
                ds.reporting_date = dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
        if re.match(r"^note\s+\d+", nl):  # a note header starts a new section
            section = "Note " + re.match(r"^note\s+(\d+)", nl).group(1)
            continue
        # amount = right-most numeric cell in the row
        amt_cell = None
        for c in reversed(row[1:]):
            if isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
                amt_cell = c
                break
        if amt_cell is None or (len(row) > 1 and amt_cell is row[1] and len(row) > 2):
            continue
        note_val = row[1].value if len(row) > 1 else None
        key = f"{section}|{label.strip()}"
        n = 2
        while key in ds.bs:  # same label on both sides of the balance sheet (e.g. derivatives)
            key = f"{section}|{label.strip()}#{n}"
            n += 1
        sv = SourceValue(key=key, label=label.strip(), amount=float(amt_cell.value), sheet=title,
                         cell=amt_cell.coordinate, section=section, note=note_val)
        ds.bs[key] = sv
        ds.bs_order.append(key)
    ds.raw_text = "\n".join(text_lines)


LARGE_ROWS = 20000


def ingest(path: str, large_rows: int = LARGE_ROWS) -> Dataset:
    """Streaming (read-only) load: small role sheets are parsed; big unrecognised sheets are only counted."""
    import itertools
    wb = load_workbook(path, data_only=True, read_only=True)
    formula_wb = load_workbook(path, data_only=False, read_only=True)
    ds = Dataset(path=path)
    for ws in wb.worksheets:
        it = ws.iter_rows()
        first = next(it, None)
        if not first:
            continue
        a1 = first[0].value
        rows = itertools.chain([first], it)
        if a1 and re.search(r"balance sheet as at", norm(a1)):
            ds.sheet_map["balance_sheet"] = ws.title
            _parse_balance_sheet(ws.title, rows, ds)
            ds.ingestion_log.append(f"'{ws.title}': presentation balance sheet; {len(ds.bs)} amounts parsed")
            continue
        headers = {norm(c.value).replace(" ", "_") for c in first if c.value is not None}
        ds.sheet_rows[ws.title] = 1
        role = _detect_role(headers)
        if role is None:
            n = 1
            for _ in it:
                n += 1
                if n > large_rows:
                    break
            if n > large_rows:
                ds.large_sheets.append(ws.title)
                ds.ingestion_log.append(f"'{ws.title}': more than {large_rows:,} rows and not a standard input sheet - "
                                        "use Large data import (streams it into the local data store)")
            else:
                ds.ingestion_log.append(f"'{ws.title}': role not recognised - skipped (flag for review)")
            continue
        ds.sheet_map[role] = ws.title
        ds.recognized_headers[role] = sorted(headers)
        setattr(ds, role, _read_table(ws.title, rows))
        ds.sheet_rows[ws.title] += len(getattr(ds, role))
        ds.ingestion_log.append(f"'{ws.title}': detected as {role} ({len(getattr(ds, role))} rows)")
        numeric_headers = {h for h in headers if any(
                token in h for token in ("amount", "value", "weight", "rwa", "notional", "rate", "capital"))}
        for rec in getattr(ds, role):
                for h in numeric_headers:
                    value = rec.get(h)
                    if value in (None, ""):
                        continue
                    if isinstance(value, bool):
                        ds.malformed_cells.append(f"'{ws.title}'!{rec['_cells'].get(h)} ({h}: boolean)")
                        continue
                    try:
                        float(str(value).replace(",", "").replace("%", "").replace("=", "").strip())
                    except (TypeError, ValueError):
                        ds.malformed_cells.append(f"'{ws.title}'!{rec['_cells'].get(h)} ({h}: {value!r})")
    for ws in formula_wb.worksheets:
        for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        ds.formula_cells.append(f"'{ws.title}'!{cell.coordinate}")
    wb.close()
    formula_wb.close()
    if ds.reporting_date is None:
        for rec in ds.capital_inputs + ds.bs_inputs:
            d = _to_date(rec.get("reporting_date"))
            if d:
                ds.reporting_date = d
                break
    for rec in ds.derivative_inputs:
        for k in ("reporting_date", "trade_date", "maturity_date"):
            rec[k] = _to_date(rec.get(k))
    return ds
