"""'Ask the Agent' - an offline assistant. No LLM, no API, nothing leaves the machine.

How it answers:
* Questions about the run (ratios, an exception, why an item was treated a certain way, data issues)
  are answered from the agent's own results - every number comes from the deterministic engine.
* What-if questions ("what if statutory reserve is included?") re-run the engine with that change.
* Regulatory questions are answered extractively: the best-matching RBI paragraphs are retrieved
  from the knowledge base (BM25) and the most relevant sentences are quoted with their paragraph
  numbers. Nothing is generated, so nothing can be invented.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

STOP = set("""a an the of and or to in for on is are be by as at with what which who whom how why when where
does do did can could should would will shall may might this that these those it its into from about
me my we our you your i please tell explain show give is there any under per than then so if""".split())


def _toks(text: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9]+", text.lower()):
        if t in STOP or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


# Regulatory abbreviations: a question in words should find text written in abbreviations, and vice versa.
SYNONYMS = [
    ("deferred tax asset", "dta"), ("deferred tax liabilit", "dtl"), ("risk weighted asset", "rwa"),
    ("risk-weighted asset", "rwa"), ("expected credit loss", "ecl"), ("cash flow hedge reserve", "cfhr"),
    ("capital to risk", "crar"), ("capital adequacy ratio", "crar"), ("common equity tier 1", "cet1"),
    ("current exposure method", "cem"), ("potential future exposure", "pfe"), ("perpetual debt", "pdi"),
    ("default loss guarantee", "dlg"), ("right of use", "rou"), ("non-banking financial", "nbfc"),
    ("exchange rate", "fx"), ("foreign exchange", "fx"), ("mark to market", "mtm"),
]


def expand(q: str) -> str:
    ql = q.lower()
    extra = []
    for phrase, abbr in SYNONYMS:
        if phrase in ql and not re.search(rf"\b{abbr}\b", ql):
            extra.append(abbr)
        elif re.search(rf"\b{abbr}s?\b", ql) and phrase not in ql:
            extra.append(phrase)
    return q + (" " + " ".join(extra) if extra else "")


@dataclass
class Answer:
    text: str
    kind: str
    sources: list = field(default_factory=list)     # {"para","title","snippet","url"}
    followups: list = field(default_factory=list)


TREAT = {"T1_INCLUDE": "include in Tier 1", "T1_EXCLUDE": "exclude from capital", "T1_DEDUCT": "deduct from Tier 1",
         "T2_GENERAL_PROVISION": "count in Tier 2 (capped)", "RISK_WEIGHT": "risk-weight"}


def _human(text: str) -> str:
    for k, v in TREAT.items():
        text = text.replace(k, v)
    return text


def _pct(x):
    return f"{x:.2%}"


def _l(x):
    return f"₹{x:,.2f} lakhs"


class Assistant:
    SUGGESTED = ["Is the client compliant with RBI minimums?", "Why is the statutory reserve flagged?",
                 "What if the statutory reserve is included in Tier 1?", "What risk weight applies to gold loans?",
                 "How is Tier 2 capped?", "Which data checks failed?"]

    def __init__(self, run=None, rag=None, frameworks: list[str] | None = None):
        self.run, self.rag = run, rag
        self.frameworks = frameworks or (["NBFC"] if run is not None and run.entity_type == "NBFC" else None)

    # ------------------------------------------------------------------ entry
    def ask(self, q: str) -> Answer:
        q = (q or "").strip()
        ql = q.lower()
        if not q or re.fullmatch(r"(hi|hello|hey|help|what can you do\??)", ql):
            return self._help()
        if self.run is not None and re.search(r"basel|cet ?1|leverage ratio|conservation buffer|\bccb\b|d-?sib|countercyclical", ql) \
                and not re.search(r"what is|explain|define|how is|how are|meaning", ql):
            return self._basel(ql)
        if self.run is not None:
            for fn in (self._what_if, self._metrics, self._validation, self._exception_or_item, self._risk_weight):
                a = fn(q, ql)
                if a:
                    return a
        else:
            a = self._risk_weight(q, ql)
            if a:
                return a
        return self._regulation(q)

    # ------------------------------------------------------------------ intents
    def _basel(self, ql) -> Answer:
        b = getattr(self.run, "basel3", None)
        if not b:
            return self._regulation(ql)
        lines = [f"**Basel III ({'binding' if b['framework'] == 'binding' else 'benchmark lens - NBFC rules govern compliance'})**",
                 "", "| Ratio | Actual | RBI Basel III incl. buffers | Headroom |", "|---|---:|---:|---:|"]
        for r in b["rows"]:
            lines.append(f"| {dict(cet1='CET1', tier1='Tier 1', total='Total capital', leverage='Leverage')[r['metric']]} | {r['value']:.2%} | "
                         f"{r['required']:.2%} | {r['headroom'] * 100:+.2f} pp |")
        lines += ["", f"Binding constraint: **{b['binding']}**. Distribution restriction: "
                      f"**{'none' if b['conservation'] == 0 else format(b['conservation'], '.0%') + ' of earnings to be conserved'}**.",
                  "Gaps: " + "; ".join(b["gaps"][:2]) + "."]
        return Answer("\n".join(lines), "basel3", [s for s in [self._cite_any("B3-MIN"), self._cite_any("B3-LEV")] if s],
                      ["What is the capital conservation buffer?", "Is the client compliant with RBI minimums?"])

    def _cite_any(self, pid):
        return self._cite(pid)

    def _help(self) -> Answer:
        return Answer(
            "I answer from this run's results and from the RBI text in the knowledge base - offline, with "
            "paragraph citations. Try asking about the ratios, a flagged item, a risk weight, a data issue, "
            "or a what-if.", "help", followups=self.SUGGESTED[:4])

    def _metrics(self, q, ql) -> Answer | None:
        r, m = self.run.final, self.run.minimums
        keys = {"crar": "crar" in ql or "capital adequacy" in ql or "car " in ql + " ",
                "t1r": "tier 1 ratio" in ql or "tier i ratio" in ql,
                "t1": bool(re.search(r"tier\s*(1|i)\b(?! ratio)", ql)),
                "t2": bool(re.search(r"tier\s*(2|ii)\b", ql)),
                "rwa": "rwa" in ql or "risk weighted" in ql or "risk-weighted" in ql,
                "comp": bool(re.search(r"complian|minimum|headroom|breach|meet|adequate|well capitali", ql))}
        if not any(keys.values()) or re.search(r"what if|suppose|why|flag", ql):
            return None
        if keys["t2"] and re.search(r"cap|limit|how", ql):
            return None                       # 'how is Tier 2 capped' is a regulatory question
        lines, srcs = [], []
        if keys["comp"] or keys["crar"]:
            ok = r.crar >= m["crar"] and r.tier1_ratio >= m["tier1"]
            lines.append(f"**{'Yes - compliant.' if ok else 'No - below a minimum.'}** CRAR is **{_pct(r.crar)}** "
                         f"against the {m['crar']:.0%} minimum (headroom {(r.crar - m['crar']) * 100:.2f} pp); "
                         f"Tier 1 ratio is **{_pct(r.tier1_ratio)}** against {m['tier1']:.0%}.")
            if r.breaches:
                lines.append("Breaches: " + "; ".join(r.breaches))
            srcs.append(self._cite("P6"))
        if keys["t1"] and not keys["t1r"]:
            inc = sum(a.cls.amount for a in self.run.cap_applied if a.applied == "T1_INCLUDE")
            ded = sum(abs(a.cls.amount) for a in self.run.cap_applied if a.applied == "T1_DEDUCT")
            lines.append(f"**Tier 1 capital is {_l(r.tier1)}** - included items {_l(inc)} less deductions "
                         f"{_l(ded)} (deferred tax assets, prepaid expenses).")
            srcs.append(self._cite("P9"))
        if keys["t1r"]:
            lines.append(f"**Tier 1 ratio is {_pct(r.tier1_ratio)}** = Tier 1 {_l(r.tier1)} ÷ RWA {_l(r.total_rwa)}.")
        if keys["t2"]:
            lines.append(f"**Tier 2 capital is {_l(r.tier2)}**: Stage 1 ECL of {_l(r.gp_gross)} is capped at 1.25% "
                         f"of RWA ({_l(r.gp_cap)}); {_l(r.gp_gross - r.tier2_gp_eligible)} is not recognised.")
            srcs.append(self._cite("P13"))
        if keys["rwa"]:
            lines.append(f"**Total RWA is {_l(r.total_rwa)}**: on-balance-sheet credit risk {_l(r.rwa_credit_on_bs)} "
                         f"plus counterparty credit risk on derivatives {_l(r.rwa_ccr)}.")
            srcs.append(self._cite("P18-1"))
        if keys["crar"] and not keys["comp"]:
            lines.append(f"CRAR = (Tier 1 + Tier 2) ÷ RWA = ({_l(r.tier1)} + {_l(r.tier2)}) ÷ {_l(r.total_rwa)}.")
        return Answer("\n\n".join(lines), "metrics", [s for s in srcs if s],
                      ["What if the statutory reserve is included in Tier 1?", "Which data checks failed?"])

    def _match_exception(self, ql):
        """Weighted token overlap: title & item labels 2, scenario 1.5, issue text 0.5."""
        best, score = None, 0.0
        qt = set(_toks(ql))
        for e in self.run.exceptions:
            if e.exc_id.lower() in ql:
                return e
            labels = " ".join(a.cls.label for a in self.run.cap_applied + self.run.rwa_applied
                              if a.cls.item_id in e.item_ids)
            s = (2 * len(qt & set(_toks(e.title + " " + labels))) + 1.5 * len(qt & set(_toks(e.scenario_desc)))
                 + 0.5 * len(qt & set(_toks(e.issue))))
            if s > score:
                best, score = e, s
        return best if score >= 3 else None

    def _what_if(self, q, ql) -> Answer | None:
        if not re.search(r"what if|suppose|assume|simulat|if we|if the|scenario", ql):
            return None
        run = self.run
        m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", ql)
        if m and ("loan" in ql or "risk weight" in ql):
            rw = float(m.group(1)) / 100
            loans = next(a for a in run.rwa_applied if a.cls.label == "Loans")
            ov = {"rwa": {loans.cls.item_id: rw}}
            desc = f"the loan book risk-weighted at {rw:.0%} instead of {loans.applied:.0%}"
        else:
            e = self._match_exception(ql)
            if e is None or not e.scenario_overrides:
                return Answer("I couldn't match that to a scenario. Try naming the item, e.g. *“what if the "
                              "statutory reserve is included?”* or *“what if loans are at 100%?”*", "what_if",
                              followups=["What if the statutory reserve is included in Tier 1?",
                                         "What if loans are risk-weighted at 100%?"])
            ov, desc = e.scenario_overrides, self._describe(ov_=e.scenario_overrides, e=e)
        base, new = run.final, run._compute(ov)
        d = (new.crar - base.crar) * 1e4
        txt = (f"With {desc}:\n\n"
               f"| | Current | Scenario | Change |\n|---|---:|---:|---:|\n"
               f"| Tier 1 capital | {base.tier1:,.2f} | {new.tier1:,.2f} | {new.tier1 - base.tier1:+,.2f} |\n"
               f"| Total RWA | {base.total_rwa:,.2f} | {new.total_rwa:,.2f} | {new.total_rwa - base.total_rwa:+,.2f} |\n"
               f"| CRAR | {_pct(base.crar)} | {_pct(new.crar)} | {d:+.1f} bps |\n"
               f"| Tier 1 ratio | {_pct(base.tier1_ratio)} | {_pct(new.tier1_ratio)} | "
               f"{(new.tier1_ratio - base.tier1_ratio) * 1e4:+.1f} bps |\n\n"
               f"{'⚠ This breaches a minimum.' if new.breaches else 'Still above all minimums.'} "
               "This is a simulation by the deterministic engine; the reported figure changes only after an SME "
               "records the decision in the review queue.")
        return Answer(txt, "what_if", followups=["Is the client compliant with RBI minimums?"])

    def _describe(self, ov_: dict, e) -> str:
        """Plain-English description of a scenario's overrides."""
        lab = {a.cls.item_id: a.cls.label.split(" (")[0] for a in self.run.cap_applied + self.run.rwa_applied}
        parts = []
        for iid, t in ov_.get("capital", {}).items():
            parts.append(f"{lab.get(iid, iid)} treated as: {TREAT.get(t, t)}")
        for iid, rw in ov_.get("rwa", {}).items():
            parts.append(f"{lab.get(iid, iid)} risk-weighted at {rw:.0%}")
        if "ccr_rw" in ov_:
            parts.append(f"derivative counterparties risk-weighted at {ov_['ccr_rw']:.0%}")
        return "; ".join(parts) or e.title

    def _exception_or_item(self, q, ql) -> Answer | None:
        e = self._match_exception(ql)
        if e is not None and not re.search(r"risk weight for|risk weight of|risk weight applies", ql):
            imp = (f" Changing it would move CRAR by **{e.impact_crar_bps:+.1f} bps**." if e.scenario_overrides else "")
            issue = re.sub(r"Matched '[^']*' to [^.]*\.\s*", "", e.issue)
            txt = _human(f"**{e.title}** — {e.severity} priority, status {e.status}.\n\n{issue}\n\n"
                         f"**Agent's best reading:** {e.ai_best_guess}\n\n"
                         f"**Other readings:** {e.competing}\n\n**Currently calculated on:** {e.baseline_basis}.{imp}"
                         f"\n\n**Evidence needed:** {e.evidence_required}")
            src = [{"para": e.citations, "title": "RBI citation", "snippet": "", "url": ""}] if e.citations else []
            fu = [f"What if {e.title.split(':')[0].lower()} is changed?"] if e.scenario_overrides else []
            return Answer(txt, "exception", src, fu + ["Which data checks failed?"])
        if re.search(r"\bwhy\b|treat|classif|includ|exclud|deduct", ql):
            qt = set(_toks(ql))
            best, score = None, 0
            for a in self.run.cap_applied + self.run.rwa_applied:
                s = len(qt & set(_toks(a.cls.label)))
                if s > score:
                    best, score = a, s
            if best is not None and score >= 1:
                c = best.cls
                how = (f"risk weight {best.applied:.0%}" if c.kind == "asset" else TREAT.get(best.applied, best.applied))
                txt = (f"**{c.label}** ({_l(c.amount)}) is treated as **{how}**.\n\n"
                       f"Rule {c.rule_id} — {c.rule_title}. {c.rationale}\n\n"
                       f"Confidence {c.confidence:.2f}; route **{c.route.replace('_', ' ').lower()}**. "
                       f"Basis: {best.basis}.")
                if c.guardrail_notes:
                    txt += "\n\nWhy it went to review: " + "; ".join(c.guardrail_notes) + "."
                src = [{"para": x["para"], "title": x.get("title", ""), "snippet": "", "url": x["url"]}
                       for x in c.citations]
                return Answer(txt, "item", src)
        return None

    def _validation(self, q, ql) -> Answer | None:
        if not re.search(r"fail|issue|problem|reconcil|data quality|validation|check|error|gap", ql):
            return None
        bad = [c for c in self.run.checks + self.run.control_checks if c.status != "PASS"]
        if not bad:
            return Answer("All validation and control checks pass.", "validation")
        lines = [f"**{len(bad)} check(s) need attention:**"]
        for c in bad:
            det = f" — {c.detail}" if c.detail else ""
            exp = f" (expected {c.expected:,.2f}, found {c.actual:,.2f})" if isinstance(c.expected, (int, float)) \
                and isinstance(c.actual, (int, float)) else ""
            lines.append(f"- **{c.check_id}** {c.description}{exp}{det}")
        return Answer("\n".join(lines), "validation", followups=["Why is the statutory reserve flagged?"])

    def _risk_weight(self, q, ql) -> Answer | None:
        if not re.search(r"risk weight|\brw\b", ql):
            return None
        from .bigdata import bucket_for
        name, rw = bucket_for(ql)
        if rw is None:
            return None
        txt = (f"**{rw:.0%}** — {name.split(' (')[0]}. Under the NBFC directions, retail consumer credit and credit "
               "card receivables carry 125%; housing, vehicle, gold, education and microfinance loans are carved out "
               "at 100%; staff loans 0%.")
        return Answer(txt, "risk_weight", [s for s in [self._cite("P18-1")] if s] + self._search_sources(q, 2))

    # ------------------------------------------------------------------ regulatory (extractive RAG)
    def _search(self, q, k=6):
        if self.rag is None:
            return []
        asof = self.run.ds.reporting_date if self.run is not None else None
        fw = None if re.search(r"basel|cet ?1|leverage|buffer|d-?sib|countercyclical|\bbank", q.lower()) else self.frameworks
        return self.rag.search(q, k=k, as_of=asof, frameworks=fw)

    def _search_sources(self, q, k=3):
        q = expand(q)
        return [{"para": h.para, "title": h.title, "snippet": h.text[:240], "url": h.url} for h in self._search(q, k)]

    def _cite(self, pid: str):
        kb = getattr(self.run, "kb", None) if self.run is not None else None
        p = kb.get(pid) if kb else None
        return {"para": p.para, "title": p.title, "snippet": p.text[:240], "url": p.url} if p else None

    def _regulation(self, q: str) -> Answer:
        q = expand(q)
        hits = self._search(q, 6)
        if not hits:
            return Answer("I couldn't find RBI text matching that. Load the RBI PDFs on the **RBI Library** page "
                          "(or drop them in `regulatory_kb/library/`) and ask again.", "no_match",
                          followups=self.SUGGESTED[:3])
        qt = set(_toks(q))
        scored = []
        for rank, h in enumerate(hits):
            for sent in re.split(r"(?<=[.;:])\s+(?=[A-Z(])", h.text):
                st = set(_toks(sent))
                if len(sent) < 30 or not st or sent.rstrip(". ").lower() == (h.heading or "").lower():
                    continue
                s = len(qt & st) + 1.0 / (rank + 1)     # relevance of the sentence + rank of its paragraph
                scored.append((s, rank, sent.strip(), h))
        scored.sort(key=lambda x: (-x[0], x[1]))
        picked, seen = [], set()
        for s, rank, sent, h in scored:
            if s < 1 or sent in seen:
                continue
            picked.append((sent, h))
            seen.add(sent)
            if len(picked) == 3:
                break
        if not picked:
            picked = [(hits[0].text[:400], hits[0])]
        body = "\n\n".join(f"> {sent}\n>\n> — *para {h.para}, {h.title[:70]}*" for sent, h in picked)
        srcs, used = [], set()
        for h in hits[:4]:
            if h.chunk_id in used:
                continue
            used.add(h.chunk_id)
            srcs.append({"para": h.para, "title": h.title, "snippet": h.text[:240], "url": h.url})
        return Answer("Here is what the RBI text says:\n\n" + body, "regulation", srcs)
