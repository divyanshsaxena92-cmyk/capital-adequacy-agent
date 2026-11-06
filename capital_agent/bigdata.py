"""Large data import - stream big Excel / CSV files into a local SQLite store.

Normal Excel loading reads the whole workbook into memory; a 500k-row loan tape would stall it.
Here every sheet is read row by row (openpyxl read-only mode) and written to SQLite in batches,
so memory stays flat whatever the file size.

    from capital_agent.bigdata import DataStore
    ds = DataStore("store/data.sqlite")
    ds.import_file("loan_tape.xlsx", progress=print)
    ds.tables(); ds.profile("t_loan_tape_sheet1"); ds.preview(...)
    summarise_loan_tape(ds, table, amount_unit="INR")   # feeds the agent's loan exception

Header detection: the header is the first row (within the first 30) with >= 2 text cells that is
followed by data, so title rows above a table don't break the import.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sqlite3
import time

BATCH = 5000
SCAN_ROWS = 30
TYPE_SAMPLE = 2000


def _slug(s: str, maxlen: int = 50) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(s)).strip("_").lower()
    return (s or "col")[:maxlen]


def _clean_columns(raw: list) -> list[str]:
    out, seen = [], {}
    for i, c in enumerate(raw):
        name = _slug(c) if c not in (None, "") else f"col_{i + 1}"
        if name[0].isdigit():
            name = "c_" + name
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        out.append(name)
    return out


def _detect_header(rows: list[tuple]) -> int:
    """Index of the header row within the scanned rows."""
    best, best_score = 0, -1
    for i, r in enumerate(rows[:-1] if len(rows) > 1 else rows):
        texts = sum(isinstance(v, str) and v.strip() != "" for v in r)
        filled_next = sum(v not in (None, "") for v in rows[i + 1]) if i + 1 < len(rows) else 0
        if texts >= 2 and filled_next >= max(2, texts // 2):
            score = texts * 10 + filled_next
            if score > best_score:
                best, best_score = i, score
                if texts >= 3:
                    return i      # first convincing header wins (titles above it have fewer text cells)
    return best


def _norm_value(v):
    if isinstance(v, dt.datetime):
        return v.isoformat(sep=" ")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, str):
        t = v.strip()
        return t if t != "" else None
    return v


def _infer_type(values: list) -> str:
    vals = [v for v in values if v is not None]
    if not vals:
        return "TEXT"
    if all(isinstance(v, bool) or isinstance(v, int) for v in vals):
        return "INTEGER"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return "REAL"
    num = 0
    for v in vals:
        if isinstance(v, str) and re.fullmatch(r"-?[\d,]+(\.\d+)?", v):
            num += 1
    return "REAL" if num == len(vals) else "TEXT"


def _coerce(v, typ):
    if v is None:
        return None
    if typ in ("REAL", "INTEGER") and isinstance(v, str):
        try:
            return float(v.replace(",", ""))
        except ValueError:
            return v
    return v


class DataStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.path = db_path
        self.db = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS _tables (table_name TEXT PRIMARY KEY, source_file TEXT,
            sheet TEXT, header_row INTEGER, n_rows INTEGER, n_cols INTEGER, columns TEXT, original_headers TEXT,
            imported_at TEXT, seconds REAL, kind TEXT)""")

    # ------------------------------------------------------------- import
    def _iter_xlsx(self, path, sheets=None):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            if sheets and ws.title not in sheets:
                continue
            yield ws.title, ws.iter_rows(values_only=True)
        wb.close()

    def _iter_csv(self, path):
        f = open(path, newline="", encoding="utf-8-sig", errors="replace")
        sample = f.read(65536)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        yield os.path.splitext(os.path.basename(path))[0], (tuple(r) for r in csv.reader(f, dialect))

    def import_file(self, path: str, sheets: list[str] | None = None, progress=None,
                    display_name: str | None = None) -> list[dict]:
        name = display_name or os.path.basename(path)
        it = self._iter_csv(path) if path.lower().endswith((".csv", ".txt")) else self._iter_xlsx(path, sheets)
        results = []
        for sheet, rows in it:
            t0 = time.time()
            head = []
            for r in rows:
                head.append(tuple(_norm_value(v) for v in r))
                if len(head) >= SCAN_ROWS:
                    break
            if not any(any(v is not None for v in r) for r in head):
                continue
            h = _detect_header(head)
            original = list(head[h])
            width = max(len(r) for r in head)
            original += [None] * (width - len(original))
            cols = _clean_columns(original)
            buffered = [r for r in head[h + 1:]]
            # type inference from a sample (buffer more rows if needed)
            for r in rows:
                buffered.append(tuple(_norm_value(v) for v in r))
                if len(buffered) >= TYPE_SAMPLE:
                    break
            types = [_infer_type([r[i] if i < len(r) else None for r in buffered]) for i in range(width)]
            table = "t_" + _slug(f"{os.path.splitext(name)[0]}_{sheet}", 60)
            self.db.execute(f'DROP TABLE IF EXISTS "{table}"')
            self.db.execute(f'CREATE TABLE "{table}" ({", ".join(f"{c} {t}" for c, t in zip(cols, types))})')
            ins = f'INSERT INTO "{table}" VALUES ({",".join("?" * width)})'
            n = 0

            def flush(batch):
                self.db.executemany(ins, batch)

            batch = []
            for r in buffered:
                rr = list(r) + [None] * (width - len(r))
                if any(v is not None for v in rr):
                    batch.append([_coerce(v, t) for v, t in zip(rr[:width], types)])
            for r in rows:
                rr = [_norm_value(v) for v in r]
                if not any(v is not None for v in rr):
                    continue
                rr = rr[:width] + [None] * (width - len(rr))
                batch.append([_coerce(v, t) for v, t in zip(rr, types)])
                if len(batch) >= BATCH:
                    flush(batch)
                    n += len(batch)
                    batch = []
                    if progress:
                        progress(sheet, n)
            if batch:
                flush(batch)
                n += len(batch)
            kind = recognise(cols, dict(zip(cols, types)))
            secs = round(time.time() - t0, 2)
            self.db.execute("INSERT OR REPLACE INTO _tables VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (table, name, sheet, h + 1, n, width, json.dumps(cols),
                             json.dumps([str(o) if o is not None else "" for o in original]),
                             dt.datetime.now().isoformat(timespec="seconds"), secs, kind))
            self.db.commit()
            if progress:
                progress(sheet, n)
            results.append({"table": table, "sheet": sheet, "rows": n, "cols": width, "header_row": h + 1,
                            "seconds": secs, "kind": kind})
        return results

    # ------------------------------------------------------------- read
    def tables(self) -> list[dict]:
        cols = ["table_name", "source_file", "sheet", "header_row", "n_rows", "n_cols", "columns",
                "original_headers", "imported_at", "seconds", "kind"]
        out = []
        for r in self.db.execute("SELECT * FROM _tables ORDER BY imported_at DESC"):
            d = dict(zip(cols, r))
            d["columns"] = json.loads(d["columns"])
            d["original_headers"] = json.loads(d["original_headers"])
            out.append(d)
        return out

    def _cols(self, table: str) -> list[str]:
        return [r[1] for r in self.db.execute(f'PRAGMA table_info("{table}")')]

    def _check(self, table: str):
        if table not in {t["table_name"] for t in self.tables()}:
            raise ValueError(f"unknown table {table}")

    def profile(self, table: str) -> list[dict]:
        self._check(table)
        out = []
        n = self.db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for c, typ in [(r[1], r[2]) for r in self.db.execute(f'PRAGMA table_info("{table}")')]:
            nn, nd = self.db.execute(f'SELECT COUNT("{c}"), COUNT(DISTINCT "{c}") FROM "{table}"').fetchone()
            row = {"column": c, "type": typ, "non_null": nn, "null_pct": round(100 * (1 - nn / n), 1) if n else 0,
                   "distinct": nd}
            if typ in ("REAL", "INTEGER"):
                mn, mx, sm = self.db.execute(f'SELECT MIN("{c}"), MAX("{c}"), SUM("{c}") FROM "{table}"').fetchone()
                row.update({"min": mn, "max": mx, "sum": sm})
            else:
                top = self.db.execute(f'SELECT "{c}", COUNT(*) k FROM "{table}" WHERE "{c}" IS NOT NULL '
                                      f'GROUP BY 1 ORDER BY k DESC LIMIT 3').fetchall()
                row["top_values"] = ", ".join(f"{v} ({k:,})" for v, k in top)
            out.append(row)
        return out

    def preview(self, table: str, where: dict | None = None, limit: int = 200, offset: int = 0):
        """Rows with simple equality / contains filters on whitelisted columns (no free SQL)."""
        self._check(table)
        cols = self._cols(table)
        clauses, args = [], []
        for c, v in (where or {}).items():
            if c not in cols or v in (None, ""):
                continue
            clauses.append(f'CAST("{c}" AS TEXT) LIKE ?')
            args.append(f"%{v}%")
        sql = f'SELECT * FROM "{table}"' + (" WHERE " + " AND ".join(clauses) if clauses else "")
        total = self.db.execute(sql.replace("SELECT *", "SELECT COUNT(*)", 1), args).fetchone()[0]
        rows = self.db.execute(sql + " LIMIT ? OFFSET ?", args + [int(limit), int(offset)]).fetchall()
        return cols, rows, total

    def drop(self, table: str):
        self._check(table)
        self.db.execute(f'DROP TABLE "{table}"')
        self.db.execute("DELETE FROM _tables WHERE table_name=?", (table,))
        self.db.commit()


