#!/usr/bin/env python3
"""Capital Adequacy Agent - command line.

Examples
  python run_agent.py --input data/sample.xlsx                       # offline, deterministic rules mode
  python run_agent.py --input data/sample.xlsx --decisions decisions/decisions.csv   # apply SME decisions
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from capital_agent.agent import Run  # noqa: E402
from capital_agent.report import build_pack  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--mode", choices=["rules"], default="rules",
                    help="offline deterministic mode (no LLM / API is used anywhere in this build)")
    ap.add_argument("--layer", choices=["ML", "UL"], default="ML", help="NBFC layer under scale-based regulation")
    ap.add_argument("--threshold", type=float, default=0.80, help="confidence needed to auto-accept")
    ap.add_argument("--decisions", help="CSV of SME decisions (exception_id, decision, reviewer, comment)")
    ap.add_argument("--rag-db", default=os.path.join(HERE, "store", "rag.sqlite"),
                    help="RBI knowledge base built with: python -m capital_agent.rag_store refresh")
    ap.add_argument("--loan-tape", help="large loan tape (xlsx/csv) to import and use as evidence")
    ap.add_argument("--tape-unit", default="INR", choices=["INR", "INR lakhs", "INR crores"])
    a = ap.parse_args()

    tape = None
    if a.loan_tape:
        from capital_agent.bigdata import DataStore, summarise_loan_tape
        store = DataStore(os.path.join(HERE, "store", "data.sqlite"))
        res = [r for r in store.import_file(a.loan_tape) if r["kind"] == "loan_tape"]
        if res:
            tape = summarise_loan_tape(store, res[0]["table"], a.tape_unit)
            print(f"Loan tape: {res[0]['rows']:,} loans imported; blended RW {tape['blended_risk_weight']:.1%}")
    run = Run(a.input, HERE, a.mode, a.layer, a.decisions, a.threshold,
              rag_db=a.rag_db if os.path.exists(a.rag_db) else None, loan_tape=tape).execute()
    os.makedirs(a.out, exist_ok=True)
    tag = "post_decisions" if a.decisions else "draft"
    xlsx = build_pack(run, os.path.join(a.out, f"Capital_Agent_Output_{run.ds.reporting_date}_{tag}.xlsx"))
    with open(os.path.join(a.out, f"run_{tag}.json"), "w") as f:
        json.dump(run.to_json(), f, indent=2, default=str)
    if not a.decisions:
        run.write_decisions_template(os.path.join(HERE, "decisions", "decisions_template.csv"))

    r = run.final
    print(f"\n{run.run_id}  [{run.mode} mode]  status: {run.status}")
    print(f"Reporting date {run.ds.reporting_date} | {run.entity_type} layer {run.layer} | KB {run.kb.version} | {run.rules.version}")
    print(f"  Tier 1 {r.tier1:>12,.2f}   Tier 2 {r.tier2:>10,.2f}   RWA {r.total_rwa:>12,.2f}")
    print(f"  CRAR   {r.crar:>11.2%}   Tier 1 ratio {r.tier1_ratio:.2%}   (min {run.minimums['crar']:.0%} / {run.minimums['tier1']:.0%})")
    print(f"  Benchmark tie-out: {sum(b['status'] == 'PASS' for b in run.benchmark)}/{len(run.benchmark)} PASS")
    fails = [c for c in run.checks if c.status == "FAIL"]
    print(f"  Validation: {len(run.checks) - len(fails)}/{len(run.checks)} source checks pass; failures: "
          + ", ".join(c.check_id for c in fails))
    print("  Exceptions:")
    for e in run.exceptions:
        imp = f"{e.impact_crar_bps:+7.1f} bps" if e.scenario_overrides else "     info"
        print(f"    [{e.severity:<8}] {imp}  {e.exc_id:<22} {e.title[:70]}  ({e.status})")
    print(f"  Output: {xlsx}")


if __name__ == "__main__":
    main()
