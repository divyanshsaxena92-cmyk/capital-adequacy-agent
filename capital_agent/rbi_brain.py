"""The 'brain' maintenance layer for the RBI knowledge base.

How RBI text gets in (in order of preference)
  1. Automatic download of RBI's own PDFs listed in regulatory_kb/sources.yaml (consolidated Directions and
     each Amendment Direction).                                              -> update_from_rbi()
  2. RBI watcher: reads RBI's official RSS feeds (notifications, press releases), shortlists capital-adequacy
     items, and indexes the linked PDF on request.                          -> check_feeds(), index_watch_item()
  3. Offline: drop PDFs in regulatory_kb/library/ or upload them in the app (corporate networks often block
     automated downloads).

What makes it reliable
  * Dates come from the text: "applicable from <date>", "with immediate effect", "Updated as on <date>".
    Issue date and effective date are kept apart (an amendment issued 1 Jan can apply from 1 Apr).
  * Drafts are stored for awareness but never used in calculations.
  * Every new version is diffed paragraph by paragraph; amendments record the paragraphs they modify.
  * Rule drift: a change to a paragraph that an approved rule cites flags that rule for SME re-approval.
  * Retrieval is always "as of" the reporting date, so a 31-Mar-2026 run never uses later rules; the health
    report lists newer text that exists but is (correctly) not applied.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import xml.etree.ElementTree as ET

MONTHS = ("january february march april may june july august september october november december").split()
_M = "|".join(MONTHS + [m[:3] for m in MONTHS])
DATE = rf"(?:(?:{_M})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_M})\.?,?\s+\d{{4}})"

FEEDS = {"notifications": "https://rbi.org.in/notifications_rss.xml",
         "press releases": "https://rbi.org.in/pressreleases_rss.xml"}
KEYWORDS = {"capital adequacy": 5, "prudential norms on capital": 5, "risk weight": 4, "tier 1": 3, "tier 2": 3,
            "crar": 3, "owned fund": 3, "basel": 3, "capital charge": 2, "leverage ratio": 2, "credit risk": 1,
            "nbfc": 1, "non-banking": 1, "provision": 1}

SCHEMA = """
CREATE TABLE IF NOT EXISTS doc_meta (doc_id TEXT, version INTEGER, kind TEXT, issued TEXT, effective_basis TEXT,
    confidence TEXT, refs TEXT, needs_ocr INTEGER, overridden INTEGER DEFAULT 0, PRIMARY KEY (doc_id, version));
CREATE TABLE IF NOT EXISTS changes (doc_id TEXT, from_v INTEGER, to_v INTEGER, para TEXT, change TEXT,
    old_text TEXT, new_text TEXT, effective TEXT, detected_at TEXT);