# ------------------------------------------------------------------ recognition
SYN = {
    "loan_id": ["loan_id", "loan_no", "loan_number", "account_no", "account_number", "agreement_no", "lan", "contract_id"],
    "outstanding": ["gross_outstanding", "principal_outstanding", "outstanding", "pos", "gross_carrying_amount",
                    "os_amount", "balance", "outstanding_amount", "exposure"],
    "ecl": ["ecl", "ecl_amount", "provision", "impairment", "impairment_allowance", "expected_credit_loss"],
    "stage": ["stage", "ecl_stage", "ifrs9_stage", "ind_as_stage", "staging"],
    "product": ["product", "product_type", "scheme", "segment", "loan_type", "product_category", "asset_class"],
    "secured": ["secured", "secured_flag", "is_secured", "security_type", "collateral"],
}


AMOUNT_KEYS = {"outstanding", "ecl"}


def _pick(cols: list[str], key: str, types: dict | None = None, taken: set | None = None) -> str | None:
    """Best column for a role: exact synonym > prefix > contains. Amount roles must be numeric columns."""
    taken = taken or set()
    ok = lambda c: c not in taken and (key not in AMOUNT_KEYS or types is None
                                       or types.get(c) in ("REAL", "INTEGER"))
    for test in (lambda c, s: c == s, lambda c, s: c.startswith(s + "_") or c.startswith(s),
                 lambda c, s: s in c):
        for syn in SYN[key]:
            for c in cols:
                if ok(c) and test(c, syn):
                    return c
    return None


