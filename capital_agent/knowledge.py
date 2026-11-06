"""Regulatory knowledge base and controlled rule library.

* Passages and rules are filtered by the reporting date, so a March-2026 run
  never sees text that only came into force later (reproducibility guardrail).
* Only rules with status APPROVED are visible to the agent and engine.
* A small BM25 retriever gives the LLM the most relevant passages and rules.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
from collections import Counter
from dataclasses import dataclass

import yaml

from .ingest import norm


def _tok(text: str) -> list[str]:
    return re.findall(r"[a-z0-9\.\-]+", norm(text))


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.toks = [_tok(d) for d in docs]
        self.k1, self.b = k1, b
        self.avg = sum(len(t) for t in self.toks) / max(len(self.toks), 1)
        df = Counter(w for t in self.toks for w in set(t))
        n = len(self.toks)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def scores(self, query: str) -> list[float]:
        q = _tok(query)
        out = []
        for t in self.toks:
            tf = Counter(t)
            s = 0.0
            for w in q:
                if w in tf:
                    f = tf[w]
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * len(t) / self.avg))
            out.append(s)
        return out


@dataclass
class Passage:
    id: str
    doc: str
    para: str
    title: str
    text: str
    tags: list
    effective_from: dt.date
    url: str
    doc_title: str

    def citation(self) -> str:
        return f"{self.doc_title}, para {self.para}"


class KnowledgeBase:
    """Curated passages (stable citation IDs for the rule library) + optional live RBI text from the RAG store."""

    def __init__(self, kb_path: str, as_of: dt.date, rag=None, rag_frameworks: list[str] | None = None):
        self.rag, self.rag_frameworks = rag, rag_frameworks
        self._rag_cache: dict = {}
        with open(kb_path) as f:
            raw = json.load(f)
        self.version = raw["kb_version"]
        self.documents = raw["documents"]
        self.as_of = as_of
        self.all_passages = []
        for p in raw["passages"]:
            d = self.documents[p["doc"]]
            self.all_passages.append(Passage(
                id=p["id"], doc=p["doc"], para=p["para"], title=p["title"], text=p["text"], tags=p["tags"],
                effective_from=dt.date.fromisoformat(p["effective_from"]), url=d["url"], doc_title=d["title"]))
        # effective-date filter
        self.passages = {p.id: p for p in self.all_passages if p.effective_from <= as_of}
        self.excluded_future = [p.id for p in self.all_passages if p.effective_from > as_of]
        ids = list(self.passages)
        self._ids = ids
        self._bm25 = BM25([self.passages[i].title + " " + self.passages[i].text + " " + " ".join(self.passages[i].tags)
                           for i in ids])

    def _from_hit(self, h) -> Passage:
        p = Passage(id=f"RAG:{h.chunk_id}", doc=h.doc_id, para=h.para, title=(h.heading or h.title)[:120],
                    text=h.text, tags=["rag", f"v{h.version}"], effective_from=dt.date.fromisoformat(h.effective_from),
                    url=h.url, doc_title=h.title)
        self._rag_cache[p.id] = p
        return p

    def retrieve(self, query: str, k: int = 5, k_rag: int = 4) -> list[Passage]:
        sc = self._bm25.scores(query)
        ranked = sorted(zip(self._ids, sc), key=lambda x: -x[1])
        out = [self.passages[i] for i, s in ranked[:k] if s > 0]
        if self.rag is not None:   # live RBI text, only versions in force at the reporting date
            out += [self._from_hit(h) for h in self.rag.search(query, k_rag, self.as_of, self.rag_frameworks)]
        return out

    def get(self, pid: str) -> Passage | None:
        if pid.startswith("RAG:"):
            if pid in self._rag_cache:
                return self._rag_cache[pid]
            if self.rag is not None:
                h = self.rag.get(pid[4:])
                if h and h.effective_from <= str(self.as_of) and (h.effective_to is None or h.effective_to > str(self.as_of)):
                    return self._from_hit(h)
            return None
        return self.passages.get(pid)

    def rag_stats(self) -> dict | None:
        return self.rag.stats() if self.rag is not None else None


class RuleLibrary:
    def __init__(self, path: str, as_of: dt.date, kb: KnowledgeBase):
        with open(path) as f:
            raw = yaml.safe_load(f)
        self.version = raw["library_version"]
        self.framework = raw["framework"]
        self.approved_by = raw.get("approved_by")
        self.rules = {}
        self.rejected = []
        for r in raw["rules"]:
            eff = dt.date.fromisoformat(str(r["effective_from"]))
            eff_to = dt.date.fromisoformat(str(r["effective_to"])) if r.get("effective_to") else None
            if r.get("status") != "APPROVED":
                self.rejected.append((r["id"], "not approved"))
                continue
            if eff > as_of or (eff_to and eff_to < as_of):
                self.rejected.append((r["id"], "not in force at reporting date"))
                continue
            missing = [c for c in r.get("citations", []) if kb.get(c) is None]
            if missing:  # guardrail: a rule that cannot be traced to in-force text is unusable
                self.rejected.append((r["id"], f"citation(s) not in KB as of date: {missing}"))
                continue
            self.rules[r["id"]] = r

    def get(self, rid: str) -> dict:
        return self.rules[rid]

    def candidates(self, label: str, areas: set[str]) -> list[tuple[dict, float]]:
        """Score rules by specific phrase matches (longer phrase = more specific)."""
        nl = norm(label)
        out = []
        for r in self.rules.values():
            if r["area"] not in areas:
                continue
            score = sum(len(t) for t in r.get("match_terms", []) if t in nl)
            if score:
                out.append((r, float(score)))
        return sorted(out, key=lambda x: -x[1])