CREATE TABLE IF NOT EXISTS watch_items (guid TEXT PRIMARY KEY, title TEXT, link TEXT, pub_date TEXT, feed TEXT,
    relevance INTEGER, kind TEXT, framework TEXT, status TEXT, seen_at TEXT, doc_id TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS source_status (source_id TEXT PRIMARY KEY, last_checked TEXT, last_ok TEXT,
    last_error TEXT, last_action TEXT);
"""


NOMENCLATURE_COLS = ("official_title", "ref_no", "circular_no")


def ensure_schema(db):
    db.executescript(SCHEMA)
    have = {r[1] for r in db.execute("PRAGMA table_info(doc_meta)")}
    for col in NOMENCLATURE_COLS:                         # older stores: add the columns in place
        if col not in have:
            db.execute(f"ALTER TABLE doc_meta ADD COLUMN {col} TEXT")
    db.commit()


def nomenclature(text: str) -> dict:
    """RBI's own identifiers, read from the document: official title, RBI reference and circular number."""
    flat = re.sub(r"\s+", " ", text[:6000]).replace("–", "-").replace("—", "-")
    ref = re.search(r"\bRBI/(?:[A-Z]{2,6}/)?\d{4}-\d{2}/\d{1,4}\b", flat)
    circ = re.search(r"\b(?:DOR|DNBR|DBR|DNBS|DoR|CO\.DOR)[A-Za-z.]*\.[A-Za-z0-9.\- ]{2,40}?/\d{2}(?:\.\d{2})?[-.]\d{2,3}[-.]\d{2,3}/\d{4}-\d{2}\b", flat)
    title = re.search(r"(?:(?:Draft\s+)?Reserve Bank of India|Master Direction\s*-?)\s*\((?:[^()]|\([^()]*\))+\)\s*"
                      r"(?:(?:First|Second|Third|Fourth|Fifth|Sixth)\s+)?(?:Amendment\s+)?Directions?,?\s*20\d\d", flat, re.I)
    if not title:
        title = re.search(r"Master Direction\s*-\s*[A-Z][^.]{10,140}?(?:Directions?,?\s*20\d\d|20\d\d)", flat)
    return {"official_title": re.sub(r"\s+", " ", title.group(0)).strip() if title else "",
            "ref_no": ref.group(0) if ref else "", "circular_no": circ.group(0).strip() if circ else ""}


# ------------------------------------------------------------------ dates and kinds
def parse_date(s: str) -> dt.date | None:
    s = re.sub(r"(\d)(st|nd|rd|th)", r"\1", s.strip().replace(",", " ").replace(".", " "))
    s = re.sub(r"\s+", " ", s)
    for f in ("%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(s.title(), f).date()
        except ValueError:
            continue
    return None


def detect_meta(text: str, title: str = "") -> dict:
    """Read issue date, effective date, document kind and amended paragraphs from the document itself."""
    head = text[:2500]
    low = text.lower()
    out = {"issued": None, "effective": None, "basis": "none", "confidence": "low", "kind": "base", "refs": [],
           "updated_as_on": None, **nomenclature(text)}
    m = re.search(DATE, head, re.I)
    if m:
        out["issued"] = parse_date(m.group(0))
    m = re.search(rf"updated\s+as\s+on\s+({DATE})", text, re.I)
    if m:
        out["updated_as_on"] = parse_date(m.group(1))
    pats = [rf"(?:shall|will)\s+(?:be\s+)?(?:applicable|effective|come\s+into\s+(?:force|effect))\s+(?:from|on|with\s+effect\s+from)\s+({DATE})",
            rf"(?:applicable|effective)\s+(?:from|on)\s+({DATE})",
            rf"(?:with\s+effect\s+from|w\.\s?e\.\s?f\.?)\s+({DATE})"]
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            d = parse_date(m.group(1))
            if d:
                out.update(effective=d, basis=f"text: '{m.group(0)[:80]}'", confidence="high")
                break
    if out["effective"] is None and re.search(r"(?:come\s+into\s+(?:force|effect)|be\s+effective|applicable)\s+(?:with\s+)?immediate(?:ly|\s+effect)", low):
        out.update(effective=out["issued"], basis="text: 'with immediate effect' -> issue date", confidence="medium")
    out["early_adoption"] = bool(re.search(r"(?:or\s+from\s+an\s+earlier\s+date|earlier\s+date\s+when\s+these\s+directions\s+are\s+adopted|"
                                           r"adopted\s+by\s+an?\s+\w+\s+in\s+entirety)", text, re.I))
    title_zone = (title + " " + text[:450]).lower()          # the document's own title, not references to others
    wide = (title + " " + text[:1500]).lower()
    if re.search(r"\bdraft\b", title_zone) or "invites comments" in wide or "invites public comments" in wide:
        out["kind"] = "draft"
    elif "amendment directions" in title_zone or "amendment) directions" in title_zone:
        out["kind"] = "amendment"
    elif out["updated_as_on"]:
        out["kind"] = "consolidated"
    amd = [parse_date(d) for d in re.findall(rf"Amendment\)?\s+Directions,?\s+20\d\d\s*\(?\s*dated\s+({DATE})", text, re.I)]
    amd = [d for d in amd if d]
    out["amended_upto"] = max(amd) if amd else None
    if out["kind"] == "base" and out["amended_upto"]:
        out["kind"] = "consolidated"
    refs = re.findall(r"paragraphs?\s+(\d{1,3}(?:\s?\([0-9a-z]{1,5}\))*)", text, re.I)
    out["refs"] = sorted({re.sub(r"\s+", "", r) for r in refs}, key=lambda x: (len(x), x))[:40]
    return out


def choose_effective(src: dict, meta: dict, fetched: dt.date) -> tuple[str, str, str]:
    """(effective date, basis, confidence). Explicit config < consolidated 'updated as on' < text < issue < fetch."""
    cfg = src.get("effective_from")
    cfg_d = dt.date.fromisoformat(str(cfg)) if cfg else None
    if src.get("effective_override"):
        return str(src["effective_override"]), "SME override", "high"
    if meta.get("updated_as_on") and (cfg_d is None or meta["updated_as_on"] > cfg_d):
        return meta["updated_as_on"].isoformat(), "RBI 'Updated as on' date (consolidated text)", "high"
    if meta.get("amended_upto") and meta.get("kind") == "consolidated" and (cfg_d is None or meta["amended_upto"] > cfg_d):
        return (meta["amended_upto"].isoformat(),
                f"consolidated text already contains amendments dated up to {meta['amended_upto']:%d %b %Y}", "high")
    if meta.get("effective") and meta["confidence"] in ("high", "medium"):
        if meta.get("early_adoption"):
            return (meta["effective"].isoformat(), meta["basis"] + "; early adoption permitted - confirm the entity's "
                    "adoption date (SME override)", "medium")
        return meta["effective"].isoformat(), meta["basis"], meta["confidence"]
    if cfg_d:
        return cfg_d.isoformat(), "configured in sources.yaml", "medium"
    if meta.get("issued"):
        return meta["issued"].isoformat(), "issue date (no effective date found - confirm)", "low"
    return fetched.isoformat(), "download date (no date found in text - confirm)", "low"


# ------------------------------------------------------------------ robust fetching
class FetchError(Exception):
    pass


ALLOWED_DOMAINS = ("rbi.org.in", "rbidocs.rbi.org.in", "www.rbi.org.in", "website.rbi.org.in", "m.rbi.org.in")
MAX_BYTES = 60 * 1024 * 1024


def domain_allowed(url: str) -> bool:
    """Downloads are limited to RBI's own websites. A firm-approved mirror can be allowed with
    CAPITAL_AGENT_ALLOWED_DOMAINS="rbi.org.in,mirror.example.com"."""
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    extra = [d.strip().lower() for d in os.environ.get("CAPITAL_AGENT_ALLOWED_DOMAINS", "").split(",") if d.strip()]
    allowed = list(ALLOWED_DOMAINS) + extra
    return urlparse(url).scheme == "https" and any(host == d or host.endswith("." + d) for d in allowed)


def fetch_robust(url: str, retries: int = 3, timeout: int = 45, backoff: float = 2.0) -> tuple[bytes, str]:
    """Plain HTTPS GET of a public RBI page or PDF - the same request a browser makes. No API key, no login, no
    client data in the request. Retries with exponential backoff; honours HTTPS_PROXY / HTTP_PROXY and a corporate
    CA bundle in CAPITAL_AGENT_CA_BUNDLE (or REQUESTS_CA_BUNDLE); refuses non-RBI hosts and files over 60 MB."""
    import requests
    if not domain_allowed(url):
        raise FetchError(f"blocked: {url} is not an RBI address (https://*.rbi.org.in). Download it yourself and upload "
                         "the PDF, or add the host to CAPITAL_AGENT_ALLOWED_DOMAINS if your firm approves it")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/124.0 Safari/537.36",
               "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml,*/*;q=0.8",
               "Accept-Language": "en-IN,en;q=0.9"}
    verify = os.environ.get("CAPITAL_AGENT_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE") or True
    last = None
    for attempt in range(retries):
        try:
            with requests.get(url, headers=headers, timeout=timeout, verify=verify, stream=True) as r:
                if r.status_code in (429, 500, 502, 503, 504):
                    raise FetchError(f"HTTP {r.status_code}")
                r.raise_for_status()
                if not domain_allowed(r.url):
                    raise FetchError(f"blocked: redirected away from RBI to {r.url}")
                buf = bytearray()
                for part in r.iter_content(65536):
                    buf.extend(part)
                    if len(buf) > MAX_BYTES:
                        raise FetchError("file larger than 60 MB - refused")
                return bytes(buf), r.headers.get("Content-Type", "")
        except FetchError as e:
            if str(e).startswith(("blocked", "file larger")):
                raise
            last = e
        except Exception as e:  # network, TLS, proxy, HTTP
            last = e
        if attempt < retries - 1:
            time.sleep(backoff ** attempt)
    hint = ""
    s = str(last).lower()
    if "ssl" in s or "certificate" in s:
        hint = " (TLS inspection on a corporate network? set CAPITAL_AGENT_CA_BUNDLE to the company certificate file)"
    elif "proxy" in s or "connect" in s or "resolve" in s or "timed out" in s:
        hint = " (no internet or a proxy is required? set HTTPS_PROXY, or use the library folder)"
    raise FetchError(f"{type(last).__name__}: {str(last)[:200]}{hint}")


def find_pdf_link(html: bytes, base: str = "https://www.rbi.org.in") -> str | None:
    """RBI notification pages link the official PDF on rbidocs.rbi.org.in."""
    txt = html.decode("utf-8", "ignore")
    for m in re.finditer(r'href=["\']([^"\']+?\.pdf)["\']', txt, re.I):
        u = m.group(1)
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = base + u
        if "rbidocs" in u.lower() or "rbi.org.in" in u.lower():
            return u
    return None


def looks_like_js_stub(content: bytes) -> bool:
    t = content[:4000].decode("utf-8", "ignore").lower()
    return "enable javascript" in t or ("<noscript" in t and len(re.sub(r"<[^>]+>", "", t).strip()) < 400)


def pdf_needs_ocr(content: bytes) -> bool:
    try:
        from pypdf import PdfReader
        import io
        rd = PdfReader(io.BytesIO(content))
        text = "".join((p.extract_text() or "") for p in rd.pages[:5])
        return len(rd.pages) > 0 and len(text.strip()) < 200
    except Exception:
        return False


# ------------------------------------------------------------------ change log
def _by_para(rows) -> dict:
    out: dict = {}
    for para, text in rows:
        out.setdefault(para, []).append(text)
    return {k: re.sub(r"\s+", " ", " ".join(v)).strip() for k, v in out.items()}


def record_changes(store, doc_id: str, from_v: int, to_v: int, effective: str) -> int:
    old = _by_para(store.db.execute("SELECT para, text FROM chunks WHERE doc_id=? AND version=? ORDER BY seq",
                                    (doc_id, from_v)).fetchall())
    new = _by_para(store.db.execute("SELECT para, text FROM chunks WHERE doc_id=? AND version=? ORDER BY seq",
                                    (doc_id, to_v)).fetchall())
    now = dt.datetime.now().isoformat(timespec="seconds")
    rows = []
    for p in sorted(set(old) | set(new)):
        if p not in old:
            rows.append((doc_id, from_v, to_v, p, "added", "", new[p][:600], effective, now))
        elif p not in new:
            rows.append((doc_id, from_v, to_v, p, "removed", old[p][:600], "", effective, now))
        elif old[p] != new[p]:
            rows.append((doc_id, from_v, to_v, p, "changed", old[p][:600], new[p][:600], effective, now))
    store.db.executemany("INSERT INTO changes VALUES (?,?,?,?,?,?,?,?,?)", rows)
    store.db.commit()
    return len(rows)


# ------------------------------------------------------------------ RBI watcher (RSS)
def parse_feed(xml_bytes: bytes, feed_name: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):
        g = lambda tag: (it.findtext(tag) or "").strip()
        title, link = g("title"), g("link")
        text = (title + " " + g("description")).lower()
        rel = sum(w for k, w in KEYWORDS.items() if k in text)
        kind = "draft" if ("draft" in text or "invites comments" in text or "public comments" in text) else (
            "amendment" if "amendment" in text else "notice")
        fw = "NBFC" if ("non-banking" in text or "nbfc" in text) else ("BANK" if "bank" in text else "")
        items.append({"guid": g("guid") or link, "title": title, "link": link, "pub_date": g("pubDate"),
                      "feed": feed_name, "relevance": rel, "kind": kind, "framework": fw})
    return items


def check_feeds(store, feeds: dict | None = None, fetch=None, min_relevance: int = 4, possible_from: int = 2) -> dict:
    """Read RBI's RSS feeds; store capital-adequacy-relevant items that are new. Returns a summary."""
    ensure_schema(store.db)
    fetch = fetch or (lambda u: fetch_robust(u)[0])
    summary = {"checked": [], "new": [], "errors": []}
    for name, url in (feeds or FEEDS).items():
        try:
            items = parse_feed(fetch(url), name)
            summary["checked"].append(f"{name}: {len(items)} items")
        except Exception as e:
            summary["errors"].append(f"{name}: {e}")
            continue
        for it in items:
            if it["relevance"] < possible_from:
                continue                       # clearly unrelated (auctions, appointments ...)
            if store.db.execute("SELECT 1 FROM watch_items WHERE guid=?", (it["guid"],)).fetchone():
                continue
            store.db.execute("INSERT INTO watch_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (it["guid"], it["title"], it["link"], it["pub_date"], it["feed"], it["relevance"],
                              it["kind"], it["framework"], "NEW" if it["relevance"] >= min_relevance else "POSSIBLE",
                              dt.datetime.now().isoformat(timespec="seconds"),
                              None, "draft - for awareness, never applied" if it["kind"] == "draft" else ""))
            if it["relevance"] >= min_relevance:
                summary["new"].append(it)
            else:
                summary.setdefault("possible", []).append(it)
    store.db.commit()
    store._log("RBI-FEEDS", "checked", json.dumps({"new": len(summary["new"]), "errors": summary["errors"]})[:300])
    store.db.commit()
    return summary


