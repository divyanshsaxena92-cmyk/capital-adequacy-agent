"""RBI 'brain' tests. Fixture texts are synthetic but follow RBI's document structure and wording patterns."""
import datetime as dt
import io
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from capital_agent import rbi_brain  # noqa: E402
from capital_agent.knowledge import KnowledgeBase, RuleLibrary  # noqa: E402
from capital_agent.rag_store import RagStore  # noqa: E402

PAD = " The applicable NBFC shall comply with these requirements on an ongoing basis and maintain adequate records." * 6


def pdf_bytes(lines):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for ln in lines:
        for i in range(0, len(ln), 95):
            c.drawString(36, y, ln[i:i + 95])
            y -= 14
            if y < 40:
                c.showPage()
                y = 800
    c.save()
    return buf.getvalue()


BASE = ["RBI/DOR/2025-26/345 November 28, 2025",
        "Reserve Bank of India (Non-Banking Financial Companies - Prudential Norms on Capital Adequacy) Directions, 2025",
        "6. Minimum capital requirement. An NBFC shall maintain a minimum CRAR of fifteen per cent." + PAD,
        "18. Risk weights.",
        "(1) Retail consumer credit shall attract a risk weight of 125 per cent." + PAD]
AMD = ["RBI/2025-26/168 DOR.CRE.REC.373/21-01-002/2025-26 January 1, 2026",
       "Reserve Bank of India (Non-Banking Financial Companies - Prudential Norms on Capital Adequacy) Amendment Directions, 2026",
       "These Amendment Directions modify the Directions as under: Sr. no. 2 (e) of the Table under paragraph 18(1) shall "
       "stand modified as under: loans to high-quality infrastructure projects shall attract 75 per cent." + PAD,
       "The Amendment Directions shall be applicable from April 1, 2026, or from an earlier date when adopted." + PAD]
DRAFT = ["January 13, 2026", "Draft Amendment Directions - RBI invites public comments on clarification on Owned Fund",
         "1. Tier 1 capital for concentration norms shall exclude quarterly profits." + PAD]
CONSOLIDATED = BASE + ["Note: as modified by the Prudential Norms on Capital Adequacy) Amendment Directions, 2026 dated "
                       "January 1, 2026 and the Third Amendment Directions, 2026 dated June 16, 2026." + PAD]


class TestDetection(unittest.TestCase):
    def test_amendment_dates_and_refs(self):
        m = rbi_brain.detect_meta(" ".join(AMD))
        self.assertEqual(m["kind"], "amendment")
        self.assertEqual(m["issued"], dt.date(2026, 1, 1))
        self.assertEqual(m["effective"], dt.date(2026, 4, 1))           # issue date != effective date
        self.assertIn("18(1)", m["refs"])

    def test_draft_detected(self):
        self.assertEqual(rbi_brain.detect_meta(" ".join(DRAFT))["kind"], "draft")

    def test_immediate_effect(self):
        m = rbi_brain.detect_meta("June 16, 2026 These directions shall come into force with immediate effect." + PAD)
        self.assertEqual(m["effective"], dt.date(2026, 6, 16))
        self.assertEqual(m["confidence"], "medium")

    def test_consolidated_text_dated_by_latest_amendment(self):
        m = rbi_brain.detect_meta(" ".join(CONSOLIDATED))
        self.assertEqual(m["kind"], "consolidated")
        eff, basis, conf = rbi_brain.choose_effective({"effective_from": "2025-11-28"}, m, dt.date(2026, 11, 6))
        self.assertEqual(eff, "2026-06-16")                              # not 28 Nov 2025: it contains June changes

    def test_date_formats(self):
        for s in ("April 1, 2026", "1 April 2026", "Apr 1 2026", "1st April, 2026"):
            self.assertEqual(rbi_brain.parse_date(s), dt.date(2026, 4, 1), s)


