"""Offline assistant: each kind of question goes to the right source, numbers come from the engine."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from capital_agent.agent import Run  # noqa: E402
from capital_agent.assistant import Assistant  # noqa: E402
from capital_agent.rag_store import RagStore  # noqa: E402


class TestAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rag = RagStore(os.path.join(tempfile.mkdtemp(), "rag.sqlite"))
        rag.seed_curated(os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json"))
        cls.agent_run = Run(os.path.join(HERE, "data", "sample_client_001.xlsx"), HERE, rag_db=rag.path).execute()
        cls.bot = Assistant(cls.agent_run, rag)

    def ask(self, q):
        return self.bot.ask(q)

    def test_compliance(self):
        a = self.ask("Is the client compliant with RBI minimums?")
        self.assertEqual(a.kind, "metrics")
        self.assertIn("25.36%", a.text)
        self.assertIn("compliant", a.text)

    def test_exception_explained(self):
        a = self.ask("Why is the statutory reserve flagged?")
        self.assertEqual(a.kind, "exception")
        self.assertNotIn("T1_INCLUDE", a.text)          # treatment codes are humanised

    def test_what_if_matches_engine(self):
        a = self.ask("What if the statutory reserve is included in Tier 1?")
        self.assertEqual(a.kind, "what_if")
        self.assertIn("28.21%", a.text)

    def test_what_if_loans_percentage(self):
        a = self.ask("what if loans are risk-weighted at 100%?")
        self.assertIn("31.14%", a.text)

    def test_what_if_counterparty(self):
        self.assertEqual(self.ask("What if derivative counterparties are non-banks?").kind, "what_if")

    def test_risk_weight_lookup(self):
        a = self.ask("What risk weight applies to gold loans?")
        self.assertTrue(a.text.startswith("**100%**"))

    def test_regulatory_answer_is_quoted_with_para(self):
        a = self.ask("How is Tier 2 capped?")
        self.assertEqual(a.kind, "regulation")
        self.assertIn("1.25% of RWA", a.text)
        self.assertTrue(any(s["para"] == "13" for s in a.sources))

    def test_validation(self):
        a = self.ask("Which data checks failed?")
        self.assertIn("V15", a.text)

    def test_no_match_is_honest(self):
        a = Assistant(None, None).ask("what is the capital of france")
        self.assertEqual(a.kind, "no_match")

    def test_no_run_still_answers_regulation(self):
        rag = RagStore(os.path.join(tempfile.mkdtemp(), "rag.sqlite"))
        rag.seed_curated(os.path.join(HERE, "regulatory_kb", "nbfc_capital_adequacy_2025.json"))
        a = Assistant(None, rag).ask("How are deferred tax assets treated?")
        self.assertEqual(a.kind, "regulation")
        self.assertIn("para 14", a.text)


if __name__ == "__main__":
    unittest.main()
