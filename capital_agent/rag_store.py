"""Regulatory knowledge base (RAG) built from RBI's own pages.

    python -m capital_agent.rag_store refresh            # download + index every enabled source
    python -m capital_agent.rag_store search "statutory reserve tier 1" --as-of 2026-03-31
    python -m capital_agent.rag_store add-file circular.pdf --title "..." --effective-from 2026-04-01

Design
* Sources are listed in regulatory_kb/sources.yaml (RBI URLs). Pages are fetched, cleaned and
  split into paragraphs that keep RBI's numbering (e.g. "7(iv)"), so every chunk is citable.
* Everything lives in one SQLite file with an FTS5 full-text index (BM25 ranking) - no server.
* Versioned: if RBI changes a page, the old chunks are kept but closed (effective_to set) and the
  new text becomes a new version. Searches take an as-of date, so a 31-Mar-2026 run only ever sees
  text that was in force on 31-Mar-2026.
* If a site blocks automated download, the same file can be uploaded manually (add-file / UI).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import sqlite3
from dataclasses import dataclass

import yaml

UA = "Mozilla/5.0 (compatible; CapitalAgent-RAG/0.3; regulatory research)"
MAX_CHUNK = 1800       # characters; longer paragraphs are split with overlap
MIN_CHUNK = 160        # shorter fragments are merged into their neighbour
OVERLAP = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT, version INTEGER, title TEXT, url TEXT, source_type TEXT, framework TEXT,
    applies_to TEXT, issued TEXT, effective_from TEXT, effective_to TEXT, content_hash TEXT,
    fetched_at TEXT, n_chunks INTEGER, origin TEXT, effective_date_note TEXT,
    PRIMARY KEY (doc_id, version));
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY, doc_id TEXT, version INTEGER, seq INTEGER, para TEXT,
    heading TEXT, text TEXT, effective_from TEXT, effective_to TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED, heading, para, text, tokenize = 'porter unicode61');
CREATE TABLE IF NOT EXISTS ingest_log (ts TEXT, doc_id TEXT, action TEXT, detail TEXT);
"""


# ------------------------------------------------------------------ extraction
def extract_text(content: bytes, source_type: str) -> str:
    if source_type == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "iframe"]):
        tag.decompose()
    # RBI pages put the direction text in a table cell; take the largest text-bearing block
    candidates = soup.find_all(["td", "div", "article", "main", "section"])
    best = max(candidates, key=lambda t: len(t.get_text(" ", strip=True)), default=soup)
    text = best.get_text("\n", strip=True)
    return text


# ------------------------------------------------------------------ chunking
ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv",
         "xvi", "xvii", "xviii", "xix", "xx"}
RE_CHAPTER = re.compile(r"^(chapter|part|section|annex(ure)?|schedule)\s+[\w\-]+", re.I)
RE_TOP = re.compile(r"^(\d{1,3})\.\s+(?=\S)")
RE_SUB = re.compile(r"^\((\d{1,3})\)\s*")
RE_PAREN = re.compile(r"^\(([a-z]{1,5})\)\s*")


@dataclass
class Chunk:
    seq: int
    para: str
    heading: str
    text: str
    effective_from: str | None = None      # per-chunk date (curated passages); defaults to the document's


def _is_roman(tok: str, stack: dict) -> bool:
    """(i)/(v)/(x) are ambiguous: roman if a roman sequence is open, letters if a letter sequence reached them."""
    if tok not in ROMAN:
        return False
    alpha = stack.get("alpha")
    if tok == "i":
        return alpha != "h"                     # (h) -> (i) continues the letters
    if len(tok) == 1:                           # (v) or (x)
        return stack.get("roman") is not None and alpha not in ("u", "w")
    return True                                 # (ii), (iv), (xii) ...


def _label(stack: dict) -> str:
    out = stack.get("top", "")
    for k in ("sub", "roman", "alpha"):
        if stack.get(k):
            out += f"({stack[k]})"
    return out