def watch_items(store, status: str | None = None) -> list[dict]:
    ensure_schema(store.db)
    cols = ["guid", "title", "link", "pub_date", "feed", "relevance", "kind", "framework", "status", "seen_at",
            "doc_id", "note"]
    sql = "SELECT * FROM watch_items" + (" WHERE status=?" if status else "") + " ORDER BY seen_at DESC, relevance DESC"
    return [dict(zip(cols, r)) for r in store.db.execute(sql, (status,) if status else ())]


def index_watch_item(store, guid: str, fetch=None) -> dict:
    """Fetch the notice, follow it to the official PDF, and index it (drafts are stored but never applied)."""
    ensure_schema(store.db)
    row = store.db.execute("SELECT title, link, framework, kind FROM watch_items WHERE guid=?", (guid,)).fetchone()
    if not row:
        return {"action": "error", "detail": "unknown item"}
    title, link, fw, kind = row
    fetch = fetch or fetch_robust
    try:
        content, ctype = fetch(link)
        typ = "pdf"
        if not content.lstrip()[:5].startswith(b"%PDF"):
            pdf = find_pdf_link(content)
            if pdf:
                content, ctype = fetch(pdf)
                link = pdf
            typ = "pdf" if content.lstrip()[:5].startswith(b"%PDF") else "html"
        doc_id = "RBI-" + re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")[:48].upper()
        res = store.ingest({"id": doc_id, "title": title, "url": link, "type": typ, "framework": fw or "NBFC"},
                           content, origin=f"RBI feed ({kind})")
        status = "INDEXED" if res["action"] in ("indexed", "new version", "unchanged") else "FAILED"
        store.db.execute("UPDATE watch_items SET status=?, doc_id=?, note=? WHERE guid=?",
                         (status, doc_id, res.get("detail", ""), guid))
        store.db.commit()
        return res
    except Exception as e:
        store.db.execute("UPDATE watch_items SET status='FAILED', note=? WHERE guid=?", (str(e)[:300], guid))
        store.db.commit()
        return {"action": "error", "detail": str(e)[:300]}


