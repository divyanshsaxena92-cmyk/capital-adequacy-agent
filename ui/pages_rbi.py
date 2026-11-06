"""RBI library - the 'brain' made visible: what RBI text is loaded, which version applies to this run,
what changed, which rules are affected, and what's new on RBI's feeds."""
from __future__ import annotations

import datetime as dt
from html import escape

from capital_agent import rbi_brain

from .page_kit import bars, boxes, card, count, drill, hero, page, table, tag

KIND = {"base": ("Base Directions", "#4F2D7F"), "consolidated": ("Consolidated", "#7B4FC4"), "amendment": ("Amendment", "#169C8F"),
        "draft": ("Draft — never applied", "#A9A6B3"), "curated": ("Curated summary", "#C9B8E0")}


def build(run, rag):
    as_of = run.ds.reporting_date if run is not None else dt.date.today()
    h = rbi_brain.health(rag, as_of)
    drift = rbi_brain.rule_drift(rag, run.rules.rules, run.kb, as_of=as_of) if run is not None else []
    watch = rbi_brain.watch_items(rag)
    changes = rag.db.execute("SELECT doc_id, from_v, to_v, para, change, old_text, new_text, effective FROM changes "
                             "ORDER BY rowid DESC LIMIT 200").fetchall()
    docs = h["documents"]
    cat = {(c["doc_id"], c["version"]): c for c in rbi_brain.catalogue(rag)}
    nm = lambda d: cat.get((d["doc_id"], d["version"]), {})
    short = lambda d: (nm(d).get("ref_no") or ("Curated summary" if d["kind"] == "curated" else d["doc_id"])) + (f" · v{d['version']}" if d["version"] > 1 else "")
    verdict = {"ok": ("Full RBI text in force on the reporting date", "ok"),
               "curated-only": ("Curated summaries only — load RBI text", ""),
               "stale": ("RBI text loaded but not updated recently", "")}[h["verdict"]]
    new_n = sum(w["status"] == "NEW" for w in watch)
    ring = (f'<div style="min-width:230px"><div class="eyebrow" style="margin-bottom:10px">For this run · {as_of:%d %b %Y}</div>'
            f'<div style="font-size:13px;line-height:1.9;color:#EDE6FA">✓ {h["full_text_in_force"]} full RBI text(s) in force<br>'
            f'⏭ {len(h["newer_than_as_of"])} newer version(s) — not applied<br>✎ {h["drafts"]} draft(s) — never applied<br>'
            f'⚑ {sum(d["applies_to_run"] for d in drift)} rule(s) need re-approval</div></div>')
    body = hero("The brain · RBI knowledge base", verdict[0], count(len({d["doc_id"] for d in docs})), " documents",
                [(f"{rag.stats()['chunks_current']:,} paragraphs searchable", ""),
                 (f"Last RBI download: {(h['last_download'] or 'never')[:10]}", ""),
                 (f"Feeds checked: {(h['feeds_last_checked'] or 'never')[:10]}", ""), (f"{new_n} new RBI notice(s)", "")], ring, span="c12")

    how = """<div class="howto">
 <div class="h"><span class="badge2">RECOMMENDED · AUTOMATIC</span><br><b>1 · Update from RBI</b><p>Downloads the official PDFs listed in
 <code>sources.yaml</code> (the consolidated Directions and each Amendment). Unchanged files are skipped; changed files become a new
 dated version, and the changed paragraphs are logged.</p></div>
 <div class="h"><span class="badge2">STAYING CURRENT</span><br><b>2 · Check RBI for new notices</b><p>Reads RBI's official
 notification and press-release feeds, shortlists capital-adequacy items, and indexes the one you pick (it follows the notice to the
 official PDF). Drafts are kept for awareness and never applied.</p></div>
 <div class="h"><span class="badge2">IF DOWNLOADS ARE BLOCKED</span><br><b>3 · PDF, folder or URL</b><p>Save the PDF from rbi.org.in in
 your browser and upload it, or drop it in <code>regulatory_kb/library/</code>. Add any RBI URL as a source. Dates are still read from
 the text and can be corrected by an SME.</p></div>
 <div class="h"><span class="badge2">WHICH RULES APPLY</span><br><b>The reporting date decides</b><p>A 31-Mar run uses text in force on
 31-Mar. A rule issued later — even if already downloaded — applies only to runs dated on or after its effective date, which the brain
 reads from "applicable from …" in the text (issue date ≠ effective date).</p></div></div>"""
    body += card("How the brain gets RBI text", "Use 1 and 2 routinely; 3 when your network blocks rbi.org.in", how, "c12", d=.08)

    stages = [("Sources", f"{len(rag.documents())} versions held", "ok"),
              ("Download", "OK" if h["last_download"] else "never run", "ok" if h["last_download"] else "warn"),
              ("Dates & kind", f"{sum(1 for d in docs if d.get('confidence') == 'high')} high-confidence dates", "ok"),
              ("Versions & diff", f"{h['changes_logged']} paragraph changes logged", "ok"),
              ("Rule drift", f"{len(drift)} citation(s) affected", "warn" if any(d['applies_to_run'] for d in drift) else "ok"),
              ("As-of retrieval", f"{h['full_text_in_force']} full text(s) for {as_of:%d %b %Y}", "ok" if h["full_text_in_force"] else "warn"),
              ("Watcher", f"{new_n} new notice(s)" + (" · not checked in 14+ days (feeds keep only recent items)" if h["feeds_stale"] else ""),
               "warn" if (new_n or h["feeds_stale"]) else "ok")]
    pipe = "".join(f'<div class="p"><span class="st" style="color:{"#2E8B5E" if s == "ok" else "#C7781A"}">{"● OK" if s == "ok" else "● ATTENTION"}</span>'
                   f'<b>{i + 1}. {escape(n)}</b><small>{escape(t)}</small></div>' for i, (n, t, s) in enumerate(stages))
    body += card("Pipeline status", "Each stage of keeping the brain current", f'<div class="pipe">{pipe}</div>', "c12", d=.14)

    # ---------------- version timeline
    def d_(s):
        try:
            return dt.date.fromisoformat(str(s)[:10])
        except ValueError:
            return None
    starts = [d_(d["effective_from"]) for d in docs if d_(d["effective_from"])]
    lo = min(starts + [as_of]) - dt.timedelta(days=30) if starts else as_of - dt.timedelta(days=365)
    hi = max(starts + [as_of, dt.date.today()]) + dt.timedelta(days=45)
    span = (hi - lo).days or 1
    px = lambda d: max(0.0, min(100.0, (d - lo).days / span * 100))
    lanes = []
    for d in sorted(docs, key=lambda x: (x["doc_id"], x["version"])):
        k, col = KIND.get(d["kind"], (d["kind"], "#7B4FC4"))
        s0 = d_(d["effective_from"]) or lo
        e0 = d_(d["effective_to"]) or hi
        stripe = "repeating-linear-gradient(45deg,#BDB9C6 0 6px,#D5D2DC 6px 12px)" if d["kind"] == "draft" else col
        lanes.append(f'<div class="lane"><span class="nm" title="{escape(nm(d).get("official_title") or d["title"])}">{escape(short(d))}</span>'
                     f'<div class="track"><span class="bar" data-drill="doc-{escape(d["doc_id"])}-{d["version"]}" style="left:{px(s0):.2f}%;'
                     f'width:{max(px(e0) - px(s0), 1.2):.2f}%;background:{stripe}">{escape(k)}</span></div></div>')
    ticks = []
    t = dt.date(lo.year, lo.month, 1)
    while t <= hi:
        if t.month in (1, 4, 7, 10):
            ticks.append(f'<span style="left:{px(t):.2f}%">{t:%b %Y}</span>')
        t = (t.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    tl = (f'<div class="tlx">{"".join(lanes) or "<div class=s>No documents yet.</div>"}'
          f'<div class="ax"><div></div><div>{"".join(ticks)}</div></div>'
          f'<div style="position:absolute;top:0;bottom:22px;left:calc(234px + (100% - 234px) * {px(as_of) / 100:.4f})" class="now"><span>Reporting date {as_of:%d %b %Y}</span></div></div>')
    body += card("Version timeline", "Each bar = when that text is in force · the red line is this run's reporting date", tl, "c8", d=.2)

    applied = [d for d in docs if d["in_force_on_date"]]
    newer = h["newer_than_as_of"]
    def _nm_line(d, colour=""):
        c = nm(d)
        title = c.get("official_title") or ("Curated summary (not an RBI document)" if d["kind"] == "curated" else d["title"])
        ref = " · ".join(x for x in (c.get("ref_no"), c.get("circular_no")) if x)
        noref = ("paraphrased summary used until RBI text is loaded" if d["kind"] == "curated" else "reference not read - see document details")
        return (f'<div class="ov-q" style="margin-top:8px{";border-color:" + colour if colour else ""}"><b>{escape(title[:120])}</b>'
                f'<br><span class="mono" style="font-size:11px">{escape(ref or noref)}</span>'
                f' · {escape(c.get("rbi_type", ""))} · in force from {escape(d["effective_from"])}</div>')
    lst = "".join(_nm_line(d) for d in applied[:6])
    nw = "".join(_nm_line(d, "#169C8F") for d in newer[:6])
    body += card("What applies to this run", f"Text in force on {as_of:%d %b %Y}",
                 f'<div class="s" style="font-weight:650;color:var(--ink)">Applied ({len(applied)})</div>{lst or "<div class=s>Curated summaries only.</div>"}'
                 f'<div class="s" style="font-weight:650;color:var(--ink);margin-top:16px">Newer — not applied ({len(newer)})</div>{nw or "<div class=s>None.</div>"}',
                 "c4", d=.26)

    # ---------------- drift + changes
    drows = [f'<tr data-app="{"yes" if x["applies_to_run"] else "no"}"><td class="mono">{escape(x["rule_id"])}</td><td>{escape(x["rule"][:46])}</td>'
             f'<td>{escape(x["para"])}</td><td>{escape(x["what"])}</td><td>{escape(str(x["effective"]))}</td>'
             f'<td>{tag("Applies to this run", "rgba(214,69,96,.13)", "#D64560") if x["applies_to_run"] else tag("Later date", "var(--chip)", "var(--mut)")}</td></tr>'
             for x in drift]
    body += card("Rule-drift alerts", "Approved rules whose RBI paragraph changed — SME re-approval needed",
                 table("dr", [("Rule", "txt", ""), ("Title", "txt", ""), ("Para", "txt", ""), ("Change", "txt", ""), ("Effective", "txt", ""), ("For this run", "txt", "")],
                       drows, [("app", [("All", "all"), ("Applies now", "yes"), ("Later", "no")])]) if drows else
                 '<div class="s">No approved rule cites a paragraph that RBI has changed.</div>', "c12", d=.3)
    crows, tpls = [], []
    for i, (doc_id, fv, tv, para, ch, old, new, eff) in enumerate(changes):
        key = f"chg-{i}"
        crows.append(f'<tr data-drill="{key}" data-ch="{ch}"><td class="mono">{escape(doc_id)}</td><td>v{fv} → v{tv}</td><td>{escape(para)}</td>'
                     f'<td>{tag(ch.title(), "rgba(123,79,196,.12)", "#7B4FC4")}</td><td>{escape(str(eff))}</td></tr>')
        tpls.append(drill(key, f"{doc_id} · para {para} {ch}", f"v{fv} → v{tv} · effective {eff}",
                          f'<div class="ov-p"><b>Before</b></div><div class="ov-q">{escape(old or "—")}</div>'
                          f'<div class="ov-p"><b>After</b></div><div class="ov-q" style="border-color:#2E8B5E">{escape(new or "—")}</div>'))
    body += card("Change log", "Paragraph-level differences between RBI versions · click to compare",
                 table("ch", [("Document", "txt", ""), ("Versions", "txt", ""), ("Para", "txt", ""), ("Change", "txt", ""), ("Effective", "txt", "")],
                       crows, [("ch", [("All", "all"), ("Changed", "changed"), ("Added", "added"), ("Removed", "removed")])]) if crows else
                 '<div class="s">No document has changed since it was first indexed.</div>', "c6", d=.34)

    wrows = [f'<tr data-wk="{escape(w["kind"])}" data-ws="{escape(w["status"])}"><td>{escape(w["pub_date"][:16])}</td><td title="{escape(w["title"])}">{escape(w["title"][:70])}</td>'
             f'<td>{tag(w["kind"].title(), "var(--chip)", "#A9A6B3" if w["kind"] == "draft" else "#169C8F")}</td><td>{escape(w["status"].title())}</td></tr>'
             for w in watch[:60]]
    body += card("RBI watcher", "Capital-adequacy items from RBI's official feeds · index them with the controls below",
                 table("wt", [("Published", "txt", ""), ("Notice", "txt", ""), ("Kind", "txt", ""), ("Status", "txt", "")], wrows,
                       [("ws", [("All", "all"), ("New", "NEW"), ("Possible", "POSSIBLE"), ("Indexed", "INDEXED"), ("Failed", "FAILED")])]) if wrows else
                 '<div class="s">Not checked yet — use "Check RBI for new notices" below.</div>', "c6", d=.38)

    dr2 = []
    for c in sorted(cat.values(), key=lambda x: (x["kind"] == "curated", x["in_force_from"])):
        key = f"doc-{c['doc_id']}-{c['version']}"
        stc = {"Current": ("rgba(46,139,94,.12)", "#2E8B5E"), "Superseded": ("var(--chip)", "var(--mut)"),
               "Draft - never applied": ("rgba(212,139,18,.14)", "#C27C10"), "Not an RBI document": ("rgba(123,79,196,.12)", "#7B4FC4")}[c["status"]]
        title = c["official_title"] or ("Curated summary (not an RBI document)" if c["kind"] == "curated" else c["our_label"])
        wrap = 'style="white-space:normal;max-width:none;line-height:1.4"'
        dr2.append(f'<tr data-drill="{key}" data-st="{escape(c["status"])}"><td {wrap} title="{escape(title)}"><b>{escape(title)}</b></td>'
                   f'<td class="mono">{escape(c["ref_no"] or "—")}</td><td class="mono" style="white-space:normal;max-width:220px;word-break:break-all">{escape(c["circular_no"] or "—")}</td>'
                   f'<td>{escape(c["rbi_type"].split(" (")[0].split(" -")[0])}</td><td>{escape(str(c["dated"])[:10])}</td>'
                   f'<td>{escape(c["in_force_from"])}</td><td>{escape(c["in_force_to"] or "—")}</td><td>{tag(c["status"], *stc)}</td></tr>')
        tpls.append(drill(key, title, f'{c["rbi_type"]} · {c["status"]}',
                          boxes([("RBI reference", c["ref_no"] or ("n/a - not an RBI document" if c["kind"] == "curated" else "not read")),
                                 ("Circular number", c["circular_no"] or ("n/a" if c["kind"] == "curated" else "not read")),
                                 ("Dated", str(c["dated"])[:10] or "—"), ("In force from", c["in_force_from"]), ("In force to", c["in_force_to"] or "current"),
                                 ("Version in system", f"v{c['version']}")])
                          + f'<div class="ov-p"><b>Name source:</b> {"not an RBI document - a paraphrased summary of the Directions, used for search until the official text is loaded" if c["kind"] == "curated" else ("read from the RBI document itself" if c["name_read_from_document"] else "taken from sources.yaml (not found in the text) - confirm")}</div>'
                          + f'<div class="ov-p"><b>Date basis:</b> {escape(c["date_basis"] or "—")}</div>'
                          + f'<div class="ov-p"><b>Internal ID:</b> <span class="mono">{escape(c["doc_id"])}</span> · <b>Origin:</b> {escape(c["origin"])} · <b>Fetched:</b> {escape(c["fetched"])}</div>'
                          + (f'<div class="ov-p"><b>Source:</b> {escape(c["source"])}</div>' if c["source"] else "")
                          + '<div class="ov-p" style="color:var(--mut)">Name or reference wrong? Correct it with "Correct the RBI name / reference" below (logged).</div>'))
    reg_card = card("What's in the system — RBI register", "Official RBI names, references and status of every document the brain holds",
                 table("dc", [("Official RBI name", "txt", ""), ("RBI reference", "txt", ""), ("Circular no.", "txt", ""), ("Type", "txt", ""),
                              ("Dated", "txt", ""), ("In force from", "txt", ""), ("To", "txt", ""), ("Status", "txt", "")], dr2,
                       [("st", [("All", "all"), ("Current", "Current"), ("Superseded", "Superseded"), ("Draft", "Draft - never applied"),
                                ("Curated", "Not an RBI document")])]), "c12", d=.14)
    if h["recent_errors"]:
        errs = "".join(f'<div class="ov-q" style="border-color:#D64560"><b>{escape(e[1])}</b> · {escape(e[0])}<br>{escape(e[2])}</div>' for e in h["recent_errors"])
        body += card("Recent download problems", "What went wrong and how to fix it", errs, "c12", d=.46)
    cut = body.index("</section>") + len("</section>")          # register directly under the brain status
    body = body[:cut] + reg_card + body[cut:]
    return page("RBI library · the brain", f"As at {as_of:%d %b %Y}", body, "".join(tpls)), {}
