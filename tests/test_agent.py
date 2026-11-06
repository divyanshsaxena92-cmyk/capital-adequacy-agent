"""Run: python -m unittest discover -s tests -v"""
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from capital_agent.agent import Run  # noqa: E402
from capital_agent.classifier import AUTO, REVIEW, LineItem, RegulatoryAgent  # noqa: E402
from capital_agent.engine import add_on_factor  # noqa: E402
from capital_agent.knowledge import KnowledgeBase, RuleLibrary  # noqa: E402

DATA = os.path.join(HERE, "data", "sample_client_001.xlsx")
KB = os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json")
RL = os.path.join(HERE, "rules", "rule_library_v1.0.yaml")
ASOF = dt.date(2026, 3, 31)


class StubLLM:
    """Stands in for anthropic.Anthropic(); returns a canned JSON answer."""
    def __init__(self, payload):
        self.payload = payload
        self.messages = types.SimpleNamespace(create=self._create)
        self.calls = 0

    def _create(self, **kw):
        self.calls += 1
        return types.SimpleNamespace(content=[types.SimpleNamespace(text=json.dumps(self.payload))])


class TestBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = Run(DATA, HERE).execute()

    def test_reproduces_expected_output(self):
        exp = {"Tier 1 Capital": 49045.16, "Tier 2 Capital": 2542.6660018143498, "Total RWA": 203413.28014514799,
               "CRAR": 0.25361090468136221, "Tier 1 Ratio": 0.24111090468136209}
        got = self.res.final.as_dict()
        for k, v in exp.items():
            self.assertAlmostEqual(got[k], v, places=6, msg=k)
        self.assertTrue(all(b["status"] == "PASS" for b in self.res.benchmark))

    def test_entity_profiled_as_nbfc_and_framework_flagged(self):
        self.assertEqual(self.res.entity_type, "NBFC")
        self.assertEqual(self.res.minimums, {"crar": 0.15, "tier1": 0.10})
        self.assertIn("EXC-GOV-FRAMEWORK", {e.exc_id for e in self.res.exceptions})

    def test_every_classification_cited(self):
        for a in self.res.cap_applied + self.res.rwa_applied:
            self.assertTrue(a.cls.citations, a.cls.item_id)

    def test_interpretive_items_never_auto_accepted(self):
        for a in self.res.cap_applied + self.res.rwa_applied:
            if a.cls.interpretive:
                self.assertEqual(a.cls.route, REVIEW, a.cls.label)

    def test_known_data_issues_detected(self):
        fails = {c.check_id for c in self.res.checks if c.status == "FAIL"}
        self.assertTrue({"V15", "V16-CAP003", "V18-RWA010"} <= fails)

    def test_status_is_draft_with_open_exceptions(self):
        self.assertTrue(self.res.status.startswith("DRAFT"))

    def test_asset_coverage_control(self):
        self.assertEqual(next(c for c in self.res.control_checks if c.check_id == "C04").status, "PASS")


