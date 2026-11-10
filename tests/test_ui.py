"""Headless smoke tests for the Streamlit front end (python -m unittest discover -s tests)."""
import os
import runpy
import sys
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tests"))

import streamlit_stub as stub  # noqa: E402

sys.modules["streamlit"] = stub.module
sys.modules["streamlit.components"] = stub.module.components
sys.modules["streamlit.components.v1"] = stub.module.components.v1

APP = os.path.join(HERE, "app.py")


def run_app():
    stub.CALLS.clear()
    try:
        runpy.run_path(APP, run_name="__main__")
    except stub.Rerun:
        pass
    return stub.module.session_state


def tab_errors():
    return [a for n, a, k in stub.CALLS if n == "error" and a and "failed to render" in str(a[0])]


class TestApp(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._store = tempfile.mkdtemp()
        os.environ["CAPITAL_AGENT_STORE"] = self._store
        stub.module.session_state.clear()
        stub.COMPONENT["return"] = None
        stub.BUTTONS.clear()
        stub.FILE["upload"] = None

    def test_sample_autoruns_and_all_tabs_render(self):
        ss = run_app()
        self.assertIsNone(ss.error, ss.error)
        self.assertIsNotNone(ss.run)
        self.assertEqual(tab_errors(), [], [c for c in stub.CALLS if c[0] == "code"])
        titles = list(stub.PAGES)
        self.assertGreaterEqual(len(titles), 16)
        self.assertNotIn("My page", titles)            # template ignored
        dl = [a[0] for n, a, k in stub.CALLS if n == "download_button"]
        self.assertIn("Excel output pack", dl)
        self.assertAlmostEqual(ss.run.final.crar, 0.25361090468136221, places=9)

    def test_decision_rerun_from_ui(self):
        ss = run_app()
        ns = runpy.run_path(APP, run_name="__main__")  # second pass gives us the functions bound to state
        try:
            ns["rerun_with_decisions"]([{"exception_id": "EXC-CAP-03", "decision": "ACCEPT_ALTERNATIVE",
                                         "reviewer": "SME-TEST", "comment": "test"}])
        except stub.Rerun:
            pass
        self.assertAlmostEqual(ss.run.final.tier1, 49045.16 + 5796.43, places=2)
        run_app()                                     # tabs still render after decisions
        self.assertEqual(tab_errors(), [])

    def test_uploaded_balance_sheet_only_workbook(self):
        path = os.path.join(HERE, "data", "example_balance_sheet_only.xlsx")
        if not os.path.exists(path):
            self.skipTest("stripped workbook not prepared")
        data = open(path, "rb").read()
        stub.FILE["upload"] = types.SimpleNamespace(getvalue=lambda: data, name="bs_only.xlsx")
        stub.BUTTONS["Run agent"] = True
        ss = run_app()
        self.assertIsNone(ss.error, ss.error)
        self.assertEqual(ss.preflight["blocking"], [])
        self.assertEqual(tab_errors(), [])
        self.assertAlmostEqual(ss.run.final.tier1, 49045.16, places=2)

    def test_unusable_workbook_is_blocked_not_crashed(self):
        from openpyxl import Workbook
        wb = Workbook()
        wb.active["A1"] = "Something else"
        p = "/tmp/junk.xlsx"
        wb.save(p)
        data = open(p, "rb").read()
        stub.FILE["upload"] = types.SimpleNamespace(getvalue=lambda: data, name="junk.xlsx")
        stub.BUTTONS["Run agent"] = True
        ss = run_app()
        self.assertIsNone(ss.run)
        self.assertTrue(ss.preflight["blocking"])
        self.assertEqual(tab_errors(), [])              # source tab still renders


def _html():
    return " ".join(str(a[0]) for n, a, k in stub.CALLS if n in ("markdown", "caption", "error", "info", "html") and a)


class TestOfflineDashboard(unittest.TestCase):
    """v0.4: offline-only shell, assistant and simulator."""

    def setUp(self):
        import tempfile
        os.environ["CAPITAL_AGENT_STORE"] = tempfile.mkdtemp()
        stub.module.session_state.clear()
        stub.COMPONENT["return"] = None
        stub.BUTTONS.clear()
        stub.FILE["upload"] = None
        stub.CHAT["q"] = None

    def test_no_llm_or_api_key_anywhere_in_ui(self):
        run_app()
        text = _html() + " ".join(str(a) for n, a, k in stub.CALLS)
        self.assertNotIn("API key", text.replace("no API key", ""))
        self.assertNotIn("Reasoning mode", text)
        self.assertEqual(stub.module.session_state.run.mode, "rules")

    def test_knowledge_base_seeded_on_start(self):
        ss = run_app()
        self.assertGreaterEqual(ss.rag_store.stats()["chunks_current"], 20)

    def test_sections_and_pages(self):
        run_app()
        secs = {a[0] for n, a, k in stub.CALLS if n == "page"}
        self.assertEqual(secs, {"Dashboard", "Capital", "Review", "Regulation", "Data & evidence"})
        self.assertEqual(tab_errors(), [], [c for c in stub.CALLS if c[0] == "code"])

    def test_chat_what_if_through_ui(self):
        run_app()
        stub.CHAT["q"] = "What if the statutory reserve is included in Tier 1?"
        ss = run_app()
        self.assertEqual(ss.chat[-1]["role"], "assistant")
        self.assertIn("+285.0 bps", ss.chat[-1]["content"])

    def test_chat_regulatory_answer_cites_paragraph(self):
        run_app()
        stub.CHAT["q"] = "How is Tier 2 capped?"
        ss = run_app()
        self.assertTrue(any(s["para"] == "13" for s in ss.chat[-1]["sources"]))

    def test_simulator_toggle(self):
        ss = run_app()
        stub.BUTTONS["wi-EXC-CAP-03"] = True
        run_app()
        self.assertIn("28.21%", _html())          # statutory reserve included => CRAR 28.21%
        self.assertEqual(tab_errors(), [])


class TestCommandCentre(unittest.TestCase):
    def setUp(self):
        import tempfile
        os.environ["CAPITAL_AGENT_STORE"] = tempfile.mkdtemp()
        stub.module.session_state.clear()
        stub.COMPONENT["return"] = None
        stub.BUTTONS.clear()
        stub.FILE["upload"] = None
        stub.CHAT["q"] = None
        stub.COMPONENT["return"] = None

    def _comp(self):
        return next(k for n, a, k in stub.CALLS if n == "component")

    def test_component_gets_engine_numbers_and_no_network(self):
        run_app()
        kw = self._comp()
        html, data = kw["html"], kw["data"]
        for needle in ("Capital Command Centre", "GRANT THORNTON", "Judgement calls at stake", "Risk heat map",
                       "Live what-if", "sc-floor", 'id="q"', 'id="theme"', "prefers-reduced-motion"):
            self.assertIn(needle, html)
        self.assertNotIn("<script", html.lower())                 # all JS lives in the static component
        self.assertNotIn("http", html)                            # no external assets
        self.assertAlmostEqual(data["reported"], 25.361090468, places=6)
        self.assertAlmostEqual(data["crar"][data["xs"].index(100)], 31.14, places=1)

    def test_component_js_has_no_network_calls(self):
        js = open(os.path.join(HERE, "ui", "dashboard_component", "index.html")).read()
        for bad in ("fetch(", "XMLHttpRequest", "WebSocket", "http://", "https://", "<script src"):
            self.assertNotIn(bad, js)

    def test_search_enter_asks_agent_and_switches_page(self):
        run_app()
        stub.COMPONENT["return"] = {"type": "ask", "q": "What if the statutory reserve is included in Tier 1?", "nonce": "n1"}
        ss = run_app()
        self.assertIn(("switch_page", ("Ask the Agent",), {}), [c for c in stub.CALLS if c[0] == "switch_page"])
        self.assertIn("+285.0 bps", ss.chat[-1]["content"])

    def test_night_mode_applies_to_whole_app(self):
        run_app()
        self.assertEqual(self._comp()["data"]["theme"], "light")
        stub.COMPONENT["return"] = {"type": "theme", "value": "dark", "nonce": "t1"}
        ss = run_app()
        self.assertEqual(ss.theme, "dark")
        stub.COMPONENT["return"] = None
        run_app()
        html = " ".join(str(a[0]) for n, a, k in stub.CALLS if n == "markdown" and a)
        self.assertIn("Night theme for the whole app", html)                    # Streamlit shell goes dark too
        self.assertEqual(self._comp()["data"]["theme"], "dark")                  # and every component page opens dark

    def test_command_palette_lists_every_page(self):
        run_app()
        cmds = self._comp()["data"]["commands"]
        self.assertGreaterEqual(len(cmds), 17)
        self.assertIn("t16_basel3", [c["page"] for c in cmds])

    def test_nav_event_and_nonce_dedup(self):
        run_app()
        stub.COMPONENT["return"] = {"type": "nav", "page": "t06_exceptions", "nonce": "n2"}
        run_app()
        self.assertTrue(any(c[0] == "switch_page" for c in stub.CALLS))
        run_app()                                                  # same nonce again -> no second navigation
        self.assertFalse(any(c[0] == "switch_page" for c in stub.CALLS))


class TestViewerMode(unittest.TestCase):
    """Hosted copy: visitors explore; only an admin (password from secrets/env) can change data."""

    def setUp(self):
        import tempfile
        os.environ["CAPITAL_AGENT_STORE"] = tempfile.mkdtemp()
        os.environ["CAPITAL_AGENT_MODE"] = "viewer"
        os.environ["CAPITAL_AGENT_ADMIN_PASSWORD"] = "s3cret-pass"
        stub.module.session_state.clear()
        stub.COMPONENT["return"] = None
        stub.BUTTONS.clear()
        stub.FILE["upload"] = None
        stub.CHAT["q"] = None

    def tearDown(self):
        for k in ("CAPITAL_AGENT_MODE", "CAPITAL_AGENT_ADMIN_PASSWORD"):
            os.environ.pop(k, None)

    def _labels(self, kind):
        return [a[0] for n, a, k in stub.CALLS if n == kind and a]

    def test_visitor_cannot_upload_or_update(self):
        run_app()
        self.assertNotIn("Client workbook (.xlsx)", self._labels("file_uploader"))
        self.assertNotIn("Excel or CSV (up to 1 GB)", self._labels("file_uploader"))
        self.assertNotIn("Update from RBI", self._labels("button"))
        self.assertIn("Sign in", self._labels("button"))
        self.assertEqual(tab_errors(), [], [c for c in stub.CALLS if c[0] == "code"])

    def test_wrong_password_rejected_right_password_unlocks(self):
        run_app()
        stub.module.session_state["adm-pw"] = "guess"
        stub.BUTTONS["adm-in"] = True
        ss = run_app()
        self.assertFalse(ss.get("is_admin"))
        stub.module.session_state["adm-pw"] = "s3cret-pass"
        ss = run_app()
        self.assertTrue(ss.get("is_admin"))
        stub.BUTTONS.clear()
        run_app()
        self.assertIn("Client workbook (.xlsx)", self._labels("file_uploader"))
        self.assertIn("Update from RBI", self._labels("button"))

    def test_local_full_mode_unchanged(self):
        os.environ.pop("CAPITAL_AGENT_MODE", None)
        run_app()
        self.assertIn("Client workbook (.xlsx)", self._labels("file_uploader"))
        self.assertNotIn("Sign in", self._labels("button"))


class TestAllComponentPages(unittest.TestCase):
    def setUp(self):
        import tempfile
        os.environ["CAPITAL_AGENT_STORE"] = tempfile.mkdtemp()
        stub.module.session_state.clear()
        stub.COMPONENT["return"] = None
        stub.BUTTONS.clear()
        stub.FILE["upload"] = None
        stub.CHAT["q"] = None

    def test_every_analytical_page_is_a_rich_component(self):
        run_app()
        comps = {k.get("key"): k["html"] for n, a, k in stub.CALLS if n == "component"}
        expect = {"cc": "Capital Command Centre", "t02_tier1": "Tier 1 bridge", "t03_tier2": "How Tier 2 is computed",
                  "t04_rwa": "Risk-weight buckets", "t05_cem": "The CEM formula, live", "t07_sensitivity": "Tornado",
                  "t08_classification": "Every classification", "t09_validation": "All checks", "t10_audit": "Trail",
                  "t11_regulatory": "Rules", "t06_exceptions": "CRAR at stake by item", "t13_rbi": "Version timeline",
                  "t16_basel3": "Requirement stack vs capital held", "t17_calculation": "Independent check"}
        for key, needle in expect.items():
            self.assertIn(key, comps, key)
            self.assertIn(needle, comps[key], key)
            self.assertNotIn("<script", comps[key].lower(), key)
        self.assertEqual(tab_errors(), [], [c for c in stub.CALLS if c[0] == "code"])

    def test_calculation_downloads_and_rbi_register(self):
        run_app()
        dl = [a[0] for n, a, k in stub.CALLS if n == "download_button"]
        for want in ("Calculation ledger (CSV)", "Management memo (HTML → PDF)", "Download CSV ledger", "Download Excel pack"):
            self.assertIn(want, dl)
        comps = {k.get("key"): k["html"] for n, a, k in stub.CALLS if n == "component"}
        self.assertIn("Ledger reproduces the engine", comps["t17_calculation"])
        self.assertIn("in the system — RBI register", comps["t13_rbi"])
        self.assertIn("RBI reference", comps["t13_rbi"])

    def test_rbi_hero_uses_responsive_non_overlapping_layout(self):
        run_app()
        html = {k.get("key"): k["html"] for n, a, k in stub.CALLS if n == "component"}["t13_rbi"]
        self.assertIn("hero-copy", html)
        self.assertIn("hero-aside", html)
        self.assertIn("grid-template-columns: 1fr", html)
        self.assertIn("minmax(210px, 30%)", html)

    def test_overview_hides_prominent_run_status_label(self):
        run_app()
        html = {k.get("key"): k["html"] for n, a, k in stub.CALLS if n == "component"}["cc"]
        self.assertIn("Run status", html)
        self.assertNotIn("Calculated draft — human approval pending", html)
        self.assertNotIn("Blocked — evidence/control gate failed", html)
        self.assertNotIn("Management-ready — human approval recorded", html)

    def test_overlays_tables_and_toggles_present(self):
        run_app()
        comps = {k.get("key"): k for n, a, k in stub.CALLS if n == "component"}
        self.assertIn('data-drill-body="cc-t1"', comps["cc"]["html"])            # tiles open over the dashboard
        self.assertIn('class="panes"', comps["cc"]["html"])                      # tabs keep a fixed height
        self.assertIn('data-table="t1"', comps["t02_tier1"]["html"])
        self.assertIn("data-chips-for", comps["t02_tier1"]["html"])
        sets = comps["t05_cem"]["data"]["sets"]["cp"]
        self.assertEqual(sets["bank"]["rw"], "20%")
        self.assertNotEqual(sets["corporate"]["crar"], sets["bank"]["crar"])      # toggling counterparty moves CRAR


class TestNewTabs(unittest.TestCase):
    """RBI knowledge base and Large data tabs render against populated stores."""

    def setUp(self):
        import tempfile
        from test_rag_bigdata import PAGE_V1, ROWS, _tape_xlsx, src
        from capital_agent.bigdata import DataStore
        from capital_agent.rag_store import RagStore
        self.d = tempfile.mkdtemp()
        os.environ["CAPITAL_AGENT_STORE"] = self.d
        RagStore(os.path.join(self.d, "rag.sqlite")).ingest(src(), PAGE_V1)
        p = os.path.join(self.d, "tape.xlsx")
        _tape_xlsx(p, ROWS)
        DataStore(os.path.join(self.d, "data.sqlite")).import_file(p)
        stub.module.session_state.clear()
        stub.COMPONENT["return"] = None
        stub.BUTTONS.clear()
        stub.FILE["upload"] = None

    def test_tabs_render_with_data(self):
        ss = run_app()
        self.assertIsNone(ss.error, ss.error)
        self.assertEqual(tab_errors(), [], [c for c in stub.CALLS if c[0] == "code"])
        self.assertIn("RBI library", stub.PAGES)
        self.assertIn("Large data import", stub.PAGES)
        html = " ".join(str(a[0]) for n, a, k in stub.CALLS if n == "markdown" and a)
        self.assertIn("Blended risk weight", html)
        comps = {k.get("key"): k for n, a, k in stub.CALLS if n == "component"}
        self.assertIn("RBI library · the brain", comps["t13_rbi"]["html"])
        self.assertIn("How the brain gets RBI text", comps["t13_rbi"]["html"])
        self.assertTrue(any("RAG store" in e.description for e in ss.run.audit))   # agent used the store

    def test_attach_loan_tape_reruns_agent(self):
        ss = run_app()
        ns = runpy.run_path(APP, run_name="__main__")
        from capital_agent.bigdata import summarise_loan_tape
        t = ss.data_store.tables()[0]["table_name"]
        try:
            ns["set_loan_tape"](summarise_loan_tape(ss.data_store, t, "INR"))
        except stub.Rerun:
            pass
        self.assertIn("EXC-DATA-LOANTAPE", [e.exc_id for e in ss.run.exceptions])
        run_app()
        self.assertEqual(tab_errors(), [])


if __name__ == "__main__":
    unittest.main()