def dismiss_watch_item(store, guid: str):
    store.db.execute("UPDATE watch_items SET status='DISMISSED' WHERE guid=?", (guid,))
    store.db.commit()


# ------------------------------------------------------------------ rule drift
def _para_match(a: str, b: str) -> bool:
    a, b = a.replace(" ", ""), b.replace(" ", "")
    return a == b or a.startswith(b + "(") or b.startswith(a + "(")


def rule_drift(store, rules: dict, kb, as_of: dt.date | str | None = None) -> list[dict]:
    """Approved rules whose cited RBI paragraph has been changed or amended since the rule library was approved."""
    ensure_schema(store.db)
    as_of = str(as_of) if as_of else None
    events = []
    for doc_id, to_v, para, change, eff, new_text in store.db.execute(
            "SELECT doc_id, to_v, para, change, effective, new_text FROM changes"):
        events.append({"source": f"{doc_id} v{to_v}", "para": para, "what": f"paragraph {change}", "effective": eff,
                       "text": new_text})
    for doc_id, version, refs, kind in store.db.execute("SELECT doc_id, version, refs, kind FROM doc_meta WHERE kind='amendment'"):
        eff = store.db.execute("SELECT effective_from FROM documents WHERE doc_id=? AND version=?", (doc_id, version)).fetchone()
        for p in json.loads(refs or "[]"):
            events.append({"source": f"{doc_id} v{version}", "para": p, "what": "amended by an Amendment Direction",
                           "effective": eff[0] if eff else None, "text": ""})
    out = []
    for r in rules.values():
        cited = [kb.get(pid).para for pid in r.get("citations", []) if kb.get(pid) is not None]
        for ev in events:
            for c in cited:
                if c and ev["para"] and any(_para_match(ev["para"], x) for x in re.split(r"[-–,]", c) if x):
                    applies = (as_of is None or (ev["effective"] or "9999") <= as_of)
                    out.append({"rule_id": r["id"], "rule": r["title"], "para": ev["para"], "cited": c,
                                "source": ev["source"], "what": ev["what"], "effective": ev["effective"],
                                "applies_to_run": applies})
    seen, uniq = set(), []
    for d in out:
        k = (d["rule_id"], d["para"], d["source"])
        if k not in seen:
            seen.add(k)
            uniq.append(d)
    return uniq