def chunk_text(text: str) -> list[Chunk]:
    """Split regulation text into paragraphs, keeping RBI-style numbering as the citation label."""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    stack: dict = {}
    heading = ""
    blocks: list[list] = []          # [label, heading, text]
    cur = None
    for ln in lines:
        new_label = None
        if RE_CHAPTER.match(ln) and len(ln) < 120:
            heading = ln
            continue
        m = RE_TOP.match(ln)
        if m and int(m.group(1)) < 400:
            stack = {"top": m.group(1)}
            new_label = _label(stack)
        elif RE_SUB.match(ln) and stack.get("top"):
            stack = {"top": stack["top"], "sub": RE_SUB.match(ln).group(1)}
            new_label = _label(stack)
        elif RE_PAREN.match(ln) and stack.get("top"):
            tok = RE_PAREN.match(ln).group(1)
            is_roman = _is_roman(tok, stack)
            if is_roman:
                stack = {k: v for k, v in stack.items() if k in ("top", "sub")} | {"roman": tok}
            else:
                stack = {k: v for k, v in stack.items() if k in ("top", "sub", "roman")} | {"alpha": tok}
            new_label = _label(stack)
        if new_label is not None:
            cur = [new_label, heading, ln]
            blocks.append(cur)
        elif cur is None:
            cur = ["preamble", heading, ln]
            blocks.append(cur)
        else:
            cur[2] += " " + ln
    # merge very small blocks into the previous one (same top paragraph), split very long ones
    merged: list[list] = []
    for b in blocks:
        top = lambda lbl: (re.match(r"\d+|[a-z]+", lbl) or [lbl])[0]
        if merged and len(b[2]) < MIN_CHUNK and top(merged[-1][0]) == top(b[0]) \
                and len(merged[-1][2]) + len(b[2]) < MAX_CHUNK:
            merged[-1][2] += " " + b[2]
            first = merged[-1][0].split("\u2013")[0]
            merged[-1][0] = f"{first}\u2013{b[0]}" if b[0] != first else first
        else:
            merged.append(list(b))
    out: list[Chunk] = []
    for label, head, body in merged:
        if len(body) <= MAX_CHUNK:
            out.append(Chunk(len(out), label, head, body))
            continue
        start = 0
        while start < len(body):
            end = min(len(body), start + MAX_CHUNK)
            if end < len(body):                       # break at a sentence boundary if possible
                cut = body.rfind(". ", start + MAX_CHUNK // 2, end)
                end = cut + 1 if cut > 0 else end
            out.append(Chunk(len(out), label, head, body[start:end].strip()))
            if end >= len(body):
                break
            start = max(end - OVERLAP, start + 1)
    return out


# ------------------------------------------------------------------ store
@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    version: int
    title: str
    para: str
    heading: str
    text: str
    url: str
    effective_from: str
    effective_to: str | None
    score: float


class RagStore:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.path = db_path
        # shared by every user of a deployment: WAL lets many read while one writes; writers wait instead of failing
        self.db = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript(SCHEMA)
        from . import rbi_brain
        rbi_brain.ensure_schema(self.db)

    # ---------------- ingestion
    def _log(self, doc_id, action, detail=""):
        self.db.execute("INSERT INTO ingest_log VALUES (?,?,?,?)",
                        (dt.datetime.now().isoformat(timespec="seconds"), doc_id, action, detail))

    def latest(self, doc_id: str):
        return self.db.execute("SELECT version, content_hash, effective_from FROM documents WHERE doc_id=? "
                               "ORDER BY version DESC LIMIT 1", (doc_id,)).fetchone()

    def ingest(self, src: dict, content: bytes, origin: str = "download", chunks: list | None = None) -> dict:
        """Index one document. Unchanged content is skipped; changed content becomes a new version."""
        doc_id = src["id"]
        h = hashlib.sha256(content).hexdigest()
        prev = self.latest(doc_id)
        if prev and prev[1] == h:
            self._log(doc_id, "unchanged", f"v{prev[0]}")
            self.db.commit()
            return {"doc_id": doc_id, "action": "unchanged", "version": prev[0]}
        from . import rbi_brain
        curated = chunks is not None
        if chunks is None:
            if src.get("type") == "pdf" and rbi_brain.pdf_needs_ocr(content):
                self._log(doc_id, "rejected", "scanned PDF - no text layer")
                self.db.commit()
                return {"doc_id": doc_id, "action": "rejected", "detail": "scanned PDF with no text layer - needs OCR; "
                        "download the text version of the PDF from rbi.org.in"}
            text = extract_text(content, src.get("type", "html"))
            chunks = chunk_text(text)
        else:
            text = " ".join(c.text for c in chunks)
        if len(text) < 500 or not chunks:
            js = rbi_brain.looks_like_js_stub(content)
            self._log(doc_id, "rejected", f"only {len(text)} characters extracted" + (" (JavaScript page)" if js else ""))
            self.db.commit()
            return {"doc_id": doc_id, "action": "rejected", "detail": ("the site returned a JavaScript-only page" if js else
                    "too little text extracted") + " - use the PDF link or the library folder"}
        if prev and not curated:                                  # same words, new file (re-published PDF)?
            old_txt = " ".join(t for (t,) in self.db.execute("SELECT text FROM chunks WHERE doc_id=? AND version=? "
                                                              "ORDER BY seq", (doc_id, prev[0])))
            if re.sub(r"\s+", " ", old_txt).strip() == re.sub(r"\s+", " ", " ".join(c.text for c in chunks)).strip():
                self._log(doc_id, "unchanged", f"v{prev[0]} (file re-published, text identical)")
                self.db.commit()
                return {"doc_id": doc_id, "action": "unchanged", "version": prev[0], "detail": "same text, new file"}
        meta = {"kind": "curated", "issued": None, "refs": []} if curated else rbi_brain.detect_meta(text, src.get("title", ""))
        if src.get("kind_override"):
            meta["kind"] = src["kind_override"]
        if not curated:                                            # RBI's own names: document first, then sources.yaml
            meta["official_title"] = meta.get("official_title") or (src.get("title", "") if src.get("title", "").startswith("Reserve Bank of India") else "")
            meta["ref_no"] = meta.get("ref_no") or src.get("ref_no", "")
        version = (prev[0] + 1) if prev else 1
        today = dt.date.today()
        if curated:
            eff, basis, conf = str(src.get("effective_from") or today), "curated summary", "high"
        elif prev:
            s_new = dict(src)
            s_new.pop("effective_from", None)                       # config date belongs to the first version
            if src.get("new_version_effective_from"):
                s_new["effective_override"] = src["new_version_effective_from"]
            eff, basis, conf = rbi_brain.choose_effective(s_new, meta, today)
            if eff <= prev[2]:                                     # never earlier than the version it replaces
                eff, basis, conf = today.isoformat(), "download date (detected date not after previous version)", "low"
        else:
            eff, basis, conf = rbi_brain.choose_effective(src, meta, today)
        note = "" if conf == "high" else f"{basis}; confirm"
        if prev:
            self.db.execute("UPDATE documents SET effective_to=? WHERE doc_id=? AND version=?", (eff, doc_id, prev[0]))
            self.db.execute("UPDATE chunks SET effective_to=? WHERE doc_id=? AND version=?", (eff, doc_id, prev[0]))
        issued = str(src.get("issued") or (meta["issued"].isoformat() if meta.get("issued") else ""))
        eff_to = str(src["effective_to"]) if src.get("effective_to") else None
        self.db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (doc_id, version, src.get("title", doc_id), src.get("url", ""), src.get("type", "html"),
                         src.get("framework", ""), src.get("applies_to", ""), issued, eff, eff_to,
                         h, dt.datetime.now().isoformat(timespec="seconds"), len(chunks), origin, note))
        for c in chunks:
            cid = f"{doc_id}:v{version}:{c.seq:04d}"
            self.db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?)",
                            (cid, doc_id, version, c.seq, c.para, c.heading, c.text, c.effective_from or eff, eff_to))
            self.db.execute("INSERT INTO chunks_fts VALUES (?,?,?,?)", (cid, c.heading, c.para, c.text))
        import json as _json
        self.db.execute("INSERT OR REPLACE INTO doc_meta (doc_id, version, kind, issued, effective_basis, confidence, refs, "
                        "needs_ocr, overridden, official_title, ref_no, circular_no) VALUES (?,?,?,?,?,?,?,?,0,?,?,?)",
                        (doc_id, version, meta["kind"], issued, basis, conf, _json.dumps(meta.get("refs", [])), 0,
                         meta.get("official_title", ""), meta.get("ref_no", ""), meta.get("circular_no", "")))
        self._log(doc_id, "indexed", f"v{version}: {len(chunks)} chunks from {len(text):,} chars ({origin}); "
                  f"{meta['kind']}; effective {eff} [{basis}]")
        self.db.commit()
        changed = rbi_brain.record_changes(self, doc_id, prev[0], version, eff) if prev else 0
        return {"doc_id": doc_id, "action": "indexed" if version == 1 else "new version", "version": version,
                "chunks": len(chunks), "kind": meta["kind"], "effective_from": eff, "basis": basis,
                "official_title": meta.get("official_title", ""), "ref_no": meta.get("ref_no", ""),
                "circular_no": meta.get("circular_no", ""),
                "confidence": conf, "paragraphs_changed": changed}

    @staticmethod
    def fetch(url: str, timeout: int = 45) -> bytes:
        from .rbi_brain import fetch_robust
        return fetch_robust(url, timeout=timeout)[0]

    def _fetch_and_ingest(self, s: dict) -> dict:
        """Try the primary URL; if it fails or yields too little text, try fallback_url."""
        attempts = [(s["url"], s.get("type", "html"))]
        if s.get("fallback_url"):
            fb = s["fallback_url"]
            attempts.append((fb, "pdf" if fb.lower().endswith(".pdf") else "html"))
        last = None
        for url, typ in attempts:
            try:
                content = self.fetch(url)
                if not content.lstrip()[:5].startswith(b"%PDF"):
                    from .rbi_brain import find_pdf_link
                    pdf = find_pdf_link(content)
                    if pdf:                            # a notification page: follow it to the official PDF
                        content, url = self.fetch(pdf), pdf
                typ = "pdf" if content.lstrip()[:5].startswith(b"%PDF") else "html"
                res = self.ingest({**s, "url": url, "type": typ}, content)
                if res["action"] != "rejected":
                    return res
                last = res
            except Exception as e:  # network / parse problems are reported, not fatal
                self._log(s["id"], "error", f"{url}: {str(e)[:250]}")
                self.db.commit()
                last = {"doc_id": s["id"], "action": "error", "detail": str(e)[:300]}
        return last

    def refresh(self, sources: list[dict], progress=None) -> list[dict]:
        results = []
        enabled = [s for s in sources if s.get("enabled", True)]
        for i, s in enumerate(enabled):
            if progress:
                progress(i / max(len(enabled), 1), f"Fetching {s.get('title', s['id'])}")
            results.append(self._fetch_and_ingest(s))
        if progress:
            progress(1.0, "Done")
        return results

    def ingest_folder(self, folder: str) -> list[dict]:
        """Index every PDF / saved HTML page in a folder (the offline route when downloads are blocked)."""
        out = []
        if not os.path.isdir(folder):
            return out
        for fn in sorted(os.listdir(folder)):
            if not fn.lower().endswith((".pdf", ".html", ".htm")):
                continue
            path = os.path.join(folder, fn)
            low = fn.lower()
            fw = "BANK" if any(k in low for k in ("bank", "scb", "commercial", "151md")) else "NBFC"
            mdate = dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()
            src = {"id": "LIB-" + re.sub(r"[^A-Za-z0-9]+", "-", os.path.splitext(fn)[0]).strip("-")[:40].upper(),
                   "title": os.path.splitext(fn)[0].replace("_", " "), "type": "pdf" if low.endswith(".pdf") else "html",
                   "framework": fw, "url": f"file:{fn}"}
            with open(path, "rb") as f:
                content = f.read()
            prev = self.latest(src["id"])
            if not prev:
                src["issued"] = mdate      # effective date unknown for a dropped file: flagged in the documents table
            res = self.ingest(src, content, origin="library folder")
            res["file"] = fn
            out.append(res)
        return out

    def seed_curated(self, kb_json_path: str) -> dict:
        """Load the curated paragraph summaries (NBFC and Basel III kept as separate documents) so search and chat
        work before any RBI download."""
        with open(kb_json_path, "rb") as f:
            raw = json.loads(f.read())
        out = {}
        for doc_key, (doc_id, fw) in {"NBFC-CA-2025": ("CURATED-NBFC-SUMMARIES", "NBFC"),
                                      "SCB-CA-2025": ("CURATED-BASEL3-SUMMARIES", "BANK")}.items():
            ps = [p for p in raw["passages"] if p["doc"] == doc_key]
            if not ps:
                continue
            chunks = [Chunk(i, p["para"], p["title"], f"{p['title']}. {p['text']}", p["effective_from"]) for i, p in enumerate(ps)]
            doc = raw["documents"][doc_key]
            src = {"id": doc_id, "title": "Curated summaries - " + doc["title"], "type": "curated", "framework": fw,
                   "url": doc["url"], "effective_from": "2025-11-28", "issued": "2025-11-28"}
            out[doc_id] = self.ingest(src, json.dumps(ps, sort_keys=True).encode(), origin="curated summary (paraphrased)", chunks=chunks)
        return out.get("CURATED-NBFC-SUMMARIES", next(iter(out.values()), {}))

    # ---------------- retrieval
    @staticmethod
    def _fts_query(q: str) -> str:
        toks = [t for t in re.findall(r"[A-Za-z0-9]+", q.lower()) if len(t) > 1]
        stop = {"the", "of", "and", "to", "in", "for", "on", "or", "is", "be", "an", "by", "as", "at", "with"}
        toks = [t for t in toks if t not in stop]
        return " OR ".join(f'"{t}"' for t in toks[:30])

    def search(self, query: str, k: int = 6, as_of: dt.date | str | None = None,
               frameworks: list[str] | None = None) -> list[Hit]:
        fq = self._fts_query(query)
        if not fq:
            return []
        sql = ("SELECT c.chunk_id, c.doc_id, c.version, d.title, c.para, c.heading, c.text, d.url, "
               "c.effective_from, c.effective_to, bm25(chunks_fts) AS s "
               "FROM chunks_fts JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id "
               "JOIN documents d ON d.doc_id = c.doc_id AND d.version = c.version "
               "WHERE chunks_fts MATCH ? AND NOT EXISTS (SELECT 1 FROM doc_meta m WHERE m.doc_id = c.doc_id "
               "AND m.version = c.version AND m.kind = 'draft')")
        args: list = [fq]
        if as_of:
            a = str(as_of)
            sql += " AND c.effective_from <= ? AND (c.effective_to IS NULL OR c.effective_to > ?)"
            args += [a, a]
        if frameworks:
            sql += f" AND d.framework IN ({','.join('?' * len(frameworks))})"
            args += list(frameworks)
        sql += " ORDER BY s LIMIT ?"
        args.append(k)
        rows = self.db.execute(sql, args).fetchall()
        return [Hit(*r[:10], score=round(-r[10], 3)) for r in rows]

    def get(self, chunk_id: str) -> Hit | None:
        r = self.db.execute("SELECT c.chunk_id, c.doc_id, c.version, d.title, c.para, c.heading, c.text, d.url, "
                            "c.effective_from, c.effective_to FROM chunks c JOIN documents d "
                            "ON d.doc_id=c.doc_id AND d.version=c.version WHERE c.chunk_id=?", (chunk_id,)).fetchone()
        return Hit(*r, score=0.0) if r else None

    # ---------------- reporting
    def documents(self) -> list[dict]:
        cols = ["doc_id", "version", "title", "url", "source_type", "framework", "applies_to", "issued",
                "effective_from", "effective_to", "content_hash", "fetched_at", "n_chunks", "origin",
                "effective_date_note"]
        return [dict(zip(cols, r)) for r in self.db.execute("SELECT * FROM documents ORDER BY doc_id, version")]

    def log(self, n: int = 50) -> list[tuple]:
        return self.db.execute("SELECT * FROM ingest_log ORDER BY rowid DESC LIMIT ?", (n,)).fetchall()

    def stats(self) -> dict:
        d = self.db.execute("SELECT COUNT(DISTINCT doc_id), COUNT(*) FROM documents").fetchone()
        live = self.db.execute("SELECT COUNT(*) FROM chunks WHERE effective_to IS NULL").fetchone()[0]
        total = self.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        last = self.db.execute("SELECT MAX(fetched_at) FROM documents").fetchone()[0]
        return {"documents": d[0], "versions": d[1], "chunks_current": live, "chunks_all_versions": total,
                "last_refresh": last}


