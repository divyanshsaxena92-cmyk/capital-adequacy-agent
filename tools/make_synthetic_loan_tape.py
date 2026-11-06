"""Generate a SYNTHETIC loan tape for testing large-file import. Not client data.

    python tools/make_synthetic_loan_tape.py --rows 200000 --out data/synthetic_loan_tape.xlsx
"""
import argparse
import datetime as dt
import random

from openpyxl import Workbook

PRODUCTS = [("Personal Loan - Unsecured", 0.45, 150_000), ("Credit Card Receivables", 0.25, 60_000),
            ("Consumer Durable Loan", 0.12, 40_000), ("Two Wheeler Loan", 0.10, 90_000),
            ("Gold Loan", 0.06, 120_000), ("Staff Loan", 0.02, 300_000)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=200_000)
    ap.add_argument("--out", default="data/synthetic_loan_tape.xlsx")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Loan Tape")
    ws.append(["SYNTHETIC TEST DATA - generated for import testing, not real borrowers"])
    ws.append(["Reporting date: 31-Mar-2026; amounts in INR"])
    ws.append([])
    ws.append(["Loan ID", "Product Type", "Sanction Date", "Gross Outstanding (INR)", "ECL Stage",
               "ECL Amount (INR)", "DPD", "Branch"])
    names, weights = [p[0] for p in PRODUCTS], [p[1] for p in PRODUCTS]
    for i in range(a.rows):
        k = rnd.choices(range(len(PRODUCTS)), weights)[0]
        prod, _, avg = PRODUCTS[k]
        bal = round(rnd.lognormvariate(0, 0.6) * avg, 2)
        stage = rnd.choices([1, 2, 3], [0.92, 0.05, 0.03])[0]
        ecl = round(bal * {1: 0.02, 2: 0.12, 3: 0.55}[stage] * rnd.uniform(0.7, 1.3), 2)
        dpd = {1: rnd.randint(0, 29), 2: rnd.randint(30, 89), 3: rnd.randint(90, 400)}[stage]
        ws.append([f"LN{i:08d}", prod, dt.date(2022, 1, 1) + dt.timedelta(days=rnd.randint(0, 1500)), bal,
                   f"Stage {stage}", ecl, dpd, f"BR{rnd.randint(1, 250):03d}"])
    wb.save(a.out)
    print(f"wrote {a.rows:,} rows to {a.out}")


if __name__ == "__main__":
    main()