# ------------------------------------------------------------------ health
def health(store, as_of: dt.date | str | None = None, stale_days: int = 30,
           framework: str | None = None) -> dict:
    ensure_schema(store.db)
    as_of = str(as_of or dt.date.today())
    docs = store.documents()
    meta = {(d, v): (k, iss, basis, conf, ocr) for d, v, k, iss, basis, conf, ocr in
            store.db.execute("SELECT doc_id, version, kind, issued, effective_basis, confidence, needs_ocr FROM doc_meta")}
    rows = []
    for d in docs:
        k, iss, basis, conf, ocr = meta.get((d["doc_id"], d["version"]), ("curated" if d["origin"].startswith("curated") else "base",
                                                                           d.get("issued"), d.get("effective_date_note") or "", "", 0))
        in_force = d["effective_from"] <= as_of and (d["effective_to"] is None or d["effective_to"] > as_of)
        rows.append({**d, "kind": k, "issued": iss or d.get("issued"), "basis": basis, "confidence": conf,
                     "needs_ocr": bool(ocr), "in_force_on_date": in_force and k != "draft",
                     "after_date": d["effective_from"] > as_of and k != "draft"})
    full_text = [r for r in rows if r["in_force_on_date"] and r["kind"] != "curated"
                 and (not framework or r.get("framework") == framework)]
    newer = [r for r in rows if r["after_date"]]
    framework_mismatch = ([r for r in rows if r["in_force_on_date"] and r["kind"] != "curated"
                           and framework and r.get("framework") != framework]
                          if framework else [])
    last = store.db.execute("SELECT MAX(fetched_at) FROM documents WHERE origin NOT LIKE 'curated%'").fetchone()[0]
    stale = (last is None) or (dt.datetime.fromisoformat(last).date() < dt.date.today() - dt.timedelta(days=stale_days))
    errors = store.db.execute("SELECT ts, doc_id, detail FROM ingest_log WHERE action IN ('error','rejected') "
                              "ORDER BY rowid DESC LIMIT 5").fetchall()
    feeds_last = store.db.execute("SELECT MAX(ts) FROM ingest_log WHERE doc_id='RBI-FEEDS'").fetchone()[0]
    feeds_stale = (feeds_last is None or
                   dt.datetime.fromisoformat(feeds_last).date() < dt.date.today() - dt.timedelta(days=14))
    new_watch = store.db.execute("SELECT COUNT(*) FROM watch_items WHERE status='NEW'").fetchone()[0]
    changes = store.db.execute("SELECT COUNT(*) FROM changes").fetchone()[0]
    blocking = []
    if not full_text:
        blocking.append("No full-text source in force for the reporting date and applicable framework.")
    if framework_mismatch:
        blocking.append("In-force full-text sources are framework-mismatched: " +
                        ", ".join(f"{r['doc_id']} v{r['version']}" for r in framework_mismatch))
    if newer:
        blocking.append("Future-dated source versions are present: " +
                        ", ".join(f"{r['doc_id']} v{r['version']} ({r['effective_from']})" for r in newer[:8]))
    if any(r["kind"] == "draft" for r in rows):
        blocking.append("Draft sources are present and must not support management status.")
    if stale:
        blocking.append("The RBI source refresh is stale or has never completed successfully.")
    if not blocking:
        verdict = "ok"
    elif framework_mismatch:
        verdict = "framework-mismatch"
    elif not full_text:
        verdict = "curated-only"
    elif newer:
        verdict = "future-dated"
    elif any(r["kind"] == "draft" for r in rows):
        verdict = "draft-present"
    else:
        verdict = "stale"
    return {"as_of": as_of, "framework": framework, "documents": rows, "full_text_in_force": len(full_text),
            "source_ids_in_force": [f"{r['doc_id']} v{r['version']}" for r in full_text],
            "newer_than_as_of": newer, "framework_mismatch": framework_mismatch,
            "drafts": sum(r["kind"] == "draft" for r in rows), "needs_ocr": [r["doc_id"] for r in rows if r["needs_ocr"]],
            "last_download": last, "stale": stale, "recent_errors": errors, "feeds_last_checked": feeds_last,
            "new_feed_items": new_watch, "changes_logged": changes, "feeds_stale": feeds_stale,
            "blocking_issues": blocking, "verdict": verdict}


