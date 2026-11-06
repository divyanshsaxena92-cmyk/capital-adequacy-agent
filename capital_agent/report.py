"""Stage 7 - Review-ready output pack (Excel).

Calculation sheets use live formulas so a checker can trace and recalculate
every number. Scenario figures (Sensitivity, impact columns) come from engine
re-runs and are labelled as such.
"""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

BRAND = "4F2D7F"          # header colour
FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_BOLD = Font(name=FONT, size=10, bold=True)
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, size=14, bold=True, color=BRAND)
F_INPUT = Font(name=FONT, size=10, color="0000FF")
F_LINK = Font(name=FONT, size=10, color="008000")
F_NOTE = Font(name=FONT, size=9, italic=True, color="595959")
FILL_HEAD = PatternFill("solid", fgColor=BRAND)
FILL_SUB = PatternFill("solid", fgColor="E8E1F0")
FILL_SME = PatternFill("solid", fgColor="FFFF00")
FILL_TOTAL = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
NUM = '#,##0.00;(#,##0.00);"-"'
PCT = '0.00%;(0.00%);"-"'
SEV_FILL = {"Critical": "C00000", "High": "FF7C80", "Medium": "FFD966", "Low": "C6E0B4"}


def _header(ws, row, headers, widths=None):
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font, c.fill, c.alignment, c.border = F_HEAD, FILL_HEAD, Alignment(wrap_text=True, vertical="center"), BOX
    if widths:
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = F_TITLE
    if sub:
        ws["A2"] = sub
        ws["A2"].font = F_NOTE


def _row(ws, r, values, fonts=None, fmts=None, wrap=True):
    for i, v in enumerate(values, 1):
        c = ws.cell(row=r, column=i, value=v)
        c.font = (fonts or {}).get(i, F_BASE)
        c.border = BOX
        if wrap:
            c.alignment = WRAP
        if fmts and i in fmts:
            c.number_format = fmts[i]


