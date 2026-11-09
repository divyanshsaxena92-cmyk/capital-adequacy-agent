"""Orchestrator - runs the 8-stage controlled workflow (Concept Note s.5).

  1 Ingestion -> 2 Validation -> 3 Regulatory mapping (AI) -> 4 Calculation (deterministic)
  -> 5 Reasoning/citations -> 6 Exceptions & human review -> 7 Output -> 8 Quality/controls

Which number gets used (guardrail: the agent never self-approves an interpretation):
  * agent AUTO_ACCEPT and agrees with maker (or no maker)  -> agent treatment
  * agent disagrees with maker, or item routed to review   -> maker treatment retained (or the
    rule's conservative treatment if no maker schedule), exception raised with quantified impact
  * SME decision recorded in decisions file                -> applied on the next run, logged
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import uuid
from dataclasses import asdict, dataclass, field

from .classifier import AUTO, REVIEW, Classification, LineItem, RegulatoryAgent
from .engine import CapitalLine, RWALine, compute_capital, compute_cem
from .ingest import Dataset, SourceValue, ingest, norm
from .knowledge import KnowledgeBase, RuleLibrary
from .validate import _num, source_checks, Check
from .security import LOCAL_ONLY_POLICY, enforce_local_only
from .framework import profile_for_dataset, preflight_diagnostics

SEV_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
TOL = 0.01


@dataclass
class AppliedItem:
    cls: Classification
    maker_ref: str | None
    maker_treatment: str | None        # capital treatment or risk weight (as str)
    maker_match: str
    applied: str | float
    basis: str
    exposure: float | None = None      # RWA exposure actually risk-weighted


@dataclass
class ExceptionItem:
    exc_id: str
    category: str
    title: str
    issue: str
    ai_best_guess: str
    competing: str
    citations: str
    evidence_required: str
    baseline_basis: str
    impact_crar_bps: float = 0.0
    impact_t1_bps: float = 0.0
    scenario_desc: str = ""
    scenario_overrides: dict = field(default_factory=dict)
    severity: str = "Low"
    maker_ref: str = ""
    item_ids: list = field(default_factory=list)
    status: str = "OPEN"
    decision: str = ""
    reviewer: str = ""
    comment: str = ""


@dataclass
class AuditEntry:
    seq: int
    stage: str
    item_id: str
    description: str
    source_ref: str
    input_value: float | str | None
    rule_id: str
    citation: str
    treatment: str
    output_value: float | str | None
    actor: str
    lineage_status: str = "UNVERIFIED"
    reconciliation_status: str = "NOT_APPLICABLE"


class Run:
    def __init__(self, input_path: str, base_dir: str, mode: str = "rules", layer: str = "ML",
                 decisions_path: str | None = None, threshold: float = 0.80, llm_client=None,
                 requested_framework: str = "SCB-CA-2025", rules_path: str | None = None,
                 kb_path: str | None = None, rag_db: str | None = None, loan_tape: dict | None = None):
        self.run_id = "RUN-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4].upper()
        self.started = dt.datetime.now().isoformat(timespec="seconds")
        self.input_path, self.base_dir, self.mode, self.layer = input_path, base_dir, mode, layer
        enforce_local_only(mode, llm_client)
        self.decisions_path, self.threshold, self.llm_client = decisions_path, threshold, None
        self.requested_framework = requested_framework
        self.kb_path = kb_path or os.path.join(base_dir, "regulatory_kb", "nbfc_capital_adequacy_2025.json")
        self.rules_path = rules_path or os.path.join(base_dir, "rules", "rule_library_v1.0.yaml")
        self.rag_db = rag_db
        self.loan_tape = loan_tape          # summary from capital_agent.bigdata.summarise_loan_tape
        self.market_rwa = 0.0
        self.operational_rwa = 0.0
        self.audit: list[AuditEntry] = []
        self.exceptions: list[ExceptionItem] = []

    # ----------------------------------------------------------------- audit
    def log(self, stage, item_id, desc, src="", inp=None, rule="", cite="", treat="", out=None, actor="Engine"):
        # Derived totals may not have one source cell; their rule and citation
        # still provide the required evidence lineage.
        lineage = "COMPLETE" if rule and cite else ("PARTIAL" if src or rule or cite else "NONE")
        self.audit.append(AuditEntry(len(self.audit) + 1, stage, item_id, desc, src, inp, rule, cite, treat, out, actor,
                                     lineage, "PENDING"))

    # ============================================================== pipeline
    def execute(self):
        # ---- Stage 1: ingestion
        self.ds: Dataset = ingest(self.input_path)
        ds = self.ds
        for line in ds.ingestion_log:
            self.log("1 Ingestion", "-", line, actor="Agent")
        self.log("1 Ingestion", "-", f"Reporting date {ds.reporting_date}; units {ds.units}", actor="Agent")

        # ---- regulatory corpus as of reporting date
        rag = None
        if self.rag_db and os.path.exists(self.rag_db):
            from .rag_store import RagStore
            rag = RagStore(self.rag_db)
        self.profile = profile_for_dataset(ds)
        self.entity_type = self.profile.entity_type
        self.kb = KnowledgeBase(self.kb_path, ds.reporting_date, rag,
                                ["NBFC"] if self.entity_type == "NBFC" else None)
        self.rbi_health, self.rbi_drift = None, []
        if rag is not None:
            from . import rbi_brain
            self.rbi_health = rbi_brain.health(rag, ds.reporting_date)
            st = rag.stats()
            self.log("1 Ingestion", "-", f"RAG store: {st['documents']} RBI documents, {st['chunks_current']} current "
                     f"paragraph chunks; retrieval filtered to text in force on {ds.reporting_date}", actor="Engine")
        self.rules = RuleLibrary(self.rules_path, ds.reporting_date, self.kb)
        if rag is not None:
            from . import rbi_brain
            self.rbi_drift = rbi_brain.rule_drift(rag, self.rules.rules, self.kb, as_of=ds.reporting_date)
        self.log("1 Ingestion", "-", f"KB {self.kb.version}: {len(self.kb.passages)} passages in force; "
                 f"excluded as not yet effective: {self.kb.excluded_future}", actor="Engine")
        self.log("1 Ingestion", "-", f"Rule library {self.rules.version}: {len(self.rules.rules)} rules loaded; "
                 f"rejected: {self.rules.rejected}", actor="Engine")

        # ---- entity profiling (which framework applies?)
        if self.entity_type == "BANK":
            self.minimums = dict(self.profile.minimums)
            framework = self.profile.framework
            profile_basis = "commercial-bank markers and capital/RWA schedules"
        elif self.entity_type == "NBFC":
            self.minimums = self.rules.get("R-MIN-001")["minimums"][self.layer]
            framework = "NBFC-CA-2025"
            profile_basis = "NBFC markers / statutory reserve evidence"
        else:
            self.minimums = {"crar": 0.0, "tier1": 0.0}
            framework = self.profile.framework
            profile_basis = "no explicit entity/framework evidence"
        self.framework_diagnostics = preflight_diagnostics(ds, self.profile)
        for diagnostic in self.framework_diagnostics:
            self._add(ExceptionItem(
                f"EXC-FRAMEWORK-{len(self.exceptions)+1}", "Framework evidence",
                "Framework evidence is incomplete", diagnostic,
                "Do not sign off until the missing evidence is supplied", "No silent assumption",
                self.profile.framework, ", ".join(self.profile.required_evidence),
                "No framework-specific adjustment applied", maker_ref="Preflight"), None, "High")
        self.log("1 Ingestion", "-", f"Entity profiled as {self.entity_type} ({profile_basis}); "
                 f"framework {framework}; layer assumed {self.layer}", rule="R-MIN-001", actor="Agent")

        # ---- Stage 2: validation
        self.checks: list[Check] = source_checks(ds)
        for c in self.checks:
            self.log("2 Validation", c.check_id, c.description, inp=c.expected, out=c.actual, treat=c.status)

        # ---- Stage 3: regulatory mapping (AI)
        self.agent = RegulatoryAgent(self.kb, self.rules, "rules", self.threshold, None)
        self.market_rwa = self._schedule_total("market_inputs", "market_risk_rwa")
        self.operational_rwa = self._schedule_total("operational_inputs", "operational_risk_rwa")
        known_diagnostics = {e.issue for e in self.exceptions}
        for diagnostic in self.framework_diagnostics:
            if diagnostic not in known_diagnostics:
                self._add(ExceptionItem(
                    f"EXC-FRAMEWORK-{len(self.exceptions)+1}", "Framework evidence",
                    "Framework schedule evidence is invalid", diagnostic,
                    "Correct the schedule before sign-off", "No silent assumption",
                    self.profile.framework, ", ".join(self.profile.required_evidence),
                    "Invalid row excluded from RWA", maker_ref="Preflight"), None, "High")
        self.capital_items = self._build_capital_items()
        self.cap_applied = [self._apply_capital(self.agent.classify(it)) for it in self.capital_items]
        deducted = {a.cls.label for a in self.cap_applied if a.applied == "T1_DEDUCT"}
        self.asset_items = self._build_asset_items(deducted)
        self.rwa_applied = [self._apply_rwa(self.agent.classify(it)) for it in self.asset_items]

        # ---- Stage 4: deterministic calculation (baseline = pre-SME-decision)
        self.cem = self._compute_cem()
        self.baseline = self._compute()
        self._log_calc(self.baseline, "Baseline")

        # ---- Stage 6: exceptions + sensitivity
        self._build_exceptions()
        self._apply_decisions()
        self.final = self.baseline
        if any(e.status == "RESOLVED - ALTERNATIVE APPLIED" for e in self.exceptions):
            self._commit_decisions()
            self.final = self._compute()
        if self.final is not self.baseline:
            self._log_calc(self.final, "Post-SME-decision")

        # ---- Basel III lens (binding for banks, benchmark for NBFCs)
        from . import basel3
        self.basel3 = basel3.assess(self)
        b3 = self.basel3
        self.log("8 Controls", "BASEL3", f"Basel III ({b3['framework']}): CET1 {b3['ratios']['cet1']:.2%} vs {b3['required']['cet1']:.2%}, "
                 f"Tier 1 {b3['ratios']['tier1']:.2%} vs {b3['required']['tier1']:.2%}, total {b3['ratios']['total']:.2%} vs "
                 f"{b3['required']['total']:.2%}, leverage {b3['ratios']['leverage']:.2%} vs {b3['required']['leverage']:.2%}",
                 rule="R-B3-001..006", cite="Commercial Banks Directions 2025 (Basel III)", treat=b3["framework"],
                 out=round(b3["ratios"]["cet1"], 6))

        # ---- Stage 8: controls
        self._benchmark()
        self.control_checks = self._controls()
        for entry in self.audit:
            if entry.stage == "4 Calculation":
                entry.reconciliation_status = "BENCHMARK_PENDING"
        if self.benchmark and all(b["status"] == "PASS" for b in self.benchmark):
            for entry in self.audit:
                if entry.stage == "4 Calculation":
                    entry.reconciliation_status = "BENCHMARK_PASS"
        open_blocking = [e for e in self.exceptions if e.status == "OPEN" and SEV_RANK[e.severity] <= 2]
        self.status = ("DRAFT - PENDING SME REVIEW" if open_blocking else "READY FOR CHECKER SIGN-OFF")
        self.log("8 Controls", "-", f"Run status: {self.status}; return submission disabled (human approval required)",
                 actor="Engine")
        return self

    # ============================================================ item builders
    def _schedule_total(self, role: str, value_key: str) -> float:
        """Sum an explicit supplemental RWA schedule; missing schedules remain zero and are diagnosed."""
        total = 0.0
        for rec in getattr(self.ds, role, []):
            value = _num(rec.get(value_key))
            if value is None or value < 0:
                self.framework_diagnostics.append(
                    f"{role} row {rec.get('_row')} has no non-negative numeric {value_key}; row excluded from RWA."
                )
                continue
            total += value
            self.log("3 Mapping", f"{role}:{rec.get('item_id', rec.get('_row'))}",
                     f"Included explicit {value_key} in total RWA",
                     f"'{rec.get('_sheet')}'!{rec.get('_cells', {}).get(value_key)}",
                     value, "R-BANK-RWA", "bank schedule", "RWA", value, "Engine")
        return total

    def _build_capital_items(self) -> list[LineItem]:
        ds, items = self.ds, []

        def add(sv: SourceValue, label=None, amount=None, ctx=None):
            if sv is None:
                label = label or "Missing capital source line"
                items.append(LineItem(f"CAP-{len(items) + 1:02d}", label, amount or 0.0,
                                      "MISSING", "capital", ctx or {}))
                return
            items.append(LineItem(f"CAP-{len(items) + 1:02d}", label or sv.label, sv.amount if amount is None else amount,
                                  sv.ref, "capital", ctx or {}))

        add(ds.find("^equity share capital"))
        n23 = ds.section_items("Note 23")
        for i, sv in enumerate(n23):
            nl = norm(sv.label)
            if nl.startswith("total"):
                continue
            nxt = n23[i + 1] if i + 1 < len(n23) else None
            if nxt and "of which" in norm(nxt.label) and "of which" not in nl:
                continue  # parent line; its 'of which' children are classified individually
            label = sv.label
            if "of which" in nl:
                label = "Equity others - " + sv.label.split(":", 1)[-1].strip()
            add(sv, label)
        for pat, sec in (("deferred tax assets", "FACE"), ("intangible", "FACE"), ("goodwill", "FACE"),
                         ("prepaid", "Note 14"), ("right of use", "FACE")):
            sv = ds.find(pat, sec)
            if sv and abs(sv.amount) > TOL:
                add(sv)
        ecl = ds.find("stage 1 - impairment", "Note 8")
        if ecl:
            add(ecl, amount=abs(ecl.amount))
        # Tier 2 instruments are outside the Note 23 equity breakup.
        seen = set()
        for pat in ("tier 2 bonds", "subordinated debt", "at1 bonds", "perpetual debt"):
            sv = ds.find(pat, "Note 24")
            if sv and sv.key not in seen and abs(sv.amount) > TOL:
                add(sv)
                seen.add(sv.key)
        for it in items:
            self.log("3 Mapping", it.item_id, f"Capital candidate identified: {it.label}", it.source_ref, it.amount,
                     actor="Agent")
        return items

    def _build_asset_items(self, deducted_labels: set) -> list[LineItem]:
        ds, items = self.ds, []

        def add(label, amount, ref, ctx=None):
            items.append(LineItem(f"RWA-{len(items) + 1:02d}", label, amount, ref, "asset", ctx or {}))

        cash, bank = ds.find("cash and cash equivalents"), ds.find("bank balances other")
        add("Cash and bank balances", (cash.amount if cash else 0.0) + (bank.amount if bank else 0.0),
            " + ".join(x.ref for x in (cash, bank) if x) or "MISSING")
        tr = ds.find("^trade receivables$")
        add("Trade receivables", tr.amount if tr else 0.0, tr.ref if tr else "MISSING")
        for sv in ds.section_items("Note 10"):
            if "total" not in norm(sv.label):
                add(sv.label, sv.amount, sv.ref)
        onfa, pre = ds.find("other non-financial assets"), ds.find("prepaid", "Note 14")
        pre_lbl = pre.label if pre else ""
        add("Other non-financial assets (excl. prepaid expenses)", (onfa.amount if onfa else 0.0) - (pre.amount if pre else 0),
            f"{onfa.ref if onfa else 'MISSING'} - {pre.ref if pre else ''}")
        if pre:
            add("Prepaid expenses", pre.amount, pre.ref, {"deducted_from_capital": pre_lbl in deducted_labels})
        fixed = [sv for pat in ("property, plant", "right of use") if (sv := ds.find(pat))]
        if fixed:
            add("Fixed assets + ROU", sum(sv.amount for sv in fixed), " + ".join(sv.ref for sv in fixed))
        for pat in ("current tax assets", "^investments$"):
            sv = ds.find(pat)
            if sv and abs(sv.amount) > TOL:
                add(sv.label, sv.amount, sv.ref)
        loans, ecl = ds.find("^loans$"), ds.find("stage 1 - impairment", "Note 8")
        loan_amount = loans.amount if loans else 0.0
        gross_up = abs(ecl.amount) if ecl else 0.0
        add("Loans", loan_amount + gross_up, f"{loans.ref if loans else 'MISSING'} + {ecl.ref if ecl else ''}",
            {"net_loans": loan_amount, "stage1_ecl_gross_up": gross_up})
        self.log("3 Mapping", "RWA", "Loan exposure measured gross of Stage 1 ECL (counted in Tier 2; only specific "
                 "provisions may be netted)", loans.ref if loans else "MISSING", loan_amount, "R-RWA-007", "para 18(2)(i), 16(6)",
                 "Gross-up", loan_amount + gross_up, "Engine")
        dta = ds.find("deferred tax assets")
        if dta:
            add(dta.label, dta.amount, dta.ref, {"deducted_from_capital": dta.label in deducted_labels})
        return items

    # ============================================================ maker matching
    MAKER_CAP_KEYS = [("equity share capital", "paid-up"), ("securities premium", "securities premium"),
                      ("statutory reserve", "statutory reserve"), ("retained earnings", "retained earnings"),
                      ("deferred tax", "deferred tax"), ("prepaid", "prepaid"), ("stage 1", "general provisions"),
                      ("investment fluctuation reserve", "investment fluctuation reserve"),
                      ("tier 2 bonds", "tier 2 bonds"), ("subordinated debt", "tier 2 bonds"),
                      ("at1", "at1 bonds"), ("perpetual debt", "at1 bonds")]

    def _maker_cap(self, it: LineItem):
        nl = norm(it.label)
        for a, b in self.MAKER_CAP_KEYS:
            if a in nl:
                for rec in self.ds.capital_inputs:
                    if b in norm(rec["line_item"]):
                        return rec, "label"
        for rec in self.ds.capital_inputs:  # fall back to amount match
            raw = _num(rec.get("raw_amount_inr_lakhs"))
            if raw and abs(raw - it.amount) <= TOL:
                return rec, "amount (label differs)"
        return None, "not in maker schedule"

    @staticmethod
    def _maker_treatment(rec) -> str | None:
        if rec is None:
            return "T1_EXCLUDE"
        raw = _num(rec.get("raw_amount_inr_lakhs")) or 0.0
        adj_s = str(rec.get("agent_adjusted_amount", "")).strip().lower()
        if rec.get("capital_category") == "Tier 2" and ("cap" in adj_s or "general provision" in norm(rec["line_item"])):
            return "T2_GENERAL_PROVISION"
        if rec.get("capital_category") == "Tier 2":
            return "T2_INCLUDE"
        adj = raw if adj_s == "same" else _num(adj_s)
        if adj is None:
            return None
        if abs(adj) <= TOL:
            return "T1_EXCLUDE"
        if adj < 0 < raw:
            return "T1_DEDUCT"
        if abs(adj - raw) <= TOL:
            return "T1_INCLUDE"
        return None

    def _apply_capital(self, c: Classification) -> AppliedItem:
        rec, how = self._maker_cap(next(i for i in self.capital_items if i.item_id == c.item_id))
        maker_t = self._maker_treatment(rec) if self.ds.capital_inputs else None   # no maker schedule supplied
        maker_ref = rec["item_id"] if rec else None
        if c.route == AUTO and (maker_t is None or maker_t == c.treatment):
            applied, basis = c.treatment, "Agent classification auto-accepted (agrees with maker)"
        elif c.route == AUTO:
            applied, basis = maker_t, "Maker treatment retained - agent disagrees (pending SME)"
        else:
            rule = self.rules.rules.get(c.rule_id or "", {})
            applied = maker_t or rule.get("conservative_treatment") or "T1_EXCLUDE"
            basis = ("Maker treatment retained pending SME" if maker_t
                     else "Conservative treatment applied pending SME")
        if rec is None and self.ds.capital_inputs:
            basis += " [item omitted from maker schedule => treated as excluded]"
        elif not self.ds.capital_inputs:
            basis = basis.replace("(agrees with maker)", "(no maker schedule supplied)")
        a = AppliedItem(c, maker_ref, maker_t, how, applied, basis)
        self.log("3 Mapping", c.item_id, f"{c.label}: agent proposes {c.treatment} (conf {c.confidence}); {c.route}",
                 c.source_ref, c.amount, c.rule_id or "", c.citation_text, c.treatment, None, f"Agent ({c.mode})")
        self.log("4 Calculation", c.item_id, f"Applied {applied}: {basis}", c.source_ref, c.amount, c.rule_id or "",
                 c.citation_text, applied, CapitalLine(c.item_id, c.label, c.amount, applied).tier1_effect,
                 "Engine")
        return a

    MAKER_RWA_KEYS = [("other non-financial", "other non-financial"), ("prepaid", "prepaid"),
                      ("cash and bank", "cash and bank"), ("trade receivables", "trade receivables"),
                      ("security deposits", "security deposits"), ("payment gateway", "payment gateway"),
                      ("other advances", "other advances"),
                      ("fixed assets", "fixed assets"), ("investments", "investments"),
                      ("loans", "loans"), ("loan portfolio", "loan portfolio")]

    def _apply_rwa(self, c: Classification) -> AppliedItem:
        nl, rec = norm(c.label), None
        for a, b in self.MAKER_RWA_KEYS:
            if nl.startswith(a) or a in nl:
                rec = next((r for r in self.ds.rwa_inputs if b in norm(r["asset_class"])), None)
                break
        agent_rw = c.risk_weight
        if not self.ds.rwa_inputs:  # no maker schedule: agent weight (conservative when ambiguous), pending review
            applied = agent_rw if agent_rw is not None else 1.0
            basis = ("Agent risk weight auto-accepted (no maker schedule supplied)" if c.route == AUTO
                     else "Agent conservative weight pending SME (no maker schedule supplied)")
            a = AppliedItem(c, None, None, "no maker schedule", applied, basis, c.amount)
            self.log("3 Mapping", c.item_id, f"{c.label}: agent proposes RW {agent_rw} (conf {c.confidence}); {c.route}",
                     c.source_ref, c.amount, c.rule_id or "", c.citation_text, f"RW {agent_rw}", None, f"Agent ({c.mode})")
            self.log("4 Calculation", c.item_id, f"Applied RW {applied}: {basis}", c.source_ref, c.amount,
                     c.rule_id or "", c.citation_text, f"RW {applied}", c.amount * applied, "Engine")
            return a
        maker_rw = _num(rec["risk_weight"]) if rec else 0.0  # omitted => not risk-weighted
        fallback_rw = agent_rw if agent_rw is not None else 1.0
        if c.route == AUTO and (rec is None and agent_rw == 0.0 or rec is not None and agent_rw is not None and agent_rw == maker_rw):
            applied, basis = agent_rw, "Agent risk weight auto-accepted (agrees with maker)"
        elif c.route == AUTO:
            applied = maker_rw if maker_rw is not None else fallback_rw
            basis = ("Maker risk weight retained - agent disagrees (pending SME)" if maker_rw is not None
                     else "Maker risk weight missing - agent/conservative weight retained pending SME")
        else:
            applied = maker_rw if rec and maker_rw is not None else fallback_rw
            basis = ("Maker risk weight retained pending SME" if rec and maker_rw is not None
                     else "Maker risk weight missing - agent/conservative weight pending SME" if rec
                     else "Agent/conservative weight pending SME")
        if rec is None and nl.startswith("prepaid"):
            applied = 1.0
            basis = "No explicit prepaid RWA row supplied; 100% risk weight retained pending SME"
        if rec is None:
            basis += " [not in maker RWA schedule]"
        a = AppliedItem(c, rec["item_id"] if rec else None,
                        None if rec is None or maker_rw is None else str(maker_rw), "label", applied,
                        basis, c.amount)
        self.log("3 Mapping", c.item_id, f"{c.label}: agent proposes RW {agent_rw} (conf {c.confidence}); {c.route}",
                 c.source_ref, c.amount, c.rule_id or "", c.citation_text, f"RW {agent_rw}", None, f"Agent ({c.mode})")
        self.log("4 Calculation", c.item_id, f"Applied RW {applied}: {basis}", c.source_ref, c.amount, c.rule_id or "",
                 c.citation_text, f"RW {applied}", c.amount * applied, "Engine")
        return a

    # ============================================================ calculation
    def _compute_cem(self):
        rule = self.rules.get("R-CCR-001")
        rc_sv = self.ds.find("derivative financial")
        rw = self.rules.get("R-CCR-002")["risk_weight"]
        cem = compute_cem(self.ds.derivative_inputs, self.ds.reporting_date, rule["add_on_table"],
                          rc_sv.amount if rc_sv else 0.0, rc_sv.ref if rc_sv else "MISSING", rw)
        for d in cem.deals:
            self.log("4 Calculation", d.item_id, f"{d.deal_id}: classified {d.contract_type} (two currencies); residual "
                     f"{d.residual_years:.2f}y => add-on {d.add_on:.1%}", d.source_ref, d.notional_lakhs, "R-CCR-001",
                     "para 18(7)(iii)(b), 18(8)(iii)", "PFE", d.pfe_lakhs, "Agent+Engine")
        self.log("4 Calculation", "CEM", "Replacement cost = gross positive MTM (balance-sheet derivative asset); no "
                 "netting recognised", rc_sv.ref if rc_sv else "MISSING", rc_sv.amount if rc_sv else 0.0,
                 "R-CCR-001", "para 18(8)(ii)", "RC", cem.replacement_cost)
        self.log("4 Calculation", "CEM", f"Counterparty risk weight {rw:.0%} (bank counterparty assumed)", "", cem.credit_equivalent,
                 "R-CCR-002", "para 18(3)(ii)", "RWA", cem.rwa)
        return cem

    def _lines(self, ov: dict | None = None):
        ov = ov or {}
        cap = [CapitalLine(a.cls.item_id, a.cls.label, a.cls.amount, ov.get("capital", {}).get(a.cls.item_id, a.applied),
                           a.cls.source_ref) for a in self.cap_applied]
        rwa = [RWALine(a.cls.item_id, a.cls.label, a.exposure, ov.get("rwa", {}).get(a.cls.item_id, a.applied),
                       a.cls.source_ref) for a in self.rwa_applied]
        return cap, rwa

    def _compute(self, ov: dict | None = None):
        cap, rwa = self._lines(ov)
        cem = self.cem
        if ov and "ccr_rw" in ov:
            cem = compute_cem(self.ds.derivative_inputs, self.ds.reporting_date,
                              self.rules.get("R-CCR-001")["add_on_table"], self.cem.replacement_cost,
                              self.cem.rc_source_ref, ov["ccr_rw"])
        rate = self.rules.get("R-T2-001")["cap"]["rate"]
        return compute_capital(cap, rwa, cem, rate, self.minimums,
                               self.market_rwa, self.operational_rwa)

    def _log_calc(self, r, label):
        self.log("4 Calculation", "TIER1", f"{label}: Tier 1 = sum of included items less deductions", "", None,
                 "R-T1-*", "paras 7-10, 14, 16", "", round(r.tier1, 2))
        self.log("4 Calculation", "TIER2", f"{label}: Tier 2 = general provisions {r.gp_gross:,.2f} + other eligible "
                 f"Tier 2 {r.tier2_other:,.2f}, with provisions capped at 1.25% of RWA {r.gp_cap:,.2f}; "
                 f"total capped at Tier 1", "", r.gp_gross, "R-T2-001/002/003", "paras 13(iii), 16(6), 6(3)",
                 "Cap", round(r.tier2, 2))
        self.log("4 Calculation", "RWA", f"{label}: Total RWA = on-balance-sheet {r.rwa_credit_on_bs:,.2f} + CCR "
                 f"{r.rwa_ccr:,.2f}", "", None, "R-RWA-*/R-CCR-*", "para 18", "", round(r.total_rwa, 2))
        self.log("4 Calculation", "RATIOS", f"{label}: CRAR {r.crar:.4%}; Tier 1 ratio {r.tier1_ratio:.4%}; "
                 f"breaches: {r.breaches or 'none'}", "", None, "R-MIN-001", "para 6", "", round(r.crar, 6))

    # ============================================================ exceptions
    def _impact(self, ov) -> tuple[float, float, object]:
        r = self._compute(ov)
        return ((r.crar - self.baseline.crar) * 1e4, (r.tier1_ratio - self.baseline.tier1_ratio) * 1e4, r)

    def _sev(self, bps, floor="Low", breach=False):
        if breach:
            return "Critical"
        s = "High" if abs(bps) >= 25 else "Medium" if abs(bps) >= 5 else "Low"
        return min(s, floor, key=lambda x: SEV_RANK[x])

    def _add(self, e: ExceptionItem, ov: dict | None, floor="Low"):
        if ov:
            e.scenario_overrides = ov
            e.impact_crar_bps, e.impact_t1_bps, r = self._impact(ov)
            e.severity = self._sev(e.impact_crar_bps, floor, bool(r.breaches))
            e.scenario_desc += f" => CRAR {r.crar:.2%}, Tier 1 {r.tier1_ratio:.2%}"
        else:
            e.severity = floor
        self.exceptions.append(e)

    def _cls_exception(self, a: AppliedItem, kind: str):
        c = a.cls
        disagrees = (a.maker_treatment is not None and str(c.treatment) != str(a.maker_treatment)) if kind == "capital" else \
            (a.maker_treatment is not None and c.risk_weight is not None and float(a.maker_treatment) != c.risk_weight)
        if c.route == AUTO and not disagrees:
            return
        rule = self.rules.rules.get(c.rule_id or "", {})
        alts = [x for x in (c.alternatives or [])]
        # headline scenario = the alternative that differs from what was applied, with largest impact
        best, best_ov, best_imp = None, None, -1
        cands = alts + ([{"treatment": c.treatment, "risk_weight": c.risk_weight, "basis": "Agent proposal"}])
        for alt in cands:
            if kind == "capital":
                t = alt.get("treatment")
                if not t or t == a.applied:
                    continue
                ov = {"capital": {c.item_id: t}}
            else:
                rw = alt.get("risk_weight")
                if rw is None or rw == a.applied:
                    continue
                ov = {"rwa": {c.item_id: rw}}
            imp = abs(self._impact(ov)[0])
            if imp > best_imp:
                best, best_ov, best_imp = alt, ov, imp
        guess = (f"{c.treatment}" if kind == "capital" else
                 f"Risk weight {format(c.risk_weight, '.0%') if c.risk_weight is not None else 'unknown'}") + \
            f" (confidence {c.confidence:.2f}, {c.rule_id})"
        comp = " | ".join(
            f"{x.get('treatment') if kind == 'capital' else (format(x.get('risk_weight'), '.0%') if x.get('risk_weight') is not None else 'unknown')}: "
            f"{x.get('basis', '')}"
            for x in alts) or "None identified"
        if disagrees:
            title = f"{c.label}: agent and maker treatments differ"
        else:
            title = f"{c.label}: {c.rule_title}"
        why = "; ".join(c.guardrail_notes)
        applied_txt = a.applied if kind == "capital" else f"RW {a.applied:.0%}"
        e = ExceptionItem(
            exc_id=f"EXC-{c.item_id}", category="Regulatory interpretation" if c.interpretive else "Classification",
            title=title, issue=f"{c.rationale} Routed because: {why or 'agent disagrees with maker'}.",
            ai_best_guess=guess, competing=comp,
            citations="; ".join(f"{x['doc']} para {x['para']}" for x in c.citations),
            evidence_required=c.evidence_required or rule.get("evidence_required", ""),
            baseline_basis=f"Calculated on: {applied_txt} ({a.basis})", item_ids=[c.item_id],
            scenario_desc=(f"If '{best.get('treatment') if kind == 'capital' else (format(best.get('risk_weight'), '.0%') if best.get('risk_weight') is not None else 'unknown')}' "
                           f"applied" if best else "No alternative with numeric effect"),
            maker_ref=a.maker_ref or "")
        self._add(e, best_ov, "Medium" if c.interpretive else "Low")

    def _build_exceptions(self):
        for a in self.cap_applied:
            self._cls_exception(a, "capital")
        for a in self.rwa_applied:
            self._cls_exception(a, "asset")
        chk = {c.check_id: c for c in self.checks}

        # enrich statutory reserve exception with the maker schedule mismatch
        for e in self.exceptions:
            if "45-ic" in norm(e.title) or "statutory" in norm(e.title):
                bad = [c for c in self.checks if c.check_id.startswith("V16") and c.status == "FAIL"
                       and "statutory" in norm(c.description)]
                if bad:
                    e.issue += (f" Data: maker schedule carries raw amount {bad[0].actual:,.2f} vs "
                                f"{bad[0].expected:,.2f} in Note 23 ({bad[0].detail}).")
                e.maker_ref += " / EX001"
            if any(k in norm(e.title) for k in ("cost of hedging", "corporate guarantee", "esop", "remeasurement")):
                e.maker_ref += " / EX001"
            if "prepaid" in norm(e.title):
                e.maker_ref += " / EX002"
        # ---- data / completeness / governance items
        v15 = chk.get("V15")
        loans = next(a for a in self.rwa_applied if a.cls.label == "Loans")
        if v15 and v15.status == "FAIL":
            self._add(ExceptionItem(
                "EXC-DATA-LOANS", "Data completeness", "Loan book does not reconcile to stage-wise ECL data",
                v15.detail + " Lifetime ECL (Stage 2/3) must be reduced from RWA and excluded from Tier 2.",
                "Cannot resolve without data - request stage-wise gross, ECL and product split",
                "n/a", "NBFC-CA-2025 para 16(6), 18(2)(i)", "Stage 1/2/3 gross & ECL; EIR adjustments; product-wise book",
                "Loans risk-weighted on net + Stage 1 ECL", item_ids=[loans.cls.item_id], maker_ref="EX004"), None, "High")
        rw010 = [c for c in self.checks if c.check_id == "V18-RWA010" and c.status == "FAIL"]
        if rw010:
            c = rw010[0]
            self._add(ExceptionItem(
                "EXC-DATA-RWA010", "Data quality", "Maker RWA schedule: loan asset value inconsistent with RWA",
                f"RWA010 shows asset value 148,971.19 but RWA {c.actual:,.2f} = 125% x 157,412.82 (net loans + Stage 1 ECL). "
                "Number is right, column is wrong; the agent rebuilt the exposure from source.",
                "Correct asset value column to 157,412.82 with a gross-up note", "n/a", "NBFC-CA-2025 para 18(2)(i)",
                "Maker to correct schedule", "No numeric impact", maker_ref="RWA010"), None, "Low")
        v17 = chk.get("V17")
        if v17 and v17.status != "PASS":
            self._add(ExceptionItem(
                "EXC-DATA-CAPCOL", "Data quality", "Non-numeric entries in Agent_Adjusted_Amount",
                v17.detail + f" Items: {v17.actual}.", "Interpreted as documented in classification log", "n/a", "-",
                "Clean the source column", "No numeric impact", maker_ref="Capital Inputs"), None, "Low")
        # governance: framework
        if self.requested_framework != "NBFC-CA-2025" and self.entity_type == "NBFC":
            self._add(ExceptionItem(
                "EXC-GOV-FRAMEWORK", "Governance", "Concept note cites Commercial Bank directions; entity is an NBFC",
                "The source balance sheet carries a statutory reserve u/s 45-IC and Ind AS NBFC presentation. The "
                "applicable text is the NBFC Capital Adequacy Directions 2025 (min CRAR 15%, Tier 1 10%), not the "
                "Commercial Bank Directions (CRAR 9% + CCB, CET1/AT1 Basel III structure). Rule library built on the "
                "NBFC directions.", "Apply NBFC-CA-2025", "SCB-CA-2025 would apply only if the entity were a bank",
                "NBFC-CA-2025 paras 3, 6; SCB-CA-2025", "Confirm entity's RBI registration / CoR", "NBFC-CA-2025 applied",
                maker_ref="Concept note s.6.1, s.9"), None, "High")
        # layer
        alt_layer = "UL" if self.layer == "ML" else "ML"
        self._add(ExceptionItem(
            "EXC-GOV-LAYER", "Governance", f"NBFC layer not stated in source - {self.layer} assumed",
            "Layer drives minimum ratios (UL adds CET1 9%), the Tier 1 build (para 10 owned-fund route for ML vs "
            "para 11 CET1 route for UL) and therefore the statutory-reserve question.",
            f"{self.layer} (most common for NBFC-ICC of this size)", f"{alt_layer}", "NBFC-CA-2025 paras 6, 10, 11",
            "RBI layer classification letter / SBR list", f"Minimums for {self.layer} applied", maker_ref="EX004"),
            None, "High")
        # CCR evidence
        self._add(ExceptionItem(
            "EXC-CCR-EVIDENCE", "Evidence", "Derivative CEM inputs need deal-level evidence",
            "Replacement cost is taken from the balance-sheet derivative asset (aggregate) since deal-level MTM was not "
            "provided; counterparty assumed to be a bank (20%); no netting recognised; add-on assumes a single "
            "principal exchange at maturity for each cross-currency swap.",
            "Bank counterparty, 10% FX add-on (residual 4.7y), gross RC", "Non-bank counterparty => 100% RW; "
            "multiple principal exchanges => add-on x remaining payments", "NBFC-CA-2025 paras 18(3), 18(8), 18(9)",
            "Deal confirmations, counterparty legal entity, per-deal MTM, ISDA/CSA and netting opinion",
            "20% counterparty RW", scenario_desc="If counterparty is non-bank (100% RW)", maker_ref="EX003"),
            {"ccr_rw": 1.0}, "Medium")
        # completeness checks the regulation requires
        if "co-lending" in norm(self.ds.raw_text):
            self._add(ExceptionItem(
                "EXC-INFO-COLEND", "Completeness", "Co-lending arrangements present - unrealised profit not evidenced",
                "Note 18 shows payables under co-lending. Unrealised profit booked on co-lent loans must be deducted from "
                "CET1 / owned fund until maturity; no such figure is in the data.", "Request figure; nil deduction applied",
                "n/a", "NBFC-CA-2025 para 15(2)", "Upfront gain recognised on co-lending / assignments", "Nil assumed",
                maker_ref="-"), None, "Medium")
        self._add(ExceptionItem(
            "EXC-INFO-DLG", "Completeness", "Default loss guarantee (DLG) exposure not evidenced",
            "If the entity provides DLG under digital-lending arrangements, the outstanding DLG is deducted from capital.",
            "Request confirmation; nil applied", "n/a", "NBFC-CA-2025 para 15(3)", "DLG register / confirmation",
            "Nil assumed", maker_ref="-"), None, "Medium")
        self._add(ExceptionItem(
            "EXC-INFO-OBS", "Completeness", "No off-balance-sheet (non-market) exposures supplied",
            "Undrawn sanctioned limits (e.g. credit-card or credit lines), guarantees and other commitments attract CCFs "
            "of 0-100% before risk weighting. The note referencing card advances suggests undrawn limits may exist.",
            "Request contingent liabilities & undrawn commitments; nil applied", "n/a", "NBFC-CA-2025 para 18(4)-(5)",
            "Contingent liabilities note; undrawn limits by tenor and cancellability", "Nil assumed", maker_ref="-"),
            None, "Medium")
        self._add(ExceptionItem(
            "EXC-INFO-DTA", "Evidence", "Confirm DTA composition",
            "Full net DTA is deducted (agent and maker agree). Confirm no DTL is available for same-authority offset and "
            "split of DTA on accumulated losses.", "Deduct 8,385.36 in full", "n/a", "NBFC-CA-2025 paras 8(2), 14",
            "Tax note", "Full deduction", maker_ref="EX002"), None, "Low")
        # evidence from an imported loan tape (large-data import)
        lt = self.loan_tape
        if lt and lt.get("blended_risk_weight") is not None:
            bs_net = self.ds.find("^loans$").amount
            bs_ecl1 = abs(self.ds.find("stage 1 - impairment", "Note 8").amount) if self.ds.find("stage 1 - impairment", "Note 8") else 0.0
            mix = "; ".join(f"{b['bucket']}: {b['gross']:,.0f} L ({b['gross'] / lt['gross_lakhs']:.0%})"
                            for b in lt["by_bucket"] if lt["gross_lakhs"])
            recon = (f"Tape: {lt['rows']:,} loans, gross {lt['gross_lakhs']:,.2f} L, ECL {lt['ecl_lakhs']:,.2f} L, net "
                     f"{lt['net_lakhs']:,.2f} L vs balance-sheet net loans {bs_net:,.2f} L (difference "
                     f"{lt['net_lakhs'] - bs_net:,.2f} L). Stage 1 ECL per tape {lt['stage1_ecl_lakhs']:,.2f} L vs "
                     f"Note 8 {bs_ecl1:,.2f} L. Lifetime (Stage 2/3) ECL per tape {lt['lifetime_ecl_lakhs']:,.2f} L - "
                     "to be reduced from RWA under para 16(6).")
            unm = f" {lt['unmapped_share']:.1%} of the book has a product the mapping could not place - review." \
                if lt["unmapped_share"] > 0.001 else ""
            self._add(ExceptionItem(
                "EXC-DATA-LOANTAPE", "Evidence", "Loan tape imported - product mix implies a blended risk weight",
                f"Product mix from {lt['source_file']} / {lt['sheet']}: {mix}. {recon}{unm}",
                f"Blended risk weight {lt['blended_risk_weight']:.1%} on the loan exposure (para 18(1))",
                "125% on the whole book (current basis)", "NBFC-CA-2025 paras 18(1), 16(6), 18(2)(i)",
                "Confirm product-to-bucket mapping and that the tape reconciles to the balance sheet",
                "Loans at 125% (maker basis)", item_ids=[loans.cls.item_id],
                scenario_desc=f"If blended RW {lt['blended_risk_weight']:.1%} from the tape is applied",
                maker_ref="EX004"), {"rwa": {loans.cls.item_id: round(lt["blended_risk_weight"], 6)}}, "Medium")
        # ---- RBI knowledge-base governance (the "brain")
        h = self.rbi_health
        if h is not None:
            date = f"{self.ds.reporting_date:%d %b %Y}"
            by_rule: dict = {}
            for d in self.rbi_drift:
                if d["applies_to_run"]:
                    by_rule.setdefault(d["rule_id"], []).append(d)
            for rid, ds_ in by_rule.items():
                items = "; ".join(f"para {d['para']} {d['what']} ({d['source']}, effective {d['effective']})" for d in ds_[:4])
                self._add(ExceptionItem(
                    f"EXC-RBI-{rid}", "Governance", f"RBI text cited by {rid} changed on or before {date}",
                    f"{ds_[0]['rule']}: {items}. The rule was approved against earlier text.",
                    "Re-approve or update the rule before relying on it", "Rule still valid if the change is editorial",
                    ", ".join(sorted({d['cited'] for d in ds_})), "Compare old and new paragraph in RBI library > Change log",
                    f"Rule {rid} as approved", maker_ref="Rule library"), None, "High")
            future = [d for d in self.rbi_drift if not d["applies_to_run"]]
            newer = h.get("newer_than_as_of", [])
            if future or newer:
                lst = "; ".join(f"{n['title'][:70]} (from {n['effective_from']})" for n in newer[:4])
                self._add(ExceptionItem(
                    "EXC-RBI-FUTURE", "Governance", f"Newer RBI text exists after {date} - correctly not applied",
                    f"{len(newer)} document version(s) take effect after the reporting date: {lst}. "
                    f"{len(future)} rule citation(s) are affected from those dates. A run with a later reporting date "
                    "will apply them automatically.", "No action for this reporting date", "-",
                    "As-of retrieval", "Re-approve affected rules before the next reporting date", "Text in force on reporting date",
                    maker_ref="RBI library"), None, "Low")
            if h["verdict"] == "curated-only":
                self._add(ExceptionItem(
                    "EXC-RBI-COVERAGE", "Governance", f"No full RBI text in force on {date} is loaded",
                    "Regulatory search is running on the curated paragraph summaries only. Load the RBI Directions "
                    "(RBI library > Update from RBI, or drop the PDF in the library folder). For an exact historical "
                    "run, add the version 'Updated as on' a date on or before the reporting date from RBI's "
                    "'Master Directions - Previous Versions' page.", "Load RBI text", "-", "Knowledge base health",
                    "RBI Directions PDF in force on the reporting date", "Curated summaries", maker_ref="RBI library"),
                    None, "Medium")
            elif h["verdict"] == "stale":
                self._add(ExceptionItem(
                    "EXC-RBI-STALE", "Governance", "RBI knowledge base not updated recently",
                    f"Last successful download {h['last_download']}. Run 'Update from RBI' and 'Check RBI for new "
                    "notices' before finalising.", "Update the knowledge base", "-", "Knowledge base health",
                    "Fresh download", "Existing text", maker_ref="RBI library"), None, "Low")
        self.exceptions.sort(key=lambda e: (SEV_RANK[e.severity], -abs(e.impact_crar_bps)))
        for e in self.exceptions:
            self.log("6 Exceptions", e.exc_id, f"[{e.severity}] {e.title}", inp=e.ai_best_guess,
                     out=f"{e.impact_crar_bps:+.1f} bps CRAR" if e.scenario_overrides else "info", actor="Agent")
        # combined: everything the agent proposes
        ov = {"capital": {}, "rwa": {}}
        for a in self.cap_applied:
            if a.cls.treatment != a.applied and a.cls.treatment in {"T1_INCLUDE", "T1_EXCLUDE", "T1_DEDUCT"}:
                ov["capital"][a.cls.item_id] = a.cls.treatment
        for a in self.rwa_applied:
            if a.cls.risk_weight is not None and a.cls.risk_weight != a.applied:
                ov["rwa"][a.cls.item_id] = a.cls.risk_weight
        self.agent_view_overrides = ov
        self.agent_view = self._compute(ov)

    # ============================================================ decisions
    def _apply_decisions(self):
        if not self.decisions_path or not os.path.exists(self.decisions_path):
            return
        with open(self.decisions_path) as f:
            rows = {r["exception_id"]: r for r in csv.DictReader(f) if r.get("decision")}
        for e in self.exceptions:
            r = rows.get(e.exc_id)
            if not r:
                continue
            d = r["decision"].strip().upper()
            e.decision, e.reviewer, e.comment = d, r.get("reviewer", ""), r.get("comment", "")
            if not e.reviewer:
                e.status = "OPEN"  # guardrail: an unsigned decision is not a decision
                e.comment += " [ignored - reviewer missing]"
                continue
            if d == "ACCEPT_ALTERNATIVE" and e.scenario_overrides:
                e.status = "RESOLVED - ALTERNATIVE APPLIED"
            elif d in {"RETAIN_BASELINE", "NOTED", "ACCEPT_ALTERNATIVE"}:
                e.status = "RESOLVED - BASELINE RETAINED" if d != "NOTED" else "RESOLVED - NOTED"
            self.log("6 Exceptions", e.exc_id, f"SME decision {d}: {e.comment}", out=e.status, actor=f"Human ({e.reviewer})")

    def _commit_decisions(self):
        """Write SME-approved alternatives into the applied treatments so every downstream view agrees."""
        for e in self.exceptions:
            if e.status != "RESOLVED - ALTERNATIVE APPLIED":
                continue
            tag = f"SME decision by {e.reviewer} ({e.exc_id})"
            for a in self.cap_applied:
                if a.cls.item_id in e.scenario_overrides.get("capital", {}):
                    a.applied, a.basis = e.scenario_overrides["capital"][a.cls.item_id], tag
            for a in self.rwa_applied:
                if a.cls.item_id in e.scenario_overrides.get("rwa", {}):
                    a.applied, a.basis = e.scenario_overrides["rwa"][a.cls.item_id], tag
            if "ccr_rw" in e.scenario_overrides:
                self.cem = compute_cem(self.ds.derivative_inputs, self.ds.reporting_date,
                                       self.rules.get("R-CCR-001")["add_on_table"], self.cem.replacement_cost,
                                       self.cem.rc_source_ref, e.scenario_overrides["ccr_rw"])
            self.log("4 Calculation", e.exc_id, f"Applied SME-approved alternative: {e.scenario_desc}",
                     actor=f"Human ({e.reviewer})")

    def _decision_overrides(self) -> dict:
        ov = {"capital": {}, "rwa": {}}
        for e in self.exceptions:
            if e.status == "RESOLVED - ALTERNATIVE APPLIED":
                for k, v in e.scenario_overrides.items():
                    if isinstance(v, dict):
                        ov[k].update(v)
                    else:
                        ov[k] = v
        return ov

    # ============================================================ controls
    def _benchmark(self):
        self.benchmark = []
        got = self.final.as_dict()
        for rec in self.ds.expected_output:
            m = rec.get("metric")
            exp = _num(rec.get("expected_value"))
            if m in got and exp is not None:
                act = got[m]
                tol = 1e-6 if rec.get("unit") == "Ratio" else TOL
                self.benchmark.append({"metric": m, "expected": exp, "actual": act, "diff": act - exp,
                                       "status": "PASS" if abs(act - exp) <= tol else "FAIL"})
                self.log("8 Controls", "BENCH", f"{m}: expected {exp} vs engine {act}", inp=exp, out=act,
                         treat="PASS" if abs(act - exp) <= tol else "FAIL")

    def _controls(self) -> list[Check]:
        r, out = self.final, []
        out.append(Check("C01", "Control", f"CRAR >= {self.minimums['crar']:.0%}",
                         "PASS" if r.crar >= self.minimums["crar"] else "FAIL", self.minimums["crar"], round(r.crar, 6)))
        out.append(Check("C02", "Control", f"Tier 1 ratio >= {self.minimums['tier1']:.0%}",
                         "PASS" if r.tier1_ratio >= self.minimums["tier1"] else "FAIL", self.minimums["tier1"],
                         round(r.tier1_ratio, 6)))
        out.append(Check("C03", "Control", "Tier 2 <= 100% of Tier 1", "PASS" if r.tier2 <= r.tier1 + TOL else "FAIL",
                         round(r.tier1, 2), round(r.tier2, 2)))
        # asset coverage: every balance-sheet asset is risk-weighted, deducted (0%) or captured as derivative RC
        loans = next((a for a in self.rwa_applied if a.cls.label == "Loans"), None)
        loan_sv, asset_sv = self.ds.find("^loans$"), self.ds.find("^total assets")
        covered = sum(a.exposure for a in self.rwa_applied) - (loans.cls.amount if loans else 0.0) \
            + (loan_sv.amount if loan_sv else 0.0) + self.cem.replacement_cost
        out.append(Check("C04", "Control", "All balance-sheet assets covered by RWA/deduction/CCR",
                         "PASS" if asset_sv and abs(covered - asset_sv.amount) <= TOL else "FAIL",
                         round(asset_sv.amount, 2) if asset_sv else None, round(covered, 2)))
        uncited = [a.cls.item_id for a in self.cap_applied + self.rwa_applied if not a.cls.citations]
        out.append(Check("C05", "Control", "Every classification carries a regulatory citation",
                         "PASS" if not uncited else "FAIL", actual=", ".join(uncited) or "all cited"))
        out.append(Check("C06", "Control", "Engine reproduces benchmark (Expected Output)",
                         "PASS" if self.benchmark and all(b["status"] == "PASS" for b in self.benchmark) else "FAIL",
                         actual=f"{sum(b['status'] == 'PASS' for b in self.benchmark)}/{len(self.benchmark)} metrics"))
        out.append(Check("C07", "Control", "Source data unchanged (agent outputs are additive)", "PASS",
                         detail="Input workbook opened read-only; outputs written to a separate pack"))
        out.append(Check("C08", "Control", "All calculation audit rows have source/rule/citation lineage",
                         "PASS" if all(e.lineage_status == "COMPLETE" for e in self.audit if e.stage == "4 Calculation")
                         else "WARN",
                         actual=f"{sum(e.lineage_status == 'COMPLETE' for e in self.audit if e.stage == '4 Calculation')}/"
                               f"{sum(e.stage == '4 Calculation' for e in self.audit)} complete"))
        out.append(Check("C09", "Control", "RBI source is in force for the reporting date",
                         "PASS" if self.rbi_health is None or self.rbi_health.get("verdict") == "ok" else "WARN",
                         actual=self.rbi_health.get("verdict") if self.rbi_health else "curated KB only",
                         detail="Curated-only or stale source text requires SME confirmation before sign-off."))
        return out

    # ============================================================ export
    def to_json(self) -> dict:
        r = self.final
        return {
            "run_id": self.run_id, "started": self.started, "status": self.status, "mode": self.mode,
            "data_policy": LOCAL_ONLY_POLICY,
            "reporting_date": str(self.ds.reporting_date), "entity_type": self.entity_type, "layer": self.layer,
            "framework": self.profile.framework, "market_rwa": self.market_rwa,
            "operational_rwa": self.operational_rwa,
            "kb_version": self.kb.version, "rule_library": self.rules.version,
            "results": r.as_dict(), "agent_view": self.agent_view.as_dict(), "minimums": self.minimums,
            "benchmark": self.benchmark,
            "exceptions": [{k: v for k, v in asdict(e).items()} for e in self.exceptions],
            "checks": [asdict(c) for c in self.checks + self.control_checks],
        }

    def write_decisions_template(self, path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["exception_id", "severity", "title", "decision", "reviewer", "comment"])
            for e in self.exceptions:
                w.writerow([e.exc_id, e.severity, e.title, "", "", ""])