def pick_columns(cols: list[str], types: dict | None = None) -> dict:
    """Assign roles in an order that avoids collisions (stage before ecl, so 'ecl_stage' is not read as ECL)."""
    taken, out = set(), {}
    for key in ("loan_id", "stage", "product", "outstanding", "ecl", "secured"):
        c = _pick(cols, key, types, taken)
        out[key] = c
        if c:
            taken.add(c)
    return out


def recognise(cols: list[str], types: dict | None = None) -> str:
    r = pick_columns(cols, types)
    if r["loan_id"] and r["outstanding"] and (r["stage"] or r["product"]):
        return "loan_tape"
    if {"deal_id_masked", "maturity_date"} <= set(cols) or (any("notional" in c for c in cols) and
                                                         any("maturity" in c for c in cols)):
        return "derivative_deals"
    return "generic"


# Product -> RBI risk-weight bucket (NBFC-CA-2025 para 18(1)). Editable; anything unmatched is flagged.
PRODUCT_BUCKETS = [
    ("Staff loans (0%)", 0.0, ["staff", "employee"]),
    ("Carved out of consumer-credit bucket (100%)", 1.0,
     ["housing", "home loan", "home_loan", "mortgage", "vehicle", "auto", "two wheeler", "two_wheeler", "car",
      "tractor", "gold", "education", "microfinance", "mfi", "shg", "jlg", "lap", "property", "sme", "msme",
      "business", "secured"]),
    ("Retail consumer credit / credit card (125%)", 1.25,
     ["personal", "consumer", "credit card", "credit_card", "card", "bnpl", "durable", "cd loan", "unsecured",
      "pl", "instant", "paylater"]),
]


