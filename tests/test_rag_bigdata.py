"""Tests for the RBI knowledge base (RAG) and large-data import. Fixture texts are synthetic."""
import csv
import datetime as dt
import io
import json
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from capital_agent.agent import Run  # noqa: E402
from capital_agent.bigdata import DataStore, bucket_for, summarise_loan_tape  # noqa: E402
from capital_agent.classifier import AUTO, REVIEW, LineItem, RegulatoryAgent  # noqa: E402
from capital_agent.ingest import ingest  # noqa: E402
from capital_agent.knowledge import KnowledgeBase, RuleLibrary  # noqa: E402
from capital_agent.rag_store import RagStore, chunk_text  # noqa: E402

KB = os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json")
RL = os.path.join(HERE, "rules", "rule_library_v1.0.yaml")
DATA = os.path.join(HERE, "data", "sample_client_001.xlsx")

FILLER = " The applicable entity shall apply this requirement consistently in every reporting period and " \
         "shall maintain records sufficient to demonstrate compliance to the supervisor on request."
PAGE_V1 = f"""<html><head><script>var x=1;</script></head><body><nav>Home | Notifications</nav>
<table><tr><td>
<p>Synthetic Capital Directions (test fixture)</p>
<p>Chapter II - Capital requirements</p>
<p>6. Minimum capital ratio</p>
<p>(1) An applicable company shall maintain a minimum capital ratio of fifteen per cent of its aggregate
risk weighted assets.{FILLER}</p>
<p>(2) Tier 2 capital shall not exceed Tier 1 capital at any point of time.{FILLER}</p>
<p>7. Elements of common equity</p>
<p>(i) paid-up equity share capital;{FILLER}</p>
<p>(iv) statutory reserves created under the governing statute form part of common equity.{FILLER}</p>
<p>8. Treatment of cash flow hedge reserve</p>
<p>The cash flow hedge reserve shall be derecognised when computing owned fund.{FILLER}{FILLER}</p>
</td></tr></table><footer>Copyright</footer></body></html>""".encode()
PAGE_V2 = PAGE_V1.replace(b"fifteen per cent", b"sixteen per cent")


def src(eff="2025-11-28", **kw):
    return {"id": "TEST-CA", "title": "Synthetic Capital Directions", "type": "html", "framework": "NBFC",
            "effective_from": eff, "url": "https://example.test/ca", **kw}


class TestChunking(unittest.TestCase):
    def test_paragraph_labels_and_heading(self):
        from capital_agent.rag_store import extract_text
        chunks = chunk_text(extract_text(PAGE_V1, "html"))
        labels = [c.para for c in chunks]
        self.assertTrue(any(l.startswith("6") for l in labels))
        self.assertTrue(any("7(iv)" in l for l in labels), labels)
        self.assertTrue(all("var x" not in c.text for c in chunks))       # scripts stripped
        self.assertTrue(any("Chapter II" in c.heading for c in chunks))

    def test_roman_vs_letter(self):
        import capital_agent.rag_store as R
        old, R.MIN_CHUNK = R.MIN_CHUNK, 0
        try:
            t = "7. Head\n(iv) four\n(a) a\n(h) h\n(i) letter i\n(v) roman five\n8. next"
            self.assertEqual([c.para for c in R.chunk_text(t)],
                             ["7", "7(iv)", "7(iv)(a)", "7(iv)(h)", "7(iv)(i)", "7(v)", "8"])
        finally:
            R.MIN_CHUNK = old

    def test_long_paragraph_split_with_overlap(self):
        t = "9. " + ("Sentence about capital. " * 300)
        ch = chunk_text(t)
        self.assertGreater(len(ch), 2)
        self.assertTrue(all(c.para == "9" for c in ch))
        self.assertTrue(all(len(c.text) <= 1900 for c in ch))