def set_effective_override(store, doc_id: str, version: int, date_iso: str, who: str = "SME"):
    """SME correction of a detected effective date (logged; re-dates the version's paragraphs)."""
    ensure_schema(store.db)
    dt.date.fromisoformat(date_iso)
    store.db.execute("UPDATE documents SET effective_from=?, effective_date_note=? WHERE doc_id=? AND version=?",
                     (date_iso, f"overridden by {who}", doc_id, version))
    store.db.execute("UPDATE chunks SET effective_from=? WHERE doc_id=? AND version=?", (date_iso, doc_id, version))
    store.db.execute("UPDATE doc_meta SET overridden=1, effective_basis=? WHERE doc_id=? AND version=?",
                     (f"SME override by {who}", doc_id, version))
    store._log(doc_id, "override", f"v{version} effective_from -> {date_iso} by {who}")
    store.db.commit()


def update_from_rbi(store, sources: list[dict], progress=None) -> list[dict]:
    """Download every enabled source (with fallbacks) and record per-source status."""
    ensure_schema(store.db)
    out = []
    enabled = [s for s in sources if s.get("enabled", True)]
    for i, s in enumerate(enabled):
        if progress:
            progress(i / max(len(enabled), 1), f"Checking {s.get('title', s['id'])[:60]}")
        now = dt.datetime.now().isoformat(timespec="seconds")
        res = store._fetch_and_ingest(s)
        ok = res and res.get("action") in ("indexed", "new version", "unchanged")
        store.db.execute("INSERT INTO source_status VALUES (?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET "
                         "last_checked=excluded.last_checked, last_ok=COALESCE(excluded.last_ok, source_status.last_ok), "
                         "last_error=excluded.last_error, last_action=excluded.last_action",
                         (s["id"], now, now if ok else None, None if ok else (res or {}).get("detail", "failed"),
                          (res or {}).get("action", "error")))
        store.db.commit()
        out.append({"source": s["id"], **(res or {})})
    if progress:
        progress(1.0, "Done")
    return out