class TestStoreBehaviour(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.rag = RagStore(os.path.join(self.d, "rag.sqlite"))

    def test_amendment_not_applied_before_it_takes_effect(self):
        self.rag.ingest({"id": "BASE", "title": "Directions, 2025", "type": "pdf", "framework": "NBFC",
                         "effective_from": "2025-11-28"}, pdf_bytes(BASE))
        r = self.rag.ingest({"id": "AMD1", "title": "Amendment Directions, 2026", "type": "pdf", "framework": "NBFC"},
                            pdf_bytes(AMD))
        self.assertEqual((r["kind"], r["effective_from"]), ("amendment", "2026-04-01"))
        march = self.rag.search("infrastructure projects risk weight", as_of="2026-03-31")
        june = self.rag.search("infrastructure projects risk weight", as_of="2026-06-30")
        self.assertFalse(any(h.doc_id == "AMD1" for h in march))
        self.assertTrue(any(h.doc_id == "AMD1" for h in june))

    def test_drafts_never_retrieved(self):
        self.rag.ingest({"id": "DRAFT1", "title": "Draft Amendment Directions", "type": "pdf", "framework": "NBFC"},
                        pdf_bytes(DRAFT))
        self.assertEqual(self.rag.search("quarterly profits tier 1 concentration", as_of="2026-12-31"), [])

    def test_new_version_logs_paragraph_changes_and_rule_drift(self):
        self.rag.ingest({"id": "BASE", "title": "Directions, 2025", "type": "pdf", "framework": "NBFC",
                         "effective_from": "2025-11-28"}, pdf_bytes(BASE))
        changed = [ln.replace("125 per cent", "100 per cent") for ln in BASE]
        r = self.rag.ingest({"id": "BASE", "title": "Directions, 2025", "type": "pdf", "framework": "NBFC",
                             "new_version_effective_from": "2026-10-07"}, pdf_bytes(changed))
        self.assertEqual(r["action"], "new version")
        self.assertGreaterEqual(r["paragraphs_changed"], 1)
        kb = KnowledgeBase(os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json"), dt.date(2026, 3, 31))
        rl = RuleLibrary(os.path.join(HERE, "rules", "rule_library_v1.0.yaml"), dt.date(2026, 3, 31), kb)
        drift = rbi_brain.rule_drift(self.rag, rl.rules, kb, as_of="2026-03-31")
        hit = [d for d in drift if d["rule_id"] == "R-RWA-002"]            # 125% consumer-credit rule cites 18(1)
        self.assertTrue(hit)
        self.assertFalse(hit[0]["applies_to_run"])                         # Oct change does not apply to a March run
        drift_dec = rbi_brain.rule_drift(self.rag, rl.rules, kb, as_of="2026-12-31")
        self.assertTrue(any(d["rule_id"] == "R-RWA-002" and d["applies_to_run"] for d in drift_dec))

    def test_health_reports_coverage_and_newer_text(self):
        self.rag.seed_curated(os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json"))
        self.assertEqual(rbi_brain.health(self.rag, "2026-03-31")["verdict"], "curated-only")
        self.rag.ingest({"id": "BASE", "title": "Directions, 2025", "type": "pdf", "framework": "NBFC",
                         "effective_from": "2025-11-28"}, pdf_bytes(BASE))
        self.rag.ingest({"id": "AMD1", "title": "Amendment Directions, 2026", "type": "pdf", "framework": "NBFC"},
                        pdf_bytes(AMD))
        h = rbi_brain.health(self.rag, "2026-03-31")
        self.assertEqual(h["full_text_in_force"], 1)
        self.assertIn("AMD1", [d["doc_id"] for d in h["newer_than_as_of"]])

    def test_health_blocks_framework_mismatch_and_exposes_source_ids(self):
        self.rag.ingest({"id": "BANK1", "title": "Bank Directions", "type": "pdf", "framework": "BANK",
                         "effective_from": "2025-11-28"}, pdf_bytes(BASE))
        h = rbi_brain.health(self.rag, "2026-03-31", framework="NBFC")
        self.assertEqual(h["verdict"], "framework-mismatch")
        self.assertTrue(any("BANK1" in issue for issue in h["blocking_issues"]))
        self.assertEqual(h["source_ids_in_force"], [])

    def test_health_blocks_draft_and_future_sources(self):
        self.rag.ingest({"id": "BASE", "title": "Directions, 2025", "type": "pdf", "framework": "NBFC",
                         "effective_from": "2025-11-28"}, pdf_bytes(BASE))
        self.rag.ingest({"id": "DRAFT1", "title": "Draft Amendment Directions", "type": "pdf", "framework": "NBFC"},
                        pdf_bytes(DRAFT))
        self.rag.ingest({"id": "FUTURE1", "title": "Future Directions", "type": "pdf", "framework": "NBFC",
                         "effective_from": "2027-01-01"}, pdf_bytes(BASE))
        h = rbi_brain.health(self.rag, "2026-03-31", framework="NBFC")
        self.assertIn(h["verdict"], {"draft-present", "future-dated"})
        self.assertTrue(h["blocking_issues"])

    def test_sme_override_redates_text(self):
        self.rag.ingest({"id": "AMD1", "title": "Amendment Directions, 2026", "type": "pdf", "framework": "NBFC"},
                        pdf_bytes(AMD))
        rbi_brain.set_effective_override(self.rag, "AMD1", 1, "2026-03-01", "SME-1")
        self.assertTrue(self.rag.search("infrastructure projects", as_of="2026-03-31"))


RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Notifications</title>
<item><title>Reserve Bank of India (Non-Banking Financial Companies - Prudential Norms on Capital Adequacy) Fourth Amendment Directions, 2026</title>
<link>https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=99001</link><pubDate>Wed, 07 Oct 2026 18:00:00</pubDate>
<description>Amendment to risk weights</description></item>
<item><title>Draft directions on capital adequacy - RBI invites comments</title><link>https://www.rbi.org.in/x?Id=99002</link>
<pubDate>Thu, 08 Oct 2026</pubDate><description></description></item>
<item><title>Auction of Government securities</title><link>https://www.rbi.org.in/x?Id=99003</link><pubDate>Fri, 09 Oct 2026</pubDate>
<description></description></item></channel></rss>"""


class TestWatcher(unittest.TestCase):
    def setUp(self):
        self.rag = RagStore(os.path.join(tempfile.mkdtemp(), "rag.sqlite"))

    def test_feed_shortlists_capital_items_once(self):
        s = rbi_brain.check_feeds(self.rag, {"notifications": "x"}, fetch=lambda u: RSS)
        titles = [i["title"] for i in s["new"]]
        self.assertEqual(len(titles), 2)                                    # G-sec auction filtered out
        self.assertEqual({i["kind"] for i in s["new"]}, {"amendment", "draft"})
        self.assertEqual(rbi_brain.check_feeds(self.rag, {"notifications": "x"}, fetch=lambda u: RSS)["new"], [])

    def test_index_follows_notice_page_to_pdf(self):
        rbi_brain.check_feeds(self.rag, {"notifications": "x"}, fetch=lambda u: RSS)
        item = next(i for i in rbi_brain.watch_items(self.rag) if i["kind"] == "amendment")
        page = b'<html><body><a href="https://rbidocs.rbi.org.in/rdocs/notification/PDFs/NT99001.PDF">PDF</a></body></html>'
        pdf = pdf_bytes(AMD)
        res = rbi_brain.index_watch_item(self.rag, item["guid"],
                                         fetch=lambda u: (pdf, "application/pdf") if u.endswith(".PDF") else (page, "text/html"))
        self.assertEqual(res["action"], "indexed")
        self.assertEqual(res["effective_from"], "2026-04-01")
        self.assertEqual(rbi_brain.watch_items(self.rag, "INDEXED")[0]["guid"], item["guid"])


class TestFetchHelpers(unittest.TestCase):
    def test_js_stub_and_pdf_link(self):
        self.assertTrue(rbi_brain.looks_like_js_stub(b"<html><noscript>Please enable JavaScript</noscript></html>"))
        self.assertEqual(rbi_brain.find_pdf_link(b'<a href="/rdocs/x/NT1.PDF">x</a>'), "https://www.rbi.org.in/rdocs/x/NT1.PDF")


if __name__ == "__main__":
    unittest.main()


class TestFlawFixes(unittest.TestCase):
    def setUp(self):
        self.rag = RagStore(os.path.join(tempfile.mkdtemp(), "rag.sqlite"))

    def test_only_rbi_domains_downloadable(self):
        self.assertTrue(rbi_brain.domain_allowed("https://rbidocs.rbi.org.in/rdocs/notification/PDFs/X.PDF"))
        self.assertTrue(rbi_brain.domain_allowed("https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=1"))
        self.assertFalse(rbi_brain.domain_allowed("https://evil.example.com/rbi.org.in.pdf"))
        self.assertFalse(rbi_brain.domain_allowed("https://rbi.org.in.attacker.net/x.pdf"))
        self.assertFalse(rbi_brain.domain_allowed("http://www.rbi.org.in/plain-http"))
        with self.assertRaises(rbi_brain.FetchError):
            rbi_brain.fetch_robust("https://example.com/file.pdf")

    def test_republished_pdf_with_same_text_is_not_a_new_version(self):
        a = pdf_bytes(BASE)
        import time; time.sleep(1.1)
        b = pdf_bytes(BASE)                                   # new file: different timestamp, same words
        self.assertNotEqual(a, b)
        self.rag.ingest({"id": "B", "title": "Directions, 2025", "type": "pdf", "effective_from": "2025-11-28"}, a)
        r = self.rag.ingest({"id": "B", "title": "Directions, 2025", "type": "pdf"}, b)
        self.assertEqual(r["action"], "unchanged")

    def test_early_adoption_flagged(self):
        m = rbi_brain.detect_meta(" ".join(AMD))
        self.assertTrue(m["early_adoption"])
        eff, basis, conf = rbi_brain.choose_effective({}, m, dt.date(2026, 11, 6))
        self.assertEqual(eff, "2026-04-01")
        self.assertIn("early adoption", basis)

    def test_near_miss_notices_kept_as_possible(self):
        rss = (b'<?xml version="1.0"?><rss><channel><item><title>Credit risk management for NBFCs - revised guidance</title>'
               b'<link>https://www.rbi.org.in/x?Id=1</link><pubDate>x</pubDate><description></description></item></channel></rss>')
        s = rbi_brain.check_feeds(self.rag, {"n": "x"}, fetch=lambda u: rss)
        self.assertEqual(s["new"], [])
        self.assertEqual(rbi_brain.watch_items(self.rag, "POSSIBLE")[0]["title"][:11], "Credit risk")

    def test_previous_versions_give_exact_historical_windows(self):
        page = (b'<html><a href="/Scripts/v1.pdf">Updated as on Nov 28, 2025</a>'
                b'<a href="https://rbidocs.rbi.org.in/v2.pdf"><b>Updated as on</b> March 10, 2026</a></html>')
        v1 = pdf_bytes(BASE)
        v2 = pdf_bytes([ln.replace("fifteen", "sixteen") for ln in BASE])
        fake = lambda u: ((page, "text/html") if u.endswith("prev") else ((v1 if "v1" in u else v2), "application/pdf"))
        res = rbi_brain.import_previous_versions(self.rag, "https://www.rbi.org.in/prev", "NBFC-CA-2025", "Directions", fetch=fake)
        self.assertEqual([r["as_on"] for r in res], ["2025-11-28", "2026-03-10"])
        self.assertEqual(res[0]["in_force_to"], "2026-03-10")
        dec = self.rag.search("minimum CRAR per cent", as_of="2025-12-31")
        apr = self.rag.search("minimum CRAR per cent", as_of="2026-04-30")
        self.assertTrue(any("fifteen" in h.text for h in dec) and not any("sixteen" in h.text for h in dec))
        self.assertTrue(any("sixteen" in h.text for h in apr) and not any("fifteen" in h.text for h in apr))


class TestBasel3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from capital_agent.agent import Run
        cls.r = Run(os.path.join(HERE, "data", "sample_client_001.xlsx"), HERE).execute()

    def test_rbi_basel3_requirements(self):
        b = self.r.basel3
        self.assertAlmostEqual(b["required"]["cet1"], 0.08)          # 5.5% + 2.5% CCB
        self.assertAlmostEqual(b["required"]["tier1"], 0.095)
        self.assertAlmostEqual(b["required"]["total"], 0.115)
        self.assertAlmostEqual(b["required"]["leverage"], 0.035)
        self.assertEqual(b["framework"], "benchmark")                # NBFC: lens, not the compliance verdict
        self.assertAlmostEqual(b["ratios"]["cet1"], self.r.final.tier1_ratio, places=9)   # no AT1 in source

    def test_dsib_ccyb_and_op_risk_dials(self):
        from capital_agent import basel3
        s = basel3.assess(self.r, dsib=0.008, ccyb=0.025, op_addon=0.2)
        self.assertAlmostEqual(s["required"]["cet1"], 0.055 + 0.025 + 0.025 + 0.008)
        self.assertAlmostEqual(s["required"]["leverage"], 0.04)      # D-SIB leverage floor
        self.assertLess(s["ratios"]["cet1"], self.r.basel3["ratios"]["cet1"])

    def test_leverage_exposure_avoids_double_count(self):
        lev = self.r.basel3["leverage"]
        self.assertAlmostEqual(lev["exposure"], lev["total_assets"] - lev["less_deductions"] - lev["less_derivative_asset"]
                               + lev["derivatives_cem"])

    def test_conservation_quartiles(self):
        from capital_agent.basel3 import conservation
        self.assertEqual(conservation(0.081, 0.025), 0.0)
        self.assertEqual(conservation(0.0555, 0.025), 1.0)
        self.assertEqual(conservation(0.0745, 0.025), 0.4)