def build_pack(run, path: str):
    wb = Workbook()
    ds, base = run.ds, run.baseline
    refs = {}
    cem_blk = 5 + len(run.cem.deals) + 2          # first row of the CEM summary block
    refs["ccr"] = f"Derivative_CEM!$H${cem_blk + 4}"

    # ------------------------------------------------------------------ Tier 1
    ws = wb.active
    ws.title = "Tier1_Capital"
    _title(ws, "Tier 1 Capital - component build", f"{ds.units}. Source amounts in blue; regulatory amount is a live "
           "formula on the applied treatment. NBFC-CA-2025 paras 7-10, 14, 16.")
    hdr = ["Item ID", "Line item", "Source cell", "Source amount", "Applied treatment", "Regulatory amount",
           "Agent proposal", "Confidence", "Route", "Rule", "RBI citation", "Calculated on (basis)"]
    _header(ws, 4, hdr, [9, 44, 30, 14, 18, 15, 18, 10, 14, 11, 26, 50])
    r = 5
    first = r
    for a in run.cap_applied:
        if a.applied == "T2_GENERAL_PROVISION":
            continue
        c = a.cls
        _row(ws, r, [c.item_id, c.label, c.source_ref, c.amount, a.applied,
                     f'=IF(E{r}="T1_DEDUCT",-ABS(D{r}),IF(E{r}="T1_INCLUDE",D{r},0))', c.treatment, c.confidence,
                     c.route, c.rule_id, c.citation_text, a.basis],
             fonts={4: F_INPUT}, fmts={4: NUM, 6: NUM, 8: "0.00"})
        r += 1
    _row(ws, r, ["", "Tier 1 Capital", "", "", "", f"=SUM(F{first}:F{r - 1})"], fonts={2: F_BOLD, 6: F_BOLD},
         fmts={6: NUM})
    for col in range(1, 13):
        ws.cell(row=r, column=col).fill = FILL_TOTAL
    refs["tier1"] = f"Tier1_Capital!$F${r}"
    ws.cell(row=r + 2, column=2, value="Treatments: T1_INCLUDE adds the source amount; T1_DEDUCT subtracts its absolute "
            "value; T1_EXCLUDE has no effect. Items routed to HUMAN_REVIEW are calculated on the maker treatment until an "
            "SME decision is recorded.").font = F_NOTE

    # ------------------------------------------------------------------- RWA
    ws = wb.create_sheet("RWA")
    _title(ws, "Risk-weighted assets - credit risk (on-balance-sheet) and counterparty credit risk",
           "NBFC-CA-2025 para 18. RWA = exposure x applied risk weight (live formula).")
    hdr = ["Item ID", "Exposure", "Source cell", "Exposure value", "Applied RW", "RWA", "Agent RW", "Confidence",
           "Route", "Rule", "RBI citation", "Calculated on (basis)"]
    _header(ws, 4, hdr, [9, 44, 34, 15, 11, 15, 10, 10, 14, 11, 26, 50])
    r = first = 5
    for a in run.rwa_applied:
        c = a.cls
        _row(ws, r, [c.item_id, c.label, c.source_ref, a.exposure, a.applied, f"=D{r}*E{r}",
                     c.risk_weight, c.confidence, c.route, c.rule_id, c.citation_text, a.basis],
             fonts={4: F_INPUT, 5: F_INPUT}, fmts={4: NUM, 5: "0%", 6: NUM, 7: "0%", 8: "0.00"})
        if c.label == "Loans":
            ws.cell(row=r, column=4).comment = Comment(
                f"Net loans {ds.find('^loans$').amount:,.2f} + Stage 1 "
                f"ECL {abs(ds.find('stage 1 - impairment', 'Note 8').amount):,.2f} (para 18(2)(i): only specific "
                "provisions may be netted; Stage 1 ECL is counted in Tier 2).", "Capital Agent")
        r += 1
    last_bs = r - 1
    _row(ws, r, ["CCR", "Counterparty credit risk - derivatives (CEM)", "Derivative_CEM", "", "", f"={refs['ccr']}"],
         fonts={6: F_LINK}, fmts={6: NUM})
    r += 1
    _row(ws, r, ["", "Total RWA", "", f"=SUM(D{first}:D{last_bs})", "", f"=SUM(F{first}:F{r - 1})"],
         fonts={2: F_BOLD, 4: F_BOLD, 6: F_BOLD}, fmts={4: NUM, 6: NUM})
    for col in range(1, 13):
        ws.cell(row=r, column=col).fill = FILL_TOTAL
    refs["rwa"] = f"RWA!$F${r}"

    # ----------------------------------------------------------------- Tier 2
    ws = wb.create_sheet("Tier2_Capital")
    _title(ws, "Tier 2 Capital - eligibility and caps", "NBFC-CA-2025 paras 13(iii), 16(6), 6(3).")
    ecl = next(a for a in run.cap_applied if a.applied == "T2_GENERAL_PROVISION")
    ws.column_dimensions["A"].width = 62
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 60
    rows = [
        ("Stage 1 ECL (12-month) - general provision", ecl.cls.amount, NUM, F_INPUT, ecl.cls.source_ref),
        ("Cap rate on RWA", 0.0125, "0.00%", F_INPUT, "para 13(iii)"),
        ("Total RWA", f"={refs['rwa']}", NUM, F_LINK, "RWA sheet"),
        ("Cap amount (1.25% x RWA)", "=B5*B6", NUM, F_BASE, ""),
        ("Eligible general provisions = MIN(provision, cap)", "=MIN(B4,B7)", NUM, F_BASE, ""),
        ("Other Tier 2 instruments (pref shares, sub debt, hybrid, PDI excess, revaluation)", 0, NUM, F_INPUT,
         "None in source (Capital Inputs CAP011-CAP015 = 0)"),
        ("Tier 1 Capital", f"={refs['tier1']}", NUM, F_LINK, "Tier 2 may not exceed 100% of Tier 1 - para 6(3)"),
        ("Tier 2 Capital = MIN(eligible + other, Tier 1)", "=MIN(B8+B9,B10)", NUM, F_BOLD, ""),
        ("Excess provision not recognised", "=B4-B8", NUM, F_BASE, "Not reckoned; remains a provision"),
    ]
    _row(ws, 3, ["Component", "INR Lakhs", "Note / source"], fonts={1: F_HEAD, 2: F_HEAD, 3: F_HEAD})
    for col in range(1, 4):
        ws.cell(row=3, column=col).fill = FILL_HEAD
    for i, (lbl, val, fmt, fnt, note) in enumerate(rows, start=4):
        _row(ws, i, [lbl, val, note], fonts={2: fnt}, fmts={2: fmt})
    ws["A11"].font = F_BOLD
    refs["tier2"] = "Tier2_Capital!$B$11"

    # ------------------------------------------------------------ CEM
    ws = wb.create_sheet("Derivative_CEM")
    _title(ws, "Counterparty credit risk - Current Exposure Method",
           "NBFC-CA-2025 para 18(7)-(8). Add-on factor and residual maturity are live formulas.")
    hdr = ["Item ID", "Deal (masked)", "Contract type", "Notional (INR)", "Notional (lakhs)", "Reporting date",
           "Maturity date", "Residual (yrs)", "Add-on", "PFE (lakhs)"]
    _header(ws, 4, hdr, [9, 14, 12, 18, 14, 13, 13, 12, 9, 14])
    r = 5
    for d in run.cem.deals:
        mat = next(x["maturity_date"] for x in ds.derivative_inputs if x["item_id"] == d.item_id)
        _row(ws, r, [d.item_id, d.deal_id, d.contract_type, d.notional_inr, f"=D{r}/100000", ds.reporting_date, mat,
                     f"=(G{r}-F{r})/365",
                     f'=IF(C{r}="fx_gold",IF(H{r}<=1,0.02,IF(H{r}<=5,0.1,0.15)),IF(H{r}<=1,0.005,IF(H{r}<=5,0.01,0.03)))',
                     f"=E{r}*I{r}"],
             fonts={4: F_INPUT, 6: F_INPUT, 7: F_INPUT},
             fmts={4: "#,##0.00", 5: NUM, 6: "dd-mmm-yyyy", 7: "dd-mmm-yyyy", 8: "0.00", 9: "0.0%", 10: NUM})
        r += 1
    # fixed summary block rows 10-14 (col G label, H value)
    b = cem_blk
    blk = [(b, "Total PFE", f"=SUM(J5:J{r - 1})", F_BASE, NUM),
           (b + 1, "Replacement cost (gross positive MTM)", run.cem.replacement_cost, F_INPUT, NUM),
           (b + 2, "Credit equivalent (RC + PFE)", f"=H{b}+H{b + 1}", F_BASE, NUM),
           (b + 3, "Counterparty risk weight", run.cem.counterparty_rw, F_INPUT, "0%"),
           (b + 4, "CCR RWA", f"=H{b + 2}*H{b + 3}", F_BOLD, NUM)]
    for rr, lbl, val, fnt, fmt in blk:
        ws.cell(row=rr, column=7, value=lbl).font = F_BOLD
        c = ws.cell(row=rr, column=8, value=val)
        c.font, c.number_format, c.border = fnt, fmt, BOX
    ws.cell(row=b + 6, column=1).value = (f"Replacement cost: {run.cem.rc_source_ref} (aggregate derivative asset; deal-level MTM not supplied). "
                 "Counterparty assumed to be a bank (20%, para 18(3)(ii)). Cross-currency swaps classified as exchange-"
                 "rate contracts (para 18(7)(iii)(b)). No netting recognised (para 18(9)). See EXC-CCR-EVIDENCE.")
    ws.cell(row=b + 6, column=1).font = F_NOTE

    # ------------------------------------------------------------ Summary (first sheet)
    ws = wb.create_sheet("Summary", 0)
    _title(ws, "Capital Adequacy - Agent Output Pack", "Grant Thornton | AI-assisted Tier 1 / Tier 2 capital computation "
           "| Decision-support only - not for regulatory submission without approval")
    for col, w in zip("ABCDEFGH", [34, 18, 16, 16, 16, 16, 14, 44]):
        ws.column_dimensions[col].width = w
    meta = [("Client", "CLIENT_001 (sanitised)"), ("Reporting date", ds.reporting_date), ("Units", ds.units),
            ("Entity type (agent-profiled)", f"{run.entity_type} - layer {run.layer} (assumed; see EXC-GOV-LAYER)"),
            ("Regulatory framework applied", "RBI NBFC Prudential Norms on Capital Adequacy Directions, 2025 "
             "(RBI/DOR/2025-26/345), as in force at reporting date"),
            ("Knowledge base / rule library", f"{run.kb.version} / {run.rules.version}"),
            ("Agent mode", run.mode), ("Run ID", run.run_id), ("Run status", run.status)]
    for i, (k, v) in enumerate(meta, start=4):
        ws.cell(row=i, column=1, value=k).font = F_BOLD
        c = ws.cell(row=i, column=2, value=v)
        c.font = F_BASE
        if k == "Reporting date":
            c.number_format = "dd-mmm-yyyy"
            c.alignment = Alignment(horizontal="left")
    ws["B12"].font = Font(name=FONT, size=10, bold=True, color="C00000" if "DRAFT" in run.status else "008000")

    _row(ws, 14, ["Metric", "Engine (calculated basis)", "Regulatory minimum", "Headroom", "Benchmark (Expected_Output)",
                  "Difference", "Tie-out", "Agent view - all proposals accepted (NOT approved)"],
         fonts={i: F_HEAD for i in range(1, 9)})
    for col in range(1, 9):
        ws.cell(row=14, column=col).fill = FILL_HEAD
    ws.row_dimensions[14].height = 30
    bench = {b["metric"]: b["expected"] for b in run.benchmark}
    av = run.agent_view.as_dict()
    lines = [
        ("Tier 1 Capital", f"={refs['tier1']}", None, NUM),
        ("Tier 2 Capital", f"={refs['tier2']}", None, NUM),
        ("Total RWA", f"={refs['rwa']}", None, NUM),
        ("CRAR", "=(B15+B16)/B17", run.minimums["crar"], PCT),
        ("Tier 1 Ratio", "=B15/B17", run.minimums["tier1"], PCT),
    ]
    for i, (m, f, mn, fmt) in enumerate(lines, start=15):
        tol = "0.000001" if fmt == PCT else "0.01"
        _row(ws, i, [m, f, mn, (f"=B{i}-C{i}" if mn is not None else None), bench.get(m), f"=B{i}-E{i}",
                     f'=IF(ABS(F{i})<={tol},"PASS","FAIL")', av[m]],
             fonts={1: F_BOLD, 2: F_LINK if i < 18 else F_BOLD, 3: F_INPUT, 5: F_INPUT},
             fmts={2: fmt, 3: fmt, 4: fmt, 5: fmt, 6: fmt if fmt == NUM else "0.000000%", 8: fmt})
    if "cet1" in run.minimums:
        _row(ws, 20, ["CET1 Ratio (UL)", "=B19", run.minimums["cet1"], "=B20-C20", None, None, None, None],
             fmts={2: PCT, 3: PCT, 4: PCT})
    ws.conditional_formatting.add("G15:G19", CellIsRule(operator="equal", formula=['"PASS"'],
                                  fill=PatternFill("solid", fgColor="C6EFCE")))
    ws.conditional_formatting.add("G15:G19", CellIsRule(operator="equal", formula=['"FAIL"'],
                                  fill=PatternFill("solid", fgColor="FFC7CE")))

    ws["A22"] = "Exception queue"
    ws["A22"].font = F_BOLD
    _row(ws, 23, ["Severity", "Open", "Resolved", "Total"], fonts={i: F_HEAD for i in range(1, 5)})
    for col in range(1, 5):
        ws.cell(row=23, column=col).fill = FILL_HEAD
    for i, sev in enumerate(["Critical", "High", "Medium", "Low"], start=24):
        _row(ws, i, [sev, f'=COUNTIFS(Exception_Queue!$B:$B,A{i},Exception_Queue!$O:$O,"OPEN")',
                     f'=COUNTIFS(Exception_Queue!$B:$B,A{i},Exception_Queue!$O:$O,"RESOLVED*")',
                     f"=COUNTIF(Exception_Queue!$B:$B,A{i})"])
        ws.cell(row=i, column=1).fill = PatternFill("solid", fgColor=SEV_FILL[sev])
    ws["A29"] = "How to read this pack"
    ws["A29"].font = F_BOLD
    notes = [
        "Engine column = deterministic calculation on the treatments currently applied. Items the agent routed to "
        "review are calculated on the maker's treatment until an SME records a decision (Exception_Queue, yellow cells).",
        "Agent view = what the numbers would be if every agent proposal were accepted. Shown for transparency; it is not "
        "an approved figure.",
        "Every classification carries a confidence score and an RBI paragraph citation (Classification_Log). Every "
        "number traces source cell -> rule -> adjustment -> output (Audit_Trail).",
        "Blue = source input; green = cross-sheet link; black = formula. Yellow = reviewer input.",
    ]
    for i, n in enumerate(notes, start=30):
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=8)
        c = ws.cell(row=i, column=1, value=f"- {n}")
        c.font, c.alignment = F_BASE, WRAP
        ws.row_dimensions[i].height = 28

    # ------------------------------------------------------------ Exception queue
    ws = wb.create_sheet("Exception_Queue")
    _title(ws, "Exception & regulatory-query queue (human review)",
           "Prioritised by severity then CRAR impact. Impact = engine re-run with the alternative treatment applied. "
           "Agent never resolves these itself. Record decisions in the yellow columns or the decisions CSV.")
    hdr = ["Exception ID", "Severity", "Category", "Title", "Issue / reasoning", "Agent's reading",
           "Competing interpretations", "RBI citation", "Evidence required", "Currently calculated on",
           "CRAR impact (bps)", "Tier 1 ratio impact (bps)", "Scenario", "Sample/maker ref", "Status",
           "SME decision", "Reviewer", "Comment"]
    _header(ws, 4, hdr, [20, 9, 15, 34, 60, 30, 50, 28, 34, 34, 10, 10, 34, 14, 16, 20, 14, 30])
    for i, e in enumerate(run.exceptions, start=5):
        _row(ws, i, [e.exc_id, e.severity, e.category, e.title, e.issue, e.ai_best_guess, e.competing, e.citations,
                     e.evidence_required, e.baseline_basis,
                     round(e.impact_crar_bps, 1) if e.scenario_overrides else None,
                     round(e.impact_t1_bps, 1) if e.scenario_overrides else None,
                     e.scenario_desc, e.maker_ref, e.status, e.decision, e.reviewer, e.comment],
             fmts={11: "+0.0;-0.0;0.0", 12: "+0.0;-0.0;0.0"})
        ws.cell(row=i, column=2).fill = PatternFill("solid", fgColor=SEV_FILL[e.severity])
        for col in (16, 17, 18):
            ws.cell(row=i, column=col).fill = FILL_SME
        ws.row_dimensions[i].height = 90
    dv = DataValidation(type="list", formula1='"ACCEPT_ALTERNATIVE,RETAIN_BASELINE,NOTED"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"P5:P{4 + len(run.exceptions)}")

    # ------------------------------------------------------------ Sensitivity
    ws = wb.create_sheet("Sensitivity")
    _title(ws, "Sensitivity - impact of each open interpretation on capital ratios",
           "Each row is a full deterministic engine re-run with one alternative applied (values, not formulas).")
    hdr = ["Scenario", "Exception", "Tier 1", "Tier 2", "Total RWA", "CRAR", "Tier 1 ratio", "CRAR vs baseline (bps)",
           "Breach?"]
    _header(ws, 4, hdr, [58, 20, 14, 14, 15, 10, 11, 13, 30])
    scen = [("Baseline (calculated basis)", "-", base)]
    for e in run.exceptions:
        if e.scenario_overrides:
            scen.append((e.scenario_desc.split(" =>")[0] + f" - {e.title}", e.exc_id, run._compute(e.scenario_overrides)))
    scen.append(("Agent view - all agent proposals accepted", "combined", run.agent_view))
    for i, (name, eid, res) in enumerate(scen, start=5):
        _row(ws, i, [name, eid, res.tier1, res.tier2, res.total_rwa, res.crar, res.tier1_ratio,
                     (res.crar - base.crar) * 1e4, "; ".join(res.breaches) or "No"],
             fmts={3: NUM, 4: NUM, 5: NUM, 6: PCT, 7: PCT, 8: "+0.0;-0.0;0.0"})

    # ------------------------------------------------------------ Classification log
    ws = wb.create_sheet("Classification_Log")
    _title(ws, "Regulatory mapping & reasoning log - every agent classification",
           "Confidence below threshold, interpretive provisions, missing citations or disagreement with the maker route "
           "the item to human review.")
    hdr = ["Item ID", "Kind", "Line item", "Amount", "Source cell", "Agent treatment", "Agent RW", "Rule", "Rule title",
           "Citations (para)", "Official link", "Confidence", "Route", "Mode", "Rationale", "Competing interpretations",
           "Evidence required", "Guardrail notes", "Maker ref", "Maker treatment", "Maker match", "Applied",
           "Basis"]
    _header(ws, 4, hdr, [9, 8, 40, 13, 28, 18, 9, 11, 34, 18, 30, 10, 14, 8, 50, 50, 34, 44, 9, 18, 16, 16, 44])
    for i, a in enumerate(run.cap_applied + run.rwa_applied, start=5):
        c = a.cls
        alts = " | ".join(f"{x.get('treatment') or ''} {('RW ' + format(x['risk_weight'], '.0%')) if x.get('risk_weight') is not None else ''}: {x.get('basis', '')}"
                          for x in c.alternatives)
        _row(ws, i, [c.item_id, c.kind, c.label, c.amount, c.source_ref, c.treatment, c.risk_weight, c.rule_id,
                     c.rule_title, c.citation_text, c.citations[0]["url"] if c.citations else "", c.confidence, c.route,
                     c.mode, c.rationale, alts, c.evidence_required, "; ".join(c.guardrail_notes), a.maker_ref,
                     a.maker_treatment, a.maker_match, a.applied, a.basis],
             fmts={4: NUM, 7: "0%", 12: "0.00"})
        if c.citations:
            ws.cell(row=i, column=11).hyperlink = c.citations[0]["url"]
        if c.route != "AUTO_ACCEPT":
            ws.cell(row=i, column=13).fill = PatternFill("solid", fgColor="FFD966")

    # ------------------------------------------------------------ Validation
    ws = wb.create_sheet("Validation")
    _title(ws, "Validation & reconciliation report", "Source tie-outs (V), controls (C) and benchmark tie-out.")
    hdr = ["Check ID", "Area", "Description", "Status", "Expected", "Actual", "Difference", "Detail"]
    _header(ws, 4, hdr, [12, 14, 58, 8, 16, 16, 14, 70])
    r = 5
    for c in run.checks + run.control_checks:
        _row(ws, r, [c.check_id, c.area, c.description, c.status, c.expected, c.actual, c.difference, c.detail],
             fmts={5: "#,##0.00####", 6: "#,##0.00####", 7: "#,##0.00####"})
        ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor={"PASS": "C6EFCE", "FAIL": "FFC7CE"}.get(c.status, "FFEB9C"))
        r += 1
    for b in run.benchmark:
        _row(ws, r, ["BENCH", "Benchmark", f"{b['metric']} vs Expected_Output", b["status"], b["expected"], b["actual"],
                     b["diff"], "Engine vs sample benchmark"], fmts={5: "#,##0.00####", 6: "#,##0.00####", 7: "0.00E+00"})
        ws.cell(row=r, column=4).fill = PatternFill("solid", fgColor="C6EFCE" if b["status"] == "PASS" else "FFC7CE")
        r += 1

    # ------------------------------------------------------------ Audit trail
    ws = wb.create_sheet("Audit_Trail")
    _title(ws, "Source-to-output audit trail", f"Run {run.run_id}. Source -> regulatory rule -> treatment -> output; "
           "actor shows Agent, Engine or Human.")
    hdr = ["#", "Stage", "Item", "Description", "Source", "Input", "Rule", "Citation", "Treatment / result", "Output",
           "Actor"]
    _header(ws, 4, hdr, [5, 14, 13, 70, 30, 14, 12, 26, 18, 16, 16])
    for i, e in enumerate(run.audit, start=5):
        _row(ws, i, [e.seq, e.stage, e.item_id, e.description, e.source_ref, e.input_value, e.rule_id, e.citation,
                     e.treatment, e.output_value, e.actor], fmts={6: "#,##0.00####", 10: "#,##0.00####"})

    # ------------------------------------------------------------ Rule library
    ws = wb.create_sheet("Rule_Library")
    _title(ws, f"Controlled rule library {run.rules.version} (in force at {ds.reporting_date})",
           f"Approval: {run.rules.approved_by}. Rules not in force or unapproved are rejected: {run.rules.rejected or 'none'}")
    hdr = ["Rule ID", "Area", "Title", "Treatment", "Risk weight", "Interpretive", "Default confidence", "Citations",
           "Paragraphs", "Evidence required", "Effective from", "Status"]
    _header(ws, 4, hdr, [11, 9, 48, 20, 10, 11, 11, 16, 26, 44, 12, 11])
    for i, rule in enumerate(run.rules.rules.values(), start=5):
        paras = ", ".join(run.kb.get(p).para for p in rule.get("citations", []))
        _row(ws, i, [rule["id"], rule["area"], rule["title"], rule["treatment"], rule.get("risk_weight"),
                     "Yes" if rule.get("interpretive") else "No", rule["default_confidence"],
                     ", ".join(rule.get("citations", [])), paras, rule.get("evidence_required", ""),
                     str(rule["effective_from"]), rule["status"]], fmts={5: "0%"})
    r = 6 + len(run.rules.rules)
    ws.cell(row=r, column=1, value="Knowledge base passages in force").font = F_BOLD
    _row(ws, r + 1, ["Passage", "Para", "Title", "Effective from", "", "", "", "Official source"],
         fonts={i: F_HEAD for i in range(1, 9)})
    for col in range(1, 9):
        ws.cell(row=r + 1, column=col).fill = FILL_HEAD
    for j, p in enumerate(run.kb.passages.values(), start=r + 2):
        _row(ws, j, [p.id, p.para, p.title, str(p.effective_from), "", "", "", p.url])
        ws.cell(row=j, column=8).hyperlink = p.url

    # ------------------------------------------------------------ Maker-checker
    ws = wb.create_sheet("Maker_Checker")
    _title(ws, "Maker-checker & approval status", "Regulatory return submission is disabled in the agent. "
           "Final figures require all Critical/High/Medium exceptions resolved and the sign-offs below.")
    for col, w in zip("ABCDE", [30, 28, 22, 16, 44]):
        ws.column_dimensions[col].width = w
    _header(ws, 4, ["Role", "Name", "Status", "Date", "Comment"])
    open_n = sum(e.status == "OPEN" for e in run.exceptions)
    roles = [("Maker (AI agent run)", f"Capital Agent - {run.mode} mode", "COMPLETED", str(run.started)[:10],
              f"{run.run_id}; {open_n} exception(s) open"),
             ("Reviewer (Regulatory SME)", "", "PENDING", "", "Resolve exception queue"),
             ("Checker", "", "PENDING", "", "Review audit trail & validation report"),
             ("Approver (Engagement lead)", "", "PENDING", "", ""),
             ("Regulatory return submission", "-", "DISABLED", "", "Human approval required (Concept Note s.4)")]
    for i, rr in enumerate(roles, start=5):
        _row(ws, i, list(rr))
        if rr[2] == "PENDING":
            for col in (2, 3, 4, 5):
                ws.cell(row=i, column=col).fill = FILL_SME

    for wsx in wb.worksheets:
        wsx.sheet_view.showGridLines = False
        wsx.sheet_properties.tabColor = BRAND if wsx.title in {"Summary", "Exception_Queue"} else None
    from openpyxl.workbook.properties import CalcProperties
    wb.calculation = CalcProperties(fullCalcOnLoad=True)   # Excel recalculates all formulas on open
    wb.save(path)
    return path