def load_sources(path: str) -> list[dict]:
    with open(path) as f:
        return yaml.safe_load(f)["sources"]


def save_sources(path: str, sources: list[dict]):
    with open(path) as f:
        raw = yaml.safe_load(f)
    raw["sources"] = sources
    with open(path, "w") as f:
        yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True)


# ------------------------------------------------------------------ CLI
def _main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser(description="RBI regulatory knowledge base")
    ap.add_argument("--db", default=os.path.join(here, "store", "rag.sqlite"))
    ap.add_argument("--sources", default=os.path.join(here, "regulatory_kb", "sources.yaml"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--as-of")
    s.add_argument("-k", type=int, default=5)
    a = sub.add_parser("add-file")
    a.add_argument("path")
    a.add_argument("--id")
    a.add_argument("--title", required=True)
    a.add_argument("--framework", default="NBFC")
    a.add_argument("--effective-from", required=True)
    sub.add_parser("stats")
    args = ap.parse_args()
    store = RagStore(args.db)
    if args.cmd == "refresh":
        for r in store.refresh(load_sources(args.sources), lambda p, m: print(f"[{p:4.0%}] {m}")):
            print(r)
    elif args.cmd == "search":
        for h in store.search(args.query, args.k, args.as_of):
            print(f"\n[{h.score}] {h.title} | para {h.para} | v{h.version} | {h.chunk_id}\n  {h.text[:300]}...")
    elif args.cmd == "add-file":
        with open(args.path, "rb") as f:
            content = f.read()
        typ = "pdf" if args.path.lower().endswith(".pdf") else "html"
        src = {"id": args.id or re.sub(r"\W+", "-", args.title)[:40], "title": args.title, "type": typ,
               "framework": args.framework, "effective_from": args.effective_from, "url": f"file://{args.path}"}
        print(store.ingest(src, content, origin="upload"))
    else:
        print(json.dumps(store.stats(), indent=2))


if __name__ == "__main__":
    _main()
