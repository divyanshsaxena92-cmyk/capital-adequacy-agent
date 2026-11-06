"""Stages 3 & 5 - Regulatory mapping and reasoning (the AI layer).

For each line item the agent: retrieves candidate rules and RBI passages,
proposes a treatment with a citation and a confidence score, lists competing
interpretations, and decides whether the item may flow straight through or
must be routed to a human reviewer.

Guardrails enforced here (Concept Note s.4):
  * no citation  -> cannot be auto-accepted
  * cited rule / paragraph must be one actually retrieved and in force
  * interpretive rules always route to human review
  * confidence below threshold routes to human review
The agent never does arithmetic on capital; that is engine.py.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .knowledge import KnowledgeBase, RuleLibrary

AUTO, REVIEW = "AUTO_ACCEPT", "HUMAN_REVIEW"
VALID_TREATMENTS = {"T1_INCLUDE", "T1_EXCLUDE", "T1_DEDUCT", "T2_GENERAL_PROVISION", "RISK_WEIGHT", "INFO", "UNCLASSIFIED"}


@dataclass
class LineItem:
    item_id: str
    label: str
    amount: float
    source_ref: str
    kind: str                      # "capital" | "asset"
    context: dict = field(default_factory=dict)


@dataclass
class Classification:
    item_id: str
    label: str
    amount: float
    source_ref: str
    kind: str
    treatment: str
    risk_weight: float | None
    rule_id: str | None
    rule_title: str
    citations: list               # [{"id","para","doc","url"}]
    confidence: float
    rationale: str
    alternatives: list
    evidence_required: str
    interpretive: bool
    route: str
    mode: str
    guardrail_notes: list = field(default_factory=list)

    @property
    def citation_text(self) -> str:
        return "; ".join(f"para {c['para']}" for c in self.citations) if self.citations else "NONE"


class RegulatoryAgent:
    def __init__(self, kb: KnowledgeBase, rules: RuleLibrary, mode: str = "rules",
                 threshold: float = 0.80, llm_client=None, model: str | None = None):
        if mode not in {"rules", "llm", "hybrid"}:
            raise ValueError(mode)
        self.kb, self.rules, self.mode, self.threshold = kb, rules, mode, threshold
        self.model = model or os.environ.get("CAPITAL_AGENT_MODEL", "claude-sonnet-5-5")
        self._client = llm_client
        if mode in {"llm", "hybrid"} and self._client is None:
            try:
                import anthropic  # lazy import - not needed in rules mode
                self._client = anthropic.Anthropic()
            except Exception as e:  # pragma: no cover
                raise RuntimeError("LLM mode needs the 'anthropic' package and ANTHROPIC_API_KEY") from e

    # ------------------------------------------------------------------ helpers
    def _areas(self, item: LineItem) -> set[str]:
        return {"Tier 1", "Tier 2"} if item.kind == "capital" else {"RWA"}

    def _cites(self, rule: dict) -> list[dict]:
        out = []
        for pid in rule.get("citations", []):
            p = self.kb.get(pid)
            out.append({"id": p.id, "para": p.para, "doc": p.doc, "url": p.url, "title": p.title})
        return out

    def _finalise(self, item, treatment, rw, rule, conf, rationale, alts, mode, notes=None,
                  extra_cites=None) -> Classification:
        interpretive = bool(rule and rule.get("interpretive"))
        cites = (self._cites(rule) if rule else []) + list(extra_cites or [])
        notes = list(notes or [])
        route = AUTO
        if not cites:
            route = REVIEW
            notes.append("No citation - cannot flow to final output")
        if interpretive:
            route = REVIEW
            notes.append("Interpretive provision - SME determination required")
        if conf < self.threshold:
            route = REVIEW
            notes.append(f"Confidence {conf:.2f} below threshold {self.threshold:.2f}")
        return Classification(
            item_id=item.item_id, label=item.label, amount=item.amount, source_ref=item.source_ref, kind=item.kind,
            treatment=treatment, risk_weight=rw, rule_id=rule["id"] if rule else None,
            rule_title=rule["title"] if rule else "", citations=cites, confidence=round(conf, 2),
            rationale=rationale, alternatives=alts, evidence_required=(rule or {}).get("evidence_required", ""),
            interpretive=interpretive, route=route, mode=mode, guardrail_notes=notes)

    # ------------------------------------------------------------- rules mode
    def _classify_rules(self, item: LineItem) -> Classification:
        if item.kind == "asset" and item.context.get("deducted_from_capital"):
            rule = self.rules.get("R-RWA-006")
            return self._finalise(item, "RISK_WEIGHT", 0.0, rule, rule["default_confidence"],
                                  "Asset is deducted from Tier 1, so it carries 0% risk weight to avoid double counting.",
                                  [{"risk_weight": 1.0, "basis": "Retain 100% if the capital deduction is reversed on review."}],
                                  "rules")
        cands = self.rules.candidates(item.label, self._areas(item))
        if not cands:
            return self._finalise(item, "UNCLASSIFIED", None, None, 0.0,
                                  "No rule in the controlled library matches this item.", [], "rules")
        rule, score = cands[0]
        conf = rule["default_confidence"]
        notes, alts = [], list(rule.get("alternatives", []))
        competing = [o for o, s in cands[1:]
                     if s >= 0.6 * score and (o["treatment"], o.get("risk_weight")) != (rule["treatment"], rule.get("risk_weight"))]
        if competing:
            conf *= 0.75
            pool = [rule] + competing
            if all(r.get("risk_weight") is not None for r in pool):
                chosen = max(pool, key=lambda r: r["risk_weight"])   # most conservative while ambiguous
            else:
                chosen = rule
            for r in pool:
                if r is not chosen:
                    notes.append(f"Competing rule {r['id']} ({r['title']}) also matches")
                    alts.append({"treatment": r["treatment"], "risk_weight": r.get("risk_weight"),
                                 "basis": f"{r['id']}: {r['title']}"})
            if chosen is not rule:
                notes.append(f"Conservative rule {chosen['id']} chosen pending review")
            rule = chosen
        rw = rule.get("risk_weight")
        rationale = f"Matched '{item.label}' to {rule['id']} ({rule['title']})."
        return self._finalise(item, rule["treatment"], rw, rule, conf, rationale, alts, "rules", notes)

    # --------------------------------------------------------------- LLM mode
    SYSTEM = (
        "You are a regulatory-capital analyst assisting a Grant Thornton engagement team. You classify one "
        "balance-sheet line item of an Indian NBFC under the RBI capital adequacy framework. You may ONLY rely on "
        "the rules and passages provided. Never invent a paragraph. If the passages do not settle the question, "
        "say so, lower your confidence and list the competing readings. You do not calculate capital. "
        "Respond with a single JSON object and nothing else."
    )

    def _prompt(self, item: LineItem, rules: list[dict], passages) -> str:
        r_txt = "\n".join(
            f"- {r['id']} | {r['title']} | treatment={r['treatment']} | risk_weight={r.get('risk_weight')} | "
            f"interpretive={r.get('interpretive')} | cites={r.get('citations')}" for r in rules)
        p_txt = "\n".join(f"- [{p.id}] para {p.para} - {p.title}: {p.text}" for p in passages)
        return (
            f"LINE ITEM\nlabel: {item.label}\namount (INR lakhs): {item.amount}\nkind: {item.kind}\n"
            f"context: {json.dumps(item.context)}\n\nCANDIDATE RULES\n{r_txt}\n\nRBI PASSAGES (in force at reporting date)\n{p_txt}\n\n"
            'Return JSON: {"rule_id": str, "treatment": one of ' + str(sorted(VALID_TREATMENTS)) +
            ', "risk_weight": number|null, "citations": [passage ids], "confidence": 0-1, '
            '"rationale": str (<=80 words, plain English, cite paras), '
            '"competing_interpretations": [{"treatment": str, "risk_weight": number|null, "basis": str}], '
            '"evidence_required": str}'
        )

    def _call_llm(self, prompt: str) -> dict:
        resp = self._client.messages.create(model=self.model, max_tokens=1000, system=self.SYSTEM,
                                            messages=[{"role": "user", "content": prompt}])
        text = "".join(getattr(b, "text", "") for b in resp.content)
        text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.M).strip()
        return json.loads(text)

    def _classify_llm(self, item: LineItem) -> Classification:
        cand_rules = [r for r, _ in self.rules.candidates(item.label, self._areas(item))][:4]
        if item.kind == "asset" and item.context.get("deducted_from_capital"):
            cand_rules = [self.rules.get("R-RWA-006")] + cand_rules
        passages = self.kb.retrieve(f"{item.label} {' '.join(item.context.keys())}", k=5)
        for r in cand_rules:  # always give the model the text its candidate rules cite
            for pid in r.get("citations", []):
                if all(p.id != pid for p in passages):
                    passages.append(self.kb.get(pid))
        try:
            out = self._call_llm(self._prompt(item, cand_rules, passages))
        except Exception as e:
            fb = self._classify_rules(item)
            fb.route, fb.mode = REVIEW, "llm-fallback"
            fb.guardrail_notes.append(f"LLM call/parse failed ({type(e).__name__}); deterministic proposal shown")
            return fb
        notes = []
        allowed_rules = {r["id"]: r for r in cand_rules}
        allowed_pids = {p.id for p in passages}
        rule = allowed_rules.get(out.get("rule_id"))
        if rule is None:
            notes.append(f"Guardrail: model cited rule '{out.get('rule_id')}' that was not retrieved - rejected")
        bad_cites = [c for c in out.get("citations", []) if c not in allowed_pids]
        if bad_cites:
            notes.append(f"Guardrail: unretrieved citation(s) {bad_cites} - rejected")
            rule = None
        treatment = out.get("treatment") if out.get("treatment") in VALID_TREATMENTS else "UNCLASSIFIED"
        if rule is not None:  # treatment must be one the rule actually allows
            allowed_t = {rule["treatment"]} | {a.get("treatment") for a in rule.get("alternatives", []) if a.get("treatment")}
            if treatment not in allowed_t:
                notes.append(f"Guardrail: treatment {treatment} not permitted by {rule['id']}")
                rule = None
        conf = float(out.get("confidence", 0.0)) if rule else 0.0
        rw = out.get("risk_weight")
        extra = []
        if rule is not None:   # live RBI paragraphs the model relied on (already verified as retrieved)
            for c in out.get("citations", []):
                if c.startswith("RAG:"):
                    p = self.kb.get(c)
                    extra.append({"id": p.id, "para": p.para, "doc": p.doc, "url": p.url, "title": p.title})
        return self._finalise(item, treatment, rw, rule, conf, out.get("rationale", ""),
                              out.get("competing_interpretations", []), "llm", notes, extra)

    # --------------------------------------------------------------- public
    def classify(self, item: LineItem) -> Classification:
        if self.mode == "rules":
            return self._classify_rules(item)
        if self.mode == "llm":
            return self._classify_llm(item)
        det, llm = self._classify_rules(item), self._classify_llm(item)
        if (det.treatment, det.risk_weight) != (llm.treatment, llm.risk_weight) or det.rule_id != llm.rule_id:
            llm.route = REVIEW
            llm.guardrail_notes.append(
                f"Hybrid check: deterministic matcher proposed {det.rule_id}/{det.treatment}/{det.risk_weight}")
        llm.mode = "hybrid"
        return llm