class TestRagStore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.rag = RagStore(os.path.join(self.d, "rag.sqlite"))
        self.r1 = self.rag.ingest(src(), PAGE_V1)

    def test_index_and_search(self):
        self.assertEqual(self.r1["action"], "indexed")
        hits = self.rag.search("statutory reserves common equity", as_of="2026-03-31")
        self.assertTrue(hits)
        self.assertIn("7", hits[0].para)
        self.assertIn("statutory reserves", hits[0].text)

    def test_unchanged_content_skipped(self):
        self.assertEqual(self.rag.ingest(src(), PAGE_V1)["action"], "unchanged")
        self.assertEqual(self.rag.stats()["versions"], 1)

    def test_versioning_by_reporting_date(self):
        r2 = self.rag.ingest(src(new_version_effective_from="2026-06-01"), PAGE_V2)
        self.assertEqual(r2["action"], "new version")
        old = self.rag.search("minimum capital ratio per cent", as_of="2026-03-31")
        new = self.rag.search("minimum capital ratio per cent", as_of="2026-07-01")
        self.assertIn("fifteen", old[0].text)
        self.assertIn("sixteen", new[0].text)
        self.assertTrue(all(h.version == 1 for h in old))
        self.assertTrue(all(h.version == 2 for h in new))

    def test_not_yet_effective_text_hidden(self):
        self.assertEqual(self.rag.search("statutory reserves", as_of="2025-01-01"), [])

    def test_framework_filter(self):
        self.assertTrue(self.rag.search("statutory reserves", frameworks=["NBFC"]))
        self.assertEqual(self.rag.search("statutory reserves", frameworks=["BANK"]), [])

    def test_too_little_text_rejected(self):
        res = self.rag.ingest(src(id="EMPTY"), b"<html><body><div>Please enable JavaScript</div></body></html>")
        self.assertEqual(res["action"], "rejected")

    def test_pdf_ingestion(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        y = 800
        for line in ["10. Leverage requirement", "(1) The leverage ratio shall be computed quarterly on a",
                     "consolidated basis using end of quarter balances." + FILLER[:60],
                     "(2) Exposure measure includes on and off balance sheet items." + FILLER[:60]] * 3:
            c.drawString(40, y, line)
            y -= 18
        c.save()
        res = self.rag.ingest(src(id="PDF-1", type="pdf"), buf.getvalue())
        self.assertIn(res["action"], ("indexed",))
        self.assertTrue(self.rag.search("leverage ratio quarterly", as_of="2026-03-31"))


class TestAgentUsesRag(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.rag = RagStore(os.path.join(d, "rag.sqlite"))
        self.rag.ingest(src(), PAGE_V1)
        self.asof = dt.date(2026, 3, 31)
        self.kb = KnowledgeBase(KB, self.asof, self.rag, ["NBFC"])
        self.rl = RuleLibrary(RL, self.asof, self.kb)

    def test_retrieve_merges_live_text(self):
        ps = self.kb.retrieve("statutory reserve common equity")
        self.assertTrue(any(p.id.startswith("RAG:") for p in ps))
        self.assertTrue(any(not p.id.startswith("RAG:") for p in ps))

    def test_llm_may_cite_retrieved_rag_paragraph(self):
        item = LineItem("T", "OCI - Cash flow hedge reserve", -177.08, "x!C1", "capital")
        rag_id = next(p.id for p in self.kb.retrieve("cash flow hedge reserve derecognised")
                      if p.id.startswith("RAG:"))

        class Stub:
            messages = types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(content=[types.SimpleNamespace(
                text=json.dumps({"rule_id": "R-T1-006", "treatment": "T1_EXCLUDE", "citations": ["P16-3", rag_id],
                                 "confidence": 0.95, "rationale": "derecognised"}))]))
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=Stub()).classify(item)
        self.assertEqual(c.route, AUTO)
        self.assertIn(rag_id, [x["id"] for x in c.citations])

    def test_fabricated_rag_citation_rejected(self):
        item = LineItem("T", "OCI - Cash flow hedge reserve", -177.08, "x!C1", "capital")

        class Stub:
            messages = types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(content=[types.SimpleNamespace(
                text=json.dumps({"rule_id": "R-T1-006", "treatment": "T1_EXCLUDE",
                                 "citations": ["RAG:TEST-CA:v1:9999"], "confidence": 0.99, "rationale": "x"}))]))
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=Stub()).classify(item)
        self.assertEqual(c.route, REVIEW)

    def test_run_with_rag_keeps_benchmark(self):
        db = self.rag.path
        r = Run(DATA, HERE, rag_db=db).execute()
        self.assertAlmostEqual(r.final.crar, 0.25361090468136221, places=9)
        self.assertTrue(any("RAG store" in a.description for a in r.audit))


def _tape_xlsx(path, rows, title_rows=True):
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Tape")
    if title_rows:
        ws.append(["SYNTHETIC LOAN TAPE"])
        ws.append([])
    ws.append(["Loan ID", "Product Type", "Gross Outstanding (INR)", "ECL Stage", "ECL Amount (INR)"])
    for r in rows:
        ws.append(list(r))
    wb.save(path)