class TestGuardrails(unittest.TestCase):
    def setUp(self):
        self.kb = KnowledgeBase(KB, ASOF)
        self.rl = RuleLibrary(RL, ASOF, self.kb)
        self.item = LineItem("T1", "OCI - Cash flow hedge reserve", -177.08, "x!C1", "capital")

    def test_valid_llm_answer_accepted(self):
        stub = StubLLM({"rule_id": "R-T1-006", "treatment": "T1_EXCLUDE", "risk_weight": None,
                        "citations": ["P16-3"], "confidence": 0.95, "rationale": "Para 16(3) derecognises CFHR.",
                        "competing_interpretations": [], "evidence_required": "OCI note"})
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=stub).classify(self.item)
        self.assertEqual(c.route, AUTO)
        self.assertEqual(c.rule_id, "R-T1-006")

    def test_hallucinated_citation_rejected(self):
        stub = StubLLM({"rule_id": "R-T1-006", "treatment": "T1_EXCLUDE", "citations": ["P99-FAKE"],
                        "confidence": 0.99, "rationale": "x"})
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=stub).classify(self.item)
        self.assertEqual(c.route, REVIEW)
        self.assertTrue(any("unretrieved citation" in n for n in c.guardrail_notes))
        self.assertEqual(c.citations, [])

    def test_unretrieved_rule_rejected(self):
        stub = StubLLM({"rule_id": "R-RWA-001", "treatment": "T1_INCLUDE", "citations": ["P16-3"],
                        "confidence": 0.99, "rationale": "x"})
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=stub).classify(self.item)
        self.assertEqual(c.route, REVIEW)

    def test_treatment_not_permitted_by_rule_rejected(self):
        stub = StubLLM({"rule_id": "R-T1-006", "treatment": "T1_INCLUDE", "citations": ["P16-3"],
                        "confidence": 0.99, "rationale": "x"})
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=stub).classify(self.item)
        self.assertEqual(c.route, REVIEW)
        self.assertTrue(any("not permitted" in n for n in c.guardrail_notes))

    def test_malformed_llm_output_falls_back_to_review(self):
        stub = StubLLM("not json at all")
        stub.messages = types.SimpleNamespace(create=lambda **kw: types.SimpleNamespace(
            content=[types.SimpleNamespace(text="I think it is Tier 1")]))
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=stub).classify(self.item)
        self.assertEqual(c.route, REVIEW)
        self.assertEqual(c.mode, "llm-fallback")

    def test_hybrid_disagreement_routes_to_review(self):
        item = LineItem("T2", "Reserve u/s 45-IC (Statutory reserve)", 5796.43, "x!C2", "capital")
        stub = StubLLM({"rule_id": "R-T1-004", "treatment": "T1_EXCLUDE", "citations": ["P9"],
                        "confidence": 0.9, "rationale": "x"})
        c = RegulatoryAgent(self.kb, self.rl, "hybrid", llm_client=stub).classify(item)
        self.assertEqual(c.route, REVIEW)
        self.assertTrue(any("Hybrid check" in n for n in c.guardrail_notes))

    def test_low_confidence_routes_to_review(self):
        stub = StubLLM({"rule_id": "R-T1-006", "treatment": "T1_EXCLUDE", "citations": ["P16-3"],
                        "confidence": 0.5, "rationale": "x"})
        c = RegulatoryAgent(self.kb, self.rl, "llm", llm_client=stub).classify(self.item)
        self.assertEqual(c.route, REVIEW)


class TestVersioning(unittest.TestCase):
    def test_future_amendment_excluded_for_march_2026(self):
        self.assertNotIn("P18-1-infra", KnowledgeBase(KB, ASOF).passages)
        self.assertIn("P18-1-infra", KnowledgeBase(KB, dt.date(2026, 6, 30)).passages)

    def test_unapproved_rule_rejected(self):
        import yaml
        with open(RL) as f:
            lib = yaml.safe_load(f)
        next(r for r in lib["rules"] if r["id"] == "R-T1-006")["status"] = "DRAFT"
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as t:
            yaml.safe_dump(lib, t)
        rl = RuleLibrary(t.name, ASOF, KnowledgeBase(KB, ASOF))
        self.assertNotIn("R-T1-006", rl.rules)
        self.assertIn(("R-T1-006", "not approved"), rl.rejected)


class TestHumanInTheLoop(unittest.TestCase):
    def _decide(self, rows):
        t = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
        w = csv.writer(t)
        w.writerow(["exception_id", "decision", "reviewer", "comment"])
        w.writerows(rows)
        t.close()
        return t.name

    def test_sme_decision_applied(self):
        base = Run(DATA, HERE).execute()
        p = self._decide([["EXC-CAP-03", "ACCEPT_ALTERNATIVE", "SME-1", "45-IC reserve is CET1 under firm methodology"]])
        run = Run(DATA, HERE, decisions_path=p).execute()
        self.assertAlmostEqual(run.final.tier1 - base.final.tier1, 5796.43, places=2)
        e = next(e for e in run.exceptions if e.exc_id == "EXC-CAP-03")
        self.assertEqual(e.status, "RESOLVED - ALTERNATIVE APPLIED")

    def test_unsigned_decision_ignored(self):
        p = self._decide([["EXC-CAP-03", "ACCEPT_ALTERNATIVE", "", "no reviewer"]])
        run = Run(DATA, HERE, decisions_path=p).execute()
        self.assertAlmostEqual(run.final.tier1, 49045.16, places=2)


class TestEngine(unittest.TestCase):
    def test_cem_add_on_buckets(self):
        t = {"fx_gold": [[1, 0.02], [5, 0.10], [999, 0.15]]}
        self.assertEqual(add_on_factor(t, "fx_gold", 0.5), 0.02)
        self.assertEqual(add_on_factor(t, "fx_gold", 4.72), 0.10)
        self.assertEqual(add_on_factor(t, "fx_gold", 7), 0.15)

    def test_source_file_not_modified(self):
        def h():
            with open(DATA, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        before = h()
        Run(DATA, HERE).execute()
        self.assertEqual(before, h())


if __name__ == "__main__":
    unittest.main()
