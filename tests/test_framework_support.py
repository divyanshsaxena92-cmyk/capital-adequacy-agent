import datetime as dt
import os
import sys
import tempfile
import unittest

from openpyxl import Workbook

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from capital_agent.agent import Run
from capital_agent.framework import BANK_PROFILE, NBFC_PROFILE, profile_for_dataset
from capital_agent.ingest import ingest
from capital_agent.security import deployment_safety_check
from ui.preflight import run as preflight


def bank_workbook(include_supplemental=True):
    wb = Workbook()
    ws = wb.active
    ws.title = "Balance Sheet"
    ws.append(["Balance Sheet as at March 31, 2026"])
    for label, amount in [
        ("Commercial Bank - RBI Basel III", None),
        ("Units: INR Lakhs", None),
        ("Cash and cash equivalents", 100.0),
        ("Bank balances other than cash", 100.0),
        ("Derivative financial instruments", 0.0),
        ("Trade receivables", 0.0),
        ("Loans", 500.0),
        ("Investments", 100.0),
        ("Other financial assets", 0.0),
        ("Total financial assets", 800.0),
        ("Other non-financial assets", 0.0),
        ("Total non-financial assets", 0.0),
        ("Total assets", 800.0),
        ("Equity share capital", 100.0),
        ("Other equity", 100.0),
        ("Total equity", 200.0),
        ("Other financial liabilities", 600.0),
        ("Total financial liabilities", 600.0),
        ("Total liabilities and equity", 800.0),
    ]:
        ws.append([label, amount])
    cap = wb.create_sheet("Capital Inputs")
    cap.append(["Item_ID", "Reporting_Date", "Capital_Category", "Line_Item", "Raw_Amount_INR_Lakhs"])
    cap.append(["CET1-01", dt.date(2026, 3, 31), "Tier 1", "Equity share capital", 100.0])
    rwa = wb.create_sheet("RWA Inputs")
    rwa.append(["Item_ID", "Reporting_Date", "Asset_Class", "Risk_Weight", "Asset_Value_INR_Lakhs"])
    rwa.append(["RWA-01", dt.date(2026, 3, 31), "Loans", 1.0, 500.0])
    if include_supplemental:
        market = wb.create_sheet("Market Risk")
        market.append(["Item_ID", "Market_Risk_RWA"])
        market.append(["MR-01", 25.0])
        operational = wb.create_sheet("Operational Risk")
        operational.append(["Item_ID", "Operational_Risk_RWA"])
        operational.append(["OR-01", 35.0])
    return wb


class TestFrameworkSupport(unittest.TestCase):
    def _save(self, wb):
        f = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        f.close()
        wb.save(f.name)
        self.addCleanup(lambda: os.unlink(f.name))
        return f.name

    def test_explicit_bank_markers_and_supplemental_risk_are_detected(self):
        path = self._save(bank_workbook())
        ds = ingest(path)
        self.assertIs(profile_for_dataset(ds), BANK_PROFILE)
        self.assertIn("market_inputs", ds.sheet_map)
        self.assertIn("operational_inputs", ds.sheet_map)
        result = preflight(path)
        self.assertEqual(result["profile"], BANK_PROFILE)
        self.assertEqual(result["diagnostics"], [])

    def test_bank_preflight_blocks_missing_market_and_operational_evidence(self):
        path = self._save(bank_workbook(include_supplemental=False))
        result = preflight(path)
        self.assertEqual(result["profile"], BANK_PROFILE)
        self.assertTrue(any("market-risk RWA schedule is missing" in x for x in result["blocking"]))
        self.assertTrue(any("operational-risk schedule is missing" in x for x in result["blocking"]))

    def test_explicit_nil_market_and_operational_rows_are_accepted(self):
        wb = bank_workbook()
        wb["Market Risk"]["B2"] = 0.0
        wb["Operational Risk"]["B2"] = 0.0
        path = self._save(wb)
        ds = ingest(path)
        self.assertTrue(ds.market_inputs and ds.operational_inputs)
        self.assertEqual(preflight(path)["diagnostics"], [])

    def test_missing_bank_evidence_blocks_run_status_instead_of_silent_zero(self):
        path = self._save(bank_workbook(include_supplemental=False))
        run = Run(path, HERE).execute()
        self.assertTrue(run.status.startswith("BLOCKED"))
        self.assertEqual(run.market_rwa, 0.0)
        self.assertTrue(any(c.check_id == "C10" and c.status == "FAIL" for c in run.control_checks))
        self.assertTrue(any("market-risk RWA schedule is missing" in e.issue for e in run.exceptions))

    def test_bank_run_includes_explicit_market_and_operational_rwa(self):
        path = self._save(bank_workbook())
        run = Run(path, HERE).execute()
        self.assertEqual(run.entity_type, "BANK")
        self.assertAlmostEqual(run.market_rwa, 25.0)
        self.assertAlmostEqual(run.operational_rwa, 35.0)
        self.assertAlmostEqual(run.final.total_rwa, 660.0)
        self.assertTrue(any(e.category == "Framework evidence" for e in run.exceptions) is False)

    def test_nbfc_profile_remains_explicit(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Balance Sheet"
        ws.append(["Balance Sheet as at March 31, 2026"])
        ws.append(["NBFC registered under section 45-IC"])
        ws.append(["Units: INR Lakhs"])
        path = self._save(wb)
        self.assertIs(profile_for_dataset(ingest(path)), NBFC_PROFILE)

    def test_community_cloud_safety_is_viewer_only(self):
        old = {k: os.environ.get(k) for k in ("CAPITAL_AGENT_DEPLOYMENT", "CAPITAL_AGENT_MODE")}
        try:
            os.environ["CAPITAL_AGENT_DEPLOYMENT"] = "community_cloud"
            os.environ["CAPITAL_AGENT_MODE"] = "full"
            with self.assertRaises(RuntimeError):
                deployment_safety_check()
            os.environ["CAPITAL_AGENT_MODE"] = "viewer"
            self.assertFalse(deployment_safety_check()["client_uploads_allowed"])
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