ROWS = [("L1", "Personal Loan - Unsecured", 1_000_000, "Stage 1", 20_000),
        ("L2", "Gold Loan", 500_000, "Stage 1", 5_000),
        ("L3", "Credit Card Receivables", 300_000, "Stage 2", 30_000),
        ("L4", "Staff Loan", 200_000, "Stage 1", 0),
        ("L5", "Mystery Product", 100_000, "Stage 3", 50_000)]


class TestBigData(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.store = DataStore(os.path.join(self.d, "data.sqlite"))

    def test_xlsx_import_header_below_titles(self):
        p = os.path.join(self.d, "tape.xlsx")
        _tape_xlsx(p, ROWS)
        res = self.store.import_file(p)
        self.assertEqual(res[0]["header_row"], 3)
        self.assertEqual(res[0]["rows"], 5)
        self.assertEqual(res[0]["kind"], "loan_tape")

    def test_csv_import_and_preview_filter(self):
        p = os.path.join(self.d, "tape.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Loan ID", "Product Type", "Gross Outstanding (INR)", "ECL Stage", "ECL Amount (INR)"])
            w.writerows(ROWS)
        t = self.store.import_file(p)[0]["table"]
        cols, rows, total = self.store.preview(t, {"product_type": "gold"})
        self.assertEqual(total, 1)
        prof = {r["column"]: r for r in self.store.profile(t)}
        self.assertEqual(prof["gross_outstanding_inr"]["type"], "REAL")
        self.assertAlmostEqual(prof["gross_outstanding_inr"]["sum"], 2_100_000)

    def test_preview_rejects_unknown_table(self):
        with self.assertRaises(ValueError):
            self.store.preview("sqlite_master; DROP TABLE x")

    def test_loan_tape_summary_math(self):
        p = os.path.join(self.d, "tape.xlsx")
        _tape_xlsx(p, ROWS)
        t = self.store.import_file(p)[0]["table"]
        sm = summarise_loan_tape(self.store, t, "INR")
        self.assertEqual(sm["columns_used"]["ecl"], "ecl_amount_inr")      # not the 'ecl_stage' text column
        self.assertAlmostEqual(sm["gross_lakhs"], 21.0)
        self.assertAlmostEqual(sm["ecl_lakhs"], 1.05)
        self.assertAlmostEqual(sm["stage1_ecl_lakhs"], 0.25)
        self.assertAlmostEqual(sm["lifetime_ecl_lakhs"], 0.80)
        # mapped: 10 L @125% + 3 L @125% + 5 L @100% + 2 L @0% ; 1 L unmapped
        self.assertAlmostEqual(sm["blended_risk_weight"], (13 * 1.25 + 5 * 1.0) / 20)
        self.assertAlmostEqual(sm["unmapped_share"], 1 / 21)

    def test_product_bucket_word_boundaries(self):
        self.assertEqual(bucket_for("Unsecured Personal Loan")[1], 1.25)
        self.assertEqual(bucket_for("Secured Business Loan")[1], 1.0)
        self.assertEqual(bucket_for("Credit Card")[1], 1.25)
        self.assertIsNone(bucket_for("Something else")[1])

    def test_agent_gets_loan_tape_exception(self):
        p = os.path.join(self.d, "tape.xlsx")
        _tape_xlsx(p, ROWS)
        sm = summarise_loan_tape(self.store, self.store.import_file(p)[0]["table"], "INR")
        r = Run(DATA, HERE, loan_tape=sm).execute()
        e = next(e for e in r.exceptions if e.exc_id == "EXC-DATA-LOANTAPE")
        self.assertGreater(e.impact_crar_bps, 0)                          # blended < 125% => higher CRAR
        self.assertAlmostEqual(r.final.crar, 0.25361090468136221, places=9)   # baseline unchanged until SME decides

    def test_main_ingest_flags_large_sheet(self):
        from openpyxl import load_workbook
        p = os.path.join(self.d, "with_tape.xlsx")
        wb = load_workbook(DATA)
        ws = wb.create_sheet("Big Tape")
        ws.append(["Loan ID", "Amount"])
        for i in range(60):
            ws.append([f"L{i}", i])
        wb.save(p)
        ds = ingest(p, large_rows=50)
        self.assertEqual(ds.large_sheets, ["Big Tape"])


if __name__ == "__main__":
    unittest.main()