def bucket_for(product: str | None) -> tuple[str, float | None]:
    p = (product or "").lower()
    for name, rw, keys in PRODUCT_BUCKETS:
        if any(re.search(rf"(^|[^a-z]){re.escape(k)}([^a-z]|$)", p) for k in keys):
            return name, rw
    return "Unmapped - review", None


UNIT = {"INR": 1e5, "INR lakhs": 1.0, "INR crores": 0.01}   # divide by this to get lakhs


def summarise_loan_tape(store: DataStore, table: str, amount_unit: str = "INR") -> dict:
    """Aggregate a loan tape: product -> RBI bucket, stage split, blended risk weight (amounts in INR lakhs)."""
    meta = next(t for t in store.tables() if t["table_name"] == table)
    cols = meta["columns"]
    types = {r[1]: r[2] for r in store.db.execute(f'PRAGMA table_info("{table}")')}
    roles = pick_columns(cols, types)
    c_os, c_ecl, c_stage, c_prod = roles["outstanding"], roles["ecl"], roles["stage"], roles["product"]
    if not c_os:
        raise ValueError("no outstanding / balance column recognised")
    div = UNIT[amount_unit]
    prod_expr = f'"{c_prod}"' if c_prod else "'(no product column)'"
    stage_expr = f'"{c_stage}"' if c_stage else "'(no stage column)'"
    ecl_expr = f'SUM("{c_ecl}")' if c_ecl else "NULL"
    rows = store.db.execute(f'SELECT {prod_expr}, {stage_expr}, COUNT(*), SUM("{c_os}"), {ecl_expr} '
                            f'FROM "{table}" GROUP BY 1, 2').fetchall()
    by_product, by_stage, by_bucket = {}, {}, {}
    total = total_ecl = 0.0
    for prod, stage, n, os_, ecl in rows:
        os_l = (os_ or 0) / div
        ecl_l = (ecl or 0) / div
        b, rw = bucket_for(str(prod))
        st = re.sub(r"[^0-9]", "", str(stage)) or str(stage)
        st = f"Stage {st}" if st.isdigit() else str(stage)
        bp = by_product.setdefault(str(prod), {"product": str(prod), "bucket": b, "risk_weight": rw, "loans": 0,
                                               "gross": 0.0, "ecl": 0.0})
        bp["loans"] += n
        bp["gross"] += os_l
        bp["ecl"] += ecl_l
        bs = by_stage.setdefault(st, {"stage": st, "loans": 0, "gross": 0.0, "ecl": 0.0})
        bs["loans"] += n
        bs["gross"] += os_l
        bs["ecl"] += ecl_l
        bb = by_bucket.setdefault(b, {"bucket": b, "risk_weight": rw, "gross": 0.0})
        bb["gross"] += os_l
        total += os_l
        total_ecl += ecl_l
    mapped = sum(v["gross"] for v in by_bucket.values() if v["risk_weight"] is not None)
    blended = (sum(v["gross"] * v["risk_weight"] for v in by_bucket.values() if v["risk_weight"] is not None)
               / mapped) if mapped else None
    s1 = by_stage.get("Stage 1", {"gross": 0.0, "ecl": 0.0})
    return {
        "table": table, "source_file": meta["source_file"], "sheet": meta["sheet"], "rows": meta["n_rows"],
        "amount_unit": amount_unit, "columns_used": {"outstanding": c_os, "ecl": c_ecl, "stage": c_stage,
                                                     "product": c_prod},
        "gross_lakhs": total, "ecl_lakhs": total_ecl, "net_lakhs": total - total_ecl,
        "stage1_gross_lakhs": s1["gross"], "stage1_ecl_lakhs": s1["ecl"],
        "lifetime_ecl_lakhs": total_ecl - s1["ecl"],
        "by_product": sorted(by_product.values(), key=lambda d: -d["gross"]),
        "by_stage": sorted(by_stage.values(), key=lambda d: d["stage"]),
        "by_bucket": sorted(by_bucket.values(), key=lambda d: -d["gross"]),
        "unmapped_share": max(0.0, 1 - mapped / total) if total else 0.0,
        "blended_risk_weight": blended,
    }