# ------------------------------------------------------------------ RBI "Master Directions - Previous Versions"
def parse_previous_versions(html: bytes, base: str = "https://www.rbi.org.in") -> list[tuple[dt.date, str]]:
    """Links labelled 'Updated as on <date>' on an RBI previous-versions page -> [(date, url)] oldest first."""
    txt = html.decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'<a\b[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', txt, re.I | re.S):
        visible = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2)))      # link text with tags removed
        dm = re.search(rf"updated\s+as\s+on\s+({DATE})", visible, re.I)
        if not dm:
            continue
        u, d = m.group(1), parse_date(dm.group(1))
        if not d:
            continue
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = base + u
        elif not u.startswith("http"):
            u = base.rstrip("/") + "/Scripts/" + u
        out.append((d, u))
    return sorted(set(out))


def import_previous_versions(store, page_url: str, base_id: str, title: str, framework: str = "NBFC", fetch=None) -> list[dict]:
    """Import every dated version listed on an RBI 'Previous Versions' page with its exact in-force window
    (version N is in force from its 'Updated as on' date until the next one), so historical runs use exact text."""
    ensure_schema(store.db)
    fetch = fetch or fetch_robust
    page, _ = fetch(page_url)
    versions = parse_previous_versions(page)
    results = []
    for i, (d, u) in enumerate(versions):
        nxt = versions[i + 1][0].isoformat() if i + 1 < len(versions) else None
        doc_id = f"{base_id}-ASON-{d.isoformat()}"
        try:
            content, _ = fetch(u)
            if not content.lstrip()[:5].startswith(b"%PDF"):
                pdf = find_pdf_link(content)
                if pdf:
                    content, _ = fetch(pdf)
            typ = "pdf" if content.lstrip()[:5].startswith(b"%PDF") else "html"
            res = store.ingest({"id": doc_id, "title": f"{title} (updated as on {d:%d %b %Y})", "url": u, "type": typ,
                                "framework": framework, "effective_override": d.isoformat(), "effective_to": nxt,
                                "kind_override": "consolidated"}, content, origin="RBI previous versions")
        except Exception as e:
            res = {"doc_id": doc_id, "action": "error", "detail": str(e)[:200]}
        results.append({"as_on": d.isoformat(), "in_force_to": nxt, **res})
    store._log(base_id, "previous-versions", f"{len(versions)} dated versions found on {page_url}")
    store.db.commit()
    return results



