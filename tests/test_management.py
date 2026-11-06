"""Management requests: calculation transparency (ledger + CSV), RBI nomenclature, memo, Calculation page."""
import csv
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [HERE, os.path.join(HERE, "tests")]

from capital_agent import ledger, memo, rbi_brain  # noqa: E402
from capital_agent.agent import Run  # noqa: E402
from capital_agent.rag_store import RagStore  # noqa: E402
from test_rbi_brain import AMD, BASE, DRAFT, pdf_bytes  # noqa: E402


class TestLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = Run(os.path.join(HERE, "data", "sample_client_001.xlsx"), HERE).execute()

    def test_ledger_reproduces_engine_exactly(self):
        led = ledger.build(self.r)
        self.assertTrue(led["reproduced"])
        self.assertEqual({c["metric"] for c in led["checks"]},
                         {"Tier 1", "Tier 2", "On-balance-sheet RWA", "Derivatives RWA", "Total RWA", "CRAR (%)", "Tier 1 ratio (%)"})

    def test_every_tier1_line_and_exposure_is_in_the_ledger(self):
        led = ledger.build(self.r)
        items = {x["Line item"] for x in led["rows"]}
        for a in self.r.cap_applied + self.r.rwa_applied:
            self.assertIn(a.cls.label, items)

    def test_csv_opens_in_excel_and_sums(self):
        raw = ledger.to_csv(self.r)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))                       # BOM: Excel shows the rupee sign
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
        hdr = rows.index(ledger.COLUMNS)
        body = [dict(zip(ledger.COLUMNS, x)) for x in rows[hdr + 1:]]
        t1 = sum(float(x["Result (₹ lakhs or %)"]) for x in body if x["Section"] == "A. Tier 1 capital" and x["Rule"])
        self.assertAlmostEqual(t1, self.r.final.tier1, places=2)               # a reviewer can re-add it in Excel
        rwa = sum(float(x["Result (₹ lakhs or %)"]) for x in body if x["Section"] == "C. Risk-weighted assets" and x["Rule"])
        self.assertAlmostEqual(rwa, self.r.final.rwa_credit_on_bs, places=2)
        self.assertIn("YES", rows[2])                                           # header says it reproduces the engine


class TestNomenclature(unittest.TestCase):
    def setUp(self):
        self.rag = RagStore(os.path.join(tempfile.mkdtemp(), "rag.sqlite"))

    def test_official_identifiers_read_from_document(self):
        n = rbi_brain.nomenclature(" ".join(AMD))
        self.assertEqual(n["ref_no"], "RBI/2025-26/168")
        self.assertTrue(n["circular_no"].startswith("DOR.CRE.REC.373"))
        self.assertTrue(n["official_title"].startswith("Reserve Bank of India (Non-Banking Financial Companies"))
        self.assertTrue(n["official_title"].endswith("Amendment Directions, 2026"))

    def test_catalogue_shows_rbi_names_and_status(self):
        self.rag.seed_curated(os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json"))
        self.rag.ingest({"id": "X1", "title": "my label", "type": "pdf", "framework": "NBFC"}, pdf_bytes(AMD))
        self.rag.ingest({"id": "D1", "title": "Draft Amendment Directions", "type": "pdf"}, pdf_bytes(DRAFT))
        cat = {c["doc_id"]: c for c in rbi_brain.catalogue(self.rag)}
        self.assertEqual(cat["X1"]["ref_no"], "RBI/2025-26/168")
        self.assertIn("Amendment Directions, 2026", cat["X1"]["official_title"])
        self.assertTrue(cat["X1"]["name_read_from_document"])
        self.assertEqual(cat["D1"]["status"], "Draft - never applied")
        self.assertEqual(cat["CURATED-NBFC-SUMMARIES"]["status"], "Not an RBI document")

    def test_config_name_used_when_scan_finds_none_and_sme_can_correct(self):
        self.rag.ingest({"id": "B", "type": "pdf", "effective_from": "2025-11-28", "ref_no": "RBI/DOR/2025-26/345",
                         "title": "Reserve Bank of India (Non-Banking Financial Companies – Prudential Norms on Capital Adequacy) Directions, 2025"},
                        pdf_bytes(BASE[1:]))                                   # header line (with the reference) removed
        c = next(x for x in rbi_brain.catalogue(self.rag) if x["doc_id"] == "B")
        self.assertEqual(c["ref_no"], "RBI/DOR/2025-26/345")
        rbi_brain.set_nomenclature(self.rag, "B", 1, c["official_title"], "RBI/DOR/2025-26/345", "DOR.CAP.REC.No.1/21-06-201/2025-26", "SME-1")
        c = next(x for x in rbi_brain.catalogue(self.rag) if x["doc_id"] == "B")
        self.assertEqual(c["circular_no"], "DOR.CAP.REC.No.1/21-06-201/2025-26")

    def test_old_store_gets_new_columns(self):
        import sqlite3
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE doc_meta (doc_id TEXT, version INTEGER, kind TEXT, issued TEXT, effective_basis TEXT, confidence TEXT, "
                   "refs TEXT, needs_ocr INTEGER, overridden INTEGER DEFAULT 0, PRIMARY KEY (doc_id, version))")
        rbi_brain.ensure_schema(db)
        self.assertTrue({"official_title", "ref_no", "circular_no"} <= {r[1] for r in db.execute("PRAGMA table_info(doc_meta)")})


class TestMemo(unittest.TestCase):
    def test_memo_has_figures_rbi_names_and_signoff(self):
        rag = RagStore(os.path.join(tempfile.mkdtemp(), "rag.sqlite"))
        rag.seed_curated(os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json"))
        rag.ingest({"id": "X1", "title": "x", "type": "pdf", "framework": "NBFC"}, pdf_bytes(AMD))
        r = Run(os.path.join(HERE, "data", "sample_client_001.xlsx"), HERE, rag_db=rag.path).execute()
        html = memo.build(r, rag, "A. Analyst").decode()
        for needle in ("25.36%", "Compliant", "RBI/2025-26/168", "Newer RBI texts", "Prepared by (maker)", "A. Analyst",
                       "independently reproduces the engine: <b>yes</b>"):
            self.assertIn(needle, html)
        self.assertNotIn("<script", html.lower())


if __name__ == "__main__":
    unittest.main()