KIND_NAME = {"base": "Directions", "consolidated": "Directions (consolidated, as amended)", "amendment": "Amendment Directions",
             "draft": "Draft - for public comments (never applied)", "curated": "Curated summary - not an RBI document"}


def set_nomenclature(store, doc_id: str, version: int, official_title: str, ref_no: str, circular_no: str, who: str):
    """SME correction of the RBI name / reference when the document scan could not read them (logged)."""
    ensure_schema(store.db)
    store.db.execute("UPDATE doc_meta SET official_title=?, ref_no=?, circular_no=? WHERE doc_id=? AND version=?",
                     (official_title.strip(), ref_no.strip(), circular_no.strip(), doc_id, version))
    store._log(doc_id, "nomenclature", f"v{version} set by {who}: {official_title[:80]} | {ref_no} | {circular_no}")
    store.db.commit()


def catalogue(store) -> list[dict]:
    """Every document version with RBI's own nomenclature - what management sees as 'what is in the system'."""
    ensure_schema(store.db)
    meta = {(r[0], r[1]): r for r in store.db.execute(
        "SELECT doc_id, version, kind, issued, effective_basis, confidence, official_title, ref_no, circular_no FROM doc_meta")}
    out = []
    for d in store.documents():
        m = meta.get((d["doc_id"], d["version"]))
        curated = d["origin"].startswith("curated")
        kind = "curated" if curated else (m[2] if m else "base")
        status = ("Draft - never applied" if kind == "draft" else "Not an RBI document" if curated else
                  "Superseded" if d["effective_to"] else "Current")
        out.append({"doc_id": d["doc_id"], "version": d["version"],
                    "official_title": (m[6] if m and m[6] else ("" if curated else d["title"])),
                    "ref_no": m[7] if m and m[7] else "", "circular_no": m[8] if m and m[8] else "",
                    "rbi_type": KIND_NAME.get(kind, kind), "kind": kind, "dated": (m[3] if m and m[3] else d.get("issued") or ""),
                    "in_force_from": d["effective_from"], "in_force_to": d["effective_to"] or "", "status": status,
                    "our_label": d["title"], "source": d["url"], "origin": d["origin"], "fetched": d["fetched_at"],
                    "name_read_from_document": bool(m and m[6]), "date_basis": m[4] if m else ""})
    return out
